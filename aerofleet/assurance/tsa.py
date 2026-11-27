"""RFC 3161 trusted timestamping for AeroFleet ledger receipts.

Why: an operator controls both their laptop's private key and its local clock. Handing a signed receipt
to an auditor stops chain rewriting after that handover, while attaching an RFC 3161 Time-Stamp Token
proves cryptographically — via an independent Time-Stamping Authority (TSA) — that the receipt's exact
SHA-256 digest existed at or before the TSA's signed UTC time (`genTime`).

Privacy: only the 32-byte SHA-256 hash of the receipt leaves the machine. No flight logs, locations,
UINs, or parameters are ever sent to the TSA.

Pure Python + `cryptography` (no extra runtime dependencies, no ML/AI libraries).
"""
from __future__ import annotations

import base64
import hashlib
import os
import secrets
import urllib.request
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec, padding, rsa
from cryptography.x509.oid import ExtendedKeyUsageOID

DEFAULT_TSA_URL = "http://timestamp.digicert.com"
OID_SHA256 = "2.16.840.1.101.3.4.2.1"
OID_SHA384 = "2.16.840.1.101.3.4.2.2"
OID_SHA512 = "2.16.840.1.101.3.4.2.3"
OID_SIGNED_DATA = "1.2.840.113549.1.7.2"
OID_TST_INFO = "1.2.840.113549.1.9.16.1.4"
OID_MESSAGE_DIGEST = "1.2.840.113549.1.9.4"
OID_RSA_ENCRYPTION = "1.2.840.113549.1.1.1"
OID_SHA256_RSA = "1.2.840.113549.1.1.11"
OID_SHA384_RSA = "1.2.840.113549.1.1.12"
OID_SHA512_RSA = "1.2.840.113549.1.1.13"
OID_ECDSA_SHA256 = "1.2.840.10045.4.3.2"
OID_ECDSA_SHA384 = "1.2.840.10045.4.3.3"
OID_ECDSA_SHA512 = "1.2.840.10045.4.3.4"

HASH_BY_OID = {
    OID_SHA256: (hashlib.sha256, hashes.SHA256()),
    OID_SHA384: (hashlib.sha384, hashes.SHA384()),
    OID_SHA512: (hashlib.sha512, hashes.SHA512()),
    OID_SHA256_RSA: (hashlib.sha256, hashes.SHA256()),
    OID_SHA384_RSA: (hashlib.sha384, hashes.SHA384()),
    OID_SHA512_RSA: (hashlib.sha512, hashes.SHA512()),
    OID_ECDSA_SHA256: (hashlib.sha256, hashes.SHA256()),
    OID_ECDSA_SHA384: (hashlib.sha384, hashes.SHA384()),
    OID_ECDSA_SHA512: (hashlib.sha512, hashes.SHA512()),
}


class TSAError(RuntimeError):
    """Raised when a TSA cannot be reached or returns an invalid RFC 3161 response."""


# ── Minimal ASN.1 DER encoder / decoder ──────────────────────────────────────

def _der_len(n: int) -> bytes:
    if n < 0x80:
        return bytes([n])
    b = n.to_bytes((n.bit_length() + 7) // 8, "big")
    return bytes([0x80 | len(b)]) + b


def _tlv(tag: int, body: bytes) -> bytes:
    return bytes([tag]) + _der_len(len(body)) + body


def _der_int(v: int) -> bytes:
    if v == 0:
        return _tlv(0x02, b"\x00")
    b = v.to_bytes((v.bit_length() + 8) // 8, "big", signed=False)
    if b[0] & 0x80:
        b = b"\x00" + b
    return _tlv(0x02, b)


def _der_oid(oid: str) -> bytes:
    parts = [int(p) for p in oid.split(".")]
    out = bytearray([40 * parts[0] + parts[1]])
    for p in parts[2:]:
        if p == 0:
            out.append(0)
            continue
        chunks = []
        while p:
            chunks.append(p & 0x7F)
            p >>= 7
        for c in reversed(chunks[1:]):
            out.append(0x80 | c)
        out.append(chunks[0])
    return _tlv(0x06, bytes(out))


def _parse_tlv(data: bytes, pos: int = 0) -> Tuple[int, bytes, int, bytes]:
    """Return (tag, value_bytes, next_pos, full_raw_tlv)."""
    if pos >= len(data):
        raise ValueError("Truncated DER data")
    start = pos
    tag = data[pos]
    pos += 1
    if pos >= len(data):
        raise ValueError("Truncated DER length")
    first = data[pos]
    pos += 1
    if first == 0x80:
        # Indefinite-length BER encoding (some TSAs use BER for CMS SignedData): scan to EOC 00 00
        inner_start = pos
        while pos + 1 < len(data) and not (data[pos] == 0 and data[pos + 1] == 0):
            _, _, pos, _ = _parse_tlv(data, pos)
        if pos + 1 >= len(data):
            raise ValueError("Unterminated indefinite-length BER element")
        val = data[inner_start:pos]
        pos += 2
        return tag, val, pos, data[start:pos]
    if first < 0x80:
        length = first
    else:
        nlen = first & 0x7F
        if pos + nlen > len(data):
            raise ValueError("Truncated DER multi-byte length")
        length = int.from_bytes(data[pos:pos + nlen], "big")
        pos += nlen
    end = pos + length
    if end > len(data):
        raise ValueError("DER element exceeds buffer")
    return tag, data[pos:end], end, data[start:end]


def _children(body: bytes) -> List[Tuple[int, bytes, bytes]]:
    out, pos = [], 0
    while pos < len(body):
        tag, val, pos, raw = _parse_tlv(body, pos)
        out.append((tag, val, raw))
    return out


def _decode_oid(val: bytes) -> str:
    if not val:
        raise ValueError("Empty OID")
    out = [val[0] // 40, val[0] % 40]
    acc = 0
    for b in val[1:]:
        acc = (acc << 7) | (b & 0x7F)
        if not (b & 0x80):
            out.append(acc)
            acc = 0
    return ".".join(str(x) for x in out)


def _decode_int(val: bytes) -> int:
    return int.from_bytes(val, "big", signed=True)


def _decode_gentime(val: bytes) -> datetime:
    s = val.decode("ascii").rstrip("Z")
    if "." in s:
        base, frac = s.split(".", 1)
        frac = (frac + "000000")[:6]
        return datetime.strptime(f"{base}.{frac}", "%Y%m%d%H%M%S.%f").replace(tzinfo=timezone.utc)
    return datetime.strptime(s, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)


def _concat_octet_strings(tag: int, val: bytes) -> bytes:
    """Handle primitive (0x04) or constructed (0x24) OCTET STRING."""
    if tag == 0x04:
        return val
    if tag == 0x24:
        return b"".join(_concat_octet_strings(t, v) for t, v, _ in _children(val))
    raise ValueError(f"Expected OCTET STRING, got tag 0x{tag:02x}")


# ── RFC 3161 Request & Transport ─────────────────────────────────────────────

def build_tsq(digest_sha256: bytes, nonce: Optional[int] = None) -> Tuple[bytes, int]:
    """Build a DER-encoded RFC 3161 TimeStampReq for a 32-byte SHA-256 digest."""
    if len(digest_sha256) != 32:
        raise ValueError("digest_sha256 must be 32 bytes")
    if nonce is None:
        nonce = secrets.randbits(63) or 1
    alg_id = _tlv(0x30, _der_oid(OID_SHA256) + _tlv(0x05, b""))
    msg_imprint = _tlv(0x30, alg_id + _tlv(0x04, digest_sha256))
    req = _tlv(0x30, _der_int(1) + msg_imprint + _der_int(nonce) + _tlv(0x01, b"\xff"))
    return req, nonce


def _http_post_tsq(url: str, tsq: bytes, timeout: float = 15.0) -> bytes:
    req = urllib.request.Request(
        url, data=tsq, method="POST",
        headers={"Content-Type": "application/timestamp-query", "Accept": "application/timestamp-reply"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
        return resp.read()


def request_timestamp(digest_sha256: bytes, tsa_url: Optional[str] = None,
                      post: Callable[[str, bytes], bytes] = _http_post_tsq) -> Dict[str, Any]:
    """Request an RFC 3161 timestamp token for `digest_sha256` and verify it before returning."""
    url = tsa_url or os.environ.get("AEROFLEET_TSA_URL") or DEFAULT_TSA_URL
    tsq, nonce = build_tsq(digest_sha256)
    try:
        tsr = post(url, tsq)
    except Exception as e:
        raise TSAError(f"Could not reach timestamp authority ({url}): {e}") from None
    check = verify_tsr(tsr, digest_sha256, expected_nonce=nonce)
    if not check["ok"]:
        raise TSAError(f"Timestamp authority returned an invalid token: {check['problem']}")
    return {
        "standard": "RFC3161",
        "tsa_url": url,
        "nonce": nonce,
        "gen_time": check["gen_time"],
        "serial": check["serial"],
        "tsa_subject": check["tsa_subject"],
        "tsr_b64": base64.b64encode(tsr).decode("ascii"),
    }


# ── RFC 3161 Response / CMS SignedData Verification ──────────────────────────

def _parse_tst_info(tst_der: bytes) -> Dict[str, Any]:
    tag, body, _, _ = _parse_tlv(tst_der, 0)
    if tag != 0x30:
        raise ValueError("TSTInfo is not a SEQUENCE")
    kids = _children(body)
    if len(kids) < 5:
        raise ValueError("TSTInfo has too few fields")
    # version(0), policy(1), messageImprint(2), serialNumber(3), genTime(4), optional accuracy/ordering/nonce/...
    mi_kids = _children(kids[2][1])
    alg_kids = _children(mi_kids[0][1])
    hash_oid = _decode_oid(alg_kids[0][1])
    hashed_msg = mi_kids[1][1]
    serial = hex(_decode_int(kids[3][1]))
    gen_time = _decode_gentime(kids[4][1])
    nonce = None
    for t, v, _ in kids[5:]:
        if t == 0x02:
            nonce = _decode_int(v)
    return {"hash_oid": hash_oid, "hashed_message": hashed_msg, "serial": serial, "gen_time": gen_time, "nonce": nonce}


def _match_signer_cert(certs: List[x509.Certificate], sid_tag: int, sid_val: bytes) -> Optional[x509.Certificate]:
    if sid_tag == 0x30:  # IssuerAndSerialNumber
        parts = _children(sid_val)
        serial = _decode_int(parts[1][1])
        for c in certs:
            if c.serial_number == serial:
                return c
    elif sid_tag == 0x80:  # SubjectKeyIdentifier
        for c in certs:
            try:
                ski = c.extensions.get_extension_for_class(x509.SubjectKeyIdentifier).value.digest
                if ski == sid_val:
                    return c
            except x509.ExtensionNotFound:
                continue
    return certs[0] if certs else None


def _verify_cert_chain(leaf: x509.Certificate, all_certs: List[x509.Certificate], ca_pem: str) -> Optional[str]:
    """Verify leaf -> optional intermediates -> trusted CA certificate(s)."""
    trusted = x509.load_pem_x509_certificates(ca_pem.encode("utf-8"))
    if not trusted:
        return "CA bundle contains no certificates"
    pool = list(all_certs) + list(trusted)
    cur = leaf
    seen = {cur.fingerprint(hashes.SHA256())}
    for _ in range(8):
        for root in trusted:
            if cur.issuer == root.subject:
                try:
                    cur.verify_directly_issued_by(root)
                    return None
                except Exception:  # noqa: BLE001
                    pass
        nxt = None
        for cand in pool:
            fp = cand.fingerprint(hashes.SHA256())
            if fp not in seen and cur.issuer == cand.subject:
                try:
                    cur.verify_directly_issued_by(cand)
                    nxt = cand
                    seen.add(fp)
                    break
                except Exception:  # noqa: BLE001
                    continue
        if nxt is None:
            return "TSA signing certificate does not chain to the supplied CA certificate"
        cur = nxt
    return "TSA certificate chain exceeded maximum depth"


def verify_tsr(tsr_der: bytes, expected_digest_sha256: bytes, expected_nonce: Optional[int] = None,
               ca_pem: Optional[str] = None) -> Dict[str, Any]:
    """Verify an RFC 3161 DER TimeStampResp against `expected_digest_sha256`."""
    try:
        tag, resp_body, _, _ = _parse_tlv(tsr_der, 0)
        if tag != 0x30:
            return {"ok": False, "problem": "Not a DER TimeStampResp"}
        resp_kids = _children(resp_body)
        if len(resp_kids) < 2:
            return {"ok": False, "problem": "TSA response contains no TimeStampToken"}
        status_int = _decode_int(_children(resp_kids[0][1])[0][1])
        if status_int not in (0, 1):
            return {"ok": False, "problem": f"TSA rejected timestamp request (PKIStatus={status_int})"}

        # TimeStampToken ::= ContentInfo (SignedData)
        ci_kids = _children(resp_kids[1][1])
        if _decode_oid(ci_kids[0][1]) != OID_SIGNED_DATA:
            return {"ok": False, "problem": "TimeStampToken is not CMS SignedData"}
        _, sd_body, _, _ = _parse_tlv(ci_kids[1][1], 0)
        sd_kids = _children(sd_body)
        # SignedData: version(0), digestAlgorithms(1), encapContentInfo(2), [0]certs?, [1]crls?, signerInfos(last)
        eci_kids = _children(sd_kids[2][1])
        if _decode_oid(eci_kids[0][1]) != OID_TST_INFO:
            return {"ok": False, "problem": "CMS payload is not RFC 3161 TSTInfo"}
        ec_tag, ec_val, _, _ = _parse_tlv(eci_kids[1][1], 0)
        tst_der = _concat_octet_strings(ec_tag, ec_val)
        tst = _parse_tst_info(tst_der)

        if tst["hash_oid"] != OID_SHA256:
            return {"ok": False, "problem": f"Unsupported TSTInfo hash algorithm ({tst['hash_oid']})"}
        if tst["hashed_message"] != expected_digest_sha256:
            return {"ok": False, "problem": "Timestamp token digest does not match this receipt (receipt was edited or token is for another record)"}
        if expected_nonce is not None and tst["nonce"] is not None and tst["nonce"] != expected_nonce:
            return {"ok": False, "problem": "Timestamp token nonce does not match the request"}

        certs: List[x509.Certificate] = []
        signer_infos_body = None
        for t, v, _ in sd_kids[3:]:
            if t == 0xA0:
                for ct, _, craw in _children(v):
                    if ct == 0x30:
                        certs.append(x509.load_der_x509_certificate(craw))
            elif t == 0x31:
                signer_infos_body = v
        if not certs or signer_infos_body is None:
            return {"ok": False, "problem": "Timestamp token is missing its TSA signing certificate or signerInfo"}

        si_kids = _children(_children(signer_infos_body)[0][1])
        # SignerInfo: version(0), sid(1), digestAlgorithm(2), [0]signedAttrs?, signatureAlgorithm, signature
        sid_tag, sid_val, _ = si_kids[1]
        digest_oid = _decode_oid(_children(si_kids[2][1])[0][1])
        if digest_oid not in HASH_BY_OID:
            return {"ok": False, "problem": f"Unsupported CMS digest algorithm ({digest_oid})"}
        py_hash, crypto_hash = HASH_BY_OID[digest_oid]

        idx = 3
        signed_attrs_val = None
        if idx < len(si_kids) and si_kids[idx][0] == 0xA0:
            signed_attrs_val = si_kids[idx][1]
            idx += 1
        sig_alg_oid = _decode_oid(_children(si_kids[idx][1])[0][1])
        sig_bytes = si_kids[idx + 1][1]

        cert = _match_signer_cert(certs, sid_tag, sid_val)
        if cert is None:
            return {"ok": False, "problem": "Could not match TSA signer certificate"}

        # Check ExtendedKeyUsage includes id-kp-timeStamping and validity at genTime
        try:
            eku = cert.extensions.get_extension_for_class(x509.ExtendedKeyUsage).value
            if ExtendedKeyUsageOID.TIME_STAMPING not in eku:
                return {"ok": False, "problem": "Signing certificate does not carry the RFC 3161 timeStamping extended key usage"}
        except x509.ExtensionNotFound:
            return {"ok": False, "problem": "Signing certificate has no ExtendedKeyUsage extension"}
        if not (cert.not_valid_before_utc <= tst["gen_time"] <= cert.not_valid_after_utc):
            return {"ok": False, "problem": "TSA certificate was not valid at the token's genTime"}

        # Verify CMS signature
        if signed_attrs_val is not None:
            # Verify messageDigest attribute equals hash(tst_der)
            found_md = None
            for _, attr_body, _ in _children(signed_attrs_val):
                ak = _children(attr_body)
                if _decode_oid(ak[0][1]) == OID_MESSAGE_DIGEST:
                    found_md = _children(ak[1][1])[0][1]
                    break
            if found_md != py_hash(tst_der).digest():
                return {"ok": False, "problem": "CMS messageDigest attribute does not match TSTInfo (token altered)"}
            to_verify = _tlv(0x31, signed_attrs_val)
        else:
            to_verify = tst_der

        pub = cert.public_key()
        try:
            if isinstance(pub, rsa.RSAPublicKey):
                pub.verify(sig_bytes, to_verify, padding.PKCS1v15(), crypto_hash)
            elif isinstance(pub, ec.EllipticCurvePublicKey):
                pub.verify(sig_bytes, to_verify, ec.ECDSA(crypto_hash))
            else:
                return {"ok": False, "problem": f"Unsupported TSA public key type ({type(pub).__name__}, alg {sig_alg_oid})"}
        except InvalidSignature:
            return {"ok": False, "problem": "TSA cryptographic signature is not valid (timestamp token was altered or forged)"}

        ca_verified = False
        if ca_pem is not None:
            err = _verify_cert_chain(cert, certs, ca_pem)
            if err:
                return {"ok": False, "problem": err}
            ca_verified = True

        return {
            "ok": True,
            "problem": None,
            "gen_time": tst["gen_time"].isoformat().replace("+00:00", "Z"),
            "serial": tst["serial"],
            "tsa_subject": cert.subject.rfc4514_string(),
            "ca_verified": ca_verified,
        }
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "problem": f"Could not parse RFC 3161 timestamp token: {e}"}
