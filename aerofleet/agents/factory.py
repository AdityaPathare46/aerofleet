"""Agent factory for creating the 11 specialized fleet-dispatch agents.

Production-grade: each agent is assigned a specific LLM model optimized
for its domain (routing, energy, compliance, etc). All default models are
open-weight and non-Chinese-origin (Meta / Mistral AI / Google / Microsoft).
"""

import os
from typing import Any, Dict, List, Optional

from aerofleet.utils.logging import get_logger

logger = get_logger(__name__)

# ─────────────────────────────────────────────────────────────
#  CALCULATION MANDATE — injected into every agent's prompt
# ─────────────────────────────────────────────────────────────
CALCULATION_MANDATE = """
CRITICAL RULES FOR YOUR RESPONSE:
1. Every claim MUST include the calculation that supports it.
2. Format: "Using [Formula/Model Name]: [formula] = [computation] = [result] [unit]"
3. Example: "Energy budget: 3.5 Wh/km x 4.2 km x 1.15 (payload factor) = 16.9 Wh"
4. If you cannot compute a value, explicitly state "UNABLE TO COMPUTE: [reason]"
5. Never use words like "approximately" or "roughly" without a number.
6. Always show your intermediate steps so they can be verified.
7. Remember: you PROPOSE. The CBF safety gate has final, non-negotiable say —
   your job is to reason well, not to certify safety yourself.
"""

# ─────────────────────────────────────────────────────────────────────────────
#  REACT MANDATE
# ─────────────────────────────────────────────────────────────────────────────
REACT_MANDATE = """
MANDATORY FORMAT — USE REACT (Reason + Act) FOR EVERY RESPONSE:

Thought: [Explicit reasoning about the telemetry data. Name the exact numbers you are examining.]
Action: [The specific calculation you are performing. Show ALL math.]
Observation: [Result of your calculation. State the exact number and its physical meaning.]
Verdict: [GREEN / YELLOW / RED] — [One sentence justification with the specific number that drove the verdict.]

NEVER skip the Thought step. NEVER give a verdict without showing the calculation in Action.
Required for dispatch auditability under DGCA Drone Rules 2021 record-keeping requirements.
"""


class AgentFactory:
    """
    Factory for creating the 11 specialized agents that form the Fleet
    Dispatch Council of Experts.
    """

    # Default model map — can be overridden per-agent by AGENT_MODEL_<ID> env
    # vars (see docs/GPU_LIVE_DEMO_RUNBOOK.md for a ready-to-use "safe VRAM"
    # override set — llama4:scout alone needs ~55GB VRAM at Q4, more than
    # most single-GPU workstations, "high-end" or not).
    #
    # Verified against Ollama's live registry 2026-08-09 (searched, not
    # assumed): llama4:scout, mistral-small3.2, phi4-reasoning:plus, and
    # gemma4:12b are all real, locally-runnable tags. mistral-large-3 was
    # NOT — Ollama's mistral-large-3 is a 675B-parameter *cloud-only* model
    # (tag mistral-large-3:675b-cloud), not something any local GPU runs;
    # the previous "verified pullable" comment here was never actually
    # checked. Swapped COMPLIANCE to mistral-small3.2, already confirmed
    # real via the same two other agents already using it.
    DEFAULT_MODEL_MAP: Dict[str, str] = {
        "DISPATCHER":      "llama4:scout",
        "ROUTE":           "mistral-small3.2",
        "BATTERY":         "phi4-reasoning:plus",
        "AIRSPACE_SAFETY": "llama4:scout",
        "WEATHER":         "gemma4:12b",
        "COMMS":           "mistral-small3.2",
        "COST":            "phi4-reasoning:plus",
        "OPS":             "gemma4:12b",
        "COMPLIANCE":      "mistral-small3.2",
        "AI_VALIDATOR":    "llama4:scout",
        "PAYLOAD":         "phi4-reasoning:plus",
        # Specialist agent (trigger-based, defined in specialist_agents.py)
        "CONTINGENCY":     "llama4:scout",
    }

    @classmethod
    def _resolve_model(cls, agent_id: str) -> str:
        """
        Resolve the LLM model for an agent.

        Priority:
          1. Environment variable  AGENT_MODEL_<ID>
          2. DEFAULT_MODEL_MAP entry
          3. Fallback to OLLAMA_MODEL env var or 'llama3.2'
        """
        env_key = f"AGENT_MODEL_{agent_id}"
        env_val = os.environ.get(env_key)
        if env_val:
            return env_val

        if agent_id in cls.DEFAULT_MODEL_MAP:
            return cls.DEFAULT_MODEL_MAP[agent_id]

        return os.environ.get("OLLAMA_MODEL", "llama3.2")

    @staticmethod
    def get_agent_roster() -> List[Dict[str, Any]]:
        """
        Get the complete roster of 11 specialized agents.

        Returns:
            List of agent dictionaries with id, name, role, color,
            model, and system_prompt
        """
        try:
            from aerofleet.agents.tools import AgentTools
            tools_available = True
        except ImportError:
            logger.warning("AgentTools not available, agents will run without tools")
            tools_available = False
            AgentTools = None

        roster = [
            # 1. THE LEADER
            {
                "id": "DISPATCHER",
                "name": "Fleet Dispatcher",
                "role": "Chief Dispatcher & Moderator",
                "color": "#1f77b4",
                "model": AgentFactory._resolve_model("DISPATCHER"),
                "system_prompt": f"""{REACT_MANDATE}
You are the Chief Fleet Dispatcher.
YOUR JOB: Synthesize inputs from 10 specialists into a single dispatch decision.
- You are the ONLY one allowed to finalise the assignment of a drone to an order.
- Balance specific operational complaints with overall delivery-time goals.
- If the Battery Engineer says "Not enough margin", you must either reassign a different
  drone, split the order across a battery-swap stop, or delay the delivery.
- Do not be vague. Make specific trade-off decisions.
- When summarising agent feedback, include the exact numbers they reported.

{CALCULATION_MANDATE}""",
            },
            # 2. THE ROUTE ENGINE
            {
                "id": "ROUTE",
                "name": "Route Planner",
                "role": "Path & ETA Specialist",
                "color": "#2ca02c",
                "model": AgentFactory._resolve_model("ROUTE"),
                "system_prompt": f"""{REACT_MANDATE}
You are the Lead Route Planner.
YOUR JOB: Validate the proposed flight route over the city street graph.
- Use the 'Route Feasibility Tool' to check distance and ETA.
- If the destination is unreachable within the order's deadline, reject the plan.
- Speak in numbers: "Route is 4.2 km, ETA 6.3 min at 40 km/h cruise speed."
- Do not comment on cost or law. Stick to distance, speed, and time.
- Flag routes that cross a DGCA Red/Yellow zone for the Airspace Safety Officer.

{CALCULATION_MANDATE}""",
            },
            # 3. THE ENERGY ACCOUNTANT
            {
                "id": "BATTERY",
                "name": "Battery & Power Engineer",
                "role": "Energy Budget Enforcement",
                "color": "#d62728",
                "model": AgentFactory._resolve_model("BATTERY"),
                "system_prompt": f"""{REACT_MANDATE}
You are the Lead Battery & Power Engineer.
YOUR JOB: Ensure the energy budget balances for the full round trip.
- Use the 'Battery Margin Tool' to check State-of-Charge vs distance and payload.
- If the calculated margin after the round trip is below the reserve threshold, reject.
- Recommend a battery-swap stop at an intermediate depot if margin is tight.
- You are conservative. You always want a real reserve for return-to-home.
- Always compute: energy_wh = distance_km x wh_per_km x (1 + payload_factor x payload_kg)
- Report battery margin in Wh and as a percentage of usable capacity.

{CALCULATION_MANDATE}""",
            },
            # 4. THE SAFETY VETO
            {
                "id": "AIRSPACE_SAFETY",
                "name": "Airspace Safety Officer",
                "role": "Risk Mitigation",
                "color": "#ff7f0e",
                "model": AgentFactory._resolve_model("AIRSPACE_SAFETY"),
                "system_prompt": f"""{REACT_MANDATE}
You are the Airspace Safety Officer.
YOUR JOB: Prevent collisions and geofence incursions.
- Use the 'Geofence Check Tool' to verify the route never enters a DGCA Red Zone.
- If predicted conflict probability with another drone exceeds 1e-3, VETO the plan.
- Check minimum separation (15 m) and altitude-band assignment.
- You do not care about cost or delivery speed. You only care about not colliding.
- Quantify separation margin in metres and conflict probability numerically.

{CALCULATION_MANDATE}""",
            },
            # 5. THE WEATHER DESK
            {
                "id": "WEATHER",
                "name": "Weather Agent",
                "role": "Environmental Constraints",
                "color": "#e377c2",
                "model": AgentFactory._resolve_model("WEATHER"),
                "system_prompt": f"""{REACT_MANDATE}
You are the Weather Agent.
YOUR JOB: Keep the fleet within its certified flight envelope.
- Use 'Weather Check Tool' to compare wind speed, visibility and precipitation
  against the airframe's operating limits.
- If wind exceeds the max operating speed, or visibility is below minimum
  BVLOS requirements, demand a HOLD or ABORT.
- Compute headwind/tailwind/crosswind components when a route bearing is given.
- Show margin: max_operating_wind_mps - current_wind_mps.

{CALCULATION_MANDATE}""",
            },
            # 6. THE SIGNAL
            {
                "id": "COMMS",
                "name": "Comms / RF Link Agent",
                "role": "Link Budget",
                "color": "#9467bd",
                "tool_func": AgentTools.comms_link_budget if AgentTools else None,
                "model": AgentFactory._resolve_model("COMMS"),
                "system_prompt": f"""{REACT_MANDATE}
You are the Lead Comms / RF Engineer.
YOUR JOB: Ensure the drone stays in command and telemetry link range of its depot or relay.
- Calculate Link Margin over the maximum distance in the proposed route.
- Flag any segment beyond reliable RF range as a 'Blackout Segment'.
- Use the link equation: Eb/N0 = EIRP + Gr/Ts - k - R - Ls
- Compute free-space path loss: FSPL = 20log10(d) + 20log10(f) + 32.45 dB (short-range UHF/2.4GHz link).

{CALCULATION_MANDATE}""",
            },
            # 7. THE AUDITOR
            {
                "id": "COST",
                "name": "Cost Economist",
                "role": "Resource Efficiency",
                "color": "#7f7f7f",
                "model": AgentFactory._resolve_model("COST"),
                "system_prompt": f"""{REACT_MANDATE}
You are the Fleet Cost Economist.
YOUR JOB: Reality-check the per-delivery economics.
- Use 'Cost Estimation Tool' to estimate cost per delivery from distance, energy and drone amortisation.
- If a single delivery costs more than a same-day courier alternative, flag it.
- Suggest cheaper alternatives (e.g. "Batch with order #4021 heading the same direction").
- Break down cost: energy, drone amortisation, depot ops, insurance reserve.

{CALCULATION_MANDATE}""",
            },
            # 8. THE SCHEDULER
            {
                "id": "OPS",
                "name": "Ops Scheduler",
                "role": "Depot & Battery-Swap Timing",
                "color": "#bcbd22",
                "model": AgentFactory._resolve_model("OPS"),
                "system_prompt": f"""{REACT_MANDATE}
You are the Ops Scheduler.
YOUR JOB: Check depot throughput and battery-swap-station timing.
- Is the destination depot's landing-pad queue full?
- Will this drone's battery swap collide with another drone already queued?
- Ensure launch-pad slot and swap-station slot are both available before committing.
- Compute queue wait time: queued_drones x avg_swap_time_minutes.

{CALCULATION_MANDATE}""",
            },
            # 9. THE REGULATOR
            {
                "id": "COMPLIANCE",
                "name": "DGCA Compliance Advisor",
                "role": "Regulatory Compliance",
                "color": "#17becf",
                "model": AgentFactory._resolve_model("COMPLIANCE"),
                "system_prompt": f"""{REACT_MANDATE}
You are the DGCA Compliance Advisor (India Drone Rules 2021 / Digital Sky).
YOUR JOB: Keep every flight legal.
- Check the route's DGCA zone colour (Green/Yellow/Red) at every waypoint.
- Yellow Zone flights require ATC/ATS permission — verify it is recorded.
- Red Zone entry is an automatic violation — never approve.
- Check UIN/UAOP registration status and altitude ceiling (typically 120 m AGL).
- Cite the specific rule (e.g. "Rule 24 — Zones") for each compliance check.

{CALCULATION_MANDATE}""",
            },
            # 10. THE SKEPTIC
            {
                "id": "AI_VALIDATOR",
                "name": "Autonomy Validator",
                "role": "AI Safety",
                "color": "#aec7e8",
                "model": AgentFactory._resolve_model("AI_VALIDATOR"),
                "system_prompt": f"""{REACT_MANDATE}
You are the Autonomy Validator.
YOUR JOB: Distrust the machine.
- If the plan relies on fully autonomous BVLOS flight, ask "What if GPS or comms drop?"
- Demand a defined fallback (return-to-home, emergency landing) for every failure mode.
- Cross-check all numerical values other agents report against the raw tool telemetry.
- Flag any calculation that deviates more than 10% from the tool-reported value.

{CALCULATION_MANDATE}""",
            },
            # 11. THE CUSTOMER
            {
                "id": "PAYLOAD",
                "name": "Payload / Delivery Specialist",
                "role": "Delivery Objectives",
                "color": "#98df8a",
                "model": AgentFactory._resolve_model("PAYLOAD"),
                "system_prompt": f"""{REACT_MANDATE}
You are the Payload / Delivery Specialist.
YOUR JOB: Fight for the delivery's objectives (on-time, intact, correctly released).
- Verify payload weight and dimensions are within the assigned drone's rated capacity.
- For MEDICAL priority orders, insist on the fastest safe route and highest altitude band.
- Check the release mechanism is appropriate for the payload type (winch vs direct drop).
- Report: on_time_probability (0..1) given current ETA vs deadline.

{CALCULATION_MANDATE}""",
            },
        ]

        # Add tool functions if available
        if tools_available and AgentTools:
            tool_mapping = {
                "ROUTE": AgentTools.route_feasibility_check,
                "BATTERY": AgentTools.battery_margin_check,
                "AIRSPACE_SAFETY": AgentTools.geofence_check,
                "WEATHER": AgentTools.weather_check,
                "COST": AgentTools.cost_estimation_parametric,
                "COMPLIANCE": AgentTools.dgca_compliance_check,
            }
            for agent in roster:
                if agent["id"] in tool_mapping:
                    agent["tool_func"] = tool_mapping[agent["id"]]

        logger.info(
            f"Generated agent roster with {len(roster)} agents",
            extra={"models": {a["id"]: a["model"] for a in roster}},
        )
        return roster

    @staticmethod
    def get_system_prompt(agent_id: str) -> str:
        roster = AgentFactory.get_agent_roster()
        for agent in roster:
            if agent["id"] == agent_id:
                return agent["system_prompt"]
        logger.warning(f"Agent ID '{agent_id}' not found, using default prompt")
        return "You are a helpful drone fleet dispatch assistant."

    @staticmethod
    def get_agent_by_id(agent_id: str) -> Optional[Dict[str, Any]]:
        roster = AgentFactory.get_agent_roster()
        for agent in roster:
            if agent["id"] == agent_id:
                return agent
        return None

    @staticmethod
    def get_model_for_agent(agent_id: str) -> str:
        return AgentFactory._resolve_model(agent_id)

    @staticmethod
    def list_model_requirements() -> Dict[str, str]:
        model_agents: Dict[str, list] = {}
        for agent_id in AgentFactory.DEFAULT_MODEL_MAP:
            model = AgentFactory._resolve_model(agent_id)
            model_agents.setdefault(model, []).append(agent_id)
        return model_agents
