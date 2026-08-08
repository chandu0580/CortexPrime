"""Strongly-typed identifiers for the Review context.

ULID-backed, so a list of reviews sorted by id is in request order without a
separate timestamp column. Distinct types, so a comment id cannot be passed where
a finding id belongs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from backend.contexts.review.domain.errors import InvalidIdentifier
from backend.platform.identity import is_ulid, monotonic_ulid, timestamp_of

__all__ = ["ReviewId", "FindingId", "CommentId"]


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
class ReviewId(_UlidIdentifier):
    KIND: ClassVar[str] = "ReviewId"


@dataclass(frozen=True, order=True)
class FindingId(_UlidIdentifier):
    KIND: ClassVar[str] = "FindingId"


@dataclass(frozen=True, order=True)
class CommentId(_UlidIdentifier):
    KIND: ClassVar[str] = "CommentId"
