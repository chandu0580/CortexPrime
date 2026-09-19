"""The governed remediation vocabulary — Phase 11.4 (ADR-124).

Owner: BC-6 Governance, consumed by composition. Level-0 like every contract:
no hashing, no JSON, no I/O. Digests are computed by the platform in the
application layer and carried here as values.

What this module holds
----------------------
* ``RemediationPlan`` -- ONE explicit, typed plan for ONE action against ONE
  exactly bound resource. Every field is filled by deterministic platform code
  from a schema-validated proposal and fresh governed evidence. There is no
  field a model's text can populate as authority: the plan's ``authority`` is
  decided by the autonomy policy and the approval authority, and its
  ``action_digest`` is the platform's canonical approval digest over the exact
  parameters that will be dispatched.
* ``ProposalDecision`` -- what the platform decided about a proposal it would
  NOT plan: rejected (malformed, unknown capability, outside the incident's
  scope, unsupported by the diagnosis) or prohibited (an action class the
  platform does not perform autonomously or at all). Recorded, never executed.
* ``RemediationStage`` / ``RemediationOutcome`` -- the lifecycle vocabulary the
  append-only remediation events use, and the honest final outcomes. There is
  no bare "SUCCESS": an executed action is only ``RESOLVED`` when independent
  verification of the world says so.

What it deliberately does not hold
----------------------------------
No command, no shell, no patch, no YAML, no URL, no credential. A plan names a
typed action (``deployment.rollback``) and scalars; the contained executor
constructs the API operation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Mapping, Optional

from backend.contracts._contract import Contract, freeze_mapping
from backend.contracts.errors import ContractViolation
from backend.contracts.policy import RiskClassification

__all__ = [
    "ReversibilityClass", "PlanAuthority", "RemediationStage", "RemediationOutcome",
    "ResourceTarget", "BlastRadius", "VerificationCriterion", "RollbackStrategy",
    "RemediationPlan", "ProposalDecision", "TERMINAL_STAGES",
]


def _req(value: Any, label: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ContractViolation(f"{label} is required")


class ReversibilityClass(str, Enum):
    """L10's three classes (Constitution §14), carried on the plan.

    ``REVERSIBLE``: a declared inverse fully restores the prior state.
    ``COMPENSABLE``: a declared compensation restores the declared state and
    leaves history behind (new revision numbers, replaced pods) -- and it was
    verified available for THIS action. ``IRREVERSIBLE``: neither.
    """

    REVERSIBLE = "reversible"
    COMPENSABLE = "compensable"
    IRREVERSIBLE = "irreversible"


class PlanAuthority(str, Enum):
    """How the platform decided this plan may proceed. Decided by the autonomy
    policy and the approval authority; never by a model."""

    AUTONOMOUS = "autonomous"
    """Earned delegated autonomy under an explicit versioned policy; executes
    on a policy-decided approval recorded in the one approval authority."""
    HUMAN_APPROVAL = "human_approval"
    """A human holding scoped approver authority must approve this exact action."""
    RECOMMENDATION_ONLY = "recommendation_only"
    """No execution path: the proposal came from the deterministic fallback, or
    the platform will not act on it without a model-backed, validated plan."""


class RemediationStage(str, Enum):
    PLANNED = "planned"
    PROPOSAL_REJECTED = "proposal_rejected"
    PROHIBITED = "prohibited"
    RECOMMENDATION_ONLY = "recommendation_only"
    AUTONOMY_DECIDED = "autonomy_decided"
    APPROVAL_REQUESTED = "approval_requested"
    APPROVAL_GRANTED = "approval_granted"
    APPROVAL_DENIED = "approval_denied"
    APPROVAL_EXPIRED = "approval_expired"
    STALE = "stale"
    EXECUTION_REFUSED = "execution_refused"
    EXECUTING = "executing"
    EXECUTED = "executed"
    EXECUTION_FAILED = "execution_failed"
    EXECUTION_UNKNOWN = "execution_unknown"
    DUPLICATE_SUPPRESSED = "duplicate_suppressed"
    VERIFIED = "verified"
    NO_EFFECT_CONFIRMED = "no_effect_confirmed"
    """The executor reported failure and independent verification confirmed the
    world did not change: an honest execution failure, confirmed -- not a
    remediation that ran and failed verification."""
    VERIFICATION_FAILED = "verification_failed"
    VERIFICATION_INSUFFICIENT = "verification_insufficient"
    DISCREPANCY = "discrepancy"
    RECOVERY_DECIDED = "recovery_decided"
    ESCALATED = "escalated"
    LEARNED = "learned"
    CLOSED = "closed"


#: Stages after which a plan performs nothing further on its own.
TERMINAL_STAGES = frozenset({
    RemediationStage.PROPOSAL_REJECTED, RemediationStage.PROHIBITED,
    RemediationStage.RECOMMENDATION_ONLY, RemediationStage.APPROVAL_DENIED,
    RemediationStage.APPROVAL_EXPIRED, RemediationStage.STALE,
    RemediationStage.EXECUTION_REFUSED, RemediationStage.ESCALATED,
    RemediationStage.CLOSED,
})


class RemediationOutcome(str, Enum):
    """The honest final outcomes. ``RESOLVED`` requires independent verification."""

    RESOLVED = "resolved"
    VERIFICATION_FAILED = "verification_failed"
    EXECUTION_FAILED = "execution_failed"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    NOT_EXECUTED = "not_executed"
    ESCALATED = "escalated"


@dataclass(frozen=True)
class ResourceTarget(Contract):
    """One exactly bound resource. Never "production", never a selector."""

    CONTRACT_NAME = "cortexprime.remediation.resource_target"

    tenant_id: str
    cluster_ref: str
    namespace: str
    kind: str
    name: str
    uid: str
    generation: int
    current_revision: int
    current_template_digest: str

    def __post_init__(self) -> None:
        for label in ("tenant_id", "cluster_ref", "namespace", "kind", "name", "uid",
                      "current_template_digest"):
            _req(getattr(self, label), label)
        for label in ("namespace", "name"):
            value = getattr(self, label)
            for bad in ("*", ",", " ", "/", "=", "\n", "..", "%", "?", "&"):
                if bad in value:
                    raise ContractViolation(f"{label} names more than one resource ({bad!r})")
        for label in ("generation", "current_revision"):
            value = getattr(self, label)
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ContractViolation(f"{label} must be a positive integer")

    @property
    def subject_ref(self) -> str:
        return f"kubernetes:{self.kind.lower()}:{self.namespace}/{self.name}"


@dataclass(frozen=True)
class BlastRadius(Contract):
    """What the action touches, stated from the target's own declared shape."""

    CONTRACT_NAME = "cortexprime.remediation.blast_radius"

    scope: str
    resource_count: int
    namespace: str
    replicas: int
    pods_replaced: int
    persistent_volumes: bool
    production: bool
    description: str

    def __post_init__(self) -> None:
        _req(self.scope, "scope")
        _req(self.description, "description")
        if self.resource_count < 1:
            raise ContractViolation("resource_count must be positive")


@dataclass(frozen=True)
class VerificationCriterion(Contract):
    """One condition the INDEPENDENT verifier checks after the action."""

    CONTRACT_NAME = "cortexprime.remediation.verification_criterion"

    name: str
    predicate: str
    expected: Mapping[str, Any]
    observed_by: str
    window_seconds: int

    def __post_init__(self) -> None:
        _req(self.name, "name")
        _req(self.predicate, "predicate")
        _req(self.observed_by, "observed_by")
        object.__setattr__(self, "expected", freeze_mapping(self.expected))
        if self.window_seconds < 1:
            raise ContractViolation("window_seconds must be positive")


@dataclass(frozen=True)
class RollbackStrategy(Contract):
    """How the action itself would be compensated, and whether it can be."""

    CONTRACT_NAME = "cortexprime.remediation.rollback_strategy"

    kind: str                      # "compensating_rollback" | "none"
    action: Optional[str]
    target_revision: Optional[int]
    target_template_digest: Optional[str]
    available: bool
    verified_by: str
    note: str

    def __post_init__(self) -> None:
        _req(self.kind, "kind")
        _req(self.verified_by, "verified_by")
        _req(self.note, "note")
        if self.available and not (self.action and self.target_revision and self.target_template_digest):
            raise ContractViolation("an available compensation must name its action, revision and template")


@dataclass(frozen=True)
class RemediationPlan(Contract):
    """ONE governed, typed, digest-bound remediation (mandate §7)."""

    CONTRACT_NAME = "cortexprime.remediation.plan"

    plan_id: str
    incident_ref: str
    investigation_ref: str
    tenant_id: str
    target: ResourceTarget
    diagnosis_ref: str
    diagnosis: str
    evidence_refs: tuple[str, ...]
    action: str
    capability_ref: str
    operation: str
    parameters: Mapping[str, Any]
    risk: RiskClassification
    reversibility: ReversibilityClass
    blast_radius: BlastRadius
    expected_state: Mapping[str, Any]
    verification_criteria: tuple[VerificationCriterion, ...]
    rollback_strategy: RollbackStrategy
    timeout_seconds: int
    approval_requirement: str
    authority: PlanAuthority
    authority_reason: str
    action_digest: str
    policy_version: str
    principal_id: str
    proposal_source: str
    proposal_digest: str
    created_at: datetime
    autonomy_decision_id: Optional[str] = None
    target_health_evidence: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        for label in ("plan_id", "incident_ref", "investigation_ref", "tenant_id", "diagnosis_ref",
                      "diagnosis", "action", "capability_ref", "operation", "approval_requirement",
                      "authority_reason", "action_digest", "policy_version", "principal_id",
                      "proposal_source", "proposal_digest"):
            _req(getattr(self, label), label)
        if not isinstance(self.target, ResourceTarget):
            raise ContractViolation("target must be a ResourceTarget")
        if self.target.tenant_id != self.tenant_id:
            raise ContractViolation("a plan's target belongs to the plan's tenant or the plan does not exist")
        if not isinstance(self.evidence_refs, tuple) or not self.evidence_refs:
            raise ContractViolation("a plan with no evidence is an opinion, not a plan")
        if not isinstance(self.risk, RiskClassification):
            raise ContractViolation("risk must be the platform's RiskClassification")
        if not isinstance(self.reversibility, ReversibilityClass):
            raise ContractViolation("reversibility must be a ReversibilityClass")
        if not isinstance(self.authority, PlanAuthority):
            raise ContractViolation("authority must be a PlanAuthority")
        if not self.verification_criteria:
            raise ContractViolation("a mutating plan without verification criteria cannot be held to anything")
        if self.timeout_seconds < 1:
            raise ContractViolation("timeout_seconds must be positive")
        if self.authority is PlanAuthority.AUTONOMOUS and self.reversibility is ReversibilityClass.IRREVERSIBLE:
            raise ContractViolation("an irreversible action always faces a fresh human (L10); it is never autonomous")
        if self.created_at.tzinfo is None:
            raise ContractViolation("created_at must be timezone-aware")
        object.__setattr__(self, "parameters", freeze_mapping(self.parameters))
        object.__setattr__(self, "expected_state", freeze_mapping(self.expected_state))

    @property
    def subject_ref(self) -> str:
        return self.target.subject_ref


@dataclass(frozen=True)
class ProposalDecision(Contract):
    """What the platform decided about a proposal it did not turn into a plan."""

    CONTRACT_NAME = "cortexprime.remediation.proposal_decision"

    proposal_digest: str
    incident_ref: str
    investigation_ref: str
    tenant_id: str
    stage: RemediationStage
    requested_action: str
    reasons: tuple[str, ...]
    proposal_source: str
    decided_at: datetime
    risk_level: Optional[str] = None
    recommendation: Optional[str] = None

    def __post_init__(self) -> None:
        for label in ("proposal_digest", "incident_ref", "investigation_ref", "tenant_id",
                      "proposal_source"):
            _req(getattr(self, label), label)
        if self.stage not in (RemediationStage.PROPOSAL_REJECTED, RemediationStage.PROHIBITED,
                              RemediationStage.RECOMMENDATION_ONLY):
            raise ContractViolation("a proposal decision is a rejection, a prohibition or a recommendation")
        if not self.reasons:
            raise ContractViolation("a refusal must state its reasons")
        if self.decided_at.tzinfo is None:
            raise ContractViolation("decided_at must be timezone-aware")
