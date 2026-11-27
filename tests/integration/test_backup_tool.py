"""tools/backup.py: a consistent copy of the database and keys, with the signed record verified in the copy."""
import importlib.util
import json
import sqlite3
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration
ROOT = Path(__file__).resolve().parents[2]


def _tool():
    spec = importlib.util.spec_from_file_location("backup", ROOT / "tools" / "backup.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_backup_copies_files_and_verifies_the_record(api_client, auth_headers, operator_headers, tmp_path):
    from aerofleet.utils.config import get_config

    if not get_config().database.database_url.startswith("sqlite:///") or ":memory:" in get_config().database.database_url:
        pytest.skip("needs a file database")
    raw = b"FS_THR_ENABLE,1\nFENCE_ENABLE,1\n"
    api_client.post("/api/v1/assurance/fleets/bk/baseline", headers=operator_headers, files={"file": ("g.param", raw, "text/plain")})
    tool = _tool()
    out = tmp_path / "bk"
    assert tool.main(["--to", str(out)]) == 0
    manifest = json.loads((out / "MANIFEST.json").read_text())
    assert manifest["signed_record_in_copy"]["ok"] is True and manifest["signed_record_in_copy"]["entries"] >= 1
    db = next(p for p in out.iterdir() if p.suffix == ".db")
    assert manifest["files"][db.name]["sha256"] == tool.sha256(db)
    con = sqlite3.connect(str(db))                   # tamper with the copy: the check must notice
    con.execute("UPDATE assurance_ledger SET subject = 'edited' WHERE seq = 1")
    con.commit()
    con.close()
    assert tool.verify_copy(db)["ok"] is False
    with pytest.raises(FileExistsError):
        tool.main(["--to", str(out)])                # never overwrites an earlier backup
