"""Held-out test of the two signals seen in the first pilot-vs-drone run, plus how often each sign fires on
normal flights.

PRE-DECLARED (committed before any held-out log was downloaded):

The first run (pilot_vs_drone.md, 93 crashes) suggested, after looking at the results:
  H1  accelerometer clipping (D_CLIP: clipping count > 50 between arming and the crash) is more common in
      crashes the uploader blamed on the drone than in crashes blamed on the pilot.
  H2  flying in MANUAL mode at the crash moment is more common in pilot-blamed crashes than in drone-blamed ones.
Each is tested once, one-sided Fisher exact, on the 123 held-out crashes; supported if p < 0.025 (0.05 split over
the two tests).

Also reported, with no pass mark:
  - Rule v1 (unchanged, from pilot_vs_drone.py) re-run on the held-out crashes: does its 0.57 replicate?
  - Rule v2: D_CLIP -> DRONE; else MANUAL at the crash -> PILOT; else UNKNOWN. Balanced accuracy and coverage.
  - For normal (good/great) flights, the share in which each sign fires, using the end of the armed period as
    the "crash" moment. A sign that fires often on normal flights is not evidence of a fault.

    python research/px4_log_study/holdout_test.py HOLDOUT_CSV LOG_DIR OUT_DIR
"""
import csv
import json
import math
import os
import sys
from collections import Counter

from pyulog import ULog

from pilot_vs_drone import TOPICS, evidence

SIGNS = ("D_BATT", "D_MOTOR", "D_CLIP", "D_GPS", "D_FD", "D_ERR", "D_CPU", "D_FAILSAFE")


def fisher_one_sided(a, b, c, d):
    """P(X >= a) for [[a, b], [c, d]] with fixed margins (a = 'more' cell)."""
    n, r1, c1 = a + b + c + d, a + b, a + c
    pr = lambda x: math.comb(c1, x) * math.comb(n - c1, r1 - x) / math.comb(n, r1)  # noqa: E731
    return sum(pr(x) for x in range(a, min(r1, c1) + 1))


def score(rows, key):
    cm = Counter((r["label"], r[key]) for r in rows)
    rec = {lab: cm[(lab, lab)] / max(1, cm[(lab, "drone")] + cm[(lab, "pilot")]) for lab in ("drone", "pilot")}
    dec = sum(1 for r in rows if r[key] != "unknown")
    wrong = sum(1 for r in rows if r[key] not in ("unknown", r["label"]))
    return cm, (rec["drone"] + rec["pilot"]) / 2, dec, wrong


def main(sel_csv, log_dir, out_dir):
    rows, skipped = [], Counter()
    for r in csv.DictReader(open(sel_csv)):
        try:
            res, why = evidence(ULog(os.path.join(log_dir, r["group"], r["log_id"] + ".ulg"), message_name_filter_list=TOPICS))
        except Exception as e:
            res, why = None, type(e).__name__
        if res is None:
            skipped[(r["group"], why)] += 1
            continue
        res.update(group=r["group"], log_id=r["log_id"], mav_type=r["mav_type"],
                   label={"crash_sw_hw": "drone", "crash_pilot": "pilot"}.get(r["rating"], "normal"))
        ev = res["evidence"]
        res["v2"] = "drone" if ev.get("D_CLIP") else ("pilot" if res["mode_at_crash"] == 0 else "unknown")
        rows.append(res)
    with open(os.path.join(out_dir, "holdout.jsonl"), "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")

    crash = [r for r in rows if r["group"] == "crash"]
    normal = [r for r in rows if r["group"] == "normal"]
    dr, pi = [r for r in crash if r["label"] == "drone"], [r for r in crash if r["label"] == "pilot"]
    L = ["# Held-out test: PX4 crash benchmark, step 2", "",
         f"Held-out crashes analysed: {len(crash)} ({len(dr)} drone-blamed, {len(pi)} pilot-blamed); normal flights: "
         f"{len(normal)}. Skipped: {dict((f'{g}: {w}', n) for (g, w), n in skipped.items())}.",
         "Hypotheses and pass marks were committed before these logs were downloaded (`holdout_test.py`).", "",
         "## Pre-declared hypotheses (one-sided Fisher exact, supported if p < 0.025)", "",
         "| | Drone-blamed | Pilot-blamed | p | Result |", "|---|---|---|---|---|"]
    d_clip = [r for r in dr if "D_CLIP" in r["evidence"]]
    p_clip = [r for r in pi if "D_CLIP" in r["evidence"]]
    a, c = sum(r["evidence"]["D_CLIP"] for r in d_clip), sum(r["evidence"]["D_CLIP"] for r in p_clip)
    p1 = fisher_one_sided(a, len(d_clip) - a, c, len(p_clip) - c)
    L.append(f"| H1 clipping | {a} of {len(d_clip)} | {c} of {len(p_clip)} | {p1:.3f} | {'supported' if p1 < 0.025 else 'not supported'} |")
    a2, c2 = sum(r["mode_at_crash"] == 0 for r in pi), sum(r["mode_at_crash"] == 0 for r in dr)
    p2 = fisher_one_sided(a2, len(pi) - a2, c2, len(dr) - c2)
    L.append(f"| H2 MANUAL at crash | {c2} of {len(dr)} | {a2} of {len(pi)} | {p2:.3f} | {'supported' if p2 < 0.025 else 'not supported'} |")
    L += ["", "## Rules on the held-out crashes", "", "| Rule | Answered | Wrong (of all) | Balanced accuracy (answered) |",
          "|---|---|---|---|"]
    for key, name in (("verdict", "v1 (as declared before the first run)"), ("v2", "v2 (clipping, then MANUAL)")):
        cm, bal, dec, wrong = score(crash, key)
        L.append(f"| {name} | {dec} of {len(crash)} | {wrong} ({100 * wrong / max(1, len(crash)):.0f}%) | {bal:.2f} |")
    L += ["", "## How often each sign fires", "", "| Sign | Drone-blamed crashes | Pilot-blamed crashes | Normal flights |",
          "|---|---|---|---|"]
    frac = lambda xs, k: (sum(r["evidence"][k] for r in xs if k in r["evidence"]), sum(1 for r in xs if k in r["evidence"]))  # noqa: E731
    for k in SIGNS:
        cells = []
        for xs in (dr, pi, normal):
            n1, n0 = frac(xs, k)
            cells.append(f"{n1} of {n0} ({100 * n1 / max(1, n0):.0f}%)")
        L.append(f"| {k} | " + " | ".join(cells) + " |")
    v1n = sum(r["verdict"] == "drone" for r in normal)
    L += ["", f"Rule v1 would have called {v1n} of {len(normal)} normal flights a drone fault "
          f"({100 * v1n / max(1, len(normal)):.0f}%).", "",
          "## Limits", "",
          "- Uploader labels are unchecked. Normal flights are those rated good/great by their uploader.",
          "- For normal flights the 'crash moment' is the end of the armed period, so late-window signs cover landing."]
    open(os.path.join(out_dir, "holdout.md"), "w").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main(*sys.argv[1:4])
