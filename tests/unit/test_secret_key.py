"""Token signing key resolution — never a value published in the repository."""
import os
import stat

import pytest

from aerofleet.api import secret_key as sk

pytestmark = pytest.mark.unit


@pytest.fixture
def no_env(monkeypatch):
    monkeypatch.delenv("AEROFLEET_SECRET_KEY", raising=False)
    monkeypatch.delenv("SECRET_KEY", raising=False)


def test_env_var_wins(monkeypatch, tmp_path):
    monkeypatch.setenv("AEROFLEET_SECRET_KEY", "x" * 40)
    assert sk.resolve_secret_key("y" * 40, key_file=tmp_path / "k") == "x" * 40


@pytest.mark.parametrize("placeholder", sorted(p for p in sk.PUBLISHED_PLACEHOLDERS if p))
def test_published_placeholders_are_never_used(no_env, tmp_path, monkeypatch, placeholder):
    monkeypatch.setenv("AEROFLEET_SECRET_KEY", placeholder)
    key = sk.resolve_secret_key(placeholder, key_file=tmp_path / "k")
    assert key not in sk.PUBLISHED_PLACEHOLDERS and len(key) == 64


def test_short_keys_are_rejected(no_env, tmp_path):
    assert sk.resolve_secret_key("too-short", key_file=tmp_path / "k") != "too-short"


def test_a_real_config_key_is_used(no_env, tmp_path):
    assert sk.resolve_secret_key("c" * 48, key_file=tmp_path / "k") == "c" * 48


def test_generated_key_is_random_persisted_private_and_reused(no_env, tmp_path):
    path = tmp_path / "AeroFleet" / "jwt_secret"
    first = sk.resolve_secret_key(None, key_file=path)
    assert len(first) == 64 and path.read_text() == first
    if os.name != "nt":
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert sk.resolve_secret_key(None, key_file=path) == first           # same key after a restart
    other = tmp_path / "other" / "jwt_secret"
    assert sk.resolve_secret_key(None, key_file=other) != first          # a different install differs


def test_a_corrupted_key_file_is_replaced(no_env, tmp_path):
    path = tmp_path / "jwt_secret"
    path.write_text("short")
    assert len(sk.resolve_secret_key(None, key_file=path)) == 64
