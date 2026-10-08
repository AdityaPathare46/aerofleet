"""Fleet plan deconfliction: make a set of planned missions safe against each other before anyone flies.

Each mission (a parsed `.waypoints` plan plus a launch time) is turned into a position-over-time
trajectory at stated speeds, every pair is checked on a common clock, and conflicts are removed by the
cheapest change that works: a launch delay, or — only when vertical separation is allowed — a different
cruise height. The result is then re-checked from scratch, so "resolved" is measured, not assumed.

Separation rule. By default a conflict is two airborne drones closer than `h_sep_m` horizontally,
whatever their heights — the same rule as the CBF gate and the live conflict forecast. Passing
`v_sep_m` switches to the usual either/or rule (far enough apart sideways OR in height); that is an
operating decision for the fleet and is recorded in the result.

What this does not promise: separation holds only if each drone flies its plan at the planned speeds
and launches at its scheduled time. Planned-versus-flown reconciliation measures how far real flights
stray. Legs are straight lines; wind is ignored.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from aerofleet.assurance.reconcile import M_PER_DEG, Plan

CRUISE_MPS, CLIMB_MPS, DESCENT_MPS = 12.0, 3.0, 2.0      # same figures the simulator and live feed use
STEP_S = 1.0
AIRBORNE_M = 0.5
ALTITUDE_CHANGE_COST_S = 20.0                             # a height change is preferred over delays longer than this


@dataclass(frozen=True)
class Mission:
    id: str
    plan: Plan
    start_s: float = 0.0
    priority: int = 0                                     # higher keeps its plan; lower is moved

    def with_altitude(self, alt_m: float) -> "Mission":
        path = [(la, lo, alt_m if a > AIRBORNE_M else a) for la, lo, a in self.plan.path]
        return replace(self, plan=Plan(self.plan.home, path, self.plan.notes))


def _trajectory(m: Mission, origin: Tuple[float, float]) -> Tuple[int, np.ndarray]:
    """(first grid index, [x, y, alt] per STEP_S) from launch to touchdown; NaN while on the ground.
    Launch times are placed on the STEP_S grid."""
    cos = math.cos(math.radians(origin[0]))
    pts = [((lo - origin[1]) * M_PER_DEG * cos, (la - origin[0]) * M_PER_DEG, a) for la, lo, a in m.plan.path]
    knots_t, t = [0.0], 0.0
    for (ax, ay, aa), (bx, by, ba) in zip(pts, pts[1:]):
        vertical = (ba - aa) / CLIMB_MPS if ba >= aa else (aa - ba) / DESCENT_MPS
        t += max(math.hypot(bx - ax, by - ay) / CRUISE_MPS, vertical, 1e-3)
        knots_t.append(t)
    times = np.arange(0.0, knots_t[-1] + STEP_S, STEP_S)
    arr = np.array(pts)
    xyz = np.stack([np.interp(times, knots_t, arr[:, k]) for k in range(3)], axis=1)
    xyz[xyz[:, 2] <= AIRBORNE_M] = np.nan                 # on the ground: not in the airspace
    return int(round(m.start_s / STEP_S)), xyz


def _pair(a: Tuple[int, np.ndarray], b: Tuple[int, np.ndarray], h_sep: float, v_sep: Optional[float]):
    """Worst moment between two trajectories, or None when they never conflict: (grid index, h, v, seconds)."""
    lo, hi = max(a[0], b[0]), min(a[0] + len(a[1]), b[0] + len(b[1]))
    if hi <= lo:
        return None
    pa, pb = a[1][lo - a[0]:hi - a[0]], b[1][lo - b[0]:hi - b[0]]
    h = np.hypot(pa[:, 0] - pb[:, 0], pa[:, 1] - pb[:, 1])
    v = np.abs(pa[:, 2] - pb[:, 2])
    bad = h < h_sep                                       # NaN (either on the ground) compares False
    if v_sep is not None:
        bad &= v < v_sep
    if not bad.any():
        return None
    k = int(np.nanargmin(np.where(bad, h, np.nan)))
    return lo + k, float(h[k]), float(v[k]), float(bad.sum() * STEP_S)


def find_conflicts(missions: Sequence[Mission], h_sep_m: float = 15.0, v_sep_m: Optional[float] = None) -> List[Dict[str, Any]]:
    if len(missions) < 2:
        return []
    origin = missions[0].plan.home
    trajs = [_trajectory(m, origin) for m in missions]
    out = []
    for i in range(len(missions)):
        for j in range(i + 1, len(missions)):
            hit = _pair(trajs[i], trajs[j], h_sep_m, v_sep_m)
            if hit:
                k, h, v, dur = hit
                out.append({"a": missions[i].id, "b": missions[j].id, "t_s": round(k * STEP_S, 1), "horizontal_m": round(h, 1),
                            "vertical_m": round(v, 1), "duration_s": dur})
    return sorted(out, key=lambda c: (c["t_s"], c["a"], c["b"]))


def deconflict(missions: Sequence[Mission], h_sep_m: float = 15.0, v_sep_m: Optional[float] = None,
               max_delay_s: float = 300.0, delay_step_s: float = 10.0,
               altitude_bands_m: Sequence[float] = (40.0, 60.0, 80.0, 100.0)) -> Dict[str, Any]:
    """Greedy and deterministic: missions are fixed one at a time (highest priority, then earliest launch,
    then id); each later one takes the cheapest change that clears every mission already fixed."""
    ids = [m.id for m in missions]
    if len(set(ids)) != len(ids):
        raise ValueError("Mission ids must be unique")
    before = find_conflicts(missions, h_sep_m, v_sep_m)
    order = sorted(missions, key=lambda m: (-m.priority, m.start_s, m.id))
    origin = missions[0].plan.home
    fixed: List[Mission] = []
    fixed_trajs: List[Tuple[int, np.ndarray]] = []
    changes: List[Dict[str, Any]] = []
    unresolved: List[str] = []
    for m in order:
        options: List[Tuple[float, float, Optional[float], Mission]] = [(0.0, 0.0, None, m)]
        if v_sep_m is not None:
            options += [(ALTITUDE_CHANGE_COST_S, 0.0, band, m.with_altitude(band)) for band in altitude_bands_m
                        if abs(band - m.plan.max_alt_m) > 1e-6]
        steps = int(max_delay_s // delay_step_s)
        options += [(d, d, None, replace(m, start_s=m.start_s + d)) for d in (delay_step_s * k for k in range(1, steps + 1))]
        chosen = None
        for cost, delay, band, cand in sorted(options, key=lambda o: (o[0], o[1])):
            traj = _trajectory(cand, origin)
            # only this candidate against the missions already fixed: an earlier unresolved pair must not block it
            if not any(_pair(traj, other, h_sep_m, v_sep_m) for other in fixed_trajs):
                chosen = (delay, band, cand)
                fixed_trajs.append(traj)
                break
        if chosen is None:
            unresolved.append(m.id)
            fixed.append(m)
            fixed_trajs.append(_trajectory(m, origin))
            continue
        delay, band, cand = chosen
        fixed.append(cand)
        if delay or band is not None:
            changes.append({"id": m.id, "delay_s": delay, "new_altitude_m": band, "old_altitude_m": m.plan.max_alt_m if band is not None else None})
    by_id = {m.id: m for m in fixed}
    result = [by_id[i] for i in ids]
    after = find_conflicts(result, h_sep_m, v_sep_m)
    return {
        "rule": {"h_sep_m": h_sep_m, "v_sep_m": v_sep_m, "vertical_separation_allowed": v_sep_m is not None,
                 "cruise_mps": CRUISE_MPS, "climb_mps": CLIMB_MPS, "descent_mps": DESCENT_MPS},
        "before": before, "after": after, "changes": sorted(changes, key=lambda c: c["id"]), "unresolved": sorted(unresolved),
        "resolved": not after,
        "schedule": [{"id": m.id, "launch_at_s": m.start_s, "cruise_altitude_m": m.plan.max_alt_m} for m in result],
        "missions": result,
        "note": "Separation holds only if every drone launches on schedule and flies its plan at the planned speeds.",
    }
