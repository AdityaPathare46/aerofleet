"""MAVLink connection to one real (or SITL) ArduPilot/PX4 vehicle.

This is the ONLY module in AeroFleet that talks to flight-controller
hardware. Everything above it (dispatch, CBF gate, fault handling) reasons
about drones abstractly; this module is where a dispatch decision that has
already been CBF-approved gets turned into an actual MAVLink command.

Safety note: this class sends real commands to real aircraft when pointed
at real hardware. It does not replace the flight controller's own
independently-configured failsafes (RC-loss, GCS-loss, battery, geofence)
or a human safety pilot with RC override authority — see
docs/HARDWARE_SETUP.md before connecting to anything that can fly.
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from aerofleet.utils.logging import get_logger

logger = get_logger(__name__)

DEFAULT_ACK_TIMEOUT_S = 3.0
DEFAULT_HEARTBEAT_TIMEOUT_S = 10.0


class MAVLinkConnectionError(Exception):
    """Raised when a connection to the vehicle cannot be established."""


class MAVLinkCommandError(Exception):
    """Raised when a command is rejected or times out waiting for an ACK."""


@dataclass
class VehicleTelemetry:
    drone_id: str
    lat: Optional[float] = None
    lon: Optional[float] = None
    alt_m: Optional[float] = None
    relative_alt_m: Optional[float] = None
    heading_deg: Optional[float] = None
    groundspeed_mps: Optional[float] = None
    battery_voltage_v: Optional[float] = None
    battery_remaining_pct: Optional[float] = None
    armed: bool = False
    flight_mode: str = "UNKNOWN"
    gps_fix_type: int = 0
    satellites_visible: int = 0
    system_status: str = "UNKNOWN"
    autopilot_type: str = "UNKNOWN"
    timestamp: float = field(default_factory=time.time)


# MAV_STATE_* values -> human labels (subset actually seen in practice)
_SYSTEM_STATUS_NAMES = {
    0: "UNINIT", 1: "BOOT", 2: "CALIBRATING", 3: "STANDBY",
    4: "ACTIVE", 5: "CRITICAL", 6: "EMERGENCY", 7: "POWEROFF", 8: "FLIGHT_TERMINATION",
}


class MAVLinkVehicle:
    """
    One connection to one vehicle.

    `connection_string` uses the same format pymavlink/Mission Planner/
    QGroundControl use:
      - "udp:127.0.0.1:14550"   SITL or a UDP telemetry bridge
      - "tcp:127.0.0.1:5760"    SITL TCP
      - "/dev/ttyACM0,57600"    USB-connected flight controller
      - "/dev/ttyUSB0,57600"    telemetry radio
    """

    def __init__(self, connection_string: str, drone_id: str, source_system: int = 255):
        self.connection_string = connection_string
        self.drone_id = drone_id
        self.source_system = source_system
        self._conn = None
        self._telemetry = VehicleTelemetry(drone_id=drone_id)
        self._connected = False
        # UDP has no disconnect signal, so poll() below never raises just
        # because the peer went away — it keeps returning the last cached
        # telemetry snapshot forever. This is the actual "did a real
        # message arrive" signal, set only from _handle_message(), used by
        # aerofleet/hardware/telemetry_service.py to detect a stale/dead
        # link for D2D purposes (aerofleet/safety/d2d_mesh.py) instead of
        # relying on an exception that this transport can't produce.
        self.last_message_at: Optional[float] = None

    # ─────────────────────────────────────────────────────────────────
    #  CONNECTION
    # ─────────────────────────────────────────────────────────────────

    def connect(self, heartbeat_timeout_s: float = DEFAULT_HEARTBEAT_TIMEOUT_S) -> None:
        from pymavlink import mavutil

        logger.info(f"[{self.drone_id}] Connecting to {self.connection_string} ...")
        try:
            self._conn = mavutil.mavlink_connection(
                self.connection_string, source_system=self.source_system
            )
            hb = self._conn.wait_heartbeat(timeout=heartbeat_timeout_s)
        except Exception as exc:
            raise MAVLinkConnectionError(
                f"Failed to connect to '{self.connection_string}': {exc}"
            ) from exc

        if hb is None:
            raise MAVLinkConnectionError(
                f"No heartbeat from '{self.connection_string}' within {heartbeat_timeout_s}s "
                "— is the vehicle/SITL powered on and reachable?"
            )

        self._connected = True
        self._telemetry.autopilot_type = {3: "ARDUPILOT", 12: "PX4"}.get(hb.autopilot, "OTHER")
        logger.info(
            f"[{self.drone_id}] Connected — system={self._conn.target_system} "
            f"component={self._conn.target_component} autopilot={self._telemetry.autopilot_type}"
        )

    def close(self) -> None:
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:
                pass
        self._connected = False
        logger.info(f"[{self.drone_id}] Disconnected")

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def last_telemetry(self) -> VehicleTelemetry:
        """Most recent telemetry snapshot without forcing a fresh poll()."""
        return self._telemetry

    # ─────────────────────────────────────────────────────────────────
    #  TELEMETRY
    # ─────────────────────────────────────────────────────────────────

    def poll(self) -> VehicleTelemetry:
        """Drain all currently-buffered messages and return the latest
        telemetry snapshot. Non-blocking — call this on a timer."""
        if not self._connected:
            raise MAVLinkConnectionError(f"[{self.drone_id}] Not connected")

        while True:
            msg = self._conn.recv_match(blocking=False)
            if msg is None:
                break
            self._handle_message(msg)

        self._telemetry.timestamp = time.time()
        return self._telemetry

    def _handle_message(self, msg) -> None:
        from pymavlink import mavutil

        self.last_message_at = time.time()
        t = msg.get_type()
        if t == "HEARTBEAT":
            self._telemetry.armed = bool(msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED)
            self._telemetry.system_status = _SYSTEM_STATUS_NAMES.get(msg.system_status, str(msg.system_status))
            self._telemetry.flight_mode = self._conn.flightmode or "UNKNOWN"
        elif t == "GLOBAL_POSITION_INT":
            self._telemetry.lat = msg.lat / 1e7
            self._telemetry.lon = msg.lon / 1e7
            self._telemetry.alt_m = msg.alt / 1000.0
            self._telemetry.relative_alt_m = msg.relative_alt / 1000.0
            if msg.hdg != 65535:
                self._telemetry.heading_deg = msg.hdg / 100.0
            self._telemetry.groundspeed_mps = math.hypot(msg.vx, msg.vy) / 100.0
        elif t == "SYS_STATUS":
            if msg.voltage_battery not in (0, -1, 65535):
                self._telemetry.battery_voltage_v = msg.voltage_battery / 1000.0
            if msg.battery_remaining != -1:
                self._telemetry.battery_remaining_pct = float(msg.battery_remaining)
        elif t == "BATTERY_STATUS":
            if msg.battery_remaining != -1:
                self._telemetry.battery_remaining_pct = float(msg.battery_remaining)
        elif t == "GPS_RAW_INT":
            self._telemetry.gps_fix_type = msg.fix_type
            self._telemetry.satellites_visible = msg.satellites_visible

    # ─────────────────────────────────────────────────────────────────
    #  COMMANDS  (all go through _send_command_and_wait_ack for a
    #  consistent accept/reject/timeout contract)
    # ─────────────────────────────────────────────────────────────────

    def _send_command_and_wait_ack(
        self, command: int, params: Tuple[float, float, float, float, float, float, float],
        ack_timeout_s: float = DEFAULT_ACK_TIMEOUT_S,
    ) -> bool:
        from pymavlink import mavutil

        self._conn.mav.command_long_send(
            self._conn.target_system, self._conn.target_component,
            command, 0, *params,
        )
        deadline = time.time() + ack_timeout_s
        while time.time() < deadline:
            ack = self._conn.recv_match(type="COMMAND_ACK", blocking=True, timeout=0.5)
            if ack is None:
                continue
            if ack.command != command:
                continue
            accepted = ack.result == mavutil.mavlink.MAV_RESULT_ACCEPTED
            if not accepted:
                logger.warning(f"[{self.drone_id}] Command {command} rejected: result={ack.result}")
            return accepted
        raise MAVLinkCommandError(f"[{self.drone_id}] Command {command} timed out waiting for ACK")

    def arm(self, force: bool = False) -> bool:
        logger.warning(f"[{self.drone_id}] ARM requested")
        return self._send_command_and_wait_ack(
            _cmd("MAV_CMD_COMPONENT_ARM_DISARM"), (1, 21196 if force else 0, 0, 0, 0, 0, 0)
        )

    def disarm(self, force: bool = False) -> bool:
        logger.info(f"[{self.drone_id}] DISARM requested")
        return self._send_command_and_wait_ack(
            _cmd("MAV_CMD_COMPONENT_ARM_DISARM"), (0, 21196 if force else 0, 0, 0, 0, 0, 0)
        )

    def set_mode(self, mode_name: str) -> bool:
        from pymavlink import mavutil

        mapping = self._conn.mode_mapping()
        if not mapping or mode_name not in mapping:
            raise MAVLinkCommandError(
                f"[{self.drone_id}] Mode '{mode_name}' not available. Known modes: "
                f"{sorted(mapping) if mapping else 'none (no heartbeat yet?)'}"
            )
        logger.info(f"[{self.drone_id}] Setting mode -> {mode_name}")
        self._conn.mav.set_mode_send(
            self._conn.target_system,
            mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
            mapping[mode_name],
        )
        return True

    def takeoff(self, altitude_m: float) -> bool:
        logger.warning(f"[{self.drone_id}] TAKEOFF requested — target alt {altitude_m}m")
        return self._send_command_and_wait_ack(
            _cmd("MAV_CMD_NAV_TAKEOFF"), (0, 0, 0, float("nan"), 0, 0, altitude_m)
        )

    def goto(self, lat: float, lon: float, alt_m: float) -> None:
        """Guided-mode position setpoint (no ACK in the mission-protocol
        sense — this is a streamed setpoint, not a one-shot command)."""
        from pymavlink import mavutil

        type_mask = 0b0000111111111000  # position only
        self._conn.mav.set_position_target_global_int_send(
            0, self._conn.target_system, self._conn.target_component,
            mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT, type_mask,
            int(lat * 1e7), int(lon * 1e7), alt_m,
            0, 0, 0, 0, 0, 0, 0, 0,
        )
        logger.info(f"[{self.drone_id}] GOTO ({lat:.6f}, {lon:.6f}) @ {alt_m}m")

    def upload_mission(self, waypoints: List[Tuple[float, float, float]], ack_timeout_s: float = 10.0) -> bool:
        """Upload a sequence of (lat, lon, alt_m) waypoints via the MAVLink
        mission protocol handshake (COUNT -> per-item REQUEST/response -> ACK)."""
        from pymavlink import mavutil

        n = len(waypoints)
        if n == 0:
            return True

        self._conn.mav.mission_count_send(self._conn.target_system, self._conn.target_component, n)
        deadline = time.time() + ack_timeout_s
        sent = 0
        while sent < n and time.time() < deadline:
            req = self._conn.recv_match(
                type=["MISSION_REQUEST", "MISSION_REQUEST_INT"], blocking=True, timeout=1.0
            )
            if req is None:
                continue
            idx = req.seq
            lat, lon, alt = waypoints[idx]
            self._conn.mav.mission_item_int_send(
                self._conn.target_system, self._conn.target_component, idx,
                mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT,
                mavutil.mavlink.MAV_CMD_NAV_WAYPOINT,
                0, 1, 0, 0, 0, float("nan"),
                int(lat * 1e7), int(lon * 1e7), alt,
            )
            sent += 1

        final_ack = self._conn.recv_match(type="MISSION_ACK", blocking=True, timeout=ack_timeout_s)
        ok = final_ack is not None and final_ack.type == mavutil.mavlink.MAV_MISSION_ACCEPTED
        logger.info(f"[{self.drone_id}] Mission upload ({sent}/{n} items sent): {'OK' if ok else 'FAILED'}")
        return ok

    def start_mission(self) -> bool:
        return self.set_mode("AUTO") if self._is_ardupilot() else self.set_mode("MISSION")

    def return_to_launch(self) -> bool:
        logger.warning(f"[{self.drone_id}] RETURN TO LAUNCH")
        return self._send_command_and_wait_ack(_cmd("MAV_CMD_NAV_RETURN_TO_LAUNCH"), (0,) * 7)

    def emergency_land(self) -> bool:
        logger.warning(f"[{self.drone_id}] EMERGENCY LAND")
        return self._send_command_and_wait_ack(_cmd("MAV_CMD_NAV_LAND"), (0, 0, 0, float("nan"), 0, 0, 0))

    def push_geofence(self, center_lat: float, center_lon: float, radius_m: float, max_alt_m: float) -> bool:
        """Best-effort defense-in-depth: sets a simple circular ArduPilot
        fence via parameters, independent of AeroFleet's own CBF check, so
        the vehicle enforces a boundary even if the companion link drops.
        (A full polygon fence via the MAVLink fence-item mission protocol
        is a documented future enhancement — see docs/HARDWARE_SETUP.md.)
        """
        if not self._is_ardupilot():
            logger.warning(f"[{self.drone_id}] push_geofence is ArduPilot-only; skipping for non-ArduPilot vehicle")
            return False
        try:
            self._set_param("FENCE_ENABLE", 1)
            self._set_param("FENCE_TYPE", 3)  # 1=altitude, 2=circle, 3=both
            self._set_param("FENCE_RADIUS", float(radius_m))
            self._set_param("FENCE_ALT_MAX", float(max_alt_m))
            logger.info(f"[{self.drone_id}] Onboard fence set: radius={radius_m}m ceiling={max_alt_m}m")
            return True
        except Exception as exc:
            logger.error(f"[{self.drone_id}] Failed to push geofence params: {exc}")
            return False

    def _set_param(self, name: str, value: float) -> None:
        from pymavlink import mavutil

        self._conn.mav.param_set_send(
            self._conn.target_system, self._conn.target_component,
            name.encode("utf-8"), value, mavutil.mavlink.MAV_PARAM_TYPE_REAL32,
        )

    def _is_ardupilot(self) -> bool:
        return self._telemetry.autopilot_type == "ARDUPILOT"


def _cmd(name: str) -> int:
    from pymavlink.dialects.v20 import common as mavlink2

    return getattr(mavlink2, name)
