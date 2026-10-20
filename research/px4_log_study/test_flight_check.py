"""Test-flight check: does a fixed log check find the fault forum experts named?

PRE-DECLARED (committed before the forum logs were downloaded; thresholds are first guesses from the PX4 docs
and are NOT to be tuned on these logs).

Window: from the first not-landed moment after arming to the crash moment t_c (pilot_vs_drone.crash_time;
for normal flights the end of the armed period). Rotary-wing checks only where noted.

  C_TUNE   rotary: RMS of (rate setpoint - measured rate) over roll and pitch > 0.30 rad/s
  C_VIBE   accelerometer clipping sum > 50, or 95th percentile of accel_vibration_metric > 30 m/s^2
  C_MAG    estimator mag_test_ratio > 1.0 for >= 1 s in total
  C_GPS    eph > 5 m or satellites_used < 6 for >= 5 s in total
  C_MOTOR  rotary: any motor >= 95% (actuator_motors >= 0.95 or actuator_outputs >= 1950 us) for >= 1 s in total
  C_BATT   battery warning >= 2, or remaining < 0.10

Matching expert causes (forum_expert_labels.csv, expert_conclusion = drone):
  tuning / configuration -> C_TUNE;  vibration / mounting -> C_VIBE;  GPS / compass / estimator -> C_MAG or C_GPS;
  motor / ESC / propeller -> C_MOTOR;  battery / power -> C_BATT

A check counts as USEFUL if it fires on >= 50% of the logs whose expert named its cause AND on <= 10% of the
normal (good/great) flights. Reported per check, with counts; no overall pass mark.

SECOND RUN, declared after the first results and before running it: the first run's window ran up to the crash,
so checks could fire on the crash itself. With END_MARGIN_S = 10 the window stops 10 s before t_c (logs with less
than 10 s left are dropped). Same checks, same thresholds, same pass marks. Set by the 6th argument.

    python research/px4_log_study/test_flight_check.py LABELS_CSV FORUM_LOG_DIR NORMAL_CSV NORMAL_LOG_DIR OUT_DIR [END_MARGIN_S]
"""
import csv
import json
import os
import sys
from collections import Counter

import numpy as np
from pyulog import ULog

from pilot_vs_drone import armed_period, between, crash_time, seconds_true, topic

TOPICS = ["vehicle_status", "vehicle_land_detected", "vehicle_attitude", "vehicle_rates_setpoint",
          "vehicle_angular_velocity", "vehicle_imu_status", "estimator_status", "vehicle_gps_position", "sensor_gps",
          "actuator_motors", "actuator_outputs", "battery_status"]
CHECKS = ("C_TUNE", "C_VIBE", "C_MAG", "C_GPS", "C_MOTOR", "C_BATT")
END_MARGIN_S = 0.0
CAUSE_CHECKS = {"tuning / configuration": ("C_TUNE",), "vibration / mounting": ("C_VIBE",),
                "GPS / compass / estimator": ("C_MAG", "C_GPS"), "motor / ESC / propeller": ("C_MOTOR",),
                "battery / power": ("C_BATT",)}


def checks(u):
    st = topic(u, "vehicle_status")
    if st is None:
        return None, "no vehicle_status"
    per = armed_period(st)
    if per is None:
        return None, "never armed"
    t_arm, t_end = per
    rotary = bool(st["is_rotary_wing"][-1]) if "is_rotary_wing" in st else True
    t_c = crash_time(u, t_arm, t_end, rotary) - END_MARGIN_S * 1e6
    land = topic(u, "vehicle_land_detected")
    t0 = t_arm
    if land is not None:
        m = between(land, t_arm, t_c) & (land["landed"] == 0)
        if m.any():
            t0 = land["timestamp"][m][0]
    if t_c - t0 < 10e6:
        return None, "less than 10 s airborne in the window"
    out = {}

    sp, av = topic(u, "vehicle_rates_setpoint"), topic(u, "vehicle_angular_velocity")
    if rotary and sp is not None and av is not None and "roll" in sp and "xyz[0]" in av:
        m = between(av, t0, t_c)
        if m.sum() > 50:
            ts = av["timestamp"][m]
            err = [np.interp(ts, sp["timestamp"], sp[k]) - av[f"xyz[{i}]"][m] for i, k in enumerate(("roll", "pitch"))]
            out["C_TUNE"] = float(np.sqrt(np.mean(np.square(err)))) > 0.30

    imu = topic(u, "vehicle_imu_status")
    if imu is not None:
        m = between(imu, t0, t_c)
        if m.any():
            clip = sum(float(imu[k][m].sum()) for k in imu if k.startswith("accel_clipping["))
            vib = float(np.percentile(imu["accel_vibration_metric"][m], 95)) if "accel_vibration_metric" in imu else 0.0
            out["C_VIBE"] = clip > 50 or vib > 30

    es = topic(u, "estimator_status")
    if es is not None and "mag_test_ratio" in es:
        m = between(es, t0, t_c)
        if m.any():
            out["C_MAG"] = seconds_true(es["timestamp"][m], es["mag_test_ratio"][m] > 1.0) >= 1.0

    gps = topic(u, "vehicle_gps_position")
    gps = gps if gps is not None else topic(u, "sensor_gps")
    if gps is not None:
        m = between(gps, t0, t_c)
        if m.any():
            bad = (gps["eph"][m] > 5) | (gps["satellites_used"][m] < 6)
            out["C_GPS"] = seconds_true(gps["timestamp"][m], bad) >= 5.0

    if rotary:
        am, ao = topic(u, "actuator_motors"), topic(u, "actuator_outputs")
        if am is not None:
            m = between(am, t0, t_c)
            cols = [k for k in am if k.startswith("control[") and m.any() and not np.isnan(am[k][m]).all()]
            if cols:
                out["C_MOTOR"] = seconds_true(am["timestamp"][m], np.any([am[k][m] >= 0.95 for k in cols], axis=0)) >= 1.0
        elif ao is not None:
            m = between(ao, t0, t_c)
            n = int(np.median(ao["noutputs"])) if "noutputs" in ao else 4
            cols = [f"output[{i}]" for i in range(min(n, 8)) if f"output[{i}]" in ao]
            if m.any() and cols:
                out["C_MOTOR"] = seconds_true(ao["timestamp"][m], np.any([ao[k][m] >= 1950 for k in cols], axis=0)) >= 1.0

    b = topic(u, "battery_status")
    if b is not None:
        m = between(b, t0, t_c)
        if m.any():
            out["C_BATT"] = bool(("warning" in b and (b["warning"][m] >= 2).any())
                                 or ("remaining" in b and ((b["remaining"][m] < 0.10) & (b["remaining"][m] >= 0)).any()))
    return {"rotary": rotary, "airborne_s": round((t_c - t0) / 1e6, 1), "checks": out}, None


def run(path):
    try:
        return checks(ULog(path, message_name_filter_list=TOPICS))
    except Exception as e:
        return None, type(e).__name__


def main(labels_csv, forum_dir, normal_csv, normal_dir, out_dir, end_margin_s="0"):
    global END_MARGIN_S
    END_MARGIN_S = float(end_margin_s)
    tag = "" if END_MARGIN_S == 0 else f"_minus{int(END_MARGIN_S)}s"
    res, skipped = [], Counter()
    for r in csv.DictReader(open(labels_csv)):
        if r["is_crash"] != "yes" or r["expert_conclusion"] != "drone" or r["cause"] not in CAUSE_CHECKS:
            continue
        logs = [lid for lid in r["log_ids"].split() if os.path.exists(os.path.join(forum_dir, lid + ".ulg"))]
        if not logs:
            skipped["forum: log not downloadable"] += 1
            continue
        out, why = run(os.path.join(forum_dir, logs[0] + ".ulg"))
        if out is None:
            skipped[f"forum: {why}"] += 1
            continue
        out.update(group="forum", topic_id=r["topic_id"], log_id=logs[0], cause=r["cause"], confirmed=r["poster_confirmed"])
        res.append(out)
    for r in csv.DictReader(open(normal_csv)):
        if r["group"] != "normal":
            continue
        out, why = run(os.path.join(normal_dir, r["log_id"] + ".ulg"))
        if out is None:
            skipped[f"normal: {why}"] += 1
            continue
        out.update(group="normal", log_id=r["log_id"])
        res.append(out)
    with open(os.path.join(out_dir, f"test_flight_check{tag}.jsonl"), "w") as f:
        for x in res:
            f.write(json.dumps(x) + "\n")

    normal = [x for x in res if x["group"] == "normal"]
    forum = [x for x in res if x["group"] == "forum"]
    L = [f"# Test-flight check against expert-diagnosed crashes (window ends {END_MARGIN_S:.0f} s before the crash)", "",
         f"Forum crash logs (expert said drone, named a matching cause): {len(forum)}; normal flights: {len(normal)}. "
         f"Skipped: {dict(skipped)}.", "Checks and pass marks were committed before the forum logs were downloaded.", "",
         "| Expert cause | Check | Fires on expert-cause logs | Fires on normal flights | Useful? |", "|---|---|---|---|---|"]
    for cause, cks in CAUSE_CHECKS.items():
        xs = [x for x in forum if x["cause"] == cause]
        ev = [x for x in xs if any(c in x["checks"] for c in cks)]
        hit = sum(any(x["checks"].get(c) for c in cks) for x in ev)
        nv = [x for x in normal if any(c in x["checks"] for c in cks)]
        nhit = sum(any(x["checks"].get(c) for c in cks) for x in nv)
        sens, fa = hit / max(1, len(ev)), nhit / max(1, len(nv))
        ok = "yes" if ev and sens >= 0.5 and fa <= 0.10 else "no"
        L.append(f"| {cause} | {' or '.join(cks)} | {hit} of {len(ev)} ({100 * sens:.0f}%) | {nhit} of {len(nv)} "
                 f"({100 * fa:.0f}%) | {ok} |")
    L += ["", "## Every check on every forum log (any cause)", "", "| Check | Forum crash logs | Normal flights |", "|---|---|---|"]
    for c in CHECKS:
        f1 = [x for x in forum if c in x["checks"]]
        n1 = [x for x in normal if c in x["checks"]]
        L.append(f"| {c} | {sum(x['checks'][c] for x in f1)} of {len(f1)} | {sum(x['checks'][c] for x in n1)} of {len(n1)} |")
    L += ["", "## Limits", "",
          "- Forum labels were recorded with AI assistance and reviewed by the project owner; quotes verified by script.",
          "- Forum logs include the crash itself; a check that fires only because of the crash is not a pre-flight finding.",
          "- Small numbers per cause. Thresholds are first guesses, declared in advance."]
    open(os.path.join(out_dir, f"test_flight_check{tag}.md"), "w").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main(*sys.argv[1:7])
