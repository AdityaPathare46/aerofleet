"""Find a flight controller the operator has plugged into this laptop.

Two access paths, tried in this order:

1. **Mission Planner's forwarded MAVLink over UDP.** Mission Planner owns
   the USB serial port while it is connected, and a COM port can only be
   opened by one program at a time. Its MAVLink Mirror (Ctrl-F ->
   "MAVLink", or SETUP > Advanced > MAVLink Mirror) set to *UDP Client*,
   host 127.0.0.1, port 14550 re-sends every packet it receives from the
   vehicle to that port — we listen there (and on 14551, a common second
   choice when something else already has 14550) for a vehicle HEARTBEAT.
   Tick "Write" in that dialog, otherwise Mission Planner drops our
   parameter requests and the report will mark parameter checks UNKNOWN.

2. **Direct USB.** Only if no forwarded stream is found: enumerate serial
   ports and match known flight-controller USB IDs / product strings. If
   opening a matching port fails with a permission/busy error, it is
   almost always Mission Planner (or QGroundControl) holding it — we say
   exactly that instead of a generic error.

Nothing here writes to the vehicle: discovery listens for HEARTBEATs and,
for USB, opens and immediately closes the port to learn whether it is free.
"""
from __future__ import annotations

import errno
import os
import socket
import threading
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from aerofleet.utils.logging import get_logger

logger = get_logger(__name__)

SOURCE_MP_FORWARD = "mission_planner_forward"
SOURCE_USB = "usb"
SOURCE_MANUAL = "manual"

DEFAULT_UDP_PORTS: Tuple[int, ...] = (14550, 14551)
DEFAULT_LISTEN_S = 2.0
DEFAULT_SERIAL_BAUD = 115200  # USB CDC ignores it; ArduPilot's SERIAL0_BAUD default is 115

MISSION_PLANNER_FORWARDING_HELP = (
    "No forwarded MAVLink stream found. If Mission Planner is connected to the drone, it owns the "
    "USB port — turn on its MAVLink Mirror once: press Ctrl-F, click \"MAVLink\" (or SETUP > "
    "Advanced > MAVLink Mirror), choose \"UDP Client\", tick \"Write\", then enter host 127.0.0.1 "
    "and port 14550 (use 14551 if 14550 is taken). Leave Mission Planner connected and run the "
    "check again. Without Mission Planner, plug the flight controller in over USB and close any "
    "other ground-station software."
)

# (vid, pid or None for "any pid", label, confidence)
KNOWN_USB_IDS: Tuple[Tuple[int, Optional[int], str, str], ...] = (
    (0x1209, 0x5740, "ArduPilot (ChibiOS)", "high"),
    (0x1209, 0x5741, "ArduPilot bootloader", "high"),
    (0x26AC, None, "3DR / PX4 FMU", "high"),
    (0x2DAE, None, "CubePilot", "high"),
    (0x3162, None, "Holybro", "high"),
    (0x0483, 0x5740, "STMicroelectronics virtual COM port (generic)", "low"),
)
PRODUCT_KEYWORDS: Tuple[str, ...] = ("ardupilot", "px4", "pixhawk", "cube")
_CONFIDENCE_RANK = {"high": 0, "medium": 1, "low": 2}

# Windows reports "PermissionError(13, 'Access is denied.')" for a COM port
# another program holds; Linux/macOS give EBUSY ("Resource busy") or, with
# exclusive locking, "Could not exclusively lock port".
_BUSY_ERRNOS = {errno.EACCES, errno.EBUSY, errno.EPERM}
_BUSY_MARKERS = ("access is denied", "permission", "resource busy", "busy", "in use",
                 "could not exclusively lock", "exclusively")


@dataclass(frozen=True)
class FCCandidate:
    source: str                      # SOURCE_MP_FORWARD | SOURCE_USB
    connection: str                  # pymavlink connection string
    label: str
    confidence: str                  # high | medium | low
    status: str                      # heartbeat | available | in_use | port_busy | error
    detail: str = ""
    udp_port: Optional[int] = None
    device: Optional[str] = None
    vid: Optional[int] = None
    pid: Optional[int] = None
    manufacturer: Optional[str] = None
    product: Optional[str] = None
    serial_number: Optional[str] = None
    system_id: Optional[int] = None
    component_id: Optional[int] = None
    autopilot: Optional[int] = None
    vehicle_type: Optional[int] = None

    @property
    def usable(self) -> bool:
        return self.status in ("heartbeat", "available")

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["usable"] = self.usable
        if self.vid is not None:
            d["usb_id"] = f"{self.vid:04X}:{self.pid:04X}" if self.pid is not None else f"{self.vid:04X}"
        return d


@dataclass(frozen=True)
class DiscoveryResult:
    candidates: Tuple[FCCandidate, ...]
    udp_ports_checked: Tuple[int, ...]
    serial_ports_seen: int
    notes: Tuple[str, ...] = ()
    serial_scan_available: bool = True

    @property
    def recommended(self) -> Optional[FCCandidate]:
        forwarded = [c for c in self.candidates if c.source == SOURCE_MP_FORWARD and c.usable]
        if forwarded:
            return forwarded[0]
        usb = [c for c in self.candidates if c.source == SOURCE_USB and c.usable]
        usb.sort(key=lambda c: _CONFIDENCE_RANK.get(c.confidence, 9))
        return usb[0] if usb else None

    @property
    def summary(self) -> str:
        rec = self.recommended
        if rec is not None and rec.source == SOURCE_MP_FORWARD:
            return f"Found Mission Planner's forwarded MAVLink on UDP {rec.udp_port}."
        if rec is not None:
            return f"Found a flight controller on {rec.device} ({rec.label})."
        busy = [c for c in self.candidates if c.status == "in_use"]
        if busy:
            return (f"{busy[0].device} is in use (Mission Planner?) — enable MAVLink forwarding "
                    "in Mission Planner so AeroFleet can read the same link.")
        return "No flight controller found."

    def to_dict(self) -> Dict[str, Any]:
        rec = self.recommended
        return {
            "candidates": [c.to_dict() for c in self.candidates],
            "recommended": rec.to_dict() if rec else None,
            "udp_ports_checked": list(self.udp_ports_checked),
            "serial_ports_seen": self.serial_ports_seen,
            "serial_scan_available": self.serial_scan_available,
            "notes": list(self.notes),
            "summary": self.summary,
            "mission_planner_help": None if (rec and rec.source == SOURCE_MP_FORWARD) else MISSION_PLANNER_FORWARDING_HELP,
        }


# ─────────────────────────────────────────────────────────────────────────
#  UDP — Mission Planner forward
# ─────────────────────────────────────────────────────────────────────────

def udp_host() -> str:
    """Interface to listen on. Mission Planner on the same laptop sends to
    127.0.0.1; set AEROFLEET_FC_UDP_HOST=0.0.0.0 to accept a forward from
    another machine on the LAN."""
    return os.environ.get("AEROFLEET_FC_UDP_HOST", "127.0.0.1")


def configured_udp_ports() -> Tuple[int, ...]:
    raw = os.environ.get("AEROFLEET_FC_UDP_PORTS")
    if not raw:
        return DEFAULT_UDP_PORTS
    ports = []
    for part in raw.split(","):
        part = part.strip()
        if part.isdigit():
            ports.append(int(part))
    return tuple(ports) or DEFAULT_UDP_PORTS


def _new_parser():
    # The v2.0 ardupilotmega parser decodes both MAVLink1 and MAVLink2
    # frames, independent of whatever global dialect mavutil has selected.
    from pymavlink.dialects.v20 import ardupilotmega as mav2

    parser = mav2.MAVLink(None)
    parser.robust_parsing = True
    return parser, mav2


def listen_udp_heartbeat(port: int, timeout_s: float = DEFAULT_LISTEN_S, host: Optional[str] = None) -> FCCandidate:
    """Bind ``host:port`` and wait up to ``timeout_s`` for a vehicle HEARTBEAT
    (ignoring GCS/companion heartbeats)."""
    host = host or udp_host()
    connection = f"udpin:{host}:{port}"
    label = f"Mission Planner MAVLink forward (UDP {port})"
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.bind((host, port))
    except OSError as exc:
        sock.close()
        busy = exc.errno in (errno.EADDRINUSE, getattr(errno, "WSAEADDRINUSE", -1))
        detail = (
            f"UDP {port} is already bound by another program on this PC (QGroundControl, another "
            "AeroFleet link, or a second listener) — point Mission Planner's mirror at a free port "
            "such as 14551." if busy else f"Could not listen on UDP {port}: {exc}"
        )
        return FCCandidate(SOURCE_MP_FORWARD, connection, label, "high",
                           "port_busy" if busy else "error", detail, udp_port=port)

    parser, mav2 = _new_parser()
    deadline = time.monotonic() + timeout_s
    packets = 0
    try:
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            sock.settimeout(remaining)
            try:
                data, _addr = sock.recvfrom(4096)
            except socket.timeout:
                break
            except OSError:
                break
            packets += 1
            try:
                msgs = parser.parse_buffer(data) or []
            except Exception:
                continue
            for msg in msgs:
                if msg.get_type() != "HEARTBEAT":
                    continue
                if msg.type in (mav2.MAV_TYPE_GCS, mav2.MAV_TYPE_ONBOARD_CONTROLLER) \
                        or msg.autopilot == mav2.MAV_AUTOPILOT_INVALID:
                    continue
                return FCCandidate(
                    SOURCE_MP_FORWARD, connection, label, "high", "heartbeat",
                    f"Vehicle HEARTBEAT received on UDP {port} (system {msg.get_srcSystem()}).",
                    udp_port=port, system_id=msg.get_srcSystem(), component_id=msg.get_srcComponent(),
                    autopilot=msg.autopilot, vehicle_type=msg.type,
                )
    finally:
        sock.close()
    detail = (f"{packets} packets on UDP {port} but no vehicle HEARTBEAT." if packets
              else f"Nothing received on UDP {port} in {timeout_s:.1f}s.")
    return FCCandidate(SOURCE_MP_FORWARD, connection, label, "high", "no_heartbeat", detail, udp_port=port)


# ─────────────────────────────────────────────────────────────────────────
#  USB serial
# ─────────────────────────────────────────────────────────────────────────

def list_serial_ports() -> Optional[List[Any]]:
    """pyserial's port list, or None when pyserial isn't installed."""
    try:
        from serial.tools import list_ports
    except ImportError:
        return None
    try:
        return list(list_ports.comports())
    except Exception as exc:  # pragma: no cover - platform enumeration failure
        logger.warning(f"Serial port enumeration failed: {exc}")
        return []


def classify_port(port: Any) -> Optional[Tuple[str, str]]:
    """(label, confidence) when a pyserial ListPortInfo looks like a flight
    controller, else None."""
    vid = getattr(port, "vid", None)
    pid = getattr(port, "pid", None)
    if vid is not None:
        for k_vid, k_pid, label, confidence in KNOWN_USB_IDS:
            if vid == k_vid and (k_pid is None or pid == k_pid):
                return label, confidence
    text = " ".join(str(getattr(port, attr, "") or "") for attr in ("product", "manufacturer", "description")).lower()
    for kw in PRODUCT_KEYWORDS:
        if kw in text:
            return f"USB device matching '{kw}'", "medium"
    return None


def is_busy_error(exc: BaseException) -> bool:
    seen = set()
    cur: Optional[BaseException] = exc
    while cur is not None and id(cur) not in seen:
        seen.add(id(cur))
        if isinstance(cur, PermissionError):
            return True
        if isinstance(cur, OSError) and cur.errno in _BUSY_ERRNOS:
            return True
        if any(marker in str(cur).lower() for marker in _BUSY_MARKERS):
            return True
        cur = cur.__cause__ or cur.__context__
    return False


def in_use_message(device: str) -> str:
    return (f"{device} is in use (Mission Planner?) — enable MAVLink forwarding in Mission Planner "
            "(Ctrl-F > MAVLink, UDP Client, 127.0.0.1:14550, tick Write) instead of disconnecting it.")


def _default_serial_opener(device: str):
    import serial

    kwargs: Dict[str, Any] = {"baudrate": DEFAULT_SERIAL_BAUD, "timeout": 0}
    if os.name == "posix":
        kwargs["exclusive"] = True  # flock(): fails if another program holds it exclusively
    return serial.Serial(device, **kwargs)


def probe_serial(device: str, opener: Optional[Callable[[str], Any]] = None) -> Tuple[str, str]:
    """Open-and-close to learn if the port is free. Returns (status, detail)."""
    opener = opener or _default_serial_opener
    try:
        handle = opener(device)
    except Exception as exc:
        if is_busy_error(exc):
            return "in_use", in_use_message(device)
        return "error", f"Could not open {device}: {exc}"
    try:
        handle.close()
    except Exception:
        pass
    return "available", f"{device} is free; AeroFleet will connect directly."


def serial_connection_string(device: str) -> str:
    return f"{device},{DEFAULT_SERIAL_BAUD}"


def scan_serial(
    ports: Optional[Iterable[Any]] = None, probe: bool = True,
    opener: Optional[Callable[[str], Any]] = None,
) -> List[FCCandidate]:
    found: List[FCCandidate] = []
    for port in ports or []:
        match = classify_port(port)
        if match is None:
            continue
        label, confidence = match
        device = getattr(port, "device", None) or str(port)
        if getattr(port, "pid", None) == 0x5741:
            status, detail = "error", (f"{device} is an ArduPilot board sitting in its bootloader — "
                                       "wait a few seconds for the firmware to start, then re-scan.")
        elif probe:
            status, detail = probe_serial(device, opener)
        else:
            status, detail = "available", f"{device} matched {label}."
        found.append(FCCandidate(
            SOURCE_USB, serial_connection_string(device), label, confidence, status, detail,
            device=device, vid=getattr(port, "vid", None), pid=getattr(port, "pid", None),
            manufacturer=getattr(port, "manufacturer", None), product=getattr(port, "product", None),
            serial_number=getattr(port, "serial_number", None),
        ))
    found.sort(key=lambda c: _CONFIDENCE_RANK.get(c.confidence, 9))
    return found


# ─────────────────────────────────────────────────────────────────────────
#  Entry point
# ─────────────────────────────────────────────────────────────────────────

def discover(
    udp_ports: Optional[Sequence[int]] = None,
    listen_s: float = DEFAULT_LISTEN_S,
    scan_usb: bool = True,
    port_lister: Optional[Callable[[], Optional[List[Any]]]] = None,
    serial_opener: Optional[Callable[[str], Any]] = None,
    host: Optional[str] = None,
) -> DiscoveryResult:
    """Listen on every UDP port in parallel (so the whole scan costs one
    ``listen_s``), then — only when no forwarded vehicle was heard — scan
    and probe USB serial ports."""
    ports = tuple(udp_ports) if udp_ports is not None else configured_udp_ports()
    results: Dict[int, FCCandidate] = {}

    def _listen(p: int) -> None:
        results[p] = listen_udp_heartbeat(p, listen_s, host)

    threads = [threading.Thread(target=_listen, args=(p,), daemon=True) for p in ports]
    for t in threads:
        t.start()
    for t in threads:
        t.join(listen_s + 2.0)

    candidates: List[FCCandidate] = [results[p] for p in ports if p in results]
    notes: List[str] = []
    for c in candidates:
        if c.status == "port_busy":
            notes.append(c.detail)
    heard = any(c.status == "heartbeat" for c in candidates)

    serial_seen = 0
    serial_available = True
    if scan_usb and not heard:
        port_list = (port_lister or list_serial_ports)()
        if port_list is None:
            serial_available = False
            notes.append("USB scan unavailable: pyserial is not installed (pip install pyserial).")
        else:
            serial_seen = len(port_list)
            candidates.extend(scan_serial(port_list, probe=True, opener=serial_opener))
    elif heard:
        notes.append("Forwarded MAVLink found — USB scan skipped (Mission Planner holds that port).")

    # Only surface UDP "nothing heard" rows when nothing else was found, to
    # keep the UI list about real devices.
    if any(c.usable or c.status == "in_use" for c in candidates):
        candidates = [c for c in candidates if c.status != "no_heartbeat"]

    result = DiscoveryResult(tuple(candidates), ports, serial_seen, tuple(notes), serial_available)
    logger.info(f"FC discovery: {result.summary}")
    return result
