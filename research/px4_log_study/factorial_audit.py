"""Factorial optimism audit: what does the crash-vs-normal AUC actually depend on?

PRE-DECLARED (committed and pushed before this script is run on any log). Status: exploratory (dagger), declared
after Peer Review Round 14, not blind. Answers Round 14 problem 1 (the 2 x 2), problem 2 (duration fixed at source)
and the originality item (a factorial audit).

Prior knowledge, stated up front. Already seen: 0.883 (148 crashes vs 139 normals, m = 0, stratified CV), 0.891
(103 multi-history crashes vs the same 139, m = 0), 0.835 (45 single-history), 0.522 (67 within-drone crashes vs 134
matched other-aircraft flights, grouped CV, m = 10 s), 0.569 (the 67 vs their own 305 earlier flights). Counted
(not scored) while writing this declaration:
  - the 67 within-drone crashes are NOT a subset of the 103; only 10 of the 67 are in the 148 at all;
  - the 139 normals are all flights the uploader rated good/great; the rough-drone controls are all unrated;
  - Step 4b's 0.522 mixed feature extractors (crashes: within_drone.features with older-firmware fallbacks;
    controls: partly leak_curve features at m = 0). This audit recomputes every flight with one extractor;
  - airborne length (dbinfo duration_s) >= 40 s: 77 of 103 (C1), 64 of 67 (C2). This set L = 30 s below;
  - set sizes from build_sets (no scoring): C1 103, C1e 12, C2 67, N1 100 (39 of the 139 removed because their
    vehicle is in C1 or C2), N2 372, S 311; every needed log is on disk. Because C1e has only 12 crashes,
    E_rule and E_pool below are descriptive only (never "supported").

SETS (no new downloads; logs already on disk under the data root; a log not on disk is dropped and counted)
  Crash sets (uploader rating crash_sw_hw or crash_pilot, real hardware):
    C1   the 103 multi-history crashes of R13-1 (in the 148 of leak_curve m = 0; vehicle has >= 2 logs in the index)
    C1e  C1 restricted to crashes meeting the within-drone eligibility rule, computed from the index alone
         (within_drone.select: >= 3 same-vehicle flights not crash-rated, >= 30 s, dated on or before the crash)
    C2   the 67 within-drone crashes (within_drone_features.jsonl, >= 1 usable earlier flight)
  Comparison sets:
    N1   the 139 leak_curve normal flights (uploader-rated good/great; not matched)
    N2   rough_drone control flights (unrated drones with no crash-rated log, matched to the within-drone cases on
         flight-controller hardware, PX4 major.minor and vehicle type; so N2 is matched to C2, not to C1)
    S    the earlier flights of the C2 drones (same aircraft)
  Any N1/N2 flight whose vehicle appears in C1 or C2 is removed (count reported).

FEATURES: the 11 leak_curve features, recomputed for every flight by one extractor (within_drone.features logic,
including the older-firmware fallbacks for vib_p95 and tune_rms) for four windows per flight:
    m in {0, 10} s: window ends at t_c - m (crash: first tilt > 60 deg; other flights: end of the armed period)
    W in {full, first30}: full = first airborne moment to the cut; first30 = the first 30 s airborne, and only if
         that ends at or before the cut. first30 removes window length and crash proximity together, so under
         first30 the m factor has no effect by construction (stated, not a finding).
  Windows under 10 s are dropped.

MODEL (unchanged from leak_curve): L2 logistic regression, lambda 1.0, training-fold median imputation and
z-scoring, 5 folds repeated with seeds 42-46. CV in {strat, group}: strat = stratified by flight; group = folds by
vehicle (a crash and its own earlier flights always share a fold). Reported AUC = mean over the 5 repeats; the +-
figure is the SD over repeats and is labelled as an SD, not an interval.

INFERENCE: one paired two-stage cluster bootstrap, 2,000 resamples, seed 2027. Each resample draws crash vehicles
(C1 u C2, a drone carries its crash flight and its S flights) and normal vehicles (N1 u N2) with replacement; every
cell's AUC is recomputed on the drawn clusters from its fixed out-of-fold scores (seed-averaged), so differences
between cells are paired. Models are not refitted inside the bootstrap (stated limitation). 95% percentile CIs.

ABORT RULES (run first; if any fails, stop, report, compute nothing else):
  A1 stored-feature anchor: C1 vs N1, m = 0, strat, seeds 0-4, leak_curve_features.jsonl: 0.891 +- 0.03.
  A2 stored-feature anchor: C2 vs S, m = 10, group, within_drone_features.jsonl: 0.569 +- 0.03.
  A3 extractor check: on flights in both the stored leak_curve rows and the recomputation (m in {0, 10}, full),
     every feature except vib_p95 and tune_rms (fallbacks allowed) must agree (abs diff <= 1e-6 or both missing)
     on >= 95% of flights.
  A4 permutation control: 20 label permutations of cell (C2, N2, m10, group, full): mean AUC 0.50 +- 0.05.

STAGE 1, PRIMARY: the 2 x 2 Round 14 asked for. One scheme: m = 10, group CV, full window, same extractor.
  Cells (C1, N1), (C1, N2), (C2, N1), (C2, N2); C1e reported in the same table as a third crash row.
  Effects (AUC differences, averaged over the other factor):
    E_N  = normal-set effect   = mean_C [AUC(C, N1) - AUC(C, N2)]
    E_C  = crash-set effect    = mean_N [AUC(C1, N) - AUC(C2, N)]
    E_CN = interaction         = [AUC(C1,N1) - AUC(C1,N2)] - [AUC(C2,N1) - AUC(C2,N2)]
    E_rule = eligibility rule  = mean_N [AUC(C1, N) - AUC(C1e, N)]
    E_pool = crash source pool = mean_N [AUC(C1e, N) - AUC(C2, N)]   (same rule, different archive pool)
  An effect is SUPPORTED if |effect| >= 0.05 and its 95% CI excludes 0. Wording for the abstract, fixed now:
    only E_N supported   -> "The drop depends on the choice of normal flights, not on which crashes are scored."
    only E_C supported   -> "The drop depends on which crashes are scored (eligibility/pool), not on the normals."
    both                 -> "Both the normal flights and the crash set contribute" (with the two numbers).
    neither              -> "The AUC depends on the comparison set; the cause is not isolated."
  E_rule / E_pool are reported with CIs as a description of which part of E_C might carry it; with 12 C1e
  crashes they are underpowered and cannot be called supported.

STAGE 2: full factorial (descriptive, with CIs).
  Other-aircraft arm: 5 binary factors, ordered from optimistic to conservative level:
    C (C1 -> C2), N (N1 -> N2), m (0 -> 10), CV (strat -> group), W (full -> first30): 32 cells.
  Same-aircraft arm: C2 vs S under m x CV x W: 8 cells; reported as a further step N2 -> S at matched settings.
  Constant subset: in Stage 2 a flight is used only if all four of its (m, W) windows exist, so attrition does
  not move between cells. Fallback, fixed now: if this leaves < 30 crashes in C1 or C2, drop W from the factorial
  (16 cells, constant over m only) and report W separately on its own constant subset.
  Optimism budget: total = AUC(all optimistic) - AUC(all conservative) over the 32 cells, split exactly into
  Shapley values over the 5 factors (average marginal drop over all 120 orderings). A factor is a MATERIAL
  contributor if its Shapley value >= 0.05 and its 95% CI excludes 0. Also reported: main effects and all
  two-way interactions (mean over the other factors), and each cell's n and AUC.
  Any cell with < 30 crash or < 30 comparison flights is flagged underpowered (still reported).

Reported whatever the outcome, in research/results/px4_log_study/factorial_audit.md and .json.

    python research/px4_log_study/factorial_audit.py DATA_ROOT
"""
import gzip
import json
import math
import os
import sys
from collections import defaultdict
from itertools import permutations, product

import numpy as np

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(SCRIPT_DIR)
RESULTS_DIR = os.path.join(SCRIPT_DIR, "..", "results", "px4_log_study")
FEATURES = ["tune_rms", "tilt_p95", "vib_p95", "clip_rate", "sat_frac", "batt_min", "volt_sag", "gps_bad", "failsafe",
            "manual_frac", "stick_p95"]
CRASH = ("crash_sw_hw", "crash_pilot")
MARGINS, WINDOWS, CVS = (0, 10), ("full", "first30"), ("strat", "group")
FIRST_S, MIN_WINDOW_S, MIN_CELL = 30, 10, 30
SEEDS, BOOT, BOOT_SEED = (42, 43, 44, 45, 46), 2000, 2027
# Optimistic -> conservative level of each Stage 2 factor.
FACTORS = {"C": ("C1", "C2"), "N": ("N1", "N2"), "m": (0, 10), "CV": ("strat", "group"), "W": ("full", "first30")}


def auc(y, s):
    y, s = np.asarray(y), np.asarray(s, float)
    ok = ~np.isnan(s)
    y, s = y[ok], s[ok]
    pos, neg = s[y == 1], s[y == 0]
    if len(pos) == 0 or len(neg) == 0:
        return np.nan
    allv = np.concatenate([pos, neg])
    ranks = np.argsort(np.argsort(allv)) + 1.0
    for v in np.unique(allv):
        idx = allv == v
        ranks[idx] = ranks[idx].mean()
    return float((ranks[: len(pos)].sum() - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg)))


def fit_predict(Xtr, ytr, Xte, lam=1.0, iters=3000, lr=0.1):
    med = np.nanmedian(Xtr, axis=0)
    med = np.where(np.isnan(med), 0.0, med)
    Xtr = np.nan_to_num(np.where(np.isnan(Xtr), med, Xtr), nan=0.0, posinf=0.0, neginf=0.0)
    Xte = np.nan_to_num(np.where(np.isnan(Xte), med, Xte), nan=0.0, posinf=0.0, neginf=0.0)
    mu, sd = Xtr.mean(0), Xtr.std(0)
    sd[sd <= 1e-6] = 1.0
    Xtr, Xte = np.clip((Xtr - mu) / sd, -10, 10), np.clip((Xte - mu) / sd, -10, 10)
    w, b = np.zeros(Xtr.shape[1]), 0.0
    for _ in range(iters):
        p = 1 / (1 + np.exp(-np.clip(Xtr @ w + b, -25, 25)))
        g = p - ytr
        w -= lr * (Xtr.T @ g / len(ytr) + lam * w / len(ytr))
        b -= lr * g.mean()
    return Xte @ w + b


def cv_scores(X, y, groups, scheme, seeds=SEEDS, k=5):
    """Out-of-fold scores per seed. Returns (mean AUC over repeats, SD over repeats, seed-averaged scores)."""
    aucs, all_scores = [], []
    for s in seeds:
        rng = np.random.default_rng(s)
        folds = np.zeros(len(y), int)
        if scheme == "strat":
            for cls in (0, 1):
                idx = np.where(y == cls)[0]
                rng.shuffle(idx)
                folds[idx] = np.arange(len(idx)) % k
        else:
            uniq = sorted(set(groups))
            rng.shuffle(uniq)
            to_fold = {g: i % k for i, g in enumerate(uniq)}
            folds = np.array([to_fold[g] for g in groups])
        scores = np.zeros(len(y))
        for f in range(k):
            te, tr = folds == f, folds != f
            scores[te] = fit_predict(X[tr], y[tr], X[te])
        aucs.append(auc(y, scores))
        all_scores.append(scores)
    return float(np.mean(aucs)), float(np.std(aucs)), np.mean(all_scores, axis=0)


# ---------------------------------------------------------------- features (one extractor, four windows)

def window_set(path, is_crash):
    """The 11 features for (m, W) in MARGINS x WINDOWS, from one parse. Missing window -> None."""
    from pyulog import ULog

    from leak_curve import TOPICS, window_features
    from pilot_vs_drone import armed_period, between, crash_time, topic

    u = ULog(path, message_name_filter_list=TOPICS + ["estimator_status"])
    st = topic(u, "vehicle_status")
    per = armed_period(st) if st is not None else None
    if per is None:
        return None
    t_arm, t_end = per
    rotary = bool(st["is_rotary_wing"][-1]) if "is_rotary_wing" in st else True
    t_c = crash_time(u, t_arm, t_end, rotary) if is_crash else t_end
    land = topic(u, "vehicle_land_detected")
    t0 = t_arm
    if land is not None:
        mm = between(land, t_arm, t_c) & (land["landed"] == 0)
        if mm.any():
            t0 = land["timestamp"][mm][0]
    es, sp, att = topic(u, "estimator_status"), topic(u, "vehicle_rates_setpoint"), topic(u, "vehicle_attitude")
    out = {"airborne_s": (t_c - t0) / 1e6}
    for m, w in product(MARGINS, WINDOWS):
        cut = t_c - m * 1e6
        b = cut if w == "full" else t0 + FIRST_S * 1e6
        if b > cut or b - t0 < MIN_WINDOW_S * 1e6:
            out[f"{m}_{w}"] = None
            continue
        f = window_features(u, st, rotary, t0, b)
        # Older-firmware fallbacks, as within_drone.features.
        if np.isnan(f["vib_p95"]) and es is not None and "vibe[1]" in es:
            mm = between(es, t0, b)
            if mm.any():
                f["vib_p95"] = float(np.percentile(es["vibe[1]"][mm], 95))
        if rotary and np.isnan(f["tune_rms"]) and sp is not None and att is not None and "roll" in sp and "rollspeed" in att:
            mm = between(att, t0, b)
            if mm.sum() > 20:
                ts = att["timestamp"][mm]
                err = [np.interp(ts, sp["timestamp"], sp[k]) - att[a][mm] for k, a in (("roll", "rollspeed"), ("pitch", "pitchspeed"))]
                f["tune_rms"] = float(np.sqrt(np.mean(np.square(err))))
        out[f"{m}_{w}"] = {k: (None if f[k] is None or np.isnan(f[k]) else float(f[k])) for k in FEATURES}
    return out


# ---------------------------------------------------------------- sets

def load_index(root):
    raw = open(os.path.join(root, "dbinfo.json"), "rb").read()
    return {x["log_id"]: x for x in json.loads(gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw)}


def jsonl(name):
    return [json.loads(line) for line in open(os.path.join(RESULTS_DIR, name))]


def build_sets(db):
    by_vehicle = defaultdict(list)
    for x in db.values():
        if x.get("vehicle_uuid") and "SITL" not in str(x.get("sys_hw")):
            by_vehicle[x["vehicle_uuid"]].append(x)
    veh = lambda lid: db.get(lid, {}).get("vehicle_uuid") or lid
    leak0 = [r for r in jsonl("leak_curve_features.jsonl") if r["margin"] == 0]
    c1 = [r["log"] for r in leak0 if r["group"] == "crash" and db.get(r["log"], {}).get("vehicle_uuid")
          and len(by_vehicle[db[r["log"]]["vehicle_uuid"]]) >= 2]

    def eligible(lid):
        c = db[lid]
        earlier = [y for y in by_vehicle[c["vehicle_uuid"]] if y["log_id"] != lid and y["rating"] not in CRASH
                   and (y.get("duration_s") or 0) >= 30 and y["log_date"] <= c["log_date"]]
        return len(earlier) >= 3

    c1e = [lid for lid in c1 if eligible(lid)]
    by_crash = defaultdict(list)
    for r in jsonl("within_drone_features.jsonl"):
        by_crash[r["crash_id"]].append(r)
    usable = {cid for cid, fl in by_crash.items() if any(x["role"] == "crash" and x["features"] for x in fl)
              and any(x["role"] == "earlier" and x["features"] for x in fl)}
    c2 = sorted(usable)
    s = [(x["log_id"], cid) for cid in c2 for x in by_crash[cid] if x["role"] == "earlier"]
    crash_veh = {veh(lid) for lid in c1 + c2}
    n1_all = [r["log"] for r in leak0 if r["group"] == "normal"]
    n2_all = sorted({r["log_id"] for r in jsonl("rough_drone_features.jsonl") if r["role"] == "control"})
    n2_veh = {r["log_id"]: r.get("vehicle") for r in jsonl("rough_drone_features.jsonl") if r["role"] == "control"}
    n1 = [lid for lid in n1_all if veh(lid) not in crash_veh]
    n2 = [lid for lid in n2_all if (n2_veh.get(lid) or veh(lid)) not in crash_veh]
    removed = {"N1": len(n1_all) - len(n1), "N2": len(n2_all) - len(n2)}
    vehicle = {lid: veh(lid) for lid in c1 + n1}
    vehicle.update({lid: n2_veh.get(lid) or veh(lid) for lid in n2})
    vehicle.update({cid: veh(cid) for cid in c2})
    vehicle.update({lid: veh(cid) for lid, cid in s})  # an earlier flight belongs to its crash drone's cluster
    return {"C1": c1, "C1e": c1e, "C2": c2, "N1": n1, "N2": n2, "S": [lid for lid, _ in s]}, vehicle, removed


def extract_all(root, sets):
    """Parse each needed log once; cache to factorial_audit_features.jsonl so a rerun does not reparse."""
    cache_path = os.path.join(RESULTS_DIR, "factorial_audit_features.jsonl")
    cache = {}
    if os.path.exists(cache_path):
        for line in open(cache_path):
            r = json.loads(line)
            cache[(r["log_id"], r["is_crash"])] = r["windows"]
    paths = {}
    for d, _, files in os.walk(root):
        for f in files:
            if f.endswith(".ulg") and not f.startswith("._"):
                paths.setdefault(f[:-4], os.path.join(d, f))
    need = [(lid, True) for k in ("C1", "C2") for lid in sets[k]] + [(lid, False) for k in ("N1", "N2", "S") for lid in sets[k]]
    missing = []
    with open(cache_path, "a") as out:
        for i, (lid, is_crash) in enumerate(dict.fromkeys(need)):
            if (lid, is_crash) in cache:
                continue
            if lid not in paths:
                missing.append(lid)
                continue
            try:
                w = window_set(paths[lid], is_crash)
            except Exception as e:  # a corrupt log is dropped and counted, not fatal
                print(f"  parse failed {lid}: {e}")
                w = None
            cache[(lid, is_crash)] = w
            out.write(json.dumps({"log_id": lid, "is_crash": is_crash, "windows": w}) + "\n")
            if i % 50 == 0:
                print(f"  extracted {i}/{len(need)}", flush=True)
    return cache, missing


# ---------------------------------------------------------------- cells and bootstrap

def cell_rows(sets, cache, crash_set, comp_set, m, w, keep):
    rows = []
    for key, label in ((crash_set, 1), (comp_set, 0)):
        is_crash = label == 1
        for lid in sets[key]:
            win = cache.get((lid, is_crash))
            if not win or not win.get(f"{m}_{w}") or (keep is not None and lid not in keep[is_crash]):
                continue
            rows.append((lid, label, [np.nan if win[f"{m}_{w}"][k] is None else win[f"{m}_{w}"][k] for k in FEATURES]))
    return rows


def run_cell(rows, vehicle, scheme):
    X = np.array([r[2] for r in rows], float)
    y = np.array([r[1] for r in rows])
    groups = [vehicle[r[0]] for r in rows]
    mean, sd, scores = cv_scores(X, y, groups, scheme)
    return {"auc": mean, "sd_over_repeats": sd, "n_crash": int(y.sum()), "n_comp": int((y == 0).sum()),
            "underpowered": bool(y.sum() < MIN_CELL or (y == 0).sum() < MIN_CELL),
            "_y": y, "_scores": scores, "_clusters": groups}


def paired_bootstrap(cells, crash_vehicles, normal_vehicles):
    """AUC of every cell on the same resampled clusters. Returns {cell: array of BOOT AUCs}."""
    rng = np.random.default_rng(BOOT_SEED)
    cv_, nv_ = np.array(sorted(crash_vehicles)), np.array(sorted(normal_vehicles))
    index = {}
    for name, c in cells.items():
        by = defaultdict(list)
        for i, g in enumerate(c["_clusters"]):
            by[g].append(i)
        index[name] = by
    out = {name: np.empty(BOOT) for name in cells}
    for b in range(BOOT):
        draw = list(rng.choice(cv_, len(cv_), replace=True)) + list(rng.choice(nv_, len(nv_), replace=True))
        for name, c in cells.items():
            idx = [i for g in draw for i in index[name].get(g, ())]
            out[name][b] = auc(c["_y"][idx], c["_scores"][idx]) if idx else np.nan
    return out


def ci(a):
    a = a[~np.isnan(a)]
    return [float(np.percentile(a, 2.5)), float(np.percentile(a, 97.5))]


def effect(point, boot):
    lo, hi = ci(boot)
    return {"effect": point, "ci95": [lo, hi], "supported": bool(abs(point) >= 0.05 and (lo > 0 or hi < 0))}


def shapley(value, names):
    """Exact Shapley split of value(all) - value(none) over factor names; value takes a frozenset."""
    n, phi = len(names), {k: 0.0 for k in names}
    for order in permutations(names):
        on = frozenset()
        for k in order:
            phi[k] += value(on | {k}) - value(on)
            on = on | {k}
    return {k: v / math.factorial(n) for k, v in phi.items()}


# ---------------------------------------------------------------- main

def anchors(db, sets):
    leak = jsonl("leak_curve_features.jsonl")
    c1 = set(sets["C1"])
    rows = [r for r in leak if r["margin"] == 0 and (r["group"] == "normal" or r["log"] in c1)]
    X = np.array([[r[f] for f in FEATURES] for r in rows], float)
    y = np.array([1 if r["group"] == "crash" else 0 for r in rows])
    a1, _, _ = cv_scores(X, y, [r["log"] for r in rows], "strat", seeds=range(5))
    w = [r for r in jsonl("within_drone_features.jsonl") if r["crash_id"] in set(sets["C2"]) and r["features"]]
    X = np.array([[np.nan if r["features"].get(k) is None else r["features"][k] for k in FEATURES] for r in w], float)
    y = np.array([1 if r["role"] == "crash" else 0 for r in w])
    a2, _, _ = cv_scores(X, y, [r["crash_id"] for r in w], "group")
    return a1, a2


def extractor_check(cache):
    agree = total = 0
    for r in jsonl("leak_curve_features.jsonl"):
        if r["margin"] not in MARGINS:
            continue
        win = cache.get((r["log"], r["group"] == "crash"))
        new = win.get(f"{r['margin']}_full") if win else None
        if not new:
            continue
        total += 1
        ok = True
        for k in FEATURES:
            if k in ("vib_p95", "tune_rms"):
                continue
            a, b = r[k], new[k]
            a_nan, b_nan = a is None or (isinstance(a, float) and math.isnan(a)), b is None
            if a_nan != b_nan or (not a_nan and abs(a - b) > 1e-6):
                ok = False
        agree += ok
    return agree, total


def main(root):
    report = {"declared_in": "research/px4_log_study/factorial_audit.py docstring"}
    db = load_index(root)
    sets, vehicle, removed = build_sets(db)
    report["set_sizes"] = {k: len(v) for k, v in sets.items()}
    report["removed_overlapping_vehicles"] = removed
    print("sets", report["set_sizes"], "removed", removed)

    a1, a2 = anchors(db, sets)
    report["anchors"] = {"A1": a1, "A2": a2}
    print(f"A1 {a1:.4f} (0.891 +- 0.03)   A2 {a2:.4f} (0.569 +- 0.03)")
    if abs(a1 - 0.891) > 0.03 or abs(a2 - 0.569) > 0.03:
        return finish(report, "ABORT: stored-feature anchor out of range")

    cache, missing = extract_all(root, sets)
    report["missing_logs"] = len(missing)
    agree, total = extractor_check(cache)
    report["extractor_check"] = {"agree": agree, "total": total}
    print(f"A3 extractor agreement {agree}/{total}")
    if total == 0 or agree / total < 0.95:
        return finish(report, "ABORT: extractor check below 95%")

    rows = cell_rows(sets, cache, "C2", "N2", 10, "full", None)
    perm = []
    for s in range(20):
        yp = np.random.default_rng(s).permutation([r[1] for r in rows])
        X = np.array([r[2] for r in rows], float)
        perm.append(cv_scores(X, yp, [vehicle[r[0]] for r in rows], "group", seeds=(42,))[0])
    report["permutation_control"] = {"mean": float(np.mean(perm)), "sd": float(np.std(perm))}
    print(f"A4 permutation mean {np.mean(perm):.4f}")
    if abs(np.mean(perm) - 0.50) > 0.05:
        return finish(report, "ABORT: permutation control out of range")

    crash_veh = {vehicle[x] for k in ("C1", "C2") for x in sets[k]}
    normal_veh = {vehicle[x] for k in ("N1", "N2") for x in sets[k]}

    # Stage 1: the 2 x 2 (+ C1e row), m = 10, group, full.
    s1 = {(c, n): run_cell(cell_rows(sets, cache, "C1" if c == "C1e" else c, n, 10, "full",
                                     {True: set(sets["C1e"]), False: set(sets[n])} if c == "C1e" else None),
                           vehicle, "group")
          for c in ("C1", "C1e", "C2") for n in ("N1", "N2")}
    boot1 = paired_bootstrap({f"{c}|{n}": v for (c, n), v in s1.items()}, crash_veh, normal_veh)
    A = lambda c, n: s1[(c, n)]["auc"]
    B = lambda c, n: boot1[f"{c}|{n}"]
    report["stage1"] = {
        "cells": {f"{c} vs {n}": {k: v for k, v in s1[(c, n)].items() if not k.startswith("_")}
                  | {"ci95": ci(B(c, n))} for c, n in s1},
        "E_N": effect(((A("C1", "N1") - A("C1", "N2")) + (A("C2", "N1") - A("C2", "N2"))) / 2,
                      ((B("C1", "N1") - B("C1", "N2")) + (B("C2", "N1") - B("C2", "N2"))) / 2),
        "E_C": effect(((A("C1", "N1") - A("C2", "N1")) + (A("C1", "N2") - A("C2", "N2"))) / 2,
                      ((B("C1", "N1") - B("C2", "N1")) + (B("C1", "N2") - B("C2", "N2"))) / 2),
        "E_CN": effect((A("C1", "N1") - A("C1", "N2")) - (A("C2", "N1") - A("C2", "N2")),
                       (B("C1", "N1") - B("C1", "N2")) - (B("C2", "N1") - B("C2", "N2"))),
        "E_rule": effect(((A("C1", "N1") - A("C1e", "N1")) + (A("C1", "N2") - A("C1e", "N2"))) / 2,
                         ((B("C1", "N1") - B("C1e", "N1")) + (B("C1", "N2") - B("C1e", "N2"))) / 2),
        "E_pool": effect(((A("C1e", "N1") - A("C2", "N1")) + (A("C1e", "N2") - A("C2", "N2"))) / 2,
                         ((B("C1e", "N1") - B("C2", "N1")) + (B("C1e", "N2") - B("C2", "N2"))) / 2),
    }
    for k in ("E_rule", "E_pool"):  # C1e has 12 crashes: descriptive only, as declared
        report["stage1"][k]["supported"] = False
    en, ec = report["stage1"]["E_N"]["supported"], report["stage1"]["E_C"]["supported"]
    report["stage1"]["wording"] = (
        "Both the normal flights and the crash set contribute." if en and ec else
        "The drop depends on the choice of normal flights, not on which crashes are scored." if en else
        "The drop depends on which crashes are scored (eligibility/pool), not on the normals." if ec else
        "The AUC depends on the comparison set; the cause is not isolated.")

    # Stage 2: constant subset over all four (m, W) windows.
    def complete(lid, is_crash):
        w = cache.get((lid, is_crash))
        return bool(w) and all(w.get(f"{m}_{x}") for m, x in product(MARGINS, WINDOWS))

    keep = {True: {x for k in ("C1", "C2") for x in sets[k] if complete(x, True)},
            False: {x for k in ("N1", "N2", "S") for x in sets[k] if complete(x, False)}}
    n_c1, n_c2 = len(keep[True] & set(sets["C1"])), len(keep[True] & set(sets["C2"]))
    factors = dict(FACTORS)
    if min(n_c1, n_c2) < MIN_CELL:
        factors.pop("W")
        keep = {True: {x for k in ("C1", "C2") for x in sets[k] if cache.get((x, True)) and all(cache[(x, True)].get(f"{m}_full") for m in MARGINS)},
                False: {x for k in ("N1", "N2", "S") for x in sets[k] if cache.get((x, False)) and all(cache[(x, False)].get(f"{m}_full") for m in MARGINS)}}
        report["stage2_fallback"] = f"W dropped: constant subset left C1={n_c1}, C2={n_c2} crashes"
    names = list(factors)
    level = lambda on: {k: factors[k][1] if k in on else factors[k][0] for k in names} | ({} if "W" in factors else {"W": "full"})
    cells2 = {}
    for bits in product((0, 1), repeat=len(names)):
        on = frozenset(k for k, b in zip(names, bits) if b)
        lv = level(on)
        cells2[on] = run_cell(cell_rows(sets, cache, lv["C"], lv["N"], lv["m"], lv["W"], keep), vehicle, lv["CV"])
    same = {}
    for m, w, cv in product(MARGINS, factors.get("W", ("full",)), CVS):
        same[(m, w, cv)] = run_cell(cell_rows(sets, cache, "C2", "S", m, w, keep), vehicle, cv)
    allcells = {"|".join(sorted(k)) or "none": v for k, v in cells2.items()}
    allcells.update({f"S|{m}|{w}|{cv}": v for (m, w, cv), v in same.items()})
    boot2 = paired_bootstrap(allcells, crash_veh, normal_veh)
    key = lambda on: "|".join(sorted(on)) or "none"
    point = shapley(lambda on: -cells2[on]["auc"], names)  # positive = drop in AUC
    bphi = {k: np.empty(BOOT) for k in names}
    for b in range(BOOT):
        v = {on: boot2[key(on)][b] for on in cells2}
        for k, x in shapley(lambda on: -v[on], names).items():
            bphi[k][b] = x
    full_on = frozenset(names)
    total = cells2[frozenset()]["auc"] - cells2[full_on]["auc"]
    main_eff, inter = {}, {}
    for k in names:
        hi = [on for on in cells2 if k not in on]
        main_eff[k] = effect(float(np.mean([cells2[on]["auc"] - cells2[on | {k}]["auc"] for on in hi])),
                             np.mean([boot2[key(on)] - boot2[key(on | {k})] for on in hi], axis=0))
    for i, a in enumerate(names):
        for bname in names[i + 1:]:
            base = [on for on in cells2 if a not in on and bname not in on]
            d = lambda f: [f(on) - f(on | {a}) - f(on | {bname}) + f(on | {a, bname}) for on in base]
            inter[f"{a}x{bname}"] = effect(float(np.mean(d(lambda on: cells2[on]["auc"]))),
                                           np.mean(d(lambda on: boot2[key(on)]), axis=0))
    cons = {k: factors[k][1] for k in names} | {"W": "first30" if "W" in factors else "full"}
    s_step = same[(cons["m"], cons["W"], cons["CV"])]["auc"] - cells2[full_on]["auc"]
    report["stage2"] = {
        "constant_subset_crashes": {"C1": n_c1, "C2": n_c2},
        "cells": {key(on): {k: v for k, v in c.items() if not k.startswith("_")} | {"ci95": ci(boot2[key(on)])}
                  for on, c in cells2.items()},
        "same_aircraft_cells": {f"m{m} {w} {cv}": {k: v for k, v in c.items() if not k.startswith("_")}
                                | {"ci95": ci(boot2[f"S|{m}|{w}|{cv}"])} for (m, w, cv), c in same.items()},
        "total_drop": {"effect": total, "ci95": ci(boot2["none"] - boot2[key(full_on)])},
        "shapley": {k: {"value": point[k], "ci95": ci(bphi[k]),
                        "material": bool(point[k] >= 0.05 and ci(bphi[k])[0] > 0)} for k in names},
        "main_effects_drop": main_eff,
        "two_way_interactions": inter,
        "step_N2_to_S_at_conservative": s_step,
    }
    return finish(report, "completed")


def finish(report, status):
    report["status"] = status
    print(status)
    with open(os.path.join(RESULTS_DIR, "factorial_audit.json"), "w") as f:
        json.dump(report, f, indent=1, default=float)
    lines = ["# Factorial optimism audit", "", f"Declared in `research/px4_log_study/factorial_audit.py` (docstring). "
             f"Exploratory (dagger), declared after Round 14. Status: **{status}**.", "",
             f"Sets: {report.get('set_sizes')}; vehicles overlapping a crash set removed: {report.get('removed_overlapping_vehicles')}.",
             f"Anchors: {report.get('anchors')}; extractor check: {report.get('extractor_check')}; "
             f"permutation control: {report.get('permutation_control')}; logs not on disk: {report.get('missing_logs')}.", ""]
    s1 = report.get("stage1")
    if s1:
        lines += ["## Stage 1: 2 x 2 (m = 10 s, vehicle-grouped CV, full window, one extractor)", "",
                  "| Crashes vs comparison | n crash | n comp | AUC | SD over repeats | 95% cluster CI |", "|---|---|---|---|---|---|"]
        for name, c in s1["cells"].items():
            flag = " (underpowered)" if c["underpowered"] else ""
            lines.append(f"| {name}{flag} | {c['n_crash']} | {c['n_comp']} | {c['auc']:.3f} | {c['sd_over_repeats']:.3f} | "
                         f"[{c['ci95'][0]:.3f}, {c['ci95'][1]:.3f}] |")
        lines += ["", "| Effect | Estimate | 95% CI | Supported (abs >= 0.05, CI excludes 0) |", "|---|---|---|---|"]
        for k in ("E_N", "E_C", "E_CN", "E_rule", "E_pool"):
            e = s1[k]
            lines.append(f"| {k} | {e['effect']:+.3f} | [{e['ci95'][0]:+.3f}, {e['ci95'][1]:+.3f}] | {'yes' if e['supported'] else 'no'} |")
        lines += ["", f"Declared wording: **{s1['wording']}**", ""]
    s2 = report.get("stage2")
    if s2:
        t = s2["total_drop"]
        lines += ["## Stage 2: full factorial (descriptive)", "",
                  f"Constant-subset crashes: {s2['constant_subset_crashes']}. {report.get('stage2_fallback', '')}", "",
                  f"Total drop, most optimistic to most conservative other-aircraft cell: {t['effect']:.3f} "
                  f"[{t['ci95'][0]:.3f}, {t['ci95'][1]:.3f}].", "",
                  "| Factor | Shapley share of the drop | 95% CI | Material | Main effect (drop) | 95% CI |", "|---|---|---|---|---|---|"]
        for k, v in s2["shapley"].items():
            me = s2["main_effects_drop"][k]
            lines.append(f"| {k} | {v['value']:+.3f} | [{v['ci95'][0]:+.3f}, {v['ci95'][1]:+.3f}] | {'yes' if v['material'] else 'no'} | "
                         f"{me['effect']:+.3f} | [{me['ci95'][0]:+.3f}, {me['ci95'][1]:+.3f}] |")
        lines += ["", "| Interaction | Estimate | 95% CI |", "|---|---|---|"]
        lines += [f"| {k} | {e['effect']:+.3f} | [{e['ci95'][0]:+.3f}, {e['ci95'][1]:+.3f}] |" for k, e in s2["two_way_interactions"].items()]
        lines += ["", f"Further step N2 -> same aircraft (S) at the conservative settings: {s2['step_N2_to_S_at_conservative']:+.3f}.", "",
                  "| Cell (factors at conservative level) | n crash | n comp | AUC | SD over repeats | 95% CI |", "|---|---|---|---|---|---|"]
        for name, c in {**s2["cells"], **{f"same aircraft {k}": v for k, v in s2["same_aircraft_cells"].items()}}.items():
            lines.append(f"| {name}{' (underpowered)' if c['underpowered'] else ''} | {c['n_crash']} | {c['n_comp']} | {c['auc']:.3f} | "
                         f"{c['sd_over_repeats']:.3f} | [{c['ci95'][0]:.3f}, {c['ci95'][1]:.3f}] |")
    lines += ["", "Bootstrap CIs resample vehicles from fixed out-of-fold scores (models not refitted). "
              "SD over repeats is the spread across CV seeds, not an interval."]
    open(os.path.join(RESULTS_DIR, "factorial_audit.md"), "w").write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "/Volumes/One Touch/AeroFleet_px4_data")
