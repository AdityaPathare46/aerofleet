"""AeroFleet 2.0 default: commands that start or move a real aircraft are refused; safing is not."""
import pytest

pytestmark = pytest.mark.integration


@pytest.fixture
def live_off(monkeypatch):
    monkeypatch.setenv("AEROFLEET_LIVE_CONTROL", "off")


def test_default_is_off_when_the_setting_is_absent(monkeypatch):
    from aerofleet.assurance.live_control import live_control_enabled

    monkeypatch.delenv("AEROFLEET_LIVE_CONTROL", raising=False)
    assert live_control_enabled() is False
    for value, expected in (("on", True), ("1", True), ("TRUE", True), ("off", False), ("", False), ("maybe", False)):
        monkeypatch.setenv("AEROFLEET_LIVE_CONTROL", value)
        assert live_control_enabled() is expected, value


def test_policy_endpoint_says_what_the_install_does(api_client, auth_headers, live_off):
    p = api_client.get("/api/v1/assurance/policy", headers=auth_headers).json()
    assert p["live_control"] is False and "does not command real aircraft" in p["summary"] and "arm" in p["blocked_when_off"]


def test_arm_and_motor_test_are_refused_with_the_reason(api_client, operator_headers, live_off):
    arm = api_client.post("/api/v1/hardware/vehicles/ANY-D1/arm", headers=operator_headers)
    assert arm.status_code == 403 and "switched off" in arm.json()["detail"]
    body = {"motor": "A", "throttle_pct": 5, "duration_s": 1, "props_removed_confirmed": True}
    motor = api_client.post("/api/v1/hardware/fc/inspections/FCI-NOPE/motor-test", headers=operator_headers, json=body)
    assert motor.status_code == 403 and "switched off" in motor.json()["detail"]


def test_safing_commands_are_never_blocked_by_the_switch(api_client, operator_headers, live_off):
    disarm = api_client.post("/api/v1/hardware/vehicles/ANY-D1/disarm", headers=operator_headers)
    assert disarm.status_code == 404                     # no such live vehicle - but not refused by the switch
    stop = api_client.post("/api/v1/hardware/emergency-stop-all", headers=operator_headers)
    assert stop.status_code != 403


def test_with_the_switch_on_arm_reaches_the_normal_checks(api_client, operator_headers, monkeypatch):
    monkeypatch.setenv("AEROFLEET_LIVE_CONTROL", "on")
    assert api_client.post("/api/v1/hardware/vehicles/ANY-D1/arm", headers=operator_headers).status_code == 404


def test_dispatch_never_selects_a_live_drone_while_off(api_client, auth_headers, live_off):
    from aerofleet.fleet.state import get_fleet_state

    fleet = get_fleet_state("pune")
    saved = {d.drone_id: d.link_mode for d in fleet.list_drones()}
    depot = api_client.get("/api/v1/fleet/depots?city=pune").json()[0]
    order = api_client.post("/api/v1/orders/", headers=auth_headers, json={
        "city": "pune", "origin_depot_id": depot["depot_id"], "destination_lat": depot["lat"] + 0.004,
        "destination_lon": depot["lon"] + 0.004, "payload_kg": 1.0, "priority": "STANDARD"}).json()
    try:
        for d in fleet.list_drones():
            d.link_mode = "LIVE"
        r = api_client.post(f"/api/v1/orders/{order['order_id']}/dispatch", headers=auth_headers)
        assert r.status_code == 409 and "No feasible drone" in r.json()["detail"]
    finally:
        for d in fleet.list_drones():
            d.link_mode = saved.get(d.drone_id, "SIMULATED")
