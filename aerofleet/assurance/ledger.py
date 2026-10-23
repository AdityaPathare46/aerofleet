"""A signed, hash-chained record of every assurance result — so later edits are detectable.

Each entry stores the SHA-256 of the report it covers and the hash of the entry before it, and is signed
with this install's Ed25519 key. Changing a stored report, changing an entry, or deleting one from the
middle breaks the chain or a signature, and `verify_chain` says where. Anyone holding the public key can
check signatures without access to this machine.

What this is and is not: it is tamper-EVIDENT. It does not prove the uploaded inputs were genuine (each
record carries the SHA-256 of the raw files it came from, so a later swap of a file is detectable, but a file
edited before upload is not), and someone with the private key and the database could rebuild the whole chain.
To close that last gap, every committed head is appended to a separate heads file (`heads_file()`); a copy of
that file kept by someone else (an auditor, an e-mail, a printout) shows any rebuilt chain, because the old
heads will no longer be in it. Timestamps come from this machine's clock. No trusted hardware is involved.
The standalone checker `tools/verify_ledger.py` needs only Python and the `cryptography` package.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import threading
import time

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from sqlalchemy import event
from sqlalchemy.exc import IntegrityError, OperationalError
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


def heads_file() -> Path:
    override = os.environ.get("AEROFLEET_LEDGER_HEADS_FILE")
    return Path(override) if override else key_file().with_name("ledger_heads.log")


def file_fingerprint(name: Optional[str], data: bytes) -> Dict[str, Any]:
    """What a record says about one uploaded file: its name, size and SHA-256 of the exact bytes received."""
    return {"name": (name or "")[:200], "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def payload_hash(payload: Any) -> str:
    return hashlib.sha256(canonical(payload)).hexdigest()


def _entry_hash(seq: int, kind: str, subject: str, payload_sha256: str, prev_hash: str, created_at: str, created_by: str) -> str:
    body = {"seq": seq, "kind": kind, "subject": subject, "payload_sha256": payload_sha256, "prev_hash": prev_hash,
            "created_at": created_at, "created_by": created_by}
    return hashlib.sha256(canonical(body)).hexdigest()


def append(db: Session, kind: str, subject: str, payload: Any, created_by: str) -> AssuranceLedgerEntry:
    """Add one entry for `payload` (not committed here: it commits with the result it records).

    The sequence number is the table's primary key, so two writers can never both take the same number.
    If another writer got there first, this one retries on the new head inside a savepoint, so the
    caller's other pending changes are kept.
    """
    digest = payload_hash(payload)
    for attempt in range(8):
        last = db.query(AssuranceLedgerEntry).order_by(AssuranceLedgerEntry.seq.desc()).first()
        seq, prev = (last.seq + 1, last.entry_hash) if last else (1, GENESIS)
        created_at = datetime.utcnow().replace(microsecond=0).isoformat()
        entry_hash = _entry_hash(seq, kind, subject, digest, prev, created_at, created_by)
        row = AssuranceLedgerEntry(seq=seq, kind=kind, subject=subject, payload_sha256=digest, prev_hash=prev, entry_hash=entry_hash,
                                   signature=base64.b64encode(_private_key().sign(bytes.fromhex(entry_hash))).decode(),
                                   created_at=created_at, created_by=created_by)
        try:
            with db.begin_nested():
                db.add(row)
                db.flush()
        except (IntegrityError, OperationalError):
            db.expire_all()
            time.sleep(0.05 * (attempt + 1))
            continue
        db.info.setdefault("ledger_heads", []).append({"seq": seq, "entry_hash": entry_hash, "created_at": created_at})
        return row
    raise RuntimeError("Could not append to the signed record: it kept changing underneath (too many concurrent writers)")


_heads_lock = threading.Lock()


@event.listens_for(Session, "after_commit")
def _write_heads(session: Session) -> None:
    """Only heads that were really committed go to the heads file (append-only, one JSON line each)."""
    heads = session.info.pop("ledger_heads", None)
    if not heads:
        return
    path = heads_file()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with _heads_lock, open(path, "a", encoding="utf-8") as f:
            for h in heads:
                f.write(json.dumps({**h, "written_at": datetime.utcnow().replace(microsecond=0).isoformat()}, sort_keys=True) + "\n")
    except OSError:
        pass                                       # the record itself is committed; the heads file is a convenience copy


@event.listens_for(Session, "after_rollback")
def _drop_heads(session: Session) -> None:
    session.info.pop("ledger_heads", None)


def read_heads(text: str) -> List[Dict[str, Any]]:
    out = []
    for line in text.splitlines():
        line = line.strip()
        if line:
            try:
                out.append(json.loads(line))
            except ValueError:
                continue
    return out


def check_heads(entries: List[Dict[str, Any]], heads: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Is every head recorded earlier still in the chain, unchanged? A rebuilt or truncated chain fails here."""
    by_seq = {e["seq"]: e["entry_hash"] for e in entries}
    for h in heads:
        if by_seq.get(h["seq"]) != h["entry_hash"]:
            return {"ok": False, "heads_checked": len(heads), "problem": f"Recorded head {h['seq']} ({h['entry_hash'][:12]}…) "
                    + ("is missing from the chain" if h["seq"] not in by_seq else "does not match the chain: it was rebuilt or altered")}
    return {"ok": True, "heads_checked": len(heads), "problem": None}


def key_fingerprint(public_pem: str) -> str:
    return hashlib.sha256(public_pem.strip().encode()).hexdigest()


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
