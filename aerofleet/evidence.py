"""Recompute the paper's headline results from the committed data, and show when each test was declared.

This is how an examiner can check a claim on the spot: each function below reads a result file committed with the
paper (research/results/px4_log_study/), recomputes the number with the same arithmetic as the study's scripts, and
returns it with the commit that declared the test (hypothesis and pass mark) and the commit that added the result.
No raw log and no model is needed, so it runs in about a second. The screening lift needs 24 GB of logs to recompute;
it is read from its stored result and labelled as such.

The rank and bootstrap arithmetic mirrors research/px4_log_study/paper_figures.py (_within_ranks, _between_ranks, _ci);
tests/unit/test_evidence.py checks that both give the same numbers.
"""
from __future__ import annotations

import json
import subprocess
import time
from collections import Counter, defaultdict
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "research" / "results" / "px4_log_study"


def _ci(x: np.ndarray):
    """Mean and 95% bootstrap interval, the same seed and draws as the paper's figure script."""
    rng = np.random.default_rng(0)
    boots = rng.choice(x, (10000, len(x))).mean(1)
    return float(x.mean()), float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))


def _exact_p(sizes: List[int], observed: float, draws: int = 100_000) -> float:
    """One-sided p from draws of the exact null: each drone's rank uniform over its own n+1 positions (the declared
    test in within_drone.py / rough_drone_test.py, seed 0)."""
    rng = np.random.default_rng(0)
    null = np.zeros(draws)
    for n in sizes:
        null += rng.integers(0, n + 1, draws) / n
    null /= len(sizes)
    return float((null >= observed).mean())


def _jsonl(name: str) -> List[Dict[str, Any]]:
    return [json.loads(line) for line in open(RES / name)]


def heldout_attribution() -> Dict[str, Any]:
    """Balanced accuracy of the declared rule (v1) on the 112 held-out crashes: mean recall over the two labels,
    counting only crashes the rule answered (holdout_test.py, score())."""
    crash = [r for r in _jsonl("holdout.jsonl") if r["group"] == "crash"]
    cm = Counter((r["label"], r["verdict"]) for r in crash)
    rec = {lab: cm[(lab, lab)] / max(1, cm[(lab, "drone")] + cm[(lab, "pilot")]) for lab in ("drone", "pilot")}
    answered = sum(1 for r in crash if r["verdict"] != "unknown")
    return {"value": (rec["drone"] + rec["pilot"]) / 2, "n": len(crash),
            "detail": f"{answered} of {len(crash)} crashes answered; aircraft-blamed recall {rec['drone']:.2f}, pilot-blamed {rec['pilot']:.2f}"}


def within_drone(feature: str = "vib_p95") -> Dict[str, Any]:
    """Scaled rank of each crash flight among the same drone's earlier flights (same measurement, at least 3)."""
    rows = _jsonl("within_drone_features.jsonl")
    src = {"vib_p95": "src_vib", "tune_rms": "src_tune"}[feature]
    crash = {r["crash_id"]: r for r in rows if r["role"] == "crash" and r["features"]}
    ranks, sizes = [], []
    for cid, c in crash.items():
        cv = c["features"].get(feature)
        ev = [r["features"][feature] for r in rows if r["role"] == "earlier" and r["crash_id"] == cid and r["features"]
              and r["features"].get(feature) is not None and r["features"].get(src) == c["features"].get(src)]
        if cv is not None and len(ev) >= 3:
            ranks.append(sum(v < cv for v in ev) / len(ev))
            sizes.append(len(ev))
    m, lo, hi = _ci(np.array(ranks))
    return {"value": m, "ci": [lo, hi], "n": len(ranks), "p": _exact_p(sizes, m),
            "detail": f"{len(ranks)} drones; 0.50 means no difference"}


def between_drones(feature: str = "vib_p95") -> Dict[str, Any]:
    """Scaled rank of each later-crashed drone among its matched drones, on ordinary flights (median per drone)."""
    rows = _jsonl("rough_drone_features.jsonl")
    src = {"vib_p95": "src_vib", "tune_rms": "src_tune"}[feature]
    sets: Dict[str, Dict[str, list]] = defaultdict(lambda: defaultdict(list))
    role = {}
    for r in rows:
        sets[r["set_id"]][r["vehicle"]].append(r)
        role[(r["set_id"], r["vehicle"])] = r["role"]

    def value(rs):
        vals = defaultdict(list)
        for r in rs:
            f = r["features"]
            if f and f.get(feature) is not None:
                vals[f.get(src)].append(f[feature])
        return {s: float(np.median(v)) for s, v in vals.items() if len(v) >= 2}

    ranks, sizes = [], []
    for sid, vehicles in sets.items():
        case = [v for v in vehicles if role[(sid, v)] == "case"]
        if not case:
            continue
        for s, cv in value(vehicles[case[0]]).items():
            ctrl = [value(vehicles[v]).get(s) for v in vehicles if role[(sid, v)] == "control"]
            ctrl = [c for c in ctrl if c is not None]
            if ctrl:
                ranks.append(sum(c < cv for c in ctrl) / len(ctrl))
                sizes.append(len(ctrl))
            break                                            # one measurement per set, as in the study
    m, lo, hi = _ci(np.array(ranks))
    return {"value": m, "ci": None, "n": len(ranks), "p": _exact_p(sizes, m),
            "detail": (f"{len(ranks)} matched sets; 0.50 means no difference. Bootstrap interval {lo:.3f} to {hi:.3f}; Figure 5 "
                       "draws its bars from a generator shared with other panels, so its lower end reads 0.57")}


def screening_lift() -> Dict[str, Any]:
    d = json.loads((RES / "screening_reference.json").read_text())
    return {"value": float(d["mean"]["10"]["lift_fleet"]), "ci": [float(x) for x in d["ci95"]["10|lift_fleet"]],   # top-decile flag
            "n": d.get("n_reference_drones"), "stored": True,
            "detail": f"read from the stored result: {d.get('n_reference_drones')} non-crash reference drones; recomputing needs the 24 GB of logs"}


CLAIMS = [
    {"id": "attribution", "claim": "Logs cannot tell pilot from aircraft causes", "paper": "0.47 balanced accuracy on 112 held-out crashes",
     "paper_text": "A fixed rule reached 0.47 balanced accuracy on 112 held-out crashes (pass mark 0.70)", "expect": 0.47, "digits": 2,
     "fn": heldout_attribution, "script": "research/px4_log_study/holdout_test.py",
     "declared": "af6fab2", "result": "da92ec3", "data": "research/results/px4_log_study/holdout.jsonl", "pass_mark": "0.70: not reached"},
    {"id": "within", "claim": "No warning against the drone's own earlier flights", "paper": "mean rank 0.48 [0.38, 0.58], p = 0.67, 61 drones",
     "paper_text": "$\\bar r=0.48$, 95\\% CI 0.38--0.58, $p=0.67$, 61 drones", "expect": 0.48, "digits": 2,
     "fn": within_drone, "script": "research/px4_log_study/within_drone.py",
     "declared": "8b417d2", "result": "c9ebca4", "data": "research/results/px4_log_study/within_drone_features.jsonl", "pass_mark": "p < 0.025: not supported"},
    {"id": "between", "claim": "Later-crashed drones vibrated more than matched drones", "paper": "mean rank 0.67, p = 0.0023 as declared, 60 sets",
     "paper_text": "$\\bar r=0.67$, $p=0.0023$", "expect": 0.67, "digits": 2,
     "fn": between_drones, "script": "research/px4_log_study/rough_drone_test.py",
     "declared": "d7a6574", "result": "a76babb", "data": "research/results/px4_log_study/rough_drone_features.jsonl", "pass_mark": "supported as declared; suggestive under stricter tests"},
    {"id": "screening", "claim": "A vibration screen did not clearly beat random inspection", "paper": "lift 1.77 [1.00, 2.60] against 412 non-crash drones",
     "paper_text": "a top-decile threshold gave a lift of only $1.77\\times$ [1.00, 2.60]", "expect": 1.77, "digits": 2,
     "fn": screening_lift, "script": "research/px4_log_study/screening_reference.py",
     "declared": "4961234", "result": "77a0bc1", "data": "research/results/px4_log_study/screening_reference.json", "pass_mark": "not shown to beat random inspection"},
]


@lru_cache(maxsize=32)
def _commit(sha: str) -> Optional[Dict[str, str]]:
    """Date and subject of a commit, from the repository itself (None if git or the commit is not available)."""
    try:
        out = subprocess.run(["git", "log", "-1", "--format=%h%x1f%aI%x1f%s", sha], cwd=ROOT, capture_output=True,
                             text=True, timeout=10, check=True).stdout.strip()
        h, when, subject = out.split("\x1f")
        return {"commit": h, "date": when, "subject": subject}
    except (OSError, subprocess.SubprocessError, ValueError):
        return None


def claims() -> List[Dict[str, Any]]:
    out = []
    for c in CLAIMS:
        t0 = time.perf_counter()
        r = c["fn"]()
        ms = round(1000 * (time.perf_counter() - t0))
        shown = None if r.get("value") is None else round(r["value"], c["digits"])
        dec, res = _commit(c["declared"]), _commit(c["result"])
        out.append({k: c[k] for k in ("id", "claim", "paper", "script", "data", "pass_mark")} | {
            "recomputed": shown, "raw": r.get("value"), "ci": [round(x, 2) for x in r["ci"]] if r.get("ci") else None,
            "n": r.get("n"), "p": r.get("p"), "detail": r["detail"], "stored": r.get("stored", False), "ms": ms,
            "matches_paper": shown is not None and abs(shown - c["expect"]) < 10 ** -c["digits"] / 2 + 1e-9,
            "declared": dec or {"commit": c["declared"]}, "result_commit": res or {"commit": c["result"]},
            "declared_before_result": bool(dec and res and dec["date"] < res["date"])})
    return out
