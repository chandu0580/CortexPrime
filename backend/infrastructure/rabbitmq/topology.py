"""
RabbitMQ Topology
-----------------
Centralized declaration of all exchanges, queues, and bindings for
the CortexPrime orchestration runtime.

Exchange architecture
~~~~~~~~~~~~~~~~~~~~~
  cortex.cognition   (topic)  — cognition event broadcast
  cortex.orchestration (direct) — task dispatch to queues
  cortex.agents      (topic)  — agent-to-agent routing
  cortex.events      (fanout) — all-subscriber broadcast
  cortex.dead.letter.x (direct) — dead-letter exchange
  cortex.retry.x     (direct) — retry staging with TTL

Topology is idempotent — declaring it twice is safe.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict

log = logging.getLogger(__name__)

try:
    import aio_pika
    _AIO_PIKA_AVAILABLE = True
except ImportError:
    _AIO_PIKA_AVAILABLE = False

from backend.infrastructure.rabbitmq.schemas import Exchanges, Queues


# =========================================================
# MESSAGE TTL  (default 30 minutes)
# =========================================================

_MESSAGE_TTL_MS = int(os.getenv("RABBITMQ_MESSAGE_TTL_MS", str(30 * 60 * 1000)))
_RETRY_DELAY_MS = int(os.getenv("RABBITMQ_RETRY_DELAY_MS", str(5_000)))  # 5 s default


# =========================================================
# TOPOLOGY
# =========================================================

class Topology:
    """Declares all RabbitMQ entities needed by CortexPrime."""

    async def declare(self, channel) -> None:
        """
        Declare all exchanges, queues, and bindings.

        Parameters
        ----------
        channel : aio_pika.Channel
            An open channel from ``rabbitmq_connection``.
        """
        if not _AIO_PIKA_AVAILABLE or channel is None:
            return

        try:
            await self._declare_exchanges(channel)
            await self._declare_queues(channel)
            await self._declare_bindings(channel)
            log.info("✅ RabbitMQ topology declared")
        except Exception as exc:
            log.warning("⚠️  Topology declaration failed: %s", exc)

    # ---------------------------------------------------------
    # EXCHANGES
    # ---------------------------------------------------------

    async def _declare_exchanges(self, ch) -> Dict[str, Any]:
        """Declare all exchanges and return them by logical name."""

        # Dead-letter exchange — must come first
        dlx = await ch.declare_exchange(
            Exchanges.DEAD_LETTER,
            aio_pika.ExchangeType.DIRECT,
            durable=True,
        )

        # Retry staging exchange (messages re-queued after TTL)
        retry_x = await ch.declare_exchange(
            Exchanges.RETRY,
            aio_pika.ExchangeType.DIRECT,
            durable=True,
        )

        # Cognition topic exchange — wildcard subscriptions
        cognition_x = await ch.declare_exchange(
            Exchanges.COGNITION,
            aio_pika.ExchangeType.TOPIC,
            durable=True,
        )

        # Orchestration direct exchange — precise routing
        orchestration_x = await ch.declare_exchange(
            Exchanges.ORCHESTRATION,
            aio_pika.ExchangeType.DIRECT,
            durable=True,
        )

        # Agents topic exchange — agent.{name}.{action} routing
        agents_x = await ch.declare_exchange(
            Exchanges.AGENTS,
            aio_pika.ExchangeType.TOPIC,
            durable=True,
        )

        # Events fanout exchange — broadcast to all bound queues
        events_x = await ch.declare_exchange(
            Exchanges.EVENTS,
            aio_pika.ExchangeType.FANOUT,
            durable=True,
        )

        return {
            "dlx":            dlx,
            "retry":          retry_x,
            "cognition":      cognition_x,
            "orchestration":  orchestration_x,
            "agents":         agents_x,
            "events":         events_x,
        }

    # ---------------------------------------------------------
    # QUEUES
    # ---------------------------------------------------------

    async def _declare_queues(self, ch) -> None:
        """Declare all durable queues with DLX and message TTL."""

        dlx_args: Dict[str, Any] = {
            "x-dead-letter-exchange":    Exchanges.DEAD_LETTER,
            "x-dead-letter-routing-key": Queues.DEAD_LETTER,
            "x-message-ttl":             _MESSAGE_TTL_MS,
        }

        retry_args: Dict[str, Any] = {
            "x-dead-letter-exchange":    Exchanges.COGNITION,
            "x-message-ttl":             _RETRY_DELAY_MS,
        }

        # ── DLQ  (no TTL — messages sit here for inspection) ──
        await ch.declare_queue(Queues.DEAD_LETTER, durable=True)

        # ── Retry staging queue ──
        await ch.declare_queue(
            Queues.RETRY,
            durable=True,
            arguments={
                **retry_args,
                # On TTL expiry, route back to orchestration exchange
                "x-dead-letter-exchange":    Exchanges.ORCHESTRATION,
            },
        )

        # ── Primary runtime queues ──
        primary_queues = [
            Queues.ORCHESTRATION,
            Queues.COGNITION_PIPELINE,
            Queues.AGENT_TASKS,
            Queues.AGENT_RESULTS,
            Queues.MEMORY_OPERATIONS,
            Queues.REFLECTION_TRIGGERS,
            Queues.EXECUTION_EVENTS,
            Queues.COGNITION_BROADCAST,
            Queues.PIPELINE_STAGES,
        ]

        for qname in primary_queues:
            await ch.declare_queue(qname, durable=True, arguments=dlx_args)

        # ── Per-agent dedicated queues ──
        agent_queues = [
            Queues.AGENT_PLANNER,
            Queues.AGENT_RESEARCHER,
            Queues.AGENT_CRITIC,
            Queues.AGENT_OPTIMIZER,
            Queues.AGENT_ORCHESTRATOR,
        ]

        for qname in agent_queues:
            await ch.declare_queue(qname, durable=True, arguments=dlx_args)

    # ---------------------------------------------------------
    # BINDINGS
    # ---------------------------------------------------------

    async def _declare_bindings(self, ch) -> None:
        """Bind queues to exchanges with routing keys."""

        # ── Cognition topic exchange bindings ──────────────────
        cognition_x = await ch.get_exchange(Exchanges.COGNITION)

        await (await ch.get_queue(Queues.COGNITION_PIPELINE)).bind(
            cognition_x, routing_key="cognition.#"
        )
        await (await ch.get_queue(Queues.COGNITION_BROADCAST)).bind(
            cognition_x, routing_key="cognition.#"
        )
        await (await ch.get_queue(Queues.EXECUTION_EVENTS)).bind(
            cognition_x, routing_key="execution.#"
        )
        await (await ch.get_queue(Queues.PIPELINE_STAGES)).bind(
            cognition_x, routing_key="pipeline.#"
        )
        await (await ch.get_queue(Queues.MEMORY_OPERATIONS)).bind(
            cognition_x, routing_key="memory.#"
        )
        await (await ch.get_queue(Queues.REFLECTION_TRIGGERS)).bind(
            cognition_x, routing_key="reflection.#"
        )

        # ── Orchestration direct exchange bindings ─────────────
        orchestration_x = await ch.get_exchange(Exchanges.ORCHESTRATION)

        for qname in (Queues.ORCHESTRATION, Queues.AGENT_TASKS):
            await (await ch.get_queue(qname)).bind(
                orchestration_x, routing_key=qname
            )
        await (await ch.get_queue(Queues.AGENT_RESULTS)).bind(
            orchestration_x, routing_key=Queues.AGENT_RESULTS
        )

        # ── Agents topic exchange bindings ─────────────────────
        agents_x = await ch.get_exchange(Exchanges.AGENTS)

        per_agent = {
            Queues.AGENT_PLANNER:      "agent.planner.#",
            Queues.AGENT_RESEARCHER:   "agent.researcher.#",
            Queues.AGENT_CRITIC:       "agent.critic.#",
            Queues.AGENT_OPTIMIZER:    "agent.optimizer.#",
            Queues.AGENT_ORCHESTRATOR: "agent.orchestrator.#",
        }

        for qname, rk in per_agent.items():
            await (await ch.get_queue(qname)).bind(agents_x, routing_key=rk)

        # ── Events fanout exchange — bind all queues ───────────
        events_x = await ch.get_exchange(Exchanges.EVENTS)

        fanout_queues = [
            Queues.COGNITION_BROADCAST,
            Queues.EXECUTION_EVENTS,
        ]
        for qname in fanout_queues:
            await (await ch.get_queue(qname)).bind(events_x, routing_key="")

        # ── DLX binding ────────────────────────────────────────
        dlx = await ch.get_exchange(Exchanges.DEAD_LETTER)
        await (await ch.get_queue(Queues.DEAD_LETTER)).bind(
            dlx, routing_key=Queues.DEAD_LETTER
        )


# =========================================================
# SINGLETON
# =========================================================

topology = Topology()
