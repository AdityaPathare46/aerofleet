"""Core dataclasses for the drone fleet simulation domain.

In-memory simulation state (as opposed to the SQLAlchemy persistence
models in aerofleet/data/models/models.py, which snapshot this state
to the database for the API/UI layers).
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class DroneState(Enum):
    IDLE = "IDLE"
    EN_ROUTE = "EN_ROUTE"
    DELIVERING = "DELIVERING"
    RETURNING = "RETURNING"
    CHARGING = "CHARGING"
    SWAPPING_BATTERY = "SWAPPING_BATTERY"
    EMERGENCY_LANDING = "EMERGENCY_LANDING"
    GROUNDED = "GROUNDED"


@dataclass
class Battery:
    """Simple energy-budget model. Capacity/soc in Wh terms; reserve_margin
    is the fraction of usable capacity that must always be kept for a safe
    return-to-home flight (enforced by the CBF gate's battery_reserve_margin
    constraint, not just by this class)."""

    capacity_wh: float = 500.0
    soc: float = 1.0          # state of charge, 0..1
    degradation: float = 0.0  # capacity fade, 0..1
    reserve_margin: float = 0.20

    @property
    def effective_capacity_wh(self) -> float:
        return self.capacity_wh * (1.0 - self.degradation)

    @property
    def usable_wh(self) -> float:
        return self.effective_capacity_wh * self.soc

    @property
    def reserve_wh(self) -> float:
        return self.effective_capacity_wh * self.reserve_margin

    @property
    def available_wh(self) -> float:
        """Energy usable for the outbound mission before dipping into the RTH reserve."""
        return max(0.0, self.usable_wh - self.reserve_wh)

    def consume(self, wh: float) -> None:
        cap = self.effective_capacity_wh
        self.soc = max(0.0, self.soc - (wh / cap if cap > 0 else 1.0))

    def swap(self) -> None:
        """Instant battery swap at a depot swap station."""
        self.soc = 1.0

    def fast_charge(self, wh: float) -> None:
        cap = self.effective_capacity_wh
        self.soc = min(1.0, self.soc + (wh / cap if cap > 0 else 0.0))


@dataclass
class Drone:
    drone_id: str
    node: int                      # current position: city graph node id
    battery: Battery = field(default_factory=Battery)
    payload_capacity_kg: float = 5.0
    current_payload_kg: float = 0.0
    state: DroneState = DroneState.IDLE
    altitude_band_m: float = 60.0
    home_depot_id: Optional[str] = None
    order_id: Optional[str] = None
    total_distance_km: float = 0.0
    last_updated: float = field(default_factory=time.time)

    # Hardware link — SIMULATED (default) drones are pure in-memory sim state
    # driven by dispatch.py; LIVE drones are backed by a real MAVLinkVehicle
    # connection and these fields are refreshed by the telemetry poller
    # instead (aerofleet/hardware/telemetry_service.py).
    lat: Optional[float] = None
    lon: Optional[float] = None
    link_mode: str = "SIMULATED"   # "SIMULATED" | "LIVE"
    armed: bool = False
    flight_mode: str = ""
    last_telemetry_at: Optional[float] = None

    # NOMINAL/DEGRADED/STORE_FORWARD/ISOLATED — see aerofleet/safety/d2d_mesh.py.
    # Driven by the same consecutive-missed-heartbeat signal
    # aerofleet/hardware/telemetry_service.py's poll loop already produces
    # for LIVE drones; only meaningful for LIVE drones (SIMULATED ones have
    # no real link to degrade, so this stays NOMINAL for them).
    d2d_link_state: str = "NOMINAL"

    # Names of currently-unresolved aerofleet.fault_tolerance.multi_fault_handler
    # FaultType entries for this drone, as detected live from telemetry by
    # DroneLinkRegistry._detect_faults(). Empty for SIMULATED drones and for
    # LIVE drones with no active fault.
    active_fault_types: List[str] = field(default_factory=list)

    @property
    def is_available(self) -> bool:
        return self.state == DroneState.IDLE and self.battery.soc > self.battery.reserve_margin

    def to_dict(self) -> Dict:
        return {
            "drone_id": self.drone_id,
            "node": self.node,
            "soc": round(self.battery.soc, 3),
            "state": self.state.value,
            "payload_kg": self.current_payload_kg,
            "payload_capacity_kg": self.payload_capacity_kg,
            "altitude_band_m": self.altitude_band_m,
            "home_depot_id": self.home_depot_id,
            "order_id": self.order_id,
            "total_distance_km": round(self.total_distance_km, 3),
            "lat": self.lat,
            "lon": self.lon,
            "link_mode": self.link_mode,
            "armed": self.armed,
            "flight_mode": self.flight_mode,
            "last_telemetry_at": self.last_telemetry_at,
            "d2d_link_state": self.d2d_link_state,
            "active_fault_types": list(self.active_fault_types),
        }


@dataclass
class Depot:
    depot_id: str
    name: str
    node: int
    launch_pad_slots: int = 4
    battery_swap_slots: int = 2
    fast_charge_slots: int = 2
    swap_time_minutes: float = 3.0
    inventory: Dict[str, int] = field(default_factory=dict)
    queued_drones: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "depot_id": self.depot_id,
            "name": self.name,
            "node": self.node,
            "launch_pad_slots": self.launch_pad_slots,
            "battery_swap_slots": self.battery_swap_slots,
            "queued_drones": list(self.queued_drones),
        }


@dataclass
class DeliveryOrder:
    order_id: str
    origin_depot_id: str
    destination_node: int
    payload_kg: float
    created_at: float = field(default_factory=time.time)
    deadline_minutes: float = 30.0
    priority: str = "STANDARD"     # STANDARD, EXPRESS, MEDICAL
    status: str = "PENDING"        # PENDING, ASSIGNED, EN_ROUTE, DELIVERED, FAILED
    assigned_drone_id: Optional[str] = None

    def to_dict(self) -> Dict:
        return {
            "order_id": self.order_id,
            "origin_depot_id": self.origin_depot_id,
            "destination_node": self.destination_node,
            "payload_kg": self.payload_kg,
            "deadline_minutes": self.deadline_minutes,
            "priority": self.priority,
            "status": self.status,
            "assigned_drone_id": self.assigned_drone_id,
        }
