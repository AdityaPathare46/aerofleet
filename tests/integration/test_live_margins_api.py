"""Integration tests for GET /api/v1/safety/live-margins — the feed behind
the VR Safety View's swarm display."""
import pytest

from aerofleet.fleet import flight_progress
from aerofleet.fleet.models import DroneState
from aerofleet.fleet.state import get_fleet_state

pytestmark = pytest.mark.integration

URL = "/api/v1/safety/live-margins?city=pune"


def _create_and_dispatch(client, headers):
    fleet = get_fleet_state("pune")
    depot_id = next(iter(fleet.depots))
    dest_lat, dest_lon = fleet.graph.node_lat_lon(fleet.depots[depot_id].node)
    resp = client.post("/api/v1/orders/", headers=headers, json={
        "city": "pune", "origin_depot_id": depot_id,
        "destination_lat": dest_lat + 0.01, "destination_lon": dest_lon + 0.01,
        "payload_kg": 1.0, "priority": "STANDARD", "deadline_minutes": 30,
    })
    assert resp.status_code == 201, resp.text
    order_id = resp.json()["order_id"]
    resp = client.post(f"/api/v1/orders/{order_id}/dispatch", headers=headers)
    assert resp.status_code == 200 and resp.json()["verdict"] == "APPROVED", resp.text
    return resp.json()


def _fly(fleet, drone, order_id, path, altitude_m, started_ago_s=0.0):
    import time

    drone.state = DroneState.EN_ROUTE
    drone.order_id = order_id
    flight_progress.register("pune", drone.drone_id, order_id, path, altitude_m, started_at=time.time() - started_ago_s)


def test_requires_auth(api_client, fresh_fleet_state):
    assert api_client.get(URL).status_code == 401


def test_idle_fleet_still_reports_constants_and_constraint_sources(api_client, auth_headers, fresh_fleet_state):
    body = api_client.get(URL, headers=auth_headers).json()
    assert body["drone_count"] == 0 and body["pairs"] == []
    c = body["constants"]
    assert c["min_separation_m"] == 15.0
    assert c["legal_ceiling_m"] == 120.0
    assert c["operational_ceiling_m"] == 100.0
    src = body["constraint_sources"]
    assert len(src["live"]) + len(src["default"]) == 11
    assert not set(src["live"]) & set(src["default"])


def test_approved_dispatch_flies_along_its_real_route(api_client, auth_headers, fresh_fleet_state):
    dispatched = _create_and_dispatch(api_client, auth_headers)
    drone_id = dispatched["assigned_drone_id"]

    first = api_client.get(URL, headers=auth_headers).json()["drones"][drone_id]
    assert first["position_source"] == "ROUTE_DEAD_RECKONING"
    assert first["state"] == "EN_ROUTE"
    assert len(first["route"]) >= 2
    assert 0.0 <= first["battery_soc_pct"] <= 100.0
    assert first["altitude_m"] <= first["altitude_ceiling_m"]

    flight_progress.get("pune", drone_id).started_at -= 60.0  # 60 s later, ~720 m flown
    later = api_client.get(URL, headers=auth_headers).json()["drones"][drone_id]
    moved_m = flight_progress.haversine_m((first["lat"], first["lon"]), (later["lat"], later["lon"]))
    assert moved_m > 100.0 or later["arrived"]


def test_pairs_carry_horizontal_and_vertical_separation(api_client, auth_headers, fresh_fleet_state):
    fleet = get_fleet_state("pune")
    a, b, far = fleet.list_drones()[:3]
    lat0, lon0 = fleet.graph.node_lat_lon(fleet.depots[next(iter(fleet.depots))].node)
    # a and b ~10 m apart horizontally, stacked 20 m apart vertically — each just past the top
    # of its climb (a drone still on the pad isn't in the airspace and isn't paired).
    def just_cruising(alt):
        return alt / flight_progress.CLIMB_RATE_MPS + 0.5
    _fly(fleet, a, "OA", [(lat0, lon0), (lat0 + 0.05, lon0)], 50.0, started_ago_s=just_cruising(50.0))
    _fly(fleet, b, "OB", [(lat0 + 0.00009, lon0), (lat0 + 0.05, lon0)], 70.0, started_ago_s=just_cruising(70.0))
    _fly(fleet, far, "OC", [(lat0 + 0.2, lon0 + 0.2), (lat0 + 0.3, lon0 + 0.2)], 50.0)

    body = api_client.get(URL, headers=auth_headers).json()
    assert body["drone_count"] == 3
    pair = next(p for p in body["pairs"] if {p["a"], p["b"]} == {a.drone_id, b.drone_id})
    assert pair["horizontal_m"] == pytest.approx(10.0, abs=1.0)
    assert pair["vertical_m"] == pytest.approx(20.0)
    assert pair["separation_margin_m"] < 0  # inside the 15 m horizontal minimum
    assert not any(far.drone_id in (p["a"], p["b"]) for p in body["pairs"])  # beyond awareness radius
    assert body["drones"][a.drone_id]["nearest_drone_id"] == b.drone_id
    assert body["drones"][a.drone_id]["passed"] is False  # CBF min_separation is horizontal


def test_trajectory_and_forecast_are_served(api_client, auth_headers, fresh_fleet_state):
    fleet = get_fleet_state("pune")
    a, b = fleet.list_drones()[:2]
    lat0, lon0 = fleet.graph.node_lat_lon(fleet.depots[next(iter(fleet.depots))].node)
    # Head-on along the same street, 1.2 km apart, same altitude: they meet in ~50 s of cruise.
    _fly(fleet, a, "OA", [(lat0, lon0), (lat0 + 0.02, lon0)], 60.0, started_ago_s=25.0)
    _fly(fleet, b, "OB", [(lat0 + 0.0108 * 2, lon0), (lat0 - 0.01, lon0)], 60.0, started_ago_s=25.0)

    body = api_client.get(URL, headers=auth_headers).json()
    traj = body["drones"][a.drone_id]["trajectory"]
    assert traj[0][2] == 0.0 and traj[0][3] < 0          # take-off, already in the past
    assert any(p[3] == 0.0 for p in traj)                 # current position at t = 0
    assert traj[-1][2] == 0.0 and traj[-1][3] > 0         # touchdown ahead
    assert body["drones"][a.drone_id]["phase"] == "CRUISE"

    conflict = next(c for c in body["predicted_conflicts"] if {c["a"], c["b"]} == {a.drone_id, b.drone_id})
    assert conflict["severity"] == "CONFLICT" and 0 < conflict["t_s"] <= 120
    assert conflict["horizontal_m"] < body["constants"]["min_separation_m"]
    assert set(body["forecast_drone_ids"]) >= {a.drone_id, b.drone_id}
