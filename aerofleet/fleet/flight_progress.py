"""Kinematic flight-progress model for SIMULATED drones.

SIMULATED drones previously had no position between dispatch and
completion — they stayed on their origin depot's graph node the whole
flight. So every drone launched from the same depot reported 0 m
separation from every other, and anything spatial (the VR Safety View's
swarm separation, live CBF min_separation) read a phantom collision at
the depot pad.

This dead-reckons each approved flight along its real planned route
(the same optimized node path dispatch_order already computes and hands
to the CBF gate) at a constant cruise speed. It is deliberately simple:
no acceleration, no wind drift, no auto-completion on arrival — a drone
that reaches its destination holds there (``arrived=True``) until the
existing order lifecycle moves it on. LIVE drones never use this; they
report their real position over MAVLink.
"""
from __future__ import annotations

import math
import threading
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

CRUISE_SPEED_MPS = 12.0
_EARTH_RADIUS_M = 6_371_000.0

LatLon = Tuple[float, float]


def haversine_m(a: LatLon, b: LatLon) -> float:
    lat1, lon1 = map(math.radians, a)
    lat2, lon2 = map(math.radians, b)
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 2 * _EARTH_RADIUS_M * math.asin(math.sqrt(h))


def bearing_deg(a: LatLon, b: LatLon) -> float:
    lat1, lon1 = map(math.radians, a)
    lat2, lon2 = map(math.radians, b)
    y = math.sin(lon2 - lon1) * math.cos(lat2)
    x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(lon2 - lon1)
    return (math.degrees(math.atan2(y, x)) + 360.0) % 360.0


def downsample(path: List[LatLon], max_points: int) -> List[LatLon]:
    """Evenly thin a polyline, always keeping both endpoints."""
    if len(path) <= max_points or max_points < 2:
        return list(path)
    step = (len(path) - 1) / (max_points - 1)
    return [path[round(i * step)] for i in range(max_points)]


@dataclass
class FlightState:
    lat: float
    lon: float
    heading_deg: float
    progress: float          # 0..1 along the planned route
    flown_m: float
    remaining_m: float
    arrived: bool
    remaining_path: List[LatLon]


@dataclass
class PlannedFlight:
    drone_id: str
    order_id: str
    path: List[LatLon]
    altitude_m: float
    started_at: float
    speed_mps: float = CRUISE_SPEED_MPS
    _cum_m: List[float] = field(default_factory=list, repr=False)

    def __post_init__(self) -> None:
        if not self.path:
            raise ValueError("PlannedFlight needs at least one waypoint")
        cum = [0.0]
        for p, q in zip(self.path, self.path[1:]):
            cum.append(cum[-1] + haversine_m(p, q))
        self._cum_m = cum

    @property
    def total_m(self) -> float:
        return self._cum_m[-1]

    @property
    def destination(self) -> LatLon:
        return self.path[-1]

    def state_at(self, now: float) -> FlightState:
        flown = max(0.0, (now - self.started_at) * self.speed_mps)
        total = self.total_m
        if total <= 0.0 or len(self.path) == 1:
            lat, lon = self.path[-1]
            return FlightState(lat, lon, 0.0, 1.0, 0.0, 0.0, True, [self.path[-1]])
        if flown >= total:
            heading = bearing_deg(self.path[-2], self.path[-1])
            lat, lon = self.path[-1]
            return FlightState(lat, lon, heading, 1.0, total, 0.0, True, [self.path[-1]])

        # Segment containing the current distance.
        i = 0
        while i + 1 < len(self._cum_m) and self._cum_m[i + 1] < flown:
            i += 1
        a, b = self.path[i], self.path[i + 1]
        seg = self._cum_m[i + 1] - self._cum_m[i]
        t = 0.0 if seg <= 0 else (flown - self._cum_m[i]) / seg
        lat = a[0] + (b[0] - a[0]) * t
        lon = a[1] + (b[1] - a[1]) * t
        return FlightState(
            lat=lat, lon=lon,
            heading_deg=bearing_deg(a, b),
            progress=flown / total,
            flown_m=flown,
            remaining_m=total - flown,
            arrived=False,
            remaining_path=[(lat, lon)] + self.path[i + 1:],
        )


_LOCK = threading.Lock()
_FLIGHTS: Dict[Tuple[str, str], PlannedFlight] = {}


def register(
    city: str, drone_id: str, order_id: str, path: List[LatLon], altitude_m: float,
    started_at: Optional[float] = None, speed_mps: float = CRUISE_SPEED_MPS,
) -> PlannedFlight:
    flight = PlannedFlight(
        drone_id=drone_id, order_id=order_id, path=list(path), altitude_m=altitude_m,
        started_at=time.time() if started_at is None else started_at, speed_mps=speed_mps,
    )
    with _LOCK:
        _FLIGHTS[(city, drone_id)] = flight
    return flight


def get(city: str, drone_id: str) -> Optional[PlannedFlight]:
    with _LOCK:
        return _FLIGHTS.get((city, drone_id))


def clear(city: Optional[str] = None, drone_id: Optional[str] = None) -> None:
    with _LOCK:
        if city is None:
            _FLIGHTS.clear()
        elif drone_id is None:
            for key in [k for k in _FLIGHTS if k[0] == city]:
                del _FLIGHTS[key]
        else:
            _FLIGHTS.pop((city, drone_id), None)
