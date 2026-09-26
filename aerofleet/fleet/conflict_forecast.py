"""Look-ahead separation check over the swarm's planned trajectories.

The live feed's pairs answer "who is too close *now*". This answers "who
*will* be too close in the next couple of minutes if everyone keeps flying
their plan" — the strategic-deconfliction question a UTM operator actually
needs answered in time to act. Every SIMULATED flight is a known function
of time (flight_progress.PlannedFlight), so each pair's closest point of
approach can be found by sampling both trajectories on a common clock.

Same separation rule as the CBF gate's min_separation constraint:
horizontal distance only (vertical is reported, never used to excuse a
conflict) — a forecast that used a different rule than the gate would
flag things the gate never would, or miss things it would. A drone on the
ground (not yet climbing, or landed) is not in the airspace and is skipped.

Deterministic, no LLM, sub-second for tens of drones. LIVE (MAVLink)
drones have no plan registered and so are not forecast — the response says
which drones were covered.
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

from aerofleet.fleet.flight_progress import LANDED, PlannedFlight

HORIZON_S = 120.0
STEP_S = 2.0
ON_GROUND_M = 0.5

_M_PER_DEG_LAT = 111_320.0


_Sample = Tuple[float, float, float, float, float]


def _lerp(p: _Sample, q: _Sample, u: float) -> _Sample:
    return tuple(p[j] + (q[j] - p[j]) * u for j in range(5))  # type: ignore[return-value]


def _closest_approach(ta: List[Optional[_Sample]], tb: List[Optional[_Sample]]):
    """Minimum horizontal distance between two sampled tracks, solved exactly within each
    sampling interval (both drones move linearly between samples), so two drones closing
    at 24 m/s can't slip between 2 s samples unseen. Returns (fractional step index,
    horizontal metres, a's sample, b's sample) or None if they're never airborne together."""
    best = None
    for k in range(len(ta)):
        pa, pb = ta[k], tb[k]
        if pa is None or pb is None:
            continue
        cand = [(float(k), pa, pb)]
        if k + 1 < len(ta) and ta[k + 1] is not None and tb[k + 1] is not None:
            qa, qb = ta[k + 1], tb[k + 1]
            r0 = (pa[0] - pb[0], pa[1] - pb[1])
            dr = ((qa[0] - qb[0]) - r0[0], (qa[1] - qb[1]) - r0[1])
            dd = dr[0] ** 2 + dr[1] ** 2
            if dd > 1e-9:
                u = min(max(-(r0[0] * dr[0] + r0[1] * dr[1]) / dd, 0.0), 1.0)
                if 0.0 < u < 1.0:
                    cand.append((k + u, _lerp(pa, qa, u), _lerp(pb, qb, u)))
        for t_idx, sa, sb in cand:
            h = math.hypot(sa[0] - sb[0], sa[1] - sb[1])
            if best is None or h < best[1] - 1e-9:
                best = (t_idx, h, sa, sb)
    return best


def forecast_conflicts(
    flights: Dict[str, PlannedFlight],
    now: float,
    min_separation_m: float,
    watch_band_m: float,
    horizon_s: float = HORIZON_S,
    step_s: float = STEP_S,
) -> List[Dict]:
    """Pairs whose separation margin over (now, now + horizon] drops below
    `watch_band_m` at some future moment, one entry per pair at its closest
    point of approach, soonest first. `severity` is CONFLICT when the
    predicted margin is negative (the gate's constraint would be violated),
    else WATCH. Pairs already at their closest right now are left to the
    live pairs list — this only reports what is still ahead."""
    if len(flights) < 2:
        return []
    steps = int(horizon_s / step_s)
    times = [now + k * step_s for k in range(steps + 1)]
    ids = sorted(flights)

    ref_lat = sum(f.path[0][0] for f in flights.values()) / len(flights)
    m_per_deg_lon = _M_PER_DEG_LAT * math.cos(math.radians(ref_lat))

    # Per drone, per step: (east_m, north_m, alt_m, lat, lon) or None when on the ground.
    # Local flat projection: at a few km its error is far below a metre.
    tracks: Dict[str, List[Optional[Tuple[float, float, float, float, float]]]] = {}
    for d in ids:
        track = []
        for t in times:
            s = flights[d].state_at(t)
            if s.phase == LANDED or s.altitude_m < ON_GROUND_M:
                track.append(None)
            else:
                track.append((s.lon * m_per_deg_lon, s.lat * _M_PER_DEG_LAT, s.altitude_m, s.lat, s.lon))
        tracks[d] = track

    out: List[Dict] = []
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            cpa = _closest_approach(tracks[a], tracks[b])
            if cpa is None:
                continue
            t_idx, horizontal, pa, pb = cpa
            if t_idx <= 1e-6:
                continue
            margin = horizontal - min_separation_m
            if margin >= watch_band_m:
                continue
            out.append({
                "a": a, "b": b,
                "t_s": round(t_idx * step_s, 1),
                "horizontal_m": round(horizontal, 1),
                "vertical_m": round(abs(pa[2] - pb[2]), 1),
                "separation_margin_m": round(margin, 1),
                "severity": "CONFLICT" if margin < 0 else "WATCH",
                "a_at": [round(pa[3], 6), round(pa[4], 6), round(pa[2], 1)],
                "b_at": [round(pb[3], 6), round(pb[4], 6), round(pb[2], 1)],
            })
    out.sort(key=lambda c: (c["severity"] != "CONFLICT", c["t_s"]))
    return out
