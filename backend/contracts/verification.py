"""Verification vocabulary.

Owner: BC-4 Verification.

Constitution P5: "Whatever produces a conclusion may not be the sole judge of
it. Verification uses a separate context, and where possible a separate model."

That independence is only meaningful if it is *recorded*, so ``VerificationResult``
carries a ``VerifierIdentity`` and refuses to construct when the verifier shares
a reasoning path with the producer. A verification that cannot demonstrate its
own independence is not verification.

Two distinct checks exist (Constitution S4):

* **Claim verification** -- is this conclusion supported by its cited evidence?
* **Outcome verification** -- did reality change as predicted?
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

from backend.contracts._contract import Contract
from backend.contracts.errors import ContractViolation

__all__ = [
    "Verdict",
    "VerificationTarget",
    "VerifierIdentity",
    "VerificationResult",
]


class Verdict(str, Enum):
    """The three honest answers a verifier can give."""

    SUPPORTED = "supported"
    """The evidence supports the claim."""

    UNSUPPORTED = "unsupported"
    """The evidence contradicts the claim or fails to support it."""

    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    """Cannot be adjudicated on what was gathered. Distinct from unsupported:
    "we don't know" is not "it's wrong", and conflating them either blocks
    correct actions or permits unfounded ones."""

    @property
    def permits_autonomous_action(self) -> bool:
        """Only a supported verdict clears autonomous action.

        Both other verdicts degrade to recommend-only (Constitution S6:
        "Prefer blocked over wrong").
        """
        return self is Verdict.SUPPORTED


class VerificationTarget(str, Enum):
    """What is being verified."""

    CLAIM = "claim"
    """Pre-execution: is the conclusion supported by evidence?"""

    OUTCOME = "outcome"
    """Post-execution: did the declared criteria come true?"""


@dataclass(frozen=True)
class VerifierIdentity(Contract):
    """Who or what performed a verification.

    ``reasoning_path_id`` identifies the context/prompt lineage used. Comparing
    it against the producer's is how independence is proven rather than assumed.
    """

    CONTRACT_NAME = "cortexprime.verification.verifier"

    verifier_id: str
    reasoning_path_id: str
    model_identifier: Optional[str] = None
    """The model used, when one was. ``None`` for deterministic verifiers --
    a criteria check against metrics needs no model and is stronger for it."""

    def __post_init__(self) -> None:
        for label, value in (
            ("verifier_id", self.verifier_id),
            ("reasoning_path_id", self.reasoning_path_id),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ContractViolation(f"{label} must be a non-blank string")

    def is_independent_of(self, producer_reasoning_path_id: str) -> bool:
        return self.reasoning_path_id != producer_reasoning_path_id


@dataclass(frozen=True)
class VerificationResult(Contract):
    """An adjudication, with proof that it was independent.

    Constructing this with a verifier sharing the producer's reasoning path
    raises. That makes P5 structural: the only way to record a verification is
    to have actually separated the paths.
    """

    CONTRACT_NAME = "cortexprime.verification.result"

    target: VerificationTarget
    subject_reference: str
    """What was verified -- a claim id or an execution key."""

    producer_reasoning_path_id: str
    """The reasoning path that produced the subject. Compared for independence."""

    verifier: VerifierIdentity
    verdict: Verdict
    rationale: str
    verified_at: datetime
    citation_ids: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not isinstance(self.target, VerificationTarget):
            raise ContractViolation("target must be a VerificationTarget")
        if not isinstance(self.verdict, Verdict):
            raise ContractViolation("verdict must be a Verdict")
        if not isinstance(self.subject_reference, str) or not self.subject_reference.strip():
            raise ContractViolation("subject_reference must be a non-blank string")
        if not isinstance(self.rationale, str) or not self.rationale.strip():
            raise ContractViolation(
                "rationale must be stated; an unexplained verdict cannot be reviewed"
            )
        if self.verified_at.tzinfo is None:
            raise ContractViolation("verified_at must be timezone-aware")
        if not isinstance(self.citation_ids, tuple):
            raise ContractViolation("citation_ids must be a tuple")

        # Constitution P5, enforced at construction.
        if not self.verifier.is_independent_of(self.producer_reasoning_path_id):
            raise ContractViolation(
                "verifier shares a reasoning path with the producer; self-verification "
                "creates correlated errors and does not satisfy Constitution P5"
            )

        if self.verdict is Verdict.SUPPORTED and not self.citation_ids:
            raise ContractViolation(
                "a supported verdict must cite the evidence that supports it "
                "(Constitution P1)"
            )
