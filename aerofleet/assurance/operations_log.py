"""Operations log: one row per reviewed flight, as a CSV a service provider can keep and report from.

For agricultural operators the crop-protection SOP asks for spray monitoring data within seven days of spraying. This is
not that official form (its exact fields are set by the Central Insecticide Board); it is the flight record such a
report is filled from: when, which drone (and its UIN), how long, how far, the area of the outline flown, where it took
off, and the fingerprint of the signed review, so any row can be checked against the tamper-evident record.

The outline area is the area of the convex hull of the flown track: an estimate of the field size, not of the area
sprayed (that depends on the spray width, which the log does not record).
"""
from __future__ import annotations

import csv
import io
import math
from typing import Any, Dict, Iterable, List, Optional, Tuple

COLUMNS = ["date_utc", "drone_id", "uin", "log_file", "flight_min", "distance_km", "outline_area_ha", "take_off_lat",
           "take_off_lon", "max_height_m", "warnings", "outside_expected", "review_id", "review_sha256"]


def _local(points: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
    la0, lo0 = points[0]
    k = 111_320.0 * math.cos(math.radians(la0))
    return [((lo - lo0) * k, (la - la0) * 111_320.0) for la, lo in points]


def _hull_area_m2(points: List[Tuple[float, float]]) -> float:
    pts = sorted(set(_local(points)))
    if len(pts) < 3:
        return 0.0

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lower: List[Tuple[float, float]] = []
    upper: List[Tuple[float, float]] = []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    hull = lower[:-1] + upper[:-1]
    return abs(sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(hull, hull[1:] + hull[:1]))) / 2


def _distance_m(points: List[Tuple[float, float]]) -> float:
    xy = _local(points)
    return sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(xy, xy[1:]))


def row(review: Dict[str, Any], uin: Optional[str], sha256: str) -> Dict[str, Any]:
    rep = review.get("report") or {}
    flown = [(p[1], p[2]) for p in ((rep.get("replay") or {}).get("flown") or [])]
    heights = [p[3] for p in ((rep.get("replay") or {}).get("flown") or [])]
    warnings = sum(1 for e in rep.get("evidence_timeline") or [] if e.get("level") == "warning" and e.get("kind") != "plan")
    outside = [k for k, t in (((rep.get("normal_flight") or {}).get("targets")) or {}).items() if t.get("position") != "inside"]
    return {"date_utc": ((rep.get("vibration") or {}).get("flown_at") or review["created_at"])[:19].replace("T", " "),
            "drone_id": review["drone_id"], "uin": uin or "", "log_file": review.get("log_name") or "",
            "flight_min": round(float(rep.get("flight_s") or 0) / 60, 1),
            "distance_km": round(_distance_m(flown) / 1000, 2) if len(flown) > 1 else 0.0,
            "outline_area_ha": round(_hull_area_m2(flown) / 10_000, 2) if len(flown) > 2 else 0.0,
            "take_off_lat": round(flown[0][0], 5) if flown else "", "take_off_lon": round(flown[0][1], 5) if flown else "",
            "max_height_m": round(max(heights), 1) if heights else "", "warnings": warnings, "outside_expected": " ".join(outside),
            "review_id": review.get("id"), "review_sha256": sha256}


def to_csv(rows: Iterable[Dict[str, Any]]) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=COLUMNS)
    w.writeheader()
    for r in rows:
        w.writerow(r)
    return buf.getvalue()
