"""The contract every worker will implement, and what it may say back.

The request a worker receives has already been decided
--------------------------------------------------------
By the time this reaches a worker, the capability exists, is trusted, is
enabled, the principal is authorized, the operation is authorized, the digest
matches, and a binding was created and validated. A worker is handed the result
of all that and is asked to perform it.

So the request deliberately carries no registry, no policy engine, no resolver
and no discovery service. A worker cannot look up whether it is allowed to run,
because there is nothing in its hand to look it up with — which is the only way
to be sure it never decides.

The result a worker returns is facts, not conclusions
-------------------------------------------------------
``WorkerExecutionResult`` says what the worker observed. It does not say what
the run's state should become, whether to retry, or whether the node failed.
Those are Execution's to decide from the effect semantics, the failure class,
the attempt history and the retry policy (Phase 3.1).

That split matters most in the ambiguous case. A worker whose HTTP call timed
out knows one thing: it stopped waiting. It does not know whether the far side
applied the change. Reporting ``TIMEOUT`` lets Execution treat the outcome as
unknown; reporting ``FAILURE`` would assert something the worker cannot know.

UNKNOWN_OUTCOME is the honest default for confusion
-----------------------------------------------------
When a worker cannot classify what happened, the answer is ``UNKNOWN_OUTCOME``,
never ``SUCCESS`` and never ``FAILURE``. Both of those are claims. Only the
first is safe when nobody knows.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping, Optional

from backend.contracts.errors import ContractViolation
from backend.contracts.execution import EffectSemantics, ExecutionStatus, SideEffectClass
from backend.contracts.identity import PrincipalRef
from backend.contexts.execution.domain.bound_capability import BoundCapability
from backend.contexts.execution.domain.failure import FailureClass, FailureRecord
from backend.contexts.execution.domain.identifiers import AttemptId, ExecutionId
from backend.contexts.execution.domain.state import NodeState
from backend.contexts.execution.domain.worker import WorkerKind
from backend.platform.hashing import compute_digest

__all__ = [
    "WorkerOutcome",
    "WorkerExecutionRequest",
    "WorkerExecutionResult",
    "CancellationSupport",
]


class WorkerOutcome(str, Enum):
    """What a worker observed. Five answers, and they are not interchangeable."""

    SUCCESS = "success"
    """The work was performed and the worker can say so."""

    FAILURE = "failure"
    """It did not happen, and the worker knows it did not. A claim -- only
    correct when the far side actually refused."""

    UNKNOWN_OUTCOME = "unknown_outcome"
    """The worker cannot say whether it happened. Not a failure: an absence of
    knowledge, and the only honest answer after a lost response."""

    CANCELLATION = "cancellation"
    """Stopped on request. Operationally distinct from failing -- 'we called it
    off' and 'it broke' lead to different conversations."""

    TIMEOUT = "timeout"
    """The worker stopped waiting. Says when we gave up, never what the far side
    did, which is why it maps to ambiguity rather than to failure."""

    @property
    def is_success(self) -> bool:
        return self is WorkerOutcome.SUCCESS

    @property
    def outcome_is_known(self) -> bool:
        """Whether the external effect is settled.

        ``TIMEOUT`` is deliberately *not* known. A deadline is a fact about the
        caller, not about the callee.
        """
        return self in {
            WorkerOutcome.SUCCESS,
            WorkerOutcome.FAILURE,
            WorkerOutcome.CANCELLATION,
        }

    @property
    def default_failure_class(self) -> Optional[FailureClass]:
        """How this maps onto Phase 3.1's taxonomy when the worker says no more."""
        return {
            WorkerOutcome.FAILURE: FailureClass.EXTERNAL_SYSTEM_FAILURE,
            WorkerOutcome.UNKNOWN_OUTCOME: FailureClass.UNKNOWN_OUTCOME,
            WorkerOutcome.CANCELLATION: FailureClass.CANCELLATION,
            WorkerOutcome.TIMEOUT: FailureClass.TIMEOUT,
        }.get(self)

    @property
    def node_state(self) -> NodeState:
        """The node state Execution records. Ambiguity becomes UNKNOWN, not FAILED."""
        return {
            WorkerOutcome.SUCCESS: NodeState.SUCCEEDED,
            WorkerOutcome.FAILURE: NodeState.FAILED,
            WorkerOutcome.CANCELLATION: NodeState.FAILED,
            WorkerOutcome.UNKNOWN_OUTCOME: NodeState.UNKNOWN,
            WorkerOutcome.TIMEOUT: NodeState.UNKNOWN,
        }[self]


class CancellationSupport(str, Enum):
    """How much a worker can honestly promise about stopping.

    Exists because "cancelled" is routinely claimed on the strength of a signal
    having been sent. A worker that fired SIGTERM and did not wait has not
    stopped anything it can vouch for, and saying so is more useful than a
    reassuring lie.
    """

    NONE = "none"
    """Cannot be interrupted. Requests are refused rather than ignored."""

    BEST_EFFORT = "best_effort"
    """A stop was requested. Whether the work stopped is unknown -- which makes
    the outcome ambiguous, not cancelled."""

    GUARANTEED = "guaranteed"
    """The worker can confirm the work stopped and left nothing running."""

    @property
    def proves_stopped(self) -> bool:
        return self is CancellationSupport.GUARANTEED


@dataclass(frozen=True)
class WorkerExecutionRequest:
    """Everything a worker needs, and deliberately nothing more."""

    execution_id: ExecutionId
    attempt_id: AttemptId
    attempt_number: int
    node_id: str
    worker_kind: WorkerKind

    tenant_id: str
    principal: PrincipalRef
    binding: BoundCapability
    """Mandatory. There is no path to a worker that does not carry one."""

    payload: Mapping[str, Any] = field(default_factory=dict)
    """Validated input. Validation happens before this object exists -- an
    adapter must not reinterpret caller data on the way through."""

    deadline_seconds: Optional[int] = None
    idempotency_key: Optional[str] = None
    execution_key: Optional[str] = None
    correlation_id: Optional[str] = None
    causation_id: Optional[str] = None
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if not isinstance(self.binding, BoundCapability):
            raise ContractViolation(
                "a worker request must carry the capability binding it is "
                "performing; without one the worker cannot be told what it was "
                "authorized to do, and nothing downstream can check it"
            )
        if not isinstance(self.worker_kind, WorkerKind):
            raise ContractViolation("worker_kind must be a WorkerKind")
        if not isinstance(self.principal, PrincipalRef):
            raise ContractViolation("principal must be a PrincipalRef")
        if self.attempt_number < 1:
            raise ContractViolation("attempt numbers start at 1")
        if self.tenant_id != self.binding.tenant_id:
            raise ContractViolation(
                "the request tenant and the binding tenant disagree; one of them "
                "is somebody else's, and guessing which would be the whole breach"
            )
        if self.principal.principal_id != self.binding.principal_id:
            raise ContractViolation(
                "the request principal and the binding principal disagree; a "
                "worker does not get to run as somebody the binding did not name"
            )
        if self.deadline_seconds is not None and self.deadline_seconds < 1:
            raise ContractViolation("deadline_seconds must be at least 1")

    @property
    def is_retry(self) -> bool:
        return self.attempt_number > 1

    @property
    def mutates(self) -> bool:
        return self.binding.mutates

    @property
    def effect_semantics(self) -> EffectSemantics:
        return self.binding.effect_semantics

    def to_dict(self) -> dict:
        """No payload. Inputs may carry customer data and this is logged."""
        return {
            "execution_id": str(self.execution_id),
            "attempt_id": str(self.attempt_id),
            "attempt_number": self.attempt_number,
            "node_id": self.node_id,
            "worker_kind": self.worker_kind.value,
            "tenant_id": self.tenant_id,
            "principal_id": self.principal.principal_id,
            "binding": self.binding.to_dict(),
            "deadline_seconds": self.deadline_seconds,
            "is_retry": self.is_retry,
            "correlation_id": self.correlation_id,
            "causation_id": self.causation_id,
        }


@dataclass(frozen=True)
class WorkerExecutionResult:
    """What the worker observed. Execution decides what it means."""

    outcome: WorkerOutcome
    binding_id: str
    attempt_id: str
    started_at: datetime
    completed_at: datetime

    failure: Optional[FailureRecord] = None
    detail: Mapping[str, Any] = field(default_factory=dict)
    """Non-sensitive facts about what happened. Never credentials, never tokens,
    never raw third-party payloads -- this reaches audit."""

    result_digest: Optional[str] = None
    """Canonical digest of the worker's output, computed with the platform's
    hashing. The output itself is deliberately not carried: results can be
    unbounded and can contain anything, and a digest is enough to tell whether
    two answers agree."""

    observed_effect: Optional[SideEffectClass] = None
    """What the worker believes it actually did. Compared against what was
    authorized -- a worker reporting a stronger effect than the bound contract
    declared is a contract violation, not a successful run."""

    cancellation_support: CancellationSupport = CancellationSupport.NONE

    def __post_init__(self) -> None:
        if not isinstance(self.outcome, WorkerOutcome):
            raise ContractViolation("outcome must be a WorkerOutcome")
        if self.completed_at < self.started_at:
            raise ContractViolation("a result cannot complete before it started")
        if self.outcome is WorkerOutcome.SUCCESS and self.failure is not None:
            raise ContractViolation(
                "a successful result cannot carry a failure; reporting both leaves "
                "whoever reads it to decide which was true"
            )
        if self.outcome is not WorkerOutcome.SUCCESS and self.failure is None:
            # Filled from the outcome's default rather than refused: a worker
            # that reports a timeout without elaborating is being honest, and
            # forcing it to invent a class would be worse.
            object.__setattr__(
                self,
                "failure",
                FailureRecord(
                    failure_class=self.outcome.default_failure_class
                    or FailureClass.UNKNOWN_OUTCOME,
                    reason=f"worker reported {self.outcome.value}",
                    occurred_at=self.completed_at,
                    source="worker",
                ),
            )

    @property
    def succeeded(self) -> bool:
        return self.outcome.is_success

    @property
    def outcome_is_known(self) -> bool:
        return self.outcome.outcome_is_known

    @property
    def failure_class(self) -> Optional[FailureClass]:
        return self.failure.failure_class if self.failure else None

    @property
    def duration_seconds(self) -> float:
        return (self.completed_at - self.started_at).total_seconds()

    def contradicts(self, binding: BoundCapability) -> Optional[str]:
        """Whether the worker did something stronger than it was authorized to.

        The check that stops a capability registered as a read from quietly
        performing writes. A contradiction is not a successful run: Execution
        refuses the result rather than recording a success it cannot stand
        behind.
        """
        if self.observed_effect is None:
            return None
        order = {
            SideEffectClass.READ: 0,
            SideEffectClass.REVERSIBLE_WRITE: 1,
            SideEffectClass.IRREVERSIBLE_WRITE: 2,
            SideEffectClass.DESTRUCTIVE: 3,
        }
        if order[self.observed_effect] > order[binding.side_effect_class]:
            return (
                f"the worker reports a {self.observed_effect.value} effect but the "
                f"bound capability declares {binding.side_effect_class.value}; the "
                "operation exceeded what was authorized"
            )
        return None

    def to_dict(self) -> dict:
        return {
            "outcome": self.outcome.value,
            "binding_id": self.binding_id,
            "attempt_id": self.attempt_id,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat(),
            "duration_seconds": self.duration_seconds,
            "outcome_is_known": self.outcome_is_known,
            "failure": self.failure.to_dict() if self.failure else None,
            "result_digest": self.result_digest,
            "observed_effect": (
                self.observed_effect.value if self.observed_effect else None
            ),
            "cancellation_support": self.cancellation_support.value,
            "detail": dict(self.detail),
        }

    # -- construction --------------------------------------------------

    @classmethod
    def success(
        cls,
        *,
        binding_id: str,
        attempt_id: str,
        started_at: datetime,
        output: Optional[Mapping[str, Any]] = None,
        observed_effect: Optional[SideEffectClass] = None,
        detail: Optional[Mapping[str, Any]] = None,
        completed_at: Optional[datetime] = None,
    ) -> "WorkerExecutionResult":
        return cls(
            outcome=WorkerOutcome.SUCCESS,
            binding_id=binding_id,
            attempt_id=attempt_id,
            started_at=started_at,
            completed_at=completed_at or datetime.now(timezone.utc),
            result_digest=(
                compute_digest(dict(output)).value if output is not None else None
            ),
            observed_effect=observed_effect,
            detail=dict(detail or {}),
        )

    @classmethod
    def failed(
        cls,
        *,
        binding_id: str,
        attempt_id: str,
        started_at: datetime,
        failure: FailureRecord,
        detail: Optional[Mapping[str, Any]] = None,
        completed_at: Optional[datetime] = None,
    ) -> "WorkerExecutionResult":
        outcome = (
            WorkerOutcome.UNKNOWN_OUTCOME
            if failure.failure_class.is_ambiguous
            else WorkerOutcome.FAILURE
        )
        return cls(
            outcome=outcome,
            binding_id=binding_id,
            attempt_id=attempt_id,
            started_at=started_at,
            completed_at=completed_at or datetime.now(timezone.utc),
            failure=failure,
            detail=dict(detail or {}),
        )

    @classmethod
    def unknown(
        cls,
        *,
        binding_id: str,
        attempt_id: str,
        started_at: datetime,
        reason: str,
        detail: Optional[Mapping[str, Any]] = None,
        completed_at: Optional[datetime] = None,
    ) -> "WorkerExecutionResult":
        """What to return when nobody can say. The safe answer, always available."""
        moment = completed_at or datetime.now(timezone.utc)
        return cls(
            outcome=WorkerOutcome.UNKNOWN_OUTCOME,
            binding_id=binding_id,
            attempt_id=attempt_id,
            started_at=started_at,
            completed_at=moment,
            failure=FailureRecord(
                failure_class=FailureClass.UNKNOWN_OUTCOME,
                reason=reason,
                occurred_at=moment,
                source="worker",
            ),
            detail=dict(detail or {}),
        )
