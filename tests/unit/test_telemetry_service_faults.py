"""Unit tests for aerofleet/hardware/telemetry_service.py's fault-detection
+ emergency-landing wiring (Phase AG). Before this phase,
aerofleet/fault_tolerance/multi_fault_handler.py and
aerofleet/safety/emergency_landing.py were fully built and unit-tested in
isolation but never called from the live telemetry poll loop — these tests
exercise the real integration: a poll tick that reveals a fault must reach
DroneLinkRegistry.execute_emergency_action(), not just update a status field.
"""
import time
from unittest.mock import MagicMock

import pytest

from aerofleet.event_bus.async_bus import AsyncEventBus
from aerofleet.fault_tolerance.multi_fault_handler import MultiFaultHandler
from aerofleet.fleet.models import DroneState
from aerofleet.fleet.state import get_fleet_state
from aerofleet.hardware.telemetry_service import DroneLinkRegistry
from aerofleet.safety.d2d_mesh import D2DLinkStateMachine

pytestmark = pytest.mark.unit


def _telemetry(
    lat=18.53, lon=73.86, armed=True,
    battery_remaining_pct=80.0, gps_fix_type=3, system_status="ACTIVE",
):
    telemetry = MagicMock()
    telemetry.lat = lat
    telemetry.lon = lon
    telemetry.armed = armed
    telemetry.flight_mode = "GUIDED"
    telemetry.timestamp = 0.0
    telemetry.battery_remaining_pct = battery_remaining_pct
    telemetry.gps_fix_type = gps_fix_type
    telemetry.system_status = system_status
    return telemetry


def _vehicle_mock(telemetry) -> MagicMock:
    vehicle = MagicMock()
    vehicle.poll.return_value = telemetry
    vehicle.last_message_at = time.time()
    vehicle.last_telemetry = telemetry
    return vehicle


@pytest.fixture
def registry():
    return DroneLinkRegistry(AsyncEventBus())


def _wire_drone(registry, fleet, drone_id, vehicle=None, city="pune"):
    registry._link_states[drone_id] = D2DLinkStateMachine()
    registry._cities[drone_id] = city
    registry._fault_handlers[drone_id] = MultiFaultHandler()
    registry._active_fault_ids[drone_id] = {}
    # execute_emergency_action() looks the vehicle up via self._links, not
    # via the vehicle passed straight into _poll_one — register it here so
    # the emergency-action path under test has something real to command.
    if vehicle is not None:
        registry._links[drone_id] = vehicle


class TestNoFault:
    def test_healthy_poll_leaves_no_active_faults(self, registry, fresh_fleet_state):
        fleet = get_fleet_state("pune")
        drone = fleet.list_drones()[0]
        _wire_drone(registry, fleet, drone.drone_id)

        registry._poll_one(drone.drone_id, _vehicle_mock(_telemetry()))

        assert drone.active_fault_types == []
        assert drone.state != DroneState.EMERGENCY_LANDING


class TestBatteryCritical:
    def test_low_battery_registers_fault_and_triggers_rth(self, registry, fresh_fleet_state):
        fleet = get_fleet_state("pune")
        drone = fleet.list_drones()[0]
        drone.home_depot_id = list(fleet.depots.keys())[0]
        vehicle = _vehicle_mock(_telemetry(battery_remaining_pct=8.0))
        _wire_drone(registry, fleet, drone.drone_id, vehicle=vehicle)

        registry._poll_one(drone.drone_id, vehicle)

        assert "BATTERY_CRITICAL" in drone.active_fault_types
        assert drone.state == DroneState.EMERGENCY_LANDING
        # RETURN_TO_HOME is a real MAVLink command — confirms execution
        # actually reached the vehicle, not just a status update.
        vehicle.return_to_launch.assert_called_once()

    def test_battery_recovering_resolves_the_fault(self, registry, fresh_fleet_state):
        fleet = get_fleet_state("pune")
        drone = fleet.list_drones()[0]
        drone.home_depot_id = list(fleet.depots.keys())[0]
        _wire_drone(registry, fleet, drone.drone_id)

        registry._poll_one(drone.drone_id, _vehicle_mock(_telemetry(battery_remaining_pct=8.0)))
        assert "BATTERY_CRITICAL" in drone.active_fault_types

        registry._poll_one(drone.drone_id, _vehicle_mock(_telemetry(battery_remaining_pct=90.0)))
        assert "BATTERY_CRITICAL" not in drone.active_fault_types


class TestGpsLoss:
    def test_no_fix_while_armed_registers_fault(self, registry, fresh_fleet_state):
        fleet = get_fleet_state("pune")
        drone = fleet.list_drones()[0]
        _wire_drone(registry, fleet, drone.drone_id)

        registry._poll_one(drone.drone_id, _vehicle_mock(_telemetry(armed=True, gps_fix_type=1)))

        assert "GPS_LOSS" in drone.active_fault_types

    def test_no_fix_while_disarmed_is_not_a_fault(self, registry, fresh_fleet_state):
        fleet = get_fleet_state("pune")
        drone = fleet.list_drones()[0]
        _wire_drone(registry, fleet, drone.drone_id)

        registry._poll_one(drone.drone_id, _vehicle_mock(_telemetry(armed=False, gps_fix_type=0)))

        assert "GPS_LOSS" not in drone.active_fault_types


class TestMotorFault:
    def test_critical_system_status_triggers_emergency_landing(self, registry, fresh_fleet_state):
        fleet = get_fleet_state("pune")
        drone = fleet.list_drones()[0]
        vehicle = _vehicle_mock(_telemetry(system_status="EMERGENCY"))
        _wire_drone(registry, fleet, drone.drone_id, vehicle=vehicle)

        registry._poll_one(drone.drone_id, vehicle)

        assert "MOTOR" in drone.active_fault_types
        assert drone.state == DroneState.EMERGENCY_LANDING
        # MOTOR is in DIVERT_TO_SAFE_ZONE — goto(), not return_to_launch().
        vehicle.goto.assert_called_once()


class TestGeofenceBreach:
    def test_real_restricted_site_coordinates_trigger_breach(self, registry, fresh_fleet_state):
        fleet = get_fleet_state("pune")
        drone = fleet.list_drones()[0]
        _wire_drone(registry, fleet, drone.drone_id)
        # Real, named DGCA site from aerofleet/city/restricted_sites.py —
        # Pune Airport (Lohegaon) — not a fabricated demo coordinate.
        vehicle = _vehicle_mock(_telemetry(lat=18.5822, lon=73.9197))

        registry._poll_one(drone.drone_id, vehicle)

        assert "GEOFENCE_BREACH" in drone.active_fault_types
        assert drone.state == DroneState.EMERGENCY_LANDING


class TestCommsLoss:
    def test_poll_exception_registers_comms_loss_and_holds(self, registry, fresh_fleet_state):
        fleet = get_fleet_state("pune")
        drone = fleet.list_drones()[0]
        drone.lat, drone.lon = 18.53, 73.86

        vehicle = MagicMock()
        vehicle.poll.side_effect = ConnectionError("simulated link loss")
        vehicle.last_telemetry.autopilot_type = "ARDUPILOT"
        _wire_drone(registry, fleet, drone.drone_id, vehicle=vehicle)

        registry._poll_one(drone.drone_id, vehicle)

        assert "COMMS_LOSS" in drone.active_fault_types
        # COMMS_LOSS resolves to DIVERT_TO_SAFE_ZONE in
        # emergency_landing.DIVERT_TO_SAFE_ZONE -> goto().
        vehicle.goto.assert_called_once()


class TestConflictPriority:
    def test_motor_outranks_battery_when_simultaneous(self, registry, fresh_fleet_state):
        """MultiFaultHandler.PRIORITY_ORDER puts MOTOR above
        BATTERY_CRITICAL — both faulting at once must act on MOTOR's plan
        (a safe-zone divert), not battery's return-to-home."""
        fleet = get_fleet_state("pune")
        drone = fleet.list_drones()[0]
        drone.home_depot_id = list(fleet.depots.keys())[0]
        vehicle = _vehicle_mock(_telemetry(battery_remaining_pct=5.0, system_status="EMERGENCY"))
        _wire_drone(registry, fleet, drone.drone_id, vehicle=vehicle)

        registry._poll_one(drone.drone_id, vehicle)

        assert {"MOTOR", "BATTERY_CRITICAL"} <= set(drone.active_fault_types)
        vehicle.goto.assert_called_once()
        vehicle.return_to_launch.assert_not_called()


class TestUnregisteredDroneIsUnaffected:
    def test_drone_without_fault_handler_is_skipped(self, registry, fresh_fleet_state):
        """Mirrors the existing D2D tests' pattern: a drone whose
        _fault_handlers entry was never populated (i.e. never went through
        register()) must not be touched by fault detection at all."""
        fleet = get_fleet_state("pune")
        drone = fleet.list_drones()[0]
        registry._link_states[drone.drone_id] = D2DLinkStateMachine()
        registry._cities[drone.drone_id] = "pune"

        registry._poll_one(drone.drone_id, _vehicle_mock(_telemetry(battery_remaining_pct=1.0)))

        assert drone.active_fault_types == []
