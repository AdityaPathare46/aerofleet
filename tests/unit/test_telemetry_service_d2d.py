"""Unit tests for aerofleet/hardware/telemetry_service.py's D2D link-state
wiring (Phase AD) — register() initializes NOMINAL, poll success/failure
drives the state machine and is reflected on the live Drone object, and
unregister() resets state cleanly.
"""
import time
from unittest.mock import MagicMock, patch

import pytest

from aerofleet.fleet.state import get_fleet_state
from aerofleet.hardware.telemetry_service import DroneLinkRegistry
from aerofleet.safety.d2d_mesh import DEGRADED_MISSED_HEARTBEATS, STORE_FORWARD_MISSED_HEARTBEATS

pytestmark = pytest.mark.unit


def _fake_telemetry(lat=18.53, lon=73.86):
    telemetry = MagicMock()
    telemetry.lat = lat
    telemetry.lon = lon
    telemetry.armed = False
    telemetry.flight_mode = "GUIDED"
    telemetry.timestamp = 0.0
    return telemetry


def _fresh_vehicle_mock() -> MagicMock:
    """A vehicle mock whose poll() succeeds AND whose last_message_at is
    recent — the two conditions _poll_one now requires to treat a poll as
    a real heartbeat (see telemetry_service.py's STALE_MESSAGE_THRESHOLD_S;
    a dead UDP peer's poll() never raises, so last_message_at is the real
    signal, not the return value alone)."""
    vehicle = MagicMock()
    vehicle.poll.return_value = _fake_telemetry()
    vehicle.last_message_at = time.time()
    return vehicle


def _stale_vehicle_mock() -> MagicMock:
    """poll() succeeds (as a dead UDP peer's would) but last_message_at is
    old — the realistic "link silently died" case this whole mechanism
    exists to detect."""
    vehicle = MagicMock()
    vehicle.poll.return_value = _fake_telemetry()
    vehicle.last_message_at = time.time() - 100.0
    return vehicle


@pytest.fixture
def registry():
    from aerofleet.event_bus.async_bus import AsyncEventBus
    return DroneLinkRegistry(AsyncEventBus())


class TestPollOne:
    def test_successful_poll_keeps_drone_nominal(self, registry, fresh_fleet_state):
        fleet = get_fleet_state("pune")
        drone = fleet.list_drones()[0]
        drone_id = drone.drone_id

        from aerofleet.safety.d2d_mesh import D2DLinkStateMachine
        registry._link_states[drone_id] = D2DLinkStateMachine()
        registry._cities[drone_id] = "pune"

        registry._poll_one(drone_id, _fresh_vehicle_mock())
        assert drone.d2d_link_state == "NOMINAL"

    def test_silently_dead_peer_transitions_to_degraded(self, registry, fresh_fleet_state):
        """The realistic UDP failure mode: poll() keeps succeeding (it
        never raises just because the peer died), but no real message has
        arrived in a while — last_message_at is the signal, not the
        poll() return value."""
        fleet = get_fleet_state("pune")
        drone = fleet.list_drones()[0]
        drone_id = drone.drone_id

        from aerofleet.safety.d2d_mesh import D2DLinkStateMachine
        registry._link_states[drone_id] = D2DLinkStateMachine()
        registry._cities[drone_id] = "pune"

        stale_vehicle = _stale_vehicle_mock()
        for _ in range(DEGRADED_MISSED_HEARTBEATS):
            registry._poll_one(drone_id, stale_vehicle)
        assert drone.d2d_link_state == "DEGRADED"

    def test_repeated_poll_failures_transition_to_degraded(self, registry, fresh_fleet_state):
        fleet = get_fleet_state("pune")
        drone = fleet.list_drones()[0]
        drone_id = drone.drone_id

        from aerofleet.safety.d2d_mesh import D2DLinkStateMachine
        registry._link_states[drone_id] = D2DLinkStateMachine()
        registry._cities[drone_id] = "pune"

        vehicle = MagicMock()
        vehicle.poll.side_effect = ConnectionError("simulated link loss")

        for _ in range(DEGRADED_MISSED_HEARTBEATS):
            registry._poll_one(drone_id, vehicle)
        assert drone.d2d_link_state == "DEGRADED"

    def test_enough_failures_reach_store_forward(self, registry, fresh_fleet_state):
        fleet = get_fleet_state("pune")
        drone = fleet.list_drones()[0]
        drone_id = drone.drone_id

        from aerofleet.safety.d2d_mesh import D2DLinkStateMachine
        registry._link_states[drone_id] = D2DLinkStateMachine()
        registry._link_states[drone_id].record_peer_contact()  # simulate D2D peers still reachable
        registry._cities[drone_id] = "pune"

        vehicle = MagicMock()
        vehicle.poll.side_effect = ConnectionError("simulated link loss")

        for _ in range(STORE_FORWARD_MISSED_HEARTBEATS):
            registry._poll_one(drone_id, vehicle)
        assert drone.d2d_link_state == "STORE_FORWARD"

    def test_recovery_after_failures_returns_to_nominal(self, registry, fresh_fleet_state):
        fleet = get_fleet_state("pune")
        drone = fleet.list_drones()[0]
        drone_id = drone.drone_id

        from aerofleet.safety.d2d_mesh import D2DLinkStateMachine
        registry._link_states[drone_id] = D2DLinkStateMachine()
        registry._cities[drone_id] = "pune"

        vehicle = MagicMock()
        vehicle.poll.side_effect = ConnectionError("simulated link loss")
        for _ in range(DEGRADED_MISSED_HEARTBEATS):
            registry._poll_one(drone_id, vehicle)
        assert drone.d2d_link_state == "DEGRADED"

        registry._poll_one(drone_id, _fresh_vehicle_mock())
        assert drone.d2d_link_state == "NOMINAL"


class TestRegisterUnregister:
    def test_register_initializes_nominal_and_a_link_state_machine(self, registry, fresh_fleet_state):
        fleet = get_fleet_state("pune")
        drone = fleet.list_drones()[0]

        fake_vehicle = _fresh_vehicle_mock()

        with patch("aerofleet.hardware.telemetry_service.MAVLinkVehicle", return_value=fake_vehicle):
            registry.register(drone.drone_id, "pune", "udpin:127.0.0.1:0")

        assert drone.d2d_link_state == "NOMINAL"
        assert drone.drone_id in registry._link_states

    def test_unregister_resets_to_nominal_and_drops_state_machine(self, registry, fresh_fleet_state):
        fleet = get_fleet_state("pune")
        drone = fleet.list_drones()[0]
        drone_id = drone.drone_id

        from aerofleet.safety.d2d_mesh import D2DLinkStateMachine
        registry._link_states[drone_id] = D2DLinkStateMachine()
        registry._cities[drone_id] = "pune"
        registry._links[drone_id] = MagicMock()
        drone.d2d_link_state = "STORE_FORWARD"

        registry.unregister(drone_id)
        assert drone.d2d_link_state == "NOMINAL"
        assert drone_id not in registry._link_states
