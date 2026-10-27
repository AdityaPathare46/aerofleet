"""Round 15 audit: refit-variance bounds, clustered between-drone p-values, a direct same- vs other-aircraft
contrast, a fixed-seed regeneration of Table 6, re-fly counts and a crash-moment plausibility check.

PRE-DECLARED (committed and pushed before this script is run). Status: exploratory (dagger), declared after Peer
Review Round 15, not blind: every published value named below is already known.

Problems found while writing this declaration (code read, nothing scored):
  - stage2_stage3_execution.auc_binary has no tie correction. Depth-3 trees give few distinct scores, so the tie
    order decides much of the published tree AUC. Part A uses the tie-corrected AUC (factorial_audit.auc) and also
    reproduces the old computation at m = 10 s to show the effect.
  - round13_audit_execution R13-4 turns each bootstrap draw into a set(), so a drone drawn twice counts once; that is
    not a bootstrap. Part B reproduces it as an anchor and adds a multiplicity-weighted two-stage bootstrap.
  - Python set ordering made earlier fold assignments run-dependent; every CV here sorts clusters first.

COMMON: model = factorial_audit.fit_predict (L2 logistic, lambda 1.0, as leak_curve); tie-corrected AUC; features
from the stored result files unless stated. "group" CV = folds by vehicle (dbinfo vehicle_uuid, else log id).

PART A - Task B (pilot vs aircraft) with refit variance (Round 15 problem 1)
  Data: leak_curve_features.jsonl crash rows labelled pilot/drone, m in {0, 2, 5, 10, 20, 30}; samples "full" (all
  rows at that m) and "const" (the 89 logs present at every m).
  Models: logistic, 5-fold stratified CV x seeds 0-4 (leak_curve's scheme); depth-3 tree (stage2's SimpleDecisionTree,
  median-imputed, same folds, scores averaged over seeds).
  Anchors: logistic full AUC within 0.02 of leak_curve.md (0.49, 0.48, 0.52, 0.42, 0.48, 0.46); old-method tree AUC
  at m = 10 s (auc_binary) 0.379 +- 0.01. If a logistic anchor fails, stop Part A and report.
  Null: 200 label permutations per cell (seed 2031), each refitting the full 5 x 5 CV. Report observed AUC, null
  mean, null SD, null 2.5/97.5 percentiles, one-sided permutation p (AUC >= observed), and the refit-variance
  interval AUC +- 1.96 x null SD. The 80% power AUC = 0.5 + 2.80 x null SD at m = 0 (full, logistic).
  Decision (fixed now): "no usable verdict" stands if every cell's upper refit-variance bound < 0.80.
  Wording rule: "prospectively declared" is used only for the fixed rule; logistic, stumps and trees are exploratory.

PART B - Between-drone vibration with dependence (Round 15 problem 2)
  Data: rough_drone_features.jsonl via sensitivity.load_between / between (vib_p95, as declared).
  B1 anchor: declared test mean rank 0.667 +- 0.005, n 60.
  B2 R13 method anchor (set-based draws, sorted lists, seed 777): mean 0.662 +- 0.01, CI within 0.02 of
     [0.536, 0.789].
  B3 two-stage cluster bootstrap, multiplicity-weighted: resample case airframes (each brings all its sets) and
     control airframes with replacement; a control drawn k times counts k times in every set it belongs to; a set
     whose controls are all undrawn is skipped. 2,000 resamples, seed 2032. Report mean, 95% CI and the null-shifted
     p = share of resamples with (mean* - rbar + 0.5) >= rbar.
  B4 one set per case airframe: 1,000 random selections (seed 2033) of one set per case airframe (40 sets); for each,
     mean rank and the exact-null p (10,000 draws) and share of sets where the crashed drone is roughest. Report the
     median mean rank, median p, share of selections with p < 0.025, and median top-rank share vs its null.
  B5 Holm over the seven Table 5 p-values with B3's p replacing 0.0023 (others 0.63, 0.045, 0.165, 0.67, 0.47,
     0.15). Decision (fixed now): the between-drone result is reported as supported if B3 p < 0.025 and its
     Holm-adjusted p < 0.05; otherwise the abstract calls it suggestive.

PART C - Same-aircraft vs other-aircraft, paired (Round 15 problem 3)
  Factorial pipeline (factorial_audit_features.jsonl, one extractor), the 67 within-drone crashes (C2), m = 10 s,
  full window, vehicle-grouped CV: AUC(C2 vs N2 matched other-aircraft) and AUC(C2 vs S own earlier flights); and S
  without the flights postcrash_audit's GPS ordering marks as following the crash (recomputed here with the same
  function). Paired two-stage bootstrap over crash and control vehicles (factorial_audit.paired_bootstrap, seed
  2034): difference other - same and its 95% CI, for S and S-without-following. Also states which cells gave the
  factorial audit's "further 0.21" (constant subset, first30 window).

PART D - Table 6 regenerated with fixed seeds (Round 15 problem 5)
  Stored features; seeds 42-46; clusters sorted; CI = cluster bootstrap over vehicles on seed-averaged out-of-fold
  scores (2,000 resamples, seed 2035; equals a flight bootstrap where vehicles are unique). Steps:
    0  148 crash vs 139 normal, m = 0, stratified            1  same, grouped by vehicle
    2  constant cohort (logs with a window at m = 30), m = 10, grouped
    3  same cohort, m = 30, grouped                          4  m = 0 without tilt_p95 and stick_p95, grouped
    5  67 crashes vs 305 earlier (within_drone), stratified  6  same, grouped by crash drone
    6b step 6 without earlier flights that GPS time places after the crash
  Control: 20 label permutations of step 1: mean 0.50 +- 0.05, else abort Part D.
  Rule (fixed now): every Table 6 value is replaced by its regenerated value; a change > 0.02 is stated in the text.

PART E - What "crash" means: re-fly counts (Round 15 problem 9), descriptive
  Archive-wide (dbinfo, real hardware, rating crash_sw_hw or crash_pilot, vehicle_uuid present): share of crashes
  whose vehicle has a log dated after the crash day; share with a later log within 1, 7 and 30 days; median days to
  the next later-dated log. Same for the 148 Task A crashes, the 67 within-drone crashes and the 40 case airframes.
  Same-day re-flights are taken from the two GPS audits (not recomputed here). Dates only; stated as a limit.

PART F - Crash moment plausibility (Round 15 problem 9), descriptive
  For the 148 Task A crash logs: t_c = pilot_vs_drone.crash_time. Plausible if within 10 s after t_c the armed
  period ends, or the land detector reports landed or ground contact. Report counts: tilt-defined vs fallback t_c,
  plausible, implausible, unreadable. A review sheet of 50 logs (seed 2036: tilt and altitude around t_c, t_c
  marked) is written for a human check by the authors; this script does not claim that check was done.

Outputs: research/results/px4_log_study/r15_audit[_PARTS].md and .json (one pair per run; parts may run as separate
processes), r15_crash_moment_sheet.png.

    python research/px4_log_study/r15_audit.py DATA_ROOT [PARTS]
"""
import gzip
import json
import os
import sys
from collections import defaultdict
from datetime import date

import numpy as np

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(SCRIPT_DIR)
import factorial_audit as fa
import postcrash_audit as pca
import sensitivity
from stage2_stage3_execution import SimpleDecisionTree, auc_binary

RESULTS_DIR = os.path.join(SCRIPT_DIR, "..", "results", "px4_log_study")
MARGINS = (0, 2, 5, 10, 20, 30)
LEAK_B = {0: 0.49, 2: 0.48, 5: 0.52, 10: 0.42, 20: 0.48, 30: 0.46}
N_PERM = 200
CRASH = ("crash_sw_hw", "crash_pilot")


def jsonl(name):
    return [json.loads(line) for line in open(os.path.join(RESULTS_DIR, name))]


def load_db(root):
    raw = open(os.path.join(root, "dbinfo.json"), "rb").read()
    return {x["log_id"]: x for x in json.loads(gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw)}


def strat_folds(y, seed, k=5):
    rng = np.random.default_rng(seed)
    folds = np.zeros(len(y), int)
    for cls in (0, 1):
        idx = np.where(y == cls)[0]
        rng.shuffle(idx)
        folds[idx] = np.arange(len(idx)) % k
    return folds


def cv_auc(X, y, model, seeds=range(5)):
    """leak_curve scheme: stratified 5-fold, repeated over seeds. Returns (mean AUC over seeds, seed-averaged scores)."""
    aucs, avg = [], np.zeros(len(y))
    Xi = X.copy()
    if model == "tree":
        med = np.nanmedian(Xi, axis=0)
        for j in range(Xi.shape[1]):
            Xi[np.isnan(Xi[:, j]), j] = med[j] if not np.isnan(med[j]) else 0.0
    for s in seeds:
        folds, sc = strat_folds(y, s), np.zeros(len(y))
        for f in range(5):
            te, tr = folds == f, folds != f
            if model == "logistic":
                sc[te] = fa.fit_predict(X[tr], y[tr], X[te])
            else:
                sc[te] = SimpleDecisionTree(max_depth=3).fit(Xi[tr], y[tr]).predict_proba(Xi[te])
        aucs.append(fa.auc(y, sc))
        avg += sc / len(seeds)
    return float(np.mean(aucs)), avg


# ---------------------------------------------------------------- A

def part_a():
    rows = [r for r in jsonl("leak_curve_features.jsonl") if r["group"] == "crash" and r["label"] in ("pilot", "drone")]
    present = defaultdict(set)
    for r in rows:
        present[r["log"]].add(r["margin"])
    const = {l for l, ms in present.items() if set(MARGINS) <= ms}
    out = {"const_n": len(const), "anchors": {}, "cells": {}}
    # Anchors first.
    for m in MARGINS:
        R = [r for r in rows if r["margin"] == m]
        X = np.array([[r[f] for f in fa.FEATURES] for r in R], float)
        y = np.array([1 if r["label"] == "drone" else 0 for r in R])
        a, _ = cv_auc(X, y, "logistic")
        out["anchors"][f"logistic_m{m}"] = a
        if abs(a - LEAK_B[m]) > 0.02:
            out["abort"] = f"logistic anchor m={m}: {a:.3f} vs {LEAK_B[m]}"
            return out
    R = [r for r in rows if r["margin"] == 10]
    X = np.array([[r[f] for f in fa.FEATURES] for r in R], float)
    y = np.array([1 if r["label"] == "drone" else 0 for r in R])
    _, sc = cv_auc(X, y, "tree")
    out["anchors"]["tree_m10_old_auc_binary"] = auc_binary(y, sc)
    out["anchors"]["tree_m10_tie_corrected"] = fa.auc(y, sc)
    rng = np.random.default_rng(2031)
    for model in ("logistic", "tree"):
        for sample in ("full", "const"):
            for m in MARGINS:
                R = [r for r in rows if r["margin"] == m and (sample == "full" or r["log"] in const)]
                X = np.array([[r[f] for f in fa.FEATURES] for r in R], float)
                y = np.array([1 if r["label"] == "drone" else 0 for r in R])
                obs, _ = cv_auc(X, y, model)
                null = np.array([cv_auc(X, rng.permutation(y), model)[0] for _ in range(N_PERM)])
                sd = float(null.std())
                out["cells"][f"{model}|{sample}|{m}"] = {
                    "n": len(y), "n_pilot": int((y == 0).sum()), "auc": obs, "null_mean": float(null.mean()), "null_sd": sd,
                    "null_95": [float(np.percentile(null, 2.5)), float(np.percentile(null, 97.5))],
                    "p": float((np.sum(null >= obs) + 1) / (N_PERM + 1)), "interval": [obs - 1.96 * sd, obs + 1.96 * sd]}
                print(f"A {model} {sample} m={m}: {obs:.3f} null sd {sd:.3f}", flush=True)
    out["power80_auc"] = 0.5 + 2.80 * out["cells"]["logistic|full|0"]["null_sd"]
    out["no_usable_verdict"] = all(c["interval"][1] < 0.80 for c in out["cells"].values())
    return out


# ---------------------------------------------------------------- B

def set_table():
    """Per analysed set: case airframe, case value, [(control airframe, value)] exactly as sensitivity.between."""
    sets, role = sensitivity.load_between()
    table = []
    for sid in sorted(sets):
        vehicles = sets[sid]
        case = [v for v in vehicles if role[(sid, v)] == "case"]
        if not case:
            continue

        def value(rs):
            vals = defaultdict(list)
            for r in rs:
                f = r["features"]
                if f and f.get("vib_p95") is not None:
                    vals[f.get("src_vib")].append(f["vib_p95"])
            return {s: float(np.median(v)) for s, v in vals.items() if len(v) >= 2}

        for s, cv in value(vehicles[case[0]]).items():
            ctrl = [(v, value(vehicles[v]).get(s)) for v in sorted(vehicles) if role[(sid, v)] == "control"]
            ctrl = [(v, x) for v, x in ctrl if x is not None]
            if ctrl:
                table.append({"set": sid, "case": case[0], "val": cv, "ctrl": ctrl})
            break
    return table


def part_b():
    sets, role = sensitivity.load_between()
    obs, p_exact, n, top, exp_top = sensitivity.between(sets, role)
    out = {"declared": {"mean_rank": obs, "p": p_exact, "n": n, "top": top, "expected_top": exp_top}}
    T = set_table()
    rank = lambda t, w=None: (sum((w.get(c, 0) if w else 1) for c, x in t["ctrl"] if x < t["val"]) /
                              sum((w.get(c, 0) if w else 1) for c, _ in t["ctrl"]))
    rbar = float(np.mean([rank(t) for t in T]))
    cases = sorted({t["case"] for t in T})
    ctrls = sorted({c for t in T for c, _ in t["ctrl"]})
    out["n_sets"], out["n_case_airframes"], out["n_control_airframes"] = len(T), len(cases), len(ctrls)
    # B2: Round 13 method (set-based draws) as anchor.
    rng = np.random.default_rng(777)
    b2 = []
    for _ in range(2000):
        sc, sk = set(rng.choice(cases, len(cases))), set(rng.choice(ctrls, len(ctrls)))
        rk = [sum(x < t["val"] for c, x in t["ctrl"] if c in sk) / len([1 for c, _ in t["ctrl"] if c in sk])
              for t in T if t["case"] in sc and any(c in sk for c, _ in t["ctrl"])]
        if rk:
            b2.append(np.mean(rk))
    out["r13_method"] = {"mean": float(np.mean(b2)), "ci": [float(np.percentile(b2, 2.5)), float(np.percentile(b2, 97.5))]}
    out["anchors_pass"] = bool(abs(obs - 0.667) <= 0.005 and n == 60 and abs(out["r13_method"]["mean"] - 0.662) <= 0.01
                               and abs(out["r13_method"]["ci"][0] - 0.536) <= 0.02 and abs(out["r13_method"]["ci"][1] - 0.789) <= 0.02)
    if not out["anchors_pass"]:
        return out
    # B3: multiplicity-weighted two-stage bootstrap.
    by_case = defaultdict(list)
    for t in T:
        by_case[t["case"]].append(t)
    rng = np.random.default_rng(2032)
    b3 = []
    for _ in range(2000):
        w = defaultdict(int)
        for c in rng.choice(ctrls, len(ctrls)):
            w[c] += 1
        rk = []
        for c in rng.choice(cases, len(cases)):
            for t in by_case[c]:
                if sum(w.get(k, 0) for k, _ in t["ctrl"]):
                    rk.append(rank(t, w))
        b3.append(np.mean(rk))
    b3 = np.array(b3)
    p3 = float(np.mean(b3 - rbar + 0.5 >= rbar))
    out["two_stage"] = {"mean": float(b3.mean()), "ci": [float(np.percentile(b3, 2.5)), float(np.percentile(b3, 97.5))], "p": p3}
    # B4: one set per case airframe.
    rng = np.random.default_rng(2033)
    mr, ps, tops, exps = [], [], [], []
    for _ in range(1000):
        pick = [by_case[c][rng.integers(len(by_case[c]))] for c in cases]
        r = [rank(t) for t in pick]
        sizes = [len(t["ctrl"]) for t in pick]
        o, p, _ = sensitivity.null_p(r, sizes, draws=10_000, seed=int(rng.integers(1 << 31)))
        mr.append(o); ps.append(p)
        tops.append(np.mean([x == 1.0 for x in r])); exps.append(np.mean([1 / (k + 1) for k in sizes]))
    out["one_per_airframe"] = {"sets": len(cases), "median_mean_rank": float(np.median(mr)), "median_p": float(np.median(ps)),
                               "share_p_below_0025": float(np.mean(np.array(ps) < 0.025)),
                               "median_top_share": float(np.median(tops)), "median_expected_top": float(np.median(exps))}
    # B5: Holm.
    pv = {"between_vib": p3, "protections": 0.63, "clipping": 0.045, "manual": 0.165, "within_vib": 0.67,
          "within_track": 0.47, "between_track": 0.15}
    order = sorted(pv, key=pv.get)
    holm, run = {}, 0.0
    for i, k in enumerate(order):
        run = max(run, min(1.0, (len(order) - i) * pv[k]))
        holm[k] = run
    out["holm"] = holm
    out["supported"] = bool(p3 < 0.025 and holm["between_vib"] < 0.05)
    return out


# ---------------------------------------------------------------- C

def part_c(root):
    db = fa.load_index(root)
    sets, vehicle, _ = fa.build_sets(db)
    cache = {}
    for line in open(os.path.join(RESULTS_DIR, "factorial_audit_features.jsonl")):
        r = json.loads(line)
        cache[(r["log_id"], r["is_crash"])] = r["windows"]
    status = pca.ordering(root, pca.within_rows())
    follows = {k for k, v in status.items() if v == "follows"}
    cells = {"other": fa.run_cell(fa.cell_rows(sets, cache, "C2", "N2", 10, "full", None), vehicle, "group"),
             "same": fa.run_cell(fa.cell_rows(sets, cache, "C2", "S", 10, "full", None), vehicle, "group"),
             "same_F": fa.run_cell(fa.cell_rows(sets, cache, "C2", "S", 10, "full",
                                                {True: set(sets["C2"]), False: set(sets["S"]) - follows}), vehicle, "group")}
    crash_veh = {vehicle[x] for x in sets["C2"]}
    normal_veh = {vehicle[x] for x in sets["N2"]}
    fa_boot_seed = fa.BOOT_SEED
    fa.BOOT_SEED = 2034
    boot = fa.paired_bootstrap(cells, crash_veh, normal_veh)
    fa.BOOT_SEED = fa_boot_seed
    out = {k: {"auc": v["auc"], "n_crash": v["n_crash"], "n_comp": v["n_comp"], "ci": fa.ci(boot[k])} for k, v in cells.items()}
    for s in ("same", "same_F"):
        d = cells["other"]["auc"] - cells[s]["auc"]
        out[f"diff_other_minus_{s}"] = {"diff": d, "ci": fa.ci(boot["other"] - boot[s])}
    out["factorial_further_021_cells"] = "constant subset; other = C2 vs N2 at m10, grouped, first30 (0.666); same = C2 vs S at m10, first30, grouped (0.455)"
    return out


# ---------------------------------------------------------------- D

def _cluster_ci(y, s, clusters, seed):
    rng = np.random.default_rng(seed)
    idx = defaultdict(list)
    for i, c in enumerate(clusters):
        idx[c].append(i)
    cids = np.array(sorted(idx))
    vals = []
    for _ in range(2000):
        pick = [i for c in rng.choice(cids, len(cids)) for i in idx[c]]
        v = fa.auc(y[pick], s[pick])
        if not np.isnan(v):
            vals.append(v)
    return [float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))]


def part_d(root):
    db = load_db(root)
    veh = lambda lid: db.get(lid, {}).get("vehicle_uuid") or lid
    leak = jsonl("leak_curve_features.jsonl")
    present = defaultdict(set)
    for r in leak:
        present[r["log"]].add(r["margin"])
    cohort = {l for l, ms in present.items() if 30 in ms}

    def leak_cell(m, scheme, feats=fa.FEATURES, only=None):
        R = [r for r in leak if r["margin"] == m and (only is None or r["log"] in only)]
        X = np.array([[r[f] for f in feats] for r in R], float)
        y = np.array([1 if r["group"] == "crash" else 0 for r in R])
        cl = [veh(r["log"]) for r in R]
        return X, y, cl, scheme

    w = pca.within_rows()
    status = pca.ordering(root, w)
    follows = {k for k, v in status.items() if v == "follows"}

    def within_cell(scheme, drop=frozenset()):
        by = defaultdict(list)
        for r in w:
            if r["features"] is not None and r["log_id"] not in drop:
                by[r["crash_id"]].append(r)
        use = [r for c in sorted(by) for r in by[c] if any(x["role"] == "crash" for x in by[c]) and any(x["role"] == "earlier" for x in by[c])]
        X = np.array([[np.nan if r["features"].get(k) is None else r["features"][k] for k in fa.FEATURES] for r in use], float)
        y = np.array([1 if r["role"] == "crash" else 0 for r in use])
        return X, y, [r["crash_id"] for r in use], scheme

    X, y, cl, _ = leak_cell(0, "group")
    perm = [fa.cv_scores(X, np.random.default_rng(s).permutation(y), cl, "group", seeds=(42,))[0] for s in range(20)]
    out = {"permutation_control": float(np.mean(perm))}
    if abs(np.mean(perm) - 0.5) > 0.05:
        out["abort"] = "permutation control"
        return out
    no_tilt = [f for f in fa.FEATURES if f not in ("tilt_p95", "stick_p95")]
    steps = {"0": leak_cell(0, "strat"), "1": leak_cell(0, "group"), "2": leak_cell(10, "group", only=cohort),
             "3": leak_cell(30, "group", only=cohort), "4": leak_cell(0, "group", feats=no_tilt),
             "5": within_cell("strat"), "6": within_cell("group"), "6b": within_cell("group", follows)}
    for k, (X, y, cl, scheme) in steps.items():
        a, sd, s = fa.cv_scores(X, y, cl, scheme)
        out[k] = {"n_crash": int(y.sum()), "n_comp": int((y == 0).sum()), "auc": a, "sd_over_repeats": sd,
                  "ci": _cluster_ci(y, s, cl, 2035)}
        print(f"D step {k}: {a:.3f}", flush=True)
    return out


# ---------------------------------------------------------------- E

def part_e(root):
    db = load_db(root)
    by_v = defaultdict(list)
    for x in db.values():
        if x.get("vehicle_uuid") and "SITL" not in str(x.get("sys_hw")):
            by_v[x["vehicle_uuid"]].append(x)
    d = lambda s: date.fromisoformat(str(s)[:10])

    def stats(ids):
        gaps, n = [], 0
        for lid in ids:
            c = db.get(lid)
            if not c or not c.get("vehicle_uuid") or not c.get("log_date"):
                continue
            n += 1
            later = [d(y["log_date"]) for y in by_v[c["vehicle_uuid"]] if y.get("log_date") and str(y["log_date"])[:10] > str(c["log_date"])[:10]]
            if later:
                gaps.append((min(later) - d(c["log_date"])).days)
        g = np.array(gaps)
        return {"crashes": n, "later_log": len(gaps), "share_later": len(gaps) / n if n else None,
                "within_1d": int((g <= 1).sum()), "within_7d": int((g <= 7).sum()), "within_30d": int((g <= 30).sum()),
                "median_days": float(np.median(g)) if len(g) else None}

    archive = [x["log_id"] for x in db.values() if x.get("rating") in CRASH and "SITL" not in str(x.get("sys_hw")) and x.get("vehicle_uuid")]
    leak = jsonl("leak_curve_features.jsonl")
    task_a = sorted({r["log"] for r in leak if r["margin"] == 0 and r["group"] == "crash"})
    c2 = sorted({r["crash_id"] for r in pca.within_rows()})
    _, role = sensitivity.load_between()
    T = set_table()
    first_set = {}
    for t in T:
        first_set.setdefault(t["case"], t["set"])
    return {"archive": stats(archive), "task_a_148": stats(task_a), "within_67": stats(c2),
            "case_airframes_40": stats(list(first_set.values())),
            "same_day_after_crash_from_gps_audits": {"between_drone": "47 of 95", "within_drone": "85 of 210"}}


# ---------------------------------------------------------------- F

def part_f(root):
    from pyulog import ULog
    from pilot_vs_drone import armed_period, between, crash_time, topic
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    paths = pca.ulg_paths(root)
    leak = jsonl("leak_curve_features.jsonl")
    ids = sorted({r["log"] for r in leak if r["margin"] == 0 and r["group"] == "crash"})
    counts = defaultdict(int)
    traces = {}
    for lid in ids:
        try:
            u = ULog(paths[lid], message_name_filter_list=["vehicle_status", "vehicle_land_detected", "vehicle_attitude",
                                                           "vehicle_local_position"])
            st = topic(u, "vehicle_status")
            t_arm, t_end = armed_period(st)
            rotary = bool(st["is_rotary_wing"][-1]) if "is_rotary_wing" in st else True
            tc = crash_time(u, t_arm, t_end, rotary)
        except Exception:
            counts["unreadable"] += 1
            continue
        counts["tilt_defined" if tc < t_end else "fallback_end_of_arming"] += 1
        land = topic(u, "vehicle_land_detected")
        ok = t_end - tc <= 10e6
        if land is not None and not ok:
            mm = between(land, tc, tc + 10e6)
            for k in ("landed", "ground_contact"):
                if k in land and mm.any() and land[k][mm].any():
                    ok = True
        counts["plausible" if ok else "implausible"] += 1
        att, lp = topic(u, "vehicle_attitude"), topic(u, "vehicle_local_position")
        if att is not None:
            m = between(att, tc - 30e6, tc + 15e6)
            q1, q2 = att["q[1]"][m], att["q[2]"][m]
            tilt = np.degrees(np.arccos(np.clip(1 - 2 * (q1 ** 2 + q2 ** 2), -1, 1)))
            alt = None
            if lp is not None and "z" in lp:
                ml = between(lp, tc - 30e6, tc + 15e6)
                alt = ((lp["timestamp"][ml] - tc) / 1e6, -lp["z"][ml])
            traces[lid] = ((att["timestamp"][m] - tc) / 1e6, tilt, alt, ok)
    pick = list(np.random.default_rng(2036).choice(sorted(traces), size=min(50, len(traces)), replace=False))
    fig, axes = plt.subplots(10, 5, figsize=(20, 26))
    for ax, lid in zip(axes.flat, pick):
        t, tilt, alt, ok = traces[lid]
        ax.plot(t, tilt, lw=0.8)
        ax.axvline(0, color="k", lw=0.8)
        ax.axhline(60, color="grey", lw=0.5, ls="--")
        if alt is not None:
            ax2 = ax.twinx()
            ax2.plot(alt[0], alt[1], lw=0.6, color="tab:orange")
        ax.set_title(f"{lid[:8]} {'auto-plausible' if ok else 'auto-implausible'}", fontsize=7)
        ax.tick_params(labelsize=6)
    fig.suptitle("Crash moment t_c (black line) with tilt (blue, deg) and altitude (orange, m); for human review")
    fig.tight_layout()
    fig.savefig(os.path.join(RESULTS_DIR, "r15_crash_moment_sheet.png"), dpi=80)
    return {"logs": len(ids), "counts": dict(counts), "review_sheet_logs": [str(x) for x in pick],
            "human_check": "pending (authors)"}


def main(root, parts="ABCDEF"):
    rep = {"declared_in": "research/px4_log_study/r15_audit.py docstring"}
    tag = "" if parts == "ABCDEF" else "_" + parts  # separate files when parts run in separate processes
    for p, fn in (("A", part_a), ("B", part_b), ("C", lambda: part_c(root)), ("D", lambda: part_d(root)),
                  ("E", lambda: part_e(root)), ("F", lambda: part_f(root))):
        if p in parts:
            print(f"=== Part {p}", flush=True)
            rep[p] = fn()
            with open(os.path.join(RESULTS_DIR, f"r15_audit{tag}.json"), "w") as f:
                json.dump(rep, f, indent=1, default=float)
    with open(os.path.join(RESULTS_DIR, f"r15_audit{tag}.md"), "w") as f:
        f.write("# Round 15 audit\n\nDeclared in `research/px4_log_study/r15_audit.py` (docstring). Exploratory (dagger).\n\n"
                "Full numbers are in `r15_audit.json`.\n\n```\n" + json.dumps(rep, indent=1, default=float)[:60000] + "\n```\n")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "/Volumes/One Touch/AeroFleet_px4_data",
         sys.argv[2] if len(sys.argv) > 2 else "ABCDEF")
