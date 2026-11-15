"""Vibration per flight, a drone's vibration over its own flights, and its place among comparable drones.

Why this exists and how far it goes (docs/paper, research/results/px4_log_study/):

- Between drones: airframes that later crashed vibrated more on their ordinary flights than matched airframes that
  did not (60 matched sets, mean rank 0.67). The result is suggestive only: Holm-adjusted p 0.016 as declared,
  0.08 clustered by airframe, 0.45 with operator sites weighted equally.
- As a screening rule it was NOT shown to beat random inspection: measured against 412 non-crash drones, a
  top-decile threshold gave a lift of 1.77 [1.00, 2.60]. So this module shows where a drone stands and draws no
  flag line; an "inspect above X" threshold would claim a validation that does not exist.
- Within one drone: the flight before a crash did not vibrate more than the same drone's earlier flights (mean
  rank 0.48, p = 0.67). So a rise on one flight is context for an inspector, not a warning.
- A log that ends in a crash contains the crash. The last END_MARGIN_S seconds of every flight are left out of
  the value, so an impact cannot make a drone look rough.
- Flights are put in the order they were flown (GPS time), not the order they were uploaded: in the public archive
  85 of 210 same-day "earlier" flights had in fact been flown after the crash.

Vibration units differ between autopilots and firmware, so drones are compared only with others whose logs report
the same measurement (`source`).
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from statistics import median
from typing import Any, Dict, Iterable, List, Optional

import numpy as np

RECENT_FLIGHTS = 5          # a drone's value: the median over its most recent reviewed flights
MIN_GROUP = 4               # a position among peers is given only when at least this many drones share a measurement
END_MARGIN_S = 10.0         # left out at the end of every flight (the study's crash-window margin)
MIN_OWN_FLIGHTS = 3         # earlier flights needed before the newest is compared with the drone's own history

EVIDENCE = ("Context for an inspector, not a prediction. In the public PX4 study, drones that later crashed vibrated more "
            "on ordinary flights than matched drones (mean rank 0.67 over 60 sets), but the result weakened under stricter "
            "tests, and as a screening rule it was not shown to beat random inspection (lift 1.77, interval 1.00 to 2.60). "
            "No threshold is drawn for that reason.")
OWN_EVIDENCE = ("In the same study the flight before a crash did not vibrate more than the drone's own earlier flights "
                "(mean rank 0.48, p = 0.67), so a higher value on one flight is a reason to look, not a warning.")


def _sig(x: float, digits: int = 4) -> float:
    return float(f"{x:.{digits}g}")


def flight_vibration(flight) -> Optional[Dict[str, Any]]:
    """95th percentile of the vibration samples recorded during the track, without the last END_MARGIN_S seconds."""
    if not flight.vibration or not flight.track:
        return None
    t0, t1 = flight.track[0][0], flight.track[-1][0]
    whole = [v for t, v in flight.vibration if t0 <= t <= t1] or [v for _, v in flight.vibration]
    cut = [v for t, v in flight.vibration if t0 <= t <= t1 - END_MARGIN_S]
    short = len(cut) < 10                     # too short to cut: say so and use the whole flight
    vals = whole if short else cut
    out = {"p95": _sig(float(np.percentile(vals, 95))), "median": _sig(float(np.median(vals))),
           "p95_whole_flight": _sig(float(np.percentile(whole, 95))), "end_margin_s": 0.0 if short else END_MARGIN_S,
           "source": flight.vibration_source, "samples": len(vals)}
    if getattr(flight, "start_utc", None):
        out["flown_at"] = datetime.fromtimestamp(flight.start_utc, timezone.utc).isoformat()
    return out


def _flights(reviews: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """One row per reviewed flight that has a vibration value, with the time used for ordering and where it came from."""
    out = []
    for r in reviews:
        v = (r.get("report") or {}).get("vibration")
        if v and v.get("source") and v.get("p95") is not None:
            out.append({"review_id": r.get("id"), "drone_id": r["drone_id"], "source": v["source"], "p95": v["p95"],
                        "when": v.get("flown_at") or r["created_at"], "ordered_by": "gps_time" if v.get("flown_at") else "upload_time",
                        "log_name": r.get("log_name")})
    return out


def fleet_ranking(reviews: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    """Each drone's recent vibration and its position among drones with the same measurement. No drone is flagged."""
    per: Dict[tuple, List[Dict[str, Any]]] = defaultdict(list)
    for f in _flights(reviews):
        per[(f["drone_id"], f["source"])].append(f)
    drones = []
    for (drone, source), fl in per.items():
        recent = [f["p95"] for f in sorted(fl, key=lambda f: f["when"], reverse=True)[:RECENT_FLIGHTS]]
        drones.append({"drone_id": drone, "source": source, "flights": len(recent), "vibration_p95": _sig(median(recent))})
    by_source: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for d in drones:
        by_source[d["source"]].append(d)
    for group in by_source.values():
        group.sort(key=lambda d: d["vibration_p95"], reverse=True)
        n = len(group)
        mid = median(d["vibration_p95"] for d in group)
        for i, d in enumerate(group):
            d["rank"], d["group_size"] = i + 1, n
            d["comparable"] = n >= MIN_GROUP
            d["times_group_median"] = _sig(d["vibration_p95"] / mid, 3) if d["comparable"] and mid > 0 else None
    out = sorted(drones, key=lambda d: (d["source"], d["rank"]))
    return {"drones": out, "evidence": EVIDENCE,
            "note": (f"Each drone's value is the median over its last {RECENT_FLIGHTS} reviewed flights, with the last "
                     f"{END_MARGIN_S:g} s of each flight left out. Drones are compared only with drones whose logs report the "
                     f"same measurement, and only when at least {MIN_GROUP} share it.")}


def drone_history(reviews: Iterable[Dict[str, Any]], drone_id: str) -> Dict[str, Any]:
    """One drone's vibration flight by flight, in the order flown, and the newest flight against its own earlier ones."""
    mine = sorted((f for f in _flights(reviews) if f["drone_id"] == drone_id), key=lambda f: f["when"])
    if not mine:
        return {"drone_id": drone_id, "flights": [], "latest_vs_own": None, "evidence": OWN_EVIDENCE,
                "message": "No reviewed flight with a vibration value yet."}
    source = mine[-1]["source"]
    same = [f for f in mine if f["source"] == source]          # a firmware change can change the measurement
    latest, earlier = same[-1], same[:-1]
    versus = None
    if len(earlier) >= MIN_OWN_FLIGHTS:
        base = median(f["p95"] for f in earlier)
        versus = {"latest_p95": latest["p95"], "earlier_median": _sig(base), "earlier_flights": len(earlier),
                  "higher_than": sum(1 for f in earlier if latest["p95"] > f["p95"]),
                  "times_own_median": _sig(latest["p95"] / base, 3) if base > 0 else None}
    upload_ordered = sum(1 for f in same if f["ordered_by"] == "upload_time")
    return {"drone_id": drone_id, "source": source, "flights": same, "latest_vs_own": versus, "evidence": OWN_EVIDENCE,
            "order_note": ("Flights are in the order they were flown (GPS time)." if not upload_ordered else
                           f"{upload_ordered} of {len(same)} flights have no GPS time and are placed by upload time, "
                           "which may not be the order flown."),
            "message": None if versus else f"The newest flight is compared with the drone's own history once {MIN_OWN_FLIGHTS} "
                                           "earlier flights are reviewed."}
