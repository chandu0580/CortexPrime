from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class MemoryPhase(str, Enum):
    INIT = "init"
    PLANNING = "planning"
    EXECUTING = "executing"
    VERIFYING = "verifying"
    COMPLETED = "completed"
    FAILED = "failed"
    ARCHIVED = "archived"


class MemoryStatus(str, Enum):
    ACTIVE = "active"
    SNAPSHOTTED = "snapshotted"
    COMPRESSED = "compressed"
    EXPIRED = "expired"
    ARCHIVED = "archived"


@dataclass
class ReasoningStep:
    step_id: str = ""
    description: str = ""
    decision: str = ""
    alternatives: List[str] = field(default_factory=list)
    confidence: float = 1.0
    timestamp: Optional[str] = None


@dataclass
class ConversationTurn:
    turn_id: str = ""
    role: str = ""
    content: str = ""
    timestamp: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkingMemory:
    current_goal: str = ""
    current_phase: MemoryPhase = MemoryPhase.INIT
    completed_steps: List[str] = field(default_factory=list)
    pending_steps: List[str] = field(default_factory=list)
    active_context: Dict[str, Any] = field(default_factory=dict)
    task_outputs: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MissionMemory:
    mission_id: str = ""
    mission_name: str = ""
    objective: str = ""
    category: str = ""
    status: str = "pending"
    priority: str = "medium"
    risk_level: str = "low"
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ReasoningMemory:
    reasoning_chain: List[ReasoningStep] = field(default_factory=list)
    decisions: List[Dict[str, Any]] = field(default_factory=list)
    alternatives_considered: List[Dict[str, Any]] = field(default_factory=list)
    critical_decisions: List[str] = field(default_factory=list)
    confidence_scores: Dict[str, float] = field(default_factory=dict)


@dataclass
class ConversationMemory:
    turns: List[ConversationTurn] = field(default_factory=list)
    current_context: str = ""
    turn_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutionMemory:
    connector_outputs: Dict[str, Any] = field(default_factory=dict)
    intermediate_results: List[Dict[str, Any]] = field(default_factory=list)
    error_history: List[Dict[str, Any]] = field(default_factory=list)
    execution_path: List[str] = field(default_factory=list)
    artifacts: List[MemoryArtifact] = field(default_factory=list)


@dataclass
class MemoryContext:
    mission_id: str
    working_memory: WorkingMemory = field(default_factory=WorkingMemory)
    mission_memory: MissionMemory = field(default_factory=MissionMemory)
    reasoning_memory: ReasoningMemory = field(default_factory=ReasoningMemory)
    conversation_memory: ConversationMemory = field(default_factory=ConversationMemory)
    execution_memory: ExecutionMemory = field(default_factory=ExecutionMemory)
    status: MemoryStatus = MemoryStatus.ACTIVE
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    expires_at: Optional[str] = None
    user_id: str = ""
    tenant_id: str = ""
    trace_id: str = ""
    correlation_id: str = ""
    tags: Dict[str, str] = field(default_factory=dict)


@dataclass
class MemorySnapshot:
    snapshot_id: str = ""
    mission_id: str = ""
    context_copy: Optional[MemoryContext] = None
    captured_at: Optional[str] = None
    compression_metadata: Dict[str, Any] = field(default_factory=dict)
    step_count: int = 0
    artifact_count: int = 0
    size_estimate_bytes: int = 0


@dataclass
class MemoryArtifact:
    artifact_id: str = ""
    name: str = ""
    artifact_type: str = ""
    data: Any = None
    source: str = ""
    created_at: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
