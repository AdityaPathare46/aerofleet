"""Desktop ↔ headset pairing through the real LAN gateway (in-process, no sockets)."""
import httpx
import pytest
from fastapi.testclient import TestClient

from aerofleet.vr.gateway import build_gateway_app
from aerofleet.vr.sessions import get_registry

pytestmark = pytest.mark.integration


@pytest.fixture
def gateway(api_client):
    from aerofleet.api.app import app

    reg = get_registry()
    reg._session = None
    with TestClient(build_gateway_app(reg, httpx.ASGITransport(app=app), "http://upstream")) as gw:
        yield gw
    reg._session = None


def _pair(api_client, auth_headers, gateway):
    assert api_client.post("/api/v1/vr/session", headers=auth_headers).status_code == 200
    req = gateway.post("/api/v1/vr/pair-requests", json={"device_name": "Quest 3"}).json()
    pending = api_client.get("/api/v1/vr/session", headers=auth_headers).json()["pending_requests"]
    assert [(p["request_id"], p["confirm_code"]) for p in pending] == [(req["request_id"], req["confirm_code"])]
    r = api_client.post(f"/api/v1/vr/session/requests/{req['request_id']}/approve", headers=auth_headers)
    assert r.status_code == 200
    polled = gateway.get(f"/api/v1/vr/pair-requests/{req['request_id']}").json()
    assert polled["status"] == "APPROVED"
    return {"Authorization": f"Bearer {polled['token']}"}


def test_hello_is_public_and_says_whether_a_session_is_open(api_client, auth_headers, gateway):
    assert gateway.get("/api/v1/vr/hello").json()["session_open"] is False
    api_client.post("/api/v1/vr/session", headers=auth_headers)
    assert gateway.get("/api/v1/vr/hello").json()["session_open"] is True


def test_pairing_without_an_open_session_is_refused(gateway):
    assert gateway.post("/api/v1/vr/pair-requests", json={"device_name": "Quest 3"}).status_code == 409


def test_paired_headset_follows_the_desktop_scenario(api_client, auth_headers, gateway):
    vr = _pair(api_client, auth_headers, gateway)
    scenario = {"city": "mumbai", "mode": "replay", "incident_id": "INC-12345678", "selected_drone": None,
                "range_km": 2, "detail_all": True, "show_buildings": False}
    v = api_client.put("/api/v1/vr/session/scenario", headers=auth_headers, json=scenario).json()["scenario_version"]
    got = gateway.get("/api/v1/vr/device/scenario", headers=vr).json()
    assert got["scenario_version"] == v and got["scenario"] == scenario

    gateway.post("/api/v1/vr/device/heartbeat", headers=vr, json={"mode": "replay", "city": "mumbai"})
    device = api_client.get("/api/v1/vr/session", headers=auth_headers).json()["device"]
    assert device["name"] == "Quest 3" and device["online"] and device["status"]["city"] == "mumbai"


def test_paired_headset_can_read_what_the_vr_view_renders(api_client, auth_headers, gateway):
    vr = _pair(api_client, auth_headers, gateway)
    assert gateway.get("/api/v1/safety/live-margins?city=pune", headers=vr).status_code == 200
    assert gateway.get("/api/v1/geofence/zones?city=pune", headers=vr).status_code == 200


def test_gateway_refuses_everything_outside_the_allowlist(api_client, auth_headers, gateway):
    vr = _pair(api_client, auth_headers, gateway)
    assert gateway.delete("/api/v1/orders/ORD-12345678", headers=vr).status_code == 405  # not even routed
    assert gateway.post("/api/v1/orders/ORD-12345678/request-explanation", headers=vr).status_code == 404
    assert gateway.get("/api/v1/admin/users", headers=vr).status_code == 404              # not in the allowlist
    assert gateway.get("/api/v1/hardware/status", headers=vr).status_code == 404


def test_gateway_does_not_accept_login_jwts_or_no_token(api_client, auth_headers, gateway):
    _pair(api_client, auth_headers, gateway)
    assert gateway.get("/api/v1/safety/live-margins?city=pune").status_code == 401
    assert gateway.get("/api/v1/safety/live-margins?city=pune", headers=auth_headers).status_code == 401


def test_closing_the_session_on_the_desktop_cuts_the_headset_off(api_client, auth_headers, gateway):
    vr = _pair(api_client, auth_headers, gateway)
    api_client.delete("/api/v1/vr/session", headers=auth_headers)
    assert gateway.get("/api/v1/vr/device/scenario", headers=vr).status_code == 401
    assert gateway.get("/api/v1/safety/live-margins?city=pune", headers=vr).status_code == 401


def test_local_device_token_for_quest_link(api_client, auth_headers, gateway):
    api_client.post("/api/v1/vr/session", headers=auth_headers)
    body = api_client.post("/api/v1/vr/session/local-device", headers=auth_headers, json={}).json()
    assert body["gateway_url"].startswith("http://127.0.0.1:")
    vr = {"Authorization": f"Bearer {body['token']}"}
    assert gateway.get("/api/v1/vr/device/scenario", headers=vr).status_code == 200


def test_session_endpoints_need_a_login(api_client):
    assert api_client.post("/api/v1/vr/session").status_code == 401
    assert api_client.get("/api/v1/vr/session").status_code == 401


def _order_body(api_client):
    depot = api_client.get("/api/v1/fleet/depots?city=pune").json()[0]
    return {"city": "pune", "origin_depot_id": depot["depot_id"], "destination_lat": depot["lat"] + 0.004,
            "destination_lon": depot["lon"] + 0.004, "payload_kg": 1.0, "priority": "STANDARD"}


def test_headset_cannot_dispatch_until_the_desktop_allows_it(api_client, auth_headers, gateway):
    vr = _pair(api_client, auth_headers, gateway)
    assert gateway.get("/api/v1/vr/device/scenario", headers=vr).json()["allow_dispatch"] is False
    r = gateway.post("/api/v1/orders/", headers=vr, json=_order_body(api_client))
    assert r.status_code == 403 and "Allow the headset to dispatch" in r.json()["detail"]

    assert api_client.put("/api/v1/vr/session/permissions", headers=auth_headers,
                          json={"allow_dispatch": True}).json() == {"allow_dispatch": True}
    assert gateway.get("/api/v1/vr/device/scenario", headers=vr).json()["allow_dispatch"] is True
    order = gateway.post("/api/v1/orders/", headers=vr, json=_order_body(api_client))
    assert order.status_code == 201, order.text
    d = gateway.post(f"/api/v1/orders/{order.json()['order_id']}/dispatch", headers=vr)
    assert d.status_code in (200, 409), d.text   # the CBF gate / fleet decides, not the gateway
    if d.status_code == 200:
        assert d.json()["verdict"] in ("APPROVED", "REJECTED") or d.json()["verdict"].startswith("FAILED")

    # revoking works immediately
    api_client.put("/api/v1/vr/session/permissions", headers=auth_headers, json={"allow_dispatch": False})
    assert gateway.post("/api/v1/orders/", headers=vr, json=_order_body(api_client)).status_code == 403


def test_a_new_session_starts_without_dispatch_permission(api_client, auth_headers, gateway):
    _pair(api_client, auth_headers, gateway)
    api_client.put("/api/v1/vr/session/permissions", headers=auth_headers, json={"allow_dispatch": True})
    api_client.delete("/api/v1/vr/session", headers=auth_headers)
    assert api_client.post("/api/v1/vr/session", headers=auth_headers).json()["allow_dispatch"] is False


def test_vr_dispatch_never_picks_a_live_hardware_drone(api_client, auth_headers, gateway):
    from aerofleet.fleet.state import get_fleet_state

    vr = _pair(api_client, auth_headers, gateway)
    api_client.put("/api/v1/vr/session/permissions", headers=auth_headers, json={"allow_dispatch": True})
    fleet = get_fleet_state("pune")
    saved = {d.drone_id: d.link_mode for d in fleet.list_drones()}
    try:
        for d in fleet.list_drones():
            d.link_mode = "LIVE"
        order = gateway.post("/api/v1/orders/", headers=vr, json=_order_body(api_client)).json()
        r = gateway.post(f"/api/v1/orders/{order['order_id']}/dispatch", headers=vr)
        assert r.status_code == 409 and "No feasible drone" in r.json()["detail"]
    finally:
        for d in fleet.list_drones():
            d.link_mode = saved.get(d.drone_id, "SIMULATED")
