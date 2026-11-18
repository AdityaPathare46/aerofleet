"""Comparison with public PX4 flights (aerofleet/assurance/public_reference.py), on a made-up reference."""
import pytest

from aerofleet.assurance import public_reference as pr
from aerofleet.assurance.vibration import drone_history, fleet_ranking

REF = {"vibration": {"px4_estimator|multirotor": {"source": "px4_estimator", "vehicle": "multirotor", "flights": 120, "vehicles": 40,
                                                   "percentiles": [i / 100 for i in range(101)]}},
       "settings": {"NAV_RCL_ACT": {"logs": 200, "values": {"2": 180, "0": 12, "1": 8}}}}


@pytest.fixture(autouse=True)
def fake_reference(monkeypatch):
    monkeypatch.setattr(pr, "reference", lambda: REF)


def test_a_flight_is_placed_among_public_flights_of_the_same_measurement_and_vehicle_kind():
    pos = pr.vibration_position("px4_estimator", "quadcopter", 0.825)
    assert pos["higher_than_pct"] == 82 and pos["flights"] == 120 and pos["vehicles"] == 40 and pos["median"] == 0.5
    assert "not a limit" in pos["note"]                       # a description, never a pass/fail line
    assert pr.vibration_position("px4_estimator", "hexacopter", -1.0)["higher_than_pct"] == 0
    assert pr.vibration_position("px4_estimator", "quadcopter", 5.0)["higher_than_pct"] == 100
    assert pr.vibration_position("px4_imu", "quadcopter", 0.5) is None          # no reference for that measurement
    assert pr.vibration_position("px4_estimator", "fixed wing", 0.5) is None    # nor for that kind of vehicle


def test_a_setting_is_shown_with_how_often_public_flights_use_it():
    off = pr.setting_context("nav_rcl_act", 0.0)
    assert off == {"same_value_pct": 6, "logs": 200, "most_common": "2", "most_common_pct": 90, "note": pr.SETTING_NOTE}
    assert "not proof of safe" in off["note"]
    assert pr.setting_context("NAV_RCL_ACT", 5.0)["same_value_pct"] == 0
    assert pr.setting_context("UNKNOWN_PARAM", 1.0) is None and pr.setting_context("NAV_RCL_ACT", None) is None


def test_small_fleets_get_a_public_comparison_where_the_fleet_comparison_needs_four_drones():
    reviews = [{"id": k, "drone_id": "SOLO", "created_at": f"2026-10-0{k}",
                "report": {"vibration": {"p95": round(0.305 + 0.1 * k, 3), "source": "px4_estimator"}, "log": {"vehicle": "quadcopter"}}} for k in range(1, 5)]
    d = fleet_ranking(reviews)["drones"][0]
    assert d["comparable"] is False and d["public"]["higher_than_pct"] == 55          # median of the four flights, 0.555
    h = drone_history(reviews, "SOLO")
    assert [f["public_pct"] for f in h["flights"]] == [40, 50, 60, 70] and h["latest_vs_public"]["higher_than_pct"] == 70


def test_without_a_reference_file_nothing_is_claimed(monkeypatch):
    monkeypatch.setattr(pr, "reference", lambda: None)
    assert pr.vibration_position("px4_estimator", "quadcopter", 0.5) is None and pr.setting_context("NAV_RCL_ACT", 0.0) is None
