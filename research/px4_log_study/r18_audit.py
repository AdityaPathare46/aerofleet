"""Round 18 audit: era-adjusted label confound, an objective crash-event detector validated against two reviewers,
and the window analyses rerun on tilt-defined and detector-defined crashes.

PRE-DECLARED (committed and pushed before this script is run). Status: exploratory (dagger), declared after the
eighteenth internal review, not blind: all earlier results named below are known.

PART A - Label confound, adjusted (review problem 1)
  Population: the 381 crash-rated multicopter logs (index mav_type Quadrotor/Hexarotor/Octorotor) of the archive-wide
  label audit; tilt-defined = crash status confirmed or tilt_unconfirmed (r16_audit.crash_status); unreadable logs
  excluded. Strata: year band (<= 2019, 2020-2022, >= 2023) x vehicle type (quad, hexa, octo).
  A1 Mantel-Haenszel common odds ratio (aircraft-rated vs pilot-rated, odds of a tilt event) with the
     Robins-Breslow-Greenland 95% CI and the Cochran-Mantel-Haenszel test (1 df, no continuity correction).
  A2 Logistic regression: tilt ~ pilot-rated + year band + vehicle type (Newton-Raphson; Wald 95% CI for the
     pilot-rated coefficient).
  A3 AUC of "tilt event present" alone as a score for aircraft-rated vs pilot-rated: (a) over the 341 readable
     multicopter logs, (b) over the 148 modelled Task B crashes (stored status); bootstrap 95% CI (2,000, seed 2050).
  Wording rule (fixed now): the paper keeps one hedge, "could", for the classifier implication; if A1's CI includes
  1 the label-confound finding is reported as "unadjusted association, not robust to era and vehicle type".

PART B - Objective crash-event detector (review problem 2)
  For a log: airborne start t0 = first land-detector "not landed" after arming (as before); search [t0, end of armed
  period]. E_tilt = first attitude sample with tilt > 60 deg. E_impact = first sensor_combined sample after t0 + 2 s
  with |accelerometer| > 4 g (39.2 m/s^2). Detector time t_e = earliest of E_tilt and E_impact; no event if neither.
  Sensitivity: impact thresholds 3 g and 6 g (event yes/no only).
  Validation on the 50 reviewed logs, each reviewer separately (A = crash_moment_review.csv reviewer_2, B = blind
  sheet via the key): "contains crash" = correct / too early / too late, "no crash visible" = no, "can't tell"
  excluded; detector event vs contains-crash: agreement and Cohen's kappa with bootstrap 95% CI (2,000, seed 2051).
  Timing vs the old t_c: of logs a reviewer called "too late", share with t_e earlier than t_c by > 2 s; "too early",
  share with t_e later by > 2 s; "correct", share with |t_e - t_c| <= 2 s.
  False-alarm check: share of the 139 normal flights (leak_curve normal sample) with a detector event.
  GATE (fixed now): detector-defined crashes are used as the primary re-analysis only if kappa >= 0.6 against BOTH
  reviewers; otherwise Part C's detector results are reported as exploratory only and the paper says so.

PART C - Window analyses rerun (review problem 2)
  C1 Grouped leak curve on the constant cohort (r16_audit.grouped_leak) for (a) the tilt-defined crashes (stored
     features; t_c unchanged), (b) detector-defined crashes (crash features recomputed with leak_curve.window_features
     ending at t_e - m; normal flights' stored features). Declared criterion: AUC(m=0) - AUC(m=10) >= 0.10.
  C2 Factorial window effect, as r16_audit A2 (C1 and C2 crash sets vs N1, N2; full window; m = 0 vs 10; grouped;
     paired cluster bootstrap seed 2053): (a) tilt-defined crashes (cached features), (b) detector-defined crashes
     (windows recomputed at t_e with the factorial extractor, older-firmware fallbacks included).
  C3 Within-drone, without earlier flights flown after the crash: rank tests and grouped model for (a) tilt-defined
     crashes (stored), (b) detector-defined crashes (crash flight recomputed at t_e - 10 s with fallbacks).

PART D - Intervals for the two-reviewer kappas: bootstrap 95% CI (2,000 resamples of the 50 logs, seed 2052) for
  "computed crash moment right" and "log contains the crash".

PART E - Counts (review problem 2): of the 148 modelled crashes, tilt-defined vs fallback by index vehicle type
  (multicopter, fixed-wing, VTOL, other) and by the log's is_rotary_wing flag; the multicopter subset reconciles the
  72/148 (49%) and 41/108 (38%) figures.

Outputs: research/results/px4_log_study/r18_audit.md and .json.

    python research/px4_log_study/r18_audit.py DATA_ROOT
"""
import csv
import gzip
import json
import math
import os
import sys
from collections import Counter, defaultdict
from itertools import product

import numpy as np
from scipy.stats import chi2

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(SCRIPT_DIR)
import factorial_audit as fa
import postcrash_audit as pca
from r16_audit import crash_status, grouped_leak

RESULTS_DIR = os.path.join(SCRIPT_DIR, "..", "results", "px4_log_study")
MULTI = ("Quadrotor", "Hexarotor", "Octorotor")
CRASH = ("crash_sw_hw", "crash_pilot")
MARGINS = (0, 2, 5, 10, 20, 30)
G = 9.80665
CONTAINS = {"correct": 1, "too early": 1, "too late": 1, "no crash visible": 0}


def jsonl(name):
    return [json.loads(l) for l in open(os.path.join(RESULTS_DIR, name))]


def load_db(root):
    raw = open(os.path.join(root, "dbinfo.json"), "rb").read()
    return {x["log_id"]: x for x in json.loads(gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw)}


def kappa(pairs):
    n = len(pairs)
    if not n:
        return None
    po = sum(a == b for a, b in pairs) / n
    ca, cb = Counter(a for a, _ in pairs), Counter(b for _, b in pairs)
    pe = sum(ca[c] * cb[c] for c in set(ca) | set(cb)) / n ** 2
    return (po - pe) / (1 - pe) if pe < 1 else None


def kappa_ci(pairs, seed):
    rng = np.random.default_rng(seed)
    vals = []
    for _ in range(2000):
        s = [pairs[i] for i in rng.integers(0, len(pairs), len(pairs))]
        k = kappa(s)
        if k is not None:
            vals.append(k)
    return [float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))]


# ---------------------------------------------------------------- per-log parse

def analyse_log(path, is_crash, thresholds=(3.0, 4.0, 6.0)):
    """One parse: old t_c, detector events, and crash-window features ending at t_e."""
    from pyulog import ULog
    from leak_curve import TOPICS, window_features
    from pilot_vs_drone import armed_period, between, crash_time, topic

    u = ULog(path, message_name_filter_list=list(TOPICS) + ["estimator_status", "sensor_combined"])
    st = topic(u, "vehicle_status")
    per = armed_period(st) if st is not None else None
    if per is None:
        return None
    t_arm, t_end = per
    rotary = bool(st["is_rotary_wing"][-1]) if "is_rotary_wing" in st else None
    t_c = crash_time(u, t_arm, t_end, True if rotary is None else rotary) if is_crash else t_end
    land = topic(u, "vehicle_land_detected")
    t0 = t_arm
    if land is not None:
        mm = between(land, t_arm, t_end) & (land["landed"] == 0)
        if mm.any():
            t0 = land["timestamp"][mm][0]
    att = topic(u, "vehicle_attitude")
    e_tilt = None
    if att is not None:
        m = between(att, t0, t_end)
        q1, q2 = att["q[1]"][m], att["q[2]"][m]
        tilt = np.degrees(np.arccos(np.clip(1 - 2 * (q1 ** 2 + q2 ** 2), -1, 1)))
        over = np.where(tilt > 60)[0]
        e_tilt = int(att["timestamp"][m][over[0]]) if len(over) else None
    sc = topic(u, "sensor_combined")
    e_imp = {}
    if sc is not None and "accelerometer_m_s2[0]" in sc:
        m = between(sc, t0 + 2e6, t_end)
        a = np.sqrt(sum(sc[f"accelerometer_m_s2[{i}]"][m].astype(float) ** 2 for i in range(3)))
        for th in thresholds:
            over = np.where(a > th * G)[0]
            e_imp[th] = int(sc["timestamp"][m][over[0]]) if len(over) else None
    else:
        e_imp = {th: None for th in thresholds}
    ev = {th: min([t for t in (e_tilt, e_imp[th]) if t is not None], default=None) for th in thresholds}
    out = {"t_arm": int(t_arm), "t_end": int(t_end), "t0": int(t0), "t_c": int(t_c), "rotary": rotary,
           "e_tilt": e_tilt, "e_impact": e_imp, "t_e": ev}
    t_e = ev[4.0]
    if is_crash and t_e is not None:
        es, sp = topic(u, "estimator_status"), topic(u, "vehicle_rates_setpoint")
        leakf, fb = {}, {}
        for mg in MARGINS:
            b = t_e - mg * 1e6
            if b - t0 < 10e6:
                continue
            f = window_features(u, st, True if rotary is None else rotary, t0, b)
            leakf[mg] = {k: (None if f[k] is None or np.isnan(f[k]) else float(f[k])) for k in fa.FEATURES}
            if mg in (0, 10):
                g = dict(f)
                if np.isnan(g["vib_p95"]) and es is not None and "vibe[1]" in es:
                    mm = between(es, t0, b)
                    if mm.any():
                        g["vib_p95"] = float(np.percentile(es["vibe[1]"][mm], 95))
                if np.isnan(g["tune_rms"]) and sp is not None and att is not None and "roll" in sp and "rollspeed" in att:
                    mm = between(att, t0, b)
                    if mm.sum() > 20:
                        ts = att["timestamp"][mm]
                        err = [np.interp(ts, sp["timestamp"], sp[k]) - att[a2][mm] for k, a2 in (("roll", "rollspeed"), ("pitch", "pitchspeed"))]
                        g["tune_rms"] = float(np.sqrt(np.mean(np.square(err))))
                fb[mg] = {k: (None if g[k] is None or (isinstance(g[k], float) and np.isnan(g[k])) else float(g[k])) for k in fa.FEATURES}
        out["leak_features"], out["fallback_features"] = leakf, fb
    return out


# ---------------------------------------------------------------- A

def mantel_haenszel(strata):
    """strata: list of (a, b, c, d) with a = aircraft&tilt, b = aircraft&no tilt, c = pilot&tilt, d = pilot&no tilt."""
    R = S = P_R = PS_QR = Q_S = 0.0
    num = var = 0.0
    for a, b, c, d in strata:
        n = a + b + c + d
        if n < 2 or (a + b) == 0 or (c + d) == 0:
            continue
        r, s = a * d / n, b * c / n
        p, q = (a + d) / n, (b + c) / n
        R += r; S += s; P_R += p * r; PS_QR += p * s + q * r; Q_S += q * s
        m1, n1, t1 = a + b, a + c, n
        e = m1 * n1 / t1
        v = m1 * (c + d) * n1 * (b + d) / (t1 ** 2 * (t1 - 1))
        num += a - e; var += v
    or_ = R / S
    se = math.sqrt(P_R / (2 * R ** 2) + PS_QR / (2 * R * S) + Q_S / (2 * S ** 2))
    stat = num ** 2 / var
    return {"or": or_, "ci95": [or_ * math.exp(-1.96 * se), or_ * math.exp(1.96 * se)], "cmh_chi2": stat,
            "p": float(chi2.sf(stat, 1))}


def logistic(X, y, iters=50):
    w = np.zeros(X.shape[1])
    for _ in range(iters):
        p = 1 / (1 + np.exp(-X @ w))
        H = X.T @ (X * (p * (1 - p))[:, None]) + 1e-8 * np.eye(len(w))
        w += np.linalg.solve(H, X.T @ (y - p))
    cov = np.linalg.inv(H)
    return w, np.sqrt(np.diag(cov))


def binary_auc(score, y, seed):
    """AUC of a 0/1 score for y (1 = aircraft-rated), with bootstrap CI."""
    def auc(s, t):
        return fa.auc(t, s.astype(float))
    rng = np.random.default_rng(seed)
    vals = [auc(score[i], y[i]) for i in (rng.integers(0, len(y), len(y)) for _ in range(2000))]
    vals = [v for v in vals if not np.isnan(v)]
    return {"auc": auc(score, y), "ci95": [float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))], "n": int(len(y))}


def part_a(root, db, paths):
    ids = [i for i, x in db.items() if x.get("rating") in CRASH and "SITL" not in str(x.get("sys_hw")) and x.get("mav_type") in MULTI]
    status = crash_status(paths, ids)
    rows = []
    for i in ids:
        if status[i] == "unreadable":
            continue
        yr = int(str(db[i].get("log_date") or "0")[:4] or 0)
        band = "<=2019" if yr <= 2019 else ("2020-2022" if yr <= 2022 else ">=2023")
        rows.append({"id": i, "tilt": int(status[i] in ("confirmed", "tilt_unconfirmed")), "aircraft": int(db[i]["rating"] == "crash_sw_hw"),
                     "band": band, "type": db[i]["mav_type"]})
    strata = []
    for band, typ in product(("<=2019", "2020-2022", ">=2023"), MULTI):
        g = [r for r in rows if r["band"] == band and r["type"] == typ]
        a = sum(r["aircraft"] and r["tilt"] for r in g); b = sum(r["aircraft"] and not r["tilt"] for r in g)
        c = sum((not r["aircraft"]) and r["tilt"] for r in g); d = sum((not r["aircraft"]) and not r["tilt"] for r in g)
        strata.append((a, b, c, d))
    out = {"n": len(rows), "strata": {f"{band}|{typ}": s for (band, typ), s in zip(product(("<=2019", "2020-2022", ">=2023"), MULTI), strata)},
           "pilot_share_by_band": {b: [sum(1 for r in rows if r["band"] == b and not r["aircraft"]), sum(1 for r in rows if r["band"] == b)] for b in ("<=2019", "2020-2022", ">=2023")}}
    out["A1_mantel_haenszel"] = mantel_haenszel(strata)
    X = np.array([[1, 1 - r["aircraft"], r["band"] == "2020-2022", r["band"] == ">=2023", r["type"] == "Hexarotor", r["type"] == "Octorotor"] for r in rows], float)
    y = np.array([r["tilt"] for r in rows], float)
    w, se = logistic(X, y)
    out["A2_logistic_pilot_coef"] = {"coef": float(w[1]), "or_pilot_vs_aircraft": float(np.exp(w[1])),
                                     "ci95_or": [float(np.exp(w[1] - 1.96 * se[1])), float(np.exp(w[1] + 1.96 * se[1]))]}
    out["A3_archive"] = binary_auc(np.array([r["tilt"] for r in rows]), np.array([r["aircraft"] for r in rows]), 2050)
    leak = [r for r in jsonl("leak_curve_features.jsonl") if r["margin"] == 0 and r["group"] == "crash" and r["label"] in ("pilot", "drone")]
    st148 = crash_status(paths, [r["log"] for r in leak])
    out["A3_modelled"] = binary_auc(np.array([int(st148[r["log"]] in ("confirmed", "tilt_unconfirmed")) for r in leak]),
                                    np.array([int(r["label"] == "drone") for r in leak]), 2050)
    return out, st148


# ---------------------------------------------------------------- main

def main(root):
    db = load_db(root)
    paths = pca.ulg_paths(root)
    veh = lambda lid: db.get(lid, {}).get("vehicle_uuid") or lid
    rep = {"declared_in": "research/px4_log_study/r18_audit.py docstring"}
    rep["A"], st148 = part_a(root, db, paths)
    print("A done", flush=True)
    leak = jsonl("leak_curve_features.jsonl")
    crash148 = sorted({r["log"] for r in leak if r["group"] == "crash"})
    normals = sorted({r["log"] for r in leak if r["group"] == "normal"})
    within = pca.within_rows()
    c2 = sorted({r["crash_id"] for r in within})
    review = list(csv.DictReader(open(os.path.join(RESULTS_DIR, "crash_moment_review.csv"))))
    key = json.load(open(os.path.join(RESULTS_DIR, "crash_moment_blind_key.json")))["panel_to_log_id"]
    A = {r["log_id"]: r["reviewer_2"].strip().lower() for r in review}
    B = {key[str(int(r["panel"]))]: r["label"].strip().lower() for r in csv.DictReader(open(os.path.join(RESULTS_DIR, "crash_moment_review_blind.csv")))}
    info = {}
    for lid in sorted(set(crash148) | set(c2) | set(A)):
        try:
            info[lid] = analyse_log(paths[lid], True) if lid in paths else None
        except Exception:
            info[lid] = None
    ninfo = {}
    for lid in normals:
        try:
            ninfo[lid] = analyse_log(paths[lid], False) if lid in paths else None
        except Exception:
            ninfo[lid] = None
    print("parse done", flush=True)
    # B: validation
    B_out = {}
    for th in (3.0, 4.0, 6.0):
        res = {}
        for who, R in (("A", A), ("B", B)):
            pairs = [(int(info[l]["t_e"][th] is not None), CONTAINS[R[l]]) for l in R if info.get(l) and R[l] in CONTAINS]
            res[who] = {"n": len(pairs), "agreement": sum(a == b for a, b in pairs) / len(pairs), "kappa": kappa(pairs),
                        "kappa_ci95": kappa_ci(pairs, 2051)}
        res["normal_false_alarm"] = [sum(1 for l in normals if ninfo.get(l) and ninfo[l]["t_e"][th] is not None),
                                     sum(1 for l in normals if ninfo.get(l))]
        B_out[f"{th}g"] = res
    timing = {}
    for who, R in (("A", A), ("B", B)):
        t = {}
        for lab, test in (("too late", lambda d: d < -2e6), ("too early", lambda d: d > 2e6), ("correct", lambda d: abs(d) <= 2e6)):
            ls = [l for l in R if R[l] == lab and info.get(l) and info[l]["t_e"][4.0] is not None]
            t[lab] = [sum(test(info[l]["t_e"][4.0] - info[l]["t_c"]) for l in ls), len(ls),
                      sum(1 for l in R if R[l] == lab)]
        timing[who] = t
    B_out["timing_vs_old_tc"] = timing
    B_out["gate_passed"] = bool(all(B_out["4.0g"][w]["kappa"] is not None and B_out["4.0g"][w]["kappa"] >= 0.6 for w in ("A", "B")))
    rep["B"] = B_out
    print("B done", flush=True)
    # E: counts
    tilt148 = {l for l in crash148 if st148.get(l) in ("confirmed", "tilt_unconfirmed")}
    cat = lambda t: "multicopter" if t in MULTI else ("fixed-wing" if t == "Fixed Wing" else ("VTOL" if t and "VTOL" in t else "other"))
    rep["E"] = {"tilt_defined": len(tilt148), "n": len(crash148),
                "by_type": {c: [sum(1 for l in crash148 if cat(db.get(l, {}).get("mav_type")) == c and l in tilt148),
                                sum(1 for l in crash148 if cat(db.get(l, {}).get("mav_type")) == c)] for c in ("multicopter", "fixed-wing", "VTOL", "other")},
                "fallback_by_is_rotary": dict(Counter(str(info[l]["rotary"]) if info.get(l) else "unreadable" for l in crash148 if l not in tilt148))}
    # C1 leak curves
    det = {l for l in crash148 if info.get(l) and info[l]["t_e"][4.0] is not None}
    rep["C1_tilt_defined"] = grouped_leak(leak, veh, tilt148)
    rows_det = [r for r in leak if r["group"] == "normal"]
    for l in det:
        lab = next(r["label"] for r in leak if r["log"] == l)
        for mg, f in info[l].get("leak_features", {}).items():
            rows_det.append({"log": l, "group": "crash", "label": lab, "margin": int(mg), **{k: (np.nan if f[k] is None else f[k]) for k in fa.FEATURES}})
    rep["C1_detector"] = grouped_leak(rows_det, veh, det)
    rep["C1_detector_crashes"] = len(det)
    print("C1 done", flush=True)
    # C2 factorial window effect
    sets, vehicle, _ = fa.build_sets(db)
    cache = {}
    for line in open(os.path.join(RESULTS_DIR, "factorial_audit_features.jsonl")):
        r = json.loads(line)
        cache[(r["log_id"], r["is_crash"])] = r["windows"]
    within_status = crash_status(paths, c2)
    tilt_all = tilt148 | {l for l in c2 if within_status.get(l) in ("confirmed", "tilt_unconfirmed")}

    def window_effect(cache_, keepfn):
        cells = {}
        for c in ("C1", "C2"):
            crashes = {x for x in sets[c] if keepfn(x) and cache_.get((x, True)) and cache_[(x, True)].get("0_full") and cache_[(x, True)].get("10_full")}
            for n in ("N1", "N2"):
                for m in (0, 10):
                    cells[f"{c}|{n}|{m}"] = fa.run_cell(fa.cell_rows(sets, cache_, c, n, m, "full", {True: crashes, False: set(sets[n])}), vehicle, "group")
        cv = {vehicle[x] for c in ("C1", "C2") for x in sets[c]}
        nv = {vehicle[x] for n in ("N1", "N2") for x in sets[n]}
        old = fa.BOOT_SEED; fa.BOOT_SEED = 2053
        boot = fa.paired_bootstrap(cells, cv, nv)
        fa.BOOT_SEED = old
        keys = [(c, n) for c in ("C1", "C2") for n in ("N1", "N2")]
        d = float(np.mean([cells[f"{c}|{n}|0"]["auc"] - cells[f"{c}|{n}|10"]["auc"] for c, n in keys]))
        db_ = np.mean([boot[f"{c}|{n}|0"] - boot[f"{c}|{n}|10"] for c, n in keys], axis=0)
        return {"diff_m0_minus_m10": d, "ci95": fa.ci(db_), "crashes": {c: cells[f"{c}|N1|0"]["n_crash"] for c in ("C1", "C2")}}

    rep["C2_tilt_defined"] = window_effect(cache, lambda x: x in tilt_all)
    cache_det = dict(cache)
    for l in set(sets["C1"]) | set(sets["C2"]):
        i = info.get(l)
        if i and i.get("fallback_features") and 0 in i["fallback_features"] and 10 in i["fallback_features"]:
            w = dict(cache.get((l, True)) or {})
            w["0_full"], w["10_full"] = i["fallback_features"][0], i["fallback_features"][10]
            cache_det[(l, True)] = w
        else:
            cache_det[(l, True)] = None
    rep["C2_detector"] = window_effect(cache_det, lambda x: True)
    print("C2 done", flush=True)
    # C3 within-drone
    follows = {k for k, v in pca.ordering(root, within).items() if v == "follows"}
    wt = [r for r in within if r["crash_id"] in tilt_all]
    rep["C3_tilt_defined"] = {"crashes": len({r["crash_id"] for r in wt}), "rank": pca.part_a(wt, follows), "model": pca.part_b(wt, follows)}
    wd = []
    for r in within:
        i = info.get(r["crash_id"])
        if not i or not i.get("fallback_features") or 10 not in i["fallback_features"]:
            continue
        if r["role"] == "crash":
            f = dict(r["features"] or {}); f.update(i["fallback_features"][10])
            wd.append({**r, "features": f})
        else:
            wd.append(r)
    rep["C3_detector"] = {"crashes": len({r["crash_id"] for r in wd if r["role"] == "crash"}), "rank": pca.part_a(wd, follows), "model": pca.part_b(wd, follows)}
    print("C3 done", flush=True)
    # D: kappa intervals for the two reviewers
    pr = [(A[l] == "correct", B[l] == "correct") for l in A if A[l] != "can't tell" and B[l] != "can't tell"]
    pc = [(CONTAINS[A[l]], CONTAINS[B[l]]) for l in A if A[l] in CONTAINS and B[l] in CONTAINS]
    rep["D"] = {"moment_right": {"kappa": kappa(pr), "ci95": kappa_ci(pr, 2052), "n": len(pr)},
                "contains_crash": {"kappa": kappa(pc), "ci95": kappa_ci(pc, 2052), "n": len(pc)}}
    json.dump(rep, open(os.path.join(RESULTS_DIR, "r18_audit.json"), "w"), indent=1, default=float)
    open(os.path.join(RESULTS_DIR, "r18_audit.md"), "w").write(
        "# Round 18 audit\n\nDeclared in `research/px4_log_study/r18_audit.py`. Exploratory (dagger).\n\n```\n" + json.dumps(rep, indent=1, default=float) + "\n```\n")
    print(json.dumps(rep, indent=1, default=float)[:6000])


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "/Volumes/One Touch/AeroFleet_px4_data")
