"""Integration tests for POST /orders/{id}/dispatch — the one endpoint in
the whole system allowed to command real hardware, and only after the CBF
gate has approved. Exercises the real FastAPI app end to end (real auth,
real in-memory FleetState, the real CBF gate) against the in-memory SQLite
DB tests/conftest.py already configures. Dispatch is unconditionally
deterministic now — there is no council/LLM branch left to opt out of
(see aerofleet/agents/explanation_worker.py for where the council actually
runs: async, after the fact, never on this path) — so no LLM/Ollama
dependency is needed here at all; the only thing mocked is the MAVLink
socket for the LIVE-hardware tests, which don't need a real vehicle to
prove the CBF-gates-hardware-commands invariant.
"""
from unittest.mock import MagicMock, patch

import pytest

from aerofleet.fleet.models import DroneState
from aerofleet.fleet.state import get_fleet_state

pytestmark = pytest.mark.integration


def _create_order(client, headers, city="pune", payload_kg=1.0):
    fleet = get_fleet_state(city)
    depot_id = next(iter(fleet.depots))
    depot = fleet.depots[depot_id]
    dest_lat, dest_lon = fleet.graph.node_lat_lon(depot.node)
    resp = client.post(
        "/api/v1/orders/",
        headers=headers,
        json={
            "city": city,
            "origin_depot_id": depot_id,
            "destination_lat": dest_lat + 0.01,
            "destination_lon": dest_lon + 0.01,
            "payload_kg": payload_kg,
            "priority": "STANDARD",
            "deadline_minutes": 30,
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["order_id"]


def _ground_all_but(fleet, keep_drone_id):
    """Force best_candidate to pick exactly one drone by grounding every
    other one — needed for the LIVE-hardware tests, which need to know in
    advance which drone will be commanded."""
    for d in fleet.list_drones():
        if d.drone_id != keep_drone_id:
            d.state = DroneState.GROUNDED


class TestDispatchApprovedByCbf:
    def test_dispatch_approves_and_assigns_a_drone(self, api_client, auth_headers, fresh_fleet_state):
        order_id = _create_order(api_client, auth_headers)
        resp = api_client.post(f"/api/v1/orders/{order_id}/dispatch", headers=auth_headers)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["verdict"] == "APPROVED"
        assert body["assigned_drone_id"] is not None
        assert body["cbf_certificate"]["passed"] is True

    def test_assigned_drone_state_actually_mutates_in_fleet_state(self, api_client, auth_headers, fresh_fleet_state):
        order_id = _create_order(api_client, auth_headers)
        resp = api_client.post(f"/api/v1/orders/{order_id}/dispatch", headers=auth_headers)
        drone_id = resp.json()["assigned_drone_id"]

        fleet = get_fleet_state("pune")
        drone = fleet.get_drone(drone_id)
        assert drone.state == DroneState.EN_ROUTE
        assert drone.order_id == order_id
        assert drone.battery.soc < 1.0  # energy was actually consumed, not just reported


class TestDispatchRejectedByCbf:
    def test_cbf_rejection_marks_order_failed_and_does_not_assign_a_drone(
        self, api_client, auth_headers, fresh_fleet_state
    ):
        order_id = _create_order(api_client, auth_headers)

        failing_result = MagicMock(passed=False, safety_margin_summary={"battery_reserve_margin": -5.0}, execution_time_ms=0.1)
        with patch("aerofleet.safety.cbf_gate.build_cbf_gate") as mock_build_gate:
            mock_build_gate.return_value.evaluate_trajectory.return_value = failing_result
            resp = api_client.post(f"/api/v1/orders/{order_id}/dispatch", headers=auth_headers)

        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["verdict"] == "REJECTED_BY_CBF_GATE"
        assert body["assigned_drone_id"] is None

        fleet = get_fleet_state("pune")
        drone_id = body["candidate"]["drone_id"]
        drone = fleet.get_drone(drone_id)
        assert drone.state == DroneState.IDLE  # never mutated — CBF rejected before any state change


class TestDispatchRejectsRealRedZoneDestination:
    """Proves the real geofence wiring, not a mocked gate: a delivery
    destination that actually falls inside one of the real, named DGCA Red
    Zones from aerofleet/city/restricted_sites.py must be rejected by the
    live CBF gate's geofence_exclusion constraint — previously impossible,
    since dispatch_order hardcoded in_red_zone=False regardless of where
    the delivery actually went."""

    def test_destination_at_pune_airport_is_rejected(self, api_client, auth_headers, fresh_fleet_state):
        order_id = _create_order(api_client, auth_headers)

        fleet = get_fleet_state("pune")
        # dispatch_order looks up the destination's real lat/lon via
        # graph.node_lat_lon(destination_node) — pin it to Pune Airport's
        # real coordinates (well inside its 5 km DGCA Red Zone) regardless
        # of which node the order actually snapped to, so this test is
        # deterministic independent of whether OSM or the synthetic-grid
        # fallback is active in the environment running it.
        with patch.object(fleet.graph, "node_lat_lon", return_value=(18.5822, 73.9197)):
            resp = api_client.post(f"/api/v1/orders/{order_id}/dispatch", headers=auth_headers)

        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["verdict"] == "REJECTED_BY_CBF_GATE"
        assert body["assigned_drone_id"] is None
        assert body["cbf_certificate"]["safety_margins"]["geofence_exclusion"] < 0

    def test_destination_far_from_any_site_is_approved(self, api_client, auth_headers, fresh_fleet_state):
        order_id = _create_order(api_client, auth_headers)

        fleet = get_fleet_state("pune")
        with patch.object(fleet.graph, "node_lat_lon", return_value=(18.40, 73.75)):
            resp = api_client.post(f"/api/v1/orders/{order_id}/dispatch", headers=auth_headers)

        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["verdict"] == "APPROVED"
        assert body["cbf_certificate"]["safety_margins"]["geofence_exclusion"] > 0

    def test_destination_in_yellow_band_caps_altitude_at_60m(self, api_client, auth_headers, fresh_fleet_state):
        order_id = _create_order(api_client, auth_headers)

        fleet = get_fleet_state("pune")
        # 8 km north of Pune Airport, in the DGCA Yellow lateral band —
        # legal but ceiling-restricted to 60 m rather than the normal 100 m
        # operational ceiling. The order from _create_order() is STANDARD
        # priority, which always gets the LOW band (0-60m); dispatch cruises
        # at that band's midpoint (30m), so the reported altitude_ceiling
        # margin is 60 - 30 = 30 here, versus 100 - 30 = 70 away from any
        # site — strictly less margin, proving the reduced ceiling was
        # actually applied rather than the normal 100m default.
        with patch.object(fleet.graph, "node_lat_lon", return_value=(18.6542, 73.9197)):
            resp = api_client.post(f"/api/v1/orders/{order_id}/dispatch", headers=auth_headers)

        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["verdict"] == "APPROVED"
        assert body["cbf_certificate"]["safety_margins"]["altitude_ceiling"] == 30.0

    def test_destination_far_from_any_site_has_larger_altitude_margin(self, api_client, auth_headers, fresh_fleet_state):
        order_id = _create_order(api_client, auth_headers)

        fleet = get_fleet_state("pune")
        with patch.object(fleet.graph, "node_lat_lon", return_value=(18.40, 73.75)):
            resp = api_client.post(f"/api/v1/orders/{order_id}/dispatch", headers=auth_headers)

        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["verdict"] == "APPROVED"
        assert body["cbf_certificate"]["safety_margins"]["altitude_ceiling"] == 70.0


class TestLiveHardwareOnlyCommandedAfterCbfApproval:
    """The whole point of Claim 1 in docs/PATENT_NOVELTY.md: no code path
    may send a hardware command without the CBF gate approving first. These
    tests prove it against the real dispatch_order code path, not just by
    reading the source."""

    def test_live_drone_armed_and_commanded_only_when_cbf_approves(
        self, api_client, auth_headers, fresh_fleet_state
    ):
        from aerofleet.hardware.telemetry_service import get_drone_link_registry

        order_id = _create_order(api_client, auth_headers)
        fleet = get_fleet_state("pune")
        target_drone = fleet.list_drones()[0]
        _ground_all_but(fleet, target_drone.drone_id)
        target_drone.link_mode = "LIVE"

        mock_vehicle = MagicMock()
        registry = get_drone_link_registry()
        registry._links[target_drone.drone_id] = mock_vehicle
        try:
            resp = api_client.post(f"/api/v1/orders/{order_id}/dispatch", headers=auth_headers)
            assert resp.status_code == 200, resp.text
            body = resp.json()
            assert body["verdict"] == "APPROVED"
            mock_vehicle.arm.assert_called_once()
            mock_vehicle.takeoff.assert_called_once()
            mock_vehicle.goto.assert_called_once()
        finally:
            registry._links.pop(target_drone.drone_id, None)

    def test_live_drone_not_commanded_when_cbf_rejects(self, api_client, auth_headers, fresh_fleet_state):
        from aerofleet.hardware.telemetry_service import get_drone_link_registry

        order_id = _create_order(api_client, auth_headers)
        fleet = get_fleet_state("pune")
        target_drone = fleet.list_drones()[0]
        _ground_all_but(fleet, target_drone.drone_id)
        target_drone.link_mode = "LIVE"

        mock_vehicle = MagicMock()
        registry = get_drone_link_registry()
        registry._links[target_drone.drone_id] = mock_vehicle

        failing_result = MagicMock(passed=False, safety_margin_summary={}, execution_time_ms=0.1)
        try:
            with patch("aerofleet.safety.cbf_gate.build_cbf_gate") as mock_build_gate:
                mock_build_gate.return_value.evaluate_trajectory.return_value = failing_result
                resp = api_client.post(f"/api/v1/orders/{order_id}/dispatch", headers=auth_headers)

            assert resp.status_code == 200, resp.text
            assert resp.json()["verdict"] == "REJECTED_BY_CBF_GATE"
            mock_vehicle.arm.assert_not_called()
            mock_vehicle.takeoff.assert_not_called()
            mock_vehicle.goto.assert_not_called()
        finally:
            registry._links.pop(target_drone.drone_id, None)


class TestDispatchAuthAndNotFound:
    def test_dispatch_requires_auth(self, api_client, fresh_fleet_state):
        resp = api_client.post("/api/v1/orders/NONEXISTENT/dispatch")
        assert resp.status_code == 401

    def test_dispatch_unknown_order_404s(self, api_client, auth_headers, fresh_fleet_state):
        resp = api_client.post("/api/v1/orders/ORD-DOES-NOT-EXIST/dispatch", headers=auth_headers)
        assert resp.status_code == 404
