"""
Specialist agents for the AeroFleet Dispatch Council of Experts.

These trigger only under specific conditions (conflict risk, battery-swap
routing, autonomous AI onboard, servicing/security review) rather than
running on every dispatch decision, keeping the common case cheap while
still covering the less frequent, higher-stakes cases.
"""

from typing import Any, Dict

from aerofleet.agents.base_agent import BaseAgent

REACT_MANDATE = """
MANDATORY FORMAT — USE REACT (Reason + Act) FOR EVERY RESPONSE:

Thought: [Explicit reasoning about the telemetry data. Name the numbers you are examining and their meaning.]
Action: [The specific calculation or check you are performing. Show ALL math.]
Observation: [The result of the calculation. State the exact number and what it means.]
Verdict: [GREEN / YELLOW / RED] — [One sentence justification with the specific number that drove the verdict.]

NEVER skip the Thought step. NEVER give a verdict without showing the calculation in Action.
"""


# ─────────────────────────────────────────────────────────────────────────────
#  SPECIALIST — CONFLICT AVOIDANCE PLANNER
# ─────────────────────────────────────────────────────────────────────────────

class ConflictAvoidancePlannerAgent(BaseAgent):
    """
    Activates ONLY when airspace pre-screening (safety/conflict_screening.py)
    finds a conflict probability above the operational threshold against
    another active drone.
    """

    name = "Conflict Avoidance Planner"
    domain = "conflict_avoidance"
    model = "llama4:scout"

    CAM_MANDATE = """
    YOU MUST SHOW EXPLICIT CALCULATIONS FOR EVERY AVOIDANCE MANEUVER YOU PROPOSE:
    1. State current conflict probability and the operational threshold (1e-3).
    2. Propose a resolution: HOLD (hover/delay), ALTITUDE_SHIFT (move to a different band),
       or REROUTE (detour around the conflict point).
    3. Compute the delay or detour distance required to bring separation back above 15m.
    4. Issue verdict GREEN (conflict resolved) or RED (dispatch must be held).
    """

    SYSTEM_PROMPT = f"""You are the Conflict Avoidance Planner for the AeroFleet dispatch council.
You activate ONLY when airspace screening has found conflict probability above 1e-3
against another active drone.

{REACT_MANDATE}

{CAM_MANDATE}

Prioritise the resolution with the least delivery-time impact:
  — Altitude-band shift is usually cheapest (no delay, no detour)
  — Short HOLD (< 60s) is next cheapest
  — Reroute only if the other two are insufficient

Always output VERDICT: GREEN, YELLOW, or RED.
"""

    def evaluate(self, dispatch_plan: Dict[str, Any], telemetry: Dict[str, Any], round_num: int) -> Dict[str, Any]:
        if not dispatch_plan.get("conflict_avoidance_required", False):
            return {
                "agent": self.name, "domain": self.domain, "verdict": "GREEN",
                "reasoning": "No conflicts above the operational threshold (1e-3). Avoidance not required.",
                "model": self.model, "skipped": True, "flags": [],
            }

        airspace = dispatch_plan.get("airspace_telemetry", {}).get("airspace_screening", {})
        top_conflicts = airspace.get("top_conflicts", [{}])
        first = top_conflicts[0] if top_conflicts else {}

        prompt = f"""
AIRSPACE SCREENING RESULTS:
  Max conflict probability: {airspace.get('max_conflict_probability', 'unknown')}
  Top conflict: {first}
  All conflicts: {top_conflicts}

DRONE PARAMETERS:
  Current altitude band: {dispatch_plan.get('altitude_m', 60)} m
  ETA to conflict point: {first.get('time_of_closest_approach_s', 'unknown')} s

{self.CAM_MANDATE}

Propose the optimal avoidance action to bring conflict probability below 1e-3.
"""
        response = self._call_llm(prompt, dispatch_plan)
        return self._parse_response(response, self.domain)


# ─────────────────────────────────────────────────────────────────────────────
#  SPECIALIST — BATTERY SWAP PLANNER
# ─────────────────────────────────────────────────────────────────────────────

class BatterySwapPlannerAgent(BaseAgent):
    """
    Activates for multi-leg deliveries or fleet-wide re-balancing missions
    where a drone needs an intermediate battery swap or a multi-depot
    routing decision (analogue of the old on-orbit-servicing specialist —
    same "does this need a special intermediate stop?" shape of problem).
    """

    name = "Battery Swap Planner"
    domain = "battery_swap_planning"
    model = "phi4-reasoning:plus"

    SYSTEM_PROMPT = f"""You are the Battery Swap Planner for the AeroFleet dispatch council.
You handle deliveries that require an intermediate battery-swap or fast-charge stop,
and multi-drone rebalancing across the micro-depot network.

{REACT_MANDATE}

YOU MUST SHOW CALCULATIONS FOR:
1. Whether the direct route's energy requirement exceeds the drone's available energy
   (i.e. usable_wh - reserve_wh < required_wh for the direct route).
2. If a swap is needed: which intermediate depot minimises total added distance?
   Rank candidate depots by (detour_km x wh_per_km) + swap_time_minutes x time_value.
3. Total revised ETA including the swap-station queue wait.
4. Whether the destination depot has spare battery-swap slots (Ops Scheduler's domain
   for capacity — you only compute whether a swap is *needed* and *where*).

Always output VERDICT: GREEN, YELLOW, or RED.
"""

    _SWAP_TRIGGER_KEYWORDS = {"battery_critical", "multi_leg", "rebalancing", "swap_required"}

    def evaluate(self, dispatch_plan: Dict[str, Any], telemetry: Dict[str, Any], round_num: int) -> Dict[str, Any]:
        trigger = dispatch_plan.get("requires_battery_swap", False) or any(
            kw in str(dispatch_plan.get("mission_type", "")).lower() for kw in self._SWAP_TRIGGER_KEYWORDS
        )
        if not trigger:
            return {
                "agent": self.name, "domain": self.domain, "verdict": "GREEN",
                "reasoning": "Direct route within battery range. Swap planning not applicable.",
                "model": self.model, "skipped": True, "flags": [],
            }

        prompt = f"""
ORDER: {dispatch_plan.get('order_id', 'unknown')}
DIRECT ROUTE DISTANCE: {dispatch_plan.get('distance_km', 0)} km
BATTERY STATE OF CHARGE: {dispatch_plan.get('battery_soc', 1.0)}
BATTERY CAPACITY: {dispatch_plan.get('battery_capacity_wh', 500)} Wh
CANDIDATE INTERMEDIATE DEPOTS: {dispatch_plan.get('candidate_depots', [])}

Evaluate whether a battery swap is required and, if so, at which depot.
Show the full energy budget.
"""
        response = self._call_llm(prompt, dispatch_plan)
        return self._parse_response(response, self.domain)


# ─────────────────────────────────────────────────────────────────────────────
#  SPECIALIST — AI GOVERNANCE VALIDATOR
# ─────────────────────────────────────────────────────────────────────────────

class AIGovernanceValidatorAgent(BaseAgent):
    """
    Produces (1) DGCA/regulatory compliance across mandatory fields and
    (2) a socio-technical risk assessment using the MAD-BAD-SAD framework
    (Donta et al. 2025), retargeted from spacecraft autonomy to urban
    autonomous drone operations.
    """

    name = "AI Governance Validator"
    domain = "governance_legal"
    model = "llama4:scout"

    SYSTEM_PROMPT = f"""You are the AI Governance Validator for the AeroFleet dispatch council.
You produce TWO outputs: (1) regulatory compliance across mandatory fields,
and (2) a socio-technical risk assessment using the MAD-BAD-SAD framework.

═══════════════════════════════════════════════════════
PART 1 — REGULATORY COMPLIANCE
═══════════════════════════════════════════════════════
OUTPUT ALL FIELDS IN THIS EXACT JSON STRUCTURE:
{{
  "dgca_zone_compliance": {{
    "status": "COMPLIANT | AT_RISK | NON_COMPLIANT",
    "zone_colour": "GREEN | YELLOW | RED",
    "atc_permission_required": true/false,
    "notes": "<one sentence>"
  }},
  "uin_uaop_registration": {{
    "status": "COMPLIANT | AT_RISK | NON_COMPLIANT",
    "notes": "<one sentence>"
  }},
  "autonomous_bvlos_flag": {{
    "status": "CLEAR | FLAGGED | CRITICAL",
    "human_override_available": true/false,
    "proposed_fallback_mechanism": "<describe RTH/emergency-landing mechanism>",
    "notes": "<one sentence>"
  }},
  "data_privacy": {{
    "status": "COMPLIANT | AT_RISK | NON_COMPLIANT",
    "onboard_camera_present": true/false,
    "notes": "<privacy concern if flying over private property>"
  }}
}}

═══════════════════════════════════════════════════════
PART 2 — MAD-BAD-SAD SOCIO-TECHNICAL ASSESSMENT
═══════════════════════════════════════════════════════
MAD (Morality, Autonomy, Dilemmas): moral basis for autonomous delivery over populated
areas; "moral crumple zone" if the AI causes harm — who is accountable?
BAD (Biases, Accountability, Dangers): dispatch-priority bias (does EXPRESS/MEDICAL routing
disadvantage a neighbourhood?); most dangerous failure modes.
SAD (Societal, Adoption, Design): noise/privacy impact on residents; is there a human-in-the-loop
override for the public to request?

{{
  "mad_bad_sad": {{
    "mad": {{"moral_basis": "<string>", "crumple_zone_risk": "LOW|MEDIUM|HIGH", "transparency_score": 1-5}},
    "bad": {{"routing_bias_risk": "LOW|MEDIUM|HIGH", "top_danger_modes": ["<mode1>", "<mode2>"]}},
    "sad": {{"societal_impact": "<string>", "human_ai_complementarity": "STRONG|ADEQUATE|WEAK"}}
  }}
}}

VERDICT: GREEN if all fields COMPLIANT and risks LOW/MEDIUM; YELLOW if any AT_RISK; RED if any NON_COMPLIANT.
ALWAYS use ReAct format.
"""

    def evaluate(self, dispatch_plan: Dict[str, Any], telemetry: Dict[str, Any], round_num: int) -> Dict[str, Any]:
        prompt = f"""
ORDER               : {dispatch_plan.get('order_id', 'unknown')}
ZONE COLOUR          : {dispatch_plan.get('zone_colour', 'GREEN')}
ATC PERMISSION       : {dispatch_plan.get('atc_permission', False)}
UIN REGISTERED       : {dispatch_plan.get('uin_registered', True)}
AUTONOMOUS BVLOS     : {dispatch_plan.get('autonomous_bvlos', True)}
ONBOARD CAMERA       : {dispatch_plan.get('onboard_camera', True)}
PRIORITY             : {dispatch_plan.get('priority', 'STANDARD')}
FLIGHT OVER RESIDENTIAL: {dispatch_plan.get('over_residential', True)}

Produce the full compliance report, then issue your VERDICT.
"""
        response = self._call_llm(prompt, dispatch_plan)
        return self._parse_response(response, self.domain)


# ─────────────────────────────────────────────────────────────────────────────
#  SPECIALIST — CYBER SECURITY AUDITOR
# ─────────────────────────────────────────────────────────────────────────────

class CyberSecurityAuditorAgent(BaseAgent):
    """Audits AI-specific and RF/GNSS-specific vulnerabilities for the
    dispatch decision, using the Breda et al. (2023) taxonomy retargeted
    at drone C2 links and onboard autonomy."""

    name = "Cyber Security Auditor"
    domain = "cybersecurity"
    model = "llama4:scout"

    SYSTEM_PROMPT = f"""You are the Cyber Security Auditor for the AeroFleet dispatch council.

{REACT_MANDATE}

CHECK ALL 4 VULNERABILITY CATEGORIES:

1. GNSS SPOOFING / DATA VULNERABILITY — Can the navigation solution be spoofed or jammed?
   Is there a visual-inertial or beacon-based fallback if GNSS is lost mid-flight?

2. MODEL VULNERABILITY — Is the onboard autonomy stack isolated from the public C2 link,
   or could a malicious uplink alter routing/behaviour?

3. C2 LINK / HARDWARE — Is the command & telemetry link encrypted (minimum AES-128)?
   Supply-chain integrity of flight controller and companion computer?

4. EXPLAINABILITY — Is the dispatch decision auditable end-to-end (agent votes -> CBF gate ->
   final action)? Is there a non-AI fallback (manual RTH trigger) on uncertainty threshold breach?

Output a structured security audit JSON, then a single VERDICT: GREEN / YELLOW / RED.
"""

    def evaluate(self, dispatch_plan: Dict[str, Any], telemetry: Dict[str, Any], round_num: int) -> Dict[str, Any]:
        prompt = f"""
C2 LINK ENCRYPTION   : {dispatch_plan.get('c2_encryption', 'unspecified')}
GNSS DEPENDENT       : {dispatch_plan.get('gnss_dependent', True)}
VISUAL FALLBACK NAV  : {dispatch_plan.get('visual_fallback_nav', False)}
AUTONOMOUS BVLOS     : {dispatch_plan.get('autonomous_bvlos', True)}
COMPANION COMPUTER   : {dispatch_plan.get('companion_computer', 'unspecified')}

Run the full 4-category cyber security audit. Issue VERDICT: GREEN, YELLOW, or RED.
"""
        response = self._call_llm(prompt, dispatch_plan)
        return self._parse_response(response, self.domain)


# ─────────────────────────────────────────────────────────────────────────────
#  SPECIALIST — EDGE COMPUTE FEASIBILITY AGENT
# ─────────────────────────────────────────────────────────────────────────────

class EdgeComputeFeasibilityAgent(BaseAgent):
    """
    Evaluates whether the drone's onboard compute (obstacle avoidance,
    visual nav, package-recognition) can run reliably given battery state,
    using a battery-SoC-based GREEN/YELLOW/RED compute-zone model — the
    drone analogue of the old eclipse/solar-power compute-zone model.
    """

    name = "Edge Compute Feasibility Agent"
    domain = "edge_compute"
    model = "phi4-reasoning:plus"

    SYSTEM_PROMPT = """You are the Edge Compute Feasibility Agent.
You evaluate whether the drone's onboard compute can run its full autonomy
stack throughout the flight, using a battery-state compute-zone model.

COMPUTE ZONE MODEL:
GREEN zone:  SoC > 60%              -> Full autonomy stack (vision obstacle-avoidance, SLAM)
YELLOW zone: 30% < SoC <= 60%        -> Lightweight inference only (reduced frame rate, coarse detection)
RED zone:    SoC <= 30%              -> Flight-critical only (IMU/GPS hold, no vision compute); land ASAP.

CALCULATIONS TO SHOW:
1. Compute power draw vs total power budget at current SoC.
2. Projected SoC at each remaining leg of the route.
3. Which compute zone the drone will be in for each leg.
4. Whether obstacle avoidance (flight-critical for BVLOS over urban areas) stays
   available for the ENTIRE flight — if not, this is a RED verdict regardless of battery margin.

OUTPUT:
{
  "compute_zones_by_leg": {"leg_1": "GREEN|YELLOW|RED", "leg_2": "GREEN|YELLOW|RED"},
  "obstacle_avoidance_available_full_flight": true/false,
  "recommendations": ["<rec1>", "<rec2>"]
}

ALWAYS use ReAct format. Issue GREEN/YELLOW/RED on compute feasibility.
"""

    def evaluate(self, dispatch_plan: Dict[str, Any], telemetry: Dict[str, Any], round_num: int) -> Dict[str, Any]:
        soc = float(dispatch_plan.get("battery_soc", 1.0))
        legs = dispatch_plan.get("route_legs", 1)

        prompt = f"""
ORDER                : {dispatch_plan.get('order_id', 'unknown')}
CURRENT BATTERY SOC   : {soc:.2f}
ROUTE LEGS            : {legs}
COMPUTE POWER DRAW (W): {dispatch_plan.get('compute_power_w', 15)}
FLIGHT DURATION (min) : {dispatch_plan.get('flight_duration_min', 10)}
OVER URBAN AREA       : {dispatch_plan.get('over_residential', True)}

Apply the battery-state compute zone model across all {legs} leg(s).
Evaluate whether obstacle avoidance stays available for the full flight.

{self.SYSTEM_PROMPT}
"""
        response = self._call_llm(prompt, dispatch_plan)
        return self._parse_response(response, self.domain)
