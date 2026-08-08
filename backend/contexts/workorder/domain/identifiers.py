"""Strongly-typed identifiers.

Every identifier is a distinct type, not a bare string. The cost is a wrapper;
the benefit is that passing an assumption id where a work order id belongs fails
at construction rather than producing a lookup that quietly returns nothing.

All are ULID-backed, using the platform's monotonic factory. That buys ordering
for free: a list of WorkOrders sorted by id is in creation order without a
separate timestamp column, and the ordering never contradicts real time.

The guarantee ULID actually gives is worth restating, because it is weaker than
people assume: lexicographic order never *contradicts* time order. Two ids
minted in the same millisecond tie rather than sort. Nothing here depends on
breaking that tie.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from backend.contexts.workorder.domain.errors import InvalidIdentifier
from backend.platform.identity import is_ulid, monotonic_ulid, timestamp_of

__all__ = [
    "WorkOrderId",
    "AssumptionId",
    "RejectionGroundId",
    "EvidenceRef",
    "AdrRef",
    "ConstraintRef",
]


@dataclass(frozen=True, order=True)
class _UlidIdentifier:
    """Shared behaviour for ULID-backed identifiers.

    ``order=True`` makes identifiers directly sortable, which is the whole point
    of choosing ULID over UUID.
    """

    KIND: ClassVar[str] = "identifier"

    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str):
            raise InvalidIdentifier(
                type(self).KIND, self.value, f"expected a string, got {type(self.value).__name__}"
            )
        if not is_ulid(self.value):
            raise InvalidIdentifier(type(self).KIND, self.value, "not a valid ULID")

    @classmethod
    def new(cls):
        """Mint a fresh identifier."""
        return cls(monotonic_ulid())

    @property
    def created_at_ms(self) -> int:
        """Milliseconds since epoch, recovered from the identifier itself."""
        return timestamp_of(self.value)

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, order=True)
class WorkOrderId(_UlidIdentifier):
    KIND: ClassVar[str] = "WorkOrderId"


@dataclass(frozen=True, order=True)
class AssumptionId(_UlidIdentifier):
    KIND: ClassVar[str] = "AssumptionId"


@dataclass(frozen=True, order=True)
class RejectionGroundId(_UlidIdentifier):
    KIND: ClassVar[str] = "RejectionGroundId"


# ----------------------------------------------------------------------
# References to artifacts owned by other contexts
# ----------------------------------------------------------------------
#
# These are opaque here. The WorkOrder context validates only that a reference
# is well-formed; whether it *resolves* is decided by a resolver injected from
# outside (see domain/validation.py). Resolving them here would require importing
# the contexts that own them, which S2 forbids.


@dataclass(frozen=True, order=True)
class _OpaqueReference:
    KIND: ClassVar[str] = "reference"
    MIN_LENGTH: ClassVar[int] = 1

    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str):
            raise InvalidIdentifier(
                type(self).KIND, self.value, f"expected a string, got {type(self.value).__name__}"
            )
        stripped = self.value.strip()
        if not stripped:
            raise InvalidIdentifier(type(self).KIND, self.value, "must not be blank")
        if stripped != self.value:
            raise InvalidIdentifier(
                type(self).KIND, self.value, "must not have leading or trailing whitespace"
            )
        if len(stripped) < type(self).MIN_LENGTH:
            raise InvalidIdentifier(
                type(self).KIND, self.value, f"must be at least {type(self).MIN_LENGTH} characters"
            )

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, order=True)
class EvidenceRef(_OpaqueReference):
    """A reference to an EvidenceRecord, owned by the Evidence context."""

    KIND: ClassVar[str] = "EvidenceRef"


@dataclass(frozen=True, order=True)
class AdrRef(_OpaqueReference):
    """A reference to an architecture decision record, e.g. ``ADR-018``."""

    KIND: ClassVar[str] = "AdrRef"
    MIN_LENGTH: ClassVar[int] = 3


@dataclass(frozen=True, order=True)
class ConstraintRef(_OpaqueReference):
    """An invariant, structural rule, or architecture rule id, e.g. ``I6``."""

    KIND: ClassVar[str] = "ConstraintRef"
