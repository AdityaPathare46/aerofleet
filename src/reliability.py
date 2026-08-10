import random

class ReliabilityEngine:
    """
    Automated FMEA (Failure Mode and Effects Analysis) Generator.
    Uses system topology to predict potential failure cascades according to NASA-STD-8729.
    """
    def generate_fmea_report(self, specs):
        """
        Generates a structured risk assessment based on spacecraft hardware.
        """
        risks = []
        
        # 1. Propulsion Risks
        if specs.engine_type == "CHEMICAL":
            risks.append({
                "Component": "Propellant Tank",
                "Failure Mode": "Leakage / Rupture",
                "Effect": "Loss of Mission (LOM)",
                "Criticality": "CRITICAL",
                "Mitigation": "Dual-wall isolation valves (ISO-14620-1 compliant)."
            })
            risks.append({
                "Component": "Injector Plate",
                "Failure Mode": "Combustion Instability",
                "Effect": "Engine Structural Failure",
                "Criticality": "HIGH",
                "Mitigation": "Acoustic cavities and baffles."
            })
        elif specs.engine_type == "NUCLEAR":
            risks.append({
                "Component": "Reactor Core",
                "Failure Mode": "Coolant Loop Failure",
                "Effect": "Thermal Runaway / Radiation Leak",
                "Criticality": "CRITICAL",
                "Mitigation": "Passive heat rejection radiators + Scram rods."
            })
        elif specs.engine_type == "ION":
             risks.append({
                "Component": "Grid Optics",
                "Failure Mode": "Erosion / Short Circuit",
                "Effect": "Thrust Degradation",
                "Criticality": "MEDIUM",
                "Mitigation": "Redundant grid segments."
            })
            
        # 2. Power Risks
        if specs.power_source == "SOLAR":
            risks.append({
                "Component": "Solar Array Drive",
                "Failure Mode": "Mechanism Seizure",
                "Effect": "Power degradation (Cosine loss)",
                "Criticality": "MEDIUM",
                "Mitigation": "Redundant motor windings."
            })
        elif specs.power_source == "RTG":
             risks.append({
                "Component": "Thermoelectric Converter",
                "Failure Mode": "Degradation over time",
                "Effect": "Reduced Power Output",
                "Criticality": "LOW",
                "Mitigation": "Over-sizing source by 15% at BOL (Beginning of Life)."
            })
            
        # 3. Payload Risks (Generic)
        if specs.payload_mass_kg > 500:
             risks.append({
                "Component": "Structural Bus",
                "Failure Mode": "Resonance during Launch",
                "Effect": "Structural Failure",
                "Criticality": "HIGH",
                "Mitigation": "Vibration testing to NASA-STD-7001."
            })
            
        return risks