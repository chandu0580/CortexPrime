from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

log = logging.getLogger(__name__)


@dataclass
class KnowledgeEvent:
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = ""
    knowledge_id: str = ""
    title: str = ""
    category: str = ""
    source: str = ""
    relationship_type: Optional[str] = None
    source_id: Optional[str] = None
    target_id: Optional[str] = None
    message: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class KnowledgeEventPublisher:
    def __init__(self) -> None:
        self._events: list[KnowledgeEvent] = []

    async def publish(self, event: KnowledgeEvent) -> None:
        self._events.append(event)
        try:
            from backend.events.event_bus import event_bus
            from backend.events.event_models import CognitionEvent
            await event_bus.publish(CognitionEvent(
                event_type=event.event_type,
                data={
                    "event_id": event.event_id,
                    "knowledge_id": event.knowledge_id,
                    "title": event.title,
                    "category": event.category,
                    "source": event.source,
                    "relationship_type": event.relationship_type,
                    "source_id": event.source_id,
                    "target_id": event.target_id,
                    "message": event.message,
                    "payload": event.payload,
                    "timestamp": event.timestamp.isoformat(),
                },
            ))
        except Exception as exc:
            log.warning("Knowledge event publish failed: %s", exc)

    def get_events(
        self,
        knowledge_id: Optional[str] = None,
        event_type: Optional[str] = None,
        limit: int = 100,
    ) -> list[KnowledgeEvent]:
        result = self._events
        if knowledge_id:
            result = [e for e in result if e.knowledge_id == knowledge_id]
        if event_type:
            result = [e for e in result if e.event_type == event_type]
        return result[-limit:]

    def get_all_events(self) -> list[KnowledgeEvent]:
        return list(self._events)


knowledge_event_publisher = KnowledgeEventPublisher()
