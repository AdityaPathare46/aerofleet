"""Flight-controller compliance check — /api/v1/hardware/fc.

Auto-detects a flight controller (Mission Planner's forwarded MAVLink over
UDP, else a USB serial port), runs a read-only inspection in the background
(aerofleet/hardware/fc_inspection_worker.py), and serves the resulting
report with its manual checklist and the operator-gated motor test.

Auth: reads need an active user; everything that changes the audit record
(checklist attestations, motor tests and their confirmation) needs an
operator. The motor test is the only endpoint that actuates hardware, and
it enforces its safety gates here, server-side, regardless of what the UI
did: disarmed only, props-off confirmation, one motor at a time, throttle
capped at 15 %, duration capped at 3 s, test order "sequence".
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from aerofleet.api.rate_limit import limiter
from aerofleet.api.routes.auth import get_current_active_user, get_current_operator_user
from aerofleet.api.routes.hardware import require_hardware_owner
from aerofleet.city.registry import DEFAULT_CITY
from aerofleet.data.database import get_db_session
from aerofleet.data.models.models import FCInspection, User
from aerofleet.hardware.compliance_rules import MANUAL_CHECK_IDS, WIZARD_CHECK_IDS, rule_table
from aerofleet.hardware.fc_discovery import configured_udp_ports, discover
from aerofleet.hardware.fc_inspection_worker import (
    HARDWARE_LOCK,
    FCInspectionJob,
    get_fc_inspection_worker,
    new_inspection_id,
    recompute_report,
)
from aerofleet.hardware.fc_inspector import FCInspectionError, FCInspector, FCPortBusyError
from aerofleet.hardware.motor_layouts import all_layouts, layout_for_frame
from aerofleet.utils.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()

MOTOR_TEST_MAX_THROTTLE_PCT = 15.0
MOTOR_TEST_MAX_DURATION_S = 3.0
ESC_SPIN_RPM_THRESHOLD = 300  # rpm above which an ESC is considered to have spun


def get_db():
    with get_db_session() as db:
        yield db


# ─────────────────────────────────────────────────────────────────────────
#  Schemas
# ─────────────────────────────────────────────────────────────────────────

class InspectionRequest(BaseModel):
    auto: bool = True
    connection: Optional[str] = Field(None, max_length=255,
                                      description="pymavlink connection string; omit (auto=true) to auto-detect")
    drone_id: Optional[str] = Field(None, max_length=50)
    city: str = DEFAULT_CITY
    uin: Optional[str] = Field(None, max_length=64, description="Digital Sky UIN for this aircraft")
    weight_kg: Optional[float] = Field(None, gt=0, le=500)
    payload_kg: float = Field(0.0, ge=0, le=500)
    bench_mode: bool = Field(False, description="Indoor bench check: no-GPS-fix results become WARN, not FAIL")
    sample_seconds: float = Field(6.0, ge=2.0, le=15.0)


class ChecklistItem(BaseModel):
    check_id: str
    result: Literal["confirmed", "failed", "unchecked"]
    note: Optional[str] = Field(None, max_length=500)


class ChecklistUpdate(BaseModel):
    items: List[ChecklistItem] = Field(..., min_length=1)


class MotorTestRequest(BaseModel):
    motor: str = Field(..., min_length=1, max_length=2, description="Sequence letter A, B, C…")
    throttle_pct: float = Field(10.0, gt=0, le=100)
    duration_s: float = Field(2.0, gt=0, le=60)
    props_removed_confirmed: bool = False


class MotorConfirmRequest(BaseModel):
    result: Literal["correct", "incorrect"]
    note: Optional[str] = Field(None, max_length=500)


# ─────────────────────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────────────────────

def _summary(row: FCInspection) -> Dict[str, Any]:
    ctx = row.context or {}
    return {
        "inspection_id": row.inspection_id, "status": row.status, "progress": row.progress, "stage": row.stage,
        "verdict": row.verdict, "source": row.source, "connection": row.connection, "drone_id": row.drone_id,
        "uin": ctx.get("uin"), "bench_mode": ctx.get("bench_mode"), "requested_by": row.requested_by,
        "firmware": (row.report or {}).get("firmware"), "counts": (row.report or {}).get("counts"),
        "error": row.error,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "completed_at": row.completed_at.isoformat() if row.completed_at else None,
    }


def _detail(row: FCInspection) -> Dict[str, Any]:
    out = _summary(row)
    layout = None
    if row.snapshot:
        params = row.snapshot.get("params") or {}
        lay = layout_for_frame(params.get("FRAME_CLASS"), params.get("FRAME_TYPE"))
        layout = lay.to_dict() if lay else None
    out.update({
        "requested_connection": row.requested_connection, "city": row.city, "context": row.context,
        "discovery": row.discovery, "report": row.report, "checklist": row.checklist or {},
        "motor_tests": row.motor_tests or {}, "motor_layout": layout,
        "snapshot": row.snapshot,
        "started_at": row.started_at.isoformat() if row.started_at else None,
    })
    return out


def _get_row(db: Session, inspection_id: str) -> FCInspection:
    row = db.query(FCInspection).filter(FCInspection.inspection_id == inspection_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Inspection not found")
    return row


def _require_ready(row: FCInspection) -> None:
    if row.status != "READY" or not row.snapshot:
        raise HTTPException(status_code=409, detail=f"Inspection is {row.status}; wait for the report first")


def _esc_corroboration(result: Dict[str, Any], expected_channels: List[int]) -> Dict[str, Any]:
    if not result.get("esc_telemetry_available"):
        return {"status": "unavailable", "expected_esc": expected_channels, "spun_esc": [],
                "note": "No ESC telemetry — rely on the operator's observation."}
    rpm = result.get("esc_rpm_max") or []
    spun = [i + 1 for i, r in enumerate(rpm) if r and r > ESC_SPIN_RPM_THRESHOLD]
    if not spun:
        status, note = "no_rpm", "ESC telemetry reported no rotation."
    elif expected_channels and set(spun) == set(expected_channels):
        status, note = "corroborated", "ESC telemetry shows the expected ESC spinning."
    else:
        status, note = "mismatch", "A different set of ESCs spun than the output mapping predicts."
    return {"status": status, "expected_esc": expected_channels, "spun_esc": spun,
            "rpm_by_esc": {str(i + 1): r for i, r in enumerate(rpm) if r}, "note": note}


# ─────────────────────────────────────────────────────────────────────────
#  Endpoints
# ─────────────────────────────────────────────────────────────────────────

@router.get("/discover")
def discover_flight_controller(
    listen_s: float = Query(2.0, ge=0.5, le=5.0),
    current_user: User = Depends(get_current_active_user),
    _owner: None = Depends(require_hardware_owner),
):
    """Listen for Mission Planner's forwarded MAVLink (UDP 14550/14551 by
    default, AEROFLEET_FC_UDP_PORTS to override), else scan USB serial."""
    worker = get_fc_inspection_worker()
    if worker.busy or HARDWARE_LOCK.locked():
        raise HTTPException(status_code=409, detail="An inspection or motor test is using the flight controller right now")
    with HARDWARE_LOCK:
        return discover(udp_ports=configured_udp_ports(), listen_s=listen_s).to_dict()


@router.get("/motor-layouts")
async def motor_layouts(current_user: User = Depends(get_current_active_user)):
    return all_layouts()


@router.get("/rules")
async def rules(current_user: User = Depends(get_current_active_user)):
    return rule_table()


@router.post("/inspections", status_code=202)
async def start_inspection(
    body: InspectionRequest,
    current_user: User = Depends(get_current_active_user),
    _owner: None = Depends(require_hardware_owner),
):
    if not body.auto and not body.connection:
        raise HTTPException(status_code=422, detail="Give a connection string or set auto=true")

    weight_kg, weight_source = body.weight_kg, "entered for this inspection" if body.weight_kg else None
    if body.drone_id and weight_kg is None:
        from aerofleet.fleet.state import get_fleet_state

        drone = get_fleet_state(body.city).get_drone(body.drone_id)
        if drone is None:
            raise HTTPException(status_code=404, detail=f"Drone '{body.drone_id}' not found in {body.city}'s fleet")
        weight_kg, weight_source = drone.weight_kg, f"AeroFleet fleet registry ({body.city})"

    context = {
        "bench_mode": body.bench_mode, "drone_id": body.drone_id, "uin": (body.uin or "").strip() or None,
        "weight_kg": weight_kg, "weight_source": weight_source, "payload_kg": body.payload_kg,
    }
    job = FCInspectionJob(
        inspection_id=new_inspection_id(),
        connection=None if body.auto and not body.connection else body.connection,
        context=context, sample_seconds=body.sample_seconds, udp_ports=configured_udp_ports(),
        drone_id=body.drone_id, city=body.city, requested_by=current_user.username,
    )
    get_fc_inspection_worker().enqueue(job)
    return {"inspection_id": job.inspection_id, "status": "PENDING"}


@router.get("/inspections")
async def list_inspections(
    drone_id: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    q = db.query(FCInspection)
    if drone_id:
        q = q.filter(FCInspection.drone_id == drone_id)
    return [_summary(r) for r in q.order_by(FCInspection.created_at.desc(), FCInspection.id.desc()).limit(limit).all()]


@router.get("/inspections/{inspection_id}")
async def get_inspection(
    inspection_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    return _detail(_get_row(db, inspection_id))


@router.get("/inspections/{inspection_id}/export")
async def export_inspection(
    inspection_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    row = _get_row(db, inspection_id)
    payload = _detail(row)
    payload["exported_at"] = datetime.utcnow().isoformat() + "Z"
    payload["exported_by"] = current_user.username
    return JSONResponse(payload, headers={"Content-Disposition": f'attachment; filename="{inspection_id}.json"'})


@router.post("/inspections/{inspection_id}/checklist")
async def update_checklist(
    inspection_id: str,
    body: ChecklistUpdate,
    current_user: User = Depends(get_current_operator_user),
    db: Session = Depends(get_db),
):
    row = _get_row(db, inspection_id)
    _require_ready(row)
    checklist = dict(row.checklist or {})
    now = datetime.utcnow().isoformat() + "Z"
    for item in body.items:
        if item.check_id in WIZARD_CHECK_IDS:
            raise HTTPException(status_code=422, detail=f"{item.check_id} is resolved through the motor-test wizard")
        if item.check_id not in MANUAL_CHECK_IDS:
            raise HTTPException(status_code=422, detail=f"{item.check_id} is not a manual checklist item")
        if item.result == "unchecked":
            checklist.pop(item.check_id, None)
        else:
            checklist[item.check_id] = {"result": item.result, "note": item.note, "by": current_user.username, "at": now}
    row.checklist = checklist
    recompute_report(row)
    db.commit()
    return _detail(row)


@router.post("/inspections/{inspection_id}/motor-test")
@limiter.limit("20/minute")
def run_motor_test(
    request: Request,
    inspection_id: str,
    body: MotorTestRequest,
    current_user: User = Depends(get_current_operator_user),
    _owner: None = Depends(require_hardware_owner),
):
    """Spin ONE motor, props off. Gates are enforced here, in this order:
    props-off confirmation, report ready, supported frame + valid letter,
    throttle/duration caps, exclusive hardware access (one motor at a time,
    never during an inspection), same vehicle as inspected, DISARMED."""
    if body.props_removed_confirmed is not True:
        raise HTTPException(status_code=400, detail="Motor test refused: confirm that ALL propellers are removed (props_removed_confirmed=true)")

    with get_db_session() as db:
        row = _get_row(db, inspection_id)
        _require_ready(row)
        snapshot = dict(row.snapshot)
        connection = row.connection
    params = snapshot.get("params") or {}
    layout = layout_for_frame(params.get("FRAME_CLASS"), params.get("FRAME_TYPE"))
    if layout is None:
        raise HTTPException(status_code=422, detail="Motor test wizard supports Quad X, Quad + and Hexa X only; use Mission Planner's Motor Test for this frame")
    letter = body.motor.strip().upper()
    position = layout.by_letter(letter)
    if position is None:
        raise HTTPException(status_code=422, detail=f"{layout.name} has motors {', '.join(m.letter for m in sorted(layout.motors, key=lambda m: m.test_order))}; '{body.motor}' is not one of them")

    throttle = min(body.throttle_pct, MOTOR_TEST_MAX_THROTTLE_PCT)
    duration = min(body.duration_s, MOTOR_TEST_MAX_DURATION_S)

    if get_fc_inspection_worker().busy or not HARDWARE_LOCK.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="The flight controller is busy (an inspection or another motor test is running) — one motor at a time")
    try:
        inspector = FCInspector(connection, source="motor_test", heartbeat_timeout_s=5.0)
        try:
            hb = inspector.connect()
            expected_sys = (snapshot.get("heartbeat") or {}).get("system_id")
            if expected_sys is not None and hb.get("system_id") != expected_sys:
                raise HTTPException(status_code=409, detail=f"Connected vehicle is system {hb.get('system_id')}, but this inspection was of system {expected_sys} — run a new inspection")
            if inspector.armed:
                raise HTTPException(status_code=409, detail="Motor test refused: the vehicle is ARMED. Disarm first.")
            result = inspector.motor_test(position.test_order, throttle, duration)
        except FCPortBusyError as exc:
            raise HTTPException(status_code=409, detail=str(exc))
        except FCInspectionError as exc:
            status = 409 if "ARMED" in str(exc) else 502
            raise HTTPException(status_code=status, detail=str(exc))
        finally:
            inspector.close()
    finally:
        HARDWARE_LOCK.release()

    expected_esc = sorted(
        int(k[len("SERVO"):-len("_FUNCTION")]) for k, v in params.items()
        if k.startswith("SERVO") and k.endswith("_FUNCTION") and k[5:-9].isdigit() and int(v) == 32 + position.motor_number
    )
    entry = {
        "letter": letter, "motor_number": position.motor_number, "position": position.position_label,
        "angle_deg": position.angle_deg, "expected_direction": position.direction,
        "throttle_pct_requested": body.throttle_pct, "throttle_pct": throttle,
        "duration_s_requested": body.duration_s, "duration_s": duration,
        "capped": throttle < body.throttle_pct or duration < body.duration_s,
        "ack_result": result["ack_result"], "accepted": result["accepted"],
        "statustexts": result["statustexts"], "esc_rpm_max": result["esc_rpm_max"],
        "esc_corroboration": _esc_corroboration(result, expected_esc),
        "tested_by": current_user.username, "tested_at": datetime.utcnow().isoformat() + "Z",
        "confirmation": None,
    }
    with get_db_session() as db:
        row = _get_row(db, inspection_id)
        mt = dict(row.motor_tests or {})
        results = dict(mt.get("results") or {})
        log = list(mt.get("log") or [])
        if result["accepted"]:
            results[letter] = entry  # a re-test replaces (and un-confirms) the previous one
        log.append({k: entry[k] for k in ("letter", "throttle_pct", "duration_s", "ack_result", "tested_by", "tested_at")})
        row.motor_tests = {"layout": layout.key, "results": results, "log": log[-100:]}
        recompute_report(row)
        verdict = row.verdict
    if not result["accepted"]:
        raise HTTPException(status_code=409, detail=f"Flight controller refused the motor test ({result['ack_result']}): {'; '.join(result['statustexts']) or 'no reason given'}")
    return {"result": entry, "verdict": verdict}


@router.post("/inspections/{inspection_id}/motor-test/{motor}/confirm")
async def confirm_motor(
    inspection_id: str,
    motor: str,
    body: MotorConfirmRequest,
    current_user: User = Depends(get_current_operator_user),
    db: Session = Depends(get_db),
):
    row = _get_row(db, inspection_id)
    _require_ready(row)
    letter = motor.strip().upper()
    mt = dict(row.motor_tests or {})
    results = dict(mt.get("results") or {})
    if letter not in results:
        raise HTTPException(status_code=409, detail=f"Motor {letter} has not been spun yet — run its motor test first")
    entry = dict(results[letter])
    entry["confirmation"] = {"result": body.result, "note": body.note, "by": current_user.username,
                             "at": datetime.utcnow().isoformat() + "Z"}
    results[letter] = entry
    mt["results"] = results
    row.motor_tests = mt
    recompute_report(row)
    db.commit()
    return _detail(row)
