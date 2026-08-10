import json
import os

class ComponentDatabase:
    def __init__(self, project_root):
        self.db_path = os.path.join(project_root, "data", "components.json")
        self.data = self._load_data()

    def _load_data(self):
        if not os.path.exists(self.db_path):
            print(f"[WARN] Component DB not found at {self.db_path}")
            return {}
        with open(self.db_path, 'r') as f:
            return json.load(f)

    def get_category(self, category):
        """Returns a dict of parts for a category (power, propulsion, instruments)"""
        return self.data.get(category, {})

    def get_component(self, category, key):
        """Returns the specific specs for a part key"""
        return self.data.get(category, {}).get(key, None)

    def list_options(self, category):
        """Returns a list of friendly names for dropdowns"""
        parts = self.data.get(category, {})
        return [f"{k}: {v['name']}" for k, v in parts.items()]