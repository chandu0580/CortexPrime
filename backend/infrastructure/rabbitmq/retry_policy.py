"""
RabbitMQ Retry Policy & Dead-Letter Queue Manager
--------------------------------------------------
Implements structured retry with exponential back-off for consumer
failures and provides tooling to inspect and replay the dead-letter
queue.

Retry flow
~~~~~~~~~~
  1. Consumer handler raises an exception
  2. ``RetryPolicy.should_retry(retry_count)`` — True if under limit
  3. Message is republished to ``cortex.retry`` queue with updated
     ``retry_count`` header and a per-message TTL
     (see ``RetryPolicy.delay_for(attempt)``).
  4. After the TTL expires, the retry exchange routes the message back
     to its original queue via the dead-letter-exchange mechanism.
  5. After ``max_retries`` the message is rejected → DLQ.

DLQ management
~~~~~~~~~~~~~~
  ``DLQManager.inspect()``      — list messages in DLQ (non-destructive)
  ``DLQManager.replay(msg_id)`` — republish a single DLQ message
  ``DLQManager.purge()``        — delete all DLQ messages (admin only)
"""
from __future__ import annotations

import logging
import random
from typing import Any, Dict, List

log = logging.getLogger(__name__)

try:
    import aio_pika
    _AIO_PIKA_AVAILABLE = True
except ImportError:
    _AIO_PIKA_AVAILABLE = False

from backend.infrastructure.rabbitmq.schemas import (
    Exchanges,
    Queues,
    RabbitMessage,
)

# =========================================================
# RETRY POLICY
# =========================================================

class RetryPolicy:
    """
    Exponential back-off retry policy.

    Parameters
    ----------
    max_retries     : maximum handler attempts before DLQ
    initial_delay_s : delay before attempt 1 (seconds)
    max_delay_s     : back-off ceiling (seconds)
    multiplier      : back-off growth factor
    jitter          : fractional random jitter (0–1)
    """

    def __init__(
        self,
        max_retries:     int   = 3,
        initial_delay_s: float = 5.0,
        max_delay_s:     float = 120.0,
        multiplier:      float = 2.0,
        jitter:          float = 0.3,
    ) -> None:
        self.max_retries     = max_retries
        self.initial_delay_s = initial_delay_s
        self.max_delay_s     = max_delay_s
        self.multiplier      = multiplier
        self.jitter          = jitter

    def should_retry(self, retry_count: int) -> bool:
        """True if the message should be retried."""
        return retry_count < self.max_retries

    def delay_for(self, attempt: int) -> float:
        """
        Return delay in seconds for the given attempt number.

        attempt=0 → initial_delay_s
        attempt=1 → initial_delay_s * multiplier
        …
        All values capped at max_delay_s, then ±jitter applied.
        """
        raw   = self.initial_delay_s * (self.multiplier ** attempt)
        capped = min(raw, self.max_delay_s)
        noise  = capped * self.jitter * (random.random() * 2 - 1)
        return max(0.1, capped + noise)

    def delay_ms(self, attempt: int) -> int:
        """Return the delay as integer milliseconds (for AMQP message TTL)."""
        return int(self.delay_for(attempt) * 1000)


# Default singleton policy — can be overridden per-queue
default_retry_policy = RetryPolicy()


# =========================================================
# DLQ MANAGER
# =========================================================

class DLQManager:
    """
    Dead-letter queue inspection and replay tooling.

    All methods are no-ops when RabbitMQ is unavailable.
    """

    # ---------------------------------------------------------
    # INSPECT (non-destructive peek)
    # ---------------------------------------------------------

    async def inspect(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Peek at messages in the DLQ without consuming them.

        Returns a list of dicts with message metadata.  This uses
        the ``get`` method which retrieves a single message at a time
        with ``no_ack=False``, then nack-requeues it.
        """
        if not _AIO_PIKA_AVAILABLE:
            return []

        from backend.infrastructure.rabbitmq.connection import rabbitmq_connection
        if not rabbitmq_connection.is_available:
            return []

        results: List[Dict[str, Any]] = []

        try:
            ch    = rabbitmq_connection.channel
            queue = await ch.get_queue(Queues.DEAD_LETTER)

            for _ in range(limit):
                raw = await queue.get(no_ack=False, fail=False)
                if raw is None:
                    break

                entry: Dict[str, Any] = {
                    "message_id":   raw.message_id,
                    "routing_key":  raw.routing_key,
                    "headers":      dict(raw.headers or {}),
                    "body_preview": raw.body[:200].decode(errors="replace"),
                }

                try:
                    msg = RabbitMessage.from_bytes(raw.body)
                    entry.update({
                        "message_type": msg.message_type.value,
                        "execution_id": msg.execution_id,
                        "retry_count":  msg.retry_count,
                        "timestamp":    msg.timestamp,
                        "trace_id":     msg.trace.trace_id,
                    })
                except Exception:
                    pass

                results.append(entry)
                # Put back without consuming
                await raw.nack(requeue=True)

        except Exception as exc:
            log.warning("DLQManager.inspect failed: %s", exc)

        return results

    # ---------------------------------------------------------
    # REPLAY
    # ---------------------------------------------------------

    async def replay(self, message_id: str) -> bool:
        """
        Find a message by message_id in the DLQ and republish it to
        its original routing key on the orchestration exchange.

        Returns True if the message was found and republished.
        """
        if not _AIO_PIKA_AVAILABLE:
            return False

        from backend.infrastructure.rabbitmq.connection import rabbitmq_connection
        if not rabbitmq_connection.is_available:
            return False

        try:
            ch    = rabbitmq_connection.channel
            queue = await ch.get_queue(Queues.DEAD_LETTER)

            # Peek up to 1000 messages looking for the target
            for _ in range(1000):
                raw = await queue.get(no_ack=False, fail=False)
                if raw is None:
                    break

                if raw.message_id == message_id:
                    # Republish with incremented retry_count = 0 (fresh)
                    try:
                        msg = RabbitMessage.from_bytes(raw.body)
                        msg.retry_count = 0
                    except Exception:
                        msg = None

                    orch_x = await ch.get_exchange(Exchanges.ORCHESTRATION)
                    await orch_x.publish(
                        aio_pika.Message(
                            body         = raw.body if msg is None else msg.to_bytes(),
                            delivery_mode= aio_pika.DeliveryMode.PERSISTENT,
                            content_type = "application/json",
                            message_id   = raw.message_id,
                            headers      = dict(raw.headers or {}),
                        ),
                        routing_key = raw.routing_key or Queues.ORCHESTRATION,
                    )

                    await raw.ack()
                    log.info("DLQ replayed message_id=%s", message_id)
                    return True
                else:
                    # Not the target — requeue
                    await raw.nack(requeue=True)

        except Exception as exc:
            log.warning("DLQManager.replay failed: %s", exc)

        return False

    # ---------------------------------------------------------
    # REPUBLISH WITH BACKOFF  (called by consumer on retry)
    # ---------------------------------------------------------

    async def republish_with_delay(
        self,
        message:     RabbitMessage,
        retry_count: int,
        policy:      RetryPolicy = default_retry_policy,
    ) -> bool:
        """
        Republish a failed message to the retry staging queue
        with a per-message TTL so it redelivers after the backoff delay.
        """
        if not _AIO_PIKA_AVAILABLE:
            return False

        from backend.infrastructure.rabbitmq.connection import rabbitmq_connection
        if not rabbitmq_connection.is_available:
            return False

        try:
            message.retry_count = retry_count
            delay_ms = policy.delay_ms(retry_count)

            ch       = rabbitmq_connection.channel
            retry_x  = await ch.get_exchange(Exchanges.RETRY)

            await retry_x.publish(
                aio_pika.Message(
                    body         = message.to_bytes(),
                    delivery_mode= aio_pika.DeliveryMode.PERSISTENT,
                    content_type = "application/json",
                    message_id   = message.message_id,
                    expiration   = str(delay_ms),   # per-message TTL in ms
                    headers      = {
                        **message.to_amqp_headers(),
                        "retry_count": str(retry_count),
                        "retry_delay_ms": str(delay_ms),
                    },
                ),
                routing_key = Queues.RETRY,
            )

            log.info(
                "Message %s queued for retry #%d in %d ms",
                message.message_id, retry_count, delay_ms,
            )
            return True

        except Exception as exc:
            log.warning("DLQManager.republish_with_delay failed: %s", exc)
            return False

    # ---------------------------------------------------------
    # PURGE  (admin / test use only)
    # ---------------------------------------------------------

    async def purge(self) -> int:
        """
        Delete all messages in the DLQ.

        Returns the number of messages deleted, or -1 on error.
        """
        if not _AIO_PIKA_AVAILABLE:
            return -1

        from backend.infrastructure.rabbitmq.connection import rabbitmq_connection
        if not rabbitmq_connection.is_available:
            return -1

        try:
            ch    = rabbitmq_connection.channel
            queue = await ch.get_queue(Queues.DEAD_LETTER)
            count = await queue.purge()
            log.warning("DLQ purged: %d messages deleted", count)
            return count
        except Exception as exc:
            log.warning("DLQManager.purge failed: %s", exc)
            return -1


# =========================================================
# SINGLETONS
# =========================================================

dlq_manager = DLQManager()
