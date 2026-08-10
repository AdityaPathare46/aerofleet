"""Unit tests for aerofleet/safety/policy_store.py and build_cbf_gate()'s
threshold resolution order (dispatch_plan > approved policy overlay > default).
"""
import pytest

from aerofleet.safety.cbf_gate import build_cbf_gate
from aerofleet.safety import policy_store

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _clear_policy_cache():
    policy_store.invalidate_policy_cache()
    yield
    policy_store.invalidate_policy_cache()


class TestGetActivePolicy:
    def test_no_proposal_returns_empty_overlay(self):
        assert policy_store.get_active_policy("nowhere") == {}

    def test_no_city_returns_empty_overlay(self):
        assert policy_store.get_active_policy("") == {}
        assert policy_store.get_active_policy(None) == {}

    def test_approved_proposal_is_returned(self, db_with_approved_policy):
        overlay = policy_store.get_active_policy("pune")
        assert overlay == {"min_separation_m": 18.0}

    def test_pending_proposal_is_not_returned(self, db_with_pending_policy):
        assert policy_store.get_active_policy("pune") == {}

    def test_rejected_proposal_is_not_returned(self, db_with_rejected_policy):
        assert policy_store.get_active_policy("pune") == {}

    def test_result_is_cached_across_calls(self, db_with_approved_policy):
        first = policy_store.get_active_policy("pune")
        # Mutate the DB directly — a cached second call should NOT see it,
        # proving the cache (not a DB round-trip) served this call.
        from aerofleet.data.database import get_db_session
        from aerofleet.data.models.models import PolicyProposal

        with get_db_session() as db:
            db.query(PolicyProposal).filter(PolicyProposal.city == "pune").delete()

        second = policy_store.get_active_policy("pune")
        assert second == first == {"min_separation_m": 18.0}

    def test_invalidate_forces_a_fresh_lookup(self, db_with_approved_policy):
        policy_store.get_active_policy("pune")  # populate cache

        from aerofleet.data.database import get_db_session
        from aerofleet.data.models.models import PolicyProposal

        with get_db_session() as db:
            db.query(PolicyProposal).filter(PolicyProposal.city == "pune").delete()

        policy_store.invalidate_policy_cache("pune")
        assert policy_store.get_active_policy("pune") == {}


class TestBuildCbfGateOverlay:
    def test_no_city_reproduces_prior_hardcoded_default(self):
        gate = build_cbf_gate({})
        constraint = next(c for c in gate.constraints if c["name"] == "min_separation")
        assert constraint["fn"]({"separation_m": 15.0}) == pytest.approx(0.0)

    def test_approved_policy_overlay_changes_default(self, db_with_approved_policy):
        gate = build_cbf_gate({}, city="pune")
        constraint = next(c for c in gate.constraints if c["name"] == "min_separation")
        # New default is 18.0m, not the hardcoded 15.0m.
        assert constraint["fn"]({"separation_m": 18.0}) == pytest.approx(0.0)

    def test_explicit_dispatch_plan_value_wins_over_policy_overlay(self, db_with_approved_policy):
        gate = build_cbf_gate({"min_separation_m": 25.0}, city="pune")
        constraint = next(c for c in gate.constraints if c["name"] == "min_separation")
        assert constraint["fn"]({"separation_m": 25.0}) == pytest.approx(0.0)

    def test_unaffected_city_keeps_hardcoded_default(self, db_with_approved_policy):
        gate = build_cbf_gate({}, city="mumbai")
        constraint = next(c for c in gate.constraints if c["name"] == "min_separation")
        assert constraint["fn"]({"separation_m": 15.0}) == pytest.approx(0.0)


@pytest.fixture
def db_with_approved_policy(fresh_fleet_state):
    yield from _seed_policy("pune", "APPROVED", {"min_separation_m": 18.0})


@pytest.fixture
def db_with_pending_policy(fresh_fleet_state):
    yield from _seed_policy("pune", "PENDING_REVIEW", {"min_separation_m": 18.0})


@pytest.fixture
def db_with_rejected_policy(fresh_fleet_state):
    yield from _seed_policy("pune", "REJECTED", {"min_separation_m": 18.0})


def _seed_policy(city, status, changes):
    from datetime import datetime

    from aerofleet.data.database import get_db_session, init_db
    from aerofleet.data.models.models import PolicyProposal

    init_db()
    with get_db_session() as db:
        db.add(PolicyProposal(
            proposal_id="POL-TESTFIX1",
            city=city,
            proposed_changes=changes,
            rationale="test fixture",
            status=status,
            reviewed_at=datetime.utcnow() if status != "PENDING_REVIEW" else None,
        ))
    yield
