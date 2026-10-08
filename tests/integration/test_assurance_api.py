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
    from aerofleet.data.models.models import FleetBaseline, ParamSnapshot

    with get_db_session() as db:
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
