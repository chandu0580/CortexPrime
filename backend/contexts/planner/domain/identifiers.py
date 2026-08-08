"""Identifiers for the Planner context.

``PlanId``, ``GoalId`` and ``RiskId`` are ULID-backed, so sorting by id gives
creation order without a separate column.

**Task ids are deliberately not ULIDs.** Dependencies name tasks by id, and a
plan whose graph reads ``01KZD7... depends on 01KZD8...`` is unreadable by the
person who has to approve it. ``TaskRef`` takes a plain string for the same
reason, so meaningful ids like ``snapshot-db`` are what both this context and the
published contract expect. Uniqueness is enforced by the plan, which is where the
whole set is visible.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from backend.contracts.errors import ContractViolation
from backend.contexts.planner.domain.errors import InvalidIdentifier
from backend.platform.identity import is_ulid, monotonic_ulid, timestamp_of

__all__ = ["PlanId", "GoalId", "RiskId", "normalise_task_id"]


@dataclass(frozen=True, order=True)
class _UlidIdentifier:
    KIND: ClassVar[str] = "identifier"

    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str):
            raise InvalidIdentifier(
                type(self).KIND,
                self.value,
                f"expected a string, got {type(self.value).__name__}",
            )
        if not is_ulid(self.value):
            raise InvalidIdentifier(type(self).KIND, self.value, "not a valid ULID")

    @classmethod
    def new(cls):
        return cls(monotonic_ulid())

    @property
    def created_at_ms(self) -> int:
        return timestamp_of(self.value)

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, order=True)
class PlanId(_UlidIdentifier):
    KIND: ClassVar[str] = "PlanId"


@dataclass(frozen=True, order=True)
class GoalId(_UlidIdentifier):
    KIND: ClassVar[str] = "GoalId"


@dataclass(frozen=True, order=True)
class RiskId(_UlidIdentifier):
    KIND: ClassVar[str] = "RiskId"


def normalise_task_id(value: str) -> str:
    """A task id a human can read in a dependency list.

    Whitespace is refused rather than trimmed at the edges only: ``deploy api``
    and ``deploy  api`` would be different tasks that look identical in a
    refusal message, which is exactly the confusion a dependency graph must not
    have.
    """
    if not isinstance(value, str) or not value.strip():
        raise ContractViolation("a task id must be non-blank text")
    if value != value.strip():
        raise ContractViolation(
            f"task id {value!r} has surrounding whitespace; two ids that differ only "
            "by spacing look identical in a dependency list"
        )
    if any(character.isspace() and character != " " for character in value):
        raise ContractViolation(f"task id {value!r} contains a tab or newline")
    return value
