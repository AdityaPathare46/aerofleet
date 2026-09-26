"""The only part of AeroFleet reachable from the local network — and only while
a VR session is open.

The main API stays bound to 127.0.0.1. A standalone headset on Wi-Fi reaches
this gateway instead (0.0.0.0:GATEWAY_PORT), which forwards a fixed allowlist
of requests to the main API and refuses everything else:

  * unauthenticated: the pairing handshake (hello, request, poll) — that is
    all a device that hasn't been approved on the desktop can do;
  * with the paired headset's session token: GET-only reads of exactly what
    the VR view renders, plus the headset's own scenario/heartbeat calls.

Why not accept normal JWTs here: login tokens are long-lived and their
signing key may be a shared default on some installs, so a LAN-facing
listener must not trust them. The headset's token is random, held only in
this process's memory, and dies with the session. For forwarded reads the
gateway mints a short-lived JWT for the session owner itself, so the main
API's auth is unchanged and the token never leaves this machine.
"""
from __future__ import annotations

import re
import threading
import time
from datetime import timedelta
from typing import Dict, Optional, Tuple

import httpx
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

from aerofleet.utils.logging import get_logger
from aerofleet.vr.sessions import VrSessionRegistry

logger = get_logger(__name__)

GATEWAY_PORT = 8765
VR_TOKEN_HEADER = "X-AeroFleet-VR-Token"

_PUBLIC = [
    ("GET", re.compile(r"^/api/v1/vr/hello$")),
    ("POST", re.compile(r"^/api/v1/vr/pair-requests$")),
    ("GET", re.compile(r"^/api/v1/vr/pair-requests/[0-9a-f]{12}$")),
]
_DEVICE = [
    ("GET", re.compile(r"^/api/v1/vr/device/scenario$")),
    ("POST", re.compile(r"^/api/v1/vr/device/heartbeat$")),
]
_READ = [re.compile(p) for p in (
    r"^/api/v1/cities/?$",
    r"^/api/v1/cities/[a-z]+/(roads|buildings)$",
    r"^/api/v1/geofence/zones$",
    r"^/api/v1/fleet/depots$",
    r"^/api/v1/safety/live-margins$",
    r"^/api/v1/incidents/?$",
    r"^/api/v1/incidents/INC-[A-Z0-9]+/vr-scene$",
)]
_HOP_HEADERS = {"connection", "keep-alive", "transfer-encoding", "te", "upgrade", "content-encoding", "content-length", "host"}


def classify(method: str, path: str) -> Optional[str]:
    """'public', 'device', 'read', or None (refused)."""
    if any(method == m and p.match(path) for m, p in _PUBLIC):
        return "public"
    if any(method == m and p.match(path) for m, p in _DEVICE):
        return "device"
    if method == "GET" and any(p.match(path) for p in _READ):
        return "read"
    return None


def build_gateway_app(registry: VrSessionRegistry, upstream: httpx.AsyncBaseTransport, upstream_base: str) -> Starlette:
    minted: Dict[str, Tuple[str, float]] = {}

    def owner_jwt(owner: str) -> str:
        from aerofleet.api.routes.auth import create_access_token

        tok, exp = minted.get(owner, ("", 0.0))
        if time.time() > exp - 30:
            tok = create_access_token({"sub": owner}, expires_delta=timedelta(minutes=5))
            minted[owner] = (tok, time.time() + 300)
        return tok

    client = httpx.AsyncClient(transport=upstream, base_url=upstream_base, timeout=20.0)

    async def handle(request: Request) -> Response:
        path, method = request.url.path, request.method
        kind = classify(method, path)
        if kind is None:
            return JSONResponse({"detail": "Not available over the VR link"}, status_code=404)

        headers = {"X-Forwarded-For": request.client.host if request.client else ""}
        if request.headers.get("content-type"):
            headers["content-type"] = request.headers["content-type"]
        if kind != "public":
            auth = request.headers.get("authorization", "")
            token = auth[7:] if auth.lower().startswith("bearer ") else request.headers.get(VR_TOKEN_HEADER, "")
            session = registry.resolve_token(token)
            if session is None:
                return JSONResponse({"detail": "Not paired — pair this headset from the AeroFleet desktop app"},
                                    status_code=401)
            headers[VR_TOKEN_HEADER] = token
            if kind == "read":
                headers["Authorization"] = f"Bearer {owner_jwt(session.owner)}"

        upstream_resp = await client.request(method, path, params=request.query_params, headers=headers,
                                             content=await request.body())
        out_headers = {k: v for k, v in upstream_resp.headers.items() if k.lower() not in _HOP_HEADERS}
        return Response(upstream_resp.content, status_code=upstream_resp.status_code, headers=out_headers)

    return Starlette(routes=[Route("/{path:path}", handle, methods=["GET", "POST"])])


class GatewayServer:
    """Runs the gateway on its own uvicorn server/thread, forwarding to the main API over localhost."""

    def __init__(self, registry: VrSessionRegistry, upstream_port: int, port: int = GATEWAY_PORT) -> None:
        self.registry, self.upstream_port, self.port = registry, upstream_port, port
        self._server = None
        self._thread: Optional[threading.Thread] = None

    @property
    def running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def start(self) -> None:
        if self.running:
            return
        import uvicorn

        app = build_gateway_app(self.registry, httpx.AsyncHTTPTransport(), f"http://127.0.0.1:{self.upstream_port}")
        # log_config=None: a second uvicorn must not reconfigure the process's logging (it silently
        # replaced the main API server's access logger).
        config = uvicorn.Config(app, host="0.0.0.0", port=self.port, log_level="warning", lifespan="off", log_config=None)
        self._server = uvicorn.Server(config)
        self._thread = threading.Thread(target=self._server.run, name="aerofleet-vr-gateway", daemon=True)
        self._thread.start()
        logger.info(f"VR gateway listening on 0.0.0.0:{self.port} (forwarding a read-only allowlist to 127.0.0.1:{self.upstream_port})")

    def stop(self) -> None:
        if self._server is not None:
            self._server.should_exit = True
        logger.info("VR gateway stopped")
