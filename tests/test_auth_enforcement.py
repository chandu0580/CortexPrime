"""
Authentication Enforcement Integration Tests
============================================
Verifies that every protected API route:
  1. Returns HTTP 401 when no token is provided
  2. Returns HTTP 401 when an invalid/expired token is provided
  3. Returns a non-401 response when a valid token is provided

Routes under test
-----------------
POST /execute
POST /execute/sync
POST /orchestrate
GET  /api/workspace/
POST /api/workspace/
GET  /governance/queue
GET  /governance/audit
POST /governance/emergency-stop
POST /governance/approve
GET  /operator/monitors
GET  /operator/active-missions
POST /operator/execute
POST /api/voice/v2/token
POST /api/voice/v2/session
GET  /api/voice/v2/sessions
DELETE /api/voice/v2/session/test-id

Public endpoints (must remain unauthenticated)
----------------------------------------------
GET /governance/health
GET /operator/health
GET /api/voice/v2/health

Run
---
    python -m pytest tests/test_auth_enforcement.py -v

Dependencies: httpx, pytest, pytest-asyncio
    pip install httpx pytest pytest-asyncio
"""
from __future__ import annotations

import os
import sys

import pytest

# Add project root to path so `backend.*` imports resolve
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# ── Import order matters: set AUTH_DISABLED before importing the app ──────────
os.environ.setdefault("AUTH_DISABLED", "false")  # enforce real auth in tests

# ── Minimal env to avoid crash on import ──────────────────────────────────────
os.environ.setdefault("OPENAI_API_KEY",              "test-key")
os.environ.setdefault("AZURE_OPENAI_API_KEY",        "test-key")
os.environ.setdefault("AZURE_OPENAI_ENDPOINT",       "https://test.openai.azure.com")
os.environ.setdefault("AZURE_OPENAI_API_VERSION",    "2025-01-01-preview")
os.environ.setdefault("AZURE_OPENAI_CHAT_DEPLOYMENT","gpt-4o")
os.environ.setdefault("JWT_SECRET_KEY",              "test-secret-key-must-be-32-chars-long!")
os.environ.setdefault("CORTEX_USER",                 "admin")
os.environ.setdefault("CORTEX_PASSWORD",             "testpass")

from httpx import AsyncClient, ASGITransport  # noqa: E402
from unittest.mock import AsyncMock, patch  # noqa: E402

# Import the FastAPI app after env vars are set
from backend.main import app  # noqa: E402
from backend.auth.jwt_handler import create_access_token  # noqa: E402

# ─────────────────────────────────────────────────────────────────────────────
# FIXTURES
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def valid_token() -> str:
    """Valid short-lived access JWT for the test user."""
    return create_access_token(user_id="test-admin", role="admin")


@pytest.fixture
def valid_headers(valid_token: str) -> dict:
    return {"Authorization": f"Bearer {valid_token}"}


@pytest.fixture
def invalid_headers() -> dict:
    return {"Authorization": "Bearer this.is.not.a.valid.jwt"}


@pytest.fixture
def no_headers() -> dict:
    return {}


# Shared async client fixture
@pytest.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as c:
        yield c


@pytest.fixture(autouse=True)
def _no_blacklist():
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)
    with patch(
        "backend.auth.token_blacklist.TokenBlacklist._get_redis",
        new_callable=AsyncMock,
        return_value=mock_redis,
    ):
        yield


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

PROTECTED_ROUTES = [
    # (method, path, body)
    ("POST",   "/execute",                              {"objective": "test"}),
    ("POST",   "/execute/sync",                         {"objective": "test"}),
    ("POST",   "/orchestrate",                          {"objective": "test"}),
    ("GET",    "/api/workspace/",                       None),
    ("POST",   "/api/workspace/",                       {"name": "test-ws"}),
    ("GET",    "/governance/queue",                     None),
    ("GET",    "/governance/audit",                     None),
    ("POST",   "/governance/emergency-stop",            {"reason": "test"}),
    ("POST",   "/governance/approve",                   {"request_id": "r1"}),
    ("GET",    "/operator/monitors",                    None),
    ("GET",    "/operator/active-missions",             None),
    ("POST",   "/operator/execute",                     {"goal": "open notepad"}),
    ("POST",   "/api/voice/v2/token",                   {}),
    ("POST",   "/api/voice/v2/session",                 {"identity": "tester"}),
    ("GET",    "/api/voice/v2/sessions",                None),
    ("DELETE", "/api/voice/v2/session/nonexistent-id",  None),
]

PUBLIC_ROUTES = [
    ("GET", "/governance/health", None),
    ("GET", "/operator/health",   None),
    ("GET", "/api/voice/v2/health", None),
    ("GET", "/health",            None),  # top-level backend health (if present)
]


# ─────────────────────────────────────────────────────────────────────────────
# TEST: 401 when no token
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
@pytest.mark.parametrize("method,path,body", PROTECTED_ROUTES)
async def test_protected_requires_auth_no_token(
    client, method: str, path: str, body
):
    """Every protected route must return 401 when called with no token."""
    response = await _request(client, method, path, body, headers={})
    assert response.status_code == 401, (
        f"{method} {path} returned {response.status_code} (expected 401)\n"
        f"Body: {response.text[:200]}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# TEST: 401 when invalid token
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
@pytest.mark.parametrize("method,path,body", PROTECTED_ROUTES)
async def test_protected_requires_auth_bad_token(
    client, method: str, path: str, body, invalid_headers: dict
):
    """Every protected route must return 401 when called with an invalid token."""
    response = await _request(client, method, path, body, headers=invalid_headers)
    assert response.status_code == 401, (
        f"{method} {path} returned {response.status_code} (expected 401)\n"
        f"Body: {response.text[:200]}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# TEST: Valid token passes auth gate (response is NOT 401 or 403)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
@pytest.mark.parametrize("method,path,body", PROTECTED_ROUTES)
async def test_protected_accepts_valid_token(
    client, method: str, path: str, body, valid_headers: dict
):
    """
    Every protected route must NOT return 401/403 when a valid token is provided.
    The route may return 422 (validation), 404 (not found), 503 (service unavailable),
    or 200/201/204 — all acceptable. What is NOT acceptable is 401 or 403.
    """
    response = await _request(client, method, path, body, headers=valid_headers)
    assert response.status_code not in (401, 403), (
        f"{method} {path} returned {response.status_code} with valid token\n"
        f"Body: {response.text[:200]}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# TEST: Public health endpoints never require auth
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
@pytest.mark.parametrize("method,path,body", PUBLIC_ROUTES)
async def test_public_routes_no_auth_required(client, method: str, path: str, body):
    """Public health endpoints must be accessible without authentication."""
    response = await _request(client, method, path, body, headers={})
    assert response.status_code not in (401, 403), (
        f"Public route {method} {path} returned {response.status_code} — "
        f"should not require auth.\nBody: {response.text[:200]}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# TEST: Login endpoint is always public
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_login_is_public(client):
    """POST /api/auth/login must be callable without any token."""
    response = await client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "testpass"},
    )
    # Either 200 (correct creds) or 401 (wrong creds) — never 403 circuit-break
    assert response.status_code in (200, 401), (
        f"Login returned unexpected status {response.status_code}: {response.text[:200]}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# TEST: Token returned from login works on protected route
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_login_then_call_protected(client):
    """
    Full round-trip: login → receive token → call protected route successfully.
    Requires CORTEX_PASSWORD=testpass in the test environment.
    """
    login_resp = await client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "testpass"},
    )
    if login_resp.status_code != 200:
        pytest.skip("Login failed — CORTEX_PASSWORD not set to 'testpass' in test env")

    token = login_resp.json().get("access_token")
    assert token, "Login response missing access_token"

    headers = {"Authorization": f"Bearer {token}"}
    response = await client.get("/api/workspace/", headers=headers)
    assert response.status_code not in (401, 403), (
        f"Token from login was rejected on /api/workspace/: {response.status_code}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# TEST: Expired token returns 401
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_expired_token_rejected(client):
    """A manually crafted expired token must be rejected with 401."""
    import jwt as pyjwt
    from datetime import datetime, timezone, timedelta

    secret = os.environ["JWT_SECRET_KEY"]
    expired_payload = {
        "sub":  "test-user",
        "role": "operator",
        "type": "access",
        "iat":  datetime.now(timezone.utc) - timedelta(hours=2),
        "exp":  datetime.now(timezone.utc) - timedelta(hours=1),  # already expired
    }
    expired_token = pyjwt.encode(expired_payload, secret, algorithm="HS256")

    response = await client.get(
        "/api/workspace/",
        headers={"Authorization": f"Bearer {expired_token}"},
    )
    assert response.status_code == 401, (
        f"Expired token should return 401, got {response.status_code}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# TEST: Refresh token cannot be used as an access token
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_refresh_token_rejected_as_access(client):
    """A refresh token must NOT be accepted as an access token."""
    from backend.auth.jwt_handler import create_refresh_token
    refresh = create_refresh_token(user_id="test-user", role="operator")

    response = await client.get(
        "/api/workspace/",
        headers={"Authorization": f"Bearer {refresh}"},
    )
    assert response.status_code == 401, (
        f"Refresh token used as access token should return 401, got {response.status_code}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# HELPER
# ─────────────────────────────────────────────────────────────────────────────

async def _request(client, method: str, path: str, body, headers: dict):
    """Dispatch an HTTP request with optional JSON body."""
    kwargs = {"headers": headers}
    if body is not None:
        kwargs["json"] = body

    dispatch = {
        "GET":    client.get,
        "POST":   client.post,
        "DELETE": client.delete,
        "PATCH":  client.patch,
        "PUT":    client.put,
    }
    fn = dispatch[method.upper()]
    return await fn(path, **kwargs)
