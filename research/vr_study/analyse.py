"""Analyse the VR debrief study exactly as declared in research/vr_study/PROTOCOL.md (V1-V5).

Run once, after the last participant. Reads the answers from the app's database (table vr_study_responses), judges
them against research/vr_study/trials_key.json, and writes to research/results/vr_study/:
  responses.csv   one row per measured answer (code, condition, block, trial, answer, right, seconds); no names exist
  results.json    V1-V5
  summary.md      the table for the report
Participants: codes P01-P99 with both blocks complete; P00 (pilot) and practice answers are never analysed.

    python research/vr_study/analyse.py
"""
from __future__ import annotations

import csv
import json
import os
import statistics
import sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
OUT = os.environ.get("VR_STUDY_OUT") or os.path.join(ROOT, "research", "results", "vr_study")   # override only for a dry run
KEY = os.path.join(ROOT, "research", "vr_study", "trials_key.json")
N_TRIALS = 15


def main() -> None:
    from scipy.stats import wilcoxon

    from aerofleet.api.routes.vr_study import GROUPS
    from aerofleet.data.database import get_db_session
    from aerofleet.data.models.models import VrStudyResponse

    key = json.load(open(KEY))
    with get_db_session() as db:
        rows = [(r.participant, r.condition, r.trial_id, r.answer, r.ms) for r in db.query(VrStudyResponse).all()]
    by_p = defaultdict(list)
    prefs = {}
    for p, cond, tid, ans, ms in rows:
        if p == "P00":
            continue
        if cond == "preference":
            prefs[p] = ans
        elif cond in ("2d", "headset"):
            by_p[p].append((cond, tid, ans, ms))
    complete = sorted(p for p, a in by_p.items() if Counter(c for c, *_ in a) == Counter({"2d": N_TRIALS, "headset": N_TRIALS}))
    incomplete = sorted(set(by_p) - set(complete))

    out_rows, per = [], {}
    for p in complete:
        first = GROUPS[int(p[1:]) % 4][0][0]
        acc, sec = {}, {}
        for cond in ("2d", "headset"):
            a = [(tid, ans, ms) for c, tid, ans, ms in by_p[p] if c == cond]
            right = [ans == key[tid]["answer"] for tid, ans, _ in a]
            acc[cond] = sum(right) / len(right)
            sec[cond] = statistics.median((ms or 0) / 1000 for *_, ms in a)
            for (tid, ans, ms), ok in zip(a, right):
                out_rows.append({"participant": p, "condition": cond, "block": 1 if cond == first else 2, "trial": tid,
                                 "version": f"{key[tid]['answer']} {key[tid]['size_m']:g} m", "answer": ans, "right": int(ok),
                                 "seconds": round((ms or 0) / 1000, 2)})
        per[p] = {"accuracy": acc, "median_s": sec, "first": first}

    def paired(metric):
        h = [per[p][metric]["headset"] for p in complete]
        d = [per[p][metric]["2d"] for p in complete]
        diffs = [a - b for a, b in zip(h, d)]
        p_val = wilcoxon(h, d, alternative="two-sided").pvalue if any(diffs) else 1.0
        return {"headset_mean": round(statistics.mean(h), 3), "2d_mean": round(statistics.mean(d), 3),
                "headset_median": round(statistics.median(h), 3), "2d_median": round(statistics.median(d), 3),
                "p_two_sided": round(float(p_val), 4), "participants": len(complete)}

    res = {"participants_complete": complete, "participants_incomplete": incomplete}
    if len(complete) >= 2:
        v1 = paired("accuracy")
        v1["outcome"] = ("supported: headset higher" if v1["p_two_sided"] < 0.05 and v1["headset_mean"] > v1["2d_mean"]
                         else "2D higher" if v1["p_two_sided"] < 0.05 else "no difference detectable")
        res["V1_accuracy"] = v1
        res["V2_median_seconds"] = paired("median_s")
    v3 = defaultdict(lambda: {"right": 0, "n": 0})
    conf = {c: Counter() for c in ("2d", "headset")}
    for r in out_rows:
        k = f"{r['condition']} | {r['version']}"
        v3[k]["right"] += r["right"]
        v3[k]["n"] += 1
        conf[r["condition"]][f"{r['version'].split()[0]} -> {r['answer']}"] += 1
    res["V3_by_version"] = {k: {**v, "share": round(v["right"] / v["n"], 3)} for k, v in sorted(v3.items())}
    res["V3_confusion"] = {c: dict(sorted(v.items())) for c, v in conf.items()}
    res["V4_preference"] = dict(Counter(prefs[p] for p in complete if p in prefs))
    blocks = defaultdict(list)
    for r in out_rows:
        blocks[r["block"]].append(r["right"])
    res["V5_by_block"] = {b: round(sum(v) / len(v), 3) for b, v in sorted(blocks.items())}

    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "responses.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["participant", "condition", "block", "trial", "version", "answer", "right", "seconds"])
        w.writeheader()
        w.writerows(out_rows)
    json.dump(res, open(os.path.join(OUT, "results.json"), "w"), indent=1)
    v1, v2 = res.get("V1_accuracy"), res.get("V2_median_seconds")
    md = ["# VR debrief study: results", "", "Declared in `research/vr_study/PROTOCOL.md`. Full numbers in `results.json`.", "",
          f"Participants with both blocks complete: {len(complete)}" + (f"; incomplete: {', '.join(incomplete)}" if incomplete else ""), ""]
    if v1:
        md += ["| Test | Headset | 2D | p (two-sided) | Outcome |", "|---|---|---|---|---|",
               f"| V1 share answered right (mean) | {v1['headset_mean']:.0%} | {v1['2d_mean']:.0%} | {v1['p_two_sided']} | {v1['outcome']} |",
               f"| V2 median seconds per flight (mean of participants) | {v2['headset_mean']:.1f} | {v2['2d_mean']:.1f} | {v2['p_two_sided']} | descriptive comparison |",
               "", f"Preference: {res['V4_preference']}. Share right by block: {res['V5_by_block']}."]
    open(os.path.join(OUT, "summary.md"), "w").write("\n".join(md) + "\n")
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
