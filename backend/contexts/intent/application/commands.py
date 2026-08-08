"""Commands and queries for the Intent context.

Frozen values naming one intent each, carrying primitives rather than domain
objects so a command can be serialised, queued, and replayed without dragging the
domain across the wire.

The validation here duplicates the domain's on purpose: a caller refused at the
command boundary is refused before anything is loaded, and the message is the
same one the aggregate would have given.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from backend.contracts.errors import ContractViolation
from backend.contexts.intent.domain.errors import (
    UnboundedConstraint,
    UnmeasurableCriterion,
)

__all__ = [
    "CaptureIntent",
    "SetObjective",
    "SetScope",
    "SetPriority",
    "SetRiskAppetite",
    "AddConstraint",
    "RemoveConstraint",
    "AddSuccessCriterion",
    "RemoveSuccessCriterion",
    "AcknowledgeRisk",
    "ValidateIntent",
    "ApproveIntent",
    "RejectIntent",
    "SupersedeIntent",
    "GetIntent",
    "ListIntents",
]

#: Kinds whose limit is mandatory. Mirrors ``ConstraintKind.is_quantitative`` so
#: the command can refuse before loading; the domain enforces it regardless.
_QUANTITATIVE_KINDS = frozenset({"budget", "deadline", "rate"})


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ContractViolation(message)


@dataclass(frozen=True)
class CaptureIntent:
    stated_goal: str
    title: str
    origin: str = "human"
    tags: tuple = ()
    requested_for: Optional[str] = None
    derived_from: Optional[str] = None

    def __post_init__(self) -> None:
        _require(
            bool(self.stated_goal and self.stated_goal.strip()),
            "stated_goal is required; the requester's own words are what makes it "
            "auditable whether the mandate matches what was asked for",
        )
        _require(bool(self.title and self.title.strip()), "title is required")
        _require(
            self.origin != "derived" or bool(self.derived_from),
            "a derived intent must name what it was derived from",
        )


@dataclass(frozen=True)
class SetObjective:
    intent_id: str
    outcome: str
    kind: str = "understand"
    rationale: str = ""
    subject: Optional[str] = None

    def __post_init__(self) -> None:
        _require(bool(self.intent_id), "intent_id is required")
        _require(
            bool(self.outcome and self.outcome.strip()),
            "an objective must state the outcome it wants",
        )


@dataclass(frozen=True)
class SetScope:
    intent_id: str
    included: tuple = ()
    excluded: tuple = ()
    environments: tuple = ("development",)
    target_type: str = "system"
    note: Optional[str] = None

    def __post_init__(self) -> None:
        _require(bool(self.intent_id), "intent_id is required")
        _require(
            bool(self.included),
            "a scope must include at least one target; one that includes nothing "
            "authorises nothing",
        )
        _require(bool(self.environments), "a scope must name at least one environment")
        overlap = set(self.included) & set(self.excluded)
        _require(
            not overlap,
            f"scope both includes and excludes {sorted(overlap)}; a planner cannot "
            "resolve the contradiction",
        )


@dataclass(frozen=True)
class SetPriority:
    intent_id: str
    priority: str

    def __post_init__(self) -> None:
        _require(bool(self.intent_id), "intent_id is required")
        _require(bool(self.priority), "priority is required")


@dataclass(frozen=True)
class SetRiskAppetite:
    intent_id: str
    appetite: str

    def __post_init__(self) -> None:
        _require(bool(self.intent_id), "intent_id is required")
        _require(bool(self.appetite), "appetite is required")


@dataclass(frozen=True)
class AddConstraint:
    intent_id: str
    kind: str
    statement: str
    limit: Optional[str] = None
    enforcement: str = "hard"
    rationale: str = ""

    def __post_init__(self) -> None:
        _require(bool(self.intent_id), "intent_id is required")
        _require(bool(self.kind), "kind is required")
        _require(
            bool(self.statement and self.statement.strip()),
            "a constraint must state what it limits",
        )
        # Raised as the domain's own error rather than a generic violation, so
        # the refusal a client receives is the structured one either way -- the
        # command failing fast must not cost the caller the better message.
        if self.kind in _QUANTITATIVE_KINDS and not (self.limit and self.limit.strip()):
            raise UnboundedConstraint(kind=self.kind, statement=self.statement)


@dataclass(frozen=True)
class RemoveConstraint:
    intent_id: str
    constraint_id: str

    def __post_init__(self) -> None:
        _require(bool(self.intent_id), "intent_id is required")
        _require(bool(self.constraint_id), "constraint_id is required")


@dataclass(frozen=True)
class AddSuccessCriterion:
    intent_id: str
    statement: str
    measure: str
    threshold: Optional[str] = None
    baseline: Optional[str] = None

    def __post_init__(self) -> None:
        _require(bool(self.intent_id), "intent_id is required")
        _require(
            bool(self.statement and self.statement.strip()),
            "a success criterion must state something",
        )
        # The domain's own error, for the same reason as above.
        if not (self.measure and self.measure.strip()):
            raise UnmeasurableCriterion(self.statement)


@dataclass(frozen=True)
class RemoveSuccessCriterion:
    intent_id: str
    criterion_id: str

    def __post_init__(self) -> None:
        _require(bool(self.intent_id), "intent_id is required")
        _require(bool(self.criterion_id), "criterion_id is required")


@dataclass(frozen=True)
class AcknowledgeRisk:
    intent_id: str
    statement: str
    impact: str = "low"
    accepted_by: Optional[str] = None

    def __post_init__(self) -> None:
        _require(bool(self.intent_id), "intent_id is required")
        _require(
            bool(self.statement and self.statement.strip()),
            "a risk must state what could go wrong",
        )
        _require(
            self.impact != "high" or bool(self.accepted_by and self.accepted_by.strip()),
            "a high-impact risk must name who accepted it; one acknowledged and not "
            "accepted is one nobody has decided about",
        )


@dataclass(frozen=True)
class ValidateIntent:
    intent_id: str

    def __post_init__(self) -> None:
        _require(bool(self.intent_id), "intent_id is required")


@dataclass(frozen=True)
class ApproveIntent:
    intent_id: str
    approved_by: str

    def __post_init__(self) -> None:
        _require(bool(self.intent_id), "intent_id is required")
        _require(
            bool(self.approved_by and self.approved_by.strip()),
            "an approval must name who gave it; an unattributed mandate has nobody "
            "accountable for it",
        )


@dataclass(frozen=True)
class RejectIntent:
    intent_id: str
    reason: str
    rejected_by: str = "reviewer"

    def __post_init__(self) -> None:
        _require(bool(self.intent_id), "intent_id is required")
        _require(
            bool(self.reason and self.reason.strip()),
            "rejecting an intent must say why; the next attempt is built from the "
            "reason, and an unexplained refusal produces the same intent again",
        )


@dataclass(frozen=True)
class SupersedeIntent:
    intent_id: str
    successor_id: str
    reason: str = "a revised intent replaces this one"

    def __post_init__(self) -> None:
        _require(bool(self.intent_id), "intent_id is required")
        _require(bool(self.successor_id), "successor_id is required")
        _require(
            self.intent_id != self.successor_id, "an intent cannot supersede itself"
        )


@dataclass(frozen=True)
class GetIntent:
    intent_id: str


@dataclass(frozen=True)
class ListIntents:
    status: Optional[str] = None
    priority: Optional[str] = None
    origin: Optional[str] = None
    planable_only: bool = False
