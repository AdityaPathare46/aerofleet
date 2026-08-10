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
import os
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
from aerofleet.event_bus.redis_bus import RedisEventBridge
from aerofleet.hardware.mavlink_link import MAVLinkCommandError, MAVLinkConnectionError
from aerofleet.hardware.telemetry_service import get_drone_link_registry
from aerofleet.utils.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()

# Single event bus shared by the background telemetry poll loop (started
# in app.py's startup hook via start_background_polling()) and this
# module's WebSocket broadcaster. redis_bridge additively relays every
# telemetry.update event to every other worker process via Redis pub/sub
# when AEROFLEET_REDIS_URL is set (Phase AH) — a no-op pass-through
# otherwise, so single-process behavior is unchanged.
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
    # Fan this event out to every other worker process (no-op if Redis
    # isn't configured) — this is the only place a LIVE telemetry event is
    # generated, since it always originates from this same registry's own
    # run_forever() poll loop, whether or not this process owns hardware.
    asyncio.create_task(redis_bridge.relay_to_redis(event))


def _on_redis_relayed_event(event) -> None:
    # Fired when listen_forever() delivers an event that arrived from
    # ANOTHER worker process's registry — same handling as a locally-
    # generated one, so a WS client connected to a non-hardware-owner
    # worker still sees live telemetry. Deliberately bypasses event_bus
    # entirely (see RedisEventBridge's docstring) so this can't loop back
    # into relay_to_redis().
    asyncio.create_task(_broadcast({"type": "telemetry.update", "drone_id": event.source, **event.payload}))


redis_bridge = RedisEventBridge(on_relayed_event=_on_redis_relayed_event)

event_bus.subscribe("telemetry.update", _on_telemetry_event)


def require_hardware_owner() -> None:
    """FastAPI dependency guarding every request that would mutate this
    process's own `registry`/FleetState — connect/disconnect/arm/disarm/
    emergency-stop, and (imported into orders.py) dispatch itself. Phase AH
    documented this gap explicitly rather than building it: a non-owner
    worker has an empty, uninitialized `registry`/FleetState, so accepting
    one of these requests wouldn't corrupt anything shared — it would
    silently do nothing (connect_vehicle would still succeed since it
    doesn't check ownership; emergency_stop_all would silently RTL zero
    vehicles because this worker's registry never has any LIVE links),
    which is a worse failure mode for an operator than a loud, immediate
    error telling them to route the request to the actual owner."""
    if not hardware_owner_enabled():
        raise HTTPException(
            status_code=503,
            detail=(
                "This server instance is not the hardware owner "
                "(AEROFLEET_HARDWARE_OWNER=0) and cannot accept dispatch or "
                "hardware-control requests — route this request to the "
                "worker configured as the hardware owner."
            ),
        )


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
    _owner: None = Depends(require_hardware_owner),
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
    _owner: None = Depends(require_hardware_owner),
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
async def arm_vehicle(
    request: Request,
    drone_id: str,
    current_user: User = Depends(get_current_operator_user),
    _owner: None = Depends(require_hardware_owner),
):
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
async def disarm_vehicle(
    request: Request,
    drone_id: str,
    current_user: User = Depends(get_current_operator_user),
    _owner: None = Depends(require_hardware_owner),
):
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
async def emergency_stop_all(
    request: Request,
    current_user: User = Depends(get_current_operator_user),
    _owner: None = Depends(require_hardware_owner),
):
    """Kill switch — RTL every LIVE vehicle immediately, independent of the
    normal dispatch/CBF path. The desktop app requires an explicit user
    confirmation before calling this; the endpoint itself executes
    unconditionally once called, by design — this is the one action in
    the whole system meant to bypass every other gate. Rate-limited against
    accidental/malicious spam, not against legitimate emergency use — the
    limit is generous (30/min) precisely because this must never be the
    thing standing between an operator and stopping a fleet.

    Guarded by require_hardware_owner() same as the other mutating
    endpoints here — deliberately, even though it's a kill switch: on a
    non-owner worker, registry._links is always empty (this process never
    ran register() for any drone), so an unguarded call would silently RTL
    zero vehicles while looking like a 200 success. A loud 503 telling the
    operator to hit the actual owner worker is the safer failure mode for
    a kill switch than a silent no-op that looks like it worked."""
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
_redis_listener_task: Optional[asyncio.Task] = None


def hardware_owner_enabled() -> bool:
    """Whether THIS process is allowed to own real MAVLink connections and
    run the telemetry poll loop (Phase AH). Defaults to true — an unset
    AEROFLEET_HARDWARE_OWNER means "single-process deployment," which
    behaves exactly as every version of this app before Phase AH did. In a
    real multi-worker deployment, exactly one worker's process env should
    set this to "0"/"false" for every worker except the one designated as
    the hardware owner — see docs/MULTI_WORKER_ARCHITECTURE.md for why a
    MAVLink link can't safely be owned by more than one process regardless
    of what else is shared via Redis."""
    return os.environ.get("AEROFLEET_HARDWARE_OWNER", "1").lower() not in ("0", "false", "no")


def start_background_polling() -> None:
    """Called once from app.py's startup event to kick off the telemetry
    poll loop as a background asyncio task on the running event loop —
    only on the process that owns real hardware (hardware_owner_enabled());
    every other worker still serves WS/REST traffic normally, receiving
    telemetry via the Redis relay instead of running its own MAVLink polls."""
    global _polling_task
    if not hardware_owner_enabled():
        logger.info("AEROFLEET_HARDWARE_OWNER=0 — this process will not poll MAVLink hardware directly")
        return
    if _polling_task is None:
        _polling_task = asyncio.create_task(registry.run_forever(poll_interval_s=0.5))


def stop_background_polling() -> None:
    global _polling_task
    registry.stop()
    # Previously missing (same class of bug fixed in explanation_worker.py /
    # policy_review_worker.py / incident_forensics_worker.py, Phase AF) —
    # without resetting _polling_task, a second startup_event within the
    # same process (e.g. across TestClient contexts in one pytest session)
    # would see _polling_task already set and silently never restart
    # telemetry polling.
    _polling_task = None


def start_background_redis_listener() -> None:
    """Runs on every worker (owner or not) so relayed telemetry from
    whichever worker owns hardware reaches this worker's own WS clients.
    No-op if AEROFLEET_REDIS_URL isn't set."""
    global _redis_listener_task
    if _redis_listener_task is None and redis_bridge.redis_enabled:
        _redis_listener_task = asyncio.create_task(redis_bridge.listen_forever())


def stop_background_redis_listener() -> None:
    global _redis_listener_task
    redis_bridge.stop()
    _redis_listener_task = None
