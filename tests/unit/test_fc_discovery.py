"""Unit tests for aerofleet/hardware/fc_discovery.py's USB serial scan
(fake pyserial port lists and fake openers — no real ports needed) and
its UDP port-conflict handling. UDP HEARTBEAT detection against the real
mock vehicle is in tests/integration/test_fc_compliance_api.py.
"""
import errno
import socket
from dataclasses import dataclass
from typing import Optional

import pytest

from aerofleet.hardware.fc_discovery import (
    SOURCE_MP_FORWARD,
    SOURCE_USB,
    classify_port,
    discover,
    is_busy_error,
    listen_udp_heartbeat,
    scan_serial,
)

pytestmark = pytest.mark.unit


@dataclass
class FakePort:
    """Shape of serial.tools.list_ports_common.ListPortInfo."""
    device: str
    vid: Optional[int] = None
    pid: Optional[int] = None
    manufacturer: Optional[str] = None
    product: Optional[str] = None
    description: str = "n/a"
    serial_number: Optional[str] = None


class FakeSerial:
    def close(self):
        pass


def free_opener(_device):
    return FakeSerial()


class SerialException(IOError):
    """Stands in for serial.SerialException (an IOError subclass)."""


def windows_busy_opener(device):
    raise SerialException(f"could not open port '{device}': PermissionError(13, 'Access is denied.', None, 5)")


def posix_busy_opener(device):
    raise SerialException(errno.EBUSY, f"could not open port {device}: [Errno 16] Resource busy: '{device}'")


class TestClassifyPort:
    @pytest.mark.parametrize("vid,pid,confidence", [
        (0x1209, 0x5740, "high"),   # ArduPilot ChibiOS
        (0x1209, 0x5741, "high"),   # ArduPilot bootloader
        (0x26AC, 0x0011, "high"),   # 3DR / PX4
        (0x2DAE, 0x1016, "high"),   # CubePilot
        (0x3162, 0x004B, "high"),   # Holybro
        (0x0483, 0x5740, "low"),    # generic STM32 virtual COM port
    ])
    def test_known_usb_ids(self, vid, pid, confidence):
        match = classify_port(FakePort("/dev/ttyACM0", vid, pid))
        assert match is not None and match[1] == confidence

    @pytest.mark.parametrize("product", ["Pixhawk6X", "CubeOrange", "ArduPilot", "PX4 FMU v5"])
    def test_product_strings(self, product):
        match = classify_port(FakePort("COM7", 0x1234, 0x0001, product=product))
        assert match is not None and match[1] == "medium"

    def test_unrelated_devices_are_ignored(self):
        assert classify_port(FakePort("COM3", 0x10C4, 0xEA60, manufacturer="Silicon Labs", product="CP2102")) is None
        assert classify_port(FakePort("/dev/ttyS0")) is None
        assert classify_port(FakePort("COM4", 0x0483, 0x3748, product="STM32 STLink")) is None


class TestScanSerial:
    PORTS = [
        FakePort("COM3", 0x10C4, 0xEA60, product="CP2102 USB to UART"),     # telemetry radio, not an FC
        FakePort("COM9", 0x0483, 0x5740, product="STM32 Virtual ComPort"),  # generic, low
        FakePort("COM5", 0x1209, 0x5740, manufacturer="ArduPilot", product="fmuv3"),
    ]

    def test_finds_flight_controllers_and_ranks_by_confidence(self):
        found = scan_serial(self.PORTS, opener=free_opener)
        assert [c.device for c in found] == ["COM5", "COM9"]
        assert found[0].source == SOURCE_USB
        assert found[0].connection == "COM5,115200"
        assert found[0].status == "available" and found[0].usable

    def test_windows_access_denied_is_reported_as_mission_planner_holding_it(self):
        found = scan_serial([self.PORTS[2]], opener=windows_busy_opener)
        assert found[0].status == "in_use"
        assert "in use (Mission Planner?)" in found[0].detail
        assert "enable MAVLink forwarding" in found[0].detail

    def test_posix_resource_busy_is_in_use_too(self):
        found = scan_serial([self.PORTS[2]], opener=posix_busy_opener)
        assert found[0].status == "in_use"

    def test_other_open_errors_are_not_mislabelled_as_busy(self):
        def gone(device):
            raise SerialException(errno.ENOENT, f"could not open port {device}: No such file or directory")
        found = scan_serial([self.PORTS[2]], opener=gone)
        assert found[0].status == "error"

    def test_bootloader_is_not_offered_for_connection(self):
        found = scan_serial([FakePort("COM6", 0x1209, 0x5741)], opener=free_opener)
        assert found[0].status == "error" and "bootloader" in found[0].detail

    def test_busy_error_detection_walks_the_exception_chain(self):
        try:
            try:
                raise PermissionError(13, "Access is denied.")
            except PermissionError as inner:
                raise RuntimeError("wrapped") from inner
        except RuntimeError as outer:
            assert is_busy_error(outer)


class TestDiscover:
    def test_usb_found_when_no_forward(self):
        port = _free_udp_port()
        result = discover(udp_ports=[port], listen_s=0.3,
                          port_lister=lambda: [FakePort("/dev/ttyACM0", 0x2DAE, 0x1016, product="CubeOrange")],
                          serial_opener=free_opener)
        assert result.recommended is not None
        assert result.recommended.source == SOURCE_USB
        assert result.to_dict()["mission_planner_help"]  # instructions still shown when no forward found

    def test_only_busy_usb_gives_the_forwarding_advice(self):
        result = discover(udp_ports=[_free_udp_port()], listen_s=0.3,
                          port_lister=lambda: [FakePort("COM5", 0x1209, 0x5740)], serial_opener=windows_busy_opener)
        assert result.recommended is None
        assert "in use (Mission Planner?)" in result.summary
        assert "MAVLink Mirror" in result.to_dict()["mission_planner_help"]

    def test_nothing_found(self):
        result = discover(udp_ports=[_free_udp_port()], listen_s=0.3, port_lister=lambda: [], serial_opener=free_opener)
        assert result.recommended is None
        assert result.summary == "No flight controller found."
        assert "Ctrl-F" in result.to_dict()["mission_planner_help"]

    def test_pyserial_missing_is_reported(self):
        result = discover(udp_ports=[_free_udp_port()], listen_s=0.2, port_lister=lambda: None)
        assert result.serial_scan_available is False
        assert any("pyserial" in n for n in result.notes)

    def test_udp_port_already_bound_is_reported_not_crashed(self):
        blocker = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        blocker.bind(("127.0.0.1", 0))
        port = blocker.getsockname()[1]
        try:
            cand = listen_udp_heartbeat(port, 0.2, host="127.0.0.1")
            assert cand.source == SOURCE_MP_FORWARD
            assert cand.status == "port_busy" and "already bound" in cand.detail
        finally:
            blocker.close()

    def test_non_mavlink_udp_traffic_is_not_a_vehicle(self):
        port = _free_udp_port()
        sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        import threading
        import time

        def spam():
            for _ in range(10):
                sender.sendto(b"hello, not mavlink", ("127.0.0.1", port))
                time.sleep(0.03)
        threading.Thread(target=spam, daemon=True).start()
        try:
            cand = listen_udp_heartbeat(port, 0.5, host="127.0.0.1")
            assert cand.status == "no_heartbeat" and not cand.usable
        finally:
            sender.close()


def _free_udp_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]
