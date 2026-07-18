from __future__ import annotations

from typing import Any, Optional

from backend.identity.jwt.key_store import KeyStore
from backend.identity.session.session_runtime import SessionRuntime


class IdentityHealth:
    def __init__(self, key_store: KeyStore, session_runtime: SessionRuntime):
        self._key_store = key_store
        self._session_runtime = session_runtime

    async def check(self) -> dict[str, Any]:
        jwt_health = await self._key_store.health()
        session_count = await self._session_runtime.count_active_sessions()

        redis_ok = False
        try:
            from backend.infrastructure.redis.connection import redis_connection
            redis_ok = await redis_connection.ping()
        except Exception:
            pass

        return {
            "status": "healthy" if jwt_health.get("healthy") else "degraded",
            "identity_runtime": {
                "status": "ready",
                "key_store": "ready" if jwt_health.get("healthy") else "degraded",
                "session_runtime": "ready" if session_count >= 0 else "degraded",
                "redis": "connected" if redis_ok else "disconnected",
            },
            "jwt": jwt_health,
            "sessions": {
                "active_count": session_count,
                "status": "ready" if session_count >= 0 else "degraded",
            },
            "repositories": {
                "status": "ready",
            },
        }
