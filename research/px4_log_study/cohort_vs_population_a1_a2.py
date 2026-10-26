"""Protocol A1 & A2 Analysis: Isolating Cohort Selection vs. Comparison Population Effects

Pre-declared in research/protocols/protocol_a1_a2_cohort_vs_population.md
(Commit 366aceb, amended in commit f152d07).
Status: Exploratory (†).

Tasks:
- Anchor 1 & Anchor 2 checks with Abort Rule.
- Permutation null check.
- A1: 67 multi-flight crashes vs. 134 independent other-aircraft normal flights (Task A matched).
- A1b: Era-matched variant (matched on vehicle type and firmware generation).
- A2: Feature-window duration-only AUC in 372 cohort, and within-drone caliper matching
      (|ln(dur_ratio)| <= 0.50 and <= 0.25) with matched vs. unmatched comparisons on same airframes.
"""
import sys
import os
import json
import gzip
import random
from collections import defaultdict, Counter
import numpy as np

# Ensure helper modules are importable
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(SCRIPT_DIR)
from pyulog import ULog
from pilot_vs_drone import armed_period, between, crash_time, topic

ROOT_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))
DATA_DIR = "/Volumes/One Touch/AeroFleet_px4_data"
RESULTS_DIR = os.path.join(ROOT_DIR, "research", "results", "px4_log_study")

FEATURES = [
    "tune_rms", "tilt_p95", "vib_p95", "clip_rate", "sat_frac",
    "batt_min", "volt_sag", "gps_bad", "failsafe", "manual_frac", "stick_p95"
]

def auc(y, s):
    y, s = np.asarray(y), np.asarray(s, float)
    ok = ~np.isnan(s)
    y, s = y[ok], s[ok]
    pos, neg = s[y == 1], s[y == 0]
    if len(pos) == 0 or len(neg) == 0:
        return np.nan
    ranks = np.argsort(np.argsort(np.concatenate([pos, neg]))) + 1.0
    allv = np.concatenate([pos, neg])
    for v in np.unique(allv):
        idx = allv == v
        ranks[idx] = ranks[idx].mean()
    return float((ranks[: len(pos)].sum() - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg)))

def fit_predict(Xtr, ytr, Xte, lam=1.0, iters=3000, lr=0.1):
    med = np.nanmedian(Xtr, axis=0)
    med = np.where(np.isnan(med), 0.0, med)
    Xtr = np.where(np.isnan(Xtr), med, Xtr)
    Xte = np.where(np.isnan(Xte), med, Xte)
    Xtr = np.nan_to_num(Xtr, nan=0.0, posinf=0.0, neginf=0.0)
    Xte = np.nan_to_num(Xte, nan=0.0, posinf=0.0, neginf=0.0)
    mu, sd = Xtr.mean(0), Xtr.std(0)
    sd[sd <= 1e-6] = 1.0
    Xtr = np.clip((Xtr - mu) / sd, -10, 10)
    Xte = np.clip((Xte - mu) / sd, -10, 10)
    w, b = np.zeros(Xtr.shape[1]), 0.0
    for _ in range(iters):
        z = np.clip(Xtr @ w + b, -25, 25)
        p = 1 / (1 + np.exp(-z))
        g = p - ytr
        w -= lr * (Xtr.T @ g / len(ytr) + lam * w / len(ytr))
        b -= lr * g.mean()
    return Xte @ w + b

def cv_evaluate(X, y, clusters, seeds=[42, 43, 44, 45, 46], k=5):
    unique_clusters = list(set(clusters))
    repeat_aucs = []
    all_scores = np.zeros((len(seeds), len(y)))
    for s_idx, s in enumerate(seeds):
        rng = np.random.default_rng(s)
        shuf = list(unique_clusters)
        rng.shuffle(shuf)
        c_to_f = {c: i % k for i, c in enumerate(shuf)}
        folds = np.array([c_to_f[c] for c in clusters])
        scores = np.zeros(len(y))
        for fold in range(k):
            te, tr = (folds == fold), (folds != fold)
            scores[te] = fit_predict(X[tr], y[tr], X[te])
        all_scores[s_idx] = scores
        repeat_aucs.append(auc(y, scores))
    mean_scores = np.mean(all_scores, axis=0)
    return float(np.mean(repeat_aucs)), float(np.std(repeat_aucs)), mean_scores

def two_stage_cluster_bootstrap(scores, y, clusters, n_resamples=2000, seed=42):
    rng = np.random.default_rng(seed)
    crash_clusters = np.array(list(set(clusters[y == 1])))
    normal_clusters = np.array(list(set(clusters[y == 0])))
    
    # Pre-index flights by cluster
    by_cluster = defaultdict(list)
    for idx, c in enumerate(clusters):
        by_cluster[c].append(idx)
        
    boot_aucs = []
    for _ in range(n_resamples):
        sampled_c = rng.choice(crash_clusters, size=len(crash_clusters), replace=True)
        sampled_n = rng.choice(normal_clusters, size=len(normal_clusters), replace=True)
        
        sample_indices = []
        for c in sampled_c:
            sample_indices.extend(by_cluster[c])
        for c in sampled_n:
            sample_indices.extend(by_cluster[c])
            
        sample_indices = np.array(sample_indices)
        sub_scores = scores[sample_indices]
        sub_y = y[sample_indices]
        
        score_auc = auc(sub_y, sub_scores)
        if not np.isnan(score_auc):
            boot_aucs.append(score_auc)
            
    ci_low = float(np.percentile(boot_aucs, 2.5))
    ci_high = float(np.percentile(boot_aucs, 97.5))
    return ci_low, ci_high, boot_aucs

def cluster_bootstrap_univariate(values, y, clusters, n_resamples=2000, seed=42):
    rng = np.random.default_rng(seed)
    crash_clusters = list(set(clusters[y == 1]))
    normal_clusters = list(set(clusters[y == 0]))
    
    by_cluster = defaultdict(list)
    for idx, c in enumerate(clusters):
        by_cluster[c].append(idx)
        
    boot_aucs = []
    for _ in range(n_resamples):
        sampled_c_clusters = rng.choice(crash_clusters, size=len(crash_clusters), replace=True)
        sampled_n_clusters = rng.choice(normal_clusters, size=len(normal_clusters), replace=True)
        
        sample_indices = []
        for c in sampled_c_clusters:
            sample_indices.extend(by_cluster[c])
        for c in sampled_n_clusters:
            sample_indices.extend(by_cluster[c])
            
        sample_indices = np.array(sample_indices)
        sub_v = values[sample_indices]
        sub_y = y[sample_indices]
        boot_aucs.append(auc(sub_y, sub_v))
        
    ci_low = float(np.percentile(boot_aucs, 2.5))
    ci_high = float(np.percentile(boot_aucs, 97.5))
    return ci_low, ci_high

def get_feature_window_duration(ulg_path, is_crash):
    u = ULog(ulg_path, message_name_filter_list=["vehicle_status", "vehicle_land_detected", "vehicle_attitude"])
    st = topic(u, "vehicle_status")
    if st is None:
        return np.nan
    per = armed_period(st)
    if per is None:
        return np.nan
    t_arm, t_end = per
    rotary = bool(st["is_rotary_wing"][-1]) if "is_rotary_wing" in st else True
    tc = crash_time(u, t_arm, t_end, rotary) if is_crash else t_end
    land = topic(u, "vehicle_land_detected")
    t0 = t_arm
    if land is not None:
        mm = between(land, t_arm, tc) & (land["landed"] == 0)
        if mm.any():
            t0 = land["timestamp"][mm][0]
    b = tc - 10 * 1e6
    return max(0.0, (b - t0) / 1e6)

def main():
    print("=" * 70)
    print("EXECUTING PRE-DECLARED PROTOCOL A1 & A2 (Amendment 1)")
    print("=" * 70)
    
    # ----------------------------------------------------
    # Load dbinfo and build ulg path map
    # ----------------------------------------------------
    raw = open(os.path.join(DATA_DIR, "dbinfo.json"), "rb").read()
    db_by_id = {x["log_id"]: x for x in json.loads(gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw)}
    
    all_ulgs = {}
    for root, dirs, files in os.walk(DATA_DIR):
        for f in files:
            if f.endswith(".ulg"):
                all_ulgs[f[:-4]] = os.path.join(root, f)

    # ----------------------------------------------------
    # Step 0: Check Anchor 1 (Step 0 Replication)
    # ----------------------------------------------------
    print("\n--- ANCHOR 1 CHECK (Step 0 Replication: 148 crash, 139 normal, m=0) ---")
    leak_rows = [json.loads(line) for line in open(os.path.join(RESULTS_DIR, "leak_curve_features.jsonl"))]
    m0_rows = [r for r in leak_rows if r["margin"] == 0]
    X_m0 = np.array([[r[f] for f in FEATURES] for r in m0_rows], dtype=float)
    y_m0 = np.array([1 if r["group"] == "crash" else 0 for r in m0_rows])
    clusters_m0 = np.array([r["log"] for r in m0_rows])
    
    a1_mean, a1_std, _ = cv_evaluate(X_m0, y_m0, clusters_m0, seeds=[0, 1, 2, 3, 4])
    print(f"Anchor 1 CV AUC: {a1_mean:.4f} +- {a1_std:.4f} (Target: 0.883 +- 0.03)")
    if abs(a1_mean - 0.883) > 0.03:
        print(f"ABORT: Anchor 1 deviates by {abs(a1_mean - 0.883):.4f} > 0.03")
        sys.exit(1)
    else:
        print("Anchor 1 check PASSED.")

    # ----------------------------------------------------
    # Step 0b: Check Anchor 2 (Step 6 Replication: 67 crash, 305 earlier)
    # ----------------------------------------------------
    print("\n--- ANCHOR 2 CHECK (Step 6 Replication: 67 drones, 372 flights) ---")
    w_rows = [json.loads(line) for line in open(os.path.join(RESULTS_DIR, "within_drone_features.jsonl"))]
    by_crash = defaultdict(list)
    for r in w_rows:
        if r.get("features") is not None:
            by_crash[r["crash_id"]].append(r)
            
    valid_67 = {cid: flist for cid, flist in by_crash.items() 
                if any(x["role"] == "crash" for x in flist) and any(x["role"] == "earlier" for x in flist)}
    
    cohort_flights = []
    for cid, flist in valid_67.items():
        for f in flist:
            cohort_flights.append({
                "crash_id": cid,
                "role": f["role"],
                "log_id": f["log_id"],
                "features": f["features"],
                "vehicle_uuid": f.get("vehicle_uuid") or cid
            })
            
    X_372 = np.array([[f["features"].get(k) if f["features"].get(k) is not None else np.nan for k in FEATURES] for f in cohort_flights], dtype=float)
    y_372 = np.array([1 if f["role"] == "crash" else 0 for f in cohort_flights])
    clusters_372 = np.array([f["crash_id"] for f in cohort_flights])
    
    a2_mean, a2_std, _ = cv_evaluate(X_372, y_372, clusters_372, seeds=[42, 43, 44, 45, 46])
    print(f"Anchor 2 Group-CV AUC: {a2_mean:.4f} +- {a2_std:.4f} (Target: 0.569 +- 0.03)")
    if abs(a2_mean - 0.569) > 0.03:
        print(f"ABORT: Anchor 2 deviates by {abs(a2_mean - 0.569):.4f} > 0.03")
        sys.exit(1)
    else:
        print("Anchor 2 check PASSED.")

    # ----------------------------------------------------
    # Control Check: Label Permutation
    # ----------------------------------------------------
    print("\n--- PERMUTATION CONTROL CHECK (10 draws) ---")
    p_aucs = []
    for s in range(10):
        rng_perm = np.random.default_rng(s)
        y_perm = rng_perm.permutation(y_372)
        pm, _, _ = cv_evaluate(X_372, y_perm, clusters_372, seeds=[42])
        p_aucs.append(pm)
    perm_mean = float(np.mean(p_aucs))
    perm_std = float(np.std(p_aucs))
    print(f"Permuted Labels Group-CV AUC: {perm_mean:.4f} +- {perm_std:.4f} (Target: 0.50 +- 0.05)")
    if abs(perm_mean - 0.50) > 0.05:
        print(f"ABORT: Permutation control deviates by {abs(perm_mean - 0.50):.4f} > 0.05")
        sys.exit(1)
    else:
        print("Permutation control check PASSED.")

    # ----------------------------------------------------
    # PROTOCOL A1: Cohort vs. Comparison Population
    # ----------------------------------------------------
    print("\n" + "=" * 70)
    print("RUNNING PROTOCOL A1: 67 Multi-flight Crashes vs. 134 Other-Aircraft Controls")
    print("=" * 70)
    
    the_67_uuids = set(f["vehicle_uuid"] for f in cohort_flights if f.get("vehicle_uuid"))
    crash_67_flights = [f for f in cohort_flights if f["role"] == "crash"]
    for c in crash_67_flights:
        db_entry = db_by_id.get(c["log_id"], {})
        c["mav_type"] = db_entry.get("mav_type", "Quadrotor")
        c["ver"] = db_entry.get("ver_sw_release", "")
    
    # Candidate clean control pool from rough_drone and leak_curve strictly excluding the_67_uuids
    candidate_controls = {}
    r_rows = [json.loads(line) for line in open(os.path.join(RESULTS_DIR, "rough_drone_features.jsonl"))]
    for r in r_rows:
        if r["role"] == "control" and r.get("features") is not None:
            lid = r["log_id"]
            vuuid = r.get("vehicle") or db_by_id.get(lid, {}).get("vehicle_uuid")
            if vuuid not in the_67_uuids and lid not in candidate_controls:
                db_entry = db_by_id.get(lid, {})
                candidate_controls[lid] = {
                    "log_id": lid, "vehicle_uuid": vuuid or lid,
                    "mav_type": db_entry.get("mav_type", "Quadrotor"),
                    "ver": db_entry.get("ver_sw_release", ""),
                    "features": r["features"]
                }
    for r in m0_rows:
        if r["group"] == "normal":
            lid = r["log"]
            vuuid = db_by_id.get(lid, {}).get("vehicle_uuid")
            if vuuid not in the_67_uuids and lid not in candidate_controls:
                db_entry = db_by_id.get(lid, {})
                candidate_controls[lid] = {
                    "log_id": lid, "vehicle_uuid": vuuid or lid,
                    "mav_type": db_entry.get("mav_type", "Quadrotor"),
                    "ver": db_entry.get("ver_sw_release", ""),
                    "features": {k: r.get(k) for k in FEATURES}
                }
    print(f"Clean candidate control flights available: {len(candidate_controls)}")
    
    # Matching 2:1 on mav_type (Task A matching)
    rng_match = random.Random(42)
    ctrl_pool_by_type = defaultdict(list)
    for c in candidate_controls.values():
        ctrl_pool_by_type[c["mav_type"]].append(c)
        
    type_counts = Counter(c["mav_type"] for c in crash_67_flights)
    matched_a1_controls = []
    for mtype, cnt in type_counts.items():
        want = cnt * 2
        available = ctrl_pool_by_type[mtype]
        if len(available) >= want:
            matched_a1_controls.extend(rng_match.sample(available, want))
        else:
            matched_a1_controls.extend(available)
            rem = want - len(available)
            matched_a1_controls.extend(rng_match.sample(ctrl_pool_by_type["Quadrotor"], rem))
            
    print(f"Selected {len(matched_a1_controls)} controls matching type distribution of 67 crashes.")
    
    # Build A1 dataset (201 flights)
    a1_flights = []
    for c in crash_67_flights:
        a1_flights.append({"cluster": c["vehicle_uuid"], "label": 1, "features": c["features"], "log_id": c["log_id"]})
    for c in matched_a1_controls:
        a1_flights.append({"cluster": c["vehicle_uuid"], "label": 0, "features": c["features"], "log_id": c["log_id"]})
        
    X_a1 = np.array([[f["features"].get(k) if f["features"].get(k) is not None else np.nan for k in FEATURES] for f in a1_flights], dtype=float)
    y_a1 = np.array([f["label"] for f in a1_flights])
    clusters_a1 = np.array([f["cluster"] for f in a1_flights])
    
    a1_auc_mean, a1_auc_std, a1_scores = cv_evaluate(X_a1, y_a1, clusters_a1, seeds=[42, 43, 44, 45, 46])
    print(f"A1 Model Group-CV AUC: {a1_auc_mean:.4f} +- {a1_auc_std:.4f}")
    
    print("Computing 2,000 two-stage cluster bootstrap resamples...")
    a1_ci_low, a1_ci_high, a1_boot = two_stage_cluster_bootstrap(a1_scores, y_a1, clusters_a1, n_resamples=2000, seed=42)
    print(f"A1 95% Two-Stage Cluster Bootstrap CI: [{a1_ci_low:.3f}, {a1_ci_high:.3f}]")
    
    # Decision interpretation
    print("\n--- PRE-DECLARED DECISION RULE EVALUATION (A1) ---")
    if a1_ci_low >= 0.75:
        a1_verdict = "Comparison Population Effect Supported (CI lower bound >= 0.75)"
    elif a1_ci_high <= 0.65:
        a1_verdict = "Cohort Selection Effect Supported (CI upper bound <= 0.65)"
    else:
        a1_verdict = f"Statistically Inconclusive / Mixed ([{a1_ci_low:.3f}, {a1_ci_high:.3f}] spans decision boundary)"
    print(f"Outcome: {a1_verdict}")

    # ----------------------------------------------------
    # PROTOCOL A1b: Era-Matched Variant
    # ----------------------------------------------------
    print("\n" + "=" * 70)
    print("RUNNING PROTOCOL A1b: Era-Matched Variant (Vehicle Type + Firmware Era)")
    print("=" * 70)
    
    def get_era(v):
        try:
            rel = (v or "").split(" ")[0].lstrip("v")
            major, minor = [int(p) for p in rel.split(".")[:2]]
            return "modern" if (major, minor) >= (1, 12) else "older"
        except Exception:
            return "older"
            
    ctrl_pool_by_type_era = defaultdict(list)
    for c in candidate_controls.values():
        c_era = get_era(c["ver"])
        ctrl_pool_by_type_era[(c["mav_type"], c_era)].append(c)
        
    matched_a1b_controls = []
    for c in crash_67_flights:
        c_era = get_era(c["ver"])
        want = 2
        pool = ctrl_pool_by_type_era.get((c["mav_type"], c_era), [])
        if len(pool) >= want:
            matched_a1b_controls.extend(rng_match.sample(pool, want))
        else:
            fallback = ctrl_pool_by_type.get(c["mav_type"], ctrl_pool_by_type["Quadrotor"])
            matched_a1b_controls.extend(rng_match.sample(fallback, want))
            
    a1b_flights = []
    for c in crash_67_flights:
        a1b_flights.append({"cluster": c["vehicle_uuid"], "label": 1, "features": c["features"], "log_id": c["log_id"]})
    for c in matched_a1b_controls:
        a1b_flights.append({"cluster": c["vehicle_uuid"], "label": 0, "features": c["features"], "log_id": c["log_id"]})
        
    X_a1b = np.array([[f["features"].get(k) if f["features"].get(k) is not None else np.nan for k in FEATURES] for f in a1b_flights], dtype=float)
    y_a1b = np.array([f["label"] for f in a1b_flights])
    clusters_a1b = np.array([f["cluster"] for f in a1b_flights])
    
    a1b_auc_mean, a1b_auc_std, a1b_scores = cv_evaluate(X_a1b, y_a1b, clusters_a1b, seeds=[42, 43, 44, 45, 46])
    a1b_ci_low, a1b_ci_high, _ = two_stage_cluster_bootstrap(a1b_scores, y_a1b, clusters_a1b, n_resamples=2000, seed=42)
    print(f"A1b (Era-Matched) Model Group-CV AUC: {a1b_auc_mean:.4f} +- {a1b_auc_std:.4f} [95% CI: {a1b_ci_low:.3f}, {a1b_ci_high:.3f}]")

    # ----------------------------------------------------
    # PROTOCOL A2: Feature-Window Duration Confounding & Caliper Matching
    # ----------------------------------------------------
    print("\n" + "=" * 70)
    print("RUNNING PROTOCOL A2: Feature-Window Duration and Caliper Matching")
    print("=" * 70)
    
    dur_cache_file = os.path.join(RESULTS_DIR, "feature_window_durations_372.json")
    if os.path.exists(dur_cache_file):
        print("Loading cached feature-window durations...")
        with open(dur_cache_file) as f:
            dur_by_log = json.load(f)
        durations = []
        for f in cohort_flights:
            d = dur_by_log.get(f["log_id"], np.nan)
            f["duration_window"] = d
            durations.append(d)
    else:
        print("Extracting feature-window duration for 372 flights...")
        durations = []
        for f in cohort_flights:
            ulg_p = all_ulgs[f["log_id"]]
            is_c = (f["role"] == "crash")
            d = get_feature_window_duration(ulg_p, is_c)
            f["duration_window"] = d
            durations.append(d)
        dur_by_log = {f["log_id"]: f["duration_window"] for f in cohort_flights}
        with open(dur_cache_file, "w") as f:
            json.dump(dur_by_log, f, indent=2)
            
    durations = np.array(durations)
    dur_auc = auc(y_372, durations)
    dur_ci_low, dur_ci_high = cluster_bootstrap_univariate(durations, y_372, clusters_372, n_resamples=2000, seed=42)
    print(f"Feature-window duration-only AUC on 372 cohort: {dur_auc:.4f} [95% cluster bootstrap CI: {dur_ci_low:.3f}, {dur_ci_high:.3f}]")
        
    def evaluate_caliper(caliper_threshold):
        matched_cohort = []
        matched_crashes = 0
        dropped_crashes = 0
        retained_drones = []
        
        for cid, flist in valid_67.items():
            c_flight = [x for x in flist if x["role"] == "crash"][0]
            c_dur = dur_by_log.get(c_flight["log_id"], np.nan)
            if np.isnan(c_dur) or c_dur <= 0:
                dropped_crashes += 1
                continue
            e_flights = [x for x in flist if x["role"] == "earlier"]
            valid_earlier = []
            for e in e_flights:
                e_dur = dur_by_log.get(e["log_id"], np.nan)
                if not np.isnan(e_dur) and e_dur > 0:
                    diff = abs(np.log(e_dur) - np.log(c_dur))
                    if diff <= caliper_threshold:
                        valid_earlier.append(e)
            if valid_earlier:
                matched_cohort.append(c_flight)
                matched_cohort.extend(valid_earlier)
                matched_crashes += 1
                retained_drones.append(cid)
            else:
                dropped_crashes += 1
                
        # Unmatched comparison on same retained drones
        unmatched_same_drones = []
        for cid in retained_drones:
            unmatched_same_drones.extend(valid_67[cid])
            
        return matched_cohort, unmatched_same_drones, matched_crashes, dropped_crashes

    for cal_val, cal_label in [(0.50, "Primary Caliper <= 0.50"), (0.25, "Secondary Tighter Caliper <= 0.25")]:
        print(f"\n--- Caliper Matching: {cal_label} ---")
        m_cohort, u_cohort, n_matched_c, n_dropped_c = evaluate_caliper(cal_val)
        print(f"Retained crashes: {n_matched_c} / 67 (Dropped: {n_dropped_c}); Total matched flights: {len(m_cohort)}")
        
        # Evaluate matched subset
        X_m = np.array([[f["features"].get(k) if f["features"].get(k) is not None else np.nan for k in FEATURES] for f in m_cohort], dtype=float)
        y_m = np.array([1 if f["role"] == "crash" else 0 for f in m_cohort])
        c_m = np.array([f["crash_id"] for f in m_cohort])
        m_auc, m_std, _ = cv_evaluate(X_m, y_m, c_m, seeds=[42, 43, 44, 45, 46])
        
        # Evaluate unmatched subset on exact same drones
        X_u = np.array([[f["features"].get(k) if f["features"].get(k) is not None else np.nan for k in FEATURES] for f in u_cohort], dtype=float)
        y_u = np.array([1 if f["role"] == "crash" else 0 for f in u_cohort])
        c_u = np.array([f["crash_id"] for f in u_cohort])
        u_auc, u_std, _ = cv_evaluate(X_u, y_u, c_u, seeds=[42, 43, 44, 45, 46])
        
        print(f"Duration-Matched Within-Drone Group-CV AUC: {m_auc:.4f} +- {m_std:.4f}")
        print(f"Unmatched (Same {n_matched_c} Drones) Group-CV AUC: {u_auc:.4f} +- {u_std:.4f}")
        print(f"Delta (Matched - Unmatched): {m_auc - u_auc:+.4f}")

    # ----------------------------------------------------
    # Save Results Summary
    # ----------------------------------------------------
    results_summary = {
        "anchor_1": {"mean": a1_mean, "std": a1_std, "passed": True},
        "anchor_2": {"mean": a2_mean, "std": a2_std, "passed": True},
        "permutation_control": {"mean": perm_mean, "passed": True},
        "a1_cross_aircraft": {
            "mean_auc": a1_auc_mean,
            "std_auc": a1_auc_std,
            "ci_95": [a1_ci_low, a1_ci_high],
            "verdict": a1_verdict
        },
        "a1b_era_matched": {
            "mean_auc": a1b_auc_mean,
            "std_auc": a1b_auc_std,
            "ci_95": [a1b_ci_low, a1b_ci_high]
        },
        "a2_duration_only": {
            "auc": dur_auc,
            "ci_95": [dur_ci_low, dur_ci_high]
        }
    }
    
    out_json = os.path.join(RESULTS_DIR, "cohort_vs_population_a1_a2.json")
    with open(out_json, "w") as f:
        json.dump(results_summary, f, indent=2)
    print(f"\nSaved structured results to: {out_json}")

if __name__ == "__main__":
    main()
