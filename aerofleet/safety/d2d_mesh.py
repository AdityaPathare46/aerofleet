"""Decentralized drone-to-drone (D2D) safety mesh — the peer-broadcast
backstop to the centralized CBF gate, activated only when the central
dispatch-server link degrades.

Design: docs/D2D_MESH_RESEARCH_DESIGN.md. Short version: every drone
periodically broadcasts a D2DBasicSafetyMessage (position, velocity,
heading — modeled on India's AIS-230 V2V standard's broadcast content and
DGCA's Remote ID mandate, NOT on C-V2X's 5.9GHz spectrum, which DGCA hasn't
authorized for UAVs). A link-state machine, adapted from
aerofleet/planning/communication_resilience.py's satellite-ISL state
machine, classifies central-channel health. When the central link is
degraded beyond a threshold, a drone builds its own CBF trajectory_points
from ONLY the D2D messages it has directly received — feeding the exact
same, unmodified aerofleet.safety.cbf_gate.ControlBarrierFunctionGate — so
the safety guarantee is identical whether evaluated centrally or
peer-locally, only the data source changes.

Terminology note: STORE_FORWARD is kept for continuity with
communication_resilience.py's vocabulary, but means something narrower
here — "central link down beyond threshold, peer-derived CBF evaluation is
authoritative for this drone" — not literal DTN bundle buffering, which
doesn't apply to a live local broadcast channel the way it does to a
satellite's scheduled contact windows.
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass
from enum import Enum, auto
from typing import Any, Dict, List, Optional

from aerofleet.utils.logging import get_logger

logger = get_logger(__name__)

# Unlike communication_resilience.py's ISOLATION_TIMEOUT_S = 3600.0 ("1 orbit
# period"), a drone that hasn't heard from the dispatch server in seconds
# should already be conservative — these are UTM-appropriate, not
# orbital-mechanics-appropriate, timeouts.
DEGRADED_MISSED_HEARTBEATS = 2
STORE_FORWARD_MISSED_HEARTBEATS = 6      # ~30s at a 5s heartbeat cadence
ISOLATION_TIMEOUT_S = 60.0               # no peers heard from either
PEER_MESSAGE_TTL_S = 5.0                 # a D2D-BSM older than this is stale


class D2DLinkState(Enum):
    NOMINAL = auto()        # central link healthy; CBF gate is server-side & authoritative
    DEGRADED = auto()       # central link intermittent; D2D runs as a hot standby, advisory only
    STORE_FORWARD = auto()  # central link down past threshold; D2D-derived CBF is authoritative
    ISOLATED = auto()       # no central link AND no peers heard from — fall back to
                             # single-drone contingency handling (safety/emergency_landing.py)


@dataclass
class D2DBasicSafetyMessage:
    """Modeled on AIS-230's V2V broadcast content (position, velocity,
    heading) and DGCA's Remote ID mandate — see
    docs/D2D_MESH_RESEARCH_DESIGN.md Section 3.2 for the field-by-field
    rationale."""
    drone_id: str
    timestamp_utc: float
    lat: float
    lon: float
    alt_m: float
    velocity_mps: float
    heading_deg: float
    battery_soc: float
    link_state: str  # the SENDER's own D2DLinkState.name, informational only


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in meters — fine-grained enough for D2D
    separation checks at city-block scale, matching the precision
    aerofleet/safety/conflict_screening.py already accepts for its own
    conflict math."""
    R = 6371000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.asin(min(1.0, math.sqrt(a)))


class D2DLinkStateMachine:
    """Classifies central-dispatch-server link health from consecutive
    missed heartbeats, and peer availability from whether any D2D-BSM has
    been received recently. NOMINAL until proven otherwise — a drone that
    has never missed a heartbeat has no reason to distrust the centralized
    CBF gate."""

    def __init__(self) -> None:
        self._missed_heartbeats = 0
        self._last_peer_contact: Optional[float] = None
        self._state = D2DLinkState.NOMINAL

    @property
    def state(self) -> D2DLinkState:
        return self._state

    def record_heartbeat(self) -> D2DLinkState:
        """Call whenever a central-server heartbeat/telemetry-ack succeeds."""
        self._missed_heartbeats = 0
        return self._recompute()

    def record_missed_heartbeat(self) -> D2DLinkState:
        self._missed_heartbeats += 1
        return self._recompute()

    def record_peer_contact(self) -> None:
        self._last_peer_contact = time.monotonic()

    def _recompute(self) -> D2DLinkState:
        prev = self._state
        heard_from_a_peer_recently = (
            self._last_peer_contact is not None
            and time.monotonic() - self._last_peer_contact < ISOLATION_TIMEOUT_S
        )

        if self._missed_heartbeats >= STORE_FORWARD_MISSED_HEARTBEATS:
            self._state = D2DLinkState.STORE_FORWARD if heard_from_a_peer_recently else D2DLinkState.ISOLATED
        elif self._missed_heartbeats >= DEGRADED_MISSED_HEARTBEATS:
            self._state = D2DLinkState.DEGRADED
        else:
            self._state = D2DLinkState.NOMINAL

        if self._state != prev:
            logger.info(f"D2D link state transition: {prev.name} -> {self._state.name}")
        return self._state


class D2DTransceiver:
    """Per-drone peer table + trajectory-point projection. Receives
    D2DBasicSafetyMessage broadcasts (in the current simulation-first
    implementation, from tools/mock_mavlink_vehicle.py's UDP broadcast —
    see docs/D2D_MESH_RESEARCH_DESIGN.md Section 3.5) and turns them into
    the exact input shape aerofleet.safety.cbf_gate's
    ControlBarrierFunctionGate.evaluate_trajectory() already expects, with
    zero changes to that gate."""

    def __init__(self, own_drone_id: str) -> None:
        self.own_drone_id = own_drone_id
        self._peers: Dict[str, D2DBasicSafetyMessage] = {}
        self._received_at: Dict[str, float] = {}
        self.link_state = D2DLinkStateMachine()

    def receive(self, msg: D2DBasicSafetyMessage) -> None:
        if msg.drone_id == self.own_drone_id:
            return
        self._peers[msg.drone_id] = msg
        self._received_at[msg.drone_id] = time.monotonic()
        self.link_state.record_peer_contact()

    def evict_stale(self, ttl_s: float = PEER_MESSAGE_TTL_S) -> List[str]:
        now = time.monotonic()
        stale = [drone_id for drone_id, ts in self._received_at.items() if now - ts > ttl_s]
        for drone_id in stale:
            self._peers.pop(drone_id, None)
            self._received_at.pop(drone_id, None)
        if stale:
            logger.debug(f"[{self.own_drone_id}] Evicted stale D2D peers: {stale}")
        return stale

    def known_peers(self) -> List[D2DBasicSafetyMessage]:
        self.evict_stale()
        return list(self._peers.values())

    def to_trajectory_points(self, own_state: Dict[str, Any]) -> List[Dict[str, Any]]:
        """own_state must carry this drone's own lat/lon plus whatever
        non-geometric CBF fields matter (battery_margin_wh, altitude_m,
        wind_speed_mps, etc. — see cbf_gate.py's constraint list). Returns
        one point per known peer with separation_m computed from that
        peer's last broadcast position; falls back to a single
        own-state-only point when no peers are known, so altitude/battery/
        etc. constraints still get evaluated even with zero D2D traffic."""
        peers = self.known_peers()
        if not peers:
            return [dict(own_state)]

        points = []
        for peer in peers:
            point = dict(own_state)
            point["separation_m"] = haversine_m(
                own_state.get("lat", 0.0), own_state.get("lon", 0.0), peer.lat, peer.lon
            )
            points.append(point)
        return points
