"""
Transient Memory Store — Redis-backed per-agent working memory.

Agents accumulate short-lived state (scratch-pad facts, in-flight thoughts,
partial results) that must survive across multiple LLM calls within a single
mission but can be discarded afterwards.

Structures per agent
--------------------
  cx:mem:transient:{agent}   HASH   — arbitrary key/value scratch pad
  cx:mem:thoughts:{agent}    LIST   — thought stack (LIFO; index 0 = latest)

All entries carry a configurable TTL that auto-refreshes on every write.
"""
from __future__ import annotations

import json
import logging
from collections import defaultdict
from typing import Any, Dict, List, Optional

from backend.infrastructure.redis.connection import redis_connection
from backend.infrastructure.redis.keys       import RedisKeys, TTL

log = logging.getLogger(__name__)

THOUGHT_STACK_MAXLEN = 50   # keep the last 50 thoughts per agent


class TransientMemoryStore:
    """
    Per-agent ephemeral working memory with automatic TTL expiry.

    All public methods are async-safe and degrade to in-process dicts
    when Redis is offline.
    """

    # In-memory fallback
    _mem_scratch: Dict[str, Dict[str, Any]] = defaultdict(dict)
    _mem_thoughts: Dict[str, List[str]]     = defaultdict(list)

    # ------------------------------------------------------------------
    # Scratch-pad (arbitrary key/value hash)
    # ------------------------------------------------------------------

    async def set(
        self,
        agent:  str,
        key:    str,
        value:  Any,
        ttl:    int = TTL.AGENT_TRANSIENT_MEM,
    ) -> None:
        """Write a field to the agent's scratch-pad and refresh TTL."""
        encoded = json.dumps(value) if not isinstance(value, str) else value

        if await redis_connection.ensure_connected():
            try:
                r = redis_connection.client
                await r.hset(RedisKeys.agent_transient_mem(agent), key, encoded)
                await r.expire(RedisKeys.agent_transient_mem(agent), ttl)
                return
            except Exception as exc:
                log.warning("TransientMemory set Redis error: %s", exc)

        self._mem_scratch[agent][key] = value

    async def get(self, agent: str, key: str) -> Optional[Any]:
        """Retrieve a scratch-pad field for an agent."""
        if await redis_connection.ensure_connected():
            try:
                raw = await redis_connection.client.hget(
                    RedisKeys.agent_transient_mem(agent), key
                )
                if raw is not None:
                    try:
                        return json.loads(raw)
                    except json.JSONDecodeError:
                        return raw
            except Exception as exc:
                log.warning("TransientMemory get Redis error: %s", exc)

        return self._mem_scratch[agent].get(key)

    async def get_all(self, agent: str) -> Dict[str, Any]:
        """Return the entire scratch-pad for an agent."""
        if await redis_connection.ensure_connected():
            try:
                raw = await redis_connection.client.hgetall(
                    RedisKeys.agent_transient_mem(agent)
                )
                result = {}
                for k, v in raw.items():
                    try:
                        result[k] = json.loads(v)
                    except json.JSONDecodeError:
                        result[k] = v
                return result
            except Exception as exc:
                log.warning("TransientMemory get_all Redis error: %s", exc)

        return dict(self._mem_scratch.get(agent, {}))

    async def delete(self, agent: str, key: str) -> None:
        """Delete a single scratch-pad field."""
        if await redis_connection.ensure_connected():
            try:
                await redis_connection.client.hdel(
                    RedisKeys.agent_transient_mem(agent), key
                )
                return
            except Exception as exc:
                log.warning("TransientMemory delete Redis error: %s", exc)
        self._mem_scratch[agent].pop(key, None)

    async def clear(self, agent: str) -> None:
        """Wipe all scratch-pad and thought stack data for an agent."""
        if await redis_connection.ensure_connected():
            try:
                r = redis_connection.client
                await r.delete(
                    RedisKeys.agent_transient_mem(agent),
                    RedisKeys.agent_thought_stack(agent),
                )
                return
            except Exception as exc:
                log.warning("TransientMemory clear Redis error: %s", exc)
        self._mem_scratch.pop(agent, None)
        self._mem_thoughts.pop(agent, None)

    # ------------------------------------------------------------------
    # Thought stack (LIFO)
    # ------------------------------------------------------------------

    async def push_thought(
        self,
        agent:   str,
        thought: str,
        ttl:     int = TTL.AGENT_THOUGHT_STACK,
    ) -> None:
        """Push a new thought onto the top of the agent's thought stack."""
        if await redis_connection.ensure_connected():
            try:
                r = redis_connection.client
                await r.lpush(RedisKeys.agent_thought_stack(agent), thought)
                await r.ltrim(
                    RedisKeys.agent_thought_stack(agent),
                    0, THOUGHT_STACK_MAXLEN - 1,
                )
                await r.expire(RedisKeys.agent_thought_stack(agent), ttl)
                return
            except Exception as exc:
                log.warning("TransientMemory push_thought Redis error: %s", exc)

        stack = self._mem_thoughts[agent]
        stack.insert(0, thought)
        if len(stack) > THOUGHT_STACK_MAXLEN:
            self._mem_thoughts[agent] = stack[:THOUGHT_STACK_MAXLEN]

    async def peek_thoughts(
        self,
        agent: str,
        limit: int = 10,
    ) -> List[str]:
        """Return the top *limit* thoughts (most recent first)."""
        if await redis_connection.ensure_connected():
            try:
                items = await redis_connection.client.lrange(
                    RedisKeys.agent_thought_stack(agent), 0, limit - 1
                )
                return list(items)
            except Exception as exc:
                log.warning("TransientMemory peek_thoughts Redis error: %s", exc)

        return self._mem_thoughts.get(agent, [])[:limit]

    async def pop_thought(self, agent: str) -> Optional[str]:
        """Pop the most recent thought off the stack."""
        if await redis_connection.ensure_connected():
            try:
                return await redis_connection.client.lpop(
                    RedisKeys.agent_thought_stack(agent)
                )
            except Exception as exc:
                log.warning("TransientMemory pop_thought Redis error: %s", exc)

        stack = self._mem_thoughts.get(agent, [])
        return stack.pop(0) if stack else None


# ===========================================================================
# SINGLETON
# ===========================================================================

transient_memory = TransientMemoryStore()
