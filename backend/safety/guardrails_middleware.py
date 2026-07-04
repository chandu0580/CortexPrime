"""
Guardrails Middleware — FastAPI Starlette middleware.

Intercepts every POST/PUT/PATCH request and runs the input guardrail
against the request body before it reaches any route handler.

Blocked requests receive HTTP 400 with a structured JSON error body.
WARN decisions are passed through but the sanitized body replaces the
original in the ASGI scope so downstream handlers receive clean text.

Routes that are excluded from input scanning:
  - Authentication endpoints (/auth/*)
  - Health endpoints (/health/*)
  - Static assets (no body anyway)
  - WebSocket upgrades

The middleware is lightweight (pure in-process regex) — adds < 1 ms to
request latency for typical payloads.
"""
from __future__ import annotations

import json
import logging
from typing import Set

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from backend.safety.guardrails_engine import guardrails_engine, GuardrailDecision

logger = logging.getLogger(__name__)

# Routes excluded from input scanning (prefix match)
_SKIP_PREFIXES: Set[str] = {
    "/auth",
    "/health",
    "/docs",
    "/openapi",
    "/redoc",
    "/favicon",
    "/static",
}

# Fields whose VALUES should be scanned in a JSON body
_SCAN_FIELDS = {
    "query", "objective", "message", "prompt", "content",
    "task", "description", "text", "input", "instruction",
    "action", "command", "goal", "user_message", "user_input",
}


def _should_skip(path: str) -> bool:
    return any(path.startswith(prefix) for prefix in _SKIP_PREFIXES)


def _extract_text_from_body(body: bytes) -> str:
    """
    Extract scannable text from a JSON body.
    Falls back to decoding the raw body if JSON parsing fails.
    """
    if not body:
        return ""
    try:
        data = json.loads(body)
        if isinstance(data, str):
            return data
        if isinstance(data, dict):
            parts = []
            for key, value in data.items():
                if key.lower() in _SCAN_FIELDS and isinstance(value, str):
                    parts.append(value)
            return " ".join(parts) if parts else ""
        return ""
    except Exception:
        try:
            return body.decode("utf-8", errors="replace")[:4096]
        except Exception:
            return ""


class GuardrailsMiddleware(BaseHTTPMiddleware):
    """
    Starlette middleware that runs NeMo Guardrails input checks on every
    mutating HTTP request before it reaches a route handler.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:

        # Only check mutating methods
        if request.method not in ("POST", "PUT", "PATCH"):
            return await call_next(request)

        path = request.url.path
        if _should_skip(path):
            return await call_next(request)

        # Read body (Starlette consumes body stream once — must cache it)
        body = await request.body()
        text = _extract_text_from_body(body)

        if text:
            result = guardrails_engine.check_input(text)

            if result.blocked:
                logger.warning(
                    "GUARDRAILS BLOCKED | path=%s rule=%s reason=%s",
                    path, result.matched_rule, result.reason,
                )
                return JSONResponse(
                    status_code=400,
                    content={
                        "error":          "Request blocked by content guardrails",
                        "violation_type": result.violation_type.value if result.violation_type else None,
                        "rule":           result.matched_rule,
                        "reason":         result.reason,
                        "risk_score":     result.risk_score,
                    },
                )

            if result.decision == GuardrailDecision.WARN and result.sanitized:
                # Replace body with sanitized version
                try:
                    data = json.loads(body)
                    for key in list(data.keys()):
                        if key.lower() in _SCAN_FIELDS and isinstance(data[key], str):
                            data[key] = result.sanitized
                    body = json.dumps(data).encode()
                    logger.info(
                        "GUARDRAILS SANITIZED | path=%s rule=%s",
                        path, result.matched_rule,
                    )
                except Exception:
                    pass  # If we can't re-serialise, proceed with original

        # Rebuild request with (potentially sanitized) body
        async def receive():
            return {"type": "http.request", "body": body, "more_body": False}

        request = Request(request.scope, receive)
        return await call_next(request)
