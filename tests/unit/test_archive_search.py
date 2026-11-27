"""Signs from a log, words mapped to signs, and the public-archive search on a small made-up index."""
import gzip
import json

import pytest

from aerofleet.assurance import archive_search as arch
from aerofleet.assurance.log_signs import signs_from_events, signs_from_words, similarity


def test_signs_come_from_the_evidence_timeline_only():
    ev = [{"kind": "gps", "level": "warning", "text": "Poor GPS for 9 s"},
          {"kind": "sensor", "level": "warning", "text": "Estimator rejected compass data for 7 s"},
          {"kind": "battery", "level": "warning", "text": "Battery below 10% (8%)"},
          {"kind": "mode", "level": "notice", "text": "Flight mode AUTO.MISSION → POSCTL (pilot took control)"},
          {"kind": "mode", "level": "info", "text": "Flight mode MANUAL → POSCTL"}]
    assert signs_from_events(ev, 95) == {"gps_poor", "est_compass", "battery_critical", "pilot_took_control", "vibration_high"}
    assert signs_from_events(ev[4:], 50) == set()


def test_words_point_to_signs_by_a_fixed_list():
    assert {"est_compass", "gps_poor"} <= signs_from_words("Compass error, then GPS glitch")
    assert "vibration_high" in signs_from_words("it was shaking badly")
    assert signs_from_words("it landed fine") == set()
    assert similarity({"a", "b"}, {"b", "c"}) == pytest.approx(1 / 3) and similarity(set(), {"a"}) == 0


@pytest.fixture
def index(tmp_path, monkeypatch):
    data = {"archive_entries": 5, "reports": [
        {"id": "r1", "date": "2024-01-01", "text": "Compass interference near power lines, toilet bowling then crash", "rating": "crash_sw_hw", "type": "Quadrotor", "airframe": "x", "min": 3.0, "same_text": 1},
        {"id": "r2", "date": "2024-01-02", "text": "Smooth mission over the farm, good landing", "rating": "good", "type": "Quadrotor", "airframe": "x", "min": 9.0, "same_text": 1},
        {"id": "r3", "date": "2024-01-03", "text": "Fixed wing compass calibration test", "rating": "good", "type": "Fixed Wing", "airframe": "y", "min": 20.0, "same_text": 4}],
        "logs": [{"id": "l1", "signs": ["est_compass", "gps_poor"], "vehicle": "quadcopter", "min": 4, "rating": "crash_pilot", "date": "2023", "airframe": "", "text": "compass trouble"},
                 {"id": "l2", "signs": ["battery_critical"], "vehicle": "quadcopter", "min": 4, "rating": "good", "date": "2023", "airframe": "", "text": None}]}
    p = tmp_path / "ix.json.gz"
    with gzip.open(p, "wt", encoding="utf-8") as f:
        json.dump(data, f)
    monkeypatch.setenv("AEROFLEET_ARCHIVE_INDEX", str(p))
    return p


def test_words_find_what_uploaders_wrote_but_never_match_logs(index):
    # Matching logs from words failed its declared test (A1), so words only search what other pilots wrote.
    out = arch.search("compass interference, it circles like a toilet bowl")
    assert out["ready"] and out["text_matches"][0]["id"] == "r1"
    assert out["text_matches"][0]["url"].endswith("log=r1") and "crash" in out["text_matches"][0]["rating"]
    assert out["log_matches"] == [] and out["signs_from"] is None
    assert "Autopilot rejected compass data" in out["words_name"] and "did not work" in out["words_tested"]
    assert "not findings" in out["note"]


def test_a_flight_s_signs_and_vehicle_kind_narrow_the_search(index):
    out = arch.search("compass", signs={"battery_critical"}, vehicle="quadcopter")
    assert [m["id"] for m in out["log_matches"]] == ["l2"] and out["signs_from"] == "your flight"
    assert "r3" not in [m["id"] for m in out["text_matches"]]           # fixed wing left out for a quadcopter


def test_without_an_index_the_search_says_how_to_build_it(tmp_path, monkeypatch):
    monkeypatch.setenv("AEROFLEET_ARCHIVE_INDEX", str(tmp_path / "none.json.gz"))
    out = arch.search("compass")
    assert out["ready"] is False and "build_archive_index" in out["message"]


def test_the_user_s_own_log_is_never_its_own_match(index):  # noqa: F811
    out = arch.search("compass", signs={"est_compass"}, exclude={"l1", "r1"})
    assert "l1" not in [m["id"] for m in out["log_matches"]] and "r1" not in [m["id"] for m in out["text_matches"]]


def test_signs_from_a_stored_review_include_high_vibration_only_against_the_public_reference(monkeypatch):
    from aerofleet.assurance import log_signs, public_reference

    rep = {"evidence_timeline": [{"kind": "sensor", "level": "warning", "text": "Estimator rejected height data for 3 s"},
                                 {"kind": "sensor", "level": "warning", "text": "Estimator reported an internal fault for 2 s"},
                                 {"kind": "battery", "level": "notice", "text": "Battery below 20% (18%)"},
                                 {"kind": "battery", "level": "notice", "text": "Battery voltage fell 30% (25 → 17 V)"},
                                 {"kind": "setting", "level": "warning", "text": "Setting FENCE_ENABLE changed 1 → 0 in flight"},
                                 {"kind": "plan", "level": "warning", "text": "Off the planned route for 9 s"}],
           "vibration": {"source": "px4_estimator", "p95": 1.0}, "log": {"vehicle": "quadcopter"}}
    monkeypatch.setattr(public_reference, "vibration_position", lambda *a: {"higher_than_pct": 95})
    assert log_signs.signs_from_report(rep) == {"est_height", "est_fault", "battery_low", "voltage_sag", "setting_in_flight",
                                                "off_plan", "vibration_high"}
    monkeypatch.setattr(public_reference, "vibration_position", lambda *a: {"higher_than_pct": 50})
    assert "vibration_high" not in log_signs.signs_from_report(rep)
    assert log_signs.signs_from_report({}) == set()


def test_signs_from_a_parsed_log_use_the_same_timeline(monkeypatch):
    from aerofleet.assurance import log_signs
    from aerofleet.assurance.flightlog import FlightLog

    f = FlightLog(format="ulg", track=[(float(t), 18.5, 73.8, 10.0) for t in range(60)],
                  gps=[(float(t), 3 if 20 <= t < 30 else 12, 0.9, 3) for t in range(60)],
                  health=[(5.0, 9.0, "Estimator rejected compass data")])
    assert log_signs.signs_from_flight(f) == {"gps_poor", "est_compass"}
