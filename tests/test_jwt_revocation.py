"""
Enterprise JWT Revocation Ã¢â‚¬â€ Test Suite
========================================
Verifies the full Redis-backed token blacklist lifecycle:

  Login Ã¢â€ â€™ Use token Ã¢â€ â€™ Logout Ã¢â€ â€™ Use token again Ã¢â€ â€™ 401

Tests are grouped by feature area and run entirely offline with
mocked Redis, so no live Redis instance is required.
"""
from __future__ import annotations

import base64
import json
import secrets
import time
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.responses import JSONResponse


# ===========================================================================
# Test app builder
# ===========================================================================

def _make_auth_app(redis_client: Optional[Any] = None) -> FastAPI:
    """
    Build a minimal FastAPI app with auth routes mounted.
    If redis_client is None, Redis is considered unavailable.
    """
    from fastapi import FastAPI as _FA
    from backend.api.auth_routes import router as auth_router

    app = _FA()
    app.include_router(auth_router)

    @app.get("/health/auth")
    async def _auth_health():
        from backend.auth.token_blacklist import token_blacklist
        return await token_blacklist.status()

    @app.get("/protected")
    async def _protected(current_user: dict = __import__(
        "fastapi", fromlist=["Depends"]
    ).Depends(__import__(
        "backend.api.auth_routes", fromlist=["get_current_user"]
    ).get_current_user)):
        return {"user_id": current_user.get("sub")}

    return app


# ===========================================================================
# Fixtures
# ===========================================================================

class _FakeRedis:
    """
    Minimal synchronous-style async Redis substitute.
    Stores keyÃ¢â€ â€™(value, expiry_epoch) in memory.
    Supports: set, get, delete, scan, zrem, zadd, zremrangebyscore, zcount, expireat, pipeline.
    """

    def __init__(self) -> None:
        self._store: Dict[str, tuple] = {}  # key Ã¢â€ â€™ (value, expiry or None)

    def _is_alive(self, key: str) -> bool:
        if key not in self._store:
            return False
        _, exp = self._store[key]
        if exp is not None and time.time() > exp:
            del self._store[key]
            return False
        return True

    async def set(self, key: str, value: Any, ex: int = None, **kw) -> None:
        exp = time.time() + ex if ex else None
        self._store[key] = (str(value), exp)

    async def get(self, key: str) -> Optional[str]:
        if not self._is_alive(key):
            return None
        return self._store[key][0]

    async def delete(self, *keys: str) -> int:
        removed = 0
        for k in keys:
            if k in self._store:
                del self._store[k]
                removed += 1
        return removed

    async def scan(self, cursor: int, match: str = "*", count: int = 100):
        import fnmatch
        live = [k for k in list(self._store) if self._is_alive(k)]
        matched = [k for k in live if fnmatch.fnmatch(k, match)]
        return (0, matched)  # single-pass Ã¢â‚¬â€ cursor always 0

    # Minimal ZSET ops (stored as dict[key] Ã¢â€ â€™ dict[member, score])
    def _zset(self, key: str) -> dict:
        val, exp = self._store.get(key, ("{}", None))
        try:
            return json.loads(val)
        except Exception:
            return {}

    def _zsave(self, key: str, zset: dict, exp: float = None) -> None:
        self._store[key] = (json.dumps(zset), exp)

    async def zadd(self, key: str, mapping: dict) -> int:
        zset = self._zset(key)
        zset.update(mapping)
        self._zsave(key, zset)
        return len(mapping)

    async def zrem(self, key: str, *members: str) -> int:
        zset = self._zset(key)
        removed = 0
        for m in members:
            if m in zset:
                del zset[m]
                removed += 1
        self._zsave(key, zset)
        return removed

    async def zremrangebyscore(self, key: str, min_score, max_score) -> int:
        zset = self._zset(key)
        mn = float("-inf") if min_score == "-inf" else float(min_score)
        mx = float("+inf") if max_score == "+inf" else float(max_score)
        to_remove = [m for m, s in zset.items() if mn <= float(s) <= mx]
        for m in to_remove:
            del zset[m]
        self._zsave(key, zset)
        return len(to_remove)

    async def zcount(self, key: str, min_score, max_score) -> int:
        zset = self._zset(key)
        mn = float("-inf") if min_score == "-inf" else float(min_score)
        mx = float("+inf") if max_score == "+inf" else float(max_score)
        return sum(1 for s in zset.values() if mn <= float(s) <= mx)

    async def expireat(self, key: str, epoch: int) -> None:
        if key in self._store:
            val, _ = self._store[key]
            self._store[key] = (val, float(epoch))

    def pipeline(self) -> "_FakePipeline":
        return _FakePipeline(self)


class _FakePipeline:
    def __init__(self, redis: _FakeRedis) -> None:
        self._redis = redis
        self._cmds: List[Any] = []

    def zremrangebyscore(self, key, mn, mx):
        self._cmds.append(("zremrangebyscore", key, mn, mx))
        return self

    def zadd(self, key, mapping):
        self._cmds.append(("zadd", key, mapping))
        return self

    def expireat(self, key, epoch):
        self._cmds.append(("expireat", key, epoch))
        return self

    async def execute(self):
        results = []
        for cmd in self._cmds:
            op = cmd[0]
            if op == "zremrangebyscore":
                results.append(await self._redis.zremrangebyscore(cmd[1], cmd[2], cmd[3]))
            elif op == "zadd":
                results.append(await self._redis.zadd(cmd[1], cmd[2]))
            elif op == "expireat":
                results.append(await self._redis.expireat(cmd[1], cmd[2]))
        return results


@pytest.fixture
def fake_redis():
    return _FakeRedis()


@pytest.fixture(autouse=True)
def patch_redis(fake_redis):
    """Patch token_blacklist's Redis client in every test."""
    with patch(
        "backend.auth.token_blacklist.TokenBlacklist._get_redis",
        new=AsyncMock(return_value=fake_redis),
    ):
        yield fake_redis


@pytest.fixture
def no_redis():
    """Fixture that simulates Redis being unavailable."""
    with patch(
        "backend.auth.token_blacklist.TokenBlacklist._get_redis",
        new=AsyncMock(return_value=None),
    ):
        yield


@pytest.fixture
def auth_client(fake_redis):
    from backend.api.auth_routes import router as auth_router
    from fastapi import FastAPI, Depends
    from backend.api.auth_routes import get_current_user

    app = FastAPI()
    app.include_router(auth_router)

    @app.get("/protected")
    async def _protected(current_user: dict = Depends(get_current_user)):
        return {"user_id": current_user.get("sub")}

    return TestClient(app, raise_server_exceptions=True)


# ===========================================================================
# Helpers
# ===========================================================================

_TEST_USER = "admin"
_TEST_PASS = "testpassword123"


def _login(client: TestClient) -> str:
    """Perform login and return the access_token string."""
    # Patch in the auth_routes namespace (where the function is called)
    with patch("backend.api.auth_routes.verify_credentials", return_value=True):
        r = client.post("/api/auth/login", json={"username": _TEST_USER, "password": _TEST_PASS})
    assert r.status_code == 200, f"Login failed: {r.text}"
    return r.json()["access_token"]


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ===========================================================================
# Token Blacklist unit tests
# ===========================================================================

class TestTokenBlacklist:
    """Unit tests directly against the TokenBlacklist class."""

    @pytest.mark.asyncio
    async def test_revoke_and_check(self, fake_redis):
        from backend.auth.token_blacklist import TokenBlacklist
        bl = TokenBlacklist()

        jti     = secrets.token_hex(16)
        user_id = "user_42"
        exp     = time.time() + 3600

        # Not revoked initially
        assert not await bl.is_jti_revoked(jti)

        # Revoke it
        await bl.revoke_token(jti=jti, user_id=user_id, expires_at=exp)
        assert await bl.is_jti_revoked(jti)

    @pytest.mark.asyncio
    async def test_revoke_is_redis_backed(self, fake_redis):
        """Revoked JTI must be stored in Redis with proper key."""
        from backend.auth.token_blacklist import TokenBlacklist, _PFX_JTI
        bl  = TokenBlacklist()
        jti = secrets.token_hex(16)

        await bl.revoke_token(jti=jti, user_id="u1", expires_at=time.time() + 100)

        stored = await fake_redis.get(f"{_PFX_JTI}{jti}")
        assert stored == "u1"

    @pytest.mark.asyncio
    async def test_ttl_matches_token_expiry(self, fake_redis):
        """Key TTL must reflect remaining token lifetime (within Ã‚Â±2s tolerance)."""
        from backend.auth.token_blacklist import TokenBlacklist, _PFX_JTI
        bl      = TokenBlacklist()
        jti     = secrets.token_hex(16)
        now     = time.time()
        exp     = now + 1800  # 30 minutes

        await bl.revoke_token(jti=jti, user_id="u2", expires_at=exp)

        key        = f"{_PFX_JTI}{jti}"
        _, stored_exp = fake_redis._store[key]
        assert abs(stored_exp - exp) <= 2, "TTL should match token expiry within 2 seconds"

    @pytest.mark.asyncio
    async def test_revoke_all_user_tokens(self, fake_redis):
        from backend.auth.token_blacklist import TokenBlacklist
        bl = TokenBlacklist()

        user_id    = "user_compromised"
        now        = time.time()
        issued_at  = now - 10  # token issued 10 seconds ago

        # Not revoked before the call
        assert not await bl.is_user_globally_revoked(user_id, issued_at)

        epoch = await bl.revoke_all_user_tokens(user_id)

        # Token issued before revocation Ã¢â€ â€™ revoked
        assert await bl.is_user_globally_revoked(user_id, issued_at)

        # Token issued AFTER revocation Ã¢â€ â€™ still valid
        future_iat = epoch + 5
        assert not await bl.is_user_globally_revoked(user_id, future_iat)

    @pytest.mark.asyncio
    async def test_is_revoked_combined(self, fake_redis):
        """is_revoked checks both JTI blacklist and user-level revocation."""
        from backend.auth.token_blacklist import TokenBlacklist
        bl = TokenBlacklist()

        user_id   = "user_combo"
        jti       = secrets.token_hex(16)
        issued_at = time.time() - 5

        # Neither check fires initially
        assert not await bl.is_revoked(jti, user_id, issued_at)

        # Revoke user globally
        await bl.revoke_all_user_tokens(user_id)

        # Now the combined check should fire
        assert await bl.is_revoked(jti, user_id, issued_at)

    @pytest.mark.asyncio
    async def test_revoked_token_count(self, fake_redis):
        from backend.auth.token_blacklist import TokenBlacklist
        bl = TokenBlacklist()

        initial = await bl.revoked_token_count()

        for i in range(3):
            jti = secrets.token_hex(16)
            await bl.revoke_token(jti=jti, user_id="u", expires_at=time.time() + 60)

        after = await bl.revoked_token_count()
        assert after == initial + 3

    @pytest.mark.asyncio
    async def test_track_and_count_sessions(self, fake_redis):
        from backend.auth.token_blacklist import TokenBlacklist
        bl = TokenBlacklist()

        user_id = "user_sessions"
        for _ in range(4):
            jti = secrets.token_hex(16)
            await bl.track_session(jti=jti, user_id=user_id, expires_at=time.time() + 3600)

        count = await bl.active_session_count()
        assert count >= 4

    @pytest.mark.asyncio
    async def test_remove_session(self, fake_redis):
        from backend.auth.token_blacklist import TokenBlacklist
        bl      = TokenBlacklist()
        user_id = "user_sess_remove"
        jti     = secrets.token_hex(16)

        await bl.track_session(jti=jti, user_id=user_id, expires_at=time.time() + 3600)
        before = await bl.active_session_count()

        await bl.remove_session(jti=jti, user_id=user_id)
        after  = await bl.active_session_count()

        assert after == before - 1

    @pytest.mark.asyncio
    async def test_status_returns_required_keys(self, fake_redis):
        from backend.auth.token_blacklist import TokenBlacklist
        bl = TokenBlacklist()
        s  = await bl.status()

        required = {"status", "redis_connected", "revoked_token_count",
                    "active_sessions", "fail_open", "user_revoke_ttl_sec"}
        assert required <= s.keys()

    @pytest.mark.asyncio
    async def test_status_healthy_when_redis_available(self, fake_redis):
        from backend.auth.token_blacklist import TokenBlacklist
        bl = TokenBlacklist()
        s  = await bl.status()
        assert s["status"] == "healthy"
        assert s["redis_connected"] is True


# ===========================================================================
# Fail-closed behaviour
# ===========================================================================

class TestFailClosed:
    """Tokens must be rejected when Redis is unavailable and REVOCATION_FAIL_OPEN=false."""

    @pytest.mark.asyncio
    async def test_jti_check_fails_closed(self, no_redis):
        from backend.auth.token_blacklist import TokenBlacklist
        import os
        os.environ["REVOCATION_FAIL_OPEN"] = "false"

        bl  = TokenBlacklist()
        jti = secrets.token_hex(16)

        # Redis is down Ã¢â‚¬â€ should reject (fail closed)
        with patch("backend.auth.token_blacklist._FAIL_OPEN", False):
            result = await bl.is_jti_revoked(jti)
        assert result is True, "Should fail closed when Redis unavailable"

    @pytest.mark.asyncio
    async def test_jti_check_fails_open(self, no_redis):
        from backend.auth.token_blacklist import TokenBlacklist

        bl  = TokenBlacklist()
        jti = secrets.token_hex(16)

        with patch("backend.auth.token_blacklist._FAIL_OPEN", True):
            result = await bl.is_jti_revoked(jti)
        assert result is False, "Should fail open when REVOCATION_FAIL_OPEN=true"

    @pytest.mark.asyncio
    async def test_empty_jti_rejected_by_default(self, fake_redis):
        """Tokens without jti claim must be rejected (cannot prove non-revocation)."""
        from backend.auth.token_blacklist import TokenBlacklist
        with patch("backend.auth.token_blacklist._FAIL_OPEN", False):
            bl     = TokenBlacklist()
            result = await bl.is_jti_revoked("")
        assert result is True

class TestFailOpenDefaults:
    def test_development_defaults_to_fail_open(self, monkeypatch: pytest.MonkeyPatch):
        from backend.auth.token_blacklist import _compute_fail_open

        monkeypatch.setenv("ENV", "development")
        monkeypatch.delenv("ENVIRONMENT", raising=False)
        monkeypatch.delenv("REVOCATION_FAIL_OPEN", raising=False)

        assert _compute_fail_open() is True

    def test_production_defaults_to_fail_closed(self, monkeypatch: pytest.MonkeyPatch):
        from backend.auth.token_blacklist import _compute_fail_open

        monkeypatch.setenv("ENV", "production")
        monkeypatch.delenv("ENVIRONMENT", raising=False)
        monkeypatch.delenv("REVOCATION_FAIL_OPEN", raising=False)

        assert _compute_fail_open() is False

    @pytest.mark.asyncio
    async def test_revoke_token_is_best_effort_in_fail_open_mode(self, no_redis):
        from backend.auth.token_blacklist import TokenBlacklist

        bl = TokenBlacklist()

        with patch("backend.auth.token_blacklist._FAIL_OPEN", True):
            await bl.revoke_token(
                jti=secrets.token_hex(16),
                user_id="dev-user",
                expires_at=time.time() + 60,
            )

# ===========================================================================
# HTTP: Login Ã¢â€ â€™ Use Ã¢â€ â€™ Logout Ã¢â€ â€™ Reject
# ===========================================================================

class TestLoginLogoutCycle:
    """The primary success test case from the spec."""

    def test_login_use_logout_reject(self, auth_client):
        """
        Login Ã¢â€ â€™ Use token Ã¢â€ â€™ Logout Ã¢â€ â€™ Use token again Ã¢â€ â€™ 401
        """
        # 1. Login
        token = _login(auth_client)
        assert token, "Expected access token from login"

        # 2. Use token Ã¢â‚¬â€ should work
        r_before = auth_client.get("/protected", headers=_auth_header(token))
        assert r_before.status_code == 200, f"Token should be valid before logout: {r_before.text}"
        assert r_before.json()["user_id"] == _TEST_USER

        # 3. Logout Ã¢â‚¬â€ revokes the token in Redis
        r_logout = auth_client.post("/api/auth/logout", headers=_auth_header(token))
        assert r_logout.status_code == 200
        assert r_logout.json()["status"] == "ok"

        # 4. Use token again Ã¢â‚¬â€ must be rejected with 401
        r_after = auth_client.get("/protected", headers=_auth_header(token))
        assert r_after.status_code == 401, (
            f"Revoked token should return 401, got {r_after.status_code}: {r_after.text}"
        )

    def test_token_before_logout_succeeds(self, auth_client):
        """Sanity: /protected returns 200 for a valid fresh token."""
        token = _login(auth_client)
        r = auth_client.get("/protected", headers=_auth_header(token))
        assert r.status_code == 200

    def test_no_token_returns_401(self, auth_client):
        r = auth_client.get("/protected")
        assert r.status_code == 401

    def test_invalid_token_returns_401(self, auth_client):
        r = auth_client.get("/protected", headers={"Authorization": "Bearer not.a.token"})
        assert r.status_code == 401

class TestFailOpenDefaults:
    def test_development_defaults_to_fail_open(self, monkeypatch: pytest.MonkeyPatch):
        from backend.auth.token_blacklist import _compute_fail_open

        monkeypatch.setenv("ENV", "development")
        monkeypatch.delenv("ENVIRONMENT", raising=False)
        monkeypatch.delenv("REVOCATION_FAIL_OPEN", raising=False)

        assert _compute_fail_open() is True

    def test_production_defaults_to_fail_closed(self, monkeypatch: pytest.MonkeyPatch):
        from backend.auth.token_blacklist import _compute_fail_open

        monkeypatch.setenv("ENV", "production")
        monkeypatch.delenv("ENVIRONMENT", raising=False)
        monkeypatch.delenv("REVOCATION_FAIL_OPEN", raising=False)

        assert _compute_fail_open() is False

    @pytest.mark.asyncio
    async def test_revoke_token_is_best_effort_in_fail_open_mode(self, no_redis):
        from backend.auth.token_blacklist import TokenBlacklist

        bl = TokenBlacklist()

        with patch("backend.auth.token_blacklist._FAIL_OPEN", True):
            await bl.revoke_token(
                jti=secrets.token_hex(16),
                user_id="dev-user",
                expires_at=time.time() + 60,
            )

# ===========================================================================
# HTTP: Refresh token rotation with revocation
# ===========================================================================

class TestRefreshRotation:
    """Old refresh token must be revoked after a successful /refresh call."""

    def test_refresh_rotates_and_revokes_old(self, auth_client):
        """
        After refresh, the old refresh token's JTI is in the blacklist.
        """
        import asyncio
        from backend.auth.jwt_handler import create_refresh_token, decode_refresh_token
        from backend.auth.token_blacklist import token_blacklist

        # Create a refresh token manually
        user_id  = "rotate_user"
        old_ref  = create_refresh_token(user_id=user_id, role="operator")
        old_pay  = decode_refresh_token(old_ref)
        old_jti  = old_pay.get("jti", "")

        # Hit /api/auth/refresh with the old refresh token as a cookie
        r = auth_client.post(
            "/api/auth/refresh",
            cookies={"cortex_refresh": old_ref},
        )
        assert r.status_code == 200, f"Refresh failed: {r.text}"

        # Old JTI must now be in the blacklist
        revoked = asyncio.run(token_blacklist.is_jti_revoked(old_jti))
        assert revoked, "Old refresh JTI should be blacklisted after rotation"

    def test_refresh_with_revoked_token_returns_401(self, auth_client):
        """Replaying a revoked refresh token must return 401."""
        import asyncio
        from backend.auth.jwt_handler import create_refresh_token, decode_refresh_token
        from backend.auth.token_blacklist import token_blacklist

        user_id = "replay_user"
        ref_tok = create_refresh_token(user_id=user_id, role="operator")
        payload = decode_refresh_token(ref_tok)
        old_jti = payload.get("jti", "")
        old_exp = float(payload.get("exp", time.time() + 3600))

        # Manually revoke it
        asyncio.run(
            token_blacklist.revoke_token(
                jti=old_jti, user_id=user_id, expires_at=old_exp, token_type="refresh"
            )
        )

        # Attempt to use the revoked refresh token
        r = auth_client.post(
            "/api/auth/refresh",
            cookies={"cortex_refresh": ref_tok},
        )
        assert r.status_code == 401, f"Expected 401, got {r.status_code}: {r.text}"

    def test_new_access_token_after_refresh_is_valid(self, auth_client):
        """The new access token issued by /refresh must work."""
        from backend.auth.jwt_handler import create_refresh_token

        user_id = "fresh_user"
        ref_tok = create_refresh_token(user_id=user_id, role="operator")

        r = auth_client.post(
            "/api/auth/refresh",
            cookies={"cortex_refresh": ref_tok},
        )
        assert r.status_code == 200
        new_access = r.json()["access_token"]
        assert new_access

        # Use the new access token
        r2 = auth_client.get("/protected", headers=_auth_header(new_access))
        assert r2.status_code == 200

class TestFailOpenDefaults:
    def test_development_defaults_to_fail_open(self, monkeypatch: pytest.MonkeyPatch):
        from backend.auth.token_blacklist import _compute_fail_open

        monkeypatch.setenv("ENV", "development")
        monkeypatch.delenv("ENVIRONMENT", raising=False)
        monkeypatch.delenv("REVOCATION_FAIL_OPEN", raising=False)

        assert _compute_fail_open() is True

    def test_production_defaults_to_fail_closed(self, monkeypatch: pytest.MonkeyPatch):
        from backend.auth.token_blacklist import _compute_fail_open

        monkeypatch.setenv("ENV", "production")
        monkeypatch.delenv("ENVIRONMENT", raising=False)
        monkeypatch.delenv("REVOCATION_FAIL_OPEN", raising=False)

        assert _compute_fail_open() is False

    @pytest.mark.asyncio
    async def test_revoke_token_is_best_effort_in_fail_open_mode(self, no_redis):
        from backend.auth.token_blacklist import TokenBlacklist

        bl = TokenBlacklist()

        with patch("backend.auth.token_blacklist._FAIL_OPEN", True):
            await bl.revoke_token(
                jti=secrets.token_hex(16),
                user_id="dev-user",
                expires_at=time.time() + 60,
            )

# ===========================================================================
# HTTP: revoke_all_tokens
# ===========================================================================

class TestRevokeAllTokens:
    """POST /api/auth/revoke-all invalidates ALL tokens for the calling user."""

    def test_revoke_all_invalidates_current_token(self, auth_client):
        """Calling revoke-all must invalidate the bearer token used in the same request."""
        token   = _login(auth_client)
        headers = _auth_header(token)

        # Revoke all Ã¢â‚¬â€ uses the same token as auth
        r = auth_client.post("/api/auth/revoke-all", headers=headers)
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

        # Same token must now be rejected
        r2 = auth_client.get("/protected", headers=headers)
        assert r2.status_code == 401, (
            f"Token should be invalid after revoke-all, got {r2.status_code}"
        )

    def test_revoke_all_does_not_affect_other_users(self, auth_client):
        """Revoking user A's tokens must not affect user B."""
        import asyncio
        from backend.auth.token_blacklist import token_blacklist
        from backend.auth.jwt_handler import create_access_token, decode_access_token

        # User A Ã¢â‚¬â€ revoke all
        token_a = _login(auth_client)
        auth_client.post("/api/auth/revoke-all", headers=_auth_header(token_a))

        # User B Ã¢â‚¬â€ fresh token (issued AFTER the revoke-all event for user A)
        token_b = create_access_token(user_id="user_b", role="operator")
        payload_b = decode_access_token(token_b)

        revoked = asyncio.run(
            token_blacklist.is_revoked(
                jti=payload_b.get("jti", ""),
                user_id="user_b",
                issued_at=float(payload_b.get("iat", 0)),
            )
        )
        assert not revoked, "User B's token should not be revoked"

class TestFailOpenDefaults:
    def test_development_defaults_to_fail_open(self, monkeypatch: pytest.MonkeyPatch):
        from backend.auth.token_blacklist import _compute_fail_open

        monkeypatch.setenv("ENV", "development")
        monkeypatch.delenv("ENVIRONMENT", raising=False)
        monkeypatch.delenv("REVOCATION_FAIL_OPEN", raising=False)

        assert _compute_fail_open() is True

    def test_production_defaults_to_fail_closed(self, monkeypatch: pytest.MonkeyPatch):
        from backend.auth.token_blacklist import _compute_fail_open

        monkeypatch.setenv("ENV", "production")
        monkeypatch.delenv("ENVIRONMENT", raising=False)
        monkeypatch.delenv("REVOCATION_FAIL_OPEN", raising=False)

        assert _compute_fail_open() is False

    @pytest.mark.asyncio
    async def test_revoke_token_is_best_effort_in_fail_open_mode(self, no_redis):
        from backend.auth.token_blacklist import TokenBlacklist

        bl = TokenBlacklist()

        with patch("backend.auth.token_blacklist._FAIL_OPEN", True):
            await bl.revoke_token(
                jti=secrets.token_hex(16),
                user_id="dev-user",
                expires_at=time.time() + 60,
            )

# ===========================================================================
# HTTP: Admin revoke-user
# ===========================================================================

class TestAdminRevokeUser:
    """POST /api/auth/admin/revoke-user/{user_id} requires admin role."""

    def test_admin_can_revoke_other_user(self, auth_client):
        import asyncio
        from backend.auth.jwt_handler import create_access_token, decode_access_token
        from backend.auth.token_blacklist import token_blacklist

        # Create an admin token
        admin_token = create_access_token(user_id="admin", role="admin")

        # Create a victim token (issued now, so iat is current)
        victim_token = create_access_token(user_id="victim_user", role="operator")
        victim_pay   = decode_access_token(victim_token)

        # Admin revokes all victim tokens
        r = auth_client.post(
            "/api/auth/admin/revoke-user/victim_user",
            headers=_auth_header(admin_token),
        )
        assert r.status_code == 200, f"Admin revoke failed: {r.text}"

        # Victim token (with iat <= revoke epoch) must be revoked
        revoked = asyncio.run(
            token_blacklist.is_revoked(
                jti=victim_pay.get("jti", ""),
                user_id="victim_user",
                issued_at=float(victim_pay.get("iat", 0)),
            )
        )
        assert revoked, "Victim's token should be revoked after admin action"

    def test_non_admin_cannot_revoke_others(self, auth_client):
        from backend.auth.jwt_handler import create_access_token
        # Use an operator token (not admin)
        token = create_access_token(user_id="operator_user", role="operator")
        r = auth_client.post(
            "/api/auth/admin/revoke-user/some_other_user",
            headers=_auth_header(token),
        )
        assert r.status_code == 403

class TestFailOpenDefaults:
    def test_development_defaults_to_fail_open(self, monkeypatch: pytest.MonkeyPatch):
        from backend.auth.token_blacklist import _compute_fail_open

        monkeypatch.setenv("ENV", "development")
        monkeypatch.delenv("ENVIRONMENT", raising=False)
        monkeypatch.delenv("REVOCATION_FAIL_OPEN", raising=False)

        assert _compute_fail_open() is True

    def test_production_defaults_to_fail_closed(self, monkeypatch: pytest.MonkeyPatch):
        from backend.auth.token_blacklist import _compute_fail_open

        monkeypatch.setenv("ENV", "production")
        monkeypatch.delenv("ENVIRONMENT", raising=False)
        monkeypatch.delenv("REVOCATION_FAIL_OPEN", raising=False)

        assert _compute_fail_open() is False

    @pytest.mark.asyncio
    async def test_revoke_token_is_best_effort_in_fail_open_mode(self, no_redis):
        from backend.auth.token_blacklist import TokenBlacklist

        bl = TokenBlacklist()

        with patch("backend.auth.token_blacklist._FAIL_OPEN", True):
            await bl.revoke_token(
                jti=secrets.token_hex(16),
                user_id="dev-user",
                expires_at=time.time() + 60,
            )

# ===========================================================================
# HTTP: Health endpoint
# ===========================================================================

class TestAuthHealthEndpoint:
    """GET /api/auth/health returns the correct shape."""

    def test_health_returns_200(self, auth_client):
        r = auth_client.get("/api/auth/health")
        assert r.status_code == 200

    def test_health_shape(self, auth_client):
        r = auth_client.get("/api/auth/health")
        body = r.json()
        required = {"status", "redis_connected", "revoked_token_count", "active_sessions"}
        assert required <= body.keys(), f"Missing fields: {required - body.keys()}"

    def test_health_shows_redis_connected(self, auth_client):
        r = auth_client.get("/api/auth/health")
        body = r.json()
        assert body["redis_connected"] is True
        assert body["status"] == "healthy"

    def test_health_reflects_revoked_tokens(self, auth_client):
        """After logout, revoked_token_count must increase."""
        token = _login(auth_client)
        r1 = auth_client.get("/api/auth/health").json()

        auth_client.post("/api/auth/logout", headers=_auth_header(token))

        r2 = auth_client.get("/api/auth/health").json()
        assert r2["revoked_token_count"] >= r1["revoked_token_count"] + 1

class TestFailOpenDefaults:
    def test_development_defaults_to_fail_open(self, monkeypatch: pytest.MonkeyPatch):
        from backend.auth.token_blacklist import _compute_fail_open

        monkeypatch.setenv("ENV", "development")
        monkeypatch.delenv("ENVIRONMENT", raising=False)
        monkeypatch.delenv("REVOCATION_FAIL_OPEN", raising=False)

        assert _compute_fail_open() is True

    def test_production_defaults_to_fail_closed(self, monkeypatch: pytest.MonkeyPatch):
        from backend.auth.token_blacklist import _compute_fail_open

        monkeypatch.setenv("ENV", "production")
        monkeypatch.delenv("ENVIRONMENT", raising=False)
        monkeypatch.delenv("REVOCATION_FAIL_OPEN", raising=False)

        assert _compute_fail_open() is False

    @pytest.mark.asyncio
    async def test_revoke_token_is_best_effort_in_fail_open_mode(self, no_redis):
        from backend.auth.token_blacklist import TokenBlacklist

        bl = TokenBlacklist()

        with patch("backend.auth.token_blacklist._FAIL_OPEN", True):
            await bl.revoke_token(
                jti=secrets.token_hex(16),
                user_id="dev-user",
                expires_at=time.time() + 60,
            )

# ===========================================================================
# HTTP: Expired token auto-clean
# ===========================================================================

class TestExpiredTokenAutoClean:
    """Tokens that have naturally expired must not appear in the active counts."""

    @pytest.mark.asyncio
    async def test_expired_jti_auto_removed(self, fake_redis):
        """A JTI blacklist entry whose TTL has passed must not be found."""
        from backend.auth.token_blacklist import TokenBlacklist, _PFX_JTI
        bl  = TokenBlacklist()
        jti = secrets.token_hex(16)

        # Inject already-expired entry directly
        expired_at = time.time() - 10
        fake_redis._store[f"{_PFX_JTI}{jti}"] = ("user1", expired_at)

        # FakeRedis TTL logic: get() returns None for expired keys
        result = await bl.is_jti_revoked(jti)
        assert result is False, "Expired blacklist entry should be treated as not-revoked"

    @pytest.mark.asyncio
    async def test_active_session_count_excludes_expired(self, fake_redis):
        """Expired sessions must not count toward active_session_count."""
        from backend.auth.token_blacklist import TokenBlacklist, _PFX_SESS
        bl      = TokenBlacklist()
        user_id = "user_exp"
        key     = f"{_PFX_SESS}{user_id}"

        now = time.time()

        # Add 2 active sessions and 2 expired sessions
        fake_redis._store[key] = (
            json.dumps({
                "jti_active_1": now + 3600,
                "jti_active_2": now + 7200,
                "jti_expired_1": now - 100,
                "jti_expired_2": now - 200,
            }),
            now + 7200,
        )

        count = await bl.active_session_count()
        assert count == 2, f"Only 2 active sessions expected, got {count}"


# ===========================================================================
# JWT handler: access token now has jti
# ===========================================================================

class TestJWTHandler:
    """Access tokens must include a jti claim after the update."""

    def test_access_token_has_jti(self):
        from backend.auth.jwt_handler import create_access_token, decode_access_token
        token   = create_access_token(user_id="test_user")
        payload = decode_access_token(token)
        assert payload is not None
        jti = payload.get("jti")
        assert jti, "Access token must have a jti claim"
        assert len(jti) == 32, "jti should be 32 hex chars (secrets.token_hex(16))"

    def test_access_tokens_have_unique_jtis(self):
        from backend.auth.jwt_handler import create_access_token, decode_access_token
        jtis = set()
        for _ in range(20):
            tok = create_access_token(user_id="u")
            pay = decode_access_token(tok)
            jtis.add(pay.get("jti"))
        assert len(jtis) == 20, "All JTIs must be unique"

    def test_refresh_token_has_jti(self):
        from backend.auth.jwt_handler import create_refresh_token, decode_refresh_token
        token   = create_refresh_token(user_id="test_user")
        payload = decode_refresh_token(token)
        assert payload is not None
        assert payload.get("jti"), "Refresh token must have a jti claim"


# ===========================================================================
# Dependencies: require_user rejects revoked tokens
# ===========================================================================

class TestRequireUserDependency:
    """The central require_user dependency must honour the blacklist."""

    @pytest.mark.asyncio
    async def test_valid_token_passes(self, fake_redis):
        from backend.auth.dependencies import require_user
        from backend.auth.jwt_handler import create_access_token
        from fastapi.security import HTTPAuthorizationCredentials

        token = create_access_token(user_id="dep_user")
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

        with patch(
            "backend.auth.dependencies._decode_and_verify",
            new=AsyncMock(return_value={"sub": "dep_user", "jti": "abc"}),
        ):
            result = await require_user(creds=creds)
        assert result["sub"] == "dep_user"

    @pytest.mark.asyncio
    async def test_revoked_token_raises_401(self, fake_redis):
        from backend.auth.dependencies import require_user
        from backend.auth.jwt_handler import create_access_token, decode_access_token
        from backend.auth.token_blacklist import token_blacklist
        from fastapi import HTTPException
        from fastapi.security import HTTPAuthorizationCredentials

        token   = create_access_token(user_id="rev_dep_user")
        payload = decode_access_token(token)
        jti     = payload.get("jti", "")

        # Revoke the token
        await token_blacklist.revoke_token(
            jti=jti, user_id="rev_dep_user",
            expires_at=float(payload.get("exp", time.time() + 3600))
        )

        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
        with pytest.raises(HTTPException) as exc_info:
            await require_user(creds=creds)
        assert exc_info.value.status_code == 401
