"""
CortexPrime — Global Exception Handlers
=========================================

Registered on the FastAPI app in main.py.  Catches every unhandled exception
and returns a standardized error envelope — never exposing stack traces,
filesystem paths, or secrets to API clients.

Handlers registered
-------------------
  CortexError            → maps to its own status code + code + message
  RequestValidationError → 422 with field-level detail (sanitized)
  HTTPException          → maps FastAPI HTTP exceptions to the error envelope
  Exception              → catch-all 500 — logs + Sentry-captures internally

Internal behaviour
------------------
  - Logs the full exception at ERROR level (with traceback for 500s)
  - Calls sentry_sdk.capture_exception() when Sentry is configured
  - Attaches request_id to both the response and the Sentry event
  - Never calls str(exc) on the response — uses safe canned messages
"""

from __future__ import annotations

import traceback

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend.core.errors import (
    CortexError,
    ErrorCode,
    http_error_response,
)
from backend.core.logging import get_logger, get_request_id

log = get_logger(__name__)


# ─── Sentry helper ────────────────────────────────────────────────────────

def _sentry_capture(exc: Exception, request: Request, request_id: str) -> None:
    """Capture exception to Sentry with correlation context attached."""
    try:
        import sentry_sdk
        with sentry_sdk.push_scope() as scope:
            scope.set_tag("request_id", request_id)
            scope.set_tag("http.method", request.method)
            scope.set_tag("http.path",   request.url.path)
            scope.set_context("request", {
                "method":     request.method,
                "url":        str(request.url),
                "request_id": request_id,
            })
            sentry_sdk.capture_exception(exc)
    except Exception:
        pass  # Never let Sentry reporting break the response


# ─── Handler registration ─────────────────────────────────────────────────

def register_exception_handlers(app: FastAPI) -> None:
    """
    Register all exception handlers on the FastAPI application instance.
    Call this in main.py after the app is created, before middleware.
    """

    # ── CortexError — domain exception with explicit HTTP mapping ──────────
    @app.exception_handler(CortexError)
    async def cortex_error_handler(request: Request, exc: CortexError) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None) or get_request_id()
        log.warning(
            "CortexError: %s %s — %s: %s",
            request.method, request.url.path, exc.code, exc.message,
        )
        if exc.status_code >= 500:
            _sentry_capture(exc, request, request_id)
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "error": {
                    "code":       exc.code,
                    "message":    exc.message,
                    "request_id": request_id,
                },
            },
            headers={"X-Request-ID": request_id},
        )

    # ── RequestValidationError — Pydantic / FastAPI validation failures ────
    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None) or get_request_id()
        log.info(
            "Validation error: %s %s — %d field error(s)",
            request.method, request.url.path, len(exc.errors()),
        )
        # Sanitize: only expose field location + type, never the raw input value
        sanitized = [
            {"field": " → ".join(str(loc) for loc in err.get("loc", [])), "type": err.get("type", "")}
            for err in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content={
                "success": False,
                "error": {
                    "code":       ErrorCode.UNPROCESSABLE,
                    "message":    "Request validation failed. Check the fields listed in 'detail'.",
                    "detail":     sanitized,
                    "request_id": request_id,
                },
            },
            headers={"X-Request-ID": request_id},
        )

    # ── StarletteHTTPException — FastAPI HTTPException (401, 403, 404 …) ──
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        getattr(request.state, "request_id", None) or get_request_id()
        log.info(
            "HTTP %d: %s %s", exc.status_code, request.method, request.url.path,
        )
        return http_error_response(request, exc.status_code)

    # ── Exception — global catch-all for all unhandled exceptions ─────────
    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None) or get_request_id()

        # Log the full traceback internally — NEVER send to client
        log.error(
            "Unhandled exception: %s %s — %s: %s\n%s",
            request.method,
            request.url.path,
            type(exc).__name__,
            str(exc),
            traceback.format_exc(),
            extra={"request_id": request_id},
        )

        # Capture to Sentry with full context
        _sentry_capture(exc, request, request_id)

        # Return sanitized 500
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": {
                    "code":       ErrorCode.INTERNAL_SERVER_ERROR,
                    "message":    "An unexpected error occurred. Please try again or contact support.",
                    "request_id": request_id,
                },
            },
            headers={"X-Request-ID": request_id},
        )
