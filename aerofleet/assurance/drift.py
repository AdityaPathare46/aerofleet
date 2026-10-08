"""Configuration drift: what changed on this drone's flight controller, and does it matter?

Compares a drone's current parameters with (a) the fleet's approved baseline and (b) the same drone's
previous snapshot. Everything here is a plain dictionary comparison plus a curated catalogue that
says how much a parameter matters for safety — no model, no judgement:

  CRITICAL  failsafes, battery failsafes, geofence, arming checks, return-to-launch altitude,
            PX4 circuit breakers. An unapproved change BLOCKS the drone.
  HIGH      flight envelope and airframe definition (tilt and speed limits, frame class/type,
            motor output mapping and limits). Needs REVIEW.
  TUNING    controller gains and estimator settings. Reported, does not block.
  INFO      anything else.
  IGNORED   values the autopilot rewrites by itself (flight-time counters, ground pressure,
            calibration offsets): reporting them would bury real changes in noise.

The catalogue below was written from the ArduPilot (Copter) and PX4 parameter references. It is a
starting list, deliberately conservative, and should be reviewed against the firmware version a
fleet actually flies (MASTER_PLAN item 1.8 measures its catch rate and false alarms).
"""
from __future__ import annotations

from fnmatch import fnmatchcase
from typing import Any, Dict, List, Mapping, Optional

CRITICAL, HIGH, TUNING, INFO = "CRITICAL", "HIGH", "TUNING", "INFO"
SEVERITY_ORDER = {CRITICAL: 0, HIGH: 1, TUNING: 2, INFO: 3}
BLOCK, REVIEW, OK = "BLOCK", "REVIEW", "OK"

IGNORED_PATTERNS = (
    "STAT_*", "SYS_NUM_RESETS", "*_GND_PRESS", "GND_ABS_PRESS*", "GND_TEMP", "BARO*_GND_*", "LOG_LASTFILE",
    "COMPASS_OFS*", "COMPASS_DIA*", "COMPASS_ODI*", "COMPASS_MOT*", "COMPASS_DEC", "INS_ACC*OFFS_*", "INS_ACC*SCAL_*",
    "INS_GYR*OFFS_*", "INS_ACC*_CALTEMP", "INS_GYR*_CALTEMP", "AHRS_TRIM_*", "CAL_*", "LND_FLIGHT_T_*", "COM_FLIGHT_UUID",
)
CATALOGUE = (
    # ArduPilot
    (CRITICAL, ("FS_*", "BATT*_FS_*", "BATT*_LOW_VOLT", "BATT*_CRT_VOLT", "BATT*_LOW_MAH", "BATT*_CRT_MAH", "BATT*_ARM_VOLT",
                "FENCE_*", "ARMING_CHECK", "ARMING_REQUIRE", "RTL_ALT", "RTL_ALT_FINAL", "RTL_CLIMB_MIN", "BRD_SAFETY*",
                "RC_OPTIONS", "THR_FAILSAFE", "THR_FS_VALUE", "AVD_*")),
    (HIGH, ("ANGLE_MAX", "WPNAV_SPEED*", "WPNAV_ACCEL*", "WPNAV_RADIUS", "PILOT_SPEED_*", "PILOT_ACCEL_Z", "LAND_SPEED*",
            "LOIT_SPEED", "LOIT_ANG_MAX", "FRAME_CLASS", "FRAME_TYPE", "MOT_SPIN_*", "MOT_BAT_*", "MOT_PWM_*", "MOT_THST_*",
            "SERVO*_FUNCTION", "SERVO*_MIN", "SERVO*_MAX", "SERVO*_REVERSED", "BATT*_CAPACITY", "BATT*_MONITOR",
            "GPS_TYPE*", "EK3_ENABLE", "AHRS_EKF_TYPE", "FLTMODE*", "SERIAL*_PROTOCOL", "SYSID_THISMAV")),
    (TUNING, ("ATC_*", "PSC_*", "INS_*", "EK2_*", "EK3_*", "AUTOTUNE_*", "ACRO_*")),
    # PX4
    (CRITICAL, ("COM_LOW_BAT_ACT", "COM_RC_LOSS_T", "COM_DL_LOSS_T", "COM_OBL_*", "COM_OF_LOSS_T", "COM_ARM_*", "COM_PREARM_MODE",
                "NAV_DLL_ACT", "NAV_RCL_ACT", "GF_*", "RTL_RETURN_ALT", "RTL_DESCEND_ALT", "RTL_MIN_DIST", "BAT*_CRIT_THR",
                "BAT*_LOW_THR", "BAT*_EMERGEN_THR", "CBRK_*", "COM_POS_FS_*", "COM_VEL_FS_*", "FD_*")),
    (HIGH, ("MPC_XY_VEL_MAX", "MPC_XY_CRUISE", "MPC_Z_VEL_MAX_*", "MPC_TILTMAX_*", "MPC_MAN_TILT_MAX", "MPC_LAND_SPEED",
            "MPC_TKO_SPEED", "SYS_AUTOSTART", "MAV_TYPE", "CA_*", "PWM_*", "BAT*_CAPACITY", "BAT*_N_CELLS", "COM_FLTMODE*",
            "EKF2_EN", "MAV_SYS_ID")),
    (TUNING, ("MC_*", "MPC_*", "EKF2_*", "FW_*")),
)


def _matches(name: str, patterns) -> bool:
    return any(fnmatchcase(name, p) for p in patterns)


def severity_of(name: str) -> Optional[str]:
    """CRITICAL / HIGH / TUNING / INFO, or None when the parameter is ignored (self-rewritten)."""
    if _matches(name, IGNORED_PATTERNS):
        return None
    for sev, patterns in CATALOGUE:
        if _matches(name, patterns):
            return sev
    return INFO


def _same(a: float, b: float) -> bool:
    # parameters travel as float32; allow that much rounding and nothing more
    return abs(a - b) <= 1e-6 * max(1.0, abs(a), abs(b))


def diff(current: Mapping[str, float], reference: Mapping[str, float], approved: Optional[Mapping[str, float]] = None
         ) -> List[Dict[str, Any]]:
    """Changes from `reference` to `current`, most severe first. A change is `approved` when the fleet
    manager has signed off that exact value for that parameter."""
    approved = approved or {}
    out: List[Dict[str, Any]] = []
    for name in sorted(set(current) | set(reference)):
        sev = severity_of(name)
        if sev is None:
            continue
        old, new = reference.get(name), current.get(name)
        if old is not None and new is not None and _same(old, new):
            continue
        kind = "changed" if old is not None and new is not None else "added" if old is None else "removed"
        ok = new is not None and name in approved and _same(approved[name], new)
        out.append({"name": name, "kind": kind, "old": old, "new": new, "severity": sev, "approved": ok})
    out.sort(key=lambda c: (SEVERITY_ORDER[c["severity"]], c["name"]))
    return out


def _verdict(changes: List[Dict[str, Any]]) -> str:
    open_changes = [c for c in changes if not c["approved"]]
    if any(c["severity"] == CRITICAL for c in open_changes):
        return BLOCK
    if any(c["severity"] == HIGH for c in open_changes):
        return REVIEW
    return OK


def _counts(changes: List[Dict[str, Any]]) -> Dict[str, int]:
    counts = {s: 0 for s in SEVERITY_ORDER}
    for c in changes:
        if not c["approved"]:
            counts[c["severity"]] += 1
    return counts


def drift_report(current: Mapping[str, float], baseline: Optional[Mapping[str, float]] = None,
                 previous: Optional[Mapping[str, float]] = None, approved: Optional[Mapping[str, float]] = None
                 ) -> Dict[str, Any]:
    """The drone's drift against the fleet baseline and against its own previous snapshot.

    The verdict comes from the baseline comparison when there is a baseline (that is the approved
    configuration); otherwise from the previous snapshot; with neither there is nothing to compare
    and the verdict is NO_REFERENCE — never a silent pass.
    """
    report: Dict[str, Any] = {"param_count": len(current), "vs_baseline": None, "vs_previous": None}
    for key, ref in (("vs_baseline", baseline), ("vs_previous", previous)):
        if ref is not None:
            changes = diff(current, ref, approved)
            report[key] = {"verdict": _verdict(changes), "counts": _counts(changes), "changes": changes}
    decided_by = "vs_baseline" if baseline is not None else "vs_previous" if previous is not None else None
    report["verdict"] = report[decided_by]["verdict"] if decided_by else "NO_REFERENCE"
    report["decided_by"] = decided_by
    return report
