from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from backend.governance.models import GOVERNANCE_EVENT_TYPES


@dataclass
class GovernanceEvent:
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = ""
    decision: str = ""
    reason_code: str = ""
    requester: str = ""
    resource_type: str = ""
    resource_id: str = ""
    action: str = ""
    mission_id: Optional[str] = None
    execution_id: Optional[str] = None
    approval_request_id: Optional[str] = None
    message: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class GovernanceEventPublisher:
    def __init__(self) -> None:
        self._events: list[GovernanceEvent] = []

    async def publish(self, event: GovernanceEvent) -> None:
        self._events.append(event)
        try:
            from backend.events.event_bus import event_bus
            from backend.events.event_models import CognitionEvent
            await event_bus.publish(CognitionEvent(
                agent="governance_runtime",
                event_type=event.event_type,
                status=event.decision or event.event_type,
                phase="governance",
                execution_id=event.execution_id or "",
                message=event.message or GOVERNANCE_EVENT_TYPES.get(event.event_type, event.event_type),
                payload={
                    "governance_event_type": event.event_type,
                    "decision": event.decision,
                    "reason_code": event.reason_code,
                    "requester": event.requester,
                    "resource_type": event.resource_type,
                    "resource_id": event.resource_id,
                    "action": event.action,
                    "mission_id": event.mission_id,
                    "execution_id": event.execution_id,
                    "approval_request_id": event.approval_request_id,
                    **(event.payload or {}),
                },
            ))
        except Exception:
            pass

    async def get_events(self, mission_id: str) -> list[GovernanceEvent]:
        return [e for e in self._events if e.mission_id == mission_id]

    async def get_all_events(self) -> list[GovernanceEvent]:
        return list(self._events)


governance_event_publisher = GovernanceEventPublisher()
