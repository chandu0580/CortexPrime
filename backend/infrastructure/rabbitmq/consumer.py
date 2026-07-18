"""
RabbitMQ Consumer
-----------------
Subscribes to RabbitMQ queues and dispatches messages to registered
async handlers.

Features
--------
* Per-message-type handler registry via ``on(MessageType, handler)``
* Per-queue consumer tags for clean cancellation
* Retry with exponential back-off via ``DLQManager.republish_with_delay``
  (delayed redelivery using per-message AMQP TTL on the retry queue)
* Terminal failure → reject to DLQ (no requeue)
* Tracing via ``MessageTracer.wrap``
* ``restart()`` — re-attach all consumers (called after broker reconnect)
* Graceful ``stop()``
"""
from __future__ import annotations

import logging
from typing import Callable, Dict, List

log = logging.getLogger(__name__)

try:
    import aio_pika  # noqa: F401
    _AIO_PIKA_AVAILABLE = True
except ImportError:
    _AIO_PIKA_AVAILABLE = False

from backend.infrastructure.rabbitmq.connection import rabbitmq_connection
from backend.infrastructure.rabbitmq.schemas import (
    MessageType,
    Queues,
    RabbitMessage,
)
from backend.infrastructure.rabbitmq.tracing import message_tracer

# =========================================================
# CONSUMER
# =========================================================

class RabbitMQConsumer:
    """
    Multi-queue async consumer with retry and DLQ integration.
    """

    # Default maximum handler retries (overridden per message by
    # the ``max_retries`` field on the message envelope)
    DEFAULT_MAX_RETRIES = 3

    def __init__(self) -> None:
        self._handlers:    Dict[str, Callable] = {}    # message_type → handler
        self._consumer_tags: Dict[str, object] = {}    # queue_name   → cancel-tag
        self._running:     bool = False

        # Queues to consume on start (can be extended before start())
        self._queues: List[str] = [
            Queues.ORCHESTRATION,
            Queues.AGENT_TASKS,
            Queues.AGENT_RESULTS,
            Queues.MEMORY_OPERATIONS,
            Queues.REFLECTION_TRIGGERS,
            Queues.EXECUTION_EVENTS,
            Queues.COGNITION_PIPELINE,
            Queues.PIPELINE_STAGES,
            # Per-agent queues
            Queues.AGENT_PLANNER,
            Queues.AGENT_RESEARCHER,
            Queues.AGENT_CRITIC,
            Queues.AGENT_OPTIMIZER,
            Queues.AGENT_ORCHESTRATOR,
        ]

    # ---------------------------------------------------------
    # HANDLER REGISTRY
    # ---------------------------------------------------------

    def on(
        self,
        message_type: MessageType,
        handler:      Callable,
        traced:       bool = True,
    ) -> None:
        """
        Register an async handler for a message type.

        Parameters
        ----------
        message_type : the message type to handle
        handler      : ``async def handler(msg: RabbitMessage) -> None``
        traced       : wrap with tracing (default True)
        """
        h = message_tracer.wrap(handler) if traced else handler
        self._handlers[message_type.value] = h
        log.debug("Handler registered for %s", message_type.value)

    def on_queue(self, queue_name: str) -> None:
        """
        Add an extra queue to the consume list before ``start()`` is called.
        """
        if queue_name not in self._queues:
            self._queues.append(queue_name)

    # ---------------------------------------------------------
    # START / STOP / RESTART
    # ---------------------------------------------------------

    async def start(self) -> None:
        """Attach consumers to all registered queues."""
        if not _AIO_PIKA_AVAILABLE:
            return

        if not await rabbitmq_connection.ensure_connected():
            return

        if self._running:
            return

        self._running = True
        await self._attach_all()

    async def stop(self) -> None:
        """Cancel all consumer tags gracefully."""
        self._running = False
        for tag in list(self._consumer_tags.values()):
            try:
                await tag.cancel()
            except Exception:
                pass
        self._consumer_tags.clear()
        log.info("RabbitMQ consumers stopped")

    async def restart(self) -> None:
        """Re-attach consumers after a broker reconnect."""
        log.info("RabbitMQ consumers restarting…")
        await self.stop()
        self._running = True
        await self._attach_all()

    # ---------------------------------------------------------
    # INTERNAL: ATTACH
    # ---------------------------------------------------------

    async def _attach_all(self) -> None:
        for qname in self._queues:
            await self._attach_queue(qname)

    async def _attach_queue(self, qname: str) -> None:
        try:
            ch    = rabbitmq_connection.channel
            queue = await ch.get_queue(qname)
            tag   = await queue.consume(self._make_dispatch(qname))
            self._consumer_tags[qname] = tag
            log.info("📥 Consuming: %s", qname)
        except Exception as exc:
            log.warning("Failed to consume queue %s: %s", qname, exc)

    # ---------------------------------------------------------
    # DISPATCH CALLBACK
    # ---------------------------------------------------------

    def _make_dispatch(self, queue_name: str) -> Callable:
        """Return a per-queue AMQP message callback."""

        async def dispatch(raw) -> None:
            async with raw.process(ignore_processed=True):
                try:
                    msg = RabbitMessage.from_bytes(raw.body)
                except Exception as exc:
                    log.error(
                        "Cannot parse RabbitMessage from %s: %s — rejecting",
                        queue_name, exc,
                    )
                    await raw.reject(requeue=False)
                    return

                handler = self._handlers.get(msg.message_type.value)

                if handler is None:
                    # No handler registered — ack silently
                    await raw.ack()
                    return

                try:
                    await handler(msg)
                    await raw.ack()

                except Exception as exc:
                    retry_count = msg.retry_count
                    max_retries = msg.max_retries or self.DEFAULT_MAX_RETRIES

                    from backend.infrastructure.rabbitmq.retry_policy import (
                        default_retry_policy,
                        dlq_manager,
                    )

                    if default_retry_policy.should_retry(retry_count):
                        log.warning(
                            "[%s] Handler failed (attempt %d/%d): %s — scheduling retry",
                            queue_name, retry_count + 1, max_retries, exc,
                        )
                        republished = await dlq_manager.republish_with_delay(
                            message     = msg,
                            retry_count = retry_count + 1,
                            policy      = default_retry_policy,
                        )
                        if republished:
                            await raw.ack()       # consumed; will re-arrive via retry queue
                        else:
                            await raw.nack(requeue=True)  # fallback: basic requeue
                    else:
                        log.error(
                            "[%s] Message exceeded retry limit (%d) — sending to DLQ: %s",
                            queue_name, max_retries, exc,
                        )
                        await raw.reject(requeue=False)

        return dispatch


# =========================================================
# SINGLETON
# =========================================================

rabbitmq_consumer = RabbitMQConsumer()
