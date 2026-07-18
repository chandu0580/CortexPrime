from __future__ import annotations

import json
import logging
import secrets
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from backend.identity.interfaces.session import (
    Session,
    SessionCreateRequest,
    SessionProvider,
)
from backend.identity.jwt.keys import IdentityRedisKeys

log = logging.getLogger(__name__)

try:
    import redis.asyncio as aioredis
except ImportError:
    aioredis = None


class SessionRuntime(SessionProvider):
    def __init__(self):
        self._redis_client: Optional[Any] = None

    async def _get_redis(self) -> Optional[Any]:
        if self._redis_client is not None:
            try:
                await self._redis_client.ping()
                return self._redis_client
            except Exception:
                self._redis_client = None
        try:
            from backend.infrastructure.redis.connection import redis_connection
            if await redis_connection.ensure_connected():
                self._redis_client = redis_connection.client
                return self._redis_client
        except Exception:
            pass
        return None

    def _session_to_dict(self, session: Session) -> dict[str, Any]:
        return {
            "session_id": session.session_id,
            "user_id": session.user_id,
            "tenant_id": session.tenant_id,
            "jti": session.jti,
            "created_at": session.created_at.isoformat(),
            "expires_at": session.expires_at.isoformat() if session.expires_at else None,
            "last_activity_at": session.last_activity_at.isoformat() if session.last_activity_at else None,
            "metadata": session.metadata,
            "is_revoked": session.is_revoked,
        }

    def _dict_to_session(self, data: dict[str, Any]) -> Session:
        return Session(
            session_id=data["session_id"],
            user_id=data["user_id"],
            tenant_id=data.get("tenant_id"),
            jti=data.get("jti", ""),
            created_at=datetime.fromisoformat(data["created_at"]) if isinstance(data.get("created_at"), str) else datetime.now(timezone.utc),
            expires_at=datetime.fromisoformat(data["expires_at"]) if data.get("expires_at") else None,
            last_activity_at=datetime.fromisoformat(data["last_activity_at"]) if data.get("last_activity_at") else None,
            metadata=data.get("metadata", {}),
            is_revoked=data.get("is_revoked", False),
        )

    async def create_session(self, request: SessionCreateRequest) -> Session:
        session_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        session = Session(
            session_id=session_id,
            user_id=request.user_id,
            tenant_id=request.tenant_id,
            jti=request.jti or secrets.token_hex(16),
            created_at=now,
            expires_at=request.expires_at,
            last_activity_at=now,
            metadata=request.metadata,
            is_revoked=False,
        )
        redis = await self._get_redis()
        if redis is not None:
            try:
                key = IdentityRedisKeys.session_key(request.user_id)
                pipe = redis.pipeline()
                pipe.zremrangebyscore(key, "-inf", time.time())
                pipe.zadd(key, {session_id: session.expires_at.timestamp() if session.expires_at else (time.time() + 3600)})
                if session.expires_at:
                    pipe.expireat(key, int(session.expires_at.timestamp()) + 60)
                await pipe.execute()
                session_key = f"{key}:{session_id}"
                await redis.setex(session_key, 86400, json.dumps(self._session_to_dict(session), default=str))
            except Exception as exc:
                log.debug("Session redis write error (non-fatal): %s", exc)
        log.info("Session created: session_id=%s user=%s", session_id[:8], request.user_id[:16])
        return session

    async def get_session(self, session_id: str) -> Optional[Session]:
        redis = await self._get_redis()
        if redis is None:
            return None
        try:
            keys = await redis.keys(f"*{session_id}")
            for key in keys:
                raw = await redis.get(key)
                if raw:
                    data = json.loads(raw)
                    if data.get("session_id") == session_id:
                        return self._dict_to_session(data)
        except Exception:
            pass
        return None

    async def validate_session(self, session_id: str) -> bool:
        redis = await self._get_redis()
        if redis is None:
            return False
        try:
            keys = await redis.keys(f"*{session_id}")
            for key in keys:
                raw = await redis.get(key)
                if raw:
                    data = json.loads(raw)
                    if data.get("session_id") == session_id and not data.get("is_revoked"):
                        exp = data.get("expires_at")
                        if exp:
                            exp_dt = datetime.fromisoformat(exp) if isinstance(exp, str) else None
                            if exp_dt and exp_dt < datetime.now(timezone.utc):
                                return False
                        return True
        except Exception:
            pass
        return False

    async def revoke_session(self, session_id: str) -> bool:
        redis = await self._get_redis()
        if redis is None:
            return False
        try:
            keys = await redis.keys(f"*{session_id}")
            for key in keys:
                raw = await redis.get(key)
                if raw:
                    data = json.loads(raw)
                    if data.get("session_id") == session_id:
                        data["is_revoked"] = True
                        await redis.setex(key, 86400, json.dumps(data, default=str))
                        user_key = IdentityRedisKeys.session_key(data.get("user_id", ""))
                        await redis.zrem(user_key, session_id)
                        return True
        except Exception:
            pass
        return False

    async def revoke_all_user_sessions(self, user_id: str) -> int:
        redis = await self._get_redis()
        if redis is None:
            return 0
        try:
            key = IdentityRedisKeys.session_key(user_id)
            members = await redis.zrange(key, 0, -1)
            count = len(members)
            await redis.delete(key)
            for session_id in members:
                session_key = f"{key}:{session_id.decode() if isinstance(session_id, bytes) else session_id}"
                await redis.delete(session_key)
            return count
        except Exception as exc:
            log.error("Revoke all sessions error: %s", exc)
            return 0

    async def touch_session(self, session_id: str) -> bool:
        redis = await self._get_redis()
        if redis is None:
            return False
        try:
            keys = await redis.keys(f"*{session_id}")
            for key in keys:
                raw = await redis.get(key)
                if raw:
                    data = json.loads(raw)
                    if data.get("session_id") == session_id:
                        now = datetime.now(timezone.utc)
                        data["last_activity_at"] = now.isoformat()
                        await redis.setex(key, 86400, json.dumps(data, default=str))
                        return True
        except Exception:
            pass
        return False

    async def list_active_sessions(self, user_id: str) -> list[Session]:
        redis = await self._get_redis()
        if redis is None:
            return []
        sessions: list[Session] = []
        try:
            key = IdentityRedisKeys.session_key(user_id)
            now_ts = time.time()
            members = await redis.zrangebyscore(key, now_ts, "+inf")
            for member in members:
                sid = member.decode() if isinstance(member, bytes) else member
                session_key = f"{key}:{sid}"
                raw = await redis.get(session_key)
                if raw:
                    data = json.loads(raw)
                    if not data.get("is_revoked"):
                        sessions.append(self._dict_to_session(data))
        except Exception:
            pass
        return sessions

    async def count_active_sessions(self) -> int:
        redis = await self._get_redis()
        if redis is None:
            return -1
        total = 0
        try:
            now_ts = time.time()
            cursor = 0
            while True:
                cursor, keys = await redis.scan(cursor, match=f"{IdentityRedisKeys.SESSION_PREFIX}*", count=200)
                for key in keys:
                    k = key.decode() if isinstance(key, bytes) else key
                    if ":sess:" in k and k.count(":") == 3:
                        continue
                    count = await redis.zcount(k, now_ts, "+inf")
                    total += count
                if cursor == 0:
                    break
        except Exception:
            pass
        return total
