"""Real-drone hardware control — connect/disconnect MAVLink links, manual
arm/disarm override, the fleet-wide emergency kill switch, and a live
telemetry WebSocket for the desktop app.

Every command here talks directly to hardware (aerofleet.hardware.mavlink_link)
via the process-wide DroneLinkRegistry. Normal delivery dispatch never goes
through this router — that path is orders.py's `/dispatch`, which only
commands hardware after the CBF gate has already approved the action. The
endpoints here are for connection lifecycle and direct operator overrides
(manual arm/disarm, emergency stop), not for the delivery-decision path.
"""
from __future__ import annotations

import asyncio
from dataclasses import asdict
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect, status
from pydantic import BaseModel

from aerofleet.api.rate_limit import limiter
from aerofleet.api.routes.auth import get_current_active_user, get_current_operator_user, get_user_from_token
from aerofleet.city.registry import DEFAULT_CITY
from aerofleet.data.database import get_db_session
from aerofleet.data.models.models import User
from aerofleet.event_bus.async_bus import AsyncEventBus
from aerofleet.hardware.mavlink_link import MAVLinkCommandError, MAVLinkConnectionError
from aerofleet.hardware.telemetry_service import get_drone_link_registry
from aerofleet.utils.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()

# Single event bus shared by the background telemetry poll loop (started
# in app.py's startup hook via start_background_polling()) and this
# module's WebSocket broadcaster.
event_bus = AsyncEventBus()
registry = get_drone_link_registry(event_bus)

_ws_connections: List[WebSocket] = []


async def _broadcast(message: dict) -> None:
    dead = []
    for ws in _ws_connections:
        try:
            await ws.send_json(message)
        except Exception:
            dead.append(ws)
    for ws in dead:
        if ws in _ws_connections:
            _ws_connections.remove(ws)


def _on_telemetry_event(event) -> None:
    # Called synchronously from AsyncEventBus.publish() inside the running
    # event loop (via registry.run_forever()'s drain() call) — safe to
    # schedule the actual send as a task from here.
    asyncio.create_task(_broadcast({"type": "telemetry.update", "drone_id": event.source, **event.payload}))


event_bus.subscribe("telemetry.update", _on_telemetry_event)


class ConnectRequest(BaseModel):
    connection_string: str
    city: str = DEFAULT_CITY


@router.post("/vehicles/{drone_id}/connect")
@limiter.limit("10/minute")
async def connect_vehicle(
    request: Request,
    drone_id: str,
    body: ConnectRequest,
    current_user: User = Depends(get_current_operator_user),
):
    try:
        telemetry = registry.register(drone_id, body.city, body.connection_string)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except MAVLinkConnectionError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    return {"drone_id": drone_id, "link_mode": "LIVE", "telemetry": asdict(telemetry)}


@router.delete("/vehicles/{drone_id}/connect")
async def disconnect_vehicle(
    drone_id: str,
    current_user: User = Depends(get_current_operator_user),
):
    registry.unregister(drone_id)
    return {"drone_id": drone_id, "link_mode": "SIMULATED"}


@router.get("/vehicles")
async def list_vehicles(current_user: User = Depends(get_current_active_user)):
    out = []
    for drone_id in registry.list_live_drone_ids():
        link = registry.get_link(drone_id)
        out.append({
            "drone_id": drone_id,
            "connected": link.is_connected if link else False,
            "telemetry": asdict(link.last_telemetry) if link else None,
        })
    return out


@router.post("/vehicles/{drone_id}/arm")
@limiter.limit("20/minute")
async def arm_vehicle(request: Request, drone_id: str, current_user: User = Depends(get_current_operator_user)):
    link = registry.get_link(drone_id)
    if link is None:
        raise HTTPException(status_code=404, detail=f"'{drone_id}' is not a LIVE vehicle")
    try:
        ok = link.arm()
    except MAVLinkCommandError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    if not ok:
        raise HTTPException(status_code=409, detail="Arm command rejected by flight controller")
    return {"drone_id": drone_id, "armed": True}


@router.post("/vehicles/{drone_id}/disarm")
@limiter.limit("20/minute")
async def disarm_vehicle(request: Request, drone_id: str, current_user: User = Depends(get_current_operator_user)):
    link = registry.get_link(drone_id)
    if link is None:
        raise HTTPException(status_code=404, detail=f"'{drone_id}' is not a LIVE vehicle")
    try:
        ok = link.disarm()
    except MAVLinkCommandError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    if not ok:
        raise HTTPException(status_code=409, detail="Disarm command rejected by flight controller")
    return {"drone_id": drone_id, "armed": False}


@router.post("/emergency-stop-all")
@limiter.limit("30/minute")
async def emergency_stop_all(request: Request, current_user: User = Depends(get_current_operator_user)):
    """Kill switch — RTL every LIVE vehicle immediately, independent of the
    normal dispatch/CBF path. The desktop app requires an explicit user
    confirmation before calling this; the endpoint itself executes
    unconditionally once called, by design — this is the one action in
    the whole system meant to bypass every other gate. Rate-limited against
    accidental/malicious spam, not against legitimate emergency use — the
    limit is generous (30/min) precisely because this must never be the
    thing standing between an operator and stopping a fleet."""
    results = registry.emergency_stop_all()
    return {"results": results}


@router.websocket("/ws/telemetry")
async def telemetry_stream(websocket: WebSocket, token: Optional[str] = None):
    """Live LIVE-drone telemetry, pushed as {"type": "telemetry.update",
    "drone_id": ..., ...VehicleTelemetry fields} on every poll cycle.
    Requires ?token=<jwt> — this stream carries live drone position/state,
    so it gets the same auth bar as the REST endpoints, not an open one."""
    if token is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Missing token")
        return
    with get_db_session() as db:
        user = get_user_from_token(token, db)
        user_is_active = user.is_active if user else False
    if user is None or not user_is_active:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid or expired token")
        return

    await websocket.accept()
    _ws_connections.append(websocket)
    logger.info(f"Hardware telemetry WebSocket connected. Total: {len(_ws_connections)}")
    try:
        await websocket.send_json({
            "type": "connected",
            "message": "AeroFleet hardware telemetry stream connected.",
            "clients": len(_ws_connections),
        })
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                if data == "ping":
                    await websocket.send_json({"type": "pong"})
            except asyncio.TimeoutError:
                await websocket.send_json({"type": "keepalive"})
    except WebSocketDisconnect:
        logger.info("Hardware telemetry WebSocket disconnected.")
    finally:
        if websocket in _ws_connections:
            _ws_connections.remove(websocket)


_polling_task: Optional[asyncio.Task] = None


def start_background_polling() -> None:
    """Called once from app.py's startup event to kick off the telemetry
    poll loop as a background asyncio task on the running event loop."""
    global _polling_task
    if _polling_task is None:
        _polling_task = asyncio.create_task(registry.run_forever(poll_interval_s=0.5))


def stop_background_polling() -> None:
    registry.stop()
