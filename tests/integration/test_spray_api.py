"""The spray register over the API: pre-filled form, signed saves, the deadline, submission and the printed form."""
import pytest

from tests.integration.test_assurance_api import _flight_files

pytestmark = pytest.mark.integration

FLEET = "/api/v1/assurance/fleets/spray-test"


@pytest.fixture(autouse=True)
def _clean():
    from aerofleet.data.database import get_db_session
    from aerofleet.data.models.models import FlightReview, SprayForm

    with get_db_session() as db:
        db.query(SprayForm).delete()
        db.query(FlightReview).filter(FlightReview.fleet == "spray-test").delete()
        db.commit()
    yield


def _flight(api_client, auth_headers, tmp_path, drone="SP1"):
    r = api_client.post(f"{FLEET}/drones/{drone}/flights", headers=auth_headers, files=_flight_files(tmp_path))
    assert r.status_code == 200, r.text
    return r.json()["id"]


def _complete():
    return {"1-2": "Field A", "2-1": "Crop", "2-2": 1.0, "2-3": "Paddy, BPH 20%", "3-1": "X / y", "3-2": "5%", "3-3": "EC",
            "3-4": "2099-01-01", "3-5": "No", "4-2": 26, "4-3": 60, "4-4": 2, "4-5": 90, "4-6": 0, "5-1": "Hydraulic",
            "5-2": "Pilot", "5-3": "M", "5-4": "N", "5-6": "2000-01-01", "5-10": "flat fan", "5-11": 1.5, "5-12": 4, "5-13": 5,
            "5-16": ["Ground party available"], "5-17": ["GPS"], "7-1": ["Gloves"], "7-2": "Yes", "7-3": ["Farmers"],
            "sop-notice": "2000-01-01T00:00", "sop-water": "Yes"}


def test_a_flight_appears_with_its_deadline_and_the_log_fills_part_of_the_form(api_client, auth_headers, tmp_path):
    rid = _flight(api_client, auth_headers, tmp_path)
    reg = api_client.get(f"{FLEET}/spray-register", headers=auth_headers).json()
    row = next(r for r in reg["rows"] if r["review_id"] == rid)
    assert reg["deadline_days"] == 7 and row["state"] in ("OVERDUE", "DRAFT", "DUE_SOON") and row["missing"] > 0
    form = api_client.get(f"{FLEET}/spray-forms/{rid}", headers=auth_headers).json()
    assert form["sources"].get("4-1s") in ("log", "upload time") and form["values"]["5-5"] == "Aerial"


def test_saving_is_signed_checked_and_submission_freezes_the_form(api_client, auth_headers, tmp_path):
    rid = _flight(api_client, auth_headers, tmp_path)
    head = lambda: api_client.get("/api/v1/assurance/ledger/head", headers=auth_headers).json()["seq"]  # noqa: E731
    before = head()
    assert api_client.put(f"{FLEET}/spray-forms/{rid}", headers=auth_headers, json={"values": {"3-3": "Gel"}}).status_code == 422
    assert api_client.put(f"{FLEET}/spray-forms/{rid}", headers=auth_headers, json={"values": {"9-9": "x"}}).status_code == 422
    early = api_client.post(f"{FLEET}/spray-forms/{rid}/submitted", headers=auth_headers, json={"submitted_on": "2026-01-01", "via": "email"})
    assert early.status_code == 422 and "Fill the form first" in early.json()["detail"]
    saved = api_client.put(f"{FLEET}/spray-forms/{rid}", headers=auth_headers, json={"values": _complete()})
    assert saved.status_code == 200, saved.text
    assert head() == before + 1 and saved.json()["status"]["missing"] == 0
    day = saved.json()["values"]["1-1"]
    sent = api_client.post(f"{FLEET}/spray-forms/{rid}/submitted", headers=auth_headers, json={"submitted_on": day, "via": "email"})
    assert sent.status_code == 200, sent.text
    assert sent.json()["status"]["state"] == "SUBMITTED" and head() == before + 2
    assert api_client.put(f"{FLEET}/spray-forms/{rid}", headers=auth_headers, json={"values": {"1-2": "B"}}).status_code == 409
    page = api_client.get(f"{FLEET}/spray-forms-print?ids={rid}", headers=auth_headers)
    assert page.status_code == 200 and "Field A" in page.text and "Annexure-I" in page.text
    csv = api_client.get(f"{FLEET}/spray-register.csv", headers=auth_headers).text
    assert "SUBMITTED" in csv.splitlines()[1]


def test_a_test_flight_can_be_set_aside_but_it_is_recorded(api_client, auth_headers, tmp_path):
    rid = _flight(api_client, auth_headers, tmp_path)
    assert api_client.post(f"{FLEET}/spray-forms/{rid}/not-spray", headers=auth_headers, json={"not_spray": True}).status_code == 200
    reg = api_client.get(f"{FLEET}/spray-register", headers=auth_headers).json()
    assert rid not in [r["review_id"] for r in reg["rows"]] and rid in [r["review_id"] for r in reg["not_spray"]]
    assert api_client.get(f"{FLEET}/spray-forms-print?ids=1,2,3,4,5,6,7", headers=auth_headers).status_code == 422
    assert api_client.get(f"{FLEET}/spray-register").status_code == 401
