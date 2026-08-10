"""
Async LLM Supervisor — ASTREA pattern (Paper 10).

World's first agentic LLM+RL hybrid proven on ISS TRL-9 hardware (Sept 2025).
Mousist & Thales Alenia Space.

Key design principle (Paper 10):
  - LLM is OUTSIDE the real-time loop.
  - Adjusts control parameter (approval threshold) asynchronously.
  - Window alignment with environmental periodicity is CRITICAL
    (wrong window → -19.1% performance; right window → +245.75%).
  - Here the "window" is aligned with mission phase transitions,
    NOT with every individual agent turn.
"""

import asyncio
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class SupervisorRecommendation:
    """Structured output from one supervisor reasoning cycle."""
    approval_threshold_adjustment: float   # +/− applied to RED-flag threshold
    confidence_level: str                  # HIGH / MEDIUM / LOW
    reasoning: str
    phase_context: str


class AsyncLLMSupervisor:
    """
    Lightweight async supervisor that adjusts the Architect's approval
    threshold between council rounds — without being in the hot path.

    ASTREA insight: align reasoning window with mission phase transitions,
    NOT with every agent turn.

    Usage::
        supervisor = AsyncLLMSupervisor(llm)
        supervisor.start()                          # starts background loop
        await supervisor.submit_round_summary(...)  # non-blocking
        rec = await supervisor.get_recommendation() # None until ready
    """

    # Mission phases used as "environmental periodicity" alignment points
    MISSION_PHASES = [
        "pre_launch", "launch", "early_orbit", "cruise",
        "orbit_insertion", "operations", "deorbit",
    ]

    def __init__(self, llm=None, model: str = "qwen3:30b"):
        """
        Args:
            llm: LocalMissionAgent instance (or None for mock mode).
            model: Ollama model for supervisor reasoning.
        """
        self._llm = llm
        self.model = model
        self._queue: asyncio.Queue = asyncio.Queue()
        self._current_recommendation: Optional[SupervisorRecommendation] = None
        self._phase_history: List[str] = []
        self._running = False

    # ─────────────────────────────────────────────────────────────────────
    #  PUBLIC API
    # ─────────────────────────────────────────────────────────────────────

    async def submit_round_summary(
        self,
        round_summary: Dict,
        mission_phase: str = "operations",
    ) -> None:
        """
        Non-blocking: enqueue a round summary for background processing.
        Council continues immediately; supervisor reasons in background.
        """
        await self._queue.put({
            "round_summary": round_summary,
            "mission_phase": mission_phase,
        })

    async def get_recommendation(self) -> Optional[SupervisorRecommendation]:
        """
        Non-blocking: return latest recommendation if available.
        Returns None if supervisor hasn't finished yet (council uses defaults).
        """
        return self._current_recommendation

    def start(self) -> None:
        """Start the background supervisor loop via asyncio task."""
        if not self._running:
            self._running = True
            asyncio.create_task(self._supervisor_loop())
            logger.info("AsyncLLMSupervisor background loop started")

    def stop(self) -> None:
        """Signal the supervisor loop to stop."""
        self._running = False

    # ─────────────────────────────────────────────────────────────────────
    #  BACKGROUND LOOP
    # ─────────────────────────────────────────────────────────────────────

    async def _supervisor_loop(self) -> None:
        """
        Background loop — processes round summaries and updates recommendation.
        Aligned with phase transitions (ASTREA periodicity).
        """
        while self._running:
            try:
                summaries: List[Dict] = []
                # Drain the queue
                try:
                    while True:
                        item = self._queue.get_nowait()
                        summaries.append(item)
                except asyncio.QueueEmpty:
                    pass

                if summaries:
                    latest_phase = summaries[-1]["mission_phase"]
                    # Only reason when phase changes (periodicity alignment)
                    if latest_phase not in self._phase_history[-1:]:
                        self._phase_history.append(latest_phase)
                        rec = await self._reason_about_phase(summaries, latest_phase)
                        self._current_recommendation = rec
                        logger.info(
                            f"Supervisor updated for phase={latest_phase}: "
                            f"threshold_adj={rec.approval_threshold_adjustment:+.2f}, "
                            f"confidence={rec.confidence_level}"
                        )

                await asyncio.sleep(0.5)   # poll every 500 ms

            except Exception as exc:
                logger.error(f"Supervisor loop error: {exc}")
                await asyncio.sleep(1.0)

    async def _reason_about_phase(
        self, summaries: List[Dict], phase: str
    ) -> SupervisorRecommendation:
        """
        LLM reasoning call aligned with a mission phase transition.
        Constrained output → executable threshold adjustment.
        """
        summary_text = "\n".join(
            f"  Round {s['round_summary'].get('round', '?')}: "
            f"RED={s['round_summary'].get('red_count', 0)}, "
            f"YELLOW={s['round_summary'].get('yellow_count', 0)}, "
            f"status={s['round_summary'].get('status', 'unknown')}"
            for s in summaries
        )

        prompt = f"""
You are supervising a space mission planning council.

Current mission phase: {phase}
Council round summaries:
{summary_text}

Based on the risk level in this phase, recommend ONE action:
  A) INCREASE_STRICTNESS — raise RED threshold (more conservative approval)
  B) MAINTAIN            — keep current threshold
  C) DECREASE_STRICTNESS — lower RED threshold (faster convergence acceptable)

Output EXACTLY in this format (no extra text):
ACTION: [A/B/C]
ADJUSTMENT: [float between -0.2 and +0.2]
CONFIDENCE: [HIGH/MEDIUM/LOW]
REASON: [one sentence]
"""

        # Use LLM if available; otherwise use deterministic heuristic
        if self._llm is not None:
            try:
                raw = self._llm.reason(
                    context_prompt=prompt,
                    model=self.model,
                )
                return self._parse_supervisor_response(raw, phase)
            except Exception as exc:
                logger.warning(f"Supervisor LLM call failed: {exc} — using heuristic")

        return self._heuristic_recommendation(summaries, phase)

    def _heuristic_recommendation(
        self, summaries: List[Dict], phase: str
    ) -> SupervisorRecommendation:
        """
        Deterministic fallback when LLM is unavailable.
        More REDs → increase strictness; all GREEN → relax slightly.
        """
        total_reds = sum(
            s["round_summary"].get("red_count", 0) for s in summaries
        )
        if total_reds >= 3:
            adj = 0.1
            confidence = "HIGH"
            reasoning = f"High RED count ({total_reds}) in phase {phase} — increasing strictness."
        elif total_reds == 0:
            adj = -0.05
            confidence = "MEDIUM"
            reasoning = f"No REDs in phase {phase} — slight relaxation acceptable."
        else:
            adj = 0.0
            confidence = "MEDIUM"
            reasoning = f"Mixed signals in phase {phase} — maintaining threshold."

        return SupervisorRecommendation(
            approval_threshold_adjustment=adj,
            confidence_level=confidence,
            reasoning=reasoning,
            phase_context=phase,
        )

    def _parse_supervisor_response(
        self, text: str, phase: str
    ) -> SupervisorRecommendation:
        """Parse supervisor LLM output into a structured recommendation."""
        adjustment = 0.0
        confidence = "MEDIUM"
        reasoning  = "No change recommended."

        for line in text.splitlines():
            line = line.strip()
            if line.startswith("ADJUSTMENT:"):
                try:
                    val = float(line.split(":", 1)[1].strip())
                    adjustment = max(-0.2, min(0.2, val))
                except ValueError:
                    pass
            elif line.startswith("CONFIDENCE:"):
                conf = line.split(":", 1)[1].strip().upper()
                if conf in {"HIGH", "MEDIUM", "LOW"}:
                    confidence = conf
            elif line.startswith("REASON:"):
                reasoning = line.split(":", 1)[1].strip()

        return SupervisorRecommendation(
            approval_threshold_adjustment=adjustment,
            confidence_level=confidence,
            reasoning=reasoning,
            phase_context=phase,
        )
