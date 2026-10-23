"""Vibration per flight, and a fleet ranking of drones by vibration on their ordinary flights.

Why this exists (research/results/px4_log_study/): on public PX4 logs, drones that later crashed were already
vibrating more on their ordinary flights than matched drones that did not crash (60 matched sets, mean rank
0.67, p = 0.002), while the flight that crashed looked no different from the same drone's earlier flights.
So vibration says something about the drone, not about one flight. The ranking flags the roughest drones in a
fleet for inspection (those above their group's upper quartile); it does not predict a crash and gives no
threshold that is "safe".

Vibration units differ between autopilots and firmware, so drones are only ranked against others whose logs
report the same measurement (`source`).
"""
from __future__ import annotations

from collections import defaultdict
from statistics import median
from typing import Any, Dict, Iterable, List, Optional

import numpy as np

RECENT_FLIGHTS = 5          # a drone's value: the median over its most recent reviewed flights
MIN_GROUP = 4               # flag only when at least this many drones share a measurement


def _sig(x: float, digits: int = 4) -> float:
    return float(f"{x:.{digits}g}")


def flight_vibration(flight) -> Optional[Dict[str, Any]]:
    """95th percentile of the vibration samples recorded while the track was recording."""
    if not flight.vibration or not flight.track:
        return None
    t0, t1 = flight.track[0][0], flight.track[-1][0]
    vals = [v for t, v in flight.vibration if t0 <= t <= t1] or [v for _, v in flight.vibration]
    return {"p95": _sig(float(np.percentile(vals, 95))), "median": _sig(float(np.median(vals))),
            "source": flight.vibration_source, "samples": len(vals)}


def fleet_ranking(reviews: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    """`reviews`: dicts with drone_id, created_at and report (newest first or any order)."""
    per: Dict[tuple, List[tuple]] = defaultdict(list)
    for r in reviews:
        v = (r.get("report") or {}).get("vibration")
        if v and v.get("source") and v.get("p95") is not None:
            per[(r["drone_id"], v["source"])].append((r["created_at"], v["p95"]))
    drones = []
    for (drone, source), vals in per.items():
        recent = [p for _, p in sorted(vals, reverse=True)[:RECENT_FLIGHTS]]
        drones.append({"drone_id": drone, "source": source, "flights": len(recent), "vibration_p95": _sig(median(recent))})
    by_source: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for d in drones:
        by_source[d["source"]].append(d)
    for group in by_source.values():
        group.sort(key=lambda d: d["vibration_p95"], reverse=True)
        n = len(group)
        # Flag only drones above the group's upper quartile: a fixed share would flag drones that are tied with
        # unflagged ones, and would flag someone even when every drone vibrates about the same.
        q3 = float(np.percentile([d["vibration_p95"] for d in group], 75)) if n >= MIN_GROUP else None
        for i, d in enumerate(group):
            d["rank"] = i + 1
            d["group_size"] = n
            d["flag"] = q3 is not None and d["vibration_p95"] > q3
    out = sorted(drones, key=lambda d: (d["source"], d["rank"]))
    return {"drones": out, "flagged": [d["drone_id"] for d in out if d["flag"]],
            "note": ("Ranked against drones whose logs report the same vibration measurement. Once at least "
                     f"{MIN_GROUP} drones share one, those above the group's upper quartile are flagged. A flag means inspect "
                     "(mounting, propellers, motors), not that a crash is coming.")}
