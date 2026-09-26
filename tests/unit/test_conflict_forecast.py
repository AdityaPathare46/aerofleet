"""Look-ahead separation check over planned trajectories."""
import pytest

from aerofleet.fleet import flight_progress as fp
from aerofleet.fleet.conflict_forecast import forecast_conflicts

pytestmark = pytest.mark.unit

MIN_SEP, BAND = 15.0, 35.0
CLIMB_S = 60.0 / fp.CLIMB_RATE_MPS


def _flight(drone, path, started_at=0.0, alt=60.0):
    return fp.PlannedFlight(drone, "O-" + drone, path, alt, started_at=started_at, speed_mps=10.0)


def test_head_on_pair_is_a_future_conflict_at_the_meeting_point():
    # 1,000 m apart on the same line at the equator, closing at 20 m/s once both cruise.
    a = _flight("A", [(0.0, 0.0), (0.0, 0.02)])
    b = _flight("B", [(0.0, 0.009), (0.0, -0.01)])
    now = CLIMB_S  # both just reached cruise
    (c,) = forecast_conflicts({"A": a, "B": b}, now, MIN_SEP, BAND)
    assert c["severity"] == "CONFLICT"
    assert c["t_s"] == pytest.approx(50.0, abs=2.0)          # ~1,000 m / 20 m/s
    assert c["horizontal_m"] < MIN_SEP
    assert c["vertical_m"] == 0.0


def test_parallel_tracks_far_apart_are_not_reported():
    a = _flight("A", [(0.0, 0.0), (0.02, 0.0)])
    b = _flight("B", [(0.0, 0.01), (0.02, 0.01)])   # ~1.1 km to the east, same direction
    assert forecast_conflicts({"A": a, "B": b}, CLIMB_S, MIN_SEP, BAND) == []


def test_a_pair_that_is_closest_right_now_is_left_to_the_live_pairs():
    # Diverging from the same point: closest at t = 0, so nothing is "ahead".
    a = _flight("A", [(0.0, 0.0), (0.02, 0.0)])
    b = _flight("B", [(0.0, 0.0), (-0.02, 0.0)])
    assert forecast_conflicts({"A": a, "B": b}, CLIMB_S + 5, MIN_SEP, BAND) == []


def test_drones_on_the_ground_are_not_in_the_airspace():
    # B lands at the point A later passes over — while B is on the ground that's not a conflict.
    a = _flight("A", [(0.0, -0.005), (0.0, 0.02)], started_at=0.0)
    b = _flight("B", [(0.0, 0.0001), (0.0, 0.0)], started_at=-1_000.0)   # long since landed
    assert forecast_conflicts({"A": a, "B": b}, CLIMB_S, MIN_SEP, BAND) == []


def test_near_miss_inside_the_watch_band_is_watch_not_conflict():
    # Crossing tracks offset so the closest approach is ~30 m: margin 15 m, inside the 35 m band.
    a = _flight("A", [(0.0, -0.005), (0.0, 0.005)])
    b = _flight("B", [(-0.005, 0.00027), (0.005, 0.00027)])
    (c,) = forecast_conflicts({"A": a, "B": b}, CLIMB_S, MIN_SEP, BAND)
    assert c["severity"] == "WATCH" and 0 <= c["separation_margin_m"] < BAND


def test_fast_closing_pair_cannot_slip_between_samples():
    # 12 m/s each, head-on: 48 m of closure per 2 s sample. Sampling alone reports the
    # nearest sample (~up to 24 m apart, a mere WATCH); the exact in-interval solve finds ~0 m.
    a = fp.PlannedFlight("A", "OA", [(0.0, 0.0), (0.0, 0.02)], 60.0, started_at=0.0, speed_mps=12.0)
    b = fp.PlannedFlight("B", "OB", [(0.0, 0.01003), (0.0, -0.01)], 60.0, started_at=0.0, speed_mps=12.0)
    (c,) = forecast_conflicts({"A": a, "B": b}, CLIMB_S, MIN_SEP, BAND, step_s=2.0)
    assert c["severity"] == "CONFLICT" and c["horizontal_m"] < 1.0
