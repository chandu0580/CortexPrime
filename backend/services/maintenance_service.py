from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models.maintenance_event import MaintenanceEvent

log = logging.getLogger(__name__)


@dataclass
class MaintenanceState:
    enabled: bool = False
    banner_message: Optional[str] = None
    started_at: Optional[str] = None
    allow_existing_missions: bool = True
    block_new_missions: bool = True
    triggered_by: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "banner_message": self.banner_message,
            "started_at": self.started_at,
            "allow_existing_missions": self.allow_existing_missions,
            "block_new_missions": self.block_new_missions,
            "triggered_by": self.triggered_by,
        }


class MaintenanceService:
    def __init__(self) -> None:
        self._state = MaintenanceState()

    async def enable(
        self,
        banner_message: Optional[str] = None,
        allow_existing_missions: bool = True,
        block_new_missions: bool = True,
        triggered_by: Optional[str] = None,
        db: Optional[AsyncSession] = None,
    ) -> MaintenanceState:
        if self._state.enabled:
            log.warning("Maintenance mode already enabled")
        self._state.enabled = True
        self._state.banner_message = banner_message or "System is undergoing maintenance. Some features may be unavailable."
        self._state.started_at = datetime.now(timezone.utc).isoformat()
        self._state.allow_existing_missions = allow_existing_missions
        self._state.block_new_missions = block_new_missions
        self._state.triggered_by = triggered_by

        if db:
            event = MaintenanceEvent(
                action="enable",
                enabled=True,
                banner_message=self._state.banner_message,
                triggered_by=triggered_by,
                details=self._state.to_dict(),
            )
            db.add(event)
            await db.flush()

        log.info(
            "Maintenance mode ENABLED by %s (allow_existing=%s, block_new=%s)",
            triggered_by or "system",
            allow_existing_missions,
            block_new_missions,
        )
        return self._state

    async def disable(self, triggered_by: Optional[str] = None, db: Optional[AsyncSession] = None) -> MaintenanceState:
        if not self._state.enabled:
            log.warning("Maintenance mode already disabled")

        was_enabled = self._state.enabled
        self._state = MaintenanceState()

        if db:
            event = MaintenanceEvent(
                action="disable",
                enabled=False,
                triggered_by=triggered_by,
                details={"was_enabled": was_enabled},
            )
            db.add(event)
            await db.flush()

        log.info("Maintenance mode DISABLED by %s", triggered_by or "system")
        return self._state

    async def get_status(self) -> Dict[str, Any]:
        return self._state.to_dict()

    def is_maintenance_active(self) -> bool:
        return self._state.enabled

    def should_block_new_mission(self) -> bool:
        return self._state.enabled and self._state.block_new_missions

    def get_banner(self) -> Optional[str]:
        return self._state.banner_message if self._state.enabled else None

    async def get_event_history(
        self, db: AsyncSession, limit: int = 100
    ) -> list[Dict[str, Any]]:
        from sqlalchemy import select
        result = await db.execute(
            select(MaintenanceEvent)
            .order_by(MaintenanceEvent.created_at.desc())
            .limit(limit)
        )
        return [e.to_dict() for e in result.scalars().all()]

    def graceful_shutdown_requested(self) -> bool:
        return self._state.enabled and not self._state.allow_existing_missions


maintenance_service = MaintenanceService()
