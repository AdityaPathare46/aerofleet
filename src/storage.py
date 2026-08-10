import json
import os
from datetime import datetime

class MissionStorage:
    def __init__(self, save_dir="saved_missions"):
        # Create a folder to store mission files if it doesn't exist
        self.save_dir = save_dir
        if not os.path.exists(self.save_dir):
            os.makedirs(self.save_dir)

    def save_mission(self, mission_name, sim, mrd_summary, chat_history):
        """
        Saves the entire state of the mission to a JSON file.
        """
        # 1. Create a dictionary of all critical data
        data = {
            "meta": {
                "name": mission_name,
                "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "stage": "APPROVED" # If saving, we assume it's a valid design
            },
            "specs": sim.specs.__dict__, # The hardware configuration
            "mission_plan": sim.mission_plan, # The trajectory calculation
            "mrd_summary": mrd_summary, # The generated document
            "chat_history": chat_history # The conversation log
        }

        # 2. Sanitize filename (remove bad characters)
        safe_name = "".join([c for c in mission_name if c.isalnum() or c in (' ','-','_')]).strip()
        filename = f"{safe_name}.json"
        filepath = os.path.join(self.save_dir, filename)

        # 3. Write to file
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=4, default=str)
        
        return filename

    def list_saves(self):
        """Returns a list of all saved mission names."""
        if not os.path.exists(self.save_dir):
            return []
        files = [f for f in os.listdir(self.save_dir) if f.endswith('.json')]
        # Remove .json extension for display
        return [f.replace('.json', '') for f in files]

    def load_mission(self, mission_name, sim):
        """
        Loads data from file and injects it back into the Simulation object.
        """
        filepath = os.path.join(self.save_dir, f"{mission_name}.json")
        
        if not os.path.exists(filepath):
            return None, None, None

        with open(filepath, 'r') as f:
            data = json.load(f)

        # INJECT DATA BACK INTO SIMULATION
        # 1. Update Hardware Specs
        if "specs" in data:
            sim.specs.__dict__.update(data["specs"])
            # Re-run internal logic to sync derived values (like wet mass)
            sim.recalculate_budgets() 

        # 2. Update Flight Plan
        if "mission_plan" in data:
            sim.mission_plan = data["mission_plan"]
            if sim.mission_plan:
                sim.mission_status = "READY_TO_LAUNCH"

        return data["mrd_summary"], data["chat_history"], data["meta"]