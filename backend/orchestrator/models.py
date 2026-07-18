from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List
from uuid import uuid4


class MissionLifecycleState(str, Enum):
    RECEIVED = "mission_received"
    ANALYZED = "mission_analyzed"
    PLANNED = "mission_planned"
    KNOWLEDGE_RETRIEVED = "knowledge_retrieved"
    LEARNING_RETRIEVED = "learning_retrieved"
    GOVERNANCE_EVALUATED = "governance_evaluated"
    EXECUTION_PLANNED = "execution_planned"
    EXECUTION_STARTED = "execution_started"
    EXECUTION_COMPLETED = "execution_completed"
    VERIFIED = "verification"
    KNOWLEDGE_UPDATED = "knowledge_updated"
    LEARNING_UPDATED = "learning_updated"
    ARCHIVED = "mission_archived"


class OrchestratorStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    FAILED = "failed"


class ExecutionMode(str, Enum):
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"


class FailureCategory(str, Enum):
    TRANSIENT = "transient"
    POLICY = "policy"
    CONNECTOR = "connector"
    TIMEOUT = "timeout"
    RUNTIME = "runtime"
    UNKNOWN = "unknown"


@dataclass
class MissionEvent:
    mission_id: str
    state: MissionLifecycleState
    event_type: str
    source: str
    message: str
    timestamp: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    correlation_id: str = ""

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()
        if not self.correlation_id:
            self.correlation_id = uuid4().hex[:12]


@dataclass
class MissionArtifact:
    artifact_id: str = ""
    name: str = ""
    artifact_type: str = ""
    data: Any = None
    source: str = ""
    state: MissionLifecycleState = MissionLifecycleState.RECEIVED
    created_at: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.artifact_id:
            self.artifact_id = uuid4().hex[:12]
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()


@dataclass
class StageResult:
    state: MissionLifecycleState
    success: bool
    result: Any = None
    error: str = ""
    duration_seconds: float = 0.0
    runtime: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OrchestratorMission:
    mission_id: str
    goal: str
    current_state: MissionLifecycleState = MissionLifecycleState.RECEIVED
    status: OrchestratorStatus = OrchestratorStatus.PENDING
    created_at: str = ""
    updated_at: str = ""
    started_at: str = ""
    completed_at: str = ""
    error: str = ""
    failure_category: str = ""
    stage_results: Dict[str, StageResult] = field(default_factory=dict)
    timeline: List[MissionEvent] = field(default_factory=list)
    artifacts: Dict[str, MissionArtifact] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    context: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()
        if not self.updated_at:
            self.updated_at = self.created_at

    def add_event(self, event: MissionEvent) -> None:
        self.timeline.append(event)
        self.updated_at = datetime.now(timezone.utc).isoformat()

    def add_artifact(self, artifact: MissionArtifact) -> None:
        self.artifacts[artifact.artifact_id] = artifact

    def set_state(self, state: MissionLifecycleState) -> None:
        self.current_state = state
        self.updated_at = datetime.now(timezone.utc).isoformat()
