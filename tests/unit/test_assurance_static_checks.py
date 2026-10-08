"""The FC compliance rules run on a parameter file alone (aerofleet/assurance/static_checks.py)."""
import pytest

from aerofleet.assurance.static_checks import checks_from_params

pytestmark = pytest.mark.unit

GOOD = {"FS_THR_ENABLE": 1, "FENCE_ENABLE": 1, "RTL_ALT": 1500, "ARMING_CHECK": 1, "BATT_MONITOR": 4, "BATT_CAPACITY": 5200,
        "BATT_FS_LOW_ACT": 2, "BATT_FS_CRT_ACT": 1, "BATT_LOW_VOLT": 14.0, "BATT_CRT_VOLT": 13.2, "FRAME_CLASS": 1, "FRAME_TYPE": 1}


def _by_id(report, group):
    return {c["id"]: c for c in report[group]}


def test_every_rule_lands_in_exactly_one_group_and_counts_add_up():
    r = checks_from_params(GOOD)
    c = r["counts"]
    assert c["total"] == 59 == c["evaluated"] + c["needs_live"] + c["manual"]
    assert c["evaluated"] == c["PASS"] + c["WARN"] + c["FAIL"] == len(r["evaluated"])
    assert {x["status"] for x in r["needs_live"]} == {"UNKNOWN"} and {x["status"] for x in r["manual"]} == {"MANUAL"}


def test_parameter_rules_are_decided_from_the_file_and_sensor_rules_are_not():
    r = checks_from_params(GOOD)
    evaluated = _by_id(r, "evaluated")
    for rule_id in ("fc.arming_check", "batt.fs_low_action", "fs.rc_loss", "fs.fence_enabled", "fs.rtl_altitude", "mot.frame"):
        assert evaluated[rule_id]["status"] == "PASS", rule_id
    assert {"fc.ekf", "fc.vibration", "fc.sensor_gyro"} <= set(_by_id(r, "needs_live"))
    assert "air.props" in _by_id(r, "manual")


def test_a_disabled_failsafe_fails_the_file_verdict_with_a_fix():
    r = checks_from_params(dict(GOOD, FS_THR_ENABLE=0))
    bad = _by_id(r, "evaluated")["fs.rc_loss"]
    assert bad["status"] == "FAIL" and bad["fix"]
    assert r["verdict"] == "FAIL" and r["counts"]["FAIL"] >= 1


def test_the_report_never_reads_as_a_full_inspection():
    r = checks_from_params(GOOD)
    assert r["source"] == "param_file" and "not covered" in r["note"] and r["counts"]["needs_live"] > 0
