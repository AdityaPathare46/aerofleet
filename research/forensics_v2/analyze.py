"""Score every condition on every dataset with the study's own rule, plus what a paper needs:
95% bootstrap CIs over cases, a paired McNemar test against C0, and the failure-mode rates the
interventions target.

  python -m research.forensics_v2.analyze   →  research/results/forensics_v2/summary.md
"""
from __future__ import annotations

import json
import math
import random
from pathlib import Path
from typing import Dict, List, Tuple

from aerofleet.agents.incident_taxonomy import CONSTRAINT_TO_FACTOR
from research.forensics_v2.conditions import CORE_FACTORS
from scenario_engine.incident_forensics_evaluation import _score_factor

RESULTS = Path("research/results/forensics_v2")
C, N, U = "CONTRIBUTED", "NOT_CONTRIBUTED", "UNCERTAIN"
PARSE_FAIL = "could not parse"


def load(path: Path) -> List[dict]:
    return [r for r in (json.loads(l) for l in path.read_text().splitlines() if l.strip()) if r.get("predictions")]


def truth(row: dict, factor: str) -> str:
    return C if factor in row["positive_factors"] else N


def macro_f1(rows: List[dict]) -> float:
    f1s = []
    for f in CORE_FACTORS:
        preds = [r["predictions"].get(f, U) for r in rows]
        gts = [truth(r, f) for r in rows]
        if C in gts:
            f1s.append(_score_factor(f, preds, gts)["f1"])
    return sum(f1s) / len(f1s) if f1s else float("nan")


def bootstrap_ci(rows: List[dict], iters: int = 1000, seed: int = 0) -> Tuple[float, float]:
    rng = random.Random(seed)
    vals = sorted(macro_f1([rows[rng.randrange(len(rows))] for _ in rows]) for _ in range(iters))
    return vals[int(0.025 * iters)], vals[int(0.975 * iters) - 1]


def rates(rows: List[dict]) -> Dict[str, float]:
    verdicts = [(r, f) for r in rows for f in CORE_FACTORS]
    parse = sum(PARSE_FAIL in (r.get("evidence") or {}).get(f, "").lower() or f not in r["predictions"] for r, f in verdicts)
    cross = cross_n = 0
    for r, f in verdicts:
        if truth(r, f) == N and any(v < 0 for v in r["margins"].values()):
            cross_n += 1
            cross += r["predictions"].get(f) == C
    controls = [r for r in rows if r["category"] == "control"]
    ctrl_fa = sum(any(r["predictions"].get(f) == C for f in CORE_FACTORS) for r in controls)
    return {"parse_fail": parse / len(verdicts), "cross_attr": cross / max(cross_n, 1),
            "control_false_alarm": ctrl_fa / max(len(controls), 1)}


def mcnemar(base: List[dict], other: List[dict]) -> Tuple[int, int, float]:
    """Paired over (case, factor) correctness; returns (b, c, two-sided exact p)."""
    bmap = {r["case_id"]: r for r in base}
    b = c = 0
    for r in other:
        r0 = bmap.get(r["case_id"])
        if not r0:
            continue
        for f in CORE_FACTORS:
            ok0 = (r0["predictions"].get(f, U) == C) == (truth(r0, f) == C)
            ok1 = (r["predictions"].get(f, U) == C) == (truth(r, f) == C)
            b += ok0 and not ok1
            c += ok1 and not ok0
    n = b + c
    if n == 0:
        return b, c, 1.0
    k = min(b, c)
    p = sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n * 2
    return b, c, min(p, 1.0)


def main() -> None:
    lines = ["# Forensics v2 — interventions measured on unseen cases\n",
             "Macro-F1 over the 5 core factors (study scoring rule), 95% bootstrap CI over cases, "
             "McNemar (paired, per case×factor correctness) against C0. b = C0 right / this wrong, "
             "c = C0 wrong / this right.\n"]
    for ds_dir in sorted(p for p in RESULTS.iterdir() if p.is_dir()):
        lines += [f"\n## {ds_dir.name}\n",
                  "| condition | cases | macro-F1 | 95% CI | parse-fail | cross-attr FP | control false alarm | vs C0 (b / c, p) | median s/case |",
                  "|---|---|---|---|---|---|---|---|---|"]
        base = load(ds_dir / "C0.jsonl") if (ds_dir / "C0.jsonl").exists() else []
        for path in sorted(ds_dir.glob("C*.jsonl")):
            rows = load(path)
            if not rows:
                continue
            lo, hi = bootstrap_ci(rows)
            rt = rates(rows)
            lat = sorted(r["latency_s"] for r in rows)[len(rows) // 2]
            vs = "—"
            if base and path.stem != "C0":
                common = {r["case_id"] for r in base} & {r["case_id"] for r in rows}
                b, c, p = mcnemar([r for r in base if r["case_id"] in common], [r for r in rows if r["case_id"] in common])
                vs = f"{b} / {c}, p={p:.3g}"
            lines.append(f"| {path.stem} | {len(rows)} | **{macro_f1(rows):.3f}** | {lo:.3f}–{hi:.3f} | "
                         f"{rt['parse_fail']:.1%} | {rt['cross_attr']:.1%} | {rt['control_false_alarm']:.1%} | {vs} | {lat:.0f} |")
    out = RESULTS / "summary.md"
    out.write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
