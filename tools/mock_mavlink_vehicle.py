#!/usr/bin/env python3
"""Fake ArduCopter 4.5 vehicle over MAVLink2/UDP.

Exists to exercise AeroFleet's MAVLink code end to end without real
flight-controller hardware or a full ArduPilot SITL build:

* aerofleet.hardware.mavlink_link.MAVLinkVehicle — connect, telemetry
  decode, arm/takeoff/mode/mission/RTL commands and their ACKs;
* aerofleet.hardware.fc_discovery / fc_inspector — the flight-controller
  compliance check: HEARTBEAT discovery, the parameter protocol
  (PARAM_REQUEST_LIST / PARAM_REQUEST_READ with retry of dropped indexes),
  AUTOPILOT_VERSION via MAV_CMD_REQUEST_MESSAGE, the sensor/battery/GPS/EKF/
  vibration/RC/servo/ESC/power streams, PreArm STATUSTEXTs via
  MAV_CMD_RUN_PREARM_CHECKS, and MAV_CMD_DO_MOTOR_TEST.

It is NOT a flight dynamics simulator — position only updates in response
to the commands it receives, there is no physics. Everything it reports is
a static, realistic *picture* of an ArduCopter on the ground, selected by
``--profile``:

  healthy  a correctly configured 4S Quad X ready for a delivery sortie
  faulty   the mistakes a real pre-flight check must catch:
           BATT_FS_LOW_ACT/BATT_FS_CRT_ACT = 0 (the real ArduCopter
           defaults: "None"), FENCE_ALT_MAX = 150 m (> DGCA 120 m), one
           unbalanced cell, high vibration with growing clipping, no
           compass detected, and SERVO3_FUNCTION duplicating Motor1 (so
           Motor3 has no output)
  bench    healthy configuration on an indoor bench: no GPS fix, EKF in
           constant-position mode, GPS PreArm messages

Parameter names and default values follow ArduCopter 4.5 (defaults
cross-checked against the Copter-4.5 source: AP_BattMonitor_Params.cpp —
FS_LOW_ACT/FS_CRT_ACT default 0, LOW_VOLT 10.5, CRT_VOLT 0, CAPACITY 3300;
AC_Fence.cpp — FENCE_ENABLE 0, FENCE_ACTION 1, FENCE_ALT_MAX 100,
FENCE_RADIUS 300, FENCE_MARGIN 2; ArduCopter/Parameters.cpp — FS_GCS_ENABLE
disabled, FS_CRASH_CHECK 1). The set is a representative subset (~380) of
the ~1,000 a real board reports, not the full list.

Per-cell voltages: a real ArduPilot only reports individual cells when the
battery monitor measures them (smart/DroneCAN batteries, cell monitors);
an analog power module reports the pack voltage only. This mock always
reports cells so the cell-balance rules are exercised; the inspector
handles the pack-only case (tested separately).

Also emits and receives D2D Basic Safety Messages (see
aerofleet/safety/d2d_mesh.py, docs/D2D_MESH_RESEARCH_DESIGN.md) over a
local UDP multicast group unless ``--no-d2d`` is given.

Usage:
    python tools/mock_mavlink_vehicle.py [--port 14550] [--profile healthy|faulty|bench]
                                         [--drone-id D1] [--d2d-port 14650] [--no-d2d]
                                         [--lossy-params] [--start-armed]

The vehicle *sends* to 127.0.0.1:<port> (like Mission Planner's MAVLink
mirror in "UDP Client" mode), so point AeroFleet at it with
connection_string="udpin:127.0.0.1:<port>".
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import os
import socket
import struct
import threading
import time
from typing import Dict, List, Optional, Tuple

# Real ArduPilot speaks MAVLink2 on USB and on Mission Planner's forward;
# ESC_TELEMETRY_1_TO_4 (id 11030) cannot even be encoded in MAVLink1.
os.environ.setdefault("MAVLINK20", "1")

from pymavlink import mavutil  # noqa: E402
from pymavlink.dialects.v20 import ardupilotmega as mavlink2  # noqa: E402

START_LAT = 18.5204   # Pune
START_LON = 73.8567

D2D_MULTICAST_GROUP = "239.192.42.99"  # organization-local scope, RFC 2365
D2D_DEFAULT_PORT = 14650
D2D_BROADCAST_INTERVAL_S = 1.0

PROFILES = ("healthy", "faulty", "bench")

# MAV_PARAM_TYPE
_I8, _I16, _I32, _F = (
    mavlink2.MAV_PARAM_TYPE_INT8, mavlink2.MAV_PARAM_TYPE_INT16,
    mavlink2.MAV_PARAM_TYPE_INT32, mavlink2.MAV_PARAM_TYPE_REAL32,
)

# ArduCopter 4.5 motor matrix (AP_MotorsMatrix.cpp): test order -> motor
# number, for the frames the motor test supports. Duplicated here rather
# than imported so the mock stays a standalone wire-level peer.
_TEST_ORDER_TO_MOTOR = {
    (1, 1): {1: 1, 2: 4, 3: 2, 4: 3},              # Quad X
    (1, 0): {1: 3, 2: 1, 3: 4, 4: 2},              # Quad +
    (2, 1): {1: 5, 2: 1, 3: 4, 4: 6, 5: 2, 6: 3},  # Hexa X
}


# ─────────────────────────────────────────────────────────────────────────
#  Parameters
# ─────────────────────────────────────────────────────────────────────────

def _base_params() -> List[Tuple[str, float, int]]:
    """A healthy, configured ArduCopter 4.5 Quad X on an fmuv3-class board."""
    p: List[Tuple[str, float, int]] = [
        ("FORMAT_VERSION", 120, _I16), ("SYSID_THISMAV", 1, _I16), ("SYSID_MYGCS", 255, _I16),
        ("PILOT_THR_FILT", 0, _F), ("PILOT_TKOFF_ALT", 0, _F), ("PILOT_THR_BHV", 0, _I16),
        ("TELEM_DELAY", 0, _I8), ("GCS_PID_MASK", 0, _I16),
        ("RTL_ALT", 3000, _I32), ("RTL_CONE_SLOPE", 3, _F), ("RTL_SPEED", 0, _F),
        ("RTL_ALT_FINAL", 0, _I16), ("RTL_CLIMB_MIN", 0, _I16), ("RTL_LOIT_TIME", 5000, _I32),
        ("RTL_ALT_TYPE", 0, _I8), ("RTL_OPTIONS", 0, _I32),
        ("FS_GCS_ENABLE", 1, _I8), ("FS_GCS_TIMEOUT", 5, _F),
        ("GPS_HDOP_GOOD", 140, _I16), ("SUPER_SIMPLE", 0, _I8), ("WP_YAW_BEHAVIOR", 2, _I8),
        ("LAND_SPEED", 50, _I16), ("LAND_SPEED_HIGH", 0, _I16), ("LAND_ALT_LOW", 1000, _I16),
        ("PILOT_SPEED_UP", 250, _I16), ("PILOT_SPEED_DN", 0, _I16), ("PILOT_ACCEL_Z", 250, _I16),
        ("FS_THR_ENABLE", 1, _I8), ("FS_THR_VALUE", 975, _I16), ("THR_DZ", 100, _I16),
        ("FLTMODE_CH", 5, _I8), ("FLTMODE1", 0, _I8), ("FLTMODE2", 2, _I8), ("FLTMODE3", 5, _I8),
        ("FLTMODE4", 6, _I8), ("FLTMODE5", 9, _I8), ("FLTMODE6", 0, _I8), ("INITIAL_MODE", 0, _I8),
        ("SIMPLE", 0, _I8), ("LOG_BITMASK", 176126, _I32), ("ESC_CALIBRATION", 0, _I8),
        ("TUNE", 0, _I8), ("FRAME_TYPE", 1, _I8), ("FRAME_CLASS", 1, _I8), ("DISARM_DELAY", 10, _I8),
        ("ANGLE_MAX", 3000, _I16), ("PHLD_BRAKE_RATE", 8, _I16), ("PHLD_BRAKE_ANGLE", 3000, _I16),
        ("LAND_REPOSITION", 1, _I8), ("FS_EKF_ACTION", 1, _I8), ("FS_EKF_THRESH", 0.8, _F),
        ("FS_CRASH_CHECK", 1, _I8), ("FS_VIBE_ENABLE", 1, _I8), ("RC_SPEED", 490, _I16),
        ("ACRO_TRAINER", 2, _I8), ("SCHED_LOOP_RATE", 400, _I16),
        # Arming
        ("ARMING_CHECK", 1, _I32), ("ARMING_REQUIRE", 1, _I8), ("ARMING_ACCTHRESH", 0.75, _F),
        ("ARMING_RUDDER", 2, _I8), ("ARMING_MIS_ITEMS", 0, _I32), ("ARMING_OPTIONS", 0, _I32),
        # Battery (analog power module on BATT_VOLT_PIN 2 / BATT_CURR_PIN 3)
        ("BATT_MONITOR", 4, _I8), ("BATT_VOLT_PIN", 2, _I8), ("BATT_CURR_PIN", 3, _I8),
        ("BATT_VOLT_MULT", 10.1, _F), ("BATT_AMP_PERVLT", 17.0, _F), ("BATT_AMP_OFFSET", 0, _F),
        ("BATT_CAPACITY", 5200, _I32), ("BATT_SERIAL_NUM", -1, _I32), ("BATT_LOW_TIMER", 10, _I8),
        ("BATT_FS_VOLTSRC", 0, _I8), ("BATT_LOW_VOLT", 14.4, _F), ("BATT_LOW_MAH", 1040, _F),
        ("BATT_CRT_VOLT", 14.0, _F), ("BATT_CRT_MAH", 520, _F), ("BATT_FS_LOW_ACT", 2, _I8),
        ("BATT_FS_CRT_ACT", 1, _I8), ("BATT_ARM_VOLT", 15.2, _F), ("BATT_ARM_MAH", 0, _I32),
        ("BATT_OPTIONS", 0, _I32),
        # Board
        ("BRD_SAFETY_DEFLT", 1, _I8), ("BRD_SAFETY_MASK", 0, _I32), ("BRD_VBUS_MIN", 4.3, _F),
        ("BRD_VSERVO_MIN", 0, _F), ("BRD_BOOT_DELAY", 0, _I16), ("BRD_OPTIONS", 1, _I32),
        # Compass (external, on the GPS mast)
        ("COMPASS_ENABLE", 1, _I8), ("COMPASS_USE", 1, _I8), ("COMPASS_USE2", 1, _I8),
        ("COMPASS_USE3", 1, _I8), ("COMPASS_EXTERNAL", 1, _I8), ("COMPASS_ORIENT", 0, _I8),
        ("COMPASS_AUTODEC", 1, _I8), ("COMPASS_LEARN", 0, _I8), ("COMPASS_OFS_X", -38.2, _F),
        ("COMPASS_OFS_Y", 12.7, _F), ("COMPASS_OFS_Z", 55.1, _F), ("COMPASS_DIA_X", 1.012, _F),
        ("COMPASS_DIA_Y", 0.994, _F), ("COMPASS_DIA_Z", 1.003, _F), ("COMPASS_ODI_X", 0.004, _F),
        ("COMPASS_ODI_Y", -0.011, _F), ("COMPASS_ODI_Z", 0.007, _F), ("COMPASS_SCALE", 1.0, _F),
        ("COMPASS_DEV_ID", 97539, _I32), ("COMPASS_DEV_ID2", 0, _I32), ("COMPASS_DEV_ID3", 0, _I32),
        ("COMPASS_PRIO1_ID", 97539, _I32), ("COMPASS_PRIO2_ID", 0, _I32), ("COMPASS_CAL_FIT", 16, _F),
        ("COMPASS_OFFS_MAX", 1800, _I16), ("COMPASS_MOTCT", 0, _I8),
        # IMU
        ("INS_GYROFFS_X", 0.0021, _F), ("INS_GYROFFS_Y", -0.0034, _F), ("INS_GYROFFS_Z", 0.0012, _F),
        ("INS_ACCOFFS_X", 0.052, _F), ("INS_ACCOFFS_Y", -0.118, _F), ("INS_ACCOFFS_Z", 0.207, _F),
        ("INS_ACCSCAL_X", 1.002, _F), ("INS_ACCSCAL_Y", 0.998, _F), ("INS_ACCSCAL_Z", 1.010, _F),
        ("INS_ACC2OFFS_X", 0.031, _F), ("INS_ACC2OFFS_Y", 0.044, _F), ("INS_ACC2OFFS_Z", -0.093, _F),
        ("INS_ACC2SCAL_X", 1.001, _F), ("INS_ACC2SCAL_Y", 1.003, _F), ("INS_ACC2SCAL_Z", 0.996, _F),
        ("INS_GYRO_FILTER", 20, _I16), ("INS_ACCEL_FILTER", 20, _I16), ("INS_USE", 1, _I8),
        ("INS_USE2", 1, _I8), ("INS_ACC_ID", 2753036, _I32), ("INS_GYR_ID", 2752780, _I32),
        ("INS_FAST_SAMPLE", 1, _I8), ("INS_HNTCH_ENABLE", 0, _I8), ("INS_ACC_BODYFIX", 2, _I8),
        # GPS
        ("GPS_TYPE", 1, _I8), ("GPS_TYPE2", 0, _I8), ("GPS_AUTO_SWITCH", 1, _I8),
        ("GPS_MIN_DGPS", 100, _I8), ("GPS_SBAS_MODE", 2, _I8), ("GPS_MIN_ELEV", -100, _I8),
        ("GPS_NAVFILTER", 8, _I8), ("GPS_AUTO_CONFIG", 1, _I8), ("GPS_GNSS_MODE", 0, _I8),
        ("GPS_RATE_MS", 200, _I16), ("GPS_SAVE_CFG", 2, _I8),
        # AHRS / EKF3
        ("AHRS_EKF_TYPE", 3, _I8), ("AHRS_ORIENTATION", 0, _I8), ("AHRS_GPS_USE", 1, _I8),
        ("AHRS_TRIM_X", 0.0, _F), ("AHRS_TRIM_Y", 0.0, _F), ("EK2_ENABLE", 0, _I8),
        ("EK3_ENABLE", 1, _I8), ("EK3_GPS_CHECK", 31, _I8), ("EK3_IMU_MASK", 3, _I8),
        ("EK3_SRC1_POSXY", 3, _I8), ("EK3_SRC1_VELXY", 3, _I8), ("EK3_SRC1_POSZ", 1, _I8),
        ("EK3_SRC1_VELZ", 3, _I8), ("EK3_SRC1_YAW", 1, _I8),
        # Fence
        ("FENCE_ENABLE", 1, _I8), ("FENCE_TYPE", 7, _I8), ("FENCE_ACTION", 1, _I8),
        ("FENCE_ALT_MAX", 100, _F), ("FENCE_ALT_MIN", -10, _F), ("FENCE_RADIUS", 300, _F),
        ("FENCE_MARGIN", 2, _F), ("FENCE_TOTAL", 0, _I8),
        # Logging
        ("LOG_BACKEND_TYPE", 1, _I8), ("LOG_FILE_BUFSIZE", 16, _I16), ("LOG_DISARMED", 0, _I8),
        ("LOG_REPLAY", 0, _I8), ("LOG_FILE_DSRMROT", 0, _I8),
        # Motors
        ("MOT_SPIN_ARM", 0.10, _F), ("MOT_SPIN_MIN", 0.15, _F), ("MOT_SPIN_MAX", 0.95, _F),
        ("MOT_PWM_TYPE", 0, _I8), ("MOT_PWM_MIN", 1000, _I16), ("MOT_PWM_MAX", 2000, _I16),
        ("MOT_THST_EXPO", 0.65, _F), ("MOT_THST_HOVER", 0.28, _F), ("MOT_HOVER_LEARN", 2, _I8),
        ("MOT_BAT_VOLT_MAX", 16.8, _F), ("MOT_BAT_VOLT_MIN", 13.2, _F), ("MOT_BAT_CURR_MAX", 0, _F),
        ("MOT_BAT_IDX", 0, _I8), ("MOT_YAW_HEADROOM", 200, _I16), ("MOT_SAFE_DISARM", 0, _I8),
        ("MOT_SAFE_TIME", 1.0, _F), ("MOT_SLEW_UP_TIME", 0, _F), ("MOT_SLEW_DN_TIME", 0, _F),
        ("MOT_SPOOL_TIME", 0.5, _F), ("MOT_BOOST_SCALE", 0, _F),
        # Servo outputs
        ("SERVO_RATE", 50, _I16), ("SERVO_DSHOT_ESC", 0, _I8), ("SERVO_BLH_MASK", 0, _I32),
        ("SERVO_BLH_AUTO", 0, _I8), ("SERVO_BLH_TRATE", 10, _I16),
        # RC
        ("RC_PROTOCOLS", 1, _I32), ("RC_OPTIONS", 32, _I32), ("RC_OVERRIDE_TIME", 3.0, _F),
        ("RC_FS_TIMEOUT", 1.0, _F), ("RSSI_TYPE", 3, _I8),
        # Serial ports: USB, TELEM1 (SiK radio), TELEM2, GPS1, GPS2
        ("SERIAL0_PROTOCOL", 2, _I8), ("SERIAL0_BAUD", 115, _I32),
        ("SERIAL1_PROTOCOL", 2, _I8), ("SERIAL1_BAUD", 57, _I32),
        ("SERIAL2_PROTOCOL", 2, _I8), ("SERIAL2_BAUD", 57, _I32),
        ("SERIAL3_PROTOCOL", 5, _I8), ("SERIAL3_BAUD", 38, _I32),
        ("SERIAL4_PROTOCOL", 5, _I8), ("SERIAL4_BAUD", 38, _I32),
        ("SR1_RAW_SENS", 2, _I16), ("SR1_EXT_STAT", 2, _I16), ("SR1_RC_CHAN", 2, _I16),
        ("SR1_POSITION", 2, _I16), ("SR1_EXTRA1", 4, _I16), ("SR1_EXTRA2", 4, _I16),
        ("SR1_EXTRA3", 2, _I16), ("SR1_PARAMS", 10, _I16),
        # Attitude / position controllers (4.5 defaults)
        ("ATC_ANG_RLL_P", 4.5, _F), ("ATC_ANG_PIT_P", 4.5, _F), ("ATC_ANG_YAW_P", 4.5, _F),
        ("ATC_RAT_RLL_P", 0.135, _F), ("ATC_RAT_RLL_I", 0.135, _F), ("ATC_RAT_RLL_D", 0.0036, _F),
        ("ATC_RAT_RLL_IMAX", 0.5, _F), ("ATC_RAT_RLL_FLTD", 20, _F), ("ATC_RAT_RLL_FLTT", 20, _F),
        ("ATC_RAT_PIT_P", 0.135, _F), ("ATC_RAT_PIT_I", 0.135, _F), ("ATC_RAT_PIT_D", 0.0036, _F),
        ("ATC_RAT_PIT_IMAX", 0.5, _F), ("ATC_RAT_PIT_FLTD", 20, _F), ("ATC_RAT_PIT_FLTT", 20, _F),
        ("ATC_RAT_YAW_P", 0.18, _F), ("ATC_RAT_YAW_I", 0.018, _F), ("ATC_RAT_YAW_D", 0.0, _F),
        ("ATC_RAT_YAW_IMAX", 0.5, _F), ("ATC_RAT_YAW_FLTE", 2.5, _F),
        ("ATC_ACCEL_R_MAX", 110000, _F), ("ATC_ACCEL_P_MAX", 110000, _F), ("ATC_ACCEL_Y_MAX", 27000, _F),
        ("ATC_INPUT_TC", 0.15, _F), ("ATC_THR_MIX_MAN", 0.1, _F), ("ATC_THR_MIX_MAX", 0.5, _F),
        ("ATC_THR_MIX_MIN", 0.1, _F),
        ("PSC_POSXY_P", 1.0, _F), ("PSC_VELXY_P", 2.0, _F), ("PSC_VELXY_I", 1.0, _F),
        ("PSC_VELXY_D", 0.5, _F), ("PSC_POSZ_P", 1.0, _F), ("PSC_VELZ_P", 5.0, _F),
        ("PSC_ACCZ_P", 0.5, _F), ("PSC_ACCZ_I", 1.0, _F), ("PSC_ACCZ_D", 0.0, _F),
        ("WPNAV_SPEED", 1000, _F), ("WPNAV_RADIUS", 200, _F), ("WPNAV_SPEED_UP", 250, _F),
        ("WPNAV_SPEED_DN", 150, _F), ("WPNAV_ACCEL", 250, _F), ("LOIT_SPEED", 1250, _F),
        ("LOIT_ACC_MAX", 500, _F), ("LOIT_BRK_ACCEL", 250, _F), ("LOIT_BRK_DELAY", 1.0, _F),
        ("LOIT_BRK_JERK", 500, _F), ("LOIT_ANG_MAX", 0, _F),
        ("NTF_BUZZ_TYPES", 1, _I8), ("NTF_LED_TYPES", 199, _I32), ("CAN_P1_DRIVER", 0, _I8),
    ]
    for n in range(1, 17):
        function = {1: 33, 2: 34, 3: 35, 4: 36}.get(n, 0)
        p += [
            (f"SERVO{n}_MIN", 1100, _I16), (f"SERVO{n}_MAX", 1900, _I16),
            (f"SERVO{n}_TRIM", 1500, _I16), (f"SERVO{n}_REVERSED", 0, _I8),
            (f"SERVO{n}_FUNCTION", function, _I16),
        ]
    for n in range(1, 17):
        trim = 1100 if n == 3 else 1500
        p += [
            (f"RC{n}_MIN", 1100, _I16), (f"RC{n}_MAX", 1900, _I16), (f"RC{n}_TRIM", trim, _I16),
            (f"RC{n}_REVERSED", 0, _I8), (f"RC{n}_DZ", 30 if n <= 4 else 0, _I16),
            (f"RC{n}_OPTION", 0, _I16),
        ]
    return p


_PROFILE_PARAM_OVERRIDES: Dict[str, Dict[str, float]] = {
    "healthy": {},
    "bench": {},
    "faulty": {
        # The ArduCopter defaults — "None" — so a low battery only warns.
        "BATT_FS_LOW_ACT": 0, "BATT_FS_CRT_ACT": 0,
        "BATT_LOW_VOLT": 10.5, "BATT_CRT_VOLT": 0, "BATT_LOW_MAH": 0, "BATT_CRT_MAH": 0,
        "BATT_CAPACITY": 3300, "BATT_ARM_VOLT": 0,
        # Above the DGCA 120 m (400 ft AGL) green-zone ceiling.
        "FENCE_ALT_MAX": 150,
        # No compass detected at all.
        "COMPASS_DEV_ID": 0, "COMPASS_PRIO1_ID": 0, "COMPASS_EXTERNAL": 0,
        "COMPASS_OFS_X": 0, "COMPASS_OFS_Y": 0, "COMPASS_OFS_Z": 0,
        # Wiring/config slip: output 3 duplicates Motor1, Motor3 has no output.
        "SERVO3_FUNCTION": 33,
        # Underpowered airframe (learned hover throttle above ~0.6).
        "MOT_THST_HOVER": 0.64,
        "FS_GCS_ENABLE": 0,
    },
}


@dataclasses.dataclass
class TelemetryProfile:
    cells_v: Tuple[float, ...]
    current_a: float
    gps_fix: int
    gps_sats: int
    gps_hdop: float
    vibe: Tuple[float, float, float]
    clip_rate_per_s: int
    compass_present: bool
    ekf_flags: int
    ekf_var: Tuple[float, float, float, float]  # velocity, pos_horiz, pos_vert, compass
    prearm_failures: Tuple[str, ...]
    vcc_mv: int
    esc_temp_c: int


_EKF_NOMINAL = (
    mavlink2.EKF_ATTITUDE | mavlink2.EKF_VELOCITY_HORIZ | mavlink2.EKF_VELOCITY_VERT
    | mavlink2.EKF_POS_HORIZ_REL | mavlink2.EKF_POS_HORIZ_ABS | mavlink2.EKF_POS_VERT_ABS
    | mavlink2.EKF_PRED_POS_HORIZ_REL | mavlink2.EKF_PRED_POS_HORIZ_ABS
)
_EKF_NO_GPS = (
    mavlink2.EKF_ATTITUDE | mavlink2.EKF_VELOCITY_VERT | mavlink2.EKF_POS_VERT_ABS
    | mavlink2.EKF_CONST_POS_MODE
)

TELEMETRY_PROFILES: Dict[str, TelemetryProfile] = {
    "healthy": TelemetryProfile(
        cells_v=(4.05, 4.06, 4.04, 4.05), current_a=0.85, gps_fix=3, gps_sats=14, gps_hdop=0.78,
        vibe=(2.1, 2.4, 3.8), clip_rate_per_s=0, compass_present=True, ekf_flags=_EKF_NOMINAL,
        ekf_var=(0.04, 0.03, 0.05, 0.02), prearm_failures=(), vcc_mv=5120, esc_temp_c=29,
    ),
    "faulty": TelemetryProfile(
        cells_v=(4.05, 4.04, 3.81, 4.06), current_a=0.92, gps_fix=3, gps_sats=12, gps_hdop=0.95,
        vibe=(44.0, 47.5, 52.3), clip_rate_per_s=3, compass_present=False, ekf_flags=_EKF_NOMINAL,
        ekf_var=(0.07, 0.06, 0.09, 0.0), prearm_failures=("PreArm: Compass not healthy",),
        vcc_mv=5080, esc_temp_c=31,
    ),
    "bench": TelemetryProfile(
        cells_v=(4.11, 4.10, 4.11, 4.10), current_a=0.64, gps_fix=1, gps_sats=3, gps_hdop=99.99,
        vibe=(0.6, 0.7, 1.1), clip_rate_per_s=0, compass_present=True, ekf_flags=_EKF_NO_GPS,
        ekf_var=(0.0, 0.0, 0.02, 0.03),
        prearm_failures=("PreArm: GPS 1: Bad fix", "PreArm: Fence requires position"),
        vcc_mv=5040, esc_temp_c=24,
    ),
}


class MockVehicle:
    def __init__(
        self, port: int = 14550, drone_id: Optional[str] = None, d2d_port: int = D2D_DEFAULT_PORT,
        profile: str = "healthy", enable_d2d: bool = True, lossy_params: bool = False,
        start_armed: bool = False,
    ):
        if profile not in PROFILES:
            raise ValueError(f"Unknown profile '{profile}' (expected one of {PROFILES})")
        self.conn = mavutil.mavlink_connection(
            f"udpout:127.0.0.1:{port}", source_system=1, source_component=1
        )
        self.profile_name = profile
        self.profile = TELEMETRY_PROFILES[profile]
        self.lat = START_LAT
        self.lon = START_LON
        self.alt_m = 0.0
        self.armed = start_armed
        self.mode = "STABILIZE"
        self.mode_map = mavutil.mode_mapping_acm
        self._gcs_system = 255
        self._gcs_component = 0
        self._running = True
        self._boot = time.time()
        self._send_lock = threading.Lock()
        self._lossy_params = lossy_params
        self._param_list_requests = 0

        self._param_order: List[str] = []
        self._params: Dict[str, float] = {}
        self._param_types: Dict[str, int] = {}
        for name, value, ptype in _base_params():
            self._param_order.append(name)
            self._params[name] = float(value)
            self._param_types[name] = ptype
        for name, value in _PROFILE_PARAM_OVERRIDES[profile].items():
            self._params[name] = float(value)

        self._clip = [0, 0, 0]
        self._esc_rpm = [0, 0, 0, 0]
        self._esc_count = [0, 0, 0, 0]
        self._motor_test_until = 0.0
        self._motor_test_outputs: List[int] = []
        self._motor_test_pwm = 1000
        self._last_prearm_broadcast = 0.0

        # D2D mesh state — separate from the MAVLink link above, which only
        # talks to this vehicle's own GCS/dispatch server, not to peers.
        self.drone_id = drone_id or f"MOCK-{port}"
        self.velocity_mps = 0.0
        self.heading_deg = 0.0
        self.battery_soc = 1.0
        self._d2d_port = d2d_port
        self._enable_d2d = enable_d2d
        if enable_d2d:
            from aerofleet.safety.d2d_mesh import D2DTransceiver

            self.d2d = D2DTransceiver(self.drone_id)
            self._d2d_send_sock = self._make_d2d_send_socket()
            self._d2d_recv_sock = self._make_d2d_recv_socket()

    # ─────────────────────────────────────────────────────────────────
    #  D2D mesh (unchanged behaviour; disabled with --no-d2d)
    # ─────────────────────────────────────────────────────────────────

    @staticmethod
    def _make_d2d_send_socket() -> socket.socket:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 1)
        return sock

    def _make_d2d_recv_socket(self) -> socket.socket:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        if hasattr(socket, "SO_REUSEPORT"):
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        sock.bind(("", self._d2d_port))
        mreq = struct.pack("4sl", socket.inet_aton(D2D_MULTICAST_GROUP), socket.INADDR_ANY)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        sock.settimeout(1.0)
        return sock

    def send_d2d_broadcast(self) -> None:
        from aerofleet.safety.d2d_mesh import D2DBasicSafetyMessage

        msg = D2DBasicSafetyMessage(
            drone_id=self.drone_id,
            timestamp_utc=time.time(),
            lat=self.lat,
            lon=self.lon,
            alt_m=self.alt_m,
            velocity_mps=self.velocity_mps,
            heading_deg=self.heading_deg,
            battery_soc=self.battery_soc,
            link_state=self.d2d.link_state.state.name,
        )
        payload = json.dumps(dataclasses.asdict(msg)).encode("utf-8")
        self._d2d_send_sock.sendto(payload, (D2D_MULTICAST_GROUP, self._d2d_port))

    def d2d_broadcast_loop(self) -> None:
        while self._running:
            try:
                self.send_d2d_broadcast()
            except OSError as exc:
                print(f"[mock] D2D broadcast send failed: {exc}")
            time.sleep(D2D_BROADCAST_INTERVAL_S)

    def d2d_receive_loop(self) -> None:
        from aerofleet.safety.d2d_mesh import D2DBasicSafetyMessage

        while self._running:
            try:
                data, _addr = self._d2d_recv_sock.recvfrom(4096)
            except socket.timeout:
                continue
            except OSError:
                break
            try:
                obj = json.loads(data.decode("utf-8"))
                self.d2d.receive(D2DBasicSafetyMessage(**obj))
            except (json.JSONDecodeError, TypeError, KeyError) as exc:
                print(f"[mock] Malformed D2D-BSM dropped: {exc}")

    # ─────────────────────────────────────────────────────────────────
    #  Telemetry
    # ─────────────────────────────────────────────────────────────────

    def _boot_ms(self) -> int:
        return int((time.time() - self._boot) * 1000) & 0xFFFFFFFF

    def _custom_mode_id(self) -> int:
        for mode_id, name in self.mode_map.items():
            if name == self.mode:
                return mode_id
        return 0

    def send_heartbeat(self) -> None:
        base_mode = mavlink2.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED | mavlink2.MAV_MODE_FLAG_STABILIZE_ENABLED
        if self.armed:
            base_mode |= mavlink2.MAV_MODE_FLAG_SAFETY_ARMED
        status = mavlink2.MAV_STATE_ACTIVE if self.armed else mavlink2.MAV_STATE_STANDBY
        with self._send_lock:
            self.conn.mav.heartbeat_send(
                mavlink2.MAV_TYPE_QUADROTOR, mavlink2.MAV_AUTOPILOT_ARDUPILOTMEGA,
                base_mode, self._custom_mode_id(), status,
            )

    def send_position(self) -> None:
        with self._send_lock:
            self.conn.mav.global_position_int_send(
                self._boot_ms(),
                int(self.lat * 1e7), int(self.lon * 1e7),
                int(self.alt_m * 1000), int(self.alt_m * 1000),
                0, 0, 0, 65535,
            )

    def _sensor_bits(self) -> Tuple[int, int, int]:
        m = mavlink2
        present = (
            m.MAV_SYS_STATUS_SENSOR_3D_GYRO | m.MAV_SYS_STATUS_SENSOR_3D_ACCEL
            | m.MAV_SYS_STATUS_SENSOR_ABSOLUTE_PRESSURE | m.MAV_SYS_STATUS_SENSOR_GPS
            | m.MAV_SYS_STATUS_SENSOR_ANGULAR_RATE_CONTROL | m.MAV_SYS_STATUS_SENSOR_ATTITUDE_STABILIZATION
            | m.MAV_SYS_STATUS_SENSOR_YAW_POSITION | m.MAV_SYS_STATUS_SENSOR_Z_ALTITUDE_CONTROL
            | m.MAV_SYS_STATUS_SENSOR_XY_POSITION_CONTROL | m.MAV_SYS_STATUS_SENSOR_MOTOR_OUTPUTS
            | m.MAV_SYS_STATUS_SENSOR_RC_RECEIVER | m.MAV_SYS_STATUS_AHRS | m.MAV_SYS_STATUS_LOGGING
            | m.MAV_SYS_STATUS_SENSOR_BATTERY | m.MAV_SYS_STATUS_GEOFENCE | m.MAV_SYS_STATUS_PREARM_CHECK
        )
        if self.profile.compass_present:
            present |= m.MAV_SYS_STATUS_SENSOR_3D_MAG
        enabled = present
        health = present
        if self.profile.gps_fix < 3:
            health &= ~m.MAV_SYS_STATUS_SENSOR_GPS
        if self.profile.prearm_failures:
            health &= ~m.MAV_SYS_STATUS_PREARM_CHECK
        if self.profile.compass_present is False and self._params.get("COMPASS_USE", 0):
            # ArduPilot marks the mag enabled-but-missing as not healthy.
            enabled |= m.MAV_SYS_STATUS_SENSOR_3D_MAG
        return present, enabled, health

    def _pack_voltage_mv(self) -> int:
        return int(round(sum(self.profile.cells_v) * 1000))

    def send_sys_status(self) -> None:
        present, enabled, health = self._sensor_bits()
        with self._send_lock:
            self.conn.mav.sys_status_send(
                present, enabled, health, 212, self._pack_voltage_mv(),
                int(self._current_a() * 100), 96, 0, 0, 0, 0, 0, 0,
            )

    def _current_a(self) -> float:
        extra = 3.5 if time.time() < self._motor_test_until else 0.0
        return self.profile.current_a + extra

    def send_battery_status(self) -> None:
        cells = [int(round(v * 1000)) for v in self.profile.cells_v]
        voltages = cells + [65535] * (10 - len(cells))
        with self._send_lock:
            self.conn.mav.battery_status_send(
                0, mavlink2.MAV_BATTERY_FUNCTION_ALL, mavlink2.MAV_BATTERY_TYPE_LIPO, 32767,
                voltages, int(self._current_a() * 100), 38, -1, 96,
            )

    def send_gps(self) -> None:
        p = self.profile
        with self._send_lock:
            self.conn.mav.gps_raw_int_send(
                int(time.time() * 1e6), p.gps_fix, int(self.lat * 1e7), int(self.lon * 1e7),
                int(self.alt_m * 1000) + 560000, int(p.gps_hdop * 100), int(p.gps_hdop * 150),
                0, 65535, p.gps_sats,
            )

    def send_ekf_status(self) -> None:
        v = self.profile.ekf_var
        with self._send_lock:
            self.conn.mav.ekf_status_report_send(self.profile.ekf_flags, v[0], v[1], v[2], v[3], 0.0)

    def send_vibration(self, dt_s: float) -> None:
        rate = self.profile.clip_rate_per_s
        if rate:
            self._clip = [c + max(1, int(round(rate * dt_s))) for c in self._clip]
        vx, vy, vz = self.profile.vibe
        with self._send_lock:
            self.conn.mav.vibration_send(int(time.time() * 1e6), vx, vy, vz, *self._clip)

    def send_rc_channels(self) -> None:
        chans = [1500, 1500, 1100, 1500, 1165, 1500, 1100, 1100] + [1500] * 8 + [65535, 65535]
        with self._send_lock:
            self.conn.mav.rc_channels_send(self._boot_ms(), 16, *chans, 212)

    def _motor_output_pwm(self) -> List[int]:
        out = []
        testing = time.time() < self._motor_test_until
        for n in range(1, 17):
            fn = int(self._params.get(f"SERVO{n}_FUNCTION", 0))
            if 33 <= fn <= 40:
                pwm = self._motor_test_pwm if testing and n in self._motor_test_outputs else 1000
                out.append(pwm)
            else:
                out.append(0)
        return out

    def send_servo_output(self) -> None:
        pwm = self._motor_output_pwm()
        with self._send_lock:
            self.conn.mav.servo_output_raw_send(int(time.time() * 1e6) & 0xFFFFFFFF, 0, *pwm)

    def send_esc_telemetry(self) -> None:
        testing = time.time() < self._motor_test_until
        rpm = []
        for i in range(4):
            target = self._esc_rpm[i] if testing and (i + 1) in self._motor_test_outputs else 0
            rpm.append(target)
            self._esc_count[i] = (self._esc_count[i] + 1) & 0xFFFF
        pack_cv = int(sum(self.profile.cells_v) * 100)
        temps = [self.profile.esc_temp_c + (4 if r else 0) for r in rpm]
        currents = [320 if r else 0 for r in rpm]
        with self._send_lock:
            self.conn.mav.esc_telemetry_1_to_4_send(
                temps, [pack_cv] * 4, currents, [0, 0, 0, 0], rpm, list(self._esc_count),
            )

    def send_power_status(self) -> None:
        flags = mavlink2.MAV_POWER_STATUS_BRICK_VALID | mavlink2.MAV_POWER_STATUS_USB_CONNECTED
        with self._send_lock:
            self.conn.mav.power_status_send(self.profile.vcc_mv, 0, flags)

    def send_radio_status(self) -> None:
        with self._send_lock:
            self.conn.mav.radio_status_send(182, 176, 100, 44, 47, 0, 0)

    def send_statustext(self, text: str, severity: int = mavlink2.MAV_SEVERITY_CRITICAL) -> None:
        with self._send_lock:
            self.conn.mav.statustext_send(severity, text.encode("ascii")[:50])

    def broadcast_prearm_failures(self) -> None:
        for text in self.profile.prearm_failures:
            self.send_statustext(text)

    def telemetry_loop(self) -> None:
        tick = 0
        period = 0.25
        while self._running:
            if tick % 4 == 0:
                self.send_heartbeat()
                self.send_position()
                self.send_sys_status()
                self.send_power_status()
                self.send_radio_status()
            if tick % 2 == 0:
                self.send_gps()
                self.send_battery_status()
                self.send_ekf_status()
                self.send_vibration(period * 2)
                self.send_rc_channels()
            self.send_servo_output()
            self.send_esc_telemetry()
            # ArduPilot repeats failing PreArm reasons every 30 s while disarmed.
            if not self.armed and time.time() - self._last_prearm_broadcast > 30.0:
                self._last_prearm_broadcast = time.time()
                self.broadcast_prearm_failures()
            tick += 1
            time.sleep(period)

    # ─────────────────────────────────────────────────────────────────
    #  Parameters
    # ─────────────────────────────────────────────────────────────────

    def _send_param(self, name: str) -> None:
        idx = self._param_order.index(name)
        with self._send_lock:
            self.conn.mav.param_value_send(
                name.encode("ascii"), self._params[name], self._param_types[name],
                len(self._param_order), idx,
            )

    def _handle_param_request_list(self) -> None:
        self._param_list_requests += 1
        drop_first_pass = self._lossy_params and self._param_list_requests == 1
        print(f"[mock] PARAM_REQUEST_LIST -> streaming {len(self._param_order)} params"
              + (" (lossy: dropping some on this pass)" if drop_first_pass else ""))
        for i, name in enumerate(self._param_order):
            if drop_first_pass and i % 29 == 7:
                continue
            self._send_param(name)
            if i % 25 == 24:
                time.sleep(0.004)

    def _handle_param_request_read(self, msg) -> None:
        name = msg.param_id.rstrip("\x00") if isinstance(msg.param_id, str) else msg.param_id
        if msg.param_index >= 0:
            if msg.param_index < len(self._param_order):
                self._send_param(self._param_order[msg.param_index])
        elif name in self._params:
            self._send_param(name)

    def _handle_param_set(self, msg) -> None:
        name = msg.param_id.rstrip("\x00")
        print(f"[mock] PARAM_SET {name} = {msg.param_value}")
        if name not in self._params:
            self._param_order.append(name)
            self._param_types[name] = msg.param_type or _F
        self._params[name] = float(msg.param_value)
        self._send_param(name)

    # ─────────────────────────────────────────────────────────────────
    #  Commands
    # ─────────────────────────────────────────────────────────────────

    def command_loop(self) -> None:
        while self._running:
            msg = self.conn.recv_match(blocking=True, timeout=1.0)
            if msg is None:
                continue
            t = msg.get_type()
            if t == "BAD_DATA":
                continue
            self._gcs_system = msg.get_srcSystem()
            self._gcs_component = msg.get_srcComponent()
            if t == "COMMAND_LONG":
                self._handle_command_long(msg)
            elif t == "SET_MODE":
                self._handle_set_mode(msg)
            elif t == "MISSION_COUNT":
                self._handle_mission_count(msg)
            elif t == "PARAM_REQUEST_LIST":
                self._handle_param_request_list()
            elif t == "PARAM_REQUEST_READ":
                self._handle_param_request_read(msg)
            elif t == "PARAM_SET":
                self._handle_param_set(msg)
            elif t == "SET_POSITION_TARGET_GLOBAL_INT":
                self.lat = msg.lat_int / 1e7
                self.lon = msg.lon_int / 1e7
                print(f"[mock] GOTO setpoint ({self.lat:.6f}, {self.lon:.6f})")

    def _ack(self, command: int, result: int) -> None:
        with self._send_lock:
            self.conn.mav.command_ack_send(command, result)

    def _send_autopilot_version(self) -> None:
        m = mavlink2
        caps = (
            m.MAV_PROTOCOL_CAPABILITY_MISSION_FLOAT | m.MAV_PROTOCOL_CAPABILITY_PARAM_FLOAT
            | m.MAV_PROTOCOL_CAPABILITY_MISSION_INT | m.MAV_PROTOCOL_CAPABILITY_COMMAND_INT
            | m.MAV_PROTOCOL_CAPABILITY_SET_POSITION_TARGET_GLOBAL_INT
            | m.MAV_PROTOCOL_CAPABILITY_FTP | m.MAV_PROTOCOL_CAPABILITY_MAVLINK2
            | m.MAV_PROTOCOL_CAPABILITY_MISSION_FENCE | m.MAV_PROTOCOL_CAPABILITY_MISSION_RALLY
        )
        # ArduPilot packs (major<<24)|(minor<<16)|(patch<<8)|FIRMWARE_VERSION_TYPE.
        flight_sw = (4 << 24) | (5 << 16) | (7 << 8) | m.FIRMWARE_VERSION_TYPE_OFFICIAL
        board_version = 9 << 16  # APJ board id 9 (fmuv3 / Pixhawk1-class) in the high 16 bits
        with self._send_lock:
            self.conn.mav.autopilot_version_send(
                caps, flight_sw, 0, (21 << 24) | (2 << 16), board_version,
                list(b"2a3dc4b7"), [0] * 8, list(b"c3f7b2e1"),
                0x1209, 0x5740, 0x0034003D32385107, list(range(18)),
            )

    def _handle_command_long(self, msg) -> None:
        cmd = msg.command
        m = mavlink2
        if cmd == m.MAV_CMD_COMPONENT_ARM_DISARM:
            self.armed = bool(msg.param1)
            print(f"[mock] {'ARMED' if self.armed else 'DISARMED'}")
            self._ack(cmd, m.MAV_RESULT_ACCEPTED)
        elif cmd == m.MAV_CMD_NAV_TAKEOFF:
            self.alt_m = msg.param7
            self.mode = "GUIDED"
            print(f"[mock] TAKEOFF -> {self.alt_m}m")
            self._ack(cmd, m.MAV_RESULT_ACCEPTED)
        elif cmd == m.MAV_CMD_NAV_RETURN_TO_LAUNCH:
            self.mode = "RTL"
            print("[mock] RTL")
            self._ack(cmd, m.MAV_RESULT_ACCEPTED)
        elif cmd == m.MAV_CMD_NAV_LAND:
            self.mode = "LAND"
            self.alt_m = 0.0
            print("[mock] LAND")
            self._ack(cmd, m.MAV_RESULT_ACCEPTED)
        elif cmd == m.MAV_CMD_REQUEST_MESSAGE:
            if int(msg.param1) == m.MAVLINK_MSG_ID_AUTOPILOT_VERSION:
                self._ack(cmd, m.MAV_RESULT_ACCEPTED)
                self._send_autopilot_version()
            else:
                self._ack(cmd, m.MAV_RESULT_ACCEPTED)
        elif cmd == m.MAV_CMD_REQUEST_AUTOPILOT_CAPABILITIES:
            self._ack(cmd, m.MAV_RESULT_ACCEPTED)
            self._send_autopilot_version()
        elif cmd == m.MAV_CMD_SET_MESSAGE_INTERVAL:
            self._ack(cmd, m.MAV_RESULT_ACCEPTED)
        elif cmd == m.MAV_CMD_RUN_PREARM_CHECKS:
            if self.armed:
                self._ack(cmd, m.MAV_RESULT_TEMPORARILY_REJECTED)
                return
            self._ack(cmd, m.MAV_RESULT_ACCEPTED)
            self.broadcast_prearm_failures()
        elif cmd == m.MAV_CMD_DO_MOTOR_TEST:
            self._handle_motor_test(msg)
        else:
            self._ack(cmd, m.MAV_RESULT_ACCEPTED)

    def _handle_motor_test(self, msg) -> None:
        m = mavlink2
        if self.armed:
            print("[mock] Motor test refused: vehicle armed")
            self.send_statustext("Motor Test: vehicle not landed", m.MAV_SEVERITY_CRITICAL)
            self._ack(msg.command, m.MAV_RESULT_FAILED)
            return
        seq = int(msg.param1)
        throttle_type = int(msg.param2)
        throttle = float(msg.param3)
        timeout_s = min(float(msg.param4), 600.0)  # MOTOR_TEST_TIMEOUT_SEC in motor_test.cpp
        frame = (int(self._params["FRAME_CLASS"]), int(self._params["FRAME_TYPE"]))
        order = _TEST_ORDER_TO_MOTOR.get(frame, {})
        motor_number = order.get(seq)
        if motor_number is None or throttle_type != m.MOTOR_TEST_THROTTLE_PERCENT:
            self._ack(msg.command, m.MAV_RESULT_FAILED)
            return
        # ArduPilot drives every output whose SERVOn_FUNCTION is this motor —
        # a duplicated function spins two outputs, a missing one spins none.
        outputs = [n for n in range(1, 17)
                   if int(self._params.get(f"SERVO{n}_FUNCTION", 0)) == 32 + motor_number]
        pwm_min, pwm_max = self._params["MOT_PWM_MIN"], self._params["MOT_PWM_MAX"]
        self._motor_test_pwm = int(pwm_min + (pwm_max - pwm_min) * throttle / 100.0)
        rpm = int(920 * sum(self.profile.cells_v) * max(0.18, throttle / 100.0))  # 920 KV motor
        for n in outputs:
            if n <= 4:
                self._esc_rpm[n - 1] = rpm
        self._motor_test_outputs = outputs
        self._motor_test_until = time.time() + timeout_s
        print(f"[mock] MOTOR TEST seq {seq} -> Motor{motor_number} outputs {outputs} "
              f"{throttle:.0f}% for {timeout_s:.1f}s")
        self._ack(msg.command, m.MAV_RESULT_ACCEPTED)

    def _handle_set_mode(self, msg) -> None:
        name = self.mode_map.get(msg.custom_mode)
        if name:
            self.mode = name
            print(f"[mock] MODE -> {name}")

    def _handle_mission_count(self, msg) -> None:
        count = msg.count
        print(f"[mock] Mission upload starting, {count} items")
        received = 0
        while received < count:
            with self._send_lock:
                self.conn.mav.mission_request_int_send(self._gcs_system, self._gcs_component, received)
            item = self.conn.recv_match(type=["MISSION_ITEM_INT", "MISSION_ITEM"], blocking=True, timeout=3.0)
            if item is None:
                break
            received += 1
        with self._send_lock:
            self.conn.mav.mission_ack_send(self._gcs_system, self._gcs_component, mavlink2.MAV_MISSION_ACCEPTED)
        print(f"[mock] Mission upload complete ({received}/{count})")

    def run(self) -> None:
        print(
            f"[mock] Fake ArduCopter '{self.drone_id}' (profile={self.profile_name}) running — "
            f"sending MAVLink2 telemetry, waiting for GCS commands"
            + (f", broadcasting D2D-BSMs on {D2D_MULTICAST_GROUP}:{self._d2d_port}" if self._enable_d2d else "")
            + "...",
            flush=True,
        )
        threading.Thread(target=self.telemetry_loop, daemon=True).start()
        threading.Thread(target=self.command_loop, daemon=True).start()
        if self._enable_d2d:
            threading.Thread(target=self.d2d_broadcast_loop, daemon=True).start()
            threading.Thread(target=self.d2d_receive_loop, daemon=True).start()
        try:
            while True:
                time.sleep(5)
                if self._enable_d2d:
                    peers = self.d2d.known_peers()
                    print(f"[mock] [{self.drone_id}] D2D link={self.d2d.link_state.state.name} "
                          f"peers={[p.drone_id for p in peers]}")
        except KeyboardInterrupt:
            self._running = False


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--port", type=int, default=14550)
    parser.add_argument("--drone-id", type=str, default=None, help="Defaults to MOCK-<port>")
    parser.add_argument("--d2d-port", type=int, default=D2D_DEFAULT_PORT)
    parser.add_argument("--no-d2d", action="store_true", help="Disable the D2D multicast mesh stand-in")
    parser.add_argument("--profile", choices=PROFILES, default="healthy")
    parser.add_argument("--lossy-params", action="store_true",
                        help="Drop some PARAM_VALUEs on the first PARAM_REQUEST_LIST (exercises GCS retry)")
    parser.add_argument("--start-armed", action="store_true",
                        help="Report ARMED from the first heartbeat (exercises 'refuse when armed' gates)")
    args = parser.parse_args()
    MockVehicle(
        port=args.port, drone_id=args.drone_id, d2d_port=args.d2d_port, profile=args.profile,
        enable_d2d=not args.no_d2d, lossy_params=args.lossy_params, start_armed=args.start_armed,
    ).run()


if __name__ == "__main__":
    main()
