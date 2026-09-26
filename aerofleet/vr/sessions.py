"""Desktop ↔ headset pairing sessions.

The desktop app (one operator, one backend on their laptop) opens a VR
session when the operator asks to connect a headset. While it is open:

  * the headset finds this computer (vr/beacon.py) and asks to pair;
  * the desktop shows the request with a 4-digit confirm code that the
    headset also displays — the operator approves only if they match,
    so a stranger's device on the same Wi-Fi can't slip in;
  * on approval the headset receives a random, server-held session token
    (not a JWT — see vr/gateway.py for why), and from then on follows the
    *scenario* the desktop pushes: city, live/replay, incident, selected
    drone, range.

State is in memory on purpose: a session only means anything while this
backend process and the operator's desktop are both running. It closes
when the desktop closes it, or after DESKTOP_IDLE_S without the desktop
polling (the app was quit or the laptop slept).
"""
from __future__ import annotations

import secrets
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

PAIR_REQUEST_TTL_S = 120.0
DESKTOP_IDLE_S = 90.0
DEVICE_STALE_S = 10.0
MAX_PENDING_REQUESTS = 3

PENDING, APPROVED, DENIED, EXPIRED = "PENDING", "APPROVED", "DENIED", "EXPIRED"


@dataclass
class PairRequest:
    request_id: str
    device_name: str
    confirm_code: str
    client_ip: str
    created_at: float
    status: str = PENDING
    token: Optional[str] = None       # handed to the headset exactly once, then cleared
    token_delivered: bool = False

    def public(self) -> Dict[str, Any]:
        return {"request_id": self.request_id, "device_name": self.device_name, "confirm_code": self.confirm_code,
                "client_ip": self.client_ip, "age_s": round(time.time() - self.created_at, 1), "status": self.status}


@dataclass
class Device:
    name: str
    via: str                           # "wifi" | "local" (Quest Link on this PC)
    token: str
    connected_at: float
    last_seen: float
    status: Dict[str, Any] = field(default_factory=dict)

    def public(self) -> Dict[str, Any]:
        return {"name": self.name, "via": self.via, "connected_at": self.connected_at,
                "last_seen_s": round(time.time() - self.last_seen, 1),
                "online": time.time() - self.last_seen < DEVICE_STALE_S, "status": self.status}


@dataclass
class VrSession:
    session_id: str
    owner: str
    created_at: float
    last_desktop_poll: float
    scenario: Dict[str, Any] = field(default_factory=dict)
    scenario_version: int = 0
    requests: Dict[str, PairRequest] = field(default_factory=dict)
    device: Optional[Device] = None

    def public(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "scenario_version": self.scenario_version,
            "device": self.device.public() if self.device else None,
            "pending_requests": [r.public() for r in self.requests.values() if r.status == PENDING],
        }


class SessionError(Exception):
    def __init__(self, status: int, detail: str):
        super().__init__(detail)
        self.status, self.detail = status, detail


class VrSessionRegistry:
    """One active session at a time — the desktop app is single-operator."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._session: Optional[VrSession] = None
        self.on_open: List[Callable[[VrSession], None]] = []
        self.on_close: List[Callable[[VrSession], None]] = []

    # ── desktop side ────────────────────────────────────────────────────

    def open(self, owner: str) -> VrSession:
        with self._lock:
            self._expire_locked()
            if self._session and self._session.owner == owner:
                self._session.last_desktop_poll = time.time()
                return self._session
            old = self._session
            now = time.time()
            self._session = VrSession(secrets.token_hex(4), owner, now, now)
            new = self._session
        if old:
            self._fire(self.on_close, old)
        self._fire(self.on_open, new)
        return new

    def get(self, owner: str, touch: bool = True) -> Optional[VrSession]:
        with self._lock:
            self._expire_locked()
            s = self._session
            if s is None or s.owner != owner:
                return None
            if touch:
                s.last_desktop_poll = time.time()
            for r in s.requests.values():
                if r.status == PENDING and time.time() - r.created_at > PAIR_REQUEST_TTL_S:
                    r.status = EXPIRED
            return s

    def close(self, owner: str) -> bool:
        with self._lock:
            s = self._session
            if s is None or s.owner != owner:
                return False
            self._session = None
        self._fire(self.on_close, s)
        return True

    def set_scenario(self, owner: str, scenario: Dict[str, Any]) -> int:
        s = self._require(owner)
        with self._lock:
            if scenario != s.scenario:
                s.scenario = dict(scenario)
                s.scenario_version += 1
            return s.scenario_version

    def decide(self, owner: str, request_id: str, approve: bool) -> PairRequest:
        s = self._require(owner)
        with self._lock:
            r = s.requests.get(request_id)
            if r is None or r.status != PENDING:
                raise SessionError(404, "No pending pair request with that id")
            if not approve:
                r.status = DENIED
                return r
            token = secrets.token_urlsafe(32)
            r.status, r.token = APPROVED, token
            s.device = Device(r.device_name, "wifi", token, time.time(), time.time())
            # one headset at a time: every other pending request is refused
            for other in s.requests.values():
                if other.status == PENDING:
                    other.status = DENIED
            return r

    def local_device(self, owner: str, name: str) -> str:
        """Token for a viewer this desktop launches itself (Quest Link on this PC) — no pairing
        needed, the operator is already sitting at this machine."""
        s = self._require(owner)
        with self._lock:
            token = secrets.token_urlsafe(32)
            s.device = Device(name, "local", token, time.time(), time.time())
            return token

    def disconnect_device(self, owner: str) -> None:
        s = self._require(owner)
        with self._lock:
            s.device = None

    # ── headset side ───────────────────────────────────────────────────

    def request_pairing(self, device_name: str, client_ip: str) -> PairRequest:
        with self._lock:
            self._expire_locked()
            s = self._session
            if s is None:
                raise SessionError(409, "No VR session is open on this computer — open the VR view in AeroFleet first")
            pending = [r for r in s.requests.values() if r.status == PENDING]
            if len(pending) >= MAX_PENDING_REQUESTS:
                raise SessionError(429, "Too many pending pair requests — approve or deny them on the desktop")
            r = PairRequest(secrets.token_hex(6), device_name[:40] or "VR headset",
                            f"{secrets.randbelow(10_000):04d}", client_ip, time.time())
            s.requests[r.request_id] = r
            return r

    def poll_pairing(self, request_id: str) -> Dict[str, Any]:
        with self._lock:
            s = self._session
            r = s.requests.get(request_id) if s else None
            if r is None:
                return {"status": EXPIRED}
            if r.status == PENDING and time.time() - r.created_at > PAIR_REQUEST_TTL_S:
                r.status = EXPIRED
            out: Dict[str, Any] = {"status": r.status}
            if r.status == APPROVED and not r.token_delivered:
                out["token"] = r.token
                r.token_delivered = True
            return out

    def resolve_token(self, token: Optional[str]) -> Optional[VrSession]:
        if not token:
            return None
        with self._lock:
            self._expire_locked()
            s = self._session
            if s and s.device and secrets.compare_digest(s.device.token, token):
                return s
            return None

    def heartbeat(self, token: str, status: Dict[str, Any]) -> Optional[VrSession]:
        s = self.resolve_token(token)
        if s:
            with self._lock:
                s.device.last_seen = time.time()
                s.device.status = dict(status)
        return s

    # ── internals ──────────────────────────────────────────────────────

    def _require(self, owner: str) -> VrSession:
        s = self.get(owner)
        if s is None:
            raise SessionError(404, "No VR session open")
        return s

    def _expire_locked(self) -> None:
        s = self._session
        if s and time.time() - s.last_desktop_poll > DESKTOP_IDLE_S:
            self._session = None
            threading.Thread(target=self._fire, args=(self.on_close, s), daemon=True).start()

    @staticmethod
    def _fire(callbacks, session) -> None:
        for cb in callbacks:
            try:
                cb(session)
            except Exception:  # a listener failing must not break session bookkeeping
                pass


_REGISTRY: Optional[VrSessionRegistry] = None


def get_registry() -> VrSessionRegistry:
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = VrSessionRegistry()
    return _REGISTRY
