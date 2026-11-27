"""Maintenance logbook: did the fix work?

An operator records what was done to a drone (new propellers, a motor, a battery, ...). AeroFleet then compares the
drone's flights just before the work with the flights after it: vibration (same measurement only) and battery drain
relative to what the normal-flight model expects for each flight, so a change in how the drone was flown does not
pass for a change in the drone.

Honest limits, shown with every result: a few flights on each side cannot prove a fix worked; this is a before/after
description, not a test.
"""
from __future__ import annotations

from datetime import datetime, timezone
from statistics import median
from typing import Any, Dict, List, Optional

ACTIONS = ["Propellers replaced", "Motor replaced", "Motor mounts / arms tightened or replaced", "Battery replaced",
           "Flight controller re-mounted or vibration damping changed", "Sensors calibrated (compass, accelerometer)",
           "Firmware updated", "Spray system serviced", "Spray system calibrated (nozzle output)",
           "Incident / crash reported (grounded for inspection)", "Post-incident inspection cleared", "Other"]
GROUNDING_ACTION = "Incident / crash reported (grounded for inspection)"
CLEARANCE_ACTION = "Post-incident inspection cleared"
N_SIDE = 3                     # flights compared on each side of the work
NOTE = ("Median of up to 3 flights before and 3 after the work. A few flights cannot prove a fix worked: read it as a "
        "description, and watch the next flights.")


def is_grounded(entries: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Return the latest unresolved grounding record if a drone had an incident/crash without a later clearance."""
    ordered = sorted(entries, key=lambda m: (_when(m["done_at"]), int(m.get("id") or 0)))
    grounded = None
    for m in ordered:
        if m.get("action") == GROUNDING_ACTION:
            grounded = {"done_at": m["done_at"], "note": m.get("note", ""), "done_by": m.get("done_by", "")}
        elif m.get("action") == CLEARANCE_ACTION:
            grounded = None
    return grounded


def _when(iso: str) -> datetime:
    d = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def flight_points(reviews: List[Dict[str, Any]], drone_id: str) -> List[Dict[str, Any]]:
    """Per reviewed flight of this drone: when it was flown, vibration (with its source) and battery drain vs expected."""
    out = []
    for r in reviews:
        if r["drone_id"] != drone_id:
            continue
        rep = r.get("report") or {}
        v = rep.get("vibration") or {}
        batt = ((rep.get("normal_flight") or {}).get("targets") or {}).get("battery_drop_pct_per_min") or {}
        out.append({"review_id": r.get("id"), "when": v.get("flown_at") or r["created_at"],
                    "vibration": v.get("p95"), "source": v.get("source"),
                    "battery_vs_expected": batt.get("times_mid")})
    return sorted(out, key=lambda p: _when(p["when"]))


def _compare(before: List[float], after: List[float], label: str, unit: str) -> Optional[Dict[str, Any]]:
    if not before or not after:
        return None
    b, a = median(before), median(after)
    change = (a - b) / b if b else None
    return {"label": label, "unit": unit, "before": b, "after": a, "flights_before": len(before), "flights_after": len(after),
            "change_pct": round(100 * change) if change is not None else None}


def effect(points: List[Dict[str, Any]], done_at: str) -> Dict[str, Any]:
    """Flights just before vs just after the work, for vibration and battery drain relative to expected."""
    t = _when(done_at)
    before = [p for p in points if _when(p["when"]) < t][-N_SIDE:]
    after = [p for p in points if _when(p["when"]) >= t][:N_SIDE]
    source = (after or before or [{}])[0].get("source")
    vib = _compare([p["vibration"] for p in before if p["vibration"] is not None and p["source"] == source],
                   [p["vibration"] for p in after if p["vibration"] is not None and p["source"] == source],
                   "Vibration (95th percentile)", f"{source} units")
    bat = _compare([p["battery_vs_expected"] for p in before if p["battery_vs_expected"]],
                   [p["battery_vs_expected"] for p in after if p["battery_vs_expected"]],
                   "Battery drain vs expected", "x typical for similar flights")
    measures = [m for m in (vib, bat) if m]
    if not after:
        summary = "No flight reviewed since the work yet: upload the next flight to see the effect."
    elif not before:
        summary = "No flight reviewed before the work, so there is nothing to compare with."
    elif not measures:
        summary = "The flights on either side have no comparable measurements."
    else:
        summary = "; ".join(f"{m['label']} {'fell' if (m['change_pct'] or 0) < 0 else 'rose'} {abs(m['change_pct'] or 0)}%"
                            for m in measures if m["change_pct"] is not None) or "No change could be computed."
    return {"flights_before": len(before), "flights_after": len(after), "measures": measures, "summary": summary, "note": NOTE}
