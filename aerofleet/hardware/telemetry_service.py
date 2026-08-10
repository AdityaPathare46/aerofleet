"""Registry of live MAVLink links + the background telemetry poll loop.

This is the bridge between the abstract `Drone` objects the rest of
AeroFleet reasons about (`aerofleet.fleet.state.FleetState`) and the real
`MAVLinkVehicle` connections in `aerofleet.hardware.mavlink_link`. A drone
becomes "LIVE" the moment it's registered here; `run_forever()` keeps its
`Drone.lat/lon/armed/flight_mode/last_telemetry_at` fields fresh and
broadcasts a `telemetry.update` event for the WebSocket layer (Phase L) to
pick up.
"""
from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import asdict
from typing import Dict, List, Optional

from aerofleet.event_bus.async_bus import AsyncEventBus, Event
from aerofleet.fault_tolerance.multi_fault_handler import FaultType, MultiFaultHandler
from aerofleet.fleet.models import DroneState
from aerofleet.fleet.state import get_fleet_state
from aerofleet.hardware.mavlink_link import MAVLinkConnectionError, MAVLinkVehicle, VehicleTelemetry
from aerofleet.safety.d2d_mesh import D2DLinkStateMachine
from aerofleet.safety.emergency_landing import EmergencyLandingPlanner
from aerofleet.utils.logging import get_logger

logger = get_logger(__name__)


class DroneLinkRegistry:
    def __init__(self, event_bus: AsyncEventBus):
        self.event_bus = event_bus
        self._links: Dict[str, MAVLinkVehicle] = {}
        self._cities: Dict[str, str] = {}
        # One link-state machine per LIVE drone — driven by this same poll
        # loop's success/failure signal, the same "consecutive missed
        # heartbeats" concept aerofleet/safety/d2d_mesh.py's D2DTransceiver
        # uses. Not fed by actual D2D-BSM broadcasts (the server doesn't
        # participate in the drone-to-drone mesh by design — see
        # docs/D2D_MESH_RESEARCH_DESIGN.md); this surfaces link-health for
        # operator visibility using the same state vocabulary.
        self._link_states: Dict[str, D2DLinkStateMachine] = {}
        # One MultiFaultHandler per LIVE drone (Phase AG) — conflict
        # resolution and survivability scoring must stay scoped to a single
        # vehicle's simultaneous faults, not mixed across the fleet.
        self._fault_handlers: Dict[str, MultiFaultHandler] = {}
        # fault_type -> currently-open ActiveFault.fault_id, so repeated
        # poll ticks don't re-register the same ongoing condition and so a
        # cleared condition can be resolved instead of left open forever.
        self._active_fault_ids: Dict[str, Dict[FaultType, str]] = {}
        self._running = False

    # Thresholds for detecting faults from real MAVLink telemetry fields
    # (aerofleet.hardware.mavlink_link.VehicleTelemetry). Deliberately
    # conservative approximations — MOTOR in particular has no dedicated
    # MAVLink field here and is inferred from MAV_STATE severity, which is
    # documented as approximate rather than overclaimed as true motor
    # diagnostics.
    BATTERY_CRITICAL_PCT = 15.0
    GPS_MIN_FIX_TYPE = 3  # below 3 = no reliable 3D fix
    CRITICAL_SYSTEM_STATUSES = {"CRITICAL", "EMERGENCY", "FLIGHT_TERMINATION"}

    def register(self, drone_id: str, city: str, connection_string: str) -> VehicleTelemetry:
        """Connect to a vehicle and flip its Drone to LIVE. Raises
        MAVLinkConnectionError if the vehicle never heartbeats."""
        if drone_id in self._links:
            self.unregister(drone_id)

        fleet = get_fleet_state(city)
        drone = fleet.get_drone(drone_id)
        if drone is None:
            raise ValueError(f"Drone '{drone_id}' not found in city '{city}'")

        vehicle = MAVLinkVehicle(connection_string, drone_id)
        vehicle.connect()

        self._links[drone_id] = vehicle
        self._cities[drone_id] = city
        self._link_states[drone_id] = D2DLinkStateMachine()
        self._fault_handlers[drone_id] = MultiFaultHandler()
        self._active_fault_ids[drone_id] = {}
        drone.link_mode = "LIVE"
        drone.d2d_link_state = D2DLinkStateMachine().state.name  # NOMINAL

        telemetry = vehicle.poll()
        self._apply_telemetry(drone, telemetry)
        logger.info(f"[{drone_id}] Registered as LIVE ({connection_string})")
        return telemetry

    def unregister(self, drone_id: str) -> None:
        vehicle = self._links.pop(drone_id, None)
        city = self._cities.pop(drone_id, None)
        self._link_states.pop(drone_id, None)
        self._fault_handlers.pop(drone_id, None)
        self._active_fault_ids.pop(drone_id, None)
        if vehicle is not None:
            vehicle.close()
        if city is not None:
            fleet = get_fleet_state(city)
            drone = fleet.get_drone(drone_id)
            if drone is not None:
                drone.link_mode = "SIMULATED"
                drone.armed = False
                drone.flight_mode = ""
                drone.d2d_link_state = "NOMINAL"
                drone.active_fault_types = []
        logger.info(f"[{drone_id}] Unregistered — reverted to SIMULATED")

    def get_link(self, drone_id: str) -> Optional[MAVLinkVehicle]:
        return self._links.get(drone_id)

    def is_live(self, drone_id: str) -> bool:
        return drone_id in self._links

    def list_live_drone_ids(self) -> List[str]:
        return list(self._links.keys())

    @staticmethod
    def _apply_telemetry(drone, telemetry: VehicleTelemetry) -> None:
        if telemetry.lat is not None:
            drone.lat = telemetry.lat
        if telemetry.lon is not None:
            drone.lon = telemetry.lon
        drone.armed = telemetry.armed
        drone.flight_mode = telemetry.flight_mode
        drone.last_telemetry_at = telemetry.timestamp

    # A dead UDP peer never makes vehicle.poll() raise (UDP has no
    # disconnect signal — poll() would happily keep returning the last
    # cached telemetry snapshot forever). MAVLinkVehicle.last_message_at is
    # the actual "did a real message arrive recently" signal; this is how
    # long to wait before treating silence as a missed heartbeat. Longer
    # than the ~1Hz heartbeat rate used throughout this project
    # (tools/mock_mavlink_vehicle.py, real ArduPilot/PX4 defaults).
    STALE_MESSAGE_THRESHOLD_S = 3.0

    def _poll_one(self, drone_id: str, vehicle: MAVLinkVehicle) -> Optional[VehicleTelemetry]:
        """One drone's poll-and-update-state step — synchronous and unit-
        testable on its own (tests/unit/test_telemetry_service_d2d.py),
        separate from run_forever's async loop/event-publishing plumbing."""
        link_state_machine = self._link_states.get(drone_id)
        city = self._cities.get(drone_id)
        fleet = get_fleet_state(city) if city else None
        drone = fleet.get_drone(drone_id) if fleet else None

        try:
            telemetry = vehicle.poll()
        except Exception as exc:
            logger.error(f"[{drone_id}] Telemetry poll failed: {exc}")
            if link_state_machine is not None and drone is not None:
                drone.d2d_link_state = link_state_machine.record_missed_heartbeat().name
            self._sync_fault(drone_id, FaultType.COMMS_LOSS, True, 0.6, ["mavlink_link"])
            self._finalize_faults(drone_id, drone, fleet, None)
            return None

        message_is_fresh = (
            vehicle.last_message_at is not None
            and (time.time() - vehicle.last_message_at) < self.STALE_MESSAGE_THRESHOLD_S
        )
        if link_state_machine is not None and drone is not None:
            if message_is_fresh:
                drone.d2d_link_state = link_state_machine.record_heartbeat().name
            else:
                drone.d2d_link_state = link_state_machine.record_missed_heartbeat().name
        if drone is not None:
            self._apply_telemetry(drone, telemetry)

        self._sync_fault(drone_id, FaultType.COMMS_LOSS, not message_is_fresh, 0.6, ["mavlink_link"])
        self._detect_faults(drone_id, telemetry, fleet)
        self._finalize_faults(drone_id, drone, fleet, telemetry)
        return telemetry

    def _sync_fault(
        self, drone_id: str, fault_type: FaultType, is_active: bool,
        severity: float, subsystems: List[str],
    ) -> None:
        """Register a fault the first time a condition is seen, resolve it
        the first time it clears — idempotent across repeated poll ticks so
        an ongoing condition doesn't spam duplicate ActiveFault entries."""
        handler = self._fault_handlers.get(drone_id)
        if handler is None:
            return
        active_ids = self._active_fault_ids.setdefault(drone_id, {})
        existing = active_ids.get(fault_type)
        if is_active and existing is None:
            fault = handler.register_fault(fault_type, severity, subsystems)
            active_ids[fault_type] = fault.fault_id
        elif not is_active and existing is not None:
            handler.resolve_fault(existing)
            del active_ids[fault_type]

    def _detect_faults(self, drone_id: str, telemetry: VehicleTelemetry, fleet) -> None:
        """Derive BATTERY_CRITICAL / GPS_LOSS / MOTOR / GEOFENCE_BREACH from
        real telemetry fields (aerofleet.hardware.mavlink_link.VehicleTelemetry)
        and this drone's live position against the real DGCA-grounded
        restricted sites (fleet.airspace, Phase AE) — no synthetic/demo data."""
        battery_pct = telemetry.battery_remaining_pct
        battery_critical = isinstance(battery_pct, (int, float)) and battery_pct < self.BATTERY_CRITICAL_PCT
        self._sync_fault(drone_id, FaultType.BATTERY_CRITICAL, battery_critical, 0.8, ["battery"])

        gps_fix = telemetry.gps_fix_type
        gps_lost = bool(telemetry.armed) and isinstance(gps_fix, int) and gps_fix < self.GPS_MIN_FIX_TYPE
        self._sync_fault(drone_id, FaultType.GPS_LOSS, gps_lost, 0.5, ["gps"])

        status = telemetry.system_status
        motor_fault = isinstance(status, str) and status in self.CRITICAL_SYSTEM_STATUSES
        self._sync_fault(drone_id, FaultType.MOTOR, motor_fault, 0.9, ["motor", "autopilot"])

        breach = (
            fleet is not None and telemetry.lat is not None and telemetry.lon is not None
            and fleet.airspace.is_no_fly(telemetry.lat, telemetry.lon)
        )
        self._sync_fault(drone_id, FaultType.GEOFENCE_BREACH, bool(breach), 0.7, ["airspace"])

    def _finalize_faults(self, drone_id: str, drone, fleet, telemetry: Optional[VehicleTelemetry]) -> None:
        """Run conflict resolution across this drone's currently-active
        faults and, if the highest-priority one demands it, actually plan
        and execute an emergency-landing action against the real vehicle —
        the step that was previously never reached (Phase AG)."""
        handler = self._fault_handlers.get(drone_id)
        if handler is None or drone is None:
            return

        report = handler.generate_recovery_plan()
        drone.active_fault_types = [f.fault_type.name for f in report.active_faults]
        if report.fault_count == 0 or not report.resolution_priority or fleet is None:
            return

        top_fault = next(
            (f for f in report.active_faults if f.fault_id == report.resolution_priority[0]), None
        )
        if top_fault is None:
            return

        current_lat = (telemetry.lat if telemetry is not None else None) or drone.lat
        current_lon = (telemetry.lon if telemetry is not None else None) or drone.lon
        if current_lat is None or current_lon is None:
            return

        depot = fleet.get_depot(drone.home_depot_id) if drone.home_depot_id else None
        home_lat, home_lon = (fleet.graph.node_lat_lon(depot.node) if depot is not None else (None, None))

        plan = EmergencyLandingPlanner(fleet.airspace).plan(
            drone_id=drone_id, fault=top_fault,
            current_lat=current_lat, current_lon=current_lon,
            home_depot_lat=home_lat, home_depot_lon=home_lon,
        )
        if plan.action in ("DIVERT_TO_SAFE_ZONE", "RETURN_TO_HOME"):
            drone.state = DroneState.EMERGENCY_LANDING
        self.execute_emergency_action(drone_id, plan.action, plan.target_lat, plan.target_lon)

    async def run_forever(self, poll_interval_s: float = 0.5) -> None:
        self._running = True
        logger.info("DroneLinkRegistry telemetry loop started")
        while self._running:
            for drone_id, vehicle in list(self._links.items()):
                telemetry = self._poll_one(drone_id, vehicle)
                if telemetry is None:
                    continue

                await self.event_bus.publish_async(
                    Event(
                        event_id=uuid.uuid4().hex,
                        event_type="telemetry.update",
                        source=drone_id,
                        payload=asdict(telemetry),
                        priority=1,
                        timestamp=time.time(),
                    )
                )

            await self.event_bus.drain()
            await asyncio.sleep(poll_interval_s)
        logger.info("DroneLinkRegistry telemetry loop stopped")

    def stop(self) -> None:
        self._running = False

    def execute_emergency_action(
        self, drone_id: str, action: str,
        target_lat: Optional[float] = None, target_lon: Optional[float] = None,
    ) -> bool:
        """Best-effort execution of an EmergencyLandingPlan.action
        (aerofleet.safety.emergency_landing) for a LIVE drone. Returns
        False for SIMULATED/unregistered drones — the caller is
        responsible for the in-memory Drone.state transition in that case."""
        vehicle = self._links.get(drone_id)
        if vehicle is None:
            return False
        try:
            if action == "RETURN_TO_HOME":
                return vehicle.return_to_launch()
            if action == "DIVERT_TO_SAFE_ZONE" and target_lat is not None and target_lon is not None:
                hold_alt = vehicle.last_telemetry.relative_alt_m or 30.0
                vehicle.goto(target_lat, target_lon, hold_alt)
                return True
            if action == "HOLD_POSITION":
                hold_mode = "LOITER" if vehicle.last_telemetry.autopilot_type == "ARDUPILOT" else "HOLD"
                return vehicle.set_mode(hold_mode)
        except Exception as exc:
            logger.error(f"[{drone_id}] execute_emergency_action({action}) failed: {exc}")
            return False
        return False

    def emergency_stop_all(self) -> Dict[str, bool]:
        """Kill switch: RTL every LIVE vehicle immediately, independent of
        the normal dispatch/CBF path. Best-effort — one failure doesn't
        stop the rest."""
        results: Dict[str, bool] = {}
        for drone_id, vehicle in self._links.items():
            try:
                results[drone_id] = vehicle.return_to_launch()
            except Exception as exc:
                logger.error(f"[{drone_id}] emergency_stop_all RTL failed: {exc}")
                results[drone_id] = False
        logger.warning(f"EMERGENCY STOP ALL issued — results: {results}")
        return results


_registry: Optional[DroneLinkRegistry] = None


def get_drone_link_registry(event_bus: Optional[AsyncEventBus] = None) -> DroneLinkRegistry:
    """Process-wide singleton, lazily created against the given event bus
    (only used on first call)."""
    global _registry
    if _registry is None:
        _registry = DroneLinkRegistry(event_bus or AsyncEventBus())
    return _registry
