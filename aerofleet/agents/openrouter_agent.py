"""OpenRouter-backed mission agent — the "API" connection mode.

Implements the exact same duck-typed interface as LocalMissionAgent /
MockLLMBackend (interpret_mission, reason, analyze_anomaly,
check_model_availability, list_available_models) so it's a drop-in
replacement selected by aerofleet.agents.llm_backend.build_llm_backend()
based on RuntimeLLMSettings.mode — the council/factory code never needs
to know which backend is actually running.

The rest of the system (AgentFactory.DEFAULT_MODEL_MAP,
CouncilOfExperts._apply_dynamic_model_routing) always deals in Ollama-style
tags (e.g. "llama4:scout"), since that's the roster's native vocabulary.
OpenRouter uses its own model-id namespace (e.g.
"meta-llama/llama-4-scout"), so this class owns the one place that
translation needs to happen — the rest of the pipeline stays backend-
agnostic.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Union

import httpx

from aerofleet.utils.logging import get_logger
from aerofleet.utils.exceptions import AgentCommunicationError

logger = get_logger(__name__)

OPENROUTER_CHAT_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"

# Ollama tag -> OpenRouter model id. Confirmed real/callable on OpenRouter
# (Aug 2026). NOTE: OpenRouter doesn't have Mistral Large 3 or Gemma 4
# listed yet (Ollama's registry is ahead of OpenRouter's catalogue here) —
# those two fall back to the previous generation (Large 2 / Gemma 3) rather
# than silently sending a tag OpenRouter would 400 on. Documented, not
# hidden: API-mode COMPLIANCE/WEATHER/OPS responses come from a slightly
# older model generation than LOCAL/TAILSCALE mode until OpenRouter
# catches up.
DEFAULT_TAG_TO_OPENROUTER_ID: Dict[str, str] = {
    "llama4:scout": "meta-llama/llama-4-scout",
    "mistral-small3.2": "mistralai/mistral-small-3.2-24b-instruct",
    "mistral-large-3": "mistralai/mistral-large",       # falls back to Large 2 — see note above
    "gemma4:12b": "google/gemma-3-12b-it",               # falls back to Gemma 3 — see note above
    "phi4-reasoning:plus": "microsoft/phi-4-reasoning-plus",
}


class OpenRouterAgent:
    def __init__(
        self,
        api_key: Optional[str],
        model_map: Optional[Dict[str, str]] = None,
        default_model: str = "meta-llama/llama-4-scout",
        timeout: float = 60.0,
    ):
        if not api_key:
            raise AgentCommunicationError(
                "OpenRouter connection mode selected but no API key is configured. "
                "Set it via the Settings panel or the OPENROUTER_API_KEY env var.",
                agent_id="OPENROUTER_AGENT",
            )
        self._api_key = api_key
        self._model_map = {**DEFAULT_TAG_TO_OPENROUTER_ID, **(model_map or {})}
        self.default_model = default_model
        self.timeout = timeout
        self._client = httpx.Client(
            timeout=timeout,
            headers={
                "Authorization": f"Bearer {api_key}",
                "HTTP-Referer": "https://github.com/aerofleet",
                "X-Title": "AeroFleet",
            },
        )

    def _get_model(self, model_override: Optional[str] = None) -> str:
        """Resolve an internal (Ollama-style) tag to an OpenRouter model id."""
        tag = model_override or self.default_model
        return self._model_map.get(tag, tag)

    def _chat(
        self,
        system_prompt: str,
        user_prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.3,
    ) -> str:
        resolved_model = self._get_model(model)
        try:
            logger.debug(f"Sending chat to OpenRouter model={resolved_model}")
            response = self._client.post(
                OPENROUTER_CHAT_URL,
                json={
                    "model": resolved_model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": temperature,
                },
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]
        except httpx.HTTPStatusError as e:
            raise AgentCommunicationError(
                f"OpenRouter chat failed (model={resolved_model}): "
                f"{e.response.status_code} {e.response.text}",
                agent_id="OPENROUTER_AGENT",
            ) from e
        except Exception as e:
            raise AgentCommunicationError(
                f"OpenRouter chat failed (model={resolved_model}): {e}",
                agent_id="OPENROUTER_AGENT",
            ) from e

    def interpret_mission(self, user_prompt: str, model: Optional[str] = None) -> Dict[str, Any]:
        system_prompt = """You are AeroFleet, an autonomous drone-fleet dispatch agent.
Your job is to interpret delivery-order commands and output ONLY valid JSON.

Output Format:
{
    "mission_type": "type of delivery (e.g., STANDARD, EXPRESS, MEDICAL)",
    "origin": "origin depot id",
    "target": "destination address or node id",
    "constraints": {
        "deadline_minutes": <number>,
        "payload_kg": <number>
    }
}
"""
        try:
            content = self._chat(
                system_prompt=system_prompt,
                user_prompt=f"Command: {user_prompt}",
                model=model,
                temperature=0.1,
            )
            start = content.find("{")
            end = content.rfind("}") + 1
            if start == -1 or end == 0:
                logger.warning("No JSON found in agent response")
                return {}
            return json.loads(content[start:end])
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from agent response: {e}")
            return {}
        except AgentCommunicationError:
            raise
        except Exception as e:
            raise AgentCommunicationError(f"Agent interpretation failed: {e}", agent_id="OPENROUTER_AGENT") from e

    def reason(
        self,
        context_prompt: Union[str, Dict],
        model: Optional[str] = None,
        system_prompt_override: Optional[str] = None,
    ) -> str:
        if isinstance(context_prompt, dict):
            context_prompt = json.dumps(context_prompt, indent=2)

        system_persona = system_prompt_override or (
            "You are ARIA, the Chief Fleet Dispatcher at AeroFleet. "
            "Your goal is to help operators run a safe, efficient city-scale drone delivery fleet. "
            "\n\nGUIDELINES:"
            "\n1. ALWAYS provide engineering reasoning for your choices "
            "(e.g., 'This route needs a battery swap because payload adds 15% energy draw...'). "
            "\n2. If the request is vague, ask clarifying questions "
            "(e.g., 'Is this a standard or medical-priority delivery?'). "
            "\n3. Critique the plan if it is unsafe, illegal (DGCA), or physically impossible. "
            "\n4. When analyzing anomalies, be decisive and prioritize safety over delivery time."
            "\n5. Be concise but technical."
            "\n6. Always show calculations and cite the formula used."
        )

        try:
            return self._chat(system_prompt=system_persona, user_prompt=context_prompt, model=model)
        except AgentCommunicationError:
            raise
        except Exception as e:
            error_msg = f"[SYSTEM ERROR] AI Reasoning Module Offline: {e}"
            logger.error(error_msg)
            return error_msg

    def analyze_anomaly(
        self, anomaly_description: str, telemetry: Dict[str, Any], model: Optional[str] = None
    ) -> Dict[str, str]:
        context = f"""CRITICAL ALERT: {anomaly_description}

Current Telemetry:
{json.dumps(telemetry, indent=2)}

Recommend immediate action: CONTINUE, SAFE_MODE, or ABORT.
Provide detailed reasoning with calculations."""
        response = self.reason(context, model=model)
        action = "SAFE_MODE"
        if "CONTINUE" in response.upper():
            action = "CONTINUE"
        elif "ABORT" in response.upper():
            action = "ABORT"
        return {"action": action, "reasoning": response}

    def check_model_availability(self, model_name: str) -> bool:
        resolved = self._get_model(model_name)
        return resolved in self.list_available_models()

    def list_available_models(self) -> List[str]:
        try:
            response = self._client.get(OPENROUTER_MODELS_URL)
            response.raise_for_status()
            return [m["id"] for m in response.json().get("data", [])]
        except Exception as e:
            logger.error(f"Failed to list OpenRouter models: {e}")
            return []
