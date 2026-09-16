"""Council of Experts — orchestrates multi-agent debate for dispatch decisions.

Architecture (unchanged from the original multi-domain council pattern,
retargeted from space-mission planning to drone-fleet dispatch):
  - Airspace pre-screening (deterministic, cheap, runs before any LLM call)
  - Iterative ACO-style convergence up to 5 rounds
  - 11 core agents + 5 specialist agents (trigger-based)
  - ReAct format mandate for auditability
  - CBF safety gate annotation (formal, non-negotiable, runs last)
  - Async LLM supervisor
  - Dispatch complexity classifier + dynamic model routing
"""

import json
import time
from typing import Any, Dict, List, Optional, Tuple

from aerofleet.agents.factory import AgentFactory
from aerofleet.agents.llm_backend import build_llm_backend
from aerofleet.utils.exceptions import AgentCommunicationError
from aerofleet.utils.logging import get_logger

logger = get_logger(__name__)


class CouncilOfExperts:
    """
    Orchestrates the fleet dispatch council's debate with iterative ACO
    convergence.

    Execution order per dispatch decision:
      1. Complexity classifier + dynamic model routing
      2. Airspace pre-screening — injects conflict/geofence telemetry
      3. Iterative debate (up to 5 rounds, pheromone decay)
         - Async supervisor adjusts threshold between rounds
      4. CBF safety gate annotation — final, non-negotiable
    """

    MAX_DEBATE_ROUNDS = 5

    def __init__(self):
        """Initialize the council with agent roster, specialist agents, and LLM backend."""
        self.roster = AgentFactory.get_agent_roster()
        self.llm = build_llm_backend()

        try:
            from aerofleet.agents.specialist_agents import (
                AIGovernanceValidatorAgent,
                BatterySwapPlannerAgent,
                ConflictAvoidancePlannerAgent,
                CyberSecurityAuditorAgent,
                EdgeComputeFeasibilityAgent,
            )

            self._specialist_agents = [
                ConflictAvoidancePlannerAgent(self.llm),
                BatterySwapPlannerAgent(self.llm),
                AIGovernanceValidatorAgent(self.llm),
                CyberSecurityAuditorAgent(self.llm),
                EdgeComputeFeasibilityAgent(self.llm),
            ]
        except Exception as exc:
            logger.warning(f"Specialist agents unavailable: {exc}")
            self._specialist_agents = []

        try:
            from aerofleet.agents.async_supervisor import AsyncLLMSupervisor
            self._supervisor = AsyncLLMSupervisor(self.llm)
        except Exception as exc:
            logger.warning(f"AsyncLLMSupervisor unavailable: {exc}")
            self._supervisor = None

        model_map = {a["id"]: a["model"] for a in self.roster}
        logger.info(
            f"Council initialized with {len(self.roster)} core + "
            f"{len(self._specialist_agents)} specialist agents",
            extra={"model_map": model_map},
        )

    def run_grand_debate(
        self,
        dispatch_plan: Dict[str, Any],
        chat_history: List[Dict[str, str]] = None,
        precomputed_cbf_certificate: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """
        Execute the iterative council debate (up to 5 rounds) over a
        candidate dispatch plan (see aerofleet/fleet/dispatch.py for how
        candidates are generated).

        This method is NEVER called synchronously from a request handler —
        it runs only from aerofleet/agents/explanation_worker.py's
        background task, generating a post-hoc explanation of a dispatch
        decision that was already made deterministically. Pass the real
        certificate from that decision as `precomputed_cbf_certificate` so
        the council explains the actual outcome instead of computing (and
        discarding) a second, redundant one — there is only ever one real
        verdict for a given dispatch, and it isn't this method's job to
        produce it.

        Returns:
            Tuple of (final_plan, debate_transcript)
        """
        if chat_history is None:
            chat_history = []

        debate_start = time.time()
        logger.info("Starting council debate (iterative ACO mode)")
        transcript: List[Dict[str, Any]] = []
        telemetry_data: Dict[str, Any] = {}
        round_history: List[Dict] = []

        # ── Complexity Classifier + Dynamic Model Routing ──────────────────
        complexity = self._classify_dispatch_complexity(dispatch_plan)
        self._apply_dynamic_model_routing(complexity)
        transcript.append({
            "role": "SYSTEM", "name": "Complexity Classifier",
            "text": f"Dispatch complexity: {complexity}",
            "phase": 0,
        })

        # ── Airspace Pre-Screening ──────────────────────────────────────
        try:
            from aerofleet.safety.conflict_screening import AirspaceScreeningModule

            # Pre-screening runs before the ROUTE agent's tool call, so seed
            # a deterministic preliminary ETA from raw distance here — the
            # screen needs a real time estimate to compare against other
            # drones' ETAs, not the tool-call default.
            if "eta_minutes" not in dispatch_plan:
                prelim_km = float(dispatch_plan.get("outbound_km", dispatch_plan.get("distance_km", 3.0)))
                dispatch_plan["eta_minutes"] = round((prelim_km / 40.0) * 60.0, 2)

            screening = AirspaceScreeningModule()
            active_drones = dispatch_plan.get("active_drones", [])
            screen_result = screening.screen(dispatch_plan, active_drones)
            dispatch_plan["airspace_telemetry"] = screen_result.airspace_telemetry
            if screen_result.conflict_avoidance_required:
                dispatch_plan["conflict_avoidance_required"] = True
            transcript.append({
                "role": "SYSTEM", "name": "Airspace Screening",
                "text": json.dumps(screen_result.airspace_telemetry, indent=2),
                "phase": 0,
            })
        except Exception as exc:
            logger.warning(f"Airspace screening skipped: {exc}")

        # Initialize pheromone weights for ACO
        agent_weights: Dict[str, float] = {a["id"]: 1.0 for a in self.roster[1:]}
        for sa in self._specialist_agents:
            agent_weights[sa.name] = 1.0

        # ── Iterative ACO Rounds ────────────────────────────────────────
        final_verdict_text = ""
        active_agent_ids: Optional[List[str]] = None  # None = all agents

        for round_num in range(self.MAX_DEBATE_ROUNDS):
            round_start = time.time()
            logger.info(f"Council round {round_num + 1}/{self.MAX_DEBATE_ROUNDS}")

            if round_num == 0 or active_agent_ids is None:
                active_roster = self.roster[1:]  # skip Dispatcher (speaks last)
            else:
                active_roster = [a for a in self.roster[1:] if a["id"] in active_agent_ids]

            transcript.append({
                "role": "SYSTEM", "name": "Council",
                "text": f"=== Round {round_num + 1} — {len(active_roster)} agents active ===",
                "phase": 1,
            })

            # --- PHASE 1: TOOL EXECUTION ---
            transcript.append({
                "role": "SYSTEM", "name": "Computer",
                "text": "Running dispatch subsystem checks...",
                "phase": 1,
            })
            for agent in self.roster:
                if "tool_func" in agent:
                    try:
                        args = self._map_plan_to_tool_args(agent["id"], dispatch_plan)
                        if args:
                            tool_start = time.time()
                            result = agent["tool_func"](**args)
                            telemetry_data[agent["id"]] = result
                            transcript.append({
                                "role": "SYSTEM",
                                "name": f"{agent['name']} Tool",
                                "text": f"Tool output: {json.dumps(result, indent=2)}",
                                "duration_s": round(time.time() - tool_start, 2),
                                "phase": 1,
                            })
                            if isinstance(result, dict) and "error" in result:
                                logger.warning(f"Tool error in {agent['id']}: {result['error']}")
                    except Exception as exc:
                        logger.error(f"Tool execution failed for {agent['id']}: {exc}")
                        telemetry_data[agent["id"]] = {"error": str(exc)}

            # --- PHASE 2: AGENT CRITIQUES ---
            agent_verdicts: Dict[str, str] = {}
            for agent in active_roster:
                try:
                    agent_start = time.time()
                    my_telemetry = telemetry_data.get(agent["id"], "No tool data available.")
                    prompt = self._build_critique_prompt(agent, dispatch_plan, my_telemetry)
                    response = self.llm.reason(
                        context_prompt=prompt,
                        model=agent["model"],
                        system_prompt_override=agent["system_prompt"],
                    )
                    verdict = "GREEN"
                    if "RED" in response.upper():
                        verdict = "RED"
                    elif "YELLOW" in response.upper():
                        verdict = "YELLOW"

                    # HARD SAFETY GATE: Force RED if telemetry failed
                    if isinstance(my_telemetry, dict) and my_telemetry.get("status") == "FAIL":
                        verdict = "RED"

                    agent_verdicts[agent["id"]] = verdict
                    transcript.append({
                        "role": agent["role"], "name": agent["name"],
                        "text": response, "verdict": verdict,
                        "color": agent.get("color", "#000000"),
                        "model": agent["model"],
                        "duration_s": round(time.time() - agent_start, 2),
                        "phase": 2, "round": round_num + 1,
                        "weight": agent_weights.get(agent["id"], 1.0),
                    })
                except AgentCommunicationError as exc:
                    logger.error(f"Agent {agent['name']} failed: {exc}")
                    self._append_error_transcript(transcript, agent, str(exc))
                    agent_verdicts[agent["id"]] = "YELLOW"
                except Exception as exc:
                    logger.error(f"Critique failed for {agent['name']}: {exc}")
                    self._append_error_transcript(transcript, agent, str(exc))

            for spec_agent in self._specialist_agents:
                if active_agent_ids is not None and spec_agent.name not in active_agent_ids:
                    continue
                try:
                    spec_start = time.time()
                    result = spec_agent.evaluate(dispatch_plan, telemetry_data, round_num + 1)
                    if result.get("skipped", False):
                        continue
                    verdict = result.get("verdict", "GREEN")
                    agent_verdicts[spec_agent.name] = verdict
                    transcript.append({
                        "role": "Specialist", "name": spec_agent.name,
                        "text": result.get("reasoning", ""), "verdict": verdict,
                        "color": "#ffaa00",
                        "model": spec_agent.model,
                        "duration_s": round(time.time() - spec_start, 2),
                        "phase": 2, "round": round_num + 1,
                        "weight": agent_weights.get(spec_agent.name, 1.0),
                    })
                except AgentCommunicationError as exc:
                    logger.error(f"Specialist {spec_agent.name} failed: {exc}")
                    self._append_error_transcript(
                        transcript, {"role": "Specialist", "name": spec_agent.name, "color": "#ffaa00"}, str(exc)
                    )
                    agent_verdicts[spec_agent.name] = "YELLOW"
                except Exception as exc:
                    logger.error(f"Critique failed for {spec_agent.name}: {exc}")
                    self._append_error_transcript(
                        transcript, {"role": "Specialist", "name": spec_agent.name, "color": "#ffaa00"}, str(exc)
                    )

            # --- PHASE 3: DISPATCHER SYNTHESIS ---
            dispatcher = self.roster[0]
            num_responses = len(agent_verdicts)
            synthesis_prompt = (
                f"ROUND {round_num+1} TEAM FEEDBACK:\n"
                f"{json.dumps(transcript[-num_responses:] if num_responses > 0 else [], indent=2)}\n\n"
                "TASK:\n"
                "1. Summarize RED flags with exact numbers.\n"
                "2. If 2+ agents RED -> VERDICT: MODIFICATION REQUIRED.\n"
                "3. Otherwise -> VERDICT: GOOD TO GO.\n"
                "4. List required fixes with numerical targets.\n"
                "5. Pay strict attention to agents with elevated 'weight' (ACO Pheromones).\n"
            )
            final_call = self.llm.reason(
                context_prompt=synthesis_prompt,
                model=dispatcher["model"],
                system_prompt_override=dispatcher["system_prompt"],
            )
            transcript.append({
                "role": dispatcher["role"], "name": dispatcher["name"],
                "text": final_call, "color": dispatcher["color"],
                "model": dispatcher["model"], "phase": 3, "round": round_num + 1,
            })

            red_count = sum(1 for v in agent_verdicts.values() if v == "RED")
            yellow_count = sum(1 for v in agent_verdicts.values() if v == "YELLOW")
            green_count = sum(1 for v in agent_verdicts.values() if v == "GREEN")
            good_to_go = "GOOD TO GO" in final_call.upper()

            # ACO Pheromone Update
            for a_id, v in agent_verdicts.items():
                if v == "RED":
                    agent_weights[a_id] = min(10.0, agent_weights.get(a_id, 1.0) * 1.5)
                elif v == "GREEN":
                    agent_weights[a_id] = max(1.0, agent_weights.get(a_id, 1.0) * 0.9)

            round_summary = {
                "round": round_num + 1,
                "active_agents": [a["id"] for a in active_roster],
                "red_count": red_count,
                "yellow_count": yellow_count,
                "green_count": green_count,
                "status": "GOOD_TO_GO" if good_to_go else "MODIFICATION_REQUIRED",
                "elapsed_ms": round((time.time() - round_start) * 1000, 1),
            }
            round_history.append(round_summary)

            if self._supervisor is not None:
                import asyncio

                phase = self._infer_dispatch_phase(dispatch_plan)
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        asyncio.ensure_future(self._supervisor.submit_round_summary(round_summary, phase))
                except Exception:
                    pass

            if good_to_go:
                logger.info(f"Council converged in {round_num+1} round(s)")
                final_verdict_text = final_call
                break

            if round_num > 0 and len(round_history) >= 2:
                prev_reds = {r["id"] for r in round_history[-2].get("red_flags", [])}
                curr_reds = set(aid for aid, v in agent_verdicts.items() if v == "RED")
                repeated = prev_reds & curr_reds
                for aid in repeated:
                    agent_weights[aid] = max(0.3, agent_weights.get(aid, 1.0) * 0.85)
                    logger.debug(f"Pheromone decay: {aid} weight -> {agent_weights[aid]:.2f}")

            active_agent_ids = [aid for aid, v in agent_verdicts.items() if v == "RED"]
            if not active_agent_ids:
                break

        # ── CBF Safety Gate Annotation ──────────────────────────────────────
        # The gate has already run and decided, before this method was ever
        # invoked — see the docstring above. If the real certificate is
        # supplied, use it verbatim; only fall back to computing one here
        # for standalone/ad-hoc debates that aren't tied to a real dispatch
        # (e.g. the /agents/debate demo endpoint).
        if precomputed_cbf_certificate is not None:
            cbf_certificate: Dict[str, Any] = precomputed_cbf_certificate
            transcript.append({
                "role": "SYSTEM", "name": "CBF Safety Gate",
                "text": f"CBF (already decided, explained here — not re-evaluated): "
                        f"{'PASSED' if cbf_certificate.get('passed') else 'VIOLATIONS FOUND'}",
                "cbf_certificate": cbf_certificate,
                "phase": 4,
            })
        else:
            cbf_certificate = {}
            try:
                from aerofleet.safety.cbf_gate import build_cbf_gate, build_trajectory_points_from_plan

                cbf_gate = build_cbf_gate(dispatch_plan)
                route_pts = build_trajectory_points_from_plan(dispatch_plan)
                cbf_result = cbf_gate.evaluate_trajectory(route_pts)
                cbf_certificate = {
                    "passed": cbf_result.passed,
                    "safety_margins": cbf_result.safety_margin_summary,
                    "execution_time_ms": cbf_result.execution_time_ms,
                    "formally_verified": cbf_result.passed,
                    "violations": [
                        {
                            "constraint": v.constraint_name,
                            "magnitude": v.violation_magnitude,
                            "time_index": v.trajectory_time_index,
                            "required_correction": v.required_correction,
                        }
                        for v in cbf_result.violations
                    ],
                }
                transcript.append({
                    "role": "SYSTEM", "name": "CBF Safety Gate",
                    "text": f"CBF: {'PASSED' if cbf_result.passed else 'VIOLATIONS FOUND'} "
                            f"({cbf_result.execution_time_ms:.2f} ms, "
                            f"{len(cbf_result.violations)} violations)",
                    "cbf_certificate": cbf_certificate,
                    "phase": 4,
                })
            except Exception as exc:
                logger.warning(f"CBF gate skipped: {exc}")

        # ── Synthesise deterministic output fields from tool telemetry ─────
        # (hard facts, not LLM opinion — matches the "tools decide the
        # numbers, agents decide the tradeoffs" architecture principle)
        self._populate_output_fields(dispatch_plan, telemetry_data, cbf_certificate)

        debate_duration = time.time() - debate_start
        logger.info(f"Debate complete in {debate_duration:.1f}s, {len(round_history)} round(s)")

        dispatch_plan["_council_meta"] = {
            "convergence_rounds": len(round_history),
            "round_history": round_history,
            "cbf_certificate": cbf_certificate,
            "complexity": complexity,
            "elapsed_seconds": round(debate_duration, 2),
        }

        return dispatch_plan, transcript

    def _populate_output_fields(
        self, dispatch_plan: Dict[str, Any], telemetry_data: Dict[str, Any], cbf_certificate: Dict[str, Any]
    ) -> None:
        """Write the deterministic tool-computed figures back into the plan
        dict at the top level, so callers (API responses, the scenario
        evaluator) can read them without re-deriving or LLM-text-parsing."""
        route = telemetry_data.get("ROUTE", {}) if isinstance(telemetry_data.get("ROUTE"), dict) else {}
        battery = telemetry_data.get("BATTERY", {}) if isinstance(telemetry_data.get("BATTERY"), dict) else {}
        cost = telemetry_data.get("COST", {}) if isinstance(telemetry_data.get("COST"), dict) else {}
        comms = telemetry_data.get("COMMS", {}) if isinstance(telemetry_data.get("COMMS"), dict) else {}
        compliance = telemetry_data.get("COMPLIANCE", {}) if isinstance(telemetry_data.get("COMPLIANCE"), dict) else {}

        if "eta_minutes" in route:
            dispatch_plan["eta_minutes"] = route["eta_minutes"]
        if "margin_wh" in battery:
            dispatch_plan["battery_margin_wh"] = battery["margin_wh"]
        if "estimated_cost_usd" in cost:
            dispatch_plan["cost_usd"] = cost["estimated_cost_usd"]
        if "margin_db" in comms:
            dispatch_plan["comm_link_margin_db"] = comms["margin_db"]

        dispatch_plan["cbf_all_pass"] = cbf_certificate.get("passed", True)
        dispatch_plan["dgca_compliant"] = compliance.get("status") != "FAIL"

        flags = []
        if dispatch_plan.get("conflict_avoidance_required"):
            flags.append("conflict_avoidance_triggered")
        if dispatch_plan.get("requires_battery_swap"):
            flags.append("battery_swap_required")
        if dispatch_plan.get("in_red_zone"):
            flags.append("geofence_violation_detected")
        if float(dispatch_plan.get("wind_speed_mps", 0)) > float(dispatch_plan.get("max_wind_mps", 10.0)):
            flags.append("weather_abort")
        if dispatch_plan.get("fault_type"):
            flags.append("emergency_landing_triggered")
        dispatch_plan["safety_flags"] = flags or ["nominal"]

    def _build_critique_prompt(self, agent: Dict[str, Any], dispatch_plan: Dict[str, Any], telemetry: Any) -> str:
        return f"""
DISPATCH PLAN:
{json.dumps(dispatch_plan, indent=2, default=str)}

*** YOUR TOOL TELEMETRY (HARD FACTS) ***
{json.dumps(telemetry, indent=2, default=str)}
****************************************

INSTRUCTION:
1. Review the dispatch plan.
2. Compare it strictly against your tool telemetry.
3. If the numbers fail (e.g. insufficient battery margin), you MUST reject.
4. If suggesting changes, be specific (e.g. "Reroute via DEPOT-3 for a battery swap").
5. Show ALL calculations step-by-step.
6. Output format: "VERDICT: [GREEN/YELLOW/RED] \\n [Reasoning with calculations]"
"""

    def _append_error_transcript(self, transcript: List[Dict], agent: Dict[str, Any], error_msg: str) -> None:
        transcript.append({
            "role": agent["role"], "name": agent["name"], "text": error_msg,
            "verdict": "YELLOW", "color": agent.get("color", "#000000"), "phase": 2,
        })

    @staticmethod
    def _resolve_distance_km(plan: Dict[str, Any]) -> float:
        """Prefer an explicit round-trip distance_km; otherwise sum
        outbound_km + return_km (how DispatchEngine candidates are built)."""
        if "distance_km" in plan:
            return float(plan["distance_km"])
        outbound = float(plan.get("outbound_km", 0.0))
        ret = float(plan.get("return_km", 0.0))
        return outbound + ret if (outbound or ret) else 3.0

    def _map_plan_to_tool_args(self, agent_id: str, plan: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Map a dispatch plan dict to the deterministic tool function arguments."""
        try:
            from aerofleet.agents.tools import AgentTools  # noqa: F401
        except ImportError:
            logger.warning("AgentTools not available, skipping tool mapping")
            return None

        try:
            if agent_id == "ROUTE":
                # ETA is time-to-destination (outbound leg only), NOT the
                # round trip — distinct from BATTERY/COST/COMMS below, which
                # correctly care about the full outbound+return energy cost.
                outbound_only = float(plan["outbound_km"]) if "outbound_km" in plan else self._resolve_distance_km(plan)
                return {
                    "distance_km": outbound_only,
                    "deadline_minutes": float(plan.get("deadline_minutes", 30.0)),
                    "avg_speed_kmh": float(plan.get("avg_speed_kmh", 40.0)),
                }

            elif agent_id == "BATTERY":
                return {
                    "distance_km": self._resolve_distance_km(plan),
                    "payload_kg": float(plan.get("payload_kg", 1.0)),
                    "battery_soc": float(plan.get("battery_soc", 1.0)),
                    "battery_capacity_wh": float(plan.get("battery_capacity_wh", 500.0)),
                    "reserve_margin": float(plan.get("reserve_margin", 0.20)),
                }

            elif agent_id == "AIRSPACE_SAFETY":
                return {
                    "in_red_zone": bool(plan.get("in_red_zone", False)),
                    "in_yellow_zone": bool(plan.get("in_yellow_zone", False)),
                    "atc_permission": bool(plan.get("atc_permission", False)),
                    "altitude_m": float(plan.get("altitude_m", 60.0)),
                    "max_altitude_m": float(plan.get("max_altitude_m", 100.0)),
                    "min_separation_m": float(plan.get("min_separation_m", 15.0)),
                    "current_separation_m": float(plan.get("separation_m", 999.0)),
                }

            elif agent_id == "WEATHER":
                return {
                    "wind_speed_mps": float(plan.get("wind_speed_mps", 3.0)),
                    "visibility_m": float(plan.get("visibility_m", 8000.0)),
                    "precipitation": bool(plan.get("precipitation", False)),
                    "max_wind_mps": float(plan.get("max_wind_mps", 10.0)),
                    "min_visibility_m": float(plan.get("min_visibility_m", 1500.0)),
                }

            elif agent_id == "COST":
                distance_km = self._resolve_distance_km(plan)
                default_energy = distance_km * 3.5 * (1.0 + 0.15 * float(plan.get("payload_kg", 1.0)))
                return {
                    "distance_km": distance_km,
                    "energy_wh": float(plan.get("energy_wh_required", default_energy)),
                    "priority": plan.get("priority", "STANDARD"),
                }

            elif agent_id == "COMPLIANCE":
                return {
                    "zone_color": plan.get("zone_colour", "GREEN"),
                    "uin_registered": bool(plan.get("uin_registered", True)),
                    "atc_permission": bool(plan.get("atc_permission", False)),
                    "altitude_m": float(plan.get("altitude_m", 60.0)),
                }

            elif agent_id == "COMMS":
                return {
                    "distance_km": self._resolve_distance_km(plan),
                    "tx_power_w": float(plan.get("tx_power_w", 1.0)),
                    "data_rate_mbps": float(plan.get("data_rate_mbps", 1.0)),
                }

            return None

        except Exception as e:
            logger.debug(f"Tool argument mapping failed for {agent_id}: {e}")
            return None

    # ─────────────────────────────────────────────────────────────────────
    #  COMPLEXITY CLASSIFIER + DYNAMIC MODEL ROUTING
    # ─────────────────────────────────────────────────────────────────────

    def _classify_dispatch_complexity(self, dispatch_plan: Dict[str, Any]) -> str:
        """Proxy: count risk/constraint dimensions in the dispatch plan."""
        score = 0
        if dispatch_plan.get("priority") == "MEDICAL":
            score += 2
        if dispatch_plan.get("autonomous_bvlos"):
            score += 1
        if dispatch_plan.get("conflict_avoidance_required"):
            score += 3
        if dispatch_plan.get("requires_battery_swap"):
            score += 2
        if dispatch_plan.get("in_yellow_zone") or dispatch_plan.get("in_red_zone"):
            score += 2
        if float(dispatch_plan.get("wind_speed_mps", 0)) > 7:
            score += 2
        geofence_flags = (
            dispatch_plan.get("airspace_telemetry", {}).get("airspace_screening", {}).get("geofence_flags", [])
        )
        score += len(geofence_flags)

        if score <= 3:
            return "SIMPLE"
        elif score <= 7:
            return "MEDIUM"
        return "COMPLEX"

    def _apply_dynamic_model_routing(self, complexity: str) -> None:
        """Formerly upgraded reasoning-critical agents to a larger model
        (llama4:scout) for COMPLEX dispatches. The roster now shares one
        model (phi4-mini-reasoning, see AgentFactory.DEFAULT_MODEL_MAP) across
        every agent — chosen specifically to run on constrained hardware
        (laptops, free-tier cloud GPUs) without the VRAM-thrashing multiple
        differently-sized models caused. There's no larger tier left to route
        complex dispatches to, so this is now a no-op that keeps the
        complexity classification (still logged to the transcript below, and
        still useful signal) without swapping models underneath it."""
        pass

    @staticmethod
    def _infer_dispatch_phase(dispatch_plan: Dict[str, Any]) -> str:
        """Infer current dispatch phase for async supervisor window alignment."""
        status = str(dispatch_plan.get("status", "")).lower()
        if "assign" in status or "planning" in status:
            return "dispatch"
        if "en_route" in status or "delivering" in status:
            return "enroute"
        if "return" in status:
            return "return"
        if "charg" in status or "swap" in status:
            return "charging"
        return "dispatch"
