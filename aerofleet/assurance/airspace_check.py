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
OUTER_YELLOW_FLOOR_M = 60.0       # Drone Rules 2021 (MoCA Airspace Map, Sep 2021): 8-12 km band is yellow only above 200 ft (~60 m)
AIRPORT_PERIMETER_ALLOWANCE_M = 1500.0  # Conservative half-runway/perimeter buffer from airport ARP center point
AIRPORT_RED_M = 5000.0            # 0-5 km from airport perimeter: RED (all altitudes)
AIRPORT_YELLOW_INNER_M = 8000.0   # 5-8 km from airport perimeter: YELLOW (all altitudes)
AIRPORT_YELLOW_OUTER_M = 12000.0  # 8-12 km from airport perimeter: YELLOW above 60 m (200 ft); GREEN <= 60 m
STEP_M = 25.0                     # spacing of the points checked along each leg
CLEAR, NEEDS_PERMISSION, NOT_PERMITTED, UNCHECKED = "CLEAR", "NEEDS_PERMISSION", "NOT_PERMITTED", "UNCHECKED"
NOTE = ("Zones are approximations from India's Drone Rules 2021 / MoCA Airspace Map (24 Sep 2021): 37 Indian civil airports "
        "(0-5 km red, 5-8 km yellow at any height, 8-12 km yellow above 60 m / 200 ft, with a 1.5 km perimeter allowance "
        "around each airport reference point) plus local Pune & Mumbai zones. Not the official Digital Sky map — verify every route on Digital Sky before flight.")

# 37 Indian civil airports (IATA/ICAO, name, lat, lon) using uniform Drone Rules 2021 / MoCA perimeter distances.
# Includes major regional & Maharashtra farming-district aerodromes (including Baramati). Outside Pune & Mumbai,
# military/cantonment sites are not mapped, so a route outside airport zones returns UNCHECKED, never CLEAR.
INDIA_AIRPORTS: Tuple[Tuple[str, str, float, float], ...] = (
    ("PNQ", "Pune Airport (Lohegaon)", 18.5822, 73.9197),
    ("BOM", "Mumbai Chhatrapati Shivaji Maharaj Intl Airport", 19.0896, 72.8656),
    ("VAJJ", "Juhu Aerodrome (Mumbai)", 19.0968, 72.8347),
    ("VABM", "Baramati Airport (Pune District)", 18.2175, 74.5764),
    ("ISK", "Nashik Airport (Ozar)", 20.1194, 73.9136),
    ("NAG", "Nagpur Dr. Babasaheb Ambedkar Intl Airport", 21.0922, 79.0472),
    ("IXU", "Aurangabad (Chhatrapati Sambhajinagar) Airport", 19.8627, 75.3981),
    ("KLH", "Kolhapur Airport", 16.6647, 74.2894),
    ("SAG", "Shirdi Airport", 19.6886, 74.3789),
    ("SSE", "Solapur Airport", 17.6280, 75.9349),
    ("JLG", "Jalgaon Airport", 20.9628, 75.6275),
    ("NDC", "Nanded Shri Guru Gobind Singh Ji Airport", 19.1833, 77.3186),
    ("DEL", "Delhi Indira Gandhi Intl Airport", 28.5562, 77.1000),
    ("BLR", "Bengaluru Kempegowda Intl Airport", 13.1986, 77.7066),
    ("HYD", "Hyderabad Rajiv Gandhi Intl Airport", 17.2403, 78.4294),
    ("MAA", "Chennai Intl Airport", 12.9941, 80.1709),
    ("CCU", "Kolkata Netaji Subhas Chandra Bose Intl Airport", 22.6547, 88.4467),
    ("AMD", "Ahmedabad Sardar Vallabhbhai Patel Intl Airport", 23.0772, 72.6347),
    ("STV", "Surat Intl Airport", 21.1141, 72.7418),
    ("BDQ", "Vadodara Airport", 22.3362, 73.2263),
    ("HSR", "Rajkot Intl Airport (Hirasar)", 22.3822, 71.0319),
    ("JAI", "Jaipur Intl Airport", 26.8242, 75.8122),
    ("UDR", "Udaipur Maharana Pratap Airport", 24.6177, 73.8961),
    ("LKO", "Lucknow Chaudhary Charan Singh Intl Airport", 26.7606, 80.8893),
    ("VNS", "Varanasi Lal Bahadur Shastri Intl Airport", 25.4524, 82.8593),
    ("IDR", "Indore Devi Ahilya Bai Holkar Airport", 22.7218, 75.8011),
    ("BHO", "Bhopal Raja Bhoj Airport", 23.2875, 77.3374),
    ("IXC", "Chandigarh Shaheed Bhagat Singh Intl Airport", 30.6735, 76.7885),
    ("ATQ", "Amritsar Sri Guru Ram Dass Jee Intl Airport", 31.7096, 74.7973),
    ("PAT", "Patna Jay Prakash Narayan Airport", 25.5913, 85.0880),
    ("IXR", "Ranchi Birsa Munda Airport", 23.3143, 85.3217),
    ("BBI", "Bhubaneswar Biju Patnaik Intl Airport", 20.2444, 85.8178),
    ("VTZ", "Visakhapatnam Airport", 17.7212, 83.2245),
    ("VGA", "Vijayawada Intl Airport", 16.5304, 80.7968),
    ("CJB", "Coimbatore Intl Airport", 11.0300, 77.0434),
    ("COK", "Kochi Cochin Intl Airport", 10.1520, 76.4019),
    ("TRV", "Thiruvananthapuram Intl Airport", 8.4821, 76.9201),
)


def india_airport_zone_at(lat: float, lon: float, height_m: Optional[float] = None) -> Optional[Dict[str, Any]]:
    """Drone Rules 2021 / MoCA Airspace Map airport RED/YELLOW lookup across 37 Indian civil airports.

    Distance is approximated from airport perimeter via `max(0, center_dist - AIRPORT_PERIMETER_ALLOWANCE_M)`:
      * 0-5 km: RED (all heights)
      * 5-8 km: YELLOW (all heights)
      * 8-12 km: YELLOW only above 60 m (200 ft); GREEN at <= 60 m (e.g. 4 m agricultural spraying).
    If `height_m` is None, conservatively applies the 8-12 km yellow zone.
    """
    yellow = None
    for code, name, alat, alon in INDIA_AIRPORTS:
        if abs(lat - alat) > 0.16 or abs(lon - alon) > 0.16:
            continue
        d_perim = max(0.0, _metres((lat, lon), (alat, alon)) - AIRPORT_PERIMETER_ALLOWANCE_M)
        if d_perim <= AIRPORT_RED_M:
            return {"id": f"AIRPORT_{code}_RED", "color": "RED", "name": name}
        if d_perim <= AIRPORT_YELLOW_INNER_M and yellow is None:
            yellow = {"id": f"AIRPORT_{code}_YELLOW", "color": "YELLOW", "name": name}
        elif d_perim <= AIRPORT_YELLOW_OUTER_M and (height_m is None or height_m > OUTER_YELLOW_FLOOR_M) and yellow is None:
            yellow = {"id": f"AIRPORT_{code}_YELLOW_HIGH", "color": "YELLOW", "name": f"{name} (8-12 km, >60 m)"}
    return yellow


def in_india_bounds(lat: float, lon: float) -> bool:
    return 6.0 <= lat <= 37.5 and 68.0 <= lon <= 97.5


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
                zone_at: Optional[Callable[..., Optional[Dict[str, Any]]]],
                airports_only: bool = False) -> Dict[str, Any]:
    """`zone_at(lat, lon)` (or `zone_at(lat, lon, height_m)`) gives the red or yellow zone at a point
    ({"id", "color", "name"}) or None; None for the whole function means there is no zone data for this place.
    When `airports_only=True` (outside Pune/Mumbai), missing all airports yields UNCHECKED rather than CLEAR."""
    import inspect

    pts = list(_samples(path))
    length = pts[-1][0]
    findings: List[Dict[str, Any]] = []
    entered: Dict[str, Dict[str, Any]] = {}
    if zone_at is not None:
        takes_h = "height_m" in inspect.signature(zone_at).parameters
        for d, la, lo, h in pts:
            z = zone_at(la, lo, height_m=h) if takes_h else zone_at(la, lo)
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
    elif zone_at is None or airports_only:
        verdict = UNCHECKED
    else:
        verdict = CLEAR
    return {"id": mission_id, "verdict": verdict, "length_m": round(length), "max_height_m": round(max(p[3] for p in pts), 1),
            "airports_only": airports_only,
            "findings": sorted(findings, key=lambda f: f["at_m"]), "path": [[round(la, 6), round(lo, 6), round(h, 1)] for la, lo, h in path]}


def explain(r: Dict[str, Any]) -> str:
    """One plain sentence per mission, for the screen and the record."""
    if r["verdict"] == UNCHECKED:
        if r.get("airports_only"):
            return (f"Checked against {len(INDIA_AIRPORTS)} major Indian airport zones (none entered) and the 120 m limit; "
                    "non-airport military/strategic zones outside Pune & Mumbai are not mapped here — verify on Digital Sky.")
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
