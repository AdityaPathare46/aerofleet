"""Crash-moment check, second reviewer: agreement between two authors, and the archive estimate under each.

PRE-DECLARED (committed and pushed before this script is run). Status: exploratory (dagger).

Data:
  - Reviewer A: crash_moment_review.csv, column reviewer_2 (one author, labelled the unblinded sheet
    r15_crash_moment_sheet.png, which shows the automatic plausible/implausible verdict in each title).
  - Reviewer B: crash_moment_review_blind.csv (a second author, labelled crash_moment_sheet_blind.png: the same 50 logs
    in a new random order, titles "Panel N" only, without access to reviewer A's labels or the panel key).
  - crash_moment_blind_key.json maps reviewer B's panels to log ids.
  Labels: correct / too early / too late / no crash visible / can't tell.

Reported (descriptive; reported whatever the result):
  1. Cross-table A x B; raw agreement and Cohen's kappa on the five labels over all 50 logs.
  2. Binary "the log contains the crash" (correct, too early, too late = yes; no crash visible = no; can't tell
     excluded for that reviewer): agreement and kappa on logs both reviewers could decide.
  3. Binary "the computed crash moment is right" (correct = yes; everything else = no; can't tell excluded):
     agreement and kappa.
  4. Each reviewer's share of "correct" by automatic status (confirmed / tilt_unconfirmed / fallback), with the
     status taken from crash_moment_agreement.json's inputs (recomputed with r16_audit.crash_status).
  5. The archive-wide estimate of the share of crash-rated multicopter logs that contain the crash, recomputed
     exactly as archive_label_audit R3 (share_tilt = 132 of 341 readable multicopter logs from
     archive_label_audit.json; P(contains | status) from the review), separately for reviewer A, reviewer B, and the
     logs on which they agree; 95% bootstrap interval, 2,000 resamples, seed 2046.
Limits stated in the output: two reviewers; reviewer A was not blind to the automatic verdict; 50 logs from the
modelled sample.

    python research/px4_log_study/crash_moment_interrater.py DATA_ROOT
"""
import csv
import json
import os
import sys
from collections import Counter, defaultdict

import numpy as np

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(SCRIPT_DIR)
import postcrash_audit as pca
from r16_audit import crash_status

RESULTS_DIR = os.path.join(SCRIPT_DIR, "..", "results", "px4_log_study")
LABELS = ["correct", "too early", "too late", "no crash visible", "can't tell"]
CONTAINS = {"correct": 1, "too early": 1, "too late": 1, "no crash visible": 0}


def kappa(pairs, cats):
    n = len(pairs)
    if n == 0:
        return None, None
    po = sum(a == b for a, b in pairs) / n
    ca, cb = Counter(a for a, _ in pairs), Counter(b for _, b in pairs)
    pe = sum(ca[c] * cb[c] for c in cats) / n ** 2
    return po, (po - pe) / (1 - pe) if pe < 1 else None


def main(root):
    A = {r["log_id"]: r["reviewer_2"].strip().lower() for r in csv.DictReader(open(os.path.join(RESULTS_DIR, "crash_moment_review.csv")))}
    key = json.load(open(os.path.join(RESULTS_DIR, "crash_moment_blind_key.json")))["panel_to_log_id"]
    B = {key[str(int(r["panel"]))]: r["label"].strip().lower() for r in csv.DictReader(open(os.path.join(RESULTS_DIR, "crash_moment_review_blind.csv")))}
    assert set(A) == set(B) and len(A) == 50, "reviewers must cover the same 50 logs"
    for lab in list(A.values()) + list(B.values()):
        assert lab in LABELS, f"unknown label {lab!r}"
    logs = sorted(A)
    status = crash_status(pca.ulg_paths(root), logs)
    out = {"n": len(logs)}
    table = defaultdict(Counter)
    for l in logs:
        table[A[l]][B[l]] += 1
    out["cross_table_A_rows_B_cols"] = {a: dict(table[a]) for a in LABELS if table[a]}
    po, k = kappa([(A[l], B[l]) for l in logs], LABELS)
    out["five_labels"] = {"agreement": po, "kappa": k}
    pairs = [(CONTAINS[A[l]], CONTAINS[B[l]]) for l in logs if A[l] in CONTAINS and B[l] in CONTAINS]
    po, k = kappa(pairs, [0, 1])
    out["contains_crash"] = {"n_both_decided": len(pairs), "agreement": po, "kappa": k}
    pairs = [(A[l] == "correct", B[l] == "correct") for l in logs if A[l] != "can't tell" and B[l] != "can't tell"]
    po, k = kappa(pairs, [True, False])
    out["crash_moment_right"] = {"n": len(pairs), "agreement": po, "kappa": k}
    by = {}
    for who, R in (("A", A), ("B", B)):
        d = defaultdict(lambda: [0, 0])
        for l in logs:
            d[status[l]][1] += 1
            d[status[l]][0] += R[l] == "correct"
        by[who] = {s: v for s, v in d.items()}
    out["correct_by_status"] = by
    arch_json = json.load(open(os.path.join(RESULTS_DIR, "archive_label_audit.json")))["R3"]
    n_read = arch_json["readable_rotary"]
    n_tilt = int(round(arch_json["share_tilt"] * n_read))
    arch = np.array([1] * n_tilt + [0] * (n_read - n_tilt))
    tilt = lambda l: status[l] in ("confirmed", "tilt_unconfirmed")

    def estimate(R, sel):
        lt = [CONTAINS[R[l]] for l in sel if tilt(l) and R[l] in CONTAINS]
        lf = [CONTAINS[R[l]] for l in sel if not tilt(l) and status[l] != "unreadable" and R[l] in CONTAINS]
        f = lambda a, t, fb: a.mean() * np.mean(t) + (1 - a.mean()) * np.mean(fb)
        rng = np.random.default_rng(2046)
        boot = [f(rng.choice(arch, len(arch)), rng.choice(lt, len(lt)), rng.choice(lf, len(lf))) for _ in range(2000)]
        return {"contains_given_tilt": [int(sum(lt)), len(lt)], "contains_given_fallback": [int(sum(lf)), len(lf)],
                "estimate": float(f(arch, lt, lf)), "ci95": [float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))]}

    agree = [l for l in logs if A[l] in CONTAINS and B[l] in CONTAINS and CONTAINS[A[l]] == CONTAINS[B[l]]]
    out["archive_estimate"] = {"A": estimate(A, logs), "B": estimate(B, logs), "agreed_logs": estimate(A, agree)}
    out["limits"] = "two reviewers; A not blind to the automatic verdict; 50 logs from the modelled sample"
    json.dump(out, open(os.path.join(RESULTS_DIR, "crash_moment_interrater.json"), "w"), indent=1, default=float)
    open(os.path.join(RESULTS_DIR, "crash_moment_interrater.md"), "w").write(
        "# Crash-moment check: two reviewers\n\nDeclared in `research/px4_log_study/crash_moment_interrater.py`.\n\n```\n"
        + json.dumps(out, indent=1, default=float) + "\n```\n")
    print(json.dumps(out, indent=1, default=float))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "/Volumes/One Touch/AeroFleet_px4_data")
