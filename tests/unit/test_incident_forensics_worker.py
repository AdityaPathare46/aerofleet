"""Unit tests for aerofleet/agents/incident_forensics_worker.py — the
multi-agent investigation engine, exercised with the real mock backend
(USE_MOCK_AGENTS=true, set globally by tests/conftest.py), not a further
mock of it. Covers the actual claim this whole design rests on: given a
frozen incident context with one clearly-violated CBF margin, the domain
agents should correctly identify which domain contributed.
"""
import pytest

from aerofleet.agents.incident_forensics_worker import (
    IncidentForensicsWorker,
    IncidentJob,
    _extract_json_block,
    _normalise_domain_verdict,
    new_incident_id,
)
from aerofleet.data.database import get_db_session
from aerofleet.data.models.models import IncidentReport

pytestmark = pytest.mark.unit


def _battery_violation_job() -> IncidentJob:
    return IncidentJob(
        incident_id=new_incident_id(),
        city="pune",
        trigger_type="CBF_REJECTION",
        trigger_detail={"constraint": "battery_reserve_margin", "violation_magnitude": 15.0},
        frozen_context={
            "cbf_certificate": {
                "passed": False,
                "safety_margins": {"battery_reserve_margin": -15.0, "min_separation": 20.0},
            },
            "dispatch_plan": {"payload_kg": 2.0, "priority": "STANDARD"},
        },
    )


class TestExtractJsonBlock:
    def test_extracts_valid_block(self):
        text = 'Some reasoning.\n```json\n{"factor": "battery_energy", "contributed": "CONTRIBUTED"}\n```'
        assert _extract_json_block(text) == {"factor": "battery_energy", "contributed": "CONTRIBUTED"}

    def test_no_block_returns_none(self):
        assert _extract_json_block("just prose") is None

    def test_malformed_json_returns_none_not_an_exception(self):
        assert _extract_json_block("```json\n{not valid}\n```") is None

    # Failure modes found in the 1,000-case study (research/results/f1_diagnostics.md),
    # where they were the majority of the council's "misses".

    def test_brace_inside_an_evidence_string_does_not_truncate_the_block(self):
        text = '```json\n{"factor": "comms", "contributed": "CONTRIBUTED", "evidence": "margins {comms_link_margin: -3.1}"}\n```'
        assert _extract_json_block(text)["evidence"] == "margins {comms_link_margin: -3.1}"

    def test_nested_object_is_parsed_whole(self):
        text = '```json\n{"factor": "battery_energy", "contributed": "CONTRIBUTED", "numbers": {"reserve": -42.1}}\n```'
        assert _extract_json_block(text)["numbers"] == {"reserve": -42.1}

    def test_fence_without_json_tag_and_bare_objects_are_accepted(self):
        assert _extract_json_block('```\n{"contributed": "UNCERTAIN"}\n```') == {"contributed": "UNCERTAIN"}
        assert _extract_json_block('Verdict: {"contributed": "NOT_CONTRIBUTED"} done.') == {"contributed": "NOT_CONTRIBUTED"}

    def test_an_echoed_invalid_schema_line_is_skipped_for_the_real_answer(self):
        text = ('Shape: {"contributed": "CONTRIBUTED" | "NOT_CONTRIBUTED", "confidence": 0.0-1.0}\n'
                '```json\n{"factor": "battery_energy", "contributed": "CONTRIBUTED", "confidence": 0.9}\n```')
        assert _extract_json_block(text)["confidence"] == 0.9


class TestNormaliseDomainVerdict:
    def test_a_relabelled_factor_is_pinned_to_the_factor_that_was_asked(self):
        out = _normalise_domain_verdict({"factor": "safety_margin_negative", "contributed": "CONTRIBUTED", "confidence": 0.9},
                                        "battery_energy")
        assert out["factor"] == "battery_energy"
        assert out["reported_factor"] == "safety_margin_negative"
        assert out["contributed"] == "CONTRIBUTED"

    def test_verdict_spelling_is_normalised_and_junk_becomes_uncertain(self):
        assert _normalise_domain_verdict({"contributed": "not contributed"}, "f")["contributed"] == "NOT_CONTRIBUTED"
        assert _normalise_domain_verdict({"contributed": "maybe"}, "f")["contributed"] == "UNCERTAIN"

    def test_confidence_is_clamped_and_non_numbers_become_zero(self):
        assert _normalise_domain_verdict({"confidence": 1.7}, "f")["confidence"] == 1.0
        assert _normalise_domain_verdict({"confidence": "high"}, "f")["confidence"] == 0.0


class TestInvestigate:
    def test_identifies_the_actually_violated_domain(self, fresh_fleet_state):
        worker = IncidentForensicsWorker()
        job = _battery_violation_job()

        factors, regulatory, transcript = worker._investigate(job)

        battery = next(f for f in factors if f["factor"] == "battery_energy")
        assert battery["contributed"] == "CONTRIBUTED"
        assert battery["confidence"] > 0.5

        airspace = next(f for f in factors if f["factor"] == "airspace_conflict")
        assert airspace["contributed"] == "NOT_CONTRIBUTED"

    def test_produces_one_transcript_entry_per_domain_agent_plus_regulatory(self, fresh_fleet_state):
        worker = IncidentForensicsWorker()
        job = _battery_violation_job()

        factors, regulatory, transcript = worker._investigate(job)

        # 7 domain agents (DOMAIN_FACTORS) + 1 regulatory (Compliance).
        assert len(transcript) == 8
        assert len(factors) == 7

    def test_regulatory_assessment_is_present(self, fresh_fleet_state):
        worker = IncidentForensicsWorker()
        job = _battery_violation_job()

        _, regulatory, _ = worker._investigate(job)
        assert regulatory["reportable"] is not None
        assert regulatory["citation"]


class TestSynthesize:
    def test_synthesis_names_the_contributing_factor(self, fresh_fleet_state):
        worker = IncidentForensicsWorker()
        job = _battery_violation_job()
        factors, regulatory, transcript = worker._investigate(job)

        synthesis = worker._synthesize(job, factors, regulatory, transcript)

        assert "battery_energy" in synthesis["root_cause_summary"]
        assert synthesis["recommended_policy_change"] is not None

    def test_no_contribution_produces_no_policy_change(self, fresh_fleet_state):
        worker = IncidentForensicsWorker()
        job = IncidentJob(
            incident_id=new_incident_id(), city="pune", trigger_type="CBF_REJECTION",
            trigger_detail={}, frozen_context={"cbf_certificate": {"passed": False, "safety_margins": {}}},
        )
        factors, regulatory, transcript = worker._investigate(job)
        synthesis = worker._synthesize(job, factors, regulatory, transcript)
        assert synthesis["recommended_policy_change"] is None


class TestEndToEnd:
    def test_full_pipeline_persists_a_ready_incident_report(self, fresh_fleet_state):
        worker = IncidentForensicsWorker()
        job = _battery_violation_job()
        worker.enqueue(job)

        factors, regulatory, transcript = worker._investigate(job)
        synthesis = worker._synthesize(job, factors, regulatory, transcript)
        worker._finalize(job.incident_id, factors, regulatory, synthesis, transcript, status="READY")

        with get_db_session() as db:
            report = db.query(IncidentReport).filter(IncidentReport.incident_id == job.incident_id).first()
            assert report.status == "READY"
            assert report.contributing_factors is not None
            assert report.investigation_transcript is not None
            assert report.completed_at is not None

    def test_enqueue_creates_a_pending_row_immediately(self, fresh_fleet_state):
        worker = IncidentForensicsWorker()
        job = _battery_violation_job()
        worker.enqueue(job)

        with get_db_session() as db:
            report = db.query(IncidentReport).filter(IncidentReport.incident_id == job.incident_id).first()
            assert report is not None
            assert report.status == "PENDING"
            assert report.trigger_type == "CBF_REJECTION"
