"""
BaseAgent — Abstract base class for specialist agents (13–16).

Provides a thin, consistent interface around LocalMissionAgent so that
new specialist agents only need to implement `evaluate()`.

Persistent Memory Integration:
    On init, each agent loads relevant past learnings from ChromaDB via
    agent_memory.memory_loader. This context is prepended to every LLM
    call so agents "remember" corrections from previous scenario runs.
"""

import logging
from typing import Dict, Any, List, Optional

from aerofleet.utils.config import get_config
from aerofleet.utils.exceptions import AgentCommunicationError

logger = logging.getLogger(__name__)

# Memory integration — graceful fallback if agent_memory is not installed
try:
    from agent_memory.memory_loader import build_memory_context
    _MEMORY_AVAILABLE = True
except ImportError:
    _MEMORY_AVAILABLE = False
    logger.debug("agent_memory not installed — persistent memory disabled.")


class BaseAgent:
    """
    Abstract base class for specialist council agents.

    Subclasses must define:
        name        (str)  — human-readable display name
        domain      (str)  — domain key used for pheromone decay routing
        model       (str)  — default Ollama model name
        SYSTEM_PROMPT (str) — the agent's persona / instruction block

    And must implement:
        evaluate(mission_plan, telemetry, round_num) -> Dict
    """

    name: str = "BaseAgent"
    domain: str = "base"
    model: str = "qwen3:30b"
    SYSTEM_PROMPT: str = "You are a drone fleet dispatch specialist."

    def __init__(self, llm: Optional[Any] = None):
        """
        Args:
            llm: Shared LLM backend instance (LocalMissionAgent or
                MockLLMBackend). If None, one is created automatically.
        """
        if llm is None:
            try:
                from aerofleet.agents.llm_backend import build_llm_backend
                llm = build_llm_backend()
            except AgentCommunicationError as exc:
                logger.warning(
                    f"BaseAgent({self.name}): Could not connect to Ollama — {exc}. "
                    "Agent will return placeholder responses."
                )
                llm = None

        self._llm = llm
        self.last_flags: List[Dict] = []    # used by pheromone decay logic
        self._memory_context: str = ""     # loaded from ChromaDB at call time

    # ─────────────────────────────────────────────────────────────────────
    #  LLM CALL
    # ─────────────────────────────────────────────────────────────────────

    def _call_llm(
        self,
        user_prompt: str,
        mission_plan: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Call the LLM with this agent's system prompt and model.

        If mission_plan is provided and agent_memory is available, the top-K
        most relevant past learnings are prepended to the system prompt so the
        agent benefits from persistent episodic memory across restarts.

        Returns the raw text response, or an offline placeholder on failure.
        """
        if self._llm is None:
            return f"[{self.name} OFFLINE] No LLM connection available."

        # ── Persistent Memory Injection ────────────────────────────────
        system_prompt = self.SYSTEM_PROMPT
        if _MEMORY_AVAILABLE and mission_plan is not None:
            try:
                memory_ctx = build_memory_context(
                    agent_id=self.domain,
                    mission_parameters=mission_plan,
                    top_k=5,
                )
                if memory_ctx:
                    system_prompt = memory_ctx + "\n\n" + system_prompt
                    logger.debug(
                        f"Agent '{self.name}': memory context injected "
                        f"({len(memory_ctx)} chars)."
                    )
            except Exception as mem_exc:
                logger.debug(f"Memory context load failed (non-fatal): {mem_exc}")

        try:
            # LocalMissionAgent.reason() is synchronous — wrap for async callers
            response = self._llm.reason(
                context_prompt=user_prompt,
                model=self.model,
                system_prompt_override=system_prompt,
            )
            return response
        except AgentCommunicationError as exc:
            logger.error(f"Agent {self.name} LLM call failed: {exc}")
            return f"[{self.name} ERROR] {exc}"
        except Exception as exc:
            logger.error(f"Agent {self.name} unexpected error: {exc}")
            return f"[{self.name} UNEXPECTED ERROR] {exc}"

    # ─────────────────────────────────────────────────────────────────────
    #  RESPONSE PARSER
    # ─────────────────────────────────────────────────────────────────────

    def _parse_response(self, response_text: str, domain: str) -> Dict[str, Any]:
        """
        Parse a raw LLM response into a standardised agent output dict.

        Extracts GREEN / YELLOW / RED verdict from the text.
        Stores flags for pheromone decay.
        """
        text_upper = response_text.upper()

        if "RED" in text_upper:
            verdict = "RED"
        elif "YELLOW" in text_upper:
            verdict = "YELLOW"
        else:
            verdict = "GREEN"

        # Extract flag keywords (simple heuristic — subclasses can override)
        flags = []
        for line in response_text.splitlines():
            if any(kw in line.upper() for kw in ["FLAG:", "VIOLATION:", "CONSTRAINT:"]):
                flags.append({"constraint": line.strip(), "domain": domain})
        self.last_flags = flags

        return {
            "agent":     self.name,
            "domain":    domain,
            "verdict":   verdict,
            "reasoning": response_text,
            "model":     self.model,
            "math_steps": [],
            "flags":     flags,
            "skipped":   False,
        }

    # ─────────────────────────────────────────────────────────────────────
    #  INTERFACE (override in subclasses)
    # ─────────────────────────────────────────────────────────────────────

    def evaluate(
        self,
        mission_plan: Dict[str, Any],
        telemetry: Dict[str, Any],
        round_num: int,
    ) -> Dict[str, Any]:
        """
        Evaluate the mission plan and return a standardised critique dict.

        Subclasses MUST override this method.
        """
        raise NotImplementedError(
            f"Agent '{self.name}' must implement evaluate()"
        )
