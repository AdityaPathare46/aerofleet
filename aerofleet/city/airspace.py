"""DGCA-style airspace zones and altitude-banded corridor allocation.

India's Drone Rules 2021 (Digital Sky) define a Red/Yellow/Green zone map:
Red = no-fly (airports, strategic sites), Yellow = ATC permission required,
Green = free flight below the prescribed ceiling. This module models that
as circular geofences plus a set of altitude bands, which the CBF safety
gate (aerofleet/safety/cbf_gate.py) uses as hard constraints — this is the
"3D layered corridor" novelty described in docs/PATENT_NOVELTY.md, as
opposed to a flat 2D no-fly polygon.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Tuple

from aerofleet.city.restricted_sites import NamedSafeZone, RestrictedSite


class ZoneColor(Enum):
    GREEN = "GREEN"
    YELLOW = "YELLOW"
    RED = "RED"


@dataclass
class AltitudeBand:
    name: str
    floor_m: float
    ceiling_m: float


# DGCA Drone Rules 2021: Green Zone ceiling is 120 m (400 ft) AGL generally,
# reduced to 60 m (200 ft) AGL within the 8-12 km lateral band around an
# active airport (the same band this module models as a YELLOW zone — see
# AirspaceModel.altitude_ceiling_m_at()). AeroFleet keeps its own
# operational ceiling below the legal 120 m limit as a deliberate safety
# margin, the same "reserve below the hard limit" pattern used for battery
# reserve margin elsewhere in this codebase — not a misreading of the rule.
DGCA_LEGAL_CEILING_M = 120.0
DEFAULT_OPERATIONAL_CEILING_M = 100.0
REDUCED_CEILING_NEAR_AIRPORT_M = 60.0

DEFAULT_ALTITUDE_BANDS: List[AltitudeBand] = [
    AltitudeBand("LOW", 0.0, 60.0),
    AltitudeBand("MID", 60.0, 80.0),
    AltitudeBand("HIGH", 80.0, 100.0),
]


@dataclass
class GeofenceZone:
    zone_id: str
    color: ZoneColor
    center_lat: float
    center_lon: float
    radius_m: float
    reason: str = ""


@dataclass
class SafeZone:
    """A pre-mapped open-ground site (park, playground, riverbank) usable
    for an automated emergency landing (fault_tolerance/emergency response)."""

    zone_id: str
    center_lat: float
    center_lon: float
    node: Optional[int] = None
    name: str = ""


class AirspaceModel:
    def __init__(
        self,
        zones: Optional[List[GeofenceZone]] = None,
        altitude_bands: Optional[List[AltitudeBand]] = None,
        safe_zones: Optional[List[SafeZone]] = None,
        operational_ceiling_m: float = DEFAULT_OPERATIONAL_CEILING_M,
    ):
        self.zones = zones or []
        self.altitude_bands = altitude_bands or list(DEFAULT_ALTITUDE_BANDS)
        self.safe_zones = safe_zones or []
        self.operational_ceiling_m = operational_ceiling_m

    def zone_at(self, lat: float, lon: float) -> ZoneColor:
        for z in self.zones:
            if z.color == ZoneColor.RED and self._haversine_m(lat, lon, z.center_lat, z.center_lon) <= z.radius_m:
                return ZoneColor.RED
        for z in self.zones:
            if z.color == ZoneColor.YELLOW and self._haversine_m(lat, lon, z.center_lat, z.center_lon) <= z.radius_m:
                return ZoneColor.YELLOW
        return ZoneColor.GREEN

    def is_no_fly(self, lat: float, lon: float) -> bool:
        return self.zone_at(lat, lon) == ZoneColor.RED

    def distance_to_nearest_red_zone_m(self, lat: float, lon: float) -> float:
        red = [z for z in self.zones if z.color == ZoneColor.RED]
        if not red:
            return float("inf")
        return min(self._haversine_m(lat, lon, z.center_lat, z.center_lon) - z.radius_m for z in red)

    def altitude_ceiling_m_at(self, lat: float, lon: float) -> float:
        """DGCA Green Zone ceiling drops from 120 m (400 ft) to 60 m
        (200 ft) AGL within the 8-12 km lateral band around an active
        airport — modeled here as that location's zone classification
        being YELLOW (see build_airspace_from_sites(), which builds the
        Yellow ring at exactly that 12 km radius). A RED-zone point has no
        legal ceiling at all (flight is prohibited outright), so this is
        only meaningful for GREEN/YELLOW callers — dispatch already
        rejects RED-zone destinations via the geofence_exclusion CBF
        constraint before altitude is ever relevant."""
        if self.zone_at(lat, lon) == ZoneColor.YELLOW:
            return REDUCED_CEILING_NEAR_AIRPORT_M
        return self.operational_ceiling_m

    def assign_altitude_band(
        self, priority: str = "STANDARD", lat: Optional[float] = None, lon: Optional[float] = None
    ) -> AltitudeBand:
        """Priority routing across altitude bands doubles as basic
        deconfliction: MEDICAL flights get the clearest (highest) lane —
        demoted to the highest band that still fits under the local
        ceiling when lat/lon are given, so a MEDICAL delivery near an
        airport doesn't get assigned a band the CBF gate would then
        reject for exceeding the reduced 60 m ceiling there."""
        if priority == "MEDICAL" and len(self.altitude_bands) >= 3:
            preferred_idx = 2
        elif priority == "EXPRESS" and len(self.altitude_bands) >= 2:
            preferred_idx = 1
        else:
            preferred_idx = 0

        if lat is None or lon is None:
            return self.altitude_bands[preferred_idx]

        ceiling = self.altitude_ceiling_m_at(lat, lon)
        for idx in range(preferred_idx, -1, -1):
            if self.altitude_bands[idx].ceiling_m <= ceiling:
                return self.altitude_bands[idx]
        return self.altitude_bands[0]

    def nearest_safe_zone(self, lat: float, lon: float) -> Optional[SafeZone]:
        if not self.safe_zones:
            return None
        return min(self.safe_zones, key=lambda s: self._haversine_m(lat, lon, s.center_lat, s.center_lon))

    @staticmethod
    def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        R = 6371000.0
        p1, p2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlmb = math.radians(lon2 - lon1)
        a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
        return 2 * R * math.asin(math.sqrt(a))


def build_default_airspace(
    city_center: Tuple[float, float] = (18.5204, 73.8567),
    airport: Optional[Tuple[float, float]] = None,
    airport_name: str = "Airport ATZ",
) -> AirspaceModel:
    """Fallback airspace for any city not covered by
    aerofleet/city/restricted_sites.py's curated real-site lists (Pune and
    Mumbai use build_airspace_from_sites() instead — see fleet/state.py).
    Models a single real airport's Red Zone (5 km) and its Yellow lateral
    band (12 km) per DGCA Drone Rules 2021, plus a few generic open-ground
    safe-zone offsets since no curated site list exists for this city."""
    lat, lon = city_center
    a_lat, a_lon = airport if airport is not None else (lat + 0.06, lon + 0.06)
    zones = [
        GeofenceZone("RED-AIRPORT", ZoneColor.RED, a_lat, a_lon, AIRPORT_RED_RADIUS_M,
                     f"{airport_name} — DGCA Red Zone (5 km), no UAS operations"),
        GeofenceZone("YELLOW-AIRPORT", ZoneColor.YELLOW, a_lat, a_lon, AIRPORT_YELLOW_RADIUS_M,
                     f"{airport_name} — DGCA Yellow Zone (12 km lateral band), ATC permission required"),
    ]
    safe_zones = [
        SafeZone("SAFE-PARK-1", lat + 0.01, lon - 0.01, name="Open ground / park (north-west)"),
        SafeZone("SAFE-PARK-2", lat - 0.015, lon + 0.02, name="Open ground / park (south-east)"),
        SafeZone("SAFE-RIVERBANK", lat + 0.02, lon + 0.005, name="Riverbank open ground"),
    ]
    return AirspaceModel(zones=zones, safe_zones=safe_zones)


def build_airspace_from_sites(
    sites: List[RestrictedSite],
    safe_zones: Optional[List[NamedSafeZone]] = None,
    operational_ceiling_m: float = DEFAULT_OPERATIONAL_CEILING_M,
) -> AirspaceModel:
    """Build a city's real airspace model from a curated list of actual,
    named, publicly-known restricted sites (aerofleet/city/restricted_sites
    .py) instead of a single generic airport circle. Each AIRPORT-category
    site gets a Red disc plus a Yellow lateral ring at its own radius (the
    two circles combine into a ring via zone_at()'s "check RED first, then
    YELLOW" ordering — a point inside the smaller Red radius reports RED
    even though it's also inside the larger Yellow circle). MILITARY and
    STRATEGIC sites get a Red disc only, matching DGCA's rule text, which
    doesn't describe an equivalent permission-buffer ring around them."""

    def _slug(name: str) -> str:
        return re.sub(r"[^A-Z0-9]+", "-", name.upper()).strip("-")

    zones: List[GeofenceZone] = []
    for site in sites:
        zones.append(GeofenceZone(
            zone_id=f"RED-{_slug(site.name)}",
            color=ZoneColor.RED,
            center_lat=site.lat, center_lon=site.lon,
            radius_m=site.red_radius_m,
            reason=f"{site.name} — DGCA Red Zone ({site.category.value.title()}). {site.source_note}",
        ))
        if site.yellow_radius_m:
            zones.append(GeofenceZone(
                zone_id=f"YELLOW-{_slug(site.name)}",
                color=ZoneColor.YELLOW,
                center_lat=site.lat, center_lon=site.lon,
                radius_m=site.yellow_radius_m,
                reason=f"{site.name} — DGCA Yellow Zone (lateral band), ATC permission required.",
            ))

    resolved_safe_zones = [
        SafeZone(zone_id=f"SAFE-{re.sub(r'[^A-Z0-9]+', '-', sz.name.upper()).strip('-')}",
                 center_lat=sz.lat, center_lon=sz.lon, name=sz.name)
        for sz in (safe_zones or [])
    ]

    return AirspaceModel(zones=zones, safe_zones=resolved_safe_zones, operational_ceiling_m=operational_ceiling_m)
