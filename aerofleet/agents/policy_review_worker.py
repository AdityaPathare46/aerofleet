"""Slow-cadence, async, human-gated fleet-policy review.

This is the third legitimate use of the LLM council established by Phase AB's
restructuring (docs/PATENT_NOVELTY.md's "council is never on the decision or
action path" claim): reasoning about *whether CBF safety thresholds should be
adjusted*, on a cadence of hours, never per-order, and never auto-applied.
The council here produces a PolicyProposal row that a human operator must
explicitly approve (aerofleet/api/routes/policy.py) before
aerofleet/safety/policy_store.py's get_active_policy() will ever return it —
the CBF gate's constraint *definitions* are never touched by any of this,
only the numeric thresholds an operator has signed off on.

Same background-worker idiom as aerofleet/hardware/telemetry_service.py and
aerofleet/agents/explanation_worker.py: module-level Optional[asyncio.Task],
idempotent start/stop wired into app.py's startup/shutdown, and the actual
LLM call kept off the event loop via run_in_executor.
"""
from __future__ import annotations

import asyncio
import json
import re
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from aerofleet.data.database import get_db_session
from aerofleet.utils.logging import get_logger

logger = get_logger(__name__)

DEFAULT_INTERVAL_S = 6 * 3600.0  # 6 hours, env-configurable via POLICY_REVIEW_INTERVAL_S

# The "Fleet Policy Analyst" phrase is load-bearing: aerofleet/agents/
# mock_agent.py's MockLLMBackend.reason() detects it to return a
# policy-shaped mock response instead of a dispatch-verdict-shaped one.
POLICY_ANALYST_SYSTEM_PROMPT = """You are the Fleet Policy Analyst for AeroFleet's drone-delivery
operations. You review recent fleet-wide statistics on a slow cadence (hours,
not per-order) and propose CONSERVATIVE adjustments to the Control-Barrier-
Function safety gate's default thresholds when — and only when — the data
supports it. You never decide anything yourself; a human operator must
approve any proposal before it takes effect.

Allowed threshold keys (only propose keys from this list, only when justified):
min_separation_m, max_altitude_m, max_wind_mps, max_payload_kg, max_noise_db,
max_collision_probability, min_link_margin_db, depot_pad_slots, min_visibility_m.

If the stats show no near-misses, CBF interventions, or fault events, propose
NO changes — an empty JSON object. End your response with a fenced JSON block
containing only the threshold keys you're proposing to change:
```json
{}
```
"""


def _extract_json_block(text: str) -> Dict[str, float]:
    """Pull the last ```json ... ``` fenced block out of an LLM response.
    Never raises — a malformed/missing block just means no changes proposed,
    which is the safe default, not an error worth failing the whole cycle over."""
    matches = re.findall(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
    if not matches:
        return {}
    try:
        parsed = json.loads(matches[-1])
        return {k: float(v) for k, v in parsed.items() if isinstance(v, (int, float))}
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        logger.warning(f"Could not parse policy JSON block: {exc}")
        return {}


_ALLOWED_KEYS = {
    "min_separation_m", "max_altitude_m", "max_wind_mps", "max_payload_kg",
    "max_noise_db", "max_collision_probability", "min_link_margin_db",
    "depot_pad_slots", "min_visibility_m",
}


def analyze_city_policy(city: str, stats: Dict[str, Any]) -> Tuple[Dict[str, float], str]:
    """Single-shot (not a multi-round debate — this doesn't need ACO
    convergence, just one analyst call) LLM consultation. Runs synchronously;
    callers must offload via run_in_executor to stay off the event loop,
    exactly like explanation_worker.py does for the dispatch-explanation council."""
    from aerofleet.agents.llm_backend import build_llm_backend

    backend = build_llm_backend()
    prompt = (
        f"City: {city}\n"
        f"Recent fleet digital-twin statistics:\n{json.dumps(stats, indent=2)}\n\n"
        "Propose threshold changes (or none) per your instructions."
    )
    raw = backend.reason(prompt, system_prompt_override=POLICY_ANALYST_SYSTEM_PROMPT)
    changes = {k: v for k, v in _extract_json_block(raw).items() if k in _ALLOWED_KEYS}
    return changes, raw


class PolicyReviewWorker:
    def __init__(self, interval_s: float = DEFAULT_INTERVAL_S) -> None:
        self.interval_s = interval_s
        self._running = False

    async def run_forever(self) -> None:
        self._running = True
        logger.info(f"Policy review worker started (interval={self.interval_s:.0f}s)")
        while self._running:
            await self._sleep_interruptible(self.interval_s)
            if not self._running:
                break
            try:
                await self.run_review_cycle()
            except Exception as exc:
                logger.error(f"Policy review cycle failed: {exc}")
        logger.info("Policy review worker stopped")

    async def _sleep_interruptible(self, total_s: float, chunk_s: float = 5.0) -> None:
        remaining = total_s
        while remaining > 0 and self._running:
            step = min(chunk_s, remaining)
            await asyncio.sleep(step)
            remaining -= step

    async def run_review_cycle(self, cities: Optional[List[str]] = None) -> List[str]:
        """Runs one review pass across `cities` (default: every currently
        active city). Returns the proposal_ids created — empty if no city
        had a signal worth proposing a change for. Safe to call directly
        for a manual/demo trigger (aerofleet/api/routes/policy.py)."""
        from aerofleet.fleet.state import get_fleet_state, list_active_cities

        target_cities = cities or list_active_cities()
        loop = asyncio.get_event_loop()
        created: List[str] = []

        for city in target_cities:
            try:
                fleet = get_fleet_state(city)
                stats = fleet.twin.to_dict()
                changes, rationale = await loop.run_in_executor(None, analyze_city_policy, city, stats)
            except Exception as exc:
                logger.error(f"[{city}] Policy review failed: {exc}")
                continue

            if not changes:
                logger.info(f"[{city}] Policy review: no changes proposed")
                continue

            proposal_id = self._persist_proposal(city, changes, rationale, stats)
            created.append(proposal_id)
            logger.info(f"[{city}] Policy proposal created: {proposal_id} — {changes}")

        return created

    @staticmethod
    def _persist_proposal(city: str, changes: Dict[str, float], rationale: str, stats: Dict[str, Any]) -> str:
        from aerofleet.data.models.models import PolicyProposal

        proposal_id = f"POL-{uuid.uuid4().hex[:8].upper()}"
        with get_db_session() as db:
            db.add(PolicyProposal(
                proposal_id=proposal_id,
                city=city,
                proposed_changes=changes,
                rationale=rationale,
                stats_snapshot=stats,
                status="PENDING_REVIEW",
                created_at=datetime.utcnow(),
            ))
        return proposal_id

    def stop(self) -> None:
        self._running = False


_worker: Optional[PolicyReviewWorker] = None
_task: Optional[asyncio.Task] = None


def get_policy_review_worker() -> PolicyReviewWorker:
    global _worker
    if _worker is None:
        import os

        interval_s = float(os.environ.get("POLICY_REVIEW_INTERVAL_S", DEFAULT_INTERVAL_S))
        _worker = PolicyReviewWorker(interval_s=interval_s)
    return _worker


def start_background_policy_review_worker() -> None:
    global _task
    if _task is None:
        _task = asyncio.create_task(get_policy_review_worker().run_forever())


def stop_background_policy_review_worker() -> None:
    global _task, _worker
    if _worker is not None:
        _worker.stop()
    # See explanation_worker.py's stop function for the full explanation —
    # both must be reset, not just _task: the old worker's asyncio.Queue
    # is itself bound to the closed event loop, and a fresh worker (fresh
    # Queue) is needed, not just a fresh Task around the same stale one.
    _task = None
    _worker = None
