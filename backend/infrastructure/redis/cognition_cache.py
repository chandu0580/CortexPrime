"""
Cognition Event Cache — Redis Streams + Sorted Sets.

Provides high-frequency, low-latency caching for every cognition event
produced by the runtime.  Three complementary structures are maintained:

  1. Redis Stream  (cx:cog:stream:{execution_id})
       - Append-only, consumer-group capable, auto-trimmed to ``STREAM_MAXLEN``
       - Source of truth for replay / audit

  2. Hash  (cx:cog:latest:{agent})
       - Latest event fields for each agent — O(1) lookup for dashboards

  3. Sorted Set  (cx:cog:timeline:{agent})
       - Event IDs scored by epoch → efficient range queries for timelines

  4. List  (cx:cog:cache:{execution_id})
       - Recent N raw JSON events for quick batch reads by the frontend

All operations degrade to a simple in-memory list when Redis is offline.
"""
from __future__ import annotations

import json
import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from backend.infrastructure.redis.connection import redis_connection
from backend.infrastructure.redis.keys import TTL, RedisKeys

log = logging.getLogger(__name__)

STREAM_MAXLEN   = 5000   # keep last N entries per execution stream
CACHE_MAXLEN    = 200    # keep last N entries in the fast-read list
TIMELINE_MAXLEN = 1000   # keep last N entries per agent timeline


class CognitionCache:
    """
    Cache cognition events for real-time AI state visibility.

    All writes are non-blocking (fire-and-forget with exception capture).
    Reads return partial / empty results rather than raising.
    """

    # In-memory fallback
    _mem_cache:    Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    _mem_latest:   Dict[str, Dict[str, Any]]       = {}
    _mem_timeline: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    async def push_event(
        self,
        execution_id: str,
        agent:        str,
        event_type:   str,
        message:      str,
        phase:        Optional[str]            = None,
        payload:      Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """
        Persist a single cognition event.

        Returns the Redis Stream entry ID on success, or None on fallback.
        """
        now   = datetime.now(timezone.utc)
        epoch = now.timestamp()
        entry = {
            "execution_id": execution_id,
            "agent":        agent,
            "event_type":   event_type,
            "message":      message,
            "phase":        phase or "",
            "timestamp":    now.isoformat(),
            "epoch":        epoch,
            "payload":      json.dumps(payload or {}),
        }

        if await redis_connection.ensure_connected():
            try:
                r      = redis_connection.client
                raw_js = json.dumps(entry)

                # 1. Append to Stream (auto-trim)
                stream_key = RedisKeys.cognition_stream(execution_id)
                entry_id   = await r.xadd(
                    stream_key,
                    {k: v for k, v in entry.items()},
                    maxlen  = STREAM_MAXLEN,
                    approximate = True,
                )
                await r.expire(stream_key, TTL.COGNITION_STREAM)

                # 2. Latest-state hash for agent
                latest_key = RedisKeys.cognition_latest(agent)
                await r.hset(latest_key, mapping=entry)
                await r.expire(latest_key, TTL.COGNITION_CACHE)

                # 3. Agent timeline (sorted set)
                timeline_key = RedisKeys.cognition_timeline(agent)
                await r.zadd(timeline_key, {raw_js: epoch})
                await r.zremrangebyrank(timeline_key, 0, -(TIMELINE_MAXLEN + 1))
                await r.expire(timeline_key, TTL.COGNITION_EVENT)

                # 4. Fast-read list
                cache_key = RedisKeys.cognition_cache(execution_id)
                await r.lpush(cache_key, raw_js)
                await r.ltrim(cache_key, 0, CACHE_MAXLEN - 1)
                await r.expire(cache_key, TTL.COGNITION_EVENT)

                return str(entry_id)

            except Exception as exc:
                log.warning("CognitionCache push_event Redis error: %s", exc)

        # In-memory fallback
        self._mem_cache[execution_id].insert(0, entry)
        if len(self._mem_cache[execution_id]) > CACHE_MAXLEN:
            self._mem_cache[execution_id] = self._mem_cache[execution_id][:CACHE_MAXLEN]
        self._mem_latest[agent]        = entry
        self._mem_timeline[agent].insert(0, entry)
        return None

    # ------------------------------------------------------------------
    # Read: fast-access list (most recent first)
    # ------------------------------------------------------------------

    async def get_recent(
        self,
        execution_id: str,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Return the most recent *limit* events for an execution."""
        if await redis_connection.ensure_connected():
            try:
                items = await redis_connection.client.lrange(
                    RedisKeys.cognition_cache(execution_id), 0, limit - 1
                )
                return [json.loads(i) for i in items]
            except Exception as exc:
                log.warning("CognitionCache get_recent Redis error: %s", exc)

        cached = self._mem_cache.get(execution_id, [])
        return cached[:limit]

    # ------------------------------------------------------------------
    # Read: Stream (replay with cursor)
    # ------------------------------------------------------------------

    async def read_stream(
        self,
        execution_id: str,
        last_id:      str = "0-0",
        count:        int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Read stream entries after *last_id*.

        Use ``last_id="0-0"`` for a full replay, or store the last returned
        entry ID to continue from where you left off.

        Returns a list of dicts, each containing a ``stream_id`` field.
        """
        if await redis_connection.ensure_connected():
            try:
                entries = await redis_connection.client.xread(
                    {RedisKeys.cognition_stream(execution_id): last_id},
                    count=count,
                    block=0,    # non-blocking
                )
                results = []
                for _stream, msgs in (entries or []):
                    for msg_id, fields in msgs:
                        record = dict(fields)
                        record["stream_id"] = str(msg_id)
                        if "payload" in record:
                            try:
                                record["payload"] = json.loads(record["payload"])
                            except json.JSONDecodeError:
                                pass
                        results.append(record)
                return results
            except Exception as exc:
                log.warning("CognitionCache read_stream Redis error: %s", exc)
        return []

    # ------------------------------------------------------------------
    # Read: latest state per agent
    # ------------------------------------------------------------------

    async def get_agent_latest(self, agent: str) -> Optional[Dict[str, Any]]:
        """Return the most recent cognition event for a specific agent."""
        if await redis_connection.ensure_connected():
            try:
                raw = await redis_connection.client.hgetall(
                    RedisKeys.cognition_latest(agent)
                )
                if raw:
                    record = dict(raw)
                    if "payload" in record:
                        try:
                            record["payload"] = json.loads(record["payload"])
                        except json.JSONDecodeError:
                            pass
                    return record
            except Exception as exc:
                log.warning("CognitionCache get_agent_latest Redis error: %s", exc)
        return self._mem_latest.get(agent)

    # ------------------------------------------------------------------
    # Read: agent timeline (time range)
    # ------------------------------------------------------------------

    async def get_agent_timeline(
        self,
        agent:      str,
        since_epoch: float = 0.0,
        limit:       int   = 100,
    ) -> List[Dict[str, Any]]:
        """Return agent events since a given epoch timestamp, newest first."""
        if await redis_connection.ensure_connected():
            try:
                items = await redis_connection.client.zrangebyscore(
                    RedisKeys.cognition_timeline(agent),
                    min=since_epoch,
                    max="+inf",
                    withscores=False,
                    start=0,
                    num=limit,
                )
                return [json.loads(i) for i in reversed(items)]
            except Exception as exc:
                log.warning("CognitionCache get_agent_timeline Redis error: %s", exc)
        entries = self._mem_timeline.get(agent, [])
        return [e for e in entries if float(e.get("epoch", 0)) >= since_epoch][:limit]

    # ------------------------------------------------------------------
    # Invalidation
    # ------------------------------------------------------------------

    async def clear_execution(self, execution_id: str) -> None:
        """Remove all cached data for a completed execution."""
        if await redis_connection.ensure_connected():
            try:
                r = redis_connection.client
                await r.delete(
                    RedisKeys.cognition_stream(execution_id),
                    RedisKeys.cognition_cache(execution_id),
                )
                return
            except Exception as exc:
                log.warning("CognitionCache clear_execution Redis error: %s", exc)
        self._mem_cache.pop(execution_id, None)


# ===========================================================================
# SINGLETON
# ===========================================================================

cognition_cache = CognitionCache()
