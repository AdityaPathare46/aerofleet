"""Unit tests for the SIMULATED-drone flight-progress model."""
import pytest

from aerofleet.fleet import flight_progress as fp

# ~1.11 km due north, then ~1.11 km due east (at the equator, 0.01 deg ~ 1113 m).
PATH = [(0.0, 0.0), (0.01, 0.0), (0.01, 0.01)]


@pytest.fixture(autouse=True)
def _clean():
    fp.clear()
    yield
    fp.clear()


def test_starts_at_origin():
    s = fp.PlannedFlight("D1", "O1", PATH, 60.0, started_at=1000.0).state_at(1000.0)
    assert (s.lat, s.lon) == pytest.approx((0.0, 0.0))
    assert s.progress == 0.0 and not s.arrived


def test_moves_along_first_leg_at_cruise_speed():
    flight = fp.PlannedFlight("D1", "O1", PATH, 60.0, started_at=0.0, speed_mps=10.0)
    s = flight.state_at(50.0)  # 500 m flown
    assert s.flown_m == pytest.approx(500.0)
    assert s.lon == pytest.approx(0.0)
    assert fp.haversine_m((0.0, 0.0), (s.lat, s.lon)) == pytest.approx(500.0, rel=1e-3)
    assert s.heading_deg == pytest.approx(0.0, abs=0.5)  # due north


def test_turns_onto_second_leg():
    flight = fp.PlannedFlight("D1", "O1", PATH, 60.0, started_at=0.0, speed_mps=10.0)
    first_leg = fp.haversine_m(PATH[0], PATH[1])
    s = flight.state_at((first_leg + 300.0) / 10.0)
    assert s.lat == pytest.approx(0.01)
    assert s.heading_deg == pytest.approx(90.0, abs=0.5)  # due east
    assert s.remaining_path[-1] == PATH[-1]


def test_holds_at_destination_after_arrival():
    flight = fp.PlannedFlight("D1", "O1", PATH, 60.0, started_at=0.0, speed_mps=10.0)
    s = flight.state_at(10_000.0)
    assert s.arrived and s.progress == 1.0 and s.remaining_m == 0.0
    assert (s.lat, s.lon) == pytest.approx(PATH[-1])


def test_single_point_path_is_already_arrived():
    s = fp.PlannedFlight("D1", "O1", [(1.0, 2.0)], 60.0, started_at=0.0).state_at(5.0)
    assert s.arrived and (s.lat, s.lon) == (1.0, 2.0)


def test_empty_path_rejected():
    with pytest.raises(ValueError):
        fp.PlannedFlight("D1", "O1", [], 60.0, started_at=0.0)


def test_registry_is_per_city_and_clearable():
    fp.register("pune", "D1", "O1", PATH, 60.0)
    fp.register("mumbai", "D1", "O2", PATH, 60.0)
    assert fp.get("pune", "D1").order_id == "O1"
    assert fp.get("mumbai", "D1").order_id == "O2"
    fp.clear("pune")
    assert fp.get("pune", "D1") is None and fp.get("mumbai", "D1") is not None


def test_downsample_keeps_endpoints():
    path = [(float(i), 0.0) for i in range(100)]
    out = fp.downsample(path, 10)
    assert len(out) == 10 and out[0] == path[0] and out[-1] == path[-1]
    assert fp.downsample(path[:5], 10) == path[:5]
