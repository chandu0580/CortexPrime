"""Claims, assumption resolutions, and risk declarations.

The claim surface is what this whole context exists to produce. Until now the
Verification context received a placeholder claim from the runtime, because
nothing carried what the implementer actually asserted. These are those
assertions.

Every claim cites evidence
--------------------------
A claim with no evidence reference gives a verifier nothing to attack -- it can
only be taken on trust, which is the one thing verification exists not to do.
So :class:`Claim` refuses to be constructed without at least one reference.

The references are **opaque**. This context does not resolve them, and it must
not: the Evidence context does not exist, and a resolver that answered "yes"
would make the requirement unfalsifiable. What they buy today is that a verifier
knows which identifiers the implementer offered, and therefore which ones it may
not reuse when producing its own evidence (ADR-021).

Claim types mirror the Verification context
--------------------------------------------
Deliberately the same five values, and deliberately **not** an import -- S2
forbids one context importing another. ``test_claims.py`` asserts the two
vocabularies agree, converting the duplication into a checked invariant.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
from typing import Iterable, Optional

from backend.contracts._contract import Contract
from backend.contracts.errors import ContractViolation
from backend.contexts.implementation_record.domain.errors import (
    AssumptionAlreadyResolved,
    ClaimWithoutEvidence,
)
from backend.contexts.implementation_record.domain.identifiers import ClaimId, RiskId

__all__ = [
    "ClaimType",
    "EvidenceRef",
    "Claim",
    "AssumptionOutcome",
    "AssumptionResolution",
    "RiskLevel",
    "RiskDeclaration",
    "CriterionCoverage",
]


class ClaimType(str, Enum):
    """What kind of assertion this is.

    The type determines what a verifier must do to settle it, which is why it is
    recorded here rather than inferred there. An implementer knows whether it is
    claiming a count or an impossibility; a verifier reading prose does not.
    """

    COUNT = "count"
    BEHAVIOUR = "behaviour"
    ABSENCE = "absence"
    EQUIVALENCE = "equivalence"
    PERFORMANCE = "performance"

    @property
    def needs_adversarial_verification(self) -> bool:
        """Whether settling this requires constructing the violation.

        Only ``ABSENCE``. Running the suite and seeing green shows that nothing
        tried; it says nothing about whether something *could*. Flagged here so an
        implementer knows what it is asking of the verifier before it asks.
        """
        return self is ClaimType.ABSENCE

    @property
    def is_easily_wrong(self) -> bool:
        """``COUNT`` claims look trivially verifiable and are the ones most often
        wrong, because the counting mechanism is itself untested."""
        return self is ClaimType.COUNT


@dataclass(frozen=True, order=True)
class EvidenceRef:
    """An identifier the implementer offers as support. Opaque here.

    Deliberately carries no content and no trust level. This context records
    which identifiers were offered; it does not read them and cannot vouch for
    them. The Verification context produces its own evidence and refuses to reuse
    these (ADR-021).
    """

    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str) or not self.value.strip():
            raise ContractViolation("an evidence reference must be non-blank text")
        if self.value != self.value.strip():
            raise ContractViolation(
                "an evidence reference must not have surrounding whitespace"
            )

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class Claim(Contract):
    """One assertion the implementer makes about its own work."""

    CONTRACT_NAME = "cortexprime.engineering.implementation_claim"

    claim_id: ClaimId
    statement: str
    claim_type: ClaimType
    evidence: frozenset = field(default_factory=frozenset)
    reproduction_hint: Optional[str] = None

    def __post_init__(self) -> None:
        if not isinstance(self.claim_id, ClaimId):
            raise ContractViolation("claim_id must be a ClaimId")
        if not isinstance(self.statement, str) or not self.statement.strip():
            raise ContractViolation("a claim must state something")
        if self.statement != self.statement.strip():
            raise ContractViolation("statement must not have surrounding whitespace")
        if not isinstance(self.claim_type, ClaimType):
            raise ContractViolation("claim_type must be a ClaimType")

        if not isinstance(self.evidence, (frozenset, set)):
            raise ContractViolation("evidence must be a set")
        for item in self.evidence:
            if not isinstance(item, EvidenceRef):
                raise ContractViolation(
                    f"evidence contains {item!r}, which is not an EvidenceRef"
                )
        object.__setattr__(self, "evidence", frozenset(self.evidence))

        if not self.evidence:
            raise ClaimWithoutEvidence(self.statement)

    @classmethod
    def create(
        cls,
        statement: str,
        claim_type: ClaimType,
        evidence: Iterable[str],
        *,
        reproduction_hint: Optional[str] = None,
    ) -> "Claim":
        return cls(
            claim_id=ClaimId.new(),
            statement=statement,
            claim_type=claim_type,
            evidence=frozenset(EvidenceRef(e) for e in evidence),
            reproduction_hint=reproduction_hint,
        )

    @property
    def evidence_ids(self) -> tuple:
        return tuple(sorted(str(e) for e in self.evidence))

    def __str__(self) -> str:  # pragma: no cover - diagnostic only
        return f"{self.claim_type.value}:{self.statement[:50]}"


class AssumptionOutcome(str, Enum):
    """What checking a WorkOrder's assumption produced."""

    CONFIRMED = "confirmed"
    CONTRADICTED = "contradicted"
    UNVERIFIABLE = "unverifiable"

    @property
    def permits_completion(self) -> bool:
        """Only ``CONFIRMED`` does.

        ``UNVERIFIABLE`` blocks alongside ``CONTRADICTED``: proceeding on a belief
        nobody could check carries the same risk as proceeding on one found
        false, minus the knowledge that it was.
        """
        return self is AssumptionOutcome.CONFIRMED

    @property
    def implies_rejection(self) -> bool:
        """A contradicted assumption means the WorkOrder's premise was false.

        The correct response is a ``PREMISE_FALSE`` rejection, not an
        implementation that works around it.
        """
        return self is AssumptionOutcome.CONTRADICTED


@dataclass(frozen=True)
class AssumptionResolution(Contract):
    """The outcome of checking one assumption the WorkOrder declared."""

    CONTRACT_NAME = "cortexprime.engineering.implementation_assumption_resolution"

    assumption_id: str
    statement: str
    outcome: AssumptionOutcome
    evidence: frozenset = field(default_factory=frozenset)
    note: Optional[str] = None
    resolved_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        for label, value in (
            ("assumption_id", self.assumption_id),
            ("statement", self.statement),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ContractViolation(f"{label} must be non-blank text")
        if not isinstance(self.outcome, AssumptionOutcome):
            raise ContractViolation("outcome must be an AssumptionOutcome")

        if not isinstance(self.evidence, (frozenset, set)):
            raise ContractViolation("evidence must be a set")
        for item in self.evidence:
            if not isinstance(item, EvidenceRef):
                raise ContractViolation(
                    f"evidence contains {item!r}, which is not an EvidenceRef"
                )
        object.__setattr__(self, "evidence", frozenset(self.evidence))

        # Every outcome cites what was checked, including "unverifiable". "I tried
        # and could not determine" is itself a finding, and recording it without
        # saying what was tried makes it indistinguishable from not having looked.
        if not self.evidence:
            raise ContractViolation(
                f"assumption {self.assumption_id} resolved {self.outcome.value!r} with no "
                "evidence; every resolution must cite what was checked, including "
                "'unverifiable'"
            )
        if self.resolved_at.tzinfo is None:
            raise ContractViolation("resolved_at must be timezone-aware")

    @classmethod
    def create(
        cls,
        assumption_id: str,
        statement: str,
        outcome: AssumptionOutcome,
        evidence: Iterable[str],
        *,
        note: Optional[str] = None,
    ) -> "AssumptionResolution":
        return cls(
            assumption_id=assumption_id,
            statement=statement,
            outcome=outcome,
            evidence=frozenset(EvidenceRef(e) for e in evidence),
            note=note,
        )

    @property
    def permits_completion(self) -> bool:
        return self.outcome.permits_completion


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

    @property
    def rank(self) -> int:
        return {RiskLevel.LOW: 0, RiskLevel.MEDIUM: 1, RiskLevel.HIGH: 2}[self]

    @property
    def requires_mitigation(self) -> bool:
        """A declared risk above LOW must say what was done about it.

        A risk declared and left unaddressed is a note; a risk with a stated
        mitigation is a decision. Only the second is reviewable.
        """
        return self.rank >= RiskLevel.MEDIUM.rank


@dataclass(frozen=True)
class RiskDeclaration(Contract):
    """Something the implementer knows could go wrong, declared rather than hidden.

    Declared by the implementer about its own work. That is unusual and
    deliberate: the party who wrote the change knows things about it that no
    reviewer will find, and the cheapest moment to surface them is before anyone
    else has spent effort looking.
    """

    CONTRACT_NAME = "cortexprime.engineering.risk_declaration"

    risk_id: RiskId
    statement: str
    level: RiskLevel
    mitigation: Optional[str] = None
    affected_paths: tuple = ()

    def __post_init__(self) -> None:
        if not isinstance(self.risk_id, RiskId):
            raise ContractViolation("risk_id must be a RiskId")
        if not isinstance(self.statement, str) or not self.statement.strip():
            raise ContractViolation("a risk must state what could go wrong")
        if not isinstance(self.level, RiskLevel):
            raise ContractViolation("level must be a RiskLevel")
        if not isinstance(self.affected_paths, tuple):
            raise ContractViolation("affected_paths must be a tuple")

        if self.level.requires_mitigation and not (
            self.mitigation and self.mitigation.strip()
        ):
            raise ContractViolation(
                f"a {self.level.value} risk must state its mitigation; a risk declared "
                "and left unaddressed is a note, not a decision"
            )

    @classmethod
    def create(
        cls,
        statement: str,
        level: RiskLevel,
        *,
        mitigation: Optional[str] = None,
        affected_paths: Iterable[str] = (),
    ) -> "RiskDeclaration":
        return cls(
            risk_id=RiskId.new(),
            statement=statement,
            level=level,
            mitigation=mitigation,
            affected_paths=tuple(affected_paths),
        )


@dataclass(frozen=True)
class CriterionCoverage(Contract):
    """One acceptance criterion, and the tests said to prove it.

    ``negative_check`` records evidence that the covering test **fails without
    the change**. Absent here is not a failure -- producing it is the Verifier's
    job (ADR-021) -- but recording it when the implementer has it saves a round
    trip, and its absence is visible rather than assumed.
    """

    CONTRACT_NAME = "cortexprime.engineering.criterion_coverage"

    criterion: str
    covering_tests: tuple = ()
    negative_check: Optional[str] = None

    def __post_init__(self) -> None:
        if not isinstance(self.criterion, str) or not self.criterion.strip():
            raise ContractViolation("a coverage entry must name its criterion")
        if not isinstance(self.covering_tests, tuple):
            raise ContractViolation("covering_tests must be a tuple")
        if not self.covering_tests:
            raise ContractViolation(
                f"criterion {self.criterion[:50]!r} claims coverage but names no test; "
                "an uncovered criterion recorded as covered is worse than one left out"
            )

    @property
    def has_negative_check(self) -> bool:
        return bool(self.negative_check)
