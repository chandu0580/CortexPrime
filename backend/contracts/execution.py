"""Execution vocabulary.

Owner: BC-5 Execution.

Encodes Constitution P2 ("Reversibility Precedes Action") and P9 ("Blast Radius
Is Declared, Not Discovered") as type-level requirements. The central rule,
enforced in ``ExecutionContract.__post_init__``:

    An action without a declared inverse cannot be classified below
    ``irreversible_write``.

This makes reversibility a structural property rather than a convention. A
caller cannot forget to think about rollback, because the contract will not
construct without an answer.

These are declarations, not invocations. Nothing here performs work; BC-5 owns
that. See ADR-005.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Mapping, Optional

from backend.contracts._contract import Contract, freeze_mapping
from backend.contracts.errors import ContractViolation

__all__ = [
    "SideEffectClass",
    "EffectSemantics",
    "ExecutionEnvironment",
    "ExecutionStatus",
    "ExecutionScope",
    "ActionRef",
    "ExecutionContract",
    "ExecutionResult",
]


class SideEffectClass(str, Enum):
    """How consequential an action is. Drives risk classification and policy."""

    READ = "read"
    """Observes without changing anything. Safe to retry freely."""

    REVERSIBLE_WRITE = "reversible_write"
    """Changes state; a declared inverse fully restores the prior state."""

    IRREVERSIBLE_WRITE = "irreversible_write"
    """Changes state with no complete inverse. Requires explicit escalation."""

    DESTRUCTIVE = "destructive"
    """Removes state or capacity. The highest-consequence class."""

    @property
    def requires_inverse(self) -> bool:
        return self is SideEffectClass.REVERSIBLE_WRITE

    @property
    def mutates(self) -> bool:
        return self is not SideEffectClass.READ


class EffectSemantics(str, Enum):
    """Whether repeating an operation is safe.

    Owner: BC-5 Execution. Consumed by BC-8 Connectivity, which is why it lives
    here rather than inside either context -- a capability declares it at
    registration and the execution runtime acts on it, and neither may import
    the other.

    Distinct from ``SideEffectClass``, which says how *consequential* an action
    is. The two are independent: a reversible write can be violently
    non-idempotent, and a destructive delete can be perfectly idempotent if it
    is keyed.

    ``UNKNOWN`` must never be treated as safe. An undeclared repeat is the
    assumption that turns one production change into two, so every decision in
    the platform treats it as non-idempotent.
    """

    READ_ONLY = "read_only"
    IDEMPOTENT_WRITE = "idempotent_write"
    NON_IDEMPOTENT_WRITE = "non_idempotent_write"
    UNKNOWN = "unknown"

    @property
    def is_repeatable(self) -> bool:
        """Whether this may be run again without further authority."""
        return self in {EffectSemantics.READ_ONLY, EffectSemantics.IDEMPOTENT_WRITE}

    @property
    def mutates(self) -> bool:
        return self is not EffectSemantics.READ_ONLY

    @property
    def is_declared(self) -> bool:
        """Whether somebody actually said what repeating this does."""
        return self is not EffectSemantics.UNKNOWN


class ExecutionEnvironment(str, Enum):
    """Where work is being performed.

    Promoted to ``contracts/`` because a third context now needs it, which is
    exactly the condition ``connectivity.domain.contract.CapabilityEnvironment``
    named for promotion rather than a third copy. Its values are identical, so a
    composition root translates by value and never by table -- and a mistranslation
    would be a ``ValueError``, not a silently wrong environment.

    Deliberately an enum rather than the free-form string ``ExecutionScope.
    environment`` still carries. That field predates this and describes a declared
    blast radius; this one is compared against what a worker is *entitled* to run
    in, and ``prod`` / ``production`` / ``Production`` becoming three environments
    is not survivable for a comparison that decides whether something may touch
    production.
    """

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"

    @property
    def is_live(self) -> bool:
        return self is ExecutionEnvironment.PRODUCTION


class ExecutionStatus(str, Enum):
    """Terminal and non-terminal states of a single execution attempt."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    COMPENSATED = "compensated"
    REFUSED = "refused"
    """Blocked before invocation -- e.g. approval hash mismatch (I2)."""

    @property
    def is_terminal(self) -> bool:
        return self in {
            ExecutionStatus.SUCCEEDED,
            ExecutionStatus.FAILED,
            ExecutionStatus.COMPENSATED,
            ExecutionStatus.REFUSED,
        }


@dataclass(frozen=True)
class ExecutionScope(Contract):
    """The declared blast radius of an action (Constitution P9).

    Credentials are minted to this scope and expire with the execution (I5).
    An empty resource set is rejected: "this action touches nothing" is never
    true of an action worth running, and permitting it would let an unscoped
    execution acquire unscoped credentials.
    """

    CONTRACT_NAME = "cortexprime.execution.scope"

    system: str
    """The external system class, e.g. "docker", "github", "kubernetes"."""

    resources: tuple[str, ...]
    """Stable identifiers of the exact resources affected."""

    environment: str
    """Deployment environment, e.g. "production", "staging"."""

    def __post_init__(self) -> None:
        for label, value in (("system", self.system), ("environment", self.environment)):
            if not isinstance(value, str) or not value.strip():
                raise ContractViolation(f"{label} must be a non-blank string")
        if not isinstance(self.resources, tuple):
            raise ContractViolation("resources must be a tuple (contracts are immutable)")
        if not self.resources:
            raise ContractViolation(
                "resources must not be empty: an action must declare what it touches (P9)"
            )
        for resource in self.resources:
            if not isinstance(resource, str) or not resource.strip():
                raise ContractViolation("resource entries must be non-blank strings")


@dataclass(frozen=True)
class ActionRef(Contract):
    """A named, parameterized action a connector knows how to perform.

    ``parameters`` is the one deliberately opaque field in the contracts
    package: BC-8 owns each tool's parameter schema, and duplicating those
    schemas here would couple the vocabulary to every connector. It is frozen
    to a read-only mapping so the opacity does not cost immutability.
    """

    CONTRACT_NAME = "cortexprime.execution.action_ref"

    action_type: str
    parameters: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.action_type, str) or not self.action_type.strip():
            raise ContractViolation("action_type must be a non-blank string")
        object.__setattr__(self, "parameters", freeze_mapping(self.parameters))


@dataclass(frozen=True)
class ExecutionContract(Contract):
    """A complete, self-describing declaration of an action to be performed.

    Every field required by Constitution S6 "Execution Contract" is present and
    mandatory. The class refuses to construct if reversibility has not been
    considered.

    ``verification_criteria`` is required and non-empty by design: declaring
    success *before* execution is what prevents success being defined
    retroactively (Constitution S4 "Verification").
    """

    CONTRACT_NAME = "cortexprime.execution.contract"

    execution_key: str
    """Idempotency key. Two executions with the same key are the same execution."""

    action: ActionRef
    scope: ExecutionScope
    side_effect_class: SideEffectClass
    verification_criteria: tuple[str, ...]

    inverse: Optional[ActionRef] = None
    """The compensating action. Required for REVERSIBLE_WRITE; forbidden for READ."""

    required_capability: Optional[str] = None
    """Minimum capability a principal must hold. None means policy decides alone."""

    def __post_init__(self) -> None:
        if not isinstance(self.execution_key, str) or not self.execution_key.strip():
            raise ContractViolation("execution_key must be a non-blank string")
        if not isinstance(self.side_effect_class, SideEffectClass):
            raise ContractViolation("side_effect_class must be a SideEffectClass")
        if not isinstance(self.verification_criteria, tuple):
            raise ContractViolation("verification_criteria must be a tuple")
        if not self.verification_criteria:
            raise ContractViolation(
                "verification_criteria must not be empty: success is declared before "
                "execution, never after (Constitution S4)"
            )

        # Constitution P2 -- the load-bearing rule of this module.
        if self.side_effect_class is SideEffectClass.REVERSIBLE_WRITE and self.inverse is None:
            raise ContractViolation(
                "an action classified reversible_write must declare its inverse; "
                "if no inverse exists, classify it irreversible_write (Constitution P2)"
            )
        if self.side_effect_class is SideEffectClass.READ and self.inverse is not None:
            raise ContractViolation("a read action must not declare an inverse")

    @property
    def requires_approval_by_default(self) -> bool:
        """Whether this action is inherently approval-worthy.

        Advisory vocabulary for callers constructing policy input. Governance
        makes the actual decision (I1); this never substitutes for it.
        """
        return self.side_effect_class in {
            SideEffectClass.IRREVERSIBLE_WRITE,
            SideEffectClass.DESTRUCTIVE,
        }


@dataclass(frozen=True)
class ExecutionResult(Contract):
    """The outcome of one execution attempt.

    ``detail`` is opaque and frozen. ``failure_reason`` is required whenever the
    status is FAILED or REFUSED: a failure without a stated reason is not
    auditable (Constitution S8).
    """

    CONTRACT_NAME = "cortexprime.execution.result"

    execution_key: str
    status: ExecutionStatus
    started_at: datetime
    completed_at: Optional[datetime] = None
    failure_reason: Optional[str] = None
    detail: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.status, ExecutionStatus):
            raise ContractViolation("status must be an ExecutionStatus")
        if self.status.is_terminal and self.completed_at is None:
            raise ContractViolation(f"a {self.status.value} execution must record completed_at")
        if self.completed_at is not None and self.completed_at < self.started_at:
            raise ContractViolation("completed_at must not precede started_at")
        needs_reason = self.status in {ExecutionStatus.FAILED, ExecutionStatus.REFUSED}
        if needs_reason and not (self.failure_reason or "").strip():
            raise ContractViolation(f"a {self.status.value} execution must state failure_reason")
        object.__setattr__(self, "detail", freeze_mapping(self.detail))
