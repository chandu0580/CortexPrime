"""
WebSocket Session Store — Redis-backed.

Tracks every live WebSocket connection as a first-class Redis entity so
that:
  - Session metadata survives restarts (when a client reconnects)
  - Any process can enumerate / query active sessions
  - Stale sessions are auto-reaped via TTL

Key layout  (see keys.py)
--------------------------
  cx:ws:session:{conn_id}   HASH   — session metadata
  cx:ws:sessions            ZSET   — all active conn_ids scored by epoch
  cx:ws:hb:{conn_id}        STRING — heartbeat timestamp (TTL=WS_HEARTBEAT)
"""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from backend.infrastructure.redis.connection import redis_connection
from backend.infrastructure.redis.keys       import RedisKeys, TTL

log = logging.getLogger(__name__)


class WebSocketSessionStore:
    """
    Manage WebSocket connection sessions in Redis.

    All public methods are async-safe and degrade gracefully (returning
    empty / default values) when Redis is offline.
    """

    # Fallback in-memory store when Redis is unavailable
    _mem: Dict[str, Dict[str, Any]] = {}

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    async def register(
        self,
        conn_id:    str,
        session_id: str,
        metadata:   Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Persist a new WebSocket connection.

        Parameters
        ----------
        conn_id    : unique connection identifier (e.g. ``str(uuid4())``)
        session_id : logical user/mission session this connection belongs to
        metadata   : optional extra fields (user_agent, remote_ip, …)
        """
        now = datetime.now(timezone.utc)
        record = {
            "conn_id":      conn_id,
            "session_id":   session_id,
            "connected_at": now.isoformat(),
            "last_seen":    now.isoformat(),
            **(metadata or {}),
        }

        if await redis_connection.ensure_connected():
            try:
                r = redis_connection.client
                # Hash: session detail
                await r.hset(
                    RedisKeys.ws_session(conn_id),
                    mapping={k: json.dumps(v) if not isinstance(v, str) else v
                             for k, v in record.items()},
                )
                await r.expire(RedisKeys.ws_session(conn_id), TTL.WS_SESSION)
                # ZSET: active sessions scored by connection epoch
                await r.zadd(
                    RedisKeys.ws_sessions_set(),
                    {conn_id: now.timestamp()},
                )
                # Heartbeat key
                await r.set(
                    RedisKeys.ws_heartbeat(conn_id),
                    now.isoformat(),
                    ex=TTL.WS_HEARTBEAT,
                )
                log.debug("WS session registered: %s (session=%s)", conn_id, session_id)
                return
            except Exception as exc:
                log.warning("WS session register Redis error: %s", exc)

        self._mem[conn_id] = record

    # ------------------------------------------------------------------
    # Heartbeat
    # ------------------------------------------------------------------

    async def heartbeat(self, conn_id: str) -> None:
        """
        Refresh the session TTL and update ``last_seen``.
        Call this on every received WebSocket message.
        """
        now = datetime.now(timezone.utc).isoformat()

        if await redis_connection.ensure_connected():
            try:
                r = redis_connection.client
                await r.hset(RedisKeys.ws_session(conn_id), "last_seen", now)
                await r.expire(RedisKeys.ws_session(conn_id), TTL.WS_SESSION)
                await r.set(
                    RedisKeys.ws_heartbeat(conn_id),
                    now,
                    ex=TTL.WS_HEARTBEAT,
                )
                return
            except Exception as exc:
                log.warning("WS heartbeat Redis error: %s", exc)

        if conn_id in self._mem:
            self._mem[conn_id]["last_seen"] = now

    # ------------------------------------------------------------------
    # Unregister
    # ------------------------------------------------------------------

    async def unregister(self, conn_id: str) -> None:
        """Remove the session when the WebSocket disconnects."""
        if await redis_connection.ensure_connected():
            try:
                r = redis_connection.client
                await r.delete(RedisKeys.ws_session(conn_id))
                await r.delete(RedisKeys.ws_heartbeat(conn_id))
                await r.zrem(RedisKeys.ws_sessions_set(), conn_id)
                log.debug("WS session unregistered: %s", conn_id)
                return
            except Exception as exc:
                log.warning("WS session unregister Redis error: %s", exc)

        self._mem.pop(conn_id, None)

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    async def get_session(self, conn_id: str) -> Optional[Dict[str, Any]]:
        """Return session metadata for a single connection."""
        if await redis_connection.ensure_connected():
            try:
                raw = await redis_connection.client.hgetall(
                    RedisKeys.ws_session(conn_id)
                )
                if raw:
                    return {
                        k: _maybe_json(v) for k, v in raw.items()
                    }
            except Exception as exc:
                log.warning("WS session get Redis error: %s", exc)

        return self._mem.get(conn_id)

    async def list_active(self) -> List[Dict[str, Any]]:
        """Return metadata for all active WebSocket connections."""
        if await redis_connection.ensure_connected():
            try:
                r = redis_connection.client
                # Prune stale connections (heartbeat TTL expired)
                stale_cutoff = time.time() - TTL.WS_SESSION
                await r.zremrangebyscore(
                    RedisKeys.ws_sessions_set(), "-inf", stale_cutoff
                )
                conn_ids = await r.zrange(RedisKeys.ws_sessions_set(), 0, -1)
                sessions = []
                for cid in conn_ids:
                    raw = await r.hgetall(RedisKeys.ws_session(cid))
                    if raw:
                        sessions.append({k: _maybe_json(v) for k, v in raw.items()})
                return sessions
            except Exception as exc:
                log.warning("WS list_active Redis error: %s", exc)

        return list(self._mem.values())

    async def count_active(self) -> int:
        """Return the number of currently connected WebSocket clients."""
        if await redis_connection.ensure_connected():
            try:
                return await redis_connection.client.zcard(
                    RedisKeys.ws_sessions_set()
                )
            except Exception as exc:
                log.warning("WS count_active Redis error: %s", exc)
        return len(self._mem)

    async def get_by_session_id(self, session_id: str) -> List[Dict[str, Any]]:
        """Return all WebSocket connections that belong to a logical session."""
        active = await self.list_active()
        return [s for s in active if s.get("session_id") == session_id]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _maybe_json(value: str) -> Any:
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return value


# ===========================================================================
# SINGLETON
# ===========================================================================

ws_session_store = WebSocketSessionStore()
