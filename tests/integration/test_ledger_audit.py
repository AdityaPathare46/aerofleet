"""Audit features of the signed record: raw-file fingerprints, the heads file, the standalone verifier and
concurrent writers."""
import base64
import copy
import hashlib
import importlib.util
import json
import threading
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

URL = "/api/v1/assurance"
BASE = "FS_THR_ENABLE,1\nFENCE_ENABLE,1\nRTL_ALT,1500\n"
ROOT = Path(__file__).resolve().parents[2]


def _tool():
    spec = importlib.util.spec_from_file_location("verify_ledger", ROOT / "tools" / "verify_ledger.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(autouse=True)
def _clean(tmp_path, monkeypatch):
    from aerofleet.data.database import get_db_session
    from aerofleet.data.models.models import AssuranceLedgerEntry, FleetBaseline, FlightReview, ParamSnapshot

    monkeypatch.setenv("AEROFLEET_LEDGER_HEADS_FILE", str(tmp_path / "heads.log"))
    with get_db_session() as db:
        for model in (AssuranceLedgerEntry, FlightReview, ParamSnapshot, FleetBaseline):
            db.query(model).delete()
        db.commit()
    yield


def _export(api_client, headers):
    led = api_client.get(f"{URL}/ledger?limit=1000", headers=headers).json()
    return {"public_key_pem": led["public_key_pem"], "entries": sorted(led["entries"], key=lambda e: e["seq"])}


def _make_three(api_client, auth_headers, operator_headers):
    raw = BASE.encode()
    api_client.post(f"{URL}/fleets/aud/baseline", headers=operator_headers, files={"file": ("golden.param", raw, "text/plain")})
    up = api_client.post(f"{URL}/fleets/aud/drones/D1/params", headers=auth_headers,
                         files={"file": ("d1.param", BASE.replace("1500", "3000").encode(), "text/plain")}).json()
    api_client.post(f"{URL}/fleets/aud/approvals", headers=operator_headers, json={"name": "RTL_ALT", "value": 3000, "note": "Tall trees"})
    return up


def test_records_carry_the_sha256_of_the_exact_files_received(api_client, auth_headers, operator_headers, tmp_path):
    up = _make_three(api_client, auth_headers, operator_headers)
    expected = hashlib.sha256(BASE.replace("1500", "3000").encode()).hexdigest()
    assert up["input_file"] == {"name": "d1.param", "bytes": len(BASE.replace("1500", "3000").encode()), "sha256": expected}

    from tests.integration.test_assurance_api import _flight_files

    files = _flight_files(tmp_path)
    review = api_client.post(f"{URL}/fleets/aud/drones/D2/flights", headers=auth_headers, files=files).json()
    assert review["report"]["input_files"]["log"]["sha256"] == hashlib.sha256(files["log"][1]).hexdigest()
    assert review["report"]["input_files"]["plan"]["sha256"] == hashlib.sha256(files["plan"][1]).hexdigest()


def test_committed_heads_go_to_the_heads_file_and_match_the_head_endpoint(api_client, auth_headers, operator_headers, tmp_path):
    _make_three(api_client, auth_headers, operator_headers)
    lines = [json.loads(x) for x in (tmp_path / "heads.log").read_text().splitlines()]
    assert [h["seq"] for h in lines] == [1, 2, 3]
    head = api_client.get(f"{URL}/ledger/head", headers=auth_headers).json()
    assert head["seq"] == 3 and head["entry_hash"] == lines[-1]["entry_hash"] and len(head["public_key_sha256"]) == 64
    assert api_client.get(f"{URL}/ledger/verify", headers=auth_headers).json()["heads"]["ok"] is True


def test_a_failed_upload_writes_no_head(api_client, auth_headers, tmp_path):
    bad = api_client.post(f"{URL}/fleets/aud/drones/D1/params", headers=auth_headers, files={"file": ("x.bin", b"\x00\x01binary", "application/octet-stream")})
    assert bad.status_code == 422 and not (tmp_path / "heads.log").exists()


def test_the_standalone_verifier_passes_an_intact_record_and_catches_four_kinds_of_tampering(api_client, auth_headers, operator_headers, tmp_path):
    _make_three(api_client, auth_headers, operator_headers)
    tool = _tool()
    export = _export(api_client, auth_headers)
    heads = [json.loads(x) for x in (tmp_path / "heads.log").read_text().splitlines()]
    pinned = hashlib.sha256(export["public_key_pem"].strip().encode()).hexdigest()
    assert tool.verify(export, heads, pinned)["ok"] is True

    flipped = copy.deepcopy(export)
    flipped["entries"][1]["subject"] = "aud/D9"                                  # one field edited
    assert "altered" in tool.verify(flipped)["problems"][0]

    deleted = copy.deepcopy(export)
    del deleted["entries"][1]
    assert "missing or out of order" in tool.verify(deleted)["problems"][0]

    reordered = copy.deepcopy(export)
    reordered["entries"][0], reordered["entries"][1] = reordered["entries"][1], reordered["entries"][0]
    assert tool.verify(reordered)["ok"] is False

    # The whole chain rebuilt with a new key passes the chain checks on its own - and fails on the pinned key
    # fingerprint and the heads kept elsewhere. This is why the heads file should be copied off the machine.
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    key = Ed25519PrivateKey.generate()
    rebuilt = copy.deepcopy(export)
    rebuilt["public_key_pem"] = key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode()
    prev = "0" * 64
    for e in rebuilt["entries"]:
        e["created_at"] = "2030-01-01T00:00:00"
        e["prev_hash"] = prev
        e["entry_hash"] = tool.entry_hash(e)
        e["signature"] = base64.b64encode(key.sign(bytes.fromhex(e["entry_hash"]))).decode()
        prev = e["entry_hash"]
    assert tool.verify(rebuilt)["ok"] is True
    result = tool.verify(rebuilt, heads, pinned)
    assert result["ok"] is False and len(result["problems"]) == 2


def test_the_command_line_exit_code(api_client, auth_headers, operator_headers, tmp_path):
    _make_three(api_client, auth_headers, operator_headers)
    path = tmp_path / "export.json"
    path.write_text(json.dumps(_export(api_client, auth_headers)))
    tool = _tool()
    assert tool.main([str(path), "--heads", str(tmp_path / "heads.log")]) == 0
    broken = json.loads(path.read_text())
    broken["entries"][0]["kind"] = "edited"
    path.write_text(json.dumps(broken))
    assert tool.main([str(path)]) == 1


def test_concurrent_writers_get_distinct_numbers_and_one_valid_chain():
    from aerofleet.assurance import ledger
    from aerofleet.data.database import get_db_session

    errors = []

    def write(i):
        try:
            with get_db_session() as db:
                ledger.append(db, "test", f"w{i}", {"i": i}, "tester")
                db.commit()
        except Exception as e:  # noqa: BLE001
            errors.append(repr(e))

    threads = [threading.Thread(target=write, args=(i,)) for i in range(12)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == []
    with get_db_session() as db:
        result = ledger.verify_chain(db)
    assert result["ok"] is True and result["entries"] == 12
