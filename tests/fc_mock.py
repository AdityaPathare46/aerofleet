"""Spawn tools/mock_mavlink_vehicle.py for flight-controller compliance tests.

These tests talk real MAVLink2 over a real UDP socket to the mock (no
mocking of pymavlink). The mock *sends* to 127.0.0.1:<port>, exactly like
Mission Planner's MAVLink mirror in "UDP Client" mode, so AeroFleet's
discovery/inspector listen on that port.
"""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, List

REPO_ROOT = Path(__file__).resolve().parent.parent
MOCK_VEHICLE_SCRIPT = REPO_ROOT / "tools" / "mock_mavlink_vehicle.py"


def free_udp_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@contextmanager
def running_mock(profile: str = "healthy", *extra_args: str) -> Iterator[int]:
    """Start a mock vehicle on a free UDP port; yields the port."""
    port = free_udp_port()
    env = dict(os.environ)
    env["PYTHONPATH"] = str(REPO_ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    cmd: List[str] = [sys.executable, str(MOCK_VEHICLE_SCRIPT), "--port", str(port), "--no-d2d",
                      "--profile", profile, *extra_args]
    # Hold the port ourselves until the mock's first datagram arrives, so
    # tests never race the mock's (slow) pymavlink import; then release it
    # for the code under test to bind.
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    probe.bind(("127.0.0.1", port))
    proc = subprocess.Popen(cmd, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    try:
        probe.settimeout(0.5)
        deadline = time.monotonic() + 20.0
        while True:
            try:
                probe.recvfrom(4096)
                break
            except socket.timeout:
                if proc.poll() is not None:
                    raise RuntimeError(f"mock vehicle exited: {proc.stderr.read().decode(errors='replace')}")
                if time.monotonic() > deadline:
                    raise RuntimeError("mock vehicle sent nothing within 20 s")
        probe.close()
        yield port
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
