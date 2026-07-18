"""
WebSocket authentication and per-connection rate limiting.

Authentication accepts either:
1) Query token (legacy compatibility)
2) HttpOnly cookie `cortex_access` (preferred)
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import os
import secrets
import time
from dataclasses import dataclass, field
from typing import Dict, Optional, Set

log = logging.getLogger(__name__)

_ENV = os.getenv("ENVIRONMENT", "development").lower()
_AUTH_REQUIRED_DEFAULT = "false" if _ENV == "development" else "true"
_AUTH_REQUIRED: bool = os.getenv("WS_AUTH_REQUIRED", _AUTH_REQUIRED_DEFAULT).lower() == "true"

MAX_MESSAGES_PER_MINUTE: int = int(os.getenv("WS_RATE_MSG_PER_MIN", "120"))
MAX_BYTES_PER_MINUTE: int = int(os.getenv("WS_RATE_BYTES_PER_MIN", str(2 * 1024 * 1024)))


@dataclass
class WSAuthContext:
    user_id: str
    token_hash: str
    is_authenticated: bool = True
    is_anonymous: bool = False
    scopes: list = field(default_factory=list)
    authenticated_at: float = field(default_factory=time.time)

    @classmethod
    def anonymous(cls) -> "WSAuthContext":
        return cls(
            user_id="anonymous",
            token_hash="",
            is_authenticated=True,
            is_anonymous=True,
        )


class AuthenticationError(Exception):
    def __init__(self, detail: str = "Unauthorized") -> None:
        super().__init__(detail)
        self.detail = detail


def authenticate(
    token: Optional[str],
    cookie_token: Optional[str] = None,
) -> WSAuthContext:
    """Authenticate using query token first, then cookie token."""
    candidate = token or cookie_token

    if candidate:
        from backend.auth.jwt_handler import decode_access_token

        payload = decode_access_token(candidate)
        if payload:
            return WSAuthContext(
                user_id=payload.get("sub", "authenticated"),
                token_hash=_hash(candidate),
                is_anonymous=False,
                scopes=["read", "write"],
            )

        if _AUTH_REQUIRED:
            log.warning("WS connection rejected - invalid JWT")
            raise AuthenticationError("Invalid or expired authentication token")

        log.warning("WS invalid token presented - accepting as anonymous (dev mode)")
        return WSAuthContext.anonymous()

    if _AUTH_REQUIRED:
        raise AuthenticationError("Missing authentication token")

    return WSAuthContext.anonymous()


def _secure_compare(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.encode())


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class ReconnectTokenStore:
    _tokens: Dict[str, dict] = {}

    def issue(self, session_id: str, topics: Set[str]) -> str:
        from backend.websocket.message_protocol import RECONNECT_TOKEN_TTL_S

        token = secrets.token_urlsafe(32)
        self._tokens[token] = {
            "session_id": session_id,
            "topics": set(topics),
            "expires_at": time.time() + RECONNECT_TOKEN_TTL_S,
        }
        self._evict_expired()
        return token

    def consume(self, token: str) -> Optional[dict]:
        record = self._tokens.pop(token, None)
        if record is None:
            return None
        if time.time() > record["expires_at"]:
            return None
        return record

    def _evict_expired(self) -> None:
        now = time.time()
        self._tokens = {t: r for t, r in self._tokens.items() if r["expires_at"] > now}


reconnect_token_store = ReconnectTokenStore()


class ConnectionRateLimiter:
    def __init__(self) -> None:
        self._windows: Dict[str, tuple] = {}

    def check(self, conn_id: str, msg_size_bytes: int) -> bool:
        now = time.monotonic()
        if conn_id not in self._windows:
            self._windows[conn_id] = (now, 0, 0)

        window_start, msg_count, byte_count = self._windows[conn_id]

        if now - window_start >= 60.0:
            window_start = now
            msg_count = 0
            byte_count = 0

        msg_count += 1
        byte_count += msg_size_bytes
        self._windows[conn_id] = (window_start, msg_count, byte_count)

        if msg_count > MAX_MESSAGES_PER_MINUTE:
            log.warning("Rate limit: conn=%s msg_count=%d", conn_id, msg_count)
            return False
        if byte_count > MAX_BYTES_PER_MINUTE:
            log.warning("Rate limit: conn=%s byte_count=%d", conn_id, byte_count)
            return False

        return True

    def remove(self, conn_id: str) -> None:
        self._windows.pop(conn_id, None)


rate_limiter = ConnectionRateLimiter()
