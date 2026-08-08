"""Goals, and the success criteria they trace back to.

A goal is the middle term between *what was asked for* and *what will be done*.
The Intent context produced criteria; this context decomposes them into goals and
hangs tasks off the goals. That middle term is what makes two coverage questions
answerable:

* **Does every criterion have a goal?** If not, the plan can complete every task
  and still not achieve what was asked for.
* **Does every goal have tasks?** If not, the plan claims a goal nothing works
  towards.

Both are checked by the aggregate, which is the only place the whole set is
visible.

Criteria are references, not copies
------------------------------------
``SuccessCriterionRef`` carries the intent's criterion id and a restatement. The
restatement exists because a plan has to be readable on its own; the id exists
because the restatement is a paraphrase and paraphrases drift. Nothing here
resolves the id -- S2 forbids importing the Intent context, and a resolver that
answered "yes, that criterion exists" would make the reference unfalsifiable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

from backend.contracts._contract import Contract
from backend.contracts.errors import ContractViolation
from backend.contexts.planner.domain.identifiers import GoalId

__all__ = ["SuccessCriterionRef", "PlanGoal"]


@dataclass(frozen=True, order=True)
class SuccessCriterionRef:
    """A criterion the plan is answerable for, as the plan restates it."""

    criterion_id: str
    statement: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.criterion_id, str) or not self.criterion_id.strip():
            raise ContractViolation(
                "a success criterion reference must name the criterion it traces to; "
                "a plan whose criteria cannot be traced back cannot be shown to serve "
                "what was asked for"
            )
        if self.criterion_id != self.criterion_id.strip():
            raise ContractViolation("criterion_id must not have surrounding whitespace")

    def __str__(self) -> str:
        return self.statement or self.criterion_id


@dataclass(frozen=True)
class PlanGoal(Contract):
    """One outcome the plan intends to produce."""

    CONTRACT_NAME = "cortexprime.planner.goal"

    goal_id: GoalId
    statement: str
    satisfies: frozenset = field(default_factory=frozenset)
    rationale: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.goal_id, GoalId):
            raise ContractViolation("goal_id must be a GoalId")
        if not isinstance(self.statement, str) or not self.statement.strip():
            raise ContractViolation("a goal must state the outcome it produces")

        if not isinstance(self.satisfies, (frozenset, set)):
            raise ContractViolation("satisfies must be a set")
        refs = frozenset(
            s if isinstance(s, SuccessCriterionRef) else SuccessCriterionRef(s)
            for s in self.satisfies
        )
        object.__setattr__(self, "satisfies", refs)

        # A goal that satisfies nothing is a goal nobody asked for. Refused here
        # rather than by policy, because a plan is assembled goal by goal and the
        # cheapest moment to notice is while the goal is being written.
        if not refs:
            raise ContractViolation(
                f"goal {self.statement[:60]!r} traces to no success criterion; a goal "
                "that satisfies nothing asked for is work the plan invented"
            )

    @property
    def criterion_ids(self) -> tuple:
        return tuple(sorted(ref.criterion_id for ref in self.satisfies))

    def __str__(self) -> str:
        return self.statement

    @classmethod
    def create(
        cls,
        statement: str,
        satisfies: Sequence,
        *,
        rationale: str = "",
    ) -> "PlanGoal":
        return cls(
            goal_id=GoalId.new(),
            statement=statement,
            satisfies=frozenset(
                s if isinstance(s, SuccessCriterionRef) else SuccessCriterionRef(s)
                for s in satisfies
            ),
            rationale=rationale,
        )
