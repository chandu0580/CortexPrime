"""
CortexPrime — Request ID Middleware
=====================================

Injects a unique correlation ID into every HTTP request/response cycle.

Behaviour
---------
- Reads ``X-Request-ID`` from the incoming request headers.
  If present and a valid non-empty string → reuse it (allows upstream
  proxies / clients to propagate their own trace IDs).
- If absent or empty → generate a fresh UUID4.
- Stores the ID in ``request.state.request_id``.
- Sets ``backend.core.logging.set_request_id()`` so every subsequent log
  line in this async context automatically includes the request_id.
- Sets ``backend.core.logging.set_context()`` with user_id if a JWT is
  present (best-effort; never raises).
- Attaches ``X-Request-ID`` to every outgoing response header.
- Attaches the request_id to the active Sentry scope (when Sentry is
  configured) so every captured error links to the originating request.

Works for
---------
  FastAPI routes, middleware-processed routes, WebSocket upgrades
  (WS connections carry the ID from the initial HTTP handshake).
"""

from __future__ import annotations

import uuid
from typing import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from backend.core.logging import set_request_id, set_context, get_logger

log = get_logger(__name__)

# Maximum length we accept from an upstream X-Request-ID header.
# Anything longer is discarded and we generate our own.
_MAX_EXTERNAL_ID_LEN = 128


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Starlette/FastAPI middleware that attaches a correlation ID to every
    request and propagates it to the response.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        # ── 1. Resolve request ID ────────────────────────────────────────
        incoming = (request.headers.get("X-Request-ID") or "").strip()
        if incoming and len(incoming) <= _MAX_EXTERNAL_ID_LEN:
            request_id = incoming
        else:
            request_id = str(uuid.uuid4())

        # ── 2. Store on request state ────────────────────────────────────
        request.state.request_id = request_id

        # ── 3. Push into async context for structured logging ────────────
        set_request_id(request_id)

        # ── 4. Best-effort user_id extraction from JWT (no DB round-trip) ──
        _attach_user_id_from_jwt(request)

        # ── 5. Attach to Sentry scope ────────────────────────────────────
        _attach_sentry_context(request_id, request)

        # ── 6. Process request ───────────────────────────────────────────
        response: Response = await call_next(request)

        # ── 7. Echo ID back in response ──────────────────────────────────
        response.headers["X-Request-ID"] = request_id

        return response


# ─── Helpers ────────────────────────────────────────────────────────────────

def _attach_user_id_from_jwt(request: Request) -> None:
    """
    Best-effort extraction of ``sub`` claim from the Authorization header.
    Never raises — silently skips on any error.
    """
    try:
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return
        token = auth_header.removeprefix("Bearer ").strip()
        if not token:
            return
        # Decode payload without signature verification (we're inside the
        # perimeter; we only want the sub claim for logging / Sentry tagging)
        import base64, json as _json
        parts = token.split(".")
        if len(parts) != 3:
            return
        # Add padding for base64 decode
        padded = parts[1] + "=" * (-len(parts[1]) % 4)
        payload = _json.loads(base64.urlsafe_b64decode(padded))
        user_id = str(payload.get("sub", "") or "")
        if user_id:
            set_context(user_id=user_id)
    except Exception:
        pass  # Never let logging setup break the request


def _attach_sentry_context(request_id: str, request: Request) -> None:
    """
    Tag the active Sentry scope with the request_id so every error captured
    in this request links to the originating trace ID.
    """
    try:
        import sentry_sdk
        with sentry_sdk.configure_scope() as scope:
            scope.set_tag("request_id", request_id)
            scope.set_tag("http.method", request.method)
            scope.set_tag("http.path", request.url.path)
    except Exception:
        pass  # Sentry not configured or unavailable
