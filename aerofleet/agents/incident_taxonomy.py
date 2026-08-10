"""AeroFleet Fleet Incident Taxonomy (FIT) — a structured, tiered
classification scheme for autonomous fleet incidents.

Methodologically inspired by, but NOT identical to, aviation's Human
Factors Analysis and Classification System (HFACS). HFACS classifies
HUMAN pilot/operator error across four tiers (Unsafe Acts, Preconditions
for Unsafe Acts, Unsafe Supervision, Organizational Influences) — AeroFleet
has no human pilot in the loop, so a literal HFACS port doesn't fit. What
transfers is the methodological idea: structured, tiered, evidence-bound
classification, with each tier mapped to a domain of expertise. This module
adapts that idea to an autonomous dispatch system's actual failure surface.

Grounding precedent (see docs/D2D_MESH_RESEARCH_DESIGN.md-style citation
practice — full sources in PROJECT_SUMMARY.md's Phase AF entry):
  - "UAV Accident Forensics via HFACS-LLM Reasoning" (Drones 9(10):704,
    2025) — single-LLM, HFACS-guided structured prompting over UAV
    incident narratives, evaluated against ASRS-report ground truth
    (macro-F1 0.58-0.76 across 18 categories, 7 models). This is where the
    taxonomy idea comes from.
  - "Flow-of-Action" and "RCACopilot" (SRE/microservices domain) —
    multi-agent, domain-specialist root-cause-analysis architectures. This
    is where the "many domain experts, one synthesizer" structure comes
    from — it's already what aerofleet/agents/factory.py's 11-agent roster
    is, just never pointed at incident investigation before.

AeroFleet's distinguishing combination: multi-agent, domain-specialized,
structured-taxonomy incident forensics for a UAV FLEET specifically — the
single-LLM HFACS work above evaluates one narrative at a time with one
model; nothing in that search turned up the multi-agent domain-specialist
version applied to fleet dispatch. This is a narrow, honestly-scoped
novelty claim, not "we invented AI incident analysis."
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional


class IncidentTrigger(Enum):
    """Tier 1 — Immediate Technical Trigger. Taken directly from the
    deterministic system's own record (a CBF constraint name, a fault
    type) — never LLM-derived, so tier 1 is always numerically exact,
    matching this project's standing rule that the LLM never certifies a
    number itself (aerofleet/agents/factory.py's CALCULATION_MANDATE)."""
    CBF_REJECTION = "CBF_REJECTION"
    FAULT_EVENT = "FAULT_EVENT"
    EMERGENCY_LANDING = "EMERGENCY_LANDING"


class ContributionVerdict(Enum):
    CONTRIBUTED = "CONTRIBUTED"
    NOT_CONTRIBUTED = "NOT_CONTRIBUTED"
    UNCERTAIN = "UNCERTAIN"


@dataclass(frozen=True)
class DomainFactor:
    """Tier 2 — Contributing Domain Factors. One per domain-expert agent
    from the existing 11-agent roster (aerofleet/agents/factory.py) that's
    actually relevant to a safety incident — Cost Economist, for instance,
    has nothing useful to say about why a CBF gate fired, so it's excluded
    here even though it's part of the normal dispatch council."""
    agent_id: str        # matches AgentFactory.DEFAULT_MODEL_MAP keys
    factor_name: str      # the FIT tier-2 category name
    description: str      # what this agent is being asked to assess


# The subset of the 11-agent roster with a genuine, real domain reason to
# weigh in on a safety incident. Excludes COST (economics aren't a safety
# factor) and DISPATCHER (who synthesizes the others' input at tier 3-4,
# not a tier-2 domain assessor itself).
DOMAIN_FACTORS: List[DomainFactor] = [
    DomainFactor("BATTERY", "battery_energy",
                 "Did battery state-of-charge, degradation, or energy-margin miscalculation contribute?"),
    DomainFactor("AIRSPACE_SAFETY", "airspace_conflict",
                 "Did proximity to another drone, a geofence, or an altitude-band violation contribute?"),
    DomainFactor("WEATHER", "weather_environmental",
                 "Did wind, visibility, or precipitation outside the certified envelope contribute?"),
    DomainFactor("COMMS", "communications_link",
                 "Did command/telemetry link degradation or loss contribute?"),
    DomainFactor("ROUTE", "routing_navigation",
                 "Did an infeasible or miscalculated route/ETA contribute?"),
    DomainFactor("OPS", "ops_scheduling_capacity",
                 "Did depot/battery-swap-station congestion or scheduling contribute?"),
    DomainFactor("AI_VALIDATOR", "cross_check_anomaly",
                 "Independently re-check the other agents' numbers — flag any that don't hold up."),
]

# Tier 3 (systemic/policy) and tier 4 (regulatory) are handled by DISPATCHER
# and COMPLIANCE respectively, not a per-domain list — they synthesize
# across the tier-2 findings rather than assessing one narrow domain.
SYSTEMIC_AGENT_ID = "DISPATCHER"
REGULATORY_AGENT_ID = "COMPLIANCE"


DOMAIN_ASSESSMENT_TASK_TEMPLATE = """
INCIDENT FORENSICS TASK — this is NOT a normal dispatch review. A decision
has ALREADY been made and is FINAL (either the CBF gate rejected a
dispatch, or a fault/emergency-landing occurred). Your job is retrospective
investigation, not a new recommendation.

You are assessing ONE factor: {description}

Respond with your normal Thought/Action/Observation/Verdict format, but end
with a fenced JSON block exactly in this shape:
```json
{{"factor": "{factor_name}", "contributed": "CONTRIBUTED" | "NOT_CONTRIBUTED" | "UNCERTAIN", "confidence": 0.0-1.0, "evidence": "cite the actual numbers from the incident context above"}}
```
Base "evidence" only on the numbers actually given to you in the incident
context — never invent a figure. If the incident context doesn't contain
enough information to assess your factor, use "UNCERTAIN" with a low
confidence and say what's missing, rather than guessing.
"""

SYNTHESIS_TASK_TEMPLATE = """
INCIDENT FORENSICS SYNTHESIS TASK — you have received {n_factors} domain
assessments of what may have contributed to this incident. Synthesize them
into a single structured incident report. Do not just restate each
assessment — weigh them, note where they agree or conflict, and produce
one coherent root-cause narrative.

End your response with a fenced JSON block exactly in this shape:
```json
{{
  "root_cause_summary": "one or two sentences",
  "contributing_factors": [{{"factor": "...", "contributed": "CONTRIBUTED", "confidence": 0.0-1.0}}],
  "systemic_factor_note": "was an existing CBF/policy threshold plausibly too tight or too loose for the observed conditions? or null",
  "recommended_action": "concrete, specific — not \\"investigate further\\"",
  "recommended_policy_change": {{"min_separation_m": 18.0}} or null
}}
```
Only include a "recommended_policy_change" if the evidence genuinely
supports one — an operator will review and must explicitly approve it
before it ever takes effect (aerofleet/api/routes/policy.py); do not
propose a change just to have something to propose.
"""

REGULATORY_TASK_TEMPLATE = """
INCIDENT FORENSICS — REGULATORY ASSESSMENT (Tier 4). A decision has already
been made and is final. Assess only the DGCA compliance/reporting
implications of this incident — not whether the dispatch decision itself
was correct (that's the CBF gate's job, already done).

End your response with a fenced JSON block exactly in this shape:
```json
{"reportable": true | false, "citation": "the specific DGCA rule/provision this touches", "note": "one sentence"}
```
"""


def build_incident_context_prompt(
    trigger: str,
    trigger_detail: Dict[str, Any],
    frozen_context: Dict[str, Any],
) -> str:
    """The shared context every agent (domain, synthesis, regulatory) sees
    — the SAME frozen numbers, never re-derived per agent, so every
    assessment is grounded in the one real, actual state of the incident."""
    import json

    return (
        f"INCIDENT TRIGGER: {trigger}\n"
        f"Trigger detail:\n{json.dumps(trigger_detail, indent=2)}\n\n"
        f"Frozen incident context (the actual state at the time — do not "
        f"re-derive or assume different numbers):\n{json.dumps(frozen_context, indent=2)}"
    )
