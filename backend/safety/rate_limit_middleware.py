"""
Rate Limit Middleware — CortexPrime
=====================================
FastAPI ``BaseHTTPMiddleware`` that enforces Redis-backed sliding-window
rate limits on every HTTP request.

Behaviour
---------
1. Skip health checks, docs, and WebSocket upgrade requests (these have
   their own rate limiting in the WS gateway).
2. Extract identity: JWT ``sub`` claim → fallback to ``X-Forwarded-For``
   header → fallback to client host IP.
3. Check the RateLimiter singleton.
4. Attach ``X-RateLimit-*`` headers to every allowed response.
5. Return ``429 Too Many Requests`` with ``Retry-After`` and a JSON body
   when the limit is exceeded.
6. Fire-and-forget audit log entry on every 429.
"""
from __future__ import annotations

import json
import logging
from typing import Callable, Optional

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

log = logging.getLogger(__name__)

# Paths that are never rate-limited
_SKIP_PREFIXES = (
    "/health",
    "/docs",
    "/openapi",
    "/redoc",
    "/favicon",
    "/static",
    "/_next",
)

# WebSocket upgrades are handled by the cognition gateway
_SKIP_UPGRADE = "websocket"


def _extract_identity(request: Request) -> str:
    """
    Determine the rate-limit identity key for this request.

        Priority:
            1. JWT ``sub`` claim from Authorization bearer token
            2. JWT ``sub`` from ``cortex_access`` cookie (httpOnly access cookie)
            3. ``X-Forwarded-For`` header (first IP in list — closest client)
            4. Direct client host IP

    Returns a short opaque string safe to use as a Redis key component.
    """
    # 1. Authorization: Bearer <token>
    auth_header = request.headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        token = auth_header[7:].strip()
        sub = _jwt_sub(token)
        if sub:
            return f"u:{sub}"

    # 2. Cookie-based JWT (httpOnly access cookie)
    cookie_token = request.cookies.get("cortex_access", "")
    if cookie_token:
        sub = _jwt_sub(cookie_token)
        if sub:
            return f"u:{sub}"

    # 3. X-Forwarded-For (reverse proxy / cloud load balancer)
    xff = request.headers.get("x-forwarded-for", "")
    if xff:
        ip = xff.split(",")[0].strip()
        if ip:
            return f"ip:{ip}"

    # 4. Direct client IP
    host = request.client.host if request.client else "unknown"
    return f"ip:{host}"


def _jwt_sub(token: str) -> Optional[str]:
    """Extract the ``sub`` claim without verifying the signature (identity only)."""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        import base64
        padded = parts[1] + "=" * (-len(parts[1]) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded))
        sub = payload.get("sub", "")
        return sub if sub else None
    except Exception:
        return None


def _should_skip(request: Request) -> bool:
    path = request.url.path
    if any(path.startswith(p) for p in _SKIP_PREFIXES):
        return True
    # WebSocket upgrade
    upgrade = request.headers.get("upgrade", "").lower()
    if upgrade == _SKIP_UPGRADE:
        return True
    return False


async def _audit_rate_limit(identity: str, endpoint: str, path: str) -> None:
    """Fire-and-forget audit log for rate limit violations."""
    try:
        import asyncio

        from backend.safety.audit_logger import audit_logger

        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(
                audit_logger.alog(
                    execution_id=f"ratelimit:{identity}",
                    agent="rate_limit_middleware",
                    action="rate_limit_triggered",
                    target=path,
                    risk_level="medium",
                    outcome="blocked",
                    reason=f"Rate limit exceeded for endpoint={endpoint} identity={identity}",
                    metadata={"endpoint": endpoint, "identity": identity, "path": path},
                )
            )
        else:
            audit_logger.log(
                execution_id=f"ratelimit:{identity}",
                agent="rate_limit_middleware",
                action="rate_limit_triggered",
                target=path,
                risk_level="medium",
                outcome="blocked",
                reason=f"Rate limit exceeded for endpoint={endpoint} identity={identity}",
                metadata={"endpoint": endpoint, "identity": identity, "path": path},
            )
    except Exception as exc:
        log.debug("Rate limit audit log failed (non-fatal): %s", exc)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    HTTP middleware that enforces per-user / per-IP sliding-window limits.

    Attach after CORSMiddleware and GuardrailsMiddleware in ``backend/main.py``.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)
        # Import singleton at construction time; errors here surface at startup
        from backend.safety.rate_limiter import rate_limiter
        self._limiter = rate_limiter

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if _should_skip(request):
            return await call_next(request)

        identity = _extract_identity(request)
        path     = request.url.path
        method   = request.method

        try:
            decision = await self._limiter.check(path, method, identity)
        except Exception as exc:
            # Limiter itself failed — fail open (allow the request) to avoid
            # taking down the service when the rate limiter has a bug.
            log.error("RateLimiter.check() raised unexpectedly: %s", exc, exc_info=True)
            return await call_next(request)

        if not decision.allowed:
            log.warning(
                "Rate limit: identity=%s endpoint=%s path=%s retry_after=%ds",
                identity, decision.endpoint, path, decision.retry_after,
            )
            # Async audit log (fire-and-forget, never blocks the 429)
            await _audit_rate_limit(identity, decision.endpoint, path)

            body = json.dumps({
                "error":       "rate_limit_exceeded",
                "detail":      (
                    f"Too many requests. Limit: {decision.limit} requests "
                    f"per {decision.window_sec}s window."
                ),
                "limit":       decision.limit,
                "window_sec":  decision.window_sec,
                "retry_after": decision.retry_after,
                "endpoint":    decision.endpoint,
                "backend":     decision.backend,
            })

            return Response(
                content     = body,
                status_code = 429,
                headers     = {
                    "Content-Type": "application/json",
                    **decision.retry_headers(),
                },
            )

        # Request is allowed — call next middleware/handler and inject headers
        response = await call_next(request)
        for k, v in decision.headers().items():
            response.headers[k] = v
        return response
