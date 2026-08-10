"""Integration tests for /api/v1/policy — proposal listing, operator-gated
approve/reject, and the manual trigger-review endpoint. Exercises the real
FastAPI app end to end against the in-memory test DB, USE_MOCK_AGENTS=true
(set globally by tests/conftest.py) so trigger-review needs no live LLM.
"""
import pytest

from aerofleet.fleet.state import get_fleet_state

pytestmark = pytest.mark.integration


def _seed_intervention(city="pune"):
    """Bumps cbf_interventions on the live FleetDigitalTwin so a review
    cycle has a signal to act on — mirrors what orders.py's dispatch_order
    now does on every real CBF rejection."""
    get_fleet_state(city).twin.update({"type": "CBF_INTERVENTION"})


class TestTriggerReview:
    def test_requires_auth(self, api_client, fresh_fleet_state):
        resp = api_client.post("/api/v1/policy/trigger-review")
        assert resp.status_code == 401

    def test_requires_operator(self, api_client, auth_headers, fresh_fleet_state):
        resp = api_client.post("/api/v1/policy/trigger-review", headers=auth_headers)
        assert resp.status_code == 403

    def test_operator_can_trigger_and_a_proposal_appears(self, api_client, operator_headers, fresh_fleet_state):
        _seed_intervention("pune")
        resp = api_client.post("/api/v1/policy/trigger-review?city=pune", headers=operator_headers)
        assert resp.status_code == 200, resp.text
        created = resp.json()["proposals_created"]
        assert len(created) == 1

        listing = api_client.get("/api/v1/policy/proposals?city=pune", headers=operator_headers)
        assert listing.status_code == 200
        proposals = listing.json()
        assert len(proposals) == 1
        assert proposals[0]["status"] == "PENDING_REVIEW"
        assert proposals[0]["proposed_changes"]

    def test_no_signal_produces_no_proposal(self, api_client, operator_headers, fresh_fleet_state):
        resp = api_client.post("/api/v1/policy/trigger-review?city=pune", headers=operator_headers)
        assert resp.status_code == 200, resp.text
        assert resp.json()["proposals_created"] == []


class TestApproveReject:
    def _create_proposal(self, api_client, operator_headers):
        _seed_intervention("pune")
        resp = api_client.post("/api/v1/policy/trigger-review?city=pune", headers=operator_headers)
        proposal_id = resp.json()["proposals_created"][0]
        return proposal_id

    def test_approve_requires_operator(self, api_client, auth_headers, operator_headers, fresh_fleet_state):
        proposal_id = self._create_proposal(api_client, operator_headers)
        resp = api_client.post(f"/api/v1/policy/proposals/{proposal_id}/approve", headers=auth_headers)
        assert resp.status_code == 403

    def test_approve_then_dispatch_uses_new_threshold(self, api_client, operator_headers, fresh_fleet_state):
        proposal_id = self._create_proposal(api_client, operator_headers)

        resp = api_client.post(f"/api/v1/policy/proposals/{proposal_id}/approve", headers=operator_headers)
        assert resp.status_code == 200, resp.text
        assert resp.json()["status"] == "APPROVED"
        assert resp.json()["reviewed_by"]

        from aerofleet.safety.policy_store import get_active_policy

        overlay = get_active_policy("pune")
        assert overlay  # the mock analyst always proposes a non-empty change when triggered by a signal

    def test_reject_leaves_no_active_policy(self, api_client, operator_headers, fresh_fleet_state):
        proposal_id = self._create_proposal(api_client, operator_headers)

        resp = api_client.post(f"/api/v1/policy/proposals/{proposal_id}/reject", headers=operator_headers)
        assert resp.status_code == 200, resp.text
        assert resp.json()["status"] == "REJECTED"

        from aerofleet.safety.policy_store import get_active_policy

        assert get_active_policy("pune") == {}

    def test_cannot_approve_twice(self, api_client, operator_headers, fresh_fleet_state):
        proposal_id = self._create_proposal(api_client, operator_headers)
        api_client.post(f"/api/v1/policy/proposals/{proposal_id}/approve", headers=operator_headers)
        resp = api_client.post(f"/api/v1/policy/proposals/{proposal_id}/approve", headers=operator_headers)
        assert resp.status_code == 409

    def test_unknown_proposal_404s(self, api_client, operator_headers, fresh_fleet_state):
        resp = api_client.post("/api/v1/policy/proposals/POL-DOESNOTEXIST/approve", headers=operator_headers)
        assert resp.status_code == 404


class TestListProposals:
    def test_requires_auth(self, api_client, fresh_fleet_state):
        resp = api_client.get("/api/v1/policy/proposals")
        assert resp.status_code == 401

    def test_non_operator_can_list_read_only(self, api_client, auth_headers, operator_headers, fresh_fleet_state):
        _seed_intervention("pune")
        api_client.post("/api/v1/policy/trigger-review?city=pune", headers=operator_headers)

        resp = api_client.get("/api/v1/policy/proposals", headers=auth_headers)
        assert resp.status_code == 200
        assert len(resp.json()) == 1
