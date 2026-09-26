"""OSM building footprints for the VR tabletop — height provenance and projection."""
import math

import pytest
from shapely.geometry import MultiPolygon, Polygon

from aerofleet.city import buildings as b

pytestmark = pytest.mark.unit

CENTER = (18.5204, 73.8567)
EAST_PER_DEG = b.METRES_PER_DEG_LAT * math.cos(math.radians(CENTER[0]))


def _square(east_m: float, north_m: float, side_m: float) -> Polygon:
    """A lon/lat square whose south-west corner is east_m/north_m from CENTER."""
    lat0, lon0 = CENTER
    def ll(e, n):
        return (lon0 + e / EAST_PER_DEG, lat0 + n / b.METRES_PER_DEG_LAT)
    return Polygon([ll(east_m, north_m), ll(east_m + side_m, north_m),
                    ll(east_m + side_m, north_m + side_m), ll(east_m, north_m + side_m)])


class TestBuildingHeight:
    def test_height_tag_wins_and_is_marked_measured(self):
        assert b.building_height({"height": "42 m", "building:levels": "3"}) == (42.0, b.SOURCE_HEIGHT)

    def test_feet_are_converted(self):
        h, src = b.building_height({"height": "100 ft"})
        assert src == b.SOURCE_HEIGHT and h == pytest.approx(30.48)

    def test_levels_used_when_no_height(self):
        assert b.building_height({"building:levels": "10"}) == (10 * b.LEVEL_HEIGHT_M, b.SOURCE_LEVELS)

    def test_untagged_building_is_assumed_not_invented(self):
        assert b.building_height({}) == (b.ASSUMED_HEIGHT_M, b.SOURCE_ASSUMED)

    def test_implausible_height_falls_through(self):
        # "1200" is almost always a typo for 120 m — don't draw a 1.2 km tower
        assert b.building_height({"height": "1200"})[1] == b.SOURCE_ASSUMED


class TestCompactBuildings:
    def test_projects_to_local_metres_with_height_in_decimetres(self):
        data = b.compact_buildings([(_square(100, 200, 20), {"building:levels": "5"})], CENTER)
        (row,) = data["buildings"]
        height_dm, source_idx, *coords = row
        assert height_dm == round(5 * b.LEVEL_HEIGHT_M * 10)
        assert data["sources"][source_idx] == b.SOURCE_LEVELS
        easts, norths = coords[0::2], coords[1::2]
        assert min(easts) == 100 and max(easts) == 120
        assert min(norths) == 200 and max(norths) == 220
        assert len(coords) == 8  # closing vertex dropped

    def test_tiny_footprints_are_dropped_and_multipolygons_split(self):
        multi = MultiPolygon([_square(0, 0, 10), _square(50, 50, 10)])
        data = b.compact_buildings([(_square(0, 0, 2), {}), (multi, {})], CENTER)
        assert len(data["buildings"]) == 2
        assert data["height_sources"] == {b.SOURCE_HEIGHT: 0, b.SOURCE_LEVELS: 0, b.SOURCE_ASSUMED: 2}


class TestLoadBuildings:
    def test_no_cache_and_no_fetch_is_an_empty_unavailable_set(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CITY_GRAPH_CACHE_PATH", str(tmp_path))
        data = b.load_buildings("nowhere", CENTER, fetch=False)
        assert data["available"] is False and data["buildings"] == []
