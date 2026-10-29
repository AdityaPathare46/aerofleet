"""Round 19 audit: aircraft types in the tilt-defined analyses, the tilt/stick check, the label link within
multicopter strata, intervals for the rule proxy, and a multi-cue crash-event detector.

PRE-DECLARED (committed and pushed before this script is run). Status: exploratory (dagger), declared after the
nineteenth internal review, not blind: every earlier result named below is known. In particular the tilt-defined
subgroup was examined after the confirmed-crash result; the paper will say so.

Found while writing this declaration (code read, nothing scored): the "rule balanced accuracy across cuts" in the paper
(0.460 -> 0.350, round13_audit_execution R13-5) is not the declared rule. It is a proxy on stored leak-curve features
(aircraft if clip_rate > 0, sat_frac > 0, failsafe > 0, gps_bad > 0 or batt_min < 10; pilot if manual_frac > 0.5 and no
aircraft sign; otherwise undecided, counted as wrong). Part B3 reports it as a proxy, with intervals.

COMMON: L2 logistic (factorial_audit.fit_predict); tie-corrected AUC; grouped folds by vehicle, clusters sorted, seeds
42-46; aircraft type from the archive index: multicopter = Quadrotor/Hexarotor/Octorotor, fixed-wing = Fixed Wing,
VTOL = any type containing "VTOL". Crash status as r16_audit.crash_status.

PART A - Aircraft types and the tilt-defined window analyses (review problems 1-2)
  A1 Counts by aircraft type x status (confirmed / tilt_unconfirmed / fallback) for the 148 modelled crashes, the 50
     reviewed logs (and the reviewers' "correct" counts per type), and the factorial crash sets.
  A2 Grouped leak curve, constant cohort (logs with a window at every m), crash vs all normal flights, for: all
     crashes; tilt-defined; tilt-defined multicopters; confirmed; confirmed multicopters - each with all 11 features
     and with tilt_p95 and stick_p95 removed. For each: n crash / n normal, AUC at m = 0 and 10 s, and the drop
     AUC(0) - AUC(10) with a 95% paired cluster-bootstrap interval (2,000 resamples of vehicles, seed 2060, on the
     seed-averaged out-of-fold scores at both cut-offs).
  A3 Factorial window effect (as r16_audit A2: C1, C2 vs N1, N2, full window, m = 0 vs 10, grouped, paired cluster
     bootstrap seed 2061) for tilt-defined multicopters, with all features and without tilt_p95 and stick_p95; n per
     crash set reported.
  A4 Both 0.014 figures restated to four decimals with their definitions (factorial Shapley share for the window
     factor on the 32-cell constant subset; mean of four m = 0 vs 10 differences over all crashes).
  Wording rules (fixed now): the abstract keeps "material" only if A3's multicopter, all-feature effect is >= 0.05
  with an interval excluding zero; if the effect without tilt and stick features fails that rule, the paper states
  that the tilt-defined effect is carried by the tilt and stick features, which cutting the window removes by
  construction.

PART B - Label link within multicopters, and the rule proxy (review problems 3, 6)
  B1 AUC of "tilt event present" for aircraft- vs pilot-rated crashes among the modelled multicopter crashes, with a
     bootstrap interval (2,000, seed 2062).
  B2 Task B logistic regression (leak_curve scheme: stratified 5-fold x seeds 0-4, mean AUC, m = 0) within tilt-defined
     multicopter crashes and within tilt-absent multicopter crashes; 200 refitting label permutations (seed 2063) for
     p and approximate bounds; n and number of pilot-rated crashes reported.
  B3 The rule proxy of R13-5 at m in {0, 5, 10, 20, 30}: balanced accuracy over all crashes (undecided counted wrong)
     and over decided crashes only, recall per class, share undecided, with bootstrap intervals (2,000, seed 2064).

PART C - Multi-cue crash-event detector (review problem 4)
  Cues after the airborne start t0 and up to the end of the armed period:
    tilt     first tilt > 60 deg;
    descent  first vehicle_local_position vz > 5 m/s (downwards) that is followed within 3 s by a landed or
             ground-contact flag or the end of the armed period;
    in_air   the vehicle is disarmed (a later vehicle_status sample is not armed) while the land detector's last
             state before the disarm is airborne (in-air disarm or motor cut-off): event time = the disarm;
             a log that simply ends while armed does not count. (Corrected before commit after a smoke test on two
             logs, one of them a reviewed log, showed the first version firing on recordings that end mid-air.)
    impact   |accelerometer| > 6 g within the 2 s before a landed or ground-contact flag or the end of the armed period.
  Event time t_e = earliest cue; no event if none. Validation as r18_audit B: event vs each reviewer's "contains
  crash" (kappa with bootstrap CI, seed 2065) and the false-alarm share on the 139 normal flights.
  GATE (fixed now): kappa >= 0.6 against BOTH reviewers AND false alarms <= 10%. Only if the gate passes: grouped leak
  curve (A2 scheme, with drop interval) on detector-defined multicopter crashes and the within-drone rank tests with the
  crash flight cut at t_e - 10 s. Otherwise the detector is reported as failing and nothing is rerun with it.

Outputs: research/results/px4_log_study/r19_audit.md and .json.

    python research/px4_log_study/r19_audit.py DATA_ROOT
"""
import csv
import gzip
import json
import os
import sys
from collections import Counter, defaultdict

import numpy as np

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(SCRIPT_DIR)
import factorial_audit as fa
import postcrash_audit as pca
import r18_audit as r18
from r16_audit import crash_status

RESULTS_DIR = os.path.join(SCRIPT_DIR, "..", "results", "px4_log_study")
MULTI = ("Quadrotor", "Hexarotor", "Octorotor")
MARGINS = (0, 2, 5, 10, 20, 30)
NO_TS = [f for f in fa.FEATURES if f not in ("tilt_p95", "stick_p95")]
G = 9.80665


def jsonl(name):
    return [json.loads(l) for l in open(os.path.join(RESULTS_DIR, name))]


def ptype(t):
    if t in MULTI:
        return "multicopter"
    if t == "Fixed Wing":
        return "fixed-wing"
    if t and "VTOL" in t:
        return "VTOL"
    return "other"


def boot_ci(vals):
    vals = [v for v in vals if not np.isnan(v)]
    return [float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))]


# ---------------------------------------------------------------- A2: leak curve with drop interval

def leak_with_drop(rows, veh, keep_crash, feats, seed=2060):
    present = defaultdict(set)
    for r in rows:
        if r["group"] == "normal" or r["log"] in keep_crash:
            present[r["log"]].add(r["margin"])
    cohort = sorted(l for l, ms in present.items() if set(MARGINS) <= ms)
    res, scores = {}, {}
    for m in (0, 10):
        by = {r["log"]: r for r in rows if r["margin"] == m and r["log"] in cohort}
        R = [by[l] for l in cohort]
        X = np.array([[np.nan if r[f] is None else r[f] for f in feats] for r in R], float)
        y = np.array([1 if r["group"] == "crash" else 0 for r in R])
        cl = [veh(r["log"]) for r in R]
        a, _, s = fa.cv_scores(X, y, cl, "group")
        res[m], scores[m] = a, s
    y = np.array([1 if r["group"] == "crash" else 0 for r in [next(x for x in rows if x["log"] == l and x["margin"] == 0) for l in cohort]])
    cl = [veh(l) for l in cohort]
    idx = defaultdict(list)
    for i, c in enumerate(cl):
        idx[c].append(i)
    cids = np.array(sorted(idx))
    rng = np.random.default_rng(seed)
    d = []
    for _ in range(2000):
        pick = [i for c in rng.choice(cids, len(cids)) for i in idx[c]]
        d.append(fa.auc(y[pick], scores[0][pick]) - fa.auc(y[pick], scores[10][pick]))
    return {"n_crash": int(y.sum()), "n_normal": int((y == 0).sum()), "auc_m0": res[0], "auc_m10": res[10],
            "drop": res[0] - res[10], "drop_ci95": boot_ci(d)}


# ---------------------------------------------------------------- C: multi-cue detector

def detect2(path):
    from pyulog import ULog
    from pilot_vs_drone import armed_period, between, topic

    u = ULog(path, message_name_filter_list=["vehicle_status", "vehicle_land_detected", "vehicle_attitude",
                                             "vehicle_local_position", "sensor_combined"])
    st = topic(u, "vehicle_status")
    per = armed_period(st) if st is not None else None
    if per is None:
        return None
    t_arm, t_end = per
    land = topic(u, "vehicle_land_detected")
    t0 = t_arm
    ground_ts = np.array([], dtype=np.int64)
    if land is not None:
        mm = between(land, t_arm, t_end) & (land["landed"] == 0)
        if mm.any():
            t0 = land["timestamp"][mm][0]
        flag = land["landed"].astype(bool)
        if "ground_contact" in land:
            flag = flag | land["ground_contact"].astype(bool)
        g = between(land, t0, t_end) & flag
        ground_ts = land["timestamp"][g].astype(np.int64)
    stops = np.concatenate([ground_ts, np.array([int(t_end)], dtype=np.int64)])
    cues = {}
    att = topic(u, "vehicle_attitude")
    if att is not None:
        m = between(att, t0, t_end)
        q1, q2 = att["q[1]"][m], att["q[2]"][m]
        tilt = np.degrees(np.arccos(np.clip(1 - 2 * (q1 ** 2 + q2 ** 2), -1, 1)))
        over = np.where(tilt > 60)[0]
        if len(over):
            cues["tilt"] = int(att["timestamp"][m][over[0]])
    lp = topic(u, "vehicle_local_position")
    if lp is not None and "vz" in lp:
        m = between(lp, t0, t_end)
        for t in lp["timestamp"][m][lp["vz"][m] > 5.0].astype(np.int64):
            if ((stops >= t) & (stops <= t + 3_000_000)).any():
                cues["descent"] = int(t)
                break
    disarmed_after = bool(((st["timestamp"] > t_end) & (st["arming_state"] != 2)).any())
    if land is not None and disarmed_after:
        before = land["timestamp"] <= t_end
        if before.any() and int(land["landed"][before][-1]) == 0 and t_end > t0:
            cues["in_air"] = int(t_end)
    sc = topic(u, "sensor_combined")
    if sc is not None and "accelerometer_m_s2[0]" in sc:
        m = between(sc, t0, t_end)
        a = np.sqrt(sum(sc[f"accelerometer_m_s2[{i}]"][m].astype(float) ** 2 for i in range(3)))
        for t in sc["timestamp"][m][a > 6 * G].astype(np.int64):
            if ((stops >= t) & (stops <= t + 2_000_000)).any():
                cues["impact"] = int(t)
                break
    t_e = min(cues.values()) if cues else None
    return {"t0": int(t0), "t_end": int(t_end), "cues": cues, "t_e": t_e}


# ---------------------------------------------------------------- main

def main(root):
    raw = open(os.path.join(root, "dbinfo.json"), "rb").read()
    db = {x["log_id"]: x for x in json.loads(gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw)}
    paths = pca.ulg_paths(root)
    veh = lambda lid: db.get(lid, {}).get("vehicle_uuid") or lid
    typ = lambda lid: ptype(db.get(lid, {}).get("mav_type"))
    rep = {"declared_in": "research/px4_log_study/r19_audit.py docstring"}
    leak = jsonl("leak_curve_features.jsonl")
    crash148 = sorted({r["log"] for r in leak if r["group"] == "crash"})
    within = pca.within_rows()
    c2 = sorted({r["crash_id"] for r in within})
    status = crash_status(paths, sorted(set(crash148) | set(c2)))
    tilt = lambda l: status.get(l) in ("confirmed", "tilt_unconfirmed")
    # A1
    review = list(csv.DictReader(open(os.path.join(RESULTS_DIR, "crash_moment_review.csv"))))
    key = json.load(open(os.path.join(RESULTS_DIR, "crash_moment_blind_key.json")))["panel_to_log_id"]
    RA = {r["log_id"]: r["reviewer_2"].strip().lower() for r in review}
    RB = {key[str(int(r["panel"]))]: r["label"].strip().lower() for r in csv.DictReader(open(os.path.join(RESULTS_DIR, "crash_moment_review_blind.csv")))}
    a1 = {"modelled": defaultdict(Counter), "reviewed": defaultdict(Counter)}
    for l in crash148:
        a1["modelled"][typ(l)][status[l]] += 1
    rev_status = crash_status(paths, sorted(RA))
    for l in RA:
        t, s = typ(l), rev_status[l]
        a1["reviewed"][t][s] += 1
        a1["reviewed"][t][f"{s}|A_correct"] += RA[l] == "correct"
        a1["reviewed"][t][f"{s}|B_correct"] += RB[l] == "correct"
    rep["A1"] = {k: {t: dict(c) for t, c in v.items()} for k, v in a1.items()}
    # A2
    subsets = {"all": set(crash148), "tilt": {l for l in crash148 if tilt(l)},
               "tilt_multicopter": {l for l in crash148 if tilt(l) and typ(l) == "multicopter"},
               "confirmed": {l for l in crash148 if status[l] == "confirmed"},
               "confirmed_multicopter": {l for l in crash148 if status[l] == "confirmed" and typ(l) == "multicopter"}}
    rep["A2"] = {}
    for name, keep in subsets.items():
        for fname, feats in (("all_features", fa.FEATURES), ("no_tilt_stick", NO_TS)):
            try:
                rep["A2"][f"{name}|{fname}"] = leak_with_drop(leak, veh, keep, feats)
            except Exception as e:
                rep["A2"][f"{name}|{fname}"] = f"not run: {e}"
        print("A2", name, flush=True)
    # A3
    sets, vehicle, _ = fa.build_sets(db)
    cache = {}
    for line in open(os.path.join(RESULTS_DIR, "factorial_audit_features.jsonl")):
        r = json.loads(line)
        cache[(r["log_id"], r["is_crash"])] = r["windows"]
    keepfn = lambda x: tilt(x) and typ(x) == "multicopter"
    rep["A1"]["factorial_tilt_multicopter_crashes"] = {c: sum(1 for x in sets[c] if keepfn(x)) for c in ("C1", "C2")}

    def window_effect(feats):
        fi = [fa.FEATURES.index(f) for f in feats]
        cells = {}
        for c in ("C1", "C2"):
            crashes = {x for x in sets[c] if keepfn(x) and cache.get((x, True)) and cache[(x, True)].get("0_full") and cache[(x, True)].get("10_full")}
            for n in ("N1", "N2"):
                for m in (0, 10):
                    rows = fa.cell_rows(sets, cache, c, n, m, "full", {True: crashes, False: set(sets[n])})
                    rows = [(lid, lab, [f[i] for i in fi]) for lid, lab, f in rows]
                    cells[f"{c}|{n}|{m}"] = fa.run_cell(rows, vehicle, "group")
        cv = {vehicle[x] for c in ("C1", "C2") for x in sets[c]}
        nv = {vehicle[x] for n in ("N1", "N2") for x in sets[n]}
        old = fa.BOOT_SEED; fa.BOOT_SEED = 2061
        boot = fa.paired_bootstrap(cells, cv, nv)
        fa.BOOT_SEED = old
        keys = [(c, n) for c in ("C1", "C2") for n in ("N1", "N2")]
        d = float(np.mean([cells[f"{c}|{n}|0"]["auc"] - cells[f"{c}|{n}|10"]["auc"] for c, n in keys]))
        db_ = np.mean([boot[f"{c}|{n}|0"] - boot[f"{c}|{n}|10"] for c, n in keys], axis=0)
        return {"diff_m0_minus_m10": d, "ci95": fa.ci(db_), "n_crash": {c: cells[f"{c}|N1|0"]["n_crash"] for c in ("C1", "C2")}}

    rep["A3"] = {"all_features": window_effect(fa.FEATURES), "no_tilt_stick": window_effect(NO_TS)}
    a3 = rep["A3"]["all_features"]
    rep["A3"]["abstract_keeps_material"] = bool(a3["diff_m0_minus_m10"] >= 0.05 and a3["ci95"][0] > 0)
    nt = rep["A3"]["no_tilt_stick"]
    rep["A3"]["carried_by_tilt_stick"] = bool(not (nt["diff_m0_minus_m10"] >= 0.05 and nt["ci95"][0] > 0))
    fj = json.load(open(os.path.join(RESULTS_DIR, "factorial_audit.json")))
    r16 = json.load(open(os.path.join(RESULTS_DIR, "r16_audit_A.json")))["A"]
    rep["A4"] = {"shapley_window_share": fj["stage2"]["shapley"]["m"], "mean_four_cell_difference_all": r16["A2_all"]}
    print("A done", flush=True)
    # B1, B2
    mc = [r for r in leak if r["margin"] == 0 and r["group"] == "crash" and r["label"] in ("pilot", "drone") and typ(r["log"]) == "multicopter"]
    rep["B1"] = r18.binary_auc(np.array([int(tilt(r["log"])) for r in mc]), np.array([int(r["label"] == "drone") for r in mc]), 2062)
    rng = np.random.default_rng(2063)
    rep["B2"] = {}
    for name, sel in (("tilt_multicopter", [r for r in mc if tilt(r["log"])]), ("no_tilt_multicopter", [r for r in mc if not tilt(r["log"])])):
        X = np.array([[r[f] for f in fa.FEATURES] for r in sel], float)
        y = np.array([1 if r["label"] == "drone" else 0 for r in sel])
        if (y == 0).sum() < 5:
            rep["B2"][name] = {"n": len(y), "n_pilot": int((y == 0).sum()), "note": "fewer than 5 pilot-rated crashes; not fitted"}
            continue
        import r15_audit as r15
        obs, _ = r15.cv_auc(X, y, "logistic")
        null = np.array([r15.cv_auc(X, rng.permutation(y), "logistic")[0] for _ in range(200)])
        rep["B2"][name] = {"n": len(y), "n_pilot": int((y == 0).sum()), "auc": obs, "null_sd": float(null.std()),
                           "p": float((np.sum(null >= obs) + 1) / 201), "approx_bounds": [obs - 1.96 * null.std(), obs + 1.96 * null.std()]}
    # B3 rule proxy
    rng = np.random.default_rng(2064)
    rep["B3"] = {}
    for m in (0, 5, 10, 20, 30):
        R = [r for r in leak if r["margin"] == m and r["group"] == "crash" and r.get("label") in ("pilot", "drone")]
        pred = []
        for r in R:
            sign = ((r.get("clip_rate") or 0) > 0 or (r.get("sat_frac") or 0) > 0 or (r.get("failsafe") or 0) > 0
                    or (r.get("gps_bad") or 0) > 0 or (r.get("batt_min") is not None and r["batt_min"] < 10))
            manual = r.get("manual_frac") is not None and r["manual_frac"] > 0.5
            pred.append("drone" if sign else ("pilot" if manual else "unknown"))
        lab = [r["label"] for r in R]

        def ba(idx, decided_only=False):
            rec = []
            for c in ("drone", "pilot"):
                ii = [i for i in idx if lab[i] == c and (not decided_only or pred[i] != "unknown")]
                if not ii:
                    return np.nan
                rec.append(np.mean([pred[i] == c for i in ii]))
            return float(np.mean(rec))

        allidx = list(range(len(R)))
        boots = [ba(list(rng.integers(0, len(R), len(R)))) for _ in range(2000)]
        bootd = [ba(list(rng.integers(0, len(R), len(R))), True) for _ in range(2000)]
        rep["B3"][m] = {"n": len(R), "ba_all": ba(allidx), "ci_all": boot_ci(boots), "ba_decided": ba(allidx, True), "ci_decided": boot_ci(bootd),
                        "undecided_share": float(np.mean([p == "unknown" for p in pred])),
                        "recall_aircraft": float(np.mean([pred[i] == "drone" for i in allidx if lab[i] == "drone"])),
                        "recall_pilot": float(np.mean([pred[i] == "pilot" for i in allidx if lab[i] == "pilot"])),
                        "aircraft_sign_share": float(np.mean([p == "drone" for p in pred]))}
    print("B done", flush=True)
    # C detector
    normals = sorted({r["log"] for r in leak if r["group"] == "normal"})
    det = {}
    for l in sorted(set(RA) | set(normals) | set(crash148)):
        try:
            det[l] = detect2(paths[l]) if l in paths else None
        except Exception:
            det[l] = None
    has = lambda l: det.get(l) is not None and det[l]["t_e"] is not None
    C = {}
    for who, R in (("A", RA), ("B", RB)):
        pairs = [(int(has(l)), r18.CONTAINS[R[l]]) for l in R if det.get(l) and R[l] in r18.CONTAINS]
        C[who] = {"n": len(pairs), "agreement": sum(a == b for a, b in pairs) / len(pairs), "kappa": r18.kappa(pairs), "kappa_ci95": r18.kappa_ci(pairs, 2065)}
    fa_n = [sum(1 for l in normals if det.get(l) and has(l)), sum(1 for l in normals if det.get(l))]
    C["normal_false_alarm"] = fa_n
    C["cue_counts_normals"] = dict(Counter(k for l in normals if has(l) for k in det[l]["cues"]))
    C["cue_counts_crashes"] = dict(Counter(k for l in crash148 if has(l) for k in det[l]["cues"]))
    C["gate_passed"] = bool(all(C[w]["kappa"] is not None and C[w]["kappa"] >= 0.6 for w in ("A", "B")) and fa_n[0] / fa_n[1] <= 0.10)
    rep["C"] = C
    if C["gate_passed"]:
        rows = [r for r in leak if r["group"] == "normal"]
        keep = set()
        for l in crash148:
            if not has(l) or typ(l) != "multicopter":
                continue
            # recompute leak-style features at the multi-cue event
            from pyulog import ULog
            from leak_curve import TOPICS, window_features
            from pilot_vs_drone import armed_period, topic
            u = ULog(paths[l], message_name_filter_list=list(TOPICS))
            st = topic(u, "vehicle_status")
            t0, te = det[l]["t0"], det[l]["t_e"]
            lab = next(r["label"] for r in leak if r["log"] == l)
            for mg in MARGINS:
                b = te - mg * 1e6
                if b - t0 < 10e6:
                    continue
                f = window_features(u, st, True, t0, b)
                rows.append({"log": l, "group": "crash", "label": lab, "margin": mg, **{k: f[k] for k in fa.FEATURES}})
            keep.add(l)
        rep["C_rerun_leak"] = leak_with_drop(rows, veh, keep, fa.FEATURES)
    json.dump(rep, open(os.path.join(RESULTS_DIR, "r19_audit.json"), "w"), indent=1, default=float)
    open(os.path.join(RESULTS_DIR, "r19_audit.md"), "w").write(
        "# Round 19 audit\n\nDeclared in `research/px4_log_study/r19_audit.py`. Exploratory (dagger).\n\n```\n" + json.dumps(rep, indent=1, default=float) + "\n```\n")
    print("done", flush=True)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "/Volumes/One Touch/AeroFleet_px4_data")
