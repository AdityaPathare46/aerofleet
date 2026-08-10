"""Local mission agent using Ollama for onboard AI reasoning.

Production-grade: supports per-agent model routing so each specialist
agent can use a different LLM optimized for its domain.
"""

import ollama
import json
from typing import Dict, Any, Union, Optional, List

from aerofleet.utils.logging import get_logger
from aerofleet.utils.config import get_config
from aerofleet.utils.exceptions import AgentCommunicationError

logger = get_logger(__name__)


class LocalMissionAgent:
    """
    Onboard AI agent using local LLM (Ollama).
    
    Supports per-agent model routing: each agent in the Council can use
    a different LLM model optimized for its specialty. The model is
    resolved per-call, allowing the Council to route different prompts
    to different models.
    """
    
    def __init__(
        self,
        model_name: Optional[str] = None,
        ollama_host_override: Optional[str] = None,
        connect_timeout: Optional[float] = None,
    ):
        """
        Initialize local mission agent.

        Args:
            model_name: Default Ollama model name (used when no
                        per-call model is specified). Defaults to config value.
            ollama_host_override: Connect to this host instead of
                        config.llm.ollama_host — used by build_llm_backend()
                        so the same class serves both "local" and
                        "tailscale" connection modes, differing only in host.
            connect_timeout: Short timeout (seconds) for the initial
                        connectivity check only, overriding config.llm.ollama_timeout
                        (which defaults to 300s, fine for real chat calls but far
                        too slow for a Settings-panel "Test Connection" click against
                        an unreachable/misspelled host — e.g. a black-holed IP can
                        otherwise hang on OS-level TCP timeouts for a minute or more).
        """
        config = get_config()

        if model_name is None:
            self.default_model = config.llm.ollama_model
        else:
            self.default_model = model_name

        self.ollama_host = ollama_host_override or config.llm.ollama_host
        self.timeout = connect_timeout or config.llm.ollama_timeout

        # Create a client pointed at the configured remote host.
        # Using ollama.Client(host=...) ensures OLLAMA_HOST in .env
        # is respected even when running against a remote GPU server.
        # timeout is passed through to the underlying httpx.Client — without
        # it, an unreachable host (e.g. a bad Tailscale IP) hangs on the OS's
        # own TCP timeout, which can be a minute or more.
        self._client = ollama.Client(host=self.ollama_host, timeout=self.timeout)
        
        # Verify Ollama connection
        try:
            models_response = self._client.list()
            # SDK returns an object with a .models attribute (list of objects)
            # but older versions return a dict — handle both.
            raw_models = getattr(models_response, "models", None) or models_response.get("models", [])
            available = [getattr(m, "model", None) or m.get("name", "") for m in raw_models]
            logger.info(
                f"Connected to Ollama at {self.ollama_host}. "
                f"Default model: {self.default_model}. "
                f"Available models: {len(available)}"
            )
        except Exception as e:
            logger.error(f"Could not connect to Ollama at {self.ollama_host}: {e}")
            raise AgentCommunicationError(
                f"Ollama connection failed at {self.ollama_host}: {e}. "
                f"Is the server running and accessible?",
                agent_id="LOCAL_AGENT"
            ) from e
    
    def _get_model(self, model_override: Optional[str] = None) -> str:
        """Resolve which model to use for a call."""
        return model_override if model_override else self.default_model
    
    def _chat(
        self,
        system_prompt: str,
        user_prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.3,
    ) -> str:
        """
        Core chat method wrapping Ollama with error handling and logging.
        
        Args:
            system_prompt: System-level instructions
            user_prompt: User/agent message
            model: Model name override (None = use default)
            temperature: Sampling temperature (lower = more deterministic)
        
        Returns:
            Response text from the model
        
        Raises:
            AgentCommunicationError: If LLM call fails
        """
        resolved_model = self._get_model(model)
        
        try:
            logger.debug(
                f"Sending chat to model={resolved_model}",
                extra={"prompt_length": len(user_prompt)}
            )
            
            response = self._client.chat(
                model=resolved_model,
                messages=[
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': user_prompt}
                ],
                options={
                    "temperature": temperature,
                    "num_predict": 4096,
                }
            )
            
            # Handle both object-style and dict-style SDK responses
            if hasattr(response, 'message'):
                content = response.message.content
            else:
                content = response['message']['content']
            
            logger.debug(
                f"Response received from {resolved_model}",
                extra={"response_length": len(content)}
            )
            
            return content
            
        except Exception as e:
            raise AgentCommunicationError(
                f"Ollama chat failed (model={resolved_model}): {e}",
                agent_id="LOCAL_AGENT"
            ) from e
    
    def interpret_mission(
        self,
        user_prompt: str,
        model: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Interpret mission command from natural language.
        
        Converts user input into structured JSON mission specification.
        
        Args:
            user_prompt: Natural language mission description
            model: Optional model override
        
        Returns:
            Dictionary with mission parameters
        
        Raises:
            AgentCommunicationError: If LLM communication fails
        """
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
            logger.debug(
                "Interpreting mission command",
                extra={"prompt_length": len(user_prompt)}
            )
            
            content = self._chat(
                system_prompt=system_prompt,
                user_prompt=f"Command: {user_prompt}",
                model=model,
                temperature=0.1,  # Low temp for structured output
            )
            
            # Extract JSON from response
            start = content.find('{')
            end = content.rfind('}') + 1
            
            if start == -1 or end == 0:
                logger.warning("No JSON found in agent response")
                return {}
            
            json_str = content[start:end]
            result = json.loads(json_str)
            
            logger.info(
                "Mission interpreted successfully",
                extra={"mission_type": result.get("mission_type")}
            )
            
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from agent response: {e}")
            return {}
        except AgentCommunicationError:
            raise
        except Exception as e:
            raise AgentCommunicationError(
                f"Agent interpretation failed: {e}",
                agent_id="LOCAL_AGENT"
            ) from e
    
    def reason(
        self,
        context_prompt: Union[str, Dict],
        model: Optional[str] = None,
        system_prompt_override: Optional[str] = None,
    ) -> str:
        """
        Core reasoning engine using Dr. Astra persona.
        
        Provides scientific consulting, detailed reasoning, and critiques
        for mission design decisions. Supports per-call model routing.
        
        Args:
            context_prompt: Question or context for reasoning (string or dict)
            model: Optional model override for this specific call
            system_prompt_override: Optional override for the default
                                   Dr. Astra persona (used by agents with
                                   their own system prompts)
        
        Returns:
            Agent's reasoning and recommendations
        """
        # Convert dict to string if necessary
        if isinstance(context_prompt, dict):
            context_prompt = json.dumps(context_prompt, indent=2)
        
        if system_prompt_override:
            system_persona = system_prompt_override
        else:
            system_persona = (
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
            logger.debug("Reasoning request received")
            
            result = self._chat(
                system_prompt=system_persona,
                user_prompt=context_prompt,
                model=model,
            )
            
            logger.info(
                "Reasoning completed",
                extra={"response_length": len(result), "model": self._get_model(model)}
            )
            
            return result
            
        except AgentCommunicationError:
            raise
        except Exception as e:
            error_msg = f"[SYSTEM ERROR] AI Reasoning Module Offline: {e}"
            logger.error(error_msg)
            return error_msg
    
    def analyze_anomaly(
        self,
        anomaly_description: str,
        telemetry: Dict[str, Any],
        model: Optional[str] = None,
    ) -> Dict[str, str]:
        """
        Analyze drone in-flight anomaly and recommend action.

        Args:
            anomaly_description: Description of the anomaly
            telemetry: Current drone telemetry data
            model: Optional model override
        
        Returns:
            Dictionary with action and reasoning
        """
        context = f"""CRITICAL ALERT: {anomaly_description}

Current Telemetry:
{json.dumps(telemetry, indent=2)}

Recommend immediate action: CONTINUE, SAFE_MODE, or ABORT.
Provide detailed reasoning with calculations."""
        
        response = self.reason(context, model=model)
        
        # Extract action if present
        action = "SAFE_MODE"  # Default to safe
        if "CONTINUE" in response.upper():
            action = "CONTINUE"
        elif "ABORT" in response.upper():
            action = "ABORT"
        
        logger.info(
            f"Anomaly analysis complete: {action}",
            extra={"anomaly": anomaly_description}
        )
        
        return {
            "action": action,
            "reasoning": response
        }
    
    def check_model_availability(self, model_name: str) -> bool:
        """
        Check if a specific model is available in Ollama.
        
        Args:
            model_name: Name of the model to check
        
        Returns:
            True if model is available
        """
        try:
            models_response = self._client.list()
            raw_models = getattr(models_response, "models", None) or models_response.get("models", [])
            available = [getattr(m, "model", None) or m.get("name", "") for m in raw_models]
            # Ollama model names can include tags, check partial match
            return any(model_name in m for m in available)
        except Exception:
            return False
    
    def list_available_models(self) -> List[str]:
        """
        List all models currently available in Ollama.
        
        Returns:
            List of model names
        """
        try:
            models_response = self._client.list()
            raw_models = getattr(models_response, "models", None) or models_response.get("models", [])
            return [getattr(m, "model", None) or m.get("name", "") for m in raw_models]
        except Exception:
            return []
