"""Integration tests for /api/v1/incidents — the auto-trigger on a real
CBF rejection through the live dispatch endpoint (not a unit-level call
into the worker directly), proposal listing, and promoting a recommended
policy change into the existing Phase AC PolicyProposal review flow.
USE_MOCK_AGENTS=true (set globally by tests/conftest.py), no live LLM
needed.
"""
import time
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.integration


def _create_order(client, headers, city="pune"):
    from aerofleet.fleet.state import get_fleet_state

    fleet = get_fleet_state(city)
    depot_id = next(iter(fleet.depots))
    depot = fleet.depots[depot_id]
    dest_lat, dest_lon = fleet.graph.node_lat_lon(depot.node)
    resp = client.post(
        "/api/v1/orders/",
        headers=headers,
        json={
            "city": city, "origin_depot_id": depot_id,
            "destination_lat": dest_lat + 0.01, "destination_lon": dest_lon + 0.01,
            "payload_kg": 1.0, "priority": "STANDARD", "deadline_minutes": 30,
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["order_id"]


def _force_cbf_rejection(client, headers, order_id):
    failing_result = MagicMock(
        passed=False, safety_margin_summary={"battery_reserve_margin": -5.0}, execution_time_ms=0.1,
        violations=[MagicMock(constraint_name="battery_reserve_margin", violation_magnitude=5.0, required_correction=5.0)],
    )
    with patch("aerofleet.safety.cbf_gate.build_cbf_gate") as mock_gate:
        mock_gate.return_value.evaluate_trajectory.return_value = failing_result
        return client.post(f"/api/v1/orders/{order_id}/dispatch", headers=headers)


def _wait_for_ready(client, headers, incident_id, timeout_s=5.0):
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        resp = client.get(f"/api/v1/incidents/{incident_id}", headers=headers)
        if resp.json()["status"] in ("READY", "FAILED"):
            return resp.json()
        time.sleep(0.1)
    raise TimeoutError(f"Incident {incident_id} did not finish within {timeout_s}s")


class TestAutoTriggerOnRealCbfRejection:
    def test_a_real_dispatch_rejection_creates_an_incident(self, api_client, auth_headers, fresh_fleet_state):
        order_id = _create_order(api_client, auth_headers)
        resp = _force_cbf_rejection(api_client, auth_headers, order_id)
        assert resp.json()["verdict"] == "REJECTED_BY_CBF_GATE"

        listing = api_client.get("/api/v1/incidents/?city=pune", headers=auth_headers)
        assert listing.status_code == 200
        incidents = listing.json()
        assert len(incidents) == 1
        assert incidents[0]["order_id"] == order_id
        assert incidents[0]["trigger_type"] == "CBF_REJECTION"

    def test_the_incident_investigation_completes_and_identifies_the_cause(self, api_client, auth_headers, fresh_fleet_state):
        order_id = _create_order(api_client, auth_headers)
        _force_cbf_rejection(api_client, auth_headers, order_id)

        incidents = api_client.get("/api/v1/incidents/?city=pune", headers=auth_headers).json()
        incident_id = incidents[0]["incident_id"]

        final = _wait_for_ready(api_client, auth_headers, incident_id)
        assert final["status"] == "READY"
        assert "battery_energy" in (final["root_cause_summary"] or "")
        assert final["recommended_policy_change"] is not None
        assert final["regulatory_reportable"] is True

    def test_an_approved_dispatch_creates_no_incident(self, api_client, auth_headers, fresh_fleet_state):
        order_id = _create_order(api_client, auth_headers)
        resp = api_client.post(f"/api/v1/orders/{order_id}/dispatch", headers=auth_headers)
        assert resp.json()["verdict"] == "APPROVED"

        incidents = api_client.get("/api/v1/incidents/?city=pune", headers=auth_headers).json()
        assert incidents == []


class TestListAndGet:
    def test_requires_auth(self, api_client, fresh_fleet_state):
        resp = api_client.get("/api/v1/incidents/")
        assert resp.status_code == 401

    def test_unknown_incident_404s(self, api_client, auth_headers, fresh_fleet_state):
        resp = api_client.get("/api/v1/incidents/INC-DOESNOTEXIST", headers=auth_headers)
        assert resp.status_code == 404


class TestPromoteToPolicyProposal:
    def _ready_incident_id(self, api_client, auth_headers):
        order_id = _create_order(api_client, auth_headers)
        _force_cbf_rejection(api_client, auth_headers, order_id)
        incidents = api_client.get("/api/v1/incidents/?city=pune", headers=auth_headers).json()
        incident_id = incidents[0]["incident_id"]
        _wait_for_ready(api_client, auth_headers, incident_id)
        return incident_id

    def test_requires_operator(self, api_client, auth_headers, fresh_fleet_state):
        incident_id = self._ready_incident_id(api_client, auth_headers)
        resp = api_client.post(f"/api/v1/incidents/{incident_id}/promote-to-policy-proposal", headers=auth_headers)
        assert resp.status_code == 403

    def test_operator_can_promote_and_it_appears_as_a_pending_proposal(self, api_client, operator_headers, fresh_fleet_state):
        incident_id = self._ready_incident_id(api_client, operator_headers)
        resp = api_client.post(f"/api/v1/incidents/{incident_id}/promote-to-policy-proposal", headers=operator_headers)
        assert resp.status_code == 200, resp.text
        proposal_id = resp.json()["promoted_policy_proposal_id"]
        assert proposal_id is not None

        proposals = api_client.get("/api/v1/policy/proposals?city=pune", headers=operator_headers).json()
        matching = [p for p in proposals if p["proposal_id"] == proposal_id]
        assert len(matching) == 1
        assert matching[0]["status"] == "PENDING_REVIEW"
        assert incident_id in matching[0]["rationale"]

    def test_cannot_promote_twice(self, api_client, operator_headers, fresh_fleet_state):
        incident_id = self._ready_incident_id(api_client, operator_headers)
        api_client.post(f"/api/v1/incidents/{incident_id}/promote-to-policy-proposal", headers=operator_headers)
        resp = api_client.post(f"/api/v1/incidents/{incident_id}/promote-to-policy-proposal", headers=operator_headers)
        assert resp.status_code == 409

    def test_unknown_incident_404s(self, api_client, operator_headers, fresh_fleet_state):
        resp = api_client.post("/api/v1/incidents/INC-DOESNOTEXIST/promote-to-policy-proposal", headers=operator_headers)
        assert resp.status_code == 404


class TestVRScene:
    """The VR Safety View's Incident Replay mode needs real frozen coordinates
    and violation detail, not a re-derived approximation — this is what
    justifies rendering the replay in VR (spatially verifying the council's
    narrative against the actual rejection geometry) rather than it being a
    generic visualization choice. See docs/PATENT_NOVELTY.md Claim 4."""

    def test_requires_auth(self, api_client, fresh_fleet_state):
        resp = api_client.get("/api/v1/incidents/INC-DOESNOTEXIST/vr-scene")
        assert resp.status_code == 401

    def test_unknown_incident_404s(self, api_client, auth_headers, fresh_fleet_state):
        resp = api_client.get("/api/v1/incidents/INC-DOESNOTEXIST/vr-scene", headers=auth_headers)
        assert resp.status_code == 404

    def test_scene_carries_the_real_frozen_geometry_and_violations(self, api_client, auth_headers, fresh_fleet_state):
        from aerofleet.fleet.state import get_fleet_state

        fleet = get_fleet_state("pune")
        depot_id = next(iter(fleet.depots))
        depot = fleet.depots[depot_id]
        depot_lat, depot_lon = fleet.graph.node_lat_lon(depot.node)

        order_id = _create_order(api_client, auth_headers)
        _force_cbf_rejection(api_client, auth_headers, order_id)

        incidents = api_client.get("/api/v1/incidents/?city=pune", headers=auth_headers).json()
        incident_id = incidents[0]["incident_id"]

        resp = api_client.get(f"/api/v1/incidents/{incident_id}/vr-scene", headers=auth_headers)
        assert resp.status_code == 200, resp.text
        scene = resp.json()

        assert scene["incident_id"] == incident_id
        assert scene["trigger_type"] == "CBF_REJECTION"

        # Destination is the real requested point (depot + 0.01, per _create_order,
        # snapped to the nearest graph node by dispatch_order), not a placeholder —
        # this is the coordinate capture fixed in orders.py specifically so this
        # endpoint would have real geometry to serve. Tolerance covers node-snapping,
        # not just floating-point noise.
        assert scene["position"]["lat"] == pytest.approx(depot_lat + 0.01, abs=0.01)
        assert scene["position"]["lon"] == pytest.approx(depot_lon + 0.01, abs=0.01)

        # Origin depot coordinates, best-effort captured alongside the destination.
        assert scene["origin"]["lat"] == pytest.approx(depot_lat, abs=1e-6)
        assert scene["origin"]["lon"] == pytest.approx(depot_lon, abs=1e-6)

        assert len(scene["violations"]) == 1
        assert scene["violations"][0]["constraint_name"] == "battery_reserve_margin"
        assert scene["violations"][0]["violation_magnitude"] == pytest.approx(5.0)
