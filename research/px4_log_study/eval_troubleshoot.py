"""Leave-one-out test of the troubleshooting search (aerofleet/assurance/troubleshoot.py).

DECLARED before running (engineering validation, not a hypothesis test).

Cases: the forum crash threads where the expert attributed the crash to the aircraft (or both) and named a cause
(expert_conclusion in {drone, both}, cause recorded).
Procedure: each case in turn is removed from the knowledge base; the search is built on the rest and queried with
  (a) the thread title only, a short description such as an operator would type, and
  (b) the title plus the descriptive terms of its opening post, a fuller description.
Measure: the share of cases whose expert cause is the search's first likely cause (top-1) and among its first
three (top-3), with 95% Wilson intervals; cases where the search returns no cause count as misses.
Baselines: always answering the most frequent cause among the other cases (top-1), and its three most frequent
causes (top-3).
Useful if: top-1 with the fuller description exceeds the top-1 baseline by at least 10 points. Either way the
result is reported; the search stays labelled as "where to look", not a diagnosis.

    python research/px4_log_study/eval_troubleshoot.py OUT_MD
"""
import json
import math
import os
import sys
from collections import Counter

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
sys.path.insert(0, ROOT)

from aerofleet.assurance import troubleshoot as ts  # noqa: E402


def wilson(k, n, z=1.96):
    if n == 0:
        return (float("nan"),) * 3
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return p, max(0.0, c - h), min(1.0, c + h)


def index_without(cases, held):
    rest = [c for c in cases if c is not held]
    case_ix = ts._BM25([ts.tokens(c["title"]) * 2 + c["terms"] for c in rest])
    causes = list(ts.PLAYBOOK)
    cause_ix = ts._BM25([ts.tokens(ts.PLAYBOOK[c]["symptoms"]) for c in causes])
    crash = [c for c in rest if c["is_crash"] and c["expert_conclusion"] in ("drone", "both")]
    return (rest, case_ix, causes, cause_ix, Counter(c["cause"] for c in crash), len(crash)), crash


def main(out_md):
    cases = json.load(open(ts.DATA))["cases"]
    eligible = [c for c in cases if c["is_crash"] and c["expert_conclusion"] in ("drone", "both") and c["cause"] in ts.PLAYBOOK]
    original = ts._index
    hits = {"title": [0, 0], "full": [0, 0]}
    base1 = base3 = 0
    try:
        for held in eligible:
            built, crash = index_without(cases, held)
            ts._index = lambda built=built: built
            freq = [c for c, _ in Counter(c["cause"] for c in crash).most_common(3)]
            base1 += freq[0] == held["cause"]
            base3 += held["cause"] in freq
            for name, query in (("title", held["title"]), ("full", held["title"] + " " + " ".join(held["terms"]))):
                ranked = [x["cause"] for x in ts.search(query, limit=5)["likely_causes"]]
                hits[name][0] += bool(ranked) and ranked[0] == held["cause"]
                hits[name][1] += held["cause"] in ranked[:3]
    finally:
        ts._index = original
    n = len(eligible)

    def row(label, k):
        p, lo, hi = wilson(k, n)
        return f"| {label} | {k} of {n} | {100 * p:.0f}% | {100 * lo:.0f}-{100 * hi:.0f}% |"

    L = ["# Leave-one-out test of the troubleshooting search", "",
         f"Cases: {n} forum crash threads where the expert blamed the aircraft and named a cause. Each was removed from the "
         "knowledge base and used as the query. Declared in `eval_troubleshoot.py`.", "",
         "| Answer | Correct | Rate | 95% CI |", "|---|---|---|---|",
         row("Top-1, title only", hits["title"][0]), row("Top-1, title and opening-post terms", hits["full"][0]),
         row("Top-1 baseline (most frequent cause)", base1),
         row("Top-3, title only", hits["title"][1]), row("Top-3, title and opening-post terms", hits["full"][1]),
         row("Top-3 baseline (three most frequent causes)", base3), "",
         f"Declared criterion (top-1 with the fuller description at least 10 points above the baseline): "
         f"{'met' if hits['full'][0] - base1 >= 0.10 * n else 'not met'}.",
         "", "Causes in the eligible cases: " + ", ".join(f"{c} {k}" for c, k in Counter(c['cause'] for c in eligible).most_common()) + "."]
    open(out_md, "w").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main(sys.argv[1])
