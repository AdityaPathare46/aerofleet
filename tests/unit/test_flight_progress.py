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


CLIMB_S = 60.0 / fp.CLIMB_RATE_MPS  # 60 m cruise altitude


def test_starts_on_the_ground_at_the_origin_and_climbs_vertically():
    flight = fp.PlannedFlight("D1", "O1", PATH, 60.0, started_at=1000.0)
    s = flight.state_at(1000.0)
    assert (s.lat, s.lon) == pytest.approx((0.0, 0.0))
    assert s.altitude_m == 0.0 and s.phase == fp.CLIMB and not s.arrived
    mid = flight.state_at(1000.0 + CLIMB_S / 2)
    assert (mid.lat, mid.lon) == pytest.approx((0.0, 0.0))  # vertical: no horizontal movement yet
    assert mid.altitude_m == pytest.approx(30.0)


def test_moves_along_first_leg_at_cruise_speed_after_the_climb():
    flight = fp.PlannedFlight("D1", "O1", PATH, 60.0, started_at=0.0, speed_mps=10.0)
    s = flight.state_at(CLIMB_S + 50.0)  # 500 m flown
    assert s.phase == fp.CRUISE and s.altitude_m == 60.0
    assert s.flown_m == pytest.approx(500.0)
    assert s.lon == pytest.approx(0.0)
    assert fp.haversine_m((0.0, 0.0), (s.lat, s.lon)) == pytest.approx(500.0, rel=1e-3)
    assert s.heading_deg == pytest.approx(0.0, abs=0.5)  # due north


def test_turns_onto_second_leg():
    flight = fp.PlannedFlight("D1", "O1", PATH, 60.0, started_at=0.0, speed_mps=10.0)
    first_leg = fp.haversine_m(PATH[0], PATH[1])
    s = flight.state_at(CLIMB_S + (first_leg + 300.0) / 10.0)
    assert s.lat == pytest.approx(0.01)
    assert s.heading_deg == pytest.approx(90.0, abs=0.5)  # due east
    assert s.remaining_path[-1] == PATH[-1]


def test_descends_at_the_destination_then_lands():
    flight = fp.PlannedFlight("D1", "O1", PATH, 60.0, started_at=0.0, speed_mps=10.0)
    top_of_descent = CLIMB_S + flight.cruise_s
    d = flight.state_at(top_of_descent + 10.0)
    assert d.phase == fp.DESCENT and not d.arrived
    assert d.altitude_m == pytest.approx(60.0 - 10.0 * fp.DESCENT_RATE_MPS)
    assert (d.lat, d.lon) == pytest.approx(PATH[-1])
    landed = flight.state_at(10_000.0)
    assert landed.arrived and landed.phase == fp.LANDED and landed.altitude_m == 0.0
    assert landed.progress == 1.0 and landed.remaining_m == 0.0 and landed.eta_s == 0.0
    assert flight.state_at(0.0).eta_s == pytest.approx(flight.duration_s)


def test_single_point_path_climbs_and_lands_in_place():
    flight = fp.PlannedFlight("D1", "O1", [(1.0, 2.0)], 60.0, started_at=0.0)
    assert flight.state_at(5.0).phase == fp.CLIMB
    s = flight.state_at(flight.duration_s + 1.0)
    assert s.arrived and (s.lat, s.lon) == (1.0, 2.0)


def test_trajectory_is_time_stamped_around_now():
    flight = fp.PlannedFlight("D1", "O1", PATH, 60.0, started_at=0.0, speed_mps=10.0)
    now = CLIMB_S + 50.0
    traj = flight.trajectory(now)
    times = [p[3] for p in traj]
    assert times == sorted(times)
    assert traj[0][:3] == (0.0, 0.0, 0.0) and traj[0][3] == pytest.approx(-now)       # take-off
    assert traj[1][2] == 60.0 and traj[1][3] == pytest.approx(-50.0)                   # top of climb
    here = next(p for p in traj if p[3] == 0.0)                                        # current position
    s = flight.state_at(now)
    assert here[:3] == pytest.approx((s.lat, s.lon, 60.0), abs=1e-6)
    assert traj[-1][2] == 0.0 and traj[-1][3] == pytest.approx(flight.duration_s - now, abs=0.1)  # touchdown


def test_trajectory_thins_long_routes_but_keeps_the_endpoints():
    path = [(i * 0.0005, 0.0) for i in range(300)]
    traj = fp.PlannedFlight("D1", "O1", path, 60.0, started_at=0.0).trajectory(0.0, max_points=48)
    assert len(traj) <= 48
    assert traj[0][:2] == path[0] and traj[-1][:2] == path[-1]


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
