import asyncio

from typing import Callable, List

from backend.events.event_models import (
    CognitionEvent
)

from backend.websocket.connection_manager import (
    manager
)

from backend.runtime.runtime_metrics import (
    runtime_metrics
)

from backend.observability.prometheus_metrics import (
    metrics as _prom_metrics
)


# ==========================================
# EVENT BUS
# ==========================================

class EventBus:

    def __init__(self):

        self.events: List[
            CognitionEvent
        ] = []

        self._handlers: List[Callable] = []


    # ==========================================
    # SUBSCRIBE / UNSUBSCRIBE
    # ==========================================

    def subscribe(self, handler: Callable) -> None:
        """Register a handler to be called on every published event."""
        if handler not in self._handlers:
            self._handlers.append(handler)

    def unsubscribe(self, handler: Callable) -> None:
        try:
            self._handlers.remove(handler)
        except ValueError:
            pass


    # ==========================================
    # PUBLISH EVENT
    # ==========================================

    async def publish(

        self,

        event: CognitionEvent

    ):

        # ==========================================
        # STORE EVENT
        # ==========================================

        self.events.append(
            event
        )

        # ==========================================
        # MISSION REPLAY STORE  — dual-layer persistence
        # ==========================================

        try:
            from backend.services.mission_replay_store import replay_store
            asyncio.ensure_future(replay_store.record(event))
        except Exception:
            pass

        # ==========================================
        # METRICS :: EXECUTION START
        # ==========================================

        if event.status == "running":

            runtime_metrics.register_execution_start(

                agent=event.agent
            )

            # Prometheus: agent execution counter
            try:
                _prom_metrics.agent_executions.labels(
                    agent=event.agent, event_type=event.event_type or "execution"
                ).inc()
                _prom_metrics.active_agents.inc()
            except Exception:
                pass

        # ==========================================
        # METRICS :: COMPLETED
        # ==========================================

        if event.status == "completed":

            runtime_metrics.register_execution_completed(

                latency_ms=(
                    event.latency_ms or 0
                )
            )

            # Prometheus: agent completion
            try:
                _prom_metrics.active_agents.dec()
            except Exception:
                pass

        # ==========================================
        # METRICS :: FAILED
        # ==========================================

        if event.status == "failed":

            runtime_metrics.register_execution_failed()

            # Prometheus: agent failure
            try:
                _prom_metrics.agent_failures.labels(
                    agent=event.agent, error_type="execution_failed"
                ).inc()
                _prom_metrics.active_agents.dec()
            except Exception:
                pass

        # ==========================================
        # METRICS :: TOKEN USAGE
        # ==========================================

        if event.token_usage:

            runtime_metrics.register_token_usage(

                prompt_tokens=(
                    event.token_usage.get(
                        "prompt_tokens",
                        0
                    )
                ),

                completion_tokens=(
                    event.token_usage.get(
                        "completion_tokens",
                        0
                    )
                )
            )

        # ==========================================
        # METRICS :: GOVERNANCE
        # ==========================================

        if event.payload:

            hallucination_score = (

                event.payload.get(
                    "hallucination_score"
                )
            )

            confidence_score = (

                event.payload.get(
                    "confidence_score"
                )
            )

            if (

                hallucination_score
                is not None

                and

                confidence_score
                is not None
            ):

                runtime_metrics.register_governance_scores(

                    hallucination_score=
                        hallucination_score,

                    confidence_score=
                        confidence_score
                )

        # ==========================================
        # DISPATCH TO SUBSCRIBERS
        # ==========================================

        for handler in list(self._handlers):
            try:
                result = handler(event)
                if asyncio.iscoroutine(result):
                    asyncio.ensure_future(result)
            except Exception:
                pass

        # ==========================================
        # STREAM EVENT — session-aware routing
        # ==========================================
        # If the event carries a session_id, route only to that session's
        # connections.  Otherwise fall back to global broadcast (cognition
        # events, system events that all clients should see).

        event_dict = event.model_dump()
        session_id: str | None = event_dict.get("session_id") or getattr(event, "session_id", None)

        try:
            from backend.websocket.connection_pool import connection_pool

            if session_id and session_id != "global":
                # Targeted — only the originating client receives this event
                sent = await connection_pool.broadcast_to_session(session_id, event_dict)
                if sent == 0:
                    # No live connection for this session — also broadcast globally
                    # so the event is not silently lost (e.g. during reconnect)
                    await manager.broadcast(event_dict)
            else:
                # Global cognition events (agent activity, system health, etc.)
                await connection_pool.broadcast(event_dict)

        except Exception:
            # Degrade gracefully to legacy manager
            await manager.broadcast(event_dict)

        # ==========================================
        # STREAM METRICS  (always broadcast to all — observability data)
        # ==========================================

        metrics_payload = {
            "agent":      "runtime",
            "event_type": "runtime_metrics",
            "status":     "active",
            "message":    "Runtime metrics updated",
            "timestamp":  event.timestamp,
            "payload":    runtime_metrics.export_metrics(),
        }

        try:
            from backend.websocket.connection_pool import connection_pool
            await connection_pool.broadcast(metrics_payload)
        except Exception:
            await manager.broadcast(metrics_payload)


    # ==========================================
    # GET EVENTS
    # ==========================================

    def get_events(self):

        return [

            event.model_dump()

            for event in self.events
        ]


# ==========================================
# SINGLETON
# ==========================================

event_bus = EventBus()