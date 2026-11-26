"""Check every SITL flight with AeroFleet's own functions and compare with the declared expectations.

Declared in research/sitl_check/PROTOCOL.md (committed and pushed before the scenarios were flown). Reads the logs and
mission files written by run_scenarios.py, and writes research/results/sitl_check/results.json and summary.md.

    python research/sitl_check/evaluate.py
"""
from __future__ import annotations

import json
import os
import sys
from glob import glob

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
LOGS = "/Volumes/One Touch/AeroFleet_px4_data/sitl"
OUT = os.path.join(ROOT, "research", "results", "sitl_check")
DESCRIPTIVE = {"S6_motor_failure", "S7_compass_failure"}


def review(path: str, baseline):
    from aerofleet.assurance.drift import drift_report, in_flight_changes
    from aerofleet.assurance.evidence import timeline
    from aerofleet.assurance.flightlog import read_flight_log
    from aerofleet.assurance.readiness import assess, last_flight_summary
    from aerofleet.assurance.reconcile import parse_waypoints, reconcile

    f = read_flight_log(path)
    plan = parse_waypoints(open(path[:-4] + ".waypoints").read())
    rep = reconcile(plan, f.track, f.modes)
    rep["evidence_timeline"] = timeline(rep, f.track, f.modes, f.battery, f.gps, f.param_changes, f.health)
    changed = in_flight_changes(f.param_changes, f.track[0][0])
    rep["settings_changed_in_flight"] = {"count": len(changed), "safety_critical": sum(1 for c in changed if c["severity"] == "CRITICAL"),
                                         "changes": changed}
    drift = drift_report(f.params, baseline, None, {})
    side = drift.get(drift["decided_by"]) if drift.get("decided_by") else None
    open_ = (side or {}).get("changes", [])
    settings = {"verdict": drift["verdict"], "critical": [c["name"] for c in open_ if c["severity"] == "CRITICAL"],
                "limits": [c["name"] for c in open_ if c["severity"] == "HIGH"]}
    verdict = assess("SITL", settings, {"uin": "SITL", "status": "VERIFIED"}, last_flight_summary(0, rep, ""))
    warnings = [e["text"] for e in rep["evidence_timeline"] if e["level"] == "warning"]
    return {"points": len(f.track), "flight_s": rep["flight_s"], "plan_verdict": rep["verdict"],
            "episodes": [{"kind": e["kind"], "duration_s": e["duration_s"], "max_m": e.get("max_m")} for e in rep["episodes"]],
            "max_sideways_m": rep["horizontal_m"]["max"] if rep.get("horizontal_m") else None,
            "max_height_dev_m": rep["vertical_m"]["max"] if rep.get("vertical_m") else None,
            "warnings": warnings, "notices": [e["text"] for e in rep["evidence_timeline"] if e["level"] == "notice"],
            "modes": [m for _, m in f.modes], "settings_verdict": drift["verdict"], "settings_critical": settings["critical"],
            "in_flight": [f"{c['name']} {c['old']:g} -> {c['new']:g} ({c['severity']})" for c in changed],
            "readiness": verdict["status"], "reasons": [r["text"] for r in verdict["reasons"]]}


def met(scenario: str, r) -> bool:
    if scenario == "S0_normal":
        return not r["warnings"] and not r["episodes"] and r["settings_verdict"] == "OK" and r["readiness"] == "READY"
    if scenario == "S1_failsafe_off":
        return (r["settings_verdict"] == "BLOCK" and {"FS_THR_ENABLE", "BATT_FS_LOW_ACT"} <= set(r["settings_critical"])
                and r["readiness"] == "DO_NOT_FLY")
    if scenario == "S2_gps_lost":
        return any(w.startswith("Poor GPS") for w in r["warnings"])
    if scenario == "S3_battery_low":
        return any(t.startswith("Battery below 20%") for t in r["warnings"] + r["notices"])
    if scenario == "S4_fence_off_in_flight":
        return any(c.startswith("FENCE_ENABLE 1 -> 0") and "CRITICAL" in c for c in r["in_flight"]) and r["readiness"] in ("CHECK_FIRST", "DO_NOT_FLY")
    if scenario == "S5_wind":
        return not r["episodes"]
    return None


def main() -> None:
    from aerofleet.assurance.flightlog import read_flight_log

    base_log = os.path.join(LOGS, "S0_normal_1.bin")
    baseline = read_flight_log(base_log).params
    rows, outcome = [], {}
    for path in sorted(glob(os.path.join(LOGS, "S*_*.bin"))):
        name = os.path.basename(path)[:-4]
        scenario, run = name.rsplit("_", 1)
        try:
            r = review(path, baseline)
        except Exception as e:  # noqa: BLE001
            r = {"error": str(e)}
        r.update({"scenario": scenario, "run": int(run)})
        r["met"] = None if "error" in r else met(scenario, r)
        rows.append(r)
    for s in sorted({r["scenario"] for r in rows}):
        rs = [r for r in rows if r["scenario"] == s]
        if s in DESCRIPTIVE:
            outcome[s] = "descriptive"
            continue
        k = sum(1 for r in rs if r["met"])
        outcome[s] = f"{'met' if k == len(rs) == 3 else 'partly met' if k else 'not met'} ({k} of {len(rs)} runs)"
    os.makedirs(OUT, exist_ok=True)
    json.dump({"baseline": "settings in the log of S0 run 1", "outcome": outcome, "runs": rows}, open(os.path.join(OUT, "results.json"), "w"), indent=1)
    md = ["# SITL check: results", "", "Declared in `research/sitl_check/PROTOCOL.md`. Every run in `results.json`.", "",
          "| Scenario | Outcome | What AeroFleet showed (run 1) |", "|---|---|---|"]
    for s, o in outcome.items():
        r1 = next((r for r in rows if r["scenario"] == s and r["run"] == 1), {})
        shown = "; ".join((r1.get("warnings") or [])[:3] + (r1.get("in_flight") or [])[:2]) or "no warnings"
        md.append(f"| {s} | {o} | verdict {r1.get('readiness')}, settings {r1.get('settings_verdict')}; {shown} |")
    open(os.path.join(OUT, "summary.md"), "w").write("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()
