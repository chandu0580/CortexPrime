"""Policy vocabulary.

Owner: BC-6 Governance.

Answers "may this happen?" -- never "should this happen?", which belongs to
Reasoning. Constitution I1 requires that no execution occurs without a policy
decision recorded before it; these are the types that decision is recorded as.

Risk is *computed from declared properties*, never inferred from resource
names. ``RiskFactors`` therefore has no field that accepts a name to
pattern-match against. See ``contracts.configuration.ResourceDeclaration`` for
where criticality actually comes from, and V7 in the Phase 1 compliance report
for why this matters.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

from backend.contracts._contract import Contract
from backend.contracts.errors import ContractViolation
from backend.contracts.execution import SideEffectClass

__all__ = [
    "RiskLevel",
    "PolicyEffect",
    "ObligationKind",
    "Obligation",
    "RiskFactors",
    "RiskClassification",
    "PolicyDecision",
]


class RiskLevel(str, Enum):
    """Ordered severity of an action's potential consequence."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

    @property
    def rank(self) -> int:
        return _RISK_RANK[self]

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, RiskLevel):
            return NotImplemented
        return self.rank < other.rank

    def __le__(self, other: object) -> bool:
        if not isinstance(other, RiskLevel):
            return NotImplemented
        return self.rank <= other.rank

    def __gt__(self, other: object) -> bool:
        if not isinstance(other, RiskLevel):
            return NotImplemented
        return self.rank > other.rank

    def __ge__(self, other: object) -> bool:
        if not isinstance(other, RiskLevel):
            return NotImplemented
        return self.rank >= other.rank


_RISK_RANK = {
    RiskLevel.LOW: 0,
    RiskLevel.MEDIUM: 1,
    RiskLevel.HIGH: 2,
    RiskLevel.CRITICAL: 3,
}


class PolicyEffect(str, Enum):
    """The three possible answers to "may this happen?"."""

    ALLOW = "allow"
    DENY = "deny"
    REQUIRE_APPROVAL = "require_approval"

    @property
    def permits_immediate_execution(self) -> bool:
        return self is PolicyEffect.ALLOW


class ObligationKind(str, Enum):
    """Conditions attached to an ALLOW.

    Constitution S8: policy "returns obligations, not just verdicts". An
    allow-with-obligations is common and materially different from a bare allow.
    """

    NOTIFY_OWNER = "notify_owner"
    RECORD_JUSTIFICATION = "record_justification"
    LIMIT_RATE = "limit_rate"
    REQUIRE_DRY_RUN = "require_dry_run"
    POST_EXECUTION_REVIEW = "post_execution_review"


@dataclass(frozen=True)
class Obligation(Contract):
    """A condition a caller must satisfy for an ALLOW to remain valid."""

    CONTRACT_NAME = "cortexprime.policy.obligation"

    kind: ObligationKind
    detail: Optional[str] = None

    def __post_init__(self) -> None:
        if not isinstance(self.kind, ObligationKind):
            raise ContractViolation("kind must be an ObligationKind")


@dataclass(frozen=True)
class RiskFactors(Contract):
    """The declared inputs to risk classification.

    Every field is an explicit declaration. There is deliberately no
    ``resource_name`` field: inferring criticality from a name is forbidden
    (Constitution S8 "Risk Classification"), and the way to make a forbidden
    practice impossible is to omit the input it would require.

    ``resource_criticality`` is Optional because policy must be able to
    distinguish "declared low" from "not declared". Governance fails closed on
    the latter -- absence is not permission.
    """

    CONTRACT_NAME = "cortexprime.policy.risk_factors"

    side_effect_class: SideEffectClass
    environment: str
    resource_count: int
    reversible: bool
    resource_criticality: Optional[RiskLevel] = None
    confidence: Optional[float] = None

    def __post_init__(self) -> None:
        if not isinstance(self.side_effect_class, SideEffectClass):
            raise ContractViolation("side_effect_class must be a SideEffectClass")
        if not isinstance(self.environment, str) or not self.environment.strip():
            raise ContractViolation("environment must be a non-blank string")
        if not isinstance(self.resource_count, int) or self.resource_count < 1:
            raise ContractViolation("resource_count must be a positive integer")
        if self.confidence is not None and not 0.0 <= self.confidence <= 1.0:
            raise ContractViolation("confidence must be between 0.0 and 1.0")

    @property
    def criticality_declared(self) -> bool:
        return self.resource_criticality is not None


@dataclass(frozen=True)
class RiskClassification(Contract):
    """A computed risk level together with the factors that produced it.

    Carrying the factors alongside the level is what makes a classification
    auditable: a reviewer can recompute it rather than trusting it
    (Constitution P10).
    """

    CONTRACT_NAME = "cortexprime.policy.risk_classification"

    level: RiskLevel
    factors: RiskFactors
    rationale: str

    def __post_init__(self) -> None:
        if not isinstance(self.level, RiskLevel):
            raise ContractViolation("level must be a RiskLevel")
        if not isinstance(self.rationale, str) or not self.rationale.strip():
            raise ContractViolation(
                "rationale must explain how the level was derived; an unexplained "
                "classification is not auditable"
            )


@dataclass(frozen=True)
class PolicyDecision(Contract):
    """The recorded answer to "may this happen?" -- Constitution I1.

    Persisted *before* the execution it governs. A decision with
    ``PolicyEffect.DENY`` and no reason is rejected: an unexplained denial is
    indistinguishable from a bug.
    """

    CONTRACT_NAME = "cortexprime.policy.decision"

    decision_id: str
    execution_key: str
    effect: PolicyEffect
    risk: RiskClassification
    decided_at: datetime
    policy_version: str
    obligations: tuple[Obligation, ...] = field(default_factory=tuple)
    reason: Optional[str] = None

    def __post_init__(self) -> None:
        if not isinstance(self.decision_id, str) or not self.decision_id.strip():
            raise ContractViolation("decision_id must be a non-blank string")
        if not isinstance(self.effect, PolicyEffect):
            raise ContractViolation("effect must be a PolicyEffect")
        if self.decided_at.tzinfo is None:
            raise ContractViolation("decided_at must be timezone-aware")
        if not isinstance(self.policy_version, str) or not self.policy_version.strip():
            raise ContractViolation(
                "policy_version must identify the ruleset used; a decision that cannot "
                "be reproduced is not auditable"
            )
        if not isinstance(self.obligations, tuple):
            raise ContractViolation("obligations must be a tuple (contracts are immutable)")
        if self.effect is PolicyEffect.DENY and not (self.reason or "").strip():
            raise ContractViolation("a denial must state a reason")
        if self.effect is not PolicyEffect.ALLOW and self.obligations:
            raise ContractViolation(
                "obligations qualify an allow; attach them to ALLOW decisions only"
            )
