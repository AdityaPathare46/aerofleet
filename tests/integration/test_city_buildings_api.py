"""Integration tests for GET /api/v1/cities/{slug}/buildings — the VR tabletop's 3D city layer."""
import pytest

from aerofleet.api.routes import cities

pytestmark = pytest.mark.integration


@pytest.fixture
def fake_buildings(monkeypatch):
    """No network in tests: serve a fixed two-building set through the real endpoint."""
    def fake_load(slug, center, fetch=True):
        return {"available": True, "sources": ["osm_height", "osm_levels", "assumed"],
                "height_sources": {"osm_height": 1, "osm_levels": 0, "assumed": 1},
                "attribution": "© OpenStreetMap contributors, ODbL",
                "buildings": [[420, 0, 0, 0, 20, 0, 20, 20, 0, 20], [90, 2, 100, 100, 110, 100, 110, 110]]}
    monkeypatch.setattr(cities, "load_buildings", fake_load)
    cities._buildings.cache_clear()
    yield
    cities._buildings.cache_clear()


def test_returns_compact_buildings_with_height_provenance(api_client, fake_buildings):
    r = api_client.get("/api/v1/cities/pune/buildings")
    assert r.status_code == 200
    body = r.json()
    assert body["available"] is True and body["count"] == 2
    assert body["height_sources"]["assumed"] == 1
    assert body["assumed_height_m"] == 9.0
    assert body["buildings"][0][:2] == [420, 0]
    assert "OpenStreetMap" in body["attribution"]


def test_unknown_city_is_404(api_client, fake_buildings):
    assert api_client.get("/api/v1/cities/atlantis/buildings").status_code == 404
