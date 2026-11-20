"""Fleet trends: the season view of a fleet, from its reviewed flights.

For a service provider's coordinator: how much the fleet flew, when, how many warnings the logs showed per flight, and which
drones are drifting from what is expected of them. Every number is a count or a median over stored flight reviews;
nothing is predicted.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from statistics import median
from typing import Any, Dict, List


def _when(r: Dict[str, Any]) -> datetime:
    iso = ((r.get("report") or {}).get("vibration") or {}).get("flown_at") or r["created_at"]
    d = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def _warnings(rep: Dict[str, Any]) -> int:
    return sum(1 for e in rep.get("evidence_timeline") or [] if e.get("level") == "warning" and e.get("kind") != "plan")


def _outside(rep: Dict[str, Any]) -> List[str]:
    return [k for k, t in (((rep.get("normal_flight") or {}).get("targets")) or {}).items() if t.get("position") != "inside"]


def fleet_trends(reviews: List[Dict[str, Any]]) -> Dict[str, Any]:
    """`reviews`: {"drone_id", "created_at", "report"} for every reviewed flight of the fleet."""
    if not reviews:
        return {"flights": 0, "drones": [], "periods": [], "message": "No reviewed flights yet."}
    rows = sorted(reviews, key=_when)
    first, last = _when(rows[0]), _when(rows[-1])
    monthly = (last - first).days > 120                       # long seasons by month, short ones by week
    bucket = (lambda d: d.strftime("%Y-%m")) if monthly else (lambda d: f"{d.isocalendar()[0]}-W{d.isocalendar()[1]:02d}")
    periods: Dict[str, Dict[str, float]] = defaultdict(lambda: {"flights": 0, "hours": 0.0, "warnings": 0})
    per: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for r in rows:
        rep = r.get("report") or {}
        p = periods[bucket(_when(r))]
        p["flights"] += 1
        p["hours"] += float(rep.get("flight_s") or 0) / 3600
        p["warnings"] += _warnings(rep)
        per[r["drone_id"]].append(r)
    hours = sum(float((r.get("report") or {}).get("flight_s") or 0) for r in rows) / 3600
    warns = sum(_warnings(r.get("report") or {}) for r in rows)
    scored = [r for r in rows if (r.get("report") or {}).get("normal_flight")]
    outside = [r for r in scored if _outside(r["report"])]
    drones = []
    for d, rs in sorted(per.items()):
        h = sum(float((r.get("report") or {}).get("flight_s") or 0) for r in rs) / 3600
        vib = [((r.get("report") or {}).get("vibration") or {}).get("p95") for r in rs]
        vib = [v for v in vib if v is not None]
        batt = [t.get("times_mid") for r in rs for k, t in ((((r.get("report") or {}).get("normal_flight") or {}).get("targets")) or {}).items()
                if k == "battery_drop_pct_per_min" and t.get("times_mid")]
        drones.append({"drone_id": d, "flights": len(rs), "hours": round(h, 2), "last_flown": _when(rs[-1]).isoformat(),
                       "warnings_per_flight": round(sum(_warnings(r.get("report") or {}) for r in rs) / len(rs), 1),
                       "latest_vibration_vs_own_median": round(vib[-1] / median(vib[:-1]), 2) if len(vib) >= 4 and median(vib[:-1]) > 0 else None,
                       "battery_vs_expected_median": round(median(batt), 2) if batt else None,
                       "flights_outside_expected": sum(1 for r in rs if (r.get("report") or {}).get("normal_flight") and _outside(r["report"]))})
    return {"flights": len(rows), "drone_count": len(per), "hours": round(hours, 1), "first": first.isoformat(), "last": last.isoformat(),
            "warnings_per_flight": round(warns / len(rows), 1),
            "share_outside_expected": round(len(outside) / len(scored), 3) if scored else None, "scored_flights": len(scored),
            "period": "month" if monthly else "week",
            "periods": [{"period": k, "flights": int(v["flights"]), "hours": round(v["hours"], 2), "warnings": int(v["warnings"])}
                        for k, v in sorted(periods.items())],
            "drones": drones,
            "note": ("Counts and medians over this fleet's reviewed flights; nothing is predicted. 'Outside expected' uses the "
                     "learned normal-flight model, which holds about 90% of healthy flights, so about 1 in 10 healthy flights "
                     "falls outside by chance.")}
