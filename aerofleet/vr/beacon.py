"""'AeroFleet is here' UDP beacon, broadcast only while a VR session is open.

A standalone headset on the same Wi-Fi has no idea which laptop runs
AeroFleet. Once a second this sends a small JSON datagram to the LAN
broadcast addresses (and to localhost, for a viewer on this same machine or
the Unity editor) on BEACON_PORT; the headset app listens there and offers
"Connect to <host>". The beacon carries no secrets — only where to knock.
"""
from __future__ import annotations

import json
import socket
import threading
from typing import Callable, List, Optional

from aerofleet.utils.logging import get_logger

logger = get_logger(__name__)

BEACON_PORT = 47800
BEACON_INTERVAL_S = 1.0


def lan_addresses() -> List[str]:
    """This machine's IPv4 addresses on local networks (no internet traffic is sent:
    connecting a UDP socket only asks the OS which interface would be used)."""
    addrs = set()
    for probe in ("10.255.255.255", "192.168.255.255", "172.31.255.255"):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect((probe, 1))
                addrs.add(s.getsockname()[0])
        except OSError:
            pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            addrs.add(info[4][0])
    except OSError:
        pass
    return sorted(a for a in addrs if not a.startswith("127.") and not a.startswith("169.254."))


def broadcast_targets(addrs: List[str]) -> List[str]:
    """Limited broadcast plus each address's /24 directed broadcast (home and lab Wi-Fi are
    almost always /24; the limited broadcast covers the rest on most routers)."""
    targets = {"255.255.255.255", "127.0.0.1"}
    for a in addrs:
        parts = a.split(".")
        if len(parts) == 4:
            targets.add(".".join(parts[:3] + ["255"]))
    return sorted(targets)


class Beacon:
    def __init__(self, payload: Callable[[], dict], port: int = BEACON_PORT) -> None:
        self._payload = payload
        self._port = port
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="aerofleet-vr-beacon", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            while not self._stop.is_set():
                data = json.dumps(self._payload()).encode()
                for target in broadcast_targets(lan_addresses()):
                    try:
                        s.sendto(data, (target, self._port))
                    except OSError:
                        pass  # an interface can vanish (Wi-Fi off) — keep beaconing on the rest
                self._stop.wait(BEACON_INTERVAL_S)
