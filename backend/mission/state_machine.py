from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from backend.mission.models import MissionStatus


TRANSITIONS: dict[MissionStatus, set[MissionStatus]] = {
    MissionStatus.CREATED: {MissionStatus.PLANNING, MissionStatus.CANCELLED},
    MissionStatus.PLANNING: {MissionStatus.RISK_ANALYSIS, MissionStatus.CANCELLED, MissionStatus.FAILED},
    MissionStatus.RISK_ANALYSIS: {MissionStatus.AWAITING_APPROVAL, MissionStatus.CANCELLED, MissionStatus.FAILED},
    MissionStatus.AWAITING_APPROVAL: {MissionStatus.APPROVED, MissionStatus.CANCELLED},
    MissionStatus.APPROVED: {MissionStatus.QUEUED, MissionStatus.CANCELLED},
    MissionStatus.QUEUED: {MissionStatus.EXECUTING, MissionStatus.CANCELLED},
    MissionStatus.EXECUTING: {MissionStatus.MONITORING, MissionStatus.FAILED, MissionStatus.CANCELLED},
    MissionStatus.MONITORING: {MissionStatus.VERIFYING, MissionStatus.FAILED, MissionStatus.CANCELLED},
    MissionStatus.VERIFYING: {MissionStatus.COMPLETED, MissionStatus.ROLLING_BACK, MissionStatus.CANCELLED},
    MissionStatus.ROLLING_BACK: {MissionStatus.ROLLED_BACK, MissionStatus.FAILED, MissionStatus.CANCELLED},
    MissionStatus.ROLLED_BACK: {MissionStatus.CANCELLED},
    MissionStatus.FAILED: {MissionStatus.QUEUED, MissionStatus.ROLLING_BACK, MissionStatus.CANCELLED},
    MissionStatus.COMPLETED: set(),
    MissionStatus.CANCELLED: set(),
}

TERMINAL = {MissionStatus.COMPLETED, MissionStatus.CANCELLED, MissionStatus.ROLLED_BACK}
TRANSIENT = {MissionStatus.PLANNING, MissionStatus.RISK_ANALYSIS,
             MissionStatus.EXECUTING, MissionStatus.MONITORING,
             MissionStatus.VERIFYING, MissionStatus.ROLLING_BACK}


def is_valid_transition(current: MissionStatus, target: MissionStatus) -> bool:
    return target in TRANSITIONS.get(current, set())


def is_terminal(status: MissionStatus) -> bool:
    return status in TERMINAL


def is_transient(status: MissionStatus) -> bool:
    return status in TRANSIENT


@dataclass
class TransitionResult:
    success: bool
    from_status: MissionStatus
    to_status: MissionStatus
    reason: Optional[str] = None

    @property
    def changed(self) -> bool:
        return self.from_status != self.to_status
