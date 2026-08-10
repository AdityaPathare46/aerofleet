"""Fleet-level CBF threshold policy proposals — council-drafted, slow
cadence (see aerofleet/agents/policy_review_worker.py), always human-gated.

Approving a proposal requires the same operator authority bar as arming a
drone (aerofleet/api/routes/hardware.py) — changing a safety threshold that
every future dispatch in a city will be checked against is not a lower-
stakes action than commanding one drone.
"""
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from aerofleet.api.routes.auth import get_current_active_user, get_current_operator_user
from aerofleet.api.schemas import PolicyProposalResponse, PolicyReviewDecision
from aerofleet.data.database import get_db_session
from aerofleet.data.models.models import PolicyProposal, User
from aerofleet.utils.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()


def get_db():
    with get_db_session() as db:
        yield db


@router.get("/proposals", response_model=List[PolicyProposalResponse])
async def list_proposals(
    city: Optional[str] = None,
    status: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    query = db.query(PolicyProposal)
    if city:
        query = query.filter(PolicyProposal.city == city.lower())
    if status:
        query = query.filter(PolicyProposal.status == status)
    return query.order_by(PolicyProposal.created_at.desc()).limit(200).all()


@router.get("/proposals/{proposal_id}", response_model=PolicyProposalResponse)
async def get_proposal(
    proposal_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    proposal = db.query(PolicyProposal).filter(PolicyProposal.proposal_id == proposal_id).first()
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")
    return proposal


@router.post("/proposals/{proposal_id}/approve", response_model=PolicyProposalResponse)
async def approve_proposal(
    proposal_id: str,
    decision: PolicyReviewDecision = PolicyReviewDecision(),
    current_user: User = Depends(get_current_operator_user),
    db: Session = Depends(get_db),
):
    proposal = db.query(PolicyProposal).filter(PolicyProposal.proposal_id == proposal_id).first()
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")
    if proposal.status != "PENDING_REVIEW":
        raise HTTPException(status_code=409, detail=f"Proposal is already {proposal.status}")

    proposal.status = "APPROVED"
    proposal.reviewed_by = current_user.username
    proposal.reviewed_at = datetime.utcnow()
    db.commit()
    db.refresh(proposal)

    from aerofleet.safety.policy_store import invalidate_policy_cache

    invalidate_policy_cache(proposal.city)
    logger.warning(
        f"[{proposal.city}] Policy proposal {proposal_id} APPROVED by {current_user.username}: "
        f"{proposal.proposed_changes}"
    )
    return proposal


@router.post("/proposals/{proposal_id}/reject", response_model=PolicyProposalResponse)
async def reject_proposal(
    proposal_id: str,
    decision: PolicyReviewDecision = PolicyReviewDecision(),
    current_user: User = Depends(get_current_operator_user),
    db: Session = Depends(get_db),
):
    proposal = db.query(PolicyProposal).filter(PolicyProposal.proposal_id == proposal_id).first()
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")
    if proposal.status != "PENDING_REVIEW":
        raise HTTPException(status_code=409, detail=f"Proposal is already {proposal.status}")

    proposal.status = "REJECTED"
    proposal.reviewed_by = current_user.username
    proposal.reviewed_at = datetime.utcnow()
    db.commit()
    db.refresh(proposal)

    logger.info(f"[{proposal.city}] Policy proposal {proposal_id} rejected by {current_user.username}")
    return proposal


@router.post("/trigger-review")
async def trigger_review(
    city: Optional[str] = Query(None, description="Limit to one city; default reviews every active city"),
    current_user: User = Depends(get_current_operator_user),
):
    """Manually fire a policy review cycle now, instead of waiting for the
    background worker's slow cadence — for demos and testing. Runs the
    council consultation off the event loop, same as the scheduled path."""
    from aerofleet.agents.policy_review_worker import get_policy_review_worker

    created = await get_policy_review_worker().run_review_cycle(cities=[city] if city else None)
    return {"proposals_created": created}
