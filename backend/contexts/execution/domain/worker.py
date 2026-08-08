"""Workers: what runs a node, as a contract this context never implements.

Interfaces only, and that is the whole point
----------------------------------------------
``ExecutionWorker`` is a ``Protocol``. This context defines what a worker must be
able to do and never implements one -- no browser, no shell, no Docker, no
Kubernetes. The same arrangement the Engineering Runtime uses for its
collaborators (ADR-020), and for the same reason: a runtime that imported the
things it drives couples itself to every one of them, and the coupling looks
harmless at each individual call site.

The practical payoff is immediate rather than theoretical. Every worker kind
below is unimplemented, and the runtime is written, tested and reasoned about
against workers that do not exist. When one does exist, it satisfies a Protocol
that was designed without it in the room.

Capability matching is the one thing checked here
---------------------------------------------------
A node declares the worker kind it needs; a worker declares the kinds it offers.
Offering a node to a worker that cannot run it is refused before a lease is
issued -- because the alternative is a lease held by something that will fail,
and a held lease blocks every other worker from taking the node until it lapses.

``RunContext``, not ``ExecutionContext``
------------------------------------------
The obvious name is taken. ``backend.platform.context.ExecutionContext`` is the
tenancy and identity context threaded through every repository in this codebase
(ADR-017), and shadowing it inside the one context most likely to be read
alongside it would be a genuine hazard. This is the *node's* runtime envelope --
what a worker is handed to do one piece of work -- so ``RunContext`` says what it
is without colliding with what it is not.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping, Optional, Protocol, Sequence, runtime_checkable

from backend.contracts._contract import Contract, freeze_mapping
from backend.contracts.errors import ContractViolation
from backend.contracts.execution import ExecutionResult, ExecutionScope, SideEffectClass
from backend.contexts.execution.domain.errors import WorkerCannotRun
from backend.contexts.execution.domain.identifiers import normalise_worker_id

__all__ = [
    "WorkerKind",
    "WorkerRegistration",
    "RunContext",
    "ExecutionWorker",
    "WorkerHealth",
]


class WorkerKind(str, Enum):
    """What sort of thing a node needs run.

    Named after the *capability*, not the vendor. ``KUBERNETES`` rather than
    ``eks``; a node that needs a cluster does not care whose.

    None of these are implemented here. They are the vocabulary a node uses to
    say what it needs and a worker uses to say what it offers.
    """

    SHELL = "shell"
    PYTHON = "python"
    HTTP = "http"
    GIT = "git"
    DATABASE = "database"
    DOCKER = "docker"
    KUBERNETES = "kubernetes"
    TERRAFORM = "terraform"
    BROWSER = "browser"

    @property
    def is_inherently_stateful(self) -> bool:
        """Whether work of this kind usually leaves something behind.

        Advisory vocabulary for policy. A ``BROWSER`` session, a ``DOCKER``
        container and a ``TERRAFORM`` apply all leave state that outlives the
        node, which is what makes an abandoned lease on one worth reporting
        rather than merely retrying.
        """
        return self in (
            WorkerKind.DOCKER,
            WorkerKind.KUBERNETES,
            WorkerKind.TERRAFORM,
            WorkerKind.BROWSER,
        )


class WorkerHealth(str, Enum):
    READY = "ready"
    BUSY = "busy"
    DRAINING = "draining"
    """Finishing what it holds and taking nothing new. How a worker leaves
    without stranding the nodes it is running."""

    LOST = "lost"

    @property
    def accepts_work(self) -> bool:
        return self is WorkerHealth.READY


@dataclass(frozen=True)
class WorkerRegistration(Contract):
    """A worker's declaration of what it can run.

    Registration is a claim, not a credential. This context records what a worker
    says it offers and matches nodes against it; whether the worker can actually
    reach a Kubernetes cluster is between the worker and the cluster.
    """

    CONTRACT_NAME = "cortexprime.execution.worker"

    worker_id: str
    kinds: frozenset = field(default_factory=frozenset)
    max_concurrent: int = 1
    health: WorkerHealth = WorkerHealth.READY
    lease_seconds: int = 300
    registered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    labels: frozenset = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        object.__setattr__(self, "worker_id", normalise_worker_id(self.worker_id))

        if not isinstance(self.kinds, (frozenset, set)):
            raise ContractViolation("kinds must be a set")
        for kind in self.kinds:
            if not isinstance(kind, WorkerKind):
                raise ContractViolation("kinds must contain WorkerKind members")
        object.__setattr__(self, "kinds", frozenset(self.kinds))
        if not self.kinds:
            raise ContractViolation(
                f"worker {self.worker_id!r} offers no kind of work; a worker that can "
                "run nothing would sit in the pool being offered nodes forever"
            )

        if not isinstance(self.max_concurrent, int) or self.max_concurrent < 1:
            raise ContractViolation("max_concurrent must be at least 1")
        if not isinstance(self.health, WorkerHealth):
            raise ContractViolation("health must be a WorkerHealth")
        if not isinstance(self.lease_seconds, int) or self.lease_seconds < 1:
            raise ContractViolation(
                "lease_seconds must be at least 1; a zero-length lease expires before "
                "the worker can act on it"
            )
        if not isinstance(self.labels, (frozenset, set)):
            raise ContractViolation("labels must be a set")
        object.__setattr__(self, "labels", frozenset(self.labels))
        if self.registered_at.tzinfo is None:
            raise ContractViolation("registered_at must be timezone-aware")

    # -- queries -------------------------------------------------------

    @property
    def accepts_work(self) -> bool:
        return self.health.accepts_work

    def can_run(self, kind: WorkerKind) -> bool:
        return kind in self.kinds

    def assert_can_run(self, node_id: str, kind: WorkerKind) -> None:
        """Refuse a node this worker cannot run, before a lease is issued.

        A lease held by something that will fail blocks every other worker from
        taking the node until it lapses, which turns a mismatch into a delay.
        """
        if not self.can_run(kind):
            raise WorkerCannotRun(
                worker_id=self.worker_id,
                node_id=node_id,
                needs=kind.value,
                has=[k.value for k in self.kinds],
            )

    @classmethod
    def create(
        cls,
        worker_id: str,
        kinds: Sequence[WorkerKind],
        *,
        max_concurrent: int = 1,
        lease_seconds: int = 300,
        labels: Sequence[str] = (),
    ) -> "WorkerRegistration":
        return cls(
            worker_id=worker_id,
            kinds=frozenset(kinds),
            max_concurrent=max_concurrent,
            lease_seconds=lease_seconds,
            labels=frozenset(labels),
        )


@dataclass(frozen=True)
class RunContext(Contract):
    """What a worker is handed to run one node.

    Deliberately not the tenancy ``ExecutionContext`` -- see the module
    docstring. This carries what the *work* needs; that one carries who is
    asking and on whose behalf, and both travel together at the call site.

    ``parameters`` is opaque and frozen, the same call ADR-005 made for
    ``ActionRef``: BC-8 owns each tool's parameter schema, and duplicating it
    here would couple the runtime to every connector.
    """

    CONTRACT_NAME = "cortexprime.execution.run_context"

    execution_id: str
    node_id: str
    attempt: int
    worker_kind: WorkerKind
    side_effect: SideEffectClass = SideEffectClass.READ
    execution_key: Optional[str] = None
    idempotency_key: Optional[str] = None
    scope: Optional[ExecutionScope] = None
    deadline_seconds: Optional[int] = None
    parameters: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for label, value in (
            ("execution_id", self.execution_id),
            ("node_id", self.node_id),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ContractViolation(f"{label} must be non-blank text")
        if not isinstance(self.attempt, int) or self.attempt < 1:
            raise ContractViolation("attempt starts at 1")
        if not isinstance(self.worker_kind, WorkerKind):
            raise ContractViolation("worker_kind must be a WorkerKind")
        if not isinstance(self.side_effect, SideEffectClass):
            raise ContractViolation("side_effect must be a SideEffectClass")
        if self.deadline_seconds is not None and self.deadline_seconds < 1:
            raise ContractViolation("deadline_seconds must be positive when given")

        # A retried mutation must carry the key that makes the retry safe.
        # Constitution P2's operational half, checked at the moment the work is
        # handed over rather than only when it was planned.
        if self.attempt > 1 and self.side_effect.mutates and not (
            self.idempotency_key and self.idempotency_key.strip()
        ):
            raise ContractViolation(
                f"attempt {self.attempt} of {self.node_id!r} is {self.side_effect.value!r} "
                "and carries no idempotency key; a re-attempt may apply the action a "
                "second time and nothing downstream would know"
            )

        object.__setattr__(self, "parameters", freeze_mapping(self.parameters))

    @property
    def is_retry(self) -> bool:
        return self.attempt > 1


@runtime_checkable
class ExecutionWorker(Protocol):
    """What something must do to run a node for this runtime.

    **Never implemented here.** Every method is the runtime's side of a
    conversation with something it deliberately cannot see.

    ``run`` is expected to be long-lived and is expected to fail. The runtime's
    contract with it is narrow on purpose: take a ``WorkerExecutionRequest``
    describing work that has already been authorized, return a
    ``WorkerExecutionResult`` saying what was observed, and if you cannot, raise.

    A worker is given no registry, no policy engine, no resolver and no
    discovery service -- so it cannot look up whether it is allowed to run, which
    is the only way to be certain it never decides. Whether a raise means the work
    happened is not the worker's to decide -- the lease answers that, and it
    answers it the same way whether the worker raised, crashed, or vanished.
    """

    def registration(self) -> WorkerRegistration:
        """What this worker offers. Read when it joins the pool."""
        ...

    def run(self, context: Any, request: Any) -> Any:
        """Perform the bound operation.

        Takes a ``WorkerExecutionRequest`` and returns a
        ``WorkerExecutionResult`` (Phase 3.3.1). Typed as ``Any`` here only to
        keep this module free of an import cycle -- ``worker_contract`` imports
        ``WorkerKind`` from here.

        **Reconciled in Phase 3.3.1.** This previously took a ``RunContext``,
        which named a node and a worker kind but carried no capability binding.
        A worker receiving one could not tell what it had been authorized to
        perform, and returned a bare ``ExecutionResult`` with no classified
        failure -- leaving the runtime to infer from an exception whether a
        production change had happened. Both are now carried explicitly.

        Nothing implemented this Protocol, so the change breaks no caller.

        May take as long as the lease permits. Whether a raise means the work
        happened is still not the worker's to decide -- the lease answers that,
        and it answers the same way whether the worker raised, crashed, or
        vanished.
        """
        ...

    def cancel(self, context: Any, execution_id: str, node_id: str) -> bool:
        """Stop work in flight. Returns whether it was stopped.

        Returning ``False`` is a legitimate answer and the honest one for work
        that cannot be interrupted -- the runtime records that the node is
        uncancellable rather than pretending it stopped.
        """
        ...

    def heartbeat(self, context: Any, worker_id: str) -> WorkerHealth:
        """How the worker is. What keeps a lease alive."""
        ...
