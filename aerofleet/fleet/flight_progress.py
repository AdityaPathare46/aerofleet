"""Kinematic flight-progress model for SIMULATED drones.

SIMULATED drones previously had no position between dispatch and
completion — they stayed on their origin depot's graph node the whole
flight. So every drone launched from the same depot reported 0 m
separation from every other, and anything spatial (the VR Safety View's
swarm separation, live CBF min_separation) read a phantom collision at
the depot pad.

This dead-reckons each approved flight along its real planned route
(the same optimized node path dispatch_order already computes and hands
to the CBF gate) with a three-phase vertical profile, the way a delivery
multirotor actually flies it:

  CLIMB    vertical at the origin depot, 0 -> cruise altitude at CLIMB_RATE_MPS
  CRUISE   along the route at the cruise altitude, CRUISE_SPEED_MPS
  DESCENT  vertical at the destination, cruise altitude -> 0 at DESCENT_RATE_MPS
  LANDED   on the ground at the destination (``arrived=True``) until the
           existing order lifecycle moves the drone on

Because the whole flight is a known function of time, ``trajectory()``
returns it as time-stamped 4D points (past and future) — what the VR
views draw and what conflict_forecast.py projects forward. It is
deliberately simple: constant rates, no acceleration, no wind drift.
LIVE drones never use this; they report their real position over MAVLink
and have no forecast.
"""
from __future__ import annotations

import math
import threading
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

CRUISE_SPEED_MPS = 12.0
# Conservative delivery-multirotor vertical rates (consumer quadcopters are
# limited to ~5-6 m/s up and ~3-4 m/s down; loaded delivery drones fly slower).
CLIMB_RATE_MPS = 3.0
DESCENT_RATE_MPS = 2.0

CLIMB, CRUISE, DESCENT, LANDED = "CLIMB", "CRUISE", "DESCENT", "LANDED"
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
    progress: float          # 0..1 along the planned route (horizontal)
    flown_m: float
    remaining_m: float
    arrived: bool            # landed at the destination
    remaining_path: List[LatLon]
    altitude_m: float = 0.0  # above ground, from the vertical profile
    phase: str = CRUISE
    eta_s: float = 0.0       # seconds until touchdown


@dataclass
class PlannedFlight:
    drone_id: str
    order_id: str
    path: List[LatLon]
    altitude_m: float
    started_at: float
    speed_mps: float = CRUISE_SPEED_MPS
    climb_mps: float = CLIMB_RATE_MPS
    descent_mps: float = DESCENT_RATE_MPS
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

    @property
    def climb_s(self) -> float:
        return self.altitude_m / self.climb_mps if self.climb_mps > 0 else 0.0

    @property
    def cruise_s(self) -> float:
        return self.total_m / self.speed_mps

    @property
    def descent_s(self) -> float:
        return self.altitude_m / self.descent_mps if self.descent_mps > 0 else 0.0

    @property
    def duration_s(self) -> float:
        return self.climb_s + self.cruise_s + self.descent_s

    def _point_at_distance(self, flown: float) -> Tuple[LatLon, int]:
        """Position `flown` metres along the route, and the index of the segment it's on."""
        if len(self.path) == 1 or self.total_m <= 0.0:
            return self.path[-1], max(len(self.path) - 2, 0)
        flown = min(max(flown, 0.0), self.total_m)
        i = 0
        while i + 2 < len(self._cum_m) and self._cum_m[i + 1] < flown:
            i += 1
        a, b = self.path[i], self.path[i + 1]
        seg = self._cum_m[i + 1] - self._cum_m[i]
        t = 0.0 if seg <= 0 else (flown - self._cum_m[i]) / seg
        return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t), i

    def _heading(self, i: int) -> float:
        return bearing_deg(self.path[i], self.path[i + 1]) if len(self.path) > 1 else 0.0

    def state_at(self, now: float) -> FlightState:
        elapsed = max(0.0, now - self.started_at)
        total = self.total_m
        eta = max(0.0, self.duration_s - elapsed)

        if elapsed < self.climb_s:
            lat, lon = self.path[0]
            return FlightState(lat, lon, self._heading(0), 0.0, 0.0, total, False, list(self.path),
                               altitude_m=elapsed * self.climb_mps, phase=CLIMB, eta_s=eta)

        cruise_elapsed = elapsed - self.climb_s
        if cruise_elapsed < self.cruise_s:
            flown = cruise_elapsed * self.speed_mps
            (lat, lon), i = self._point_at_distance(flown)
            return FlightState(
                lat=lat, lon=lon, heading_deg=self._heading(i), progress=flown / total,
                flown_m=flown, remaining_m=total - flown, arrived=False,
                remaining_path=[(lat, lon)] + self.path[i + 1:],
                altitude_m=self.altitude_m, phase=CRUISE, eta_s=eta,
            )

        lat, lon = self.path[-1]
        heading = self._heading(len(self.path) - 2) if len(self.path) > 1 else 0.0
        descent_elapsed = cruise_elapsed - self.cruise_s
        if descent_elapsed < self.descent_s:
            return FlightState(lat, lon, heading, 1.0, total, 0.0, False, [self.path[-1]],
                               altitude_m=self.altitude_m - descent_elapsed * self.descent_mps, phase=DESCENT, eta_s=eta)
        return FlightState(lat, lon, heading, 1.0, total, 0.0, True, [self.path[-1]],
                           altitude_m=0.0, phase=LANDED, eta_s=0.0)

    def trajectory(self, now: float, max_points: int = 48) -> List[Tuple[float, float, float, float]]:
        """The whole flight as (lat, lon, altitude_m, t_rel_s) points, where t_rel_s is
        seconds relative to `now` (negative = already flown). Always includes the
        take-off point, top of climb, the route (thinned to fit), top of descent,
        touchdown, and the drone's current position at t_rel_s = 0 while airborne."""
        t0 = self.started_at - now
        alt = self.altitude_m
        pts: List[Tuple[float, float, float, float]] = [(*self.path[0], 0.0, t0), (*self.path[0], alt, t0 + self.climb_s)]
        route_idx = list(range(len(self.path)))
        if len(route_idx) > max_points - 5:
            step = (len(route_idx) - 1) / (max_points - 6)
            route_idx = sorted({round(k * step) for k in range(max_points - 5)} | {len(self.path) - 1})
        for k in route_idx[1:]:
            pts.append((*self.path[k], alt, t0 + self.climb_s + self._cum_m[k] / self.speed_mps))
        pts.append((*self.path[-1], 0.0, t0 + self.duration_s))

        if t0 < 0 < t0 + self.duration_s:
            s = self.state_at(now)
            pts.append((s.lat, s.lon, s.altitude_m, 0.0))
            pts.sort(key=lambda p: p[3])
        return [(round(a, 6), round(b, 6), round(h, 1), round(t, 1)) for a, b, h, t in pts]


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
