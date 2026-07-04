"""
Orchestration Bus
-----------------
High-level facade for the entire CortexPrime message bus.

The ``OrchestrationBus`` coordinates:
  * Mission lifecycle   — start, complete, fail
  * Agent-to-agent      — task dispatch, direct messages, result collection
  * Cognition pipeline  — stage events, broadcast
  * Memory operations   — async store triggers
  * Reflection          — trigger and complete
  * Result aggregation  — ``collect_results()`` waits for N agent results
    with a configurable timeout

Architecture
~~~~~~~~~~~~
Every method is a convenience thin-wrapper over ``rabbitmq_publisher``
and ``rabbitmq_consumer``.  The bus also registers a set of default
internal handlers on startup so cross-cutting concerns (Redis state sync,
WebSocket forwarding) are always active.

Singletons used
~~~~~~~~~~~~~~~
  rabbitmq_publisher  — message publishing
  rabbitmq_consumer   — handler registration
  runtime_state       — Redis state updates (optional)
  event_bus           — in-process WebSocket broadcast (optional)

Usage
~~~~~
    await orchestration_bus.start_mission(execution_id, "Build a web scraper")
    await orchestration_bus.dispatch_to_agent("planner", execution_id, task={...})
    results = await orchestration_bus.collect_results(execution_id, expected=3, timeout=60)
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4

log = logging.getLogger(__name__)

from backend.infrastructure.rabbitmq.publisher import rabbitmq_publisher
from backend.infrastructure.rabbitmq.consumer  import rabbitmq_consumer
from backend.infrastructure.rabbitmq.schemas   import (
    MessageType,
    Queues,
    RabbitMessage,
)


# =========================================================
# RESULT COLLECTOR
# =========================================================

class ResultCollector:
    """
    Collects async agent results for a specific execution.

    ``wait(expected, timeout)`` returns when all expected results
    arrive or the timeout fires, whichever comes first.
    """

    def __init__(self, execution_id: str) -> None:
        self.execution_id = execution_id
        self._results:    List[Dict[str, Any]] = []
        self._event:      asyncio.Event = asyncio.Event()
        self._expected:   int = 0

    def push(self, result: Dict[str, Any]) -> None:
        self._results.append(result)
        if len(self._results) >= self._expected:
            self._event.set()

    async def wait(self, expected: int, timeout: float = 60.0) -> List[Dict[str, Any]]:
        self._expected = expected
        if self._results and len(self._results) >= expected:
            return self._results
        try:
            await asyncio.wait_for(self._event.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            log.warning(
                "collect_results timeout: exec=%s got %d/%d",
                self.execution_id, len(self._results), expected,
            )
        return self._results


# =========================================================
# ORCHESTRATION BUS
# =========================================================

class OrchestrationBus:
    """
    Unified async orchestration bus.

    All public methods return ``bool`` or ``List`` and never raise —
    failures are logged and the runtime continues in degraded mode.
    """

    def __init__(self) -> None:
        self._collectors: Dict[str, ResultCollector] = {}
        self._started = False

    # ---------------------------------------------------------
    # STARTUP / SHUTDOWN
    # ---------------------------------------------------------

    async def start(self) -> None:
        """
        Register internal consumers and attach to queues.

        Called once from ``backend/main.py`` lifespan startup.
        """
        if self._started:
            return

        # Register internal handlers
        rabbitmq_consumer.on(
            MessageType.AGENT_TASK_RESULT,
            self._handle_agent_result,
        )
        rabbitmq_consumer.on(
            MessageType.EXECUTION_EVENT,
            self._handle_execution_event,
        )
        rabbitmq_consumer.on(
            MessageType.MISSION_COMPLETE,
            self._handle_mission_complete,
        )
        rabbitmq_consumer.on(
            MessageType.MISSION_FAILED,
            self._handle_mission_failed,
        )
        rabbitmq_consumer.on(
            MessageType.MEMORY_STORE,
            self._handle_memory_store,
        )
        rabbitmq_consumer.on(
            MessageType.PIPELINE_STAGE_DONE,
            self._handle_pipeline_stage_done,
        )

        await rabbitmq_consumer.start()
        self._started = True
        log.info("✅ OrchestrationBus started")

    async def stop(self) -> None:
        await rabbitmq_consumer.stop()
        self._started = False
        log.info("OrchestrationBus stopped")

    # ---------------------------------------------------------
    # MISSION LIFECYCLE
    # ---------------------------------------------------------

    async def start_mission(
        self,
        execution_id: str,
        objective:    str,
        agents:       List[str] = [],
        priority:     int = 5,
        mission_id:   Optional[str] = None,
    ) -> bool:
        """
        Publish a MISSION_START message to kick off a new execution.

        Also emits an EXECUTION_STARTED event to the events fanout exchange
        so all WebSocket clients receive the update immediately.
        """
        ok = await rabbitmq_publisher.dispatch_mission(
            execution_id = execution_id,
            objective    = objective,
            agents       = agents,
            priority     = priority,
            mission_id   = mission_id,
        )

        # Forward to Redis runtime state (fire-and-forget)
        asyncio.ensure_future(self._sync_execution_start(execution_id, objective))

        return ok

    async def complete_mission(
        self,
        execution_id: str,
        result:       Dict[str, Any],
        mission_id:   Optional[str] = None,
    ) -> bool:
        return await rabbitmq_publisher.publish_mission_complete(
            execution_id = execution_id,
            result       = result,
            mission_id   = mission_id,
        )

    async def fail_mission(
        self,
        execution_id: str,
        error:        str,
        stage:        str = "",
        mission_id:   Optional[str] = None,
    ) -> bool:
        return await rabbitmq_publisher.publish_mission_failed(
            execution_id = execution_id,
            error        = error,
            stage        = stage,
            mission_id   = mission_id,
        )

    # ---------------------------------------------------------
    # AGENT DISPATCH
    # ---------------------------------------------------------

    async def dispatch_to_agent(
        self,
        agent_name:   str,
        execution_id: str,
        task:         Dict[str, Any],
        priority:     int = 5,
        parent_msg:   Optional[RabbitMessage] = None,
    ) -> bool:
        """Route a task to a specific agent's dedicated queue."""
        return await rabbitmq_publisher.dispatch_agent_task(
            execution_id = execution_id,
            agent_name   = agent_name,
            task         = task,
            priority     = priority,
            parent_msg   = parent_msg,
        )

    async def agent_to_agent(
        self,
        from_agent:   str,
        to_agent:     str,
        execution_id: str,
        content:      Dict[str, Any],
        parent_msg:   Optional[RabbitMessage] = None,
    ) -> bool:
        """
        Direct agent-to-agent message.

        Routed via the agents topic exchange with key
        ``agent.{to_agent}.task``.
        """
        return await rabbitmq_publisher.send_agent_to_agent(
            execution_id = execution_id,
            from_agent   = from_agent,
            to_agent     = to_agent,
            content      = content,
            parent_msg   = parent_msg,
        )

    async def publish_result(
        self,
        agent_name:   str,
        execution_id: str,
        result:       Dict[str, Any],
        parent_msg:   Optional[RabbitMessage] = None,
    ) -> bool:
        """Publish an agent result to the results queue."""
        return await rabbitmq_publisher.publish_agent_result(
            execution_id = execution_id,
            agent_name   = agent_name,
            result       = result,
            parent_msg   = parent_msg,
        )

    # ---------------------------------------------------------
    # RESULT AGGREGATION
    # ---------------------------------------------------------

    async def collect_results(
        self,
        execution_id: str,
        expected:     int,
        timeout:      float = 60.0,
    ) -> List[Dict[str, Any]]:
        """
        Wait until ``expected`` agent results arrive for the given
        execution, or until ``timeout`` seconds have passed.
        """
        collector = self._collectors.setdefault(
            execution_id, ResultCollector(execution_id)
        )
        results = await collector.wait(expected=expected, timeout=timeout)
        # Clean up once all results collected
        if len(results) >= expected:
            self._collectors.pop(execution_id, None)
        return results

    # ---------------------------------------------------------
    # COGNITION EVENTS
    # ---------------------------------------------------------

    async def emit_cognition(
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
        """
        Publish a cognition event to the topic exchange and also push
        to the Redis cognition stream (fire-and-forget).
        """
        ok = await rabbitmq_publisher.emit_cognition_event(
            execution_id = execution_id,
            agent        = agent,
            event_type   = event_type,
            status       = status,
            message      = message,
            phase        = phase,
            payload      = payload,
            parent_msg   = parent_msg,
        )

        asyncio.ensure_future(self._cache_cognition_event(
            execution_id, agent, event_type, status, message, phase, payload,
        ))

        return ok

    async def broadcast_runtime_event(
        self,
        event_type: str,
        payload:    Dict[str, Any],
    ) -> bool:
        """
        Fanout broadcast to all subscribers on the events exchange.
        Used for system-wide notifications (e.g. health events).
        """
        from backend.infrastructure.rabbitmq.schemas import RabbitMessage, MessageType
        msg = RabbitMessage(
            message_type = MessageType.RUNTIME_BROADCAST,
            payload      = {"event_type": event_type, **payload},
        )
        return await rabbitmq_publisher.broadcast(msg)

    # ---------------------------------------------------------
    # PIPELINE STAGES
    # ---------------------------------------------------------

    async def stage_started(
        self,
        execution_id: str,
        stage:        str,
        agent:        str,
        task:         Dict[str, Any] = {},
        parent_msg:   Optional[RabbitMessage] = None,
    ) -> bool:
        return await rabbitmq_publisher.publish_stage_start(
            execution_id = execution_id,
            stage        = stage,
            agent        = agent,
            task         = task,
            parent_msg   = parent_msg,
        )

    async def stage_completed(
        self,
        execution_id: str,
        stage:        str,
        agent:        str,
        output:       Dict[str, Any] = {},
        duration_ms:  Optional[float] = None,
        parent_msg:   Optional[RabbitMessage] = None,
    ) -> bool:
        return await rabbitmq_publisher.publish_stage_done(
            execution_id = execution_id,
            stage        = stage,
            agent        = agent,
            output       = output,
            duration_ms  = duration_ms,
            parent_msg   = parent_msg,
        )

    # ---------------------------------------------------------
    # MEMORY
    # ---------------------------------------------------------

    async def store_memory(
        self,
        execution_id: str,
        agent:        str,
        memory_type:  str,
        content:      str,
        metadata:     Dict[str, Any] = {},
    ) -> bool:
        return await rabbitmq_publisher.publish_memory_store(
            execution_id = execution_id,
            agent        = agent,
            memory_type  = memory_type,
            content      = content,
            metadata     = metadata,
        )

    # ---------------------------------------------------------
    # REFLECTION
    # ---------------------------------------------------------

    async def trigger_reflection(
        self,
        execution_id: str,
        agent:        str,
        context:      Dict[str, Any],
        mission_id:   Optional[str] = None,
    ) -> bool:
        return await rabbitmq_publisher.trigger_reflection(
            execution_id = execution_id,
            agent        = agent,
            context      = context,
            mission_id   = mission_id,
        )

    # ---------------------------------------------------------
    # CUSTOM HANDLER REGISTRATION
    # ---------------------------------------------------------

    def register_handler(
        self,
        message_type: MessageType,
        handler:      Callable,
        traced:       bool = True,
    ) -> None:
        """
        Register a custom handler for a message type.
        Must be called before ``start()``.
        """
        rabbitmq_consumer.on(message_type, handler, traced=traced)

    # ---------------------------------------------------------
    # INTERNAL HANDLERS
    # ---------------------------------------------------------

    async def _handle_agent_result(self, msg: RabbitMessage) -> None:
        """Route incoming agent results to the appropriate ResultCollector."""
        if msg.execution_id:
            collector = self._collectors.get(msg.execution_id)
            if collector:
                collector.push(msg.payload)

        # Also sync to Redis
        asyncio.ensure_future(self._sync_agent_result(msg))

    async def _handle_execution_event(self, msg: RabbitMessage) -> None:
        """Forward execution events to in-process EventBus → WebSocket."""
        asyncio.ensure_future(self._forward_to_event_bus(msg))

    async def _handle_mission_complete(self, msg: RabbitMessage) -> None:
        log.info(
            "Mission complete: exec=%s mission=%s",
            msg.execution_id, msg.mission_id,
        )
        asyncio.ensure_future(self._sync_execution_state(
            msg.execution_id, "completed", msg.payload,
        ))

    async def _handle_mission_failed(self, msg: RabbitMessage) -> None:
        log.warning(
            "Mission failed: exec=%s error=%s",
            msg.execution_id, msg.payload.get("error"),
        )
        asyncio.ensure_future(self._sync_execution_state(
            msg.execution_id, "failed", msg.payload,
        ))

    async def _handle_memory_store(self, msg: RabbitMessage) -> None:
        """Async memory persistence triggered by a MEMORY_STORE message."""
        # Memory persistence is handled by the memory subsystem;
        # this handler just logs for observability.
        log.debug(
            "Memory store: exec=%s agent=%s type=%s",
            msg.execution_id,
            msg.payload.get("agent"),
            msg.payload.get("memory_type"),
        )

    async def _handle_pipeline_stage_done(self, msg: RabbitMessage) -> None:
        asyncio.ensure_future(self._forward_to_event_bus(msg))

    # ---------------------------------------------------------
    # REDIS SYNC HELPERS  (fire-and-forget)
    # ---------------------------------------------------------

    async def _sync_execution_start(
        self, execution_id: str, objective: str
    ) -> None:
        try:
            from backend.infrastructure.redis.runtime_state_manager import runtime_state
            await runtime_state.set_execution_state(execution_id, {
                "status":    "running",
                "objective": objective,
                "started_at": datetime.now(timezone.utc).isoformat(),
            })
        except Exception as exc:
            log.debug("Redis sync execution start: %s", exc)

    async def _sync_execution_state(
        self, execution_id: Optional[str], status: str, payload: Dict[str, Any]
    ) -> None:
        if not execution_id:
            return
        try:
            from backend.infrastructure.redis.runtime_state_manager import runtime_state
            if status in ("completed", "failed"):
                await runtime_state.delete_execution_state(execution_id)
            else:
                await runtime_state.set_execution_state(execution_id, {
                    "status": status, **payload,
                })
        except Exception as exc:
            log.debug("Redis sync execution state: %s", exc)

    async def _cache_cognition_event(
        self,
        execution_id: str,
        agent:        str,
        event_type:   str,
        status:       str,
        message:      str,
        phase:        str,
        payload:      Dict[str, Any],
    ) -> None:
        try:
            from backend.infrastructure.redis.runtime_state_manager import runtime_state
            await runtime_state.record_cognition_event(
                execution_id = execution_id,
                agent        = agent,
                event_type   = event_type,
                message      = message,
                phase        = phase,
                payload      = payload,
            )
        except Exception as exc:
            log.debug("Redis cognition cache: %s", exc)

    async def _sync_agent_result(self, msg: RabbitMessage) -> None:
        try:
            from backend.infrastructure.redis.runtime_state_manager import runtime_state
            await runtime_state.update_agent_status(
                agent    = msg.payload.get("agent_name", "unknown"),
                status   = "idle",
                metadata = {"last_result_exec": msg.execution_id},
            )
        except Exception as exc:
            log.debug("Redis agent result sync: %s", exc)

    async def _forward_to_event_bus(self, msg: RabbitMessage) -> None:
        """Re-emit to the in-process EventBus so WebSocket clients receive it."""
        try:
            from backend.events.event_bus    import event_bus
            from backend.events.event_models import CognitionEvent
            p = msg.payload
            await event_bus.publish(CognitionEvent(
                agent        = p.get("agent",      "system"),
                event_type   = p.get("event_type", msg.message_type.value),
                status       = p.get("status",     "info"),
                message      = p.get("message",    ""),
                execution_id = msg.execution_id,
                phase        = p.get("phase",      ""),
                payload      = p.get("data",       {}),
            ))
        except Exception as exc:
            log.debug("EventBus forward: %s", exc)


# =========================================================
# SINGLETON
# =========================================================

orchestration_bus = OrchestrationBus()
