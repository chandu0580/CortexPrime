from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional


@dataclass
class TimelineEntry:
    entry_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    mission_id: str = ""
    entry_type: str = "activity"
    status: str = ""
    actor: Optional[str] = None
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)
    duration_ms: Optional[float] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class MissionTimelineService:
    def __init__(self) -> None:
        self._entries: dict[str, list[TimelineEntry]] = {}

    async def add_entry(self, entry: TimelineEntry) -> None:
        if entry.mission_id not in self._entries:
            self._entries[entry.mission_id] = []
        self._entries[entry.mission_id].append(entry)

    async def add_state_change(self, mission_id: str, from_status: str,
                               to_status: str, actor: Optional[str] = None,
                               reason: Optional[str] = None) -> None:
        await self.add_entry(TimelineEntry(
            mission_id=mission_id,
            entry_type="state_change",
            status=to_status,
            actor=actor,
            message=f"State changed: {from_status} → {to_status}",
            details={"from": from_status, "to": to_status, "reason": reason or ""},
        ))

    async def add_approval_event(self, mission_id: str, action: str,
                                 actor: str, approved: bool,
                                 reason: Optional[str] = None) -> None:
        await self.add_entry(TimelineEntry(
            mission_id=mission_id,
            entry_type="approval",
            status="approved" if approved else "rejected",
            actor=actor,
            message=f"Approval {action}: {'granted' if approved else 'rejected'}",
            details={"action": action, "approved": approved, "reason": reason or ""},
        ))

    async def add_retry_event(self, mission_id: str, step_id: str,
                              attempt: int, max_retries: int,
                              error: Optional[str] = None) -> None:
        await self.add_entry(TimelineEntry(
            mission_id=mission_id,
            entry_type="retry",
            status="retrying",
            message=f"Step {step_id} retry {attempt}/{max_retries}",
            details={"step_id": step_id, "attempt": attempt,
                     "max_retries": max_retries, "error": error or ""},
        ))

    async def add_execution_event(self, mission_id: str, step_id: str,
                                  status: str, duration_ms: Optional[float] = None,
                                  error: Optional[str] = None) -> None:
        await self.add_entry(TimelineEntry(
            mission_id=mission_id,
            entry_type="execution",
            status=status,
            message=f"Step {step_id}: {status}",
            details={"step_id": step_id, "error": error or ""},
            duration_ms=duration_ms,
        ))

    async def add_verification_event(self, mission_id: str, result: str,
                                     details: Optional[dict[str, Any]] = None) -> None:
        await self.add_entry(TimelineEntry(
            mission_id=mission_id,
            entry_type="verification",
            status=result,
            message=f"Verification: {result}",
            details=details or {},
        ))

    async def get_timeline(self, mission_id: str) -> list[TimelineEntry]:
        return sorted(self._entries.get(mission_id, []),
                      key=lambda e: e.timestamp)


mission_timeline = MissionTimelineService()
