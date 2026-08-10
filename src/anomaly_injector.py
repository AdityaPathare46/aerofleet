import random

class AnomalyInjector:
    def __init__(self):
        self.active_anomalies = []
        
    def check_for_anomaly(self, current_mission_time_days):
        """
        Simulates random failures based on mission duration.
        Returns a dict describing the anomaly, or None if nominal.
        """
        # 10% chance of anomaly every time we check
        if random.random() < 0.10: 
            anomaly_type = random.choice(["THRUSTER_DEGRADATION", "COLLISION_ALERT", "SOLAR_FLARE"])
            
            if anomaly_type == "THRUSTER_DEGRADATION":
                return {
                    "type": "THRUSTER_DEGRADATION",
                    "severity": "CRITICAL",
                    "description": "Main Engine Chamber Pressure Drop. Efficiency down 25%.",
                    "impact": {"thrust_reduction": 0.25, "fuel_burn_rate_increase": 0.1}
                }
            
            elif anomaly_type == "COLLISION_ALERT":
                return {
                    "type": "COLLISION_ALERT",
                    "severity": "HIGH",
                    "description": "Debris Conjunction Detected. Time to Impact: 48 hours.",
                    "impact": {"must_maneuver": True, "keep_out_radius_km": 50}
                }
                
            elif anomaly_type == "SOLAR_FLARE":
                return {
                    "type": "SOLAR_FLARE",
                    "severity": "MODERATE",
                    "description": "X-Class Solar Flare imminent. High Radiation Levels.",
                    "impact": {"safe_mode_required": True, "communication_blackout": True}
                }
        
        return None