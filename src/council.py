import json
import traceback
from mission_agent import LocalMissionAgent, _resolve_model
from agent_factory import AgentFactory
from agent_tools import AgentTools

class CouncilOfExperts:
    """
    The Orchestrator of the 12-Agent Debate.
    Enforces the "Tool-First" workflow where Math > Opinion.
    """
    def __init__(self):
        self.roster = AgentFactory.get_agent_roster()
        self.llm = LocalMissionAgent() # Shared LLM backend for all agents

    def run_grand_debate(self, mission_plan, chat_history):
        """
        Executes the State Machine:
        1. Tool Execution (Get Hard Facts)
        2. Agent Critique (Opinion based on Facts)
        3. Architect Synthesis (Final Verdict)
        """
        transcript = []
        telemetry_data = {}

        # --- PHASE 1: RUN TOOLS (The Physics Check) ---
        # We run the Python tools *before* the LLM speaks to prevent hallucinations.
        transcript.append({"role": "SYSTEM", "name": "Computer", "text": "Running subsystem simulations..."})
        
        for agent in self.roster:
            if "tool_func" in agent:
                try:
                    # Map JSON data to Tool Arguments
                    args = self._map_plan_to_tool_args(agent["id"], mission_plan)
                    if args:
                        # EXECUTE TOOL
                        result = agent["tool_func"](**args)
                        telemetry_data[agent["id"]] = result
                        
                        # Add interesting findings to transcript
                        if isinstance(result, dict) and "error" in result:
                             transcript.append({"role": "SYSTEM", "name": f"{agent['name']} Tool", "text": f"⚠️ Error: {result['error']}"})
                except Exception as e:
                    print(f"Tool Error ({agent['id']}): {e}")

        # --- PHASE 2: AGENT CRITIQUES ---
        # Each agent reviews the plan + their specific tool output
        agent_verdicts = {}
        
        # We skip the Architect (Agent 1) in this round; they speak last.
        for agent in self.roster[1:]: 
            # 1. Get their Tool Data
            my_telemetry = telemetry_data.get(agent["id"], "No specific tool data available.")
            
            # 2. Build Prompt
            prompt = f"""
            SYSTEM IDENTITY:
            {agent['system_prompt']}
            
            MISSION PLAN:
            {json.dumps(mission_plan, indent=2, default=str)}
            
            *** YOUR TOOL TELEMETRY (HARD FACTS) ***
            {json.dumps(my_telemetry, indent=2, default=str)}
            ****************************************
            
            INSTRUCTION:
            1. Review the Mission Plan.
            2. Compare it strictly against your Tool Telemetry.
            3. If the math fails (e.g. not enough fuel), you MUST Reject.
            4. If suggesting changes, be specific (e.g. "Increase Delta-V to 5000m/s").
            5. Output format: "VERDICT: [GREEN/YELLOW/RED] \n [Reasoning]"
            """
            
            # 3. Call LLM — use the agent's assigned model and system prompt
            agent_model = _resolve_model(agent["id"])
            response = self.llm.reason(
                prompt,
                model=agent_model,
                system_prompt_override=agent["system_prompt"],
            )
            
            # 4. Log
            verdict = "GREEN"
            if "RED" in response.upper(): verdict = "RED"
            elif "YELLOW" in response.upper(): verdict = "YELLOW"
            
            agent_verdicts[agent["id"]] = verdict
            transcript.append({
                "role": agent["role"], 
                "name": agent["name"], 
                "text": response,
                "verdict": verdict,
                "color": agent.get("color", "#000000")
            })

        # --- PHASE 3: ARCHITECT SYNTHESIS ---
        # The Architect reviews the 11 critiques and makes the final call
        architect = self.roster[0] # Agent 1
        
        synthesis_prompt = f"""
        SYSTEM IDENTITY:
        {architect['system_prompt']}
        
        TEAM FEEDBACK:
        {json.dumps(transcript, indent=2)}
        
        TASK:
        1. Summarize the major blockers (RED flags).
        2. If 2 or more agents flagged RED, the mission is likely a NO-GO.
        3. Issue a final "VERDICT: GOOD TO GO" or "VERDICT: MODIFICATION REQUIRED".
        4. Provide a bulleted list of required fixes.
        """
        
        architect_model = _resolve_model(architect["id"])
        final_call = self.llm.reason(
            synthesis_prompt,
            model=architect_model,
            system_prompt_override=architect["system_prompt"],
        )
        
        transcript.append({
            "role": architect["role"],
            "name": architect["name"],
            "text": final_call,
            "color": architect["color"]
        })

        return mission_plan, transcript

    def _map_plan_to_tool_args(self, agent_id, plan):
        """
        Maps the massive JSON structure to the specific arguments required by 
        src/agent_tools.py functions.
        """
        try:
            config = plan.get('configuration', {})
            phys = config.get('physical', {})
            prop = config.get('propulsion', {})
            power = config.get('power', {})
            orbit = plan.get('orbit', {})
            
            if agent_id == "ORBITAL":
                return {
                    "orbit_data": orbit.get('initial', {}),
                    "target": orbit.get('target', {}).get('type', 'LEO')
                }
                
            elif agent_id == "PROPULSION":
                return {
                    "wet_mass": float(phys.get('mass_wet', 1000)),
                    "dry_mass": float(phys.get('mass_dry', 500)),
                    "isp": float(prop.get('isp', 300)),
                    "thrust": float(prop.get('thrust_max', 100))
                }
                
            elif agent_id == "SAFETY":
                # Check orbit perigee (simplified extraction)
                a = float(orbit.get('initial', {}).get('a', 6700))
                return {
                    "perigee_km": a - 6378, # Approx
                    "inclination": float(orbit.get('initial', {}).get('i', 0)),
                    "duration_yrs": float(plan.get('overview', {}).get('duration_value', 1))
                }
                
            elif agent_id == "POWER":
                return {
                    "solar_area": float(power.get('panel_area', 2.0)),
                    "efficiency": float(power.get('efficiency', 0.3)),
                    "avg_consumption_w": float(power.get('consumption_avg', 500)),
                    "eclipse_min": 35.0 # hardcoded assumption for Phase A
                }
                
            elif agent_id == "COST":
                orbit_type = orbit.get('target', {}).get('type', 'LEO') \
                             if isinstance(orbit.get('target'), dict) else str(orbit.get('target', 'LEO'))
                duration   = float(plan.get('overview', {}).get('duration_value', 2))
                risk_class = plan.get('overview', {}).get('priority', 'High')
                line_items = plan.get('cost_breakdown', {})
                return {
                    "dry_mass_kg":  float(phys.get('mass_dry', 500)),
                    "orbit_type":   orbit_type,
                    "duration_yrs": duration,
                    "risk_class":   risk_class,
                    "line_items":   line_items,
                }

            elif agent_id == "LEGAL":
                orbit_type = orbit.get('target', {}).get('type', 'LEO') \
                             if isinstance(orbit.get('target'), dict) else str(orbit.get('target', 'LEO'))
                has_nuclear = "nuclear" in str(config.get('power', {}).get('type', '')).lower()
                return {
                    "orbit_type":        orbit_type,
                    "end_of_life_plan":  plan.get('constraints', {}).get('regulatory', {}).get('debris_mitigation', ''),
                    "target_body":       orbit_type,
                    "has_nuclear":       has_nuclear,
                }
                
            return None
        except Exception as e:
            # If mapping fails (e.g. missing keys), return None so tool is skipped
            # print(f"Mapping failed for {agent_id}: {e}")
            return None