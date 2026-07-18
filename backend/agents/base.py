from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set
from uuid import uuid4

log = logging.getLogger(__name__)


class AgentStatus(str, Enum):
    IDLE = "idle"
    ASSIGNED = "assigned"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    ESCALATED = "escalated"
    REPLACED = "replaced"


class TaskPriority(int, Enum):
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


class CollaborationMode(str, Enum):
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    DEPENDENCY = "dependency"
    VOTING = "voting"


@dataclass
class AgentCapability:
    capability_type: str
    description: str
    required_runtimes: List[str] = field(default_factory=list)
    required_permissions: List[str] = field(default_factory=list)

    def matches(self, query: str) -> bool:
        q = query.lower()
        ct = self.capability_type.lower()
        desc = self.description.lower()
        return q in ct or ct in q or q in desc or desc in q


@dataclass
class AgentTask:
    task_id: str = ""
    agent_type: str = ""
    description: str = ""
    input_data: Dict[str, Any] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)
    timeout_seconds: float = 300.0
    max_retries: int = 2
    escalation_agent: str = ""
    priority: TaskPriority = TaskPriority.NORMAL
    status: AgentStatus = AgentStatus.IDLE
    assigned_agent: str = ""
    created_at: str = ""
    completed_at: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.task_id:
            self.task_id = uuid4().hex[:12]
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()


@dataclass
class AgentResult:
    task_id: str
    agent_id: str
    agent_type: str
    success: bool
    output_data: Any = None
    error: str = ""
    duration_seconds: float = 0.0
    artifacts: List[Dict[str, Any]] = field(default_factory=list)
    reasoning_steps: List[Dict[str, Any]] = field(default_factory=list)
    voting_results: Optional[Dict[str, Any]] = None
    delegation_chain: List[str] = field(default_factory=list)


@dataclass
class AgentContext:
    mission_id: str
    agent_id: str = ""
    agent_type: str = ""
    tenant_id: str = ""
    user_id: str = ""
    trace_id: str = ""
    correlation_id: str = ""
    permissions: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.trace_id:
            self.trace_id = uuid4().hex[:12]
        if not self.correlation_id:
            self.correlation_id = uuid4().hex[:12]


class BaseAgent:
    def __init__(self, agent_id: str = "") -> None:
        self.agent_id = agent_id or f"{self.agent_type}_{uuid4().hex[:8]}"
        self.status = AgentStatus.IDLE
        self._capabilities: List[AgentCapability] = []
        self._current_task: Optional[AgentTask] = None
        self._result_history: List[AgentResult] = []

    @property
    def agent_type(self) -> str:
        return self.__class__.__name__

    @property
    def capabilities(self) -> List[AgentCapability]:
        return list(self._capabilities)

    def can_handle(self, task: AgentTask) -> bool:
        if task.agent_type and task.agent_type != self.agent_type:
            return False
        if not task.agent_type:
            return any(c.matches(task.description) for c in self._capabilities)
        return True

    async def execute(self, task: AgentTask, ctx: AgentContext) -> AgentResult:
        self._current_task = task
        self.status = AgentStatus.RUNNING
        start = datetime.now(timezone.utc)
        try:
            result = await self._execute_impl(task, ctx)
            self.status = AgentStatus.COMPLETED if result.success else AgentStatus.FAILED
            return result
        except Exception as exc:
            self.status = AgentStatus.FAILED
            dur = (datetime.now(timezone.utc) - start).total_seconds()
            return AgentResult(
                task_id=task.task_id, agent_id=self.agent_id,
                agent_type=self.agent_type, success=False, error=str(exc),
                duration_seconds=round(dur, 3),
            )
        finally:
            self._current_task = None

    async def _execute_impl(self, task: AgentTask, ctx: AgentContext) -> AgentResult:
        raise NotImplementedError

    @property
    def info(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "agent_type": self.agent_type,
            "status": self.status.value,
            "capabilities": [c.capability_type for c in self._capabilities],
        }
