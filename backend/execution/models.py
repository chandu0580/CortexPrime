from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


class ExecutionStatus(str, Enum):
    CREATED = "CREATED"
    QUEUED = "QUEUED"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    RETRYING = "RETRYING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    TIMED_OUT = "TIMED_OUT"


class ExecutionTrigger(str, Enum):
    MANUAL = "manual"
    AUTOMATIC = "automatic"
    EVENT = "event"
    SCHEDULE = "schedule"
    MISSION = "mission"
    WEBHOOK = "webhook"


class ExecutionType(str, Enum):
    SHELL = "shell"
    HTTP = "http"
    SCRIPT = "script"
    MISSION = "mission"
    CUSTOM = "custom"


@dataclass
class ExecutionContext:
    inputs: dict[str, Any] = field(default_factory=dict)
    outputs: dict[str, Any] = field(default_factory=dict)
    environment: dict[str, Any] = field(default_factory=dict)
    parameters: dict[str, Any] = field(default_factory=dict)
    working_directory: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "inputs": self.inputs,
            "outputs": self.outputs,
            "environment": self.environment,
            "parameters": self.parameters,
            "working_directory": self.working_directory,
        }

    @classmethod
    def from_dict(cls, data: Optional[dict[str, Any]]) -> ExecutionContext:
        if not data:
            return cls()
        return cls(
            inputs=data.get("inputs", {}),
            outputs=data.get("outputs", {}),
            environment=data.get("environment", {}),
            parameters=data.get("parameters", {}),
            working_directory=data.get("working_directory"),
        )


@dataclass
class ExecutionMetadata:
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    retry_count: int = 0
    max_retries: int = 3
    timeout_seconds: int = 300
    source: str = "api"
    tags: list[str] = field(default_factory=list)
    custom: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutionEntity:
    id: uuid.UUID
    execution_id: str
    status: ExecutionStatus
    execution_type: ExecutionType = ExecutionType.CUSTOM
    trigger: ExecutionTrigger = ExecutionTrigger.MANUAL
    mission_id: Optional[str] = None
    mission_step_id: Optional[str] = None
    parent_execution_id: Optional[str] = None
    agent: Optional[str] = None
    context: ExecutionContext = field(default_factory=ExecutionContext)
    result: dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None
    metadata: ExecutionMetadata = field(default_factory=ExecutionMetadata)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_ms: Optional[float] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class ExecutionEventRecord:
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    execution_id: str = ""
    event_type: str = ""
    message: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
