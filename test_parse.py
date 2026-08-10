import os
import sys
import json
import re
import ast

sys.path.insert(0, os.path.abspath('src'))
from mission_agent import LocalMissionAgent

agent = LocalMissionAgent(model_name="llama3.2")
user_text = "I want to design a flagship interplanetary mission called 'Europa Ice Diver'. It will be an Interplanetary Transfer mission launching on 2028-11-15. The primary target destination is Europa, Jupiter's moon. Since we are carrying a heavy ice-penetrating radar payload, the total wet mass of the spacecraft will be roughly 1850 kg, with a dry mass of around 900 kg. For power generation in the outer solar system, we will use a nuclear RTG system providing about 450 watts of continuous power. This is a Critical priority mission with a strict budget cap of 850 million dollars."

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

response = agent.reason(prompt)
print("--- RAW LLM RESPONSE ---")
print(repr(response))
print("------------------------")

cleaned_response = re.sub(r'```json\s*', '', response)
cleaned_response = re.sub(r'```', '', cleaned_response)
start = cleaned_response.find('{')
end = cleaned_response.rfind('}') + 1

if start == -1:
    print("No JSON found.")
else:
    json_str = cleaned_response[start:end]
    print("--- EXTRACTED JSON STRING ---")
    print(repr(json_str))
    print("-----------------------------")
    try:
        data = json.loads(json_str)
        print("JSON Loads Success!")
    except Exception as e:
        print(f"JSON Loads Failed: {e}")
        try:
            data = ast.literal_eval(json_str)
            print("AST Literal Eval Success!")
        except Exception as e2:
            print(f"AST Eval Failed: {e2}")

