"""Where does the council's F1 come from? Diagnostics for a mass-forensics study.

The headline macro-F1 is one number; this script decomposes it so it can be
reported honestly. Everything is recomputed from the study's own files —
`results.jsonl` (what the LLM council said) and `dataset_manifest.json` (the
ground truth) — with the same scoring rule as the study (`_score_factor`:
UNCERTAIN counts as "not contributed").

Sections:
  1. headline, reproduced (sanity check against the study report)
  2. naive baselines on the same labels (always-yes, prevalence-random)
  3. error anatomy — each false positive / false negative, classified
  4. abstention — metrics on the cases the council actually answered
  5. controls — how often it blames something when nothing failed
  6. confidence — is a 0.9+ confidence claim more trustworthy?
  7. deterministic claim check — the council's claims filtered through
     CONSTRAINT_TO_FACTOR (what the VR claim-check board does per incident)

Caveat printed with section 7: in this synthetic dataset the labels are a
deterministic function of the violated margins, so the geometry filter is an
upper bound on precision, not an independent result.

usage: python -m research.f1_diagnostics [--study-dir scenario_reports/mass_forensics_final] [--out research/results/f1_diagnostics.md]
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List

from aerofleet.agents.incident_taxonomy import CONSTRAINT_TO_FACTOR
from scenario_engine.incident_forensics_evaluation import _score_factor
from scenario_engine.mass_forensics_evaluation import _refresh_state
from scenario_engine.mass_forensics_dataset import load_manifest

C, N, U = "CONTRIBUTED", "NOT_CONTRIBUTED", "UNCERTAIN"
PARSE_FAIL = "could not parse"


def _load_rows(path: Path) -> Dict[str, Dict]:
    """Completed rows, selected exactly as the study does (_refresh_state: the first successful
    attempt per case is kept and never overwritten by a later failure)."""
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    latest, _counts, completed_ids, _excluded = _refresh_state(rows, retry_max=10**9)
    return {cid: latest[cid] for cid in completed_ids}


def _f1(tp: int, fp: int, fn: int) -> float:
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    return 2 * p * r / (p + r) if p + r else 0.0


def _pct(x: float) -> str:
    return f"{100 * x:.1f}%"


def analyse(study_dir: Path) -> str:
    manifest = {c.case_id: c for c in load_manifest(study_dir / "dataset_manifest.json")}
    rows = _load_rows(study_dir / "results.jsonl")
    cases = [(manifest[cid], row) for cid, row in rows.items() if cid in manifest]

    # Ground truth per factor, exactly as the study scores it.
    records = []  # (case, factor, gt, pred, confidence, evidence)
    for case, row in cases:
        gt_map = case.to_labeled_incident().ground_truth
        for factor, gt in gt_map.items():
            records.append((case, factor, gt, row["predictions"].get(factor, U),
                            (row.get("confidence") or {}).get(factor), (row.get("evidence") or {}).get(factor) or ""))
    factors = sorted({r[1] for r in records if any(x[1] == r[1] and x[2] == C for x in records)})

    out: List[str] = []
    w = out.append
    w(f"# Council F1 diagnostics — {study_dir}\n")
    w(f"{len(cases)} completed cases × {len(factors)} scorable factors "
      f"(factors with no positive case in the pool are excluded, as in the study).\n")

    # 1. headline
    w("## 1. Headline (reproduced)\n")
    w("| factor | prevalence | precision | recall | F1 | UNCERTAIN rate |")
    w("|---|---|---|---|---|---|")
    per = {}
    for f in factors:
        rs = [r for r in records if r[1] == f]
        s = _score_factor(f, [r[3] for r in rs], [r[2] for r in rs])
        s["prev"] = sum(r[2] == C for r in rs) / len(rs)
        s["unc"] = sum(r[3] == U for r in rs) / len(rs)
        per[f] = s
        w(f"| {f} | {_pct(s['prev'])} | {s['precision']:.3f} | {s['recall']:.3f} | **{s['f1']:.3f}** | {_pct(s['unc'])} |")
    macro = sum(s["f1"] for s in per.values()) / len(per)
    w(f"\n**Macro-F1 {macro:.4f}**, macro-precision {sum(s['precision'] for s in per.values()) / len(per):.4f}, "
      f"macro-recall {sum(s['recall'] for s in per.values()) / len(per):.4f}.\n")

    # 2. baselines
    w("## 2. Naive baselines on the same labels\n")
    w("A classifier that ignores the evidence. *Always-yes* predicts CONTRIBUTED for every factor of every case; "
      "*prevalence-random* says CONTRIBUTED with probability equal to the factor's prevalence (expected F1 = prevalence).\n")
    w("| factor | council F1 | always-yes F1 | prevalence-random F1 |")
    w("|---|---|---|---|")
    ay, pr = [], []
    for f, s in per.items():
        a = _f1(s["tp"] + s["fn"], s["fp"] + s["tn"], 0)
        ay.append(a); pr.append(s["prev"])
        w(f"| {f} | {s['f1']:.3f} | {a:.3f} | {s['prev']:.3f} |")
    w(f"| **macro** | **{macro:.3f}** | {sum(ay) / len(ay):.3f} | {sum(pr) / len(pr):.3f} |\n")

    # 3. error anatomy
    w("## 3. Error anatomy\n")
    key_re = re.compile("|".join(sorted(CONSTRAINT_TO_FACTOR, key=len, reverse=True)))
    fp_kinds, fn_kinds = Counter(), Counter()
    fp_by_factor = defaultdict(Counter)
    for case, f, gt, pred, conf, ev in records:
        if f not in per:
            continue
        low = ev.lower()
        if pred == C and gt == N:
            cited = {CONSTRAINT_TO_FACTOR[k] for k in key_re.findall(ev)}
            if cited and f not in cited:
                kind = "cross-attribution: cites another factor's violated constraint as its own evidence"
            elif not case.margins or all(v >= 0 for v in case.margins.values()):
                kind = "blamed a factor although nothing was violated (control case)"
            else:
                kind = "other unsupported claim"
            fp_kinds[kind] += 1
            fp_by_factor[f][kind] += 1
        elif gt == C and pred != C:
            if PARSE_FAIL in low:
                kind = "agent response could not be parsed (pipeline failure, not a judgement)"
            elif pred == U:
                kind = "abstained (UNCERTAIN)"
            else:
                kind = "said NOT_CONTRIBUTED (a real miss)"
            fn_kinds[kind] += 1
    tot_fp, tot_fn = sum(fp_kinds.values()), sum(fn_kinds.values())
    w(f"**False positives: {tot_fp}**\n")
    for k, v in fp_kinds.most_common():
        w(f"- {k}: {v} ({_pct(v / tot_fp)})")
    w(f"\n**False negatives: {tot_fn}**\n")
    for k, v in fn_kinds.most_common():
        w(f"- {k}: {v} ({_pct(v / tot_fn)})")
    w("")

    # 4. abstention
    w("## 4. When the council does answer\n")
    w("Scoring only the factor-verdicts that are not UNCERTAIN and not a parse failure "
      "(coverage = share of verdicts kept).\n")
    w("| factor | coverage | precision | recall | F1 |")
    w("|---|---|---|---|---|")
    sel_f1 = []
    for f in per:
        rs = [r for r in records if r[1] == f and r[3] != U and PARSE_FAIL not in r[5].lower()]
        allr = [r for r in records if r[1] == f]
        s = _score_factor(f, [r[3] for r in rs], [r[2] for r in rs]) if rs else {"precision": 0, "recall": 0, "f1": 0}
        sel_f1.append(s["f1"])
        w(f"| {f} | {_pct(len(rs) / len(allr))} | {s['precision']:.3f} | {s['recall']:.3f} | {s['f1']:.3f} |")
    w(f"| **macro** | | | | **{sum(sel_f1) / len(sel_f1):.3f}** |\n")

    # 5. controls
    w("## 5. Control cases (nothing violated)\n")
    ctrl = [(case, row) for case, row in cases if case.category == "control"]
    blamed = sum(1 for case, row in ctrl if any(row["predictions"].get(f) == C for f in per))
    claims = sum(1 for case, row in ctrl for f in per if row["predictions"].get(f) == C)
    w(f"{len(ctrl)} control cases. The council blamed at least one factor in **{blamed} ({_pct(blamed / max(len(ctrl), 1))})**, "
      f"{claims} false claims in total. (Per-category F1 is 0.0 for controls by construction — there are no positives to recall — "
      f"so the false-alarm rate is the meaningful number here.)\n")

    # 6. confidence
    w("## 6. Does stated confidence mean anything?\n")
    w("| council confidence on a CONTRIBUTED claim | claims | precision |")
    w("|---|---|---|")
    for lo, hi, label in [(0.9, 1.01, "≥ 0.9"), (0.7, 0.9, "0.7 – 0.9"), (-1, 0.7, "< 0.7")]:
        cl = [r for r in records if r[1] in per and r[3] == C and r[4] is not None and lo <= r[4] < hi]
        if cl:
            w(f"| {label} | {len(cl)} | {sum(r[2] == C for r in cl) / len(cl):.3f} |")
    w("")

    # 7. deterministic claim check
    w("## 7. Council claims filtered by the deterministic claim check\n")
    w("A CONTRIBUTED claim is kept only if a violated CBF constraint maps to that factor "
      "(`CONSTRAINT_TO_FACTOR`, the same rule the VR claim-check board applies to each incident). "
      "The filter can only withdraw claims, never add them.\n")
    w("| factor | precision | recall | F1 |")
    w("|---|---|---|---|")
    filt = []
    for f in per:
        preds, gts = [], []
        for case, ff, gt, pred, conf, ev in records:
            if ff != f:
                continue
            implicated = {CONSTRAINT_TO_FACTOR[k] for k, v in case.margins.items() if v < 0 and k in CONSTRAINT_TO_FACTOR}
            preds.append(C if pred == C and f in implicated else (N if pred == C else pred))
            gts.append(gt)
        s = _score_factor(f, preds, gts)
        filt.append(s["f1"])
        w(f"| {f} | {s['precision']:.3f} | {s['recall']:.3f} | {s['f1']:.3f} |")
    w(f"| **macro** | | | **{sum(filt) / len(filt):.3f}** |\n")
    w("> Caveat: this dataset's labels are generated from the violated margins, so the filter's precision is "
      "an upper bound on this benchmark, not independent evidence. What it does show is that every one of the "
      "council's false positives is detectable without an LLM — which is why the claim check, not the council, "
      "is what an operator is shown as the verdict.\n")
    return "\n".join(out)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--study-dir", default="scenario_reports/mass_forensics_final")
    ap.add_argument("--out", default="research/results/f1_diagnostics.md")
    a = ap.parse_args()
    report = analyse(Path(a.study_dir))
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(report + "\n")
    print(report)


if __name__ == "__main__":
    main()
