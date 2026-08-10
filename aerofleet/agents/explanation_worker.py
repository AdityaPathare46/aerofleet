"""Async, non-blocking generator of post-hoc council explanations for
dispatch decisions that have already been made deterministically.

Why this module exists: faculty feedback correctly identified that LLM
inference latency (seconds per agent call, up to ~80 calls across a full
debate) is incompatible with real-time decision-making. `aerofleet.agents
.council.CouncilOfExperts.run_grand_debate` is a plain synchronous method
with no internal `await`s; calling it directly inside a FastAPI request
handler doesn't just delay that one response — with no `await` in the
call chain, it blocks the entire asyncio event loop thread, stalling every
other in-flight request on the server for the duration of the debate.
That used to happen via `orders.py`'s `use_council=True` branch, which has
been removed. This worker is now the ONLY place `run_grand_debate` is ever
called, and it always does so via `run_in_executor` — offloading the
actual blocking work to a separate OS thread so the event loop stays free
to service every other request while a debate runs in the background.

Dispatch itself is unaffected either way: the CBF gate has already
approved or rejected the order before a job is ever enqueued here. This
worker only explains a decision, never makes or delays one.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional

from aerofleet.data.database import get_db_session
from aerofleet.data.models.models import Order
from aerofleet.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ExplanationJob:
    order_id: str
    dispatch_plan: Dict[str, Any]
    cbf_certificate: Dict[str, Any]


class ExplanationWorker:
    """One background task, processing one job at a time — deliberately
    not parallelized. These are non-urgent by design; running several
    11-agent debates concurrently would only contend for the same LLM
    backend without making anything faster."""

    def __init__(self) -> None:
        self._queue: "asyncio.Queue[ExplanationJob]" = asyncio.Queue()
        self._running = False

    def enqueue(self, job: ExplanationJob) -> None:
        self._queue.put_nowait(job)
        with get_db_session() as db:
            order = db.query(Order).filter(Order.order_id == job.order_id).first()
            if order is not None:
                order.council_explanation_status = "PENDING"
                order.council_explanation_requested_at = datetime.utcnow()
        logger.info(f"[{job.order_id}] Explanation job enqueued")

    async def run_forever(self) -> None:
        self._running = True
        logger.info("Explanation worker started")
        while self._running:
            try:
                job = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            await self._process(job)
        logger.info("Explanation worker stopped")

    async def _process(self, job: ExplanationJob) -> None:
        logger.info(f"[{job.order_id}] Generating council explanation (async, off the event loop)")
        with get_db_session() as db:
            order = db.query(Order).filter(Order.order_id == job.order_id).first()
            if order is not None:
                order.council_explanation_status = "RUNNING"

        transcript = None
        status = "FAILED"
        try:
            from aerofleet.agents.council import CouncilOfExperts

            loop = asyncio.get_event_loop()
            # Both the constructor (LLM connectivity check) and the debate
            # itself (up to ~80 blocking LLM calls) run in a worker thread —
            # this is the actual fix, not just "call it from a task."
            council = await loop.run_in_executor(None, CouncilOfExperts)
            _final_plan, transcript = await loop.run_in_executor(
                None,
                lambda: council.run_grand_debate(
                    dict(job.dispatch_plan), precomputed_cbf_certificate=job.cbf_certificate
                ),
            )
            status = "READY"
        except Exception as exc:
            logger.error(f"[{job.order_id}] Explanation generation failed: {exc}")

        with get_db_session() as db:
            order = db.query(Order).filter(Order.order_id == job.order_id).first()
            if order is not None:
                order.council_transcript = transcript
                order.council_explanation_status = status
                order.council_explanation_completed_at = datetime.utcnow()
        logger.info(f"[{job.order_id}] Explanation job finished: {status}")

    def stop(self) -> None:
        self._running = False


_worker: Optional[ExplanationWorker] = None
_task: Optional[asyncio.Task] = None


def get_explanation_worker() -> ExplanationWorker:
    global _worker
    if _worker is None:
        _worker = ExplanationWorker()
    return _worker


def start_background_explanation_worker() -> None:
    global _task
    if _task is None:
        _task = asyncio.create_task(get_explanation_worker().run_forever())


def stop_background_explanation_worker() -> None:
    global _task, _worker
    if _worker is not None:
        _worker.stop()
    # Reset BOTH so the next start_background_...() builds a fresh worker
    # (fresh asyncio.Queue included) tied to whatever event loop is
    # current then. Resetting only _task isn't enough: the Queue inside
    # the old _worker is itself bound to the closed loop it was first
    # awaited on, and asyncio raises "Queue ... is bound to a different
    # event loop" the moment a new loop's task calls .get() on it — this
    # was actually observed, not hypothesized (see
    # tests/integration/test_incidents_api.py, which is what surfaced it:
    # its incident-forensics tests wait synchronously for a job to reach
    # READY, which the earlier explanation/policy-review tests never did,
    # so they never noticed their own background task was silently dying
    # on every test after the first one to touch it).
    _task = None
    _worker = None
