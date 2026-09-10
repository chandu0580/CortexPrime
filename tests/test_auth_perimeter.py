"""Phase 11.1 (ADR-121): the authentication perimeter of the V1 application.

Every request into ``backend.main`` must carry a verified access token unless
its path is explicitly public or is signed machine ingress. These tests mount
the middleware on a minimal app so the rules are proven without the full
lifespan; a separate check pins the registration in ``backend/main.py`` by
reading the source, because a perimeter that is not installed protects nothing.
"""
from __future__ import annotations

import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch

import jwt
import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-for-pytest-suite-do-not-use-in-prod")

from backend.auth.jwt_handler import create_access_token  # noqa: E402
from backend.safety.auth_perimeter import (  # noqa: E402
    FENCE_EXEMPT_PREFIXES,
    PUBLIC_EXACT,
    SIGNED_INGRESS,
    V1_TENANT_ENV,
    AuthPerimeterMiddleware,
    is_public_path,
    v1_tenant_verdict,
)


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


@pytest.fixture(autouse=True)
def _no_declared_tenant(monkeypatch):
    monkeypatch.delenv(V1_TENANT_ENV, raising=False)


def _app() -> FastAPI:
    app = FastAPI()

    @app.get("/health")
    async def health():
        return {"ok": True}

    @app.get("/api/auth/health")
    async def auth_health():
        return {"ok": True}

    @app.get("/api/v1/health")
    async def v1_health():
        return {"ok": True}

    @app.get("/api/memory/status")
    async def memory(request: Request):
        ident = getattr(request.state, "perimeter", None)
        return {"principal": ident.principal_id if ident else None,
                "tenant": ident.tenant_id if ident else None}

    @app.post("/api/infrastructure/ingest/pod")
    async def ingest():
        return {"status": "ingested"}

    @app.post("/api/github/webhook")
    async def webhook():
        return {"reached_route": True}

    @app.get("/api/tenants")
    async def tenants():
        return {"reached_route": True}

    @app.options("/api/memory/status")
    async def preflight():
        return {"preflight": True}

    app.add_middleware(AuthPerimeterMiddleware)
    return app


def _client() -> TestClient:
    return TestClient(_app())


def _bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _expired_token() -> str:
    from backend.auth.jwt_handler import _ALGORITHM, _get_secret

    now = datetime.now(timezone.utc)
    return jwt.encode(
        {"sub": "old", "role": "operator", "type": "access", "jti": "x" * 32,
         "iat": now - timedelta(hours=2), "exp": now - timedelta(hours=1)},
        _get_secret(), algorithm=_ALGORITHM)


class TestPublicSurface:
    def test_public_paths_need_no_token(self):
        c = _client()
        assert c.get("/health").status_code == 200
        assert c.get("/api/auth/health").status_code == 200
        assert c.get("/api/v1/health").status_code == 200

    def test_public_lists_are_explicit_and_small(self):
        # The allow-list is the boundary. Anything that grows it is a review item.
        assert "/health" in PUBLIC_EXACT and "/metrics" in PUBLIC_EXACT
        assert is_public_path("/api/auth/login")
        # Subsystem liveness probes are public by the existing auth-enforcement contract.
        assert is_public_path("/governance/health") and is_public_path("/api/voice/v2/health")
        assert not is_public_path("/api/healthcheck") and not is_public_path("/api/health-report")
        assert not is_public_path("/api/memory/status")
        assert not is_public_path("/api/infrastructure/ingest/pod")
        assert SIGNED_INGRESS == frozenset({"/api/github/webhook", "/api/gitlab/webhook"})

    def test_preflight_passes(self):
        assert _client().options("/api/memory/status").status_code == 200

    def test_signed_ingress_reaches_its_verifying_route(self):
        # The perimeter defers to the route, which verifies the provider secret
        # (covered in test_ingress_boundary). Here: it is not blocked for lack of a JWT.
        r = _client().post("/api/github/webhook", content=b"{}")
        assert r.status_code == 200 and r.json()["reached_route"] is True


class TestAuthentication:
    def test_no_token_is_401_with_challenge(self):
        r = _client().get("/api/memory/status")
        assert r.status_code == 401
        assert r.headers["www-authenticate"] == "Bearer"
        assert r.json()["error"] == "authentication_required"

    def test_state_changing_route_without_token_is_401(self):
        assert _client().post("/api/infrastructure/ingest/pod", json={"payload": {}}).status_code == 401

    def test_garbage_token_is_401(self):
        assert _client().get("/api/memory/status", headers=_bearer("not.a.jwt")).status_code == 401

    def test_expired_token_is_401(self):
        assert _client().get("/api/memory/status", headers=_bearer(_expired_token())).status_code == 401

    def test_wrong_secret_is_401(self):
        forged = jwt.encode({"sub": "x", "type": "access", "jti": "j",
                             "iat": datetime.now(timezone.utc),
                             "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
                            "some-other-secret-that-is-long-enough-000", algorithm="HS256")
        assert _client().get("/api/memory/status", headers=_bearer(forged)).status_code == 401

    def test_revoked_token_is_401(self):
        token = create_access_token(user_id="alice", role="operator")
        with patch("backend.auth.token_blacklist.TokenBlacklist.is_revoked",
                   new_callable=AsyncMock, return_value=True):
            assert _client().get("/api/memory/status", headers=_bearer(token)).status_code == 401

    def test_verifier_crash_fails_closed(self):
        token = create_access_token(user_id="alice", role="operator")
        with patch("backend.auth.dependencies.verify_request_token",
                   new_callable=AsyncMock, side_effect=RuntimeError("boom")):
            assert _client().get("/api/memory/status", headers=_bearer(token)).status_code == 401

    def test_valid_token_passes_and_identity_is_on_request_state(self):
        token = create_access_token(user_id="alice", role="operator")
        r = _client().get("/api/memory/status", headers=_bearer(token))
        assert r.status_code == 200
        assert r.json() == {"principal": "alice", "tenant": None}

    def test_cookie_token_is_accepted(self):
        token = create_access_token(user_id="alice", role="operator")
        r = _client().get("/api/memory/status", cookies={"cortex_access": token})
        assert r.status_code == 200


class TestV1TenantFence:
    def test_verdict_table(self, monkeypatch):
        monkeypatch.delenv(V1_TENANT_ENV, raising=False)
        assert v1_tenant_verdict(None) == (True, "single_operator")
        assert v1_tenant_verdict("t-a")[0] is False
        monkeypatch.setenv(V1_TENANT_ENV, "t-a")
        assert v1_tenant_verdict("t-a") == (True, "declared_tenant")
        assert v1_tenant_verdict("t-b")[0] is False
        assert v1_tenant_verdict(None)[0] is False
        assert v1_tenant_verdict("")[0] is False

    def test_undeclared_refuses_tenant_bearing_token(self):
        token = create_access_token(user_id="alice", role="operator", tenant_id="tenant-a")
        r = _client().get("/api/memory/status", headers=_bearer(token))
        assert r.status_code == 403
        assert r.json()["error"] == "tenant_not_admitted"
        assert V1_TENANT_ENV in r.json()["detail"]

    def test_declared_admits_only_that_tenant(self, monkeypatch):
        monkeypatch.setenv(V1_TENANT_ENV, "tenant-a")
        own = create_access_token(user_id="alice", role="operator", tenant_id="tenant-a")
        other = create_access_token(user_id="mallory", role="operator", tenant_id="tenant-b")
        none = create_access_token(user_id="op", role="operator")
        c = _client()
        assert c.get("/api/memory/status", headers=_bearer(own)).status_code == 200
        assert c.get("/api/memory/status", headers=_bearer(other)).status_code == 403
        assert c.get("/api/memory/status", headers=_bearer(none)).status_code == 403
        # Cross-tenant mutation is refused at the same edge.
        assert c.post("/api/infrastructure/ingest/pod", json={"payload": {}},
                      headers=_bearer(other)).status_code == 403

    def test_refusal_is_audited_without_secrets(self, monkeypatch):
        monkeypatch.setenv(V1_TENANT_ENV, "tenant-a")
        other = create_access_token(user_id="mallory", role="operator", tenant_id="tenant-b")
        with patch("backend.safety.audit_logger.audit_logger.log") as alog:
            _client().get("/api/memory/status", headers=_bearer(other))
        assert alog.call_count == 1
        kwargs = alog.call_args.kwargs
        assert kwargs["action"] == "perimeter.tenant_refused"
        assert kwargs["user"] == "mallory"
        assert kwargs["metadata"]["tenant_id"] == "tenant-b"
        assert other not in str(kwargs)

    def test_governed_tenant_routes_are_exempt_from_the_fence(self):
        assert "/api/tenants" in FENCE_EXEMPT_PREFIXES
        token = create_access_token(user_id="admin", role="admin", tenant_id="tenant-a")
        r = _client().get("/api/tenants", headers=_bearer(token))
        assert r.status_code == 200  # authenticated; the route's own require_admin decides


class TestRegistration:
    def test_main_registers_the_perimeter_unconditionally(self):
        source = (Path(__file__).resolve().parents[1] / "backend" / "main.py").read_text(encoding="utf-8")
        assert "app.add_middleware(AuthPerimeterMiddleware)" in source
        # Not inside a try/except: a perimeter that fails to install is a boot failure.
        block = source.split("app.add_middleware(AuthPerimeterMiddleware)")[0][-600:]
        assert not re.search(r"\n\s*try:\s*\n(?:(?!\n\n).)*$", block, re.S)
        # Installed after the tenant middleware and before the rate limiter, so
        # it sits just inside the limiter and outside everything else.
        assert source.index("TenantContextMiddleware)") < source.index("AuthPerimeterMiddleware)") \
            < source.index("RateLimitMiddleware)")
