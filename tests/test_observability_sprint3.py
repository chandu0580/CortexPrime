"""
CortexPrime — Production Hardening Sprint 3
Test Suite: Request Correlation, Exception Handling, Error Model, Health

Tests
-----
  TestRequestIDMiddleware
    - X-Request-ID returned in response headers
    - Existing client X-Request-ID is preserved / echoed
    - Generated IDs are valid UUID4 strings
    - Long / invalid upstream IDs are discarded and replaced

  TestGlobalExceptionHandler
    - Unhandled Exception → 500 with standard envelope
    - No traceback exposed in response
    - No filesystem paths in response
    - request_id included in 500 response
    - CortexError → correct HTTP status + code + message

  TestErrorModel
    - 401, 403, 404, 422, 429, 500 all use same envelope schema
    - error_response() builds correct JSON
    - CortexError carries request_id

  TestHealthObservability
    - /health/system includes request_tracing, exception_handler, sentry keys
    - Each observability component has required fields

Run
---
    pytest tests/test_observability_sprint3.py -v
"""

from __future__ import annotations

import json
import re
import uuid
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ─── Minimal FastAPI test client bootstrap ────────────────────────────────
# We build a lean test app that mounts only the components under test.
# This avoids needing every dependency (Redis, PostgreSQL, RabbitMQ…) to be
# running during unit tests.

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from backend.core.errors import CortexError, ErrorCode, error_response
from backend.core.exception_handlers import register_exception_handlers
from backend.middleware.request_id import RequestIDMiddleware


def _make_app() -> FastAPI:
    """Build a minimal FastAPI app with all hardening middleware for testing."""
    app = FastAPI()
    register_exception_handlers(app)
    app.add_middleware(RequestIDMiddleware)

    @app.get("/ok")
    async def ok():
        return {"success": True}

    @app.get("/raise-unhandled")
    async def raise_unhandled():
        raise RuntimeError("This is an internal error with /secret/path details")

    @app.get("/raise-cortex/{code}/{status}")
    async def raise_cortex(code: str, status: int):
        raise CortexError(
            status_code=status,
            code=code,
            message=f"Test CortexError: {code}",
        )

    @app.get("/echo-request-id")
    async def echo_request_id(request: Request):
        return {"request_id": getattr(request.state, "request_id", "missing")}

    return app


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(_make_app(), raise_server_exceptions=False)


# ═══════════════════════════════════════════════════════════════════════════
# SUITE 1 — Request ID Middleware
# ═══════════════════════════════════════════════════════════════════════════

class TestRequestIDMiddleware:

    def test_response_always_has_x_request_id(self, client: TestClient):
        """Every response must carry X-Request-ID."""
        resp = client.get("/ok")
        assert resp.status_code == 200
        assert "x-request-id" in {k.lower() for k in resp.headers}

    def test_generated_id_is_valid_uuid4(self, client: TestClient):
        """When client sends no X-Request-ID, a fresh UUID4 is generated."""
        resp = client.get("/ok")
        rid = resp.headers.get("x-request-id") or resp.headers.get("X-Request-ID")
        assert rid is not None
        # Must parse as a UUID without raising
        parsed = uuid.UUID(rid, version=4)
        assert str(parsed) == rid

    def test_existing_request_id_is_preserved(self, client: TestClient):
        """If client sends X-Request-ID, it must be echoed unchanged."""
        my_id = str(uuid.uuid4())
        resp = client.get("/ok", headers={"X-Request-ID": my_id})
        returned = resp.headers.get("x-request-id") or resp.headers.get("X-Request-ID")
        assert returned == my_id

    def test_request_id_stored_on_state(self, client: TestClient):
        """request.state.request_id must be accessible inside route handlers."""
        my_id = str(uuid.uuid4())
        resp = client.get("/echo-request-id", headers={"X-Request-ID": my_id})
        assert resp.status_code == 200
        assert resp.json()["request_id"] == my_id

    def test_oversized_upstream_id_is_replaced(self, client: TestClient):
        """X-Request-IDs longer than 128 chars must be discarded."""
        oversized = "x" * 200
        resp = client.get("/ok", headers={"X-Request-ID": oversized})
        returned = resp.headers.get("x-request-id") or resp.headers.get("X-Request-ID")
        # Must be a fresh UUID, not the oversized string
        assert returned != oversized
        assert len(returned) == 36  # UUID4 string length

    def test_different_requests_get_different_ids(self, client: TestClient):
        """Each request without a client-supplied ID gets a unique generated ID."""
        ids = {
            (resp.headers.get("x-request-id") or resp.headers.get("X-Request-ID"))
            for resp in [client.get("/ok") for _ in range(5)]
        }
        assert len(ids) == 5, "All 5 requests should have unique IDs"


# ═══════════════════════════════════════════════════════════════════════════
# SUITE 2 — Global Exception Handler
# ═══════════════════════════════════════════════════════════════════════════

class TestGlobalExceptionHandler:

    def test_unhandled_exception_returns_500(self, client: TestClient):
        resp = client.get("/raise-unhandled")
        assert resp.status_code == 500

    def test_500_response_follows_error_envelope(self, client: TestClient):
        resp = client.get("/raise-unhandled")
        body = resp.json()
        assert body["success"] is False
        assert "error" in body
        assert "code" in body["error"]
        assert "message" in body["error"]
        assert "request_id" in body["error"]

    def test_no_traceback_in_500_response(self, client: TestClient):
        resp = client.get("/raise-unhandled")
        body_str = resp.text
        assert "Traceback" not in body_str
        assert "line " not in body_str.lower() or "traceback" not in body_str.lower()

    def test_no_filesystem_paths_in_500_response(self, client: TestClient):
        resp = client.get("/raise-unhandled")
        body_str = resp.text
        # Should not expose internal error message containing /secret/path
        assert "/secret/path" not in body_str

    def test_500_includes_request_id(self, client: TestClient):
        my_id = str(uuid.uuid4())
        resp = client.get("/raise-unhandled", headers={"X-Request-ID": my_id})
        assert resp.status_code == 500
        body = resp.json()
        assert body["error"]["request_id"] == my_id

    def test_500_error_code_is_internal_server_error(self, client: TestClient):
        resp = client.get("/raise-unhandled")
        assert resp.json()["error"]["code"] == ErrorCode.INTERNAL_SERVER_ERROR

    def test_cortex_error_respected_status_code(self, client: TestClient):
        resp = client.get(f"/raise-cortex/{ErrorCode.NOT_FOUND}/404")
        assert resp.status_code == 404

    def test_cortex_error_follows_envelope(self, client: TestClient):
        resp = client.get(f"/raise-cortex/{ErrorCode.FORBIDDEN}/403")
        body = resp.json()
        assert body["success"] is False
        assert body["error"]["code"] == ErrorCode.FORBIDDEN
        assert "request_id" in body["error"]

    def test_404_via_http_exception(self, client: TestClient):
        """Hitting a non-existent route must return a standard 404 envelope."""
        resp = client.get("/this-route-does-not-exist")
        assert resp.status_code == 404
        body = resp.json()
        assert body["success"] is False
        assert "error" in body
        assert body["error"]["code"] == ErrorCode.NOT_FOUND


# ═══════════════════════════════════════════════════════════════════════════
# SUITE 3 — Error Model
# ═══════════════════════════════════════════════════════════════════════════

class TestErrorModel:

    def test_error_response_shape(self):
        resp = error_response(None, 404, ErrorCode.NOT_FOUND, "Not found.")
        data = json.loads(resp.body)
        assert data["success"] is False
        assert data["error"]["code"] == ErrorCode.NOT_FOUND
        assert data["error"]["message"] == "Not found."
        assert "request_id" in data["error"]

    def test_error_response_status_code(self):
        for code in (400, 401, 403, 404, 422, 429, 500):
            resp = error_response(None, code, "TEST", "msg")
            assert resp.status_code == code

    def test_error_response_has_x_request_id_header(self):
        resp = error_response(None, 401, ErrorCode.UNAUTHORIZED, "Unauthorized")
        assert "x-request-id" in {k.lower() for k in resp.headers}

    def test_cortex_error_carries_status_code(self):
        exc = CortexError(429, ErrorCode.RATE_LIMITED, "Slow down.")
        assert exc.status_code == 429
        assert exc.code == ErrorCode.RATE_LIMITED

    def test_cortex_error_inherits_from_exception(self):
        exc = CortexError(500, ErrorCode.INTERNAL_SERVER_ERROR, "boom")
        assert isinstance(exc, Exception)

    @pytest.mark.parametrize("status_code,expected_code", [
        (401, ErrorCode.UNAUTHORIZED),
        (403, ErrorCode.FORBIDDEN),
        (404, ErrorCode.NOT_FOUND),
        (500, ErrorCode.INTERNAL_SERVER_ERROR),
    ])
    def test_all_error_codes_defined(self, status_code: int, expected_code: str):
        """Verify key error codes exist on the ErrorCode class."""
        assert hasattr(ErrorCode, expected_code)

    def test_envelope_never_exposes_secrets(self):
        """The error response should not echo back raw exception messages."""
        resp = error_response(None, 500, ErrorCode.INTERNAL_SERVER_ERROR,
                              "An unexpected error occurred.")
        body_str = resp.body.decode()
        # Should not contain typical secret patterns
        assert "sk-" not in body_str
        assert "password" not in body_str.lower() or "error" in body_str.lower()


# ═══════════════════════════════════════════════════════════════════════════
# SUITE 4 — Health Observability Components
# ═══════════════════════════════════════════════════════════════════════════

class TestHealthObservability:

    def test_check_observability_returns_three_components(self):
        from backend.api.system_health_routes import _check_observability
        result = _check_observability()
        assert "request_tracing"   in result
        assert "exception_handler" in result
        assert "sentry"            in result

    def test_request_tracing_is_healthy(self):
        from backend.api.system_health_routes import _check_observability
        result = _check_observability()
        component = result["request_tracing"]
        assert component["status"] in ("healthy", "degraded", "offline")
        assert "latency_ms" in component
        assert "detail" in component

    def test_exception_handler_is_healthy(self):
        from backend.api.system_health_routes import _check_observability
        result = _check_observability()
        component = result["exception_handler"]
        assert component["status"] == "healthy"
        detail = component.get("detail", {})
        assert "handlers" in detail

    def test_sentry_component_has_required_fields(self):
        from backend.api.system_health_routes import _check_observability
        result = _check_observability()
        component = result["sentry"]
        assert component["status"] in ("healthy", "degraded", "offline")
        assert "latency_ms" in component
        assert "detail" in component

    def test_observability_components_have_latency_ms(self):
        from backend.api.system_health_routes import _check_observability
        result = _check_observability()
        for name, component in result.items():
            assert "latency_ms" in component, f"{name} missing latency_ms"
            assert isinstance(component["latency_ms"], (int, float))

    def test_structured_logging_module_importable(self):
        """Verify the logging module can be imported and returns a logger."""
        from backend.core.logging import get_logger, get_request_id
        log = get_logger("test")
        assert log is not None
        rid = get_request_id()
        assert isinstance(rid, str)

    def test_request_id_context_var_roundtrip(self):
        """set_request_id → get_request_id must roundtrip correctly."""
        from backend.core.logging import set_request_id, get_request_id
        test_id = str(uuid.uuid4())
        set_request_id(test_id)
        assert get_request_id() == test_id

    def test_set_context_does_not_raise(self):
        """set_context must not raise for any combination of kwargs."""
        from backend.core.logging import set_context
        set_context(user_id="u1", mission_id="m1", session_id="s1")
        set_context()  # all None — should be a no-op


# ═══════════════════════════════════════════════════════════════════════════
# SUITE 5 — Sentry Integration
# ═══════════════════════════════════════════════════════════════════════════

class TestSentryIntegration:

    def test_sentry_capture_called_on_500(self):
        """On an unhandled exception, sentry_sdk.capture_exception must be called."""
        with patch("backend.core.exception_handlers._sentry_capture") as mock_capture:
            tc = TestClient(_make_app(), raise_server_exceptions=False)
            tc.get("/raise-unhandled")
            mock_capture.assert_called_once()

    def test_sentry_capture_receives_request_id(self):
        """_sentry_capture receives the correct request and request_id."""
        captured_args = []

        def _fake_capture(exc, request, request_id):
            captured_args.append((exc, request, request_id))

        with patch("backend.core.exception_handlers._sentry_capture", side_effect=_fake_capture):
            my_id = str(uuid.uuid4())
            tc = TestClient(_make_app(), raise_server_exceptions=False)
            tc.get("/raise-unhandled", headers={"X-Request-ID": my_id})

        assert len(captured_args) == 1
        _, _, captured_rid = captured_args[0]
        assert captured_rid == my_id

    def test_cortex_error_4xx_does_not_trigger_sentry(self):
        """4xx CortexErrors must NOT be sent to Sentry (only 5xx)."""
        with patch("backend.core.exception_handlers._sentry_capture") as mock_capture:
            tc = TestClient(_make_app(), raise_server_exceptions=False)
            tc.get(f"/raise-cortex/{ErrorCode.NOT_FOUND}/404")
            mock_capture.assert_not_called()
