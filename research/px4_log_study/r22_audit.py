"""Round 22 audit: how many crashes the tilt rule misses (multicopters only, with intervals), the published detector by
day and with length-matched windows, and a duration check on the injected-fault flights.

PRE-DECLARED (committed and pushed before this script is run). Status: exploratory (dagger), declared after the
twenty-second internal review; not blind: the review's own rough recomputation (about 9-61%) is known.

PART A - Share of crashes the tilt rule misses (review problem 1)
  Population: readable crash-rated multicopter logs in the archive (archive_label_audit R3: 341, of which share_tilt =
  132/341 are tilt-defined). Reviewed logs: the 34 multicopter logs among the 50 reviewed (index mav_type), with each
  rater's labels (A: first reviewer; B: blind reviewer; C: third rater; M: majority of the three, ties excluded).
  For rater R, among reviewed multicopter logs of status s (tilt-defined or fallback):
    found_s   = share labelled "correct" (the computed moment marks the crash);
    contains_s = share labelled correct, too early or too late (the log contains a crash; "can't tell" excluded).
  Archive shares: found = p_t * found_tilt + (1 - p_t) * found_fallback; contains = p_t * contains_tilt
  + (1 - p_t) * contains_fallback, with p_t = 132/341.
  Missed share = 1 - found / contains (the share of crash-containing logs whose computed moment does not mark the crash).
  Also the variant that ignores fallback moments judged correct (found_fallback set to 0), for comparison with the
  earlier figure. 95% intervals: 2,000 bootstrap resamples (seed 2150) of the 341 archive logs and of the reviewed
  logs within each status.
  Wording rule: the paper reports the per-rater point estimates and the range of their intervals; it says "most" only
  for raters whose interval lies wholly above 50%.

PART B - The published detector by day and with length-matched windows (review problem 3)
  Same re-implementation, windows and seeds as r21_audit A (no change to the network or training).
  B1 Per-day AUC: for the day-grouped fault-vs-normal task (A3) and the day-grouped pre-fault task (A5), AUC within
     each of the four days that contain fault-free flights, from the seed-averaged out-of-fold scores, and the
     size-weighted mean.
  B2 Length- and phase-matched pre-fault windows: for every flight, keep only windows that end no later than
     take-off + s, where s is the pseudo-onset offset of rflymad_eval for that flight pattern (the window fault-free
     flights already use); fault flights keep pre-fault windows only within that span (flights whose injection comes
     before take-off + s keep their windows up to the injection). Then the pre-fault task grouped by flight and by day,
     100 flight-level permutations (seed 2151).
  Wording rule: the paper says the detector "separates fault flights before the fault even with matched windows" only
  if the B2 flight-grouped AUC >= 0.70 with p < 0.05; otherwise that the pre-fault separation depends on window span.

AMENDMENT 1 (after an interrupted first run, before any B result was saved): in B1 a mixed day can hold no fault
  windows of the task's positive class, which made the size-weighted mean undefined (nan). The mean is now taken over
  days with both classes, and one-class days are listed. Parts A and C ran unchanged and are kept; Part B is rerun.

PART C - Duration on the injected-fault flights (review problem 3)
  C1 AUC of window length alone (pre-fault window length; whole-flight length) for fault vs fault-free flights
     (rflymad_eval sample).
  C2 The study's 11 features on length- and phase-matched pre-fault windows ([take-off, take-off + s], s as B2; fault
     flights whose injection is earlier use [take-off, injection]) recomputed from the logs (leak_curve.window_features),
     logistic regression (factorial_audit) with folds grouped by day and stratified, 200 permutations (seed 2152).
  Wording rule: the paper says the feature separation "survives length matching" if the C2 day-grouped AUC has
  permutation p < 0.05.

Outputs: research/results/px4_log_study/r22_audit.md and .json.

    PYTHONPATH=. ~/.venvs/torch/bin/python research/px4_log_study/r22_audit.py DATA_ROOT RFLYMAD_DIR
"""
import csv
import gzip
import json
import os
import re
import sys
from collections import defaultdict

import numpy as np

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(SCRIPT_DIR)
import factorial_audit as fa
import r21_audit as r21

RESULTS_DIR = os.path.join(SCRIPT_DIR, "..", "results", "px4_log_study")
MULTI = ("Quadrotor", "Hexarotor", "Octorotor")
CONTAINS = {"correct", "too early", "too late"}


def ci(v):
    v = [x for x in v if x == x]
    return [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))]


# ---------------------------------------------------------------- A

def part_a(root, db):
    import postcrash_audit as pca
    from openpyxl import load_workbook
    from r16_audit import crash_status

    key = json.load(open(os.path.join(RESULTS_DIR, "crash_moment_blind_key.json")))["panel_to_log_id"]
    A = {r["log_id"]: r["reviewer_2"].strip().lower() for r in csv.DictReader(open(os.path.join(RESULTS_DIR, "crash_moment_review.csv")))}
    B = {key[str(int(r["panel"]))]: r["label"].strip().lower() for r in csv.DictReader(open(os.path.join(RESULTS_DIR, "crash_moment_review_blind.csv")))}
    C = {}
    wb = load_workbook(os.path.join(SCRIPT_DIR, "relabel_pack", "returned", "crash_moment_form.xlsx"), data_only=True)
    for row in wb["Review"].iter_rows(min_row=2, values_only=True):
        if row[0] and row[1]:
            C[key[str(int(row[0]))]] = str(row[1]).strip().lower()
    logs = [l for l in sorted(A) if db.get(l, {}).get("mav_type") in MULTI]
    st = crash_status(pca.ulg_paths(root), logs)
    tilt = lambda l: st[l] in ("confirmed", "tilt_unconfirmed")
    M = {}
    for l in logs:
        votes = [x[l] for x in (A, B, C)]
        best = max(set(votes), key=votes.count)
        if votes.count(best) >= 2:
            M[l] = best
    arch = json.load(open(os.path.join(RESULTS_DIR, "archive_label_audit.json")))["R3"]
    n_arch, p_t = arch["readable_rotary"], arch["share_tilt"]
    arch_vec = np.array([1] * int(round(p_t * n_arch)) + [0] * (n_arch - int(round(p_t * n_arch))))

    def est(lt, lf, pt, ignore_fallback_found=False):
        def rates(lab):
            dec = [x for x in lab if x != "can't tell"]
            return (np.mean([x == "correct" for x in dec]) if dec else np.nan,
                    np.mean([x in CONTAINS for x in dec]) if dec else np.nan)
        ft, ct = rates(lt)
        ff, cf = rates(lf)
        if ignore_fallback_found:
            ff = 0.0
        found = pt * ft + (1 - pt) * ff
        contains = pt * ct + (1 - pt) * cf
        return 1 - found / contains if contains > 0 else np.nan

    out = {"n_reviewed_multicopter": len(logs), "n_tilt": sum(map(tilt, logs)), "share_tilt": p_t}
    for name, R in (("A", A), ("B", B), ("C", C), ("majority", M)):
        lt = [R[l] for l in logs if l in R and tilt(l)]
        lf = [R[l] for l in logs if l in R and not tilt(l) and st[l] != "unreadable"]
        rng = np.random.default_rng(2150)
        bs, bs0 = [], []
        for _ in range(2000):
            pt = rng.choice(arch_vec, len(arch_vec)).mean()
            bt, bf = list(rng.choice(lt, len(lt))), list(rng.choice(lf, len(lf)))
            bs.append(est(bt, bf, pt))
            bs0.append(est(bt, bf, pt, True))
        out[name] = {"n_tilt": len(lt), "n_fallback": len(lf),
                     "tilt_correct": sum(x == "correct" for x in lt), "fallback_correct": sum(x == "correct" for x in lf),
                     "missed": est(lt, lf, p_t), "ci": ci(bs),
                     "missed_ignoring_fallback_found": est(lt, lf, p_t, True), "ci_ignoring": ci(bs0)}
    out["wording_most"] = {k: bool(out[k]["ci"][0] > 0.5) for k in ("A", "B", "C", "majority")}
    return out


# ---------------------------------------------------------------- B

def part_b(rdir):
    data = r21.load_rflymad(rdir)
    R = [json.loads(l) for l in open(os.path.join(RESULTS_DIR, "rflymad_scores.jsonl"))]
    meta = {}
    off = defaultdict(list)
    for r in R:
        if "error" not in r and r["t_f"] is not None:
            off[r["status"]].append((r["t_f"] - r["t0"]) / 1e6)
    allo = [x for v in off.values() for x in v]
    for r in R:
        if "error" in r:
            continue
        s = min(max(int(round(np.median(off.get(r["status"]) or allo))), 10), 120)
        meta[r["case"] + "|" + r["path"]] = s
    out = {}

    def per_day(task_pos, task_neg, name):
        sel = [(w, 1 if k in task_pos else 0, f, d) for w, k, f, d in data if k in task_pos or k in task_neg]
        X = np.stack([s[0] for s in sel]); y = np.array([s[1] for s in sel]); dy = [s[3] for s in sel]
        S = np.mean([r21.grouped_cv(X, y, dy, seed) for seed in range(5)], axis=0)
        mixed = sorted({d for d, t in zip(dy, y) if t == 0})
        per = []
        for d in mixed:
            idx = [i for i, dd in enumerate(dy) if dd == d]
            per.append({"day": d, "n_windows": len(idx), "n_neg": int((y[idx] == 0).sum()), "auc": fa.auc(y[idx], S[idx])})
        both = [p for p in per if p["auc"] == p["auc"]]   # amendment 1: a day with one class has no AUC
        out[name] = {"per_day": per, "one_class_days": [p["day"] for p in per if p["auc"] != p["auc"]],
                     "weighted_mean": float(sum(p["n_windows"] * p["auc"] for p in both) / sum(p["n_windows"] for p in both)) if both else None}
        print(name, out[name]["weighted_mean"], flush=True)

    per_day({"FAULT"}, {"NORMAL_PRE", "NORMAL_POST"}, "B1_fault_vs_normal_by_day")
    per_day({"PRE"}, {"NORMAL_PRE"}, "B1_prefault_by_day")
    # B2 matched windows: window index k covers [t0 + 3.2k, t0 + 3.2(k+1)); keep windows ending <= t0 + s
    counts = defaultdict(int)
    sel = []
    for w, k, f, d in data:
        if k not in ("PRE", "NORMAL_PRE"):
            continue
        counts[f] += 1
        end_s = counts[f] * r21.WIN / r21.HZ
        if end_s <= meta.get(f, 20):
            sel.append((w, 1 if k == "PRE" else 0, f, d))
    X = np.stack([s[0] for s in sel]); y = np.array([s[1] for s in sel]); fl = [s[2] for s in sel]; dy = [s[3] for s in sel]
    res = {"n_windows": int(len(y)), "n_pos": int(y.sum())}
    for gname, groups in (("by_flight", fl), ("by_day", dy)):
        S = [r21.grouped_cv(X, y, groups, seed) for seed in range(5)]
        auc = float(np.mean([fa.auc(y, s) for s in S]))
        lab = {}
        for f_, yy in zip(fl, y):
            lab[f_] = yy
        fls = sorted(lab)
        rng = np.random.default_rng(2151)
        null = []
        for _ in range(100):
            perm = dict(zip(fls, rng.permutation([lab[f_] for f_ in fls])))
            yp = np.array([perm[f_] for f_ in fl])
            null.append(fa.auc(yp, r21.grouped_cv(X, yp, groups, 0)))
        res[gname] = {"auc": auc, "perm_p": float((np.sum(np.array(null) >= auc) + 1) / 101)}
        print("B2", gname, res[gname], flush=True)
    out["B2_matched_prefault"] = res
    out["wording"] = ("separates fault flights before the fault even with matched windows"
                      if res["by_flight"]["auc"] >= 0.70 and res["by_flight"]["perm_p"] < 0.05
                      else "pre-fault separation depends on window span")
    return out


# ---------------------------------------------------------------- C

def matched_features(job):
    path, t0, cut = job
    from pyulog import ULog
    from leak_curve import TOPICS, window_features
    from pilot_vs_drone import topic
    try:
        u = ULog(path, message_name_filter_list=TOPICS + ["estimator_status"])
        st = topic(u, "vehicle_status")
        rotary = bool(st["is_rotary_wing"][-1]) if "is_rotary_wing" in st else True
        f = window_features(u, st, rotary, t0, cut)
        return {k: (None if f[k] is None or np.isnan(f[k]) else float(f[k])) for k in fa.FEATURES}
    except Exception:
        return None


def part_c(rdir):
    from concurrent.futures import ProcessPoolExecutor
    R = [json.loads(l) for l in open(os.path.join(RESULTS_DIR, "rflymad_scores.jsonl"))]
    keep = [r for r in R if "error" not in r and not (r["cls"] != "no_fault" and r["t_f"] is None)
            and not (r["cls"] == "no_fault" and r["t_f"] is not None)]
    off = defaultdict(list)
    for r in keep:
        if r["t_f"] is not None:
            off[r["status"]].append((r["t_f"] - r["t0"]) / 1e6)
    allo = [x for v in off.values() for x in v]
    rows = []
    for r in keep:
        s = min(max(int(round(np.median(off.get(r["status"]) or allo))), 10), 120)
        pre_len = (r["t_f"] - r["t0"]) / 1e6 if r["t_f"] is not None else s
        cut = r["t0"] + int(min(s, pre_len) * 1e6)
        rows.append({**r, "pre_len": pre_len, "whole_len": (r["t_end"] - r["t0"]) / 1e6, "cut": cut})
    y = np.array([0 if r["cls"] == "no_fault" else 1 for r in rows])
    out = {"C1_auc_pre_length": fa.auc(y, np.array([r["pre_len"] for r in rows])),
           "C1_auc_whole_length": fa.auc(y, np.array([r["whole_len"] for r in rows]))}
    jobs = [(os.path.join(rdir, r["path"]), r["t0"], r["cut"]) for r in rows]
    with ProcessPoolExecutor(6) as ex:
        feats = list(ex.map(matched_features, jobs, chunksize=4))
    ok = [i for i, f in enumerate(feats) if f is not None and (rows[i]["cut"] - rows[i]["t0"]) >= 10e6]
    X = np.array([[np.nan if feats[i][f] is None else feats[i][f] for f in fa.FEATURES] for i in ok], float)
    yy = y[ok]
    dates = [re.search(r"log_\d+_(\d{4}-\d+-\d+)", rows[i]["path"]).group(1) for i in ok]
    res = {"n": len(ok), "n_fault": int(yy.sum())}
    for name, scheme, groups in (("stratified", "strat", None), ("by_day", "group", dates)):
        a, _, _ = fa.cv_scores(X, yy, groups, scheme)
        rng = np.random.default_rng(2152)
        null = [fa.cv_scores(X, rng.permutation(yy), groups, scheme, seeds=(42,))[0] for _ in range(200)]
        res[name] = {"auc": a, "perm_p": float((np.sum(np.array(null) >= a) + 1) / 201)}
        print("C2", name, res[name], flush=True)
    out["C2_matched_features"] = res
    out["wording"] = "survives length matching" if res["by_day"]["perm_p"] < 0.05 else "does not survive length matching"
    return out


def main(root, rdir):
    raw = open(os.path.join(root, "dbinfo.json"), "rb").read()
    db = {x["log_id"]: x for x in json.loads(gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw)}
    rep = {"declared_in": "research/px4_log_study/r22_audit.py docstring"}
    for name, fn in (("A", lambda: part_a(root, db)), ("C", lambda: part_c(rdir)), ("B", lambda: part_b(rdir))):
        try:
            rep[name] = fn()
        except Exception as e:
            rep[name] = f"not run: {type(e).__name__}: {e}"
        print("done", name, flush=True)
        json.dump(rep, open(os.path.join(RESULTS_DIR, "r22_audit.json"), "w"), indent=1, default=float)
    open(os.path.join(RESULTS_DIR, "r22_audit.md"), "w").write(
        "# Round 22 audit\n\nDeclared in `research/px4_log_study/r22_audit.py`. Exploratory (dagger).\n\n```\n"
        + json.dumps(rep, indent=1, default=float) + "\n```\n")
    print(json.dumps(rep, indent=1, default=float))


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--only-b":   # amendment 1: rerun Part B into the existing output
        rep = json.load(open(os.path.join(RESULTS_DIR, "r22_audit.json")))
        rep["B"] = part_b(sys.argv[2] if len(sys.argv) > 2 else "/Volumes/One Touch/AeroFleet_px4_data/external/rflymad")
        json.dump(rep, open(os.path.join(RESULTS_DIR, "r22_audit.json"), "w"), indent=1, default=float)
        open(os.path.join(RESULTS_DIR, "r22_audit.md"), "w").write(
            "# Round 22 audit\n\nDeclared in `research/px4_log_study/r22_audit.py`. Exploratory (dagger).\n\n```\n"
            + json.dumps(rep, indent=1, default=float) + "\n```\n")
        print(json.dumps(rep["B"], indent=1, default=float))
    else:
        main(sys.argv[1] if len(sys.argv) > 1 else "/Volumes/One Touch/AeroFleet_px4_data",
             sys.argv[2] if len(sys.argv) > 2 else "/Volumes/One Touch/AeroFleet_px4_data/external/rflymad")
