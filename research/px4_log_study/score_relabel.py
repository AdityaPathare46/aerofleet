"""Score the independent relabelling: how far do uploader ratings agree with an independent expert reading the log?

PRE-DECLARED (committed and pushed before the expert's workbook is returned or opened). Status: exploratory (dagger).
The pack is built by make_relabel_pack.py (36 pilot-rated + 36 random aircraft-rated modelled crashes, seed 2080,
blind to rating, notes, log ID and date). The expert is not an author; the paper names their role, not their identity,
unless they agree to be acknowledged.

Expert verdicts: pilot / aircraft / environment / can't tell; "no crash visible" as a cause is reported separately.
Uploader ratings: crash_pilot -> pilot, crash_sw_hw -> aircraft.

R1 Agreement with the uploader on cases the expert decided as pilot or aircraft: raw agreement and Cohen's kappa
   (bootstrap 95% CI, 2,000 resamples, seed 2081); full 4 x 2 cross-table.
R2 Of the 36 pilot-rated crashes, the share the expert calls aircraft, and of the 36 aircraft-rated, the share called
   pilot; Wilson 95% intervals. Share "can't tell" and share "no crash visible" by rating.
R3 Does the null attribution result depend on the labels? Re-score against EXPERT labels (decided cases only), with
   bootstrap intervals (seed 2082):
     - the declared attribution rule (pilot_vs_drone verdicts as used in the paper; undecided counted wrong);
     - FlightMD's critical-finding verdict (m0 window, flightmd_scores.jsonl), if that study has run;
     - "tilt event present" as a one-feature classifier (AUC; r16_audit.crash_status).
   Wording rule (fixed now): the paper says the attribution failure is "not explained by uploader labels" if the rule's
   balanced accuracy against expert labels is below 0.70 with an interval that includes or lies below 0.6; it says
   "labels may explain part of the failure" if the balanced accuracy is >= 0.70.
R4 Expert confidence: R1 and R3 repeated on high- and medium-confidence verdicts only.
Limits stated in the output: one expert; 72 cases; plots, not the raw log; balanced sample, so shares in R2 are per
rating, not archive prevalences.

    python research/px4_log_study/score_relabel.py RETURNED_WORKBOOK.xlsx KEY_CSV DATA_ROOT
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
MAP = {"pilot": 0, "aircraft": 1}


def kappa(pairs):
    n = len(pairs)
    if not n:
        return np.nan
    po = sum(a == b for a, b in pairs) / n
    ca, cb = Counter(a for a, _ in pairs), Counter(b for _, b in pairs)
    pe = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / n ** 2
    return (po - pe) / (1 - pe) if pe < 1 else np.nan


def wilson(k, n, z=1.96):
    if n == 0:
        return [np.nan, np.nan]
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [float(c - h), float(c + h)]


def ba(y, v):
    y, v = np.asarray(y), np.asarray(v)
    if not ((y == 0).any() and (y == 1).any()):
        return np.nan
    return float((np.mean(v[y == 1] == 1) + np.mean(v[y == 0] == 0)) / 2)


def auc(y, s):
    y, s = np.asarray(y), np.asarray(s, float)
    p, q = s[y == 1], s[y == 0]
    if not len(p) or not len(q):
        return np.nan
    return float(((p[:, None] > q[None, :]).sum() + 0.5 * (p[:, None] == q[None, :]).sum()) / (len(p) * len(q)))


def boot(n, stat, seed):
    rng = np.random.default_rng(seed)
    vals = [stat(rng.integers(0, n, n)) for _ in range(2000)]
    vals = [v for v in vals if not np.isnan(v)]
    return [float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))]


def main(xlsx, key_csv, root):
    from openpyxl import load_workbook
    import postcrash_audit as pca
    from r16_audit import crash_status

    ws = load_workbook(xlsx, data_only=True)["Review"]
    E = {}
    for row in ws.iter_rows(min_row=2, values_only=True):
        if row[0]:
            E[int(row[0])] = {"verdict": (row[4] or "").strip().lower(), "cause": row[5], "conf": (row[6] or "").strip().lower()}
    key = {int(r["case"]): r for r in csv.DictReader(open(key_csv))}
    up = {c: ("pilot" if k["uploader_label"] == "pilot" else "aircraft") for c, k in key.items()}
    lid = {c: k["log_id"] for c, k in key.items()}
    out = {"n_cases": len(key), "n_returned": sum(1 for c in key if E.get(c, {}).get("verdict"))}
    cross = Counter((E.get(c, {}).get("verdict") or "blank", up[c]) for c in key)
    out["cross_table_expert_x_uploader"] = {f"{a}|{b}": n for (a, b), n in cross.items()}
    rule = {}
    for name in ("pilot_vs_drone.jsonl", "holdout.jsonl"):
        p = os.path.join(RESULTS, name)
        if os.path.exists(p):
            for line in open(p):
                r = json.loads(line)
                rule[r["log_id"]] = r.get("verdict")
    fmd = {}
    p = os.path.join(RESULTS, "flightmd_scores.jsonl")
    if os.path.exists(p):
        for line in open(p):
            r = json.loads(line)
            w = (r.get("windows") or {}).get("m0")
            if w:
                fmd[r["log"]] = int(any(f[1] == "critical" for f in w["findings"]))
    status = crash_status(pca.ulg_paths(root), list(lid.values()))

    def block(keep):
        dec = [c for c in key if E.get(c, {}).get("verdict") in MAP and keep(c)]
        pairs = [(E[c]["verdict"], up[c]) for c in dec]
        r = {"n_decided": len(dec), "agreement": float(np.mean([a == b for a, b in pairs])) if pairs else np.nan,
             "kappa": kappa(pairs)}
        r["kappa_ci"] = boot(len(pairs), lambda b: kappa([pairs[i] for i in b]), 2081) if pairs else None
        y = np.array([MAP[E[c]["verdict"]] for c in dec])
        rv = np.array([1 if rule.get(lid[c]) == "drone" else (0 if rule.get(lid[c]) == "pilot" else -1) for c in dec])
        r["rule_ba_vs_expert"] = ba(y, rv)
        r["rule_ba_ci"] = boot(len(y), lambda b: ba(y[b], rv[b]), 2082) if len(y) else None
        r["rule_ba_vs_uploader_same_cases"] = ba(np.array([MAP[up[c]] for c in dec]), rv)
        have = [i for i, c in enumerate(dec) if lid[c] in fmd]
        if have:
            yf, vf = y[have], np.array([fmd[lid[dec[i]]] for i in have])
            r["flightmd_ba_vs_expert"] = ba(yf, vf)
            r["flightmd_ba_ci"] = boot(len(yf), lambda b: ba(yf[b], vf[b]), 2083)
        tl = np.array([1 if status.get(lid[c]) in ("confirmed", "tilt_unconfirmed") else 0 for c in dec])
        r["tilt_auc_vs_expert"] = auc(y, tl)
        r["tilt_auc_ci"] = boot(len(y), lambda b: auc(y[b], tl[b]), 2084) if len(y) else None
        return r

    out["R1_R3_all"] = block(lambda c: True)
    out["R4_high_medium"] = block(lambda c: E[c]["conf"] in ("high", "medium"))
    r2 = {}
    for rating in ("pilot", "aircraft"):
        cs = [c for c in key if up[c] == rating]
        other = "aircraft" if rating == "pilot" else "pilot"
        k = sum(E.get(c, {}).get("verdict") == other for c in cs)
        r2[rating] = {"n": len(cs), f"called_{other}": k, "ci": wilson(k, len(cs)),
                      "cant_tell": sum(E.get(c, {}).get("verdict") == "can't tell" for c in cs),
                      "environment": sum(E.get(c, {}).get("verdict") == "environment" for c in cs),
                      "no_crash_visible": sum(E.get(c, {}).get("cause") == "no crash visible" for c in cs)}
    out["R2"] = r2
    a = out["R1_R3_all"]
    out["wording"] = ("labels may explain part of the failure" if a["rule_ba_vs_expert"] >= 0.70 else
                      "not explained by uploader labels" if a["rule_ba_ci"] and a["rule_ba_ci"][0] <= 0.6 else "undetermined")
    out["limits"] = "one expert; 72 cases; plots, not the raw log; balanced sample, R2 shares are per rating"
    json.dump(out, open(os.path.join(RESULTS, "relabel_scores.json"), "w"), indent=1, default=float)
    open(os.path.join(RESULTS, "relabel_scores.md"), "w").write(
        "# Independent relabelling\n\nDeclared in `research/px4_log_study/score_relabel.py`.\n\n```\n"
        + json.dumps(out, indent=1, default=float) + "\n```\n")
    print(json.dumps(out, indent=1, default=float))


if __name__ == "__main__":
    main(*sys.argv[1:4])
