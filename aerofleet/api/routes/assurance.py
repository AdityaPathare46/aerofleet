"""AeroFleet 2.0 ground-side assurance: parameter-file upload, fleet baseline, configuration drift.

Everything here is deterministic (aerofleet/assurance/); no drone is contacted and no model is called.
Reading needs a signed-in user; setting a baseline or approving a change needs an operator.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from aerofleet.api.routes.auth import get_current_active_user, get_current_operator_user, get_db
from aerofleet.assurance.drift import drift_report
from aerofleet.assurance.static_checks import checks_from_params
from aerofleet.assurance.params import MAX_BYTES, ParamFile, ParamFileError, parse_param_bytes
from aerofleet.data.models.models import FleetBaseline, ParamSnapshot, User

router = APIRouter()
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_\-]{0,49}$")


def _check_id(value: str, what: str) -> str:
    if not _ID.match(value):
        raise HTTPException(status_code=422, detail=f"{what} must be 1-50 letters, digits, '-' or '_'")
    return value


async def _read(file: UploadFile) -> ParamFile:
    data = await file.read(MAX_BYTES + 1)
    try:
        return parse_param_bytes(data)
    except ParamFileError as e:
        raise HTTPException(status_code=422, detail=str(e))


def _approved_values(baseline: Optional[FleetBaseline]) -> Dict[str, float]:
    return {k: v["value"] for k, v in ((baseline.approved or {}) if baseline else {}).items()}


def _snapshots(db: Session, fleet: str, drone_id: str, limit: int = 2) -> List[ParamSnapshot]:
    return (db.query(ParamSnapshot).filter(ParamSnapshot.fleet == fleet, ParamSnapshot.drone_id == drone_id)
            .order_by(ParamSnapshot.id.desc()).limit(limit).all())


def _drift(db: Session, fleet: str, drone_id: str) -> Dict[str, Any]:
    snaps = _snapshots(db, fleet, drone_id)
    if not snaps:
        raise HTTPException(status_code=404, detail=f"No parameter file uploaded for drone '{drone_id}' in fleet '{fleet}'")
    baseline = db.get(FleetBaseline, fleet)
    report = drift_report(snaps[0].params, baseline.params if baseline else None,
                          snaps[1].params if len(snaps) > 1 else None, _approved_values(baseline))
    report.update({"drone_id": drone_id, "fleet": fleet, "snapshot_id": snaps[0].id, "filename": snaps[0].filename,
                   "uploaded_by": snaps[0].uploaded_by, "uploaded_at": snaps[0].created_at.isoformat(),
                   "baseline_set_at": baseline.set_at.isoformat() if baseline else None})
    return report


@router.post("/fleets/{fleet}/baseline")
async def set_baseline(fleet: str, file: UploadFile = File(...), user: User = Depends(get_current_operator_user),
                       db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Set (or replace) the fleet's approved configuration from a parameter file. Replacing it clears approvals."""
    _check_id(fleet, "Fleet")
    parsed = await _read(file)
    row = db.get(FleetBaseline, fleet) or FleetBaseline(fleet=fleet)
    row.params, row.approved, row.source = parsed.params, {}, (file.filename or "")[:200]
    row.set_by, row.set_at = user.username, datetime.utcnow()
    db.add(row)
    db.commit()
    return {"fleet": fleet, "param_count": len(parsed.params), "format": parsed.format, "rejected": len(parsed.rejected),
            "set_by": row.set_by, "set_at": row.set_at.isoformat()}


@router.get("/fleets/{fleet}/baseline")
async def get_baseline(fleet: str, user: User = Depends(get_current_active_user), db: Session = Depends(get_db)) -> Dict[str, Any]:
    row = db.get(FleetBaseline, fleet)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Fleet '{fleet}' has no baseline yet")
    return {"fleet": fleet, "param_count": len(row.params), "source": row.source, "set_by": row.set_by,
            "set_at": row.set_at.isoformat(), "approved": row.approved or {}, "params": row.params}


class Approval(BaseModel):
    name: str = Field(..., max_length=32)
    value: float
    note: str = Field(..., min_length=3, max_length=300)


@router.post("/fleets/{fleet}/approvals")
async def approve_change(fleet: str, body: Approval, user: User = Depends(get_current_operator_user),
                         db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Sign off one exact value for one parameter across the fleet (who, when and why are kept)."""
    row = db.get(FleetBaseline, fleet)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Fleet '{fleet}' has no baseline yet")
    approved = dict(row.approved or {})
    approved[body.name.upper()] = {"value": body.value, "by": user.username, "at": datetime.utcnow().isoformat(), "note": body.note}
    row.approved = approved
    db.commit()
    return {"fleet": fleet, "approved": approved}


@router.post("/fleets/{fleet}/drones/{drone_id}/params")
async def upload_params(fleet: str, drone_id: str, file: UploadFile = File(...),
                        user: User = Depends(get_current_active_user), db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Upload a drone's parameter file; returns its drift against the baseline and its previous upload."""
    _check_id(fleet, "Fleet"), _check_id(drone_id, "Drone id")
    parsed = await _read(file)
    db.add(ParamSnapshot(drone_id=drone_id, fleet=fleet, params=parsed.params, file_format=parsed.format,
                         filename=(file.filename or "")[:200], uploaded_by=user.username))
    db.commit()
    report = _drift(db, fleet, drone_id)
    report["file"] = {"format": parsed.format, "duplicates": parsed.duplicates,
                      "rejected": [{"line": n, "reason": r} for n, r in parsed.rejected]}
    return report


@router.get("/fleets/{fleet}/drones/{drone_id}/drift")
async def get_drift(fleet: str, drone_id: str, user: User = Depends(get_current_active_user),
                    db: Session = Depends(get_db)) -> Dict[str, Any]:
    return _drift(db, fleet, drone_id)


@router.get("/fleets/{fleet}/drones/{drone_id}/checks")
async def get_checks(fleet: str, drone_id: str, user: User = Depends(get_current_active_user),
                     db: Session = Depends(get_db)) -> Dict[str, Any]:
    """The flight-controller compliance rules run on the drone's latest uploaded parameter file."""
    from aerofleet.fleet import registration
    from aerofleet.hardware.compliance_rules import InspectionContext

    snaps = _snapshots(db, fleet, drone_id, limit=1)
    if not snaps:
        raise HTTPException(status_code=404, detail=f"No parameter file uploaded for drone '{drone_id}' in fleet '{fleet}'")
    reg = registration.get(db, drone_id)
    ctx = InspectionContext(
        bench_mode=True, drone_id=drone_id, registry_uin=reg.uin if reg else None, uin_status=registration.status_of(reg),
        uin_verified_by=reg.verified_by if reg else None,
        uin_verified_at=reg.verified_at.isoformat() if reg and reg.verified_at else None)
    report = checks_from_params(snaps[0].params, ctx)
    report.update({"drone_id": drone_id, "fleet": fleet, "snapshot_id": snaps[0].id, "uploaded_at": snaps[0].created_at.isoformat()})
    return report


@router.get("/fleets/{fleet}/drift")
async def fleet_drift(fleet: str, user: User = Depends(get_current_active_user), db: Session = Depends(get_db)) -> Dict[str, Any]:
    """One row per drone with a parameter file: its verdict and open change counts."""
    ids = [r[0] for r in db.query(ParamSnapshot.drone_id).filter(ParamSnapshot.fleet == fleet).distinct().all()]
    rows = []
    for drone_id in sorted(ids):
        r = _drift(db, fleet, drone_id)
        ref = r[r["decided_by"]] if r["decided_by"] else None
        rows.append({"drone_id": drone_id, "verdict": r["verdict"], "counts": ref["counts"] if ref else None,
                     "uploaded_at": r["uploaded_at"]})
    verdicts = [r["verdict"] for r in rows]
    return {"fleet": fleet, "has_baseline": db.get(FleetBaseline, fleet) is not None, "drones": rows,
            "summary": {v: verdicts.count(v) for v in ("BLOCK", "REVIEW", "OK", "NO_REFERENCE")}}
