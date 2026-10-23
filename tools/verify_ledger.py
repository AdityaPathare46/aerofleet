#!/usr/bin/env python3
"""Check an AeroFleet signed record without AeroFleet: needs only Python 3 and the `cryptography` package.

    python verify_ledger.py aerofleet-signed-record.json [--heads ledger_heads.log] [--key-sha256 HEX]

The JSON file is what "Export for an auditor" saves: {"public_key_pem": ..., "entries": [oldest first]}.
Checks, in order: entries are numbered 1, 2, 3 ... with none missing; each links to the one before; each entry's
hash matches its contents; each signature is valid for the public key. Then, optionally:
  --key-sha256  the key fingerprint you were given earlier. A chain re-signed with a new key fails here.
  --heads       a copy of the heads file kept outside the operator's control. A rebuilt or truncated chain fails
                here, because heads recorded earlier are no longer in it.
What it cannot show: that the files uploaded were genuine (each record carries their SHA-256, so you can compare
with the originals), or that the machine's clock was right.
Exit code 0 if everything checked passes, 1 otherwise.
"""
import argparse
import base64
import hashlib
import json
import sys

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization

GENESIS = "0" * 64


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode()


def entry_hash(e):
    body = {k: e[k] for k in ("seq", "kind", "subject", "payload_sha256", "prev_hash", "created_at", "created_by")}
    return hashlib.sha256(canonical(body)).hexdigest()


def verify(export, heads=None, key_sha256=None):
    pem = export["public_key_pem"]
    problems = []
    fingerprint = hashlib.sha256(pem.strip().encode()).hexdigest()
    if key_sha256 and key_sha256.lower() != fingerprint:
        problems.append(f"The public key is not the one you were given (fingerprint {fingerprint[:16]}…)")
    public = serialization.load_pem_public_key(pem.encode())
    prev, expected = GENESIS, 1
    for e in export["entries"]:
        if e["seq"] != expected:
            problems.append(f"Entry {e['seq']}: expected entry {expected} (an entry is missing or out of order)")
            break
        if e["prev_hash"] != prev:
            problems.append(f"Entry {e['seq']}: does not link to the entry before it")
            break
        if entry_hash(e) != e["entry_hash"]:
            problems.append(f"Entry {e['seq']}: its contents do not match its hash (altered)")
            break
        try:
            public.verify(base64.b64decode(e["signature"]), bytes.fromhex(e["entry_hash"]))
        except (InvalidSignature, ValueError):
            problems.append(f"Entry {e['seq']}: signature not valid for this key")
            break
        prev, expected = e["entry_hash"], expected + 1
    if heads is not None:
        by_seq = {e["seq"]: e["entry_hash"] for e in export["entries"]}
        for h in heads:
            if by_seq.get(h["seq"]) != h["entry_hash"]:
                problems.append(f"Recorded head {h['seq']} is " + ("missing from the chain" if h["seq"] not in by_seq
                                                                   else "different in the chain (rebuilt or altered)"))
                break
    return {"ok": not problems, "entries": len(export["entries"]), "head": prev, "key_sha256": fingerprint, "problems": problems}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("export")
    ap.add_argument("--heads")
    ap.add_argument("--key-sha256")
    a = ap.parse_args(argv)
    export = json.load(open(a.export, encoding="utf-8"))
    heads = None
    if a.heads:
        heads = [json.loads(l) for l in open(a.heads, encoding="utf-8") if l.strip()]
    r = verify(export, heads, a.key_sha256)
    print(f"{r['entries']} entries · key fingerprint {r['key_sha256']} · head {r['head']}")
    print("OK: the record is intact" if r["ok"] else "FAILED:\n  " + "\n  ".join(r["problems"]))
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
