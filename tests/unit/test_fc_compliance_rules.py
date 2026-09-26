"""Unit tests for aerofleet/hardware/compliance_rules.py — every rule
evaluated against synthetic FCSnapshots (healthy vs specific faults), plus
the honesty guarantees: missing data is UNKNOWN (never PASS), manual items
stay MANUAL when ticked, and the verdict roll-up. The same rules run
against real MAVLink from the mock vehicle in
tests/integration/test_fc_compliance_api.py.
"""
import copy
from types import MappingProxyType

import pytest

from aerofleet.hardware.compliance_rules import (
    FAIL,
    MANUAL,
    MANUAL_CHECK_IDS,
    PASS,
    RULES,
    UNKNOWN,
    WARN,
    InspectionContext,
    build_report,
    rule_table,
)
from aerofleet.hardware.fc_inspector import FCSnapshot, decode_firmware_version
from aerofleet.hardware.motor_layouts import HEXA_X, QUAD_PLUS, QUAD_X, layout_for_frame

pytestmark = pytest.mark.unit

_ALL_SENSORS = 1 | 2 | 4 | 8 | 32 | 65536 | 2097152 | 16777216 | 33554432 | 268435456

HEALTHY_PARAMS = {
    "ARMING_CHECK": 1, "LOG_BITMASK": 176126, "LOG_BACKEND_TYPE": 1,
    "INS_ACCOFFS_X": 0.05, "INS_ACCOFFS_Y": -0.11, "INS_ACCOFFS_Z": 0.2,
    "INS_ACCSCAL_X": 1.002, "INS_ACCSCAL_Y": 0.998, "INS_ACCSCAL_Z": 1.01,
    "COMPASS_DEV_ID": 97539, "COMPASS_OFS_X": -38.2, "COMPASS_OFS_Y": 12.7, "COMPASS_OFS_Z": 55.1,
    "COMPASS_OFFS_MAX": 1800, "COMPASS_EXTERNAL": 1, "FS_EKF_THRESH": 0.8, "FS_EKF_ACTION": 1,
    "BATT_MONITOR": 4, "BATT_CAPACITY": 5200, "BATT_FS_LOW_ACT": 2, "BATT_FS_CRT_ACT": 1,
    "BATT_LOW_VOLT": 14.4, "BATT_CRT_VOLT": 14.0, "BATT_LOW_MAH": 1040, "BATT_CRT_MAH": 520,
    "BRD_VBUS_MIN": 4.3, "FRAME_CLASS": 1, "FRAME_TYPE": 1,
    "SERVO1_FUNCTION": 33, "SERVO2_FUNCTION": 34, "SERVO3_FUNCTION": 35, "SERVO4_FUNCTION": 36,
    "SERVO5_FUNCTION": 0, "SERVO6_FUNCTION": 0,
    "MOT_PWM_TYPE": 0, "MOT_PWM_MIN": 1000, "MOT_PWM_MAX": 2000, "MOT_SPIN_ARM": 0.10,
    "MOT_SPIN_MIN": 0.15, "MOT_SPIN_MAX": 0.95, "MOT_THST_HOVER": 0.28, "MOT_HOVER_LEARN": 2,
    "GPS_TYPE": 1, "GPS_HDOP_GOOD": 140, "FS_THR_ENABLE": 1, "FS_THR_VALUE": 975, "RC3_MIN": 1100,
    "FS_GCS_ENABLE": 1, "FS_GCS_TIMEOUT": 5, "FS_CRASH_CHECK": 1, "FENCE_ENABLE": 1, "FENCE_TYPE": 7,
    "FENCE_ALT_MAX": 100, "FENCE_ACTION": 1, "RTL_ALT": 3000,
}


def healthy_dict():
    cells = [4050, 4060, 4040, 4050]
    return {
        "connection": "udpin:127.0.0.1:14550", "source": "mission_planner_forward", "captured_at": 1.0,
        "sample_seconds": 6.0,
        "heartbeat": {"type": 2, "autopilot": 3, "base_mode": 81, "custom_mode": 0, "system_status": 3,
                      "mavlink_version": 3, "system_id": 1, "component_id": 1, "armed": False},
        "autopilot_version": {"firmware": decode_firmware_version((4 << 24) | (5 << 16) | (7 << 8) | 255),
                              "board_id": 9, "vendor_id": 0x1209, "product_id": 0x5740, "uid": "00AB"},
        "params": dict(HEALTHY_PARAMS), "param_count_expected": len(HEALTHY_PARAMS), "params_missing_count": 0,
        "telemetry": {
            "SYS_STATUS": {"onboard_control_sensors_present": _ALL_SENSORS, "onboard_control_sensors_enabled": _ALL_SENSORS,
                           "onboard_control_sensors_health": _ALL_SENSORS, "voltage_battery": sum(cells),
                           "current_battery": 85},
            "BATTERY_STATUS": {"voltages": cells + [65535] * 6, "voltages_ext": [0, 0, 0, 0], "current_battery": 85},
            "GPS_RAW_INT": {"fix_type": 3, "satellites_visible": 14, "eph": 78},
            "EKF_STATUS_REPORT": {"flags": 831, "velocity_variance": 0.04, "pos_horiz_variance": 0.03,
                                  "pos_vert_variance": 0.05, "compass_variance": 0.02},
            "POWER_STATUS": {"Vcc": 5120, "Vservo": 0, "flags": 5},
            "RC_CHANNELS": {"chancount": 16, "rssi": 212},
            "RADIO_STATUS": {"rssi": 182, "remrssi": 176, "noise": 44, "remnoise": 47, "rxerrors": 0},
            "ESC_TELEMETRY_1_TO_4": {"temperature": [29, 29, 29, 29], "voltage": [1621] * 4, "current": [0] * 4,
                                     "rpm": [0] * 4, "count": [10, 10, 10, 10]},
        },
        "vibration_samples": [
            {"vibration_x": 2.1, "vibration_y": 2.4, "vibration_z": 3.8, "clipping_0": 0, "clipping_1": 0, "clipping_2": 0},
            {"vibration_x": 2.2, "vibration_y": 2.3, "vibration_z": 3.7, "clipping_0": 0, "clipping_1": 0, "clipping_2": 0},
        ],
        "esc_rpm_max": [0] * 8, "statustexts": [], "prearm_messages": [], "prearm_command_result": "ACCEPTED",
        "message_counts": {}, "notes": [],
    }


CTX = InspectionContext(uin="UA-0001-TEST", weight_kg=12.5, weight_source="test", drone_id="D1")


def report_for(d, ctx=CTX, **kw):
    return build_report(FCSnapshot.from_dict(d), ctx, **kw)


def status(report, check_id):
    return next(c for c in report["checks"] if c["id"] == check_id)["status"]


def check(report, check_id):
    return next(c for c in report["checks"] if c["id"] == check_id)


# ─────────────────────────────────────────────────────────────────────────

class TestRuleTable:
    def test_every_rule_has_the_required_fields_and_a_source(self):
        ids = [r.id for r in RULES]
        assert len(ids) == len(set(ids)), "duplicate rule ids"
        for row in rule_table():
            for key in ("id", "category", "title", "requirement", "fix", "source"):
                assert row[key], f"{row['id']} missing {key}"
            assert row["source"].startswith("https://")

    def test_all_seven_categories_are_populated(self):
        cats = {r.category for r in RULES}
        assert cats == {"flight_controller", "battery", "motors", "airframe", "wiring", "failsafes", "dgca"}

    def test_npnt_is_manual_and_says_it_is_not_verifiable_over_mavlink(self):
        rule = next(r for r in RULES if r.id == "dgca.npnt")
        assert rule.manual
        assert "NOT verifiable over MAVLink" in rule.fix


class TestHealthySnapshot:
    def test_healthy_aircraft_has_no_fail_warn_or_unknown(self):
        rep = report_for(healthy_dict())
        bad = [(c["id"], c["status"], c["detail"]) for c in rep["checks"] if c["status"] in (FAIL, WARN, UNKNOWN)]
        assert bad == []
        # Only the unticked manual items keep it from a full PASS.
        assert rep["verdict"] == "INCOMPLETE"
        assert {m["id"] for m in rep["manual_pending"]} == set(MANUAL_CHECK_IDS) | {"mot.motor_test"}

    def test_every_measured_pass_carries_evidence(self):
        rep = report_for(healthy_dict())
        for c in rep["checks"]:
            if c["status"] == PASS:
                assert c["evidence"], f"{c['id']} passed without evidence"

    def test_verdict_is_pass_once_manual_items_and_motor_test_are_confirmed(self):
        checklist = {cid: {"result": "confirmed", "by": "op"} for cid in MANUAL_CHECK_IDS}
        motor = {"results": {l: {"confirmation": {"result": "correct"}, "esc_corroboration": {"status": "corroborated"}}
                             for l in "ABCD"}}
        rep = report_for(healthy_dict(), checklist=checklist, motor_test=motor)
        assert rep["verdict"] == PASS
        # Attested items stay MANUAL — an operator's tick is not a measurement.
        assert status(rep, "air.props") == MANUAL and check(rep, "air.props")["resolved"] is True
        assert check(rep, "mot.motor_test")["resolved"] is True


class TestFaults:
    """One fault at a time, each producing its specific FAIL/WARN."""

    @pytest.mark.parametrize("param,value,check_id,expected", [
        ("BATT_FS_LOW_ACT", 0, "batt.fs_low_action", FAIL),
        ("BATT_FS_CRT_ACT", 0, "batt.fs_critical_action", FAIL),
        ("BATT_FS_LOW_ACT", 5, "batt.fs_low_action", WARN),
        ("BATT_CRT_VOLT", 14.6, "batt.fs_thresholds", FAIL),
        ("BATT_MONITOR", 0, "batt.monitor", FAIL),
        ("BATT_CAPACITY", 3300, "batt.capacity", WARN),
        ("FENCE_ALT_MAX", 150, "fs.fence_altitude", FAIL),
        ("FENCE_ALT_MAX", 120, "fs.fence_altitude", PASS),
        ("FENCE_TYPE", 6, "fs.fence_altitude", FAIL),
        ("FENCE_ENABLE", 0, "fs.fence_enabled", FAIL),
        ("FENCE_ACTION", 0, "fs.fence_action", FAIL),
        ("FS_THR_ENABLE", 0, "fs.rc_loss", FAIL),
        ("FS_THR_VALUE", 1150, "fs.rc_loss", FAIL),
        ("FS_GCS_ENABLE", 0, "fs.gcs_loss", WARN),
        ("FS_CRASH_CHECK", 0, "fs.crash_check", FAIL),
        ("FS_EKF_THRESH", 0, "fs.ekf", FAIL),
        ("RTL_ALT", 15000, "fs.rtl_altitude", FAIL),
        ("RTL_ALT", 12000, "fs.rtl_altitude", WARN),  # 120 m at/above the 100 m fence
        ("ARMING_CHECK", 0, "fc.arming_check", FAIL),
        ("ARMING_CHECK", 1048574, "fc.arming_check", WARN),
        ("LOG_BITMASK", 0, "fc.logging", FAIL),
        ("FRAME_CLASS", 0, "mot.frame", FAIL),
        ("MOT_SPIN_ARM", 0.16, "mot.spin_arm_min", FAIL),
        ("MOT_PWM_MIN", 2000, "mot.pwm_range", FAIL),
        ("MOT_THST_HOVER", 0.64, "air.hover_throttle", WARN),
        ("MOT_THST_HOVER", 0.35, "air.hover_throttle", UNKNOWN),
        ("GPS_TYPE", 0, "wir.gps_type", FAIL),
        ("COMPASS_EXTERNAL", 0, "wir.compass_external", WARN),
    ])
    def test_parameter_fault(self, param, value, check_id, expected):
        d = healthy_dict()
        d["params"][param] = value
        assert status(report_for(d), check_id) == expected

    def test_duplicated_motor_output_names_both_problems(self):
        d = healthy_dict()
        d["params"]["SERVO3_FUNCTION"] = 33
        c = check(report_for(d), "mot.output_mapping")
        assert c["status"] == FAIL
        assert c["evidence"]["duplicated"] == {"Motor1": [1, 3]}
        assert c["evidence"]["missing"] == ["Motor3"]

    def test_unbalanced_cell_fails_balance_but_not_minimum(self):
        d = healthy_dict()
        d["telemetry"]["BATTERY_STATUS"]["voltages"][2] = 3810
        rep = report_for(d)
        assert status(rep, "batt.cell_balance") == FAIL
        assert status(rep, "batt.cell_min") == PASS

    def test_low_cell_fails_minimum(self):
        d = healthy_dict()
        d["telemetry"]["BATTERY_STATUS"]["voltages"] = [3450, 3460, 3440, 3450] + [65535] * 6
        assert status(report_for(d), "batt.cell_min") == FAIL

    def test_missing_compass(self):
        d = healthy_dict()
        for k in ("onboard_control_sensors_present", "onboard_control_sensors_enabled", "onboard_control_sensors_health"):
            d["telemetry"]["SYS_STATUS"][k] &= ~4
        d["params"]["COMPASS_DEV_ID"] = 0
        rep = report_for(d)
        assert status(rep, "fc.sensor_mag") == FAIL
        assert status(rep, "fc.compass_calibrated") == UNKNOWN  # nothing to assess, and it says why

    def test_unhealthy_gyro(self):
        d = healthy_dict()
        d["telemetry"]["SYS_STATUS"]["onboard_control_sensors_health"] &= ~1
        assert status(report_for(d), "fc.sensor_gyro") == FAIL

    def test_uncalibrated_accel_and_compass(self):
        d = healthy_dict()
        d["params"].update({"INS_ACCOFFS_X": 0, "INS_ACCOFFS_Y": 0, "INS_ACCOFFS_Z": 0,
                            "INS_ACCSCAL_X": 1, "INS_ACCSCAL_Y": 1, "INS_ACCSCAL_Z": 1,
                            "COMPASS_OFS_X": 0, "COMPASS_OFS_Y": 0, "COMPASS_OFS_Z": 0})
        rep = report_for(d)
        assert status(rep, "fc.accel_calibrated") == FAIL
        assert status(rep, "fc.compass_calibrated") == FAIL

    @pytest.mark.parametrize("peak,clip_growth,expected", [
        (25.0, 0, PASS), (45.0, 0, WARN), (65.0, 0, FAIL), (10.0, 3, FAIL),
    ])
    def test_vibration_thresholds(self, peak, clip_growth, expected):
        d = healthy_dict()
        d["vibration_samples"] = [
            {"vibration_x": 1, "vibration_y": 1, "vibration_z": peak, "clipping_0": 5, "clipping_1": 0, "clipping_2": 0},
            {"vibration_x": 1, "vibration_y": 1, "vibration_z": peak, "clipping_0": 5 + clip_growth, "clipping_1": 0, "clipping_2": 0},
        ]
        assert status(report_for(d), "fc.vibration") == expected

    def test_ekf_two_high_variances_is_the_failsafe_condition(self):
        d = healthy_dict()
        d["telemetry"]["EKF_STATUS_REPORT"].update(velocity_variance=0.9, pos_horiz_variance=0.85)
        assert status(report_for(d), "fc.ekf") == FAIL
        d["telemetry"]["EKF_STATUS_REPORT"].update(pos_horiz_variance=0.1)
        assert status(report_for(d), "fc.ekf") == WARN

    @pytest.mark.parametrize("vcc,expected", [(5120, PASS), (4950, PASS), (4600, WARN), (5600, WARN), (4200, FAIL), (5900, FAIL)])
    def test_board_voltage(self, vcc, expected):
        d = healthy_dict()
        d["telemetry"]["POWER_STATUS"]["Vcc"] = vcc
        assert status(report_for(d), "batt.board_vcc") == expected

    def test_prearm_messages_fail(self):
        d = healthy_dict()
        d["prearm_messages"] = ["PreArm: Compass not healthy"]
        c = check(report_for(d), "fc.prearm")
        assert c["status"] == FAIL and c["evidence"]["prearm_messages"] == ["PreArm: Compass not healthy"]

    def test_no_rc_receiver(self):
        d = healthy_dict()
        d["telemetry"]["RC_CHANNELS"]["chancount"] = 0
        assert status(report_for(d), "wir.rc_receiver") == FAIL

    def test_current_sensor_reading_zero_is_flagged(self):
        d = healthy_dict()
        d["telemetry"]["BATTERY_STATUS"]["current_battery"] = 0
        assert status(report_for(d), "wir.current_sensor") == WARN

    def test_dgca_weight_near_boundary_warns(self):
        rep = report_for(healthy_dict(), InspectionContext(uin="U", weight_kg=24.0))
        c = check(rep, "air.dgca_category")
        assert c["status"] == WARN and c["evidence"]["category"] == "Small"

    def test_missing_uin_fails(self):
        rep = report_for(healthy_dict(), InspectionContext(weight_kg=12.5))
        assert status(rep, "dgca.uin") == FAIL
        assert rep["verdict"] == FAIL


class TestBenchMode:
    def _no_fix(self):
        d = healthy_dict()
        d["telemetry"]["GPS_RAW_INT"] = {"fix_type": 1, "satellites_visible": 3, "eph": 9999}
        d["prearm_messages"] = ["PreArm: GPS 1: Bad fix", "PreArm: Fence requires position"]
        return d

    def test_no_fix_fails_outdoors(self):
        rep = report_for(self._no_fix())
        assert status(rep, "wir.gps_fix") == FAIL
        assert status(rep, "fc.prearm") == FAIL

    def test_no_fix_is_only_a_warning_on_the_bench(self):
        rep = report_for(self._no_fix(), InspectionContext(uin="U", weight_kg=12.5, bench_mode=True))
        assert status(rep, "wir.gps_fix") == WARN
        assert status(rep, "fc.prearm") == WARN

    def test_bench_mode_does_not_excuse_non_gps_prearm_failures(self):
        d = self._no_fix()
        d["prearm_messages"].append("PreArm: Check MOT_SPIN_ARM")
        rep = report_for(d, InspectionContext(uin="U", weight_kg=12.5, bench_mode=True))
        assert status(rep, "fc.prearm") == FAIL


class TestHonesty:
    def test_no_parameters_means_unknown_never_pass(self):
        d = healthy_dict()
        d["params"] = {}
        rep = report_for(d)
        for cid in ("batt.fs_low_action", "fs.fence_altitude", "mot.output_mapping", "fc.arming_check", "fs.rc_loss"):
            assert status(rep, cid) == UNKNOWN, cid
            assert "Not measured" in check(rep, cid)["detail"]
        assert rep["verdict"] == "INCOMPLETE"

    def test_no_telemetry_means_unknown(self):
        d = healthy_dict()
        d["telemetry"] = {}
        d["vibration_samples"] = []
        rep = report_for(d)
        for cid in ("fc.sensor_gyro", "fc.ekf", "fc.vibration", "wir.gps_fix", "wir.rc_receiver", "batt.board_vcc", "batt.voltage"):
            assert status(rep, cid) == UNKNOWN, cid

    def test_pack_voltage_only_monitor_cannot_claim_cell_balance(self):
        d = healthy_dict()
        # ArduPilot puts the pack total in voltages[0] when there is no cell data.
        d["telemetry"]["BATTERY_STATUS"]["voltages"] = [16210] + [65535] * 9
        rep = report_for(d)
        assert status(rep, "batt.cell_balance") == UNKNOWN
        assert status(rep, "batt.cell_min") == UNKNOWN
        v = check(rep, "batt.voltage")
        assert v["status"] == PASS and v["evidence"]["cell_count"] == 4
        assert "inferred" in v["evidence"]["cell_count_method"]

    def test_optional_unknowns_do_not_block_the_verdict_but_required_ones_do(self):
        d = healthy_dict()
        del d["telemetry"]["ESC_TELEMETRY_1_TO_4"]
        checklist = {cid: {"result": "confirmed"} for cid in MANUAL_CHECK_IDS}
        motor = {"results": {l: {"confirmation": {"result": "correct"}} for l in "ABCD"}}
        rep = report_for(d, checklist=checklist, motor_test=motor)
        assert status(rep, "mot.esc_telemetry") == UNKNOWN
        assert rep["verdict"] == PASS
        del d["telemetry"]["GPS_RAW_INT"]
        assert report_for(d, checklist=checklist, motor_test=motor)["verdict"] == "INCOMPLETE"

    def test_operator_failing_a_manual_item_fails_the_report(self):
        rep = report_for(healthy_dict(), checklist={"air.frame_integrity": {"result": "failed", "note": "crack in arm 2"}})
        c = check(rep, "air.frame_integrity")
        assert c["status"] == FAIL and "crack in arm 2" in c["detail"]
        assert rep["verdict"] == FAIL

    def test_no_radio_status_is_manual_not_pass(self):
        d = healthy_dict()
        del d["telemetry"]["RADIO_STATUS"]
        assert status(report_for(d), "wir.telemetry_radio") == MANUAL

    def test_snapshot_is_immutable(self):
        snap = FCSnapshot.from_dict(healthy_dict())
        assert isinstance(snap.params, MappingProxyType)
        with pytest.raises(TypeError):
            snap.params["FENCE_ALT_MAX"] = 500  # type: ignore[index]
        with pytest.raises(Exception):
            snap.source = "x"  # type: ignore[misc]
        assert FCSnapshot.from_dict(snap.to_dict()).to_dict() == snap.to_dict()


class TestMotorTestRule:
    def test_incorrect_motor_fails(self):
        motor = {"results": {"A": {"confirmation": {"result": "incorrect"}}}}
        assert status(report_for(healthy_dict(), motor_test=motor), "mot.motor_test") == FAIL

    def test_esc_disagreement_warns_even_if_operator_confirmed(self):
        motor = {"results": {l: {"confirmation": {"result": "correct"},
                                 "esc_corroboration": {"status": "mismatch" if l == "A" else "corroborated"}}
                             for l in "ABCD"}}
        assert status(report_for(healthy_dict(), motor_test=motor), "mot.motor_test") == WARN

    def test_partial_test_is_still_manual_pending(self):
        motor = {"results": {"A": {"confirmation": {"result": "correct"}}}}
        c = check(report_for(healthy_dict(), motor_test=motor), "mot.motor_test")
        assert c["status"] == MANUAL and not c["resolved"]


class TestMotorLayouts:
    """Cross-checked against AP_MotorsMatrix.cpp (Copter-4.5)."""

    def test_quad_x(self):
        assert [(m.letter, m.motor_number, m.position_label, m.direction)
                for m in sorted(QUAD_X.motors, key=lambda m: m.test_order)] == [
            ("A", 1, "front-right", "CCW"), ("B", 4, "rear-right", "CW"),
            ("C", 2, "rear-left", "CCW"), ("D", 3, "front-left", "CW")]

    def test_quad_plus(self):
        assert [(m.letter, m.motor_number, m.position_label, m.direction)
                for m in sorted(QUAD_PLUS.motors, key=lambda m: m.test_order)] == [
            ("A", 3, "front", "CW"), ("B", 1, "right", "CCW"),
            ("C", 4, "rear", "CW"), ("D", 2, "left", "CCW")]

    def test_hexa_x(self):
        assert [(m.letter, m.motor_number, m.direction) for m in sorted(HEXA_X.motors, key=lambda m: m.test_order)] == [
            ("A", 5, "CCW"), ("B", 1, "CW"), ("C", 4, "CCW"), ("D", 6, "CW"), ("E", 2, "CCW"), ("F", 3, "CW")]

    def test_letters_run_clockwise_from_the_nose(self):
        for layout in (QUAD_X, QUAD_PLUS, HEXA_X):
            angles = [m.angle_deg % 360 for m in sorted(layout.motors, key=lambda m: m.test_order)]
            assert angles == sorted(angles), layout.key

    def test_frame_lookup(self):
        assert layout_for_frame(1, 1) is QUAD_X
        assert layout_for_frame(1.0, 0.0) is QUAD_PLUS
        assert layout_for_frame(2, 1) is HEXA_X
        assert layout_for_frame(3, 1) is None
