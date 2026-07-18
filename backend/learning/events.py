from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

log = logging.getLogger(__name__)


@dataclass
class LearningEvent:
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = ""
    session_id: str = ""
    pattern_id: Optional[str] = None
    pattern_name: Optional[str] = None
    category: Optional[str] = None
    recommendation_id: Optional[str] = None
    message: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class LearningEventPublisher:
    def __init__(self) -> None:
        self._events: list[LearningEvent] = []

    async def publish(self, event: LearningEvent) -> None:
        self._events.append(event)
        try:
            from backend.events.event_bus import event_bus
            from backend.events.event_models import CognitionEvent
            await event_bus.publish(CognitionEvent(
                event_type=event.event_type,
                data={
                    "event_id": event.event_id,
                    "session_id": event.session_id,
                    "pattern_id": event.pattern_id,
                    "pattern_name": event.pattern_name,
                    "category": event.category,
                    "recommendation_id": event.recommendation_id,
                    "message": event.message,
                    "payload": event.payload,
                    "timestamp": event.timestamp.isoformat(),
                },
            ))
        except Exception as exc:
            log.warning("Learning event publish failed: %s", exc)

    def get_events(self, session_id: Optional[str] = None, limit: int = 100) -> list[LearningEvent]:
        result = self._events
        if session_id:
            result = [e for e in result if e.session_id == session_id]
        return result[-limit:]

    def get_all_events(self) -> list[LearningEvent]:
        return list(self._events)


learning_event_publisher = LearningEventPublisher()
