"""The capability bridge — Phase 9.1 (ADR-081).

The governed execution plane declares WHAT an operation is (`ProviderOperationSpec`
+ `CapabilityContract`: method, path, side-effect class, effect semantics). The
Phase-8 intelligence plane decides HOW INDEPENDENTLY CortexPrime may perform it
(`AutonomyPolicy` over `Capability` + `RiskClassification`). Those two planes were
decoupled (Phase 9.0 §5). This contract is the **bridge** — a `CapabilityProfile`
binds a governed operation to its risk, reversibility, verification requirement,
and autonomy ceiling BY REUSE of the existing types, never by inventing a second
capability model.

It keeps the four concepts distinct (Part B):
  * CAPABILITY — what the operation IS (side-effect class, resource scope);
  * PERMISSION — whether policy allows it (the governed `PolicyEffect`, elsewhere);
  * AUTHORIZATION — whether THIS principal may (the governed authorization chain);
  * AUTONOMY — how independently the platform may (the `autonomy_ceiling` here,
    which `AutonomyPolicy` caps against).

Read-only guarantee (Part D): a READ profile must have an autonomy ceiling of at
most A1 and require no verification; a mutating profile MUST require independent
verification. This makes "a read is never an action, and a write is never
unverifiable" a construction-time invariant, not a convention.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from backend.contracts._contract import Contract
from backend.contracts.errors import ContractViolation
from backend.contracts.execution import EffectSemantics, SideEffectClass
from backend.contracts.policy import RiskClassification
from backend.contracts.intelligence.investigation import AutonomyLevel
from backend.contracts.intelligence.autonomy import Capability

__all__ = ["VerificationRequirement", "CapabilityProfile"]


class VerificationRequirement(str, Enum):
    """What independent verification a completed operation requires before its
    outcome may be trusted (Part P). A read requires none; a write must be
    independently read back (never verified by the same reasoning that proposed it)."""

    NONE = "none"                                  # read-only: nothing to verify
    INDEPENDENT_READBACK = "independent_readback"  # write: independent world read-back
    HUMAN_ADJUDICATION = "human_adjudication"      # write: human adjudication required


def _req_str(value, label: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ContractViolation(f"{label} is required")


@dataclass(frozen=True)
class CapabilityProfile(Contract):
    """The declarative bridge for one governed operation. All fields reuse existing
    types; nothing here is a new risk/autonomy vocabulary."""

    CONTRACT_NAME = "cortexprime.intelligence.capability_profile"

    capability_ref: str
    provider: str
    operation: str
    side_effect_class: SideEffectClass
    effect_semantics: EffectSemantics
    risk: RiskClassification
    autonomy_ceiling: AutonomyLevel
    verification_requirement: VerificationRequirement
    resource_scope: str                 # e.g. "namespace", "cluster", "deployment"
    reversible: bool
    timeout_seconds: float
    policy_version: str
    compensation: Optional[str] = None
    """Phase 11.4 (ADR-124): the capability that COMPENSATES this one (L10's
    compensable class), declared on the contract. A declaration, not a guarantee:
    whether the compensation is available for a particular action is verified by
    the platform at plan time and again as a precondition of execution."""

    def __post_init__(self) -> None:
        for name in ("capability_ref", "provider", "operation", "resource_scope",
                     "policy_version"):
            _req_str(getattr(self, name), name)
        if not isinstance(self.side_effect_class, SideEffectClass):
            raise ContractViolation("side_effect_class must be a SideEffectClass")
        if not isinstance(self.effect_semantics, EffectSemantics):
            raise ContractViolation("effect_semantics must be an EffectSemantics")
        if not isinstance(self.risk, RiskClassification):
            raise ContractViolation("risk must be a RiskClassification (deterministic, reused)")
        if not isinstance(self.autonomy_ceiling, AutonomyLevel):
            raise ContractViolation("autonomy_ceiling must be an AutonomyLevel")
        if not isinstance(self.verification_requirement, VerificationRequirement):
            raise ContractViolation("verification_requirement must be a VerificationRequirement")
        if not isinstance(self.reversible, bool):
            raise ContractViolation("reversible must be a bool")
        if not isinstance(self.timeout_seconds, (int, float)) or self.timeout_seconds <= 0:
            raise ContractViolation("timeout_seconds must be positive")

        # Read-only guarantee (Part D): a READ is never an action and never needs
        # verification; a write is never unverifiable.
        if self.side_effect_class is SideEffectClass.READ:
            if self.autonomy_ceiling.rank > AutonomyLevel.A1_INVESTIGATE.rank:
                raise ContractViolation(
                    "a READ capability's autonomy ceiling may be at most A1 "
                    "(observe/investigate); a read is never an autonomous action")
            if self.verification_requirement is not VerificationRequirement.NONE:
                raise ContractViolation(
                    "a READ capability requires no verification (nothing to verify)")
            if not self.reversible:
                raise ContractViolation("a READ is trivially reversible; reversible must be True")
            if self.compensation is not None:
                raise ContractViolation("a READ changes nothing and declares no compensation")
        else:  # a mutating operation
            if self.verification_requirement is VerificationRequirement.NONE:
                raise ContractViolation(
                    "a mutating capability MUST require independent verification "
                    "(a write that cannot be verified is unsuitable for governed action)")

    @property
    def is_read_only(self) -> bool:
        return self.side_effect_class is SideEffectClass.READ

    def to_capability(self, *, compensation_verified: bool = False) -> Capability:
        """Bridge to the Phase-8 ``Capability`` the ``AutonomyPolicy`` consumes —
        reusing the existing type, not duplicating it.

        ``compensable`` is True only when a compensation is DECLARED and the
        caller states it VERIFIED availability for the action being decided. The
        default is False, so a caller that verified nothing gets the stricter
        irreversible treatment."""
        return Capability(
            capability_ref=self.capability_ref, operation=self.operation,
            resource_class=self.resource_scope, side_effect_class=self.side_effect_class,
            reversible=self.reversible,
            compensable=bool(self.compensation) and bool(compensation_verified)
            and self.side_effect_class is not SideEffectClass.DESTRUCTIVE)

    def to_dict(self) -> dict:
        return {
            "capability_ref": self.capability_ref, "provider": self.provider,
            "operation": self.operation, "side_effect_class": self.side_effect_class.value,
            "effect_semantics": self.effect_semantics.value,
            "risk": {"level": self.risk.level.value, "reversible": self.risk.factors.reversible,
                     "environment": self.risk.factors.environment},
            "autonomy_ceiling": self.autonomy_ceiling.value,
            "verification_requirement": self.verification_requirement.value,
            "resource_scope": self.resource_scope, "reversible": self.reversible,
            "timeout_seconds": self.timeout_seconds, "policy_version": self.policy_version,
            "compensation": self.compensation,
        }
