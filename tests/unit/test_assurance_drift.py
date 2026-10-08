"""Configuration drift (aerofleet/assurance/drift.py)."""
import pytest

from aerofleet.assurance.drift import BLOCK, CRITICAL, HIGH, INFO, OK, REVIEW, TUNING, diff, drift_report, severity_of

pytestmark = pytest.mark.unit

BASE = {"FS_THR_ENABLE": 1, "BATT_FS_LOW_ACT": 2, "FENCE_ENABLE": 1, "RTL_ALT": 1500, "ANGLE_MAX": 3000,
        "ATC_RAT_RLL_P": 0.135, "STAT_FLTTIME": 1200, "COMPASS_OFS_X": 12.0, "SCHED_LOOP_RATE": 400}


def test_severity_catalogue_on_known_parameters():
    assert severity_of("FS_THR_ENABLE") == CRITICAL and severity_of("BATT2_FS_CRT_ACT") == CRITICAL
    assert severity_of("FENCE_ALT_MAX") == CRITICAL and severity_of("ARMING_CHECK") == CRITICAL
    assert severity_of("COM_LOW_BAT_ACT") == CRITICAL and severity_of("CBRK_SUPPLY_CHK") == CRITICAL
    assert severity_of("ANGLE_MAX") == HIGH and severity_of("FRAME_CLASS") == HIGH and severity_of("MPC_XY_VEL_MAX") == HIGH
    assert severity_of("ATC_RAT_RLL_P") == TUNING and severity_of("MPC_XY_P") == TUNING
    assert severity_of("SCHED_LOOP_RATE") == INFO
    assert severity_of("STAT_FLTTIME") is None and severity_of("COMPASS_OFS_X") is None


def test_identical_configuration_has_no_drift():
    r = drift_report(dict(BASE), baseline=BASE)
    assert r["verdict"] == OK and r["vs_baseline"]["changes"] == []


def test_disabled_failsafe_blocks_and_is_listed_first():
    cur = dict(BASE, FS_THR_ENABLE=0, ATC_RAT_RLL_P=0.2, ANGLE_MAX=4500)
    r = drift_report(cur, baseline=BASE)
    assert r["verdict"] == BLOCK and r["decided_by"] == "vs_baseline"
    names = [c["name"] for c in r["vs_baseline"]["changes"]]
    assert names == ["FS_THR_ENABLE", "ANGLE_MAX", "ATC_RAT_RLL_P"]
    first = r["vs_baseline"]["changes"][0]
    assert first == {"name": "FS_THR_ENABLE", "kind": "changed", "old": 1, "new": 0, "severity": CRITICAL, "approved": False}
    assert r["vs_baseline"]["counts"] == {CRITICAL: 1, HIGH: 1, TUNING: 1, INFO: 0}


def test_envelope_change_alone_needs_review_and_tuning_alone_passes():
    assert drift_report(dict(BASE, ANGLE_MAX=4500), baseline=BASE)["verdict"] == REVIEW
    assert drift_report(dict(BASE, ATC_RAT_RLL_P=0.2), baseline=BASE)["verdict"] == OK


def test_self_rewritten_values_never_count_as_drift():
    cur = dict(BASE, STAT_FLTTIME=99999, COMPASS_OFS_X=-40.0)
    assert drift_report(cur, baseline=BASE)["vs_baseline"]["changes"] == []


def test_float32_rounding_is_not_drift_but_a_real_change_is():
    assert diff({"RTL_ALT": 1500.00001}, {"RTL_ALT": 1500.0}) == []
    assert len(diff({"ATC_RAT_RLL_P": 0.1351}, {"ATC_RAT_RLL_P": 0.135})) == 1


def test_added_and_removed_parameters_are_reported():
    changes = diff({"FENCE_ENABLE": 1, "NEW_PARAM": 5}, {"FENCE_ENABLE": 1, "RTL_ALT": 1500})
    assert [(c["name"], c["kind"]) for c in changes] == [("RTL_ALT", "removed"), ("NEW_PARAM", "added")]
    assert drift_report({"FENCE_ENABLE": 1}, baseline={"FENCE_ENABLE": 1, "RTL_ALT": 1500})["verdict"] == BLOCK


def test_manager_approval_of_the_exact_value_clears_the_block_only_for_that_value():
    cur = dict(BASE, RTL_ALT=3000)
    assert drift_report(cur, baseline=BASE)["verdict"] == BLOCK
    r = drift_report(cur, baseline=BASE, approved={"RTL_ALT": 3000})
    assert r["verdict"] == OK and r["vs_baseline"]["changes"][0]["approved"] is True
    assert drift_report(dict(BASE, RTL_ALT=500), baseline=BASE, approved={"RTL_ALT": 3000})["verdict"] == BLOCK


def test_baseline_decides_but_previous_snapshot_is_still_reported():
    previous = dict(BASE, RTL_ALT=3000)          # already drifted last time
    cur = dict(BASE, RTL_ALT=3000, FENCE_ENABLE=0)
    r = drift_report(cur, baseline=BASE, previous=previous)
    assert {c["name"] for c in r["vs_baseline"]["changes"]} == {"RTL_ALT", "FENCE_ENABLE"}
    assert [c["name"] for c in r["vs_previous"]["changes"]] == ["FENCE_ENABLE"]   # what is new since last time


def test_without_any_reference_the_verdict_is_not_a_silent_pass():
    r = drift_report(dict(BASE))
    assert r["verdict"] == "NO_REFERENCE" and r["decided_by"] is None
    assert drift_report(dict(BASE, FS_THR_ENABLE=0), previous=BASE)["decided_by"] == "vs_previous"
