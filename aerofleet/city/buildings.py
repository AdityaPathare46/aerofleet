"""Real building footprints and heights for the VR tabletop (OpenStreetMap).

Buildings are what turn the tabletop from a street diagram into the actual
city: an operator can see a drone's cruise altitude against the towers it
flies over. Footprints come from OSM via osmnx (the same source as the street
graph), fetched once per city within the same bounded radius and cached as a
compact JSON next to the graphml.

Heights are only as good as the tags. Each building records where its height
came from — an OSM `height` tag, `building:levels` × LEVEL_HEIGHT_M, or the
ASSUMED_HEIGHT_M default when neither is tagged — and the endpoint reports
the split, so the viewer can say how much of the skyline is measured.

Data © OpenStreetMap contributors, ODbL.
"""
from __future__ import annotations

import json
import math
import os
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from aerofleet.utils.logging import get_logger

logger = get_logger(__name__)

METRES_PER_DEG_LAT = 111320.0
RADIUS_M = 4000                 # same bounded radius as the street graph
LEVEL_HEIGHT_M = 3.2            # typical storey height incl. slab
ASSUMED_HEIGHT_M = 9.0          # untagged building: ~3 storeys, the common Indian urban low-rise
MIN_AREA_M2 = 12.0              # sheds / mapping slivers aren't worth a prism on a 1:5700 table
SIMPLIFY_M = 0.8                # footprint simplification tolerance (sub-pixel at table scale)
MAX_HEIGHT_M = 350.0            # guards against unit typos ("1200" for 120 m) in OSM tags
CACHE_VERSION = 1

SOURCE_HEIGHT, SOURCE_LEVELS, SOURCE_ASSUMED = "osm_height", "osm_levels", "assumed"


def _first_number(value: Any) -> Optional[float]:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    m = re.search(r"\d+(?:\.\d+)?", str(value))
    return float(m.group()) if m else None


def building_height(tags: Dict[str, Any]) -> Tuple[float, str]:
    """(height in metres, source) from OSM tags."""
    h = _first_number(tags.get("height"))
    if h is not None and 2.0 <= h <= MAX_HEIGHT_M:
        if "ft" in str(tags.get("height")).lower():
            h *= 0.3048
        return h, SOURCE_HEIGHT
    levels = _first_number(tags.get("building:levels"))
    if levels is not None and 1 <= levels <= 120:
        return levels * LEVEL_HEIGHT_M, SOURCE_LEVELS
    return ASSUMED_HEIGHT_M, SOURCE_ASSUMED


def compact_buildings(features: Iterable[Tuple[Any, Dict[str, Any]]], center: Tuple[float, float]) -> Dict[str, Any]:
    """Project footprints to integer metres east/north of `center`.

    `features` yields (shapely geometry in lon/lat, tag dict). Returns
    {"buildings": [[height_dm, source_idx, e1, n1, e2, n2, ...], ...], "sources": {...}}
    — one exterior ring per polygon part, holes dropped, closing vertex dropped.
    """
    from shapely.geometry import MultiPolygon, Polygon
    from shapely.ops import transform

    lat0, lon0 = center
    east_per_deg = METRES_PER_DEG_LAT * math.cos(math.radians(lat0))

    def to_local(x, y, z=None):
        return (x - lon0) * east_per_deg, (y - lat0) * METRES_PER_DEG_LAT

    source_names = [SOURCE_HEIGHT, SOURCE_LEVELS, SOURCE_ASSUMED]
    counts = {s: 0 for s in source_names}
    out: List[List[int]] = []
    for geom, tags in features:
        if geom is None or geom.is_empty:
            continue
        parts = [geom] if isinstance(geom, Polygon) else list(geom.geoms) if isinstance(geom, MultiPolygon) else []
        if not parts:
            continue
        height, source = building_height(tags)
        for part in parts:
            local = transform(to_local, part)
            if local.area < MIN_AREA_M2:
                continue
            ring = local.simplify(SIMPLIFY_M, preserve_topology=True).exterior.coords
            pts = list(ring)[:-1]
            if len(pts) < 3:
                continue
            flat = [round(height * 10), source_names.index(source)]
            for e, n in pts:
                flat.extend((round(e), round(n)))
            out.append(flat)
            counts[source] += 1
    return {"buildings": out, "sources": source_names, "height_sources": counts}


def _cache_file(slug: str) -> Path:
    cache_dir = Path(os.environ.get("CITY_GRAPH_CACHE_PATH", "data/city_cache"))
    return cache_dir / f"{slug}_buildings_{RADIUS_M}m.json"


def load_buildings(slug: str, center: Tuple[float, float], fetch: bool = True) -> Dict[str, Any]:
    """Cached compact buildings for a city; fetches from OSM on first use.

    Never raises: with no cache and no network the result is an empty set
    marked `available: False`, and the tabletop simply shows streets only."""
    path = _cache_file(slug)
    if path.exists():
        data = json.loads(path.read_text())
        if data.get("version") == CACHE_VERSION:
            return data
    empty = {"version": CACHE_VERSION, "available": False, "buildings": [], "sources": [],
             "height_sources": {}, "radius_m": RADIUS_M}
    if not fetch:
        return empty
    try:
        import osmnx as ox

        logger.info(f"Fetching OSM building footprints within {RADIUS_M} m of {slug} ...")
        gdf = ox.features_from_point(center, tags={"building": True}, dist=RADIUS_M)
        tag_cols = [c for c in ("height", "building:levels") if c in gdf.columns]
        rows = ((geom, {c: row[c] for c in tag_cols}) for geom, (_, row) in zip(gdf.geometry, gdf.iterrows()))
        data = compact_buildings(rows, center)
        data.update(version=CACHE_VERSION, available=True, radius_m=RADIUS_M,
                    attribution="© OpenStreetMap contributors, ODbL")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, separators=(",", ":")))
        logger.info(f"Cached {len(data['buildings'])} buildings to {path}")
        return data
    except Exception as exc:
        logger.warning(f"OSM buildings unavailable for {slug} ({exc}); tabletop will show streets only")
        return empty
