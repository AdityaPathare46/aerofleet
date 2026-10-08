"""Planned versus flown (aerofleet/assurance/reconcile.py)."""
import math

import pytest

from aerofleet.assurance.reconcile import PlanError, parse_waypoints, reconcile
from aerofleet.integrations.mission_planner import build_waypoint_file

pytestmark = pytest.mark.unit

HOME, DEST, ALT = (18.5200, 73.8500), (18.5290, 73.8500), 60.0     # 1 km due north
PLAN = parse_waypoints(build_waypoint_file({"origin_lat": HOME[0], "origin_lon": HOME[1], "dest_lat": DEST[0], "dest_lon": DEST[1], "altitude_m": ALT}))
EAST = 1 / (111_320.0 * math.cos(math.radians(HOME[0])))          # degrees of longitude per metre


def fly(offset_m=lambda i: 0.0, alt=lambda i: ALT, n=100):
    """Climb on the spot for 10 s, then fly north along the planned leg, one point per second."""
    climb = [(float(i), HOME[0], HOME[1], ALT * i / 10) for i in range(10)]
    leg = [(10.0 + i, HOME[0] + (DEST[0] - HOME[0]) * i / (n - 1), HOME[1] + offset_m(i) * EAST, alt(i)) for i in range(n)]
    return climb + leg


def test_parses_aerofleets_own_export_into_a_path():
    assert PLAN.home == HOME and PLAN.max_alt_m == ALT
    assert PLAN.path == [(*HOME, 0.0), (*HOME, ALT), (*DEST, ALT), (*HOME, ALT), (*HOME, 0.0)]
    assert any("Return-to-launch" in n for n in PLAN.notes)


def test_a_flight_on_the_plan_conforms_including_the_climb():
    r = reconcile(PLAN, fly(), modes=[(0.0, "GUIDED"), (10.0, "AUTO")])
    assert r["verdict"] == "CONFORMED" and r["episodes"] == [] and r["manual_control"] == []
    assert r["horizontal_m"]["max"] < 1.0 and r["vertical_m"]["max"] < 1.0
    assert r["max_height_m"] == {"flown": 60.0, "planned": 60.0}


def test_a_sideways_excursion_is_measured_and_located():
    r = reconcile(PLAN, fly(offset_m=lambda i: 80.0 if 40 <= i < 60 else 0.0))
    assert r["verdict"] == "DEVIATED"
    (e,) = r["episodes"]
    assert e["kind"] == "off_route" and e["max_m"] == pytest.approx(80.0, abs=0.5)
    assert e["start_s"] == 50.0 and e["duration_s"] == 19.0 and r["time_off_route_s"] == 19.0
    assert r["horizontal_m"]["max"] == pytest.approx(80.0, abs=0.5) and r["horizontal_m"]["median"] < 1.0


def test_small_wander_and_brief_spikes_are_tolerated():
    r = reconcile(PLAN, fly(offset_m=lambda i: 20.0 if i % 2 else -20.0))
    assert r["verdict"] == "CONFORMED" and r["horizontal_m"]["max"] == pytest.approx(20.0, abs=0.5)
    spike = reconcile(PLAN, fly(offset_m=lambda i: 90.0 if i in (50, 51) else 0.0))     # 1 s: under the 3 s minimum
    assert spike["verdict"] == "CONFORMED" and spike["horizontal_m"]["max"] > 80


def test_flying_too_high_is_an_altitude_episode():
    r = reconcile(PLAN, fly(alt=lambda i: 110.0 if 30 <= i < 50 else ALT))
    (e,) = r["episodes"]
    assert e["kind"] == "off_altitude" and e["max_m"] == pytest.approx(50.0) and r["max_height_m"]["flown"] == 110.0


def test_pilot_taking_manual_control_after_auto_is_reported():
    r = reconcile(PLAN, fly(), modes=[(0.0, "LOITER"), (10.0, "AUTO"), (60.0, "LOITER"), (75.0, "AUTO")])
    assert r["verdict"] == "DEVIATED"
    assert r["manual_control"] == [{"mode": "LOITER", "start_s": 60.0, "duration_s": 15.0}]   # LOITER before AUTO is not a takeover


def test_tolerances_are_the_fleets_choice_and_zones_are_checked_when_given():
    track = fly(offset_m=lambda i: 20.0)
    assert reconcile(PLAN, track, corridor_m=10.0)["verdict"] == "DEVIATED"
    r = reconcile(PLAN, track, zone_at=lambda lat, lon: "RED" if lat > 18.527 else "GREEN")
    assert [e["kind"] for e in r["episodes"]] == ["in_no_fly_zone"] and r["verdict"] == "DEVIATED"


def test_bad_mission_files_are_refused_with_a_reason():
    for text, msg in (("hello", "Not a mission file"), ("QGC WPL 110\n0\t1\t0\t16\n", "fields"), ("QGC WPL 110\n", "no flight commands")):
        with pytest.raises(PlanError, match=msg):
            parse_waypoints(text)
