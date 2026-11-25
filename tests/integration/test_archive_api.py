"""Other controllers' logs over the API, and the public-archive search."""
from pathlib import Path

import pytest

from tests.unit.test_archive_search import index  # noqa: F401  (fixture)

pytestmark = pytest.mark.integration
URL = "/api/v1/assurance"
TEMPLATE = Path(__file__).resolve().parents[2] / "tauri-app" / "public" / "templates" / "aerofleet_flight_template.csv"


def test_a_csv_export_is_reviewed_like_any_log_and_says_what_it_lacks(api_client, auth_headers):
    files = {"log": ("agri.csv", TEMPLATE.read_bytes(), "text/csv")}
    r = api_client.post(f"{URL}/fleets/other-fc/drones/AG-1/flights", headers=auth_headers, files=files)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["verdict"] == "LOG_ONLY" and body["report"]["log"]["format"] == "csv"
    assert body["report"]["vibration"] is None and any("no settings" in n for n in body["report"]["log"]["notes"])
    bad = api_client.post(f"{URL}/fleets/other-fc/drones/AG-1/flights", headers=auth_headers,
                          files={"log": ("x.csv", b"a,b\n1,2\n", "text/csv")})
    assert bad.status_code == 422 and "latitude" in bad.json()["detail"]


def test_the_archive_search_takes_words_or_one_of_my_flights(api_client, auth_headers, index):  # noqa: F811
    assert api_client.get(f"{URL}/archive/status", headers=auth_headers).json()["ready"] is True
    out = api_client.post(f"{URL}/archive/search", headers=auth_headers, json={"description": "compass interference, toilet bowl"}).json()
    assert out["text_matches"][0]["id"] == "r1" and out["log_matches"] == []          # words never match logs (test A1)
    rid = api_client.post(f"{URL}/fleets/other-fc/drones/AG-2/flights", headers=auth_headers,
                          files={"log": ("agri.csv", TEMPLATE.read_bytes(), "text/csv")}).json()["id"]
    mine = api_client.post(f"{URL}/archive/search", headers=auth_headers, json={"review_id": rid, "fleet": "other-fc"}).json()
    assert mine["your_flight"]["review_id"] == rid
    assert api_client.post(f"{URL}/archive/search", headers=auth_headers, json={"description": ""}).status_code == 422
    assert api_client.post(f"{URL}/archive/search", json={"description": "compass"}).status_code == 401
