"""The verdict on one claim.

A :class:`ClaimResult` requires :class:`~..evidence.VerifiedEvidence` -- the
verifier's own finding, not the implementer's reference. There is no conversion
between the two types, so "verification" that re-points at the implementer's
artifact does not type-check.

Four verdicts, and the last two are not failures
------------------------------------------------
``REPRODUCED``      the verifier established the claim independently
``CONTRADICTED``    the verifier established the opposite
``UNREPRODUCIBLE``  the verifier could not establish either
``OUT_OF_SCOPE``    the claim concerns something this verification does not cover

``UNREPRODUCIBLE`` is deliberately not a soft ``REPRODUCED``. A claim nobody
could check carries the same risk as one checked and found false, minus the
knowledge that it was -- so it blocks a complete verification just as a
contradiction does.

``OUT_OF_SCOPE`` exists so a verifier can say "this is real but not mine" without
either passing it or failing it. Silence would be indistinguishable from having
missed it.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from backend.contracts._contract import Contract
from backend.contracts.errors import ContractViolation
from backend.contexts.engineering_verification.domain.claim import (
    Claim,
    Determinism,
    ReproductionStep,
)
from backend.contexts.engineering_verification.domain.errors import (
    BorrowedEvidence,
    ReproductionInadequate,
)
from backend.contexts.engineering_verification.domain.evidence import (
    TrustLevel,
    VerifiedEvidence,
)
from backend.contexts.engineering_verification.domain.identifiers import ClaimId

__all__ = ["ClaimVerdict", "ClaimResult"]


class ClaimVerdict(str, Enum):
    REPRODUCED = "reproduced"
    CONTRADICTED = "contradicted"
    UNREPRODUCIBLE = "unreproducible"
    OUT_OF_SCOPE = "out_of_scope"

    @property
    def permits_completion(self) -> bool:
        """Whether a verification containing this verdict may be marked complete.

        ``OUT_OF_SCOPE`` does, because it is an honest statement about coverage
        rather than an unresolved question. ``UNREPRODUCIBLE`` does not.
        """
        return self in {ClaimVerdict.REPRODUCED, ClaimVerdict.OUT_OF_SCOPE}

    @property
    def is_finding(self) -> bool:
        """Whether this verdict is itself a finding worth surfacing."""
        return self in {ClaimVerdict.CONTRADICTED, ClaimVerdict.UNREPRODUCIBLE}


@dataclass(frozen=True)
class ClaimResult(Contract):
    """What the verifier found, and the evidence it produced finding it."""

    CONTRACT_NAME = "cortexprime.engineering.claim_result"

    claim: Claim
    reproduction: ReproductionStep
    observed: str
    verdict: ClaimVerdict
    verdict_evidence: Optional[VerifiedEvidence] = None
    note: Optional[str] = None

    def __post_init__(self) -> None:
        if not isinstance(self.claim, Claim):
            raise ContractViolation("claim must be a Claim")
        if not isinstance(self.reproduction, ReproductionStep):
            raise ContractViolation("reproduction must be a ReproductionStep")
        if not isinstance(self.verdict, ClaimVerdict):
            raise ContractViolation("verdict must be a ClaimVerdict")
        if not isinstance(self.observed, str) or not self.observed.strip():
            raise ContractViolation(
                "observed must state what actually happened; a verdict with no "
                "observation is an opinion"
            )

        # OUT_OF_SCOPE is the one verdict that needs no evidence -- the verifier
        # is declining to rule, not ruling. Everything else must show its working.
        if self.verdict is ClaimVerdict.OUT_OF_SCOPE:
            if self.verdict_evidence is not None:
                raise ContractViolation(
                    "an out-of-scope claim was not examined, so it cannot carry evidence"
                )
            if not self.note or not self.note.strip():
                raise ContractViolation(
                    "an out-of-scope verdict must say why the claim is outside this "
                    "verification's coverage"
                )
            return

        if self.verdict_evidence is None:
            raise ContractViolation(
                f"a {self.verdict.value} verdict must carry the evidence the verifier "
                "produced reaching it"
            )
        if not isinstance(self.verdict_evidence, VerifiedEvidence):
            raise ContractViolation(
                "verdict_evidence must be VerifiedEvidence; an implementer's reference "
                "is not a reproduction"
            )

        # Wrapping the implementer's identifier in new evidence is the obvious way
        # around the type separation, so it is checked explicitly.
        if self.claim.borrows(str(self.verdict_evidence.evidence_id)):
            raise BorrowedEvidence(
                claim_id=str(self.claim.claim_id),
                evidence_id=str(self.verdict_evidence.evidence_id),
            )

        if not self.verdict_evidence.trust.is_admissible:
            raise ContractViolation(
                f"verdict evidence is {self.verdict_evidence.trust.value}, which names "
                "the absence of evidence and is never admissible"
            )

        # A method that cannot establish what the claim asserts settles nothing,
        # however carefully it was run.
        if self.verdict is ClaimVerdict.REPRODUCED and not self.reproduction.settles(
            self.claim.claim_type
        ):
            required = self.claim.claim_type.required_method
            raise ReproductionInadequate(
                claim_id=str(self.claim.claim_id),
                claim_type=self.claim.claim_type.value,
                method=self.reproduction.method.value,
                required=required.value if required else "a suitable method",
            )

        # A flaky proof is not a proof.
        if self.verdict is ClaimVerdict.REPRODUCED and not self.reproduction.can_prove:
            raise ContractViolation(
                f"claim {self.claim.claim_id} was marked reproduced from a "
                "nondeterministic reproduction; repeated runs disagreed, so the claim "
                "was not established"
            )

    # ------------------------------------------------------------------

    @property
    def claim_id(self) -> ClaimId:
        return self.claim.claim_id

    @property
    def permits_completion(self) -> bool:
        return self.verdict.permits_completion

    @property
    def trust(self) -> TrustLevel:
        """The strength of this result, bounded by its evidence.

        An out-of-scope result has no evidence and therefore no trust to report;
        it is excluded from strength calculations rather than counted as zero.
        """
        if self.verdict_evidence is None:
            return TrustLevel.ASSERTED
        return self.verdict_evidence.trust

    def stale_against(self, current_commit: Optional[str]) -> bool:
        if self.verdict_evidence is None:
            return False
        return self.verdict_evidence.stale_against(current_commit)

    def __str__(self) -> str:  # pragma: no cover - diagnostic only
        return f"{self.claim.claim_type.value}:{self.verdict.value}"
