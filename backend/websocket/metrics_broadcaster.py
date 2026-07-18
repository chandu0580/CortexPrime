"""
Metrics Broadcaster
===================
Background asyncio task that periodically collects runtime metrics and
pushes them to all WebSocket connections subscribed to the ``metrics``
topic.

Metrics collected every ``BROADCAST_INTERVAL_S`` seconds:
  - Active WebSocket connection count + pool stats
  - Agent activity summary (from Redis agent_activity_store)
  - Active execution count + statuses
  - Heartbeat monitor stats
  - System uptime
  - LLM provider status (optional, best-effort)

The payload is also published to ``cx:pub:metrics`` so external Redis
subscribers (e.g. admin tools) receive it too.

Usage
-----
Start once at app startup::

    from backend.websocket.metrics_broadcaster import metrics_broadcaster
    await metrics_broadcaster.start()

Stop at app shutdown::

    await metrics_broadcaster.stop()
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Any, Dict, Optional

log = logging.getLogger(__name__)

BROADCAST_INTERVAL_S: float = float(os.getenv("WS_METRICS_INTERVAL_S", "10"))
AGENT_TELEMETRY_INTERVAL_S: float = float(os.getenv("WS_AGENT_TELEMETRY_INTERVAL_S", "5"))


class MetricsBroadcaster:
    """
    Periodically collects and broadcasts runtime metrics + agent telemetry.
    """

    def __init__(self) -> None:
        self._metrics_task:   Optional[asyncio.Task] = None
        self._telemetry_task: Optional[asyncio.Task] = None
        self._running:        bool  = False
        self._start_time:     float = time.time()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        if self._running:
            return
        self._running     = True
        self._start_time  = time.time()
        self._metrics_task = asyncio.create_task(
            self._metrics_loop(), name="ws-metrics-broadcast"
        )
        self._telemetry_task = asyncio.create_task(
            self._telemetry_loop(), name="ws-agent-telemetry"
        )
        log.info(
            "MetricsBroadcaster started: metrics=%ss telemetry=%ss",
            BROADCAST_INTERVAL_S, AGENT_TELEMETRY_INTERVAL_S,
        )

    async def stop(self) -> None:
        self._running = False
        for task in (self._metrics_task, self._telemetry_task):
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        log.info("MetricsBroadcaster stopped")

    # ------------------------------------------------------------------
    # Metrics broadcast loop
    # ------------------------------------------------------------------

    async def _metrics_loop(self) -> None:
        while self._running:
            await asyncio.sleep(BROADCAST_INTERVAL_S)
            if not self._running:
                break
            try:
                await self._broadcast_metrics()
            except Exception as exc:
                log.warning("MetricsBroadcaster._metrics_loop error: %s", exc)

    async def _broadcast_metrics(self) -> None:
        from backend.infrastructure.redis.keys import RedisKeys
        from backend.infrastructure.redis.pub_sub import pub_sub
        from backend.websocket.message_protocol import build_runtime_metrics
        from backend.websocket.stream_router import stream_router

        metrics = await self._collect_metrics()
        payload = build_runtime_metrics(metrics)

        # Broadcast to metrics-topic subscribers in the pool
        await stream_router.broadcast_to_topic("metrics", payload)
        # Also publish to Redis metrics channel for external consumers
        try:
            await pub_sub.publish(RedisKeys.channel_metrics(), payload)
        except Exception:
            pass

    async def _collect_metrics(self) -> Dict[str, Any]:
        metrics: Dict[str, Any] = {
            "uptime_s": round(time.time() - self._start_time, 1),
        }

        # WebSocket pool stats
        try:
            from backend.websocket.connection_pool import connection_pool
            metrics["websocket"] = connection_pool.stats()
        except Exception:
            metrics["websocket"] = {}

        # Heartbeat monitor stats
        try:
            from backend.websocket.heartbeat_monitor import heartbeat_monitor
            metrics["heartbeat"] = heartbeat_monitor.stats()
        except Exception:
            metrics["heartbeat"] = {}

        # Active executions (from Redis)
        try:
            from backend.infrastructure.redis.runtime_state_manager import runtime_state
            snapshot = await runtime_state.get_runtime_snapshot()
            metrics["active_executions"] = snapshot.get("active_executions", [])
            metrics["agents"]            = snapshot.get("agents", {})
        except Exception:
            metrics["active_executions"] = []
            metrics["agents"]            = {}

        # Runtime metrics from legacy runtime_metrics module
        try:
            from backend.runtime.runtime_metrics import runtime_metrics as rm
            metrics["runtime"] = rm.get_metrics() if hasattr(rm, "get_metrics") else {}
        except Exception:
            metrics["runtime"] = {}

        return metrics

    # ------------------------------------------------------------------
    # Agent telemetry loop
    # ------------------------------------------------------------------

    async def _telemetry_loop(self) -> None:
        """Push per-agent telemetry to agent-topic subscribers."""
        while self._running:
            await asyncio.sleep(AGENT_TELEMETRY_INTERVAL_S)
            if not self._running:
                break
            try:
                await self._broadcast_agent_telemetry()
            except Exception as exc:
                log.warning("MetricsBroadcaster._telemetry_loop error: %s", exc)

    async def _broadcast_agent_telemetry(self) -> None:
        from backend.websocket.connection_pool import connection_pool
        from backend.websocket.message_protocol import build_agent_telemetry

        # Find all agent:{name} topics that have active subscribers
        stats = connection_pool.stats()
        topic_counts = stats.get("topic_subscriber_counts", {})
        agent_topics = {
            t: c for t, c in topic_counts.items()
            if t.startswith("agent:") and c > 0
        }

        if not agent_topics:
            return

        try:
            from backend.infrastructure.redis.agent_activity_store import (
                agent_activity_store,
            )
        except ImportError:
            return

        for topic in agent_topics:
            agent_name = topic[len("agent:"):]
            try:
                activity = await agent_activity_store.get_activity(agent_name)
                if activity:
                    payload = build_agent_telemetry(agent_name, activity)
                    await connection_pool.broadcast_to_topic(topic, payload)
            except Exception as exc:
                log.debug(
                    "MetricsBroadcaster agent telemetry error agent=%s: %s",
                    agent_name, exc,
                )

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def is_running(self) -> bool:
        return self._running


# Singleton
metrics_broadcaster = MetricsBroadcaster()
