"""AeroFleet 2.0 ground-side assurance: parameter-file upload, fleet baseline, configuration drift.

Everything here is deterministic (aerofleet/assurance/); no drone is contacted and no model is called.
Reading needs a signed-in user; setting a baseline or approving a change needs an operator.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from aerofleet.api.routes.auth import get_current_active_user, get_current_operator_user, get_db
from aerofleet.assurance import ledger
from aerofleet.assurance.drift import drift_report
from aerofleet.assurance.static_checks import checks_from_params
from aerofleet.assurance.params import MAX_BYTES, ParamFile, ParamFileError, parse_param_bytes
from aerofleet.data.models.models import FleetBaseline, FlightReview, ParamSnapshot, User

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
    entry = ledger.append(db, "baseline", fleet, {"params": parsed.params, "source": row.source}, user.username)
    db.commit()
    return {"fleet": fleet, "param_count": len(parsed.params), "format": parsed.format, "rejected": len(parsed.rejected),
            "set_by": row.set_by, "set_at": row.set_at.isoformat(), "ledger_seq": entry.seq}


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
    entry = ledger.append(db, "approval", fleet, {"name": body.name.upper(), **approved[body.name.upper()]}, user.username)
    db.commit()
    return {"fleet": fleet, "approved": approved, "ledger_seq": entry.seq}


@router.post("/fleets/{fleet}/drones/{drone_id}/params")
async def upload_params(fleet: str, drone_id: str, file: UploadFile = File(...),
                        user: User = Depends(get_current_active_user), db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Upload a drone's parameter file; returns its drift against the baseline and its previous upload."""
    _check_id(fleet, "Fleet"), _check_id(drone_id, "Drone id")
    parsed = await _read(file)
    db.add(ParamSnapshot(drone_id=drone_id, fleet=fleet, params=parsed.params, file_format=parsed.format,
                         filename=(file.filename or "")[:200], uploaded_by=user.username))
    db.flush()
    report = _drift(db, fleet, drone_id)
    report["ledger_seq"] = ledger.append(db, "drift", f"{fleet}/{drone_id}", report, user.username).seq
    db.commit()
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


@router.get("/policy")
async def policy(user: User = Depends(get_current_active_user)) -> Dict[str, Any]:
    """What this install will and will not do with a real aircraft."""
    from aerofleet.assurance.live_control import ENV, live_control_enabled

    on = live_control_enabled()
    return {"live_control": on, "setting": ENV,
            "blocked_when_off": ["arm", "take-off and go-to after dispatch", "bench motor test"],
            "always_allowed": ["disarm", "emergency stop", "return-to-home and hold fallbacks", "reading files and telemetry"],
            "summary": "Legacy live control is enabled on this install." if on
                       else "Ground-side only: this install does not command real aircraft."}


# ── planned versus flown ───────────────────────────────────────────────

def _review(row: FlightReview, full: bool = True) -> Dict[str, Any]:
    out = {"id": row.id, "drone_id": row.drone_id, "fleet": row.fleet, "verdict": row.verdict, "plan_name": row.plan_name,
           "log_name": row.log_name, "uploaded_by": row.uploaded_by, "uploaded_at": row.created_at.isoformat()}
    if full:
        out["report"] = row.report
    else:
        r = row.report
        out.update({"flight_s": r["flight_s"], "max_off_route_m": r["horizontal_m"]["max"], "episodes": len(r["episodes"]),
                    "manual_control": len(r["manual_control"])})
    return out


@router.post("/fleets/{fleet}/drones/{drone_id}/flights")
async def upload_flight(fleet: str, drone_id: str, plan: UploadFile = File(...), log: UploadFile = File(...),
                        city: Optional[str] = Query(None, description="Check the track against this city's no-fly zones"),
                        corridor_m: float = Query(30.0, gt=0, le=1000), altitude_m: float = Query(15.0, gt=0, le=500),
                        user: User = Depends(get_current_active_user), db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Compare a flight log (.tlog / .bin) with the approved mission file (.waypoints).

    The parameters found in the log are also stored as the drone's newest snapshot, so the drift check
    covers the configuration it actually flew with.
    """
    import os
    import tempfile

    from aerofleet.assurance.flightlog import MAX_BYTES as LOG_MAX, FlightLogError, read_flight_log
    from aerofleet.assurance.reconcile import PlanError, parse_waypoints, reconcile

    _check_id(fleet, "Fleet"), _check_id(drone_id, "Drone id")
    ext = os.path.splitext(log.filename or "")[1].lower()
    try:
        mission = parse_waypoints((await plan.read(MAX_BYTES + 1)).decode("utf-8", errors="replace"))
    except PlanError as e:
        raise HTTPException(status_code=422, detail=str(e))
    zone_at = None
    if city:
        from aerofleet.fleet.state import get_fleet_state

        airspace = get_fleet_state(city).airspace
        zone_at = lambda lat, lon: airspace.zone_at(lat, lon).value  # noqa: E731
    fd, tmp = tempfile.mkstemp(suffix=ext or ".unknown")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(await log.read(LOG_MAX + 1))
        flight = read_flight_log(tmp)
        report = reconcile(mission, flight.track, flight.modes, corridor_m=corridor_m, altitude_tol_m=altitude_m, zone_at=zone_at)
    except (FlightLogError, PlanError) as e:
        raise HTTPException(status_code=422, detail=str(e))
    finally:
        os.unlink(tmp)
    report["log"] = flight.summary()
    report["zones_checked"] = city
    if flight.params:
        db.add(ParamSnapshot(drone_id=drone_id, fleet=fleet, params=flight.params, file_format=f"log:{flight.format}",
                             filename=(log.filename or "")[:200], uploaded_by=user.username))
    row = FlightReview(drone_id=drone_id, fleet=fleet, verdict=report["verdict"], report=report,
                       plan_name=(plan.filename or "")[:200], log_name=(log.filename or "")[:200], uploaded_by=user.username)
    db.add(row)
    entry = ledger.append(db, "flight_review", f"{fleet}/{drone_id}", report, user.username)
    db.commit()
    db.refresh(row)
    out = _review(row)
    out["ledger_seq"] = entry.seq
    out["drift"] = _drift(db, fleet, drone_id) if flight.params else None
    return out


@router.get("/fleets/{fleet}/flights")
async def list_flights(fleet: str, drone_id: Optional[str] = None, limit: int = Query(50, ge=1, le=200),
                       user: User = Depends(get_current_active_user), db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    q = db.query(FlightReview).filter(FlightReview.fleet == fleet)
    if drone_id:
        q = q.filter(FlightReview.drone_id == drone_id)
    return [_review(r, full=False) for r in q.order_by(FlightReview.id.desc()).limit(limit).all()]


@router.get("/fleets/{fleet}/flights/{review_id}")
async def get_flight(fleet: str, review_id: int, user: User = Depends(get_current_active_user),
                     db: Session = Depends(get_db)) -> Dict[str, Any]:
    row = db.get(FlightReview, review_id)
    if row is None or row.fleet != fleet:
        raise HTTPException(status_code=404, detail="No such flight review in this fleet")
    return _review(row)


# ── fleet plan deconfliction ───────────────────────────────────────────

MAX_PLANS = 300


@router.post("/plans/deconflict")
async def deconflict_plans(plans: List[UploadFile] = File(...), options: str = Form("{}"),
                           user: User = Depends(get_current_active_user)) -> Dict[str, Any]:
    """Check a set of mission files against each other and return a conflict-free launch schedule.

    Each file is one mission; its id is the file name without the extension. `options` is JSON:
    {"launch_s": {id: seconds}, "priority": {id: int}, "h_sep_m": 15, "v_sep_m": null,
     "max_delay_s": 300}. With `v_sep_m` set, a different cruise height may be assigned and the
    returned file for that mission carries the new height. Nothing is stored.
    """
    import json
    import os

    from aerofleet.assurance.deconflict import Mission, deconflict, retarget_altitude
    from aerofleet.assurance.reconcile import PlanError, parse_waypoints

    try:
        opt = json.loads(options or "{}")
        launch, priority = dict(opt.get("launch_s") or {}), dict(opt.get("priority") or {})
        h_sep, v_sep = float(opt.get("h_sep_m", 15.0)), opt.get("v_sep_m")
        v_sep = float(v_sep) if v_sep is not None else None
        max_delay = float(opt.get("max_delay_s", 300.0))
        if not (0 < h_sep <= 1000) or (v_sep is not None and not (0 < v_sep <= 500)) or not (0 <= max_delay <= 3600):
            raise ValueError("a separation or delay value is out of range")
    except (ValueError, TypeError, AttributeError) as e:
        raise HTTPException(status_code=422, detail=f"Bad options: {e}")
    if not (2 <= len(plans) <= MAX_PLANS):
        raise HTTPException(status_code=422, detail=f"Upload between 2 and {MAX_PLANS} mission files")
    missions, texts = [], {}
    for f in plans:
        mid = os.path.splitext(os.path.basename(f.filename or ""))[0]
        if not _ID.match(mid) or mid in texts:
            raise HTTPException(status_code=422, detail=f"File name '{f.filename}' must give a unique id of letters, digits, '-' or '_'")
        texts[mid] = (await f.read(MAX_BYTES + 1)).decode("utf-8", errors="replace")
        try:
            missions.append(Mission(mid, parse_waypoints(texts[mid]), start_s=float(launch.get(mid, 0.0)), priority=int(priority.get(mid, 0))))
        except (PlanError, ValueError) as e:
            raise HTTPException(status_code=422, detail=f"{f.filename}: {e}")
    result = deconflict(missions, h_sep_m=h_sep, v_sep_m=v_sep, max_delay_s=max_delay)
    result.pop("missions")
    new_alt = {c["id"]: c["new_altitude_m"] for c in result["changes"] if c["new_altitude_m"] is not None}
    result["files"] = {mid: retarget_altitude(texts[mid], new_alt[mid]) if mid in new_alt else texts[mid] for mid in texts}
    return result


# ── wind at cruise height ──────────────────────────────────────────────

@router.post("/plans/wind-check")
async def wind_check_plan(plan: UploadFile = File(...), payload_kg: float = Form(..., ge=0, le=500),
                          usable_wh: float = Form(..., gt=0, le=100000), hour_utc: Optional[str] = Form(None),
                          max_wind_mps: Optional[float] = Form(None, gt=0, le=60), profile: Optional[str] = Form(None),
                          user: User = Depends(get_current_active_user)) -> Dict[str, Any]:
    """Battery margin for a mission in still air, on the 10 m wind and on the wind at its cruise height.

    `usable_wh` is the battery energy above the landing reserve. The wind comes from the Open-Meteo
    forecast for the mission's home position and `hour_utc` (default: the current forecast hour).
    `profile` supplies the wind by hand instead — JSON {"10": [speed, from_deg], "80": [...], "120": [...],
    "180": [...]} — for offline use. 503 when no forecast can be fetched and none was supplied.
    """
    import json

    from aerofleet.assurance.reconcile import PlanError, parse_waypoints
    from aerofleet.assurance.wind import WindUnavailable, fetch_profiles, profile_for, wind_check

    try:
        mission = parse_waypoints((await plan.read(MAX_BYTES + 1)).decode("utf-8", errors="replace"))
    except PlanError as e:
        raise HTTPException(status_code=422, detail=str(e))
    if profile:
        try:
            wind = {int(h): (float(v[0]), float(v[1])) for h, v in json.loads(profile).items()}
            if not wind or any(s < 0 or s > 80 for s, _ in wind.values()):
                raise ValueError("wind speeds must be between 0 and 80 m/s")
        except (ValueError, TypeError, KeyError, IndexError, AttributeError) as e:
            raise HTTPException(status_code=422, detail=f"Bad wind profile: {e}")
        hour, source = hour_utc, "supplied by the user"
    else:
        try:
            hour, wind = profile_for(fetch_profiles(mission.home[0], mission.home[1], forecast_days=3), hour_utc)
        except WindUnavailable as e:
            raise HTTPException(status_code=503, detail=f"{e}. Supply the wind by hand with the 'profile' field to check offline.")
        source = "Open-Meteo forecast"
    report = wind_check(mission, payload_kg, usable_wh, wind, max_wind_mps)
    report.update({"hour_utc": hour, "wind_source": source, "notes": list(mission.notes)})
    return report


# ── signed record ──────────────────────────────────────────────────────

@router.get("/ledger")
async def list_ledger(limit: int = Query(100, ge=1, le=1000), user: User = Depends(get_current_active_user),
                      db: Session = Depends(get_db)) -> Dict[str, Any]:
    """The newest entries of the signed record, and the public key that verifies them."""
    from aerofleet.data.models.models import AssuranceLedgerEntry

    rows = db.query(AssuranceLedgerEntry).order_by(AssuranceLedgerEntry.seq.desc()).limit(limit).all()
    return {"public_key_pem": ledger.public_key_pem(), "entries": [ledger.to_dict(r) for r in rows]}


@router.get("/ledger/verify")
async def verify_ledger(user: User = Depends(get_current_active_user), db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Re-check every link and signature. `ok: false` names the first entry that fails and why."""
    return ledger.verify_chain(db)
