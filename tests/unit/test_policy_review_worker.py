"""Unit tests for aerofleet/agents/policy_review_worker.py's JSON extraction
and the mock backend's policy-analyst response shape (USE_MOCK_AGENTS=true
path — no live LLM needed, consistent with the rest of this suite).
"""
import os

import pytest

from aerofleet.agents.policy_review_worker import _extract_json_block, analyze_city_policy

pytestmark = pytest.mark.unit


class TestExtractJsonBlock:
    def test_extracts_valid_json_block(self):
        text = 'Some reasoning.\n```json\n{"min_separation_m": 18.0}\n```'
        assert _extract_json_block(text) == {"min_separation_m": 18.0}

    def test_empty_json_block_returns_empty_dict(self):
        text = 'No changes needed.\n```json\n{}\n```'
        assert _extract_json_block(text) == {}

    def test_no_json_block_returns_empty_dict(self):
        assert _extract_json_block("just prose, no fenced block") == {}

    def test_malformed_json_returns_empty_dict_not_an_exception(self):
        text = '```json\n{not valid json}\n```'
        assert _extract_json_block(text) == {}

    def test_non_numeric_values_are_dropped(self):
        text = '```json\n{"min_separation_m": 18.0, "note": "hello"}\n```'
        assert _extract_json_block(text) == {"min_separation_m": 18.0}

    def test_uses_the_last_block_when_multiple_present(self):
        text = '```json\n{"min_separation_m": 1.0}\n```\nrevised:\n```json\n{"min_separation_m": 2.0}\n```'
        assert _extract_json_block(text) == {"min_separation_m": 2.0}


class TestAnalyzeCityPolicyMock:
    """USE_MOCK_AGENTS is already true for the whole test session
    (tests/conftest.py sets it) — these exercise the real mock backend
    end to end, not a further mock of it."""

    def test_zero_stats_proposes_no_changes(self):
        stats = {"near_misses_resolved": 0, "cbf_interventions": 0, "fault_events": 0, "deliveries_completed": 5}
        changes, rationale = analyze_city_policy("pune", stats)
        assert changes == {}
        assert "no" in rationale.lower() or "no change" in rationale.lower()

    def test_nonzero_cbf_interventions_proposes_a_change(self):
        stats = {"near_misses_resolved": 0, "cbf_interventions": 3, "fault_events": 0, "deliveries_completed": 5}
        changes, rationale = analyze_city_policy("pune", stats)
        assert changes
        assert all(isinstance(v, float) for v in changes.values())

    def test_proposed_keys_are_all_allowed_cbf_keys(self):
        from aerofleet.agents.policy_review_worker import _ALLOWED_KEYS

        stats = {"near_misses_resolved": 2, "cbf_interventions": 1, "fault_events": 0}
        changes, _ = analyze_city_policy("pune", stats)
        assert set(changes.keys()) <= _ALLOWED_KEYS
