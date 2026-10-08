"""Parameter upload, fleet baseline and configuration drift over the API."""
import pytest

pytestmark = pytest.mark.integration

URL = "/api/v1/assurance/fleets/pune-agri"
BASE = "FS_THR_ENABLE,1\nFENCE_ENABLE,1\nRTL_ALT,1500\nANGLE_MAX,3000\nATC_RAT_RLL_P,0.135\nSTAT_FLTTIME,100\n"


def _file(text, name="drone.param"):
    return {"file": (name, text.encode(), "text/plain")}


@pytest.fixture(autouse=True)
def _clean():
    from aerofleet.data.database import get_db_session
    from aerofleet.data.models.models import FleetBaseline, FlightReview, ParamSnapshot

    with get_db_session() as db:
        db.query(FlightReview).delete()
        db.query(ParamSnapshot).delete()
        db.query(FleetBaseline).delete()
        db.commit()
    yield


def test_upload_without_baseline_is_not_a_silent_pass(api_client, auth_headers):
    r = api_client.post(f"{URL}/drones/D1/params", headers=auth_headers, files=_file(BASE))
    assert r.status_code == 200, r.text
    assert r.json()["verdict"] == "NO_REFERENCE" and r.json()["param_count"] == 6


def test_only_an_operator_can_set_the_baseline(api_client, auth_headers, operator_headers):
    assert api_client.post(f"{URL}/baseline", headers=auth_headers, files=_file(BASE)).status_code == 403
    r = api_client.post(f"{URL}/baseline", headers=operator_headers, files=_file(BASE, "golden.param"))
    assert r.status_code == 200 and r.json()["param_count"] == 6
    assert api_client.get(f"{URL}/baseline", headers=auth_headers).json()["source"] == "golden.param"


def test_drift_blocks_on_a_disabled_failsafe_and_approval_clears_only_that_value(api_client, auth_headers, operator_headers):
    api_client.post(f"{URL}/baseline", headers=operator_headers, files=_file(BASE))
    drifted = BASE.replace("FS_THR_ENABLE,1", "FS_THR_ENABLE,0").replace("STAT_FLTTIME,100", "STAT_FLTTIME,99999")
    r = api_client.post(f"{URL}/drones/D1/params", headers=auth_headers, files=_file(drifted)).json()
    assert r["verdict"] == "BLOCK" and r["decided_by"] == "vs_baseline"
    assert [c["name"] for c in r["vs_baseline"]["changes"]] == ["FS_THR_ENABLE"]      # the flight-time counter is ignored

    body = {"name": "fs_thr_enable", "value": 0, "note": "Bench drone, no RC receiver fitted"}
    assert api_client.post(f"{URL}/approvals", headers=auth_headers, json=body).status_code == 403
    assert api_client.post(f"{URL}/approvals", headers=operator_headers, json=body).status_code == 200
    after = api_client.get(f"{URL}/drones/D1/drift", headers=auth_headers).json()
    assert after["verdict"] == "OK" and after["vs_baseline"]["changes"][0]["approved"] is True


def test_previous_upload_shows_what_is_new_and_fleet_view_summarises(api_client, auth_headers, operator_headers):
    api_client.post(f"{URL}/baseline", headers=operator_headers, files=_file(BASE))
    api_client.post(f"{URL}/drones/D1/params", headers=auth_headers, files=_file(BASE.replace("ANGLE_MAX,3000", "ANGLE_MAX,4500")))
    second = BASE.replace("ANGLE_MAX,3000", "ANGLE_MAX,4500").replace("FENCE_ENABLE,1", "FENCE_ENABLE,0")
    r = api_client.post(f"{URL}/drones/D1/params", headers=auth_headers, files=_file(second)).json()
    assert {c["name"] for c in r["vs_baseline"]["changes"]} == {"FENCE_ENABLE", "ANGLE_MAX"}
    assert [c["name"] for c in r["vs_previous"]["changes"]] == ["FENCE_ENABLE"]
    api_client.post(f"{URL}/drones/D2/params", headers=auth_headers, files=_file(BASE))

    fleet = api_client.get(f"{URL}/drift", headers=auth_headers).json()
    assert [(d["drone_id"], d["verdict"]) for d in fleet["drones"]] == [("D1", "BLOCK"), ("D2", "OK")]
    assert fleet["summary"] == {"BLOCK": 1, "REVIEW": 0, "OK": 1, "NO_REFERENCE": 0} and fleet["has_baseline"] is True


def test_bad_uploads_and_unknown_drones_get_clear_errors(api_client, auth_headers):
    r = api_client.post(f"{URL}/drones/D1/params", headers=auth_headers, files={"file": ("x.bin", b"\x00\x01\x02binary", "application/octet-stream")})
    assert r.status_code == 422 and "binary" in r.json()["detail"]
    assert api_client.post(f"{URL}/drones/bad id!/params", headers=auth_headers, files=_file(BASE)).status_code == 422
    assert api_client.get(f"{URL}/drones/NOPE/drift", headers=auth_headers).status_code == 404
    assert api_client.get(f"{URL}/baseline", headers=auth_headers).status_code == 404
    assert api_client.post(f"{URL}/drones/D1/params", files=_file(BASE)).status_code == 401


def test_compliance_rules_run_on_the_uploaded_file(api_client, auth_headers):
    assert api_client.get(f"{URL}/drones/D1/checks", headers=auth_headers).status_code == 404
    api_client.post(f"{URL}/drones/D1/params", headers=auth_headers, files=_file(BASE.replace("FS_THR_ENABLE,1", "FS_THR_ENABLE,0")))
    r = api_client.get(f"{URL}/drones/D1/checks", headers=auth_headers).json()
    assert r["source"] == "param_file" and r["counts"]["total"] == 59 and r["verdict"] == "FAIL"
    by_id = {c["id"]: c for c in r["evaluated"]}
    assert by_id["fs.rc_loss"]["status"] == "FAIL" and by_id["fs.fence_enabled"]["status"] == "PASS"
    assert by_id["dgca.uin"]["status"] == "FAIL"          # no UIN registered for D1
    assert r["counts"]["needs_live"] > 0 and r["counts"]["manual"] > 0


# ── planned versus flown ───────────────────────────────────────────────

def _flight_files(tmp_path, offset_m=0.0, modes=((0.0, 4), (10.0, 3)), params=(("FS_THR_ENABLE", 1.0), ("FENCE_ENABLE", 1.0))):
    import math

    from aerofleet.integrations.mission_planner import build_waypoint_file
    from tests.unit.test_assurance_flightlog import write_tlog

    home, dest, alt = (18.5200, 73.8500), (18.5290, 73.8500), 60.0
    plan = build_waypoint_file({"origin_lat": home[0], "origin_lon": home[1], "dest_lat": dest[0], "dest_lon": dest[1], "altitude_m": alt})
    east = offset_m / (111_320.0 * math.cos(math.radians(home[0])))
    track = [(float(i), home[0], home[1], alt * i / 10) for i in range(10)]
    track += [(10.0 + i, home[0] + (dest[0] - home[0]) * i / 99, home[1] + (east if 40 <= i < 60 else 0.0), alt) for i in range(100)]
    path = write_tlog(str(tmp_path / "flight.tlog"), track, params=list(params), modes=list(modes))
    return {"plan": ("mission.waypoints", plan.encode(), "text/plain"), "log": ("flight.tlog", open(path, "rb").read(), "application/octet-stream")}


def test_a_flight_on_plan_conforms_and_its_parameters_feed_the_drift_check(api_client, auth_headers, operator_headers, tmp_path):
    api_client.post(f"{URL}/baseline", headers=operator_headers, files=_file("FS_THR_ENABLE,1\nFENCE_ENABLE,1\n"))
    r = api_client.post(f"{URL}/drones/D1/flights", headers=auth_headers, files=_flight_files(tmp_path))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["verdict"] == "CONFORMED" and body["report"]["episodes"] == [] and body["report"]["log"]["points"] == 110
    assert body["drift"]["verdict"] == "OK" and body["drift"]["param_count"] == 2      # parameters came from the log
    listed = api_client.get(f"{URL}/flights?drone_id=D1", headers=auth_headers).json()
    assert [(x["verdict"], x["episodes"]) for x in listed] == [("CONFORMED", 0)]
    assert api_client.get(f"{URL}/flights/{body['id']}", headers=auth_headers).json()["report"]["verdict"] == "CONFORMED"


def test_an_excursion_and_a_disabled_failsafe_in_the_log_are_both_caught(api_client, auth_headers, operator_headers, tmp_path):
    api_client.post(f"{URL}/baseline", headers=operator_headers, files=_file("FS_THR_ENABLE,1\nFENCE_ENABLE,1\n"))
    files = _flight_files(tmp_path, offset_m=80.0, params=(("FS_THR_ENABLE", 0.0), ("FENCE_ENABLE", 1.0)))
    body = api_client.post(f"{URL}/drones/D2/flights", headers=auth_headers, files=files).json()
    assert body["verdict"] == "DEVIATED"
    (episode,) = body["report"]["episodes"]
    assert episode["kind"] == "off_route" and 79 < episode["max_m"] < 81
    assert body["drift"]["verdict"] == "BLOCK"
    tight = api_client.post(f"{URL}/drones/D2/flights?corridor_m=100", headers=auth_headers, files=_flight_files(tmp_path, offset_m=80.0))
    assert tight.json()["verdict"] == "CONFORMED"                                      # the fleet's own tolerance


def test_flight_upload_errors_are_clear(api_client, auth_headers, tmp_path):
    files = _flight_files(tmp_path)
    bad_plan = dict(files, plan=("mission.waypoints", b"not a mission", "text/plain"))
    assert "Not a mission file" in api_client.post(f"{URL}/drones/D1/flights", headers=auth_headers, files=bad_plan).json()["detail"]
    bad_log = dict(files, log=("flight.ulg", b"ULog\x01", "application/octet-stream"))
    assert "Unsupported log type" in api_client.post(f"{URL}/drones/D1/flights", headers=auth_headers, files=bad_log).json()["detail"]
    assert api_client.post(f"{URL}/drones/D1/flights", files=files).status_code == 401
    assert api_client.get(f"{URL}/flights/999999", headers=auth_headers).status_code == 404


# ── fleet plan deconfliction ───────────────────────────────────────────

def _mission(origin, dest, alt=60.0):
    from aerofleet.integrations.mission_planner import build_waypoint_file

    return build_waypoint_file({"origin_lat": origin[0], "origin_lon": origin[1], "dest_lat": dest[0], "dest_lon": dest[1], "altitude_m": alt})


DECONFLICT = "/api/v1/assurance/plans/deconflict"
DEPOT, NORTH = (18.5200, 73.8500), (18.5290, 73.8500)


def _plans(**files):
    return [("plans", (f"{name}.waypoints", text.encode(), "text/plain")) for name, text in files.items()]


def test_same_depot_launches_get_a_staggered_schedule(api_client, auth_headers):
    r = api_client.post(DECONFLICT, headers=auth_headers, files=_plans(alpha=_mission(DEPOT, NORTH), bravo=_mission(DEPOT, NORTH)))
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["before"]) == 1 and body["after"] == [] and body["resolved"] is True
    assert [c["id"] for c in body["changes"]] == ["bravo"] and "missions" not in body
    launch = {s["id"]: s["launch_at_s"] for s in body["schedule"]}
    assert launch["alpha"] == 0.0 and launch["bravo"] > 0
    assert body["files"]["alpha"] == _mission(DEPOT, NORTH)                    # untouched


def test_priority_and_vertical_separation_options_and_the_rewritten_file(api_client, auth_headers):
    import json

    from aerofleet.assurance.reconcile import parse_waypoints

    files = _plans(alpha=_mission(DEPOT, NORTH), bravo=_mission(NORTH, DEPOT))
    opts = {"priority": {"bravo": 5}, "v_sep_m": 20}
    body = api_client.post(DECONFLICT, headers=auth_headers, files=files, data={"options": json.dumps(opts)}).json()
    (change,) = body["changes"]
    assert change["id"] == "alpha" and change["new_altitude_m"] != 60.0 and body["rule"]["vertical_separation_allowed"] is True
    rewritten = parse_waypoints(body["files"]["alpha"])
    assert rewritten.max_alt_m == change["new_altitude_m"] and rewritten.path[0][2] == 0.0     # home row untouched
    assert parse_waypoints(body["files"]["bravo"]).max_alt_m == 60.0


def test_deconflict_input_errors(api_client, auth_headers):
    one = api_client.post(DECONFLICT, headers=auth_headers, files=_plans(alpha=_mission(DEPOT, NORTH)))
    assert one.status_code == 422 and "between 2 and" in one.json()["detail"]
    bad = api_client.post(DECONFLICT, headers=auth_headers, files=_plans(alpha=_mission(DEPOT, NORTH), bravo="nope"))
    assert bad.status_code == 422 and "bravo.waypoints" in bad.json()["detail"]
    opts = api_client.post(DECONFLICT, headers=auth_headers, files=_plans(alpha=_mission(DEPOT, NORTH), bravo=_mission(DEPOT, NORTH)),
                           data={"options": "{not json"})
    assert opts.status_code == 422 and "Bad options" in opts.json()["detail"]
    assert api_client.post(DECONFLICT, files=_plans(alpha=_mission(DEPOT, NORTH), bravo=_mission(DEPOT, NORTH))).status_code == 401
