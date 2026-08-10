"""Deterministic mock LLM backend.

Implements the same interface as LocalMissionAgent (reason, interpret_mission,
analyze_anomaly, check_model_availability, list_available_models) but never
makes a network call. Used for offline development, CI, and this sandbox
where the remote Ollama GPU server (Tailscale-only) is unreachable —
selected automatically when USE_MOCK_AGENTS=true.

Produces rule-based, ReAct-shaped responses from the same telemetry dicts
the real agents receive, so the rest of the council/CBF/API pipeline can
be exercised end-to-end without a live model.
"""
import json
import re
from typing import Any, Dict, List, Optional, Union

from aerofleet.utils.logging import get_logger

logger = get_logger(__name__)


class MockLLMBackend:
    def __init__(self, model_name: Optional[str] = None):
        self.default_model = model_name or "mock-deterministic"
        logger.info("MockLLMBackend active — no live LLM calls will be made")

    def _get_model(self, model_override: Optional[str] = None) -> str:
        return model_override or self.default_model

    def interpret_mission(self, user_prompt: str, model: Optional[str] = None) -> Dict[str, Any]:
        return {
            "mission_type": "STANDARD",
            "origin": "DEPOT-1",
            "target": "unspecified",
            "constraints": {"deadline_minutes": 30, "payload_kg": 1.0},
        }

    def reason(
        self,
        context_prompt: Union[str, Dict],
        model: Optional[str] = None,
        system_prompt_override: Optional[str] = None,
    ) -> str:
        if isinstance(context_prompt, dict):
            context_prompt = json.dumps(context_prompt, indent=2)

        if "Fleet Policy Analyst" in (system_prompt_override or ""):
            return self._mock_policy_response(context_prompt, model)

        prompt_text = system_prompt_override or ""
        if "INCIDENT FORENSICS SYNTHESIS TASK" in prompt_text:
            return self._mock_incident_synthesis_response(context_prompt, model)
        if "INCIDENT FORENSICS — REGULATORY ASSESSMENT" in prompt_text:
            return self._mock_incident_regulatory_response(context_prompt, model)
        if "INCIDENT FORENSICS TASK" in prompt_text:
            return self._mock_incident_domain_response(context_prompt, prompt_text, model)

        verdict = self._infer_verdict(context_prompt)
        agent_hint = self._infer_agent_hint(system_prompt_override or "")

        return (
            f"Thought: Reviewing the supplied telemetry for {agent_hint}.\n"
            f"Action: Checked reported status/margin fields against nominal thresholds.\n"
            f"Observation: {'FAIL status found in telemetry' if verdict == 'RED' else 'All checked fields within nominal range'}.\n"
            f"Verdict: {verdict} — mock deterministic evaluation "
            f"(MockLLMBackend, model={self._get_model(model)})."
        )

    def _mock_policy_response(self, context_prompt: str, model: Optional[str]) -> str:
        """Deterministic stand-in for a policy-review debate: proposes a
        small, conservative separation-margin tightening whenever the
        supplied stats mention any near-misses or CBF interventions, and no
        change otherwise — mirrors the shape a real LLM's response is
        parsed from (aerofleet/agents/policy_review_worker.py's
        _extract_json_block), not the specific numbers a real model would
        propose."""
        text = context_prompt.lower()
        tightening_signal = any(
            token in text for token in ("near_misses_resolved", "cbf_interventions", "fault_events")
        ) and not all(f'"{k}": 0' in text for k in ("near_misses_resolved", "cbf_interventions", "fault_events"))

        if tightening_signal:
            changes = {"min_separation_m": 18.0, "max_wind_mps": 8.0}
            rationale = (
                "Recent stats show non-zero near-miss/CBF-intervention/fault activity. "
                "Proposing a conservative tightening of horizontal separation and wind "
                "ceiling to widen the safety margin ahead of the next review cycle."
            )
        else:
            changes = {}
            rationale = "No near-misses, CBF interventions, or fault events in the reviewed window — no threshold change proposed."

        return (
            f"Thought: Reviewing recent fleet digital-twin statistics for policy-relevant signals.\n"
            f"Action: Checked near_misses_resolved, cbf_interventions, and fault_events against zero.\n"
            f"Observation: {rationale}\n"
            f"Proposal (mock deterministic evaluation, MockLLMBackend, model={self._get_model(model)}):\n"
            f"```json\n{json.dumps(changes, indent=2)}\n```"
        )

    # ─────────────────────────────────────────────────────────────────
    #  Incident forensics (aerofleet/agents/incident_forensics_worker.py)
    # ─────────────────────────────────────────────────────────────────

    # Which CBF safety-margin field(s) each FIT tier-2 factor would show as
    # negative if that domain actually contributed to the incident. Not
    # every factor maps to a CBF margin (routing/ops rarely gate a
    # rejection directly) — those fall through to UNCERTAIN, honestly
    # reflecting that the mock has no real signal to judge them on either.
    _FACTOR_MARGIN_FIELDS = {
        "battery_energy": ["battery_reserve_margin"],
        "airspace_conflict": ["min_separation", "geofence_exclusion", "collision_probability"],
        "weather_environmental": ["wind_limit", "weather_visibility"],
        "communications_link": ["comms_link_margin"],
        "ops_scheduling_capacity": ["depot_capacity"],
    }

    def _mock_incident_domain_response(self, context_prompt: str, prompt_text: str, model: Optional[str]) -> str:
        """Deterministic stand-in for one domain agent's incident
        assessment: CONTRIBUTED if this factor's CBF margin field appears
        negative anywhere in the frozen incident context, NOT_CONTRIBUTED
        if present and non-negative, UNCERTAIN if this factor has no
        directly corresponding CBF margin to check (honest — not a guess)."""
        factor_match = re.search(r'"factor":\s*"([a-z_]+)"', prompt_text)
        factor_name = factor_match.group(1) if factor_match else "unknown_factor"

        margin_fields = self._FACTOR_MARGIN_FIELDS.get(factor_name)
        contributed, confidence, evidence = "UNCERTAIN", 0.3, "No directly corresponding CBF margin field to check."

        if factor_name == "cross_check_anomaly":
            evidence = "Cross-check only — no independent domain claim to make in mock mode."
        elif margin_fields:
            negative_hit = None
            for field_name in margin_fields:
                m = re.search(rf'"{field_name}":\s*(-?[\d.]+)', context_prompt)
                if m and float(m.group(1)) < 0:
                    negative_hit = (field_name, m.group(1))
                    break
            if negative_hit:
                contributed, confidence = "CONTRIBUTED", 0.8
                evidence = f"{negative_hit[0]} = {negative_hit[1]} (negative — constraint violated)."
            elif any(field_name in context_prompt for field_name in margin_fields):
                contributed, confidence = "NOT_CONTRIBUTED", 0.7
                evidence = f"Checked {margin_fields} — none negative in the frozen context."

        payload = {
            "factor": factor_name, "contributed": contributed,
            "confidence": confidence, "evidence": evidence,
        }
        return (
            f"Thought: Checking whether {factor_name} shows a violated margin in the frozen incident context.\n"
            f"Action: Searched frozen_context for {margin_fields or '(no mapped field)'}.\n"
            f"Observation: {evidence}\n"
            f"Verdict: {contributed} — mock deterministic evaluation (MockLLMBackend, model={self._get_model(model)}).\n"
            f"```json\n{json.dumps(payload, indent=2)}\n```"
        )

    def _mock_incident_regulatory_response(self, context_prompt: str, model: Optional[str]) -> str:
        """Every incident type this project auto-triggers on (CBF
        rejection, fault event, emergency landing) is the kind of thing a
        real DGCA-compliant operator would need to log — this mock always
        reports reportable=true, honestly labeled as a fixed mock
        judgment, not a real regulatory determination."""
        payload = {
            "reportable": True,
            "citation": "DGCA Drone Rules 2021 — operator record-keeping/incident-logging requirement (Rule 19 zone-check trail; exact incident-report rule to be confirmed against the current Digital Sky operator manual).",
            "note": "Mock deterministic judgment — always reportable for the incident types this system auto-triggers on.",
        }
        return (
            f"Thought: This is a CBF rejection or fault/emergency-landing event — DGCA operators are expected "
            f"to maintain an auditable record of safety-relevant interventions.\n"
            f"Action: Classified as reportable by default for this trigger category.\n"
            f"Observation: {payload['citation']}\n"
            f"```json\n{json.dumps(payload, indent=2)}\n```"
        )

    def _mock_incident_synthesis_response(self, context_prompt: str, model: Optional[str]) -> str:
        """Deterministic stand-in for the Dispatcher's final synthesis:
        counts how many domain assessments in the (already-JSON-embedded)
        context came back CONTRIBUTED, and proposes a conservative,
        matching policy tightening only when a policy-relevant factor
        (battery or airspace) actually contributed — same "don't propose
        just to have something to propose" restraint as
        policy_review_worker.py's mock.

        Scoped per-object deliberately: an earlier version matched
        "factor" and "contributed" independently across the whole prompt
        text, so a non-greedy regex could pair one factor's NAME with a
        DIFFERENT factor's "contributed": "CONTRIBUTED" value later in the
        same JSON array — caught live (not in a unit test — the labeled
        eval harness only checks per-factor domain assessment, not
        synthesis attribution) when a real geofence rejection got
        attributed to "battery_energy" in the summary despite the
        per-factor list correctly showing airspace_conflict as the only
        CONTRIBUTED entry."""
        factor_objects = re.findall(r'\{[^{}]*"factor":\s*"[a-z_]+"[^{}]*\}', context_prompt)
        contributed_factors = []
        for obj_text in factor_objects:
            name_match = re.search(r'"factor":\s*"([a-z_]+)"', obj_text)
            verdict_match = re.search(r'"contributed":\s*"(CONTRIBUTED|NOT_CONTRIBUTED|UNCERTAIN)"', obj_text)
            if name_match and verdict_match and verdict_match.group(1) == "CONTRIBUTED":
                contributed_factors.append(name_match.group(1))

        if not contributed_factors:
            summary = "No domain assessment found sufficient evidence of contribution — root cause remains inconclusive from available telemetry."
            changes = None
            systemic_note = None
        else:
            summary = f"Contributing factor(s) identified: {', '.join(contributed_factors)}."
            systemic_note = None
            changes = None
            if "battery_energy" in contributed_factors:
                changes = {"battery_reserve_margin_wh": 20.0}
                systemic_note = "Battery reserve margin threshold may be too tight for observed conditions."
            elif "airspace_conflict" in contributed_factors:
                changes = {"min_separation_m": 18.0}
                systemic_note = "Minimum separation threshold may be too tight for observed traffic density."

        payload = {
            "root_cause_summary": summary,
            "contributing_factors": [{"factor": f, "contributed": "CONTRIBUTED"} for f in contributed_factors],
            "systemic_factor_note": systemic_note,
            "recommended_action": (
                "Review the flagged domain's recent telemetry trend before the next dispatch to this area."
                if contributed_factors else "No corrective action indicated by available evidence."
            ),
            "recommended_policy_change": changes,
        }
        return (
            f"Thought: Synthesizing {len(contributed_factors)} contributing-factor finding(s) from the domain agents.\n"
            f"Action: Weighed each CONTRIBUTED finding against its confidence.\n"
            f"Observation: {summary}\n"
            f"```json\n{json.dumps(payload, indent=2)}\n```"
        )

    def analyze_anomaly(
        self, anomaly_description: str, telemetry: Dict[str, Any], model: Optional[str] = None
    ) -> Dict[str, str]:
        action = "SAFE_MODE"
        low = anomaly_description.lower()
        if "battery" in low or "motor" in low or "gps" in low:
            action = "ABORT"
        return {
            "action": action,
            "reasoning": f"[MockLLMBackend] Deterministic rule-based response to: {anomaly_description}",
        }

    def check_model_availability(self, model_name: str) -> bool:
        return True

    def list_available_models(self) -> List[str]:
        return [self.default_model]

    # ─────────────────────────────────────────────────────────────────

    @staticmethod
    def _infer_verdict(prompt_text: str) -> str:
        text = prompt_text.upper()
        if '"STATUS": "FAIL"' in text or "'STATUS': 'FAIL'" in text:
            return "RED"
        if '"STATUS": "WARNING"' in text or "'STATUS': 'WARNING'" in text:
            return "YELLOW"
        return "GREEN"

    @staticmethod
    def _infer_agent_hint(system_prompt: str) -> str:
        match = re.search(r"You are the ([^.\n]+)", system_prompt)
        return match.group(1).strip() if match else "this dispatch decision"
