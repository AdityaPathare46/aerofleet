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
    bad_log = dict(files, log=("flight.kml", b"<kml/>", "application/xml"))
    assert "Unsupported log type" in api_client.post(f"{URL}/drones/D1/flights", headers=auth_headers, files=bad_log).json()["detail"]
    broken = dict(files, log=("flight.ulg", b"ULog\x01", "application/octet-stream"))
    assert "Could not open the log" in api_client.post(f"{URL}/drones/D1/flights", headers=auth_headers, files=broken).json()["detail"]
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
    rh = body["rehearsal"]
    assert len(rh["before"]["conflicts"]) == 1 and rh["after"]["conflicts"] == [] and {t["id"] for t in rh["after"]["tracks"]} == {"alpha", "bravo"}


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


# ── wind at cruise height ──────────────────────────────────────────────

WIND = "/api/v1/assurance/plans/wind-check"


def test_wind_check_with_a_supplied_profile_and_its_errors(api_client, auth_headers):
    import json

    plan = {"plan": ("m.waypoints", _mission(DEPOT, NORTH, alt=100.0).encode(), "text/plain")}
    profile = json.dumps({"10": [2, 0], "80": [5, 0], "120": [7, 0], "180": [8, 0]})
    r = api_client.post(WIND, headers=auth_headers, files=plan, data={"payload_kg": 1, "usable_wh": 9.7, "profile": profile})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["verdict"] == "FAILS_AT_ALTITUDE" and body["wind"]["at_cruise"]["speed_mps"] == 6.0 and body["wind_source"] == "supplied by the user"
    assert body["still_air"]["margin_wh"] > 0 > body["cruise_wind"]["margin_wh"]
    ok = api_client.post(WIND, headers=auth_headers, files=plan, data={"payload_kg": 1, "usable_wh": 20, "profile": profile})
    assert ok.json()["verdict"] == "PASS"
    bad = api_client.post(WIND, headers=auth_headers, files=plan, data={"payload_kg": 1, "usable_wh": 20, "profile": "{oops"})
    assert bad.status_code == 422 and "Bad wind profile" in bad.json()["detail"]
    assert api_client.post(WIND, files=plan, data={"payload_kg": 1, "usable_wh": 20}).status_code == 401


def test_wind_check_without_a_forecast_says_how_to_continue(api_client, auth_headers, monkeypatch):
    from aerofleet.assurance import wind

    def offline(url):
        raise OSError("network is unreachable")

    monkeypatch.setattr(wind.fetch_profiles, "__defaults__", (0, 1, offline))
    plan = {"plan": ("m.waypoints", _mission(DEPOT, NORTH, alt=100.0).encode(), "text/plain")}
    r = api_client.post(WIND, headers=auth_headers, files=plan, data={"payload_kg": 1, "usable_wh": 20})
    assert r.status_code == 503 and "Supply the wind by hand" in r.json()["detail"]


def test_settings_changed_during_a_flight_are_reported_in_the_review(api_client, auth_headers, tmp_path):
    files = _flight_files(tmp_path, params=(("FENCE_ENABLE", 1.0), ("FS_THR_ENABLE", 1.0), ("FENCE_ENABLE", 0.0, 30.0), ("FENCE_ENABLE", 1.0, 80.0)))
    body = api_client.post(f"{URL}/drones/D7/flights", headers=auth_headers, files=files).json()
    changed = body["report"]["settings_changed_in_flight"]
    assert changed["count"] == 2 and changed["safety_critical"] == 2
    assert [(c["name"], c["new"], c["t_s"]) for c in changed["changes"]] == [("FENCE_ENABLE", 0.0, 30.0), ("FENCE_ENABLE", 1.0, 80.0)]   # to the position before it
    assert body["drift"]["param_count"] == 2                               # the final settings alone look untouched
    listed = api_client.get(f"{URL}/flights?drone_id=D7", headers=auth_headers).json()
    assert listed[0]["settings_changed_critical"] == 2


# ── printable report, no-fly zones through the API, signed record for stateless checks ──

def test_printable_report_escapes_upload_text_and_checks_the_signed_record(api_client, auth_headers, tmp_path):
    from aerofleet.data.database import get_db_session
    from aerofleet.data.models.models import FlightReview

    files = _flight_files(tmp_path, offset_m=80.0, params=(("FENCE_ENABLE", 1.0), ("FENCE_ENABLE", 0.0, 30.0)))
    files["log"] = ("<script>alert(1)</script>.tlog", files["log"][1], files["log"][2])
    body = api_client.post(f"{URL}/drones/D8/flights", headers=auth_headers, files=files).json()
    r = api_client.get(f"{URL}/flights/{body['id']}/report", headers=auth_headers)
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/html")
    page = r.text
    assert "<script>" not in page and "&lt;script&gt;alert(1)&lt;/script&gt;.tlog" in page
    assert "Deviated from the plan" in page and "Off the planned route" in page and "FENCE_ENABLE" in page and "Safety-critical" in page
    assert f"This review matches entry #{body['ledger_seq']} of the signed record" in page

    with get_db_session() as db:                                   # someone edits the stored review afterwards
        row = db.get(FlightReview, body["id"])
        row.report = dict(row.report, verdict="CONFORMED", episodes=[])
        db.commit()
    tampered = api_client.get(f"{URL}/flights/{body['id']}/report", headers=auth_headers).text
    assert "No entry in the signed record matches this review" in tampered
    assert api_client.get(f"{URL}/flights/{body['id']}/report").status_code == 401
    assert api_client.get(f"{URL}/flights/999999/report", headers=auth_headers).status_code == 404


def test_time_inside_a_real_no_fly_zone_is_reported_when_a_city_is_given(api_client, auth_headers, tmp_path):
    from aerofleet.integrations.mission_planner import build_waypoint_file
    from tests.unit.test_assurance_flightlog import write_tlog

    red = next(z for z in api_client.get("/api/v1/geofence/zones?city=pune").json() if z["zone_type"] == "RED")
    lat, lon = red["center_lat"], red["center_lon"]
    plan = build_waypoint_file({"origin_lat": lat, "origin_lon": lon, "dest_lat": lat + 0.001, "dest_lon": lon, "altitude_m": 60.0})
    track = [(float(i), lat, lon, 60.0 * i / 10) for i in range(10)] + [(10.0 + i, lat + 0.001 * i / 29, lon, 60.0) for i in range(30)]
    log = write_tlog(str(tmp_path / "zone.tlog"), track, modes=[(0.0, 4), (10.0, 3)])

    def files():
        return {"plan": ("m.waypoints", plan.encode(), "text/plain"), "log": ("zone.tlog", open(log, "rb").read(), "application/octet-stream")}

    without = api_client.post(f"{URL}/drones/Z1/flights", headers=auth_headers, files=files()).json()
    assert without["verdict"] == "CONFORMED" and without["report"]["zones_checked"] is None       # on plan, zones not asked for
    with_city = api_client.post(f"{URL}/drones/Z1/flights?city=pune", headers=auth_headers, files=files()).json()
    assert with_city["verdict"] == "DEVIATED" and with_city["report"]["zones_checked"] == "pune"
    kinds = [e["kind"] for e in with_city["report"]["episodes"]]
    assert kinds == ["in_no_fly_zone"] and with_city["report"]["episodes"][0]["duration_s"] >= 30


def test_deconfliction_and_wind_checks_are_written_to_the_signed_record(api_client, auth_headers):
    import json

    d = api_client.post(DECONFLICT, headers=auth_headers, files=_plans(alpha=_mission(DEPOT, NORTH), bravo=_mission(DEPOT, NORTH))).json()
    profile = json.dumps({"10": [2, 0], "80": [5, 0], "120": [7, 0], "180": [8, 0]})
    w = api_client.post(WIND, headers=auth_headers, files={"plan": ("north.waypoints", _mission(DEPOT, NORTH, alt=100.0).encode(), "text/plain")},
                        data={"payload_kg": 1, "usable_wh": 20, "profile": profile}).json()
    assert w["ledger_seq"] == d["ledger_seq"] + 1
    entries = {e["seq"]: e for e in api_client.get("/api/v1/assurance/ledger", headers=auth_headers).json()["entries"]}
    assert (entries[d["ledger_seq"]]["kind"], entries[d["ledger_seq"]]["subject"]) == ("deconflict", "alpha,bravo")
    assert (entries[w["ledger_seq"]]["kind"], entries[w["ledger_seq"]]["subject"]) == ("wind_check", "north.waypoints")
    assert api_client.get("/api/v1/assurance/ledger/verify", headers=auth_headers).json()["ok"] is True


def test_a_px4_ulg_log_is_reviewed_like_an_ardupilot_one(api_client, auth_headers, tmp_path):
    from aerofleet.integrations.mission_planner import build_waypoint_file
    from tests.unit.test_assurance_ulog import write_ulog

    home, dest, alt = (18.5200, 73.8500), (18.5290, 73.8500), 60.0
    plan = build_waypoint_file({"origin_lat": home[0], "origin_lon": home[1], "dest_lat": dest[0], "dest_lon": dest[1], "altitude_m": alt})
    track = [(float(i), home[0], home[1], alt * i / 10) for i in range(10)]
    track += [(10.0 + i, home[0] + (dest[0] - home[0]) * i / 99, home[1], alt) for i in range(100)]
    log = write_ulog(str(tmp_path / "px4.ulg"), track, params=[("MAV_TYPE", 2), ("GF_ACTION", 1)], nav_states=[(0.0, 17), (10.0, 3)])
    files = {"plan": ("mission.waypoints", plan.encode(), "text/plain"), "log": ("px4.ulg", open(log, "rb").read(), "application/octet-stream")}
    r = api_client.post(f"{URL}/drones/PX1/flights", headers=auth_headers, files=files)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["verdict"] == "CONFORMED" and body["report"]["log"]["format"] == "ulg" and body["report"]["log"]["points"] == 110
    assert body["drift"]["param_count"] == 2                                            # PX4 settings feed the drift check too


def test_fleet_vibration_ranks_drones_from_their_reviewed_flights(api_client, auth_headers, tmp_path):
    from aerofleet.integrations.mission_planner import build_waypoint_file
    from tests.unit.test_assurance_flightlog import write_tlog

    home, dest = (18.5200, 73.8500), (18.5290, 73.8500)
    plan = build_waypoint_file({"origin_lat": home[0], "origin_lon": home[1], "dest_lat": dest[0], "dest_lon": dest[1], "altitude_m": 60.0})
    track = [(float(i), home[0], home[1], 6.0 * i) for i in range(10)]
    track += [(10.0 + i, home[0] + (dest[0] - home[0]) * i / 99, home[1], 60.0) for i in range(100)]
    for k, level in enumerate((4.0, 6.0, 9.0, 30.0)):
        log = write_tlog(str(tmp_path / f"v{k}.tlog"), track, vibration=lambda t, lv=level: (lv, lv / 2, lv / 3))
        files = {"plan": ("m.waypoints", plan.encode(), "text/plain"), "log": ("f.tlog", open(log, "rb").read(), "application/octet-stream")}
        assert api_client.post(f"{URL}/drones/V{k}/flights", headers=auth_headers, files=files).status_code == 200
    out = api_client.get(f"{URL}/vibration", headers=auth_headers).json()
    assert [d["drone_id"] for d in out["drones"]] == ["V3", "V2", "V1", "V0"]
    assert "flagged" not in out and "not shown to beat random inspection" in out["evidence"]      # position only, no flag line
    one = api_client.get(f"{URL}/drones/V3/vibration", headers=auth_headers).json()
    assert one["among_peers"]["rank"] == 1 and len(one["flights"]) == 1 and one["latest_vs_own"] is None


def test_a_log_can_be_reviewed_without_a_mission_file(api_client, auth_headers, tmp_path):
    """Public logs and most field logs come with no plan: the events, evidence quality and vibration are still reviewed,
    signed and printable, and nothing is said to conform or deviate."""
    from tests.unit.test_assurance_ulog import TRACK, write_ulog

    log = write_ulog(str(tmp_path / "solo.ulg"), TRACK, nav_states=((0.0, 2), (20.0, 3)), vibration=[(1.0 + i, 5.0) for i in range(60)])
    files = {"log": ("solo.ulg", open(log, "rb").read(), "application/octet-stream")}
    r = api_client.post(f"{URL}/drones/SOLO/flights", headers=auth_headers, files=files)
    assert r.status_code == 200, r.text
    body = r.json()
    rep = body["report"]
    assert body["verdict"] == "LOG_ONLY" and rep["episodes"] == [] and rep["input_files"]["plan"] is None
    assert len(rep["input_files"]["log"]["sha256"]) == 64 and body["ledger_seq"] >= 1
    assert rep["manual_control"][0]["mode"] == "POSCTL" and rep["vibration"]["end_margin_s"] == 10.0
    assert any(e["kind"] == "mode" for e in rep["evidence_timeline"]) and rep["replay"]["planned"] == []
    html = api_client.get(f"{URL}/flights/{body['id']}/report", headers=auth_headers).text
    assert "reviewed on its own" in html and "does not name a cause" in html and "Flew the plan" not in html
    listed = api_client.get(f"{URL}/flights", headers=auth_headers).json()
    assert listed[0]["verdict"] == "LOG_ONLY" and listed[0]["max_off_route_m"] is None


def test_a_review_states_the_quality_of_its_evidence(api_client, auth_headers, tmp_path):
    body = api_client.post(f"{URL}/drones/DQ/flights", headers=auth_headers, files=_flight_files(tmp_path)).json()
    dq = body["report"]["data_quality"]
    assert dq["position_rate_hz"] == 1.0 and dq["longest_gap_s"] == 1.0
    assert "relative_alt" in dq["height_reference"] and "time since boot" in dq["clock"]
    assert dq["tolerances"] == {"corridor_m": 30.0, "altitude_m": 15.0} and "not reported" in dq["note"]
    html = api_client.get(f"{URL}/flights/{body['id']}/report", headers=auth_headers).text
    assert "Quality of the evidence" in html


def test_troubleshoot_matches_a_description_and_adds_the_drones_vibration(api_client, auth_headers):
    r = api_client.post("/api/v1/assurance/troubleshoot", headers=auth_headers,
                        json={"description": "compass heading wrong, drone drifts in loiter", "fleet": "tf", "drone_id": "D1"})
    assert r.status_code == 200
    body = r.json()
    assert any(c["cause"] == "GPS / compass / estimator" and c["mentioned"] for c in body["checklist"])
    assert body["this_drone_vibration"]["drone_id"] == "D1"
    assert api_client.post("/api/v1/assurance/troubleshoot", json={"description": "x y z"}).status_code == 401
    assert api_client.post("/api/v1/assurance/troubleshoot", headers=auth_headers, json={"description": "ok", "fleet": "../x", "drone_id": "D1"}).status_code in (400, 422)


def test_the_tamper_demonstration_catches_every_attack_and_leaves_the_record_intact(api_client, auth_headers, tmp_path):
    for k in range(3):                                          # a few signed entries to attack
        assert api_client.post(f"{URL}/drones/T{k}/flights", headers=auth_headers, files=_flight_files(tmp_path)).status_code == 200
    before = api_client.get("/api/v1/assurance/ledger/verify", headers=auth_headers).json()
    out = api_client.post("/api/v1/assurance/ledger/tamper-demo", headers=auth_headers).json()
    names = [a["attack"] for a in out["attacks"]]
    assert "Delete an entry from the middle" in names and "Rewrite an entry and re-sign it with another key" in names
    assert out["all_caught"] and all(a["caught"] and a["problem"] for a in out["attacks"])
    assert any("signature" in a["problem"] for a in out["attacks"] if "another key" in a["attack"])
    after = api_client.get("/api/v1/assurance/ledger/verify", headers=auth_headers).json()
    assert before["ok"] == after["ok"] and out["record_untouched"]["entries"] == after["entries"]


@pytest.mark.parametrize("name,content,why", [
    ("empty.ulg", b"", "empty"),
    ("noise.ulg", bytes(range(256)) * 40, "not a log"),
    ("text.ulg", b"QGC WPL 110\n0\t1\t0\t16\n", "a mission file renamed"),
    ("photo.jpg", b"\xff\xd8\xff\xe0" + b"0" * 100, "wrong type"),
])
def test_damaged_or_wrong_files_get_a_clear_error_not_a_crash(api_client, auth_headers, name, content, why):
    r = api_client.post(f"{URL}/drones/BAD/flights", headers=auth_headers, files={"log": (name, content, "application/octet-stream")})
    assert r.status_code == 422, (why, r.status_code, r.text)
    assert isinstance(r.json()["detail"], str) and len(r.json()["detail"]) > 10


def test_a_log_cut_off_mid_flight_is_still_reviewed_from_what_survives(api_client, auth_headers, tmp_path):
    """A crash can cut a log short. The part that was written is reviewed; nothing is invented for the rest."""
    from tests.unit.test_assurance_ulog import TRACK, write_ulog

    full = open(write_ulog(str(tmp_path / "full.ulg"), TRACK, vibration=[(1.0 + i, 5.0) for i in range(60)]), "rb").read()
    cut = full[: int(len(full) * 0.7)]
    r = api_client.post(f"{URL}/drones/CUT/flights", headers=auth_headers, files={"log": ("cut.ulg", cut, "application/octet-stream")})
    assert r.status_code in (200, 422), r.text
    if r.status_code == 200:
        assert r.json()["report"]["flight_s"] <= 60 and r.json()["verdict"] == "LOG_ONLY"


def test_route_check_against_the_real_pune_zones_the_ceiling_and_each_other(api_client, auth_headers):
    """The five demo missions (tauri-app/public/demo/route_check), plus one near Delhi IGI airport and one in rural Maharashtra."""
    from pathlib import Path

    from aerofleet.integrations.mission_planner import build_waypoint_file

    demo = Path(__file__).resolve().parents[2] / "tauri-app" / "public" / "demo" / "route_check"
    files = [("plans", (p.name, p.read_bytes(), "text/plain")) for p in sorted(demo.glob("[A-Z]*.waypoints"))]
    delhi = build_waypoint_file({"origin_lat": 28.61, "origin_lon": 77.20, "dest_lat": 28.62, "dest_lon": 77.21, "altitude_m": 60.0})
    rural = build_waypoint_file({"origin_lat": 19.20, "origin_lon": 75.50, "dest_lat": 19.21, "dest_lon": 75.51, "altitude_m": 60.0})
    files.append(("plans", ("DELHI-TEST.waypoints", delhi.encode(), "text/plain")))
    files.append(("plans", ("RURAL-MH.waypoints", rural.encode(), "text/plain")))
    r = api_client.post("/api/v1/assurance/plans/airspace", headers=auth_headers, files=files)
    assert r.status_code == 200, r.text
    out = r.json()
    v = {m["id"]: m["verdict"] for m in out["missions"]}
    assert v == {"SPRAY-NEAR-CANTONMENT": "NOT_PERMITTED", "CROP-MAP-150M": "NOT_PERMITTED", "SPRAY-NEAR-AIRPORT": "NEEDS_PERMISSION",
                 "SPRAY-FIELD-A": "CLEAR", "SPRAY-FIELD-B": "CLEAR", "DELHI-TEST": "NEEDS_PERMISSION", "RURAL-MH": "UNCHECKED"}
    cant = next(m for m in out["missions"] if m["id"] == "SPRAY-NEAR-CANTONMENT")
    assert "Pune Cantonment" in cant["summary"] and cant["city"] == "pune"
    assert {frozenset((c["a"], c["b"])) for c in out["conflicts"]} == {frozenset(("SPRAY-FIELD-A", "SPRAY-FIELD-B"))}
    assert "Digital Sky" in out["note"] and out["ledger_seq"] >= 1 and len(out["input_files"]) == 7
    assert api_client.post("/api/v1/assurance/plans/airspace", headers=auth_headers,
                           files=[("plans", ("bad name!.waypoints", delhi.encode(), "text/plain"))]).status_code == 422


def test_the_readiness_board_combines_settings_registration_and_the_last_flight(api_client, auth_headers, operator_headers, tmp_path):
    from aerofleet.data.database import get_session
    from aerofleet.data.models.models import DroneRegistration

    api_client.post(f"{URL}/baseline", headers=operator_headers, files=_file(BASE))
    api_client.post(f"{URL}/drones/RB-OK/params", headers=auth_headers, files=_file(BASE))
    api_client.post(f"{URL}/drones/RB-BAD/params", headers=auth_headers, files=_file(BASE.replace("FS_THR_ENABLE,1", "FS_THR_ENABLE,0")))
    db = get_session()
    for d in ("RB-OK", "RB-BAD"):
        db.merge(DroneRegistration(drone_id=d, uin=f"UA-{d}", status="VERIFIED"))
    db.commit()
    board = api_client.get(f"{URL}/readiness", headers=auth_headers).json()
    rows = {r["drone_id"]: r for r in board["drones"]}
    assert rows["RB-OK"]["status"] == "READY"
    assert rows["RB-BAD"]["status"] == "DO_NOT_FLY" and "FS_THR_ENABLE" in rows["RB-BAD"]["reasons"][0]["text"]
    assert board["drones"][0]["status"] == "DO_NOT_FLY"                  # worst first
    assert "never changes the verdict" in board["vibration_note"] and board["counts"]["READY"] >= 1


def test_the_maintenance_logbook_is_signed_and_shows_the_effect(api_client, auth_headers, tmp_path):
    r = api_client.post(f"{URL}/drones/MX/flights", headers=auth_headers, files=_flight_files(tmp_path))
    assert r.status_code == 200
    seq_before = api_client.get("/api/v1/assurance/ledger/head", headers=auth_headers).json()["seq"]
    ok = api_client.post(f"{URL}/drones/MX/maintenance", headers=auth_headers,
                         json={"done_at": "2026-01-01T09:00:00", "action": "Propellers replaced", "note": "new 10-inch set"})
    assert ok.status_code == 200, ok.text
    entry = ok.json()["entries"][0]
    assert entry["action"] == "Propellers replaced" and entry["done_by"] and "summary" in entry["effect"]
    assert api_client.get("/api/v1/assurance/ledger/head", headers=auth_headers).json()["seq"] == seq_before + 1
    assert api_client.post(f"{URL}/drones/MX/maintenance", headers=auth_headers,
                           json={"done_at": "2099-01-01T00:00:00", "action": "Propellers replaced"}).status_code == 422
    assert api_client.post(f"{URL}/drones/MX/maintenance", headers=auth_headers,
                           json={"done_at": "2026-01-01T00:00:00", "action": "Painted it red"}).status_code == 422
    hist = api_client.get(f"{URL}/drones/MX/vibration", headers=auth_headers).json()
    assert len(hist["maintenance"]) == 1 and "Propellers replaced" in hist["maintenance_actions"]


def test_the_evening_batch_upload_matches_each_log_to_its_drone(api_client, auth_headers, tmp_path, monkeypatch):
    import aerofleet.api.routes.assurance as routes
    from tests.unit.test_assurance_ulog import TRACK, write_ulog

    log = open(write_ulog(str(tmp_path / "x.ulg"), TRACK, vibration=[(1.0 + i, 5.0) for i in range(60)]), "rb").read()
    ids = {"BT-1_morning.ulg": "UUID-1", "renamed-by-pilot.ulg": "UUID-1", "mystery.ulg": "UUID-9", "nameless.tlog": None}
    monkeypatch.setattr(routes, "_log_uuid", lambda name, data: ids.get(name))
    files = [("logs", (n, log, "application/octet-stream")) for n in ("BT-1_morning.ulg", "renamed-by-pilot.ulg", "mystery.ulg")]
    out = api_client.post(f"{URL}/flights/batch", headers=auth_headers, files=files).json()
    by = {r["file"]: r for r in out["results"]}
    assert by["BT-1_morning.ulg"]["drone_id"] == "BT-1" and by["BT-1_morning.ulg"]["matched_by"].startswith("file name")
    assert by["renamed-by-pilot.ulg"]["drone_id"] == "BT-1" and by["renamed-by-pilot.ulg"]["matched_by"] == "flight-controller id seen before"
    assert by["mystery.ulg"]["drone_id"] is None and "Unknown drone" in by["mystery.ulg"]["error"]
    assert out["reviewed"] == 2 and out["not_reviewed"] == 1 and by["BT-1_morning.ulg"]["verdict"] == "LOG_ONLY"
    assert api_client.post(f"{URL}/flights/batch", headers=auth_headers, files=[]).status_code == 422


def test_dgca_compliance_rule45_accident_dossier_and_fleet_list(api_client, auth_headers, operator_headers, tmp_path):
    from aerofleet.data.database import get_session
    from aerofleet.data.models.models import DroneRegistration

    api_client.post(f"{URL}/baseline", headers=operator_headers, files=_file(BASE))
    api_client.post(f"{URL}/drones/DG-1/params", headers=auth_headers, files=_file(BASE))
    api_client.post(f"{URL}/drones/DG-1/flights", headers=auth_headers, files=_flight_files(tmp_path))
    db = get_session()
    db.merge(DroneRegistration(drone_id="DG-1", uin="UA00DG1", status="VERIFIED"))
    db.commit()

    # Save expired Rule 44 insurance -> signed into ledger and turns readiness to DO_NOT_FLY
    r = api_client.put(
        "/api/v1/assurance/drones/DG-1/compliance",
        headers=operator_headers,
        json={"insurance_policy": "POL-99", "insurance_insurer": "NIA", "insurance_valid_until": "2020-01-01",
              "type_certificate_no": "DAN-AGRI", "pilot_name": "Pilot A", "pilot_rpc_no": "RPC-1", "pilot_rpc_valid_until": "2030-01-01"},
    )
    assert r.status_code == 200 and r.json()["ledger_seq"] >= 1
    board = api_client.get(f"{URL}/readiness", headers=auth_headers).json()
    row = next(d for d in board["drones"] if d["drone_id"] == "DG-1")
    assert row["status"] == "DO_NOT_FLY"
    assert any(x["code"] == "insurance_expired" for x in row["reasons"])

    # Fleet listing includes the test fleet
    fleet_name = URL.rsplit("/", 1)[-1]
    fleets = api_client.get("/api/v1/assurance/fleets", headers=auth_headers).json()
    assert any(f["fleet"] == fleet_name and f["drones"] >= 1 for f in fleets["fleets"])

    # Rule 45 48-hour accident dossier JSON & printable HTML both return complete verified data
    dj = api_client.get(f"{URL}/drones/DG-1/accident-dossier.json", headers=auth_headers)
    assert dj.status_code == 200
    body = dj.json()
    assert body["aircraft"]["uin"] == "UA00DG1" and body["aircraft"]["insurance_policy"] == "POL-99"
    assert body["ledger"] and body["ledger"]["matches_record"] is True
    dh = api_client.get(f"{URL}/drones/DG-1/accident-dossier", headers=auth_headers)
    assert dh.status_code == 200 and "DGCA Rule 45" in dh.text and "POL-99" in dh.text and "VERIFIED" in dh.text
