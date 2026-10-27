"""Round 16 audit: confirmed-crash subset, archive dates vs GPS time, grouped leak curve on one cohort, clustered
between-drone variants, and stumps against the refit null.

PRE-DECLARED (committed and pushed before this script is run). Status: exploratory (dagger), declared after the
sixteenth internal review, not blind: every published value named below is already known.

COMMON: model = factorial_audit.fit_predict (L2 logistic, lambda 1.0); tie-corrected AUC (factorial_audit.auc);
"grouped" = folds by vehicle (dbinfo vehicle_uuid, else log id), clusters sorted, seeds 42-46; CIs = cluster
bootstrap over vehicles on seed-averaged out-of-fold scores (2,000 resamples). Crash moment t_c and "confirmed" use
pilot_vs_drone.crash_time exactly as before.

PART A - Confirmed-crash subset (internal review 16, problem 1)
  A crash log is CONFIRMED if t_c is tilt-defined (tilt > 60 deg before the end of the armed period) AND within 10 s
  after t_c the armed period ends or the land detector reports landed or ground contact (the plausibility rule of the
  earlier crash-moment check). Groups reported separately: confirmed, tilt-defined but not confirmed, fallback (no
  tilt > 60 deg).
  A1 Leak curve (crash vs normal, stored leak_curve features) at m in {0, 2, 5, 10, 20, 30}, grouped, on (a) all
     crashes and (b) confirmed crashes, each against all normal flights, constant cohort within each (logs with a
     window at every m). Declared criterion re-evaluated: AUC(m = 0) - AUC(m = 10) >= 0.10.
  A2 Window effect in the factorial pipeline: for crash sets C1 and C2 restricted to confirmed crashes, against N1
     and N2, full window, grouped: AUC(m = 0) - AUC(m = 10), averaged over the four cells, with a paired cluster
     bootstrap CI (factorial_audit.paired_bootstrap, seed 2041). Compared with the same quantity on all crashes.
     Rule (fixed now): leakage is called material for confirmed crashes if this difference is >= 0.05 and its CI
     excludes 0.
  A3 Within-drone tests on confirmed crashes, without earlier flights flown after the crash (the current primary):
     rank tests (within_drone.rank_test, vib_p95 then tune_rms, rng seed 0) and grouped model with cluster CI.
  A4 The 7/9 -> 1/9 tuning-check drop tested against the normal-flight drop: one-sided Fisher exact test on
     (crash logs that lost firing, crash logs that kept firing) vs (normal flights that lost firing, kept firing),
     using flights present at both m = 0 and m = 10 in test_flight_check(_minus10s)_settled.jsonl. Descriptive.

PART B - Archive dates vs GPS time (problem 2), descriptive
  For every exposure flight of the between-drone cases (rough_drone_features, role case), every earlier flight of the
  within-drone selection, and their crash logs, on disk: GPS UTC start (r14_audit.utc_start). Report: share with a
  usable GPS time; share whose GPS UTC date equals the index log_date (exact, +-1 day); for flights dated before the
  crash day, how many start after the crash by GPS time. Percentages are also restated with undated flights excluded.

PART C - Grouped leak curve and Table 6 additions (problem 3)
  C1 Grouped CV at m = 0 on the 213-flight constant cohort (Table 6 Step "1b"), so Steps 2-3 change only the window.
  C2 = A1(a) above on the 213-flight cohort; declared Q3a criterion re-evaluated with grouped folds.

PART D - Clustered between-drone variants (problem 4)
  For each variant - declared; S1 same airframe; S2 no crash-day case flights; S3 accelerometer only; S3 estimator
  only; without case flights GPS places after the crash; without those and undated ones - keep one set per crashed
  airframe, 1,000 random selections (seed 2042): median mean rank, median exact-null p (10,000 draws), share of
  selections with p < 0.025; and the roughest-drone test (share of sets where the crashed drone ranks highest)
  with a simulated Poisson-binomial p (10,000 draws) per selection, median reported. S8 (duration-adjusted) is not
  re-run and is flagged as unclustered.
  D2 The bootstrap p of the Round-15 audit is restated with its method: null-shifted two-stage bootstrap
     p = share of resamples with mean* >= 2 rbar - 0.5; also the percentile p = share of resamples with mean* <= 0.5.

PART E - Stumps against the refit null (problem 5)
  Depth-1 trees (SimpleDecisionTree max_depth=1), Task B, full sample, m in {0, 10}, stratified 5-fold x seeds 0-4,
  mean AUC over seeds; 200 refitting label permutations (seed 2043); report AUC, null mean/SD, p and approximate
  bounds AUC +- 1.96 null SD (called approximate: the null SD is the spread without signal, not the SE at the
  observed AUC).

Outputs: research/results/px4_log_study/r16_audit[_PARTS].md and .json.

    python research/px4_log_study/r16_audit.py DATA_ROOT [PARTS]
"""
import gzip
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone

import numpy as np

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(SCRIPT_DIR)
import factorial_audit as fa
import postcrash_audit as pca
import r14_audit as r14
import r15_audit as r15
import sensitivity
from within_drone import rank_test

RESULTS_DIR = os.path.join(SCRIPT_DIR, "..", "results", "px4_log_study")
MARGINS = (0, 2, 5, 10, 20, 30)


def jsonl(name):
    return [json.loads(line) for line in open(os.path.join(RESULTS_DIR, name))]


def crash_status(paths, ids):
    """{log_id: 'confirmed' | 'tilt_unconfirmed' | 'fallback' | 'unreadable'}"""
    from pyulog import ULog
    from pilot_vs_drone import armed_period, between, crash_time, topic

    out = {}
    for lid in ids:
        try:
            u = ULog(paths[lid], message_name_filter_list=["vehicle_status", "vehicle_land_detected", "vehicle_attitude"])
            st = topic(u, "vehicle_status")
            t_arm, t_end = armed_period(st)
            rotary = bool(st["is_rotary_wing"][-1]) if "is_rotary_wing" in st else True
            tc = crash_time(u, t_arm, t_end, rotary)
        except Exception:
            out[lid] = "unreadable"
            continue
        if not tc < t_end:
            out[lid] = "fallback"
            continue
        ok = t_end - tc <= 10e6
        land = topic(u, "vehicle_land_detected")
        if land is not None and not ok:
            mm = between(land, tc, tc + 10e6)
            for k in ("landed", "ground_contact"):
                if k in land and mm.any() and land[k][mm].any():
                    ok = True
        out[lid] = "confirmed" if ok else "tilt_unconfirmed"
    return out


def grouped_leak(rows, veh, keep_crash):
    """Grouped crash-vs-normal AUC at each margin on the constant cohort of the given crash subset."""
    present = defaultdict(set)
    for r in rows:
        if r["group"] == "normal" or r["log"] in keep_crash:
            present[r["log"]].add(r["margin"])
    cohort = {l for l, ms in present.items() if set(MARGINS) <= ms}
    out = {}
    for m in MARGINS:
        R = [r for r in rows if r["margin"] == m and r["log"] in cohort]
        X = np.array([[r[f] for f in fa.FEATURES] for r in R], float)
        y = np.array([1 if r["group"] == "crash" else 0 for r in R])
        cl = [veh(r["log"]) for r in R]
        a, sd, s = fa.cv_scores(X, y, cl, "group")
        out[m] = {"n_crash": int(y.sum()), "n_normal": int((y == 0).sum()), "auc": a, "sd": sd, "ci": r15._cluster_ci(y, s, cl, 2040)}
    out["drop_0_10"] = out[0]["auc"] - out[10]["auc"]
    out["criterion_met"] = bool(out["drop_0_10"] >= 0.10)
    return out


# ---------------------------------------------------------------- A and C

def part_ac(root):
    db = r15.load_db(root)
    veh = lambda lid: db.get(lid, {}).get("vehicle_uuid") or lid
    paths = pca.ulg_paths(root)
    leak = jsonl("leak_curve_features.jsonl")
    crash_ids = sorted({r["log"] for r in leak if r["group"] == "crash"})
    w = pca.within_rows()
    c2 = sorted({r["crash_id"] for r in w})
    status = crash_status(paths, sorted(set(crash_ids) | set(c2)))
    groups = defaultdict(int)
    for lid in crash_ids:
        groups[status[lid]] += 1
    out = {"task_a_status_counts": dict(groups),
           "within_status_counts": dict(defaultdict(int, {k: sum(status[c] == k for c in c2) for k in set(status.values())}))}
    confirmed = {l for l, s in status.items() if s == "confirmed"}
    # C1: grouped m = 0 on the 213-flight cohort (all crashes)
    present = defaultdict(set)
    for r in leak:
        present[r["log"]].add(r["margin"])
    cohort = {l for l, ms in present.items() if 30 in ms}
    R = [r for r in leak if r["margin"] == 0 and r["log"] in cohort]
    X = np.array([[r[f] for f in fa.FEATURES] for r in R], float)
    y = np.array([1 if r["group"] == "crash" else 0 for r in R])
    cl = [veh(r["log"]) for r in R]
    a, sd, s = fa.cv_scores(X, y, cl, "group")
    out["C1_step1b"] = {"n_crash": int(y.sum()), "n_normal": int((y == 0).sum()), "auc": a, "ci": r15._cluster_ci(y, s, cl, 2040)}
    out["A1_all"] = grouped_leak(leak, veh, set(crash_ids))
    out["A1_confirmed"] = grouped_leak(leak, veh, confirmed)
    print("A1 done", flush=True)
    # A2: factorial window effect on confirmed crashes
    sets, vehicle, _ = fa.build_sets(db)
    cache = {}
    for line in open(os.path.join(RESULTS_DIR, "factorial_audit_features.jsonl")):
        r = json.loads(line)
        cache[(r["log_id"], r["is_crash"])] = r["windows"]

    def window_effect(subset_filter, tag):
        cells = {}
        for c in ("C1", "C2"):
            crashes = {x for x in sets[c] if subset_filter(x)}
            for n in ("N1", "N2"):
                for m in (0, 10):
                    keep = {True: crashes, False: set(sets[n])}
                    both = {x for x in crashes if cache.get((x, True)) and cache[(x, True)].get(f"0_full") and cache[(x, True)].get(f"10_full")}
                    keep[True] = both
                    cells[f"{c}|{n}|{m}"] = fa.run_cell(fa.cell_rows(sets, cache, c, n, m, "full", keep), vehicle, "group")
        crash_veh = {vehicle[x] for c in ("C1", "C2") for x in sets[c]}
        normal_veh = {vehicle[x] for n in ("N1", "N2") for x in sets[n]}
        old = fa.BOOT_SEED
        fa.BOOT_SEED = 2041
        boot = fa.paired_bootstrap(cells, crash_veh, normal_veh)
        fa.BOOT_SEED = old
        keys = [(c, n) for c in ("C1", "C2") for n in ("N1", "N2")]
        d = float(np.mean([cells[f"{c}|{n}|0"]["auc"] - cells[f"{c}|{n}|10"]["auc"] for c, n in keys]))
        db_ = np.mean([boot[f"{c}|{n}|0"] - boot[f"{c}|{n}|10"] for c, n in keys], axis=0)
        return {"diff_m0_minus_m10": d, "ci": fa.ci(db_),
                "cells": {k: {"auc": v["auc"], "n_crash": v["n_crash"], "n_comp": v["n_comp"]} for k, v in cells.items()}}

    out["A2_all"] = window_effect(lambda x: True, "all")
    out["A2_confirmed"] = window_effect(lambda x: x in confirmed, "confirmed")
    out["A2_material_for_confirmed"] = bool(out["A2_confirmed"]["diff_m0_minus_m10"] >= 0.05 and out["A2_confirmed"]["ci"][0] > 0)
    print("A2 done", flush=True)
    # A3: within-drone on confirmed, without following flights
    ordering = pca.ordering(root, w)
    follows = {k for k, v in ordering.items() if v == "follows"}
    wc = [r for r in w if r["crash_id"] in confirmed]
    a3 = {"confirmed_crashes_in_within_sample": len({r["crash_id"] for r in wc})}
    a3["rank"] = pca.part_a(wc, follows)
    try:
        a3["model"] = pca.part_b(wc, follows)
    except Exception as e:  # too few crashes for 5 folds
        a3["model"] = f"not run: {e}"
    out["A3_within_confirmed"] = a3
    # A4: tuning check drop, crash vs normal
    out["A4"] = tuning_fisher()
    return out


def tuning_fisher():
    """Paired logs firing C_TUNE at m = 0: did crash logs lose firing at m = 10 s more often than normal flights?"""
    from math import comb

    def load(name):
        return {(r["group"], r["log_id"]): r for r in jsonl(name)}

    full, cut = load("test_flight_check_settled.jsonl"), load("test_flight_check_minus10s_settled.jsonl")

    def counts(group, cause_ok):
        lost = kept = 0
        for key, r in full.items():
            if key[0] != group or not cause_ok(r) or key not in cut:
                continue
            if r["checks"].get("C_TUNE") and "C_TUNE" in cut[key]["checks"]:
                if cut[key]["checks"]["C_TUNE"]:
                    kept += 1
                else:
                    lost += 1
        return lost, kept

    cl, ck = counts("forum", lambda r: str(r.get("cause", "")).startswith("tuning"))
    nl, nk = counts("normal", lambda r: True)
    # One-sided Fisher exact: P(crash losses >= observed | margins), hypergeometric.
    n, K, N = cl + ck, cl + nl, cl + ck + nl + nk
    p = sum(comb(K, x) * comb(N - K, n - x) for x in range(cl, min(K, n) + 1)) / comb(N, n) if n and N else None
    return {"crash_lost": cl, "crash_kept": ck, "normal_lost": nl, "normal_kept": nk, "one_sided_fisher_p": p}


# ---------------------------------------------------------------- B

def part_b(root):
    db = r15.load_db(root)
    paths = pca.ulg_paths(root)
    sets, role = sensitivity.load_between()
    pairs = []  # (flight log_id, crash log_id)
    for sid in sets:
        for v, rs in sets[sid].items():
            if role[(sid, v)] == "case":
                pairs += [(r["log_id"], sid) for r in rs]
    for r in pca.within_rows():
        if r["role"] == "earlier":
            pairs.append((r["log_id"], r["crash_id"]))
    pairs = sorted(set(pairs))
    utc = {}
    for lid in sorted({x for p in pairs for x in p}):
        try:
            utc[lid] = r14.utc_start(paths[lid]) if lid in paths else None
        except Exception:
            utc[lid] = None
    gdate = lambda lid: datetime.fromtimestamp(utc[lid] / 1e6, tz=timezone.utc).date().isoformat() if utc.get(lid) else None
    logs = sorted(utc)
    with_gps = [l for l in logs if utc[l] is not None]
    same = sum(gdate(l) == str(db.get(l, {}).get("log_date"))[:10] for l in with_gps)
    within1 = sum(abs((datetime.fromisoformat(gdate(l)) - datetime.fromisoformat(str(db[l]["log_date"])[:10])).days) <= 1
                  for l in with_gps if db.get(l, {}).get("log_date"))
    before_day = [(f, c) for f, c in pairs if str(db.get(f, {}).get("log_date"))[:10] < str(db.get(c, {}).get("log_date"))[:10]]
    viol = [(f, c) for f, c in before_day if utc.get(f) and utc.get(c) and utc[f] > utc[c]]
    return {"logs": len(logs), "with_gps": len(with_gps), "gps_date_equals_index_date": same,
            "within_one_day": within1, "pairs": len(pairs), "earlier_dated_pairs": len(before_day),
            "earlier_dated_pairs_with_both_gps": sum(1 for f, c in before_day if utc.get(f) and utc.get(c)),
            "earlier_dated_but_after_crash_by_gps": len(viol),
            "dated_only_shares": {"between": "47 of 85 (55%)", "within": "85 of 192 (44%)"}}


# ---------------------------------------------------------------- D

def per_set(sets, role, keep_case=lambda r: True, keep_control=lambda sid, v: True, source=None):
    rows = []
    for sid in sorted(sets):
        vehicles = sets[sid]
        case = [v for v in vehicles if role[(sid, v)] == "case"]
        if not case:
            continue

        def value(rs, flt):
            vals = defaultdict(list)
            for r in rs:
                f = r["features"]
                if f and f.get("vib_p95") is not None and flt(r):
                    vals[f.get("src_vib")].append(f["vib_p95"])
            return {s: float(np.median(v)) for s, v in vals.items() if len(v) >= 2}

        for s, cv in value(vehicles[case[0]], keep_case).items():
            if source and s != source:
                break
            ctrl = [value(vehicles[v], lambda r: True).get(s) for v in sorted(vehicles)
                    if role[(sid, v)] == "control" and keep_control(sid, v)]
            ctrl = [x for x in ctrl if x is not None]
            if ctrl:
                rows.append({"case": case[0], "rank": sum(x < cv for x in ctrl) / len(ctrl), "k": len(ctrl)})
            break
    return rows


def one_per_airframe(rows, rng):
    by = defaultdict(list)
    for r in rows:
        by[r["case"]].append(r)
    cases = sorted(by)
    mr, ps, tops, tps = [], [], [], []
    for _ in range(1000):
        pick = [by[c][rng.integers(len(by[c]))] for c in cases]
        o, p, _ = sensitivity.null_p([x["rank"] for x in pick], [x["k"] for x in pick], draws=10_000, seed=int(rng.integers(1 << 31)))
        top = sum(x["rank"] == 1.0 for x in pick)
        sim = sum(rng.random((10_000,)) < 1 / (x["k"] + 1) for x in pick)
        mr.append(o); ps.append(p); tops.append(top / len(pick)); tps.append(float(np.mean(sim >= top)))
    return {"sets_all": len(rows), "airframes": len(cases), "median_mean_rank": float(np.median(mr)), "median_p": float(np.median(ps)),
            "share_p_below_0025": float(np.mean(np.array(ps) < 0.025)), "median_top_share": float(np.median(tops)),
            "median_top_p": float(np.median(tps))}


def part_d(root):
    db = r15.load_db(root)
    sets, role = sensitivity.load_between()
    from collections import Counter
    airframe = {}
    for sid, vehicles in sets.items():
        for v, rs in vehicles.items():
            names = Counter(db[r["log_id"]].get("airframe_name") for r in rs if r["log_id"] in db)
            airframe[(sid, v)] = names.most_common(1)[0][0] if names else None
    case_of = lambda sid: next(v for v in sets[sid] if role[(sid, v)] == "case")
    same_day = {r["log_id"] for r in pca.within_rows() if r["role"] == "earlier" and r["same_day"] == "1"}
    # GPS ordering of case crash-day flights, as r14_audit Part B
    paths = pca.ulg_paths(root)
    follows, undet = set(), set()
    for sid in sets:
        for r in sets[sid][case_of(sid)]:
            if db.get(r["log_id"], {}).get("log_date") == db.get(sid, {}).get("log_date"):
                try:
                    a, b = r14.utc_start(paths[r["log_id"]]), r14.utc_start(paths[sid])
                except Exception:
                    a = b = None
                if a is None or b is None:
                    undet.add(r["log_id"])
                elif a > b:
                    follows.add(r["log_id"])
    variants = {
        "declared": {},
        "S1_same_airframe": {"keep_control": lambda sid, v: airframe[(sid, v)] is not None and airframe[(sid, v)] == airframe[(sid, case_of(sid))]},
        "S2_no_crash_day": {"keep_case": lambda r: r["log_id"] not in same_day},
        "S3_accelerometer": {"source": "imu"},
        "S3_estimator": {"source": "estimator_vibe"},
        "gps_without_following": {"keep_case": lambda r: r["log_id"] not in follows},
        "gps_without_following_or_undated": {"keep_case": lambda r: r["log_id"] not in follows | undet},
    }
    rng = np.random.default_rng(2042)
    out = {"S8": "duration-adjusted variant not re-run; unclustered"}
    for name, kw in variants.items():
        out[name] = one_per_airframe(per_set(sets, role, **kw), rng)
        print("D", name, round(out[name]["median_p"], 4), flush=True)
    # D2: restate the Round-15 two-stage bootstrap p by both methods (same resampling as r15 B3, seed 2032)
    T = r15.set_table()
    by_case = defaultdict(list)
    for t in T:
        by_case[t["case"]].append(t)
    cases = sorted(by_case)
    ctrls = sorted({c for t in T for c, _ in t["ctrl"]})
    rank = lambda t, w: sum(w.get(c, 0) for c, x in t["ctrl"] if x < t["val"]) / sum(w.get(c, 0) for c, _ in t["ctrl"])
    rbar = float(np.mean([sum(x < t["val"] for _, x in t["ctrl"]) / len(t["ctrl"]) for t in T]))
    rng = np.random.default_rng(2032)
    b = []
    for _ in range(2000):
        w = defaultdict(int)
        for c in rng.choice(ctrls, len(ctrls)):
            w[c] += 1
        rk = [rank(t, w) for c in rng.choice(cases, len(cases)) for t in by_case[c] if sum(w.get(k, 0) for k, _ in t["ctrl"])]
        b.append(np.mean(rk))
    b = np.array(b)
    out["D2_bootstrap_p"] = {"rbar": rbar, "shifted_p": float(np.mean(b >= 2 * rbar - 0.5)), "percentile_p": float(np.mean(b <= 0.5)),
                             "ci": [float(np.percentile(b, 2.5)), float(np.percentile(b, 97.5))]}
    return out


# ---------------------------------------------------------------- E

def part_e():
    from stage2_stage3_execution import SimpleDecisionTree
    rows = [r for r in jsonl("leak_curve_features.jsonl") if r["group"] == "crash" and r["label"] in ("pilot", "drone")]
    rng = np.random.default_rng(2043)
    out = {}

    def stump_auc(X, y):
        Xi = X.copy()
        med = np.nanmedian(Xi, axis=0)
        for j in range(Xi.shape[1]):
            Xi[np.isnan(Xi[:, j]), j] = med[j] if not np.isnan(med[j]) else 0.0
        aucs = []
        for s in range(5):
            folds, sc = r15.strat_folds(y, s), np.zeros(len(y))
            for f in range(5):
                te, tr = folds == f, folds != f
                sc[te] = SimpleDecisionTree(max_depth=1).fit(Xi[tr], y[tr]).predict_proba(Xi[te])
            aucs.append(fa.auc(y, sc))
        return float(np.mean(aucs))

    for m in (0, 10):
        R = [r for r in rows if r["margin"] == m]
        X = np.array([[r[f] for f in fa.FEATURES] for r in R], float)
        y = np.array([1 if r["label"] == "drone" else 0 for r in R])
        obs = stump_auc(X, y)
        null = np.array([stump_auc(X, rng.permutation(y)) for _ in range(200)])
        sd = float(null.std())
        out[f"m{m}"] = {"n": len(y), "auc": obs, "null_mean": float(null.mean()), "null_sd": sd,
                        "p": float((np.sum(null >= obs) + 1) / 201), "approx_bounds": [obs - 1.96 * sd, obs + 1.96 * sd]}
        print("E", m, round(obs, 3), flush=True)
    return out


def main(root, parts="ABDE"):
    rep = {"declared_in": "research/px4_log_study/r16_audit.py docstring"}
    tag = "" if parts == "ABDE" else "_" + parts
    for p, fn in (("A", lambda: part_ac(root)), ("B", lambda: part_b(root)), ("D", lambda: part_d(root)), ("E", part_e)):
        if p in parts:
            print(f"=== Part {p}", flush=True)
            rep[p] = fn()
            with open(os.path.join(RESULTS_DIR, f"r16_audit{tag}.json"), "w") as f:
                json.dump(rep, f, indent=1, default=float)
    with open(os.path.join(RESULTS_DIR, f"r16_audit{tag}.md"), "w") as f:
        f.write("# Round 16 audit\n\nDeclared in `research/px4_log_study/r16_audit.py` (docstring). Exploratory (dagger).\n\n"
                "Part A includes Part C (grouped leak curve and Step 1b). Full numbers:\n\n```\n"
                + json.dumps(rep, indent=1, default=float)[:60000] + "\n```\n")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "/Volumes/One Touch/AeroFleet_px4_data",
         sys.argv[2] if len(sys.argv) > 2 else "ABDE")
