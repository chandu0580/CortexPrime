"""
Memory Event Subscriber.

Bridges the internal CortexPrime EventBus to the memory system.
Subscribes to significant agent events and automatically persists them
to the appropriate memory stores.

Also optionally connects to RabbitMQ for cross-service memory event
propagation when RABBITMQ_HOST / RABBITMQ_URL is configured.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Event types that warrant episodic memory persistence
_PERSIST_TYPES = frozenset({
    "AGENT_COMPLETED",
    "AGENT_FAILED",
    "PHASE_COMPLETED",
    "STREAM_COMPLETED",
    "PLAN_GENERATED",
    "RESEARCH_COMPLETED",
    "CRITIQUE_COMPLETED",
    "OPTIMIZATION_COMPLETED",
    "ORCHESTRATION_COMPLETED",
})

# Event types that warrant reflection storage
_REFLECT_TYPES = frozenset({
    "REFLECTION_GENERATED",
    "SELF_CRITIQUE",
    "PERFORMANCE_REVIEW",
})


class MemoryEventSubscriber:
    """
    Listens to the internal EventBus and routes significant events to
    memory stores.  Optionally publishes to RabbitMQ.
    """

    def __init__(self) -> None:
        self._running:    bool         = False
        self._mq_channel: Optional[Any] = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        if self._running:
            return
        self._running = True

        from backend.events.event_bus import event_bus
        event_bus.subscribe(self._on_event)
        logger.info("Memory event subscriber started")

        # Optional RabbitMQ bridge
        if os.getenv("RABBITMQ_HOST") or os.getenv("RABBITMQ_URL"):
            asyncio.ensure_future(self._connect_rabbitmq())

    async def stop(self) -> None:
        self._running = False
        if self._mq_channel:
            try:
                await self._mq_channel.close()
            except Exception:
                pass
            self._mq_channel = None

    # ------------------------------------------------------------------
    # Event handler (registered as sync callback, dispatches async task)
    # ------------------------------------------------------------------

    def _on_event(self, event: Any) -> None:
        if self._running:
            asyncio.ensure_future(self._process(event))

    async def _process(self, event: Any) -> None:
        from backend.memory.memory_orchestrator import memory_orchestrator

        try:
            event_type = (getattr(event, "event_type", "") or "").upper()
            message    = getattr(event, "message", "") or ""
            agent      = getattr(event, "agent",   "unknown")

            if not message:
                return

            if event_type in _PERSIST_TYPES:
                session_id = getattr(event, "execution_id", None) or "global"
                await memory_orchestrator.store_cognition_event(
                    agent      = agent,
                    event_type = getattr(event, "event_type", event_type),
                    content    = message,
                    session_id = session_id,
                    mission_id = getattr(event, "execution_id", None),
                    metadata   = {
                        "status":     getattr(event, "status",     None),
                        "latency_ms": getattr(event, "latency_ms", None),
                        "phase":      getattr(event, "phase",      None),
                    },
                )

            elif event_type in _REFLECT_TYPES:
                await memory_orchestrator.store_reflection(
                    agent      = agent,
                    reflection = message,
                    mission_id = getattr(event, "execution_id", None),
                    score      = getattr(event, "confidence_score", None),
                )

        except Exception as exc:
            logger.debug(f"Memory event processing error: {exc}")

    # ------------------------------------------------------------------
    # Optional RabbitMQ bridge
    # ------------------------------------------------------------------

    async def _connect_rabbitmq(self) -> None:
        try:
            import aio_pika

            url = os.getenv("RABBITMQ_URL") or (
                "amqp://{user}:{pw}@{host}:{port}/{vhost}".format(
                    user  = os.getenv("RABBITMQ_USER",     "cortex"),
                    pw    = os.getenv("RABBITMQ_PASSWORD", "cortexmq"),
                    host  = os.getenv("RABBITMQ_HOST",     "localhost"),
                    port  = os.getenv("RABBITMQ_PORT",     "5672"),
                    vhost = os.getenv("RABBITMQ_VHOST",    "cortex"),
                )
            )
            connection = await aio_pika.connect_robust(url, timeout=5)
            channel    = await connection.channel()

            exchange = await channel.declare_exchange(
                "cortex.memory",
                aio_pika.ExchangeType.TOPIC,
                durable=True,
            )
            for queue_name in ("memory.episodic", "memory.semantic", "memory.reflection"):
                q = await channel.declare_queue(queue_name, durable=True)
                await q.bind(exchange, routing_key=queue_name)

            self._mq_channel = channel
            logger.info("Memory subscriber connected to RabbitMQ")

        except ImportError:
            logger.debug("aio-pika not installed — RabbitMQ bridge skipped")
        except Exception as exc:
            logger.warning(f"RabbitMQ connection failed: {exc}")

    async def publish_memory_event(
        self,
        routing_key: str,
        payload:     Dict[str, Any],
    ) -> None:
        if self._mq_channel is None:
            return
        try:
            import aio_pika

            exchange = await self._mq_channel.get_exchange("cortex.memory")
            message  = aio_pika.Message(
                body          = json.dumps(payload).encode(),
                content_type  = "application/json",
                delivery_mode = aio_pika.DeliveryMode.PERSISTENT,
            )
            await exchange.publish(message, routing_key=routing_key)
        except Exception as exc:
            logger.debug(f"RabbitMQ publish failed: {exc}")


# =========================================================
# SINGLETON
# =========================================================

memory_event_subscriber = MemoryEventSubscriber()
