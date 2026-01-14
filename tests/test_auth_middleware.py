import pytest

# Skip if slowapi (rate limiting dependency) is not installed in the environment
pytest.importorskip("slowapi")

from fastapi.testclient import TestClient
from src.api.main_local import app


def test_login_returns_token_and_me_endpoint():
    client = TestClient(app)

    resp = client.post(
        "/api/auth/login", json={"username": "admin", "password": "admin123"}
    )
    assert resp.status_code == 200
    data = resp.json()
    token = data["access_token"]
    assert token
    assert data["user"]["role"] == "admin"

    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    me_body = me.json()
    assert me_body["user_id"] == "admin"
    assert me_body["auth_method"] == "jwt"


def test_rate_limit_headers_present_on_auth():
    client = TestClient(app)
    resp = client.post(
        "/api/auth/login", json={"username": "user", "password": "wrong"}
    )
    # Even on failed auth, SlowAPI should inject rate limit headers
    assert "X-RateLimit-Limit" in resp.headers
    assert "X-RateLimit-Remaining" in resp.headers
