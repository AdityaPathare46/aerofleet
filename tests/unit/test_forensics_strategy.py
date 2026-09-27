"""Forensics prompting/decoding strategies — each switch does what the experiment claims."""
import json

import pytest

from aerofleet.agents import forensics_strategy as fs
from aerofleet.agents.incident_forensics_worker import (
    IncidentForensicsWorker, IncidentJob, _extract_json_block_v1, new_incident_id,
)

pytestmark = pytest.mark.unit

FROZEN = {"cbf_certificate": {"passed": False, "safety_margins": {"battery_reserve_margin": -12.0, "wind_limit": 0.4}}}


def test_ownership_block_names_the_owner_and_state_of_every_margin():
    block = fs.evidence_ownership_block(FROZEN)
    assert "battery_reserve_margin = -12.0 → VIOLATED · belongs to: battery_energy" in block
    assert "wind_limit = 0.4 → within limit · belongs to: weather_environmental" in block


def test_schema_pins_the_factor_and_verdict_values():
    s = fs.domain_json_schema("communications_link")
    assert s["properties"]["factor"]["enum"] == ["communications_link"]
    assert set(s["properties"]["contributed"]["enum"]) == {"CONTRIBUTED", "NOT_CONTRIBUTED", "UNCERTAIN"}
    assert s["required"][0] == "reasoning"  # the model reasons before it commits to a verdict


def test_few_shot_block_only_shows_the_agents_own_examples():
    ex = (fs.FewShotExample("battery_energy", {"battery_reserve_margin": -3.0}, "CONTRIBUTED", "x"),
          fs.FewShotExample("weather_environmental", {"wind_limit": -2.0}, "CONTRIBUTED", "y"))
    block = fs.few_shot_block(ex, "battery_energy")
    assert "battery_reserve_margin" in block and "wind_limit" not in block
    assert fs.few_shot_block(ex, "communications_link") == ""


def test_v1_extractor_keeps_the_original_failure_modes_for_the_baseline():
    # Measured, not assumed: the v1 regex handles nested objects and braces inside strings, but it
    # needs a ```json fence and only tries the LAST one — so an echoed invalid schema line wins.
    assert _extract_json_block_v1('```json\n{"a": {"b": 1}}\n```') == {"a": {"b": 1}}
    assert _extract_json_block_v1('```\n{"contributed": "UNCERTAIN"}\n```') is None
    assert _extract_json_block_v1('Verdict: {"contributed": "UNCERTAIN"}') is None
    answer_then_echo = '```json\n{"a": 1}\n```\n```json\n{"c": "A" | "B"}\n```'
    assert _extract_json_block_v1(answer_then_echo) is None


class _Recorder:
    def __init__(self):
        self.calls = []

    def reason(self, context_prompt, model=None, system_prompt_override=None, **kwargs):
        self.calls.append({"context": context_prompt, "system": system_prompt_override or "", **kwargs})
        schema = kwargs.get("json_schema")
        factor = schema["properties"]["factor"]["enum"][0] if schema else "battery_energy"
        return json.dumps({"reasoning": "r", "factor": factor, "contributed": "NOT_CONTRIBUTED", "confidence": 0.5, "evidence": "e"})


def _run(strategy, monkeypatch):
    rec = _Recorder()
    monkeypatch.setattr("aerofleet.agents.llm_backend.build_llm_backend", lambda: rec)
    job = IncidentJob(incident_id=new_incident_id(), city="pune", trigger_type="CBF_REJECTION",
                      trigger_detail={}, frozen_context=FROZEN)
    factors, _, _ = IncidentForensicsWorker(strategy)._investigate(job)
    return rec, factors


def test_structured_strategy_sends_the_schema_and_temperature(monkeypatch):
    rec, factors = _run(fs.ForensicsStrategy(structured_output=True, evidence_ownership=True, temperature=0.0), monkeypatch)
    domain = [c for c in rec.calls if "json_schema" in c]
    assert len(domain) == 7 and all(c["temperature"] == 0.0 for c in domain)
    assert all("CONSTRAINT OWNERSHIP" in c["context"] for c in domain)
    assert {f["contributed"] for f in factors} == {"NOT_CONTRIBUTED"}


def test_default_strategy_sends_no_schema(monkeypatch):
    rec, _ = _run(fs.ForensicsStrategy(), monkeypatch)
    assert not any("json_schema" in c for c in rec.calls)
    assert not any("CONSTRAINT OWNERSHIP" in c["context"] for c in rec.calls)
