"""Leases, attempts, and node runtime state.

The lease is the load-bearing idea in this context
----------------------------------------------------
A worker may only record a result for a node it holds the lease on. That single
rule is what prevents the failure with no honest recovery: two workers running
one node, the action happening twice, the record showing once, and nothing in the
system able to say which result describes the world.

Leases expire, and expiry is information
------------------------------------------
A lease that lapses without a result does not mean the node failed. It means the
worker stopped talking -- crashed, was killed, lost its network, or is still
working and cannot say so. The node becomes ``UNKNOWN``, which is the honest
answer and the one that makes the retry rule work.

Reclaiming the node is then a *decision*, not a cleanup: safe for a read,
requiring an idempotency key for anything that mutates.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from backend.contracts._contract import Contract
from backend.contracts.errors import ContractViolation
from backend.contracts.execution import ExecutionResult, SideEffectClass
from backend.contexts.execution.domain.failure import FailureClass, FailureRecord
from backend.contexts.execution.domain.errors import (
    AmbiguousRetry,
    AttemptsExhausted,
    IllegalNodeTransition,
    LeaseExpired,
    LeaseNotHeld,
    NodeAlreadyLeased,
    NodeNotRunning,
)
from backend.contexts.execution.domain.identifiers import (
    AttemptId,
    LeaseId,
    normalise_node_id,
    normalise_worker_id,
)
from backend.contexts.execution.domain.state import (
    NodeState,
    is_legal_node_transition,
    node_permitted_from,
)
from backend.contexts.execution.domain.worker import WorkerKind

__all__ = ["ExecutionLease", "ExecutionAttempt", "NodeSpec", "NodeRun"]


@dataclass(frozen=True)
class ExecutionLease(Contract):
    """One worker's exclusive claim on one node, for a bounded time."""

    CONTRACT_NAME = "cortexprime.execution.lease"

    lease_id: LeaseId
    node_id: str
    worker_id: str
    granted_at: datetime
    expires_at: datetime
    released_at: Optional[datetime] = None
    heartbeat_at: Optional[datetime] = None
    """When the holder was last heard from.

    Distinct from ``expires_at`` on purpose. Expiry says when the claim lapses;
    the heartbeat says when the worker last proved it was alive. A worker that
    took a long lease and died one second later looks perfectly healthy by
    expiry alone, and ``silent_for`` is what tells the difference."""

    def __post_init__(self) -> None:
        if not isinstance(self.lease_id, LeaseId):
            raise ContractViolation("lease_id must be a LeaseId")
        object.__setattr__(self, "node_id", normalise_node_id(self.node_id))
        object.__setattr__(self, "worker_id", normalise_worker_id(self.worker_id))

        for label in ("granted_at", "expires_at", "released_at", "heartbeat_at"):
            value = getattr(self, label)
            if value is not None and value.tzinfo is None:
                raise ContractViolation(f"{label} must be timezone-aware")

        if self.expires_at <= self.granted_at:
            raise ContractViolation(
                "a lease must expire after it is granted; one that expires on grant "
                "is not a claim on anything"
            )

    # -- queries -------------------------------------------------------

    @property
    def is_released(self) -> bool:
        return self.released_at is not None

    def has_expired_at(self, moment: datetime) -> bool:
        return not self.is_released and moment >= self.expires_at

    def is_live_at(self, moment: datetime) -> bool:
        return not self.is_released and moment < self.expires_at

    def held_by(self, worker_id: str) -> bool:
        return self.worker_id == worker_id and not self.is_released

    @property
    def seconds_granted(self) -> int:
        return int((self.expires_at - self.granted_at).total_seconds())

    @property
    def last_seen(self) -> datetime:
        """The most recent proof the holder was alive."""
        return self.heartbeat_at or self.granted_at

    def silent_for(self, moment: datetime) -> int:
        """Seconds since the holder was last heard from.

        A lease can be well inside its window and still belong to a worker that
        died minutes ago. This is the number that says so.
        """
        return max(0, int((moment - self.last_seen).total_seconds()))

    def is_stale_at(self, moment: datetime, *, silence_seconds: int) -> bool:
        """Whether the holder has gone quiet for longer than it should have.

        Advisory: going quiet is evidence a worker is gone, not proof. Only
        expiry entitles anyone else to the node, because acting on evidence
        alone is how two workers end up holding one lease.
        """
        if self.is_released or silence_seconds < 1:
            return False
        return self.silent_for(moment) >= silence_seconds

    # -- transitions ---------------------------------------------------

    def renewed(self, seconds: int, *, now: Optional[datetime] = None) -> "ExecutionLease":
        """Extend the claim. What a heartbeat does.

        Refuses on an already-expired lease: renewing one that lapsed would
        reclaim a node that may have been handed to somebody else, which is the
        split-brain this whole mechanism exists to prevent.
        """
        moment = now or datetime.now(timezone.utc)
        if self.is_released:
            raise ContractViolation(f"lease {self.lease_id} was already released")
        if self.has_expired_at(moment):
            raise LeaseExpired(node_id=self.node_id, worker_id=self.worker_id)
        if seconds < 1:
            raise ContractViolation("a renewal must add at least one second")
        return replace(self, expires_at=moment + timedelta(seconds=seconds))

    def beating(self, *, now: Optional[datetime] = None) -> "ExecutionLease":
        """Record that the holder is still alive, without extending the claim.

        Separate from ``renewed`` deliberately. A worker saying "still here"
        and a worker asking for more time are different requests, and a
        heartbeat that silently extended the lease would let a stuck worker
        hold a node forever by doing nothing but breathing.
        """
        moment = now or datetime.now(timezone.utc)
        if self.is_released:
            raise ContractViolation(f"lease {self.lease_id} was already released")
        if self.has_expired_at(moment):
            raise LeaseExpired(node_id=self.node_id, worker_id=self.worker_id)
        return replace(self, heartbeat_at=moment)

    def released(self, *, now: Optional[datetime] = None) -> "ExecutionLease":
        if self.is_released:
            return self
        return replace(self, released_at=now or datetime.now(timezone.utc))

    @classmethod
    def grant(
        cls,
        node_id: str,
        worker_id: str,
        seconds: int,
        *,
        now: Optional[datetime] = None,
    ) -> "ExecutionLease":
        moment = now or datetime.now(timezone.utc)
        if seconds < 1:
            raise ContractViolation("a lease must be granted for at least one second")
        return cls(
            lease_id=LeaseId.new(),
            node_id=node_id,
            worker_id=worker_id,
            granted_at=moment,
            expires_at=moment + timedelta(seconds=seconds),
            heartbeat_at=moment,
        )


@dataclass(frozen=True)
class ExecutionAttempt(Contract):
    """One try at one node, and how it ended.

    Every attempt is kept, including the ones that ended unknown. A runtime that
    recorded only the last attempt would answer "did this work" but never "how
    many times did we touch production before it did", which is the question
    asked after an incident.
    """

    CONTRACT_NAME = "cortexprime.execution.attempt"

    attempt_id: AttemptId
    node_id: str
    number: int
    worker_id: str
    lease_id: str
    started_at: datetime
    outcome: NodeState = NodeState.LEASED
    ended_at: Optional[datetime] = None
    result: Optional[ExecutionResult] = None
    failure_reason: Optional[str] = None
    failure: Optional[FailureRecord] = None
    """The classified failure, where one was classified.

    ``failure_reason`` is for the human reading the incident; this is for the
    runtime deciding what to do next. Keeping both is deliberate -- a class
    without a reason cannot be reviewed, and a reason without a class cannot be
    acted on."""
    retry_decision: Optional[dict] = None
    """The recorded retry decision that followed this attempt, if any.

    Held as a plain mapping so the attempt stays a record of what happened
    rather than a live policy object. Every retry in this runtime leaves one of
    these behind; a retry with no decision beside it is the signature of a
    silent loop."""

    def __post_init__(self) -> None:
        if not isinstance(self.attempt_id, AttemptId):
            raise ContractViolation("attempt_id must be an AttemptId")
        object.__setattr__(self, "node_id", normalise_node_id(self.node_id))
        object.__setattr__(self, "worker_id", normalise_worker_id(self.worker_id))

        if not isinstance(self.number, int) or self.number < 1:
            raise ContractViolation("attempt numbers start at 1")
        if not isinstance(self.outcome, NodeState):
            raise ContractViolation("outcome must be a NodeState")

        for label in ("started_at", "ended_at"):
            value = getattr(self, label)
            if value is not None and value.tzinfo is None:
                raise ContractViolation(f"{label} must be timezone-aware")

        if self.outcome is NodeState.LEASED:
            if self.ended_at is not None:
                raise ContractViolation("an attempt still in flight has not ended")
        else:
            if self.ended_at is None:
                raise ContractViolation(
                    f"an attempt that ended {self.outcome.value!r} must record when"
                )

        if self.outcome is NodeState.FAILED and not (
            self.failure_reason and self.failure_reason.strip()
        ):
            raise ContractViolation(
                "a failed attempt must say why; a failure with no reason tells the "
                "next attempt nothing and the incident review less"
            )

        # An unknown outcome carries no result by definition -- if a result had
        # arrived, the outcome would not be unknown.
        if self.outcome is NodeState.UNKNOWN and self.result is not None:
            raise ContractViolation(
                "an attempt that ended unknown cannot carry a result; if a result "
                "arrived, the outcome is not unknown"
            )

    @property
    def is_open(self) -> bool:
        return self.outcome is NodeState.LEASED

    @property
    def is_ambiguous(self) -> bool:
        return self.outcome.is_ambiguous

    def concluded(
        self,
        outcome: NodeState,
        *,
        result: Optional[ExecutionResult] = None,
        failure_reason: Optional[str] = None,
        now: Optional[datetime] = None,
        failure: Optional[FailureRecord] = None,
    ) -> "ExecutionAttempt":
        if not self.is_open:
            raise ContractViolation(
                f"attempt {self.number} of {self.node_id!r} already ended "
                f"{self.outcome.value!r}"
            )
        return replace(
            self,
            outcome=outcome,
            result=result,
            failure_reason=failure_reason,
            failure=failure,
            ended_at=now or datetime.now(timezone.utc),
        )

    @classmethod
    def open(
        cls,
        node_id: str,
        number: int,
        worker_id: str,
        lease_id: str,
        *,
        now: Optional[datetime] = None,
    ) -> "ExecutionAttempt":
        return cls(
            attempt_id=AttemptId.new(),
            node_id=node_id,
            number=number,
            worker_id=worker_id,
            lease_id=lease_id,
            started_at=now or datetime.now(timezone.utc),
        )


@dataclass(frozen=True)
class NodeSpec(Contract):
    """What the compiled workflow said about one node.

    A projection, not a copy of the workflow's node. This context cannot import
    the Workflow context (S2), so the compiled graph arrives as data: what the
    node needs, what it waits for, how many attempts it gets, how long it has.

    The projection is deliberately thin. Everything here is something the
    *runtime* has to act on. What the node is *for* stays in the workflow, where
    somebody approved it.
    """

    CONTRACT_NAME = "cortexprime.execution.node_spec"

    node_id: str
    worker_kind: WorkerKind
    depends_on: tuple = ()
    side_effect: SideEffectClass = SideEffectClass.READ
    max_attempts: int = 1
    timeout_seconds: Optional[int] = None
    idempotency_key: Optional[str] = None
    compensates: Optional[str] = None
    cancellable: bool = True
    execution_key: Optional[str] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "node_id", normalise_node_id(self.node_id))

        if not isinstance(self.worker_kind, WorkerKind):
            raise ContractViolation("worker_kind must be a WorkerKind")
        if not isinstance(self.side_effect, SideEffectClass):
            raise ContractViolation("side_effect must be a SideEffectClass")

        if not isinstance(self.depends_on, tuple):
            raise ContractViolation("depends_on must be a tuple")
        for dependency in self.depends_on:
            normalise_node_id(dependency)
        if self.node_id in self.depends_on:
            raise ContractViolation(f"node {self.node_id!r} depends on itself")
        if len(set(self.depends_on)) != len(self.depends_on):
            raise ContractViolation(f"node {self.node_id!r} lists a dependency twice")

        if not isinstance(self.max_attempts, int) or self.max_attempts < 1:
            raise ContractViolation("max_attempts must be at least 1")
        if self.timeout_seconds is not None and self.timeout_seconds < 1:
            raise ContractViolation("timeout_seconds must be positive when given")

        if self.compensates is not None:
            normalise_node_id(self.compensates)

    @property
    def mutates(self) -> bool:
        return self.side_effect.mutates

    @property
    def is_idempotent(self) -> bool:
        return bool(self.idempotency_key and self.idempotency_key.strip())

    @property
    def is_compensation(self) -> bool:
        return self.compensates is not None

    def assert_retryable_after(self, state: NodeState) -> None:
        """Refuse a retry that could apply a non-idempotent action twice.

        Constitution P2's operational half. The Workflow context refuses this at
        compile time for a *declared* retry policy; this is the same rule at the
        moment a specific ambiguous attempt is about to be re-run, which is when
        it actually costs something.
        """
        if not state.is_ambiguous:
            return
        if not self.mutates or self.is_idempotent:
            return
        raise AmbiguousRetry(node_id=self.node_id, side_effect=self.side_effect.value)


@dataclass(frozen=True)
class NodeRun(Contract):
    """The runtime state of one node: where it is, who holds it, what it tried."""

    CONTRACT_NAME = "cortexprime.execution.node_run"

    spec: NodeSpec
    state: NodeState = NodeState.WAITING
    lease: Optional[ExecutionLease] = None
    attempts: tuple = ()
    skipped_reason: Optional[str] = None

    def __post_init__(self) -> None:
        if not isinstance(self.spec, NodeSpec):
            raise ContractViolation("spec must be a NodeSpec")
        if not isinstance(self.state, NodeState):
            raise ContractViolation("state must be a NodeState")
        if self.lease is not None and not isinstance(self.lease, ExecutionLease):
            raise ContractViolation("lease must be an ExecutionLease")

        if not isinstance(self.attempts, tuple):
            raise ContractViolation("attempts must be a tuple")
        for attempt in self.attempts:
            if not isinstance(attempt, ExecutionAttempt):
                raise ContractViolation("attempts must contain ExecutionAttempt values")

        numbers = [a.number for a in self.attempts]
        if numbers != list(range(1, len(numbers) + 1)):
            raise ContractViolation(
                f"node {self.spec.node_id!r} has attempts numbered {numbers}; a gap "
                "would make 'how many times did we touch this' unanswerable"
            )

        if len(self.attempts) > self.spec.max_attempts:
            raise AttemptsExhausted(
                node_id=self.spec.node_id, attempts=self.spec.max_attempts
            )

        # A leased node holds a lease; anything else does not.
        if self.state is NodeState.LEASED:
            if self.lease is None or self.lease.is_released:
                raise ContractViolation(
                    f"node {self.spec.node_id!r} is leased but holds no live lease"
                )
        if self.state is NodeState.SKIPPED and not (
            self.skipped_reason and self.skipped_reason.strip()
        ):
            raise ContractViolation(
                f"node {self.spec.node_id!r} was skipped without a reason; a skip "
                "nobody explained is indistinguishable from work that was forgotten"
            )

    # -- queries -------------------------------------------------------

    @property
    def node_id(self) -> str:
        return self.spec.node_id

    @property
    def attempt_count(self) -> int:
        return len(self.attempts)

    @property
    def attempts_remaining(self) -> int:
        return max(0, self.spec.max_attempts - self.attempt_count)

    @property
    def current_attempt(self) -> Optional[ExecutionAttempt]:
        for attempt in reversed(self.attempts):
            if attempt.is_open:
                return attempt
        return None

    @property
    def last_attempt(self) -> Optional[ExecutionAttempt]:
        return self.attempts[-1] if self.attempts else None

    @property
    def is_finished(self) -> bool:
        return self.state.is_finished

    @property
    def satisfies_dependents(self) -> bool:
        return self.state.satisfies_dependents

    @property
    def held_by(self) -> str:
        if self.lease is None or self.lease.is_released:
            return ""
        return self.lease.worker_id

    @property
    def result(self):
        for attempt in reversed(self.attempts):
            if attempt.result is not None:
                return attempt.result
        return None

    # -- transitions ---------------------------------------------------

    def _moved(self, to_state: NodeState, **changes: Any) -> "NodeRun":
        if not is_legal_node_transition(self.state, to_state):
            raise IllegalNodeTransition(
                node_id=self.node_id,
                source=self.state.value,
                target=to_state.value,
                permitted=node_permitted_from(self.state),
            )
        return replace(self, state=to_state, **changes)

    def become_ready(self) -> "NodeRun":
        return self._moved(NodeState.READY)

    def leased_to(
        self, worker_id: str, seconds: int, *, now: Optional[datetime] = None
    ) -> "NodeRun":
        """Hand the node to a worker. Refuses a second holder."""
        if self.state is NodeState.LEASED:
            raise NodeAlreadyLeased(node_id=self.node_id, held_by=self.held_by)
        if self.attempts_remaining < 1:
            raise AttemptsExhausted(
                node_id=self.node_id, attempts=self.spec.max_attempts
            )
        self.spec.assert_retryable_after(self.state)

        moment = now or datetime.now(timezone.utc)
        lease = ExecutionLease.grant(self.node_id, worker_id, seconds, now=moment)
        attempt = ExecutionAttempt.open(
            self.node_id,
            self.attempt_count + 1,
            worker_id,
            str(lease.lease_id),
            now=moment,
        )
        return self._moved(
            NodeState.LEASED, lease=lease, attempts=self.attempts + (attempt,)
        )

    def assert_held_by(self, worker_id: str, *, now: Optional[datetime] = None) -> None:
        """The rule the context exists for: only the holder may report."""
        moment = now or datetime.now(timezone.utc)
        if self.state is not NodeState.LEASED:
            raise NodeNotRunning(node_id=self.node_id, state=self.state.value)
        if self.lease is None or not self.lease.held_by(worker_id):
            raise LeaseNotHeld(
                node_id=self.node_id, offered=worker_id, held_by=self.held_by
            )
        if self.lease.has_expired_at(moment):
            raise LeaseExpired(node_id=self.node_id, worker_id=worker_id)

    def concluded(
        self,
        outcome: NodeState,
        worker_id: str,
        *,
        result: Optional[ExecutionResult] = None,
        failure_reason: Optional[str] = None,
        now: Optional[datetime] = None,
        failure: Optional[FailureRecord] = None,
    ) -> "NodeRun":
        """Record what the holder reports."""
        moment = now or datetime.now(timezone.utc)
        self.assert_held_by(worker_id, now=moment)

        attempt = self.current_attempt
        concluded = attempt.concluded(
            outcome,
            result=result,
            failure_reason=failure_reason,
            now=moment,
            failure=failure,
        )
        return self._moved(
            outcome,
            lease=self.lease.released(now=moment),
            attempts=tuple(
                concluded if a.attempt_id == attempt.attempt_id else a
                for a in self.attempts
            ),
        )

    def abandoned(self, *, now: Optional[datetime] = None) -> "NodeRun":
        """Record that the lease lapsed without a result.

        Not a failure -- a statement about what is knowable. The node becomes
        ``UNKNOWN`` and whether it may be retried is then a decision the spec
        makes, not a cleanup this method performs.
        """
        moment = now or datetime.now(timezone.utc)
        if self.state is not NodeState.LEASED:
            raise NodeNotRunning(node_id=self.node_id, state=self.state.value)
        if self.lease is not None and self.lease.is_live_at(moment):
            raise ContractViolation(
                f"the lease on {self.node_id!r} has not expired; reclaiming it now "
                "would take the node from a worker that is still entitled to it"
            )

        attempt = self.current_attempt
        changes: dict = {"lease": self.lease.released(now=moment) if self.lease else None}
        if attempt is not None:
            concluded = attempt.concluded(
                NodeState.UNKNOWN,
                now=moment,
                failure=FailureRecord(
                    failure_class=FailureClass.UNKNOWN_OUTCOME,
                    reason=(
                        f"the lease on {self.node_id!r} lapsed without a result; "
                        "whether the work was applied is not knowable from here"
                    ),
                    occurred_at=moment,
                    source="lease-expiry",
                ),
            )
            changes["attempts"] = tuple(
                concluded if a.attempt_id == attempt.attempt_id else a
                for a in self.attempts
            )
        return self._moved(NodeState.UNKNOWN, **changes)

    def retried(self) -> "NodeRun":
        """Return a finished-but-unsuccessful node to the ready pool."""
        if self.attempts_remaining < 1:
            raise AttemptsExhausted(
                node_id=self.node_id, attempts=self.spec.max_attempts
            )
        self.spec.assert_retryable_after(self.state)
        return self._moved(NodeState.READY)

    def skipped(self, reason: str) -> "NodeRun":
        if not reason or not reason.strip():
            raise ContractViolation("skipping a node must say why")
        return self._moved(NodeState.SKIPPED, skipped_reason=reason.strip())

    def compensated(self) -> "NodeRun":
        return self._moved(NodeState.COMPENSATED)

    @classmethod
    def of(cls, spec: NodeSpec) -> "NodeRun":
        """A fresh run for a node. Entry nodes start ready, the rest wait."""
        return cls(
            spec=spec,
            state=NodeState.READY if not spec.depends_on else NodeState.WAITING,
        )
