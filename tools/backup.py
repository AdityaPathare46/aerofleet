#!/usr/bin/env python3
"""Back up an AeroFleet install: the database, the signing keys and the heads file, checked and fingerprinted.

Everything AeroFleet keeps (users, settings snapshots, flight reviews, spray forms, the signed record) is in one SQLite
file, and the record's signing key and heads file sit next to it. A laptop that dies takes all of it. This copies them
to a dated folder:

  * the database with SQLite's own online backup (safe while the app is running, unlike copying the file);
  * the signing key, the secret key and the heads file, if present;
  * MANIFEST.json with each file's SHA-256 and size, and the result of verifying the signed record in the COPY.

Keep backups somewhere else (a second drive, the guide's machine): the keys are secret, so never put them in git or a
shared folder. To restore, stop the app, copy the files back to the data folder (the manifest lists where each came
from) and start it again; Fleet Assurance > Check the record should say "Record intact".

    python tools/backup.py [--to FOLDER]          # default: ~/AeroFleet_backups/YYYY-MM-DD_HHMMSS
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def database_file() -> Path:
    from aerofleet.utils.config import get_config

    url = get_config().database.database_url
    if not url.startswith("sqlite:///") or url == "sqlite:///:memory:":
        raise SystemExit(f"Only a file SQLite database can be backed up this way (DATABASE_URL is {url.split(':')[0]})")
    return Path(url[len("sqlite:///"):])


def verify_copy(db_copy: Path):
    """Verify the signed record inside the backed-up database, with this install's public key."""
    from aerofleet.assurance import ledger

    con = sqlite3.connect(str(db_copy))
    con.row_factory = sqlite3.Row
    rows = con.execute("SELECT seq, kind, subject, payload_sha256, prev_hash, entry_hash, signature, created_at, created_by "
                       "FROM assurance_ledger ORDER BY seq").fetchall()
    con.close()
    return ledger.verify_entries([dict(r) for r in rows], ledger.public_key_pem())


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--to", default=None)
    a = ap.parse_args(argv)
    from aerofleet.api.secret_key import default_key_file
    from aerofleet.assurance import ledger

    out = Path(a.to or Path.home() / "AeroFleet_backups" / datetime.now().strftime("%Y-%m-%d_%H%M%S"))
    out.mkdir(parents=True, exist_ok=False)
    os.chmod(out, 0o700)
    db = database_file()
    files = {}
    src = sqlite3.connect(str(db))
    dst = sqlite3.connect(str(out / db.name))
    with dst:
        src.backup(dst)                              # consistent copy even while the API is writing
    src.close()
    dst.close()
    os.chmod(out / db.name, 0o600)
    files[db.name] = str(db)
    for p in (ledger.key_file(), default_key_file(), ledger.heads_file()):
        if p.exists():
            shutil.copy2(p, out / p.name)
            os.chmod(out / p.name, 0o600)
            files[p.name] = str(p)
    check = verify_copy(out / db.name)
    manifest = {"made": datetime.now().isoformat(timespec="seconds"), "files": {
        name: {"from": origin, "sha256": sha256(out / name), "bytes": (out / name).stat().st_size} for name, origin in files.items()},
        "signed_record_in_copy": {"ok": check["ok"], "entries": check["entries"], "problem": check["problem"]}}
    (out / "MANIFEST.json").write_text(json.dumps(manifest, indent=1))
    print(f"Backed up {len(files)} files to {out}")
    print(f"Signed record in the copy: {'intact' if check['ok'] else 'PROBLEM: ' + str(check['problem'])} ({check['entries']} entries)")
    return 0 if check["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
