"""Evaluate the SITL retest exactly as declared in research/sitl_check/PROTOCOL_v2.md.

Same review as evaluate.py (v1), with the reader and readiness rules as they are at the declaring commit (ArduPilot
error reports, compass health, estimator test ratios, tilt, motor saturation; failsafes switched off), the baseline =
the settings in the log of v2 S0 run 1, and the v2 expectations.

    python research/sitl_check/evaluate_v2.py
"""
from __future__ import annotations

import json
import os
import sys
from glob import glob

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import evaluate as v1  # noqa: E402

LOGS = "/Volumes/One Touch/AeroFleet_px4_data/sitl_v2"
OUT = os.path.join(v1.ROOT, "research", "results", "sitl_check_v2")
MOTOR_SIGNS = ("Tilt above 60°", "A motor held at its maximum output", "Autopilot reported: thrust loss check",
               "Autopilot reported: crash check")
COMPASS_SIGNS = ("Compass 1 reported unhealthy", "Autopilot reported: compass", "Estimator rejected compass data")


def review(path, baseline):
    from aerofleet.assurance.flightlog import read_flight_log
    from aerofleet.assurance.readiness import failsafes_off

    r = v1.review(path, baseline)
    params = read_flight_log(path).params
    off = failsafes_off(params)
    r["failsafes_off"] = [f["name"] for f in off]
    if off and r["readiness"] == "READY":          # v1.review builds readiness without the failsafe rule; apply it here
        r["readiness"] = "CHECK_FIRST"
    return r


def met(scenario, r):
    warns = r["warnings"]
    if scenario in ("S0_normal", "S5_wind"):
        ok = not warns and not r["episodes"] and not r["failsafes_off"]
        return ok and (scenario != "S0_normal" or (r["settings_verdict"] == "OK" and r["readiness"] == "READY"))
    if scenario == "S1_failsafe_off":
        both = {"FS_THR_ENABLE", "BATT_FS_LOW_ACT"}
        return both <= set(r["settings_critical"]) and both <= set(r["failsafes_off"]) and r["readiness"] == "DO_NOT_FLY"
    if scenario == "S6_motor_failure":
        return any(w.startswith(MOTOR_SIGNS) for w in warns)
    if scenario == "S7_compass_failure":
        return any(w.startswith(COMPASS_SIGNS) for w in warns)
    return v1.met(scenario, r)


def main() -> None:
    from aerofleet.assurance.flightlog import read_flight_log

    baseline = read_flight_log(os.path.join(LOGS, "S0_normal_1.bin")).params
    rows, outcome = [], {}
    for path in sorted(glob(os.path.join(LOGS, "S*_*.bin"))):
        scenario, run = os.path.basename(path)[:-4].rsplit("_", 1)
        try:
            r = review(path, baseline)
        except Exception as e:  # noqa: BLE001
            r = {"error": str(e)}
        r.update({"scenario": scenario, "run": int(run)})
        r["met"] = None if "error" in r else met(scenario, r)
        rows.append(r)
    for s in sorted({r["scenario"] for r in rows}):
        k = sum(1 for r in rows if r["scenario"] == s and r["met"])
        n = sum(1 for r in rows if r["scenario"] == s)
        outcome[s] = f"{'met' if k == n == 3 else 'partly met' if k else 'not met'} ({k} of {n} runs)"
    os.makedirs(OUT, exist_ok=True)
    json.dump({"baseline": "settings in the log of v2 S0 run 1", "outcome": outcome, "runs": rows},
              open(os.path.join(OUT, "results.json"), "w"), indent=1)
    md = ["# SITL retest (v2): results", "", "Declared in `research/sitl_check/PROTOCOL_v2.md`. Every run in `results.json`.", "",
          "| Scenario | Outcome | What AeroFleet showed (run 1) |", "|---|---|---|"]
    for s, o in outcome.items():
        r1 = next((r for r in rows if r["scenario"] == s and r["run"] == 1), {})
        shown = "; ".join((r1.get("warnings") or [])[:4] + [f"failsafes off: {', '.join(r1.get('failsafes_off') or [])}"] * bool(r1.get("failsafes_off")))
        md.append(f"| {s} | {o} | verdict {r1.get('readiness')}, settings {r1.get('settings_verdict')}; {shown or 'no warnings'} |")
    open(os.path.join(OUT, "summary.md"), "w").write("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()
