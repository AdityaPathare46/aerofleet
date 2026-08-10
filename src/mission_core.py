import os
import json
import math
import pandas as pd
import numpy as np
import re
import ast
from datetime import datetime, timedelta

# --- SUBSYSTEM IMPORTS ---
from data_loader import MissionDataLoader
from mission_agent import LocalMissionAgent
from trajectory_engine import TrajectoryEngine
from optimizer import MissionOptimizer
from physics_tools import PhysicsTools
from anomaly_injector import AnomalyInjector
from components_db import ComponentDatabase

try:
    from aerofleet.agents.council import CouncilOfExperts
    COUNCIL_AVAILABLE = True
except ImportError:
    COUNCIL_AVAILABLE = False

from reliability import ReliabilityEngine
from rl_optimizer import RLOptimizer

class SpacecraftSpecs:
    """
    The Master Data Structure for the Comprehensive Mission Specification Form.
    Implements the 11-Section structure defined in the requirements.
    """
    def __init__(self):
        # SECTION 1: MISSION OVERVIEW
        self.overview = {
            "name": "New Mission",
            "type": "Single Satellite Mission", # Dropdown options
            "priority": "High",
            "description": "",
            "duration_value": 5.0,
            "duration_unit": "Years",
            "launch_date": datetime.now() + timedelta(days=365),
            "end_date": None,
            "objectives": {
                "primary": "",
                "secondary": [],
                "success_criteria": ""
            }
        }

        # SECTION 2: SPACECRAFT CONFIGURATION
        self.configuration = {
            "physical": {
                "number_of_spacecraft": 1,
                "mass_dry": 500.0,
                "mass_wet": 1000.0,
                "payload_mass": 100.0,
                "dimensions": {"L": 2.0, "W": 2.0, "H": 3.0, "Area": 4.0},
                "drag_coeff": 2.2,
                "reflectivity": 1.3
            },
            "propulsion": {
                "type": "Chemical (Bipropellant)",
                "propellant_mass": 500.0,
                "isp": 320.0,
                "thrust_max": 400.0,
                "thrust_min": 0.0,
                "vectoring": False,
                "thruster_count": 4,
                "config": "4-way"
            },
            "power": {
                "type": "Solar Panels",
                "generation_w": 1500.0,
                "battery_wh": 2000.0,
                "panel_area": 4.0,
                "efficiency": 0.30,
                "consumption_avg": 500.0,
                "consumption_peak": 800.0
            },
            "acs": {
                "type": "3-Axis Stabilized",
                "pointing_accuracy": 0.1,
                "slew_rate": 3.0,
                "momentum_storage": 10.0
            },
            "comms": {
                "bands": ["X-band"],
                "data_rate_mbps": 10.0,
                "antenna_type": "Directional",
                "ground_stations": ["Global DSN"],
                "windows_per_day": 2,
                "latency_limit": 60
            },
            "sensors": {
                "navigation": ["Star Tracker", "IMU"],
                "payload_type": ["Optical Camera"],
                "payload_power": 50.0,
                "duty_cycle": 100.0
            }
        }

        # SECTION 3: ORBITAL PARAMETERS
        self.orbit = {
            "initial": {
                "method": "Keplerian Elements",
                "a": 6771.0, "e": 0.0, "i": 28.5, "raan": 0.0, "arg_p": 0.0, "nu": 0.0,
                "tle_line1": "", "tle_line2": ""
            },
            "target": {
                "method": "Orbit Type",
                "type": "GEO", # Destination
                "description": "Geostationary Orbit",
                "arrival_body": "Earth"
            },
            "waypoints": [] # List of {name, params, time_constraint}
        }

        # SECTION 4: MISSION CONSTRAINTS
        self.constraints = {
            "trajectory": {
                "max_delta_v": 5000.0,
                "max_duration_days": 3650,
                "min_duration_days": 30,
                "maneuver_type": "Hybrid",
                "transfer_type": "Hohmann"
            },
            "safety": {
                "min_altitude_km": 300.0,
                "max_altitude_km": 100000.0,
                "collision_avoidance": True,
                "radiation_limit": "Minimize Exposure"
            },
            "operational": {
                "ground_contact_required": True,
                "sun_exclusion_angle": 30.0,
                "thermal_min": -20,
                "thermal_max": 60
            },
            "regulatory": {
                "license": "",
                "debris_mitigation": "25-Year Deorbit Required"
            }
        }

        # SECTION 5: ENVIRONMENTAL CONDITIONS
        self.environment = {
            "space_weather": {
                "solar_activity": "Average",
                "kp_index": "Use Real-Time",
                "f10_7": "Use Real-Time"
            },
            "perturbations": {
                "drag_model": "NRLMSISE-00",
                "j2": True,
                "higher_order_gravity": False,
                "solar_pressure": True,
                "third_body": ["Moon", "Sun"]
            },
            "debris": {
                "track": True,
                "database": "Latest Space-Track"
            }
        }

        # SECTION 6: OPTIMIZATION PREFERENCES
        self.optimization = {
            "goal": "Balanced", # Min Fuel, Min Time, Risk, Custom
            "custom_weights": {"fuel": 33, "time": 33, "safety": 34},
            "planning": {
                "horizon_days": 30,
                "replanning_freq": 24,
                "autonomy_level": "Standard" # Minimal, Standard, Detailed
            },
            "ai_settings": {
                "reasoning": "Standard",
                "format": "Both"
            }
        }

        # SECTION 7: TARGETS & OBJECTIVES
        self.targets = {
            "definitions": {
                "type": "Satellite",
                "id": "ISS",
                "geometry": "Direct Rendezvous",
                "approach_speed": 0.1
            },
            "multi_target": {
                "count": 1,
                "sequence": []
            },
            "ground_track": {
                "coverage": "Global"
            }
        }

        # SECTION 8: CONTINGENCY & FAILURE MODES
        self.contingency = {
            "responses": {
                "sensor_fail": "Switch to Backup",
                "prop_degrade": "Replan with Reduced Thrust",
                "power_fail": "Safe Mode",
                "comm_loss": 24 # hours
            },
            "abort": {
                "triggers": ["Fuel Below 5%", "Critical System Failure"],
                "destination": "Safe Parking Orbit"
            }
        }

        # SECTION 9: SIMULATION & ANALYSIS
        self.simulation = {
            "params": {
                "step_size": 60,
                "integrator": "RK45",
                "monte_carlo": False
            },
            "outputs": ["Timeline", "Delta-V Budget", "3D Visualisation"]
        }

        # SECTION 10: ADVANCED OPTIONS
        self.advanced = {
            "expert": {
                "custom_propagator": False,
                "force_trajectory": ""
            },
            "formation": {
                "type": "None",
                "inter_sat_link": False
            },
            "interplanetary": {
                "departure_body": "Earth",
                "arrival_body": "Mars",
                "flybys": [],
                "use_gravity_assist": True
            }
        }

        # SECTION 11: FINANCIALS & SUBMISSION (Calculated/Output)
        self.financials = {
            "budget_cap_m": 500.0,
            "cost_estimate_m": 0.0,
            "is_feasible": False
        }

        # SECTION 2B: SPACECRAFT ARCHITECTURE (populated by dashboard)
        self.architecture = {
            "bus_form_factor": "Medium Platform (600–2000 kg)",
            "primary_structure_material": "Aluminium 6061-T6",
            "launch_adapter": "ESPA Standard",
            "tcs_passive": ["MLI Blankets", "Radiator Panels"],
            "tcs_active": ["Heaters"],
            "heater_power_w": 50.0,
            "temp_op_min": -20.0,
            "temp_op_max": 60.0,
            "temp_sur_min": -40.0,
            "temp_sur_max": 85.0,
            "rw_torque_nm": 20.0,
            "rw_momentum_nms": 4.0,
            "mtq_dipole": 5.0,
            "star_tracker_accuracy_arcsec": 5.0,
            "imu_drift_deg_hr": 0.1,
            "pointing_modes": ["Nadir-Pointing", "Sun-Tracking"],
            "obc_type": "LEON4FT (GR740)",
            "storage_gb": 64.0,
            "redundancy": "Cold Spare",
            "data_compression": "Lossless (CCSDS 123)",
            "tx_power_w": 5.0,
            "tx_gain_dbi": 6.0,
            "gs_gain_dbi": 40.0,
            "gs_noise_k": 135.0,
        }

    # --- COMPATIBILITY PROPERTIES (Legacy Bridge) ---
    @property
    def name(self): return self.overview['name']
    @name.setter
    def name(self, val): self.overview['name'] = val
    
    @property
    def target(self): 
        # Resolves target for legacy engines
        if self.overview['type'] == "Interplanetary Transfer":
            return self.advanced['interplanetary']['arrival_body']
        # Helper for Orbit Type dropdown
        return self.orbit['target'].get('type', 'Unknown')
    @target.setter
    def target(self, val): 
        self.orbit['target']['type'] = val
        self.advanced['interplanetary']['arrival_body'] = val

    @property
    def risk_class(self):
        # Map Priority to Risk Class
        prio = self.overview.get('priority', 'High')
        if prio == "Critical": return "CLASS_A (Flagship)"
        if prio == "High": return "CLASS_B (Discovery)"
        if prio == "Medium": return "CLASS_C (Scout)"
        return "CLASS_D (CubeSat)"
    @risk_class.setter
    def risk_class(self, val):
        # Reverse map for setting
        if "CLASS_A" in val: self.overview['priority'] = "Critical"
        elif "CLASS_B" in val: self.overview['priority'] = "High"
        elif "CLASS_C" in val: self.overview['priority'] = "Medium"
        else: self.overview['priority'] = "Low"

    @property
    def total_wet_mass(self): return self.configuration['physical']['mass_wet']
    @property
    def dry_mass_kg(self): return self.configuration['physical']['mass_dry']
    @property
    def engine_type(self): return self.configuration['propulsion']['type']
    @property
    def power_source(self): return self.configuration['power']['type']
    
    @property
    def payload_mass_kg(self): return self.configuration['physical']['payload_mass']
    @payload_mass_kg.setter
    def payload_mass_kg(self, val): self.configuration['physical']['payload_mass'] = val

    @property
    def launch_year(self): return self.overview['launch_date'].year
    
    @property
    def budget_cap_m(self): return self.financials['budget_cap_m']
    @budget_cap_m.setter
    def budget_cap_m(self, val): self.financials['budget_cap_m'] = val
    
    @property
    def cost_estimate_m(self): return self.financials['cost_estimate_m']
    @cost_estimate_m.setter
    def cost_estimate_m(self, val): self.financials['cost_estimate_m'] = val


class MissionSimulation:
    def __init__(self):
        current_script_path = os.path.abspath(__file__)
        project_root = os.path.dirname(os.path.dirname(current_script_path))
        
        self.loader = MissionDataLoader(project_root)
        self.loader.load_spice_kernels()
        self.component_db = ComponentDatabase(project_root)
        
        self.trajectory_engine = TrajectoryEngine(self.loader)
        self.optimizer = MissionOptimizer(self.trajectory_engine)
        self.agent = LocalMissionAgent(model_name="llama3.2")
        self.physics = PhysicsTools()
        self.chaos = AnomalyInjector()
        
        self.rag = None
        try:
            from knowledge_base import MissionKnowledgeBase
            self.rag = MissionKnowledgeBase(project_root)
            print("[SYSTEM] RAG Knowledge Base online.")
        except: pass
        
        self.safety = ReliabilityEngine()
        self.rl_brain = RLOptimizer()
        
        if COUNCIL_AVAILABLE:
            self.council = CouncilOfExperts()
        else:
            self.council = None
        
        self.specs = SpacecraftSpecs()
        self.mission_plan = None
        self.mission_status = "CONCEPT_PHASE"
        self.current_time = datetime.now()
        self.logs = []
        self.chat_history = [] 

    def recalculate_budgets(self):
        """
        Updates financials using a clearer heuristic for deep space missions.
        Ensures cost estimates are more realistic (higher) for interplanetary targets.
        All outputs are validated as finite floats to prevent UI crashes.
        """
        try:
            dry_mass     = float(self.specs.configuration['physical']['mass_dry'])
            payload_mass = float(self.specs.configuration['physical']['payload_mass'])

            # 1. Hardware Cost Logic
            hw_cost = (dry_mass * 0.25) + (payload_mass * 0.5)

            # 2. Complexity Multipliers
            m_type = self.specs.overview['type']
            if "Interplanetary" in m_type:
                hw_cost *= 3.0
            elif "Constellation" in m_type:
                hw_cost *= 1.5

            p_type = self.specs.configuration['power']['type']
            if "Nuclear" in p_type:
                hw_cost += 150.0

            # 3. Operations & Launch Cost
            duration   = float(self.specs.overview['duration_value'])
            ops_cost   = duration * 12.0
            launch_cost = 80.0

            total = hw_cost + ops_cost + launch_cost

            # Guard: clamp & validate
            if not math.isfinite(total) or total < 0:
                total = 0.0
            total = min(total, 1_000_000.0)   # hard cap at $1T equivalent

            self.specs.financials['cost_estimate_m'] = round(total, 2)
            try:
                self.specs.cost_estimate_m = round(total, 2)
            except Exception:
                pass

            # Also guard budget_cap_m
            try:
                cap = float(self.specs.financials.get('budget_cap_m', 500.0))
                if not math.isfinite(cap) or cap < 0:
                    cap = 500.0
                self.specs.financials['budget_cap_m'] = min(cap, 50_000.0)
            except Exception:
                self.specs.financials['budget_cap_m'] = 500.0

        except Exception as e:
            # Failsafe: set sane defaults so UI never crashes
            self.specs.financials['cost_estimate_m'] = 0.0
            self.specs.financials['budget_cap_m']    = 500.0

    def parse_natural_language_mission(self, user_text):
        """
        Robustly parses LLM output by asking for a FLAT JSON and mapping it manually.
        This fixes the nesting issues where data was lost.
        """
        # Ask for a FLAT structure (easier for LLM)
        flat_skeleton = {
            "mission_name": "string",
            "mission_type": "string",
            "launch_date": "YYYY-MM-DD",
            "wet_mass_kg": 0.0,
            "dry_mass_kg": 0.0,
            "power_watts": 0.0,
            "target_body": "string",
            "budget_cap_m": 0.0,
            "priority": "High"
        }
        
        prompt = f"""
        You are a Systems Engineering Parsing Agent.
        USER REQUEST: "{user_text}"
        
        TASK: Extract technical parameters into this EXACT JSON structure:
        {json.dumps(flat_skeleton, indent=2)}
        
        RULES: 
        1. Return ONLY valid JSON. No markdown.
        2. Format date as YYYY-MM-DD.
        3. If value is missing, infer a reasonable default.
        4. "wet_mass_kg" includes fuel. "dry_mass_kg" is without fuel.
        """
        
        response = self.agent.reason(prompt)
        print(f"\\n[DEBUG AI AUTO-FILL] RAW RESPONSE FROM LLM:\\n{response}\\n----------------------\\n")
        
        try:
            # Clean response
            cleaned_response = re.sub(r'```json\s*', '', response)
            cleaned_response = re.sub(r'```', '', cleaned_response)
            start = cleaned_response.find('{')
            end = cleaned_response.rfind('}')
            
            if start == -1: return False, f"No JSON found in response. RAW RESPONSE: {response}"
            
            # If the LLM forgot the closing brace, take the rest of the string and append a brace
            if end == -1 or end < start:
                json_str = cleaned_response[start:] + "}"
            else:
                json_str = cleaned_response[start:end+1]
            
            # Parse
            try:
                data = json.loads(json_str)
            except Exception as e1:
                # Fallback for single quotes or Python literals
                try:
                    # Convert JS booleans/null to Python
                    py_str = json_str.replace("true", "True").replace("false", "False").replace("null", "None")
                    data = ast.literal_eval(py_str)
                except Exception as e2:
                    return False, f"Parsing failed.\\n\\nRAW LLM RESPONSE:\\n{response}\\n\\nJSON String Attempted:\\n{json_str}"

            # --- EXPLICIT MAPPING (Fixes Auto-Fill) ---
            # 1. Overview
            if 'mission_name' in data: self.specs.overview['name'] = data['mission_name']
            if 'mission_type' in data: self.specs.overview['type'] = data['mission_type']
            if 'priority' in data: self.specs.overview['priority'] = data['priority']
            
            # 2. Date Parsing (Fixes Date Crash)
            if 'launch_date' in data:
                try:
                    dt = datetime.strptime(data['launch_date'], "%Y-%m-%d")
                    self.specs.overview['launch_date'] = dt
                except:
                    pass # Keep default if parse fails

            # 3. Configuration & Power (Fixes Power/Mass Update)
            if 'wet_mass_kg' in data: 
                self.specs.configuration['physical']['mass_wet'] = float(data['wet_mass_kg'])
            if 'dry_mass_kg' in data and data['dry_mass_kg'] > 0:
                self.specs.configuration['physical']['mass_dry'] = float(data['dry_mass_kg'])
            elif 'wet_mass_kg' in data:
                 # Fallback if dry mass not provided
                 self.specs.configuration['physical']['mass_dry'] = float(data['wet_mass_kg']) * 0.4
                
            if 'power_watts' in data:
                self.specs.configuration['power']['generation_w'] = float(data['power_watts'])

            # 4. Target
            if 'target_body' in data:
                self.specs.orbit['target']['type'] = data['target_body']
                # Sync logic for legacy fields
                if data['target_body'] in ["Mars", "Venus", "Jupiter", "Saturn", "Europa"]:
                    self.specs.advanced['interplanetary']['arrival_body'] = data['target_body']

            # 5. Financials (Fixes Budget Cap Update)
            if 'budget_cap_m' in data:
                val = float(data['budget_cap_m'])
                self.specs.financials['budget_cap_m'] = val
                self.specs.budget_cap_m = val # Update property wrapper too

            # Trigger Recalc with new data
            self.recalculate_budgets()
            return True, "Mission parameters mapped successfully."
            
        except Exception as e:
            return False, f"Parsing failed: {e}"

    def review_section(self, section_name, section_data):
        if not self.council: return "ERROR", "Council not loaded."

        background_context = f"Mission: {self.specs.overview['name']}, Type: {self.specs.overview['type']}"
        if section_name == "ORBIT":
            background_context += f", Target: {self.specs.orbit['target']['type']}"
        elif section_name == "CONFIG":
            background_context += f", Power: {self.specs.configuration['power']['type']}"

        context_prompt = f"""
        
        REVIEW FOCUS: {section_name.upper()}
        DATA PROVIDED: {json.dumps(section_data, default=str)}
        BACKGROUND CONTEXT: {background_context}
        
        TASK: Critique logic & physics. Check for errors.
        Assess if the user would understand the response better with the use of diagrams and trigger them. 
        You can insert a diagram by adding the 

[Image of X]
 tag where X is a contextually relevant and domain-specific query to fetch the diagram.
        
        OUTPUT: Start with 'VERDICT: GOOD TO GO' or 'VERDICT: MODIFICATION REQUIRED'.
        """
        
        fake_history = [{"role": "user", "content": context_prompt}]
        _, transcript = self.council.run_grand_debate(self.specs.__dict__, fake_history)
        
        final_verdict = "VERDICT: GOOD TO GO"
        for t in reversed(transcript):
            if "VERDICT:" in t['text']:
                if "MODIFICATION" in t['text']: final_verdict = "VERDICT: MODIFICATION REQUIRED"
                break
        return final_verdict, transcript

    # Stub methods
    def generate_flight_plan(self, target, launch_date):
        self.mission_plan = {
            "launch_date": launch_date,
            "arrival_date": launch_date + timedelta(days=200),
            "estimated_delta_v_km_s": 5.6,
            "target": target
        }
        self.mission_status = "READY_TO_LAUNCH"
        return True

    def get_trajectory_points(self):
        if not self.mission_plan: return None, np.array([0,0,0]), np.array([0,0,0])
        r1 = self.loader.get_planet_position("EARTH", "SUN", self.mission_plan['launch_date'])
        target = str(self.mission_plan.get('target', 'Mars')).upper()
        spice_map = {"MARS": "MARS BARYCENTER", "JUPITER": "JUPITER BARYCENTER"}
        target_spice = spice_map.get(target, target)
        r2 = self.loader.get_planet_position(target_spice, "SUN", self.mission_plan['arrival_date'])
        
        dt = (pd.Timestamp(self.mission_plan['arrival_date']) - pd.Timestamp(self.mission_plan['launch_date'])).total_seconds()
        v1, _ = self.trajectory_engine.solve_lambert(np.array(r1), np.array(r2), dt)
        
        times = np.linspace(0, dt, 100)
        points = []
        curr_r = np.array(r1)
        curr_v = v1
        dt_step = times[1] - times[0]
        
        for _ in times:
            points.append(curr_r.copy())
            r_mag = np.linalg.norm(curr_r)
            acc = -1.327e11 * curr_r / r_mag**3
            curr_v += acc * dt_step
            curr_r += curr_v * dt_step
            
        return np.array(points), np.array(r1), np.array(r2)

    def estimate_build_timeline(self): return 36, datetime.now() + timedelta(days=1000)
    def step_simulation(self): return None
    
    def consult_architect(self, user_input):
        prompt = f"""
        Context: {json.dumps(self.specs.__dict__, default=str)}
        User Question: {user_input}
        Answer briefly. Assess if the user would understand the response better with the use of diagrams and trigger them.
        You can insert a diagram by adding the 

[Image of X]
 tag where X is a contextually relevant query.
        """
        return self.agent.reason(prompt)

    def get_component_advice(self, topic, context):
        expert_role = "Systems Engineer"
        rag_info = ""
        if self.rag:
            try: rag_info = self.rag.retrieve_context(f"advantages of different {topic.lower()} systems")
            except: pass

        prompt = f"""
        You are the {expert_role}.
        CONTEXT: {json.dumps(context, default=str)}
        Topic: {topic}. RELEVANT DOCS: {rag_info}
        TASK: Compare options. Include tags like  if instructive.
        """
        return self.agent.reason(prompt)

    def log(self, msg, type_="INFO"): self.logs.append({"msg": msg})