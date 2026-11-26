"""Fly the declared SITL scenarios on the real ArduCopter firmware and keep each flight's log.

ArduPilot SITL runs the actual ArduCopter flight code on this computer with a simulated quadcopter; it writes the same
DataFlash .bin log a Pixhawk writes. Protocol and expectations: research/sitl_check/PROTOCOL.md (declared first).

Each run: a fresh vehicle (parameters wiped to ArduPilot's SITL defaults), home on a field near Pune, a spraying-style
mission (back-and-forth passes 8 m apart at 4 m over an 80 m x 40 m field, then return to launch), the scenario's
change, and the log copied to the data drive with the mission file next to it.

    python research/sitl_check/run_scenarios.py [SCENARIO ...]      # all scenarios, 3 runs each, by default
"""
from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
import sys
import time
from glob import glob

from pymavlink import mavutil

AP = os.path.expanduser("~/aerofleet_sitl/ardupilot")
BIN = os.path.join(AP, "build", "sitl", "bin", "arducopter")
DEFAULTS = os.path.join(AP, "Tools", "autotest", "default_params", "copter.parm")
WORK = os.path.expanduser("~/aerofleet_sitl/runs")
OUT = "/Volumes/One Touch/AeroFleet_px4_data/sitl"
SPEEDUP = 5
HOME = (18.4470, 73.9790, 560.0)        # a farm field east of Pune (any open place works; nothing here is checked against maps)
ALT = 4.0
M = 111_320.0

# Each scenario: parameters set before arming, and an action at a set time after the mission starts (sim seconds).
SCENARIOS = {
    "S0_normal":        {"pre": {}, "at": None},
    "S1_failsafe_off":  {"pre": {"FS_THR_ENABLE": 0, "BATT_FS_LOW_ACT": 0}, "at": None},
    "S2_gps_lost":      {"pre": {}, "at": (40, {"SIM_GPS1_ENABLE": 0}), "restore": (60, {"SIM_GPS1_ENABLE": 1})},
    "S3_battery_low":   {"pre": {"SIM_BATT_CAP_AH": 0.35, "BATT_CAPACITY": 350, "BATT_LOW_MAH": 90, "BATT_FS_LOW_ACT": 2}, "at": None},
    "S4_fence_off_in_flight": {"pre": {"FENCE_ENABLE": 1, "FENCE_TYPE": 1, "FENCE_ALT_MAX": 50}, "at": (40, {"FENCE_ENABLE": 0})},
    "S5_wind":          {"pre": {"SIM_WIND_SPD": 8, "SIM_WIND_DIR": 270}, "at": None},
    "S6_motor_failure": {"pre": {}, "at": (40, {"SIM_ENGINE_MUL": 0.0, "SIM_ENGINE_FAIL": 1})},
    "S7_compass_failure": {"pre": {}, "at": (40, {"SIM_MAG1_FAIL": 1})},
}
RUNS = 3


def field(k: int):
    """Waypoints for run k: the field moves 150 m per run and alternates east-west / north-south passes."""
    la0, lo0 = HOME[0] + 0.0002 + 0.00135 * k, HOME[1] + 0.0002
    k_lon = M * math.cos(math.radians(la0))
    pts = []
    for i in range(6):
        off, a, b = 8.0 * i, 0.0, (80.0 if k % 2 == 0 else 40.0)
        if k % 2 == 0:                    # passes east-west
            e0, e1, n = (a, b, off) if i % 2 == 0 else (b, a, off)
            pts += [(la0 + n / M, lo0 + e0 / k_lon), (la0 + n / M, lo0 + e1 / k_lon)]
        else:                             # passes north-south
            n0, n1, e = (a, 80.0, off) if i % 2 == 0 else (80.0, a, off)
            pts += [(la0 + n0 / M, lo0 + e / k_lon), (la0 + n1 / M, lo0 + e / k_lon)]
    return [(HOME[0] + 0.0001 * k, HOME[1])] + pts


def waypoints_file(home, pts) -> str:
    lines = ["QGC WPL 110", f"0\t1\t0\t16\t0\t0\t0\t0\t{home[0]:.8f}\t{home[1]:.8f}\t{HOME[2]:.2f}\t1",
             f"1\t0\t3\t22\t0\t0\t0\t0\t{pts[0][0]:.8f}\t{pts[0][1]:.8f}\t{ALT:.2f}\t1"]
    lines += [f"{i}\t0\t3\t16\t0\t0\t0\t0\t{la:.8f}\t{lo:.8f}\t{ALT:.2f}\t1" for i, (la, lo) in enumerate(pts, 2)]
    lines.append(f"{len(pts) + 2}\t0\t3\t20\t0\t0\t0\t0\t0\t0\t0\t1")
    return "\n".join(lines) + "\n"


def set_param(m, name: str, value: float, tries: int = 5) -> None:
    for _ in range(tries):
        m.mav.param_set_send(m.target_system, m.target_component, name.encode(), float(value), mavutil.mavlink.MAV_PARAM_TYPE_REAL32)
        msg = m.recv_match(type="PARAM_VALUE", blocking=True, timeout=3)
        while msg is not None and msg.param_id != name:
            msg = m.recv_match(type="PARAM_VALUE", blocking=True, timeout=3)
        if msg is not None and abs(msg.param_value - value) < 1e-3:
            return
    raise RuntimeError(f"could not set {name}")


def upload(m, home, pts) -> None:
    items = [(mavutil.mavlink.MAV_CMD_NAV_WAYPOINT, home[0], home[1], 0.0, mavutil.mavlink.MAV_FRAME_GLOBAL),
             (mavutil.mavlink.MAV_CMD_NAV_TAKEOFF, pts[0][0], pts[0][1], ALT, mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT)]
    items += [(mavutil.mavlink.MAV_CMD_NAV_WAYPOINT, la, lo, ALT, mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT) for la, lo in pts]
    items.append((mavutil.mavlink.MAV_CMD_NAV_RETURN_TO_LAUNCH, 0, 0, 0, mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT))
    m.mav.mission_count_send(m.target_system, m.target_component, len(items))
    while True:
        req = m.recv_match(type=["MISSION_REQUEST_INT", "MISSION_REQUEST", "MISSION_ACK"], blocking=True, timeout=10)
        if req is None:
            raise RuntimeError("mission upload timed out")
        if req.get_type() == "MISSION_ACK":
            if req.type != 0:
                raise RuntimeError(f"mission rejected: {req.type}")
            return
        cmd, la, lo, alt, frame = items[req.seq]
        m.mav.mission_item_int_send(m.target_system, m.target_component, req.seq, frame, cmd, 0, 1, 0, 0, 0, 0,
                                    int(la * 1e7), int(lo * 1e7), alt)


def mode(m, name: str) -> None:
    m.set_mode(m.mode_mapping()[name])


def run(scenario: str, k: int) -> dict:
    spec = SCENARIOS[scenario]
    d = os.path.join(WORK, f"{scenario}_{k + 1}")
    shutil.rmtree(d, ignore_errors=True)
    os.makedirs(d)
    pts = field(k)
    home = pts[0]
    proc = subprocess.Popen([BIN, "-S", "--model", "quad", "--speedup", str(SPEEDUP), "--wipe", "--defaults", DEFAULTS,
                             "--home", f"{home[0]},{home[1]},{HOME[2]},0", "-I0"], cwd=d,
                            stdout=open(os.path.join(d, "sitl.out"), "w"), stderr=subprocess.STDOUT)
    log = {"scenario": scenario, "run": k + 1, "events": []}
    try:
        time.sleep(2)
        m = mavutil.mavlink_connection("tcp:127.0.0.1:5760", source_system=255)
        m.wait_heartbeat(timeout=60)
        m.mav.request_data_stream_send(m.target_system, m.target_component, mavutil.mavlink.MAV_DATA_STREAM_ALL, 10, 1)
        set_param(m, "LOG_DISARMED", 0)
        for name, v in spec["pre"].items():
            set_param(m, name, v)
        gps_deadline = time.time() + 120                 # the vehicle must finish starting (GPS lock) before a mission fits
        while time.time() < gps_deadline:
            g = m.recv_match(type="GPS_RAW_INT", blocking=True, timeout=3)
            if g is not None and g.fix_type >= 3:
                break
        for attempt in range(6):
            try:
                upload(m, home, pts[1:])
                break
            except RuntimeError:
                if attempt == 5:
                    raise
                time.sleep(3)
        mode(m, "GUIDED")
        deadline = time.time() + 180
        while not m.motors_armed():                       # wait for GPS and the EKF, retrying the arm
            if time.time() > deadline:
                raise RuntimeError("never armed")
            m.arducopter_arm()
            m.recv_match(type="HEARTBEAT", blocking=True, timeout=3)
        m.mav.command_long_send(m.target_system, m.target_component, mavutil.mavlink.MAV_CMD_NAV_TAKEOFF, 0, 0, 0, 0, 0, 0, 0, ALT)
        t_wait = time.time() + 60
        while time.time() < t_wait:
            pos = m.recv_match(type="GLOBAL_POSITION_INT", blocking=True, timeout=3)
            if pos and pos.relative_alt / 1000.0 > ALT * 0.9:
                break
        mode(m, "AUTO")
        t0 = None
        done_at, done_restore = False, False
        deadline = time.time() + 900 / SPEEDUP * 2
        while time.time() < deadline:
            msg = m.recv_match(type=["SYSTEM_TIME", "HEARTBEAT", "STATUSTEXT"], blocking=True, timeout=3)
            if msg is None:
                continue
            if msg.get_type() == "STATUSTEXT":
                log["events"].append(msg.text)
            if msg.get_type() == "SYSTEM_TIME":
                now = msg.time_boot_ms / 1000.0
                t0 = now if t0 is None else t0
                if spec.get("at") and not done_at and now - t0 >= spec["at"][0]:
                    for name, v in spec["at"][1].items():
                        set_param(m, name, v)
                    log["events"].append(f"INJECTED at mission+{now - t0:.0f}s: {spec['at'][1]}")
                    done_at = True
                if spec.get("restore") and done_at and not done_restore and now - t0 >= spec["restore"][0]:
                    for name, v in spec["restore"][1].items():
                        set_param(m, name, v)
                    log["events"].append(f"RESTORED at mission+{now - t0:.0f}s: {spec['restore'][1]}")
                    done_restore = True
            if msg.get_type() == "HEARTBEAT" and t0 is not None and not m.motors_armed():
                log["events"].append("disarmed")
                break
        time.sleep(1)
    except Exception as e:  # noqa: BLE001
        log["error"] = str(e)
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
    bins = sorted(glob(os.path.join(d, "logs", "*.BIN")), key=os.path.getmtime)
    os.makedirs(OUT, exist_ok=True)
    if bins:
        dest = os.path.join(OUT, f"{scenario}_{k + 1}.bin")
        shutil.copyfile(bins[-1], dest)
        log["log"] = dest
    open(os.path.join(OUT, f"{scenario}_{k + 1}.waypoints"), "w").write(waypoints_file(home, pts[1:]))
    return log


def main(names) -> None:
    names = names or list(SCENARIOS)
    results = []
    for s in names:
        for k in range(RUNS):
            r = run(s, k)
            print(json.dumps({x: r[x] for x in r if x != "events"}), flush=True)
            results.append(r)
    json.dump(results, open(os.path.join(OUT, "runs.json"), "w"), indent=1)


if __name__ == "__main__":
    main(sys.argv[1:])
