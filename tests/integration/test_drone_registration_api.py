"""Drone registration (UIN) registry: honest statuses, operator-only writes."""
import pytest

pytestmark = pytest.mark.integration

URL = "/api/v1/fleet/registrations"


@pytest.fixture(autouse=True)
def _clean():
    from aerofleet.data.database import get_db_session
    from aerofleet.data.models.models import DroneRegistration

    with get_db_session() as db:
        db.query(DroneRegistration).delete()
        db.commit()
    yield


def test_unregistered_drone_reads_as_none(api_client, auth_headers):
    assert api_client.get(f"{URL}/PUN-D1", headers=auth_headers).json() == {"drone_id": "PUN-D1", "uin": None, "status": "NONE"}


def test_record_then_verify(api_client, operator_headers):
    r = api_client.put(f"{URL}/PUN-D1", headers=operator_headers, json={"uin": " ua-1234-abcd "})
    assert r.status_code == 200 and r.json()["uin"] == "UA-1234-ABCD" and r.json()["status"] == "RECORDED"
    v = api_client.post(f"{URL}/PUN-D1/verify", headers=operator_headers, json={"note": "Checked on Digital Sky, serial matches"})
    body = v.json()
    assert body["status"] == "VERIFIED" and body["verified_by"] and "Digital Sky" in body["verification_note"]


def test_changing_the_uin_resets_verification(api_client, operator_headers):
    api_client.put(f"{URL}/PUN-D1", headers=operator_headers, json={"uin": "UA-1234-ABCD"})
    api_client.post(f"{URL}/PUN-D1/verify", headers=operator_headers, json={"note": "checked"})
    r = api_client.put(f"{URL}/PUN-D1", headers=operator_headers, json={"uin": "UA-9999-ZZZZ"})
    assert r.json()["status"] == "RECORDED" and r.json()["verified_by"] is None


def test_verification_needs_a_recorded_uin_and_a_note(api_client, operator_headers):
    assert api_client.post(f"{URL}/PUN-D9/verify", headers=operator_headers, json={"note": "checked"}).status_code == 422
    api_client.put(f"{URL}/PUN-D9", headers=operator_headers, json={"uin": "UA-1234-ABCD"})
    assert api_client.post(f"{URL}/PUN-D9/verify", headers=operator_headers, json={"note": "  "}).status_code == 422


@pytest.mark.parametrize("bad", ["", "abc", "has spaces 123", "UA_1234!", "-UA1234"])
def test_obviously_invalid_uins_are_rejected(api_client, operator_headers, bad):
    assert api_client.put(f"{URL}/PUN-D1", headers=operator_headers, json={"uin": bad}).status_code == 422


def test_writes_need_an_operator(api_client, auth_headers):
    assert api_client.put(f"{URL}/PUN-D1", headers=auth_headers, json={"uin": "UA-1234-ABCD"}).status_code == 403
    assert api_client.get(URL).status_code == 401
