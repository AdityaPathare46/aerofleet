"""Round 14 audit: caliper lift without duration-linked features, and a real GPS-time ordering check.

PRE-DECLARED (committed and pushed before this script is run). Status: exploratory (dagger), declared after Peer
Review Round 14, not blind.

Prior knowledge, stated up front. Already seen: caliper 0.25 on 36 airframes gives Group-CV AUC 0.642 matched vs 0.532
unmatched as a 5-seed mean (lift +0.110, A1/A2 script) and 0.604 vs 0.479 for seed 42 alone (lift +0.125, Round 13
script). The paired cluster CI [+0.074, +0.238] was computed from a third set of folds (rng 2026). Univariate gains
under matching: clip_rate +0.068, tilt_p95 +0.037, volt_sag +0.031. The caliper 0.25 was declared beforehand as the
secondary caliper of protocol A2 (commit f152d07); it was then reported as the headline. The A1/A2 script shuffled
list(set(clusters)), whose order changes between Python runs, so its folds are not exactly reproducible; this script
sorts clusters first. Round 13's "GPS" check compared calendar dates only (dbinfo log_date), so a same-day flight
could never appear to follow its crash; it also counted all 66 rough-drone sets (44 same-day) rather than the 60
analysed sets (39 same-day). Nothing in Part B below has been looked at.

PART A: caliper lift with and without duration-linked features (Round 14 problem 2)
  Data: within_drone_features.jsonl (stored features, the pipeline the published numbers used) and
  feature_window_durations_372.json. Cohort: crashes with >= 1 earlier flight within |ln(d_crash / d_earlier)|
  <= 0.25 (the 36 airframes). Matched = crash + its caliper-matched earlier flights; unmatched = crash + all its
  earlier flights, on the same 36 airframes. Model and preprocessing as leak_curve (L2 logistic, lambda 1.0).
  Group-CV by crash_id, 5 folds, clusters sorted before shuffling.
  Feature sets: F11 = all 11 features; F8 = F11 without clip_rate, tilt_p95 and volt_sag.
  For each feature set:
    lift_5   = mean over seeds 42-46 of AUC(matched) - mean of AUC(unmatched)
    lift_42  = AUC(matched) - AUC(unmatched), seed 42 only
    paired cluster bootstrap CI (2,000 resamples of the 36 airframes, seed 2028) for each lift, computed from the
    out-of-fold scores of the same run (seed-averaged scores for lift_5, seed-42 scores for lift_42).
  Anchors / abort (run first): F11 5-seed matched 0.642 +- 0.03 and unmatched 0.532 +- 0.03; F11 seed 42 matched
  0.604 +- 0.03 and unmatched 0.479 +- 0.03; 36 airframes exactly. If any fails, stop and report.
  Decision, fixed now: the "masked precursors" reading keeps support only if F8 lift_5 >= 0.05 AND its CI excludes 0.
  Otherwise the paper states that the lift is carried by duration-linked or consequence-type features and is not
  evidence of masked precursors. Both lifts and all CIs are reported whatever the outcome.

PART B: GPS-time ordering of crash-day exposure flights (Round 14 problem 4, Round 13 item)
  Sets: the 60 analysed between-drone sets (sensitivity.between, as declared, vib_p95). A case exposure flight is
  "same-day" if its dbinfo log_date equals its crash log's log_date.
  Time: for every same-day exposure flight and its crash log, the first vehicle_gps_position (else sensor_gps)
  sample with time_utc_usec > 0 gives the log's UTC anchor; the log's UTC start = anchor UTC - (anchor timestamp -
  ULog start_timestamp). A flight PRECEDES its crash if its UTC start is earlier than the crash log's UTC start.
  Undeterminable if either log has no valid GPS UTC (counted, not dropped silently).
  Report: same-day sets and flights among the 60; precede / follow / undeterminable counts.
  Rule, fixed now: if any flight follows its crash, remove those flights and recompute the between-drone test
  (sensitivity.between with keep_case excluding them): mean scaled rank and exact one-sided p. Also recomputed
  dropping undeterminable same-day flights (descriptive). Paper text about the GPS check is replaced by these counts.

Outputs: research/results/px4_log_study/r14_audit.md and .json.

    python research/px4_log_study/r14_audit.py DATA_ROOT
"""
import gzip
import json
import math
import os
import sys
from collections import defaultdict

import numpy as np

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(SCRIPT_DIR)
from factorial_audit import auc, cv_scores  # same model, same CV code as the factorial audit

RESULTS_DIR = os.path.join(SCRIPT_DIR, "..", "results", "px4_log_study")
F11 = ["tune_rms", "tilt_p95", "vib_p95", "clip_rate", "sat_frac", "batt_min", "volt_sag", "gps_bad", "failsafe",
       "manual_frac", "stick_p95"]
F8 = [f for f in F11 if f not in ("clip_rate", "tilt_p95", "volt_sag")]
CALIPER, BOOT, BOOT_SEED = 0.25, 2000, 2028


def jsonl(name):
    return [json.loads(line) for line in open(os.path.join(RESULTS_DIR, name))]


# ---------------------------------------------------------------- Part A

def caliper_cohorts():
    dur = json.load(open(os.path.join(RESULTS_DIR, "feature_window_durations_372.json")))
    by_crash = defaultdict(list)
    for r in jsonl("within_drone_features.jsonl"):
        if r.get("features") is not None:
            by_crash[r["crash_id"]].append(r)
    ok = lambda d: d is not None and not np.isnan(d) and d > 0
    matched, unmatched = [], []
    for cid in sorted(by_crash):
        fl = by_crash[cid]
        crash = [f for f in fl if f["role"] == "crash"]
        earlier = [f for f in fl if f["role"] == "earlier"]
        if not crash or not earlier or not ok(dur.get(crash[0]["log_id"])):
            continue
        dc = dur[crash[0]["log_id"]]
        near = [f for f in earlier if ok(dur.get(f["log_id"])) and abs(math.log(dc / dur[f["log_id"]])) <= CALIPER]
        if near:
            matched += [crash[0]] + near
            unmatched += [crash[0]] + earlier
    return matched, unmatched


def arrays(rows, feats):
    X = np.array([[np.nan if r["features"].get(k) is None else r["features"][k] for k in feats] for r in rows], float)
    y = np.array([1 if r["role"] == "crash" else 0 for r in rows])
    return X, y, [r["crash_id"] for r in rows]


def paired_lift_ci(ym, sm, cm, yu, su, cu):
    rng = np.random.default_rng(BOOT_SEED)
    im, iu = defaultdict(list), defaultdict(list)
    for i, c in enumerate(cm):
        im[c].append(i)
    for i, c in enumerate(cu):
        iu[c].append(i)
    cids = np.array(sorted(im))
    d = []
    for _ in range(BOOT):
        draw = rng.choice(cids, len(cids), replace=True)
        a = [i for c in draw for i in im[c]]
        b = [i for c in draw for i in iu[c]]
        x = auc(ym[a], sm[a]) - auc(yu[b], su[b])
        if not np.isnan(x):
            d.append(x)
    return [float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5))]


def part_a():
    matched, unmatched = caliper_cohorts()
    n_air = len({r["crash_id"] for r in matched})
    out = {"airframes": n_air, "matched_flights": len(matched), "unmatched_flights": len(unmatched)}
    for name, feats in (("F11", F11), ("F8", F8)):
        Xm, ym, cm = arrays(matched, feats)
        Xu, yu, cu = arrays(unmatched, feats)
        m5, _, sm5 = cv_scores(Xm, ym, cm, "group")
        u5, _, su5 = cv_scores(Xu, yu, cu, "group")
        m42, _, sm42 = cv_scores(Xm, ym, cm, "group", seeds=(42,))
        u42, _, su42 = cv_scores(Xu, yu, cu, "group", seeds=(42,))
        out[name] = {"matched_5": m5, "unmatched_5": u5, "lift_5": m5 - u5, "ci_5": paired_lift_ci(ym, sm5, cm, yu, su5, cu),
                     "matched_42": m42, "unmatched_42": u42, "lift_42": m42 - u42,
                     "ci_42": paired_lift_ci(ym, sm42, cm, yu, su42, cu)}
        if name == "F11":
            a = out["F11"]
            checks = [n_air == 36, abs(a["matched_5"] - 0.642) <= 0.03, abs(a["unmatched_5"] - 0.532) <= 0.03,
                      abs(a["matched_42"] - 0.604) <= 0.03, abs(a["unmatched_42"] - 0.479) <= 0.03]
            out["anchors_pass"] = all(checks)
            if not out["anchors_pass"]:
                return out
    f8 = out["F8"]
    out["masking_supported"] = bool(f8["lift_5"] >= 0.05 and f8["ci_5"][0] > 0)
    return out


# ---------------------------------------------------------------- Part B

def utc_start(path):
    """UTC start of a log in microseconds, from the first GPS sample with a valid UTC time; None if unavailable."""
    from pyulog import ULog

    u = ULog(path, message_name_filter_list=["vehicle_gps_position", "sensor_gps"])
    for name in ("vehicle_gps_position", "sensor_gps"):
        ds = [d for d in u.data_list if d.name == name]
        if not ds or "time_utc_usec" not in ds[0].data:
            continue
        t, utc = ds[0].data["timestamp"], ds[0].data["time_utc_usec"]
        ok = np.where(utc > 0)[0]
        if len(ok):
            i = ok[0]
            return int(utc[i]) - (int(t[i]) - int(u.start_timestamp))
    return None


def part_b(root):
    import sensitivity

    raw = open(os.path.join(root, "dbinfo.json"), "rb").read()
    db = {x["log_id"]: x for x in json.loads(gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw)}
    paths = {}
    for d, _, files in os.walk(root):
        for f in files:
            if f.endswith(".ulg") and not f.startswith("._"):
                paths.setdefault(f[:-4], os.path.join(d, f))
    sets, role = sensitivity.load_between()
    base = sensitivity.between(sets, role)
    # The 60 analysed sets: those the declared test uses (a case value and >= 1 control value).
    analysed = []
    for sid in sets:
        one = {sid: sets[sid]}
        if sensitivity.between(one, role)[2] == 1:
            analysed.append(sid)
    same_day = []  # (set_id, exposure log_id)
    for sid in analysed:
        case = next(v for v in sets[sid] if role[(sid, v)] == "case")
        for r in sets[sid][case]:
            if db.get(r["log_id"], {}).get("log_date") == db.get(sid, {}).get("log_date"):
                same_day.append((sid, r["log_id"]))
    cache, status = {}, {}
    get = lambda lid: cache.setdefault(lid, utc_start(paths[lid]) if lid in paths else None)
    for sid, lid in same_day:
        a, b = get(lid), get(sid)
        status[lid] = "undeterminable" if a is None or b is None else ("precedes" if a < b else "follows")
    counts = {k: sum(v == k for v in status.values()) for k in ("precedes", "follows", "undeterminable")}
    follows = {k for k, v in status.items() if v == "follows"}
    undet = {k for k, v in status.items() if v == "undeterminable"}
    out = {"analysed_sets": len(analysed), "declared_test": base[:3],
           "same_day_sets": len({s for s, _ in same_day}), "same_day_flights": len(same_day), "counts": counts}
    if follows:
        out["without_following"] = sensitivity.between(sets, role, keep_case=lambda r: r["log_id"] not in follows)[:3]
    if undet or follows:
        out["without_following_or_undeterminable"] = sensitivity.between(
            sets, role, keep_case=lambda r: r["log_id"] not in follows | undet)[:3]
    return out


def main(root):
    rep = {"declared_in": "research/px4_log_study/r14_audit.py docstring", "A": part_a()}
    if rep["A"].get("anchors_pass"):
        rep["B"] = part_b(root)
    with open(os.path.join(RESULTS_DIR, "r14_audit.json"), "w") as f:
        json.dump(rep, f, indent=1, default=float)
    A = rep["A"]
    L = ["# Round 14 audit", "", "Declared in `research/px4_log_study/r14_audit.py` (docstring). Exploratory (dagger).", "",
         "## Part A: caliper lift (0.25) with and without clip_rate, tilt_p95, volt_sag", "",
         f"Airframes {A['airframes']}; matched flights {A['matched_flights']}; unmatched {A['unmatched_flights']}. "
         f"Anchors pass: {A.get('anchors_pass')}.", ""]
    if A.get("anchors_pass"):
        L += ["| Features | Matched (5 seeds) | Unmatched (5 seeds) | Lift | Paired 95% CI | Matched (seed 42) | Unmatched (seed 42) | Lift | Paired 95% CI |",
              "|---|---|---|---|---|---|---|---|---|"]
        for k in ("F11", "F8"):
            a = A[k]
            L.append(f"| {k} | {a['matched_5']:.3f} | {a['unmatched_5']:.3f} | {a['lift_5']:+.3f} | [{a['ci_5'][0]:+.3f}, {a['ci_5'][1]:+.3f}] | "
                     f"{a['matched_42']:.3f} | {a['unmatched_42']:.3f} | {a['lift_42']:+.3f} | [{a['ci_42'][0]:+.3f}, {a['ci_42'][1]:+.3f}] |")
        L += ["", f"Masking reading supported (F8 lift_5 >= 0.05 and CI excludes 0): **{A['masking_supported']}**", ""]
        B = rep["B"]
        L += ["## Part B: GPS-time ordering of crash-day exposure flights", "",
              f"Analysed sets: {B['analysed_sets']} (declared test: mean rank {B['declared_test'][0]:.3f}, p {B['declared_test'][1]:.4f}, n {B['declared_test'][2]}).",
              f"Same-day sets: {B['same_day_sets']}; same-day exposure flights: {B['same_day_flights']}; {B['counts']}."]
        for k in ("without_following", "without_following_or_undeterminable"):
            if k in B:
                L.append(f"{k}: mean rank {B[k][0]:.3f}, p {B[k][1]:.4f}, n {B[k][2]}.")
    open(os.path.join(RESULTS_DIR, "r14_audit.md"), "w").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "/Volumes/One Touch/AeroFleet_px4_data")
