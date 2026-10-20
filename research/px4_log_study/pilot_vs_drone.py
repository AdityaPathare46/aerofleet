"""Pilot or drone? A fixed, no-AI rule tested on PX4 crash logs labelled by their uploaders.

PRE-DECLARED (written and committed before the rule was run on any crash log; do not tune on these 100 logs).

Crash moment t_c: in the last armed period, after the vehicle is first not landed, the first time the tilt exceeds
60 degrees (rotary wing only). Otherwise (fixed wing, or no such tilt) the end of the armed period.
Evidence window: arming to t_c, and the "late" window t_c - 10 s to t_c.

Drone evidence (any one makes the answer DRONE):
  D_BATT     battery_status.warning >= 2 (critical/emergency/failed), or remaining < 0.10, between arming and t_c
  D_MOTOR    rotary wing: in the late window, any motor at >= 95% (actuator_motors >= 0.95, or actuator_outputs
             >= 1950 us on the first N motor outputs) for >= 1.0 s in total
  D_CLIP     sum of accelerometer clipping counts between arming and t_c > 50
  D_GPS      in the late window, while in a GPS-dependent mode: eph > 5 m or fix_type < 3
  D_FD       failure detector motor/battery/imbalanced-prop/external flag, or engine_failure, between arming and t_c
  D_ERR      an autopilot message at error level or worse (EMERG..ERR) between arming and t_c
  D_CPU      cpuload.load > 0.95 between arming and t_c
  D_FAILSAFE vehicle_status.failsafe true between arming and t_c
Otherwise, if the flight mode at t_c is pilot-flown (MANUAL, ALTCTL, POSCTL, ACRO, STAB): PILOT.
Otherwise: UNKNOWN (a person must look).

Success, declared in advance: on the crashes the rule decides, balanced accuracy >= 0.70; it decides >= 60% of
crashes; and it is wrong on <= 20% of all crashes. Baseline to beat: always answering DRONE (the larger label).

    python research/px4_log_study/pilot_vs_drone.py SELECTION_CSV LOG_DIR OUT_DIR
"""
import csv
import json
import os
import sys
from collections import Counter

import numpy as np
from pyulog import ULog

PILOT_MODES = {0: "MANUAL", 1: "ALTCTL", 2: "POSCTL", 10: "ACRO", 15: "STAB"}
GPS_MODES = {2, 3, 4, 5, 17, 18, 19, 20, 21}   # POSCTL and the AUTO modes
TOPICS = ["vehicle_status", "battery_status", "actuator_motors", "actuator_outputs", "vehicle_imu_status",
          "vehicle_gps_position", "sensor_gps", "failure_detector_status", "cpuload", "vehicle_attitude",
          "vehicle_land_detected"]


def topic(u, name):
    ds = [d for d in u.data_list if d.name == name]
    return ds[0].data if ds else None


def armed_period(st):
    t, armed = st["timestamp"], st["arming_state"] == 2
    if not armed.any():
        return None
    end = int(np.where(armed)[0][-1])
    start = end
    while start > 0 and armed[start - 1]:
        start -= 1
    nxt = t[end + 1] if end + 1 < len(t) else t[end]
    return t[start], nxt


def between(d, t0, t1):
    return (d["timestamp"] >= t0) & (d["timestamp"] <= t1)


def crash_time(u, t_arm, t_end, rotary):
    if not rotary:
        return t_end
    att, land = topic(u, "vehicle_attitude"), topic(u, "vehicle_land_detected")
    t_air = t_arm
    if land is not None:
        m = between(land, t_arm, t_end) & (land["landed"] == 0)
        if m.any():
            t_air = land["timestamp"][m][0]
    if att is None:
        return t_end
    m = between(att, t_air, t_end)
    qx, qy = att["q[1]"][m], att["q[2]"][m]
    tilt = np.degrees(np.arccos(np.clip(1 - 2 * (qx ** 2 + qy ** 2), -1, 1)))
    over = np.where(tilt > 60)[0]
    return att["timestamp"][m][over[0]] if len(over) else t_end


def seconds_true(ts, flag):
    if len(ts) < 2:
        return 0.0
    dt = np.diff(ts, append=ts[-1]) / 1e6
    return float(dt[flag].sum())


def evidence(u):
    st = topic(u, "vehicle_status")
    if st is None:
        return None, "no vehicle_status"
    per = armed_period(st)
    if per is None:
        return None, "never armed"
    t_arm, t_end = per
    rotary = bool(st["is_rotary_wing"][-1]) if "is_rotary_wing" in st else True
    t_c = crash_time(u, t_arm, t_end, rotary)
    late0 = t_c - 10e6
    ev = {}

    b = topic(u, "battery_status")
    if b is not None:
        m = between(b, t_arm, t_c)
        ev["D_BATT"] = bool(m.any() and (("warning" in b and (b["warning"][m] >= 2).any())
                                         or ("remaining" in b and ((b["remaining"][m] < 0.10) & (b["remaining"][m] >= 0)).any())))

    if rotary:
        am, ao = topic(u, "actuator_motors"), topic(u, "actuator_outputs")
        sat = None
        if am is not None:
            m = between(am, late0, t_c)
            cols = [k for k in am if k.startswith("control[") and not np.isnan(am[k][m]).all()] if m.any() else []
            if cols:
                sat = seconds_true(am["timestamp"][m], np.any([am[k][m] >= 0.95 for k in cols], axis=0))
        elif ao is not None:
            m = between(ao, late0, t_c)
            n = int(np.median(ao["noutputs"])) if "noutputs" in ao else 4
            cols = [f"output[{i}]" for i in range(min(n, 8)) if f"output[{i}]" in ao]
            if m.any() and cols:
                sat = seconds_true(ao["timestamp"][m], np.any([ao[k][m] >= 1950 for k in cols], axis=0))
        if sat is not None:
            ev["D_MOTOR"] = sat >= 1.0

    imu = topic(u, "vehicle_imu_status")
    if imu is not None:
        m = between(imu, t_arm, t_c)
        cols = [k for k in imu if k.startswith("accel_clipping[")]
        if cols:
            ev["D_CLIP"] = float(sum(imu[k][m].sum() for k in cols)) > 50

    gps = topic(u, "vehicle_gps_position")
    gps = gps if gps is not None else topic(u, "sensor_gps")
    if gps is not None:
        m = between(gps, late0, t_c)
        nav = np.interp(gps["timestamp"][m], st["timestamp"], st["nav_state"]).round().astype(int) if m.any() else []
        in_gps_mode = np.isin(nav, list(GPS_MODES)) if m.any() else np.array([], bool)
        bad = (gps["eph"][m] > 5) | (gps["fix_type"][m] < 3) if m.any() else np.array([], bool)
        ev["D_GPS"] = bool((bad & in_gps_mode).any())

    fd = topic(u, "failure_detector_status")
    m_st = between(st, t_arm, t_c)
    flag = bool("engine_failure" in st and st["engine_failure"][m_st].any())
    if fd is not None:
        m = between(fd, t_arm, t_c)
        flag |= any(fd[k][m].any() for k in ("fd_motor", "fd_battery", "fd_imbalanced_prop", "fd_ext") if k in fd)
    ev["D_FD"] = flag

    lvl = lambda m: m.log_level - 48 if m.log_level >= 48 else m.log_level  # noqa: E731  ('0'..'7' or 0..7)
    errs = [m.message for m in u.logged_messages if t_arm <= m.timestamp <= t_c and lvl(m) <= 3]
    ev["D_ERR"] = bool(errs)

    cpu = topic(u, "cpuload")
    if cpu is not None:
        ev["D_CPU"] = bool((cpu["load"][between(cpu, t_arm, t_c)] > 0.95).any())

    ev["D_FAILSAFE"] = bool("failsafe" in st and st["failsafe"][m_st].any())

    i = np.searchsorted(st["timestamp"], t_c, side="right") - 1
    mode = int(st["nav_state"][max(i, 0)])
    if any(ev.values()):
        verdict = "drone"
    elif mode in PILOT_MODES:
        verdict = "pilot"
    else:
        verdict = "unknown"
    return {"verdict": verdict, "mode_at_crash": mode, "rotary": rotary, "evidence": ev,
            "errors": errs[:5], "flight_s": round((t_c - t_arm) / 1e6, 1)}, None


def main(sel_csv, log_dir, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    rows, skipped = [], Counter()
    for r in csv.DictReader(open(sel_csv)):
        if r["group"] != "crash":
            continue
        try:
            res, why = evidence(ULog(os.path.join(log_dir, "crash", r["log_id"] + ".ulg"), message_name_filter_list=TOPICS))
        except Exception as e:
            res, why = None, type(e).__name__
        if res is None:
            skipped[why] += 1
            continue
        res.update(log_id=r["log_id"], label="drone" if r["rating"] == "crash_sw_hw" else "pilot", mav_type=r["mav_type"])
        rows.append(res)
    with open(os.path.join(out_dir, "pilot_vs_drone.jsonl"), "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")

    n = len(rows)
    cm = Counter((r["label"], r["verdict"]) for r in rows)
    dec = [r for r in rows if r["verdict"] != "unknown"]
    rec = {lab: cm[(lab, lab)] / max(1, sum(cm[(lab, v)] for v in ("drone", "pilot"))) for lab in ("drone", "pilot")}
    bal = (rec["drone"] + rec["pilot"]) / 2
    wrong = sum(1 for r in dec if r["verdict"] != r["label"])
    base = sum(1 for r in rows if r["label"] == "drone")
    ok = bal >= 0.70 and len(dec) / max(1, n) >= 0.60 and wrong / max(1, n) <= 0.20
    L = ["# Pilot or drone? First test on PX4 crash logs", "",
         f"Crash logs analysed: {n} (skipped: {dict(skipped)}). Labels are the uploader's own rating on PX4 Flight Review.",
         "The rule was written and committed before it was run (see the docstring of `pilot_vs_drone.py`).", "",
         "| Uploader said ↓ / rule said → | drone | pilot | unknown |", "|---|---|---|---|"]
    for lab in ("drone", "pilot"):
        L.append(f"| {lab} | {cm[(lab, 'drone')]} | {cm[(lab, 'pilot')]} | {cm[(lab, 'unknown')]} |")
    L += ["", f"- Decided: {len(dec)} of {n} ({100 * len(dec) / max(1, n):.0f}%)",
          f"- Right when it decided: {len(dec) - wrong} of {len(dec)}; wrong: {wrong} ({100 * wrong / max(1, n):.0f}% of all)",
          f"- Balanced accuracy on decided cases: {bal:.2f} (drone recall {rec['drone']:.2f}, pilot recall {rec['pilot']:.2f})",
          f"- Baseline 'always drone': right on {base} of {n} ({100 * base / max(1, n):.0f}%), balanced accuracy 0.50",
          f"- Pre-declared success test: **{'PASSED' if ok else 'FAILED'}**", "",
          "## How often each piece of evidence fired", "", "| Evidence | Drone-labelled crashes | Pilot-labelled crashes |",
          "|---|---|---|"]
    for k in ("D_BATT", "D_MOTOR", "D_CLIP", "D_GPS", "D_FD", "D_ERR", "D_CPU", "D_FAILSAFE"):
        d = [r for r in rows if r["label"] == "drone" and k in r["evidence"]]
        p = [r for r in rows if r["label"] == "pilot" and k in r["evidence"]]
        L.append(f"| {k} | {sum(r['evidence'][k] for r in d)} of {len(d)} | {sum(r['evidence'][k] for r in p)} of {len(p)} |")
    modes = Counter((r["label"], PILOT_MODES.get(r["mode_at_crash"], f"auto/other {r['mode_at_crash']}")) for r in rows)
    L += ["", "## Flight mode at the crash moment", "", "| Mode | Drone-labelled | Pilot-labelled |", "|---|---|---|"]
    for m in sorted({m for _, m in modes}):
        L.append(f"| {m} | {modes[('drone', m)]} | {modes[('pilot', m)]} |")
    L += ["", "## Limits", "",
          "- Uploader labels are unchecked and can be wrong; 'pilot' and 'drone' causes can both be present.",
          "- No normal flights were tested here, so how often each evidence item fires on good flights is not known yet;",
          "  an item that fires on many good flights is not evidence of anything.",
          "- 100 logs; the pilot group is about a third of them."]
    open(os.path.join(out_dir, "pilot_vs_drone.md"), "w").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main(*sys.argv[1:4])
