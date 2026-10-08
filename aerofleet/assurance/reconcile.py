"""Planned versus flown: did the aircraft fly the mission that was approved?

Takes the approved mission file (QGC WPL 110 `.waypoints`, what Mission Planner / QGroundControl and
AeroFleet's own export use) and a flight log's track, and measures, for every logged position, how far
it was from the planned path horizontally and vertically. Everything is geometry — no model.

What counts as a deviation is set by two tolerances with plain defaults (30 m sideways, 15 m in height,
sustained for 3 s). They are operating choices, not regulatory limits: pass the fleet's own values.

Known simplifications, stated in every report: the path between waypoints is taken as a straight line;
RETURN_TO_LAUNCH is modelled as flying back to home at the last planned height (the real height depends
on the aircraft's RTL altitude setting); commands other than takeoff / waypoint / land / RTL are ignored.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

WAYPOINT, RTL, LAND, TAKEOFF = 16, 20, 21, 22
PILOT_MODES = {"STABILIZE", "ALT_HOLD", "LOITER", "POSHOLD", "ACRO", "SPORT", "DRIFT", "FLIP", "MANUAL", "ALTCTL", "POSCTL"}
M_PER_DEG = 111_320.0


class PlanError(ValueError):
    pass


@dataclass
class Plan:
    home: Tuple[float, float]
    path: List[Tuple[float, float, float]]          # (lat, lon, height above home m), in flying order
    notes: List[str]

    @property
    def max_alt_m(self) -> float:
        return max(p[2] for p in self.path)


def parse_waypoints(text: str) -> Plan:
    lines = [l for l in text.splitlines() if l.strip()]
    if not lines or not lines[0].startswith("QGC WPL"):
        raise PlanError("Not a mission file — expected a .waypoints file starting with 'QGC WPL 110'")
    rows = []
    for n, line in enumerate(lines[1:], start=2):
        parts = line.split()
        if len(parts) < 11:
            raise PlanError(f"Line {n} of the mission file has {len(parts)} fields; 12 are expected")
        try:
            rows.append((int(parts[3]), float(parts[8]), float(parts[9]), float(parts[10])))
        except ValueError:
            raise PlanError(f"Line {n} of the mission file is not numeric") from None
    if len(rows) < 2:
        raise PlanError("The mission file has no flight commands after the home position")
    home = (rows[0][1], rows[0][2])
    path: List[Tuple[float, float, float]] = [(home[0], home[1], 0.0)]
    notes: List[str] = []
    for cmd, lat, lon, alt in rows[1:]:
        here = (lat, lon) if (abs(lat) > 1e-7 or abs(lon) > 1e-7) else (path[-1][0], path[-1][1])
        if cmd == TAKEOFF:
            path.append((path[-1][0], path[-1][1], alt))
        elif cmd == WAYPOINT:
            path.append((here[0], here[1], alt))
        elif cmd == LAND:
            path.append((here[0], here[1], 0.0))
        elif cmd == RTL:
            path += [(home[0], home[1], path[-1][2]), (home[0], home[1], 0.0)]
            notes.append("Return-to-launch is modelled at the last planned height; the real height depends on the RTL altitude setting")
        else:
            notes.append(f"Mission command {cmd} is not modelled and was ignored")
    if len(path) < 3:
        raise PlanError("The mission file has no waypoints to compare with")
    return Plan(home, path, notes)


def _xy(lat: float, lon: float, origin: Tuple[float, float]) -> Tuple[float, float]:
    return ((lon - origin[1]) * M_PER_DEG * math.cos(math.radians(origin[0])), (lat - origin[0]) * M_PER_DEG)


def _deviation(p: Tuple[float, float], alt: float, segs: Sequence[Tuple]) -> Tuple[float, float]:
    """(horizontal m, vertical m) to the nearest planned segment."""
    best = (float("inf"), 0.0)
    for (ax, ay, aalt), (bx, by, balt) in segs:
        dx, dy = bx - ax, by - ay
        length2 = dx * dx + dy * dy
        if length2 < 1.0:                                   # a climb or descent on the spot
            h = math.hypot(p[0] - ax, p[1] - ay)
            lo, hi = min(aalt, balt), max(aalt, balt)
            v = 0.0 if lo <= alt <= hi else min(abs(alt - lo), abs(alt - hi))
        else:
            u = max(0.0, min(1.0, ((p[0] - ax) * dx + (p[1] - ay) * dy) / length2))
            h = math.hypot(p[0] - (ax + u * dx), p[1] - (ay + u * dy))
            v = abs(alt - (aalt + u * (balt - aalt)))
        if (h, v) < best:
            best = (h, v)
    return best


def _episodes(track, flags: List[bool], values: List[float], min_s: float, kind: str) -> List[Dict[str, Any]]:
    out, start = [], None
    for i in range(len(track) + 1):
        on = i < len(track) and flags[i]
        if on and start is None:
            start = i
        elif not on and start is not None:
            dur = track[i - 1][0] - track[start][0]
            if dur >= min_s:
                worst = max(range(start, i), key=lambda k: values[k])
                out.append({"kind": kind, "start_s": round(track[start][0] - track[0][0], 1), "duration_s": round(dur, 1),
                            "max_m": round(values[worst], 1), "lat": round(track[worst][1], 6), "lon": round(track[worst][2], 6)})
            start = None
    return out


def reconcile(plan: Plan, track: Sequence[Tuple[float, float, float, float]], modes: Sequence[Tuple[float, str]] = (),
              corridor_m: float = 30.0, altitude_tol_m: float = 15.0, min_duration_s: float = 3.0,
              zone_at: Optional[Callable[[float, float], str]] = None) -> Dict[str, Any]:
    if len(track) < 2:
        raise PlanError("The flight log has too few positions to compare")
    pts = [(*_xy(la, lo, plan.home), alt) for la, lo, alt in plan.path]
    segs = list(zip(pts, pts[1:]))
    horiz, vert = [], []
    for _, lat, lon, alt in track:
        h, v = _deviation(_xy(lat, lon, plan.home), alt, segs)
        horiz.append(h)
        vert.append(v)
    episodes = (_episodes(track, [h > corridor_m for h in horiz], horiz, min_duration_s, "off_route")
                + _episodes(track, [v > altitude_tol_m for v in vert], vert, min_duration_s, "off_altitude"))
    if zone_at is not None:
        red = [zone_at(lat, lon) == "RED" for _, lat, lon, _ in track]
        episodes += _episodes(track, red, [0.0] * len(track), 0.0, "in_no_fly_zone")
    episodes.sort(key=lambda e: e["start_s"])

    t0, t_end = track[0][0], track[-1][0]
    seen_auto, manual = False, []
    for i, (t, mode) in enumerate(modes):
        name = mode.upper()
        if name in ("AUTO", "MISSION"):
            seen_auto = True
        elif seen_auto and name in PILOT_MODES:
            until = modes[i + 1][0] if i + 1 < len(modes) else t_end
            manual.append({"mode": name, "start_s": round(t - t0, 1), "duration_s": round(max(0.0, until - t), 1)})

    ordered = sorted(horiz)
    outside = sum(e["duration_s"] for e in episodes if e["kind"] == "off_route")
    return {
        "verdict": "DEVIATED" if episodes or manual else "CONFORMED",
        "tolerances": {"corridor_m": corridor_m, "altitude_m": altitude_tol_m, "min_duration_s": min_duration_s},
        "horizontal_m": {"max": round(ordered[-1], 1), "p95": round(ordered[int(0.95 * (len(ordered) - 1))], 1),
                         "median": round(ordered[len(ordered) // 2], 1)},
        "vertical_m": {"max": round(max(vert), 1)},
        "max_height_m": {"flown": round(max(p[3] for p in track), 1), "planned": round(plan.max_alt_m, 1)},
        "time_off_route_s": round(outside, 1), "flight_s": round(t_end - t0, 1), "points": len(track),
        "episodes": episodes, "manual_control": manual, "notes": list(plan.notes),
    }
