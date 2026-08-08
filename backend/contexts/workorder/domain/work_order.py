"""The WorkOrder aggregate.

The unit of engineering work, and the only artifact that authorises action.
Nothing may be implemented, reviewed, verified, or merged except in service of
exactly one of these.

Immutable, like everything else in this codebase's domain layer. Every
transition returns a *new* WorkOrder plus the event that describes the change,
so a caller cannot accidentally mutate a WorkOrder another part of the system
still holds, and two concurrent operations cannot observe each other's
half-applied state.

Identity is the pair ``(work_id, version)``
-------------------------------------------
``version`` increments in exactly one circumstance: a blast-radius expansion
re-approved under ``OUT_OF_BLAST_RADIUS``. Every other change produces a new
WorkOrder superseding this one.

The asymmetry is deliberate. Predicting a blast radius correctly on the first
attempt is genuinely hard, and forcing a new ``work_id`` for an expansion would
sever the causal chain back to the original intent -- losing the ability to ask
"what did we think this would touch, and how wrong were we?", which is one of
the few direct quality signals about the Architect stance.

Governed fields are immutable after approval
--------------------------------------------
Approval binds to a digest. Changing a governed field afterwards would mean
implementing something other than what was approved, so the aggregate refuses
rather than recomputing the digest to match.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Iterable, Optional

from backend.contracts._contract import Contract
from backend.contracts.approval import PayloadDigest
from backend.contracts.errors import ContractViolation
from backend.contexts.workorder.domain.assumption import Assumption, AssumptionResolution
from backend.contexts.workorder.domain.blast_radius import BlastRadius
from backend.contexts.workorder.domain.digest import (
    compute_work_order_digest,
    digest_matches,
)
from backend.contexts.workorder.domain.errors import (
    DigestMismatch,
    DigestNotComputed,
    ImmutableAfterApproval,
    InvalidTransition,
    TerminalState,
)
from backend.contexts.workorder.domain.identifiers import (
    AdrRef,
    AssumptionId,
    ConstraintRef,
    EvidenceRef,
    WorkOrderId,
)
from backend.contexts.workorder.domain.rejection import RejectionGround, RejectionType
from backend.contexts.workorder.domain.states import (
    WorkOrderState,
    is_allowed,
    transition_reason,
)

__all__ = ["Priority", "WorkOrder"]


class Priority(str, Enum):
    """Scheduling metadata. Never a justification.

    Priority orders dispatch and nothing else. It does not shorten review, skip
    a gate, or waive a merge condition. Any argument of the form "this is P0, so
    skip X" is void -- which is why this enum carries no comparison helpers that
    would make such an argument convenient to express in code.
    """

    P0 = "p0"
    P1 = "p1"
    P2 = "p2"


@dataclass(frozen=True)
class WorkOrder(Contract):
    """An approved -- or proposed -- unit of engineering work."""

    CONTRACT_NAME = "cortexprime.engineering.work_order"

    # --- Identity -----------------------------------------------------
    work_id: WorkOrderId
    version: int

    # --- Governed content (immutable after approval) -------------------
    intent: str
    acceptance_criteria: frozenset
    adr_references: frozenset
    evidence: frozenset
    constraints: frozenset
    blast_radius: BlastRadius
    assumptions: tuple
    rejection_grounds: tuple
    dependencies: frozenset
    definition_of_done: frozenset

    # --- Mutable / lifecycle ------------------------------------------
    state: WorkOrderState = WorkOrderState.DRAFT
    priority: Priority = Priority.P1
    digest: Optional[PayloadDigest] = None

    # --- Envelope ------------------------------------------------------
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: str = "architect"
    supersedes: Optional[WorkOrderId] = None
    superseded_by: Optional[WorkOrderId] = None
    rejection_type: Optional[RejectionType] = None
    rejection_detail: Optional[str] = None

    # ------------------------------------------------------------------
    # Invariants
    # ------------------------------------------------------------------

    def __post_init__(self) -> None:
        if not isinstance(self.work_id, WorkOrderId):
            raise ContractViolation("work_id must be a WorkOrderId")
        if not isinstance(self.version, int) or self.version < 1:
            raise ContractViolation("version must be a positive integer starting at 1")

        if not isinstance(self.intent, str) or not self.intent.strip():
            raise ContractViolation("intent must be non-blank text")
        if self.intent != self.intent.strip():
            raise ContractViolation("intent must not have leading or trailing whitespace")

        self._require_statements("acceptance_criteria", self.acceptance_criteria)
        self._require_statements("definition_of_done", self.definition_of_done)
        self._require_refs("adr_references", self.adr_references, AdrRef)
        self._require_refs("evidence", self.evidence, EvidenceRef)
        self._require_refs("constraints", self.constraints, ConstraintRef)
        self._require_refs("dependencies", self.dependencies, WorkOrderId)

        if not isinstance(self.blast_radius, BlastRadius):
            raise ContractViolation("blast_radius must be a BlastRadius")

        for label, items, expected in (
            ("assumptions", self.assumptions, Assumption),
            ("rejection_grounds", self.rejection_grounds, RejectionGround),
        ):
            if not isinstance(items, tuple):
                raise ContractViolation(f"{label} must be a tuple")
            for item in items:
                if not isinstance(item, expected):
                    raise ContractViolation(
                        f"{label} contains {item!r}, which is not a {expected.__name__}"
                    )
            object.__setattr__(self, label, tuple(items))

        if not isinstance(self.state, WorkOrderState):
            raise ContractViolation("state must be a WorkOrderState")
        if not isinstance(self.priority, Priority):
            raise ContractViolation("priority must be a Priority")
        if self.digest is not None and not isinstance(self.digest, PayloadDigest):
            raise ContractViolation("digest must be a PayloadDigest when present")

        if self.created_at.tzinfo is None:
            raise ContractViolation("created_at must be timezone-aware")

        # V8 -- a WorkOrder cannot depend on itself. Checked here rather than in
        # the validator because it is a structural impossibility, not a policy.
        if self.work_id in self.dependencies:
            raise ContractViolation(
                f"WorkOrder {self.work_id} lists itself as a dependency"
            )

        # A governed state requires a digest: that is what "governed" means.
        if self.state.is_governed and self.digest is None:
            raise ContractViolation(
                f"WorkOrder in state {self.state.value!r} must carry the digest it "
                "was approved against"
            )

        # A rejected WorkOrder must say why, with a typed verdict.
        if self.state is WorkOrderState.REJECTED:
            if self.rejection_type is None:
                raise ContractViolation("a rejected WorkOrder must carry a rejection_type")
            if not self.rejection_detail or not self.rejection_detail.strip():
                raise ContractViolation(
                    "a rejected WorkOrder must carry rejection_detail citing its evidence"
                )
        elif self.rejection_type is not None or self.rejection_detail is not None:
            raise ContractViolation(
                "rejection_type and rejection_detail are only valid on a rejected WorkOrder"
            )

        for label, value in (("supersedes", self.supersedes), ("superseded_by", self.superseded_by)):
            if value is not None and not isinstance(value, WorkOrderId):
                raise ContractViolation(f"{label} must be a WorkOrderId when present")

    @staticmethod
    def _require_statements(label: str, values: Any) -> None:
        if not isinstance(values, (frozenset, set)):
            raise ContractViolation(f"{label} must be a set of statements")
        for value in values:
            if not isinstance(value, str) or not value.strip():
                raise ContractViolation(f"{label} contains a blank statement")
            if value != value.strip():
                raise ContractViolation(
                    f"{label} contains a statement with leading or trailing whitespace"
                )

    @staticmethod
    def _require_refs(label: str, values: Any, expected: type) -> None:
        if not isinstance(values, (frozenset, set)):
            raise ContractViolation(f"{label} must be a set")
        for value in values:
            if not isinstance(value, expected):
                raise ContractViolation(
                    f"{label} contains {value!r}, which is not a {expected.__name__}"
                )

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    @property
    def identity(self) -> tuple:
        """``(work_id, version)`` -- the real identity of this artifact."""
        return (self.work_id, self.version)

    @property
    def is_terminal(self) -> bool:
        return self.state.is_terminal

    @property
    def unresolved_assumptions(self) -> tuple:
        return tuple(a for a in self.assumptions if not a.is_resolved)

    @property
    def blocking_assumptions(self) -> tuple:
        """Assumptions resolved to something other than ``CONFIRMED``.

        ``UNVERIFIABLE`` blocks alongside ``CONTRADICTED``: proceeding on a
        belief nobody could check carries the same risk as proceeding on one
        found false, minus the knowledge that it was.
        """
        return tuple(a for a in self.assumptions if a.is_resolved and not a.permits_progress)

    def assumption(self, assumption_id: AssumptionId) -> Optional[Assumption]:
        for candidate in self.assumptions:
            if candidate.assumption_id == assumption_id:
                return candidate
        return None

    def grounds_for(self, assumption_id: AssumptionId) -> tuple:
        return tuple(
            g for g in self.rejection_grounds if g.triggering_assumption == assumption_id
        )

    # ------------------------------------------------------------------
    # Digest
    # ------------------------------------------------------------------

    def compute_digest(self) -> PayloadDigest:
        return compute_work_order_digest(self)

    def verify_digest(self) -> None:
        """Raise unless the content still hashes to the approved digest.

        Called at every governed transition. This is what makes approval bind to
        content rather than to a name.
        """
        if self.digest is None:
            raise DigestNotComputed(str(self.work_id))
        if not digest_matches(self, self.digest):
            raise DigestMismatch(
                work_order_id=str(self.work_id),
                approved=self.digest.value,
                recomputed=self.compute_digest().value,
            )

    # ------------------------------------------------------------------
    # Transitions -- each returns a new WorkOrder
    # ------------------------------------------------------------------

    def _guard_transition(self, requested: WorkOrderState) -> None:
        if self.state.is_terminal:
            raise TerminalState(work_order_id=str(self.work_id), state=self.state.value)
        if not is_allowed(self.state, requested):
            raise InvalidTransition(
                work_order_id=str(self.work_id),
                current=self.state.value,
                requested=requested.value,
                reason=transition_reason(self.state, requested) or "not permitted",
            )

    def approve(self) -> "WorkOrder":
        """Ratify the WorkOrder and bind the digest.

        The digest is computed *here*, once, and every later transition
        re-verifies it. Computing it lazily at each check would mean the digest
        always matched, which is a check that cannot fail.
        """
        self._guard_transition(WorkOrderState.APPROVED)
        # Hashed before the transition, not after. ``state`` is excluded from the
        # digest payload, so the value is identical either way -- but building an
        # APPROVED instance first would violate the invariant that a governed
        # state must already carry its digest.
        digest = compute_work_order_digest(self)
        return replace(self, state=WorkOrderState.APPROVED, digest=digest)

    def transition(self, requested: WorkOrderState) -> "WorkOrder":
        """Move to ``requested``, re-verifying the approval digest on the way."""
        self._guard_transition(requested)
        if requested is WorkOrderState.APPROVED:
            return self.approve()
        if self.state.is_governed:
            self.verify_digest()
        return replace(self, state=requested)

    def reject(self, rejection_type: RejectionType, detail: str) -> "WorkOrder":
        """Close the WorkOrder with a typed verdict.

        A successful outcome, not a failure. ``detail`` must cite the evidence
        required by the rejection type; a rejection without it is refusal to
        work, and the aggregate refuses to record one.
        """
        self._guard_transition(WorkOrderState.REJECTED)
        if not isinstance(rejection_type, RejectionType):
            raise ContractViolation("rejection_type must be a RejectionType")
        if not isinstance(detail, str) or not detail.strip():
            raise ContractViolation(
                f"a {rejection_type.value} rejection must cite: "
                f"{rejection_type.evidence_requirement}"
            )
        return replace(
            self,
            state=WorkOrderState.REJECTED,
            rejection_type=rejection_type,
            rejection_detail=detail.strip(),
        )

    def resolve_assumption(
        self,
        assumption_id: AssumptionId,
        resolution: AssumptionResolution,
        evidence: EvidenceRef,
    ) -> "WorkOrder":
        """Record the outcome of checking an assumption.

        Permitted only while the work is in flight. Resolving an assumption
        after ``READY`` would mean it was never actually checked -- the WorkOrder
        had already passed every gate that depended on it.
        """
        if self.state not in (
            WorkOrderState.SPEC_TESTS,
            WorkOrderState.IMPLEMENTATION,
            WorkOrderState.VERIFICATION,
        ):
            raise ContractViolation(
                f"assumptions may only be resolved during spec_tests, implementation, or "
                f"verification; this WorkOrder is {self.state.value!r}"
            )
        target = self.assumption(assumption_id)
        if target is None:
            raise ContractViolation(
                f"WorkOrder {self.work_id} has no assumption {assumption_id}"
            )
        resolved = target.resolve(resolution, evidence)
        return replace(
            self,
            assumptions=tuple(
                resolved if a.assumption_id == assumption_id else a for a in self.assumptions
            ),
        )

    def expand_blast_radius(self, radius: BlastRadius) -> "WorkOrder":
        """Widen the scope and re-approve as a new version.

        The one governed field expandable without a new ``work_id``. It produces
        a new version and a new digest, which is what makes the expansion
        visible as a re-approval rather than a silent edit.

        Narrowing is refused: a radius that shrinks after approval may already
        have authorised work now retroactively out of scope.
        """
        if not isinstance(radius, BlastRadius):
            raise ContractViolation("radius must be a BlastRadius")
        if self.state.is_terminal:
            raise TerminalState(work_order_id=str(self.work_id), state=self.state.value)
        if not radius.allowed >= self.blast_radius.allowed:
            raise ContractViolation(
                "a blast radius expansion must be a superset of the approved radius; "
                "narrowing would retroactively place already-authorised work out of scope"
            )
        # Staged as a DRAFT so the new content can be hashed before the governed
        # state demands a digest, then promoted with the digest attached.
        staged = replace(
            self,
            version=self.version + 1,
            blast_radius=radius,
            state=WorkOrderState.DRAFT,
            digest=None,
        )
        return replace(
            staged,
            state=WorkOrderState.APPROVED,
            digest=compute_work_order_digest(staged),
        )

    def reprioritise(self, priority: Priority) -> "WorkOrder":
        """Change scheduling order.

        The only governed-state mutation that does not invalidate the digest,
        because ``priority`` is excluded from it. Re-ordering the queue must not
        require re-approving the work.
        """
        if not isinstance(priority, Priority):
            raise ContractViolation("priority must be a Priority")
        return replace(self, priority=priority)

    def supersede(self, successor: WorkOrderId) -> "WorkOrder":
        """Record that a later WorkOrder replaces this one."""
        if not isinstance(successor, WorkOrderId):
            raise ContractViolation("successor must be a WorkOrderId")
        if successor == self.work_id:
            raise ContractViolation("a WorkOrder cannot supersede itself")
        if self.superseded_by is not None:
            raise ContractViolation(
                f"WorkOrder {self.work_id} is already superseded by {self.superseded_by}"
            )
        return replace(self, superseded_by=successor)

    # ------------------------------------------------------------------
    # Governed-field protection
    # ------------------------------------------------------------------

    def with_governed_change(self, **changes: Any) -> "WorkOrder":
        """Change a governed field. Permitted only before approval.

        Exists so the refusal is explicit and named. Without it a caller would
        reach for :func:`dataclasses.replace` directly, bypass the check, and
        produce a WorkOrder whose content no longer matches its approval -- which
        would then fail confusingly at the next transition instead of here.
        """
        if self.state is not WorkOrderState.DRAFT:
            raise ImmutableAfterApproval(
                work_order_id=str(self.work_id), field=", ".join(sorted(changes))
            )
        return replace(self, **changes)
