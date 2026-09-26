"""Desktop ↔ headset pairing and scenario sync (see aerofleet/vr/sessions.py).

Desktop endpoints use the operator's normal login. Headset endpoints are
reached through the LAN gateway (aerofleet/vr/gateway.py): the pairing
handshake needs no login — an approval on the desktop is what grants
access — and everything after it carries the headset's session token.
"""
from __future__ import annotations

import os
import socket
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field

from aerofleet.api.routes.auth import get_current_active_user
from aerofleet.data.models.models import User
from aerofleet.utils.logging import get_logger
from aerofleet.vr.beacon import Beacon, lan_addresses
from aerofleet.vr.gateway import GATEWAY_PORT, VR_TOKEN_HEADER, GatewayServer
from aerofleet.vr.sessions import SessionError, VrSession, get_registry

logger = get_logger(__name__)
router = APIRouter()

# Tests and CI set this to "off": sessions still work in-process, but no socket is opened on the LAN.
NETWORK_ENABLED = os.environ.get("AEROFLEET_VR_NETWORK", "on").lower() != "off"
API_PORT = int(os.environ.get("AEROFLEET_API_PORT", "8000"))

_registry = get_registry()
_gateway = GatewayServer(_registry, upstream_port=API_PORT)


def _beacon_payload() -> Dict[str, Any]:
    s = _registry._session  # read-only snapshot for the broadcast
    return {"aerofleet_vr": 1, "host": socket.gethostname(), "gateway_port": GATEWAY_PORT,
            "addrs": lan_addresses(), "session": s.session_id if s else None}


_beacon = Beacon(_beacon_payload)


def _on_open(_: VrSession) -> None:
    if NETWORK_ENABLED:
        _gateway.start()
        _beacon.start()


def _on_close(_: VrSession) -> None:
    _beacon.stop()
    _gateway.stop()


_registry.on_open.append(_on_open)
_registry.on_close.append(_on_close)


def _raise(e: SessionError):
    raise HTTPException(status_code=e.status, detail=e.detail)


def _desktop_view(s: VrSession) -> Dict[str, Any]:
    return {
        **s.public(),
        "scenario": s.scenario,
        "host": socket.gethostname(),
        "addresses": lan_addresses(),
        "gateway_port": GATEWAY_PORT,
        "network": "on" if NETWORK_ENABLED else "off",
        "gateway_running": _gateway.running,
    }


# ── desktop ────────────────────────────────────────────────────────────

class Scenario(BaseModel):
    city: str = "pune"
    mode: str = Field("live", pattern="^(live|replay)$")
    incident_id: Optional[str] = None
    selected_drone: Optional[str] = None
    range_km: int = 4
    detail_all: bool = False
    show_buildings: bool = True


@router.post("/session")
async def open_session(user: User = Depends(get_current_active_user)) -> Dict[str, Any]:
    """Start (or resume) this operator's VR session: opens the LAN gateway and beacon so a
    headset on the same Wi-Fi can find this computer and ask to pair."""
    return _desktop_view(_registry.open(user.username))


@router.get("/session")
async def session_status(user: User = Depends(get_current_active_user)) -> Dict[str, Any]:
    """Polled by the desktop while the VR view is open: pending pair requests and the headset's status."""
    s = _registry.get(user.username)
    if s is None:
        raise HTTPException(status_code=404, detail="No VR session open")
    return _desktop_view(s)


@router.delete("/session")
async def close_session(user: User = Depends(get_current_active_user)) -> Dict[str, Any]:
    return {"closed": _registry.close(user.username)}


@router.put("/session/scenario")
async def push_scenario(scenario: Scenario, user: User = Depends(get_current_active_user)) -> Dict[str, Any]:
    try:
        return {"scenario_version": _registry.set_scenario(user.username, scenario.model_dump())}
    except SessionError as e:
        _raise(e)


@router.post("/session/requests/{request_id}/{decision}")
async def decide_request(request_id: str, decision: str, user: User = Depends(get_current_active_user)) -> Dict[str, Any]:
    if decision not in ("approve", "deny"):
        raise HTTPException(status_code=404, detail="Unknown decision")
    try:
        r = _registry.decide(user.username, request_id, decision == "approve")
    except SessionError as e:
        _raise(e)
    return r.public()


class LocalDevice(BaseModel):
    device_name: str = "This PC (Quest Link)"


@router.post("/session/local-device")
async def local_device(body: LocalDevice, user: User = Depends(get_current_active_user)) -> Dict[str, Any]:
    """For the viewer this desktop launches on the same PC (Quest Link): no pairing handshake —
    returns a session token the launcher passes to the viewer as AEROFLEET_TOKEN."""
    try:
        token = _registry.local_device(user.username, body.device_name)
    except SessionError as e:
        _raise(e)
    return {"token": token, "gateway_url": f"http://127.0.0.1:{GATEWAY_PORT}"}


@router.post("/session/device/disconnect")
async def disconnect_device(user: User = Depends(get_current_active_user)) -> Dict[str, Any]:
    try:
        _registry.disconnect_device(user.username)
    except SessionError as e:
        _raise(e)
    return {"disconnected": True}


# ── headset: pairing handshake (public, via the gateway) ───────────────

@router.get("/hello")
async def hello() -> Dict[str, Any]:
    return {"aerofleet_vr": 1, "host": socket.gethostname(), "session_open": _registry._session is not None}


class PairRequestBody(BaseModel):
    device_name: str = Field("VR headset", max_length=40)


@router.post("/pair-requests")
async def request_pairing(body: PairRequestBody, request: Request) -> Dict[str, Any]:
    ip = request.headers.get("x-forwarded-for") or (request.client.host if request.client else "")
    try:
        r = _registry.request_pairing(body.device_name, ip)
    except SessionError as e:
        _raise(e)
    return {"request_id": r.request_id, "confirm_code": r.confirm_code, "poll_after_s": 1.0}


@router.get("/pair-requests/{request_id}")
async def poll_pairing(request_id: str) -> Dict[str, Any]:
    return _registry.poll_pairing(request_id)


# ── headset: after pairing ─────────────────────────────────────────────

def _device_session(token: Optional[str]) -> VrSession:
    s = _registry.resolve_token(token)
    if s is None:
        raise HTTPException(status_code=401, detail="Not paired, or the desktop ended the VR session")
    return s


@router.get("/device/scenario")
async def device_scenario(x_aerofleet_vr_token: Optional[str] = Header(None, alias=VR_TOKEN_HEADER)) -> Dict[str, Any]:
    s = _device_session(x_aerofleet_vr_token)
    return {"scenario_version": s.scenario_version, "scenario": s.scenario, "owner": s.owner}


@router.post("/device/heartbeat")
async def device_heartbeat(status: Dict[str, Any],
                           x_aerofleet_vr_token: Optional[str] = Header(None, alias=VR_TOKEN_HEADER)) -> Dict[str, Any]:
    s = _registry.heartbeat(x_aerofleet_vr_token or "", status)
    if s is None:
        raise HTTPException(status_code=401, detail="Not paired, or the desktop ended the VR session")
    return {"ok": True, "scenario_version": s.scenario_version}
