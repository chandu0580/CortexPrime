"""Execution lifecycle events.

Namespaced ``execution.runtime.*``. ``CONTRACT_NAME`` is globally unique and a
clash raises at import time.

These are the first events in this codebase that describe *work happening*
rather than a document being decided on. That changes what they have to carry:
an event about a run is read during an incident, so each one carries what an
operator would otherwise have to go and look up -- which worker, which attempt,
what is still outstanding.

``ExecutionTimedOut`` and ``ExecutionFailed`` are separate for the same reason
``UNKNOWN`` and ``FAILED`` are separate node states: a deadline that fired and a
thing that broke call for different responses, and collapsing them loses the one
that is usually recoverable.
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.contracts.errors import ContractViolation
from backend.platform.events import DomainEvent

__all__ = [
    "AGGREGATE_TYPE",
    "ExecutionStarted",
    "ExecutionAssigned",
    "ExecutionCheckpointCreated",
    "ExecutionPaused",
    "ExecutionResumed",
    "ExecutionCompleted",
    "ExecutionFailed",
    "ExecutionCancelled",
    "ExecutionTimedOut",
    "ExecutionRetried",
    "EXECUTION_EVENT_TYPES",
]

AGGREGATE_TYPE = "execution"


def _require_text(label: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ContractViolation(f"{label} must be non-blank text")


@dataclass(frozen=True)
class ExecutionStarted(DomainEvent):
    """A run began, against a specific compiled workflow."""

    EVENT_TYPE = "execution.runtime.started"

    execution_id: str = ""
    workflow_id: str = ""
    workflow_digest: str = ""
    mission_id: str = ""
    attempt: int = 1
    nodes: int = 0

    def __post_init__(self) -> None:
        super().__post_init__()
        _require_text("execution_id", self.execution_id)
        _require_text("workflow_id", self.workflow_id)
        _require_text("workflow_digest", self.workflow_digest)
        if self.nodes < 1:
            raise ContractViolation(
                "a run has at least one node; one with none would complete instantly "
                "having done nothing and report success for it"
            )


@dataclass(frozen=True)
class ExecutionAssigned(DomainEvent):
    """A node was leased to a worker.

    Carries the lease and the attempt number because those are what an operator
    correlates against when two things claim to have run the same node.
    """

    EVENT_TYPE = "execution.runtime.assigned"

    execution_id: str = ""
    node_id: str = ""
    worker_id: str = ""
    lease_id: str = ""
    attempt: int = 1
    worker_kind: str = ""
    lease_seconds: int = 0

    def __post_init__(self) -> None:
        super().__post_init__()
        _require_text("execution_id", self.execution_id)
        _require_text("node_id", self.node_id)
        _require_text("worker_id", self.worker_id)
        _require_text("lease_id", self.lease_id)
        if self.attempt < 1:
            raise ContractViolation("attempt numbers start at 1")
        if self.lease_seconds < 1:
            raise ContractViolation(
                "a lease lasts at least a second; one that expires on grant hands the "
                "node straight back"
            )


@dataclass(frozen=True)
class ExecutionCheckpointCreated(DomainEvent):
    EVENT_TYPE = "execution.runtime.checkpoint_created"

    execution_id: str = ""
    checkpoint_id: str = ""
    sequence: int = 1
    label: str = ""
    finished_nodes: int = 0
    digest: str = ""

    def __post_init__(self) -> None:
        super().__post_init__()
        _require_text("execution_id", self.execution_id)
        _require_text("checkpoint_id", self.checkpoint_id)
        _require_text("label", self.label)
        _require_text("digest", self.digest)
        if self.sequence < 1:
            raise ContractViolation("checkpoint sequence starts at 1")


@dataclass(frozen=True)
class ExecutionPaused(DomainEvent):
    """Dispatch stopped. Nodes already leased keep running.

    ``leased_nodes`` is the field that matters: a pause is not a stop, and an
    operator who reads this as "everything has halted" will be wrong about
    exactly the nodes that are still changing things.
    """

    EVENT_TYPE = "execution.runtime.paused"

    execution_id: str = ""
    reason: str = ""
    leased_nodes: int = 0
    finished_nodes: int = 0
    resumable_from: str = ""

    def __post_init__(self) -> None:
        super().__post_init__()
        _require_text("execution_id", self.execution_id)
        _require_text("reason", self.reason)


@dataclass(frozen=True)
class ExecutionResumed(DomainEvent):
    EVENT_TYPE = "execution.runtime.resumed"

    execution_id: str = ""
    resumed_from_checkpoint: str = ""
    skipped_nodes: int = 0
    ready_nodes: int = 0

    def __post_init__(self) -> None:
        super().__post_init__()
        _require_text("execution_id", self.execution_id)


@dataclass(frozen=True)
class ExecutionCompleted(DomainEvent):
    """The run finished with every node accounted for.

    Refuses construction with anything outstanding or ambiguous. An event that
    could describe a completion over unfinished work would make the log a worse
    record than the aggregate.
    """

    EVENT_TYPE = "execution.runtime.completed"

    execution_id: str = ""
    workflow_id: str = ""
    digest: str = ""
    nodes: int = 0
    succeeded: int = 0
    skipped: int = 0
    compensated: int = 0
    outstanding: int = 0
    ambiguous: int = 0

    def __post_init__(self) -> None:
        super().__post_init__()
        _require_text("execution_id", self.execution_id)
        _require_text("digest", self.digest)
        if self.outstanding:
            raise ContractViolation(
                f"a run cannot be reported complete with {self.outstanding} node(s) "
                "unfinished"
            )
        if self.ambiguous:
            raise ContractViolation(
                f"a run cannot be reported complete with {self.ambiguous} node(s) whose "
                "outcome nobody can state"
            )


@dataclass(frozen=True)
class ExecutionFailed(DomainEvent):
    EVENT_TYPE = "execution.runtime.failed"

    execution_id: str = ""
    reason: str = ""
    digest: str = ""
    failed_nodes: int = 0
    ambiguous_nodes: int = 0
    mutated_nodes: int = 0

    def __post_init__(self) -> None:
        super().__post_init__()
        _require_text("execution_id", self.execution_id)
        _require_text("reason", self.reason)
        _require_text("digest", self.digest)


@dataclass(frozen=True)
class ExecutionCancelled(DomainEvent):
    """The run was called off.

    ``mutated_nodes`` is mandatory information rather than colour: cancelling
    does not un-change the world, and this is the number somebody has to act on.
    """

    EVENT_TYPE = "execution.runtime.cancelled"

    execution_id: str = ""
    reason: str = ""
    cancelled_by: str = ""
    digest: str = ""
    mutated_nodes: int = 0
    leased_nodes: int = 0

    def __post_init__(self) -> None:
        super().__post_init__()
        _require_text("execution_id", self.execution_id)
        _require_text("reason", self.reason)
        _require_text("cancelled_by", self.cancelled_by)
        _require_text("digest", self.digest)


@dataclass(frozen=True)
class ExecutionTimedOut(DomainEvent):
    """The deadline fired.

    Separate from failure because it calls for a different response: a timeout
    says nothing about whether the work was wrong, only that it took too long,
    and the nodes still leased when it fired may still be running.
    """

    EVENT_TYPE = "execution.runtime.timed_out"

    execution_id: str = ""
    digest: str = ""
    deadline_seconds: int = 0
    finished_nodes: int = 0
    leased_nodes: int = 0

    def __post_init__(self) -> None:
        super().__post_init__()
        _require_text("execution_id", self.execution_id)
        _require_text("digest", self.digest)


@dataclass(frozen=True)
class ExecutionRetried(DomainEvent):
    """A node was returned to the ready pool.

    ``after`` distinguishes the two cases that matter: retrying a *failed* node
    re-runs work known not to have happened; retrying an *unknown* one may apply
    an action a second time, which is why the idempotency rule guards it.
    """

    EVENT_TYPE = "execution.runtime.retried"

    execution_id: str = ""
    node_id: str = ""
    after: str = ""
    attempt: int = 1
    attempts_remaining: int = 0
    idempotent: bool = False

    def __post_init__(self) -> None:
        super().__post_init__()
        _require_text("execution_id", self.execution_id)
        _require_text("node_id", self.node_id)
        _require_text("after", self.after)
        if not isinstance(self.idempotent, bool):
            raise ContractViolation("idempotent must be a bool")
        if self.after == "unknown" and not self.idempotent:
            raise ContractViolation(
                "a node whose last attempt ended unknown cannot be retried without an "
                "idempotency key; the retry may apply the action a second time"
            )


EXECUTION_EVENT_TYPES = (
    ExecutionStarted,
    ExecutionAssigned,
    ExecutionCheckpointCreated,
    ExecutionPaused,
    ExecutionResumed,
    ExecutionCompleted,
    ExecutionFailed,
    ExecutionCancelled,
    ExecutionTimedOut,
    ExecutionRetried,
)
