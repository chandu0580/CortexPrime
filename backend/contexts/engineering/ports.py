"""The collaborators the Engineering Runtime orchestrates.

Every one is a Protocol this package defines and something else implements. The
runtime imports no bounded context, and the contexts import no runtime; adapters
are wired at the composition root, which is the only layer permitted to see both.

Why ports rather than direct imports
------------------------------------
An orchestrator that imports the contexts it orchestrates couples them
permanently, and the coupling looks harmless at every individual call site. That
is the erosion Constitution S2 exists to prevent.

``BND-CONTEXT-ISOLATION`` would not catch it here -- neither ``workorder`` nor
``engineering`` is one of the nine product contexts the rule iterates -- but a
gap in enforcement is not a licence. ADR-019 recorded that gap; this package is
the first thing that could have widened it and does not.

The practical payoff is immediate rather than theoretical: Review, Verification
and Context are three of the four collaborators here, and none of them exists
yet. Ports let the runtime be written, tested, and reasoned about against
collaborators that are still hypothetical.

State travels as strings
------------------------
A port that exchanged ``WorkOrderState`` would import the WorkOrder context.
:class:`WorkOrderPhase` is this package's own vocabulary, whose values are
exactly the WorkOrder context's state strings, and
``test_ports.py::test_phase_vocabulary_matches_the_workorder_context`` asserts
the two never drift. That converts a duplication risk into a checked invariant.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, Optional, Protocol, Sequence, runtime_checkable

__all__ = [
    "WorkOrderPhase",
    "TERMINAL_PHASES",
    "GOVERNED_PHASES",
    "PHASE_TRANSITIONS",
    "WorkOrderSnapshot",
    "WorkOrderPort",
    "ReviewPort",
    "VerificationPort",
    "ContextPort",
    "ReviewOutcome",
    "VerificationOutcome",
    "ContextBundleRef",
]


class WorkOrderPhase(str, Enum):
    """Where a WorkOrder is, in the runtime's vocabulary.

    Values are the WorkOrder context's state strings verbatim, so a port can
    exchange a plain string and both sides agree without either importing the
    other.
    """

    DRAFT = "draft"
    APPROVED = "approved"
    BLOCKED = "blocked"
    ASSIGNED = "assigned"
    SPEC_TESTS = "spec_tests"
    IMPLEMENTATION = "implementation"
    REVIEW = "review"
    VERIFICATION = "verification"
    READY = "ready"
    MERGED = "merged"
    CLOSED = "closed"
    REJECTED = "rejected"

    @property
    def is_terminal(self) -> bool:
        return self in TERMINAL_PHASES

    @property
    def is_governed(self) -> bool:
        return self in GOVERNED_PHASES


TERMINAL_PHASES = frozenset({WorkOrderPhase.CLOSED, WorkOrderPhase.REJECTED})

GOVERNED_PHASES = frozenset(
    {
        WorkOrderPhase.APPROVED,
        WorkOrderPhase.BLOCKED,
        WorkOrderPhase.ASSIGNED,
        WorkOrderPhase.SPEC_TESTS,
        WorkOrderPhase.IMPLEMENTATION,
        WorkOrderPhase.REVIEW,
        WorkOrderPhase.VERIFICATION,
        WorkOrderPhase.READY,
        WorkOrderPhase.MERGED,
        WorkOrderPhase.CLOSED,
    }
)

#: The runtime's own copy of the lifecycle, mirroring Engineering Constitution
#: §3.2. Held here rather than read through the port so the executor can refuse
#: an illegal transition *before* touching a collaborator -- an orchestrator that
#: has to call out to discover a move is illegal has already started it.
PHASE_TRANSITIONS: Mapping[WorkOrderPhase, frozenset] = {
    WorkOrderPhase.DRAFT: frozenset({WorkOrderPhase.APPROVED, WorkOrderPhase.REJECTED}),
    WorkOrderPhase.APPROVED: frozenset({WorkOrderPhase.BLOCKED, WorkOrderPhase.ASSIGNED}),
    WorkOrderPhase.BLOCKED: frozenset({WorkOrderPhase.APPROVED}),
    WorkOrderPhase.ASSIGNED: frozenset({WorkOrderPhase.SPEC_TESTS}),
    WorkOrderPhase.SPEC_TESTS: frozenset(
        {WorkOrderPhase.IMPLEMENTATION, WorkOrderPhase.REJECTED}
    ),
    WorkOrderPhase.IMPLEMENTATION: frozenset({WorkOrderPhase.REVIEW, WorkOrderPhase.REJECTED}),
    WorkOrderPhase.REVIEW: frozenset(
        {WorkOrderPhase.VERIFICATION, WorkOrderPhase.IMPLEMENTATION, WorkOrderPhase.REJECTED}
    ),
    WorkOrderPhase.VERIFICATION: frozenset(
        {WorkOrderPhase.READY, WorkOrderPhase.IMPLEMENTATION, WorkOrderPhase.REJECTED}
    ),
    WorkOrderPhase.READY: frozenset({WorkOrderPhase.MERGED, WorkOrderPhase.VERIFICATION}),
    WorkOrderPhase.MERGED: frozenset({WorkOrderPhase.CLOSED}),
    WorkOrderPhase.CLOSED: frozenset(),
    WorkOrderPhase.REJECTED: frozenset(),
}


@dataclass(frozen=True)
class WorkOrderSnapshot:
    """What the runtime needs to know about a WorkOrder to orchestrate it.

    Deliberately not the aggregate. The runtime schedules and gates; it does not
    reason about acceptance criteria or rewrite a blast radius. Passing the whole
    aggregate through the port would let it start doing so, and the boundary
    would be gone before anyone noticed it moved.
    """

    work_id: str
    version: int
    phase: WorkOrderPhase
    digest: Optional[str]
    priority: str
    intent: str
    blast_radius_allowed: tuple = ()
    constraints: tuple = ()
    unresolved_assumptions: int = 0
    blocking_assumptions: int = 0
    dependencies: tuple = ()
    superseded_by: Optional[str] = None

    @property
    def is_terminal(self) -> bool:
        return self.phase.is_terminal


@dataclass(frozen=True)
class ReviewOutcome:
    """What a review round produced. Owned by the Review context, not this one."""

    work_id: str
    round: int
    lens: str
    verdict: str
    blocking_findings: int = 0
    advisory_findings: int = 0

    @property
    def passed(self) -> bool:
        return self.verdict == "pass" and self.blocking_findings == 0


@dataclass(frozen=True)
class VerificationOutcome:
    """What a verification attempt produced. Owned by the Verification context."""

    work_id: str
    attempt: int
    status: str
    claims_reproduced: int = 0
    claims_contradicted: int = 0
    claims_unreproducible: int = 0

    @property
    def complete(self) -> bool:
        return (
            self.status == "complete"
            and self.claims_contradicted == 0
            and self.claims_unreproducible == 0
        )


@dataclass(frozen=True)
class ContextBundleRef:
    """A reference to an assembled context bundle. Owned by the Context context."""

    work_id: str
    work_order_version: int
    base_commit: str
    manifest_digest: str
    bundle_version: int = 1


# ----------------------------------------------------------------------
# Ports
# ----------------------------------------------------------------------


@runtime_checkable
class WorkOrderPort(Protocol):
    """The WorkOrder context, as the runtime sees it.

    Narrow on purpose: fetch, move, reject, supersede. The runtime cannot draft,
    approve, or edit a WorkOrder through this port, because none of those are
    orchestration -- they are decisions with their own authority.
    """

    def snapshot(self, context: Any, work_id: str) -> Optional[WorkOrderSnapshot]: ...

    def transition(self, context: Any, work_id: str, to_phase: WorkOrderPhase, actor: str) -> WorkOrderSnapshot: ...

    def reject(self, context: Any, work_id: str, rejection_type: str, detail: str, raised_by: str) -> WorkOrderSnapshot: ...

    def supersede(self, context: Any, work_id: str, successor_id: str, actor: str) -> WorkOrderSnapshot: ...

    def active(self, context: Any) -> Sequence[WorkOrderSnapshot]: ...


@runtime_checkable
class ReviewPort(Protocol):
    """The Review context. Not implemented yet -- the runtime only calls it."""

    def request(self, context: Any, work_id: str, round: int, lenses: Sequence[str]) -> Sequence[str]: ...

    def outcomes(self, context: Any, work_id: str, round: int) -> Sequence[ReviewOutcome]: ...

    def required_lenses(self) -> Sequence[str]: ...


@runtime_checkable
class VerificationPort(Protocol):
    """The Verification context. Not implemented yet."""

    def request(self, context: Any, work_id: str, attempt: int) -> str: ...

    def outcome(self, context: Any, work_id: str, attempt: int) -> Optional[VerificationOutcome]: ...


@runtime_checkable
class ContextPort(Protocol):
    """The Context-bundle context. Not implemented yet."""

    def assemble(self, context: Any, work_id: str, work_order_version: int) -> ContextBundleRef: ...

    def current(self, context: Any, work_id: str) -> Optional[ContextBundleRef]: ...
