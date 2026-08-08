"""Strongly-typed identifiers for the Intent context.

ULID-backed, so a list of constraints sorted by id is in the order they were
declared without a separate timestamp column. Distinct types, so a criterion id
cannot be passed where a constraint id belongs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from backend.contexts.intent.domain.errors import InvalidIdentifier
from backend.platform.identity import is_ulid, monotonic_ulid, timestamp_of

__all__ = ["IntentId", "ConstraintId", "CriterionId", "RiskId"]


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
class IntentId(_UlidIdentifier):
    KIND: ClassVar[str] = "IntentId"


@dataclass(frozen=True, order=True)
class ConstraintId(_UlidIdentifier):
    KIND: ClassVar[str] = "ConstraintId"


@dataclass(frozen=True, order=True)
class CriterionId(_UlidIdentifier):
    KIND: ClassVar[str] = "CriterionId"


@dataclass(frozen=True, order=True)
class RiskId(_UlidIdentifier):
    KIND: ClassVar[str] = "RiskId"
