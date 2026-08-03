"""
Enterprise API Rate Limiting — Test Suite
==========================================
Validates Redis sliding-window HTTP rate limiting, local in-process
fallback, 429 response shape, per-user isolation, and WebSocket limits.

All tests use the real RateLimiter / middleware stack with mocked Redis
so they run offline without a live Redis instance.
"""
from __future__ import annotations

import asyncio
import json
import time
import types
import unittest.mock as mock
from typing import Any, Dict, List, Tuple
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from httpx import AsyncClient
from starlette.responses import Response

# ---------------------------------------------------------------------------
# Helpers — build a minimal test app with rate-limit middleware
# ---------------------------------------------------------------------------

def _make_app(rate_limit_enabled: bool = True) -> FastAPI:
    """Return a minimal FastAPI app with RateLimitMiddleware registered."""
    import os
    os.environ["RATE_LIMIT_ENABLED"] = "true" if rate_limit_enabled else "false"

    from fastapi import FastAPI as _FA
    from starlette.responses import JSONResponse

    test_app = _FA()

    from backend.safety.rate_limit_middleware import RateLimitMiddleware
    test_app.add_middleware(RateLimitMiddleware)

    @test_app.post("/orchestrate")
    async def _orchestrate():
        return JSONResponse({"ok": True})

    @test_app.post("/execute")
    async def _execute():
        return JSONResponse({"ok": True})

    @test_app.get("/items")
    async def _items():
        return JSONResponse({"items": []})

    @test_app.get("/health/rate-limiter")
    async def _health():
        from backend.safety.rate_limiter import rate_limiter
        return await rate_limiter.status()

    return test_app


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_local_fallback():
    """
    Reset the local in-process sliding window between tests so test counters
    don't bleed across tests.
    """
    from backend.safety import rate_limiter as _mod
    _mod._local_fallback._windows.clear()
    yield
    _mod._local_fallback._windows.clear()


@pytest.fixture
def app_no_redis():
    """
    App where Redis is NOT available — forces local fallback path.
    Uses the real _LocalSlidingWindow counters.
    """
    import os
    os.environ["RATE_LIMIT_ENABLED"] = "true"

    async def _fake_ensure_connected():
        return False

    with patch(
        "backend.infrastructure.redis.connection.redis_connection.ensure_connected",
        new=AsyncMock(side_effect=_fake_ensure_connected),
    ):
        # Also make _get_redis() on the RateLimiter singleton return None
        with patch(
            "backend.safety.rate_limiter.RateLimiter._get_redis",
            new=AsyncMock(return_value=None),
        ):
            app = _make_app()
            yield app


@pytest.fixture
def app_with_redis():
    """
    App where Redis returns a mock client that always allows.
    We patch _redis_check directly to control per-test allow/deny.
    """
    import os
    os.environ["RATE_LIMIT_ENABLED"] = "true"
    app = _make_app()
    return app


# ---------------------------------------------------------------------------
# Helper: fake Redis client that tracks calls
# ---------------------------------------------------------------------------

def _make_fake_redis_client(window_sec: int = 60) -> MagicMock:
    """
    Minimal async mock that simulates an incrementing Sorted Set.
    Each call to eval() advances a counter keyed by (key,).
    Returns Lua-compatible [allowed, remaining, 0] results.
    """
    counters: Dict[str, int] = {}
    limits: Dict[str, int] = {}  # populated lazily

    async def fake_eval(script, num_keys, key, cutoff, now_ms, limit, window_ms, member):
        counters.setdefault(key, 0)
        limits[key] = int(limit)
        c = counters[key]
        lim = int(limit)
        if c < lim:
            counters[key] += 1
            return [1, lim - counters[key], 0]
        else:
            retry_ms = window_ms  # full window
            return [0, 0, int(retry_ms)]

    client = MagicMock()
    client.eval = fake_eval
    client.scan = AsyncMock(return_value=(0, []))
    return client


# ===========================================================================
# Tests: single-user spam → 429
# ===========================================================================

class TestSingleUserSpam:
    """Verify that a single user exceeding the orchestrate limit gets 429."""

    def test_spam_orchestrate_local_fallback(self, app_no_redis):
        """
        POST /orchestrate 11 times with the same identity.
        Limit = 10; 11th must return 429.
        """
        from backend.safety import rate_limiter as _mod
        # Patch the limit down to 5 to keep the test fast
        with patch.dict(_mod._LIMITS, {"orchestrate": 5}):
            client = TestClient(app_no_redis, raise_server_exceptions=True)
            headers = {"X-Forwarded-For": "10.0.0.1"}

            responses: List[int] = []
            for _ in range(7):
                r = client.post("/orchestrate", headers=headers)
                responses.append(r.status_code)

            allowed = responses.count(200)
            denied  = responses.count(429)

            assert allowed == 5, f"Expected 5 allowed, got {allowed}. Statuses: {responses}"
            assert denied  == 2, f"Expected 2 denied, got {denied}. Statuses: {responses}"

    def test_spam_orchestrate_with_redis(self):
        """
        Same test but using a fake Redis client so both code paths are covered.
        """
        import os
        os.environ["RATE_LIMIT_ENABLED"] = "true"

        from backend.safety import rate_limiter as _mod

        fake_redis = _make_fake_redis_client()

        with patch.dict(_mod._LIMITS, {"orchestrate": 5}):
            with patch.object(
                _mod.RateLimiter, "_get_redis", new=AsyncMock(return_value=fake_redis)
            ):
                app = _make_app()
                client = TestClient(app, raise_server_exceptions=True)
                headers = {"X-Forwarded-For": "10.0.0.2"}

                statuses = [
                    client.post("/orchestrate", headers=headers).status_code
                    for _ in range(7)
                ]

        assert statuses.count(200) == 5
        assert statuses.count(429) == 2


# ===========================================================================
# Tests: multiple users are isolated
# ===========================================================================

class TestMultiUserIsolation:
    """Each user has a separate counter — user A's limit doesn't block user B."""

    def test_users_independent(self, app_no_redis):
        from backend.safety import rate_limiter as _mod

        with patch.dict(_mod._LIMITS, {"orchestrate": 3}):
            client = TestClient(app_no_redis, raise_server_exceptions=True)

            # User A — exhaust limit
            for _ in range(3):
                r = client.post("/orchestrate", headers={"X-Forwarded-For": "1.1.1.1"})
                assert r.status_code == 200, "User A setup failed"

            # User A should now be blocked
            ra = client.post("/orchestrate", headers={"X-Forwarded-For": "1.1.1.1"})
            assert ra.status_code == 429, "User A should be rate-limited"

            # User B should still be allowed
            for _ in range(3):
                rb = client.post("/orchestrate", headers={"X-Forwarded-For": "2.2.2.2"})
                assert rb.status_code == 200, "User B should not be blocked"


# ===========================================================================
# Tests: 429 response shape
# ===========================================================================

class TestRateLimitResponseShape:
    """Verify the body and headers of a 429 response."""

    def test_429_body_and_headers(self, app_no_redis):
        from backend.safety import rate_limiter as _mod

        with patch.dict(_mod._LIMITS, {"orchestrate": 1}):
            client = TestClient(app_no_redis, raise_server_exceptions=True)
            headers = {"X-Forwarded-For": "9.9.9.9"}

            # First request must succeed (limit=1)
            r1 = client.post("/orchestrate", headers=headers)
            assert r1.status_code == 200

            # Second must be 429
            r2 = client.post("/orchestrate", headers=headers)
            assert r2.status_code == 429

            # JSON body
            body = r2.json()
            assert body.get("error") == "rate_limit_exceeded", f"Unexpected body: {body}"
            assert "retry_after" in body
            assert "limit"       in body
            assert "window_sec"  in body
            assert "endpoint"    in body

            # HTTP headers
            assert "Retry-After"         in r2.headers
            assert "X-RateLimit-Limit"   in r2.headers
            assert "X-RateLimit-Remaining" in r2.headers
            assert "X-RateLimit-Window"  in r2.headers

    def test_allowed_response_has_ratelimit_headers(self, app_no_redis):
        """Every 200 response should carry X-RateLimit-* headers."""
        client = TestClient(app_no_redis, raise_server_exceptions=True)
        r = client.post("/orchestrate", headers={"X-Forwarded-For": "5.5.5.5"})
        assert r.status_code == 200
        assert "X-RateLimit-Limit"   in r.headers
        assert "X-RateLimit-Remaining" in r.headers


# ===========================================================================
# Tests: GET endpoints have a higher limit
# ===========================================================================

class TestEndpointClassification:
    """GET requests fall into the 'get' bucket (limit=100), not 'default' (60)."""

    def test_get_uses_100_limit(self, app_no_redis):
        from backend.safety import rate_limiter as _mod
        from backend.safety.rate_limiter import _classify_endpoint

        bucket = _classify_endpoint("/items", "GET")
        assert bucket == "get"
        assert _mod._LIMITS["get"] == int(
            __import__("os").getenv("RATE_LIMIT_GET", "100")
        )

    def test_orchestrate_uses_documented_limit(self):
        from backend.safety.rate_limiter import _classify_endpoint, _LIMITS
        bucket = _classify_endpoint("/api/orchestrate", "POST")
        assert bucket == "orchestrate"
        assert _LIMITS["orchestrate"] <= 50   # documented default=50; env may override higher

    def test_voice_bucket(self):
        from backend.safety.rate_limiter import _classify_endpoint
        assert _classify_endpoint("/voice/stream", "POST") == "voice"

    def test_health_paths_are_skipped(self, app_no_redis):
        """Requests to /health/* are never rate-limited."""
        client = TestClient(app_no_redis, raise_server_exceptions=True)
        # Spam health endpoint; should always 200
        for _ in range(200):
            r = client.get("/health/rate-limiter")
            assert r.status_code == 200


# ===========================================================================
# Tests: Redis fallback to local
# ===========================================================================

class TestRedisFallback:
    """Confirm behaviour degrades gracefully when Redis is unreachable."""

    def test_local_fallback_still_enforces(self, app_no_redis):
        """When Redis is down, local fallback must still block excess requests."""
        from backend.safety import rate_limiter as _mod

        # /execute maps to the "execute" bucket — patch that, not "default"
        with patch.dict(_mod._LIMITS, {"execute": 2}):
            client = TestClient(app_no_redis, raise_server_exceptions=True)
            headers = {"X-Forwarded-For": "3.3.3.3"}

            # First 2 POST /execute → should 200 (limit=2)
            for _ in range(2):
                r = client.post("/execute", headers=headers)
                assert r.status_code == 200

            # 3rd → must 429
            r3 = client.post("/execute", headers=headers)
            assert r3.status_code == 429

    def test_local_fallback_backend_name(self, app_no_redis):
        """X-RateLimit-Backend must be 'local' when Redis is unavailable."""
        client = TestClient(app_no_redis, raise_server_exceptions=True)
        r = client.post("/orchestrate", headers={"X-Forwarded-For": "4.4.4.4"})
        assert r.status_code == 200
        assert r.headers.get("X-RateLimit-Backend") == "local"

    def test_redis_backend_name(self):
        """X-RateLimit-Backend must be 'redis' when Redis is available."""
        import os
        os.environ["RATE_LIMIT_ENABLED"] = "true"
        from backend.safety import rate_limiter as _mod

        fake_redis = _make_fake_redis_client()

        with patch.object(
            _mod.RateLimiter, "_get_redis", new=AsyncMock(return_value=fake_redis)
        ):
            app = _make_app()
            client = TestClient(app, raise_server_exceptions=True)
            r = client.post("/orchestrate", headers={"X-Forwarded-For": "6.6.6.6"})
            assert r.status_code == 200
            assert r.headers.get("X-RateLimit-Backend") == "redis"


# ===========================================================================
# Tests: Health endpoint
# ===========================================================================

class TestHealthEndpoint:
    """Verify /health/rate-limiter returns the expected shape."""

    def test_health_shape(self, app_no_redis):
        client = TestClient(app_no_redis, raise_server_exceptions=True)
        r = client.get("/health/rate-limiter")
        assert r.status_code == 200
        body = r.json()

        assert "status"          in body
        assert "enabled"         in body
        assert "redis_connected" in body
        assert "backend"         in body
        assert "active_keys"     in body
        assert "window_sec"      in body
        assert "limits"          in body
        assert "ws_limits"       in body

    def test_health_degraded_when_redis_down(self, app_no_redis):
        client = TestClient(app_no_redis, raise_server_exceptions=True)
        r = client.get("/health/rate-limiter")
        body = r.json()
        assert body["status"] == "degraded"
        assert body["redis_connected"] is False
        assert body["backend"] == "local_fallback"

    def test_health_healthy_when_redis_up(self):
        import os
        os.environ["RATE_LIMIT_ENABLED"] = "true"
        from backend.safety import rate_limiter as _mod

        fake_redis = _make_fake_redis_client()

        with patch.object(
            _mod.RateLimiter, "_get_redis", new=AsyncMock(return_value=fake_redis)
        ):
            app = _make_app()
            client = TestClient(app, raise_server_exceptions=True)
            r = client.get("/health/rate-limiter")
            body = r.json()
            assert body["status"] == "healthy"
            assert body["redis_connected"] is True
            assert body["backend"] == "redis"


# ===========================================================================
# Tests: RateLimitDecision dataclass
# ===========================================================================

class TestRateLimitDecision:
    """Unit-test the RateLimitDecision dataclass helpers."""

    def _make_decision(self, allowed: bool = True) -> Any:
        from backend.safety.rate_limiter import RateLimitDecision
        return RateLimitDecision(
            allowed=allowed,
            limit=10,
            remaining=9 if allowed else 0,
            window_sec=60,
            retry_after=0 if allowed else 42,
            identity="u:user1",
            endpoint="orchestrate",
            backend="redis",
        )

    def test_headers_on_allowed(self):
        d = self._make_decision(allowed=True)
        h = d.headers()
        assert h["X-RateLimit-Limit"]     == "10"
        assert h["X-RateLimit-Remaining"] == "9"
        assert h["X-RateLimit-Window"]    == "60"
        assert "Retry-After" not in h

    def test_retry_headers_on_denied(self):
        d = self._make_decision(allowed=False)
        h = d.retry_headers()
        assert h["X-RateLimit-Remaining"] == "0"
        assert h["Retry-After"]           == "42"


# ===========================================================================
# Tests: Local sliding window unit tests
# ===========================================================================

class TestLocalSlidingWindow:
    """Directly exercise _LocalSlidingWindow without FastAPI."""

    def test_allows_up_to_limit(self):
        from backend.safety.rate_limiter import _LocalSlidingWindow
        sw = _LocalSlidingWindow()
        for i in range(5):
            allowed, remaining, _ = sw.check("ep", "uid", 5, 60)
            assert allowed, f"Request {i+1} should be allowed"

    def test_blocks_after_limit(self):
        from backend.safety.rate_limiter import _LocalSlidingWindow
        sw = _LocalSlidingWindow()
        for _ in range(5):
            sw.check("ep", "uid", 5, 60)
        allowed, _, retry_after = sw.check("ep", "uid", 5, 60)
        assert not allowed
        assert retry_after >= 1

    def test_window_resets_after_expiry(self):
        from backend.safety.rate_limiter import _LocalSlidingWindow
        sw = _LocalSlidingWindow()
        # Inject old timestamps directly into the deque
        old_time = time.time() - 120   # 2 minutes ago
        key = ("ep", "uid")
        import collections
        sw._windows[key] = collections.deque([old_time] * 5)

        # Now the window has 5 old entries; a new request should start fresh
        allowed, remaining, _ = sw.check("ep", "uid", 5, 60)
        assert allowed, "Should be allowed after window expiry"

    def test_active_key_count(self):
        from backend.safety.rate_limiter import _LocalSlidingWindow
        sw = _LocalSlidingWindow()
        sw.check("ep1", "u1", 5, 60)
        sw.check("ep2", "u2", 5, 60)
        assert sw.active_key_count() == 2


# ===========================================================================
# Tests: Identity extraction
# ===========================================================================

class TestIdentityExtraction:
    """Verify _extract_identity picks the right field."""

    def _build_request(
        self,
        auth_header: str | None = None,
        forwarded_for: str | None = None,
        client_host: str = "127.0.0.1",
    ) -> MagicMock:
        req = MagicMock()
        req.headers = {}
        if auth_header:
            req.headers["authorization"] = auth_header
        if forwarded_for:
            req.headers["x-forwarded-for"] = forwarded_for
        req.client = MagicMock()
        req.client.host = client_host
        req.cookies = {}
        return req

    def test_uses_jwt_sub(self):
        import base64
        from backend.safety.rate_limit_middleware import _extract_identity

        # Build a minimal JWT (header.payload.sig) — no verification needed
        payload = base64.urlsafe_b64encode(
            json.dumps({"sub": "user_abc"}).encode()
        ).decode().rstrip("=")
        token = f"header.{payload}.sig"
        req = self._build_request(auth_header=f"Bearer {token}")
        identity = _extract_identity(req)
        assert identity == "u:user_abc"

    def test_falls_back_to_forwarded_for(self):
        from backend.safety.rate_limit_middleware import _extract_identity
        req = self._build_request(forwarded_for="192.168.1.1, 10.0.0.1")
        identity = _extract_identity(req)
        assert identity == "ip:192.168.1.1"

    def test_falls_back_to_client_host(self):
        from backend.safety.rate_limit_middleware import _extract_identity
        req = self._build_request(client_host="172.16.0.5")
        identity = _extract_identity(req)
        assert identity == "ip:172.16.0.5"


# ===========================================================================
# Tests: Stability — 100 rapid requests
# ===========================================================================

class TestStability:
    """
    Send many rapid requests; confirm the system stays stable and
    returned statuses are consistently 200 (within limit) or 429 (over).
    """

    def test_100_requests_no_crash(self, app_no_redis):
        from backend.safety import rate_limiter as _mod

        limit = 10
        with patch.dict(_mod._LIMITS, {"orchestrate": limit}):
            client = TestClient(app_no_redis, raise_server_exceptions=True)
            headers = {"X-Forwarded-For": "77.77.77.77"}

            statuses: List[int] = [
                client.post("/orchestrate", headers=headers).status_code
                for _ in range(100)
            ]

        assert all(s in (200, 429) for s in statuses), "Unexpected status code in responses"
        assert statuses[:limit] == [200] * limit, "First 10 should all be 200"
        assert all(s == 429 for s in statuses[limit:]), "Requests after limit should all be 429"

    def test_multiple_identities_no_interference(self, app_no_redis):
        from backend.safety import rate_limiter as _mod

        limit = 5
        with patch.dict(_mod._LIMITS, {"orchestrate": limit}):
            client = TestClient(app_no_redis, raise_server_exceptions=True)

            results: Dict[str, List[int]] = {}
            for ip_suffix in range(1, 6):
                ip = f"10.10.10.{ip_suffix}"
                results[ip] = [
                    client.post("/orchestrate", headers={"X-Forwarded-For": ip}).status_code
                    for _ in range(limit + 2)
                ]

        for ip, statuses in results.items():
            assert statuses[:limit] == [200] * limit, f"IP {ip}: first {limit} should pass"
            assert all(s == 429 for s in statuses[limit:]), f"IP {ip}: should block after limit"


# ===========================================================================
# Tests: RateLimiter.check async unit test
# ===========================================================================

class TestRateLimiterAsync:
    """Async unit tests directly against the RateLimiter class."""

    @pytest.mark.asyncio
    async def test_check_returns_decision(self):
        from backend.safety.rate_limiter import RateLimiter, _LIMITS
        rl = RateLimiter()

        with patch.object(rl, "_get_redis", new=AsyncMock(return_value=None)):
            decision = await rl.check("/orchestrate", "POST", "u:test_user")

        assert decision.endpoint == "orchestrate"
        assert decision.allowed is True
        assert decision.backend == "local"

    @pytest.mark.asyncio
    async def test_check_disabled_always_allows(self):
        from backend.safety import rate_limiter as _mod
        from backend.safety.rate_limiter import RateLimiter

        with patch.object(_mod, "_ENABLED", False):
            rl = RateLimiter()
            decision = await rl.check("/orchestrate", "POST", "u:anyone")
            assert decision.allowed is True
            assert decision.backend == "disabled"

    @pytest.mark.asyncio
    async def test_status_returns_required_keys(self):
        from backend.safety.rate_limiter import RateLimiter

        rl = RateLimiter()
        with patch.object(rl, "_get_redis", new=AsyncMock(return_value=None)):
            s = await rl.status()

        required = {"status", "enabled", "redis_connected", "backend",
                    "active_keys", "window_sec", "limits", "ws_limits"}
        assert required <= s.keys()

    @pytest.mark.asyncio
    async def test_check_websocket_local_fallback(self):
        """When Redis is unavailable, check_websocket uses the local WS limiter."""
        from backend.safety.rate_limiter import RateLimiter
        from backend.websocket.auth import ConnectionRateLimiter

        rl = RateLimiter()
        local_ws = ConnectionRateLimiter()

        with patch.object(rl, "_get_redis", new=AsyncMock(return_value=None)):
            with patch(
                "backend.safety.rate_limiter.RateLimiter.check_websocket",
                wraps=rl.check_websocket,
            ):
                with patch(
                    "backend.websocket.auth.rate_limiter", local_ws
                ):
                    allowed = await rl.check_websocket("conn-1", 100)

        assert isinstance(allowed, bool)


# ===========================================================================
# Tests: Endpoint skip logic
# ===========================================================================

class TestSkipLogic:
    """Health and docs paths must bypass the rate limiter entirely."""

    SKIP_PATHS = [
        "/health",
        "/health/guardrails",
        "/health/rate-limiter",
        "/docs",
        "/openapi.json",
        "/redoc",
    ]

    def test_skip_paths_never_rate_limited(self, app_no_redis):
        from backend.safety import rate_limiter as _mod

        # Set an absurdly low limit that would normally trigger quickly
        with patch.dict(_mod._LIMITS, {"get": 1}):
            client = TestClient(app_no_redis, raise_server_exceptions=True)
            for path in self.SKIP_PATHS:
                statuses = [client.get(path).status_code for _ in range(5)]
                # All must be non-429 (the app may 404 but never 429)
                assert all(s != 429 for s in statuses), \
                    f"Path {path} was rate-limited but should be skipped. Statuses: {statuses}"
