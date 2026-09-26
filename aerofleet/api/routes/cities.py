"""City registry API endpoint — powers the frontend city selector, plus the
street network used as the VR Safety View's tabletop base map."""

import math
from functools import lru_cache
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException

from aerofleet.city.registry import CITY_REGISTRY

router = APIRouter()

MAJOR_HIGHWAYS = {
    "motorway", "motorway_link", "trunk", "trunk_link", "primary", "primary_link",
    "secondary", "secondary_link", "tertiary", "tertiary_link",
}
METRES_PER_DEG_LAT = 111320.0


@router.get("/")
async def list_cities() -> List[dict]:
    return [
        {
            "slug": cfg.slug,
            "name": cfg.name,
            "center": list(cfg.center),
            "airport_name": cfg.airport_name,
            "bounds_radius_km": cfg.bounds_radius_km,
        }
        for cfg in CITY_REGISTRY.values()
    ]


def _highway_class(value: Any) -> str:
    if isinstance(value, list):
        value = value[0] if value else ""
    return str(value or "")


@lru_cache(maxsize=8)
def _road_network(slug: str) -> Dict[str, Any]:
    from aerofleet.fleet.state import get_fleet_state

    cfg = CITY_REGISTRY[slug]
    center_lat, center_lon = cfg.center
    east_per_deg = METRES_PER_DEG_LAT * math.cos(math.radians(center_lat))

    def local(lat: float, lon: float) -> List[int]:
        return [round((lon - center_lon) * east_per_deg), round((lat - center_lat) * METRES_PER_DEG_LAT)]

    graph_wrapper = get_fleet_state(slug).graph
    g = graph_wrapper.load()
    seen = set()
    major: List[List[int]] = []
    minor: List[List[int]] = []
    edges = g.edges(keys=True, data=True) if g.is_multigraph() else ((u, v, 0, d) for u, v, d in g.edges(data=True))
    for u, v, _key, data in edges:
        undirected = (min(u, v), max(u, v))
        if undirected in seen:
            continue
        seen.add(undirected)
        is_major = _highway_class(data.get("highway")) in MAJOR_HIGHWAYS
        geometry = data.get("geometry")
        if geometry is not None and is_major:
            coords = [(lat, lon) for lon, lat in geometry.coords]
        else:
            coords = [graph_wrapper.node_lat_lon(u), graph_wrapper.node_lat_lon(v)]
        flat: List[int] = []
        for lat, lon in coords:
            flat.extend(local(lat, lon))
        (major if is_major else minor).append(flat)

    return {
        "city": slug,
        "center": [center_lat, center_lon],
        "synthetic": graph_wrapper.is_synthetic,
        "units": "metres east/north of center",
        "major": major,
        "minor": minor,
    }


@router.get("/{slug}/roads")
async def city_roads(slug: str) -> Dict[str, Any]:
    """Street network as compact local-metre polylines (east, north relative
    to the city registry center) — the VR Safety View's tabletop base map.
    Two-way streets are deduplicated; only major roads keep their curved
    geometry, minor streets are straight node-to-node segments. Cached per
    city after the first call."""
    if slug not in CITY_REGISTRY:
        raise HTTPException(status_code=404, detail=f"Unknown city '{slug}'")
    return _road_network(slug)
