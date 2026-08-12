"""Unit tests for aerofleet/city/graph.py's offline synthetic-grid fallback
(Phase AK). Before this phase, _build_synthetic_grid() was hardcoded to
Pune's coordinates regardless of which city was actually being built (a real
bug: an offline Mumbai fleet was silently placed at Pune's coordinates), and
was too small to reach any city's real DGCA restricted sites — meaning Red
Zone geofence rejection (aerofleet/city/restricted_sites.py, Phase AE) could
never be exercised through a normal simulated dispatch when osmnx/network
access is unavailable.
"""
import pytest

from aerofleet.city.graph import CityGraph
from aerofleet.city.registry import CITY_REGISTRY, get_city_config

pytestmark = pytest.mark.unit


def _force_synthetic(graph: CityGraph):
    """Deterministically exercises the synthetic-grid fallback regardless of
    whether osmnx/network access happens to be available in this environment
    — earlier versions of this helper relied on load() failing naturally
    (true when osmnx wasn't installed), which made these tests flaky against
    an environment where osmnx became available and real OSM/Overpass
    access started succeeding. Building the synthetic grid directly, the
    same way load()'s except branch does, tests the fallback itself without
    depending on a real network call succeeding or failing."""
    graph._graph = graph._build_synthetic_grid()
    graph.is_synthetic = True
    return graph


class TestPerCityAnchoring:
    @pytest.mark.parametrize("slug", list(CITY_REGISTRY.keys()))
    def test_synthetic_grid_anchors_at_the_requested_citys_own_center(self, slug):
        cfg = get_city_config(slug)
        graph = _force_synthetic(CityGraph(city_name=cfg.osm_name, radius_m=4000.0))

        lats = [graph._graph.nodes[n]["y"] for n in graph._graph.nodes]
        lons = [graph._graph.nodes[n]["x"] for n in graph._graph.nodes]
        center_lat, center_lon = cfg.center

        # The grid's own centroid should land close to the city's real
        # center — not another city's coordinates.
        mid_lat = (min(lats) + max(lats)) / 2
        mid_lon = (min(lons) + max(lons)) / 2
        assert abs(mid_lat - center_lat) < 0.01
        assert abs(mid_lon - center_lon) < 0.01

    def test_mumbai_is_not_silently_placed_at_pune(self):
        """The regression this phase fixes: before, EVERY city's synthetic
        grid used Pune's hardcoded base_lat/base_lon."""
        mumbai_cfg = get_city_config("mumbai")
        graph = _force_synthetic(CityGraph(city_name=mumbai_cfg.osm_name, radius_m=4000.0))

        lats = [graph._graph.nodes[n]["y"] for n in graph._graph.nodes]
        pune_lat = 18.5204
        mumbai_lat = mumbai_cfg.center[0]
        # Every node should be much closer to Mumbai's real latitude than
        # to Pune's.
        for lat in lats:
            assert abs(lat - mumbai_lat) < abs(lat - pune_lat)


class TestReachesRealRestrictedSites:
    @pytest.mark.parametrize("slug", list(CITY_REGISTRY.keys()))
    def test_every_restricted_site_and_safe_zone_falls_within_the_grid(self, slug):
        cfg = get_city_config(slug)
        graph = _force_synthetic(CityGraph(city_name=cfg.osm_name, radius_m=4000.0))

        lats = [graph._graph.nodes[n]["y"] for n in graph._graph.nodes]
        lons = [graph._graph.nodes[n]["x"] for n in graph._graph.nodes]
        lat_range, lon_range = (min(lats), max(lats)), (min(lons), max(lons))

        for site in cfg.restricted_sites:
            assert lat_range[0] <= site.lat <= lat_range[1], f"{site.name} lat outside synthetic grid"
            assert lon_range[0] <= site.lon <= lon_range[1], f"{site.name} lon outside synthetic grid"
        for zone in cfg.safe_zones:
            assert lat_range[0] <= zone.lat <= lat_range[1], f"{zone.name} lat outside synthetic grid"
            assert lon_range[0] <= zone.lon <= lon_range[1], f"{zone.name} lon outside synthetic grid"

    def test_a_real_graph_node_near_the_airport_is_flagged_no_fly(self):
        """End-to-end: nearest_node() -> node_lat_lon() -> is_no_fly() must
        actually chain together correctly through the synthetic graph, not
        just have the raw coordinate happen to fall in the bounding box."""
        from aerofleet.fleet.state import get_fleet_state

        fleet = get_fleet_state("pune", reload=True)
        node = fleet.graph.nearest_node(*fleet.city_config.airport)
        lat, lon = fleet.graph.node_lat_lon(node)
        assert fleet.airspace.is_no_fly(lat, lon)


class TestUnknownCityFallsBackSafely:
    def test_unrecognized_city_name_still_produces_a_usable_grid(self):
        graph = _force_synthetic(CityGraph(city_name="Nowhereville, Atlantis", radius_m=4000.0))
        assert graph.node_count() > 0
        lat, lon = graph.node_lat_lon(next(iter(graph._graph.nodes)))
        assert lat is not None and lon is not None
