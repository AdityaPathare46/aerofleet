"""Real MAVLink wire-protocol test — spawns tools/mock_mavlink_vehicle.py
as a subprocess and drives a real aerofleet.hardware.mavlink_link.
MAVLinkVehicle against it over a real UDP socket. This is the only test in
the suite that actually exercises the wire protocol end to end rather than
mocking pymavlink; everything else in tests/unit/test_mavlink_link.py
tests the pure decode/dispatch logic without a socket.

Excluded from the default `pytest tests/` run (see the `-m "not hardware"`
in pytest.ini/pyproject.toml) since it needs a free UDP port and real
subprocess timing, not just Python-level mocking — run explicitly with:
    pytest tests/ -m hardware
"""
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

from aerofleet.hardware.mavlink_link import MAVLinkVehicle

pytestmark = pytest.mark.hardware

REPO_ROOT = Path(__file__).parent.parent.parent
MOCK_VEHICLE_SCRIPT = REPO_ROOT / "tools" / "mock_mavlink_vehicle.py"


def _free_udp_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def mock_vehicle_process():
    port = _free_udp_port()
    proc = subprocess.Popen(
        [sys.executable, str(MOCK_VEHICLE_SCRIPT), "--port", str(port)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    time.sleep(0.5)  # let it bind and start sending heartbeats
    try:
        yield port
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()


class TestMockVehicleFullSequence:
    """Codifies the same connect -> arm -> takeoff -> mission-upload -> RTL
    -> disarm sequence manually verified against this same mock vehicle
    during the original hardware-integration phase, as an actual
    repeatable, automated test."""

    def test_full_command_sequence_round_trips(self, mock_vehicle_process):
        port = mock_vehicle_process
        vehicle = MAVLinkVehicle(f"udpin:127.0.0.1:{port}", drone_id="TEST-HW")
        try:
            vehicle.connect(heartbeat_timeout_s=5)
            assert vehicle.is_connected is True

            time.sleep(1.2)
            telemetry = vehicle.poll()
            assert telemetry.lat == pytest.approx(18.5204, abs=1e-3)
            assert telemetry.gps_fix_type == 3
            assert telemetry.autopilot_type == "ARDUPILOT"

            assert vehicle.arm() is True
            time.sleep(1.2)
            assert vehicle.poll().armed is True

            assert vehicle.takeoff(30.0) is True
            vehicle.goto(18.53, 73.85, 30.0)  # no ACK — a streamed setpoint, not a command
            assert vehicle.upload_mission([(18.531, 73.851, 40.0), (18.532, 73.852, 40.0)]) is True
            assert vehicle.set_mode("LOITER") is True
            assert vehicle.return_to_launch() is True
            assert vehicle.disarm() is True
        finally:
            vehicle.close()

    def test_connect_to_nothing_listening_raises(self):
        from aerofleet.hardware.mavlink_link import MAVLinkConnectionError

        dead_port = _free_udp_port()  # bound briefly, released, nothing is actually listening
        vehicle = MAVLinkVehicle(f"udpin:127.0.0.1:{dead_port}", drone_id="TEST-HW-DEAD")
        with pytest.raises(MAVLinkConnectionError):
            vehicle.connect(heartbeat_timeout_s=2)
