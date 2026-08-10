"""Admin panel — list users and grant/revoke is_operator / is_admin
(Phase AI). Before this phase, the only way to make a user an operator (and
thus able to arm/disarm real hardware) was direct SQL against the users
table. Every endpoint here requires get_current_admin_user.
"""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from aerofleet.api.routes.auth import get_current_admin_user, get_db
from aerofleet.api.schemas import UserPermissionsUpdate, UserResponse
from aerofleet.data.models.models import User
from aerofleet.utils.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()


@router.get("/users", response_model=List[UserResponse])
async def list_users(
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin_user),
):
    return db.query(User).order_by(User.id).all()


@router.patch("/users/{user_id}", response_model=UserResponse)
async def update_user_permissions(
    user_id: int,
    body: UserPermissionsUpdate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin_user),
):
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    if body.is_admin is False and user.id == current_admin.id:
        # An admin locking themselves out with no other admin account left
        # is a real, easy-to-hit foot-gun (there's no recovery path short
        # of the same raw-SQL workaround this phase exists to remove) —
        # block self-revocation outright rather than trying to detect
        # "are you the last admin" races.
        raise HTTPException(status_code=400, detail="Cannot revoke your own admin access")

    if body.is_operator is not None:
        user.is_operator = body.is_operator
    if body.is_admin is not None:
        user.is_admin = body.is_admin
    if body.is_active is not None:
        user.is_active = body.is_active

    db.commit()
    db.refresh(user)
    logger.info(f"Admin '{current_admin.username}' updated permissions for '{user.username}': {body.model_dump(exclude_unset=True)}")
    return user
