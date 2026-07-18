from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


class MissionStatus(str, Enum):
    CREATED = "CREATED"
    PLANNING = "PLANNING"
    RISK_ANALYSIS = "RISK_ANALYSIS"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    APPROVED = "APPROVED"
    QUEUED = "QUEUED"
    EXECUTING = "EXECUTING"
    MONITORING = "MONITORING"
    VERIFYING = "VERIFYING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    ROLLING_BACK = "ROLLING_BACK"
    ROLLED_BACK = "ROLLED_BACK"
    CANCELLED = "CANCELLED"


class MissionPriority(int, Enum):
    CRITICAL = 1
    HIGH = 2
    MEDIUM = 3
    LOW = 4
    BACKGROUND = 5


class MissionType(str, Enum):
    STANDARD = "standard"
    RECOVERY = "recovery"
    MAINTENANCE = "maintenance"
    COMPLIANCE = "compliance"
    EMERGENCY = "emergency"
    EXPLORATORY = "exploratory"


@dataclass
class MissionTimeline:
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    planning_at: Optional[datetime] = None
    approved_at: Optional[datetime] = None
    queued_at: Optional[datetime] = None
    executing_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    failed_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    duration_ms: Optional[float] = None


@dataclass
class MissionMetadata:
    version: int = 1
    tags: list[str] = field(default_factory=list)
    source: str = "api"
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    retry_count: int = 0
    original_mission_id: Optional[str] = None
    custom: dict[str, Any] = field(default_factory=dict)


@dataclass
class MissionContext:
    inputs: dict[str, Any] = field(default_factory=dict)
    outputs: dict[str, Any] = field(default_factory=dict)
    environment: dict[str, Any] = field(default_factory=dict)
    constraints: list[str] = field(default_factory=list)


@dataclass
class MissionOwnership:
    owner: str
    team: Optional[str] = None
    department: Optional[str] = None
    created_by: str = ""
    approved_by: Optional[str] = None


@dataclass
class MissionEntity:
    id: uuid.UUID
    title: str
    objective: str
    status: MissionStatus
    priority: MissionPriority
    mission_type: MissionType
    category: Optional[str] = None
    timeline: MissionTimeline = field(default_factory=MissionTimeline)
    metadata: MissionMetadata = field(default_factory=MissionMetadata)
    context: MissionContext = field(default_factory=MissionContext)
    ownership: Optional[MissionOwnership] = None


@dataclass
class MissionEventRecord:
    event_id: str
    mission_id: str
    event_type: str
    correlation_id: str
    from_status: Optional[str]
    to_status: Optional[str]
    actor: Optional[str]
    reason: Optional[str]
    payload: dict[str, Any]
    timestamp: datetime
