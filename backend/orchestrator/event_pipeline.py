from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4

from backend.orchestrator.models import MissionEvent, MissionLifecycleState

log = logging.getLogger(__name__)


class EventPipeline:
    def __init__(self) -> None:
        self._events: Dict[str, List[MissionEvent]] = {}
        self._handlers: Dict[str, List[Callable]] = {}

    def register_handler(self, event_type: str, handler: Callable) -> None:
        self._handlers.setdefault(event_type, []).append(handler)

    def emit(
        self,
        mission_id: str,
        state: MissionLifecycleState,
        event_type: str,
        source: str,
        message: str,
        metadata: Optional[Dict[str, Any]] = None,
        correlation_id: str = "",
    ) -> MissionEvent:
        event = MissionEvent(
            mission_id=mission_id,
            state=state,
            event_type=event_type,
            source=source,
            message=message,
            timestamp=datetime.now(timezone.utc).isoformat(),
            metadata=metadata or {},
            correlation_id=correlation_id or uuid4().hex[:12],
        )
        self._events.setdefault(mission_id, []).append(event)

        for handler in self._handlers.get(event_type, []):
            try:
                handler(event)
            except Exception as exc:
                log.warning("Event handler failed for %s: %s", event_type, exc)

        return event

    def get_events(self, mission_id: str) -> List[MissionEvent]:
        return self._events.get(mission_id, [])

    def get_events_by_type(self, mission_id: str, event_type: str) -> List[MissionEvent]:
        return [e for e in self._events.get(mission_id, []) if e.event_type == event_type]

    def get_events_by_state(self, mission_id: str, state: MissionLifecycleState) -> List[MissionEvent]:
        return [e for e in self._events.get(mission_id, []) if e.state == state]


event_pipeline = EventPipeline()
