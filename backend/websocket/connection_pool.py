"""
Connection Pool
===============
Central registry for all live WebSocket connections.

Responsibilities
----------------
- Thread-safe (asyncio.Lock) storage of ``ConnectionContext`` objects.
- Filtered broadcast: by topic, by session_id, by conn_id.
- Dead-connection cleanup (called by HeartbeatMonitor).
- Connection statistics.

This module is the single source-of-truth for "who is connected right now"
and "how do I reach them?"  No other module holds WebSocket references.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from fastapi import WebSocket

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Connection context
# ---------------------------------------------------------------------------

@dataclass
class ConnectionContext:
    """Metadata and state for a single active WebSocket connection."""

    conn_id:    str
    session_id: str
    websocket:  WebSocket

    # Auth
    is_authenticated: bool = False
    is_anonymous:     bool = True
    user_id:          str  = "anonymous"

    # Topic subscriptions (e.g. "cognition", "metrics", "execution:abc123")
    topics: Set[str] = field(default_factory=set)

    # Heartbeat tracking
    last_heartbeat_s:  float = field(default_factory=time.monotonic)
    last_pong_s:       float = field(default_factory=time.monotonic)
    pending_ping_seq:  Optional[int] = None   # seq of an unanswered ping

    # Metrics
    connected_at_s:    float = field(default_factory=time.monotonic)
    messages_sent:     int   = 0
    messages_received: int   = 0
    bytes_sent:        int   = 0
    bytes_received:    int   = 0

    # Flags
    is_alive: bool = True

    # Remote address (for logging)
    remote_addr: str = ""

    def age_s(self) -> float:
        return time.monotonic() - self.connected_at_s

    def idle_s(self) -> float:
        return time.monotonic() - self.last_heartbeat_s

    def to_dict(self) -> Dict[str, Any]:
        return {
            "conn_id":          self.conn_id,
            "session_id":       self.session_id,
            "user_id":          self.user_id,
            "is_authenticated": self.is_authenticated,
            "is_anonymous":     self.is_anonymous,
            "topics":           list(self.topics),
            "age_s":            round(self.age_s(), 1),
            "idle_s":           round(self.idle_s(), 1),
            "messages_sent":    self.messages_sent,
            "messages_received":self.messages_received,
            "remote_addr":      self.remote_addr,
        }


# ---------------------------------------------------------------------------
# Connection pool
# ---------------------------------------------------------------------------

class ConnectionPool:
    """
    Async-safe central registry for all live WebSocket connections.

    All state mutations are serialised through a single ``asyncio.Lock``
    to prevent races on register/unregister/broadcast cycles.
    """

    def __init__(self) -> None:
        self._connections: Dict[str, ConnectionContext] = {}
        self._lock         = asyncio.Lock()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def register(self, ctx: ConnectionContext) -> None:
        """Add a connection to the pool."""
        async with self._lock:
            self._connections[ctx.conn_id] = ctx
        log.info(
            "Pool +conn conn=%s session=%s addr=%s total=%d",
            ctx.conn_id, ctx.session_id, ctx.remote_addr, len(self._connections),
        )

    async def unregister(self, conn_id: str) -> None:
        """Remove a connection from the pool (called on disconnect / eviction)."""
        async with self._lock:
            self._connections.pop(conn_id, None)
        log.info("Pool -conn conn=%s total=%d", conn_id, len(self._connections))

    def get(self, conn_id: str) -> Optional[ConnectionContext]:
        """Return the ConnectionContext for *conn_id*, or None."""
        return self._connections.get(conn_id)

    # ------------------------------------------------------------------
    # Topic subscriptions
    # ------------------------------------------------------------------

    def subscribe_topic(self, conn_id: str, topic: str) -> None:
        """Add *topic* to a connection's subscription set."""
        ctx = self._connections.get(conn_id)
        if ctx:
            ctx.topics.add(topic)

    def unsubscribe_topic(self, conn_id: str, topic: str) -> None:
        """Remove *topic* from a connection's subscription set."""
        ctx = self._connections.get(conn_id)
        if ctx:
            ctx.topics.discard(topic)

    def connections_for_topic(self, topic: str) -> List[ConnectionContext]:
        """Return all ConnectionContexts subscribed to *topic*."""
        return [
            ctx for ctx in self._connections.values()
            if topic in ctx.topics and ctx.is_alive
        ]

    # ------------------------------------------------------------------
    # Send helpers
    # ------------------------------------------------------------------

    async def send_to(
        self,
        conn_id: str,
        payload: Dict[str, Any],
    ) -> bool:
        """
        Send *payload* to a single connection.
        Returns True on success, False if connection is not found or dead.
        """
        ctx = self._connections.get(conn_id)
        if ctx is None or not ctx.is_alive:
            return False
        return await self._send_ctx(ctx, payload)

    async def broadcast(
        self,
        payload: Dict[str, Any],
    ) -> int:
        """
        Send *payload* to ALL connected clients.
        Returns the number of successful sends.
        """
        sent, dead = 0, []
        async with self._lock:
            targets = list(self._connections.values())
        for ctx in targets:
            if not ctx.is_alive:
                continue
            ok = await self._send_ctx(ctx, payload)
            if ok:
                sent += 1
            else:
                dead.append(ctx.conn_id)
        # Remove dead connections outside lock to avoid deadlock
        for conn_id in dead:
            await self.unregister(conn_id)
        return sent

    async def broadcast_to_topic(
        self,
        topic: str,
        payload: Dict[str, Any],
    ) -> int:
        """
        Send *payload* to all connections subscribed to *topic*.
        Returns the number of successful sends.
        """
        targets = self.connections_for_topic(topic)
        sent, dead = 0, []
        for ctx in targets:
            ok = await self._send_ctx(ctx, payload)
            if ok:
                sent += 1
            else:
                dead.append(ctx.conn_id)
        for conn_id in dead:
            await self.unregister(conn_id)
        return sent

    async def broadcast_to_session(
        self,
        session_id: str,
        payload: Dict[str, Any],
    ) -> int:
        """Send *payload* to all connections belonging to *session_id*."""
        targets = [
            ctx for ctx in self._connections.values()
            if ctx.session_id == session_id and ctx.is_alive
        ]
        sent, dead = 0, []
        for ctx in targets:
            ok = await self._send_ctx(ctx, payload)
            if ok:
                sent += 1
            else:
                dead.append(ctx.conn_id)
        for conn_id in dead:
            await self.unregister(conn_id)
        return sent

    # ------------------------------------------------------------------
    # Internal send
    # ------------------------------------------------------------------

    async def _send_ctx(
        self,
        ctx: ConnectionContext,
        payload: Dict[str, Any],
    ) -> bool:
        """Low-level send to a single connection context. Returns success."""
        if not ctx.is_alive:
            return False
        try:
            raw = json.dumps(payload, default=str)
            await ctx.websocket.send_text(raw)
            ctx.messages_sent += 1
            ctx.bytes_sent    += len(raw)
            return True
        except Exception as exc:
            log.debug("Pool send failed conn=%s: %s", ctx.conn_id, exc)
            ctx.is_alive = False
            return False

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def all_connections(self) -> List[ConnectionContext]:
        """Return a snapshot list of all currently registered connections."""
        return list(self._connections.values())

    def count(self) -> int:
        return len(self._connections)

    def stats(self) -> Dict[str, Any]:
        """Return aggregate statistics across all connections."""
        conns  = list(self._connections.values())
        alive  = sum(1 for c in conns if c.is_alive)
        topics: Dict[str, int] = {}
        for ctx in conns:
            for t in ctx.topics:
                topics[t] = topics.get(t, 0) + 1
        return {
            "total_connections": len(conns),
            "alive_connections": alive,
            "topic_subscriber_counts": topics,
            "total_messages_sent":     sum(c.messages_sent for c in conns),
            "total_messages_received": sum(c.messages_received for c in conns),
        }

    async def evict_stale(self, max_idle_s: float) -> int:
        """
        Evict connections that have been idle for more than *max_idle_s* seconds.
        Returns the number of connections evicted.
        """
        stale = [
            ctx.conn_id
            for ctx in self._connections.values()
            if ctx.idle_s() > max_idle_s or not ctx.is_alive
        ]
        for conn_id in stale:
            log.warning("Pool evicting stale conn=%s", conn_id)
            ctx = self._connections.get(conn_id)
            if ctx:
                ctx.is_alive = False
                try:
                    await ctx.websocket.close(code=1001, reason="Idle timeout")
                except Exception:
                    pass
            await self.unregister(conn_id)
        return len(stale)


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

connection_pool = ConnectionPool()
