"""Delivery order CRUD + dispatch trigger."""

import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from aerofleet.api.routes.auth import get_current_active_user
from aerofleet.api.schemas import OrderCreate, OrderResponse, OrderUpdate
from aerofleet.data.database import get_db_session
from aerofleet.data.models.models import Order, User
from aerofleet.fleet.models import DeliveryOrder
from aerofleet.fleet.state import get_fleet_state
from aerofleet.utils.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()


def get_db():
    with get_db_session() as db:
        yield db


@router.post("/", response_model=OrderResponse, status_code=201)
async def create_order(
    order: OrderCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Create a new delivery order and register it with the live fleet state."""
    order_id = f"ORD-{uuid.uuid4().hex[:8].upper()}"
    city = order.city or "pune"
    logger.info(f"Creating new order: {order_id} (city={city})")

    fleet = get_fleet_state(city)
    depot = fleet.get_depot(order.origin_depot_id)
    if depot is None:
        raise HTTPException(status_code=404, detail=f"Depot '{order.origin_depot_id}' not found in {city}")

    dest_node = fleet.graph.nearest_node(order.destination_lat, order.destination_lon)

    db_order = Order(
        order_id=order_id,
        user_id=current_user.id,
        city=city,
        origin_depot_id=depot.node,
        destination_node_id=dest_node,
        destination_lat=order.destination_lat,
        destination_lon=order.destination_lon,
        payload_kg=order.payload_kg,
        priority=order.priority,
        deadline_minutes=order.deadline_minutes,
        status="PENDING",
    )
    db.add(db_order)
    db.commit()
    db.refresh(db_order)

    fleet.orders[order_id] = DeliveryOrder(
        order_id=order_id,
        origin_depot_id=order.origin_depot_id,
        destination_node=dest_node,
        payload_kg=order.payload_kg,
        deadline_minutes=order.deadline_minutes,
        priority=order.priority,
    )

    logger.info(f"Order created: {order_id}")
    return _to_response(db_order, order.origin_depot_id, city)


@router.get("/", response_model=List[OrderResponse])
async def list_orders(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    status: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    query = db.query(Order).filter(Order.user_id == current_user.id)
    if status:
        query = query.filter(Order.status == status)
    orders = query.offset(skip).limit(limit).all()
    return [_to_response(o) for o in orders]


@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    order = db.query(Order).filter(Order.order_id == order_id, Order.user_id == current_user.id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return _to_response(order)


@router.put("/{order_id}", response_model=OrderResponse)
async def update_order(
    order_id: str,
    order_update: OrderUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    order = db.query(Order).filter(Order.order_id == order_id, Order.user_id == current_user.id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    for field, value in order_update.dict(exclude_unset=True).items():
        setattr(order, field, value)
    order.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(order)
    return _to_response(order)


@router.post("/{order_id}/dispatch")
async def dispatch_order(
    order_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Generate dispatch candidates for a pending order and CBF-gate the
    final action — always deterministic, always fast (no LLM call is ever
    on this path). The multi-agent council can optionally explain a
    decision made here afterward, asynchronously, via
    POST /{order_id}/request-explanation — it never runs synchronously as
    part of this endpoint. See aerofleet/agents/explanation_worker.py.

    In a multi-worker deployment, this must only be accepted by the
    process that owns FleetState/hardware (see
    docs/MULTI_WORKER_ARCHITECTURE.md) — a non-owner worker's FleetState
    is a separate, uninitialized copy nobody else can see, so silently
    mutating it here would be worse than failing loudly.
    """
    # Local import, same pattern already used elsewhere in this route
    # package (aerofleet/api/routes/safety.py imports from fleet.py the
    # same way) — avoids a module-level cross-route-module import cycle.
    from aerofleet.api.routes.hardware import require_hardware_owner

    require_hardware_owner()
    order = db.query(Order).filter(Order.order_id == order_id, Order.user_id == current_user.id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    fleet = get_fleet_state(order.city or "pune")
    live_order = fleet.orders.get(order_id)
    if live_order is None:
        raise HTTPException(status_code=404, detail="Order not registered with fleet state")

    candidate = fleet.dispatch_engine.best_candidate(live_order, fleet.list_drones(), fleet.depots)
    if candidate is None:
        order.status = "FAILED"
        db.commit()
        raise HTTPException(status_code=409, detail="No feasible drone found for this order")

    # Real DGCA zone/ceiling check against the actual destination — previously
    # hardcoded to in_red_zone=False regardless of where the delivery actually
    # went, meaning the CBF gate's geofence_exclusion constraint could never
    # fire in practice. See aerofleet/city/restricted_sites.py for the real,
    # named Red/Yellow sites this now checks against for Pune and Mumbai.
    from aerofleet.city.airspace import ZoneColor

    dest_lat, dest_lon = fleet.graph.node_lat_lon(live_order.destination_node)
    dest_zone = fleet.airspace.zone_at(dest_lat, dest_lon)
    altitude_band = fleet.airspace.assign_altitude_band(live_order.priority, dest_lat, dest_lon)

    # Origin depot coordinates, best-effort — needed for both the VR Safety
    # View's Incident Replay geometry (on rejection) and Mission Planner
    # waypoint export (on approval, see aerofleet/integrations/
    # mission_planner.py): a mission needs a real launch point, not just a
    # destination. Captured once here rather than separately per branch.
    origin_lat, origin_lon = None, None
    try:
        origin_depot = fleet.depots.get(candidate.depot_id)
        if origin_depot is not None:
            origin_lat, origin_lon = fleet.graph.node_lat_lon(origin_depot.node)
    except Exception:
        pass

    dispatch_plan = {
        "order_id": order_id,
        "drone_id": candidate.drone_id,
        "origin_depot_id": candidate.depot_id,
        "origin_lat": origin_lat,
        "origin_lon": origin_lon,
        "distance_km": candidate.outbound_km + candidate.return_km,
        "deadline_minutes": live_order.deadline_minutes,
        "payload_kg": live_order.payload_kg,
        "battery_margin_wh": candidate.battery_margin_wh,
        "energy_wh_required": candidate.energy_wh_required,
        "priority": live_order.priority,
        # Cruise at the midpoint of the assigned band, not its floor: the
        # previous "altitude_band.floor_m or 60.0" silently treated the LOW
        # band's legitimate 0.0 m floor as falsy and substituted 60.0 (a
        # real bug, exposed by tests/integration/test_dispatch_order_api.py
        # ::TestDispatchRejectsRealRedZoneDestination once altitude_m was
        # location-aware) — and even fixed naively to use floor_m directly,
        # every band's floor is its *lower* boundary, giving zero margin
        # against the band immediately below rather than the deliberate
        # headroom the midpoint gives against both neighbors.
        "altitude_m": (altitude_band.floor_m + altitude_band.ceiling_m) / 2.0,
        "max_altitude_m": fleet.airspace.altitude_ceiling_m_at(dest_lat, dest_lon),
        "in_red_zone": dest_zone == ZoneColor.RED,
        "in_yellow_zone": dest_zone == ZoneColor.YELLOW,
        # Not previously captured, even though already computed above —
        # frozen_context (below) needs real coordinates to spatially
        # reconstruct a rejected dispatch's geometry (VR Safety View's
        # Incident Replay mode); every other dispatch_plan field already
        # flowed into the CBF certificate/incident record, only these two
        # were silently dropped.
        "dest_lat": dest_lat,
        "dest_lon": dest_lon,
    }

    # The ONLY decision path. No LLM call sits anywhere between a dispatch
    # request and this gate — deterministic, sub-millisecond, always.
    from aerofleet.safety.cbf_gate import build_cbf_gate, build_trajectory_points_from_plan

    gate = build_cbf_gate(dispatch_plan, city=order.city)
    result = gate.evaluate_trajectory(build_trajectory_points_from_plan(dispatch_plan))
    cbf_certificate = {
        "passed": result.passed,
        "safety_margins": result.safety_margin_summary,
        "execution_time_ms": result.execution_time_ms,
    }
    verdict = "APPROVED" if result.passed else "REJECTED_BY_CBF_GATE"

    if verdict == "APPROVED":
        drone = fleet.get_drone(candidate.drone_id)
        drone.order_id = order_id
        drone.current_payload_kg = live_order.payload_kg
        from aerofleet.fleet.models import DroneState

        drone.state = DroneState.EN_ROUTE
        drone.battery.consume(candidate.energy_wh_required)
        drone.total_distance_km += candidate.outbound_km + candidate.return_km

        order.status = "ASSIGNED"
        fleet.twin.update({
            "type": "DELIVERY_LEG",
            "energy_wh": candidate.energy_wh_required,
            "distance_km": candidate.outbound_km + candidate.return_km,
        })

        # CBF gate has already approved this action above — this is the
        # ONLY place a hardware command may be issued as a result of
        # dispatch, and it only happens after that approval.
        if drone.link_mode == "LIVE":
            from aerofleet.hardware.telemetry_service import get_drone_link_registry

            link = get_drone_link_registry().get_link(candidate.drone_id)
            if link is None:
                logger.error(f"[{candidate.drone_id}] marked LIVE but has no registered link — grounding")
                drone.state = DroneState.GROUNDED
                order.status = "FAILED"
                verdict = "FAILED_NO_HARDWARE_LINK"
            else:
                try:
                    dest_lat, dest_lon = fleet.graph.node_lat_lon(live_order.destination_node)
                    altitude_m = dispatch_plan["altitude_m"]
                    link.arm()
                    link.takeoff(altitude_m)
                    link.goto(dest_lat, dest_lon, altitude_m)
                    logger.warning(
                        f"[{candidate.drone_id}] LIVE hardware commanded: arm -> takeoff({altitude_m}m) "
                        f"-> goto({dest_lat:.6f}, {dest_lon:.6f})"
                    )
                except Exception as exc:
                    logger.error(f"[{candidate.drone_id}] Hardware command failed after CBF approval: {exc}")
                    drone.state = DroneState.GROUNDED
                    order.status = "FAILED"
                    verdict = "FAILED_HARDWARE_COMMAND"
    else:
        order.status = "FAILED"
        # Was defined on FleetDigitalTwin since Phase B but never actually
        # recorded anywhere — this is the one place a CBF rejection happens,
        # so it's the one place this event type should fire. Feeds
        # aerofleet/agents/policy_review_worker.py's slow-cadence review.
        fleet.twin.update({"type": "CBF_INTERVENTION"})

        # Auto-trigger the Fleet Incident Forensics Council — never
        # requested manually, never on this response path (enqueue only;
        # the actual multi-agent investigation runs async, off the event
        # loop, same as explanation_worker.py). This is the live trigger;
        # fault-event and emergency-landing triggers are documented as not
        # yet wired to a live signal — see
        # aerofleet/agents/incident_forensics_worker.py's module docstring.
        from aerofleet.agents.incident_forensics_worker import (
            IncidentJob,
            get_incident_forensics_worker,
            new_incident_id,
        )

        get_incident_forensics_worker().enqueue(IncidentJob(
            incident_id=new_incident_id(),
            city=order.city,
            order_id=order_id,
            trigger_type="CBF_REJECTION",
            trigger_detail={
                "violations": [
                    {
                        "constraint_name": v.constraint_name,
                        "violation_magnitude": v.violation_magnitude,
                        "required_correction": v.required_correction,
                    }
                    for v in result.violations
                ],
            },
            frozen_context={
                "cbf_certificate": cbf_certificate,
                "dispatch_plan": dispatch_plan,
                "candidate": candidate.__dict__,
                "origin_lat": dispatch_plan["origin_lat"],
                "origin_lon": dispatch_plan["origin_lon"],
            },
        ))

    order.council_verdict = verdict
    order.cbf_certificate = cbf_certificate
    order.dispatch_plan = dispatch_plan
    db.commit()

    logger.info(f"Dispatch decision for {order_id}: {verdict} (drone={candidate.drone_id})")

    return {
        "order_id": order_id,
        "assigned_drone_id": candidate.drone_id if verdict == "APPROVED" else None,
        "verdict": verdict,
        "candidate": candidate.__dict__,
        "cbf_certificate": cbf_certificate,
        "explanation_status": "NOT_REQUESTED",
    }


@router.post("/{order_id}/request-explanation")
async def request_explanation(
    order_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Ask the multi-agent council to explain a dispatch decision that has
    already been made. Purely asynchronous — enqueues a background job and
    returns immediately; never blocks, never influences the decision
    itself (already final by the time this can even be called). Poll
    GET /{order_id} and watch council_explanation_status for RUNNING/READY.
    """
    order = db.query(Order).filter(Order.order_id == order_id, Order.user_id == current_user.id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.cbf_certificate is None:
        raise HTTPException(status_code=409, detail="Order hasn't been dispatched yet — nothing to explain")
    if order.council_explanation_status in ("PENDING", "RUNNING"):
        return {"order_id": order_id, "council_explanation_status": order.council_explanation_status}

    from aerofleet.agents.explanation_worker import ExplanationJob, get_explanation_worker

    get_explanation_worker().enqueue(
        ExplanationJob(
            order_id=order_id,
            dispatch_plan=order.dispatch_plan or {},
            cbf_certificate=order.cbf_certificate,
        )
    )
    db.refresh(order)
    return {"order_id": order_id, "council_explanation_status": order.council_explanation_status}


@router.get("/{order_id}/mission-planner-waypoints")
async def get_mission_planner_waypoints(
    order_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Exports this order's CBF-approved dispatch as a standard QGC WPL 110
    `.waypoints` file — the format ArduPilot Mission Planner and
    QGroundControl both read directly (Flight Plan tab -> Open). AeroFleet
    still made the only decision that matters before this file can exist;
    Mission Planner is downstream flight-planning/monitoring tooling, not
    a second decision-maker. See aerofleet/integrations/mission_planner.py.
    """
    from fastapi.responses import PlainTextResponse

    from aerofleet.integrations.mission_planner import build_waypoint_file

    order = db.query(Order).filter(Order.order_id == order_id, Order.user_id == current_user.id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.council_verdict != "APPROVED":
        raise HTTPException(
            status_code=409,
            detail="Only a CBF-approved dispatch has a real route to export — this order's verdict is "
                   f"{order.council_verdict or 'not dispatched yet'}.",
        )

    waypoints = build_waypoint_file(order.dispatch_plan or {})
    if waypoints is None:
        raise HTTPException(status_code=422, detail="This order's dispatch_plan is missing coordinates needed to build a route")

    return PlainTextResponse(
        content=waypoints,
        media_type="text/plain",
        headers={"Content-Disposition": f'attachment; filename="{order_id}.waypoints"'},
    )


@router.delete("/{order_id}", status_code=204)
async def delete_order(
    order_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    order = db.query(Order).filter(Order.order_id == order_id, Order.user_id == current_user.id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    db.delete(order)
    db.commit()
    return None


def _to_response(order: Order, origin_depot_id: Optional[str] = None, city: Optional[str] = None) -> OrderResponse:
    return OrderResponse(
        id=order.id,
        order_id=order.order_id,
        city=city or order.city or "pune",
        origin_depot_id=origin_depot_id or str(order.origin_depot_id),
        destination_lat=order.destination_lat,
        destination_lon=order.destination_lon,
        payload_kg=order.payload_kg,
        priority=order.priority,
        deadline_minutes=order.deadline_minutes,
        status=order.status,
        council_verdict=order.council_verdict,
        cbf_certificate=order.cbf_certificate,
        council_explanation_status=order.council_explanation_status or "NOT_REQUESTED",
        council_transcript=order.council_transcript,
        council_explanation_requested_at=order.council_explanation_requested_at,
        council_explanation_completed_at=order.council_explanation_completed_at,
        created_at=order.created_at,
        updated_at=order.updated_at,
    )
