from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4


class ApproverRole(str, Enum):
    EXECUTIVE = "executive"
    MANAGER = "manager"
    SECURITY_OFFICER = "security_officer"
    COMPLIANCE_OFFICER = "compliance_officer"
    PLATFORM_ADMIN = "platform_admin"
    MISSION_OWNER = "mission_owner"


class WorkflowStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    APPROVED = "approved"
    REJECTED = "rejected"
    ESCALATED = "escalated"
    EXPIRED = "expired"
    DELEGATED = "delegated"
    BREAK_GLASS = "break_glass"
    OVERRIDDEN = "overridden"


class StepStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    ESCALATED = "escalated"
    EXPIRED = "expired"
    DELEGATED = "delegated"
    SKIPPED = "skipped"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ApprovalPolicy:
    policy_id: str
    name: str
    description: str
    risk_level: RiskLevel
    mission_ids: List[str] = field(default_factory=list)
    required_roles: List[ApproverRole] = field(default_factory=list)
    required_levels: int = 1
    escalation_minutes: int = 15
    expiration_minutes: int = 30
    requires_break_glass: bool = False
    break_glass_roles: List[ApproverRole] = field(default_factory=list)
    notify_roles: List[ApproverRole] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "name": self.name,
            "description": self.description,
            "risk_level": self.risk_level.value,
            "mission_ids": self.mission_ids,
            "required_roles": [r.value for r in self.required_roles],
            "required_levels": self.required_levels,
            "escalation_minutes": self.escalation_minutes,
            "expiration_minutes": self.expiration_minutes,
            "requires_break_glass": self.requires_break_glass,
            "break_glass_roles": [r.value for r in self.break_glass_roles],
            "notify_roles": [r.value for r in self.notify_roles],
        }


@dataclass
class ApprovalStep:
    step_id: str
    level: int
    required_roles: List[ApproverRole]
    assigned_to: Optional[str] = None
    status: StepStatus = StepStatus.PENDING
    resolved_by: Optional[str] = None
    resolved_at: Optional[str] = None
    reason: Optional[str] = None
    delegated_to: Optional[str] = None
    escalation_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_id": self.step_id,
            "level": self.level,
            "required_roles": [r.value for r in self.required_roles],
            "assigned_to": self.assigned_to,
            "status": self.status.value,
            "resolved_by": self.resolved_by,
            "resolved_at": self.resolved_at,
            "reason": self.reason,
            "delegated_to": self.delegated_to,
            "escalation_count": self.escalation_count,
        }


@dataclass
class ApprovalWorkflow:
    workflow_id: str
    execution_id: str
    mission_id: str
    policy_id: str
    objective: str
    risk_level: RiskLevel
    current_step: int = 0
    steps: List[ApprovalStep] = field(default_factory=list)
    status: WorkflowStatus = WorkflowStatus.PENDING
    break_glass: bool = False
    break_glass_by: Optional[str] = None
    break_glass_reason: Optional[str] = None
    overridden_by: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def current_step_obj(self) -> Optional[ApprovalStep]:
        if 0 <= self.current_step < len(self.steps):
            return self.steps[self.current_step]
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "execution_id": self.execution_id,
            "mission_id": self.mission_id,
            "policy_id": self.policy_id,
            "objective": self.objective[:200],
            "risk_level": self.risk_level.value,
            "current_step": self.current_step,
            "total_steps": len(self.steps),
            "steps": [s.to_dict() for s in self.steps],
            "status": self.status.value,
            "break_glass": self.break_glass,
            "break_glass_by": self.break_glass_by,
            "break_glass_reason": self.break_glass_reason,
            "overridden_by": self.overridden_by,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class Delegation:
    delegation_id: str
    from_role: ApproverRole
    from_user: str
    to_role: ApproverRole
    to_user: str
    reason: str
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    expires_at: Optional[str] = None
    active: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "delegation_id": self.delegation_id,
            "from_role": self.from_role.value,
            "from_user": self.from_user,
            "to_role": self.to_role.value,
            "to_user": self.to_user,
            "reason": self.reason,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "active": self.active,
        }


@dataclass
class BreakGlassRecord:
    record_id: str
    execution_id: str
    mission_id: str
    overridden_by: str
    role: ApproverRole
    reason: str
    risk_level: RiskLevel
    original_assessment: str
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    justification_documentation: Optional[str] = None
    reviewed: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "record_id": self.record_id,
            "execution_id": self.execution_id,
            "mission_id": self.mission_id,
            "overridden_by": self.overridden_by,
            "role": self.role.value,
            "reason": self.reason,
            "risk_level": self.risk_level.value,
            "original_assessment": self.original_assessment,
            "created_at": self.created_at,
            "justification_documentation": self.justification_documentation,
            "reviewed": self.reviewed,
        }


def new_step_id() -> str:
    return f"step_{uuid4().hex[:12]}"


def new_workflow_id() -> str:
    return f"wf_{uuid4().hex[:12]}"


def new_delegation_id() -> str:
    return f"del_{uuid4().hex[:12]}"


def new_break_glass_id() -> str:
    return f"bg_{uuid4().hex[:12]}"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
