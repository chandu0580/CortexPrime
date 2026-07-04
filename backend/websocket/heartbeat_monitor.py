"""
Heartbeat Monitor
=================
Background asyncio task that monitors connection liveness by:

1. Sending a ``heartbeat_ping`` to every connection every
   ``PING_INTERVAL_S`` seconds.
2. Expecting a ``pong`` reply within ``PONG_TIMEOUT_S`` seconds.
3. Evicting connections that miss consecutive pings beyond
   ``MAX_MISSED_PINGS``.
4. Running a stale-session sweep every ``SWEEP_INTERVAL_S`` seconds
   to remove connections whose ``idle_s()`` exceeds the configured
   max-idle threshold.

The monitor also updates the Redis ``ws_session_store`` heartbeat key
so that external observers (e.g. admin dashboards) can see which
sessions are truly alive.

Usage
-----
Start once at app startup::

    from backend.websocket.heartbeat_monitor import heartbeat_monitor
    await heartbeat_monitor.start()

Stop at app shutdown::

    await heartbeat_monitor.stop()
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Any, Dict, Optional

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

PING_INTERVAL_S: float = float(os.getenv("WS_PING_INTERVAL_S",  "30"))
PONG_TIMEOUT_S:  float = float(os.getenv("WS_PONG_TIMEOUT_S",   "15"))
MAX_MISSED_PINGS: int  = int(  os.getenv("WS_MAX_MISSED_PINGS",  "2"))
SWEEP_INTERVAL_S: float = float(os.getenv("WS_SWEEP_INTERVAL_S", "60"))
MAX_IDLE_S:       float = float(os.getenv("WS_MAX_IDLE_S",        "300"))   # 5 min


class HeartbeatMonitor:
    """
    Monitors WebSocket connection liveness.

    Maintains an independent ``missed_pings`` counter per connection.
    The counter is reset when a pong arrives (``record_pong()`` called
    by the per-connection gateway).
    """

    def __init__(self) -> None:
        self._ping_task:  Optional[asyncio.Task] = None
        self._sweep_task: Optional[asyncio.Task] = None
        self._running:    bool = False
        self._seq:        int  = 0
        # conn_id → consecutive missed pings
        self._missed: Dict[str, int] = {}

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        if self._running:
            return
        self._running    = True
        self._ping_task  = asyncio.create_task(
            self._ping_loop(), name="ws-heartbeat-ping"
        )
        self._sweep_task = asyncio.create_task(
            self._sweep_loop(), name="ws-heartbeat-sweep"
        )
        log.info(
            "HeartbeatMonitor started: ping=%ss pong_timeout=%ss max_idle=%ss",
            PING_INTERVAL_S, PONG_TIMEOUT_S, MAX_IDLE_S,
        )

    async def stop(self) -> None:
        self._running = False
        for task in (self._ping_task, self._sweep_task):
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        log.info("HeartbeatMonitor stopped")

    # ------------------------------------------------------------------
    # Record pong from gateway
    # ------------------------------------------------------------------

    def record_pong(self, conn_id: str) -> None:
        """Called by the gateway when a pong arrives."""
        self._missed.pop(conn_id, None)
        ctx = self._get_ctx(conn_id)
        if ctx:
            ctx.last_pong_s = time.monotonic()
            ctx.pending_ping_seq = None

    # ------------------------------------------------------------------
    # Background loops
    # ------------------------------------------------------------------

    async def _ping_loop(self) -> None:
        """Send heartbeat pings on the configured interval."""
        while self._running:
            await asyncio.sleep(PING_INTERVAL_S)
            if not self._running:
                break
            await self._send_pings()

    async def _sweep_loop(self) -> None:
        """Periodically evict stale / dead connections."""
        while self._running:
            await asyncio.sleep(SWEEP_INTERVAL_S)
            if not self._running:
                break
            await self._sweep_stale()

    # ------------------------------------------------------------------
    # Ping logic
    # ------------------------------------------------------------------

    async def _send_pings(self) -> None:
        from backend.websocket.connection_pool import connection_pool
        from backend.websocket.message_protocol import build_heartbeat_ping

        self._seq += 1
        current_seq = self._seq
        payload     = build_heartbeat_ping(current_seq)
        now         = time.monotonic()

        evict_ids = []

        for ctx in connection_pool.all_connections():
            if not ctx.is_alive:
                continue

            # Check if previous ping went unanswered past timeout
            if ctx.pending_ping_seq is not None:
                waited = now - ctx.last_heartbeat_s
                if waited > PONG_TIMEOUT_S:
                    self._missed[ctx.conn_id] = self._missed.get(ctx.conn_id, 0) + 1
                    if self._missed[ctx.conn_id] >= MAX_MISSED_PINGS:
                        log.warning(
                            "Evicting unresponsive conn=%s (missed=%d)",
                            ctx.conn_id, self._missed[ctx.conn_id],
                        )
                        evict_ids.append(ctx.conn_id)
                        continue

            # Send ping
            sent = await connection_pool.send_to(ctx.conn_id, payload)
            if sent:
                ctx.pending_ping_seq = current_seq
                ctx.last_heartbeat_s = now
                # Update Redis heartbeat
                await self._update_redis_heartbeat(ctx.conn_id)
            else:
                evict_ids.append(ctx.conn_id)

        # Evict after iterating to avoid mutation during iteration
        for conn_id in evict_ids:
            await self._evict(conn_id)

    # ------------------------------------------------------------------
    # Stale sweep
    # ------------------------------------------------------------------

    async def _sweep_stale(self) -> None:
        from backend.websocket.connection_pool import connection_pool

        evicted = await connection_pool.evict_stale(MAX_IDLE_S)
        if evicted:
            log.info("HeartbeatMonitor sweep evicted %d stale connections", evicted)
        # Clean up missed-ping counters for gone connections
        alive_ids = {c.conn_id for c in connection_pool.all_connections()}
        self._missed = {k: v for k, v in self._missed.items() if k in alive_ids}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _evict(self, conn_id: str) -> None:
        from backend.websocket.connection_pool import connection_pool
        ctx = connection_pool.get(conn_id)
        if ctx:
            ctx.is_alive = False
            try:
                await ctx.websocket.close(code=1001, reason="Heartbeat timeout")
            except Exception:
                pass
        await connection_pool.unregister(conn_id)
        self._missed.pop(conn_id, None)

    def _get_ctx(self, conn_id: str):
        from backend.websocket.connection_pool import connection_pool
        return connection_pool.get(conn_id)

    async def _update_redis_heartbeat(self, conn_id: str) -> None:
        try:
            from backend.infrastructure.redis.websocket_session_store import ws_session_store
            await ws_session_store.heartbeat(conn_id)
        except Exception:
            pass  # Redis unavailable — heartbeat still works in-memory

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def stats(self) -> Dict[str, Any]:
        return {
            "running":      self._running,
            "ping_interval_s": PING_INTERVAL_S,
            "pong_timeout_s":  PONG_TIMEOUT_S,
            "max_idle_s":      MAX_IDLE_S,
            "current_seq":     self._seq,
            "connections_with_missed_pings": len(self._missed),
        }


# Singleton
heartbeat_monitor = HeartbeatMonitor()
