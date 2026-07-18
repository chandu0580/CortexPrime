from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from backend.ai.models import RuntimeTarget

log = logging.getLogger(__name__)


@dataclass
class CorrelationEvent:
    event_id: str = ""
    correlation_id: str = ""
    source_runtime: str = ""
    event_type: str = ""
    status: str = ""
    message: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class EventCorrelator:
    def __init__(self) -> None:
        self._events: list[CorrelationEvent] = []

    async def record(
        self,
        correlation_id: str,
        source_runtime: str,
        event_type: str,
        status: str = "info",
        message: str = "",
        payload: Optional[dict[str, Any]] = None,
    ) -> CorrelationEvent:
        event = CorrelationEvent(
            event_id=_generate_id("evt"),
            correlation_id=correlation_id,
            source_runtime=source_runtime,
            event_type=event_type,
            status=status,
            message=message,
            payload=payload or {},
        )
        self._events.append(event)
        await self._publish_to_event_bus(event)
        return event

    def get_by_correlation(self, correlation_id: str) -> list[CorrelationEvent]:
        return [e for e in self._events if e.correlation_id == correlation_id]

    def get_by_runtime(self, runtime: RuntimeTarget) -> list[CorrelationEvent]:
        return [e for e in self._events if e.source_runtime == runtime.value]

    def get_timeline(self, correlation_id: str) -> list[CorrelationEvent]:
        events = self.get_by_correlation(correlation_id)
        events.sort(key=lambda e: e.timestamp)
        return events

    def get_events(self, correlation_id: Optional[str] = None, limit: int = 100) -> list[CorrelationEvent]:
        result = self._events
        if correlation_id:
            result = self.get_by_correlation(correlation_id)
        return result[-limit:]

    async def _publish_to_event_bus(self, event: CorrelationEvent) -> None:
        try:
            from backend.events.event_bus import event_bus
            from backend.events.event_models import CognitionEvent
            await event_bus.publish(CognitionEvent(
                agent="ai_runtime",
                event_type=f"correlation.{event.event_type}",
                status=event.status,
                message=event.message,
                execution_id=None,
                data={
                    "correlation_id": event.correlation_id,
                    "source_runtime": event.source_runtime,
                    "event_type": event.event_type,
                    "payload": event.payload,
                    "timestamp": event.timestamp,
                },
            ))
        except Exception as exc:
            log.warning("Failed to publish correlation event: %s", exc)


correlation_events = EventCorrelator()


def _generate_id(prefix: str = "id") -> str:
    import uuid
    return f"{prefix}-{uuid.uuid4().hex[:12]}"
