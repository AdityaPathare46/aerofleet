"""The VR debrief study: which trials a participant sees, in which order, and their answers.

Protocol: research/vr_study/PROTOCOL.md (declared before the first participant). Trials:
aerofleet/assurance/data/vr_study_trials.json (no answers in it; the key stays in research/vr_study/). Answers are
stored as given and judged only by research/vr_study/analyse.py after the last participant.

Counterbalancing: participant number n decides the group, n mod 4:
  0: 2D first with set A, then headset with set B     1: headset first with A, then 2D with B
  2: 2D first with set B, then headset with set A     3: headset first with B, then 2D with A
Trial order within a block is shuffled with a seed made from the participant code and the condition.
"""
from __future__ import annotations

import hashlib
import json
import random
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from aerofleet.api.routes.auth import get_current_active_user, get_db
from aerofleet.data.models.models import User, VrStudyResponse

router = APIRouter()
TRIALS = Path(__file__).resolve().parents[2] / "assurance" / "data" / "vr_study_trials.json"
CODE = re.compile(r"^P\d{2}$")
ANSWERS = {"none", "sideways", "height"}
PREFER = {"2d", "headset", "same"}
GROUPS = [(("2d", "A"), ("headset", "B")), (("headset", "A"), ("2d", "B")),
          (("2d", "B"), ("headset", "A")), (("headset", "B"), ("2d", "A"))]


@lru_cache(maxsize=1)
def _trials() -> Dict[str, Any]:
    return json.loads(TRIALS.read_text())


def _code(p: str) -> str:
    if not CODE.match(p or ""):
        raise HTTPException(status_code=422, detail="Participant code must be P followed by two digits, e.g. P07")
    return p


def plan_for(participant: str) -> List[Dict[str, Any]]:
    n = int(participant[1:])
    blocks = []
    for condition, s in GROUPS[n % 4]:
        trials = list(_trials()["sets"][s])
        seed = int(hashlib.sha256(f"{participant}|{condition}".encode()).hexdigest()[:8], 16)
        random.Random(seed).shuffle(trials)
        blocks.append({"condition": condition, "set": s, "practice": _trials()["sets"]["P"], "trials": trials})
    return blocks


@router.get("/plan/{participant}")
async def study_plan(participant: str, user: User = Depends(get_current_active_user), db: Session = Depends(get_db)) -> Dict[str, Any]:
    """The participant's two blocks in order, and which trials are already answered (so a block can resume)."""
    _code(participant)
    done = {(r.condition, r.trial_id) for r in db.query(VrStudyResponse).filter(VrStudyResponse.participant == participant)}
    return {"participant": participant, "group": int(participant[1:]) % 4, "blocks": plan_for(participant),
            "done": [f"{c}|{t}" for c, t in sorted(done)]}


class ResponseIn(BaseModel):
    participant: str
    condition: str = Field(..., pattern="^(2d|headset|practice-2d|practice-headset|preference)$")
    trial_id: str = Field(..., max_length=8)
    position: int = Field(..., ge=0, le=100)
    answer: str = Field(..., max_length=10)
    ms: Optional[int] = Field(None, ge=0, le=3_600_000)


@router.post("/responses")
async def record_response(body: ResponseIn, user: User = Depends(get_current_active_user), db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Store one answer. A trial is answered once per participant and condition; the first answer counts."""
    _code(body.participant)
    if body.condition == "preference":
        if body.answer not in PREFER:
            raise HTTPException(status_code=422, detail="Preference must be 2d, headset or same")
    elif body.answer not in ANSWERS:
        raise HTTPException(status_code=422, detail="Answer must be none, sideways or height")
    sets = _trials()["sets"]
    if body.condition != "preference" and not any(t["id"] == body.trial_id for s in sets.values() for t in s):
        raise HTTPException(status_code=422, detail="Unknown trial")
    dup = db.query(VrStudyResponse).filter(VrStudyResponse.participant == body.participant, VrStudyResponse.condition == body.condition,
                                           VrStudyResponse.trial_id == body.trial_id).first()
    if dup:
        raise HTTPException(status_code=409, detail="Already answered; the first answer counts")
    db.add(VrStudyResponse(participant=body.participant, condition=body.condition, trial_id=body.trial_id, position=body.position,
                           answer=body.answer, ms=body.ms, recorded_by=user.username))
    db.commit()
    out: Dict[str, Any] = {"recorded": True}
    if body.condition.startswith("practice"):                      # practice only: say whether it was right
        out["correct_answer"] = next(t["answer"] for t in sets["P"] if t["id"] == body.trial_id)
    return out


@router.get("/progress")
async def study_progress(user: User = Depends(get_current_active_user), db: Session = Depends(get_db)) -> Dict[str, Any]:
    """How many answers each participant has given per condition (not whether they were right)."""
    rows: Dict[str, Dict[str, int]] = {}
    for r in db.query(VrStudyResponse).all():
        rows.setdefault(r.participant, {}).setdefault(r.condition, 0)
        rows[r.participant][r.condition] += 1
    return {"participants": rows}
