"""The crash-window leak: how much of a log check's "accuracy" comes from the crash itself?

PRE-DECLARED (committed before this script was run on any log).

Logs: every full crash log already downloaded (first sample + held-out, 223) and the 149 full normal flights
(good/great). The crash moment t_c is pilot_vs_drone.crash_time (first tilt > 60 deg after take-off for rotary
wing, else the end of the armed period); for normal flights it is the end of the armed period.

For each cut-off margin m in MARGINS, features are computed only on the window from the first not-landed
moment to t_c - m. Windows shorter than 10 s are dropped for that margin.

Features (window-length normalised, so log length cannot decide):
  tune_rms     RMS of rate setpoint minus measured rate, roll and pitch (rad/s; rotary wing)
  tilt_p95     95th percentile of tilt (deg)
  vib_p95      95th percentile of accel_vibration_metric
  clip_rate    accelerometer clipping counts per second
  sat_frac     share of time any motor is at >= 95% (rotary wing)
  batt_min     lowest battery remaining (%)
  volt_sag     (start voltage - lowest voltage) / start voltage
  gps_bad      share of time with eph > 5 m or fewer than 6 satellites
  failsafe     1 if a failsafe was active at any time
  manual_frac  share of time in a pilot-flown mode (MANUAL, ALTCTL, POSCTL, ACRO, STABILIZED)
  stick_p95    95th percentile of the largest roll/pitch stick deflection
Missing values are filled with the training fold's median.

Tasks and models:
  A  crash vs normal flight            all crash logs vs all normal logs
  B  pilot vs drone (uploader label)   crash logs only
  Model: L2-regularised logistic regression (numpy, lambda = 1.0, standardised features), 5-fold stratified
  cross-validation repeated 5 times (seeds 0-4). Metric: ROC AUC, mean and standard deviation over the repeats.
  Also the AUC of each single feature on its own (no fitting), to show which features carry the effect.

Hypothesis H_leak: for task A, the mean AUC at m = 0 exceeds the mean AUC at m = 10 s by at least 0.10.
Reported whatever the outcome; task B and the per-feature AUCs are descriptive.

    python research/px4_log_study/leak_curve.py LOG_ROOT OUT_DIR
LOG_ROOT holds crash/, h/crash/ and h/normal/ (as downloaded by the earlier steps).
"""
import json
import os
import sys
from glob import glob

import numpy as np
from pyulog import ULog

from pilot_vs_drone import PILOT_MODES, armed_period, between, crash_time, topic

MARGINS = [0, 2, 5, 10, 20, 30]
FEATURES = ["tune_rms", "tilt_p95", "vib_p95", "clip_rate", "sat_frac", "batt_min", "volt_sag", "gps_bad", "failsafe",
            "manual_frac", "stick_p95"]
TOPICS = ["vehicle_status", "vehicle_land_detected", "vehicle_attitude", "vehicle_rates_setpoint", "vehicle_angular_velocity",
          "vehicle_imu_status", "actuator_motors", "actuator_outputs", "battery_status", "vehicle_gps_position", "sensor_gps",
          "manual_control_setpoint"]


def frac_time(ts, flag):
    if len(ts) < 2:
        return np.nan
    dt = np.diff(ts, append=ts[-1]).astype(float)
    return float(dt[flag].sum() / max(dt.sum(), 1.0))


def window_features(u, st, rotary, a, b):
    f = {k: np.nan for k in FEATURES}
    dur = (b - a) / 1e6
    sp, av = topic(u, "vehicle_rates_setpoint"), topic(u, "vehicle_angular_velocity")
    if rotary and sp is not None and av is not None and "roll" in sp and "xyz[0]" in av:
        m = between(av, a, b)
        if m.sum() > 20:
            ts = av["timestamp"][m]
            err = [np.interp(ts, sp["timestamp"], sp[k]) - av[f"xyz[{i}]"][m] for i, k in enumerate(("roll", "pitch"))]
            f["tune_rms"] = float(np.sqrt(np.mean(np.square(err))))
    att = topic(u, "vehicle_attitude")
    if att is not None:
        m = between(att, a, b)
        if m.any():
            qx, qy = att["q[1]"][m], att["q[2]"][m]
            f["tilt_p95"] = float(np.percentile(np.degrees(np.arccos(np.clip(1 - 2 * (qx ** 2 + qy ** 2), -1, 1))), 95))
    imu = topic(u, "vehicle_imu_status")
    if imu is not None:
        m = between(imu, a, b)
        if m.any():
            if "accel_vibration_metric" in imu:
                f["vib_p95"] = float(np.percentile(imu["accel_vibration_metric"][m], 95))
            f["clip_rate"] = sum(float(imu[k][m].sum()) for k in imu if k.startswith("accel_clipping[")) / dur
    if rotary:
        am, ao = topic(u, "actuator_motors"), topic(u, "actuator_outputs")
        if am is not None:
            m = between(am, a, b)
            cols = [k for k in am if k.startswith("control[") and m.any() and not np.isnan(am[k][m]).all()]
            if cols:
                f["sat_frac"] = frac_time(am["timestamp"][m], np.any([am[k][m] >= 0.95 for k in cols], axis=0))
        elif ao is not None:
            m = between(ao, a, b)
            n = int(np.median(ao["noutputs"])) if "noutputs" in ao else 4
            cols = [f"output[{i}]" for i in range(min(n, 8)) if f"output[{i}]" in ao]
            if m.any() and cols:
                f["sat_frac"] = frac_time(ao["timestamp"][m], np.any([ao[k][m] >= 1950 for k in cols], axis=0))
    bat = topic(u, "battery_status")
    if bat is not None:
        m = between(bat, a, b)
        if m.any():
            if "remaining" in bat:
                r = bat["remaining"][m]
                r = r[r >= 0]
                if len(r):
                    f["batt_min"] = float(r.min() * 100)
            v = bat["voltage_v"] if "voltage_v" in bat else bat.get("voltage_filtered_v")
            if v is not None:
                v = v[m]
                v = v[v > 0]
                if len(v) > 2 and v[: max(1, len(v) // 20)].max() > 0:
                    v0 = v[: max(1, len(v) // 20)].max()
                    f["volt_sag"] = float((v0 - v.min()) / v0)
    gps = topic(u, "vehicle_gps_position")
    gps = gps if gps is not None else topic(u, "sensor_gps")
    if gps is not None:
        m = between(gps, a, b)
        if m.any():
            f["gps_bad"] = frac_time(gps["timestamp"][m], (gps["eph"][m] > 5) | (gps["satellites_used"][m] < 6))
    m = between(st, a, b)
    if m.any():
        f["failsafe"] = float(st["failsafe"][m].any()) if "failsafe" in st else np.nan
        f["manual_frac"] = frac_time(st["timestamp"][m], np.isin(st["nav_state"][m], list(PILOT_MODES)))
    mc = topic(u, "manual_control_setpoint")
    if mc is not None:
        m = between(mc, a, b)
        kx, ky = ("x", "y") if "x" in mc else ("pitch", "roll")
        if m.any() and kx in mc:
            f["stick_p95"] = float(np.percentile(np.maximum(np.abs(mc[kx][m]), np.abs(mc[ky][m])), 95))
    return f


def log_rows(path, group, label):
    u = ULog(path, message_name_filter_list=TOPICS)
    st = topic(u, "vehicle_status")
    if st is None:
        return []
    per = armed_period(st)
    if per is None:
        return []
    t_arm, t_end = per
    rotary = bool(st["is_rotary_wing"][-1]) if "is_rotary_wing" in st else True
    t_c = crash_time(u, t_arm, t_end, rotary) if group == "crash" else t_end
    land = topic(u, "vehicle_land_detected")
    t0 = t_arm
    if land is not None:
        mm = between(land, t_arm, t_c) & (land["landed"] == 0)
        if mm.any():
            t0 = land["timestamp"][mm][0]
    rows = []
    for margin in MARGINS:
        b = t_c - margin * 1e6
        if b - t0 < 10e6:
            continue
        rows.append({"log": os.path.basename(path)[:-4], "group": group, "label": label, "margin": margin,
                     **window_features(u, st, rotary, t0, b)})
    return rows


def auc(y, s):
    y, s = np.asarray(y), np.asarray(s, float)
    ok = ~np.isnan(s)
    y, s = y[ok], s[ok]
    pos, neg = s[y == 1], s[y == 0]
    if len(pos) == 0 or len(neg) == 0:
        return np.nan
    ranks = np.argsort(np.argsort(np.concatenate([pos, neg]))) + 1.0
    allv = np.concatenate([pos, neg])
    for v in np.unique(allv):                                         # average ranks for ties
        idx = allv == v
        ranks[idx] = ranks[idx].mean()
    return float((ranks[: len(pos)].sum() - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg)))


def fit_predict(Xtr, ytr, Xte, lam=1.0, iters=3000, lr=0.1):
    med = np.nanmedian(Xtr, axis=0)
    med = np.where(np.isnan(med), 0.0, med)
    Xtr, Xte = np.where(np.isnan(Xtr), med, Xtr), np.where(np.isnan(Xte), med, Xte)
    mu, sd = Xtr.mean(0), Xtr.std(0)
    sd[sd == 0] = 1.0
    Xtr, Xte = (Xtr - mu) / sd, (Xte - mu) / sd
    w, b = np.zeros(Xtr.shape[1]), 0.0
    for _ in range(iters):
        p = 1 / (1 + np.exp(-(Xtr @ w + b)))
        g = p - ytr
        w -= lr * (Xtr.T @ g / len(ytr) + lam * w / len(ytr))
        b -= lr * g.mean()
    return Xte @ w + b


def cv_auc(X, y, seeds=range(5), k=5):
    out = []
    for seed in seeds:
        rng = np.random.default_rng(seed)
        folds = np.zeros(len(y), int)
        for cls in (0, 1):
            idx = np.where(y == cls)[0]
            rng.shuffle(idx)
            folds[idx] = np.arange(len(idx)) % k
        scores = np.zeros(len(y))
        for f in range(k):
            te, tr = folds == f, folds != f
            scores[te] = fit_predict(X[tr], y[tr], X[te])
        out.append(auc(y, scores))
    return float(np.mean(out)), float(np.std(out))


def main(root, out_dir):
    from csv import DictReader

    labels = {}
    for sel in (os.path.join(root, "selection.csv"), os.path.join(root, "holdout.csv")):
        for r in DictReader(open(sel)):
            labels[r["log_id"]] = {"crash_sw_hw": "drone", "crash_pilot": "pilot"}.get(r["rating"], "normal")
    files = [(p, "crash") for p in glob(os.path.join(root, "crash", "*.ulg")) + glob(os.path.join(root, "h", "crash", "*.ulg"))]
    files += [(p, "normal") for p in glob(os.path.join(root, "h", "normal", "*.ulg"))]
    rows, skipped = [], 0
    for p, g in sorted(files):
        try:
            got = log_rows(p, g, labels.get(os.path.basename(p)[:-4], "normal"))
        except Exception:
            got = []
        skipped += not got
        rows += got
    with open(os.path.join(out_dir, "leak_curve_features.jsonl"), "w") as fh:
        for r in rows:
            fh.write(json.dumps({k: (None if isinstance(v, float) and np.isnan(v) else v) for k, v in r.items()}) + "\n")

    L = ["# The crash-window leak", "",
         f"Logs with at least one usable window: {len({r['log'] for r in rows})} (skipped {skipped}). Features are computed on the "
         "flight up to *m* seconds before the crash (normal flights: before the end of the armed period). Declared in advance "
         "in `leak_curve.py`.", "",
         "## Model (logistic regression, 5-fold CV x 5)", "",
         "| Cut-off m (s) | A: crash vs normal — logs | A: AUC | B: pilot vs drone — logs | B: AUC |", "|---|---|---|---|---|"]
    res = {}
    for m in MARGINS:
        R = [r for r in rows if r["margin"] == m]
        X = np.array([[r[f] for f in FEATURES] for r in R], float)
        ya = np.array([1 if r["group"] == "crash" else 0 for r in R])
        Rb = [r for r in R if r["group"] == "crash" and r["label"] in ("pilot", "drone")]
        Xb = np.array([[r[f] for f in FEATURES] for r in Rb], float)
        yb = np.array([1 if r["label"] == "drone" else 0 for r in Rb])
        a_m, a_s = cv_auc(X, ya)
        b_m, b_s = cv_auc(Xb, yb)
        res[m] = (a_m, b_m)
        L.append(f"| {m} | {ya.sum()} crash / {(ya == 0).sum()} normal | {a_m:.2f} ± {a_s:.2f} | "
                 f"{yb.sum()} drone / {(yb == 0).sum()} pilot | {b_m:.2f} ± {b_s:.2f} |")
    drop = res[0][0] - res[10][0]
    L += ["", f"**H_leak** (task A AUC at 0 s minus at 10 s >= 0.10): drop = {drop:.2f} → "
          f"**{'supported' if drop >= 0.10 else 'not supported'}**.", "",
          "## Single features, task A (crash vs normal), AUC with no fitting", "",
          "| Feature | " + " | ".join(f"m={m}" for m in MARGINS) + " |", "|---|" + "---|" * len(MARGINS)]
    for f in FEATURES:
        cells = []
        for m in MARGINS:
            R = [r for r in rows if r["margin"] == m]
            cells.append(f"{auc([1 if r['group'] == 'crash' else 0 for r in R], [r[f] for r in R]):.2f}")
        L.append(f"| {f} | " + " | ".join(cells) + " |")
    L += ["", "AUC 0.5 = no better than chance; below 0.5 means the feature is *lower* in crashes.", "",
          "## Limits", "",
          "- Labels are the uploaders'; normal flights are self-rated good/great.",
          "- The crash moment is estimated from attitude (rotary wing) or the end of arming (fixed wing).",
          "- Normal flights end with a landing, crashes with a crash; the cut-off removes the last m seconds of both.",
          "- One simple model; a stronger model could do better at every cut-off, which would not remove the leak."]
    open(os.path.join(out_dir, "leak_curve.md"), "w").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main(*sys.argv[1:3])
