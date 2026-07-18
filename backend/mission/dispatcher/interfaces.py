from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    TIMEOUT = "timeout"


@dataclass
class DispatchStepResult:
    step_id: str
    status: StepStatus
    outputs: dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_ms: Optional[float] = None


@dataclass
class DispatchResult:
    mission_id: str
    success: bool
    step_results: list[DispatchStepResult] = field(default_factory=list)
    error: Optional[str] = None
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None


@dataclass
class ProgressReport:
    mission_id: str
    total_steps: int
    completed_steps: int
    failed_steps: int
    current_step: Optional[str] = None
    percent: float = 0.0
    status: str = "running"
    message: Optional[str] = None


class MissionDispatcher(ABC):
    @abstractmethod
    async def dispatch(self, mission_id: str, plan_id: str,
                       steps: list[Any]) -> DispatchResult:
        ...

    @abstractmethod
    async def cancel(self, mission_id: str) -> bool:
        ...

    @abstractmethod
    async def get_progress(self, mission_id: str) -> Optional[ProgressReport]:
        ...

    @abstractmethod
    async def is_running(self, mission_id: str) -> bool:
        ...
