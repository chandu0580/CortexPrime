"""
RabbitMQ Publisher
------------------
Publishes messages to RabbitMQ exchanges and queues.

Features
--------
* Uses the ``ChannelPool`` to eliminate single-channel contention under load.
* Injects distributed tracing headers via ``MessageTracer``.
* Returns bool success/failure — never raises; falls back silently when the
  broker is unavailable so the runtime stays operational.
* Typed high-level helpers for common event types.

All public methods are fire-and-forget safe (can be wrapped in
``asyncio.ensure_future`` or ``asyncio.create_task``).
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

try:
    import aio_pika
    _AIO_PIKA_AVAILABLE = True
except ImportError:
    _AIO_PIKA_AVAILABLE = False

from backend.infrastructure.rabbitmq.channel_pool import channel_pool
from backend.infrastructure.rabbitmq.connection import rabbitmq_connection
from backend.infrastructure.rabbitmq.schemas import (
    Exchanges,
    Queues,
    RabbitMessage,
    RoutingKeys,
    agent_task_message,
    agent_to_agent_message,
    cognition_event_message,
    memory_store_message,
    mission_complete_message,
    mission_failed_message,
    mission_start_message,
    pipeline_stage_done_message,
    pipeline_stage_start_message,
    reflection_trigger_message,
)
from backend.infrastructure.rabbitmq.tracing import message_tracer

# =========================================================
# RABBITMQ PUBLISHER
# =========================================================

class RabbitMQPublisher:
    """
    Publishes messages to RabbitMQ exchanges and queues via the
    shared channel pool with automatic tracing header injection.
    """

    # ---------------------------------------------------------
    # CORE PUBLISH
    # ---------------------------------------------------------

    async def publish(
        self,
        message:       RabbitMessage,
        exchange_name: str = Exchanges.COGNITION,
        routing_key:   Optional[str] = None,
    ) -> bool:
        """
        Publish a message to the named exchange.

        Parameters
        ----------
        message       : the typed ``RabbitMessage`` envelope
        exchange_name : target exchange (default: cognition topic)
        routing_key   : AMQP routing key; defaults to message_type value

        Returns ``True`` on success, ``False`` on any failure.
        """
        if not _AIO_PIKA_AVAILABLE:
            return False

        if not await rabbitmq_connection.ensure_connected():
            return False

        rk = routing_key or message.message_type.value

        try:
            async with channel_pool.acquire() as ch:
                if ch is None:
                    return False

                exchange = await ch.get_exchange(exchange_name)
                await exchange.publish(
                    aio_pika.Message(
                        body          = message.to_bytes(),
                        delivery_mode = aio_pika.DeliveryMode.PERSISTENT,
                        content_type  = "application/json",
                        message_id    = message.message_id,
                        priority      = min(message.priority, 9),  # AMQP max is 9
                        headers       = message_tracer.outgoing_headers(message),
                    ),
                    routing_key = rk,
                )

            message_tracer.record_publish(message, queue=rk)
            return True

        except Exception as exc:
            log.warning(
                "RabbitMQ publish failed (exchange=%s rk=%s): %s",
                exchange_name, rk, exc,
            )
            return False

    # ---------------------------------------------------------
    # DIRECT QUEUE PUBLISH
    # ---------------------------------------------------------

    async def publish_to_queue(
        self,
        message:    RabbitMessage,
        queue_name: str,
    ) -> bool:
        """
        Publish directly to a named queue via the default exchange.
        Use for precise direct routing (e.g. per-agent task queues).
        """
        if not _AIO_PIKA_AVAILABLE:
            return False

        if not await rabbitmq_connection.ensure_connected():
            return False

        try:
            async with channel_pool.acquire() as ch:
                if ch is None:
                    return False

                await ch.default_exchange.publish(
                    aio_pika.Message(
                        body          = message.to_bytes(),
                        delivery_mode = aio_pika.DeliveryMode.PERSISTENT,
                        content_type  = "application/json",
                        message_id    = message.message_id,
                        priority      = min(message.priority, 9),
                        headers       = message_tracer.outgoing_headers(message),
                    ),
                    routing_key = queue_name,
                )

            message_tracer.record_publish(message, queue=queue_name)
            return True

        except Exception as exc:
            log.warning(
                "RabbitMQ direct-queue publish failed (queue=%s): %s",
                queue_name, exc,
            )
            return False

    # ---------------------------------------------------------
    # FANOUT BROADCAST
    # ---------------------------------------------------------

    async def broadcast(
        self,
        message: RabbitMessage,
    ) -> bool:
        """Publish to the fanout events exchange (all bound queues receive it)."""
        return await self.publish(
            message,
            exchange_name = Exchanges.EVENTS,
            routing_key   = "",
        )

    # =========================================================
    # HIGH-LEVEL HELPERS
    # =========================================================

    # ── Missions ──────────────────────────────────────────────

    async def dispatch_mission(
        self,
        execution_id: str,
        objective:    str,
        agents:       List[str] = [],
        priority:     int = 5,
        mission_id:   Optional[str] = None,
    ) -> bool:
        msg = mission_start_message(
            execution_id = execution_id,
            objective    = objective,
            agents       = agents,
            priority     = priority,
            mission_id   = mission_id,
        )
        return await self.publish_to_queue(msg, Queues.ORCHESTRATION)

    async def publish_mission_complete(
        self,
        execution_id: str,
        result:       Dict[str, Any],
        mission_id:   Optional[str] = None,
    ) -> bool:
        msg = mission_complete_message(
            execution_id = execution_id,
            result       = result,
            mission_id   = mission_id,
        )
        return await self.publish(
            msg,
            exchange_name = Exchanges.EVENTS,
            routing_key   = "",
        )

    async def publish_mission_failed(
        self,
        execution_id: str,
        error:        str,
        stage:        str = "",
        mission_id:   Optional[str] = None,
    ) -> bool:
        msg = mission_failed_message(
            execution_id = execution_id,
            error        = error,
            stage        = stage,
            mission_id   = mission_id,
        )
        return await self.publish(
            msg,
            exchange_name = Exchanges.EVENTS,
            routing_key   = "",
        )

    # ── Agent tasks ───────────────────────────────────────────

    async def dispatch_agent_task(
        self,
        execution_id: str,
        agent_name:   str,
        task:         Dict[str, Any],
        priority:     int = 5,
        parent_msg:   Optional[RabbitMessage] = None,
    ) -> bool:
        """Dispatch a task to a specific agent's dedicated queue."""
        msg = agent_task_message(
            execution_id = execution_id,
            agent_name   = agent_name,
            task         = task,
            priority     = priority,
            parent_msg   = parent_msg,
        )
        # Route to per-agent queue via agents topic exchange
        return await self.publish(
            msg,
            exchange_name = Exchanges.AGENTS,
            routing_key   = RoutingKeys.agent_task(agent_name),
        )

    async def send_agent_to_agent(
        self,
        execution_id: str,
        from_agent:   str,
        to_agent:     str,
        content:      Dict[str, Any],
        parent_msg:   Optional[RabbitMessage] = None,
    ) -> bool:
        """Direct agent-to-agent message via agents topic exchange."""
        msg = agent_to_agent_message(
            execution_id = execution_id,
            from_agent   = from_agent,
            to_agent     = to_agent,
            content      = content,
            parent_msg   = parent_msg,
        )
        return await self.publish(
            msg,
            exchange_name = Exchanges.AGENTS,
            routing_key   = RoutingKeys.agent_task(to_agent),
        )

    async def publish_agent_result(
        self,
        execution_id: str,
        agent_name:   str,
        result:       Dict[str, Any],
        parent_msg:   Optional[RabbitMessage] = None,
    ) -> bool:
        from backend.infrastructure.rabbitmq.schemas import agent_result_message
        trace = parent_msg.trace.child() if parent_msg else None
        msg = agent_result_message(
            execution_id      = execution_id,
            agent_name        = agent_name,
            result            = result,
            parent_message_id = parent_msg.message_id if parent_msg else None,
            trace             = trace,
        )
        return await self.publish_to_queue(msg, Queues.AGENT_RESULTS)

    # ── Cognition events ──────────────────────────────────────

    async def emit_cognition_event(
        self,
        execution_id: str,
        agent:        str,
        event_type:   str,
        status:       str,
        message:      str,
        phase:        str = "",
        payload:      Dict[str, Any] = {},
        parent_msg:   Optional[RabbitMessage] = None,
    ) -> bool:
        msg = cognition_event_message(
            execution_id = execution_id,
            agent        = agent,
            event_type   = event_type,
            status       = status,
            message      = message,
            phase        = phase,
            payload      = payload,
            parent_msg   = parent_msg,
        )
        return await self.publish(
            msg,
            exchange_name = Exchanges.COGNITION,
            routing_key   = RoutingKeys.cognition(phase or "event", agent),
        )

    # Backward-compat alias
    async def emit_execution_event(
        self,
        execution_id: str,
        agent:        str,
        event_type:   str,
        status:       str,
        message:      str,
        payload:      Dict[str, Any] = {},
    ) -> bool:
        return await self.emit_cognition_event(
            execution_id = execution_id,
            agent        = agent,
            event_type   = event_type,
            status       = status,
            message      = message,
            payload      = payload,
        )

    # ── Pipeline stages ───────────────────────────────────────

    async def publish_stage_start(
        self,
        execution_id: str,
        stage:        str,
        agent:        str,
        task:         Dict[str, Any] = {},
        parent_msg:   Optional[RabbitMessage] = None,
    ) -> bool:
        msg = pipeline_stage_start_message(
            execution_id = execution_id,
            stage        = stage,
            agent        = agent,
            task         = task,
            parent_msg   = parent_msg,
        )
        return await self.publish(
            msg,
            exchange_name = Exchanges.COGNITION,
            routing_key   = f"pipeline.stage.start.{agent.lower()}",
        )

    async def publish_stage_done(
        self,
        execution_id: str,
        stage:        str,
        agent:        str,
        output:       Dict[str, Any] = {},
        duration_ms:  Optional[float] = None,
        parent_msg:   Optional[RabbitMessage] = None,
    ) -> bool:
        msg = pipeline_stage_done_message(
            execution_id = execution_id,
            stage        = stage,
            agent        = agent,
            output       = output,
            duration_ms  = duration_ms,
            parent_msg   = parent_msg,
        )
        return await self.publish(
            msg,
            exchange_name = Exchanges.COGNITION,
            routing_key   = f"pipeline.stage.done.{agent.lower()}",
        )

    # ── Memory ────────────────────────────────────────────────

    async def publish_memory_store(
        self,
        execution_id: str,
        agent:        str,
        memory_type:  str,
        content:      str,
        metadata:     Dict[str, Any] = {},
    ) -> bool:
        msg = memory_store_message(
            execution_id = execution_id,
            agent        = agent,
            memory_type  = memory_type,
            content      = content,
            metadata     = metadata,
        )
        return await self.publish(
            msg,
            exchange_name = Exchanges.COGNITION,
            routing_key   = "memory.store",
        )

    # ── Reflection ────────────────────────────────────────────

    async def trigger_reflection(
        self,
        execution_id: str,
        agent:        str,
        context:      Dict[str, Any],
        mission_id:   Optional[str] = None,
    ) -> bool:
        msg = reflection_trigger_message(
            execution_id = execution_id,
            agent        = agent,
            context      = context,
            mission_id   = mission_id,
        )
        return await self.publish_to_queue(msg, Queues.REFLECTION_TRIGGERS)


# =========================================================
# SINGLETON
# =========================================================

rabbitmq_publisher = RabbitMQPublisher()
