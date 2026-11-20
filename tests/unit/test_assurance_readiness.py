"""Morning readiness rules (aerofleet/assurance/readiness.py)."""
from aerofleet.assurance.readiness import CHECK_FIRST, DO_NOT_FLY, READY, assess, last_flight_summary

OK_SETTINGS = {"verdict": "OK", "critical": [], "limits": []}
VERIFIED = {"uin": "UA-TEST", "status": "VERIFIED"}
CLEAN = {"review_id": 1, "flown_at": "2026-11-01T06:00:00+00:00", "warnings": [], "critical_in_flight": 0, "deviated": False}


def test_a_clean_drone_is_ready():
    r = assess("D1", OK_SETTINGS, VERIFIED, CLEAN)
    assert r["status"] == READY and r["reasons"] == []


def test_hard_rules_say_do_not_fly_and_name_the_setting():
    blocked = assess("D1", {"verdict": "BLOCK", "critical": ["NAV_RCL_ACT"], "limits": []}, VERIFIED, CLEAN)
    assert blocked["status"] == DO_NOT_FLY and "NAV_RCL_ACT" in blocked["reasons"][0]["text"] and blocked["reasons"][0]["where"] == "settings"
    no_uin = assess("D1", OK_SETTINGS, None, CLEAN)
    assert no_uin["status"] == DO_NOT_FLY and "UIN" in no_uin["reasons"][0]["text"]


def test_softer_findings_say_check_first_and_the_worst_reason_comes_first():
    assert assess("D1", {"verdict": "REVIEW", "critical": [], "limits": ["MPC_XY_VEL_MAX"]}, VERIFIED, CLEAN)["status"] == CHECK_FIRST
    assert assess("D1", OK_SETTINGS, {"uin": "UA-TEST", "status": "RECORDED"}, CLEAN)["status"] == CHECK_FIRST
    assert assess("D1", None, VERIFIED, None)["status"] == CHECK_FIRST                    # settings never checked
    warned = assess("D1", OK_SETTINGS, None, dict(CLEAN, warnings=["Estimator rejected compass data for 6 s"]))
    assert warned["status"] == DO_NOT_FLY and [r["level"] for r in warned["reasons"]] == [DO_NOT_FLY, CHECK_FIRST]
    assert "compass" in warned["reasons"][1]["text"] and warned["reasons"][1]["where"] == "flight"


def test_vibration_is_shown_but_never_changes_the_verdict():
    loud = {"latest_vs_own": {"higher_than": 7, "earlier_flights": 7}, "public": {"higher_than_pct": 99, "flights": 100}}
    r = assess("D1", OK_SETTINGS, VERIFIED, CLEAN, loud)
    assert r["status"] == READY and r["vibration"] == loud


def test_the_last_flight_summary_keeps_one_line_per_kind_of_warning():
    report = {"verdict": "LOG_ONLY", "flight_s": 300, "settings_changed_in_flight": {"safety_critical": 1},
              "evidence_timeline": [{"level": "warning", "kind": "sensor", "text": "Estimator rejected compass data for 6 s"},
                                    {"level": "warning", "kind": "sensor", "text": "Estimator rejected compass data for 2 s"},
                                    {"level": "notice", "kind": "mode", "text": "Flight mode POSCTL → RTL"},
                                    {"level": "warning", "kind": "plan", "text": "Off the planned route for 9 s"}]}
    s = last_flight_summary(5, report, "2026-11-02T10:00:00")
    assert s["warnings"] == ["Estimator rejected compass data for 6 s"] and s["critical_in_flight"] == 1 and s["deviated"] is False
    assert assess("D1", OK_SETTINGS, VERIFIED, s)["status"] == CHECK_FIRST
