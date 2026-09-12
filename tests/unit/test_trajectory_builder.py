"""Unit tests for aerofleet/city/trajectory_builder.py — turning a real
node path into the List[Dict] cbf_gate.py's evaluate_trajectory() expects,
with real per-waypoint battery/zone/altitude values.
"""
from unittest.mock import MagicMock

import pytest

from aerofleet.city.airspace import ZoneColor, build_airspace_from_sites
from aerofleet.city.restricted_sites import PUNE_RESTRICTED_SITES, PUNE_SAFE_ZONES
from aerofleet.city.trajectory_builder import build_trajectory_points_from_path
from aerofleet.fleet.dispatch import DispatchEngine

pytestmark = pytest.mark.unit

_REQUIRED_KEYS = {
    "separation_m", "in_red_zone", "battery_margin_wh", "altitude_m", "wind_speed_mps",
    "payload_kg", "noise_db", "collision_probability", "link_margin_db",
    "depot_queue_length", "visibility_m",
}


@pytest.fixture
def pune_airspace():
    return build_airspace_from_sites(PUNE_RESTRICTED_SITES, PUNE_SAFE_ZONES)


@pytest.fixture
def three_point_graph():
    """node 1: real GREEN point. node 2: real RED point (Pune Airport).
    node 3: another real GREEN point. Leg lengths are stubbed to fixed,
    known values so the expected cumulative battery can be computed
    precisely via the same real energy formula the code under test uses."""
    graph = MagicMock()
    graph.node_lat_lon.side_effect = [
        (18.40, 73.75),      # node 1 — GREEN
        (18.5822, 73.9197),  # node 2 — RED (real Pune Airport)
        (18.42, 73.77),      # node 3 — GREEN
    ]
    graph.path_length_km.side_effect = [2.0, 3.0]  # leg 1->2, leg 2->3
    return graph


class TestBuildTrajectoryPointsFromPath:
    def test_returns_one_point_per_node(self, three_point_graph, pune_airspace):
        points = build_trajectory_points_from_path(
            [1, 2, 3], three_point_graph, pune_airspace, payload_kg=1.0, available_wh=100.0,
        )
        assert len(points) == 3

    def test_every_point_has_all_required_keys(self, three_point_graph, pune_airspace):
        points = build_trajectory_points_from_path(
            [1, 2, 3], three_point_graph, pune_airspace, payload_kg=1.0, available_wh=100.0,
        )
        for p in points:
            assert set(p.keys()) == _REQUIRED_KEYS

    def test_in_red_zone_is_real_per_waypoint(self, three_point_graph, pune_airspace):
        points = build_trajectory_points_from_path(
            [1, 2, 3], three_point_graph, pune_airspace, payload_kg=1.0, available_wh=100.0,
        )
        assert points[0]["in_red_zone"] is False
        assert points[1]["in_red_zone"] is True, "node 2 is the real Pune Airport — must register as red"
        assert points[2]["in_red_zone"] is False

    def test_battery_margin_decreases_by_the_real_energy_formula(self, three_point_graph, pune_airspace):
        available_wh = 100.0
        payload_kg = 1.0
        points = build_trajectory_points_from_path(
            [1, 2, 3], three_point_graph, pune_airspace, payload_kg=payload_kg, available_wh=available_wh,
        )
        expected_after_leg1 = available_wh - DispatchEngine.estimate_energy_wh(2.0, payload_kg)
        expected_after_leg2 = expected_after_leg1 - DispatchEngine.estimate_energy_wh(3.0, payload_kg)

        assert points[0]["battery_margin_wh"] == available_wh
        assert points[1]["battery_margin_wh"] == round(expected_after_leg1, 1)
        assert points[2]["battery_margin_wh"] == round(expected_after_leg2, 1)
        # Monotonically decreasing — the real point of "cumulative" accounting.
        assert points[0]["battery_margin_wh"] > points[1]["battery_margin_wh"] > points[2]["battery_margin_wh"]

    def test_battery_margin_can_go_negative_rather_than_being_clamped(self, three_point_graph, pune_airspace):
        # A deliberately tiny budget — real negative margin should surface
        # so the CBF gate's battery_reserve_margin constraint can actually
        # fire, not be silently hidden by clamping at zero.
        points = build_trajectory_points_from_path(
            [1, 2, 3], three_point_graph, pune_airspace, payload_kg=1.0, available_wh=1.0,
        )
        assert points[-1]["battery_margin_wh"] < 0

    def test_altitude_matches_a_direct_assign_altitude_band_call(self, three_point_graph, pune_airspace):
        points = build_trajectory_points_from_path(
            [1, 2, 3], three_point_graph, pune_airspace, payload_kg=1.0, available_wh=100.0, priority="STANDARD",
        )
        lat, lon = 18.40, 73.75
        band = pune_airspace.assign_altitude_band("STANDARD", lat, lon)
        expected_altitude_m = (band.floor_m + band.ceiling_m) / 2.0
        assert points[0]["altitude_m"] == expected_altitude_m

    def test_payload_kg_carried_through_to_every_point(self, three_point_graph, pune_airspace):
        points = build_trajectory_points_from_path(
            [1, 2, 3], three_point_graph, pune_airspace, payload_kg=2.5, available_wh=100.0,
        )
        assert all(p["payload_kg"] == 2.5 for p in points)

    def test_overrides_replace_the_flat_defaults(self, three_point_graph, pune_airspace):
        points = build_trajectory_points_from_path(
            [1, 2, 3], three_point_graph, pune_airspace, payload_kg=1.0, available_wh=100.0,
            overrides={"visibility_m": 200.0, "wind_speed_mps": 12.0},
        )
        assert all(p["visibility_m"] == 200.0 for p in points)
        assert all(p["wind_speed_mps"] == 12.0 for p in points)

    def test_single_node_path_does_not_crash(self, pune_airspace):
        graph = MagicMock()
        graph.node_lat_lon.return_value = (18.40, 73.75)
        points = build_trajectory_points_from_path(
            [1], graph, pune_airspace, payload_kg=1.0, available_wh=100.0,
        )
        assert len(points) == 1
        assert points[0]["battery_margin_wh"] == 100.0
