"""The objective, and how anyone would know it was met.

These live together because they are one idea. An objective without a way to
check it is a wish, and a success criterion with no objective is a measurement
nobody asked for.

A success criterion nobody can check is a wish
-----------------------------------------------
This is the rule the whole context turns on. "The system should be faster"
cannot be satisfied or refuted: an executor cannot know when to stop, and a
verifier cannot know whether it worked. So every criterion must name **how it is
measured** -- the observation, query, or signal that settles it.

Refused at construction rather than flagged by policy. A criterion this weak is
consumed by whatever reads the intent the moment it exists, and by then the
damage is a plan built on an unfalsifiable goal.

The measure is deliberately opaque
-----------------------------------
This context does not run the measurement, resolve the query, or know whether
the signal exists. It records what the requester said would settle the question.
A resolver that answered "yes, that metric exists" would make the requirement
unfalsifiable in a different way, and this context has no business reaching a
metrics system.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from backend.contracts._contract import Contract
from backend.contracts.errors import ContractViolation
from backend.contexts.intent.domain.errors import UnmeasurableCriterion
from backend.contexts.intent.domain.identifiers import CriterionId

__all__ = ["OutcomeKind", "IntentObjective", "SuccessCriterion"]


class OutcomeKind(str, Enum):
    """What kind of change the objective is asking for.

    Coarse on purpose. The kind steers policy defaults -- an objective that
    changes a live system is held to a different standard than one that observes
    it -- and it is not a taxonomy of everything an enterprise might want.
    """

    UNDERSTAND = "understand"
    DETECT = "detect"
    REDUCE = "reduce"
    RESTORE = "restore"
    PROTECT = "protect"
    PROVE = "prove"

    @property
    def changes_the_world(self) -> bool:
        """Whether achieving this necessarily mutates a live system.

        ``REDUCE`` and ``RESTORE`` act; the rest observe or attest. Policy holds
        acting objectives to a stricter standard, because the cost of a wrong
        observation is a wrong answer and the cost of a wrong action is an
        outage.
        """
        return self in (OutcomeKind.REDUCE, OutcomeKind.RESTORE)

    @property
    def is_continuous(self) -> bool:
        """Whether this objective has a natural end.

        ``DETECT`` does not -- "notice when this breaks" is answered for as long
        as anyone cares. Policy uses this to avoid demanding a deadline from an
        objective that cannot have one.
        """
        return self is OutcomeKind.DETECT


@dataclass(frozen=True)
class SuccessCriterion(Contract):
    """One checkable statement about what "done" means."""

    CONTRACT_NAME = "cortexprime.intent.success_criterion"

    criterion_id: CriterionId
    statement: str
    measure: str
    threshold: Optional[str] = None
    baseline: Optional[str] = None
    declared_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if not isinstance(self.criterion_id, CriterionId):
            raise ContractViolation("criterion_id must be a CriterionId")
        if not isinstance(self.statement, str) or not self.statement.strip():
            raise ContractViolation("a success criterion must state something")
        if not isinstance(self.measure, str) or not self.measure.strip():
            raise UnmeasurableCriterion(self.statement)
        for label, value in (("threshold", self.threshold), ("baseline", self.baseline)):
            if value is not None and not value.strip():
                raise ContractViolation(f"{label} must be non-blank when given")
        if self.declared_at.tzinfo is None:
            raise ContractViolation("declared_at must be timezone-aware")

    @property
    def is_comparative(self) -> bool:
        """Whether this criterion claims an improvement.

        A comparative criterion without a baseline cannot be settled: "30% fewer
        errors" than *what* is unanswerable after the fact, when the before-state
        is gone. Policy flags it; construction does not refuse it, because the
        baseline is sometimes genuinely established later.
        """
        return self.baseline is None and self.threshold is not None

    def __str__(self) -> str:
        suffix = f" (threshold: {self.threshold})" if self.threshold else ""
        return f"{self.statement}{suffix}"

    @classmethod
    def create(
        cls,
        statement: str,
        measure: str,
        *,
        threshold: Optional[str] = None,
        baseline: Optional[str] = None,
    ) -> "SuccessCriterion":
        return cls(
            criterion_id=CriterionId.new(),
            statement=statement,
            measure=measure,
            threshold=threshold,
            baseline=baseline,
        )


@dataclass(frozen=True)
class IntentObjective(Contract):
    """What the requester wants to be true that is not true now.

    ``outcome`` is the structured statement; ``rationale`` is why it matters.
    The rationale is not decoration: an objective whose reason is recorded can be
    re-examined when circumstances change, and one whose reason was never written
    down gets carried forward forever because nobody remembers whether it still
    applies.
    """

    CONTRACT_NAME = "cortexprime.intent.objective"

    outcome: str
    kind: OutcomeKind
    rationale: str = ""
    subject: Optional[str] = None

    def __post_init__(self) -> None:
        if not isinstance(self.outcome, str) or not self.outcome.strip():
            raise ContractViolation(
                "an objective must state the outcome it wants; an intent with no "
                "objective is a request for nothing in particular"
            )
        if not isinstance(self.kind, OutcomeKind):
            raise ContractViolation("kind must be an OutcomeKind")
        if self.subject is not None and not self.subject.strip():
            raise ContractViolation("subject must be non-blank when given")

    @property
    def changes_the_world(self) -> bool:
        return self.kind.changes_the_world

    def __str__(self) -> str:
        return self.outcome

    @classmethod
    def create(
        cls,
        outcome: str,
        kind: OutcomeKind,
        *,
        rationale: str = "",
        subject: Optional[str] = None,
    ) -> "IntentObjective":
        return cls(outcome=outcome, kind=kind, rationale=rationale, subject=subject)
