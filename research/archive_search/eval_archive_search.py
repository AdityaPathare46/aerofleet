"""Does the public-archive search connect what pilots write with what logs show? Declared test.

DECLARED BEFORE RUNNING (committed and pushed before the first run). Engineering validation of the "Search the public
log archive" feature (aerofleet/assurance/archive_search.py, log_signs.py). Fixed as they were at commit e0c43be: the
word list SIGN_WORDS, the sign rules, and the archive index built on 24 Nov 2026 by tools/build_archive_index.py
(2,521 readable public PX4 logs on this computer, signs computed by AeroFleet's own reader). Nothing is tuned here.

What the feature claims: when a person describes a problem in words, the words point to signs (poor GPS, compass data
rejected, critical battery, ...), and the search returns public logs that show those signs. That is only useful if the
signs a description's words point to are signs the described flight's own log tends to show. Each public log here has
its uploader's own description, so the description and the log of the SAME flight can be compared.

DATA. Local public logs in the index that (a) carry uploader text and (b) whose text names at least one sign by the
fixed word list. To stop test benches that upload the same note hundreds of times from dominating, one log is kept per
distinct text (texts compared lower-case with digits replaced; the first log id in sorted order is kept).

A1 (primary). Hit: at least one sign the text names is among the signs the same flight's log shows.
  Baseline: the same word-sign sets shuffled across the same logs, 2,000 permutations (seed 0); one-sided p is
  (permutations with a hit rate >= observed + 1) / 2,001.
  Useful if: p <= 0.05 AND the observed hit rate is at least 1.5 times the mean permuted hit rate.
A2 (descriptive). Per sign: how many texts name it, the share of those flights whose log shows it, the share of all
  eligible flights whose log shows it, and the ratio. No pass mark.
A3 (descriptive, reported either way). Do flights with similar log signs share outcomes? Among local logs with at
  least one sign and an uploader rating, for each crash-rated flight (crash_sw_hw, crash_pilot) and each good-rated
  flight (good, great, BRAVO!), the 10 other logs with the highest sign overlap (Jaccard, ties by log id) and the
  crash share among the rated ones. Difference in mean crash share, crash queries minus good queries, with a 2,000
  label-permutation p. The local logs were downloaded for a crash study, so crashes are over-represented: any
  difference describes this sample and is not a risk score, which the product never presents it as.

Also reported: how many local logs carry text, and the share whose text names any sign (coverage).
Outputs only counts and rates (no uploader text) to research/results/archive_search/.

    python research/archive_search/eval_archive_search.py
"""
from __future__ import annotations

import json
import os
import random
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
OUT = os.path.join(ROOT, "research", "results", "archive_search")
PERMS = 2000
CRASH = {"crash_sw_hw", "crash_pilot"}
GOOD = {"good", "great", "BRAVO!"}


def main() -> None:
    from aerofleet.assurance.archive_search import index
    from aerofleet.assurance.log_signs import SIGNS, signs_from_words, similarity

    ix = index()
    if ix is None:
        sys.exit("archive index not built: run tools/build_archive_index.py")
    logs = sorted(ix.logs, key=lambda r: r["id"])
    with_text = [r for r in logs if r.get("text")]
    seen, eligible = set(), []
    for r in with_text:
        key = re.sub(r"\d+", "#", r["text"].lower())
        words = signs_from_words(r["text"])
        if not words or key in seen:
            continue
        seen.add(key)
        eligible.append((words, set(r["signs"])))
    n = len(eligible)

    def rate(pairs):
        return sum(1 for w, s in pairs if w & s) / len(pairs)

    observed = rate(eligible)
    rng = random.Random(0)
    words_only = [w for w, _ in eligible]
    perm = []
    for _ in range(PERMS):
        rng.shuffle(words_only)
        perm.append(rate(list(zip(words_only, [s for _, s in eligible]))))
    mean_perm = sum(perm) / len(perm)
    p = (sum(1 for x in perm if x >= observed) + 1) / (PERMS + 1)
    lift = observed / mean_perm if mean_perm else float("inf")
    a1 = {"eligible_flights": n, "hit_rate": round(observed, 4), "permuted_mean": round(mean_perm, 4),
          "lift": round(lift, 2), "p_one_sided": round(p, 5), "useful": bool(p <= 0.05 and lift >= 1.5)}

    a2 = []
    for sign in SIGNS:
        named = [(w, s) for w, s in eligible if sign in w]
        shown_all = sum(1 for _, s in eligible if sign in s) / n
        if named:
            shown = sum(1 for _, s in named if sign in s) / len(named)
            a2.append({"sign": sign, "texts_naming_it": len(named), "shown_when_named": round(shown, 3),
                       "shown_overall": round(shown_all, 3), "ratio": round(shown / shown_all, 2) if shown_all else None})

    rated = [r for r in logs if r["signs"] and r.get("rating")]
    sets = {r["id"]: set(r["signs"]) for r in rated}

    def crash_share_of_neighbours(q):
        others = sorted((r for r in rated if r["id"] != q["id"]),
                        key=lambda r: (-similarity(sets[q["id"]], sets[r["id"]]), r["id"]))[:10]
        return sum(1 for r in others if r["rating"] in CRASH) / len(others) if others else 0.0

    queries = [r for r in rated if r["rating"] in CRASH | GOOD]
    share = {r["id"]: crash_share_of_neighbours(r) for r in queries}
    labels = [r["rating"] in CRASH for r in queries]
    vals = [share[r["id"]] for r in queries]

    def diff(lab):
        c = [v for v, l in zip(vals, lab) if l]
        g = [v for v, l in zip(vals, lab) if not l]
        return (sum(c) / len(c) - sum(g) / len(g)) if c and g else 0.0

    d_obs = diff(labels)
    lab = labels[:]
    rng = random.Random(0)
    perm_d = []
    for _ in range(PERMS):
        rng.shuffle(lab)
        perm_d.append(diff(lab))
    p3 = (sum(1 for x in perm_d if abs(x) >= abs(d_obs)) + 1) / (PERMS + 1)
    a3 = {"crash_queries": sum(labels), "good_queries": len(labels) - sum(labels),
          "mean_crash_share_crash_queries": round(sum(v for v, l in zip(vals, labels) if l) / max(1, sum(labels)), 3),
          "mean_crash_share_good_queries": round(sum(v for v, l in zip(vals, labels) if not l) / max(1, len(labels) - sum(labels)), 3),
          "difference": round(d_obs, 3), "p_two_sided": round(p3, 5)}

    out = {"declared": "research/archive_search/eval_archive_search.py", "index_logs": len(logs),
           "logs_with_text": len(with_text), "coverage_text_names_a_sign": round(sum(1 for r in with_text if signs_from_words(r["text"])) / max(1, len(with_text)), 3),
           "A1": a1, "A2": a2, "A3": a3}
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "results.json"), "w") as f:
        json.dump(out, f, indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
