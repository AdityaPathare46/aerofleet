"""Fleet plan deconfliction (aerofleet/assurance/deconflict.py)."""
import pytest

from aerofleet.assurance.deconflict import Mission, deconflict, find_conflicts
from aerofleet.assurance.reconcile import parse_waypoints
from aerofleet.integrations.mission_planner import build_waypoint_file

pytestmark = pytest.mark.unit


def plan(origin, dest, alt=60.0):
    return parse_waypoints(build_waypoint_file({"origin_lat": origin[0], "origin_lon": origin[1], "dest_lat": dest[0],
                                                "dest_lon": dest[1], "altitude_m": alt}))


DEPOT = (18.5200, 73.8500)
NORTH, EAST, FAR = (18.5290, 73.8500), (18.5200, 73.8600), (18.6000, 73.9500)


def test_missions_that_never_meet_are_left_alone():
    ms = [Mission("A", plan(DEPOT, NORTH)), Mission("B", plan(FAR, (18.6090, 73.9500)))]
    r = deconflict(ms)
    assert find_conflicts(ms) == [] and r["before"] == [] and r["changes"] == [] and r["resolved"]


def test_two_drones_launching_together_from_one_depot_conflict_and_a_delay_fixes_it():
    ms = [Mission("A", plan(DEPOT, NORTH)), Mission("B", plan(DEPOT, NORTH))]
    (c,) = find_conflicts(ms)
    assert (c["a"], c["b"]) == ("A", "B") and c["horizontal_m"] == 0.0
    r = deconflict(ms)
    assert r["resolved"] and r["after"] == [] and r["unresolved"] == []
    (change,) = r["changes"]
    assert change["id"] == "B" and change["delay_s"] > 0 and change["new_altitude_m"] is None
    assert find_conflicts(r["missions"]) == []                                  # re-checked independently
    assert {s["id"]: s["launch_at_s"] for s in r["schedule"]} == {"A": 0.0, "B": change["delay_s"]}


def test_four_drones_from_one_depot_are_staggered_in_a_deterministic_order():
    ms = [Mission(f"D{i}", plan(DEPOT, NORTH if i % 2 else EAST)) for i in range(1, 5)]
    r1, r2 = deconflict(ms), deconflict(list(reversed(ms)))
    assert r1["resolved"] and len(r1["before"]) == 6                            # every pair meets over the depot
    assert r1["changes"] == r2["changes"]                                       # same answer whatever order they arrive in
    assert "D1" not in [c["id"] for c in r1["changes"]]                         # first by id keeps its plan


def test_priority_decides_who_keeps_the_plan():
    ms = [Mission("A", plan(DEPOT, NORTH)), Mission("MED", plan(DEPOT, NORTH), priority=5)]
    assert [c["id"] for c in deconflict(ms)["changes"]] == ["A"]


def test_height_only_separates_when_the_fleet_allows_vertical_separation():
    # head-on along the same line at different heights, launched so they pass mid-route
    a, b = Mission("A", plan(DEPOT, NORTH, alt=40.0)), Mission("B", plan(NORTH, DEPOT, alt=100.0))
    assert len(find_conflicts([a, b])) == 1                                     # horizontal-only rule: still a conflict
    assert find_conflicts([a, b], v_sep_m=20.0) == []                           # 60 m apart in height
    same = [Mission("A", plan(DEPOT, NORTH, alt=60.0)), Mission("B", plan(NORTH, DEPOT, alt=60.0))]
    r = deconflict(same, v_sep_m=20.0)
    assert r["resolved"] and r["rule"]["vertical_separation_allowed"]
    (change,) = r["changes"]
    assert change["new_altitude_m"] in (40.0, 80.0, 100.0) and change["old_altitude_m"] == 60.0 and change["delay_s"] == 0.0


def test_an_impossible_set_is_reported_as_unresolved_not_hidden():
    ms = [Mission("A", plan(DEPOT, NORTH)), Mission("B", plan(DEPOT, NORTH))]
    r = deconflict(ms, max_delay_s=10.0, delay_step_s=10.0)                     # 10 s is not enough to clear the climb
    assert not r["resolved"] and r["unresolved"] == ["B"] and r["after"] != []


def test_duplicate_ids_are_refused():
    with pytest.raises(ValueError, match="unique"):
        deconflict([Mission("A", plan(DEPOT, NORTH)), Mission("A", plan(DEPOT, EAST))])
