"""Compare a flight or a setting with ordinary public PX4 flights.

The reference (data/public_reference.json, built by tools/build_public_reference.py) describes real PX4 flights from the
public Flight Review archive that their pilots rated good or great, read with AeroFleet's own reader. It lets an
operator with one to three drones (too few for the in-fleet comparison) see where a flight stands, and shows how other
PX4 pilots set each safety-critical setting.

It is a description, not a limit. In the study, vibration was not shown to beat random inspection as a screen, and
settings did not differ between crashed and normal flights, so "higher than most" or "unusual" is a reason to look,
not a finding. Each result carries that sentence.
"""
from __future__ import annotations

import bisect
import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional

from aerofleet.assurance.flightlog import MULTIROTORS

DATA = Path(__file__).with_name("data") / "public_reference.json"
VIBRATION_NOTE = ("Compared with public PX4 flights rated good or great. A description, not a limit: being above most of "
                  "them was not shown to mean a drone will crash.")
SETTING_NOTE = ("How public PX4 flights rated good or great set this. Common is not proof of safe: in the study, settings "
                "did not differ between crashed and normal flights.")


@lru_cache(maxsize=1)
def reference() -> Optional[Dict[str, Any]]:
    try:
        return json.loads(DATA.read_text())
    except (OSError, ValueError):
        return None


def vehicle_kind(vehicle: Optional[str]) -> str:
    """The grouping the reference uses: multirotors together, other vehicle types by name."""
    return "multirotor" if vehicle in MULTIROTORS else (vehicle or "unknown")


def vibration_position(source: Optional[str], vehicle: Optional[str], p95: Optional[float]) -> Optional[Dict[str, Any]]:
    """Share of public flights (same measurement, same kind of vehicle) with lower vibration than `p95`."""
    ref = reference()
    if not ref or source is None or p95 is None:
        return None
    g = ref["vibration"].get(f"{source}|{vehicle_kind(vehicle)}")
    if not g:
        return None
    q = g["percentiles"]                                   # q[i] is the i-th percentile of the public flights
    pct = min(100, max(0, bisect.bisect_left(q, p95) - 1 if p95 > q[0] else 0))
    return {"higher_than_pct": pct, "flights": g["flights"], "vehicles": g["vehicles"], "median": q[50],
            "source": source, "vehicle": g["vehicle"], "note": VIBRATION_NOTE}


def setting_context(name: str, value: Optional[float]) -> Optional[Dict[str, Any]]:
    """How many public flights use this exact value of a safety-critical PX4 setting, and the most common value."""
    ref = reference()
    s = (ref or {}).get("settings", {}).get(name.upper())
    if not s or value is None:
        return None
    n = s["logs"]
    common_value, common_count = next(iter(s["values"].items()))
    same = s["values"].get(f"{value:g}", 0)
    return {"same_value_pct": round(100 * same / n), "logs": n, "most_common": common_value,
            "most_common_pct": round(100 * common_count / n), "note": SETTING_NOTE}
