from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


class IntentType(str, Enum):
    MISSION_REQUEST = "mission_request"
    QUESTION = "question"
    ANALYSIS = "analysis"
    INVESTIGATION = "investigation"
    AUTOMATION = "automation"
    RECOMMENDATION = "recommendation"
    CONVERSATION = "conversation"
    TOOL_INVOCATION = "tool_invocation"


class ExecutionMode(str, Enum):
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    DEPENDENCY = "dependency"


class RuntimeTarget(str, Enum):
    IDENTITY = "identity_runtime"
    MISSION = "mission_runtime"
    GOVERNANCE = "governance_runtime"
    KNOWLEDGE = "knowledge_runtime"
    LEARNING = "learning_runtime"
    EXECUTION = "execution_runtime"
    CONNECTOR = "connector_runtime"
    AI = "ai_runtime"


class PlanStepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    SKIPPED = "skipped"


class AIRequestStatus(str, Enum):
    RECEIVED = "received"
    CLASSIFIED = "classified"
    PLANNED = "planned"
    ROUTED = "routed"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class AIContext:
    request_id: str = ""
    user_id: str = ""
    tenant_id: str = ""
    session_id: str = ""
    source: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class AIRequest:
    id: str = field(default_factory=lambda: f"ai-{uuid.uuid4().hex[:12]}")
    intent: IntentType = IntentType.CONVERSATION
    prompt: str = ""
    context: Optional[AIContext] = None
    raw_input: dict[str, Any] = field(default_factory=dict)
    constraints: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class PlanStep:
    step_id: str = field(default_factory=lambda: f"step-{uuid.uuid4().hex[:8]}")
    order: int = 0
    name: str = ""
    description: str = ""
    runtime: RuntimeTarget = RuntimeTarget.AI
    action: str = ""
    params: dict[str, Any] = field(default_factory=dict)
    depends_on: list[str] = field(default_factory=list)
    timeout_seconds: float = 30.0
    status: PlanStepStatus = PlanStepStatus.PENDING
    result: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


@dataclass
class AIExecutionPlan:
    plan_id: str = field(default_factory=lambda: f"plan-{uuid.uuid4().hex[:12]}")
    request_id: str = ""
    steps: list[PlanStep] = field(default_factory=list)
    mode: ExecutionMode = ExecutionMode.SEQUENTIAL
    status: AIRequestStatus = AIRequestStatus.RECEIVED
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def is_complete(self) -> bool:
        return all(s.status == PlanStepStatus.COMPLETED for s in self.steps)

    @property
    def has_failed(self) -> bool:
        return any(s.status == PlanStepStatus.FAILED for s in self.steps)

    @property
    def is_cancelled(self) -> bool:
        return any(s.status == PlanStepStatus.CANCELLED for s in self.steps)


@dataclass
class AIReasoningTrace:
    trace_id: str = field(default_factory=lambda: f"trace-{uuid.uuid4().hex[:12]}")
    request_id: str = ""
    steps: list[dict[str, Any]] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def add_step(self, label: str, detail: str, data: Optional[dict[str, Any]] = None) -> None:
        self.steps.append({
            "label": label,
            "detail": detail,
            "data": data or {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    def get_summary(self) -> list[str]:
        return [f"{s['label']}: {s['detail']}" for s in self.steps]


@dataclass
class AIResponse:
    request_id: str = ""
    status: AIRequestStatus = AIRequestStatus.RECEIVED
    intent: Optional[IntentType] = None
    plan: Optional[AIExecutionPlan] = None
    trace: Optional[AIReasoningTrace] = None
    result: Optional[dict[str, Any]] = None
    summary: str = ""
    error: Optional[str] = None
    duration_ms: Optional[float] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
