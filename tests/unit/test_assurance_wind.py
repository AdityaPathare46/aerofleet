"""Wind at cruise height and the battery margin (aerofleet/assurance/wind.py)."""
import pytest

from aerofleet.assurance.reconcile import parse_waypoints
from aerofleet.assurance.wind import WindUnavailable, fetch_profiles, mission_energy, profile_for, wind_at, wind_check
from aerofleet.fleet.dispatch import DispatchEngine
from aerofleet.integrations.mission_planner import build_waypoint_file

pytestmark = pytest.mark.unit

HOME, NORTH = (18.5200, 73.8500), (18.5290, 73.8500)      # 1 km due north, out and back
PLAN = parse_waypoints(build_waypoint_file({"origin_lat": HOME[0], "origin_lon": HOME[1], "dest_lat": NORTH[0], "dest_lon": NORTH[1], "altitude_m": 100.0}))
STILL = 2 * DispatchEngine.estimate_energy_wh(1.0019, 1.0)
PROFILE = {10: (2.0, 0.0), 80: (5.0, 0.0), 120: (7.0, 0.0), 180: (8.0, 0.0)}      # northerly, stronger with height


def test_still_air_matches_the_fleets_energy_model():
    e = mission_energy(PLAN, 1.0)
    assert e["flyable"] and e["energy_wh"] == pytest.approx(STILL, abs=0.06) and len(e["legs"]) == 2     # the report rounds to 0.1 Wh
    assert all(leg["ground_speed_mps"] == 12.0 for leg in e["legs"])


def test_head_and_tail_wind_do_not_cancel_out():
    e = mission_energy(PLAN, 1.0, wind=(6.0, 0.0))            # head wind out (6 m/s over ground), tail wind back (18)
    out, back = e["legs"]
    assert out["ground_speed_mps"] == 6.0 and back["ground_speed_mps"] == 18.0
    assert e["energy_wh"] == pytest.approx(STILL / 2 * (12 / 6 + 12 / 18), abs=0.11) and e["energy_wh"] > STILL * 1.3


def test_crosswind_costs_energy_both_ways_and_too_much_wind_is_unflyable():
    e = mission_energy(PLAN, 1.0, wind=(6.0, 90.0))           # from the east: pure crosswind on a north-south route
    assert all(leg["ground_speed_mps"] == pytest.approx(108 ** 0.5, abs=0.01) for leg in e["legs"])
    assert mission_energy(PLAN, 1.0, wind=(13.0, 0.0)) == {"energy_wh": None, "flyable": False, "legs": mission_energy(PLAN, 1.0, wind=(13.0, 0.0))["legs"]}


def test_wind_is_interpolated_to_the_cruise_height():
    assert wind_at(PROFILE, 100) == pytest.approx((6.0, 0.0))
    assert wind_at(PROFILE, 5) == (2.0, 0.0) and wind_at(PROFILE, 300) == (8.0, 0.0)
    veer = {10: (4.0, 0.0), 80: (4.0, 90.0), 120: (4.0, 90.0), 180: (4.0, 90.0)}
    speed, frm = wind_at(veer, 45)
    assert frm == pytest.approx(45.0) and speed == pytest.approx(4.0 * 2 ** -0.5, rel=1e-6)   # vectors, not a naive average


def test_a_mission_that_passes_on_ground_wind_can_fail_at_altitude():
    r = wind_check(PLAN, 1.0, usable_wh=STILL * 1.2, profile=PROFILE)
    assert r["wind"]["at_10m"]["speed_mps"] == 2.0 and r["wind"]["at_cruise"]["speed_mps"] == 6.0 and r["wind"]["ratio"] == 3.0
    assert r["ground_wind"]["margin_wh"] > 0 and r["cruise_wind"]["margin_wh"] < 0 and r["verdict"] == "FAILS_AT_ALTITUDE"
    assert wind_check(PLAN, 1.0, STILL * 2.0, PROFILE)["verdict"] == "PASS"
    assert wind_check(PLAN, 1.0, STILL * 0.9, PROFILE)["verdict"] == "FAIL"
    assert wind_check(PLAN, 1.0, STILL * 2.0, PROFILE, max_wind_mps=5.0)["verdict"] == "FAILS_AT_ALTITUDE"   # over the wind limit aloft


def test_forecast_parsing_and_failures_without_touching_the_network():
    hourly = {"time": ["2026-10-12T00:00", "2026-10-12T01:00"]}
    for h, s in ((10, [1.4, None]), (80, [3.0, 3.1]), (120, [3.2, 3.3]), (180, [4.6, 4.7])):
        hourly[f"wind_speed_{h}m"], hourly[f"wind_direction_{h}m"] = s, [82, 80]
    seen = {}
    profiles = fetch_profiles(18.52, 73.86, fetch=lambda url: seen.setdefault("url", url) and {"hourly": hourly})
    assert "wind_speed_120m" in seen["url"] and "wind_speed_unit=ms" in seen["url"]
    assert profiles == [("2026-10-12T00:00", {10: (1.4, 82.0), 80: (3.0, 82.0), 120: (3.2, 82.0), 180: (4.6, 82.0)})]   # the hour with a gap is dropped
    assert profile_for(profiles, "2026-10-12T00:30:00Z")[0] == "2026-10-12T00:00"
    with pytest.raises(WindUnavailable, match="No forecast for"):
        profile_for(profiles, "2026-10-13T00:00")

    def offline(url):
        raise OSError("network is unreachable")

    with pytest.raises(WindUnavailable, match="Could not get a wind forecast"):
        fetch_profiles(18.52, 73.86, fetch=offline)
