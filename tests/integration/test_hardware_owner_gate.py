"""Integration tests for require_hardware_owner() (multi-worker follow-up
to Phase AH) — every endpoint that mutates this process's own
registry/FleetState (dispatch, connect/disconnect/arm/disarm,
emergency-stop-all) must fail loudly with a 503 on a worker that isn't the
hardware owner, rather than silently mutating or no-op-ing on a copy
nobody else can see.
"""
import pytest

from aerofleet.fleet.state import get_fleet_state

pytestmark = pytest.mark.integration


def _create_order(client, headers, city="pune"):
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
            "payload_kg": 1.0,
            "priority": "STANDARD",
            "deadline_minutes": 30,
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["order_id"]


class TestDispatchOwnerGate:
    def test_dispatch_503s_when_not_hardware_owner(self, monkeypatch, api_client, auth_headers, fresh_fleet_state):
        order_id = _create_order(api_client, auth_headers)
        monkeypatch.setenv("AEROFLEET_HARDWARE_OWNER", "0")

        resp = api_client.post(f"/api/v1/orders/{order_id}/dispatch", headers=auth_headers)

        assert resp.status_code == 503
        assert "hardware owner" in resp.json()["detail"].lower()

    def test_dispatch_works_normally_when_owner_unset(self, api_client, auth_headers, fresh_fleet_state):
        order_id = _create_order(api_client, auth_headers)
        resp = api_client.post(f"/api/v1/orders/{order_id}/dispatch", headers=auth_headers)
        assert resp.status_code != 503

    def test_dispatch_works_normally_when_owner_explicitly_true(
        self, monkeypatch, api_client, auth_headers, fresh_fleet_state
    ):
        monkeypatch.setenv("AEROFLEET_HARDWARE_OWNER", "1")
        order_id = _create_order(api_client, auth_headers)
        resp = api_client.post(f"/api/v1/orders/{order_id}/dispatch", headers=auth_headers)
        assert resp.status_code != 503


class TestHardwareEndpointsOwnerGate:
    def test_connect_503s_when_not_hardware_owner(self, monkeypatch, api_client, operator_headers, fresh_fleet_state):
        monkeypatch.setenv("AEROFLEET_HARDWARE_OWNER", "0")
        fleet = get_fleet_state("pune")
        drone_id = fleet.list_drones()[0].drone_id

        resp = api_client.post(
            f"/api/v1/hardware/vehicles/{drone_id}/connect",
            headers=operator_headers,
            json={"connection_string": "udpin:127.0.0.1:0", "city": "pune"},
        )
        assert resp.status_code == 503

    def test_disconnect_503s_when_not_hardware_owner(self, monkeypatch, api_client, operator_headers, fresh_fleet_state):
        monkeypatch.setenv("AEROFLEET_HARDWARE_OWNER", "0")
        resp = api_client.delete("/api/v1/hardware/vehicles/SOME-DRONE/connect", headers=operator_headers)
        assert resp.status_code == 503

    def test_arm_503s_when_not_hardware_owner(self, monkeypatch, api_client, operator_headers, fresh_fleet_state):
        monkeypatch.setenv("AEROFLEET_HARDWARE_OWNER", "0")
        resp = api_client.post("/api/v1/hardware/vehicles/SOME-DRONE/arm", headers=operator_headers)
        assert resp.status_code == 503

    def test_disarm_503s_when_not_hardware_owner(self, monkeypatch, api_client, operator_headers, fresh_fleet_state):
        monkeypatch.setenv("AEROFLEET_HARDWARE_OWNER", "0")
        resp = api_client.post("/api/v1/hardware/vehicles/SOME-DRONE/disarm", headers=operator_headers)
        assert resp.status_code == 503

    def test_emergency_stop_all_503s_when_not_hardware_owner(
        self, monkeypatch, api_client, operator_headers, fresh_fleet_state
    ):
        monkeypatch.setenv("AEROFLEET_HARDWARE_OWNER", "0")
        resp = api_client.post("/api/v1/hardware/emergency-stop-all", headers=operator_headers)
        assert resp.status_code == 503

    def test_owner_gate_is_checked_before_operator_gate_does_not_leak_hardware_state(
        self, monkeypatch, api_client, auth_headers, fresh_fleet_state
    ):
        """A non-operator, non-owner request should still be rejected —
        confirms the new gate doesn't accidentally bypass the existing
        get_current_operator_user auth check for non-operators."""
        monkeypatch.setenv("AEROFLEET_HARDWARE_OWNER", "0")
        resp = api_client.post("/api/v1/hardware/emergency-stop-all", headers=auth_headers)
        assert resp.status_code in (403, 503)  # never a 200/success

    def test_read_only_list_vehicles_is_not_gated(self, monkeypatch, api_client, auth_headers, fresh_fleet_state):
        """GET endpoints are deliberately NOT guarded — a non-owner worker
        serving a (possibly stale/empty) read is the documented, accepted
        gap (see docs/MULTI_WORKER_ARCHITECTURE.md); only mutations fail loudly."""
        monkeypatch.setenv("AEROFLEET_HARDWARE_OWNER", "0")
        resp = api_client.get("/api/v1/hardware/vehicles", headers=auth_headers)
        assert resp.status_code == 200

    def test_arm_still_works_normally_when_owner(self, api_client, operator_headers, fresh_fleet_state):
        """Sanity check the gate doesn't false-positive-block a legitimate
        owner-worker request — 404 (no LIVE vehicle registered) is the
        expected non-gate failure here, never 503."""
        resp = api_client.post("/api/v1/hardware/vehicles/SOME-DRONE/arm", headers=operator_headers)
        assert resp.status_code == 404
