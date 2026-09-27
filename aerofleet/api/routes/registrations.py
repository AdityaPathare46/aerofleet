"""Drone registration (DGCA Digital Sky UIN) — see aerofleet/fleet/registration.py."""
from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from aerofleet.api.routes.auth import get_current_active_user, get_current_operator_user, get_db
from aerofleet.data.models.models import DroneRegistration, User
from aerofleet.fleet import registration as reg

router = APIRouter()


class UinBody(BaseModel):
    uin: str = Field(..., max_length=40)


class VerifyBody(BaseModel):
    note: str = Field(..., min_length=3, max_length=500)


@router.get("/")
async def list_registrations(user: User = Depends(get_current_active_user), db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    return [reg.to_dict(r, r.drone_id) for r in db.query(DroneRegistration).order_by(DroneRegistration.drone_id).all()]


@router.get("/{drone_id}")
async def get_registration(drone_id: str, user: User = Depends(get_current_active_user), db: Session = Depends(get_db)) -> Dict[str, Any]:
    return reg.to_dict(reg.get(db, drone_id), drone_id)


@router.put("/{drone_id}")
async def record_uin(drone_id: str, body: UinBody, user: User = Depends(get_current_operator_user),
                     db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Record (or change) the drone's UIN. Changing it resets VERIFIED to RECORDED."""
    try:
        return reg.to_dict(reg.record(db, drone_id, body.uin, user.username), drone_id)
    except reg.RegistrationError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post("/{drone_id}/verify")
async def verify_uin(drone_id: str, body: VerifyBody, user: User = Depends(get_current_operator_user),
                     db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Operator attestation that the UIN was checked on Digital Sky for this airframe (AeroFleet can't
    check it itself). Who, when and how are stored with it."""
    try:
        return reg.to_dict(reg.verify(db, drone_id, user.username, body.note), drone_id)
    except reg.RegistrationError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.delete("/{drone_id}")
async def delete_registration(drone_id: str, user: User = Depends(get_current_operator_user),
                              db: Session = Depends(get_db)) -> Dict[str, Any]:
    return {"deleted": reg.remove(db, drone_id)}
