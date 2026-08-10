#!/usr/bin/env python3
"""Minimal fake ArduPilot vehicle over MAVLink/UDP.

Exists to exercise aerofleet.hardware.mavlink_link.MAVLinkVehicle end to
end (connect, telemetry decode, arm/takeoff/mode/mission/RTL commands and
their ACKs) without needing real flight-controller hardware or a full
ArduPilot SITL build. It is NOT a flight dynamics simulator — position
only updates in response to the commands it receives, there is no
physics.

Also emits and receives D2D Basic Safety Messages (see
aerofleet/safety/d2d_mesh.py, docs/D2D_MESH_RESEARCH_DESIGN.md) over a
local UDP multicast group — the current stand-in for a real drone-to-drone
mesh radio. Every instance of this script (one per simulated drone)
broadcasts its own position/velocity/heading once a second and listens for
every other running instance's broadcasts, maintaining a live peer table.

Usage:
    python tools/mock_mavlink_vehicle.py [--port 14550] [--drone-id D1] [--d2d-port 14650]

Then point aerofleet at it with connection_string="udpin:127.0.0.1:14550".
Run a second instance with a different --port and --drone-id (same
--d2d-port) to see the two exchange D2D broadcasts.
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import socket
import struct
import threading
import time
from typing import Optional

from pymavlink import mavutil
from pymavlink.dialects.v20 import common as mavlink2

from aerofleet.safety.d2d_mesh import D2DBasicSafetyMessage, D2DTransceiver

START_LAT = 18.5204   # Pune
START_LON = 73.8567

D2D_MULTICAST_GROUP = "239.192.42.99"  # organization-local scope, RFC 2365
D2D_DEFAULT_PORT = 14650
D2D_BROADCAST_INTERVAL_S = 1.0


class MockVehicle:
    def __init__(self, port: int = 14550, drone_id: Optional[str] = None, d2d_port: int = D2D_DEFAULT_PORT):
        self.conn = mavutil.mavlink_connection(
            f"udpout:127.0.0.1:{port}", source_system=1, source_component=1
        )
        self.lat = START_LAT
        self.lon = START_LON
        self.alt_m = 0.0
        self.armed = False
        self.mode = "STABILIZE"
        self.mode_map = mavutil.mode_mapping_acm
        self._gcs_system = 255
        self._gcs_component = 0
        self._running = True

        # D2D mesh state — separate from the MAVLink link above, which only
        # talks to this vehicle's own GCS/dispatch server, not to peers.
        self.drone_id = drone_id or f"MOCK-{port}"
        self.velocity_mps = 0.0
        self.heading_deg = 0.0
        self.battery_soc = 1.0
        self.d2d = D2DTransceiver(self.drone_id)
        self._d2d_port = d2d_port
        self._d2d_send_sock = self._make_d2d_send_socket()
        self._d2d_recv_sock = self._make_d2d_recv_socket()

    @staticmethod
    def _make_d2d_send_socket() -> socket.socket:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 1)
        return sock

    def _make_d2d_recv_socket(self) -> socket.socket:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        if hasattr(socket, "SO_REUSEPORT"):
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        sock.bind(("", self._d2d_port))
        mreq = struct.pack("4sl", socket.inet_aton(D2D_MULTICAST_GROUP), socket.INADDR_ANY)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        sock.settimeout(1.0)
        return sock

    def send_d2d_broadcast(self) -> None:
        msg = D2DBasicSafetyMessage(
            drone_id=self.drone_id,
            timestamp_utc=time.time(),
            lat=self.lat,
            lon=self.lon,
            alt_m=self.alt_m,
            velocity_mps=self.velocity_mps,
            heading_deg=self.heading_deg,
            battery_soc=self.battery_soc,
            link_state=self.d2d.link_state.state.name,
        )
        payload = json.dumps(dataclasses.asdict(msg)).encode("utf-8")
        self._d2d_send_sock.sendto(payload, (D2D_MULTICAST_GROUP, self._d2d_port))

    def d2d_broadcast_loop(self) -> None:
        while self._running:
            try:
                self.send_d2d_broadcast()
            except OSError as exc:
                print(f"[mock] D2D broadcast send failed: {exc}")
            time.sleep(D2D_BROADCAST_INTERVAL_S)

    def d2d_receive_loop(self) -> None:
        while self._running:
            try:
                data, _addr = self._d2d_recv_sock.recvfrom(4096)
            except socket.timeout:
                continue
            except OSError:
                break
            try:
                obj = json.loads(data.decode("utf-8"))
                self.d2d.receive(D2DBasicSafetyMessage(**obj))
            except (json.JSONDecodeError, TypeError, KeyError) as exc:
                print(f"[mock] Malformed D2D-BSM dropped: {exc}")

    def _custom_mode_id(self) -> int:
        for mode_id, name in self.mode_map.items():
            if name == self.mode:
                return mode_id
        return 0

    def send_heartbeat(self) -> None:
        base_mode = mavlink2.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED
        if self.armed:
            base_mode |= mavlink2.MAV_MODE_FLAG_SAFETY_ARMED
        status = mavlink2.MAV_STATE_ACTIVE if self.armed else mavlink2.MAV_STATE_STANDBY
        self.conn.mav.heartbeat_send(
            mavlink2.MAV_TYPE_QUADROTOR, mavlink2.MAV_AUTOPILOT_ARDUPILOTMEGA,
            base_mode, self._custom_mode_id(), status,
        )

    def send_position(self) -> None:
        self.conn.mav.global_position_int_send(
            int(time.time() * 1000) & 0xFFFFFFFF,
            int(self.lat * 1e7), int(self.lon * 1e7),
            int(self.alt_m * 1000), int(self.alt_m * 1000),
            0, 0, 0, 65535,
        )

    def send_sys_status(self) -> None:
        self.conn.mav.sys_status_send(
            0, 0, 0, 500, 12600, -1, 87, 0, 0, 0, 0, 0, 0,
        )

    def send_gps(self) -> None:
        self.conn.mav.gps_raw_int_send(
            int(time.time() * 1e6), 3, int(self.lat * 1e7), int(self.lon * 1e7),
            int(self.alt_m * 1000), 65535, 65535, 0, 0, 10,
        )

    def telemetry_loop(self) -> None:
        while self._running:
            self.send_heartbeat()
            self.send_position()
            self.send_sys_status()
            self.send_gps()
            time.sleep(1.0)

    def command_loop(self) -> None:
        while self._running:
            msg = self.conn.recv_match(blocking=True, timeout=1.0)
            if msg is None:
                continue
            self._gcs_system = msg.get_srcSystem()
            self._gcs_component = msg.get_srcComponent()
            t = msg.get_type()
            if t == "COMMAND_LONG":
                self._handle_command_long(msg)
            elif t == "SET_MODE":
                self._handle_set_mode(msg)
            elif t == "MISSION_COUNT":
                self._handle_mission_count(msg)
            elif t == "PARAM_SET":
                print(f"[mock] PARAM_SET {msg.param_id.strip(chr(0))} = {msg.param_value}")
            elif t == "SET_POSITION_TARGET_GLOBAL_INT":
                self.lat = msg.lat_int / 1e7
                self.lon = msg.lon_int / 1e7
                print(f"[mock] GOTO setpoint ({self.lat:.6f}, {self.lon:.6f})")

    def _ack(self, command: int, result: int) -> None:
        self.conn.mav.command_ack_send(command, result)

    def _handle_command_long(self, msg) -> None:
        cmd = msg.command
        if cmd == mavlink2.MAV_CMD_COMPONENT_ARM_DISARM:
            self.armed = bool(msg.param1)
            print(f"[mock] {'ARMED' if self.armed else 'DISARMED'}")
            self._ack(cmd, mavlink2.MAV_RESULT_ACCEPTED)
        elif cmd == mavlink2.MAV_CMD_NAV_TAKEOFF:
            self.alt_m = msg.param7
            self.mode = "GUIDED"
            print(f"[mock] TAKEOFF -> {self.alt_m}m")
            self._ack(cmd, mavlink2.MAV_RESULT_ACCEPTED)
        elif cmd == mavlink2.MAV_CMD_NAV_RETURN_TO_LAUNCH:
            self.mode = "RTL"
            print("[mock] RTL")
            self._ack(cmd, mavlink2.MAV_RESULT_ACCEPTED)
        elif cmd == mavlink2.MAV_CMD_NAV_LAND:
            self.mode = "LAND"
            self.alt_m = 0.0
            print("[mock] LAND")
            self._ack(cmd, mavlink2.MAV_RESULT_ACCEPTED)
        else:
            self._ack(cmd, mavlink2.MAV_RESULT_ACCEPTED)

    def _handle_set_mode(self, msg) -> None:
        name = self.mode_map.get(msg.custom_mode)
        if name:
            self.mode = name
            print(f"[mock] MODE -> {name}")

    def _handle_mission_count(self, msg) -> None:
        count = msg.count
        print(f"[mock] Mission upload starting, {count} items")
        received = 0
        while received < count:
            self.conn.mav.mission_request_int_send(self._gcs_system, self._gcs_component, received)
            item = self.conn.recv_match(type=["MISSION_ITEM_INT", "MISSION_ITEM"], blocking=True, timeout=3.0)
            if item is None:
                break
            received += 1
        self.conn.mav.mission_ack_send(self._gcs_system, self._gcs_component, mavlink2.MAV_MISSION_ACCEPTED)
        print(f"[mock] Mission upload complete ({received}/{count})")

    def run(self) -> None:
        print(
            f"[mock] Fake ArduPilot vehicle '{self.drone_id}' running — sending telemetry, "
            f"waiting for GCS commands, broadcasting D2D-BSMs on {D2D_MULTICAST_GROUP}:{self._d2d_port}..."
        )
        threading.Thread(target=self.telemetry_loop, daemon=True).start()
        threading.Thread(target=self.command_loop, daemon=True).start()
        threading.Thread(target=self.d2d_broadcast_loop, daemon=True).start()
        threading.Thread(target=self.d2d_receive_loop, daemon=True).start()
        try:
            while True:
                time.sleep(5)
                peers = self.d2d.known_peers()
                print(f"[mock] [{self.drone_id}] D2D link={self.d2d.link_state.state.name} peers={[p.drone_id for p in peers]}")
        except KeyboardInterrupt:
            self._running = False


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=14550)
    parser.add_argument("--drone-id", type=str, default=None, help="Defaults to MOCK-<port>")
    parser.add_argument("--d2d-port", type=int, default=D2D_DEFAULT_PORT)
    args = parser.parse_args()
    MockVehicle(port=args.port, drone_id=args.drone_id, d2d_port=args.d2d_port).run()


if __name__ == "__main__":
    main()
