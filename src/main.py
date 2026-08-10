import os
import json
import time
import pandas as pd
import numpy as np

from data_loader import MissionDataLoader
from mission_agent import LocalMissionAgent
from trajectory_engine import TrajectoryEngine
from visualization import plot_mission_3d
from optimizer import MissionOptimizer
from physics_tools import PhysicsTools
from anomaly_injector import AnomalyInjector # <--- NEW MODULE

def run_mission_architect():
    print("============================================================")
    print("   SPACE MISSION ARCHITECT - PHASE III (REAL-TIME AUTONOMY)")
    print("============================================================")

    # 1. INITIALIZATION
    current_script_path = os.path.abspath(__file__)
    project_root = os.path.dirname(os.path.dirname(current_script_path))
    
    loader = MissionDataLoader(project_root)
    loader.load_spice_kernels()
    
    trajectory_engine = TrajectoryEngine(loader)
    optimizer = MissionOptimizer(trajectory_engine)
    agent = LocalMissionAgent(model_name="llama3.2")
    physics = PhysicsTools()
    chaos_engine = AnomalyInjector() # <--- INIT CHAOS
    
    # 2. INITIAL PLANNING PHASE
    print("\n[MISSION CONTROL] Please define the mission parameters.")
    user_command = input("COMMAND > ")
    
    print("\n[AGENT] Generating Initial Strategy...")
    mission_params = agent.interpret_mission(user_command)
    
    origin = mission_params.get("origin", "EARTH")
    target = mission_params.get("target", "MARS")
    
    print(f"[PLANNER] Optimizing Trajectory for {origin} -> {target}...")
    # Quick search for demo purposes
    best_mission = optimizer.find_optimal_launch_window(origin, target, "2020-01-01", "2022-01-01")
    
    if not best_mission:
        print("[ERROR] No trajectory found. Aborting.")
        return

    print(f"[SUCCESS] Launch set for {best_mission['launch_date']}. Delta-V: {best_mission['estimated_delta_v_km_s']:.2f} km/s")
    
    # ... (previous code remains the same) ...

    # 3. MISSION EXECUTION LOOP (CLOSED-LOOP CONTROL)
    print("\n" + "="*30)
    print("   INITIATING MISSION SIMULATION")
    print("="*30)
    
    mission_duration_days = 200 
    current_day = 0
    mission_status = "NOMINAL"
    velocity_factor = 1.0 # 1.0 = Full Speed, 0.0 = Stop
    
    while current_day < mission_duration_days:
        time.sleep(0.5) 
        
        # Advance time based on current velocity (Simulating impact of Safe Mode)
        day_step = 10 * velocity_factor
        current_day += day_step
        
        print(f"[T+{current_day:.1f} DAYS] Status: {mission_status} | Speed: {velocity_factor*100:.0f}% | Distance: {current_day * 25000:.0f} km")
        
        # CHECK FOR ANOMALIES
        anomaly = chaos_engine.check_for_anomaly(current_day)
        
        if anomaly:
            print("\n" + "!"*50)
            print(f" [ALERT] ANOMALY DETECTED: {anomaly['type']}")
            print(f" [DIAGNOSTIC] {anomaly['description']}")
            print("!"*50)
            
            # TRIGGER AGENTIC REPLANNING (With Structured Output)
            print("\n[AGENT] Analyzing Telemetry...")
            
            context_prompt = (
                f"CRITICAL ALERT: Mission Day {current_day:.1f}.\n"
                f"Anomaly: {anomaly['description']}\n"
                f"Impact: {anomaly['impact']}\n"
                "COMMAND REQUIRED: You must select one ACTION from: [CONTINUE, SAFE_MODE, ABORT].\n"
                "Output Format: JSON only. Example: {\"action\": \"SAFE_MODE\", \"reason\": \"Radiation risk high.\"}"
            )
            
            # Get Agent Response
            try:
                response_text = agent.reason(context_prompt)
                # Quick hack to find JSON if LLM adds extra text
                start = response_text.find('{')
                end = response_text.rfind('}') + 1
                command_data = json.loads(response_text[start:end])
                
                action = command_data.get("action", "CONTINUE")
                reason = command_data.get("reason", "No reason provided.")
                
                print(f"[AGENT DECISION] {action}")
                print(f"[AGENT REASONING] {reason}")
                
                # --- CLOSED LOOP CONTROL LOGIC ---
                # The Python script actually changes the ship's physics based on the AI
                
                if action == "SAFE_MODE":
                    print("[SYSTEM] ENGAGING SAFE MODE. THROTTLING DOWN SYSTEMS.")
                    mission_status = "SAFE_MODE"
                    velocity_factor = 0.5 # Ship slows down to 50% speed to save power/fuel
                    
                elif action == "ABORT":
                    print("[SYSTEM] ABORT SEQUENCE INITIATED. RETURNING TO EARTH.")
                    break # End Simulation
                    
                elif action == "CONTINUE":
                    print("[SYSTEM] OVERRIDING ALERT. CONTINUING MISSION.")
                    mission_status = "WARNING"
                    
            except Exception as e:
                print(f"[ERROR] Agent command malformed. Defaulting to Safe Mode. ({e})")
                velocity_factor = 0.5

            input("\n[PRESS ENTER TO PROCEED]...")
            
            # If we were in Safe Mode, maybe we recover after a while?
            # For this demo, we assume the anomaly passes after one cycle
            if mission_status == "SAFE_MODE":
                print("[SYSTEM] Anomaly cleared. Resuming nominal cruise.")
                mission_status = "NOMINAL"
                velocity_factor = 1.0

    if current_day >= mission_duration_days:
        print("\n[MISSION CONTROL] Arrival at Target. Mission Successful.")
    
    # Final Plot
    print("\n[SYSTEM] Generating Trajectory Log...")
    # (Plotting code remains the same, called at end)
    # We can skip the plot call here to focus on the text output for this test

if __name__ == "__main__":
    run_mission_architect()