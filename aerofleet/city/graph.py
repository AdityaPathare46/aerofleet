"""City street graph — real OpenStreetMap data via osmnx, cached to disk.

Drone routes default to following the road network beneath them (mirrors
real-world proposed drone-corridor policy of flying above existing
right-of-way rather than over private property). Falls back to a small
synthetic grid if osmnx or network access is unavailable, so the rest of
the system still runs fully offline.
"""
from __future__ import annotations

import logging
import math
import os
import random
from pathlib import Path
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)


class CityGraph:
    def __init__(
        self,
        city_name: str = "Pune, Maharashtra, India",
        cache_dir: Optional[str] = None,
        radius_m: float = 4000.0,
    ):
        """
        Args:
            city_name: geocoded to a centre point (fast, single lookup) —
                the graph is NOT fetched for the whole city/metro area.
            radius_m: fetch only the street network within this radius of
                the centre point. Realistic drone delivery range is a few
                km, and a whole-metro `graph_from_place` fetch for a large
                city can take many minutes (or hang) against the public
                Overpass API — bounding the query keeps this fast and
                reliable while still using real OSM data.
        """
        self.city_name = city_name
        self.radius_m = radius_m
        self.cache_dir = Path(cache_dir or os.environ.get("CITY_GRAPH_CACHE_PATH", "data/city_cache"))
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._graph = None
        self.is_synthetic = False

    # ─────────────────────────────────────────────────────────────────
    #  LOADING
    # ─────────────────────────────────────────────────────────────────

    def load(self):
        if self._graph is not None:
            return self._graph

        cache_file = self.cache_dir / f"{self._slug(self.city_name)}_{int(self.radius_m)}m.graphml"
        try:
            import osmnx as ox

            if cache_file.exists():
                logger.info(f"Loading cached city graph: {cache_file}")
                self._graph = ox.load_graphml(cache_file)
            else:
                logger.info(
                    f"Geocoding '{self.city_name}' and fetching a {self.radius_m:.0f}m-radius "
                    "street graph (bounded, not the whole city) ..."
                )
                center_lat, center_lon = ox.geocode(self.city_name)
                self._graph = ox.graph_from_point(
                    (center_lat, center_lon), dist=self.radius_m, network_type="drive"
                )
                ox.save_graphml(self._graph, cache_file)
                logger.info(f"Cached city graph to {cache_file}")
        except Exception as exc:
            logger.warning(
                f"OSM graph unavailable for '{self.city_name}' ({exc}); "
                "falling back to a synthetic grid city."
            )
            self._graph = self._build_synthetic_grid()
            self.is_synthetic = True

        return self._graph

    # ─────────────────────────────────────────────────────────────────
    #  ROUTING
    # ─────────────────────────────────────────────────────────────────

    def shortest_path(self, orig_node: int, dest_node: int) -> List[int]:
        import networkx as nx

        g = self.load()
        return nx.shortest_path(g, orig_node, dest_node, weight="length")

    @staticmethod
    def edge_attrs(data: Optional[dict]) -> dict:
        """Extract real edge attributes from whatever `g.get_edge_data(u, v)`
        (or a networkx weight-callable's own edge-data argument) returns.
        MultiDiGraph.get_edge_data (real OSM data) returns
        {parallel_edge_key: {attrs}}; plain Graph.get_edge_data (the
        offline synthetic-grid fallback) returns {attrs} directly. Handle
        both rather than assuming the OSM shape unconditionally — the
        fallback graph used to crash here. Shared by path_length_km below
        and aerofleet/city/route_weights.py's zone/energy-aware weighting,
        so there's exactly one place that knows this shape duality."""
        if not data:
            return {}
        first_value = next(iter(data.values()))
        return first_value if isinstance(first_value, dict) else data

    def path_length_km(self, path: List[int]) -> float:
        g = self.load()
        total_m = 0.0
        for u, v in zip(path[:-1], path[1:]):
            edge = self.edge_attrs(g.get_edge_data(u, v))
            total_m += edge.get("length", 0.0)
        return total_m / 1000.0

    def route_distance_km(self, orig_node: int, dest_node: int) -> float:
        if orig_node == dest_node:
            return 0.0
        path = self.shortest_path(orig_node, dest_node)
        return self.path_length_km(path)

    def node_lat_lon(self, node: int) -> Tuple[float, float]:
        g = self.load()
        data = g.nodes[node]
        return float(data["y"]), float(data["x"])

    def nearest_node(self, lat: float, lon: float) -> int:
        g = self.load()
        if self.is_synthetic:
            best_node, best_dist = None, float("inf")
            for n, data in g.nodes(data=True):
                d = (data["y"] - lat) ** 2 + (data["x"] - lon) ** 2
                if d < best_dist:
                    best_node, best_dist = n, d
            return best_node
        import osmnx as ox

        return ox.distance.nearest_nodes(g, lon, lat)

    def random_node(self, rng: Optional[random.Random] = None) -> int:
        g = self.load()
        nodes = list(g.nodes)
        return (rng or random).choice(nodes)

    def node_count(self) -> int:
        return self.load().number_of_nodes()

    # ─────────────────────────────────────────────────────────────────
    #  SYNTHETIC FALLBACK
    # ─────────────────────────────────────────────────────────────────

    # Minimum diameter (in metres) any synthetic grid will span, even for a
    # city with no restricted sites registered — keeps a reasonably-sized
    # demo area rather than degenerating to a single point.
    MIN_SYNTHETIC_SPAN_M = 3000.0
    # Multiplier past the farthest real restricted-site/safe-zone coordinate
    # from city center, so the grid doesn't just barely graze the site's
    # edge — it comfortably contains it plus some surrounding road network.
    SYNTHETIC_SPAN_MARGIN = 2.4

    def _build_synthetic_grid(self, size: int = 24):
        """Offline fallback city graph. Anchored at the *requested* city's
        real center coordinates (previously hardcoded to Pune regardless of
        which city was being built — a real bug: an offline Mumbai fleet
        was silently placed at Pune's coordinates) and sized to actually
        reach every one of that city's real DGCA restricted sites and safe
        zones (aerofleet/city/restricted_sites.py, Phase AE), not just a
        small patch around downtown — otherwise Red Zone geofence rejection
        can never be exercised through a normal simulated dispatch when
        osmnx/network access is unavailable, only via directly-injected
        test coordinates."""
        import networkx as nx

        from aerofleet.city.registry import CITY_REGISTRY

        cfg = next((c for c in CITY_REGISTRY.values() if c.osm_name == self.city_name), None)
        if cfg is not None:
            base_lat, base_lon = cfg.center
            site_coords = [(s.lat, s.lon) for s in cfg.restricted_sites] + [
                (z.lat, z.lon) for z in cfg.safe_zones
            ]
            max_dist_m = max(
                (self._haversine_m(base_lat, base_lon, lat, lon) for lat, lon in site_coords),
                default=self.MIN_SYNTHETIC_SPAN_M / self.SYNTHETIC_SPAN_MARGIN,
            )
        else:
            logger.warning(
                f"No CITY_REGISTRY entry matches synthetic-grid city_name '{self.city_name}' — "
                "anchoring at Pune's center as a last-resort default."
            )
            base_lat, base_lon = 18.5204, 73.8567
            max_dist_m = self.MIN_SYNTHETIC_SPAN_M / self.SYNTHETIC_SPAN_MARGIN

        span_m = max(max_dist_m * self.SYNTHETIC_SPAN_MARGIN, self.MIN_SYNTHETIC_SPAN_M)
        spacing_m = span_m / size

        g = nx.grid_2d_graph(size, size)
        g = nx.convert_node_labels_to_integers(g)
        for u, v in g.edges:
            g.edges[u, v]["length"] = spacing_m

        # Attach synthetic lat/lon, centered on the city (not just growing
        # from one corner) so real sites north/south/east/west of center
        # all fall within the grid, not only ones in one quadrant.
        deg_per_m_lat = 1.0 / 111_320.0
        deg_per_m_lon = 1.0 / (111_320.0 * max(0.1, math.cos(math.radians(base_lat))))
        half = (size - 1) / 2.0
        for i, (_, data) in enumerate(g.nodes(data=True)):
            row, col = divmod(i, size)
            data["y"] = base_lat + (row - half) * spacing_m * deg_per_m_lat
            data["x"] = base_lon + (col - half) * spacing_m * deg_per_m_lon

        return g

    @staticmethod
    def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        r = 6_371_000.0
        p1, p2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)
        a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
        return 2 * r * math.asin(math.sqrt(a))

    @staticmethod
    def _slug(name: str) -> str:
        return name.lower().replace(",", "").replace(" ", "_")


_default_graph: Optional[CityGraph] = None


def get_city_graph(reload: bool = False) -> CityGraph:
    """Process-wide cached CityGraph for the configured DEMO_CITY."""
    global _default_graph
    if _default_graph is None or reload:
        city_name = os.environ.get("DEMO_CITY", "Pune, Maharashtra, India")
        _default_graph = CityGraph(city_name=city_name)
    return _default_graph
