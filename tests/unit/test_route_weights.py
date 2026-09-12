"""Unit tests for aerofleet/city/route_weights.py — the zone/energy-aware
weighted routing that's supposed to produce a genuinely different path
than plain distance-shortest routing, not just decompose the same path
into checkpoints.
"""
import networkx as nx
import pytest

from aerofleet.city.airspace import build_airspace_from_sites
from aerofleet.city.restricted_sites import PUNE_RESTRICTED_SITES, PUNE_SAFE_ZONES
from aerofleet.city.route_weights import (
    RED_ZONE_PENALTY_KM,
    YELLOW_ZONE_PENALTY_KM,
    make_zone_energy_weight,
    optimized_shortest_path,
)

pytestmark = pytest.mark.unit


@pytest.fixture
def pune_airspace():
    return build_airspace_from_sites(PUNE_RESTRICTED_SITES, PUNE_SAFE_ZONES)


@pytest.fixture
def zone_avoidance_graph():
    """A -> B -> C is the short (2km) route, but B sits exactly on the
    real Pune Airport's coordinates (a real RED zone). A -> D -> C is a
    longer (10km) detour through a real GREEN-zone point. Plain
    distance-shortest routing must pick the B path; zone-aware routing
    must pick the D path instead."""
    g = nx.Graph()
    # Real Pune Airport coordinates — RED per PUNE_RESTRICTED_SITES.
    airport_lat, airport_lon = 18.5822, 73.9197
    # A/C/D are all real points confirmed >20km from both the airport
    # (5km red radius) and the cantonment (2km red radius) — far enough
    # that only B (placed exactly on the airport) registers as red.
    g.add_node("A", y=18.30, x=73.70)
    g.add_node("B", y=airport_lat, x=airport_lon)
    g.add_node("C", y=18.35, x=73.72)
    g.add_node("D", y=18.40, x=73.75)  # same GREEN point test_restricted_sites.py already asserts

    g.add_edge("A", "B", length=1000.0)
    g.add_edge("B", "C", length=1000.0)
    g.add_edge("A", "D", length=5000.0)
    g.add_edge("D", "C", length=5000.0)
    return g


class TestZoneAvoidance:
    def test_plain_shortest_path_goes_through_the_red_zone(self, zone_avoidance_graph):
        path = nx.shortest_path(zone_avoidance_graph, "A", "C", weight="length")
        assert path == ["A", "B", "C"], "sanity check: the short path really is through B"

    def test_optimized_path_avoids_the_red_zone(self, zone_avoidance_graph, pune_airspace):
        path = optimized_shortest_path(zone_avoidance_graph, pune_airspace, "A", "C", payload_kg=1.0)
        assert path == ["A", "D", "C"], (
            f"zone-aware routing should detour around the real red zone at B, got {path}"
        )

    def test_heavier_payload_still_avoids_the_red_zone(self, zone_avoidance_graph, pune_airspace):
        # The zone penalty (50km-equivalent) should dominate even a heavy
        # payload's extra energy cost over a mere 4km of extra detour.
        path = optimized_shortest_path(zone_avoidance_graph, pune_airspace, "A", "C", payload_kg=5.0)
        assert path == ["A", "D", "C"]


class TestWeightFunction:
    def test_weight_of_red_zone_edge_includes_the_red_penalty(self, zone_avoidance_graph, pune_airspace):
        weight_fn = make_zone_energy_weight(zone_avoidance_graph, pune_airspace, payload_kg=1.0)
        w = weight_fn("A", "B", zone_avoidance_graph.get_edge_data("A", "B"))
        assert w >= RED_ZONE_PENALTY_KM, f"expected the red penalty baked into the weight, got {w}"

    def test_weight_of_clean_edge_has_no_zone_penalty(self, zone_avoidance_graph, pune_airspace):
        from aerofleet.city.route_weights import ENERGY_WEIGHT_KM_PER_WH
        from aerofleet.fleet.dispatch import DispatchEngine

        weight_fn = make_zone_energy_weight(zone_avoidance_graph, pune_airspace, payload_kg=1.0)
        w = weight_fn("A", "D", zone_avoidance_graph.get_edge_data("A", "D"))
        # A-D is a genuinely clean 5km edge — the weight should equal
        # exactly distance + energy, with zero zone penalty added, not
        # just "under some threshold" (a 5km edge's own weight can
        # legitimately exceed YELLOW_ZONE_PENALTY_KM on length alone).
        expected_clean_weight = 5.0 + ENERGY_WEIGHT_KM_PER_WH * DispatchEngine.estimate_energy_wh(5.0, 1.0)
        assert w == pytest.approx(expected_clean_weight), f"expected no zone penalty on a clean edge, got {w}"

    def test_heavier_payload_increases_weight(self, zone_avoidance_graph, pune_airspace):
        light = make_zone_energy_weight(zone_avoidance_graph, pune_airspace, payload_kg=0.5)
        heavy = make_zone_energy_weight(zone_avoidance_graph, pune_airspace, payload_kg=5.0)
        edge_data = zone_avoidance_graph.get_edge_data("A", "D")
        assert heavy("A", "D", edge_data) > light("A", "D", edge_data)
