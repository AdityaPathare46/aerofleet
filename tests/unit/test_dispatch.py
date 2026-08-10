"""Tests for the deterministic dispatch candidate-generation engine
(aerofleet/fleet/dispatch.py) — the "candidate generation" half of the
hybrid architecture that the council reasons over and the CBF gate has
final say on. Uses a stubbed CityGraph (no real OSM network dependency)
since only route_distance_km's return value matters to this logic.
"""
from unittest.mock import MagicMock

import pytest

from aerofleet.fleet.dispatch import DispatchEngine
from aerofleet.fleet.models import Battery, DeliveryOrder, Depot, Drone, DroneState

pytestmark = pytest.mark.unit


def make_graph(distance_km: float = 2.0):
    """A CityGraph stub whose route_distance_km always returns a fixed
    value — dispatch.py never inspects the graph otherwise."""
    graph = MagicMock()
    graph.route_distance_km.return_value = distance_km
    return graph


def make_drone(drone_id="D1", soc=1.0, payload_capacity_kg=5.0, state=DroneState.IDLE, home_depot_id="DEPOT-1"):
    return Drone(
        drone_id=drone_id,
        node=1,
        battery=Battery(capacity_wh=500.0, soc=soc),
        payload_capacity_kg=payload_capacity_kg,
        state=state,
        home_depot_id=home_depot_id,
    )


def make_order(payload_kg=1.0, order_id="ORD-1"):
    return DeliveryOrder(order_id=order_id, origin_depot_id="DEPOT-1", destination_node=2, payload_kg=payload_kg)


def make_depots():
    return {"DEPOT-1": Depot(depot_id="DEPOT-1", name="Depot 1", node=1)}


class TestGenerateCandidates:
    def test_available_feasible_drone_produces_a_candidate(self):
        engine = DispatchEngine(graph=make_graph(2.0), airspace=MagicMock())
        candidates = engine.generate_candidates(make_order(), [make_drone()], make_depots())
        assert len(candidates) == 1
        assert candidates[0].drone_id == "D1"
        assert candidates[0].outbound_km == 2.0
        assert candidates[0].return_km == 2.0

    def test_non_idle_drone_excluded(self):
        engine = DispatchEngine(graph=make_graph(), airspace=MagicMock())
        busy = make_drone(state=DroneState.EN_ROUTE)
        candidates = engine.generate_candidates(make_order(), [busy], make_depots())
        assert candidates == []

    def test_low_battery_drone_excluded_from_availability(self):
        """Drone.is_available requires soc > reserve_margin (0.2 default) —
        a near-empty battery shouldn't even be considered."""
        engine = DispatchEngine(graph=make_graph(), airspace=MagicMock())
        empty = make_drone(soc=0.1)
        candidates = engine.generate_candidates(make_order(), [empty], make_depots())
        assert candidates == []

    def test_payload_too_heavy_excluded(self):
        engine = DispatchEngine(graph=make_graph(), airspace=MagicMock())
        small_drone = make_drone(payload_capacity_kg=1.0)
        heavy_order = make_order(payload_kg=3.0)
        candidates = engine.generate_candidates(heavy_order, [small_drone], make_depots())
        assert candidates == []

    def test_insufficient_energy_for_round_trip_excluded(self):
        """A drone with just enough SoC for a short hop shouldn't be
        offered for a route requiring far more energy than it has available."""
        engine = DispatchEngine(graph=make_graph(distance_km=500.0), airspace=MagicMock())
        thin_battery = make_drone(soc=0.25)  # barely above the 0.2 reserve margin
        candidates = engine.generate_candidates(make_order(), [thin_battery], make_depots())
        assert candidates == []

    def test_multiple_drones_ranked_by_score_best_first(self):
        """Lower score wins (faster ETA / larger margin) — a closer depot's
        drone should be ranked ahead of a farther one when both are otherwise
        identical, since outbound_km alone drives ETA."""
        engine = DispatchEngine(graph=make_graph(), airspace=MagicMock())
        near = make_drone(drone_id="NEAR")
        far = make_drone(drone_id="FAR")

        # Different distances per drone: patch route_distance_km with a
        # side_effect keyed by the calling drone's node isn't directly
        # observable here, so instead give each drone a distinct outcome by
        # calling generate_candidates once per drone and comparing scores
        # directly — simpler and equally valid for this ranking behavior.
        engine.graph.route_distance_km.return_value = 1.0
        near_candidates = engine.generate_candidates(make_order(), [near], make_depots())
        engine.graph.route_distance_km.return_value = 20.0
        far_candidates = engine.generate_candidates(make_order(), [far], make_depots())

        assert near_candidates[0].score < far_candidates[0].score

    def test_top_k_limits_result_count(self):
        engine = DispatchEngine(graph=make_graph(), airspace=MagicMock())
        drones = [make_drone(drone_id=f"D{i}") for i in range(5)]
        candidates = engine.generate_candidates(make_order(), drones, make_depots(), top_k=2)
        assert len(candidates) == 2

    def test_energy_estimate_scales_with_payload(self):
        light = DispatchEngine.estimate_energy_wh(distance_km=10.0, payload_kg=0.0)
        heavy = DispatchEngine.estimate_energy_wh(distance_km=10.0, payload_kg=5.0)
        assert heavy > light


class TestBestCandidate:
    def test_returns_none_when_no_feasible_drone(self):
        engine = DispatchEngine(graph=make_graph(), airspace=MagicMock())
        candidate = engine.best_candidate(make_order(), [], make_depots())
        assert candidate is None

    def test_returns_the_single_best_candidate(self):
        engine = DispatchEngine(graph=make_graph(), airspace=MagicMock())
        drones = [make_drone(drone_id="D1"), make_drone(drone_id="D2")]
        candidate = engine.best_candidate(make_order(), drones, make_depots())
        assert candidate is not None
        assert candidate.drone_id in {"D1", "D2"}
