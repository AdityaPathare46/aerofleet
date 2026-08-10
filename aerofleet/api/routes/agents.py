"""Agent and council API endpoints."""

import uuid
from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from aerofleet.api.schemas import AgentDebateRequest
from aerofleet.agents.factory import AgentFactory
from aerofleet.utils.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()

# In-memory job store for standalone/ad-hoc debates (not tied to a real
# order — /orders/{id}/dispatch and /request-explanation are the real
# operational path; this exists for testing/demoing the council against an
# arbitrary plan). Same async-off-the-event-loop principle either way: the
# debate NEVER runs synchronously inside a request handler.
_debate_jobs: Dict[str, Dict[str, Any]] = {}


@router.get("/roster")
async def get_agent_roster():
    """Get the complete roster of specialized agents."""
    roster = AgentFactory.get_agent_roster()
    
    # Remove tool functions from response (not JSON serializable)
    clean_roster = []
    for agent in roster:
        clean_agent = {
            "id": agent["id"],
            "name": agent["name"],
            "role": agent["role"],
            "color": agent["color"],
            "has_tool": "tool_func" in agent
        }
        clean_roster.append(clean_agent)
    
    return {"agents": clean_roster, "total": len(clean_roster)}


@router.get("/roster/{agent_id}")
async def get_agent(agent_id: str):
    """Get specific agent details."""
    agent = AgentFactory.get_agent_by_id(agent_id)
    
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")
    
    return {
        "id": agent["id"],
        "name": agent["name"],
        "role": agent["role"],
        "color": agent["color"],
        "system_prompt": agent["system_prompt"],
        "has_tool": "tool_func" in agent
    }


@router.post("/debate", status_code=202)
async def start_council_debate(request: AgentDebateRequest):
    """
    Kick off a standalone Council of Experts debate over an arbitrary
    dispatch plan, for testing/demoing the council in isolation — this is
    NOT part of the real dispatch decision path (see
    POST /orders/{id}/dispatch for that; it never calls this).

    Returns immediately with a job id; the debate itself runs on a
    background thread via run_in_executor so it never blocks the event
    loop (up to ~80 LLM calls, tens of seconds to minutes). Poll
    GET /debate/{job_id} for the result.
    """
    import asyncio

    job_id = uuid.uuid4().hex[:12]
    _debate_jobs[job_id] = {"status": "RUNNING", "result": None, "error": None}

    async def _run() -> None:
        try:
            from aerofleet.agents.council import CouncilOfExperts

            loop = asyncio.get_event_loop()
            council = await loop.run_in_executor(None, CouncilOfExperts)
            final_plan, transcript = await loop.run_in_executor(
                None,
                lambda: council.run_grand_debate(
                    dispatch_plan=request.dispatch_plan, chat_history=request.chat_history
                ),
            )
            verdict = "APPROVED"
            if transcript:
                verdict_text = transcript[-1].get("text", "")
                if "reject" in verdict_text.lower() or "veto" in verdict_text.lower():
                    verdict = "REJECTED"
                elif "concern" in verdict_text.lower() or "warning" in verdict_text.lower():
                    verdict = "APPROVED_WITH_CONCERNS"
            _debate_jobs[job_id] = {
                "status": "READY",
                "result": {"final_plan": final_plan, "transcript": transcript, "verdict": verdict},
                "error": None,
            }
            logger.info(f"[debate:{job_id}] Complete: {verdict}")
        except Exception as exc:
            logger.error(f"[debate:{job_id}] Failed: {exc}")
            _debate_jobs[job_id] = {"status": "FAILED", "result": None, "error": str(exc)}

    asyncio.create_task(_run())
    logger.info(f"[debate:{job_id}] Started (async, off the event loop)")
    return {"job_id": job_id, "status": "RUNNING"}


@router.get("/debate/{job_id}")
async def get_council_debate(job_id: str):
    """Poll a standalone debate started via POST /debate."""
    job = _debate_jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Debate job '{job_id}' not found")
    return {"job_id": job_id, **job}
