from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from backend.api.auth_routes import get_current_user, router as auth_router
from backend.auth.jwt_handler import create_access_token
from backend.auth.token_blacklist import token_blacklist
from backend.websocket.auth import AuthenticationError, ReconnectTokenStore, authenticate


@pytest.fixture(autouse=True)
def patch_blacklist_methods(monkeypatch: pytest.MonkeyPatch):
    """Keep auth-route tests deterministic and independent of Redis."""
    monkeypatch.setattr(token_blacklist, "is_revoked", AsyncMock(return_value=False))
    monkeypatch.setattr(token_blacklist, "track_session", AsyncMock(return_value=None))
    monkeypatch.setattr(token_blacklist, "revoke_token", AsyncMock(return_value=None))
    monkeypatch.setattr(token_blacklist, "remove_session", AsyncMock(return_value=None))


@pytest.fixture
def auth_client() -> TestClient:
    app = FastAPI()
    app.include_router(auth_router)

    @app.get("/protected")
    async def protected(user: dict = Depends(get_current_user)):
        return {"user_id": user.get("sub")}

    return TestClient(app, raise_server_exceptions=True)


def test_login_sets_http_only_lax_cookies(auth_client: TestClient) -> None:
    with patch("backend.api.auth_routes.verify_credentials", return_value=True):
        res = auth_client.post("/api/auth/login", json={"username": "admin", "password": "pw"})

    assert res.status_code == 200
    set_cookies = res.headers.get_list("set-cookie")

    access_cookie = next((c for c in set_cookies if c.lower().startswith("cortex_access=")), "")
    refresh_cookie = next((c for c in set_cookies if c.lower().startswith("cortex_refresh=")), "")

    assert access_cookie
    assert "httponly" in access_cookie.lower()
    assert "samesite=lax" in access_cookie.lower()

    assert refresh_cookie
    assert "httponly" in refresh_cookie.lower()
    assert "samesite=lax" in refresh_cookie.lower()


def test_refresh_and_me_work_with_cookie_only_auth(auth_client: TestClient) -> None:
    with patch("backend.api.auth_routes.verify_credentials", return_value=True):
        login_res = auth_client.post("/api/auth/login", json={"username": "admin", "password": "pw"})

    assert login_res.status_code == 200
    old_access = login_res.json()["access_token"]

    refresh_res = auth_client.post("/api/auth/refresh")
    assert refresh_res.status_code == 200
    new_access = refresh_res.json()["access_token"]
    assert new_access != old_access

    me_res = auth_client.get("/api/auth/me")
    assert me_res.status_code == 200
    assert me_res.json()["user_id"] == "admin"


def test_logout_clears_access_and_refresh_cookies(auth_client: TestClient) -> None:
    with patch("backend.api.auth_routes.verify_credentials", return_value=True):
        login_res = auth_client.post("/api/auth/login", json={"username": "admin", "password": "pw"})
    assert login_res.status_code == 200

    logout_res = auth_client.post("/api/auth/logout")
    assert logout_res.status_code == 200

    set_cookies = logout_res.headers.get_list("set-cookie")
    access_clear = next((c for c in set_cookies if c.lower().startswith("cortex_access=")), "")
    refresh_clear = next((c for c in set_cookies if c.lower().startswith("cortex_refresh=")), "")

    assert access_clear and "max-age=0" in access_clear.lower()
    assert refresh_clear and "max-age=0" in refresh_clear.lower()


def test_expired_or_invalid_token_returns_401(auth_client: TestClient) -> None:
    with patch("backend.api.auth_routes.verify_credentials", return_value=True):
        login_res = auth_client.post("/api/auth/login", json={"username": "admin", "password": "pw"})
    assert login_res.status_code == 200

    with patch("backend.api.auth_routes.decode_access_token", return_value=None):
        me_res = auth_client.get("/api/auth/me")

    assert me_res.status_code == 401
    assert "Invalid or expired token" in me_res.text


def test_websocket_auth_accepts_cookie_token() -> None:
    token = create_access_token(user_id="cookie-user", role="operator")
    ctx = authenticate(token=None, cookie_token=token)
    assert ctx.is_authenticated
    assert not ctx.is_anonymous
    assert ctx.user_id == "cookie-user"


def test_websocket_auth_missing_token_rejected_when_required(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("backend.websocket.auth._AUTH_REQUIRED", True)
    with pytest.raises(AuthenticationError):
        authenticate(token=None, cookie_token=None)


def test_websocket_reconnect_token_issue_and_single_use() -> None:
    store = ReconnectTokenStore()
    token = store.issue("sess-1", {"topic:a", "topic:b"})

    record = store.consume(token)
    assert record is not None
    assert record["session_id"] == "sess-1"
    assert record["topics"] == {"topic:a", "topic:b"}

    # Reconnect tokens are one-time use.
    assert store.consume(token) is None


def test_websocket_reconnect_token_expiration() -> None:
    store = ReconnectTokenStore()
    token = store.issue("sess-exp", set())
    store._tokens[token]["expires_at"] = 0

    assert store.consume(token) is None
