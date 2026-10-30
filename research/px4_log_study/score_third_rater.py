"""Score the third (non-author) rater on the crash-moment check.

PRE-DECLARED (committed and pushed before the pack is sent and before the form is returned). Status: exploratory
(dagger). Rater C labels the same blind 50-panel sheet as reviewer B (crash_moment_sheet_blind.png; panel ids mapped by
crash_moment_blind_key.json). Labels: correct / too early / too late / no crash visible / can't tell.
Limitation stated in the output: the panel key and both earlier reviewers' labels are public in the repository; C is
asked not to open it, which cannot be verified.

Reported, whatever the result (definitions as crash_moment_interrater.py):
  T1 Pairwise Cohen's kappa C-A, C-B (and A-B for reference) and Fleiss' kappa for A, B, C, on (i) "computed crash
     moment is right" (correct vs not; can't tell excluded) and (ii) "log contains the crash" (correct / too early /
     too late vs no crash visible); bootstrap 95% intervals over logs (2,000, seed 2100).
  T2 Share judged correct by crash status (confirmed / tilt_unconfirmed / fallback) and by aircraft type, as r19_audit.
  T3 Disputed logs (A and B differ on "contains crash"): with which reviewer C agrees, counts.
  T4 Archive estimate of the share of crash-rated multicopter logs that contain the crash (crash_moment_interrater
     method, seed 2101) under C's labels and under the majority of A, B, C.
  Wording rule (fixed now): the paper reports a single archive figure only if Fleiss' kappa on "contains crash" is
  >= 0.6; otherwise it keeps the range across reviewers. If C agrees with B on >= 2/3 of disputed logs the paper says
  the third rater sided with the blind reviewer, and conversely for A; otherwise that the dispute is unresolved.

    python research/px4_log_study/score_third_rater.py RETURNED_FORM.xlsx DATA_ROOT
"""
import csv
import json
import os
import sys
from collections import Counter

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.append(HERE)
RESULTS = os.path.join(HERE, "..", "results", "px4_log_study")
LABELS = ["correct", "too early", "too late", "no crash visible", "can't tell"]
CONTAINS = {"correct": 1, "too early": 1, "too late": 1, "no crash visible": 0}


def kappa(pairs):
    n = len(pairs)
    if not n:
        return np.nan
    po = sum(a == b for a, b in pairs) / n
    ca, cb = Counter(a for a, _ in pairs), Counter(b for _, b in pairs)
    pe = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / n ** 2
    return (po - pe) / (1 - pe) if pe < 1 else np.nan


def fleiss(rows):
    """rows: list of label tuples (one per item, all raters present)."""
    if not rows:
        return np.nan
    cats = sorted({x for r in rows for x in r})
    n, m = len(rows), len(rows[0])
    P = [(sum(r.count(c) ** 2 for c in cats) - m) / (m * (m - 1)) for r in rows]
    p = [sum(r.count(c) for r in rows) / (n * m) for c in cats]
    pe = sum(x * x for x in p)
    return (np.mean(P) - pe) / (1 - pe) if pe < 1 else np.nan


def boot(items, stat, seed):
    rng = np.random.default_rng(seed)
    vals = [stat([items[i] for i in rng.integers(0, len(items), len(items))]) for _ in range(2000)]
    vals = [v for v in vals if not np.isnan(v)]
    return [float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))] if vals else None


def main(xlsx, root):
    from openpyxl import load_workbook
    import postcrash_audit as pca
    from r16_audit import crash_status

    key = json.load(open(os.path.join(RESULTS, "crash_moment_blind_key.json")))["panel_to_log_id"]
    A = {r["log_id"]: r["reviewer_2"].strip().lower() for r in csv.DictReader(open(os.path.join(RESULTS, "crash_moment_review.csv")))}
    B = {key[str(int(r["panel"]))]: r["label"].strip().lower() for r in csv.DictReader(open(os.path.join(RESULTS, "crash_moment_review_blind.csv")))}
    C = {}
    for row in load_workbook(xlsx, data_only=True)["Review"].iter_rows(min_row=2, values_only=True):
        if row[0] and row[1]:
            lab = str(row[1]).strip().lower()
            assert lab in LABELS, f"unknown label {lab!r}"
            C[key[str(int(row[0]))]] = lab
    logs = sorted(set(A) & set(B) & set(C))
    out = {"n_A_B_C": len(logs), "n_returned": len(C)}
    defs = {"right": lambda x: None if x == "can't tell" else x == "correct",
            "contains": lambda x: CONTAINS.get(x)}
    for name, f in defs.items():
        res = {}
        for p, (X, Y) in {"C-A": (C, A), "C-B": (C, B), "A-B": (A, B)}.items():
            items = [(f(X[l]), f(Y[l])) for l in logs if f(X[l]) is not None and f(Y[l]) is not None]
            res[p] = {"n": len(items), "kappa": kappa(items), "ci": boot(items, kappa, 2100)}
        trip = [(f(A[l]), f(B[l]), f(C[l])) for l in logs if None not in (f(A[l]), f(B[l]), f(C[l]))]
        res["fleiss"] = {"n": len(trip), "kappa": fleiss(trip), "ci": boot(trip, fleiss, 2100)}
        out[f"T1_{name}"] = res
    status = crash_status(pca.ulg_paths(root), logs)
    out["T2_correct_by_status"] = {s: [sum(C[l] == "correct" for l in logs if status[l] == s), sum(status[l] == s for l in logs)]
                                   for s in sorted(set(status.values()))}
    disputed = [l for l in logs if CONTAINS.get(A[l]) is not None and CONTAINS.get(B[l]) is not None and CONTAINS[A[l]] != CONTAINS[B[l]]]
    side = Counter("A" if CONTAINS.get(C[l]) == CONTAINS[A[l]] else ("B" if CONTAINS.get(C[l]) == CONTAINS[B[l]] else "undecided") for l in disputed)
    out["T3_disputed"] = {"n": len(disputed), **dict(side)}
    arch = json.load(open(os.path.join(RESULTS, "archive_label_audit.json")))["R3"]
    n_read, share = arch["readable_rotary"], arch["share_tilt"]
    tilt = lambda l: status[l] in ("confirmed", "tilt_unconfirmed")

    def estimate(lab, seed=2101):
        lt = [lab[l] for l in logs if tilt(l) and lab.get(l) is not None]
        lf = [lab[l] for l in logs if not tilt(l) and status[l] != "unreadable" and lab.get(l) is not None]
        a = np.array([1] * int(round(share * n_read)) + [0] * (n_read - int(round(share * n_read))))
        f = lambda a_, t, fb: a_.mean() * np.mean(t) + (1 - a_.mean()) * np.mean(fb)
        rng = np.random.default_rng(seed)
        bs = [f(rng.choice(a, len(a)), rng.choice(lt, len(lt)), rng.choice(lf, len(lf))) for _ in range(2000)]
        return {"estimate": float(f(a, lt, lf)), "ci": [float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))]}

    labC = {l: CONTAINS.get(C[l]) for l in logs}
    maj = {}
    for l in logs:
        v = [CONTAINS.get(x[l]) for x in (A, B, C) if CONTAINS.get(x[l]) is not None]
        maj[l] = int(sum(v) * 2 > len(v)) if len(v) >= 2 and sum(v) * 2 != len(v) else None
    out["T4_archive_estimate"] = {"C": estimate(labC), "majority": estimate(maj)}
    fk = out["T1_contains"]["fleiss"]["kappa"]
    out["wording"] = {"single_archive_figure": bool(fk >= 0.6),
                      "dispute": ("sided with blind reviewer B" if disputed and side["B"] >= 2 / 3 * len(disputed) else
                                  "sided with reviewer A" if disputed and side["A"] >= 2 / 3 * len(disputed) else "unresolved")}
    out["limits"] = "key and earlier labels public in the repository; C asked not to open it; 50 logs"
    json.dump(out, open(os.path.join(RESULTS, "third_rater.json"), "w"), indent=1, default=float)
    open(os.path.join(RESULTS, "third_rater.md"), "w").write(
        "# Crash-moment check: third rater\n\nDeclared in `research/px4_log_study/score_third_rater.py`.\n\n```\n"
        + json.dumps(out, indent=1, default=float) + "\n```\n")
    print(json.dumps(out, indent=1, default=float))


if __name__ == "__main__":
    main(*sys.argv[1:3])
