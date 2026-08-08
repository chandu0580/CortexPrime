"""Evidence, and the trust it can carry.

The central rule of this context is expressed in the type system rather than in a
check: **what the implementer points at and what the verifier produces are
different types.**

An implementer's evidence arrives as :class:`AssertedEvidenceRef` -- an opaque
identifier, nothing more. The verifier's own findings are
:class:`VerifiedEvidence`, which cannot be constructed without saying how it was
collected and how strongly it is held.

A :class:`~...results.ClaimResult` requires ``VerifiedEvidence``. There is no
conversion from one to the other, so "verification" that merely re-points at the
implementer's artifact does not type-check. That is stronger than any runtime
check, because it fails at the call site rather than at the end of a run.

A runtime check backs it up anyway (see ``BorrowedEvidence``), because someone
can always wrap an implementer's identifier in a new ``VerifiedEvidence`` and
claim to have collected it.

Trust levels
------------
The trust level of the weakest supporting evidence bounds the strength of any
claim resting on it::

    DETERMINISTIC   reproduces identically for anyone at the same commit
    ENVIRONMENTAL   reproduces given the recorded environment
    OBSERVED        was true once, cannot be re-established
    ASSERTED        no evidence collected -- never admissible

``OBSERVED`` is the awkward one, and it is deliberately second-class rather than
excluded. Live validation against a real external system produces exactly this,
and it is the most valuable evidence there is for whether something actually
works -- but it cannot be reproduced, so it can never be the sole support for a
gate. ``ASSERTED`` exists in the enumeration so it can be named and refused,
rather than passing silently as absence.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from backend.contracts._contract import Contract
from backend.contracts.errors import ContractViolation
from backend.contexts.engineering_verification.domain.identifiers import EvidenceId

__all__ = [
    "EvidenceKind",
    "TrustLevel",
    "AssertedEvidenceRef",
    "VerifiedEvidence",
]


class EvidenceKind(str, Enum):
    """What sort of thing was observed."""

    REPOSITORY = "repository"
    COMMAND = "command"
    ADR = "adr"
    TEST = "test"
    EXTERNAL = "external"
    ABSENCE = "absence"

    @property
    def requires_base_commit(self) -> bool:
        """Whether this kind is meaningless without a tree to bind it to.

        A file citation, a test outcome, or a command result describes a
        particular tree. The same citation against a different commit is a
        different fact.
        """
        return self in {EvidenceKind.REPOSITORY, EvidenceKind.COMMAND, EvidenceKind.TEST}

    @property
    def is_reproducible(self) -> bool:
        """``EXTERNAL`` is not: the external system has moved on."""
        return self is not EvidenceKind.EXTERNAL


class TrustLevel(str, Enum):
    DETERMINISTIC = "deterministic"
    ENVIRONMENTAL = "environmental"
    OBSERVED = "observed"
    ASSERTED = "asserted"

    @property
    def rank(self) -> int:
        return {
            TrustLevel.ASSERTED: 0,
            TrustLevel.OBSERVED: 1,
            TrustLevel.ENVIRONMENTAL: 2,
            TrustLevel.DETERMINISTIC: 3,
        }[self]

    @property
    def is_admissible(self) -> bool:
        """``ASSERTED`` never is. It is the absence of evidence, named."""
        return self is not TrustLevel.ASSERTED

    @property
    def can_stand_alone(self) -> bool:
        """Whether this may be the *only* support for a gate.

        ``OBSERVED`` cannot. It was true once and cannot be re-established, so a
        merge condition resting on it alone is a condition nobody can re-check.
        """
        return self.rank >= TrustLevel.ENVIRONMENTAL.rank

    def at_least(self, floor: "TrustLevel") -> bool:
        return self.rank >= floor.rank


@dataclass(frozen=True, order=True)
class AssertedEvidenceRef:
    """An implementer's evidence reference. Opaque, and never admissible on its own.

    Deliberately carries no trust level, no content, and no collection method --
    only an identifier. The verifier is not meant to read it; it is meant to know
    which identifiers it must *not* reuse.
    """

    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str) or not self.value.strip():
            raise ContractViolation("an asserted evidence reference must be non-blank text")
        if self.value != self.value.strip():
            raise ContractViolation(
                "an asserted evidence reference must not have surrounding whitespace"
            )

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class VerifiedEvidence(Contract):
    """Something the verifier established for itself.

    Cannot be constructed without saying what was done and how strongly the
    result is held. That is the point: evidence with no stated collection method
    is an assertion wearing evidence's clothes.
    """

    CONTRACT_NAME = "cortexprime.engineering.verified_evidence"

    evidence_id: EvidenceId
    kind: EvidenceKind
    trust: TrustLevel
    summary: str
    collected_by: str
    base_commit: Optional[str] = None
    detail: Optional[str] = None
    collected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if not isinstance(self.evidence_id, EvidenceId):
            raise ContractViolation("evidence_id must be an EvidenceId")
        if not isinstance(self.kind, EvidenceKind):
            raise ContractViolation("kind must be an EvidenceKind")
        if not isinstance(self.trust, TrustLevel):
            raise ContractViolation("trust must be a TrustLevel")

        for label, value in (("summary", self.summary), ("collected_by", self.collected_by)):
            if not isinstance(value, str) or not value.strip():
                raise ContractViolation(f"{label} must be non-blank text")

        # ASSERTED cannot be *collected*. The level exists so a claim resting on
        # nothing can be named and refused, not so it can be recorded as a finding.
        if self.trust is TrustLevel.ASSERTED:
            raise ContractViolation(
                "verified evidence cannot be ASSERTED; that level names the absence of "
                "evidence and exists only to be refused"
            )

        if self.kind.requires_base_commit and not self.base_commit:
            raise ContractViolation(
                f"{self.kind.value} evidence describes a particular tree and must record "
                "the base commit it was collected against"
            )

        # External observations cannot be re-established, so claiming they
        # reproduce identically for anyone is false on its face.
        if self.kind is EvidenceKind.EXTERNAL and self.trust.at_least(TrustLevel.ENVIRONMENTAL):
            raise ContractViolation(
                "external evidence cannot be better than OBSERVED; the external system "
                "has moved on and nobody can re-establish what it said"
            )

        if self.collected_at.tzinfo is None:
            raise ContractViolation("collected_at must be timezone-aware")

    # ------------------------------------------------------------------

    @classmethod
    def create(
        cls,
        kind: EvidenceKind,
        trust: TrustLevel,
        summary: str,
        *,
        collected_by: str = "verifier",
        base_commit: Optional[str] = None,
        detail: Optional[str] = None,
    ) -> "VerifiedEvidence":
        return cls(
            evidence_id=EvidenceId.new(),
            kind=kind,
            trust=trust,
            summary=summary,
            collected_by=collected_by,
            base_commit=base_commit,
            detail=detail,
        )

    @property
    def is_stale_against(self) -> bool:  # pragma: no cover - see stale_against
        raise NotImplementedError

    def stale_against(self, current_commit: Optional[str]) -> bool:
        """Whether this evidence describes a tree other than the one being merged.

        Kinds that do not bind to a commit are never stale; an ADR citation does
        not stop being true because the tree moved.
        """
        if not self.kind.requires_base_commit or current_commit is None:
            return False
        return self.base_commit != current_commit

    def __str__(self) -> str:  # pragma: no cover - diagnostic only
        return f"{self.kind.value}/{self.trust.value}:{self.evidence_id}"
