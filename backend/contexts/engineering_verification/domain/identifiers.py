"""Strongly-typed identifiers for the Verification context.

ULID-backed, so a list of verifications sorted by id is in creation order without
a separate timestamp column. Distinct types, so an evidence id cannot be passed
where a claim id belongs -- which in this context is not a theoretical concern:
the whole design turns on keeping the implementer's evidence references and the
verifier's own findings apart.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from backend.contexts.engineering_verification.domain.errors import InvalidIdentifier
from backend.platform.identity import is_ulid, monotonic_ulid, timestamp_of

__all__ = ["VerificationId", "ClaimId", "EvidenceId"]


@dataclass(frozen=True, order=True)
class _UlidIdentifier:
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
        return cls(monotonic_ulid())

    @property
    def created_at_ms(self) -> int:
        return timestamp_of(self.value)

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, order=True)
class VerificationId(_UlidIdentifier):
    KIND: ClassVar[str] = "VerificationId"


@dataclass(frozen=True, order=True)
class ClaimId(_UlidIdentifier):
    KIND: ClassVar[str] = "ClaimId"


@dataclass(frozen=True, order=True)
class EvidenceId(_UlidIdentifier):
    KIND: ClassVar[str] = "EvidenceId"
