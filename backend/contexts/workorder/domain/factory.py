"""Construction helpers for WorkOrders.

The aggregate's own constructor takes strongly-typed values and enforces every
invariant, which is correct and verbose. This module is the ergonomic path in:
plain strings become identifiers, and the assumption/rejection-ground pairing
that V3 requires is produced automatically rather than left to a caller to
remember.

That last part is the point of having a factory at all. V3 exists because an
unverified belief with no refusal path is how a false premise reaches
production; a factory that lets you declare an assumption *and* forget its
rejection ground would recreate exactly the gap the rule closes.
"""

from __future__ import annotations

from typing import Iterable, Optional, Sequence

from backend.contexts.workorder.domain.assumption import Assumption
from backend.contexts.workorder.domain.blast_radius import BlastRadius
from backend.contexts.workorder.domain.identifiers import (
    AdrRef,
    ConstraintRef,
    EvidenceRef,
    WorkOrderId,
)
from backend.contexts.workorder.domain.rejection import RejectionGround, RejectionType
from backend.contexts.workorder.domain.states import WorkOrderState
from backend.contexts.workorder.domain.work_order import Priority, WorkOrder

__all__ = ["AssumptionSpec", "draft_work_order"]


class AssumptionSpec:
    """An assumption plus the condition under which it forces a refusal.

    Deliberately a pair. Declaring a belief without declaring what to do when it
    turns out false is the failure V3 exists to prevent, so this type makes them
    inseparable at the point of authoring.
    """

    __slots__ = ("statement", "verification_method", "rejection_condition", "rejection_type")

    def __init__(
        self,
        statement: str,
        verification_method: str,
        *,
        rejection_condition: Optional[str] = None,
        rejection_type: RejectionType = RejectionType.PREMISE_FALSE,
    ) -> None:
        self.statement = statement
        self.verification_method = verification_method
        # The obvious default: if the belief is false, the premise is false.
        self.rejection_condition = (
            rejection_condition or f"the assumption does not hold: {statement}"
        )
        self.rejection_type = rejection_type


def draft_work_order(
    *,
    intent: str,
    acceptance_criteria: Iterable[str],
    blast_radius: BlastRadius,
    definition_of_done: Iterable[str] = (),
    adr_references: Iterable[str] = (),
    evidence: Iterable[str] = (),
    constraints: Iterable[str] = (),
    assumptions: Sequence[AssumptionSpec] = (),
    extra_rejection_grounds: Iterable[tuple] = (),
    dependencies: Iterable[str] = (),
    priority: Priority = Priority.P1,
    created_by: str = "architect",
    supersedes: Optional[str] = None,
) -> WorkOrder:
    """Build a Draft WorkOrder from plain values.

    Every assumption yields a matching rejection ground, so a WorkOrder built
    here can never fail V3. ``extra_rejection_grounds`` adds grounds unrelated to
    any assumption -- a spec can be refusable for reasons that are not beliefs.
    """
    built_assumptions: list = []
    built_grounds: list = []

    for spec in assumptions:
        assumption = Assumption.create(spec.statement, spec.verification_method)
        built_assumptions.append(assumption)
        built_grounds.append(
            RejectionGround.create(
                spec.rejection_condition,
                spec.rejection_type,
                triggering_assumption=assumption.assumption_id,
            )
        )

    for condition, rejection_type in extra_rejection_grounds:
        built_grounds.append(RejectionGround.create(condition, rejection_type))

    return WorkOrder(
        work_id=WorkOrderId.new(),
        version=1,
        intent=intent,
        acceptance_criteria=frozenset(acceptance_criteria),
        adr_references=frozenset(AdrRef(a) for a in adr_references),
        evidence=frozenset(EvidenceRef(e) for e in evidence),
        constraints=frozenset(ConstraintRef(c) for c in constraints),
        blast_radius=blast_radius,
        assumptions=tuple(built_assumptions),
        rejection_grounds=tuple(built_grounds),
        dependencies=frozenset(WorkOrderId(d) for d in dependencies),
        definition_of_done=frozenset(definition_of_done),
        state=WorkOrderState.DRAFT,
        priority=priority,
        created_by=created_by,
        supersedes=WorkOrderId(supersedes) if supersedes else None,
    )
