from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class MissionPriority(str, Enum):
    LOWEST = "lowest"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class PlanStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class MissionAnalysis:
    goal: str
    category: str = ""
    constraints: List[str] = field(default_factory=list)
    risk: RiskLevel = RiskLevel.LOW
    priority: MissionPriority = MissionPriority.MEDIUM
    dependencies: List[str] = field(default_factory=list)
    required_capabilities: List[str] = field(default_factory=list)
    suggested_connectors: List[str] = field(default_factory=list)
    estimated_duration_minutes: int = 30
    tags: List[str] = field(default_factory=list)
    confidence: float = 0.8
    reasoning: str = ""


@dataclass
class MissionTask:
    id: str
    name: str
    description: str = ""
    required_capability: str = ""
    suggested_connector: str = ""
    depends_on: List[str] = field(default_factory=list)
    estimated_duration_seconds: int = 60
    retry_allowed: bool = True
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MissionStep:
    id: str
    task_id: str
    name: str
    order: int = 0
    connector_type: str = ""
    operation: str = ""
    params: Dict[str, Any] = field(default_factory=dict)
    depends_on: List[str] = field(default_factory=list)
    group_id: Optional[str] = None
    verification_required: bool = True
    rollback_step_id: Optional[str] = None


@dataclass
class TaskGroup:
    id: str
    name: str
    task_ids: List[str] = field(default_factory=list)
    parallel: bool = True


@dataclass
class MissionDecomposition:
    mission_id: str
    tasks: List[MissionTask] = field(default_factory=list)
    steps: List[MissionStep] = field(default_factory=list)
    groups: List[TaskGroup] = field(default_factory=list)
    critical_path: List[str] = field(default_factory=list)
    estimated_duration_seconds: int = 0


@dataclass
class CapabilityPlan:
    task_mappings: Dict[str, str] = field(default_factory=dict)
    connector_mappings: Dict[str, str] = field(default_factory=dict)
    capability_gaps: List[str] = field(default_factory=list)
    available_connectors: List[str] = field(default_factory=list)


@dataclass
class KnowledgeInsight:
    similar_missions: List[Dict[str, Any]] = field(default_factory=list)
    previous_failures: List[Dict[str, Any]] = field(default_factory=list)
    best_practices: List[str] = field(default_factory=list)
    relevant_documents: List[str] = field(default_factory=list)
    confidence: float = 0.0


@dataclass
class LearningInsight:
    patterns: List[Dict[str, Any]] = field(default_factory=list)
    recommendations: List[Dict[str, Any]] = field(default_factory=list)
    risk_indicators: List[str] = field(default_factory=list)
    success_rate: Optional[float] = None


@dataclass
class ComplianceCheck:
    policy: str = ""
    status: str = "pending"
    reason: str = ""
    required_role: str = "admin"
    evidence: Optional[Dict[str, Any]] = None


@dataclass
class GovernancePlan:
    compliance_checks: List[ComplianceCheck] = field(default_factory=list)
    required_approvals: int = 0
    approval_gates: List[Dict[str, Any]] = field(default_factory=list)
    risk_assessment: RiskLevel = RiskLevel.LOW
    approved: bool = False
    governance_level: str = "none"


@dataclass
class ExecutionSubPlan:
    type: str = "sequential"
    steps: List[str] = field(default_factory=list)
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutionPlan:
    mission_id: str = ""
    status: PlanStatus = PlanStatus.PENDING
    sub_plans: List[ExecutionSubPlan] = field(default_factory=list)
    connectors_needed: List[str] = field(default_factory=list)
    estimated_duration_seconds: int = 0
    max_retries: int = 2
    rollback_plan: Optional[str] = None
    verification_plan: Optional[str] = None
    created_at: Optional[str] = None


@dataclass
class MissionVerification:
    success_criteria: List[Dict[str, Any]] = field(default_factory=list)
    verification_steps: List[Dict[str, Any]] = field(default_factory=list)
    rollback_criteria: List[str] = field(default_factory=list)
    completion_criteria: List[str] = field(default_factory=list)
    verification_methods: Dict[str, str] = field(default_factory=dict)


@dataclass
class PipelineStep:
    pipeline_id: str = ""
    name: str = ""
    phase: str = ""
    status: str = "pending"
    duration_ms: float = 0.0
    output: Optional[Dict[str, Any]] = None


@dataclass
class TimelineEntry:
    timestamp: str = ""
    source: str = ""
    event_type: str = ""
    detail: str = ""
    correlation_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MissionTimeline:
    entries: List[TimelineEntry] = field(default_factory=list)
    pipeline_steps: List[PipelineStep] = field(default_factory=list)
    connectors_used: List[str] = field(default_factory=list)
    artifacts_referenced: List[str] = field(default_factory=list)
