"""Constraints: the boundaries an objective must be pursued within.

A quantitative constraint carries its limit
--------------------------------------------
"Keep costs down" states a concern, not a boundary. Nothing can be shown to have
exceeded it, so it constrains nothing and an automated system pursuing the
objective will treat it as advice. Constraints of a *quantitative* kind --
budget, deadline, rate -- are therefore refused without a limit.

Qualitative kinds are not held to that standard, because forcing a number onto
"do not violate GDPR" would produce a fake one. What they are held to is being
stated as a boundary rather than a preference, which is a judgement policy
reports rather than a rule construction can enforce.

Constraints are recorded, never negotiated
-------------------------------------------
This context does not decide whether a constraint is achievable. That is the
planner's problem, and an intent that quietly dropped an unachievable constraint
would hand the planner a mandate the requester never gave.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Final, Optional

from backend.contracts._contract import Contract
from backend.contracts.errors import ContractViolation
from backend.contexts.intent.domain.errors import UnboundedConstraint
from backend.contexts.intent.domain.identifiers import ConstraintId

__all__ = ["ConstraintKind", "ConstraintEnforcement", "IntentConstraint"]


class ConstraintKind(str, Enum):
    """What sort of boundary this is."""

    BUDGET = "budget"
    DEADLINE = "deadline"
    RATE = "rate"
    AVAILABILITY = "availability"
    COMPLIANCE = "compliance"
    SAFETY = "safety"
    APPROVAL = "approval"
    DATA_RESIDENCY = "data_residency"

    @property
    def is_quantitative(self) -> bool:
        """Whether a limit is meaningful and therefore mandatory.

        A budget without a number is a wish. A compliance requirement without a
        number is normal -- the boundary is the regulation, not a threshold.
        """
        return self in _QUANTITATIVE

    @property
    def is_inviolable(self) -> bool:
        """Whether breaching this is a stop, not a trade-off.

        Compliance, safety, data residency and required approvals are not
        negotiable against speed or cost. Marking them as a distinct class means
        a planner reading this intent can tell which boundaries it may optimise
        around and which it may not.
        """
        return self in _INVIOLABLE


_QUANTITATIVE: Final[frozenset] = frozenset(
    {ConstraintKind.BUDGET, ConstraintKind.DEADLINE, ConstraintKind.RATE}
)

_INVIOLABLE: Final[frozenset] = frozenset(
    {
        ConstraintKind.COMPLIANCE,
        ConstraintKind.SAFETY,
        ConstraintKind.APPROVAL,
        ConstraintKind.DATA_RESIDENCY,
    }
)


class ConstraintEnforcement(str, Enum):
    """How hard a boundary this is.

    ``HARD`` stops the work; ``SOFT`` is a preference the planner may trade off
    and must report trading off. Two values rather than three, because a scale
    with a middle lets everything become the middle.
    """

    HARD = "hard"
    SOFT = "soft"

    @property
    def stops_the_work(self) -> bool:
        return self is ConstraintEnforcement.HARD


@dataclass(frozen=True)
class IntentConstraint(Contract):
    """One boundary the objective must be pursued within."""

    CONTRACT_NAME = "cortexprime.intent.constraint"

    constraint_id: ConstraintId
    kind: ConstraintKind
    statement: str
    limit: Optional[str] = None
    enforcement: ConstraintEnforcement = ConstraintEnforcement.HARD
    rationale: str = ""
    declared_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if not isinstance(self.constraint_id, ConstraintId):
            raise ContractViolation("constraint_id must be a ConstraintId")
        if not isinstance(self.kind, ConstraintKind):
            raise ContractViolation("kind must be a ConstraintKind")
        if not isinstance(self.enforcement, ConstraintEnforcement):
            raise ContractViolation("enforcement must be a ConstraintEnforcement")
        if not isinstance(self.statement, str) or not self.statement.strip():
            raise ContractViolation("a constraint must state what it limits")

        if self.limit is not None and not self.limit.strip():
            raise ContractViolation("limit must be non-blank when given")

        # A quantitative constraint with no limit does not constrain anything.
        if self.kind.is_quantitative and not (self.limit and self.limit.strip()):
            raise UnboundedConstraint(kind=self.kind.value, statement=self.statement)

        # An inviolable boundary cannot be a preference. Allowing "soft
        # compliance" would let a planner trade a regulation against a deadline
        # and report it as a legitimate optimisation.
        if self.kind.is_inviolable and not self.enforcement.stops_the_work:
            raise ContractViolation(
                f"a {self.kind.value!r} constraint cannot be soft; it is not "
                "negotiable against speed or cost, and marking it tradeable is how "
                "it gets traded"
            )

        if self.declared_at.tzinfo is None:
            raise ContractViolation("declared_at must be timezone-aware")

    @property
    def is_hard(self) -> bool:
        return self.enforcement.stops_the_work

    def __str__(self) -> str:
        suffix = f" ({self.limit})" if self.limit else ""
        return f"{self.kind.value}: {self.statement}{suffix}"

    @classmethod
    def create(
        cls,
        kind: ConstraintKind,
        statement: str,
        *,
        limit: Optional[str] = None,
        enforcement: ConstraintEnforcement = ConstraintEnforcement.HARD,
        rationale: str = "",
    ) -> "IntentConstraint":
        return cls(
            constraint_id=ConstraintId.new(),
            kind=kind,
            statement=statement,
            limit=limit,
            enforcement=enforcement,
            rationale=rationale,
        )
