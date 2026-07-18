from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

CONNECTOR_EVENT_TYPES: dict[str, str] = {
    "connector.registered": "Connector has been registered",
    "connector.ready": "Connector is ready",
    "connector.failed": "Connector has failed",
    "connector.disabled": "Connector has been disabled",
    "connector.enabled": "Connector has been enabled",
    "connector.updated": "Connector configuration updated",
    "connector.degraded": "Connector is in degraded state",
    "connector.removed": "Connector has been removed",
    "connector.capability_executing": "Connector capability execution started",
    "connector.capability_executed": "Connector capability execution completed",
}


@dataclass
class ConnectorEvent:
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    connector_type: str = ""
    connector_name: str = ""
    event_type: str = ""
    correlation_id: str = ""
    from_status: Optional[str] = None
    to_status: Optional[str] = None
    actor: Optional[str] = None
    message: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class ConnectorEventPublisher:
    def __init__(self) -> None:
        self._events: list[ConnectorEvent] = []

    async def publish(self, event: ConnectorEvent) -> None:
        self._events.append(event)
        try:
            from backend.events.event_bus import event_bus
            from backend.events.event_models import CognitionEvent
            await event_bus.publish(CognitionEvent(
                agent=f"connector_runtime:{event.connector_type}",
                event_type=event.event_type,
                status=event.to_status or event.event_type,
                phase="connector",
                execution_id=event.connector_type,
                message=event.message or CONNECTOR_EVENT_TYPES.get(event.event_type, event.event_type),
                payload={
                    "connector_type": event.connector_type,
                    "connector_name": event.connector_name,
                    "correlation_id": event.correlation_id,
                    "from_status": event.from_status,
                    "to_status": event.to_status,
                    "actor": event.actor,
                    **(event.payload or {}),
                },
            ))
        except Exception:
            pass

    async def get_events(self, connector_type: str) -> list[ConnectorEvent]:
        return [e for e in self._events if e.connector_type == connector_type]

    async def get_all_events(self) -> list[ConnectorEvent]:
        return list(self._events)


connector_event_publisher = ConnectorEventPublisher()
