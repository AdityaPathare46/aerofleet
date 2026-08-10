"""Registry of demo cities — geocodable name, map center, and the real
airport coordinates used to seed each city's DGCA Red Zone.

`restricted_sites`/`safe_zones` (aerofleet/city/restricted_sites.py) carry
each city's curated list of real, named restricted sites and open-ground
safe zones; fleet/state.py uses them via
aerofleet.city.airspace.build_airspace_from_sites() when present, falling
back to the single-airport-circle build_default_airspace() for any future
city added here without a curated list.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from aerofleet.city.restricted_sites import (
    MUMBAI_RESTRICTED_SITES,
    MUMBAI_SAFE_ZONES,
    NamedSafeZone,
    PUNE_RESTRICTED_SITES,
    PUNE_SAFE_ZONES,
    RestrictedSite,
)


@dataclass(frozen=True)
class CityConfig:
    slug: str
    name: str
    osm_name: str          # passed to osmnx for geocoding + street graph fetch
    center: tuple          # (lat, lon) — map/UI center
    airport: tuple         # (lat, lon) — real airport, used by the build_default_airspace() fallback
    airport_name: str
    bounds_radius_km: float = 20.0   # map pan/zoom-out limit — keeps the map scoped
                                      # to the city instead of panning to the whole world
    restricted_sites: List[RestrictedSite] = field(default_factory=list)
    safe_zones: List[NamedSafeZone] = field(default_factory=list)


CITY_REGISTRY: Dict[str, CityConfig] = {
    "pune": CityConfig(
        slug="pune",
        name="Pune",
        osm_name="Pune, Maharashtra, India",
        center=(18.5204, 73.8567),
        airport=(18.5822, 73.9197),
        airport_name="Pune Airport (Lohegaon)",
        bounds_radius_km=20.0,
        restricted_sites=PUNE_RESTRICTED_SITES,
        safe_zones=PUNE_SAFE_ZONES,
    ),
    "mumbai": CityConfig(
        slug="mumbai",
        name="Mumbai",
        osm_name="Mumbai, Maharashtra, India",
        center=(19.0760, 72.8777),
        airport=(19.0896, 72.8656),
        airport_name="Chhatrapati Shivaji Maharaj International Airport",
        bounds_radius_km=20.0,
        restricted_sites=MUMBAI_RESTRICTED_SITES,
        safe_zones=MUMBAI_SAFE_ZONES,
    ),
}

DEFAULT_CITY = "pune"


def get_city_config(slug: str) -> CityConfig:
    cfg = CITY_REGISTRY.get(slug.lower())
    if cfg is None:
        raise KeyError(f"Unknown city '{slug}'. Available: {list(CITY_REGISTRY)}")
    return cfg
