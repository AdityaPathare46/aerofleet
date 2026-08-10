"""Fleet Incident Forensics — read access to auto-triggered multi-agent
investigations, plus promoting a recommended policy change into the
existing, human-gated PolicyProposal review flow (aerofleet/api/routes
/policy.py). Nothing here ever applies a threshold change directly — an
incident's recommended_policy_change is only ever a suggestion until an
operator explicitly promotes it, and then still only takes effect once a
*second* operator approval (or the same one, their call) goes through the
normal policy-proposal approve endpoint.
"""
import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from aerofleet.api.routes.auth import get_current_active_user, get_current_operator_user
from aerofleet.api.schemas import IncidentReportResponse
from aerofleet.data.database import get_db_session
from aerofleet.data.models.models import IncidentReport, PolicyProposal, User
from aerofleet.utils.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()


def get_db():
    with get_db_session() as db:
        yield db


@router.get("/", response_model=List[IncidentReportResponse])
async def list_incidents(
    city: Optional[str] = None,
    status: Optional[str] = None,
    trigger_type: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    query = db.query(IncidentReport)
    if city:
        query = query.filter(IncidentReport.city == city.lower())
    if status:
        query = query.filter(IncidentReport.status == status)
    if trigger_type:
        query = query.filter(IncidentReport.trigger_type == trigger_type)
    return query.order_by(IncidentReport.created_at.desc()).limit(200).all()


@router.get("/{incident_id}", response_model=IncidentReportResponse)
async def get_incident(
    incident_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    incident = db.query(IncidentReport).filter(IncidentReport.incident_id == incident_id).first()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    return incident


@router.post("/{incident_id}/promote-to-policy-proposal", response_model=IncidentReportResponse)
async def promote_to_policy_proposal(
    incident_id: str,
    current_user: User = Depends(get_current_operator_user),
    db: Session = Depends(get_db),
):
    """Turns an incident's recommended_policy_change into a real, pending
    PolicyProposal — reusing the exact review flow already built in Phase
    AC (aerofleet/api/routes/policy.py's approve/reject), rather than
    inventing a second, parallel way for a threshold to change. Requires
    the same operator authority as approving a proposal directly."""
    incident = db.query(IncidentReport).filter(IncidentReport.incident_id == incident_id).first()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    if incident.status != "READY":
        raise HTTPException(status_code=409, detail=f"Incident investigation is not complete yet (status={incident.status})")
    if not incident.recommended_policy_change:
        raise HTTPException(status_code=409, detail="This incident's investigation made no policy recommendation")
    if incident.promoted_policy_proposal_id:
        raise HTTPException(status_code=409, detail=f"Already promoted as {incident.promoted_policy_proposal_id}")

    proposal_id = f"POL-{uuid.uuid4().hex[:8].upper()}"
    rationale = (
        f"Promoted from incident {incident.incident_id} ({incident.trigger_type}) by {current_user.username}. "
        f"Root cause: {incident.root_cause_summary or 'n/a'}. "
        f"Systemic factor: {incident.systemic_factor_note or 'n/a'}."
    )
    db.add(PolicyProposal(
        proposal_id=proposal_id,
        city=incident.city,
        proposed_changes=incident.recommended_policy_change,
        rationale=rationale,
        stats_snapshot={"promoted_from_incident": incident.incident_id},
        status="PENDING_REVIEW",
        created_at=datetime.utcnow(),
    ))
    incident.promoted_policy_proposal_id = proposal_id
    db.commit()
    db.refresh(incident)

    logger.warning(f"[{incident_id}] Promoted to policy proposal {proposal_id} by {current_user.username}")
    return incident
