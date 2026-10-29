"""Fault-injection positive control on real flights: RflyMAD (Le et al., IJRR 2025), real-flight subset.

PRE-DECLARED (committed and pushed before any RflyMAD log is scored). Status: exploratory (dagger), declared after the
twentieth internal round. Nothing from these logs has been scored; one motor-fault log was opened to find how the
injection is recorded (below), and one TestInfo workbook was read.

Engineering check before commit (not an analysis): score_one was run once on that same motor-fault log and only the
names of the filled fields were printed (no values), to confirm the pipeline runs (4 s per log).

WHY: the archive study cannot tell a tool that fails from labels that fail. RflyMAD's real flights have a KNOWN cause
(firmware-injected motor or sensor faults on three multicopters) and a KNOWN onset time, so they answer two questions
the archive cannot: (1) when the aircraft really is at fault, do the study's attribution tools say so? (2) how much
crash-vs-normal-style separation comes from flight differences that exist BEFORE the fault (confounding) rather than
from the fault itself?

DATA: Kaggle copy xianglile/rflymad, folders Real-Motor, Real-Sensors, Real-No_Fault, fetched by rflymad_fetch.py
(.ulg, TestInfo_*.xlsx, wind_data.csv). The Kaggle copy has 51 no-fault real flights, not the 84 the dataset page lists.
GROUND TRUTH FROM THE LOG: topic rfly_ctrl_lxl; field id is 1500 when no fault is active and the fault code during
injection (e.g. 123450, motor). Fault onset t_f = first sample with id not in {0, 1500}; fault end = next return to
1500 (or end of log). Found while declaring: a TestInfo workbook can describe a different case from the log in the same
folder (folder 419_1 holds the workbook of case 428), so TestInfo is not used; class comes from the top folder (motor /
sensor / no-fault) and onset from the log. A Real-Motor or Real-Sensors log with no fault code is reported and
excluded; a Real-No_Fault log WITH a fault code is reported and excluded.
Flight status = first token of the second path component (acce, circling, hover, velocity, waypoint, ...).
No-fault flights get a pseudo-onset: take-off + the median (t_f - take-off) of fault flights with the same flight
status (all fault flights if that status has none).
Take-off t0 and the armed period as factorial_audit.window_set (land detector; pilot_vs_drone.armed_period).

WINDOWS (from t0):  pre = [t0, t_f];  fault = [t0, t_f + 10 s];  whole = [t0, end of armed period].
A window shorter than 10 s is missing.

I1 Declared attribution rule (pilot_vs_drone.evidence, unchanged, on the whole log): share of verdict "drone" in motor-
   fault, sensor-fault and no-fault flights with Wilson intervals; balanced accuracy for fault (motor and sensor
   separately) vs no-fault, undecided counted wrong, bootstrap interval (2,000, seed 2090).
I2 FlightMD (flightmd_eval.score_log machinery, unchanged tool): "any critical finding" share and mean health score per
   class for each window; AUC of badness (100 - score) fault vs no-fault for pre, fault and whole, bootstrap intervals
   (seed 2091).
I3 The study's 11 leak-curve features (leak_curve.window_features) with L2 logistic regression (factorial_audit
   fit_predict), stratified 5-fold x seeds 42-46 (vehicle grouping is impossible: three airframes), fault (motor +
   sensor) vs no-fault, for pre, fault and whole windows; 200 refitting label permutations (seed 2092) for p; paired
   bootstrap interval (2,000 over flights, seed 2093) for fault - pre and whole - pre on the seed-averaged scores.
   Repeated for motor-only vs no-fault.
I4 Pre-fault separation within flight status: I3 pre-window AUC computed within each flight status with >= 5 flights
   per class, pooled by size-weighted mean.

WORDING RULES (fixed now):
  - "the study's tools recognise injected aircraft faults" only if I1 balanced accuracy (motor vs no-fault) >= 0.70;
    otherwise the paper says the declared rule misses most known aircraft faults, which limits what its archive
    failure can show.
  - "separation before the fault" (confounding) is reported as present if the I3 pre-window AUC has permutation
    p < 0.05; then the paper says a crash-vs-normal design can score above chance with no fault present.
  - the fault itself adds signal if I3 fault - pre >= 0.05 with a bootstrap interval excluding zero.
Limits stated in the output: three airframes, one operator, faults injected in firmware (efficiency loss, sensor
noise), most not ending in a crash; stratified rather than vehicle-grouped folds.

    PYTHONPATH=<FlightMD checkout> ~/.venvs/flightmd/bin/python research/px4_log_study/rflymad_eval.py score RFLYMAD_DIR
    PYTHONPATH=<FlightMD checkout> ~/.venvs/flightmd/bin/python research/px4_log_study/rflymad_eval.py analyze RFLYMAD_DIR
"""
import glob
import json
import os
import sys
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor

import numpy as np

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(SCRIPT_DIR)
import factorial_audit as fa

RESULTS_DIR = os.path.join(SCRIPT_DIR, "..", "results", "px4_log_study")
OUT = os.path.join(RESULTS_DIR, "rflymad_scores.jsonl")
CLASS = {"Real-Motor": "motor", "Real-Sensors": "sensor", "Real-No_Fault": "no_fault"}
WINDOWS = ("pre", "fault", "whole")
MIN_S = 10


def onset(u):
    d = next((x.data for x in u.data_list if x.name == "rfly_ctrl_lxl"), None)
    if d is None:
        return None, None, None
    ids = d["id"]
    on = np.where(~np.isin(ids, (0, 1500)))[0]
    if not len(on):
        return None, None, None
    i = on[0]
    after = np.where(np.isin(ids[i:], (0, 1500)))[0]
    end = d["timestamp"][i + after[0]] if len(after) else d["timestamp"][-1]
    return int(d["timestamp"][i]), int(end), int(ids[i])


def flightmd_window(topics, params, cut):
    from flightmd_core.analysers import (BatteryAnalyser, EKFAnalyser, GPSAnalyser, MotorAnalyser,
                                         OscillationAnalyser, ParameterAnalyser, VibrationAnalyser)
    from flightmd_core.services.score_calculator import ScoreCalculator
    tp = {k: (df if "timestamp" not in df.columns else df[df["timestamp"] <= cut].reset_index(drop=True))
          for k, df in topics.items()}
    res = []
    for A in (OscillationAnalyser, VibrationAnalyser, EKFAnalyser, BatteryAnalyser, GPSAnalyser, ParameterAnalyser,
              MotorAnalyser):
        a = A()
        if a.is_applicable(set(tp)):
            res.append(a.safe_analyse(tp, params))
    score, label, _ = ScoreCalculator().calculate(res)
    crit = any(str(getattr(f.severity, "value", f.severity)) == "critical" for r in res for f in r.findings)
    return {"score": float(score), "critical": int(crit)}


def score_one(path):
    from pyulog import ULog
    from flightmd_core.services.ulog_parser import ULogParser
    from leak_curve import TOPICS, window_features
    from pilot_vs_drone import armed_period, between, evidence, topic

    rel = path.split(os.sep + "rflymad" + os.sep, 1)[-1]
    parts = rel.split(os.sep)
    out = {"path": rel, "cls": CLASS.get(parts[0]), "status": parts[1].split("-")[0], "case": parts[2]}
    try:
        u = ULog(path)
        out["t_f"], out["t_f_end"], out["fault_id"] = onset(u)
        st = topic(u, "vehicle_status")
        per = armed_period(st)
        if per is None:
            out["error"] = "never armed"
            return out
        t_arm, t_end = per
        land = topic(u, "vehicle_land_detected")
        t0 = t_arm
        if land is not None:
            mm = between(land, t_arm, t_end) & (land["landed"] == 0)
            if mm.any():
                t0 = land["timestamp"][mm][0]
        out.update(t0=int(t0), t_end=int(t_end))
        v = evidence(u)
        out["rule"] = v[0]["verdict"] if isinstance(v, tuple) and isinstance(v[0], dict) else (v["verdict"] if isinstance(v, dict) else None)
        out["sys_autostart"] = u.initial_parameters.get("SYS_AUTOSTART")
        rotary = bool(st["is_rotary_wing"][-1]) if "is_rotary_wing" in st else True
        topics, params, _ = ULogParser().parse(path)
        # Features and FlightMD for the cut points known now; no-fault pseudo-onsets are added in analyze via "grid".
        out["feat"], out["fmd"] = {}, {}
        cuts = {"whole": t_end}
        if out["t_f"] is not None:
            cuts["pre"] = out["t_f"]
            cuts["fault"] = out["t_f"] + 10_000_000
        else:
            for s in range(10, 121):  # grid of candidate pseudo-onsets, seconds after take-off
                cuts[f"g{s}"] = t0 + s * 1_000_000
        for name, cut in cuts.items():
            cut = min(cut, t_end)
            if cut - t0 < MIN_S * 1_000_000:
                continue
            f = window_features(u, st, rotary, t0, cut)
            out["feat"][name] = {k: (None if f[k] is None or np.isnan(f[k]) else float(f[k])) for k in fa.FEATURES}
            if name in ("whole", "pre", "fault") or name.startswith("g"):
                out["fmd"][name] = flightmd_window(topics, params, cut)
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {str(e)[:120]}"
    return out


def score(root):
    paths = sorted(p for p in glob.glob(os.path.join(root, "Real-*", "**", "*.ulg"), recursive=True)
                   if not os.path.basename(p).startswith("._"))
    with open(OUT, "w") as f, ProcessPoolExecutor(6) as ex:
        for r in ex.map(score_one, paths, chunksize=2):
            f.write(json.dumps(r, default=float) + "\n")
    print(f"scored {len(paths)}")


# ---------------------------------------------------------------- analysis

def wilson(k, n, z=1.96):
    if not n:
        return [np.nan, np.nan]
    p, d = k / n, 1 + z * z / n
    c, h = (p + z * z / (2 * n)) / d, z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [float(c - h), float(c + h)]


def ba(y, v):
    y, v = np.asarray(y), np.asarray(v)
    return float((np.mean(v[y == 1] == 1) + np.mean(v[y == 0] == 0)) / 2)


def boot_ci(n, stat, seed, B=2000):
    rng = np.random.default_rng(seed)
    vals = [stat(rng.integers(0, n, n)) for _ in range(B)]
    vals = [x for x in vals if not np.isnan(x)]
    return [float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))]


def analyze(root):
    R = [json.loads(l) for l in open(OUT)]
    rep = {"declared_in": "research/px4_log_study/rflymad_eval.py docstring", "n_logs": len(R),
           "errors": Counter(r.get("error", "")[:50] for r in R if "error" in r)}
    excl = Counter()
    keep = []
    for r in R:
        if "error" in r or r["cls"] is None:
            excl["error"] += 1
        elif r["cls"] != "no_fault" and r["t_f"] is None:
            excl["fault folder, no fault code"] += 1
        elif r["cls"] == "no_fault" and r["t_f"] is not None:
            excl["no-fault folder with fault code"] += 1
        else:
            keep.append(r)
    rep["excluded"] = dict(excl)
    rep["n_by_class"] = dict(Counter(r["cls"] for r in keep))
    rep["fault_ids"] = dict(Counter(str(r["fault_id"]) for r in keep if r["fault_id"] is not None))
    rep["airframes_SYS_AUTOSTART"] = dict(Counter(str(r.get("sys_autostart")) for r in keep))
    # pseudo-onset for no-fault flights
    off = defaultdict(list)
    for r in keep:
        if r["t_f"] is not None:
            off[r["status"]].append((r["t_f"] - r["t0"]) / 1e6)
    allo = [x for v in off.values() for x in v]
    for r in keep:
        if r["t_f"] is None:
            s = int(round(np.median(off.get(r["status"]) or allo)))
            s = min(max(s, 10), 120)
            for w, g in (("pre", s), ("fault", min(s + 10, 120))):
                if f"g{g}" in r["feat"]:
                    r["feat"][w] = r["feat"][f"g{g}"]
                if f"g{g}" in r["fmd"]:
                    r["fmd"][w] = r["fmd"][f"g{g}"]
    rep["pseudo_onset_median_s"] = {k: float(np.median(v)) for k, v in off.items()}

    # I1
    i1 = {}
    for c in ("motor", "sensor", "no_fault"):
        rs = [r for r in keep if r["cls"] == c]
        k = sum(r["rule"] == "drone" for r in rs)
        i1[c] = {"n": len(rs), "drone": k, "share": k / len(rs) if rs else np.nan, "ci": wilson(k, len(rs)),
                 "verdicts": dict(Counter(str(r["rule"]) for r in rs))}
    for c in ("motor", "sensor"):
        rs = [r for r in keep if r["cls"] in (c, "no_fault")]
        y = np.array([1 if r["cls"] == c else 0 for r in rs])
        v = np.array([1 if r["rule"] == "drone" else (0 if r["rule"] == "pilot" else -1) for r in rs])
        i1[f"ba_{c}_vs_nofault"] = ba(y, v)
        i1[f"ba_{c}_ci"] = boot_ci(len(y), lambda b: ba(y[b], v[b]), 2090)
    rep["I1"] = i1

    # I2
    i2 = {}
    for w in WINDOWS:
        rs = [r for r in keep if w in r["fmd"]]
        y = np.array([0 if r["cls"] == "no_fault" else 1 for r in rs])
        s = np.array([100 - r["fmd"][w]["score"] for r in rs])
        i2[w] = {"n_fault": int(y.sum()), "n_nofault": int((y == 0).sum()),
                 "critical_share": {c: float(np.mean([r["fmd"][w]["critical"] for r in rs if r["cls"] == c])) for c in ("motor", "sensor", "no_fault") if any(r["cls"] == c for r in rs)},
                 "mean_score": {c: float(np.mean([r["fmd"][w]["score"] for r in rs if r["cls"] == c])) for c in ("motor", "sensor", "no_fault") if any(r["cls"] == c for r in rs)},
                 "auc_badness": fa.auc(y, s), "auc_ci": boot_ci(len(y), lambda b: fa.auc(y[b], s[b]), 2091)}
    rep["I2"] = i2

    # I3
    def model(classes, tag):
        rs = [r for r in keep if r["cls"] in classes + ("no_fault",) and all(w in r["feat"] for w in WINDOWS)]
        y = np.array([0 if r["cls"] == "no_fault" else 1 for r in rs])
        out, sc = {"n_fault": int(y.sum()), "n_nofault": int((y == 0).sum())}, {}
        for w in WINDOWS:
            X = np.array([[np.nan if r["feat"][w][f] is None else r["feat"][w][f] for f in fa.FEATURES] for r in rs], float)
            a, sd, s = fa.cv_scores(X, y, None, "strat")
            sc[w] = s
            rng = np.random.default_rng(2092)
            null = [fa.cv_scores(X, rng.permutation(y), None, "strat", seeds=(42,))[0] for _ in range(200)]
            out[w] = {"auc": a, "sd_repeats": sd, "perm_p": float((np.sum(np.array(null) >= a) + 1) / 201),
                      "null_sd": float(np.std(null))}
        for a_, b_ in (("fault", "pre"), ("whole", "pre")):
            out[f"{a_}_minus_{b_}"] = out[a_]["auc"] - out[b_]["auc"]
            out[f"{a_}_minus_{b_}_ci"] = boot_ci(len(y), lambda b: fa.auc(y[b], sc[a_][b]) - fa.auc(y[b], sc[b_][b]), 2093)
        if tag == "all":
            # I4 within flight status, pre window
            per = []
            for stt in sorted({r["status"] for r in rs}):
                idx = [i for i, r in enumerate(rs) if r["status"] == stt]
                yy = y[idx]
                if min(yy.sum(), (yy == 0).sum()) >= 5:
                    per.append((len(idx), fa.auc(yy, sc["pre"][idx]), stt))
            rep["I4_pre_within_status"] = {"strata": [{"status": s, "n": n, "auc": a} for n, a, s in per],
                                           "pooled": float(sum(n * a for n, a, _ in per) / sum(n for n, _, _ in per)) if per else None}
        return out

    rep["I3"] = {"fault_vs_nofault": model(("motor", "sensor"), "all"), "motor_vs_nofault": model(("motor",), "motor")}
    m = rep["I3"]["fault_vs_nofault"]
    rep["wording"] = {
        "tools_recognise_motor_faults": rep["I1"]["ba_motor_vs_nofault"] >= 0.70,
        "separation_before_fault": m["pre"]["perm_p"] < 0.05,
        "fault_adds_signal": m["fault_minus_pre"] >= 0.05 and m["fault_minus_pre_ci"][0] > 0}
    rep["limits"] = ("three airframes, one operator; firmware-injected efficiency loss and sensor noise, mostly not "
                     "ending in a crash; stratified, not vehicle-grouped, folds")
    json.dump(rep, open(os.path.join(RESULTS_DIR, "rflymad_eval.json"), "w"), indent=1, default=float)
    open(os.path.join(RESULTS_DIR, "rflymad_eval.md"), "w").write(
        "# RflyMAD fault-injection positive control\n\nDeclared in `research/px4_log_study/rflymad_eval.py`. "
        "Exploratory (dagger).\n\n```\n" + json.dumps(rep, indent=1, default=float) + "\n```\n")
    print(json.dumps(rep, indent=1, default=float))


if __name__ == "__main__":
    {"score": score, "analyze": analyze}[sys.argv[1]](sys.argv[2] if len(sys.argv) > 2 else "/Volumes/One Touch/AeroFleet_px4_data/external/rflymad")
