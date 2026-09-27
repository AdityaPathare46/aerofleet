"""Silent session renewal: refresh tokens, and that they can't be used as logins."""
import uuid

import pytest

pytestmark = pytest.mark.integration


def _login(client):
    name = f"ref_{uuid.uuid4().hex[:8]}"
    client.post("/api/v1/auth/register", json={"username": name, "email": f"{name}@example.com", "password": "TestPass123!"})
    r = client.post("/api/v1/auth/login", data={"username": name, "password": "TestPass123!"})
    assert r.status_code == 200
    return r.json()


def test_login_returns_access_and_refresh_tokens(api_client):
    body = _login(api_client)
    assert body["access_token"] and body["refresh_token"] and body["expires_in"] >= 60 * 60


def test_refresh_issues_a_working_access_token_and_rotates(api_client):
    body = _login(api_client)
    r = api_client.post("/api/v1/auth/refresh", json={"refresh_token": body["refresh_token"]})
    assert r.status_code == 200
    new = r.json()
    assert new["refresh_token"] != body["refresh_token"]
    me = api_client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {new['access_token']}"})
    assert me.status_code == 200


def test_a_refresh_token_is_not_a_login(api_client):
    body = _login(api_client)
    me = api_client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {body['refresh_token']}"})
    assert me.status_code == 401


def test_an_access_token_cannot_be_used_to_refresh(api_client):
    body = _login(api_client)
    assert api_client.post("/api/v1/auth/refresh", json={"refresh_token": body["access_token"]}).status_code == 401
    assert api_client.post("/api/v1/auth/refresh", json={"refresh_token": "garbage"}).status_code == 401
