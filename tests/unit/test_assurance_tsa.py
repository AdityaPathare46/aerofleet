"""Offline, deterministic cryptographic tests for RFC 3161 trusted timestamping (aerofleet/assurance/tsa.py)."""
from __future__ import annotations

import base64
import copy
import hashlib
import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

from aerofleet.assurance import ledger, tsa

pytestmark = pytest.mark.unit
ROOT = Path(__file__).resolve().parents[2]


def _make_tsa_pki(include_eku: bool = True):
    """Build an ephemeral root CA and TSA signing certificate in memory."""
    now = datetime.now(timezone.utc)
    ca_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    ca_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "AeroFleet Test Root CA")])
    ca_cert = (
        x509.CertificateBuilder()
        .subject_name(ca_name).issuer_name(ca_name)
        .public_key(ca_key.public_key()).serial_number(100)
        .not_valid_before(now - timedelta(days=1)).not_valid_after(now + timedelta(days=30))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(ca_key, hashes.SHA256())
    )
    tsa_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    tsa_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "AeroFleet Test TSA")])
    builder = (
        x509.CertificateBuilder()
        .subject_name(tsa_name).issuer_name(ca_name)
        .public_key(tsa_key.public_key()).serial_number(200)
        .not_valid_before(now - timedelta(days=1)).not_valid_after(now + timedelta(days=30))
    )
    if include_eku:
        builder = builder.add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.TIME_STAMPING]), critical=True)
    tsa_cert = builder.sign(ca_key, hashes.SHA256())
    ca_pem = ca_cert.public_bytes(serialization.Encoding.PEM).decode("utf-8")
    return ca_cert, ca_pem, tsa_key, tsa_cert


def _sign_tsr(tsq: bytes, tsa_key, tsa_cert, gen_time: datetime | None = None,
              tamper_digest: bytes | None = None, ess: str = "v2", drop_nonce: bool = False) -> bytes:
    """Parse a DER TimeStampReq and produce a genuine RFC 3161 DER TimeStampResp signed by `tsa_key`."""
    _, req_body, _, _ = tsa._parse_tlv(tsq, 0)
    kids = tsa._children(req_body)
    mi_kids = tsa._children(kids[1][1])
    digest = tamper_digest if tamper_digest is not None else mi_kids[1][1]
    nonce = tsa._decode_int(kids[2][1]) if len(kids) > 2 and kids[2][0] == 0x02 and not drop_nonce else None

    gt = (gen_time or datetime.now(timezone.utc)).strftime("%Y%m%d%H%M%SZ").encode("ascii")
    alg_sha256 = tsa._tlv(0x30, tsa._der_oid(tsa.OID_SHA256) + tsa._tlv(0x05, b""))
    msg_imprint = tsa._tlv(0x30, alg_sha256 + tsa._tlv(0x04, digest))
    tst_parts = tsa._der_int(1) + tsa._der_oid("1.2.3.4") + msg_imprint + tsa._der_int(9991) + tsa._tlv(0x18, gt)
    if nonce is not None:
        tst_parts += tsa._der_int(nonce)
    tst_der = tsa._tlv(0x30, tst_parts)

    # Build CMS SignedData with signedAttrs carrying messageDigest = sha256(tst_der)
    cert_der = tsa_cert.public_bytes(serialization.Encoding.DER)
    ct_attr = tsa._tlv(0x30, tsa._der_oid(tsa.OID_CONTENT_TYPE) + tsa._tlv(0x31, tsa._der_oid(tsa.OID_TST_INFO)))
    md_attr = ct_attr + tsa._tlv(0x30, tsa._der_oid(tsa.OID_MESSAGE_DIGEST) + tsa._tlv(0x31, tsa._tlv(0x04, hashlib.sha256(tst_der).digest())))
    if ess != "none":
        named = cert_der if ess == "v2" else b"some other certificate"
        ess_id = tsa._tlv(0x30, tsa._tlv(0x04, hashlib.sha256(named).digest()))          # ESSCertIDv2, default SHA-256
        md_attr += tsa._tlv(0x30, tsa._der_oid(tsa.OID_SIGNING_CERT_V2) + tsa._tlv(0x31, tsa._tlv(0x30, tsa._tlv(0x30, ess_id))))
    sig = tsa_key.sign(tsa._tlv(0x31, md_attr), padding.PKCS1v15(), hashes.SHA256())

    issuer_der = tsa_cert.issuer.public_bytes()
    sid = tsa._tlv(0x30, issuer_der + tsa._der_int(tsa_cert.serial_number))
    sig_alg = tsa._tlv(0x30, tsa._der_oid(tsa.OID_RSA_ENCRYPTION) + tsa._tlv(0x05, b""))
    signer_info = tsa._tlv(0x30, tsa._der_int(1) + sid + alg_sha256 + tsa._tlv(0xA0, md_attr) + sig_alg + tsa._tlv(0x04, sig))

    eci = tsa._tlv(0x30, tsa._der_oid(tsa.OID_TST_INFO) + tsa._tlv(0xA0, tsa._tlv(0x04, tst_der)))
    signed_data = tsa._tlv(
        0x30,
        tsa._der_int(3) + tsa._tlv(0x31, alg_sha256) + eci + tsa._tlv(0xA0, cert_der) + tsa._tlv(0x31, signer_info),
    )
    token = tsa._tlv(0x30, tsa._der_oid(tsa.OID_SIGNED_DATA) + tsa._tlv(0xA0, signed_data))
    status_info = tsa._tlv(0x30, tsa._der_int(0))
    return tsa._tlv(0x30, status_info + token)


@pytest.fixture
def trust(monkeypatch):
    """Trust one test CA as if it were in data/tsa_roots.pem, and allow its URL."""
    def _trust(ca_pem: str, url: str = "http://test.tsa"):
        monkeypatch.setattr(tsa, "trusted_roots_pem", lambda: ca_pem)
        monkeypatch.setattr(tsa, "ALLOWED_TSA_URLS", frozenset({url}))
    return _trust


def test_a_token_from_a_self_made_ca_is_rejected(trust):
    """C2 (critical review 27 Nov 2026): a certificate embedded in the token proves nothing on its own."""
    _, _, forger_key, forger_cert = _make_tsa_pki()              # the forger's own CA, not trusted
    _, real_ca_pem, _, _ = _make_tsa_pki()
    trust(real_ca_pem)
    digest = hashlib.sha256(b"backdated receipt").digest()
    tsq, nonce = tsa.build_tsq(digest)
    forged = _sign_tsr(tsq, forger_key, forger_cert, gen_time=datetime.now(timezone.utc) - timedelta(hours=20))
    r = tsa.verify_tsr(forged, digest, expected_nonce=nonce)
    assert r["ok"] is False and "trusted root" in r["problem"]
    with pytest.raises(tsa.TSAError):
        tsa.request_timestamp(digest, tsa_url="http://test.tsa", post=lambda _u, q: _sign_tsr(q, forger_key, forger_cert))


def test_pinned_roots_file_loads_and_default_url_is_allowed():
    roots = x509.load_pem_x509_certificates(tsa.trusted_roots_pem().encode())
    assert any("DigiCert Trusted Root G4" in c.subject.rfc4514_string() for c in roots)
    assert tsa.DEFAULT_TSA_URL in tsa.ALLOWED_TSA_URLS
    with pytest.raises(tsa.TSAError):
        tsa.check_tsa_url("http://169.254.169.254/latest/meta-data")


def test_ess_binding_nonce_and_signed_attributes_are_required(trust):
    _, ca_pem, key, cert = _make_tsa_pki()
    trust(ca_pem)
    digest = hashlib.sha256(b"x").digest()
    tsq, nonce = tsa.build_tsq(digest)
    assert tsa.verify_tsr(_sign_tsr(tsq, key, cert), digest, expected_nonce=nonce)["ok"] is True
    no_ess = tsa.verify_tsr(_sign_tsr(tsq, key, cert, ess="none"), digest, expected_nonce=nonce)
    assert no_ess["ok"] is False and "ESS" in no_ess["problem"]
    wrong_ess = tsa.verify_tsr(_sign_tsr(tsq, key, cert, ess="wrong"), digest, expected_nonce=nonce)
    assert wrong_ess["ok"] is False and "ESS" in wrong_ess["problem"]
    no_nonce = tsa.verify_tsr(_sign_tsr(tsq, key, cert, drop_nonce=True), digest, expected_nonce=nonce)
    assert no_nonce["ok"] is False and "nonce" in no_nonce["problem"]


def test_rfc3161_request_and_verification_roundtrip_and_tamper_detection(trust):
    _, ca_pem, tsa_key, tsa_cert = _make_tsa_pki()
    trust(ca_pem)
    digest = hashlib.sha256(b"aerofleet-receipt-payload").digest()

    res = tsa.request_timestamp(digest, tsa_url="http://test.tsa", post=lambda _u, q: _sign_tsr(q, tsa_key, tsa_cert))
    assert res["standard"] == "RFC3161" and "AeroFleet Test TSA" in res["tsa_subject"]
    tsr = base64.b64decode(res["tsr_b64"])

    ok = tsa.verify_tsr(tsr, digest, expected_nonce=res["nonce"])
    assert ok["ok"] is True and ok["ca_verified"] is True

    # Wrong digest -> rejected
    bad_digest = tsa.verify_tsr(tsr, hashlib.sha256(b"different").digest())
    assert bad_digest["ok"] is False and "does not match" in bad_digest["problem"]

    # Wrong CA -> rejected
    _, other_ca_pem, _, _ = _make_tsa_pki()
    bad_ca = tsa.verify_tsr(tsr, digest, ca_pem=other_ca_pem)
    assert bad_ca["ok"] is False and "chain" in bad_ca["problem"]

    # Flip a byte inside the signature -> invalid cryptographic signature
    corrupted = bytearray(tsr)
    corrupted[-5] ^= 0xFF
    bad_sig = tsa.verify_tsr(bytes(corrupted), digest)
    assert bad_sig["ok"] is False

    # Missing timeStamping EKU -> rejected
    _, _, bad_key, bad_cert = _make_tsa_pki(include_eku=False)
    tsq, nonce = tsa.build_tsq(digest)
    bad_eku = tsa.verify_tsr(_sign_tsr(tsq, bad_key, bad_cert), digest, expected_nonce=nonce, ca_pem=_)
    assert bad_eku["ok"] is False and "ExtendedKeyUsage" in bad_eku["problem"]


def test_ledger_receipt_and_standalone_cli_verify_rfc3161_tokens(trust):
    _, ca_pem, tsa_key, tsa_cert = _make_tsa_pki()
    trust(ca_pem)
    pem = ledger.public_key_pem()
    entry_hash = ledger._entry_hash(1, "drift", "f/D1", "a" * 64, ledger.GENESIS, "2026-11-27T10:00:00", "op")
    entries = [{
        "seq": 1, "kind": "drift", "subject": "f/D1", "payload_sha256": "a" * 64,
        "prev_hash": ledger.GENESIS, "entry_hash": entry_hash,
        "signature": base64.b64encode(ledger._private_key().sign(bytes.fromhex(entry_hash))).decode(),
        "created_at": "2026-11-27T10:00:00", "created_by": "op",
    }]
    body = {"aerofleet_receipt": 1, "seq": 1, "entry_hash": entry_hash, "entry_created_at": "2026-11-27T10:00:00",
            "issued_at": "2026-11-27T10:05:00", "key_sha256": ledger.key_fingerprint(pem)}
    digest = hashlib.sha256(ledger.canonical(body)).digest()
    receipt = {
        **body,
        "signature": base64.b64encode(ledger._private_key().sign(digest)).decode(),
        "tsa": tsa.request_timestamp(digest, tsa_url="http://test.tsa", post=lambda _u, q: _sign_tsr(q, tsa_key, tsa_cert)),
    }

    ok = ledger.check_receipt(entries, pem, receipt)
    assert ok["ok"] is True and ok["tsa"]["ca_verified"] is True and "RFC 3161 TSA" in ok["meaning"]

    # Standalone verifier CLI module checks it identically
    spec = importlib.util.spec_from_file_location("verify_ledger", ROOT / "tools" / "verify_ledger.py")
    tool = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tool)
    export = {"public_key_pem": pem, "entries": entries}
    cli_ok = tool.verify(export, receipts=[receipt], tsa_ca_pem=ca_pem)
    assert cli_ok["ok"] is True and len(cli_ok["tsa_verified"]) == 1 and cli_ok["tsa_verified"][0]["ca_verified"] is True

    # Swapping in a TSA token minted for another digest is caught even if Ed25519 receipt sig is valid
    swapped = copy.deepcopy(receipt)
    swapped["tsa"] = tsa.request_timestamp(hashlib.sha256(b"other").digest(), tsa_url="http://test.tsa",
                                           post=lambda _u, q: _sign_tsr(q, tsa_key, tsa_cert))
    assert ledger.check_receipt(entries, pem, swapped)["ok"] is False
    assert tool.verify(export, receipts=[swapped])["ok"] is False
