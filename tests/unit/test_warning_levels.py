"""A GPS or autopilot-health complaint is a warning only in the air and only if it lasts 3 s (FA1, research/false_alarms)."""
from aerofleet.assurance.evidence import timeline
from aerofleet.assurance.readiness import assess, last_flight_summary

# 0-9 s on the ground, 10-49 s in the air at 10 m, 50-59 s on the ground again
TRACK = [(float(t), 18.5, 73.8, 10.0 if 10 <= t < 50 else 0.0) for t in range(60)]


def _levels(health):
    ev = timeline({"episodes": []}, TRACK, [], (), (), (), health)
    return {e["text"].split(" for ")[0]: e["level"] for e in ev if e["kind"] == "sensor"}


def test_complaints_on_the_ground_or_too_short_are_notices():
    lv = _levels([(2.0, 8.0, "Estimator rejected compass data"),        # on the ground before take-off
                  (20.0, 22.0, "Estimator rejected velocity data"),     # in the air, only 2 s
                  (30.0, 35.0, "Estimator rejected position data"),     # in the air, 5 s
                  (45.0, 55.0, "Estimator rejected height data")])     # 4 s of it in the air
    assert lv == {"Estimator rejected compass data": "notice", "Estimator rejected velocity data": "notice",
                  "Estimator rejected position data": "warning", "Estimator rejected height data": "warning"}


def test_a_single_error_report_counts_only_in_the_air():
    lv = _levels([(30.0, 30.0, "Autopilot reported: compass, unhealthy"), (55.0, 55.0, "Autopilot reported: EKF check, bad variance")])
    assert lv == {"Autopilot reported: compass, unhealthy": "warning", "Autopilot reported: EKF check, bad variance": "notice"}


def test_a_low_battery_landing_is_a_pilot_note_not_a_reason():
    report = {"evidence_timeline": [{"kind": "battery", "level": "warning", "text": "Battery below 10% (8%)"}]}
    last = last_flight_summary(1, report, "2026-01-01T00:00:00")
    assert last["warnings"] == [] and last["pilot_notes"] == ["Battery below 10% (8%)"]
    row = assess("D1", {"verdict": "OK", "critical": [], "limits": []}, {"uin": "U", "status": "VERIFIED"}, last)
    assert row["status"] == "READY"
