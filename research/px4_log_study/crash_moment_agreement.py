"""Crash-moment check: does the automatic crash moment agree with one author's reading of the traces?

PRE-DECLARED (committed and pushed before this script is run). Status: exploratory (dagger).

Data: crash_moment_review.csv, 50 crash logs drawn at random (seed 2036) for the crash-moment review sheet
(r15_crash_moment_sheet.png). One co-author labelled each panel by eye (column reviewer_2; reviewer_1 empty) as
correct / too early / too late / no crash visible / can't tell, without a second blind reviewer. The labels were made
before this script existed; the author saw the sheet's "auto-plausible / auto-implausible" panel titles.

Automatic status, as in the third robustness audit (r16_audit.crash_status): confirmed (tilt > 60 deg, then disarm or
landed/ground contact within 10 s), tilt_unconfirmed (tilt > 60 deg without that), fallback (no tilt > 60 deg; crash
moment = end of arming), unreadable.

Reported (descriptive, no hypothesis test):
  - cross-table of automatic status by human label;
  - share of panels the author labelled "correct" overall, among confirmed, tilt_unconfirmed and fallback logs;
  - of the logs the author labelled "correct", the share the confirmed rule also confirms (its recall) and, of the
    confirmed logs, the share labelled "correct" (its precision), each with an exact 95% Clopper-Pearson interval;
  - share of fallback logs labelled "no crash visible".
Limits stated in the output: one reviewer, not blind to the panel titles, 50 of 148 logs.

AMENDMENT 1 (27 Oct 2026, before any output): scipy failed to load (corrupted binary on the external drive), so the
Clopper-Pearson interval is computed exactly in plain Python. Nothing else changes.

    python research/px4_log_study/crash_moment_agreement.py DATA_ROOT
"""
import csv
import json
import os
import sys
from collections import Counter, defaultdict

from math import comb

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(SCRIPT_DIR)
import postcrash_audit as pca
from r16_audit import crash_status

RESULTS_DIR = os.path.join(SCRIPT_DIR, "..", "results", "px4_log_study")


def _tail(k, n, p, upper):
    """P(X >= k) if upper else P(X <= k), X ~ Binomial(n, p)."""
    r = range(k, n + 1) if upper else range(0, k + 1)
    return sum(comb(n, i) * p ** i * (1 - p) ** (n - i) for i in r)


def _solve(f, target):
    lo, hi = 0.0, 1.0
    for _ in range(100):
        mid = (lo + hi) / 2
        if f(mid) < target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def cp(k, n):
    """Exact Clopper-Pearson 95% interval (Amendment 1: plain Python; scipy failed to load)."""
    if n == 0:
        return [None, None]
    lo = 0.0 if k == 0 else _solve(lambda p: _tail(k, n, p, True), 0.025)
    hi = 1.0 if k == n else _solve(lambda p: -_tail(k, n, p, False), -0.025)
    return [lo, hi]


def main(root):
    rows = list(csv.DictReader(open(os.path.join(RESULTS_DIR, "crash_moment_review.csv"))))
    label = {r["log_id"]: r["reviewer_2"].strip() for r in rows}
    status = crash_status(pca.ulg_paths(root), sorted(label))
    table = defaultdict(Counter)
    for lid, lab in label.items():
        table[status[lid]][lab] += 1
    correct = [l for l in label if label[l] == "correct"]
    confirmed = [l for l in label if status[l] == "confirmed"]
    k_rec = sum(status[l] == "confirmed" for l in correct)
    k_prec = sum(label[l] == "correct" for l in confirmed)
    fallback = [l for l in label if status[l] == "fallback"]
    k_fb = sum(label[l] == "no crash visible" for l in fallback)
    out = {"n": len(label), "table": {k: dict(v) for k, v in table.items()},
           "correct_overall": [len(correct), len(label)],
           "correct_by_status": {s: [table[s]["correct"], sum(table[s].values())] for s in table},
           "confirmed_recall": [k_rec, len(correct), cp(k_rec, len(correct))],
           "confirmed_precision": [k_prec, len(confirmed), cp(k_prec, len(confirmed))],
           "fallback_no_crash": [k_fb, len(fallback), cp(k_fb, len(fallback))],
           "limits": "one reviewer, not blind to panel titles, 50 of 148 logs"}
    json.dump(out, open(os.path.join(RESULTS_DIR, "crash_moment_agreement.json"), "w"), indent=1)
    L = ["# Crash-moment check: automatic status vs one author's reading", "",
         "Declared in `research/px4_log_study/crash_moment_agreement.py`. One reviewer, not blind to panel titles.", "",
         "| Automatic status | " + " | ".join(sorted({l for v in table.values() for l in v})) + " |",
         "|---|" + "---|" * len({l for v in table.values() for l in v})]
    labs = sorted({l for v in table.values() for l in v})
    for s in sorted(table):
        L.append(f"| {s} | " + " | ".join(str(table[s][l]) for l in labs) + " |")
    L += ["", f"Labelled correct: {len(correct)} of {len(label)}.",
          f"Confirmed rule recall: {k_rec} of {len(correct)}; precision: {k_prec} of {len(confirmed)}.",
          f"Fallback logs labelled no crash visible: {k_fb} of {len(fallback)}."]
    open(os.path.join(RESULTS_DIR, "crash_moment_agreement.md"), "w").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "/Volumes/One Touch/AeroFleet_px4_data")
