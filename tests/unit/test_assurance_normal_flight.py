"""The normal-flight model evaluator (aerofleet/assurance/normal_flight.py), with a tiny hand-made model."""
import math

import pytest

from aerofleet.assurance import normal_flight as nf
from aerofleet.assurance.flightlog import FlightLog


def stump(feature, threshold, left, right, missing_left=True):
    return {"left": [1, -1, -1], "right": [2, -1, -1], "feature": [feature, 0, 0], "threshold": [threshold, 0.0, 0.0],
            "missing_left": [missing_left, False, False], "value": [0.0, left, right]}


# vibration on a log scale: faster flights vibrate more. Feature 0 is speed_ms.
SPEC = {"numeric": ["speed_ms"], "categories": {"kind": ["multirotor"]}, "transform": "log",
        "quantiles": {"q05": {"init": math.log(1.0), "learning_rate": 1.0, "trees": [stump(0, 5.0, 0.0, 1.0)]},
                      "q50": {"init": math.log(2.0), "learning_rate": 1.0, "trees": [stump(0, 5.0, 0.0, 1.0)]},
                      "q95": {"init": math.log(4.0), "learning_rate": 1.0, "trees": [stump(0, 5.0, 0.0, 1.0)]}}}
MODEL = {"targets": {"vibration": SPEC}, "card": {"name": "test model"}}


@pytest.fixture(autouse=True)
def tiny_model(monkeypatch):
    monkeypatch.setattr(nf, "model", lambda: MODEL)


def test_trees_are_walked_like_scikit_learn_including_missing_values():
    assert nf.encode({"speed_ms": 3.0, "kind": "multirotor"}, SPEC) == [3.0, 1.0, 0.0]
    assert nf.encode({"speed_ms": None, "kind": "boat"}, SPEC)[1:] == [0.0, 1.0]          # unseen category -> "other"
    slow, fast = nf.expected("vibration", {"speed_ms": 3.0, "kind": "multirotor"}), nf.expected("vibration", {"speed_ms": 8.0, "kind": "multirotor"})
    assert slow == pytest.approx({"low": 1.0, "mid": 2.0, "high": 4.0})
    assert fast["mid"] == pytest.approx(2.0 * math.e)                                  # the right leaf adds 1 on the log scale
    assert nf.expected("vibration", {"speed_ms": None, "kind": "multirotor"})["mid"] == pytest.approx(2.0)   # missing goes left
    assert nf.expected("battery_drop_pct_per_min", {"speed_ms": 3.0}) is None             # no model for that target


def _flight(vib_level, n=200):
    f = FlightLog(format="ulg")
    f.track = [(float(t), 18.5 + 1e-5 * t, 73.8, 20.0) for t in range(n)]                 # ~1.1 m/s, 200 s
    f.vibration = [(float(t), vib_level) for t in range(n)]
    f.vibration_source, f.vehicle, f.hardware, f.firmware = "px4_imu", "quadcopter", "PX4_FMU_V5", "1.14"
    return f


def test_a_flight_is_placed_below_inside_or_above_its_expected_range():
    assert nf.assess(_flight(3.0))["targets"]["vibration"]["position"] == "inside"
    high = nf.assess(_flight(9.0))["targets"]["vibration"]
    assert high["position"] == "above" and high["times_mid"] == 4.5 and high["low"] == 1.0 and high["high"] == 4.0
    assert nf.assess(_flight(0.5))["targets"]["vibration"]["position"] == "below"
    assert "not a prediction" in nf.assess(_flight(3.0))["note"]


def test_only_px4_flights_of_at_least_a_minute_are_scored():
    short = _flight(3.0, n=40)
    assert nf.assess(short) is None
    ardupilot = _flight(3.0)
    ardupilot.format = "bin"
    assert nf.assess(ardupilot) is None
    f = nf.features(_flight(3.0))
    assert f["kind"] == "multirotor" and f["firmware"] == 114.0 and 1.0 < f["speed_ms"] < 1.3 and f["minutes"] == pytest.approx(189 / 60)


def test_without_a_model_nothing_is_claimed(monkeypatch):
    monkeypatch.setattr(nf, "model", lambda: None)
    assert nf.assess(_flight(3.0)) is None and nf.expected("vibration", {"speed_ms": 3.0}) is None


def test_the_calibrated_widening_is_applied_on_the_model_scale(monkeypatch):
    widened = {"targets": {"vibration": dict(SPEC, widen=0.5)}, "card": {}}
    monkeypatch.setattr(nf, "model", lambda: widened)
    e = nf.expected("vibration", {"speed_ms": 3.0, "kind": "multirotor"})
    assert e["low"] == pytest.approx(1.0 * math.exp(-0.5)) and e["high"] == pytest.approx(4.0 * math.exp(0.5))
    assert e["mid"] == pytest.approx(2.0)                                                  # the middle does not move


def test_no_ratio_is_shown_when_the_observed_value_is_not_positive():
    f = _flight(3.0)
    f.battery = [(float(t), 12.0 + 0.002 * t, None) for t in range(200)]            # voltage rose during the flight
    widened = {"targets": {"battery_drop_pct_per_min": {"numeric": ["speed_ms"], "categories": {}, "transform": None,
               "quantiles": {k: {"init": v, "learning_rate": 1.0, "trees": []} for k, v in (("q05", 0.1), ("q50", 0.5), ("q95", 1.0))}}}, "card": {}}
    nf.model = lambda: widened  # restored by the autouse fixture's monkeypatch on the next test
    t = nf.assess(f)["targets"]["battery_drop_pct_per_min"]
    assert t["position"] == "below" and t["observed"] < 0 and t["times_mid"] is None
