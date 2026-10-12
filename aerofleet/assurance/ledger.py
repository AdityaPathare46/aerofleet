"""A signed, hash-chained record of every assurance result — so later edits are detectable.

Each entry stores the SHA-256 of the report it covers and the hash of the entry before it, and is signed
with this install's Ed25519 key. Changing a stored report, changing an entry, or deleting one from the
middle breaks the chain or a signature, and `verify_chain` says where. Anyone holding the public key can
check signatures without access to this machine.

What this is and is not: it is tamper-EVIDENT. It does not prove the uploaded inputs were genuine, and
someone with the private key and the database could rebuild the whole chain — keeping a copy of the
latest entry hash somewhere else (an email, a printout) closes that gap. No trusted hardware is involved.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from sqlalchemy.orm import Session

from aerofleet.api.secret_key import default_key_file
from aerofleet.data.models.models import AssuranceLedgerEntry

GENESIS = "0" * 64
_key: Optional[Ed25519PrivateKey] = None
_key_path: Optional[Path] = None


def key_file() -> Path:
    override = os.environ.get("AEROFLEET_REPORT_KEY_FILE")
    return Path(override) if override else default_key_file().with_name("report_signing_key.pem")


def _private_key() -> Ed25519PrivateKey:
    global _key, _key_path
    path = key_file()
    if _key is not None and _key_path == path:
        return _key
    try:
        key = serialization.load_pem_private_key(path.read_bytes(), password=None)
    except FileNotFoundError:
        key = Ed25519PrivateKey.generate()
        path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(path.with_suffix(".tmp"), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
        os.replace(path.with_suffix(".tmp"), path)
    _key, _key_path = key, path
    return key


def public_key_pem() -> str:
    return _private_key().public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode()


def canonical(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode()


def payload_hash(payload: Any) -> str:
    return hashlib.sha256(canonical(payload)).hexdigest()


def _entry_hash(seq: int, kind: str, subject: str, payload_sha256: str, prev_hash: str, created_at: str, created_by: str) -> str:
    body = {"seq": seq, "kind": kind, "subject": subject, "payload_sha256": payload_sha256, "prev_hash": prev_hash,
            "created_at": created_at, "created_by": created_by}
    return hashlib.sha256(canonical(body)).hexdigest()


def append(db: Session, kind: str, subject: str, payload: Any, created_by: str) -> AssuranceLedgerEntry:
    """Add one entry for `payload` (not committed here: it commits with the result it records)."""
    last = db.query(AssuranceLedgerEntry).order_by(AssuranceLedgerEntry.seq.desc()).first()
    seq, prev = (last.seq + 1, last.entry_hash) if last else (1, GENESIS)
    created_at = datetime.utcnow().replace(microsecond=0).isoformat()
    digest = payload_hash(payload)
    entry_hash = _entry_hash(seq, kind, subject, digest, prev, created_at, created_by)
    row = AssuranceLedgerEntry(seq=seq, kind=kind, subject=subject, payload_sha256=digest, prev_hash=prev, entry_hash=entry_hash,
                               signature=base64.b64encode(_private_key().sign(bytes.fromhex(entry_hash))).decode(),
                               created_at=created_at, created_by=created_by)
    db.add(row)
    db.flush()
    return row


def to_dict(row: AssuranceLedgerEntry) -> Dict[str, Any]:
    return {"seq": row.seq, "kind": row.kind, "subject": row.subject, "payload_sha256": row.payload_sha256, "prev_hash": row.prev_hash,
            "entry_hash": row.entry_hash, "signature": row.signature, "created_at": row.created_at, "created_by": row.created_by}


def verify_entries(entries: List[Dict[str, Any]], public_pem: str) -> Dict[str, Any]:
    """Check a list of entries (oldest first) with nothing but the public key."""
    public: Ed25519PublicKey = serialization.load_pem_public_key(public_pem.encode())
    prev, expected_seq = GENESIS, 1
    for e in entries:
        problem = None
        if e["seq"] != expected_seq:
            problem = f"expected entry {expected_seq}, found {e['seq']} (an entry is missing or out of order)"
        elif e["prev_hash"] != prev:
            problem = "does not link to the entry before it"
        elif _entry_hash(e["seq"], e["kind"], e["subject"], e["payload_sha256"], e["prev_hash"], e["created_at"], e["created_by"]) != e["entry_hash"]:
            problem = "its contents do not match its hash (the entry was altered)"
        else:
            try:
                public.verify(base64.b64decode(e["signature"]), bytes.fromhex(e["entry_hash"]))
            except (InvalidSignature, ValueError):
                problem = "its signature is not valid for this install's key"
        if problem:
            return {"ok": False, "entries": len(entries), "first_bad_seq": e["seq"], "problem": f"Entry {e['seq']}: {problem}"}
        prev, expected_seq = e["entry_hash"], expected_seq + 1
    return {"ok": True, "entries": len(entries), "head": prev if entries else None, "first_bad_seq": None, "problem": None}


def verify_chain(db: Session) -> Dict[str, Any]:
    rows = db.query(AssuranceLedgerEntry).order_by(AssuranceLedgerEntry.seq).all()
    return verify_entries([to_dict(r) for r in rows], public_key_pem())


def matches(db: Session, seq: int, payload: Any) -> bool:
    """Is `payload` exactly what entry `seq` recorded?"""
    row = db.get(AssuranceLedgerEntry, seq)
    return row is not None and row.payload_sha256 == payload_hash(payload)
