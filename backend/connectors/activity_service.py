from __future__ import annotations

import logging
import time
import uuid
from typing import Any, Dict, Optional

from backend.database.models.connector_activity import ConnectorActivityModel
from backend.database.repositories.connector_activity_repository import (
    ConnectorActivityRepository,
)
from backend.database.session import get_session
from backend.events.event_bus import event_bus
from backend.events.event_models import CognitionEvent
from backend.safety.audit_logger import audit_logger

log = logging.getLogger(__name__)


class ConnectorActivityService:

    @staticmethod
    async def record(
        connector_name: str,
        connector_type: str,
        operation: str,
        status: str = "success",
        resource: Optional[str] = None,
        resource_id: Optional[str] = None,
        duration_ms: Optional[int] = None,
        initiated_by: Optional[str] = None,
        request_id: Optional[uuid.UUID] = None,
        correlation_id: Optional[uuid.UUID] = None,
        message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ConnectorActivityModel:
        async for session in get_session():
            repo = ConnectorActivityRepository(session)
            activity = await repo.create(
                ConnectorActivityModel(
                    connector_name=connector_name,
                    connector_type=connector_type,
                    operation=operation,
                    resource=resource,
                    resource_id=resource_id,
                    status=status,
                    initiated_by=initiated_by,
                    duration_ms=duration_ms,
                    request_id=request_id,
                    correlation_id=correlation_id,
                    message=message,
                    metadata_=metadata,
                )
            )

            user = initiated_by or "system"
            await audit_logger.alog(
                execution_id=str(activity.id),
                agent=f"connector:{connector_type}",
                action=f"connector.{operation}",
                target=f"{connector_type}/{resource or operation}",
                risk_level="low" if status == "success" else "medium",
                outcome="allowed" if status == "success" else "failed",
                reason=message or f"{connector_name} {operation} {status}",
                user=user,
                metadata={
                    "connector_name": connector_name,
                    "connector_type": connector_type,
                    "operation": operation,
                    "status": status,
                    "duration_ms": duration_ms,
                    "activity_id": str(activity.id),
                },
            )

            try:
                await event_bus.publish(
                    CognitionEvent(
                        agent=f"connector:{connector_type}",
                        event_type=f"connector.{operation}",
                        status=status,
                        message=message or f"{connector_name} {operation}",
                        phase="operation",
                    )
                )
            except Exception:
                log.warning("Failed to publish connector event to event bus", exc_info=True)

            log.info(
                "Connector activity: %s/%s %s - %s (%dms)",
                connector_type, connector_name, operation, status, duration_ms or 0,
            )
            return activity

    @staticmethod
    async def record_operation(
        connector_name: str,
        connector_type: str,
        operation: str,
        resource: Optional[str] = None,
        func=None,
        *args,
        **kwargs,
    ):
        start = time.monotonic()
        status = "success"
        resource_id = None
        message = None
        result = None
        try:
            result = await func(*args, **kwargs)
            if hasattr(result, "id"):
                resource_id = str(result.id)
            elif isinstance(result, dict) and "id" in result:
                resource_id = str(result["id"])
            return result
        except Exception as e:
            status = "failed"
            message = str(e)
            raise
        finally:
            duration_ms = int((time.monotonic() - start) * 1000)
            try:
                await ConnectorActivityService.record(
                    connector_name=connector_name,
                    connector_type=connector_type,
                    operation=operation,
                    resource=resource or operation,
                    resource_id=resource_id,
                    status=status,
                    duration_ms=duration_ms,
                    message=message,
                )
            except Exception:
                log.warning("Failed to record connector activity", exc_info=True)
