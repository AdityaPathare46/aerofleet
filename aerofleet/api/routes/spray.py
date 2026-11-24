"""Spray register: the SOP Spray Monitoring Form for each spraying flight, and the seven-day deadline.

The form, its checks and the deadline live in aerofleet/assurance/spray_form.py (deterministic, no model).
Every save, every "not a spray flight" mark and every submission is signed into the record.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from aerofleet.api.routes.auth import get_current_active_user, get_db
from aerofleet.assurance import ledger
from aerofleet.assurance import spray_form as sf
from aerofleet.data.models.models import DroneRegistration, FlightReview, MaintenanceEntry, SprayForm, User

router = APIRouter()
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_\-]{0,49}$")
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_DATETIME = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$")
KINDS = {f[0]: (f[3], f[4]) for f in sf.ALL_FIELDS}
MAX_PRINT = 6                                   # the printed form has six columns


def _fleet(fleet: str) -> str:
    if not _ID.match(fleet):
        raise HTTPException(status_code=422, detail="Fleet must be 1-50 letters, digits, '-' or '_'")
    return fleet


def _valid_day(s: str) -> bool:
    try:
        date.fromisoformat(s)
        return True
    except ValueError:
        return False


def _clean(values: Dict[str, Any]) -> Dict[str, Any]:
    """Keep only the form's own fields, each in the form's type; refuse anything else with a plain message."""
    out: Dict[str, Any] = {}
    for code, v in values.items():
        if code not in KINDS:
            raise HTTPException(status_code=422, detail=f"Unknown field {code}")
        kind, options = KINDS[code]
        if v is None or v == "" or v == []:
            out[code] = None
            continue
        if kind == "number":
            try:
                v = float(v)
            except (TypeError, ValueError):
                raise HTTPException(status_code=422, detail=f"{code} must be a number")
            if v != v or abs(v) > 1e6:
                raise HTTPException(status_code=422, detail=f"{code} is out of range")
        elif kind == "date":
            if not (isinstance(v, str) and _DATE.match(v) and _valid_day(v)):
                raise HTTPException(status_code=422, detail=f"{code} must be a date YYYY-MM-DD")
        elif kind == "datetime":
            if not (isinstance(v, str) and _DATETIME.match(v[:16]) and _valid_day(v[:10])):
                raise HTTPException(status_code=422, detail=f"{code} must be a date and time YYYY-MM-DDTHH:MM")
            v = v[:16]
        elif kind == "yesno":
            if v not in ("Yes", "No"):
                raise HTTPException(status_code=422, detail=f"{code} must be Yes or No")
        elif kind == "choice":
            if v not in (options or []):
                raise HTTPException(status_code=422, detail=f"{code} must be one of: {', '.join(options or [])}")
        elif kind == "multi":
            if not (isinstance(v, list) and all(x in (options or []) for x in v)):
                raise HTTPException(status_code=422, detail=f"{code} must be a list from: {', '.join(options or [])}")
            v = [x for x in (options or []) if x in v]
        else:
            if not isinstance(v, str):
                raise HTTPException(status_code=422, detail=f"{code} must be text")
            v = v.strip()[:300]
        out[code] = v
    return out


def _review(db: Session, fleet: str, review_id: int) -> FlightReview:
    r = db.get(FlightReview, review_id)
    if r is None or r.fleet != fleet:
        raise HTTPException(status_code=404, detail=f"No reviewed flight #{review_id} in fleet '{fleet}'")
    return r


def _last_calibration(db: Session, fleet: str, drone_id: str, day: Optional[str]) -> Optional[str]:
    q = (db.query(MaintenanceEntry).filter(MaintenanceEntry.fleet == fleet, MaintenanceEntry.drone_id == drone_id,
                                           MaintenanceEntry.action.in_(sf.CALIBRATION_ACTIONS)))
    rows = [m for m in q.all() if not day or m.done_at.date().isoformat() <= day]
    return max(rows, key=lambda m: m.done_at).done_at.date().isoformat() if rows else None


def _previous(forms: List[SprayForm], drone_id: str, review_id: int) -> Optional[Dict[str, Any]]:
    """The values of this drone's most recently saved other form (for fields that rarely change)."""
    mine = [f for f in forms if f.drone_id == drone_id and f.review_id != review_id and not f.not_spray and f.values]
    return max(mine, key=lambda f: f.updated_at).values if mine else None


def _form(db: Session, r: FlightReview, saved: Optional[SprayForm], others: List[SprayForm], as_of: date) -> Dict[str, Any]:
    log = sf.log_values(r.report or {}, r.created_at.isoformat())
    pre = sf.defaults(log, _previous(others, r.drone_id, r.id), _last_calibration(db, r.fleet, r.drone_id, log.get("1-1")))
    stored = (saved.values if saved else None) or {}
    values = {code: p["value"] for code, p in pre.items()}
    values.update({k: v for k, v in stored.items() if k in sf.CODES})
    sources = {code: (p["source"] if stored.get(code, p["value"]) == p["value"] else "entered") for code, p in pre.items()}
    sources.update({k: "entered" for k, v in stored.items() if k not in pre and v not in (None, "", [])})
    reg = db.get(DroneRegistration, r.drone_id)
    found = sf.checks(values, log, reg.uin if reg else None)
    st = sf.status(values, found, saved.submitted_on if saved else None, as_of)
    return {"review_id": r.id, "drone_id": r.drone_id, "fleet": r.fleet, "log_name": r.log_name, "values": values,
            "sources": sources, "log": log, "checks": found, "status": st, "uin": reg.uin if reg else None,
            "not_spray": bool(saved and saved.not_spray), "submitted_on": saved and saved.submitted_on,
            "submitted_via": saved and saved.submitted_via, "updated_by": saved and saved.updated_by,
            "updated_at": saved and saved.updated_at.isoformat(), "review_sha256": ledger.payload_hash(r.report)}


def _as_of(s: Optional[str]) -> date:
    if not s:
        return datetime.now(timezone.utc).date()
    if not (_DATE.match(s) and _valid_day(s)):
        raise HTTPException(status_code=422, detail="as_of must be YYYY-MM-DD")
    return date.fromisoformat(s)


def _all(db: Session, fleet: str, as_of: date) -> List[Dict[str, Any]]:
    forms = db.query(SprayForm).filter(SprayForm.fleet == fleet).all()
    by_id = {f.review_id: f for f in forms}
    reviews = db.query(FlightReview).filter(FlightReview.fleet == fleet).order_by(FlightReview.id.desc()).limit(2000).all()
    return [_form(db, r, by_id.get(r.id), forms, as_of) for r in reviews]


@router.get("/spray-form/fields")
async def spray_fields(user: User = Depends(get_current_active_user)) -> Dict[str, Any]:
    """The form's fields in order, as the SOP's Annexure-I lists them, plus the two SOP pre-spray items."""
    return {"source": sf.SOURCE, "deadline_days": sf.DEADLINE_DAYS,
            "fields": [{"code": c, "label": l, "section": s, "kind": k, "options": o, "required": q}
                       for c, l, s, k, o, q in sf.ALL_FIELDS]}


@router.get("/fleets/{fleet}/spray-register")
async def spray_register(fleet: str, as_of: Optional[str] = Query(None, description="YYYY-MM-DD; default today (UTC)"),
                         user: User = Depends(get_current_active_user), db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Every reviewed flight of the fleet with its form's state and days left; flights marked as not spraying are
    listed separately."""
    _fleet(fleet)
    day = _as_of(as_of)
    forms = _all(db, fleet, day)
    rows = [{"review_id": f["review_id"], "drone_id": f["drone_id"], "uin": f["uin"], "log_name": f["log_name"],
             "date": f["values"].get("1-1"), "location": f["values"].get("1-2"), "product": f["values"].get("3-1"),
             "crop": f["values"].get("2-3"), **f["status"], "submitted_on": f["submitted_on"],
             "not_spray": f["not_spray"]} for f in forms]
    spray = sorted([r for r in rows if not r["not_spray"]], key=lambda r: (sf.ORDER[r["state"]], r["due"] or "", r["drone_id"]))
    return {"fleet": fleet, "as_of": day.isoformat(), "deadline_days": sf.DEADLINE_DAYS, "source": sf.SOURCE,
            "counts": {k: sum(r["state"] == k for r in spray) for k in sf.ORDER},
            "rows": spray, "not_spray": [r for r in rows if r["not_spray"]],
            "latest_flight": max((r["date"] for r in spray if r["date"]), default=None)}


@router.get("/fleets/{fleet}/spray-forms/{review_id}")
async def get_spray_form(fleet: str, review_id: int, as_of: Optional[str] = Query(None),
                         user: User = Depends(get_current_active_user), db: Session = Depends(get_db)) -> Dict[str, Any]:
    _fleet(fleet)
    r = _review(db, fleet, review_id)
    return _form(db, r, db.get(SprayForm, review_id), db.query(SprayForm).filter(SprayForm.fleet == fleet).all(), _as_of(as_of))


class FormIn(BaseModel):
    values: Dict[str, Any] = Field(default_factory=dict)


def _save(db: Session, r: FlightReview, user: User, **changes: Any) -> SprayForm:
    row = db.get(SprayForm, r.id) or SprayForm(review_id=r.id, fleet=r.fleet, drone_id=r.drone_id, values={}, not_spray=False)
    for k, v in changes.items():
        setattr(row, k, v)
    row.updated_by, row.updated_at = user.username, datetime.utcnow()
    db.add(row)
    db.flush()
    ledger.append(db, "spray_form", f"{r.fleet}/review/{r.id}",
                  {"review_id": r.id, "review_sha256": ledger.payload_hash(r.report), "values": row.values,
                   "not_spray": row.not_spray, "submitted_on": row.submitted_on, "submitted_via": row.submitted_via},
                  user.username)
    db.commit()
    return row


@router.put("/fleets/{fleet}/spray-forms/{review_id}")
async def put_spray_form(fleet: str, review_id: int, body: FormIn, as_of: Optional[str] = Query(None),
                         user: User = Depends(get_current_active_user), db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Save the form (all fields sent are stored; unsent ones keep their pre-filled values). Signed into the record."""
    _fleet(fleet)
    r = _review(db, fleet, review_id)
    saved = db.get(SprayForm, review_id)
    if saved and saved.submitted_on:
        raise HTTPException(status_code=409, detail="This form was already submitted; the submitted version stays as it was")
    values = {**((saved.values if saved else None) or {}), **_clean(body.values)}
    _save(db, r, user, values=values)
    return _form(db, r, db.get(SprayForm, review_id), db.query(SprayForm).filter(SprayForm.fleet == fleet).all(), _as_of(as_of))


class NotSprayIn(BaseModel):
    not_spray: bool


@router.post("/fleets/{fleet}/spray-forms/{review_id}/not-spray")
async def mark_not_spray(fleet: str, review_id: int, body: NotSprayIn, user: User = Depends(get_current_active_user),
                         db: Session = Depends(get_db)) -> Dict[str, Any]:
    """A test, survey or training flight needs no spray form. The mark is signed, so it cannot be used quietly."""
    _fleet(fleet)
    r = _review(db, fleet, review_id)
    saved = db.get(SprayForm, review_id)
    if saved and saved.submitted_on:
        raise HTTPException(status_code=409, detail="This form was already submitted")
    _save(db, r, user, not_spray=body.not_spray)
    return {"review_id": review_id, "not_spray": body.not_spray}


class SubmittedIn(BaseModel):
    submitted_on: str = Field(..., description="YYYY-MM-DD")
    via: str = Field(..., max_length=100, description="For example: email to the address in the CIB&RC guidelines, or the portal")


@router.post("/fleets/{fleet}/spray-forms/{review_id}/submitted")
async def mark_submitted(fleet: str, review_id: int, body: SubmittedIn, user: User = Depends(get_current_active_user),
                         db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Record that the operator sent the form. AeroFleet does not send it; it records when and how it was sent."""
    _fleet(fleet)
    r = _review(db, fleet, review_id)
    if not (_DATE.match(body.submitted_on) and _valid_day(body.submitted_on)):
        raise HTTPException(status_code=422, detail="submitted_on must be YYYY-MM-DD")
    if date.fromisoformat(body.submitted_on) > datetime.now(timezone.utc).date():
        raise HTTPException(status_code=422, detail="The submission date cannot be in the future")
    if not body.via.strip():
        raise HTTPException(status_code=422, detail="Say how it was sent")
    forms = db.query(SprayForm).filter(SprayForm.fleet == fleet).all()
    saved = db.get(SprayForm, review_id)
    if saved and saved.not_spray:
        raise HTTPException(status_code=409, detail="This flight is marked as not a spray flight")
    if saved and saved.submitted_on:
        raise HTTPException(status_code=409, detail="Already recorded as submitted")
    current = _form(db, r, saved, forms, date.fromisoformat(body.submitted_on))
    missing = [c["text"] for c in current["checks"] if c["level"] == "missing"]
    if missing:
        raise HTTPException(status_code=422, detail=f"Fill the form first: {len(missing)} fields are empty ({missing[0]} ...)")
    if current["values"].get("1-1") and body.submitted_on < current["values"]["1-1"]:
        raise HTTPException(status_code=422, detail="The form cannot be submitted before the spraying date")
    # Freeze the pre-filled values too, so the submitted version no longer depends on the log, logbook or other forms.
    _save(db, r, user, values=current["values"], submitted_on=body.submitted_on, submitted_via=body.via.strip()[:100])
    return _form(db, r, db.get(SprayForm, review_id), forms, _as_of(None))


@router.get("/fleets/{fleet}/spray-forms-print", response_class=HTMLResponse)
async def print_forms(fleet: str, ids: str = Query(..., description="Comma-separated review ids, at most 6"),
                      user: User = Depends(get_current_active_user), db: Session = Depends(get_db)) -> HTMLResponse:
    """The filled Annexure-I as a printable page, one column per flight (print to PDF from the browser)."""
    _fleet(fleet)
    try:
        wanted = [int(x) for x in ids.split(",") if x.strip()]
    except ValueError:
        raise HTTPException(status_code=422, detail="ids must be numbers")
    if not 1 <= len(wanted) <= MAX_PRINT:
        raise HTTPException(status_code=422, detail=f"Choose 1 to {MAX_PRINT} flights (the form has {MAX_PRINT} columns)")
    forms = db.query(SprayForm).filter(SprayForm.fleet == fleet).all()
    out = [_form(db, _review(db, fleet, i), db.get(SprayForm, i), forms, _as_of(None)) for i in wanted]
    return HTMLResponse(sf.print_html(out, fleet), headers={"Cache-Control": "no-store"})


@router.get("/fleets/{fleet}/spray-register.csv")
async def register_csv(fleet: str, user: User = Depends(get_current_active_user), db: Session = Depends(get_db)) -> Response:
    """Every spray form of the fleet, one row per flight, one column per field code."""
    import csv
    import io

    _fleet(fleet)
    forms = [f for f in _all(db, fleet, _as_of(None)) if not f["not_spray"]]
    cols = ["review_id", "drone_id", "uin", "state", "due", "submitted_on", "submitted_via"] + [c for c, *_ in sf.ALL_FIELDS] + ["review_sha256"]
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(cols)
    for f in sorted(forms, key=lambda f: (f["values"].get("1-1") or "", f["drone_id"])):
        base = {"review_id": f["review_id"], "drone_id": f["drone_id"], "uin": f["uin"] or "", "state": f["status"]["state"],
                "due": f["status"]["due"] or "", "submitted_on": f["submitted_on"] or "", "submitted_via": f["submitted_via"] or "",
                "review_sha256": f["review_sha256"]}
        w.writerow([base[c] if c in base else sf._show(f["values"].get(c)) for c in cols])
    return Response(buf.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="aerofleet-{fleet}-spray-register.csv"', "Cache-Control": "no-store"})
