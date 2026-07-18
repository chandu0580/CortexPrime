from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


class GovernanceDecision(str, Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"
    REQUIRE_REVIEW = "REQUIRE_REVIEW"
    ESCALATE = "ESCALATE"


class DecisionReasonCode(str, Enum):
    POLICY_ALLOWED = "policy_allowed"
    POLICY_DENIED = "policy_denied"
    RISK_TOO_HIGH = "risk_too_high"
    APPROVAL_REQUIRED = "approval_required"
    APPROVED = "approved"
    REJECTED = "rejected"
    ESCALATED = "escalated"
    AUTO_APPROVED = "auto_approved"
    MANUAL_APPROVED = "manual_approved"
    NO_POLICY_MATCH = "no_policy_match"
    SYSTEM_DENIED = "system_denied"
    EMERGENCY_STOP = "emergency_stop"
    TIMEOUT = "timeout"


@dataclass
class PolicyResult:
    policy_name: str = ""
    policy_id: str = ""
    category: str = ""
    severity: str = "medium"
    matched: bool = False
    decision: GovernanceDecision = GovernanceDecision.ALLOW
    reason_code: Optional[DecisionReasonCode] = None
    message: str = ""
    conditions_evaluated: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class DecisionRequest:
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    requester: str = ""
    user: str = ""
    role: str = ""
    tenant: str = ""

    mission_id: Optional[str] = None
    mission_type: Optional[str] = None
    execution_id: Optional[str] = None
    execution_type: Optional[str] = None

    resource_type: str = ""
    resource_id: str = ""
    action: str = ""

    connector_type: Optional[str] = None
    connector_capability: Optional[str] = None

    scope: str = "mission"
    risk_level: str = "low"
    context: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class DecisionResponse:
    decision: GovernanceDecision
    reason_code: DecisionReasonCode
    message: str = ""
    matched_policies: list[PolicyResult] = field(default_factory=list)
    approval_request_id: Optional[str] = None
    approval_workflow_id: Optional[str] = None
    risk_level: str = "low"
    evaluated_by: str = "governance_runtime"
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def allowed(self) -> bool:
        return self.decision == GovernanceDecision.ALLOW

    @property
    def denied(self) -> bool:
        return self.decision == GovernanceDecision.DENY

    @property
    def requires_approval(self) -> bool:
        return self.decision == GovernanceDecision.REQUIRE_APPROVAL

    @property
    def requires_review(self) -> bool:
        return self.decision == GovernanceDecision.REQUIRE_REVIEW

    @property
    def escalated(self) -> bool:
        return self.decision == GovernanceDecision.ESCALATE


GOVERNANCE_EVENT_TYPES: dict[str, str] = {
    "governance.policy_evaluated": "Policy was evaluated",
    "governance.allowed": "Action was allowed by governance",
    "governance.denied": "Action was denied by governance",
    "governance.approval_requested": "Approval was requested",
    "governance.approved": "Action was approved",
    "governance.rejected": "Action was rejected",
    "governance.escalated": "Action was escalated",
    "governance.review_required": "Review was required",
    "governance.emergency_stop": "Emergency stop activated",
}
