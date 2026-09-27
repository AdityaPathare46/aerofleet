"""The key AeroFleet signs login tokens with — never a value published in the repo.

Resolution order:
  1. AEROFLEET_SECRET_KEY (or SECRET_KEY) environment variable — deployments, CI, tests.
  2. `secret_key` from config, if it isn't one of the placeholder strings the repo ships.
  3. A random 256-bit key generated once per install and kept in the user's config
     directory (owner-only permissions), then reused on every start.

Previously every install signed with a constant committed to the repository (and the
config placeholder was never even read), so anyone could forge a login for any user.
"""
from __future__ import annotations

import os
import secrets
import sys
from pathlib import Path
from typing import Optional

from aerofleet.utils.logging import get_logger

logger = get_logger(__name__)

MIN_LENGTH = 32

# Values that have appeared in this repo and must never be used to sign anything.
PUBLISHED_PLACEHOLDERS = frozenset({
    "",
    "development-secret-key-change-in-production",
    "your-secret-key-here-change-in-production",
    "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7",
})


def default_key_file() -> Path:
    override = os.environ.get("AEROFLEET_SECRET_KEY_FILE")
    if override:
        return Path(override)
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "AeroFleet" / "jwt_secret"


def _usable(value: Optional[str]) -> bool:
    return bool(value) and value not in PUBLISHED_PLACEHOLDERS and len(value) >= MIN_LENGTH


def _read_or_create(path: Path) -> str:
    try:
        existing = path.read_text().strip()
        if _usable(existing):
            return existing
    except FileNotFoundError:
        pass
    key = secrets.token_hex(32)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(key)
    os.replace(tmp, path)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass  # Windows: the per-user AppData directory is already private to the account
    logger.info(f"Generated a new per-install token signing key at {path}")
    return key


def resolve_secret_key(config_value: Optional[str] = None, key_file: Optional[Path] = None) -> str:
    for env in ("AEROFLEET_SECRET_KEY", "SECRET_KEY"):
        value = os.environ.get(env)
        if value:
            if _usable(value):
                return value
            logger.warning(f"Ignoring {env}: it is a published placeholder or shorter than {MIN_LENGTH} characters")
    if _usable(config_value):
        return config_value  # type: ignore[return-value]
    return _read_or_create(key_file or default_key_file())
