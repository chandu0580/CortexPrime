from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from backend.execution.models import ExecutionStatus


EXECUTION_EVENT_TYPES: dict[str, str] = {
    "execution.created": "Execution has been created",
    "execution.queued": "Execution has been queued",
    "execution.started": "Execution has started",
    "execution.paused": "Execution has been paused",
    "execution.progress": "Execution progress update",
    "execution.completed": "Execution completed successfully",
    "execution.failed": "Execution has failed",
    "execution.cancelled": "Execution has been cancelled",
    "execution.timed_out": "Execution has timed out",
    "execution.retried": "Execution is being retried",
    "execution.retrying": "Execution retry attempt",
    "execution.log": "Execution log entry",
}


@dataclass
class ExecutionEvent:
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    execution_id: str = ""
    event_type: str = ""
    correlation_id: str = ""
    from_status: Optional[str] = None
    to_status: Optional[str] = None
    actor: Optional[str] = None
    message: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class ExecutionEventPublisher:
    def __init__(self) -> None:
        self._events: list[ExecutionEvent] = []

    async def publish(self, event: ExecutionEvent) -> None:
        self._events.append(event)
        try:
            from backend.events.event_bus import event_bus
            from backend.events.event_models import CognitionEvent
            await event_bus.publish(CognitionEvent(
                agent="execution_runtime",
                event_type=event.event_type,
                status=event.to_status or event.event_type,
                phase="execution",
                execution_id=event.execution_id,
                message=event.message or EXECUTION_EVENT_TYPES.get(event.event_type, event.event_type),
                payload={
                    "execution_id": event.execution_id,
                    "correlation_id": event.correlation_id,
                    "from_status": event.from_status,
                    "to_status": event.to_status,
                    "actor": event.actor,
                    **(event.payload or {}),
                },
            ))
        except Exception:
            pass

    async def get_events(self, execution_id: str) -> list[ExecutionEvent]:
        return [e for e in self._events if e.execution_id == execution_id]

    async def get_all_events(self) -> list[ExecutionEvent]:
        return list(self._events)


execution_event_publisher = ExecutionEventPublisher()
