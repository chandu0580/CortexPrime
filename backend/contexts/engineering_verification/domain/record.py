"""The VerificationRecord aggregate, and the request that starts one.

Immutable, like every other domain layer in this codebase. Recording a result
returns a new record, so two concurrent verifiers cannot observe each other's
half-applied state.

Status, and why ``Incomplete`` is not a soft ``Complete``
---------------------------------------------------------
::

    REQUESTED    asked for; nobody has begun
    RUNNING      a verifier is working
    COMPLETE     every claim reproduced, nothing outstanding
    FAILED       at least one claim contradicted
    INCOMPLETE   at least one claim could not be reproduced either way
    INVALIDATED  an approved premise turned out to be false
    STALE        the tree moved; every claim must be reproduced again

``INCOMPLETE`` and ``FAILED`` are separate because they mean different things to
whoever reads the record. ``FAILED`` says the work is wrong. ``INCOMPLETE`` says
the verifier could not tell -- which is a fact about the verification, not the
work, and merging on it is a different decision requiring different information.

Collapsing them into "not complete" is the change that makes a verification
report useless: it removes exactly the distinction the reader needs.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from backend.contracts._contract import Contract
from backend.contracts.errors import ContractViolation
from backend.contexts.engineering_verification.domain.claim import Claim
from backend.contexts.engineering_verification.domain.errors import (
    ClaimAlreadyResolved,
    ClaimNotRequested,
    VerificationAlreadyClosed,
    VerificationNotStarted,
)
from backend.contexts.engineering_verification.domain.evidence import (
    TrustLevel,
    VerifiedEvidence,
)
from backend.contexts.engineering_verification.domain.identifiers import (
    ClaimId,
    VerificationId,
)
from backend.contexts.engineering_verification.domain.results import ClaimResult, ClaimVerdict

__all__ = ["VerificationStatus", "VerificationRequest", "VerificationRecord"]


class VerificationStatus(str, Enum):
    REQUESTED = "requested"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"
    INCOMPLETE = "incomplete"
    INVALIDATED = "invalidated"
    STALE = "stale"

    @property
    def is_terminal(self) -> bool:
        return self in {
            VerificationStatus.COMPLETE,
            VerificationStatus.FAILED,
            VerificationStatus.INCOMPLETE,
            VerificationStatus.INVALIDATED,
        }

    @property
    def is_open(self) -> bool:
        return self in {VerificationStatus.REQUESTED, VerificationStatus.RUNNING}

    @property
    def permits_ready(self) -> bool:
        """Whether a WorkOrder may move to Ready on this outcome. Only one does."""
        return self is VerificationStatus.COMPLETE


@dataclass(frozen=True)
class VerificationRequest(Contract):
    """What was asked for: a WorkOrder, an attempt, and the claims to settle."""

    CONTRACT_NAME = "cortexprime.engineering.verification_request"

    work_id: str
    attempt: int
    claims: tuple
    base_commit: str
    requested_by: str = "engineering-runtime"

    def __post_init__(self) -> None:
        if not isinstance(self.work_id, str) or not self.work_id.strip():
            raise ContractViolation("work_id must be non-blank text")
        if not isinstance(self.attempt, int) or self.attempt < 1:
            raise ContractViolation("attempt starts at 1")
        if not isinstance(self.base_commit, str) or not self.base_commit.strip():
            raise ContractViolation(
                "base_commit is required; evidence that names no tree cannot be "
                "checked for staleness"
            )
        if not isinstance(self.claims, tuple):
            raise ContractViolation("claims must be a tuple")
        for claim in self.claims:
            if not isinstance(claim, Claim):
                raise ContractViolation(f"claims contains {claim!r}, which is not a Claim")

        # A verification with nothing to verify would report COMPLETE having
        # established nothing -- the most dangerous possible outcome, because it
        # looks exactly like success.
        if not self.claims:
            raise ContractViolation(
                "a verification request must carry at least one claim; verifying "
                "nothing would report complete having established nothing"
            )

        identifiers = [str(c.claim_id) for c in self.claims]
        if len(set(identifiers)) != len(identifiers):
            raise ContractViolation("claims contains duplicate claim ids")


@dataclass(frozen=True)
class VerificationRecord(Contract):
    """One verification attempt against one WorkOrder."""

    CONTRACT_NAME = "cortexprime.engineering.verification_record"

    verification_id: VerificationId
    request: VerificationRequest
    status: VerificationStatus = VerificationStatus.REQUESTED
    results: tuple = ()
    extra_evidence: tuple = ()
    verifier: Optional[str] = None
    started_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    closing_note: Optional[str] = None
    superseded_by: Optional[VerificationId] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if not isinstance(self.verification_id, VerificationId):
            raise ContractViolation("verification_id must be a VerificationId")
        if not isinstance(self.request, VerificationRequest):
            raise ContractViolation("request must be a VerificationRequest")
        if not isinstance(self.status, VerificationStatus):
            raise ContractViolation("status must be a VerificationStatus")

        for label, items, expected in (
            ("results", self.results, ClaimResult),
            ("extra_evidence", self.extra_evidence, VerifiedEvidence),
        ):
            if not isinstance(items, tuple):
                raise ContractViolation(f"{label} must be a tuple")
            for item in items:
                if not isinstance(item, expected):
                    raise ContractViolation(
                        f"{label} contains {item!r}, which is not a {expected.__name__}"
                    )

        requested = {str(c.claim_id) for c in self.request.claims}
        for result in self.results:
            if str(result.claim_id) not in requested:
                raise ClaimNotRequested(
                    claim_id=str(result.claim_id),
                    verification_id=str(self.verification_id),
                )

        seen = [str(r.claim_id) for r in self.results]
        if len(set(seen)) != len(seen):
            raise ContractViolation("results contains two verdicts for the same claim")

        if self.status is not VerificationStatus.REQUESTED and self.started_at is None:
            raise ContractViolation(
                f"a verification in status {self.status.value!r} must record when it started"
            )
        if self.status.is_terminal and self.closed_at is None:
            raise ContractViolation(
                f"a verification in terminal status {self.status.value!r} must record "
                "when it closed"
            )
        for label, value in (("started_at", self.started_at), ("closed_at", self.closed_at)):
            if value is not None and value.tzinfo is None:
                raise ContractViolation(f"{label} must be timezone-aware")

        if self.superseded_by is not None and not isinstance(
            self.superseded_by, VerificationId
        ):
            raise ContractViolation("superseded_by must be a VerificationId")

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    @property
    def work_id(self) -> str:
        return self.request.work_id

    @property
    def attempt(self) -> int:
        return self.request.attempt

    @property
    def base_commit(self) -> str:
        return self.request.base_commit

    @property
    def outstanding_claims(self) -> tuple:
        settled = {str(r.claim_id) for r in self.results}
        return tuple(c for c in self.request.claims if str(c.claim_id) not in settled)

    def result_for(self, claim_id: ClaimId) -> Optional[ClaimResult]:
        for result in self.results:
            if result.claim_id == claim_id:
                return result
        return None

    def count(self, verdict: ClaimVerdict) -> int:
        return sum(1 for r in self.results if r.verdict is verdict)

    @property
    def contradicted(self) -> tuple:
        return tuple(r for r in self.results if r.verdict is ClaimVerdict.CONTRADICTED)

    @property
    def unreproducible(self) -> tuple:
        return tuple(r for r in self.results if r.verdict is ClaimVerdict.UNREPRODUCIBLE)

    @property
    def weakest_trust(self) -> Optional[TrustLevel]:
        """The floor of the whole verification.

        A verification is only as strong as its weakest supporting evidence.
        Out-of-scope results are excluded -- they carry no evidence because
        nothing was examined, and counting them as zero would misreport a fully
        evidenced verification as unsupported.
        """
        graded = [
            r.trust for r in self.results if r.verdict is not ClaimVerdict.OUT_OF_SCOPE
        ]
        return min(graded, key=lambda t: t.rank) if graded else None

    def stale_results(self, current_commit: Optional[str]) -> tuple:
        return tuple(r for r in self.results if r.stale_against(current_commit))

    # ------------------------------------------------------------------
    # Transitions
    # ------------------------------------------------------------------

    def _require_open(self) -> None:
        if not self.status.is_open:
            raise VerificationAlreadyClosed(
                verification_id=str(self.verification_id), status=self.status.value
            )

    def start(self, verifier: str) -> "VerificationRecord":
        """Claim the verification. Named, because a verdict has an author."""
        self._require_open()
        if self.status is VerificationStatus.RUNNING:
            raise ContractViolation(
                f"verification {self.verification_id} is already running under "
                f"{self.verifier!r}"
            )
        if not isinstance(verifier, str) or not verifier.strip():
            raise ContractViolation("a verifier must be named")
        return replace(
            self,
            status=VerificationStatus.RUNNING,
            verifier=verifier.strip(),
            started_at=datetime.now(timezone.utc),
        )

    def record(self, result: ClaimResult) -> "VerificationRecord":
        """Add a verdict. Refuses a second verdict on a settled claim."""
        self._require_open()
        if self.status is not VerificationStatus.RUNNING:
            raise VerificationNotStarted(str(self.verification_id))

        requested = {str(c.claim_id) for c in self.request.claims}
        if str(result.claim_id) not in requested:
            raise ClaimNotRequested(
                claim_id=str(result.claim_id), verification_id=str(self.verification_id)
            )

        existing = self.result_for(result.claim_id)
        if existing is not None:
            raise ClaimAlreadyResolved(
                claim_id=str(result.claim_id), verdict=existing.verdict.value
            )

        return replace(self, results=self.results + (result,))

    def add_evidence(self, evidence: VerifiedEvidence) -> "VerificationRecord":
        """Attach evidence that supports the verification as a whole.

        For findings that belong to no single claim -- an environment
        description, a gate run covering everything at once.
        """
        self._require_open()
        if not isinstance(evidence, VerifiedEvidence):
            raise ContractViolation("only VerifiedEvidence may be attached")
        return replace(self, extra_evidence=self.extra_evidence + (evidence,))

    def close(self, status: VerificationStatus, note: Optional[str] = None) -> "VerificationRecord":
        """Close with an outcome.

        The outcome is supplied rather than inferred, because deciding it is the
        policy's job and this aggregate should not hold a second copy of those
        rules. It does enforce that the outcome is a closing one.
        """
        self._require_open()
        if not isinstance(status, VerificationStatus) or not status.is_terminal:
            raise ContractViolation(
                f"{status!r} is not a closing status; a verification closes as complete, "
                "failed, incomplete, or invalidated"
            )
        if status is not VerificationStatus.COMPLETE and not (note and note.strip()):
            raise ContractViolation(
                f"closing as {status.value} must say why; an unexplained non-success "
                "tells a reader nothing they can act on"
            )
        return replace(
            self,
            status=status,
            closed_at=datetime.now(timezone.utc),
            closing_note=note.strip() if note else None,
        )

    def mark_stale(self, current_commit: str) -> "VerificationRecord":
        """The tree moved. Everything must be reproduced again.

        Not terminal: a stale verification is superseded by a fresh attempt
        rather than closed, and the distinction matters because stale means
        "ask again", not "the answer was no".
        """
        self._require_open()
        return replace(
            self,
            status=VerificationStatus.STALE,
            started_at=self.started_at or datetime.now(timezone.utc),
            closing_note=(
                f"base moved from {self.base_commit} to {current_commit}; every claim "
                "must be reproduced against the tree being merged"
            ),
        )

    def supersede(self, successor: VerificationId) -> "VerificationRecord":
        if not isinstance(successor, VerificationId):
            raise ContractViolation("successor must be a VerificationId")
        if successor == self.verification_id:
            raise ContractViolation("a verification cannot supersede itself")
        if self.superseded_by is not None:
            raise ContractViolation(
                f"verification {self.verification_id} is already superseded by "
                f"{self.superseded_by}"
            )
        return replace(self, superseded_by=successor)
