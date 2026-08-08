"""Claims under verification, and how they may be reproduced.

A claim arrives from outside as data: its statement, its type, and the identifiers
the implementer offered as support. This context never resolves those
identifiers -- it only records which ones may not be reused.

Claim type determines the reproduction that can settle it
---------------------------------------------------------
This is the rule that makes verification more than re-running the tests.

An ``ABSENCE`` claim -- *"no cross-tenant read is possible"*, *"there are no
remaining violations"* -- cannot be settled by observing success. Running the
suite and seeing green shows that nothing tried; it says nothing about whether
something *could*. Only constructing the violation and observing refusal does.

A ``COUNT`` claim looks trivially verifiable and is the one most often wrong,
because the counting mechanism is itself untested. It must be reproduced by a
method that recounts independently, not by reading the number back.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from backend.contracts._contract import Contract
from backend.contracts.errors import ContractViolation
from backend.contexts.engineering_verification.domain.identifiers import ClaimId
from backend.contexts.engineering_verification.domain.evidence import AssertedEvidenceRef

__all__ = ["ClaimType", "ReproductionMethod", "Determinism", "Claim", "ReproductionStep"]


class ReproductionMethod(str, Enum):
    COMMAND_EXECUTION = "command_execution"
    SOURCE_INSPECTION = "source_inspection"
    ADVERSARIAL_CONSTRUCTION = "adversarial_construction"
    NEGATIVE_CHECK = "negative_check"

    @property
    def establishes_impossibility(self) -> bool:
        """Whether this method can settle a claim that something *cannot* happen."""
        return self is ReproductionMethod.ADVERSARIAL_CONSTRUCTION


class Determinism(str, Enum):
    DETERMINISTIC = "deterministic"
    ENVIRONMENT_DEPENDENT = "environment_dependent"
    NONDETERMINISTIC = "nondeterministic"

    @property
    def can_prove(self) -> bool:
        """A flaky proof is not a proof.

        A reproduction whose repeated runs disagree cannot establish that a claim
        holds -- it establishes only that it sometimes appears to.
        """
        return self is not Determinism.NONDETERMINISTIC


class ClaimType(str, Enum):
    COUNT = "count"
    BEHAVIOUR = "behaviour"
    ABSENCE = "absence"
    EQUIVALENCE = "equivalence"
    PERFORMANCE = "performance"

    @property
    def required_method(self) -> Optional[ReproductionMethod]:
        """The method this claim type demands, if it demands one.

        Only ``ABSENCE`` does. The others can legitimately be settled several
        ways, and forcing a single method would make the rule feel arbitrary --
        which is how rules get worked around.
        """
        if self is ClaimType.ABSENCE:
            return ReproductionMethod.ADVERSARIAL_CONSTRUCTION
        return None

    @property
    def demands_independent_measurement(self) -> bool:
        """Whether reading the value back is insufficient.

        ``COUNT`` claims are singled out because they look trivially verifiable
        and are the ones most often wrong: the counting mechanism is itself
        untested, so recounting the same way reproduces the same error.
        """
        return self is ClaimType.COUNT


@dataclass(frozen=True)
class Claim(Contract):
    """One assertion under verification.

    ``asserted_evidence`` holds the implementer's references. This context does
    not resolve them and does not read them -- it records them so it can refuse a
    verdict that reuses one.
    """

    CONTRACT_NAME = "cortexprime.engineering.verification_claim"

    claim_id: ClaimId
    statement: str
    claim_type: ClaimType
    asserted_evidence: frozenset = field(default_factory=frozenset)
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

        if not isinstance(self.asserted_evidence, (frozenset, set)):
            raise ContractViolation("asserted_evidence must be a set")
        for item in self.asserted_evidence:
            if not isinstance(item, AssertedEvidenceRef):
                raise ContractViolation(
                    f"asserted_evidence contains {item!r}, which is not an "
                    "AssertedEvidenceRef; the implementer's references are opaque here"
                )
        object.__setattr__(self, "asserted_evidence", frozenset(self.asserted_evidence))

    @classmethod
    def create(
        cls,
        statement: str,
        claim_type: ClaimType,
        *,
        asserted_evidence: tuple = (),
        reproduction_hint: Optional[str] = None,
    ) -> "Claim":
        return cls(
            claim_id=ClaimId.new(),
            statement=statement,
            claim_type=claim_type,
            asserted_evidence=frozenset(AssertedEvidenceRef(e) for e in asserted_evidence),
            reproduction_hint=reproduction_hint,
        )

    def borrows(self, evidence_id: str) -> bool:
        """Whether ``evidence_id`` is one the implementer already offered."""
        return any(str(ref) == str(evidence_id) for ref in self.asserted_evidence)


@dataclass(frozen=True)
class ReproductionStep(Contract):
    """How the verifier tried to settle a claim."""

    CONTRACT_NAME = "cortexprime.engineering.reproduction_step"

    method: ReproductionMethod
    specification: str
    determinism: Determinism = Determinism.DETERMINISTIC
    runs: int = 1

    def __post_init__(self) -> None:
        if not isinstance(self.method, ReproductionMethod):
            raise ContractViolation("method must be a ReproductionMethod")
        if not isinstance(self.determinism, Determinism):
            raise ContractViolation("determinism must be a Determinism")
        if not isinstance(self.specification, str) or not self.specification.strip():
            raise ContractViolation(
                "a reproduction must state exactly what was run, inspected, or "
                "constructed; 'we checked' is not a reproduction"
            )
        if not isinstance(self.runs, int) or self.runs < 1:
            raise ContractViolation("runs must be a positive integer")

        # Claiming determinism from a single run is an assertion about repeated
        # behaviour made without repeating it.
        if self.determinism is Determinism.DETERMINISTIC and self.runs < 1:
            raise ContractViolation("a deterministic reproduction must have run at least once")

    @property
    def can_prove(self) -> bool:
        return self.determinism.can_prove

    def settles(self, claim_type: ClaimType) -> bool:
        """Whether this method can establish what a claim of that type asserts."""
        required = claim_type.required_method
        return required is None or self.method is required
