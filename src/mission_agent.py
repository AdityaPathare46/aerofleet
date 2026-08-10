import os
import ollama
import json
from pathlib import Path
from typing import Dict, Any, Union

# Auto-load .env from the project root (parent of src/) so OLLAMA_HOST
# is always picked up regardless of working directory.
def _load_env():
    try:
        from dotenv import load_dotenv
        # Try current dir first, then parent (project root)
        for env_path in [Path(".env"), Path(__file__).parent.parent / ".env"]:
            if env_path.exists():
                load_dotenv(env_path, override=True)
                break
    except ImportError:
        pass  # python-dotenv not available; rely on shell env vars

_load_env()

try:
    from agent_interface import AgentInterface
except ImportError:
    class AgentInterface:
        pass

# ─────────────────────────────────────────────────────────────
# Per-agent model assignments — read from environment variables.
# Set AGENT_MODEL_<ID> in .env to override the defaults below.
# ─────────────────────────────────────────────────────────────
# Originally decided model assignments based on models installed on friend's PC.
# 30B models are used for reasoning-heavy roles; 8B/12B for fast math tasks.
DEFAULT_MODEL_MAP = {
    "ARCHITECT":    "qwen3:30b",           # Best reasoning for synthesis
    "ORBITAL":      "qwen3-coder:30b",     # Code + math for astrodynamics
    "PROPULSION":   "deepseek-r1:8b",      # Chain-of-thought math reasoning
    "SAFETY":       "qwen3:30b",           # Strong rule-based reasoning
    "POWER":        "deepseek-r1:8b",      # Fast math for power budgets
    "COMMS":        "gemma3:12b",          # Structured analysis, link budgets
    "GNC":          "qwen3-coder:30b",     # Code + math for navigation algos
    "COST":         "gemma3:12b",          # Structured parametric reasoning
    "OPS":          "qwen3:30b",           # Strong instruction-following
    "LEGAL":        "qwen3:30b",           # Document/rule interpretation
    "AI_VALIDATOR": "qwen3:30b",           # Meta-reasoning, cross-checks
    "SCIENCE":      "qwen3-vl:30b",        # Vision-language for instrument data
}

def _resolve_model(agent_id: str) -> str:
    """Read AGENT_MODEL_<ID> from env, fall back to DEFAULT_MODEL_MAP, then OLLAMA_MODEL."""
    env_val = os.environ.get(f"AGENT_MODEL_{agent_id}")
    if env_val:
        return env_val
    return DEFAULT_MODEL_MAP.get(agent_id, os.environ.get("OLLAMA_MODEL", "llama3.2"))


class LocalMissionAgent(AgentInterface):
    """
    Onboard AI agent using local Ollama — supports remote GPU server.
    Reads OLLAMA_HOST from environment so all requests go to the
    configured remote server (e.g. friend's PC via Tailscale).
    """

    def __init__(self, model_name: str = None):
        # Read remote host from env — defaults to localhost for dev
        self.ollama_host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")

        # Default model: read OLLAMA_MODEL from env or use llama3.2 as fallback
        self.model = model_name or os.environ.get("OLLAMA_MODEL", "llama3.2")

        # Use Client so requests go to the configured remote host
        self._client = ollama.Client(host=self.ollama_host)

        try:
            resp = self._client.list()
            raw = getattr(resp, "models", None) or resp.get("models", [])
            count = len(raw)
            print(f"[SYSTEM] Connected to Ollama at {self.ollama_host} — {count} models available")
            print(f"[SYSTEM] Default model: {self.model}")
        except Exception as e:
            print(f"[ERROR] Could not connect to Ollama at {self.ollama_host}: {e}")

    def _chat(self, model: str, messages: list, temperature: float = 0.3) -> str:
        """Core chat method using the remote client."""
        response = self._client.chat(
            model=model,
            messages=messages,
            options={"temperature": temperature, "num_predict": 4096}
        )
        # Handle both object-style and dict-style SDK responses
        if hasattr(response, "message"):
            return response.message.content
        return response["message"]["content"]

    def interpret_mission(self, user_prompt: str) -> Dict[str, Any]:
        """Interpret mission command from natural language into structured JSON."""
        system_prompt = """You are the Space Mission Architect, an autonomous spacecraft agent.
Your job is to interpret mission commands and output ONLY valid JSON.

Output Format:
{
    "mission_type": "type of mission (e.g., ORBITAL_TRANSFER, FLYBY, LANDING)",
    "origin": "origin body (e.g., EARTH, MARS)",
    "target": "destination body",
    "constraints": {
        "max_duration_days": <number>,
        "fuel_limit_kg": <number>
    }
}
"""
        try:
            content = self._chat(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Command: {user_prompt}"}
                ],
                temperature=0.1,
            )
            start = content.find("{")
            end = content.rfind("}") + 1
            return json.loads(content[start:end]) if start != -1 else {}
        except Exception as e:
            print(f"[ERROR] Agent interpretation failed: {e}")
            return {}

    def reason(
        self,
        context_prompt: Union[str, Dict],
        model: str = None,
        system_prompt_override: str = None,
    ) -> str:
        """
        Core reasoning engine. Supports per-agent model routing via the
        optional `model` parameter — passed by council.py for each agent.
        """
        if isinstance(context_prompt, dict):
            context_prompt = json.dumps(context_prompt, indent=2)

        resolved_model = model or self.model

        system_persona = system_prompt_override or (
            "You are Dr. Astra, the Chief Mission Architect at a Space Agency. "
            "Your goal is to help scientists design realistic space missions. "
            "\n\nGUIDELINES:"
            "\n1. ALWAYS provide scientific reasoning for your choices."
            "\n2. If the user's request is vague, ask clarifying questions."
            "\n3. Critique the user's design if it is unsafe or physically impossible."
            "\n4. When analyzing anomalies, be decisive and prioritize safety."
            "\n5. Be concise but technical."
            "\n6. Always show calculations and cite the formula used."
        )

        try:
            return self._chat(
                model=resolved_model,
                messages=[
                    {"role": "system", "content": system_persona},
                    {"role": "user", "content": context_prompt}
                ],
            )
        except Exception as e:
            return f"[SYSTEM ERROR] AI Reasoning Module Offline: {e}"

    def analyze_anomaly(self, anomaly_description: str, telemetry: Dict[str, Any]) -> Dict[str, str]:
        """Analyze spacecraft anomaly and recommend action."""
        context = (
            f"CRITICAL ALERT: {anomaly_description}\n\n"
            f"Current Telemetry:\n{json.dumps(telemetry, indent=2)}\n\n"
            "Recommend immediate action: CONTINUE, SAFE_MODE, or ABORT. "
            "Provide detailed reasoning with calculations."
        )
        response = self.reason(context)
        action = "SAFE_MODE"
        if "CONTINUE" in response.upper():
            action = "CONTINUE"
        elif "ABORT" in response.upper():
            action = "ABORT"
        return {"action": action, "reasoning": response}

    def plan_trajectory(self, origin: str, target: str, constraints: Dict[str, Any]):
        print(f"[PLANNER] Calculating transfer from {origin} to {target}...")
        return "Trajectory calculation pending TrajectoryEngine execution."


# --- TESTING BLOCK ---
if __name__ == "__main__":
    agent = LocalMissionAgent()
    print("\n[TEST] Testing Scientist Persona...")
    response = agent.reason("I want to send a solar powered probe to Pluto.")
    print(f"[AGENT]: {response}")