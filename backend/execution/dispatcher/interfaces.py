from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


class DispatchStepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    TIMEOUT = "timeout"


@dataclass
class ExecutionDispatchStepResult:
    step_id: str
    status: DispatchStepStatus
    outputs: dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    execution_id: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_ms: Optional[float] = None


@dataclass
class ExecutionDispatchResult:
    execution_id: str
    success: bool
    step_results: list[ExecutionDispatchStepResult] = field(default_factory=list)
    error: Optional[str] = None
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None


@dataclass
class ExecutionProgressReport:
    execution_id: str
    total_steps: int = 1
    completed_steps: int = 0
    failed_steps: int = 0
    current_step: Optional[str] = None
    percent: float = 0.0
    status: str = "running"
    message: Optional[str] = None


class ExecutionDispatcher(ABC):
    @abstractmethod
    async def dispatch(
        self,
        execution_id: str,
        execution_type: str,
        command: str,
        inputs: Optional[dict[str, Any]] = None,
        environment: Optional[dict[str, Any]] = None,
        timeout_seconds: int = 300,
    ) -> ExecutionDispatchResult:
        ...

    @abstractmethod
    async def cancel(self, execution_id: str) -> bool:
        ...

    @abstractmethod
    async def get_progress(self, execution_id: str) -> Optional[ExecutionProgressReport]:
        ...

    @abstractmethod
    async def is_running(self, execution_id: str) -> bool:
        ...
