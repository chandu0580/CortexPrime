from __future__ import annotations

import logging
from typing import Any, Optional

from backend.ai.client import RuntimeInvocationClient
from backend.ai.context import ContextPropagator
from backend.ai.correlation import correlation_events
from backend.ai.events import AIEventPublisher, ai_event_publisher
from backend.ai.failure import FailureHandler
from backend.ai.invoker import RuntimeInvoker
from backend.ai.models import (
    AIContext,
    AIExecutionPlan,
    AIReasoningTrace,
    AIRequest,
    AIResponse,
    AIRequestStatus,
    IntentType,
    PlanStep,
    RuntimeTarget,
)
from backend.ai.orchestrator import AIOrchestrator
from backend.ai.router import RuntimeRouter

log = logging.getLogger(__name__)


class AIService:
    def __init__(
        self,
        orchestrator: Optional[AIOrchestrator] = None,
        events: Optional[AIEventPublisher] = None,
        propagator: Optional[ContextPropagator] = None,
        client: Optional[RuntimeInvocationClient] = None,
        failure_handler: Optional[FailureHandler] = None,
    ) -> None:
        self._propagator = propagator or ContextPropagator()
        self._failure_handler = failure_handler or FailureHandler()
        self._client = client or RuntimeInvocationClient(
            failure_handler=self._failure_handler,
            correlator=correlation_events,
            propagator=self._propagator,
        )
        self._events = events or ai_event_publisher
        self._orchestrator = orchestrator or AIOrchestrator(
            events=self._events,
            propagator=self._propagator,
            client=self._client,
            failure_handler=self._failure_handler,
        )

    async def process_request(
        self,
        prompt: str,
        context: Optional[AIContext] = None,
    ) -> AIResponse:
        return await self._orchestrator.handle_request(prompt, context)

    async def process_plan(
        self,
        plan: AIExecutionPlan,
        context: Optional[AIContext] = None,
    ) -> AIResponse:
        return await self._orchestrator.process_plan(plan, context)

    async def get_runtime_map(self) -> list[dict[str, Any]]:
        routes = RuntimeRouter.ROUTING_TABLE
        result: list[dict[str, Any]] = []
        for intent, runtime_routes in routes.items():
            entry = {
                "intent": intent.value,
                "runtimes": [
                    {"name": r.runtime.value, "priority": r.priority, "reason": r.reason}
                    for r in runtime_routes
                ],
            }
            result.append(entry)
        return result

    async def get_reasoning_trace(self, request_id: str) -> Optional[AIReasoningTrace]:
        events = self._events.get_events(request_id=request_id)
        if not events:
            return None
        trace = AIReasoningTrace(request_id=request_id)
        for event in events:
            trace.add_step(
                label=event.event_type,
                detail=event.message,
                data=event.payload,
            )
        return trace

    async def get_correlation_timeline(self, correlation_id: str) -> list[dict[str, Any]]:
        events = correlation_events.get_timeline(correlation_id)
        return [
            {
                "event_id": e.event_id,
                "correlation_id": e.correlation_id,
                "source_runtime": e.source_runtime,
                "event_type": e.event_type,
                "status": e.status,
                "message": e.message,
                "timestamp": e.timestamp,
            }
            for e in events
        ]

    async def cancel_request(self, request_id: str) -> bool:
        try:
            log.info("Cancellation requested for request %s", request_id)
            await self._events.publish_cancelled(request_id, "Cancelled by user")
            return True
        except Exception as exc:
            log.warning("Failed to cancel request %s: %s", request_id, exc)
            return False

    async def health(self) -> dict[str, Any]:
        return {
            "status": "healthy",
            "service": "ai_runtime",
            "intents_supported": [i.value for i in IntentType],
            "runtimes_available": [r.value for r in RuntimeTarget],
            "integration_layer": "active",
        }
