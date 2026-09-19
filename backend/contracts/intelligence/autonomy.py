"""Controlled autonomy & earned authority — Phase 8.8 (ADR-079).

Autonomy is delegated authority, never a capability. The platform decides — from
independently-evaluated evidence — under exactly which conditions CortexPrime has
earned the right to act without another human approval, and a deterministic
mechanism takes that right away the moment the evidence no longer supports it. The
model is never an input to this decision and can never appear on the authority side
of the boundary.

These are reference-only value contracts. They separate three concepts (Part B):
  * CAPABILITY — what the system technically CAN do (an operation on a resource);
  * PERMISSION — what policy currently ALLOWS (a PolicyEffect over a capability);
  * AUTONOMY — how independently it may exercise a permission (the A0–A4 level).
A system may legally be high-capability, low-permission, low-autonomy.

There is deliberately NO global trust score (Part E): reliability, assurance,
authority, risk, experience, and calibration stay separate typed inputs, and the
output is a typed ``AutonomyDecision`` — an explainable verdict, never a number.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

from backend.contracts._contract import Contract
from backend.contracts.errors import ContractViolation
from backend.contracts.tenant import TenantRef
from backend.contracts.execution import SideEffectClass
from backend.contracts.policy import RiskClassification, RiskLevel
from backend.contracts.intelligence.investigation import AutonomyLevel

__all__ = [
    "Capability",
    "AutonomyScope",
    "AutonomyEligibility",
    "ApprovalRequirement",
    "AutonomyDecision",
    "AutonomyPolicyConfig",
    "CircuitBreakerConfig",
    "EmergencyStopState",
    "BreakerTrip",
]


def _req_str(value, label: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ContractViolation(f"{label} is required")


@dataclass(frozen=True)
class Capability(Contract):
    """WHAT the system can technically do — an operation on a resource class. A
    capability is not a permission and not an autonomy grant; it carries its own
    consequence class and whether it declares a complete inverse (reversibility)."""

    CONTRACT_NAME = "cortexprime.intelligence.capability"

    capability_ref: str
    operation: str                 # e.g. "restart", "rollback", "scale"
    resource_class: str            # e.g. "deployment", "database"
    side_effect_class: SideEffectClass
    reversible: bool               # a declared, verified inverse exists
    compensable: bool = False
    """Phase 11.4 (ADR-124): L10's middle class. True only when the capability
    DECLARES a compensation (another governed action that restores the declared
    state, leaving history behind) AND the platform VERIFIED, for this action,
    that the compensation is available. A compensable action is not reversible:
    it stays ``reversible=False``. Default False, so every existing capability
    keeps exactly the autonomy behaviour it had."""

    def __post_init__(self) -> None:
        for name in ("capability_ref", "operation", "resource_class"):
            _req_str(getattr(self, name), name)
        if not isinstance(self.side_effect_class, SideEffectClass):
            raise ContractViolation("side_effect_class must be a SideEffectClass")
        if not isinstance(self.compensable, bool):
            raise ContractViolation("compensable must be a bool")
        if self.compensable and self.side_effect_class is SideEffectClass.DESTRUCTIVE:
            raise ContractViolation(
                "a DESTRUCTIVE capability is never compensable: removing state or capacity "
                "is the class no compensation restores")

    def to_dict(self) -> dict:
        return {"capability_ref": self.capability_ref, "operation": self.operation,
                "resource_class": self.resource_class,
                "side_effect_class": self.side_effect_class.value, "reversible": self.reversible,
                "compensable": self.compensable}


@dataclass(frozen=True)
class AutonomyScope(Contract):
    """WHERE an autonomy decision applies (Part F). Autonomy is never universal:
    a grant is 'A4 is permitted for THIS capability under THESE conditions', never
    'the agent is A4'."""

    CONTRACT_NAME = "cortexprime.intelligence.autonomy_scope"

    tenant: TenantRef
    environment: str
    service: str
    capability_ref: str
    operation: str
    resource_class: str

    def __post_init__(self) -> None:
        if not isinstance(self.tenant, TenantRef):
            raise ContractViolation("tenant must be a TenantRef; autonomy is tenant-scoped")
        for name in ("environment", "service", "capability_ref", "operation", "resource_class"):
            _req_str(getattr(self, name), name)

    @property
    def key(self) -> str:
        return "|".join((self.tenant.tenant_id, self.environment, self.service,
                         self.capability_ref, self.operation, self.resource_class))

    def to_dict(self) -> dict:
        return {"tenant": self.tenant.tenant_id, "environment": self.environment,
                "service": self.service, "capability_ref": self.capability_ref,
                "operation": self.operation, "resource_class": self.resource_class}


class AutonomyEligibility(str, Enum):
    """The typed autonomy verdict (Part E) — never a global trust score. Each value
    is an explainable, distinct reason the requested level was or was not granted."""

    ELIGIBLE = "eligible"
    INELIGIBLE = "ineligible"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    STALE_EVIDENCE = "stale_evidence"
    DRIFT_DETECTED = "drift_detected"
    POLICY_FORBIDDEN = "policy_forbidden"
    ASSURANCE_INSUFFICIENT = "assurance_insufficient"
    HUMAN_APPROVAL_REQUIRED = "human_approval_required"
    EMERGENCY_STOPPED = "emergency_stopped"
    CIRCUIT_OPEN = "circuit_open"


class ApprovalRequirement(str, Enum):
    """What must be presented to actually execute at the allowed level."""

    NONE = "none"                          # A4: policy-authorized, no per-action approval
    HUMAN_APPROVAL = "human_approval"      # A3: a digest-bound human APPROVED event
    POLICY_AUTHORIZATION = "policy_authorization"  # A4: an explicit policy authorization ref
    NOT_PERMITTED = "not_permitted"        # A0–A2: no autonomous action at all


class EmergencyStopState(str, Enum):
    """Platform-controlled stop lifecycle (Part M). Prevents NEW autonomous actions;
    never retroactively erases history."""

    RUNNING = "running"
    STOP_REQUESTED = "stop_requested"
    STOP_ACTIVE = "stop_active"
    DRAINING = "draining"
    STOPPED = "stopped"

    @property
    def blocks_new_actions(self) -> bool:
        return self in (EmergencyStopState.STOP_REQUESTED, EmergencyStopState.STOP_ACTIVE,
                        EmergencyStopState.DRAINING, EmergencyStopState.STOPPED)


@dataclass(frozen=True)
class AutonomyPolicyConfig(Contract):
    """The EXPLICIT, versioned autonomy policy — thresholds are configuration, never
    hidden constants (Part D/N). Every threshold is justified and auditable; changing
    one changes ``policy_version``. The per-blast-radius caps are the deterministic
    'A4 for low-blast, A1 for critical' policy (Part F/G)."""

    CONTRACT_NAME = "cortexprime.intelligence.autonomy_policy_config"

    policy_version: str
    # Calibration evidence required before ANY autonomous action (Part D/K).
    min_decided_outcomes: int = 8
    min_support_rate: float = 0.8
    min_assurance_coverage: float = 0.75
    require_no_drift: bool = True
    require_fresh_world: bool = True
    deny_on_world_conflict: bool = True
    # Reversibility: at or above this level an autonomous WRITE must be reversible (Part H).
    require_reversible_at_or_above: AutonomyLevel = AutonomyLevel.A3_APPROVED_ACTION
    # Phase 11.4 (ADR-124): whether a COMPENSABLE capability (declared compensation,
    # verified available for the action) may earn delegated autonomy instead of
    # being forced to a human by the reversibility gate. L10 names the fresh-human
    # rule for IRREVERSIBLE actions; compensable is its own class. OFF by default:
    # a deployment turns it on only in an explicit, versioned policy, and every
    # other gate (risk cap, calibration, assurance, drift, world, breaker, stop)
    # still applies. A DESTRUCTIVE capability is never compensable.
    compensable_autonomy: bool = False
    # Deterministic blast-radius caps: the maximum autonomy per RiskLevel (Part F/G).
    max_level_low: AutonomyLevel = AutonomyLevel.A4_AUTONOMOUS
    max_level_medium: AutonomyLevel = AutonomyLevel.A3_APPROVED_ACTION
    max_level_high: AutonomyLevel = AutonomyLevel.A2_RECOMMEND
    max_level_critical: AutonomyLevel = AutonomyLevel.A1_INVESTIGATE

    def __post_init__(self) -> None:
        _req_str(self.policy_version, "policy_version")
        if not 0.0 <= self.min_support_rate <= 1.0:
            raise ContractViolation("min_support_rate must be in [0,1]")
        if not 0.0 <= self.min_assurance_coverage <= 1.0:
            raise ContractViolation("min_assurance_coverage must be in [0,1]")
        if not isinstance(self.compensable_autonomy, bool):
            raise ContractViolation("compensable_autonomy must be a bool")
        for name in ("require_reversible_at_or_above", "max_level_low", "max_level_medium",
                     "max_level_high", "max_level_critical"):
            if not isinstance(getattr(self, name), AutonomyLevel):
                raise ContractViolation(f"{name} must be an AutonomyLevel")

    def cap_for_risk(self, level: RiskLevel) -> AutonomyLevel:
        return {RiskLevel.LOW: self.max_level_low, RiskLevel.MEDIUM: self.max_level_medium,
                RiskLevel.HIGH: self.max_level_high, RiskLevel.CRITICAL: self.max_level_critical}[level]


@dataclass(frozen=True)
class CircuitBreakerConfig(Contract):
    """Explicit circuit-breaker thresholds (Part N) — named triggers with configured
    counts, never hidden constants. Autonomy halts when any count crosses its
    threshold."""

    CONTRACT_NAME = "cortexprime.intelligence.circuit_breaker_config"

    max_action_failures: int = 2
    max_verification_failures: int = 1
    max_consecutive_refusals: int = 5
    trip_on_drift: bool = True
    trip_on_world_conflict: bool = True

    def evaluate(self, *, action_failures: int = 0, verification_failures: int = 0,
                 consecutive_refusals: int = 0, drift: bool = False,
                 world_conflict: bool = False) -> Optional["BreakerTrip"]:
        """Return a BreakerTrip if any configured threshold is crossed, else None."""
        if action_failures >= self.max_action_failures:
            return BreakerTrip(trigger="action_failure", count=action_failures,
                               threshold=self.max_action_failures,
                               reason=f"{action_failures} action failures >= {self.max_action_failures}")
        if verification_failures >= self.max_verification_failures:
            return BreakerTrip(trigger="verification_failure", count=verification_failures,
                               threshold=self.max_verification_failures,
                               reason=f"{verification_failures} verification failures >= "
                                      f"{self.max_verification_failures}")
        if consecutive_refusals >= self.max_consecutive_refusals:
            return BreakerTrip(trigger="consecutive_refusals", count=consecutive_refusals,
                               threshold=self.max_consecutive_refusals,
                               reason=f"{consecutive_refusals} consecutive refusals")
        if drift and self.trip_on_drift:
            return BreakerTrip(trigger="drift", count=1, threshold=1,
                               reason="calibration drift detected")
        if world_conflict and self.trip_on_world_conflict:
            return BreakerTrip(trigger="world_conflict", count=1, threshold=1,
                               reason="conflicting authoritative world evidence")
        return None


@dataclass(frozen=True)
class BreakerTrip(Contract):
    """A tripped circuit breaker — an explicit, auditable halt condition (Part N).
    The trigger is a named condition and the count that crossed the configured
    threshold; there are no hidden constants."""

    CONTRACT_NAME = "cortexprime.intelligence.breaker_trip"

    trigger: str                   # e.g. "verification_failure", "action_failure", "drift"
    count: int
    threshold: int
    reason: str

    def __post_init__(self) -> None:
        _req_str(self.trigger, "trigger")
        _req_str(self.reason, "reason")


@dataclass(frozen=True)
class AutonomyDecision(Contract):
    """The explainable, durable autonomy decision (Part J/Z). Computed by the
    platform from independent evidence; the model is never an input. It carries
    requested vs allowed vs effective level, the scope, the eligibility verdict, the
    evidence references (calibration/assurance/world/risk), the approval requirement,
    and the runtime versions it is bound to — enough to audit without ever inspecting
    model chain-of-thought."""

    CONTRACT_NAME = "cortexprime.intelligence.autonomy_decision"

    decision_id: str
    scope: AutonomyScope
    requested_level: AutonomyLevel
    allowed_level: AutonomyLevel
    effective_level: AutonomyLevel        # allowed, after downgrades (drift/conflict/breaker/stop)
    eligibility: AutonomyEligibility
    approval_requirement: ApprovalRequirement
    risk: RiskClassification
    reason: str
    decided_at: datetime
    policy_version: str
    model_identity: str
    harness_version: str
    reliability_ref: Optional[str] = None          # calibration result digest (advisory)
    assurance_ref: Optional[str] = None
    world_evidence_ref: Optional[str] = None
    calibration_dataset_digest: Optional[str] = None
    downgraded_from: Optional[str] = None          # allowed_level.value, if effective < allowed
    breaker: Optional[BreakerTrip] = None

    def __post_init__(self) -> None:
        _req_str(self.decision_id, "decision_id")
        _req_str(self.reason, "reason")   # never a vague "safety policy prevented action"
        _req_str(self.policy_version, "policy_version")
        _req_str(self.model_identity, "model_identity")
        _req_str(self.harness_version, "harness_version")
        if not isinstance(self.scope, AutonomyScope):
            raise ContractViolation("scope must be an AutonomyScope; autonomy is never universal")
        for name in ("requested_level", "allowed_level", "effective_level"):
            if not isinstance(getattr(self, name), AutonomyLevel):
                raise ContractViolation(f"{name} must be an AutonomyLevel")
        if not isinstance(self.eligibility, AutonomyEligibility):
            raise ContractViolation("eligibility must be an AutonomyEligibility")
        if not isinstance(self.approval_requirement, ApprovalRequirement):
            raise ContractViolation("approval_requirement must be an ApprovalRequirement")
        if not isinstance(self.risk, RiskClassification):
            raise ContractViolation("risk must be a RiskClassification (deterministic, not a model score)")
        # Effective can only be <= allowed (a downgrade), never a silent escalation.
        if self.effective_level.rank > self.allowed_level.rank:
            raise ContractViolation("effective_level may never exceed allowed_level (no escalation)")
        if self.allowed_level.rank > self.requested_level.rank:
            raise ContractViolation("allowed_level may never exceed requested_level")

    @property
    def permits_autonomous_action(self) -> bool:
        """True only when the effective level permits an action AND no human approval
        is outstanding for it (A4 policy-authorized). A3 still requires approval."""
        return (self.effective_level.permits_action()
                and self.approval_requirement in (ApprovalRequirement.NONE,
                                                  ApprovalRequirement.POLICY_AUTHORIZATION))

    def to_dict(self) -> dict:
        return {
            "decision_id": self.decision_id, "scope": self.scope.to_dict(),
            "requested_level": self.requested_level.value, "allowed_level": self.allowed_level.value,
            "effective_level": self.effective_level.value, "eligibility": self.eligibility.value,
            "approval_requirement": self.approval_requirement.value,
            "risk": {"level": self.risk.level.value, "rationale": self.risk.rationale,
                     "reversible": self.risk.factors.reversible,
                     "environment": self.risk.factors.environment},
            "reason": self.reason, "decided_at": self.decided_at.isoformat(),
            "policy_version": self.policy_version, "model_identity": self.model_identity,
            "harness_version": self.harness_version, "reliability_ref": self.reliability_ref,
            "assurance_ref": self.assurance_ref, "world_evidence_ref": self.world_evidence_ref,
            "calibration_dataset_digest": self.calibration_dataset_digest,
            "downgraded_from": self.downgraded_from,
            "breaker": self.breaker.to_dict() if self.breaker else None,
        }
