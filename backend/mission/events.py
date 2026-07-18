from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional


MISSION_EVENT_TYPES = {
    "mission.created": "Mission has been created",
    "mission.planned": "Mission plan has been created",
    "mission.risk_analyzed": "Risk analysis completed",
    "mission.awaiting_approval": "Mission is awaiting approval",
    "mission.approved": "Mission has been approved",
    "mission.queued": "Mission has been queued for execution",
    "mission.executing": "Mission execution has started",
    "mission.monitoring": "Mission is being monitored",
    "mission.verifying": "Mission results are being verified",
    "mission.completed": "Mission completed successfully",
    "mission.failed": "Mission has failed",
    "mission.rollback_started": "Rollback has been initiated",
    "mission.rollback_completed": "Rollback completed",
    "mission.cancelled": "Mission has been cancelled",
    "mission.progress": "Mission progress update",
    "mission.retry": "Mission step being retried",
    "mission.approval_requested": "Approval has been requested",
    "mission.approval_granted": "Approval has been granted",
    "mission.approval_rejected": "Approval has been rejected",
    "mission.error": "Mission error occurred",
}


@dataclass
class MissionEvent:
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    mission_id: str = ""
    event_type: str = ""
    correlation_id: str = ""
    from_status: Optional[str] = None
    to_status: Optional[str] = None
    actor: Optional[str] = None
    reason: Optional[str] = None
    payload: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class MissionEventPublisher:
    def __init__(self) -> None:
        self._event_bus = None
        self._events: list[MissionEvent] = []

    async def publish(self, event: MissionEvent) -> None:
        self._events.append(event)
        try:
            from backend.events.event_bus import event_bus
            from backend.events.event_models import CognitionEvent
            await event_bus.publish(CognitionEvent(
                agent="mission_runtime",
                event_type=event.event_type,
                status=event.to_status or event.event_type,
                phase="mission",
                execution_id=event.mission_id,
                message=MISSION_EVENT_TYPES.get(event.event_type, event.event_type),
                payload={
                    "mission_id": event.mission_id,
                    "correlation_id": event.correlation_id,
                    "from_status": event.from_status,
                    "to_status": event.to_status,
                    "actor": event.actor,
                    "reason": event.reason,
                    **(event.payload or {}),
                },
            ))
        except Exception:
            pass

    async def get_events(self, mission_id: str) -> list[MissionEvent]:
        return [e for e in self._events if e.mission_id == mission_id]

    async def get_all_events(self) -> list[MissionEvent]:
        return list(self._events)


mission_event_publisher = MissionEventPublisher()
