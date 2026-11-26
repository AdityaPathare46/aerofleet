"""Fly the SITL retest (research/sitl_check/PROTOCOL_v2.md): fresh flights, a properly configured vehicle.

Same runner as run_scenarios.py (v1, unchanged), with three differences declared in PROTOCOL_v2.md:
  * every run starts from a CONFIGURED vehicle: battery failsafes set (low: return, critical: land) and the geofence on,
    on top of ArduPilot's SITL defaults, so a normal flight has no failsafe switched off;
  * new fields (field numbers 3, 4, 5: none of them flown in v1), with home 10 m south of each field so the default
    300 m fence circle is never reached;
  * logs go to AeroFleet_px4_data/sitl_v2/.

    python research/sitl_check/run_v2.py [SCENARIO ...]
"""
from __future__ import annotations

import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_scenarios as v1  # noqa: E402

CONFIGURED = {"BATT_FS_LOW_ACT": 2, "BATT_FS_CRT_ACT": 1, "BATT_LOW_VOLT": 10.5, "BATT_CRT_VOLT": 10.0, "FENCE_ENABLE": 1}
FIELD_OFFSET = 3
v1.OUT = "/Volumes/One Touch/AeroFleet_px4_data/sitl_v2"
v1.WORK = os.path.expanduser("~/aerofleet_sitl/runs_v2")


def field(k: int):
    """Same pattern as v1 on field number k + 3; home 10 m south of the field's corner."""
    k = k + FIELD_OFFSET
    la0, lo0 = v1.HOME[0] + 0.0002 + 0.00135 * k, v1.HOME[1] + 0.0002
    k_lon = v1.M * math.cos(math.radians(la0))
    pts = []
    for i in range(6):
        off, a = 8.0 * i, 0.0
        if k % 2 == 0:
            e0, e1 = (a, 80.0) if i % 2 == 0 else (80.0, a)
            pts += [(la0 + off / v1.M, lo0 + e0 / k_lon), (la0 + off / v1.M, lo0 + e1 / k_lon)]
        else:
            n0, n1 = (a, 80.0) if i % 2 == 0 else (80.0, a)
            pts += [(la0 + n0 / v1.M, lo0 + off / k_lon), (la0 + n1 / v1.M, lo0 + off / k_lon)]
    return [(la0 - 10.0 / v1.M, lo0)] + pts


v1.field = field
SCENARIOS = {name: {**spec, "pre": {**CONFIGURED, **spec["pre"]}} for name, spec in v1.SCENARIOS.items()}
SCENARIOS["S4_fence_off_in_flight"]["pre"] = dict(CONFIGURED)     # v2: the fence is part of the configured vehicle
v1.SCENARIOS = SCENARIOS


if __name__ == "__main__":
    v1.main(sys.argv[1:])
    print(json.dumps({"configured": CONFIGURED, "fields": [k + FIELD_OFFSET for k in range(v1.RUNS)]}))
