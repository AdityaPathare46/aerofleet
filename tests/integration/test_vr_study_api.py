"""The VR debrief study API: counterbalanced plans, no answers sent, one answer per trial."""
import pytest

pytestmark = pytest.mark.integration
URL = "/api/v1/vr-study"


@pytest.fixture(autouse=True)
def _clean():
    from aerofleet.data.database import get_db_session
    from aerofleet.data.models.models import VrStudyResponse

    with get_db_session() as db:
        db.query(VrStudyResponse).filter(VrStudyResponse.participant.in_(["P96", "P97", "P98", "P99"])).delete(synchronize_session=False)
        db.commit()
    yield


def test_four_groups_counterbalance_condition_order_and_set(api_client, auth_headers):
    seen = set()
    for code in ("P96", "P97", "P98", "P99"):
        plan = api_client.get(f"{URL}/plan/{code}", headers=auth_headers).json()
        b1, b2 = plan["blocks"]
        assert {b1["condition"], b2["condition"]} == {"2d", "headset"} and {b1["set"], b2["set"]} == {"A", "B"}
        assert len(b1["trials"]) == 15 and len(b1["practice"]) == 3
        assert all("answer" not in t for b in plan["blocks"] for t in b["trials"])          # no answers leave the server
        seen.add((b1["condition"], b1["set"]))
    assert len(seen) == 4


def test_answers_are_stored_once_and_only_practice_gets_feedback(api_client, auth_headers):
    plan = api_client.get(f"{URL}/plan/P97", headers=auth_headers).json()
    b = plan["blocks"][0]
    t = b["trials"][0]["id"]
    body = {"participant": "P97", "condition": b["condition"], "trial_id": t, "position": 1, "answer": "sideways", "ms": 4200}
    r = api_client.post(f"{URL}/responses", headers=auth_headers, json=body)
    assert r.status_code == 200 and "correct_answer" not in r.json()
    assert api_client.post(f"{URL}/responses", headers=auth_headers, json=body).status_code == 409
    p = b["practice"][1]["id"]
    pr = api_client.post(f"{URL}/responses", headers=auth_headers, json={**body, "condition": f"practice-{b['condition']}", "trial_id": p})
    assert pr.json()["correct_answer"] in ("none", "sideways", "height")
    assert api_client.post(f"{URL}/responses", headers=auth_headers, json={**body, "trial_id": "A02", "answer": "maybe"}).status_code == 422
    assert api_client.get(f"{URL}/plan/John", headers=auth_headers).status_code == 422
    assert f"{b['condition']}|{t}" in api_client.get(f"{URL}/plan/P97", headers=auth_headers).json()["done"]
