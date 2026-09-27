"""Drone registration (DGCA Digital Sky UIN) — the registry every compliance check reads.

Statuses, in order of what AeroFleet actually knows:
  NONE      no UIN on file for this drone
  RECORDED  an operator entered a UIN (format-checked only)
  VERIFIED  an operator attested they checked the UIN on Digital Sky for this airframe

AeroFleet never claims a UIN is valid on Digital Sky by itself: DGCA offers no public lookup API.
Changing the UIN resets VERIFIED to RECORDED, since the attestation was about the old number.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from aerofleet.data.models.models import DroneRegistration

NONE, RECORDED, VERIFIED = "NONE", "RECORDED", "VERIFIED"

# Digital Sky's exact UIN format isn't published in a form we could confirm, so this only rejects
# things that clearly aren't an identifier (spaces, punctuation, too short/long). Stored upper-case.
_UIN_RE = re.compile(r"^[A-Z0-9][A-Z0-9/\-]{4,38}[A-Z0-9]$")


class RegistrationError(ValueError):
    pass


def normalise_uin(uin: str) -> str:
    value = (uin or "").strip().upper()
    if not _UIN_RE.match(value):
        raise RegistrationError("A UIN is 6–40 letters/digits (hyphens or slashes allowed inside), as issued by Digital Sky.")
    return value


def get(db: Session, drone_id: str) -> Optional[DroneRegistration]:
    return db.query(DroneRegistration).filter(DroneRegistration.drone_id == drone_id).first()


def status_of(reg: Optional[DroneRegistration]) -> str:
    return reg.status if reg else NONE


def to_dict(reg: Optional[DroneRegistration], drone_id: str) -> Dict[str, Any]:
    if reg is None:
        return {"drone_id": drone_id, "uin": None, "status": NONE}
    return {
        "drone_id": reg.drone_id, "uin": reg.uin, "status": reg.status,
        "recorded_by": reg.recorded_by, "recorded_at": reg.recorded_at.isoformat() if reg.recorded_at else None,
        "verified_by": reg.verified_by, "verified_at": reg.verified_at.isoformat() if reg.verified_at else None,
        "verification_note": reg.verification_note,
    }


def record(db: Session, drone_id: str, uin: str, by: str) -> DroneRegistration:
    value = normalise_uin(uin)
    reg = get(db, drone_id)
    if reg is None:
        reg = DroneRegistration(drone_id=drone_id, uin=value, status=RECORDED, recorded_by=by, recorded_at=datetime.utcnow())
        db.add(reg)
    elif reg.uin != value:
        reg.uin, reg.status, reg.recorded_by, reg.recorded_at = value, RECORDED, by, datetime.utcnow()
        reg.verified_by = reg.verified_at = reg.verification_note = None
    db.commit()
    db.refresh(reg)
    return reg


def verify(db: Session, drone_id: str, by: str, note: str) -> DroneRegistration:
    reg = get(db, drone_id)
    if reg is None:
        raise RegistrationError("Record a UIN for this drone before verifying it.")
    if not (note or "").strip():
        raise RegistrationError("Say how it was verified (e.g. 'checked on Digital Sky, airframe serial matches').")
    reg.status, reg.verified_by, reg.verified_at, reg.verification_note = VERIFIED, by, datetime.utcnow(), note.strip()
    db.commit()
    db.refresh(reg)
    return reg


def remove(db: Session, drone_id: str) -> bool:
    reg = get(db, drone_id)
    if reg is None:
        return False
    db.delete(reg)
    db.commit()
    return True
