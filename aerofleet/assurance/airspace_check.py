"""Pre-flight route check: does a planned mission stay out of restricted airspace and under the height limit?

India's Drone Rules 2021 divide airspace into red zones (no flying without central government permission), yellow
zones (air traffic control permission needed) and green zones (no permission needed up to 120 m / 400 ft above
ground). This module walks each planned route in small steps and reports where it enters a red or yellow zone and
where it is planned above 120 m.

What it can and cannot say: the zones are AeroFleet's approximations from public rule distances around known sites
(aerofleet/city/restricted_sites.py: airports, military and strategic sites in Pune and Mumbai), not the official
Digital Sky map, which cannot be queried automatically. A route reported clear here must still be checked on Digital
Sky before flight, and a route outside the supported cities is reported as unchecked, never as clear. Heights are the
plan's heights above the take-off point, not above the ground under the drone.
"""
from __future__ import annotations

import math
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

LEGAL_CEILING_M = 120.0           # Drone Rules 2021: green-zone limit without permission (400 ft)
STEP_M = 25.0                     # spacing of the points checked along each leg
CLEAR, NEEDS_PERMISSION, NOT_PERMITTED, UNCHECKED = "CLEAR", "NEEDS_PERMISSION", "NOT_PERMITTED", "UNCHECKED"
NOTE = ("Zones are approximations from the public distances in India's Drone Rules 2021 around known airports and "
        "military or strategic sites, not the official Digital Sky map. Check every route on Digital Sky before flight.")


def _metres(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * 6_371_000 * math.asin(math.sqrt(h))


def _samples(path: Sequence[Tuple[float, float, float]]):
    """(distance along the route m, lat, lon, height m) every STEP_M along each leg, ends included."""
    along = 0.0
    yield 0.0, path[0][0], path[0][1], path[0][2]
    for (la1, lo1, h1), (la2, lo2, h2) in zip(path, path[1:]):
        leg = _metres((la1, lo1), (la2, lo2))
        n = max(1, int(leg // STEP_M))
        for k in range(1, n + 1):
            f = k / n
            yield along + f * leg, la1 + f * (la2 - la1), lo1 + f * (lo2 - lo1), h1 + f * (h2 - h1)
        along += leg


def check_route(mission_id: str, path: Sequence[Tuple[float, float, float]],
                zone_at: Optional[Callable[[float, float], Optional[Dict[str, Any]]]]) -> Dict[str, Any]:
    """`zone_at(lat, lon)` gives the red or yellow zone at a point ({"id", "color", "name"}) or None; None for the
    whole function means there is no zone data for this place."""
    pts = list(_samples(path))
    length = pts[-1][0]
    findings: List[Dict[str, Any]] = []
    entered: Dict[str, Dict[str, Any]] = {}
    if zone_at is not None:
        for d, la, lo, _h in pts:
            z = zone_at(la, lo)
            if z and z["id"] not in entered:
                entered[z["id"]] = {"kind": "zone", "color": z["color"], "zone": z["name"], "at_m": round(d),
                                    "lat": round(la, 6), "lon": round(lo, 6)}
            if z and z["id"] in entered:
                entered[z["id"]]["until_m"] = round(d)
        findings += list(entered.values())
    high = [(d, la, lo, h) for d, la, lo, h in pts if h > LEGAL_CEILING_M]
    if high:
        findings.append({"kind": "ceiling", "max_m": round(max(h for *_, h in high), 1), "at_m": round(high[0][0]),
                         "until_m": round(high[-1][0]), "lat": round(high[0][1], 6), "lon": round(high[0][2], 6)})
    colors = {f["color"] for f in findings if f["kind"] == "zone"}
    if "RED" in colors or high:
        verdict = NOT_PERMITTED
    elif "YELLOW" in colors:
        verdict = NEEDS_PERMISSION
    elif zone_at is None:
        verdict = UNCHECKED
    else:
        verdict = CLEAR
    return {"id": mission_id, "verdict": verdict, "length_m": round(length), "max_height_m": round(max(p[3] for p in pts), 1),
            "findings": sorted(findings, key=lambda f: f["at_m"]), "path": [[round(la, 6), round(lo, 6), round(h, 1)] for la, lo, h in path]}


def explain(r: Dict[str, Any]) -> str:
    """One plain sentence per mission, for the screen and the record."""
    if r["verdict"] == UNCHECKED:
        return "No airspace data for this location in AeroFleet: not checked. Use Digital Sky."
    parts = []
    for f in r["findings"]:
        if f["kind"] == "zone":
            what = "red zone (flying not permitted)" if f["color"] == "RED" else "yellow zone (needs air traffic control permission)"
            where = "from take-off" if f["at_m"] < 50 else f"{f['at_m'] / 1000:.1f} km into the route"
            parts.append(f"is in the {what} of {f['zone']} {where}")
        else:
            parts.append(f"is planned up to {f['max_m']:g} m, above the 120 m limit")
    return ("Stays in green airspace and under 120 m." if not parts else "The route " + "; ".join(parts) + ".")
