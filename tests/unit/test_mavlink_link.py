"""Unit tests for the pure-logic pieces of aerofleet/hardware/mavlink_link.py
that don't need a live socket connection — telemetry field decoding,
default state, and the MAV_CMD_* constant resolver. The full wire-protocol
round-trip (connect/arm/takeoff/mission-upload/RTL against a real MAVLink
peer) is covered separately by the `hardware`-marked integration test
against tools/mock_mavlink_vehicle.py.
"""
from unittest.mock import MagicMock

import pytest

from aerofleet.hardware.mavlink_link import MAVLinkVehicle, VehicleTelemetry, _cmd

pytestmark = pytest.mark.unit


class TestVehicleTelemetryDefaults:
    def test_defaults_are_unknown_not_crashed_or_false_safe(self):
        t = VehicleTelemetry(drone_id="D1")
        assert t.drone_id == "D1"
        assert t.lat is None
        assert t.armed is False
        assert t.flight_mode == "UNKNOWN"
        assert t.autopilot_type == "UNKNOWN"
        assert t.gps_fix_type == 0


class TestCmdResolution:
    """_cmd() resolves MAV_CMD_* names to their integer values — these are
    the exact command codes sent to real hardware, so a wrong resolution
    would silently send the wrong command."""

    def test_known_commands_resolve_to_documented_mavlink_values(self):
        assert _cmd("MAV_CMD_NAV_TAKEOFF") == 22
        assert _cmd("MAV_CMD_COMPONENT_ARM_DISARM") == 400
        assert _cmd("MAV_CMD_NAV_RETURN_TO_LAUNCH") == 20
        assert _cmd("MAV_CMD_NAV_LAND") == 21

    def test_unknown_command_name_raises(self):
        with pytest.raises(AttributeError):
            _cmd("MAV_CMD_DOES_NOT_EXIST")


class TestConnectionStateBeforeConnect:
    def test_fresh_vehicle_is_not_connected(self):
        vehicle = MAVLinkVehicle("udpin:127.0.0.1:0", drone_id="D1")
        assert vehicle.is_connected is False
        assert vehicle.last_telemetry.drone_id == "D1"

    def test_poll_before_connect_raises(self):
        from aerofleet.hardware.mavlink_link import MAVLinkConnectionError

        vehicle = MAVLinkVehicle("udpin:127.0.0.1:0", drone_id="D1")
        with pytest.raises(MAVLinkConnectionError):
            vehicle.poll()


class TestHandleMessage:
    """_handle_message() is the pure decode logic poll() drives — tested
    directly against synthetic message objects so it doesn't need a real
    socket or a running mock vehicle."""

    def _vehicle(self):
        vehicle = MAVLinkVehicle("udpin:127.0.0.1:0", drone_id="D1")
        vehicle._conn = MagicMock()
        vehicle._conn.flightmode = "GUIDED"
        return vehicle

    def test_heartbeat_decodes_armed_state_and_mode(self):
        from pymavlink import mavutil

        vehicle = self._vehicle()
        msg = MagicMock()
        msg.get_type.return_value = "HEARTBEAT"
        msg.base_mode = mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED | mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED
        msg.system_status = 4  # MAV_STATE_ACTIVE

        vehicle._handle_message(msg)

        assert vehicle.last_telemetry.armed is True
        assert vehicle.last_telemetry.flight_mode == "GUIDED"
        assert vehicle.last_telemetry.system_status == "ACTIVE"

    def test_heartbeat_decodes_disarmed_state(self):
        from pymavlink import mavutil

        vehicle = self._vehicle()
        msg = MagicMock()
        msg.get_type.return_value = "HEARTBEAT"
        msg.base_mode = mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED  # armed bit not set
        msg.system_status = 3  # MAV_STATE_STANDBY

        vehicle._handle_message(msg)

        assert vehicle.last_telemetry.armed is False
        assert vehicle.last_telemetry.system_status == "STANDBY"

    def test_global_position_int_decodes_lat_lon_alt(self):
        vehicle = self._vehicle()
        msg = MagicMock()
        msg.get_type.return_value = "GLOBAL_POSITION_INT"
        msg.lat = int(18.5204 * 1e7)
        msg.lon = int(73.8567 * 1e7)
        msg.alt = 60000       # mm -> 60.0 m
        msg.relative_alt = 30000  # mm -> 30.0 m
        msg.hdg = 9000         # centidegrees -> 90.0 deg
        msg.vx, msg.vy = 300, 400  # cm/s -> groundspeed via hypot

        vehicle._handle_message(msg)

        t = vehicle.last_telemetry
        assert t.lat == pytest.approx(18.5204, abs=1e-4)
        assert t.lon == pytest.approx(73.8567, abs=1e-4)
        assert t.alt_m == pytest.approx(60.0)
        assert t.relative_alt_m == pytest.approx(30.0)
        assert t.heading_deg == pytest.approx(90.0)
        assert t.groundspeed_mps == pytest.approx(5.0)  # hypot(3, 4) m/s

    def test_global_position_int_ignores_invalid_heading_sentinel(self):
        """65535 is MAVLink's 'heading unknown' sentinel, not a real value."""
        vehicle = self._vehicle()
        msg = MagicMock()
        msg.get_type.return_value = "GLOBAL_POSITION_INT"
        msg.lat, msg.lon, msg.alt, msg.relative_alt = 0, 0, 0, 0
        msg.hdg = 65535
        msg.vx, msg.vy = 0, 0

        vehicle._handle_message(msg)

        assert vehicle.last_telemetry.heading_deg is None

    def test_sys_status_decodes_voltage_and_battery_remaining(self):
        vehicle = self._vehicle()
        msg = MagicMock()
        msg.get_type.return_value = "SYS_STATUS"
        msg.voltage_battery = 12600  # mV -> 12.6V
        msg.battery_remaining = 87

        vehicle._handle_message(msg)

        assert vehicle.last_telemetry.battery_voltage_v == pytest.approx(12.6)
        assert vehicle.last_telemetry.battery_remaining_pct == 87.0

    def test_sys_status_ignores_sentinel_voltage_values(self):
        vehicle = self._vehicle()
        for sentinel in (0, -1, 65535):
            msg = MagicMock()
            msg.get_type.return_value = "SYS_STATUS"
            msg.voltage_battery = sentinel
            msg.battery_remaining = -1
            vehicle._handle_message(msg)
        # Never overwritten with a bogus value derived from a sentinel.
        assert vehicle.last_telemetry.battery_voltage_v is None

    def test_unknown_message_type_is_ignored_without_error(self):
        vehicle = self._vehicle()
        msg = MagicMock()
        msg.get_type.return_value = "SOME_UNHANDLED_TYPE"
        vehicle._handle_message(msg)  # must not raise
        assert vehicle.last_telemetry.drone_id == "D1"
