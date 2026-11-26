"""A failsafe switched off is flagged whatever the approved baseline says (readiness: check first)."""
from aerofleet.assurance.readiness import assess, failsafes_off


def test_px4_failsafes_at_their_documented_off_value():
    off = failsafes_off({"NAV_RCL_ACT": 0, "COM_LOW_BAT_ACT": 0, "GF_ACTION": 1})
    assert [f["name"] for f in off] == ["NAV_RCL_ACT", "COM_LOW_BAT_ACT"]
    assert failsafes_off({"NAV_RCL_ACT": 2, "COM_LOW_BAT_ACT": 2, "GF_ACTION": 1}) == [] and failsafes_off({}) == []


def test_ardupilot_failsafes_come_from_the_compliance_rules():
    off = {f["name"] for f in failsafes_off({"FS_THR_ENABLE": 0, "BATT_FS_LOW_ACT": 0, "BATT_FS_CRT_ACT": 0, "FENCE_ENABLE": 0})}
    assert {"FS_THR_ENABLE", "BATT_FS_LOW_ACT", "FENCE_ENABLE"} <= off


def test_an_approved_configuration_with_a_failsafe_off_is_still_check_first():
    settings = {"verdict": "OK", "critical": [], "limits": [], "failsafes_off": [{"name": "BATT_FS_LOW_ACT", "title": "Low-battery failsafe"}]}
    row = assess("D1", settings, {"uin": "U", "status": "VERIFIED"}, None)
    assert row["status"] == "CHECK_FIRST" and row["reasons"][0]["code"] == "failsafe_off"
    assert "BATT_FS_LOW_ACT" in row["reasons"][0]["text"]
