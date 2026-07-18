from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from backend.ai.models import IntentType, RuntimeTarget

log = logging.getLogger(__name__)


@dataclass
class AIEvent:
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = ""
    request_id: str = ""
    plan_id: Optional[str] = None
    step_id: Optional[str] = None
    correlation_id: str = ""
    intent: Optional[str] = None
    runtime: Optional[str] = None
    message: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class AIEventPublisher:
    AI_REQUESTED = "ai.requested"
    AI_PLANNED = "ai.planned"
    AI_RUNTIME_SELECTED = "ai.runtime_selected"
    AI_COMPLETED = "ai.completed"
    AI_FAILED = "ai.failed"
    AI_CANCELLED = "ai.cancelled"
    AI_REASONING_GENERATED = "ai.reasoning.generated"

    def __init__(self) -> None:
        self._events: list[AIEvent] = []

    async def publish(self, event: AIEvent) -> None:
        self._events.append(event)
        try:
            from backend.events.event_bus import event_bus
            from backend.events.event_models import CognitionEvent
            await event_bus.publish(CognitionEvent(
                agent="ai_runtime",
                event_type=event.event_type,
                status="completed" if event.event_type in (self.AI_COMPLETED,) else "active",
                message=event.message,
                execution_id=None,
                data={
                    "event_id": event.event_id,
                    "request_id": event.request_id,
                    "plan_id": event.plan_id,
                    "step_id": event.step_id,
                    "correlation_id": event.correlation_id,
                    "intent": event.intent,
                    "runtime": event.runtime,
                    "payload": event.payload,
                    "timestamp": event.timestamp,
                },
            ))
        except Exception as exc:
            log.warning("AI event publish failed: %s", exc)

    async def publish_requested(self, request_id: str, intent: IntentType, prompt: str) -> None:
        await self.publish(AIEvent(
            event_type=self.AI_REQUESTED,
            request_id=request_id,
            intent=intent.value,
            message=f"AI request received: intent={intent.value}",
            payload={"prompt": prompt[:200]},
        ))

    async def publish_planned(self, request_id: str, plan_id: str, step_count: int) -> None:
        await self.publish(AIEvent(
            event_type=self.AI_PLANNED,
            request_id=request_id,
            plan_id=plan_id,
            message=f"AI execution plan created with {step_count} steps",
            payload={"plan_id": plan_id, "step_count": step_count},
        ))

    async def publish_runtime_selected(self, request_id: str, runtime: RuntimeTarget, reason: str) -> None:
        await self.publish(AIEvent(
            event_type=self.AI_RUNTIME_SELECTED,
            request_id=request_id,
            runtime=runtime.value,
            message=f"Runtime selected: {runtime.value}",
            payload={"runtime": runtime.value, "reason": reason},
        ))

    async def publish_completed(self, request_id: str, summary: str) -> None:
        await self.publish(AIEvent(
            event_type=self.AI_COMPLETED,
            request_id=request_id,
            message=summary,
        ))

    async def publish_failed(self, request_id: str, error: str) -> None:
        await self.publish(AIEvent(
            event_type=self.AI_FAILED,
            request_id=request_id,
            message=f"AI request failed: {error}",
            payload={"error": error},
        ))

    async def publish_cancelled(self, request_id: str, reason: str) -> None:
        await self.publish(AIEvent(
            event_type=self.AI_CANCELLED,
            request_id=request_id,
            message=f"AI request cancelled: {reason}",
            payload={"reason": reason},
        ))

    async def publish_reasoning(self, request_id: str, step_label: str, detail: str) -> None:
        await self.publish(AIEvent(
            event_type=self.AI_REASONING_GENERATED,
            request_id=request_id,
            message=f"Reasoning step: {step_label}",
            payload={"label": step_label, "detail": detail},
        ))

    def get_events(self, request_id: Optional[str] = None, limit: int = 100) -> list[AIEvent]:
        result = self._events
        if request_id:
            result = [e for e in result if e.request_id == request_id]
        return result[-limit:]


ai_event_publisher = AIEventPublisher()
