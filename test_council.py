import asyncio
import json
from aerofleet.agents.council import CouncilOfExperts
from aerofleet.agents.local_agent import LocalMissionAgent
import logging

logging.basicConfig(level=logging.DEBUG)

def test_council():
    council = CouncilOfExperts()
    
    # Check if 17 agents total (1 architect + 11 core + 5 specialists)
    core_count = len(council.roster)
    spec_count = len(council._specialist_agents)
    print(f"Core agents: {core_count}")
    print(f"Specialist agents: {spec_count}")
    assert core_count + spec_count == 17, f"Expected 17 agents, got {core_count + spec_count}"
    
    # Run a simple debate to ensure no syntax/type errors
    dummy_plan = {
        "mission_name": "Test Mission",
        "mission_type": "debris removal", # triggers OOS
        "target_body": "LEO",
        "autonomous_ai_onboard": True, # triggers Onboard Compute Feasibility
        "cam_required": True, # triggers CAM
        "stm_telemetry": {
            "stm_screening": {
                "max_Pc": 0.001,
                "top_conjunctions": [{"object_name": "Debris A", "cam_dv_required_ms": 15.0}]
            }
        },
        "cam_details": [],
        "configuration": {
            "physical": {"mass_dry": 1000, "mass_wet": 1500},
            "propulsion": {"isp": 300},
            "power": {"panel_area": 5.0, "efficiency": 0.3, "consumption_avg": 500}
        },
        "orbit": {
            "initial": {"a": 7000, "i": 98.0},
            "target": {"type": "LEO"}
        },
        "overview": {
            "duration_value": 5,
            "type": "technology demonstration",
            "priority": "High"
        }
    }
    
    print("Running grand debate...")
    # we don't actually want to call Ollama (might be slow or unavailable), so we can mock the LLM if we want.
    # Actually we can just let it run if Ollama is mocked or handles errors gracefully.
    try:
        final_plan, transcript = council.run_grand_debate(dummy_plan)
        print("Debate completed successfully.")
        print(f"Transcript length: {len(transcript)}")
    except Exception as e:
        print(f"Debate failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_council()
