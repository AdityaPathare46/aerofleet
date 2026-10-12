"""The signed, hash-chained record of assurance results (aerofleet/assurance/ledger.py)."""
import pytest

pytestmark = pytest.mark.integration

URL = "/api/v1/assurance"
BASE = "FS_THR_ENABLE,1\nFENCE_ENABLE,1\nRTL_ALT,1500\n"


def _file(text):
    return {"file": ("x.param", text.encode(), "text/plain")}


@pytest.fixture(autouse=True)
def _clean():
    from aerofleet.data.database import get_db_session
    from aerofleet.data.models.models import AssuranceLedgerEntry, FleetBaseline, FlightReview, ParamSnapshot

    with get_db_session() as db:
        for model in (AssuranceLedgerEntry, FlightReview, ParamSnapshot, FleetBaseline):
            db.query(model).delete()
        db.commit()
    yield


def _three_entries(api_client, auth_headers, operator_headers):
    a = api_client.post(f"{URL}/fleets/led/baseline", headers=operator_headers, files=_file(BASE)).json()
    b = api_client.post(f"{URL}/fleets/led/drones/D1/params", headers=auth_headers, files=_file(BASE.replace("RTL_ALT,1500", "RTL_ALT,3000"))).json()
    c = api_client.post(f"{URL}/fleets/led/approvals", headers=operator_headers, json={"name": "RTL_ALT", "value": 3000, "note": "Tall trees at this site"}).json()
    return a, b, c


def test_every_recorded_result_gets_a_linked_signed_entry(api_client, auth_headers, operator_headers):
    a, b, c = _three_entries(api_client, auth_headers, operator_headers)
    assert (a["ledger_seq"], b["ledger_seq"], c["ledger_seq"]) == (1, 2, 3)
    led = api_client.get(f"{URL}/ledger", headers=auth_headers).json()
    newest, middle, oldest = led["entries"]
    assert [e["kind"] for e in (oldest, middle, newest)] == ["baseline", "drift", "approval"]
    assert oldest["prev_hash"] == "0" * 64 and middle["prev_hash"] == oldest["entry_hash"] and newest["prev_hash"] == middle["entry_hash"]
    assert middle["subject"] == "led/D1" and "BEGIN PUBLIC KEY" in led["public_key_pem"]
    v = api_client.get(f"{URL}/ledger/verify", headers=auth_headers).json()
    assert v == {"ok": True, "entries": 3, "head": newest["entry_hash"], "first_bad_seq": None, "problem": None}


def test_the_public_key_alone_verifies_and_the_recorded_report_is_the_one_returned(api_client, auth_headers, operator_headers):
    from aerofleet.assurance import ledger

    _, drift, _ = _three_entries(api_client, auth_headers, operator_headers)
    led = api_client.get(f"{URL}/ledger", headers=auth_headers).json()
    entries = list(reversed(led["entries"]))
    assert ledger.verify_entries(entries, led["public_key_pem"])["ok"] is True
    returned = {k: v for k, v in drift.items() if k not in ("ledger_seq", "file")}
    assert ledger.payload_hash(returned) == entries[1]["payload_sha256"]          # what the user saw is what was signed
    assert ledger.payload_hash(dict(returned, verdict="OK")) != entries[1]["payload_sha256"]


@pytest.mark.parametrize("tamper, expect", [
    (lambda row: setattr(row, "subject", "led/D9"), "contents do not match its hash"),
    (lambda row: setattr(row, "payload_sha256", "f" * 64), "contents do not match its hash"),
    (lambda row: setattr(row, "signature", "AAAA"), "signature is not valid"),
])
def test_altering_a_stored_entry_is_detected_and_located(api_client, auth_headers, operator_headers, tamper, expect):
    from aerofleet.data.database import get_db_session
    from aerofleet.data.models.models import AssuranceLedgerEntry

    _three_entries(api_client, auth_headers, operator_headers)
    with get_db_session() as db:
        tamper(db.get(AssuranceLedgerEntry, 2))
        db.commit()
    v = api_client.get(f"{URL}/ledger/verify", headers=auth_headers).json()
    assert v["ok"] is False and v["first_bad_seq"] == 2 and expect in v["problem"]


def test_deleting_an_entry_from_the_middle_is_detected(api_client, auth_headers, operator_headers):
    from aerofleet.data.database import get_db_session
    from aerofleet.data.models.models import AssuranceLedgerEntry

    _three_entries(api_client, auth_headers, operator_headers)
    with get_db_session() as db:
        db.delete(db.get(AssuranceLedgerEntry, 2))
        db.commit()
    v = api_client.get(f"{URL}/ledger/verify", headers=auth_headers).json()
    assert v["ok"] is False and v["first_bad_seq"] == 3 and "missing or out of order" in v["problem"]


def test_a_forged_entry_signed_with_another_key_fails(api_client, auth_headers, operator_headers):
    import base64

    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    from aerofleet.assurance import ledger

    _three_entries(api_client, auth_headers, operator_headers)
    led = api_client.get(f"{URL}/ledger", headers=auth_headers).json()
    entries = list(reversed(led["entries"]))
    forged = dict(entries[2], signature=base64.b64encode(Ed25519PrivateKey.generate().sign(bytes.fromhex(entries[2]["entry_hash"]))).decode())
    v = ledger.verify_entries(entries[:2] + [forged], led["public_key_pem"])
    assert v["ok"] is False and v["first_bad_seq"] == 3 and "signature is not valid" in v["problem"]


def test_the_signing_key_is_created_private_and_reads_need_a_login(api_client):
    import os
    import stat

    from aerofleet.assurance import ledger

    ledger.public_key_pem()
    assert stat.S_IMODE(os.stat(ledger.key_file()).st_mode) == 0o600
    assert api_client.get(f"{URL}/ledger").status_code == 401 and api_client.get(f"{URL}/ledger/verify").status_code == 401
