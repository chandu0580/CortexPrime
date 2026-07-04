from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class MissionCategory(str, Enum):
    SOFTWARE_RELEASE = "software_release"
    INCIDENT_RESPONSE = "incident_response"
    EXECUTIVE_RESEARCH = "executive_research"
    COMPLIANCE_AUDIT = "compliance_audit"
    CHANGE_MANAGEMENT = "change_management"
    INFRASTRUCTURE_DEPLOYMENT = "infrastructure_deployment"
    SECURITY_INVESTIGATION = "security_investigation"
    KNOWLEDGE_DISCOVERY = "knowledge_discovery"
    CUSTOMER_ESCALATION = "customer_escalation"
    DISASTER_RECOVERY = "disaster_recovery"


class WorkerType(str, Enum):
    BROWSER = "browser"
    VOICE = "voice"
    COMPUTER = "computer"


class ConnectorType(str, Enum):
    RABBITMQ = "rabbitmq"
    REDIS = "redis"
    NEO4J = "neo4j"


class GovernanceLevel(str, Enum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ExecutionStage(str, Enum):
    INIT = "INIT"
    PLANNING = "PLANNING"
    RESEARCHING = "RESEARCHING"
    REASONING = "REASONING"
    VALIDATING = "VALIDATING"
    GENERATING = "GENERATING"
    MEMORY_UPDATE = "MEMORY_UPDATE"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class AuditLevel(str, Enum):
    STANDARD = "standard"
    DETAILED = "detailed"
    FULL = "full"


@dataclass
class RetryPolicy:
    max_retries: int = 3
    backoff_seconds: float = 2.0
    backoff_multiplier: float = 2.0
    max_backoff_seconds: float = 60.0


@dataclass
class SuccessCriterion:
    description: str
    metric_name: Optional[str] = None
    metric_threshold: Optional[float] = None


@dataclass
class FailureRecovery:
    description: str
    rollback_action: Optional[str] = None
    notify_on_failure: bool = True


@dataclass
class MissionMetadata:
    id: str
    name: str
    version: str = "1.0.0"
    description: str = ""
    category: MissionCategory = MissionCategory.KNOWLEDGE_DISCOVERY
    tags: List[str] = field(default_factory=list)


@dataclass
class MissionDefinition:
    metadata: MissionMetadata
    objective_template: str
    objectives: List[str] = field(default_factory=list)
    required_workers: List[WorkerType] = field(default_factory=list)
    required_connectors: List[ConnectorType] = field(default_factory=list)
    required_approvals: GovernanceLevel = GovernanceLevel.LOW
    execution_stages: List[ExecutionStage] = field(default_factory=lambda: [
        ExecutionStage.INIT,
        ExecutionStage.PLANNING,
        ExecutionStage.RESEARCHING,
        ExecutionStage.VALIDATING,
        ExecutionStage.GENERATING,
        ExecutionStage.MEMORY_UPDATE,
        ExecutionStage.COMPLETED,
    ])
    success_criteria: List[SuccessCriterion] = field(default_factory=list)
    failure_recovery: FailureRecovery = field(default_factory=FailureRecovery)
    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)
    metrics: List[str] = field(default_factory=lambda: [
        "mission_duration", "llm_tokens", "llm_cost",
        "confidence_score", "agent_executions",
    ])
    audit_requirements: AuditLevel = AuditLevel.STANDARD
    supports_workspace: bool = True
    supports_voice: bool = False
    needs_browser: bool = False
    needs_computer: bool = False

    def build_objective(self, **kwargs: Any) -> str:
        return self.objective_template.format(**kwargs)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "metadata": {
                "id": self.metadata.id,
                "name": self.metadata.name,
                "version": self.metadata.version,
                "description": self.metadata.description,
                "category": self.metadata.category.value,
                "tags": self.metadata.tags,
            },
            "objectives": self.objectives,
            "required_workers": [w.value for w in self.required_workers],
            "required_connectors": [c.value for c in self.required_connectors],
            "required_approvals": self.required_approvals.value,
            "execution_stages": [s.value for s in self.execution_stages],
            "success_criteria": [
                {"description": c.description, "metric": c.metric_name, "threshold": c.metric_threshold}
                for c in self.success_criteria
            ],
            "failure_recovery": {
                "description": self.failure_recovery.description,
                "rollback_action": self.failure_recovery.rollback_action,
                "notify_on_failure": self.failure_recovery.notify_on_failure,
            },
            "retry_policy": {
                "max_retries": self.retry_policy.max_retries,
                "backoff_seconds": self.retry_policy.backoff_seconds,
                "backoff_multiplier": self.retry_policy.backoff_multiplier,
                "max_backoff_seconds": self.retry_policy.max_backoff_seconds,
            },
            "metrics": self.metrics,
            "audit_requirements": self.audit_requirements.value,
        }


@dataclass
class MissionResult:
    status: str
    execution_id: str
    mission_id: str
    objective: str
    confidence_score: float
    response: str
    response_length: int
    stages_completed: List[str] = field(default_factory=list)
    worker_invocations: List[str] = field(default_factory=list)
    total_tokens: int = 0
    total_cost: float = 0.0
    duration_seconds: float = 0.0
    error: Optional[str] = None
