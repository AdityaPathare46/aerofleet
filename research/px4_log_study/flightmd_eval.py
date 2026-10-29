"""Re-evaluation of a published log-diagnostic tool, FlightMD, under this study's protocol.

PRE-DECLARED (committed and pushed before this script is run). Status: exploratory (dagger), declared after the
twentieth internal round, not blind: every earlier result of this study is known; no FlightMD score of any study log
has been seen.

THE TOOL: FlightMD (github.com/Praddyx15/FlightMD, MIT licence, commit 306d0cb, cloned 29 Oct 2026). A deterministic
rule-based PX4 log health checker; its author reports validating it on 50 PX4 Flight Review logs. It is not
peer-reviewed; the paper will say so. Seven weighted modules (oscillation 20, vibration 20, EKF 20, battery 15, GPS 15,
parameters 5, motors 5) give findings of severity critical / warning / info; the tool's ScoreCalculator turns them into a
0-100 health score (labels: >= 90 Excellent, >= 75 Good, >= 60 Caution, >= 40 Warning, else Critical).
We call its ULogParser, the seven analysers and ScoreCalculator directly, with the code unchanged. We do NOT call
run_analysis, because it sends the log's GPS position to external weather and reverse-geocoding services and has an
optional language-model step; neither affects the score. The ascent-profile module is outside the score and is not run.
Engineering check before this declaration (not an analysis): the pipeline was run once on one normal control log to
confirm that it parses and scores (0.2 s per log); that log's score is not used to set anything below.

WINDOWS: per log, t_arm and t_end from pilot_vs_drone.armed_period; take-off t0 and crash moment t_c exactly as
factorial_audit.window_set (t_c = first tilt > 60 deg for crash logs unless the log's rotary flag says fixed-wing, else
t_end; normal and earlier flights t_c = t_end). Every topic's rows are kept from the start of the log to the cut:
  whole  the entire log, as a user of the tool would submit it (includes anything after the crash);
  m0     cut at t_c;
  m10    cut at t_c - 10 s.
A window is missing if t0 to the cut is shorter than 10 s (as the main study). Score = 100 - health score ("badness").

SAMPLES (fixed by the main study): the 148 modelled crash logs and 139 normal flights of leak_curve_features.jsonl; the
constant cohort is the r19_audit A2 cohort (logs present at every margin: 89 crashes, 124 normals). Vehicle = index
vehicle_uuid. Within-drone: within_drone_features.jsonl crash and earlier flights, earlier flights flown after the
crash by GPS time removed (postcrash_audit.ordering, "follows").

F1 Crash vs normal on the constant cohort: AUC of badness at whole, m0 and m10, each with a 95% vehicle-cluster
   bootstrap interval (2,000 resamples, seed 2070), and the paired drops whole - m0 and m0 - m10 with intervals.
   Repeated on the 24 tilt-defined multicopter crashes (post hoc subgroup of the main study) against the same normals.
   Also, per window: share of crashes and of normals with health score < 60 (Warning or Critical label).
   Wording rules: the tool "separates crashes from normal flights before the crash window" only if the m10 AUC interval
   lies above 0.5; crash-window leakage is "material" for the tool if m0 - m10 >= 0.05 with an interval excluding
   zero; post-crash data "inflate" the whole-log score if whole - m0 >= 0.05 with an interval excluding zero.
F2 Pilot or aircraft, on all modelled crashes with a window: verdict "aircraft" if the tool reports any critical
   finding, else "pilot". Balanced accuracy against the uploader label at whole, m0 and m10 with bootstrap intervals
   (2,000 over crashes, seed 2071), pass mark 0.70 (the main study's declared mark). AUC of badness for aircraft- vs
   pilot-rated crashes with interval.
F3 Within the same drone: rank of the crash flight's badness (m10, and m0 as secondary) among that drone's own earlier
   flights (whole earlier flight to t_end), drones with >= 3 earlier flights, within_drone.rank_test (seed 0). Within-
   drone warning only if p < 0.025 (as postcrash_audit).
F4 False alarms: on the 139 normal flights (whole log), the distribution of labels and the share scored < 60; the most
   frequent critical and warning finding titles on normal flights (top 10).
F5 Which modules move: per module, mean module score in crashes vs normals at m0 and m10.

Logs that fail to parse are counted and reported, not dropped silently. Outputs:
research/results/px4_log_study/flightmd_eval.md, .json, and flightmd_scores.jsonl (per log and window).

Runs in its own environment (Python 3.12; FlightMD needs >= 3.11), without FlightMD's AI packages:
    PYTHONPATH=<FlightMD checkout> ~/.venvs/flightmd/bin/python research/px4_log_study/flightmd_eval.py score DATA_ROOT
    PYTHONPATH=<FlightMD checkout> ~/.venvs/flightmd/bin/python research/px4_log_study/flightmd_eval.py analyze DATA_ROOT
"""
import gzip
import json
import os
import sys
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor

import numpy as np

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(SCRIPT_DIR)
import postcrash_audit as pca
from within_drone import rank_test

RESULTS_DIR = os.path.join(SCRIPT_DIR, "..", "results", "px4_log_study")
SCORES = os.path.join(RESULTS_DIR, "flightmd_scores.jsonl")
MARGINS = (0, 2, 5, 10, 20, 30)
WINDOWS = ("whole", "m0", "m10")
MULTI = ("Quadrotor", "Hexarotor", "Octorotor")
MIN_WINDOW_S = 10


def jsonl(name):
    return [json.loads(l) for l in open(os.path.join(RESULTS_DIR, name))]


def times(path, is_crash):
    from pyulog import ULog
    from pilot_vs_drone import armed_period, between, crash_time, topic

    u = ULog(path, message_name_filter_list=["vehicle_status", "vehicle_land_detected", "vehicle_attitude"])
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
    return int(t0), int(t_c)


def score_log(job):
    """job = (log_id, path, is_crash). Returns {log, windows: {w: {score, label, modules, findings} | None}}."""
    from flightmd_core.analysers import (BatteryAnalyser, EKFAnalyser, GPSAnalyser, MotorAnalyser,
                                         OscillationAnalyser, ParameterAnalyser, VibrationAnalyser)
    from flightmd_core.services.score_calculator import ScoreCalculator
    from flightmd_core.services.ulog_parser import ULogParser

    lid, path, is_crash = job
    out = {"log": lid, "is_crash": is_crash, "windows": {}}
    try:
        tt = times(path, is_crash)
        topics, params, _ = ULogParser().parse(path)
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"
        return out
    if tt is None:
        out["error"] = "no armed period"
        return out
    t0, t_c = tt
    for w in WINDOWS:
        if w == "whole":
            cut = None
        else:
            cut = t_c - (0 if w == "m0" else 10) * 1_000_000
            if cut - t0 < MIN_WINDOW_S * 1_000_000:
                out["windows"][w] = None
                continue
        tp = {k: (df if cut is None or "timestamp" not in df.columns else df[df["timestamp"] <= cut].reset_index(drop=True))
              for k, df in topics.items()}
        res = []
        for A in (OscillationAnalyser, VibrationAnalyser, EKFAnalyser, BatteryAnalyser, GPSAnalyser, ParameterAnalyser,
                  MotorAnalyser):
            a = A()
            if a.is_applicable(set(tp)):
                res.append(a.safe_analyse(tp, params))
        score, label, _ = ScoreCalculator().calculate(res)
        out["windows"][w] = {
            "score": float(score), "label": label,
            "modules": {r.analyser: (None if r.skipped else r.health_score) for r in res},
            "findings": [[r.analyser, str(getattr(f.severity, "value", f.severity)), f.title] for r in res for f in r.findings]}
    return out


def score(root):
    paths = pca.ulg_paths(root)
    leak = jsonl("leak_curve_features.jsonl")
    jobs = {}
    for r in leak:
        jobs[r["log"]] = r["group"] == "crash"
    for r in pca.within_rows():
        jobs.setdefault(r["log_id"], r["role"] == "crash")
    todo = [(l, paths.get(l), c) for l, c in sorted(jobs.items())]
    missing = [l for l, p, _ in todo if p is None]
    with open(SCORES, "w") as f, ProcessPoolExecutor(6) as ex:
        for res in ex.map(score_log, [j for j in todo if j[1] is not None], chunksize=4):
            f.write(json.dumps(res) + "\n")
    print(f"scored {len(todo) - len(missing)}; missing file {len(missing)}")


# ---------------------------------------------------------------- analysis

def auc(y, s):
    y, s = np.asarray(y), np.asarray(s, float)
    pos, neg = s[y == 1], s[y == 0]
    if len(pos) == 0 or len(neg) == 0:
        return np.nan
    return float(((pos[:, None] > neg[None, :]).sum() + 0.5 * (pos[:, None] == neg[None, :]).sum()) / (len(pos) * len(neg)))


def ci(vals):
    vals = [v for v in vals if not np.isnan(v)]
    return [float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))]


def cluster_boot(n_items, clusters, stat, seed, B=2000):
    idx = defaultdict(list)
    for i, c in enumerate(clusters):
        idx[c].append(i)
    cids = np.array(sorted(idx))
    rng = np.random.default_rng(seed)
    return [stat([i for c in rng.choice(cids, len(cids)) for i in idx[c]]) for _ in range(B)]


def balanced_accuracy(y, v):
    y, v = np.asarray(y), np.asarray(v)
    r = [np.mean(v[y == k] == k) for k in (0, 1) if (y == k).any()]
    return float(np.mean(r)) if len(r) == 2 else np.nan


def analyze(root):
    raw = open(os.path.join(root, "dbinfo.json"), "rb").read()
    db = {x["log_id"]: x for x in json.loads(gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw)}
    veh = lambda l: db.get(l, {}).get("vehicle_uuid") or l
    S = {r["log"]: r for r in (json.loads(l) for l in open(SCORES))}
    leak = jsonl("leak_curve_features.jsonl")
    group = {r["log"]: r["group"] for r in leak}
    label = {r["log"]: r["label"] for r in leak if r["group"] == "crash"}
    present = defaultdict(set)
    for r in leak:
        present[r["log"]].add(r["margin"])
    cohort = sorted(l for l, ms in present.items() if set(MARGINS) <= ms)
    sc = lambda l, w: (S.get(l, {}).get("windows", {}).get(w) or {}).get("score")
    bad = lambda l, w: None if sc(l, w) is None else 100.0 - sc(l, w)
    rep = {"declared_in": "research/px4_log_study/flightmd_eval.py docstring", "tool": "FlightMD 306d0cb",
           "parse_errors": Counter(v.get("error", "")[:60] for v in S.values() if "error" in v),
           "n_scored": len(S)}

    from r16_audit import crash_status
    paths = pca.ulg_paths(root)
    crashes = sorted(l for l, g in group.items() if g == "crash")
    status = crash_status(paths, crashes)
    tilt_mc = {l for l in crashes if status.get(l) in ("confirmed", "tilt_unconfirmed") and db.get(l, {}).get("mav_type") in MULTI}

    # F1
    def f1(keep_crash, seed):
        logs = [l for l in cohort if (group[l] == "normal" or l in keep_crash) and all(bad(l, w) is not None for w in WINDOWS)]
        y = np.array([1 if group[l] == "crash" else 0 for l in logs])
        s = {w: np.array([bad(l, w) for l in logs]) for w in WINDOWS}
        cl = [veh(l) for l in logs]
        out = {"n_crash": int(y.sum()), "n_normal": int((y == 0).sum())}
        for w in WINDOWS:
            out[f"auc_{w}"] = auc(y, s[w])
            out[f"auc_{w}_ci"] = ci(cluster_boot(len(y), cl, lambda p: auc(y[p], s[w][p]), seed))
        for a, b in (("whole", "m0"), ("m0", "m10")):
            out[f"drop_{a}_{b}"] = out[f"auc_{a}"] - out[f"auc_{b}"]
            out[f"drop_{a}_{b}_ci"] = ci(cluster_boot(len(y), cl, lambda p: auc(y[p], s[a][p]) - auc(y[p], s[b][p]), seed + 100))
        for w in WINDOWS:
            out[f"share_below60_{w}"] = {"crash": float(np.mean(s[w][y == 1] > 40)), "normal": float(np.mean(s[w][y == 0] > 40))}
        return out

    rep["F1"] = {"all": f1(set(crashes), 2070), "tilt_multicopter": f1(tilt_mc, 2072)}
    a = rep["F1"]["all"]
    rep["F1"]["wording"] = {
        "separates_before_window": a["auc_m10_ci"][0] > 0.5,
        "window_leakage_material": a["drop_m0_m10"] >= 0.05 and a["drop_m0_m10_ci"][0] > 0,
        "postcrash_inflates": a["drop_whole_m0"] >= 0.05 and a["drop_whole_m0_ci"][0] > 0}

    # F2
    def crit(l, w):
        win = S.get(l, {}).get("windows", {}).get(w)
        return None if win is None else int(any(f[1] == "critical" for f in win["findings"]))

    rep["F2"] = {}
    for w in WINDOWS:
        logs = [l for l in crashes if crit(l, w) is not None]
        y = np.array([1 if label[l] == "drone" or label[l] == "aircraft" else 0 for l in logs])
        v = np.array([crit(l, w) for l in logs])
        s = np.array([bad(l, w) for l in logs])
        rng = np.random.default_rng(2071)
        boots = [rng.integers(0, len(y), len(y)) for _ in range(2000)]
        rep["F2"][w] = {"n": len(y), "n_pilot": int((y == 0).sum()), "ba": balanced_accuracy(y, v),
                        "ba_ci": ci([balanced_accuracy(y[b], v[b]) for b in boots]),
                        "recall_aircraft": float(np.mean(v[y == 1] == 1)), "recall_pilot": float(np.mean(v[y == 0] == 0)),
                        "auc_badness": auc(y, s), "auc_badness_ci": ci([auc(y[b], s[b]) for b in boots]),
                        "passes_0_70": balanced_accuracy(y, v) >= 0.70}

    # F3
    rows = pca.within_rows()
    order = pca.ordering(root, rows)
    follows = {k for k, v in order.items() if v == "follows"}
    by = defaultdict(list)
    for r in rows:
        by[r["crash_id"]].append(r)
    rep["F3"] = {}
    for w in ("m10", "m0"):
        groups = []
        for cid, fl in by.items():
            cb = bad(cid, w)
            ev = [bad(r["log_id"], "m0") for r in fl if r["role"] == "earlier" and r["log_id"] not in follows]
            groups.append((cb, [e for e in ev if e is not None]))
        n, mr, p, above = rank_test(groups, "flightmd", np.random.default_rng(0))
        rep["F3"][w] = {"n_drones": n, "mean_rank": mr, "p": p, "above_median": above, "warning": bool(p < 0.025)}

    # F4
    normals = [l for l, g in group.items() if g == "normal" and S.get(l, {}).get("windows", {}).get("whole")]
    labs = Counter(S[l]["windows"]["whole"]["label"] for l in normals)
    titles = Counter()
    for l in normals:
        for f in S[l]["windows"]["whole"]["findings"]:
            if f[1] in ("critical", "warning"):
                titles[f"{f[1]}: {f[2].split('(')[0].strip()}"] += 1
    rep["F4"] = {"n_normal": len(normals), "labels": dict(labs),
                 "share_below60": float(np.mean([S[l]["windows"]["whole"]["score"] < 60 for l in normals])),
                 "top_findings": titles.most_common(10)}

    # F5
    rep["F5"] = {}
    for w in ("m0", "m10"):
        mods = defaultdict(lambda: {"crash": [], "normal": []})
        for l in cohort:
            win = S.get(l, {}).get("windows", {}).get(w)
            if not win:
                continue
            for m, v in win["modules"].items():
                if v is not None:
                    mods[m][group[l]].append(v)
        rep["F5"][w] = {m: {g: (float(np.mean(v)) if v else None) for g, v in d.items()} for m, d in mods.items()}

    json.dump(rep, open(os.path.join(RESULTS_DIR, "flightmd_eval.json"), "w"), indent=1, default=float)
    open(os.path.join(RESULTS_DIR, "flightmd_eval.md"), "w").write(
        "# FlightMD re-evaluation\n\nDeclared in `research/px4_log_study/flightmd_eval.py`. Exploratory (dagger).\n\n```\n"
        + json.dumps(rep, indent=1, default=float) + "\n```\n")
    print(json.dumps(rep, indent=1, default=float))


if __name__ == "__main__":
    {"score": score, "analyze": analyze}[sys.argv[1]](sys.argv[2] if len(sys.argv) > 2 else "/Volumes/One Touch/AeroFleet_px4_data")
