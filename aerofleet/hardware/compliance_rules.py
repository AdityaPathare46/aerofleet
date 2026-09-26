"""Flight-controller compliance rules — a data-driven table evaluated
against one immutable :class:`~aerofleet.hardware.fc_inspector.FCSnapshot`.

Every check carries: id, category, title, requirement, status, evidence
(the actual values read), fix, and a source URL (plus a short reference
naming the exact parameter/section). Status is one of

* ``PASS``    — measured over MAVLink and meets the requirement
* ``WARN``    — measured; works but is outside guidance / worth attention
* ``FAIL``    — measured; does not meet the requirement
* ``UNKNOWN`` — the data needed was not received (never guessed)
* ``MANUAL``  — cannot be sensed over MAVLink at all; a person must check it

Honesty rules this module follows: a check only returns PASS from values it
actually read; a missing parameter or message is UNKNOWN; physical and
paperwork items are MANUAL and stay MANUAL even when an operator ticks
them (the tick is recorded as an attestation, not converted into a PASS).
An operator marking a manual item as failed turns it into FAIL.

Thresholds are ArduPilot's own where ArduPilot documents one (URL in
``source``). Where it doesn't, the threshold is labelled as an AeroFleet
guideline in ``reference`` rather than attributed to ArduPilot.

``build_report()`` is pure and deterministic: the API rebuilds the report
from the stored snapshot + operator checklist + motor-test records every
time either changes, so there is a single source of truth.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Mapping, Optional, Tuple

from aerofleet.hardware.fc_inspector import FCSnapshot
from aerofleet.hardware.motor_layouts import (
    FRAME_CLASS_MOTOR_COUNT,
    FRAME_CLASS_NAMES,
    FRAME_TYPE_NAMES,
    layout_for_frame,
)

PASS, WARN, FAIL, MANUAL, UNKNOWN = "PASS", "WARN", "FAIL", "MANUAL", "UNKNOWN"
STATUSES = (PASS, WARN, FAIL, MANUAL, UNKNOWN)

CATEGORIES: Tuple[Tuple[str, str], ...] = (
    ("flight_controller", "Flight controller & firmware"),
    ("battery", "Battery & power"),
    ("motors", "Motors & ESCs"),
    ("airframe", "Airframe & design"),
    ("wiring", "Wiring & sensors"),
    ("failsafes", "Failsafes"),
    ("dgca", "DGCA regulatory"),
)
CATEGORY_TITLES = dict(CATEGORIES)

# ── Sources ──────────────────────────────────────────────────────────────
AP = "https://ardupilot.org/copter/docs/"
SRC_PREARM = AP + "common-prearm-safety-checks.html"
SRC_PARAMS = AP + "parameters-Copter-stable-V4.5.7.html"
SRC_VIBE = AP + "common-measuring-vibration.html"
SRC_BATT_FS = AP + "failsafe-battery.html"
SRC_TUNING_SETUP = AP + "setting-up-for-tuning.html"
SRC_POWER_MODULE = AP + "common-power-module-configuration-in-mission-planner.html"
SRC_EKF_FS = AP + "common-ekf-inav-failsafe.html"
SRC_FENCE = AP + "common-ac2_simple_geofence.html"
SRC_RADIO_FS = AP + "radio-failsafe.html"
SRC_GCS_FS = AP + "gcs-failsafe.html"
SRC_CRASH = AP + "crash_check.html"
SRC_RTL = AP + "rtl-mode.html"
SRC_HOVER = AP + "ac_throttlemid.html"
SRC_MOTORS = AP + "connect-escs-and-motors.html"
SRC_MOTOR_RANGE = AP + "set-motor-range.html"
SRC_DSHOT = AP + "common-dshot-escs.html"
SRC_ESC_TELEM = AP + "common-esc-telemetry.html"
SRC_ACCEL_CAL = AP + "common-accelerometer-calibration.html"
SRC_COMPASS_CAL = AP + "common-compass-calibration-in-mission-planner.html"
SRC_COMPASS_ADV = AP + "common-compass-setup-advanced.html"
SRC_GPS = AP + "common-gps-how-it-works.html"
SRC_LOGS = AP + "common-logs.html"
SRC_MAV_SYS_STATUS = "https://mavlink.io/en/messages/common.html#SYS_STATUS"
SRC_MAV_FW_TYPE = "https://mavlink.io/en/messages/common.html#FIRMWARE_VERSION_TYPE"
SRC_MAV_RADIO = "https://mavlink.io/en/messages/common.html#RADIO_STATUS"
SRC_MAV_HEARTBEAT = "https://mavlink.io/en/messages/common.html#HEARTBEAT"
SRC_DRONE_RULES = "https://www.civilaviation.gov.in/ministry-documents/rules/drones-rules-2021-dated-25-august-2021"
SRC_DIGITAL_SKY = "https://digitalsky.dgca.gov.in/"

# ── Thresholds (each tagged with where it comes from) ────────────────────
VIBE_OK_MS2 = 30.0            # ArduPilot: "below 30m/s/s are normally acceptable"
VIBE_BAD_MS2 = 60.0           # ArduPilot: "above 60m/s/s nearly always have problems"
EKF_THRESH_DEFAULT = 0.8      # FS_EKF_THRESH default ("0.8=Default")
BOARD_V_MIN, BOARD_V_MAX = 4.3, 5.8   # ArduPilot PreArm "Board (Xv) out of range 4.3-5.8v"
BOARD_V_WARN_LO, BOARD_V_WARN_HI = 4.8, 5.4  # AeroFleet margin, not an ArduPilot limit
LIPO_CELL_MAX = 4.2           # ArduPilot tuning setup: "4.2v x No. Cells for standard LiPos"
LIPO_CELL_MIN = 3.3           # ArduPilot tuning setup: "3.3v x No. Cells for standard LiPos"
CELL_REST_MIN = 3.5           # AeroFleet pre-flight guideline (resting, before take-off)
CELL_IMBALANCE_MAX = 0.10     # AeroFleet pre-flight guideline
HOVER_TYPICAL_MAX = 0.6       # ArduPilot: "usually between 0.2 and 0.6"
HOVER_DEFAULT = 0.35          # MOT_THST_HOVER firmware default (not yet learned)
DGCA_MAX_ALT_M = 120.0        # Drone Rules 2021: green zone = up to 400 ft AGL
FS_THR_VALUE_MIN = 910        # ArduPilot PreArm: "Set FS_THR_VALUE between 910 and RC throttle's min"
ESC_IDLE_TEMP_WARN_C = 60     # AeroFleet heuristic: a disarmed ESC should be near ambient
IDLE_CURRENT_WARN_A = 10.0    # AeroFleet heuristic: disarmed draw above this suggests a fault/miscalibration

_MOTOR_FUNCTIONS = {33 + i: i + 1 for i in range(8)} | {82 + i: 9 + i for i in range(4)}

BATT_MONITOR_NAMES = {
    0: "Disabled", 3: "Analog voltage only", 4: "Analog voltage and current", 5: "Solo",
    6: "Bebop", 7: "SMBus-Generic", 8: "DroneCAN-BatteryInfo", 9: "ESC", 10: "Sum of selected monitors",
    11: "FuelFlow", 12: "FuelLevelPWM", 13: "SMBUS-SUI3", 14: "SMBUS-SUI6", 15: "NeoDesign",
    16: "SMBus-Maxell", 17: "Generator-Elec", 18: "Generator-Fuel", 19: "Rotoye", 20: "MPPT",
    21: "INA2XX", 22: "LTC2946", 23: "Torqeedo", 24: "FuelLevelAnalog", 25: "Synthetic Current and Analog Voltage",
    26: "INA239_SPI", 27: "EFI", 28: "AD7091R5", 29: "Scripting",
}
# @Values{Copter} of BATT_FS_LOW_ACT / BATT_FS_CRT_ACT (Copter battery failsafe page).
BATT_FS_ACTIONS = {
    0: "None (warn only)", 1: "Land", 2: "RTL", 3: "SmartRTL or RTL", 4: "SmartRTL or Land",
    5: "Terminate", 6: "Auto DO_LAND_START or RTL", 7: "Brake or Land",
}
MOT_PWM_TYPES = {
    0: "Normal", 1: "OneShot", 2: "OneShot125", 3: "Brushed", 4: "DShot150", 5: "DShot300",
    6: "DShot600", 7: "DShot1200", 8: "PWMRange", 9: "PWMAngle",
}
_COPTER_MAV_TYPES = {2: "Quadrotor", 3: "Coaxial", 4: "Helicopter", 13: "Hexarotor", 14: "Octorotor",
                     15: "Tricopter", 29: "Dodecarotor", 35: "Decarotor"}
_AUTOPILOTS = {3: "ArduPilot", 12: "PX4"}

# SYS_STATUS sensor bits (MAV_SYS_STATUS_SENSOR)
BIT_GYRO, BIT_ACCEL, BIT_MAG, BIT_BARO, BIT_GPS = 1, 2, 4, 8, 32
BIT_RC, BIT_AHRS, BIT_LOGGING, BIT_BATTERY, BIT_PREARM = 65536, 2097152, 16777216, 33554432, 268435456

# EKF_STATUS_FLAGS
EKF_ATTITUDE, EKF_CONST_POS_MODE, EKF_UNINITIALIZED, EKF_GPS_GLITCHING = 1, 128, 1024, 32768

_BENCH_PREARM_MARKERS = ("gps", "position", "fence requires", "ekf", "ahrs", "hdop", "satellite")


# ─────────────────────────────────────────────────────────────────────────
#  Inputs
# ─────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class InspectionContext:
    """What AeroFleet knows about the aircraft beyond the flight controller."""
    bench_mode: bool = False          # indoor bench check: no GPS fix expected
    drone_id: Optional[str] = None
    uin: Optional[str] = None
    weight_kg: Optional[float] = None
    weight_source: Optional[str] = None
    payload_kg: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "bench_mode": self.bench_mode, "drone_id": self.drone_id, "uin": self.uin,
            "weight_kg": self.weight_kg, "weight_source": self.weight_source, "payload_kg": self.payload_kg,
        }

    @classmethod
    def from_dict(cls, d: Optional[Mapping[str, Any]]) -> "InspectionContext":
        d = d or {}
        return cls(
            bench_mode=bool(d.get("bench_mode", False)), drone_id=d.get("drone_id"), uin=d.get("uin"),
            weight_kg=d.get("weight_kg"), weight_source=d.get("weight_source"),
            payload_kg=float(d.get("payload_kg") or 0.0),
        )


@dataclass(frozen=True)
class Outcome:
    status: str
    evidence: Dict[str, Any] = field(default_factory=dict)
    detail: str = ""


class _Missing(Exception):
    def __init__(self, what: str):
        super().__init__(what)
        self.what = what


class Facts:
    """Read-only accessors over a snapshot that raise _Missing instead of
    guessing, so every rule gets UNKNOWN for free when data is absent."""

    def __init__(self, snap: FCSnapshot, ctx: InspectionContext,
                 motor_test: Optional[Mapping[str, Any]] = None):
        self.snap = snap
        self.ctx = ctx
        self.motor_test = motor_test or {}

    @property
    def has_params(self) -> bool:
        return bool(self.snap.params)

    def p(self, name: str) -> float:
        if not self.snap.params:
            raise _Missing("parameters were not downloaded")
        if name not in self.snap.params:
            raise _Missing(f"parameter {name} was not reported")
        return float(self.snap.params[name])

    def p_opt(self, name: str, default: Optional[float] = None) -> Optional[float]:
        v = self.snap.params.get(name)
        return float(v) if v is not None else default

    def p_first(self, *names: str) -> Tuple[str, float]:
        for n in names:
            if n in self.snap.params:
                return n, float(self.snap.params[n])
        if not self.snap.params:
            raise _Missing("parameters were not downloaded")
        raise _Missing(f"none of {', '.join(names)} was reported")

    def tel(self, name: str) -> Mapping[str, Any]:
        t = self.snap.telemetry.get(name)
        if t is None:
            raise _Missing(f"no {name} message received in {self.snap.sample_seconds:.0f}s")
        return t

    def tel_opt(self, name: str) -> Optional[Mapping[str, Any]]:
        return self.snap.telemetry.get(name)

    def sensor(self, bit: int) -> Tuple[bool, bool, bool]:
        s = self.tel("SYS_STATUS")
        return (bool(s["onboard_control_sensors_present"] & bit),
                bool(s["onboard_control_sensors_enabled"] & bit),
                bool(s["onboard_control_sensors_health"] & bit))

    def prearm_matching(self, *needles: str) -> List[str]:
        out = []
        for m in self.snap.prearm_messages:
            low = m.lower()
            if all(n in low for n in needles):
                out.append(m)
        return out

    # Battery helpers ----------------------------------------------------
    def battery_cells(self) -> Tuple[Optional[float], List[float], str]:
        """(pack volts, per-cell volts or [], source description)."""
        bs = self.tel_opt("BATTERY_STATUS")
        if bs is not None:
            raw = [v for v in list(bs.get("voltages") or []) if v not in (65535, None)]
            raw += [v for v in list(bs.get("voltages_ext") or []) if v not in (0, 65535, None)]
            if raw:
                if any(v > 4500 for v in raw):
                    # ArduPilot puts the pack total in voltages[0] when the
                    # monitor has no cell data — not a cell reading.
                    return sum(raw) / 1000.0, [], "BATTERY_STATUS (pack voltage only)"
                return sum(raw) / 1000.0, [v / 1000.0 for v in raw], "BATTERY_STATUS per-cell voltages"
        ss = self.tel_opt("SYS_STATUS")
        if ss is not None and ss.get("voltage_battery") not in (None, 65535, -1):
            return ss["voltage_battery"] / 1000.0, [], "SYS_STATUS voltage_battery"
        raise _Missing("no BATTERY_STATUS or SYS_STATUS battery voltage received")

    def cell_count(self) -> Tuple[Optional[int], str]:
        try:
            pack, cells, _ = self.battery_cells()
        except _Missing:
            return None, "unknown"
        if cells:
            return len(cells), "reported per cell"
        if pack and pack > 1.0:
            return int(math.ceil(pack / 4.25)), "inferred from pack voltage (ceil(V / 4.25 V))"
        return None, "unknown"


Evaluator = Callable[[Facts], Outcome]


@dataclass(frozen=True)
class Rule:
    id: str
    category: str
    title: str
    requirement: str
    fix: str
    source: str
    reference: str = ""
    evaluate: Optional[Evaluator] = None     # None => MANUAL checklist item
    required: bool = True                    # UNKNOWN on a non-required check doesn't block the verdict

    @property
    def manual(self) -> bool:
        return self.evaluate is None


RULES: List[Rule] = []


def rule(id: str, category: str, title: str, requirement: str, fix: str, source: str,
         reference: str = "", required: bool = True):
    def deco(fn: Evaluator) -> Evaluator:
        RULES.append(Rule(id, category, title, requirement, fix, source, reference, fn, required))
        return fn
    return deco


def manual(id: str, category: str, title: str, requirement: str, fix: str, source: str, reference: str = "") -> None:
    RULES.append(Rule(id, category, title, requirement, fix, source, reference, None, True))


def _o(status: str, detail: str = "", **evidence: Any) -> Outcome:
    return Outcome(status, evidence, detail)


def _r(x: Optional[float], nd: int = 2) -> Optional[float]:
    return None if x is None else round(float(x), nd)


# ═════════════════════════════════════════════════════════════════════════
#  Flight controller & firmware
# ═════════════════════════════════════════════════════════════════════════

@rule("fc.autopilot", "flight_controller", "Autopilot firmware family",
      "HEARTBEAT reports ArduPilot (these checks read ArduCopter parameters).",
      "Connect an ArduPilot (ArduCopter) flight controller; PX4 parameter names differ.",
      SRC_MAV_HEARTBEAT, "MAVLink HEARTBEAT.autopilot (MAV_AUTOPILOT)")
def _fc_autopilot(f: Facts) -> Outcome:
    hb = f.snap.heartbeat
    if not hb:
        raise _Missing("no vehicle HEARTBEAT")
    ap = hb.get("autopilot")
    name = _AUTOPILOTS.get(ap, f"MAV_AUTOPILOT {ap}")
    if ap == 3:
        return _o(PASS, autopilot=name, system_id=hb.get("system_id"))
    return _o(WARN, "Checks are written for ArduCopter parameters; many will read UNKNOWN on this autopilot.",
              autopilot=name)


@rule("fc.vehicle_type", "flight_controller", "Vehicle type is a multicopter",
      "HEARTBEAT.type is a multirotor/copter frame.",
      "Load ArduCopter firmware (Mission Planner > SETUP > Install Firmware).",
      SRC_MAV_HEARTBEAT, "MAVLink HEARTBEAT.type (MAV_TYPE)")
def _fc_vehicle_type(f: Facts) -> Outcome:
    hb = f.snap.heartbeat
    if not hb:
        raise _Missing("no vehicle HEARTBEAT")
    t = hb.get("type")
    if t in _COPTER_MAV_TYPES:
        return _o(PASS, mav_type=t, vehicle=_COPTER_MAV_TYPES[t])
    return _o(WARN, "Not a copter airframe — the Motors/Airframe checks assume ArduCopter.", mav_type=t)


@rule("fc.firmware", "flight_controller", "Firmware version and release type",
      "AUTOPILOT_VERSION received and the build is an official release (not dev/alpha/beta/rc).",
      "Flash the latest stable ArduCopter from Mission Planner > SETUP > Install Firmware.",
      SRC_MAV_FW_TYPE, "AUTOPILOT_VERSION.flight_sw_version, FIRMWARE_VERSION_TYPE")
def _fc_firmware(f: Facts) -> Outcome:
    av = f.snap.autopilot_version
    if not av:
        raise _Missing("AUTOPILOT_VERSION not received")
    fw = av.get("firmware") or {}
    ev = dict(version=fw.get("version"), release_type=fw.get("type_name"), board_id=av.get("board_id"),
              usb_vendor_id=f"0x{int(av.get('vendor_id') or 0):04X}", usb_product_id=f"0x{int(av.get('product_id') or 0):04X}",
              uid=av.get("uid"), git_hash=av.get("flight_custom_version_str"))
    if fw.get("type") == 255:
        return Outcome(PASS, ev)
    return Outcome(WARN, ev, f"Firmware is a {fw.get('type_name')} build, not an official release.")


def _sensor_rule(bit: int, label: str) -> Evaluator:
    def ev(f: Facts) -> Outcome:
        present, enabled, healthy = f.sensor(bit)
        e = dict(present=present, enabled=enabled, healthy=healthy)
        if not present:
            return Outcome(FAIL, e, f"No {label} detected by the autopilot.")
        if not enabled:
            return Outcome(WARN, e, f"{label} detected but disabled.")
        if not healthy:
            return Outcome(FAIL, e, f"{label} reported unhealthy.")
        return Outcome(PASS, e)
    return ev


for _id, _bit, _label, _fix in (
    ("fc.sensor_gyro", BIT_GYRO, "gyroscope", "Reboot the autopilot; if it persists the board's IMU has failed — replace the flight controller."),
    ("fc.sensor_accel", BIT_ACCEL, "accelerometer", "Reboot the autopilot; if it persists the board's IMU has failed — replace the flight controller."),
    ("fc.sensor_mag", BIT_MAG, "compass (magnetometer)", "Connect the GPS/compass module's I2C lead, check COMPASS_ENABLE=1 / COMPASS_USE=1, reboot and re-run compass calibration."),
    ("fc.sensor_baro", BIT_BARO, "barometer", "Reboot; keep the barometer out of prop wash/light (foam cover). If it persists, replace the flight controller."),
):
    rule(_id, "flight_controller", f"{_label[0].upper()}{_label[1:]} present and healthy",
         f"SYS_STATUS reports the {_label} present, enabled and healthy.", _fix,
         SRC_MAV_SYS_STATUS, "SYS_STATUS onboard_control_sensors_present/enabled/health")(_sensor_rule(_bit, _label))


@rule("fc.accel_calibrated", "flight_controller", "Accelerometers calibrated",
      "INS_ACCOFFS_*/INS_ACCSCAL_* differ from their uncalibrated defaults and no \"3D Accel calibration needed\" PreArm.",
      "Mission Planner > SETUP > Mandatory Hardware > Accel Calibration (all six positions), then Calibrate Level.",
      SRC_ACCEL_CAL, "PreArm \"3D Accel calibration needed\" (" + SRC_PREARM + ")")
def _fc_accel_cal(f: Facts) -> Outcome:
    offs = [f.p(f"INS_ACCOFFS_{a}") for a in "XYZ"]
    scal = [f.p(f"INS_ACCSCAL_{a}") for a in "XYZ"]
    msgs = f.prearm_matching("accel", "calib")
    ev = dict(INS_ACCOFFS=[_r(v, 4) for v in offs], INS_ACCSCAL=[_r(v, 4) for v in scal])
    if msgs:
        return Outcome(FAIL, {**ev, "prearm": msgs}, "Autopilot reports the accelerometers need calibration.")
    if all(v == 0 for v in offs) and all(v in (0.0, 1.0) for v in scal):
        return Outcome(FAIL, ev, "Offsets are all zero and scales at default — accel calibration never done.")
    return Outcome(PASS, ev)


@rule("fc.compass_calibrated", "flight_controller", "Compass calibrated",
      "COMPASS_OFS_X/Y/Z non-zero and within COMPASS_OFFS_MAX, no \"Compass not calibrated\" PreArm.",
      "Mission Planner > SETUP > Mandatory Hardware > Compass > Start (Onboard Mag Calibration), away from metal; reboot after.",
      SRC_COMPASS_CAL, "PreArm \"Compass not calibrated\" — offsets zero or sensor count changed (" + SRC_PREARM + ")")
def _fc_compass_cal(f: Facts) -> Outcome:
    dev_id = f.p("COMPASS_DEV_ID")
    offs = [f.p(f"COMPASS_OFS_{a}") for a in "XYZ"]
    ofs_max = f.p_opt("COMPASS_OFFS_MAX", 1800.0)
    ev = dict(COMPASS_DEV_ID=int(dev_id), COMPASS_OFS=[_r(v, 1) for v in offs], COMPASS_OFFS_MAX=ofs_max)
    if dev_id == 0:
        return Outcome(UNKNOWN, ev, "No primary compass is configured (COMPASS_DEV_ID=0) — nothing to assess; see the compass presence check.")
    msgs = f.prearm_matching("compass", "calib")
    if msgs:
        return Outcome(FAIL, {**ev, "prearm": msgs})
    if all(v == 0 for v in offs):
        return Outcome(FAIL, ev, "Compass offsets are all zero — compass calibration never done.")
    length = math.sqrt(sum(v * v for v in offs))
    if ofs_max and length > ofs_max:
        return Outcome(FAIL, {**ev, "offset_length": round(length, 1)},
                       "Compass offsets exceed COMPASS_OFFS_MAX — magnetic interference near the compass.")
    return Outcome(PASS, {**ev, "offset_length": round(length, 1)})


@rule("fc.ekf", "flight_controller", "EKF healthy",
      "EKF attitude valid and velocity/position/compass variances below FS_EKF_THRESH (default 0.8).",
      "Wait for GPS lock and EKF convergence; check the compass calibration and vibration; reboot if variances stay high.",
      SRC_EKF_FS, "EKF failsafe: any two of compass/position/velocity variance above FS_EKF_THRESH for 1 s")
def _fc_ekf(f: Facts) -> Outcome:
    e = f.tel("EKF_STATUS_REPORT")
    thresh = f.p_opt("FS_EKF_THRESH", EKF_THRESH_DEFAULT) or EKF_THRESH_DEFAULT
    variances = {"velocity": e["velocity_variance"], "position_horizontal": e["pos_horiz_variance"],
                 "compass": e["compass_variance"]}
    flags = int(e["flags"])
    over = [k for k, v in variances.items() if v >= thresh]
    ev = dict(flags=flags, FS_EKF_THRESH=thresh, pos_vert_variance=_r(e["pos_vert_variance"], 3),
              **{f"{k}_variance": _r(v, 3) for k, v in variances.items()},
              const_pos_mode=bool(flags & EKF_CONST_POS_MODE))
    if flags & EKF_UNINITIALIZED or not flags & EKF_ATTITUDE:
        return Outcome(FAIL, ev, "EKF attitude solution not valid / EKF uninitialised.")
    if len(over) >= 2:
        return Outcome(FAIL, ev, f"{' and '.join(over)} variance at or above {thresh} — this is the EKF failsafe condition.")
    if over:
        return Outcome(WARN, ev, f"{over[0]} variance at or above {thresh}.")
    if flags & EKF_GPS_GLITCHING:
        return Outcome(WARN, ev, "EKF reports a GPS glitch.")
    return Outcome(PASS, ev)


@rule("fc.vibration", "flight_controller", "Vibration and accelerometer clipping",
      "VIBRATION below 30 m/s² on every axis and clipping counters not increasing.",
      "Balance/replace props, soft-mount the flight controller, tighten arms and motor screws; re-measure in a hover.",
      SRC_VIBE, "\"below 30m/s/s are normally acceptable... above 60m/s/s nearly always have problems\"; increasing clip counts = serious")
def _fc_vibration(f: Facts) -> Outcome:
    samples = list(f.snap.vibration_samples)
    if not samples:
        raise _Missing(f"no VIBRATION message received in {f.snap.sample_seconds:.0f}s")
    peak = max(max(s["vibration_x"], s["vibration_y"], s["vibration_z"]) for s in samples)
    first, last = samples[0], samples[-1]
    growth = [int(last[f"clipping_{i}"]) - int(first[f"clipping_{i}"]) for i in range(3)]
    total = [int(last[f"clipping_{i}"]) for i in range(3)]
    ev = dict(peak_ms2=_r(peak, 1), latest=[_r(last[k], 1) for k in ("vibration_x", "vibration_y", "vibration_z")],
              clipping_total=total, clipping_growth_during_sample=growth, samples=len(samples),
              measured="disarmed, on the ground — in-flight levels are higher; confirm with a hover log")
    if peak > VIBE_BAD_MS2:
        return Outcome(FAIL, ev, f"Peak vibration {peak:.1f} m/s² is above 60 m/s².")
    if any(g > 0 for g in growth):
        extra = f" Peak vibration is also {peak:.1f} m/s² (above 30)." if peak > VIBE_OK_MS2 else ""
        return Outcome(FAIL, ev, "Accelerometer clipping counters increased during the sample window." + extra)
    if peak > VIBE_OK_MS2:
        return Outcome(WARN, ev, f"Peak vibration {peak:.1f} m/s² is above 30 m/s².")
    if any(t >= 100 for t in total):
        return Outcome(WARN, ev, "Clipping has accumulated since boot (≥100) — review the last flight's log.")
    return Outcome(PASS, ev)


@rule("fc.arming_check", "flight_controller", "Arming checks enabled",
      "ARMING_CHECK = 1 (all checks) — or ARMING_SKIPCHK = 0 on newer firmware.",
      "Set ARMING_CHECK = 1 in Mission Planner > CONFIG > Full Parameter List and fix whatever the checks report.",
      SRC_PREARM, "ARMING_CHECK / ARMING_SKIPCHK")
def _fc_arming_check(f: Facts) -> Outcome:
    if "ARMING_SKIPCHK" in f.snap.params:
        v = int(f.p("ARMING_SKIPCHK"))
        if v == 0:
            return _o(PASS, ARMING_SKIPCHK=v)
        if v == -1:
            return _o(FAIL, "All arming checks are skipped.", ARMING_SKIPCHK=v)
        return _o(WARN, "Some arming checks are skipped.", ARMING_SKIPCHK=v)
    v = int(f.p("ARMING_CHECK"))
    if v == 1:
        return _o(PASS, ARMING_CHECK=v)
    if v == 0:
        return _o(FAIL, "All pre-arm checks are disabled.", ARMING_CHECK=v)
    return _o(WARN, "Only a subset of pre-arm checks is enabled (bitmask, not 1 = All).", ARMING_CHECK=v)


@rule("fc.logging", "flight_controller", "Onboard logging enabled",
      "LOG_BITMASK non-zero, LOG_BACKEND_TYPE non-zero, and the logging subsystem healthy.",
      "Set LOG_BITMASK (Copter default 176126) and LOG_BACKEND_TYPE=1 (File); replace the SD card if logging reports unhealthy.",
      SRC_LOGS, "LOG_BITMASK, LOG_BACKEND_TYPE; PreArm \"Logging failed\" (" + SRC_PREARM + ")")
def _fc_logging(f: Facts) -> Outcome:
    bitmask = int(f.p("LOG_BITMASK"))
    backend = f.p_opt("LOG_BACKEND_TYPE")
    ev: Dict[str, Any] = dict(LOG_BITMASK=bitmask, LOG_BACKEND_TYPE=None if backend is None else int(backend))
    try:
        present, _enabled, healthy = f.sensor(BIT_LOGGING)
        ev["logging_health_bit"] = healthy if present else "not reported"
    except _Missing:
        present, healthy = False, True
    if bitmask == 0:
        return Outcome(FAIL, ev, "LOG_BITMASK = 0: nothing is logged, so no flight record exists for an incident investigation.")
    if backend is not None and int(backend) == 0:
        return Outcome(FAIL, ev, "LOG_BACKEND_TYPE = 0: logging has no backend.")
    if present and not healthy:
        return Outcome(FAIL, ev, "Autopilot reports logging unhealthy (SD card missing/failed?).")
    return Outcome(PASS, ev)


@rule("fc.prearm", "flight_controller", "Autopilot pre-arm checks pass",
      "No \"PreArm:\" messages after MAV_CMD_RUN_PREARM_CHECKS and the SYS_STATUS pre-arm bit healthy.",
      "Resolve every PreArm message listed (Mission Planner > DATA > Messages shows the same text).",
      SRC_PREARM, "MAV_CMD_RUN_PREARM_CHECKS + STATUSTEXT \"PreArm: ...\"")
def _fc_prearm(f: Facts) -> Outcome:
    msgs = list(f.snap.prearm_messages)
    bit_state: Optional[bool] = None
    ss = f.tel_opt("SYS_STATUS")
    if ss is not None and ss["onboard_control_sensors_present"] & BIT_PREARM:
        bit_state = bool(ss["onboard_control_sensors_health"] & BIT_PREARM)
    ev = dict(prearm_messages=msgs, prearm_health_bit=bit_state, run_prearm_checks_ack=f.snap.prearm_command_result)
    if msgs:
        if f.ctx.bench_mode:
            bench_only = all(any(k in m.lower() for k in _BENCH_PREARM_MARKERS) for m in msgs)
            if bench_only:
                return Outcome(WARN, ev, "Only GPS/position-related PreArm failures, expected on an indoor bench.")
        return Outcome(FAIL, ev, f"{len(msgs)} PreArm failure(s) reported by the autopilot.")
    if bit_state is False:
        return Outcome(FAIL, ev, "The pre-arm health bit says NOT ready to arm, but no reason text arrived — check Mission Planner's Messages tab.")
    if bit_state is True or f.snap.prearm_command_result == "ACCEPTED":
        return Outcome(PASS, ev)
    raise _Missing("no pre-arm result: the command was not acknowledged and SYS_STATUS carries no pre-arm bit")


# ═════════════════════════════════════════════════════════════════════════
#  Battery & power
# ═════════════════════════════════════════════════════════════════════════

@rule("batt.monitor", "battery", "Battery monitor configured",
      "BATT_MONITOR ≠ 0 (a voltage — ideally voltage and current — monitor is enabled).",
      "Set BATT_MONITOR (4 = analog voltage and current for a standard power module) and calibrate it.",
      SRC_POWER_MODULE, "BATT_MONITOR")
def _batt_monitor(f: Facts) -> Outcome:
    v = int(f.p("BATT_MONITOR"))
    ev = dict(BATT_MONITOR=v, type=BATT_MONITOR_NAMES.get(v, f"type {v}"))
    if v == 0:
        return Outcome(FAIL, ev, "No battery monitoring: battery failsafes cannot trigger.")
    if v == 3:
        return Outcome(WARN, ev, "Voltage only — no current sensing, so mAh-based failsafes and capacity estimates are unavailable.")
    return Outcome(PASS, ev)


@rule("batt.voltage", "battery", "Pack voltage plausible for its cell count",
      "Pack voltage per cell between 3.3 V and 4.2 V (standard LiPo) for the reported/inferred cell count.",
      "Charge the pack; if the reading is wrong, recalibrate BATT_VOLT_MULT against a multimeter.",
      SRC_TUNING_SETUP, "MOT_BAT_VOLT_MAX = 4.2 V × cells, MOT_BAT_VOLT_MIN = 3.3 V × cells (standard LiPo)")
def _batt_voltage(f: Facts) -> Outcome:
    pack, cells, src = f.battery_cells()
    n, method = f.cell_count()
    ev: Dict[str, Any] = dict(pack_v=_r(pack), cell_count=n, cell_count_method=method, source=src)
    if pack is None or pack < 1.0:
        return Outcome(FAIL, ev, "No battery voltage — is the flight pack connected (USB power alone reads ~0 V)?")
    per_cell = pack / n
    ev["average_cell_v"] = _r(per_cell, 3)
    if per_cell < LIPO_CELL_MIN:
        return Outcome(FAIL, ev, f"Average {per_cell:.2f} V/cell is below 3.3 V/cell.")
    if per_cell > LIPO_CELL_MAX + 0.05:
        return Outcome(WARN, ev, f"Average {per_cell:.2f} V/cell is above 4.2 V — a LiHV pack, a mis-inferred cell count, or BATT_VOLT_MULT is off.")
    return Outcome(PASS, ev)


@rule("batt.cell_min", "battery", "Lowest cell voltage (resting)",
      "Every cell ≥ 3.5 V at rest before take-off.",
      "Charge or replace the pack before flight.",
      SRC_TUNING_SETUP, "AeroFleet pre-flight guideline (3.5 V resting); ArduPilot's 3.3 V/cell is the under-load floor")
def _batt_cell_min(f: Facts) -> Outcome:
    pack, cells, src = f.battery_cells()
    if not cells:
        return Outcome(UNKNOWN, dict(pack_v=_r(pack), source=src),
                       "This battery monitor reports only pack voltage; individual cells cannot be read over MAVLink. Check with a cell checker.")
    lo = min(cells)
    ev = dict(cells_v=[_r(c, 3) for c in cells], min_cell_v=_r(lo, 3), lowest_cell=cells.index(lo) + 1)
    if lo < CELL_REST_MIN:
        return Outcome(FAIL, ev, f"Cell {cells.index(lo) + 1} is at {lo:.2f} V.")
    return Outcome(PASS, ev)


@rule("batt.cell_balance", "battery", "Cell balance",
      "Highest minus lowest cell ≤ 0.10 V.",
      "Balance-charge the pack; retire it if the imbalance returns — a weak cell sags first under load.",
      SRC_TUNING_SETUP, "AeroFleet pre-flight guideline (0.10 V imbalance)")
def _batt_cell_balance(f: Facts) -> Outcome:
    pack, cells, src = f.battery_cells()
    if not cells:
        return Outcome(UNKNOWN, dict(pack_v=_r(pack), source=src),
                       "Pack voltage only — cell balance cannot be read over MAVLink. Check with a cell checker.")
    spread = max(cells) - min(cells)
    ev = dict(cells_v=[_r(c, 3) for c in cells], imbalance_v=_r(spread, 3))
    if spread > CELL_IMBALANCE_MAX + 1e-9:
        return Outcome(FAIL, ev, f"Cells differ by {spread:.2f} V.")
    return Outcome(PASS, ev)


@rule("batt.capacity", "battery", "Battery capacity set",
      "BATT_CAPACITY > 0 and set to the actual pack (not left at the 3300 mAh default).",
      "Set BATT_CAPACITY to the pack's rated mAh.",
      SRC_POWER_MODULE, "BATT_CAPACITY (firmware default 3300 mAh, AP_BattMonitor_Params.cpp)")
def _batt_capacity(f: Facts) -> Outcome:
    v = f.p("BATT_CAPACITY")
    if v <= 0:
        return _o(FAIL, "Capacity unset: remaining-% and mAh failsafes are meaningless.", BATT_CAPACITY=v)
    if v == 3300:
        return _o(WARN, "Still the firmware default — confirm it matches the fitted pack.", BATT_CAPACITY=v)
    return _o(PASS, BATT_CAPACITY=v)


def _fs_action_rule(param: str, which: str) -> Evaluator:
    def ev(f: Facts) -> Outcome:
        v = int(f.p(param))
        e = {param: v, "action": BATT_FS_ACTIONS.get(v, f"value {v}")}
        if v == 0:
            return Outcome(FAIL, e, f"{which} battery failsafe takes no action — the ArduCopter default. The aircraft keeps flying on a {which.lower()} battery.")
        if v == 5:
            return Outcome(WARN, e, "Terminate disarms the motors in the air — the aircraft falls.")
        return Outcome(PASS, e)
    return ev


rule("batt.fs_low_action", "battery", "Low-battery failsafe action",
     "BATT_FS_LOW_ACT ≠ 0 (RTL/SmartRTL/Land).",
     "Set BATT_FS_LOW_ACT = 2 (RTL) or 3 (SmartRTL or RTL).",
     SRC_BATT_FS, "BATT_FS_LOW_ACT — default 0 = None (AP_BattMonitor_Params.cpp)")(_fs_action_rule("BATT_FS_LOW_ACT", "Low"))
rule("batt.fs_critical_action", "battery", "Critical-battery failsafe action",
     "BATT_FS_CRT_ACT ≠ 0 (normally Land).",
     "Set BATT_FS_CRT_ACT = 1 (Land).",
     SRC_BATT_FS, "BATT_FS_CRT_ACT — default 0 = None (AP_BattMonitor_Params.cpp)")(_fs_action_rule("BATT_FS_CRT_ACT", "Critical"))


@rule("batt.fs_thresholds", "battery", "Battery failsafe thresholds",
      "Low and critical thresholds set (voltage and/or mAh), low > critical, and low ≥ 3.3 V/cell.",
      "E.g. 4S LiPo: BATT_LOW_VOLT 14.4, BATT_CRT_VOLT 14.0; BATT_LOW_MAH ≈ 20 % of capacity.",
      SRC_BATT_FS, "BATT_LOW_VOLT/BATT_CRT_VOLT/BATT_LOW_MAH/BATT_CRT_MAH; PreArm \"voltage failsafe critical >= low\"")
def _batt_fs_thresholds(f: Facts) -> Outcome:
    low_v, crt_v = f.p("BATT_LOW_VOLT"), f.p("BATT_CRT_VOLT")
    low_mah, crt_mah = f.p_opt("BATT_LOW_MAH", 0.0) or 0.0, f.p_opt("BATT_CRT_MAH", 0.0) or 0.0
    n, method = f.cell_count()
    ev: Dict[str, Any] = dict(BATT_LOW_VOLT=low_v, BATT_CRT_VOLT=crt_v, BATT_LOW_MAH=low_mah, BATT_CRT_MAH=crt_mah,
                              cell_count=n, cell_count_method=method)
    problems, warnings = [], []
    if low_v <= 0 and low_mah <= 0:
        problems.append("no low-battery threshold (voltage or mAh)")
    if crt_v <= 0 and crt_mah <= 0:
        problems.append("no critical-battery threshold (voltage or mAh)")
    if low_v > 0 and crt_v > 0 and crt_v >= low_v:
        problems.append("BATT_CRT_VOLT ≥ BATT_LOW_VOLT (the autopilot refuses to arm)")
    if low_mah > 0 and crt_mah > 0 and crt_mah >= low_mah:
        problems.append("BATT_CRT_MAH ≥ BATT_LOW_MAH")
    if n and low_v > 0:
        per_cell = low_v / n
        ev["low_v_per_cell"] = _r(per_cell, 2)
        if per_cell < LIPO_CELL_MIN:
            warnings.append(f"BATT_LOW_VOLT is {per_cell:.2f} V/cell, below 3.3 V/cell")
    if problems:
        return Outcome(FAIL, ev, "; ".join(problems + warnings) + ".")
    if warnings:
        return Outcome(WARN, ev, "; ".join(warnings) + ".")
    return Outcome(PASS, ev)


@rule("batt.board_vcc", "battery", "Flight-controller supply voltage",
      "Board Vcc inside ArduPilot's 4.3–5.8 V pre-arm window (AeroFleet also flags outside 4.8–5.4 V).",
      "Check the power module/BEC output and its cable; don't fly on USB power alone.",
      SRC_PREARM, "PreArm \"Board (Xv) out of range 4.3-5.8v\" (BRD_VBUS_MIN); 4.8–5.4 V is an AeroFleet margin")
def _batt_board_vcc(f: Facts) -> Outcome:
    ps = f.tel("POWER_STATUS")
    vcc = ps["Vcc"] / 1000.0
    vmin = f.p_opt("BRD_VBUS_MIN", BOARD_V_MIN) or BOARD_V_MIN
    ev = dict(vcc_v=_r(vcc, 3), BRD_VBUS_MIN=vmin, flags=ps.get("flags"))
    if vcc < vmin or vcc > BOARD_V_MAX:
        return Outcome(FAIL, ev, f"Board voltage {vcc:.2f} V is outside {vmin}–{BOARD_V_MAX} V.")
    if vcc < BOARD_V_WARN_LO or vcc > BOARD_V_WARN_HI:
        return Outcome(WARN, ev, f"Board voltage {vcc:.2f} V is inside ArduPilot's limits but outside 4.8–5.4 V.")
    return Outcome(PASS, ev)


# ═════════════════════════════════════════════════════════════════════════
#  Motors & ESCs
# ═════════════════════════════════════════════════════════════════════════

@rule("mot.frame", "motors", "Frame class and type set",
      "FRAME_CLASS ≠ 0 and FRAME_TYPE a valid layout for it.",
      "Mission Planner > SETUP > Mandatory Hardware > Frame Type; select the airframe's class and type, then reboot.",
      SRC_PREARM, "PreArm \"Motors: Check frame class and type\"; FRAME_CLASS/FRAME_TYPE")
def _mot_frame(f: Facts) -> Outcome:
    fc, ft = int(f.p("FRAME_CLASS")), int(f.p("FRAME_TYPE"))
    layout = layout_for_frame(fc, ft)
    ev = dict(FRAME_CLASS=fc, frame_class=FRAME_CLASS_NAMES.get(fc, f"class {fc}"), FRAME_TYPE=ft,
              frame_type=FRAME_TYPE_NAMES.get(ft, f"type {ft}"), motor_test_diagram=layout.name if layout else None)
    if fc == 0:
        return Outcome(FAIL, ev, "FRAME_CLASS is Undefined — motors will not arm.")
    if f.prearm_matching("frame"):
        return Outcome(FAIL, {**ev, "prearm": f.prearm_matching("frame")})
    return Outcome(PASS, ev)


@rule("mot.output_mapping", "motors", "Motor outputs mapped once each",
      "SERVOn_FUNCTION assigns Motor1..MotorN (N from the frame) to exactly one output each, no extras.",
      "Mission Planner > SETUP > Servo Output: give each motor output its MotorN function exactly once and match the ESC wiring to the frame diagram.",
      SRC_MOTORS, "SERVOn_FUNCTION 33–40 = Motor1–8, 82–85 = Motor9–12")
def _mot_output_mapping(f: Facts) -> Outcome:
    fc = int(f.p("FRAME_CLASS"))
    expected = FRAME_CLASS_MOTOR_COUNT.get(fc)
    outputs: Dict[int, List[int]] = {}
    for n in range(1, 33):
        name = f"SERVO{n}_FUNCTION"
        if name not in f.snap.params:
            continue
        fn = int(f.snap.params[name])
        if fn in _MOTOR_FUNCTIONS:
            outputs.setdefault(_MOTOR_FUNCTIONS[fn], []).append(n)
    if not any(f"SERVO{n}_FUNCTION" in f.snap.params for n in range(1, 17)):
        raise _Missing("SERVOn_FUNCTION parameters were not reported")
    mapping = {f"Motor{m}": outs for m, outs in sorted(outputs.items())}
    ev: Dict[str, Any] = dict(frame_class=FRAME_CLASS_NAMES.get(fc, fc), expected_motors=expected, mapping=mapping)
    if expected is None:
        return Outcome(UNKNOWN, ev, "Motor count unknown for this frame class; mapping listed for manual review.")
    missing = [f"Motor{m}" for m in range(1, expected + 1) if m not in outputs]
    dupes = {f"Motor{m}": outs for m, outs in outputs.items() if len(outs) > 1}
    extra = [f"Motor{m}" for m in outputs if m > expected]
    ev.update(missing=missing, duplicated=dupes, unexpected=extra)
    if missing or dupes:
        bits = []
        if dupes:
            bits.append("duplicated: " + ", ".join(f"{k} on outputs {v}" for k, v in dupes.items()))
        if missing:
            bits.append("no output for " + ", ".join(missing))
        return Outcome(FAIL, ev, "; ".join(bits) + ".")
    if extra:
        return Outcome(WARN, ev, f"Outputs assigned to motors this frame doesn't have: {', '.join(extra)}.")
    return Outcome(PASS, ev)


@rule("mot.pwm_range", "motors", "Motor output range",
      "MOT_PWM_MIN < MOT_PWM_MAX with a usable span (≥ 500 µs), or 1000/2000 for DShot.",
      "Set MOT_PWM_MIN/MAX to the ESC's calibrated range (typically 1000/2000) and calibrate the ESCs (not needed for DShot).",
      SRC_MOTOR_RANGE, "MOT_PWM_MIN, MOT_PWM_MAX, MOT_PWM_TYPE (DShot: " + SRC_DSHOT + ")")
def _mot_pwm_range(f: Facts) -> Outcome:
    lo, hi = f.p("MOT_PWM_MIN"), f.p("MOT_PWM_MAX")
    ptype = int(f.p_opt("MOT_PWM_TYPE", 0) or 0)
    ev = dict(MOT_PWM_MIN=lo, MOT_PWM_MAX=hi, MOT_PWM_TYPE=ptype, protocol=MOT_PWM_TYPES.get(ptype, ptype))
    if 4 <= ptype <= 7:
        if (lo, hi) == (1000, 2000):
            return Outcome(PASS, ev)
        return Outcome(WARN, ev, "DShot expects MOT_PWM_MIN=1000 and MOT_PWM_MAX=2000.")
    if lo == 0 and hi == 0:
        return Outcome(WARN, ev, "0/0 means the RC3 (throttle) range is used — make sure the ESCs were calibrated to it.")
    if lo >= hi:
        return Outcome(FAIL, ev, "MOT_PWM_MIN is not below MOT_PWM_MAX.")
    if hi - lo < 500:
        return Outcome(WARN, ev, "Narrow output span — check the ESC calibration.")
    return Outcome(PASS, ev)


@rule("mot.spin_arm_min", "motors", "Spin-when-armed below minimum spin",
      "MOT_SPIN_ARM < MOT_SPIN_MIN < MOT_SPIN_MAX.",
      "Use the motor test to find the lowest reliable spin, set MOT_SPIN_ARM just above it and MOT_SPIN_MIN ~0.03 higher.",
      SRC_PREARM, "PreArm \"Check MOT_SPIN_ARM\" — reduce MOT_SPIN_ARM to below MOT_SPIN_MIN")
def _mot_spin(f: Facts) -> Outcome:
    arm, mn, mx = f.p("MOT_SPIN_ARM"), f.p("MOT_SPIN_MIN"), f.p_opt("MOT_SPIN_MAX", 0.95)
    ev = dict(MOT_SPIN_ARM=_r(arm, 3), MOT_SPIN_MIN=_r(mn, 3), MOT_SPIN_MAX=_r(mx, 3))
    if arm >= mn:
        return Outcome(FAIL, ev, "MOT_SPIN_ARM must be lower than MOT_SPIN_MIN.")
    if mx is not None and mn >= mx:
        return Outcome(FAIL, ev, "MOT_SPIN_MIN must be lower than MOT_SPIN_MAX.")
    return Outcome(PASS, ev)


@rule("mot.esc_telemetry", "motors", "ESC telemetry and temperatures",
      "Every motor's ESC reports telemetry, and idle (disarmed) ESC temperatures ≤ 60 °C.",
      "Check ESC telemetry wiring/SERVO_BLH_* or DShot bidirectional settings; investigate any hot ESC before flight.",
      SRC_ESC_TELEM, "ESC_TELEMETRY_1_TO_4/5_TO_8; 60 °C idle limit is an AeroFleet heuristic", required=False)
def _mot_esc(f: Facts) -> Outcome:
    blocks = [(0, f.tel_opt("ESC_TELEMETRY_1_TO_4")), (4, f.tel_opt("ESC_TELEMETRY_5_TO_8"))]
    if all(b is None for _, b in blocks):
        raise _Missing("no ESC telemetry (ESCs without BLHeli/DShot telemetry don't report any)")
    reporting: Dict[int, Dict[str, Any]] = {}
    for base, b in blocks:
        if b is None:
            continue
        for i in range(4):
            count = list(b.get("count") or [0] * 4)[i]
            volt = list(b.get("voltage") or [0] * 4)[i]
            if count or volt:
                reporting[base + i + 1] = dict(temp_c=list(b["temperature"])[i], rpm=list(b["rpm"])[i],
                                               voltage_v=_r(volt / 100.0), current_a=_r(list(b["current"])[i] / 100.0))
    expected = FRAME_CLASS_MOTOR_COUNT.get(int(f.p_opt("FRAME_CLASS", 0) or 0))
    ev: Dict[str, Any] = dict(escs_reporting=len(reporting), expected=expected, escs=reporting)
    hot = {k: v["temp_c"] for k, v in reporting.items() if v["temp_c"] > ESC_IDLE_TEMP_WARN_C}
    if hot:
        return Outcome(WARN, ev, f"ESC(s) {sorted(hot)} above {ESC_IDLE_TEMP_WARN_C} °C while disarmed.")
    if expected and len(reporting) < expected:
        return Outcome(WARN, ev, f"Only {len(reporting)} of {expected} ESCs report telemetry.")
    return Outcome(PASS, ev)


@rule("mot.motor_test", "motors", "Motor order and spin direction verified",
      "Each motor, tested one at a time props-off, spins at the expected position in the expected direction (operator-confirmed; ESC rpm corroborates when available).",
      "Swap any two of a wrong-direction motor's three wires; fix SERVOn_FUNCTION or ESC signal wiring for a motor in the wrong position.",
      SRC_MOTORS, "Motor test sequence A, B, C… clockwise; motor matrix from AP_MotorsMatrix.cpp (Copter-4.5)")
def _mot_motor_test(f: Facts) -> Outcome:
    mt = f.motor_test or {}
    layout = layout_for_frame(f.p_opt("FRAME_CLASS"), f.p_opt("FRAME_TYPE"))
    results: Mapping[str, Any] = mt.get("results") or {}
    if layout is None:
        return Outcome(MANUAL, dict(results=results),
                       "No guided diagram for this frame — run Mission Planner's Motor Test and compare with ArduPilot's motor diagram.")
    letters = [m.letter for m in sorted(layout.motors, key=lambda m: m.test_order)]
    confirmations = {l: (results.get(l) or {}).get("confirmation") for l in letters}
    incorrect = [l for l, c in confirmations.items() if c and c.get("result") == "incorrect"]
    mismatch = [l for l in letters if ((results.get(l) or {}).get("esc_corroboration") or {}).get("status") == "mismatch"]
    pending = [l for l, c in confirmations.items() if not c]
    ev = dict(layout=layout.name, letters=letters, confirmed={l: (c or {}).get("result") for l, c in confirmations.items()},
              esc_corroboration={l: ((results.get(l) or {}).get("esc_corroboration") or {}).get("status") for l in letters})
    if incorrect:
        return Outcome(FAIL, ev, f"Operator reported motor(s) {', '.join(incorrect)} wrong position or direction.")
    if pending:
        return Outcome(MANUAL, ev, f"Motor test not complete: {', '.join(pending)} still to confirm.")
    if mismatch:
        return Outcome(WARN, ev, f"Operator confirmed all motors, but ESC telemetry saw a different ESC spin for {', '.join(mismatch)} — check ESC telemetry wiring and SERVOn_FUNCTION.")
    return Outcome(MANUAL, {**ev, "resolved": True}, "All motors confirmed by the operator.")


# ═════════════════════════════════════════════════════════════════════════
#  Airframe & design
# ═════════════════════════════════════════════════════════════════════════

@rule("air.hover_throttle", "airframe", "Hover throttle (power margin)",
      "Learned MOT_THST_HOVER within ArduPilot's typical 0.2–0.6; above 0.6 the airframe is short of thrust.",
      "Reduce all-up weight, fit larger props/higher-KV motors or a higher-voltage pack; leave MOT_HOVER_LEARN=2 so it keeps learning.",
      SRC_HOVER, "\"The value is usually between 0.2 and 0.6\" — MOT_THST_HOVER", required=False)
def _air_hover(f: Facts) -> Outcome:
    v = f.p("MOT_THST_HOVER")
    learn = f.p_opt("MOT_HOVER_LEARN")
    ev = dict(MOT_THST_HOVER=_r(v, 3), MOT_HOVER_LEARN=None if learn is None else int(learn))
    if abs(v - HOVER_DEFAULT) < 1e-6:
        return Outcome(UNKNOWN, ev, "Still the 0.35 firmware default — the aircraft hasn't learned its hover throttle yet (fly a hover in AltHold/Loiter with MOT_HOVER_LEARN=2).")
    if v > HOVER_TYPICAL_MAX:
        return Outcome(WARN, ev, f"Hovers at {v:.0%} throttle — little headroom for payload, wind or a failing motor.")
    return Outcome(PASS, ev, "Below 0.2 is fine for a very high power-to-weight airframe." if v < 0.2 else "")


@rule("air.dgca_category", "airframe", "DGCA weight category",
      "All-up weight (airframe + payload) known and its Drone Rules 2021 category determined; flagged within 10 % of a boundary.",
      "Record the drone's weight in the AeroFleet fleet registry (or enter it for this inspection) and weigh the aircraft ready-to-fly.",
      SRC_DRONE_RULES, "Nano ≤ 250 g, Micro ≤ 2 kg, Small ≤ 25 kg, Medium ≤ 150 kg, Large > 150 kg (AeroFleet compliance_report._airworthiness_domain)")
def _air_dgca_category(f: Facts) -> Outcome:
    from aerofleet.agents.compliance_report import _airworthiness_domain

    if f.ctx.weight_kg is None:
        raise _Missing("drone weight not recorded in AeroFleet for this inspection")
    dom = _airworthiness_domain(f.ctx.weight_kg, f.ctx.payload_kg)
    ev = dict(category=dom.get("category"), total_weight_kg=dom.get("total_weight_kg"), airframe_kg=f.ctx.weight_kg,
              payload_kg=f.ctx.payload_kg, weight_source=f.ctx.weight_source,
              note="from AeroFleet's records, not measured by the flight controller")
    if dom["status"] == "AT_RISK":
        return Outcome(WARN, ev, "Within 10 % of a category boundary — weigh the aircraft to confirm its category.")
    return Outcome(PASS, ev)


manual("air.props", "airframe", "Propellers",
       "Props undamaged (no chips/cracks), balanced, correct CW/CCW prop on each motor per the frame diagram, prop nuts tight.",
       "Replace any damaged prop; match prop direction to the motor diagram.", SRC_MOTORS)
manual("air.frame_integrity", "airframe", "Frame and arms",
       "No cracks in frame plates, arms or landing gear; motor mounts tight; no play when the arms are flexed.",
       "Replace cracked parts before flight.", SRC_VIBE, "Loose/cracked structure is a leading vibration source")
manual("air.arm_locks", "airframe", "Folding-arm locks",
       "Every folding-arm latch/lock fully engaged.", "Lock each arm; replace worn latches.", SRC_MOTORS)
manual("air.cg", "airframe", "Centre of gravity and battery retention",
       "CG within the centre of the motor layout with payload fitted; battery strapped so it cannot slide.",
       "Move the battery/payload to bring the CG to the centre; add a second strap.", SRC_TUNING_SETUP)
manual("air.payload_mount", "airframe", "Payload mount / release",
       "Payload secured; release mechanism (if fitted) tested and cannot open unintentionally.",
       "Re-secure the payload and cycle the release on the ground.", SRC_DRONE_RULES)


# ═════════════════════════════════════════════════════════════════════════
#  Wiring & sensors
# ═════════════════════════════════════════════════════════════════════════

@rule("wir.gps_type", "wiring", "GPS configured",
      "GPS_TYPE (GPS1_TYPE on newer firmware) ≠ 0.",
      "Set GPS_TYPE = 1 (Auto) and check the GPS serial port's SERIALn_PROTOCOL = 5.",
      SRC_GPS, "GPS_TYPE / GPS1_TYPE")
def _wir_gps_type(f: Facts) -> Outcome:
    name, v = f.p_first("GPS_TYPE", "GPS1_TYPE")
    if int(v) == 0:
        return _o(FAIL, "GPS disabled.", **{name: int(v)})
    return _o(PASS, **{name: int(v)})


@rule("wir.gps_fix", "wiring", "GPS fix quality",
      "3D fix (or better) and HDOP ≤ GPS_HDOP_GOOD/100 (default 1.4); ≥ 6 satellites.",
      "Move outdoors with a clear view of the sky, wait for lock; check the GPS cable and antenna.",
      SRC_PREARM, "PreArm \"GPS x: Bad fix\" / \"High GPS HDOP\" (GPS_HDOP_GOOD)")
def _wir_gps_fix(f: Facts) -> Outcome:
    g = f.tel("GPS_RAW_INT")
    fix, sats = int(g["fix_type"]), int(g["satellites_visible"])
    hdop = None if g["eph"] in (65535, None) else g["eph"] / 100.0
    good = (f.p_opt("GPS_HDOP_GOOD", 140) or 140) / 100.0
    ev = dict(fix_type=fix, satellites=sats, hdop=_r(hdop), hdop_limit=good, bench_mode=f.ctx.bench_mode)
    bad = FAIL if not f.ctx.bench_mode else WARN
    if fix < 3:
        return Outcome(bad, ev, "No 3D fix" + (" — expected indoors on a bench; re-check outdoors before flight." if f.ctx.bench_mode else "."))
    if hdop is None or hdop > good:
        return Outcome(bad, ev, f"HDOP {hdop} above {good}.")
    if sats < 6:
        return Outcome(WARN, ev, "Fewer than 6 satellites.")
    return Outcome(PASS, ev)


@rule("wir.compass_external", "wiring", "External compass in use",
      "Primary compass is external (COMPASS_EXTERNAL ≠ 0), away from power wiring and motors.",
      "Mount a GPS/compass module on a mast and make it the primary compass (Mission Planner > SETUP > Compass priority).",
      SRC_COMPASS_ADV, "COMPASS_EXTERNAL", required=False)
def _wir_compass_external(f: Facts) -> Outcome:
    dev = f.p("COMPASS_DEV_ID")
    ext = int(f.p("COMPASS_EXTERNAL"))
    ev = dict(COMPASS_EXTERNAL=ext, COMPASS_DEV_ID=int(dev))
    if dev == 0:
        raise _Missing("no compass configured")
    if ext == 0:
        return Outcome(WARN, ev, "Only an internal compass — prone to interference from the power wiring.")
    return Outcome(PASS, ev)


@rule("wir.rc_receiver", "wiring", "RC receiver connected",
      "RC_CHANNELS reports ≥ 4 channels and the RC receiver is healthy (a safety pilot can take over).",
      "Bind and connect the receiver (RC_PROTOCOLS), then do the radio calibration.",
      SRC_RADIO_FS, "RC_CHANNELS.chancount; SYS_STATUS RC receiver bit")
def _wir_rc(f: Facts) -> Outcome:
    rc = f.tel("RC_CHANNELS")
    count = int(rc["chancount"])
    rssi = int(rc.get("rssi", 255))
    ev: Dict[str, Any] = dict(channels=count, rssi="not reported" if rssi == 255 else rssi)
    try:
        present, _en, healthy = f.sensor(BIT_RC)
        ev["rc_health_bit"] = healthy if present else "not reported"
    except _Missing:
        present, healthy = False, True
    if count == 0:
        return Outcome(FAIL, ev, "No RC input — no manual override and the RC failsafe cannot work.")
    if present and not healthy:
        return Outcome(FAIL, ev, "RC receiver reported unhealthy (signal lost?).")
    if count < 4:
        return Outcome(FAIL, ev, "Fewer than 4 RC channels.")
    return Outcome(PASS, ev)


@rule("wir.telemetry_radio", "wiring", "Telemetry radio link",
      "A telemetry radio reports link quality (RADIO_STATUS) — optional when AeroFleet talks over another link.",
      "Fit a telemetry/C2 radio for beyond-arm's-reach operation and range-test it.",
      SRC_MAV_RADIO, "RADIO_STATUS (SiK and compatible radios)", required=False)
def _wir_radio(f: Facts) -> Outcome:
    r = f.tel_opt("RADIO_STATUS")
    if r is None:
        return Outcome(MANUAL, {}, "No RADIO_STATUS seen (normal over USB or a non-SiK link). Confirm your telemetry/C2 link is fitted and range-tested.")
    return _o(PASS, rssi=r["rssi"], remote_rssi=r["remrssi"], noise=r["noise"], remote_noise=r["remnoise"],
              rx_errors=r["rxerrors"])


@rule("wir.current_sensor", "wiring", "Power-module current reading plausible",
      "Current is measured and reads a plausible idle draw while disarmed (above 0, below 10 A).",
      "Calibrate BATT_AMP_PERVLT / BATT_AMP_OFFSET against a clamp meter (Mission Planner > SETUP > Battery Monitor).",
      SRC_POWER_MODULE, "BATTERY_STATUS/SYS_STATUS current; 0–10 A idle band is an AeroFleet heuristic", required=False)
def _wir_current(f: Facts) -> Outcome:
    monitor = f.p_opt("BATT_MONITOR")
    bs, ss = f.tel_opt("BATTERY_STATUS"), f.tel_opt("SYS_STATUS")
    raw = None
    if bs is not None and bs.get("current_battery") not in (None, -1):
        raw = bs["current_battery"]
    elif ss is not None and ss.get("current_battery") not in (None, -1):
        raw = ss["current_battery"]
    ev: Dict[str, Any] = dict(BATT_MONITOR=None if monitor is None else int(monitor))
    if monitor is not None and int(monitor) == 3:
        return Outcome(WARN, ev, "Voltage-only monitor — current is not measured.")
    if raw is None:
        raise _Missing("no battery current reported (-1 = not measured)")
    amps = raw / 100.0
    ev["current_a"] = _r(amps)
    if amps < 0:
        return Outcome(WARN, ev, "Negative current — BATT_AMP_OFFSET is miscalibrated.")
    if amps == 0:
        return Outcome(WARN, ev, "Exactly 0 A while the electronics are powered — the current sensor is probably not calibrated or not wired.")
    if amps > IDLE_CURRENT_WARN_A:
        return Outcome(WARN, ev, f"{amps:.1f} A while disarmed — check for a short or a miscalibrated BATT_AMP_PERVLT.")
    return Outcome(PASS, ev)


manual("wir.gps_mast", "wiring", "GPS/compass mast",
       "GPS/compass mast rigid, module arrow pointing forward, clear of carbon plates and power leads.",
       "Tighten the mast; re-run compass calibration after any change.", SRC_COMPASS_ADV)
manual("wir.connectors", "wiring", "Connectors secured",
       "Battery, ESC, GPS, receiver and telemetry connectors fully seated and retained; no chafed insulation.",
       "Re-seat and secure connectors (hot glue/clips on JST-GH); replace chafed wires.", SRC_MOTORS)
manual("wir.antennas", "wiring", "Antennas",
       "RC and telemetry antennas undamaged and oriented away from carbon/motors.",
       "Replace damaged antennas; mount them vertically, away from the frame.", SRC_RADIO_FS)


# ═════════════════════════════════════════════════════════════════════════
#  Failsafes
# ═════════════════════════════════════════════════════════════════════════

@rule("fs.rc_loss", "failsafes", "RC-loss (throttle) failsafe",
      "FS_THR_ENABLE ≠ 0 and 910 ≤ FS_THR_VALUE < RC3_MIN.",
      "Set FS_THR_ENABLE = 1 (RTL) and FS_THR_VALUE between 910 and RC3_MIN − 10.",
      SRC_RADIO_FS, "FS_THR_ENABLE, FS_THR_VALUE; PreArm \"Check FS_THR_VALUE\" (" + SRC_PREARM + ")")
def _fs_rc(f: Facts) -> Outcome:
    en = int(f.p("FS_THR_ENABLE"))
    val = f.p_opt("FS_THR_VALUE")
    rc3 = f.p_opt("RC3_MIN")
    ev = dict(FS_THR_ENABLE=en, FS_THR_VALUE=val, RC3_MIN=rc3)
    if en == 0:
        return Outcome(FAIL, ev, "RC failsafe disabled — on RC loss the aircraft keeps its last command.")
    if val is not None and rc3 is not None and not (FS_THR_VALUE_MIN <= val < rc3):
        return Outcome(FAIL, ev, f"FS_THR_VALUE {val:.0f} must be ≥ 910 and below RC3_MIN {rc3:.0f}.")
    return Outcome(PASS, ev)


@rule("fs.gcs_loss", "failsafes", "GCS-loss failsafe",
      "FS_GCS_ENABLE ≠ 0 — AeroFleet commands the aircraft over MAVLink, so losing that link must trigger an action.",
      "Set FS_GCS_ENABLE = 1 (RTL) and keep FS_GCS_TIMEOUT at 5 s.",
      SRC_GCS_FS, "FS_GCS_ENABLE (0 = disabled; Copter default disabled)")
def _fs_gcs(f: Facts) -> Outcome:
    v = int(f.p("FS_GCS_ENABLE"))
    if v == 0:
        return _o(WARN, "GCS failsafe disabled — if AeroFleet's link drops mid-mission the aircraft continues.", FS_GCS_ENABLE=v)
    return _o(PASS, FS_GCS_ENABLE=v, FS_GCS_TIMEOUT=f.p_opt("FS_GCS_TIMEOUT"))


@rule("fs.ekf", "failsafes", "EKF failsafe",
      "FS_EKF_ACTION ≠ 0 and FS_EKF_THRESH between 0.6 and 1.0.",
      "Set FS_EKF_ACTION = 1 (Land) and FS_EKF_THRESH = 0.8.",
      SRC_EKF_FS, "FS_EKF_ACTION (default 1 = Land), FS_EKF_THRESH (0.6 strict – 0.8 default – 1.0 relaxed)")
def _fs_ekf(f: Facts) -> Outcome:
    act, th = int(f.p("FS_EKF_ACTION")), f.p("FS_EKF_THRESH")
    ev = dict(FS_EKF_ACTION=act, FS_EKF_THRESH=_r(th, 2))
    if act == 0 or th == 0:
        return Outcome(FAIL, ev, "EKF failsafe disabled.")
    if th > 1.0:
        return Outcome(WARN, ev, "Threshold above 1.0 — the aircraft may drift far before the failsafe acts.")
    return Outcome(PASS, ev)


@rule("fs.crash_check", "failsafes", "Crash check",
      "FS_CRASH_CHECK = 1 (disarm motors after a detected crash).",
      "Set FS_CRASH_CHECK = 1.", SRC_CRASH, "FS_CRASH_CHECK (default 1)")
def _fs_crash(f: Facts) -> Outcome:
    v = int(f.p("FS_CRASH_CHECK"))
    return _o(PASS if v == 1 else FAIL, "" if v == 1 else "Crash check disabled — motors keep spinning after a crash.", FS_CRASH_CHECK=v)


@rule("fs.fence_enabled", "failsafes", "Geofence enabled",
      "FENCE_ENABLE = 1.", "Set FENCE_ENABLE = 1 (and FENCE_TYPE to include the altitude ceiling).",
      SRC_FENCE, "FENCE_ENABLE (default 0)")
def _fs_fence_enabled(f: Facts) -> Outcome:
    v = int(f.p("FENCE_ENABLE"))
    return _o(PASS if v == 1 else FAIL, "" if v == 1 else "The onboard fence is off — nothing on the aircraft enforces the altitude ceiling.", FENCE_ENABLE=v)


@rule("fs.fence_altitude", "failsafes", "Altitude ceiling ≤ 120 m",
      "Altitude fence active (FENCE_TYPE bit 0) with FENCE_ALT_MAX ≤ 120 m — DGCA Drone Rules 2021 green zone is up to 400 ft AGL.",
      "Set FENCE_ALT_MAX ≤ 120 (lower for yellow-zone permissions) and include bit 0 in FENCE_TYPE.",
      SRC_DRONE_RULES, "Drone Rules 2021 (green zone ≤ 400 ft AGL); FENCE_ALT_MAX, FENCE_TYPE (" + SRC_FENCE + ")")
def _fs_fence_alt(f: Facts) -> Outcome:
    alt = f.p("FENCE_ALT_MAX")
    ftype = int(f.p("FENCE_TYPE"))
    enabled = int(f.p_opt("FENCE_ENABLE", 0) or 0)
    ev = dict(FENCE_ALT_MAX=alt, FENCE_TYPE=ftype, altitude_fence_bit=bool(ftype & 1), FENCE_ENABLE=enabled,
              dgca_limit_m=DGCA_MAX_ALT_M)
    if alt > DGCA_MAX_ALT_M:
        return Outcome(FAIL, ev, f"Ceiling {alt:.0f} m is above the 120 m (400 ft) DGCA limit.")
    if not ftype & 1:
        return Outcome(FAIL, ev, "FENCE_TYPE doesn't include the altitude ceiling, so FENCE_ALT_MAX isn't enforced.")
    return Outcome(PASS, ev)


@rule("fs.fence_action", "failsafes", "Fence breach action",
      "FENCE_ACTION ≠ 0 (0 only reports the breach).",
      "Set FENCE_ACTION = 1 (RTL or Land).", SRC_FENCE, "FENCE_ACTION (default 1)")
def _fs_fence_action(f: Facts) -> Outcome:
    v = int(f.p("FENCE_ACTION"))
    return _o(PASS if v != 0 else FAIL, "" if v else "Breach is only reported; the aircraft does not turn back.", FENCE_ACTION=v)


@rule("fs.rtl_altitude", "failsafes", "RTL altitude sane",
      "RTL altitude ≥ 5 m (obstacle clearance), ≤ 120 m, and below the fence ceiling.",
      "Set RTL_ALT above local obstacles (e.g. 3000 cm = 30 m) and below FENCE_ALT_MAX.",
      SRC_RTL, "RTL_ALT (cm; RTL_ALT_M in m on newer firmware) — \"limited to be below the fence's maximum altitude\"; 5 m floor is an AeroFleet heuristic")
def _fs_rtl(f: Facts) -> Outcome:
    if "RTL_ALT_M" in f.snap.params:
        rtl_m = f.p("RTL_ALT_M")
        ev: Dict[str, Any] = dict(RTL_ALT_M=rtl_m)
    else:
        raw = f.p("RTL_ALT")
        rtl_m = raw / 100.0
        ev = dict(RTL_ALT_cm=raw, rtl_alt_m=_r(rtl_m, 1))
    fence_alt = f.p_opt("FENCE_ALT_MAX")
    fence_on = int(f.p_opt("FENCE_ENABLE", 0) or 0) == 1 and int(f.p_opt("FENCE_TYPE", 0) or 0) & 1
    ev.update(FENCE_ALT_MAX=fence_alt, altitude_fence_active=bool(fence_on))
    if rtl_m > DGCA_MAX_ALT_M:
        return Outcome(FAIL, ev, f"RTL climbs to {rtl_m:.0f} m, above 120 m.")
    if rtl_m == 0:
        return Outcome(WARN, ev, "RTL_ALT 0 returns at the current altitude — no climb over obstacles.")
    if rtl_m < 5:
        return Outcome(WARN, ev, f"RTL at {rtl_m:.1f} m is unlikely to clear buildings/trees.")
    if fence_on and fence_alt is not None and rtl_m >= fence_alt:
        return Outcome(WARN, ev, f"RTL altitude {rtl_m:.0f} m is at/above the fence ceiling {fence_alt:.0f} m; ArduPilot will cap it below the fence.")
    return Outcome(PASS, ev)


# ═════════════════════════════════════════════════════════════════════════
#  DGCA regulatory
# ═════════════════════════════════════════════════════════════════════════

@rule("dgca.uin", "dgca", "UIN recorded",
      "The drone's Digital Sky Unique Identification Number (UIN) is recorded in AeroFleet for this aircraft.",
      "Register the drone on Digital Sky and enter its UIN when starting the inspection.",
      SRC_DIGITAL_SKY, "Drone Rules 2021 — registration and UIN before operation (" + SRC_DRONE_RULES + ")")
def _dgca_uin(f: Facts) -> Outcome:
    uin = (f.ctx.uin or "").strip()
    if not uin:
        return _o(FAIL, "No UIN recorded for this aircraft in AeroFleet.", drone_id=f.ctx.drone_id)
    return _o(PASS, "Recorded only — validity on Digital Sky is not verifiable over MAVLink.", uin=uin, drone_id=f.ctx.drone_id)


manual("dgca.remote_pilot", "dgca", "Remote pilot certificate",
       "The pilot in command holds a valid DGCA Remote Pilot Certificate from an authorised RPTO for this category/class.",
       "Carry the certificate; operators are responsible for checking it.", SRC_DRONE_RULES)
manual("dgca.npnt", "dgca", "NPNT / Digital Sky permission",
       "Any NPNT permission artefact / Digital Sky flight permission required for this operation is obtained.",
       "Apply on Digital Sky. NOT verifiable over MAVLink: ArduPilot exposes no NPNT state, so AeroFleet cannot sense it.",
       SRC_DIGITAL_SKY)
manual("dgca.airspace", "dgca", "Airspace zone",
       "The planned area is green zone on the Digital Sky airspace map, or yellow-zone ATC permission is held; never red zone.",
       "Check the Digital Sky airspace map for the exact operating area and date.", SRC_DIGITAL_SKY)
manual("dgca.insurance", "dgca", "Third-party insurance",
       "Valid third-party liability insurance covers this aircraft and operation.",
       "Obtain/renew cover and keep proof with the aircraft.", SRC_DRONE_RULES)
manual("dgca.type_certificate", "dgca", "Type certificate",
       "The drone model has a DGCA type certificate where one is required for its category/use.",
       "Check the model against the Digital Sky list of type-certified drones.", SRC_DIGITAL_SKY)


# ═════════════════════════════════════════════════════════════════════════
#  Report
# ═════════════════════════════════════════════════════════════════════════

RULES_BY_ID: Dict[str, Rule] = {r.id: r for r in RULES}
MANUAL_CHECK_IDS: Tuple[str, ...] = tuple(r.id for r in RULES if r.manual)
# Resolved through the motor-test wizard, not the checklist.
WIZARD_CHECK_IDS: Tuple[str, ...] = ("mot.motor_test",)


def _evaluate(r: Rule, facts: Facts) -> Outcome:
    if r.manual:
        return Outcome(MANUAL, {}, "Physical/paperwork item — cannot be sensed over MAVLink.")
    try:
        return r.evaluate(facts)  # type: ignore[misc]
    except _Missing as m:
        return Outcome(UNKNOWN, {}, f"Not measured: {m.what}.")
    except (KeyError, TypeError, ValueError, ZeroDivisionError) as exc:
        return Outcome(UNKNOWN, {}, f"Not measured: malformed data ({exc}).")


def build_report(
    snapshot: FCSnapshot,
    context: Optional[InspectionContext] = None,
    checklist: Optional[Mapping[str, Mapping[str, Any]]] = None,
    motor_test: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Evaluate every rule and roll up a verdict.

    ``checklist`` maps manual check id -> {"result": "confirmed"|"failed"|"unchecked", "note", "by", "at"}.
    ``motor_test`` is the stored motor-test record ({"results": {"A": {...}}}).

    Verdict: FAIL if any FAIL; else INCOMPLETE if a required check is
    UNKNOWN or any MANUAL item is unresolved; else WARN if any WARN; else PASS.
    """
    ctx = context or InspectionContext()
    facts = Facts(snapshot, ctx, motor_test)
    checklist = checklist or {}
    checks: List[Dict[str, Any]] = []
    for r in RULES:
        out = _evaluate(r, facts)
        entry: Dict[str, Any] = {
            "id": r.id, "category": r.category, "category_title": CATEGORY_TITLES[r.category],
            "title": r.title, "requirement": r.requirement, "status": out.status,
            "evidence": out.evidence, "detail": out.detail, "fix": r.fix, "source": r.source,
            "reference": r.reference, "kind": "manual" if r.manual else ("wizard" if r.id in WIZARD_CHECK_IDS else "measured"),
            "required": r.required, "resolved": None,
        }
        if out.status == MANUAL:
            resolved = bool(out.evidence.get("resolved"))
            item = checklist.get(r.id) if r.manual else None
            if item:
                entry["attestation"] = dict(item)
                if item.get("result") == "confirmed":
                    resolved = True
                elif item.get("result") == "failed":
                    entry["status"] = FAIL
                    entry["detail"] = "Operator reported this item as failed" + (f": {item.get('note')}" if item.get("note") else ".")
            entry["resolved"] = resolved if entry["status"] == MANUAL else None
        checks.append(entry)

    counts = {s: 0 for s in STATUSES}
    for c in checks:
        counts[c["status"]] += 1
    fails = [c["id"] for c in checks if c["status"] == FAIL]
    warns = [c["id"] for c in checks if c["status"] == WARN]
    unknown_required = [c["id"] for c in checks if c["status"] == UNKNOWN and c["required"]]
    unknown_optional = [c["id"] for c in checks if c["status"] == UNKNOWN and not c["required"]]
    manual_pending = [c["id"] for c in checks if c["status"] == MANUAL and not c["resolved"]]
    if fails:
        verdict = FAIL
    elif unknown_required or manual_pending:
        verdict = "INCOMPLETE"
    elif warns:
        verdict = WARN
    else:
        verdict = PASS

    categories = []
    for key, title in CATEGORIES:
        cat = [c for c in checks if c["category"] == key]
        cat_counts = {s: sum(1 for c in cat if c["status"] == s) for s in STATUSES}
        categories.append({"key": key, "title": title, "counts": cat_counts, "check_ids": [c["id"] for c in cat]})

    titles = {c["id"]: c["title"] for c in checks}
    return {
        "verdict": verdict,
        "counts": counts,
        "failed": [{"id": i, "title": titles[i]} for i in fails],
        "warnings": [{"id": i, "title": titles[i]} for i in warns],
        "unknown_required": [{"id": i, "title": titles[i]} for i in unknown_required],
        "unknown_optional": [{"id": i, "title": titles[i]} for i in unknown_optional],
        "manual_pending": [{"id": i, "title": titles[i]} for i in manual_pending],
        "categories": categories,
        "checks": checks,
        "context": ctx.to_dict(),
        "snapshot_notes": list(snapshot.notes),
        "firmware": ((snapshot.autopilot_version or {}).get("firmware") or {}).get("version"),
        "params_received": len(snapshot.params),
        "params_expected": snapshot.param_count_expected,
        "rules_version": RULES_VERSION,
    }


RULES_VERSION = "2026.09-1"


def rule_table() -> List[Dict[str, Any]]:
    """The static rule table (for docs/UI), without evaluating anything."""
    return [
        {"id": r.id, "category": r.category, "category_title": CATEGORY_TITLES[r.category], "title": r.title,
         "requirement": r.requirement, "fix": r.fix, "source": r.source, "reference": r.reference,
         "kind": "manual" if r.manual else ("wizard" if r.id in WIZARD_CHECK_IDS else "measured"),
         "required": r.required}
        for r in RULES
    ]
