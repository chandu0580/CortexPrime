"""
Runtime Context Store — Redis.

Manages active session state, chat message history, and transient
cognition cache.  Gracefully degrades to an in-memory fallback when
Redis is unavailable.
"""
from __future__ import annotations

import json
import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from backend.memory.db.redis_client import redis_client
from backend.memory.models import RuntimeContext

logger = logging.getLogger(__name__)

# Defaults
SESSION_TTL      = 6 * 3600   # 6 hours
COG_CACHE_TTL    = 5 * 60     # 5 minutes
MAX_MESSAGES     = 100


class ContextStore:
    """
    Runtime context store backed by Redis.

    Falls back to a process-local in-memory dict when Redis is unavailable
    so agents can still operate — just without persistence across restarts.
    """

    def __init__(self) -> None:
        # In-memory fallback
        self._mem_ctx:  Dict[str, Dict[str, Any]] = defaultdict(dict)
        self._mem_msgs: Dict[str, List[str]]       = defaultdict(list)

    # ------------------------------------------------------------------
    # Context key/value
    # ------------------------------------------------------------------

    async def set_context(
        self,
        session_id: str,
        key:        str,
        value:      Any,
        ttl:        int = SESSION_TTL,
    ) -> None:
        encoded = json.dumps(value)
        hkey    = f"ctx:{session_id}"

        if redis_client.is_available:
            await redis_client.hset(hkey, {key: encoded})
            await redis_client.expire(hkey, ttl)
        else:
            self._mem_ctx[session_id][key] = value

    async def get_context(self, session_id: str) -> Dict[str, Any]:
        if redis_client.is_available:
            raw = await redis_client.hgetall(f"ctx:{session_id}")
            result: Dict[str, Any] = {}
            for k, v in raw.items():
                try:
                    result[k] = json.loads(v)
                except json.JSONDecodeError:
                    result[k] = v
            return result
        return dict(self._mem_ctx.get(session_id, {}))

    async def set_objective(self, session_id: str, objective: str) -> None:
        await self.set_context(session_id, "current_objective", objective)

    async def set_active_agents(
        self, session_id: str, agents: List[str]
    ) -> None:
        await self.set_context(session_id, "active_agents", agents)

    # ------------------------------------------------------------------
    # Message history
    # ------------------------------------------------------------------

    async def append_message(
        self,
        session_id:   str,
        message:      Dict[str, Any],
        max_messages: int = MAX_MESSAGES,
    ) -> None:
        """Prepend message (newest-first) and cap list length."""
        key     = f"msgs:{session_id}"
        encoded = json.dumps(message)

        if redis_client.is_available:
            await redis_client.lpush(key, encoded)
            await redis_client.ltrim(key, 0, max_messages - 1)
            await redis_client.expire(key, SESSION_TTL)
        else:
            msgs = self._mem_msgs[session_id]
            msgs.insert(0, encoded)
            if len(msgs) > max_messages:
                self._mem_msgs[session_id] = msgs[:max_messages]

    async def get_messages(
        self,
        session_id: str,
        n:          int = 20,
    ) -> List[Dict[str, Any]]:
        """Return the N most recent messages (newest first)."""
        if redis_client.is_available:
            raw = await redis_client.lrange(f"msgs:{session_id}", 0, n - 1)
        else:
            raw = self._mem_msgs.get(session_id, [])[:n]

        results = []
        for item in raw:
            try:
                results.append(json.loads(item))
            except json.JSONDecodeError:
                pass
        return results

    # ------------------------------------------------------------------
    # Cognition cache
    # ------------------------------------------------------------------

    async def cache_cognition(
        self,
        key:   str,
        value: Any,
        ttl:   int = COG_CACHE_TTL,
    ) -> None:
        await redis_client.set(f"cog:{key}", json.dumps(value), ex=ttl)

    async def get_cognition(self, key: str) -> Optional[Any]:
        raw = await redis_client.get(f"cog:{key}")
        if raw is not None:
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                return raw
        return None

    # ------------------------------------------------------------------
    # Session assembly
    # ------------------------------------------------------------------

    async def get_runtime_context(self, session_id: str) -> RuntimeContext:
        """Assemble a full RuntimeContext from Redis (or in-memory fallback)."""
        ctx      = await self.get_context(session_id)
        messages = await self.get_messages(session_id, n=20)

        return RuntimeContext(
            session_id        = session_id,
            messages          = messages,
            active_agents     = ctx.get("active_agents", []),
            current_objective = ctx.get("current_objective"),
            metadata          = ctx,
            updated_at        = datetime.now(timezone.utc),
        )

    async def clear_session(self, session_id: str) -> None:
        if redis_client.is_available:
            await redis_client.delete(
                f"ctx:{session_id}",
                f"msgs:{session_id}",
            )
        else:
            self._mem_ctx.pop(session_id, None)
            self._mem_msgs.pop(session_id, None)


context_store = ContextStore()
