"""Fleet Incident Forensics Council — multi-agent, auto-triggered
investigation of a real fleet anomaly.

This is the actual answer to "what does the AI decide": not whether to
write an explanation paragraph on request, but "what went wrong, in which
subsystem, with what confidence, and what to do about it" — triggered
automatically the moment the deterministic system produces an anomaly (a
CBF rejection today; fault events and emergency landings once
aerofleet/fault_tolerance/multi_fault_handler.py is wired to a live
trigger — see aerofleet/api/routes/orders.py's dispatch_order for the one
currently live).

Same background-worker idiom as explanation_worker.py and
policy_review_worker.py: module-level Optional[asyncio.Task], idempotent
start/stop wired into app.py, an internal queue, LLM calls kept off the
event loop via run_in_executor. Never on the decision path — this only
ever investigates a decision that has already been made and is final,
exactly like the explanation worker, just auto-triggered and structured
around a real taxonomy instead of free-form explanation.

See aerofleet/agents/incident_taxonomy.py for the full design rationale
and citations.
"""
from __future__ import annotations

import asyncio
import json
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from aerofleet.agents.incident_taxonomy import (
    DOMAIN_ASSESSMENT_TASK_TEMPLATE,
    DOMAIN_FACTORS,
    REGULATORY_AGENT_ID,
    REGULATORY_TASK_TEMPLATE,
    SYNTHESIS_TASK_TEMPLATE,
    SYSTEMIC_AGENT_ID,
    build_incident_context_prompt,
)
from aerofleet.data.database import get_db_session
from aerofleet.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class IncidentJob:
    incident_id: str
    city: str
    trigger_type: str
    trigger_detail: Dict[str, Any]
    frozen_context: Dict[str, Any]
    order_id: Optional[str] = None


def _extract_json_block(text: str) -> Optional[Dict[str, Any]]:
    """Pull the last ```json ... ``` fenced block out of an LLM response.
    Never raises — a malformed/missing block is treated as "this agent's
    assessment couldn't be parsed," not a fatal error for the whole
    investigation (see _process()'s per-agent try/except)."""
    matches = re.findall(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
    if not matches:
        return None
    try:
        return json.loads(matches[-1])
    except json.JSONDecodeError as exc:
        logger.warning(f"Could not parse incident-forensics JSON block: {exc}")
        return None


class IncidentForensicsWorker:
    def __init__(self) -> None:
        self._queue: "asyncio.Queue[IncidentJob]" = asyncio.Queue()
        self._running = False

    def enqueue(self, job: IncidentJob) -> None:
        self._queue.put_nowait(job)
        from aerofleet.data.models.models import IncidentReport

        with get_db_session() as db:
            db.add(IncidentReport(
                incident_id=job.incident_id,
                city=job.city,
                order_id=job.order_id,
                trigger_type=job.trigger_type,
                trigger_detail=job.trigger_detail,
                frozen_context=job.frozen_context,
                status="PENDING",
            ))
        logger.warning(f"[{job.incident_id}] Incident forensics job enqueued ({job.trigger_type})")

    async def run_forever(self) -> None:
        self._running = True
        logger.info("Incident forensics worker started")
        while self._running:
            try:
                job = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            await self._process(job)
        logger.info("Incident forensics worker stopped")

    async def _process(self, job: IncidentJob) -> None:
        logger.info(f"[{job.incident_id}] Investigating (async, off the event loop)")
        self._set_status(job.incident_id, "INVESTIGATING")

        loop = asyncio.get_event_loop()
        try:
            factors, regulatory, transcript = await loop.run_in_executor(None, self._investigate, job)
            synthesis = await loop.run_in_executor(None, self._synthesize, job, factors, regulatory, transcript)
            self._finalize(job.incident_id, factors, regulatory, synthesis, transcript, status="READY")
            logger.info(f"[{job.incident_id}] Investigation complete")
        except Exception as exc:
            logger.error(f"[{job.incident_id}] Investigation failed: {exc}")
            self._set_status(job.incident_id, "FAILED")

    # ─────────────────────────────────────────────────────────────────
    #  Synchronous — runs in the executor thread, not the event loop
    # ─────────────────────────────────────────────────────────────────

    def _investigate(self, job: IncidentJob) -> Tuple[List[Dict[str, Any]], Dict[str, Any], List[Dict[str, Any]]]:
        from aerofleet.agents.factory import AgentFactory
        from aerofleet.agents.llm_backend import build_llm_backend

        backend = build_llm_backend()
        roster = {a["id"]: a for a in AgentFactory.get_agent_roster()}
        context_prompt = build_incident_context_prompt(job.trigger_type, job.trigger_detail, job.frozen_context)

        transcript: List[Dict[str, Any]] = []
        factors: List[Dict[str, Any]] = []

        for domain_factor in DOMAIN_FACTORS:
            agent = roster.get(domain_factor.agent_id)
            if agent is None:
                continue
            task = DOMAIN_ASSESSMENT_TASK_TEMPLATE.format(
                description=domain_factor.description, factor_name=domain_factor.factor_name
            )
            system_prompt = f"{agent['system_prompt']}\n\n{task}"
            raw = backend.reason(context_prompt, model=agent["model"], system_prompt_override=system_prompt)
            transcript.append({
                "phase": 2, "agent_id": domain_factor.agent_id, "name": agent["name"],
                "model": agent["model"], "text": raw,
            })
            parsed = _extract_json_block(raw)
            factors.append(parsed if parsed else {
                "factor": domain_factor.factor_name, "contributed": "UNCERTAIN",
                "confidence": 0.0, "evidence": "Could not parse this agent's response.",
            })

        regulatory_agent = roster.get(REGULATORY_AGENT_ID)
        regulatory: Dict[str, Any] = {"reportable": None, "citation": None}
        if regulatory_agent:
            system_prompt = f"{regulatory_agent['system_prompt']}\n\n{REGULATORY_TASK_TEMPLATE}"
            raw = backend.reason(context_prompt, model=regulatory_agent["model"], system_prompt_override=system_prompt)
            transcript.append({
                "phase": 4, "agent_id": REGULATORY_AGENT_ID, "name": regulatory_agent["name"],
                "model": regulatory_agent["model"], "text": raw,
            })
            parsed = _extract_json_block(raw)
            if parsed:
                regulatory = parsed

        return factors, regulatory, transcript

    def _synthesize(
        self, job: IncidentJob, factors: List[Dict[str, Any]], regulatory: Dict[str, Any],
        transcript: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        from aerofleet.agents.factory import AgentFactory
        from aerofleet.agents.llm_backend import build_llm_backend

        backend = build_llm_backend()
        roster = {a["id"]: a for a in AgentFactory.get_agent_roster()}
        dispatcher = roster.get(SYSTEMIC_AGENT_ID)
        if dispatcher is None:
            return {}

        context_prompt = (
            build_incident_context_prompt(job.trigger_type, job.trigger_detail, job.frozen_context)
            + f"\n\nDomain assessments received:\n{json.dumps(factors, indent=2)}"
            + f"\n\nRegulatory assessment:\n{json.dumps(regulatory, indent=2)}"
        )
        task = SYNTHESIS_TASK_TEMPLATE.format(n_factors=len(factors))
        system_prompt = f"{dispatcher['system_prompt']}\n\n{task}"
        raw = backend.reason(context_prompt, model=dispatcher["model"], system_prompt_override=system_prompt)
        transcript.append({
            "phase": 3, "agent_id": SYSTEMIC_AGENT_ID, "name": dispatcher["name"],
            "model": dispatcher["model"], "text": raw,
        })
        return _extract_json_block(raw) or {}

    # ─────────────────────────────────────────────────────────────────

    @staticmethod
    def _set_status(incident_id: str, status: str) -> None:
        from aerofleet.data.models.models import IncidentReport

        with get_db_session() as db:
            report = db.query(IncidentReport).filter(IncidentReport.incident_id == incident_id).first()
            if report is not None:
                report.status = status

    @staticmethod
    def _finalize(
        incident_id: str, factors: List[Dict[str, Any]], regulatory: Dict[str, Any],
        synthesis: Dict[str, Any], transcript: List[Dict[str, Any]], status: str,
    ) -> None:
        from aerofleet.data.models.models import IncidentReport

        with get_db_session() as db:
            report = db.query(IncidentReport).filter(IncidentReport.incident_id == incident_id).first()
            if report is None:
                return
            report.status = status
            report.contributing_factors = factors
            report.root_cause_summary = synthesis.get("root_cause_summary")
            report.systemic_factor_note = synthesis.get("systemic_factor_note")
            report.recommended_action = synthesis.get("recommended_action")
            report.recommended_policy_change = synthesis.get("recommended_policy_change")
            report.regulatory_reportable = regulatory.get("reportable")
            report.regulatory_citation = regulatory.get("citation")
            report.investigation_transcript = transcript
            report.completed_at = datetime.utcnow()

    def stop(self) -> None:
        self._running = False


_worker: Optional[IncidentForensicsWorker] = None
_task: Optional[asyncio.Task] = None


def get_incident_forensics_worker() -> IncidentForensicsWorker:
    global _worker
    if _worker is None:
        _worker = IncidentForensicsWorker()
    return _worker


def start_background_incident_forensics_worker() -> None:
    global _task
    if _task is None:
        _task = asyncio.create_task(get_incident_forensics_worker().run_forever())


def stop_background_incident_forensics_worker() -> None:
    global _task, _worker
    if _worker is not None:
        _worker.stop()
    # See explanation_worker.py's stop function for the full explanation —
    # both must be reset, not just _task: the old worker's asyncio.Queue
    # is itself bound to the closed event loop, and a fresh worker (fresh
    # Queue) is needed, not just a fresh Task around the same stale one.
    _task = None
    _worker = None


def new_incident_id() -> str:
    return f"INC-{uuid.uuid4().hex[:8].upper()}"
