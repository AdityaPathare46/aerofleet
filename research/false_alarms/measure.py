"""How often would Today's fleet flag a healthy drone because of its last flight's log? Declared measurement (FA1).

DECLARED BEFORE RUNNING (committed and pushed before the first run; nothing below has been computed yet).

Why: Today's fleet says "Check first" whenever the last flight's log shows a warning-level event: poor GPS (fewer than
6 satellites, no 3D fix or HDOP above 2.5, for 2 s or more), battery below 10%, a safety-critical setting changed in
flight, or what the autopilot reported about itself (PX4: estimator rejecting compass, velocity, position or height
data, an internal fault, or failsafe, for 1 s or more; ArduPilot: error reports, compass health, estimator test ratios,
tilt above 60°, motor saturation). These thresholds are conventions, never validated. If healthy drones are flagged
often, operators will learn to ignore the board.

DATA: the 1,121 ordinary public PX4 flights of 401 vehicles that trained the normal-flight model
(research/results/normal_flight/features.jsonl: not rated crash or unsatisfactory, readable, PX4, at least 60 s, no
demo-fleet vehicle), each read with AeroFleet's own reader as the product would. Uploader rating from the archive index
(dbinfo.json). Real flights of mostly hobby, research and test drones, not spraying drones.

SPLIT (for any later fix): vehicles are split at random (seed 2026) into a development half D and a held-out half H.
This measurement reports both. Any change to the warning rules made after seeing it must be developed on D only and
tested on H in a new declaration.

MEASURE (FA1): the share of flights whose log alone gives at least one warning-level event (and so "Check first"),
with a 95% Wilson interval, overall and for flights the uploader rated good or great; plus the share for each kind of
warning, and the share of vehicles with at least one flagged flight.
PASS MARK (our judgment, stated in advance): usable as declared if at most 20% of the good-or-great flights are flagged.
An operator re-checking more than one healthy drone in five every morning would soon stop reading the board.

OUTPUT: research/results/false_alarms/ (results.json, summary.md, per_flight.jsonl with log id, half, rating and the
kinds of warning only). Reported whatever it shows.

    python research/false_alarms/measure.py
"""
from __future__ import annotations

import gzip
import json
import math
import os
import random
import re
import sys
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
DATA = "/Volumes/One Touch/AeroFleet_px4_data"
FEATURES = os.path.join(ROOT, "research", "results", "normal_flight", "features.jsonl")
OUT = os.path.join(ROOT, "research", "results", "false_alarms")
GOOD = {"good", "great", "BRAVO!"}
SEED = 2026


def kind(text: str) -> str:
    """The warning without its numbers: 'Poor GPS for 12 s (...)' -> 'Poor GPS'."""
    t = re.split(r" for \d| \(|\d+%", text)[0]
    return re.sub(r"\s+", " ", t).strip()


def wilson(k: int, n: int, z: float = 1.96):
    if n == 0:
        return None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(p, 4), round(max(0.0, c - h), 4), round(min(1.0, c + h), 4)]


def one(args):
    log_id, path = args
    from aerofleet.assurance.evidence import timeline
    from aerofleet.assurance.flightlog import read_flight_log

    try:
        f = read_flight_log(path)
        ev = timeline({"episodes": []}, f.track, f.modes, f.battery, f.gps, f.param_changes, f.health)
        return {"log_id": log_id, "warnings": sorted({kind(e["text"]) for e in ev if e["level"] == "warning"})}
    except Exception as e:  # noqa: BLE001
        return {"log_id": log_id, "error": str(e)[:120]}


def main() -> None:
    rows = [json.loads(line) for line in open(FEATURES)]
    paths = {}
    for dirpath, _, files in os.walk(DATA):
        if "/external" in dirpath or "/sitl" in dirpath:
            continue
        for n in files:
            if n.endswith(".ulg") and not n.startswith("._"):
                paths.setdefault(n[:-4], os.path.join(dirpath, n))
    raw = open(os.path.join(DATA, "dbinfo.json"), "rb").read()
    try:
        raw = gzip.decompress(raw)
    except OSError:
        pass
    rating = {e["log_id"]: e.get("rating") or "" for e in json.loads(raw)}
    vehicles = sorted({r["vehicle"] for r in rows})
    random.Random(SEED).shuffle(vehicles)
    half = {v: ("D" if i % 2 == 0 else "H") for i, v in enumerate(vehicles)}
    todo = [(r["log_id"], paths[r["log_id"]]) for r in rows if r["log_id"] in paths]
    vehicle_of = {r["log_id"]: r["vehicle"] for r in rows}
    done = []
    with ProcessPoolExecutor(6) as ex:
        for fut in as_completed([ex.submit(one, t) for t in todo]):
            done.append(fut.result())
    ok = [d for d in done if "error" not in d]
    for d in ok:
        d.update(half=half[vehicle_of[d["log_id"]]], rating=rating.get(d["log_id"], ""), vehicle=vehicle_of[d["log_id"]])

    def summary(sub):
        flagged = [d for d in sub if d["warnings"]]
        kinds = Counter(k for d in sub for k in d["warnings"])
        veh = {d["vehicle"] for d in sub}
        vflag = {d["vehicle"] for d in flagged}
        return {"flights": len(sub), "flagged": len(flagged), "share": wilson(len(flagged), len(sub)),
                "by_kind": {k: wilson(v, len(sub)) + [v] for k, v in kinds.most_common()},
                "vehicles": len(veh), "vehicles_with_a_flagged_flight": len(vflag)}

    good = [d for d in ok if d["rating"] in GOOD]
    res = {"declared": "research/false_alarms/measure.py", "logs_found": len(todo), "read": len(ok),
           "unreadable": len(done) - len(ok), "all": summary(ok), "good_or_great": summary(good),
           "D": summary([d for d in ok if d["half"] == "D"]), "H": summary([d for d in ok if d["half"] == "H"]),
           "pass_mark": "at most 20% of good-or-great flights flagged"}
    share = res["good_or_great"]["share"]
    res["FA1_usable_as_declared"] = bool(share and share[0] <= 0.20)
    os.makedirs(OUT, exist_ok=True)
    json.dump(res, open(os.path.join(OUT, "results.json"), "w"), indent=1)
    with open(os.path.join(OUT, "per_flight.jsonl"), "w") as f:
        for d in sorted(ok, key=lambda x: x["log_id"]):
            f.write(json.dumps({k: d[k] for k in ("log_id", "half", "rating", "warnings")}) + "\n")
    g, a = res["good_or_great"], res["all"]
    md = ["# FA1: how often does Today's fleet flag a healthy drone from its last log?", "",
          "Declared in `research/false_alarms/measure.py`. Full numbers in `results.json`.", "",
          "| Flights | Flagged (Check first) | 95% interval |", "|---|---|---|",
          f"| All {a['flights']} ordinary flights | {a['flagged']} ({100 * a['share'][0]:.1f}%) | {100 * a['share'][1]:.1f}-{100 * a['share'][2]:.1f}% |",
          f"| {g['flights']} rated good or great | {g['flagged']} ({100 * g['share'][0]:.1f}%) | {100 * g['share'][1]:.1f}-{100 * g['share'][2]:.1f}% |",
          "", f"Pass mark: at most 20% of good-or-great flights. **{'Met' if res['FA1_usable_as_declared'] else 'Not met'}.**", "",
          "| Warning (all flights) | Share | Flights |", "|---|---|---|"]
    md += [f"| {k} | {100 * v[0]:.1f}% | {v[3]} |" for k, v in a["by_kind"].items()]
    open(os.path.join(OUT, "summary.md"), "w").write("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()
