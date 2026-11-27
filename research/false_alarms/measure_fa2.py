"""FA2: does the revised warning rule keep healthy drones off "Check first"? Declared test on the held-out half H.

DECLARED BEFORE RUNNING (committed and pushed with the product change it tests; H has not been read since FA1).

Background: FA1 (measure.py, result 9375a6d) failed: 28.8% of good-or-great flights would be flagged. On the development
half D only (develop_on_D.py, exploratory) the rule was changed, each part for a stated reason:
  * a GPS or autopilot-health complaint is a warning only for the part in the air (track above 2 m) and only if that
    part lasts at least 3 s; an autopilot error report counts only in the air; shorter or ground complaints are listed
    as notices (aerofleet/assurance/evidence.py: AIRBORNE_M, SUSTAINED_S);
  * landing below 10% battery is a pilot note on Today's fleet, not a reason (aerofleet/assurance/readiness.py).
On D: 19.3% of good-or-great flights flagged (from 34.9%); real RflyMAD motor-fault flights flagged 19.4% (from 21.5%),
sensor-fault flights 53.8% (from 58.4%), no-fault flights 0%.

DATA: the held-out half H of FA1's vehicles (572 flights of the 1,121 ordinary public PX4 flights), read by the product
code at this commit. Flagged = the flight's own log gives at least one reason for "Check first" on Today's fleet:
readiness.last_flight_summary(...) lists a warning, a safety-critical setting changed in flight, or the flight left its
plan (no plans here, so the last never applies).

FA2 (primary): share of H's good-or-great flights flagged, with a 95% Wilson interval.
PASS MARK (the same as FA1, stated in advance): at most 20%.
Also reported: all H flights, the reasons, and D for comparison. Reported whatever it shows; the rule is not changed
again on the basis of this result without a new declaration on new data.

    python research/false_alarms/measure_fa2.py
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import measure as fa1  # noqa: E402

GOOD = fa1.GOOD


def one(args):
    log_id, path = args
    from aerofleet.assurance.evidence import timeline
    from aerofleet.assurance.flightlog import read_flight_log
    from aerofleet.assurance.readiness import last_flight_summary

    try:
        f = read_flight_log(path)
        ev = timeline({"episodes": []}, f.track, f.modes, f.battery, f.gps, f.param_changes, f.health)
        s = last_flight_summary(0, {"evidence_timeline": ev}, "")
        return {"log_id": log_id, "reasons": sorted({fa1.kind(w) for w in s["warnings"]}), "pilot_notes": bool(s["pilot_notes"])}
    except Exception as e:  # noqa: BLE001
        return {"log_id": log_id, "error": str(e)[:120]}


def main() -> None:
    per = {p["log_id"]: p for p in (json.loads(line) for line in open(os.path.join(fa1.OUT, "per_flight.jsonl")))}
    paths = {}
    for dirpath, _, files in os.walk(fa1.DATA):
        if "/external" in dirpath or "/sitl" in dirpath:
            continue
        for n in files:
            if n.endswith(".ulg") and not n.startswith("._") and n[:-4] in per:
                paths.setdefault(n[:-4], os.path.join(dirpath, n))
    todo = [(i, paths[i]) for i, p in per.items() if i in paths]
    done = []
    with ProcessPoolExecutor(6) as ex:
        for fut in as_completed([ex.submit(one, t) for t in todo]):
            done.append(fut.result())
    ok = [d for d in done if "error" not in d]
    for d in ok:
        d.update(half=per[d["log_id"]]["half"], rating=per[d["log_id"]]["rating"])

    def summary(sub):
        flagged = [d for d in sub if d["reasons"]]
        return {"flights": len(sub), "flagged": len(flagged), "share": fa1.wilson(len(flagged), len(sub)),
                "by_reason": dict(Counter(r for d in sub for r in d["reasons"]).most_common(12)),
                "pilot_notes": sum(d["pilot_notes"] for d in sub)}

    H = [d for d in ok if d["half"] == "H"]
    D = [d for d in ok if d["half"] == "D"]
    res = {"declared": "research/false_alarms/measure_fa2.py", "read": len(ok), "unreadable": len(done) - len(ok),
           "H_good_or_great": summary([d for d in H if d["rating"] in GOOD]), "H_all": summary(H),
           "D_good_or_great": summary([d for d in D if d["rating"] in GOOD]), "D_all": summary(D),
           "pass_mark": "at most 20% of H's good-or-great flights flagged"}
    share = res["H_good_or_great"]["share"]
    res["FA2_met"] = bool(share and share[0] <= 0.20)
    json.dump(res, open(os.path.join(fa1.OUT, "fa2_results.json"), "w"), indent=1)
    g, a = res["H_good_or_great"], res["H_all"]
    md = ["# FA2: the revised warning rule on the held-out half H", "",
          "Declared in `research/false_alarms/measure_fa2.py`. Full numbers in `fa2_results.json`.", "",
          "| Flights (held-out half H) | Flagged | 95% interval |", "|---|---|---|",
          f"| {g['flights']} rated good or great | {g['flagged']} ({100 * g['share'][0]:.1f}%) | {100 * g['share'][1]:.1f}-{100 * g['share'][2]:.1f}% |",
          f"| All {a['flights']} | {a['flagged']} ({100 * a['share'][0]:.1f}%) | {100 * a['share'][1]:.1f}-{100 * a['share'][2]:.1f}% |",
          "", f"Pass mark: at most 20% of H's good-or-great flights. **{'Met' if res['FA2_met'] else 'Not met'}.**", "",
          "Reasons (all H flights): " + "; ".join(f"{k} {v}" for k, v in a["by_reason"].items()),
          f"Pilot notes (landed below 10% battery), shown but not a reason: {a['pilot_notes']} of {a['flights']} H flights."]
    open(os.path.join(fa1.OUT, "fa2_summary.md"), "w").write("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()
