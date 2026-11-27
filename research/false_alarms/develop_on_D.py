"""EXPLORATORY (†): try revised readiness warning rules on the development half D only, after FA1 failed.

Not a test. FA1 (declared in measure.py, result 9375a6d) found 28.8% of good-or-great public flights would get "Check
first". Here candidate rules, each motivated by what the board is for (is this drone fit to fly today?), are scored on:
  * the D-half vehicles' ordinary flights (false alarms; H is never read here), and
  * real fault flights, as a check that a rule does not go blind: RflyMAD motor- and sensor-fault flights (real PX4
    flights with faults injected in flight) and the SITL v2 fault flights (ArduPilot).
The chosen rule is then declared, with a pass mark, and tested once on H (FA2).

Variants:
  current     the rules as they are (any warning-level timeline event)
  airborne    a GPS or autopilot-health warning counts only for the part that overlaps the airborne time
              (track height above 2 m), and only if that part lasts the event's minimum (GPS 2 s, health 1 s)
  no_battery  landing below 10% is a note about how the last flight was flown, not about the drone: not a reason
  sustained N an autopilot-health or GPS complaint must last N s in the air (N = 3, 5)
Single error reports (ArduPilot ERR, an instant) always count when airborne.

    python research/false_alarms/develop_on_D.py
"""
from __future__ import annotations

import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from glob import glob

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
DATA = "/Volumes/One Touch/AeroFleet_px4_data"
OUT = os.path.join(ROOT, "research", "results", "false_alarms")


def events(path: str):
    """Warning-level events with start/end (log seconds from the first track point) and the airborne window."""
    from aerofleet.assurance.evidence import timeline
    from aerofleet.assurance.flightlog import read_flight_log

    f = read_flight_log(path)
    ev = timeline({"episodes": []}, f.track, f.modes, f.battery, f.gps, f.param_changes, f.health)
    t0 = f.track[0][0]
    air = [p[0] - t0 for p in f.track if p[3] > 2.0]
    window = (min(air), max(air)) if air else None
    out = [{"kind": e["kind"], "text": e["text"], "a": e["t_s"], "b": e.get("end_s", e["t_s"])} for e in ev if e["level"] == "warning"]
    return out, window


def flagged(evs, window, variant: str) -> bool:
    for e in evs:
        if e["kind"] == "battery" and variant != "current":
            continue
        if variant == "current":
            return True
        if e["kind"] in ("gps", "sensor"):
            if window is None:
                continue
            a, b = max(e["a"], window[0]), min(e["b"], window[1])
            need = {"airborne": 2.0 if e["kind"] == "gps" else 1.0, "sustained3": 3.0, "sustained5": 5.0}[variant]
            instant = e["a"] == e["b"]
            if instant and window[0] <= e["a"] <= window[1]:
                return True
            if not instant and b - a >= need:
                return True
            continue
        return True                                    # settings changed in flight, plan deviations: unchanged
    return False


VARIANTS = ["current", "airborne", "sustained3", "sustained5"]


def score(path):
    try:
        evs, w = events(path)
        return {v: flagged(evs, w, v) for v in VARIANTS}
    except Exception as e:  # noqa: BLE001
        return {"error": str(e)[:100]}


def run(paths):
    res = []
    with ProcessPoolExecutor(6) as ex:
        for fut in as_completed([ex.submit(score, p) for p in paths]):
            r = fut.result()
            if "error" not in r:
                res.append(r)
    return {v: round(sum(r[v] for r in res) / len(res), 4) if res else None for v in VARIANTS} | {"n": len(res)}


def main() -> None:
    per = [json.loads(line) for line in open(os.path.join(OUT, "per_flight.jsonl"))]
    d_ids = {p["log_id"] for p in per if p["half"] == "D"}
    good = {p["log_id"] for p in per if p["half"] == "D" and p["rating"] in ("good", "great", "BRAVO!")}
    paths = {}
    for dirpath, _, files in os.walk(DATA):
        if "/external" in dirpath or "/sitl" in dirpath:
            continue
        for n in files:
            if n.endswith(".ulg") and not n.startswith("._") and n[:-4] in d_ids:
                paths.setdefault(n[:-4], os.path.join(dirpath, n))
    rfly = {k: sorted(p for p in glob(f"{DATA}/external/rflymad/{k}/**/*.ulg", recursive=True) if "/._" not in p)
            for k in ("Real-Motor", "Real-Sensors", "Real-No_Fault")}
    sitl = sorted(glob(f"{DATA}/sitl_v2/S[2367]_*.bin"))
    out = {"D_all": run(list(paths.values())), "D_good": run([paths[i] for i in good if i in paths]),
           "rflymad_motor_faults": run(rfly["Real-Motor"]), "rflymad_sensor_faults": run(rfly["Real-Sensors"]),
           "rflymad_no_fault": run(rfly["Real-No_Fault"]), "sitl_v2_faults_S2_S3_S6_S7": run(sitl),
           "note": "Exploratory. Battery below 10% is not a reason in every variant except current."}
    json.dump(out, open(os.path.join(OUT, "develop_on_D.json"), "w"), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
