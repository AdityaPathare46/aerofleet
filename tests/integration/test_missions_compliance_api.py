"""Atharv's compliance and mission routes, wired to the registry, the database and the signed record."""
import pytest

pytestmark = pytest.mark.integration

PLAN = {"origin_lat": 18.5200, "origin_lon": 73.8500, "dest_lat": 18.5290, "dest_lon": 73.8500, "altitude_m": 60.0,
        "city": "pune", "drone_category": "Small", "atc_permission": True, "rpc_provided": True,
        "insurance_provided": True, "mavlink_signing_enabled": True, "maintenance_log_current": True,
        "drone_weight_kg": 6.0}


@pytest.fixture(autouse=True)
def _clean():
    from aerofleet.data.database import get_db_session
    from aerofleet.data.models.models import DroneRegistration, FlightReview, MissionRecord, ParamSnapshot

    with get_db_session() as db:
        for model in (MissionRecord, FlightReview, ParamSnapshot, DroneRegistration):
            db.query(model).delete()
        db.commit()
    yield


def _verify(api_client, headers, seq):
    entries = api_client.get("/api/v1/assurance/ledger", headers=headers).json()["entries"]
    return any(e["seq"] == seq for e in entries) and \
        api_client.get("/api/v1/assurance/ledger/verify", headers=headers).json()["ok"] is True


def test_pre_flight_reads_the_uin_from_the_registry_and_is_signed(api_client, auth_headers, operator_headers):
    body = dict(PLAN, drone_id="PUNE-07", uin_registered=True)          # the typed-in claim must be ignored
    r = api_client.post("/api/v1/compliance/pre-flight", headers=auth_headers, json=body)
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["inputs"]["uin_source"] == "registry" and out["inputs"]["uin_status"] == "NONE"
    assert "uin_registered" not in out["inputs"]["operator_declared"] and "rpc_provided" in out["inputs"]["operator_declared"]
    assert out["attestation"]["ledger_seq"] >= 1 and len(out["attestation"]["entry_hash"]) == 64
    assert _verify(api_client, auth_headers, out["attestation"]["ledger_seq"])

    rec = api_client.put("/api/v1/fleet/registrations/PUNE-07", headers=operator_headers, json={"uin": "UA-0001-PUNE"})
    assert rec.status_code == 200, rec.text
    again = api_client.post("/api/v1/compliance/pre-flight", headers=auth_headers, json=dict(PLAN, drone_id="PUNE-07")).json()
    assert again["inputs"]["uin_status"] == "RECORDED"
    assert again["attestation"]["ledger_seq"] == out["attestation"]["ledger_seq"] + 1


def test_without_a_drone_the_uin_is_marked_as_operator_declared(api_client, auth_headers):
    out = api_client.post("/api/v1/compliance/pre-flight", headers=auth_headers, json=dict(PLAN, uin_registered=True)).json()
    assert out["inputs"]["uin_source"] == "operator-declared" and out["inputs"]["operator_declared"][0] == "uin_registered"


def test_generation_is_blocked_and_not_stored_when_compliance_fails(api_client, auth_headers):
    body = dict(PLAN, uin_registered=True, maintenance_log_current=False)
    out = api_client.post("/api/v1/missions/generate", headers=auth_headers, json=body).json()
    assert out["mission_file_generated"] is False and "document_checklist" in out["failing_domains"]
    assert api_client.get(f"/api/v1/missions/{out['mission_id']}/waypoints", headers=auth_headers).status_code == 404


def _generate(api_client, headers, **extra):
    r = api_client.post("/api/v1/missions/generate", headers=headers, json=dict(PLAN, uin_registered=True, **extra))
    assert r.status_code == 200, r.text
    return r.json()


def test_a_generated_mission_is_stored_signed_and_downloadable(api_client, auth_headers):
    out = _generate(api_client, auth_headers)
    assert out["mission_file_generated"], out.get("failing_domains")
    assert out["attestation"]["ledger_seq"] >= 1
    wpl = api_client.get(out["download_url"], headers=auth_headers)
    assert wpl.status_code == 200 and wpl.text.startswith("QGC WPL 110")

    from aerofleet.data.database import get_db_session
    from aerofleet.data.models.models import MissionRecord

    with get_db_session() as db:                                          # survives a restart: it is in the database
        row = db.get(MissionRecord, out["mission_id"])
        assert row is not None and row.ledger_seq == out["attestation"]["ledger_seq"]
    assert api_client.get("/api/v1/missions/MIS-NOPE/waypoints", headers=auth_headers).status_code == 404


def test_reconcile_runs_the_real_flight_review_against_the_stored_mission(api_client, auth_headers, operator_headers, tmp_path):
    import math

    from aerofleet.assurance.reconcile import parse_waypoints
    from tests.unit.test_assurance_flightlog import write_tlog

    api_client.put("/api/v1/fleet/registrations/PUNE-08", headers=operator_headers, json={"uin": "UA-0002-PUNE"})
    out = _generate(api_client, auth_headers, drone_id="PUNE-08")
    assert out["inputs"]["uin_status"] == "RECORDED"
    assert out["mission_file_generated"], out.get("failing_domains")
    wpl = api_client.get(out["download_url"], headers=auth_headers).text
    path = parse_waypoints(wpl).path
    track, t = [], 0.0
    for a, b in zip(path, path[1:]):
        steps = max(2, int(math.dist(a[:2], b[:2]) * 111_000 / 5))
        for i in range(steps):
            f = i / steps
            track.append((t, a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f, a[2] + (b[2] - a[2]) * f))
            t += 1.0
    log = write_tlog(str(tmp_path / "flown.tlog"), track, modes=[(0.0, 3)])
    r = api_client.post(f"/api/v1/missions/{out['mission_id']}/reconcile", headers=auth_headers,
                        files={"log_file": ("flown.tlog", open(log, "rb").read(), "application/octet-stream")})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["mission_id"] == out["mission_id"] and body["drone_id"] == "PUNE-08"
    assert body["verdict"] == "CONFORMED", body["report"]["episodes"]
    assert body["report"]["log"]["points"] == len(track) and "likely_causes" in body["report"]
    assert body["ledger_seq"] > out["attestation"]["ledger_seq"]
    assert "deviations" not in body                                       # the old hard-coded report is gone
