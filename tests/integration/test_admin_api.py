"""Integration tests for aerofleet/api/routes/admin.py (Phase AI) — the
admin panel that replaces "grant is_operator via raw SQL" with a real,
auth-gated API surface.
"""
import uuid

import pytest

pytestmark = pytest.mark.integration


def _register(api_client, username=None):
    username = username or f"user_{uuid.uuid4().hex[:8]}"
    api_client.post(
        "/api/v1/auth/register",
        json={"username": username, "email": f"{username}@example.com", "password": "TestPass123!"},
    )
    return username


class TestListUsersRequiresAdmin:
    def test_anonymous_is_rejected(self, api_client):
        resp = api_client.get("/api/v1/admin/users")
        assert resp.status_code == 401

    def test_regular_active_user_is_rejected(self, api_client, auth_headers):
        resp = api_client.get("/api/v1/admin/users", headers=auth_headers)
        assert resp.status_code == 403

    def test_operator_without_admin_is_rejected(self, api_client, operator_headers):
        """is_operator (hardware control) must not double as admin access —
        the two are deliberately separate privilege types."""
        resp = api_client.get("/api/v1/admin/users", headers=operator_headers)
        assert resp.status_code == 403

    def test_admin_can_list_users(self, api_client, admin_headers):
        headers, _ = admin_headers
        _register(api_client)
        resp = api_client.get("/api/v1/admin/users", headers=headers)
        assert resp.status_code == 200
        users = resp.json()
        assert len(users) >= 2
        assert "hashed_password" not in users[0]
        assert "is_operator" in users[0] and "is_admin" in users[0]


class TestGrantOperator:
    def test_admin_can_grant_operator(self, api_client, admin_headers):
        headers, _ = admin_headers
        username = _register(api_client)

        listing = api_client.get("/api/v1/admin/users", headers=headers).json()
        target = next(u for u in listing if u["username"] == username)
        assert target["is_operator"] is False

        resp = api_client.patch(
            f"/api/v1/admin/users/{target['id']}", json={"is_operator": True}, headers=headers
        )
        assert resp.status_code == 200
        assert resp.json()["is_operator"] is True

        listing = api_client.get("/api/v1/admin/users", headers=headers).json()
        assert next(u for u in listing if u["id"] == target["id"])["is_operator"] is True

    def test_admin_can_revoke_operator(self, api_client, admin_headers, operator_headers):
        headers, _ = admin_headers
        # operator_headers already granted is_operator via the DB fixture;
        # confirm the admin endpoint can independently revoke it.
        me = api_client.get("/api/v1/auth/me", headers=operator_headers).json()
        resp = api_client.patch(
            f"/api/v1/admin/users/{me['id']}", json={"is_operator": False}, headers=headers
        )
        assert resp.status_code == 200
        assert resp.json()["is_operator"] is False

    def test_non_admin_cannot_grant_operator(self, api_client, auth_headers):
        me = api_client.get("/api/v1/auth/me", headers=auth_headers).json()
        resp = api_client.patch(
            f"/api/v1/admin/users/{me['id']}", json={"is_operator": True}, headers=auth_headers
        )
        assert resp.status_code == 403

    def test_unknown_user_404s(self, api_client, admin_headers):
        headers, _ = admin_headers
        resp = api_client.patch("/api/v1/admin/users/999999", json={"is_operator": True}, headers=headers)
        assert resp.status_code == 404


class TestSelfRevocationBlocked:
    def test_admin_cannot_revoke_own_admin_access(self, api_client, admin_headers):
        headers, user_id = admin_headers
        resp = api_client.patch(f"/api/v1/admin/users/{user_id}", json={"is_admin": False}, headers=headers)
        assert resp.status_code == 400

    def test_admin_can_grant_admin_to_someone_else(self, api_client, admin_headers):
        headers, _ = admin_headers
        username = _register(api_client)
        listing = api_client.get("/api/v1/admin/users", headers=headers).json()
        target = next(u for u in listing if u["username"] == username)

        resp = api_client.patch(f"/api/v1/admin/users/{target['id']}", json={"is_admin": True}, headers=headers)
        assert resp.status_code == 200
        assert resp.json()["is_admin"] is True


class TestBootstrapAdmin:
    def test_bootstrap_grants_admin_to_named_user(self, monkeypatch):
        from aerofleet.api.routes.auth import ensure_bootstrap_admin
        from aerofleet.data.database import get_db_session
        from aerofleet.data.models.models import User

        username = f"bootstrap_{uuid.uuid4().hex[:8]}"
        with get_db_session() as db:
            user = User(username=username, email=f"{username}@example.com", hashed_password="x")
            db.add(user)
            db.commit()

        monkeypatch.setenv("AEROFLEET_BOOTSTRAP_ADMIN_USERNAME", username)
        with get_db_session() as db:
            ensure_bootstrap_admin(db)

        with get_db_session() as db:
            refreshed = db.query(User).filter(User.username == username).first()
            assert refreshed.is_admin is True

    def test_bootstrap_is_a_no_op_when_unset(self, monkeypatch):
        from aerofleet.api.routes.auth import ensure_bootstrap_admin
        from aerofleet.data.database import get_db_session

        monkeypatch.delenv("AEROFLEET_BOOTSTRAP_ADMIN_USERNAME", raising=False)
        with get_db_session() as db:
            ensure_bootstrap_admin(db)  # must not raise

    def test_bootstrap_is_a_no_op_for_unknown_username(self, monkeypatch):
        from aerofleet.api.routes.auth import ensure_bootstrap_admin
        from aerofleet.data.database import get_db_session

        monkeypatch.setenv("AEROFLEET_BOOTSTRAP_ADMIN_USERNAME", "does-not-exist-at-all")
        with get_db_session() as db:
            ensure_bootstrap_admin(db)  # must not raise
