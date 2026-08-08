"""Typed rejection grounds.

A rejection is a **successful outcome**, not a failure. It closes a WorkOrder
having produced the most valuable artifact available: proof that the plan was
wrong before the code was written.

The six types are fixed by Engineering Constitution §4. Each carries, as data,
who may raise it and who resolves it -- because those differ, and getting them
wrong routes a governance decision to an agent. ``CONSTRAINT_CONFLICT`` in
particular resolves to the **Founder**, never the Architect: a conflict between
a goal and an invariant is not a specification problem to be edited away.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from backend.contracts._contract import Contract
from backend.contracts.errors import ContractViolation
from backend.contexts.workorder.domain.identifiers import AssumptionId, RejectionGroundId

__all__ = ["RejectionType", "RejectionGround", "Resolver", "Raiser"]


class Raiser(str, Enum):
    """Which stance may raise a rejection type."""

    ANY_ROLE = "any_role"
    IMPLEMENTER = "implementer"
    SPEC_TEST_AUTHOR = "spec_test_author"
    REVIEWER = "reviewer"
    VERIFIER = "verifier"
    AUTOMATED = "automated"


class Resolver(str, Enum):
    """Who decides what happens after a rejection."""

    ARCHITECT = "architect"
    FOUNDER = "founder"


class RejectionType(str, Enum):
    """Engineering Constitution §4."""

    PREMISE_FALSE = "premise_false"
    SCOPE_INDIVISIBLE = "scope_indivisible"
    EVIDENCE_MISSING = "evidence_missing"
    CONSTRAINT_CONFLICT = "constraint_conflict"
    OUT_OF_BLAST_RADIUS = "out_of_blast_radius"
    ARCHITECTURE_VIOLATION = "architecture_violation"

    @property
    def resolver(self) -> Resolver:
        """Who resolves this rejection.

        Only ``CONSTRAINT_CONFLICT`` escalates to the Founder. Every other type
        is answered by a corrected or merged WorkOrder, which is the Architect's
        work. A conflict between a goal and an invariant is a governance
        decision, and the output is either a changed goal or a superseding ADR --
        never a silent exception.
        """
        if self is RejectionType.CONSTRAINT_CONFLICT:
            return Resolver.FOUNDER
        return Resolver.ARCHITECT

    @property
    def raisers(self) -> frozenset:
        """Which stances may raise it."""
        return _RAISERS[self]

    @property
    def requires_evidence(self) -> bool:
        """Every type does.

        Present as a property rather than assumed, so that adding a type forces
        an explicit answer rather than inheriting a default nobody chose. A
        rejection with no evidence is refusal to work.
        """
        return True

    @property
    def evidence_requirement(self) -> str:
        """What must be cited for this rejection to stand."""
        return _EVIDENCE_REQUIREMENTS[self]


_RAISERS = {
    RejectionType.PREMISE_FALSE: frozenset(
        {Raiser.IMPLEMENTER, Raiser.SPEC_TEST_AUTHOR, Raiser.VERIFIER}
    ),
    RejectionType.SCOPE_INDIVISIBLE: frozenset({Raiser.IMPLEMENTER}),
    RejectionType.EVIDENCE_MISSING: frozenset({Raiser.ANY_ROLE}),
    RejectionType.CONSTRAINT_CONFLICT: frozenset({Raiser.IMPLEMENTER, Raiser.REVIEWER}),
    RejectionType.OUT_OF_BLAST_RADIUS: frozenset({Raiser.IMPLEMENTER, Raiser.AUTOMATED}),
    RejectionType.ARCHITECTURE_VIOLATION: frozenset(
        {Raiser.REVIEWER, Raiser.VERIFIER, Raiser.AUTOMATED}
    ),
}

_EVIDENCE_REQUIREMENTS = {
    RejectionType.PREMISE_FALSE: (
        "the premise as stated; a citation demonstrating the contradiction; the "
        "acceptance criteria that become unreachable"
    ),
    RejectionType.SCOPE_INDIVISIBLE: (
        "the specific import, call, or shared-state edge coupling the two halves, "
        "cited by file and line; what the intermediate commit would fail at"
    ),
    RejectionType.EVIDENCE_MISSING: (
        "the precise question; what was consulted; why the answer is not derivable "
        "from the supplied context"
    ),
    RejectionType.CONSTRAINT_CONFLICT: (
        "the acceptance criterion; the constraint identifier; the concrete "
        "construction under which they cannot both hold"
    ),
    RejectionType.OUT_OF_BLAST_RADIUS: (
        "the module; why the change is unavoidable; whether the excess is coupling "
        "or an incomplete declaration"
    ),
    RejectionType.ARCHITECTURE_VIOLATION: (
        "the rule identifier; the offending module and line; the gate output"
    ),
}


@dataclass(frozen=True)
class RejectionGround(Contract):
    """A condition under which the receiver must refuse rather than proceed.

    Written by the Architect against its own specification. Composing these is
    the Architect stating, in advance, how it could be wrong -- which is the
    only reliable way an implementer gets permission to say so later.
    """

    CONTRACT_NAME = "cortexprime.engineering.rejection_ground"

    ground_id: RejectionGroundId
    condition: str
    rejection_type: RejectionType
    triggering_assumption: Optional[AssumptionId] = None

    def __post_init__(self) -> None:
        if not isinstance(self.ground_id, RejectionGroundId):
            raise ContractViolation("ground_id must be a RejectionGroundId")
        if not isinstance(self.condition, str) or not self.condition.strip():
            raise ContractViolation("condition must be non-blank text")
        if self.condition != self.condition.strip():
            raise ContractViolation("condition must not have leading or trailing whitespace")
        if not isinstance(self.rejection_type, RejectionType):
            raise ContractViolation("rejection_type must be a RejectionType")
        if self.triggering_assumption is not None and not isinstance(
            self.triggering_assumption, AssumptionId
        ):
            raise ContractViolation("triggering_assumption must be an AssumptionId")

    @classmethod
    def create(
        cls,
        condition: str,
        rejection_type: RejectionType,
        *,
        triggering_assumption: Optional[AssumptionId] = None,
    ) -> "RejectionGround":
        return cls(
            ground_id=RejectionGroundId.new(),
            condition=condition,
            rejection_type=rejection_type,
            triggering_assumption=triggering_assumption,
        )

    @property
    def resolver(self) -> Resolver:
        return self.rejection_type.resolver
