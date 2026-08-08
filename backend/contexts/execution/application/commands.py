"""Commands and queries for the Execution Runtime.

Frozen values naming one intent each, carrying primitives rather than domain
objects so a command can be serialised, queued, and replayed without dragging the
domain across the wire.

Every command that records an outcome carries the ``worker_id``, because the
lease check is the point: a result offered without saying who is offering it
cannot be authorised at all.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from backend.contracts.errors import ContractViolation

__all__ = [
    "StartExecution",
    "RegisterWorker",
    "AssignNode",
    "RecordSuccess",
    "RecordFailure",
    "ReclaimNode",
    "Heartbeat",
    "PlanRecovery",
    "ReplayExecution",
    "RetryNode",
    "SkipNode",
    "CompensateNode",
    "CreateCheckpoint",
    "PauseExecution",
    "ResumeExecution",
    "CompleteExecution",
    "FailExecution",
    "CancelExecution",
    "TimeOutExecution",
    "GetExecution",
    "GetReadyNodes",
    "ListExecutions",
]

_MUTATING = frozenset({"reversible_write", "irreversible_write", "destructive"})


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ContractViolation(message)


@dataclass(frozen=True)
class StartExecution:
    """``nodes`` is the projection of the compiled workflow, as mappings."""

    workflow_id: str
    workflow_digest: str
    mission_id: str
    nodes: tuple = ()
    attempt: int = 1
    requested_by: str = "mission-runtime"

    def __post_init__(self) -> None:
        _require(bool(self.workflow_id), "workflow_id is required")
        _require(
            bool(self.workflow_digest and self.workflow_digest.strip()),
            "workflow_digest is required; a run that cannot name the exact graph it "
            "executes is a run of whatever somebody later decides it was running",
        )
        _require(bool(self.mission_id), "mission_id is required")
        _require(
            bool(self.nodes),
            "a run needs at least one node; one with none would complete instantly "
            "having done nothing and report success for it",
        )
        for node in self.nodes:
            _require(bool(node.get("node_id")), "every node needs a node_id")
            _require(bool(node.get("worker_kind")), "every node needs a worker_kind")
            _require(
                node.get("max_attempts", 1) < 2
                or node.get("side_effect", "read") not in _MUTATING
                or bool(node.get("idempotency_key")),
                f"node {node.get('node_id')!r} is retryable and mutating but carries no "
                "idempotency key; a re-attempt may apply the action twice",
            )


@dataclass(frozen=True)
class RegisterWorker:
    worker_id: str
    kinds: tuple = ()
    max_concurrent: int = 1
    lease_seconds: int = 300
    labels: tuple = ()

    def __post_init__(self) -> None:
        _require(bool(self.worker_id and self.worker_id.strip()), "worker_id is required")
        _require(
            bool(self.kinds),
            "a worker must offer at least one kind of work; one that can run nothing "
            "would sit in the pool being offered nodes forever",
        )
        _require(self.lease_seconds >= 1, "lease_seconds must be at least 1")


@dataclass(frozen=True)
class AssignNode:
    execution_id: str
    node_id: str
    worker_id: str

    def __post_init__(self) -> None:
        _require(bool(self.execution_id), "execution_id is required")
        _require(bool(self.node_id), "node_id is required")
        _require(bool(self.worker_id), "worker_id is required")


@dataclass(frozen=True)
class RecordSuccess:
    execution_id: str
    node_id: str
    worker_id: str
    execution_key: str
    detail: Optional[Dict[str, Any]] = None

    def __post_init__(self) -> None:
        _require(bool(self.execution_id), "execution_id is required")
        _require(bool(self.node_id), "node_id is required")
        _require(
            bool(self.worker_id),
            "worker_id is required; a result offered without saying who is offering "
            "it cannot be authorised against the lease",
        )
        _require(bool(self.execution_key), "execution_key is required")


@dataclass(frozen=True)
class RecordFailure:
    execution_id: str
    node_id: str
    worker_id: str
    reason: str
    execution_key: Optional[str] = None
    failure_class: str = "transient_failure"
    """How the failure should be classified.

    Defaulted to transient because that is the *least* consequential wrong
    answer: it leads to a retry, which the effect semantics then refuse if the
    node is not safe to repeat. Defaulting to a terminal class would silently
    give up on recoverable work; defaulting to unknown_outcome would escalate
    every ordinary error to a human.
    """
    failure_source: Optional[str] = None

    def __post_init__(self) -> None:
        _require(bool(self.execution_id), "execution_id is required")
        _require(bool(self.node_id), "node_id is required")
        _require(bool(self.worker_id), "worker_id is required")
        _require(
            bool(self.reason and self.reason.strip()),
            "a failed attempt must say why; a failure with no reason tells the next "
            "attempt nothing and the incident review less",
        )


@dataclass(frozen=True)
class Heartbeat:
    """A worker saying it is still alive. Never extends the lease."""

    execution_id: str
    node_id: str
    worker_id: str

    def __post_init__(self) -> None:
        _require(bool(self.execution_id), "execution_id is required")
        _require(bool(self.node_id), "node_id is required")
        _require(bool(self.worker_id), "worker_id is required")


@dataclass(frozen=True)
class PlanRecovery:
    execution_id: str
    trigger: str = "operator_request"

    def __post_init__(self) -> None:
        _require(bool(self.execution_id), "execution_id is required")


@dataclass(frozen=True)
class ReplayExecution:
    execution_id: str

    def __post_init__(self) -> None:
        _require(bool(self.execution_id), "execution_id is required")


@dataclass(frozen=True)
class ReclaimNode:
    execution_id: str
    node_id: str

    def __post_init__(self) -> None:
        _require(bool(self.execution_id), "execution_id is required")
        _require(bool(self.node_id), "node_id is required")


@dataclass(frozen=True)
class RetryNode:
    execution_id: str
    node_id: str

    def __post_init__(self) -> None:
        _require(bool(self.execution_id), "execution_id is required")
        _require(bool(self.node_id), "node_id is required")


@dataclass(frozen=True)
class SkipNode:
    execution_id: str
    node_id: str
    reason: str

    def __post_init__(self) -> None:
        _require(bool(self.execution_id), "execution_id is required")
        _require(bool(self.node_id), "node_id is required")
        _require(
            bool(self.reason and self.reason.strip()),
            "skipping a node must say why; a skip nobody explained is "
            "indistinguishable from work that was forgotten",
        )


@dataclass(frozen=True)
class CompensateNode:
    execution_id: str
    node_id: str

    def __post_init__(self) -> None:
        _require(bool(self.execution_id), "execution_id is required")
        _require(bool(self.node_id), "node_id is required")


@dataclass(frozen=True)
class CreateCheckpoint:
    execution_id: str
    label: str
    payload_ref: Optional[str] = None
    recorded_by: str = "execution-runtime"

    def __post_init__(self) -> None:
        _require(bool(self.execution_id), "execution_id is required")
        _require(
            bool(self.label and self.label.strip()),
            "a checkpoint must be labelled; an unlabelled resumption point tells "
            "whoever resumes nothing about what they are resuming into",
        )


@dataclass(frozen=True)
class PauseExecution:
    execution_id: str
    reason: str

    def __post_init__(self) -> None:
        _require(bool(self.execution_id), "execution_id is required")
        _require(bool(self.reason and self.reason.strip()), "pausing must say why")


@dataclass(frozen=True)
class ResumeExecution:
    execution_id: str
    from_checkpoint: Optional[str] = None

    def __post_init__(self) -> None:
        _require(bool(self.execution_id), "execution_id is required")


@dataclass(frozen=True)
class CompleteExecution:
    execution_id: str

    def __post_init__(self) -> None:
        _require(bool(self.execution_id), "execution_id is required")


@dataclass(frozen=True)
class FailExecution:
    execution_id: str
    reason: str

    def __post_init__(self) -> None:
        _require(bool(self.execution_id), "execution_id is required")
        _require(bool(self.reason and self.reason.strip()), "a failed run must say why")


@dataclass(frozen=True)
class CancelExecution:
    execution_id: str
    reason: str
    cancelled_by: str = "operator"

    def __post_init__(self) -> None:
        _require(bool(self.execution_id), "execution_id is required")
        _require(bool(self.reason and self.reason.strip()), "cancelling must say why")


@dataclass(frozen=True)
class TimeOutExecution:
    execution_id: str
    deadline_seconds: int = 0

    def __post_init__(self) -> None:
        _require(bool(self.execution_id), "execution_id is required")


@dataclass(frozen=True)
class GetExecution:
    execution_id: str


@dataclass(frozen=True)
class GetReadyNodes:
    execution_id: str


@dataclass(frozen=True)
class ListExecutions:
    mission_id: Optional[str] = None
    workflow_id: Optional[str] = None
    state: Optional[str] = None
    live_only: bool = False
