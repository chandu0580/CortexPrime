"""The ReviewRecord aggregate and its digest.

One review is one lens reading one round of one WorkOrder. The runtime requests
several per round and refuses to call the round reviewed until each has reported,
so this aggregate is deliberately small: it holds one reader's judgement, not the
round's.

Review never changes the implementation
----------------------------------------
Structurally, not by convention. This context imports nothing from
``implementation_record`` -- it holds the implementation's *id* and *digest* as
opaque strings and has no path to the aggregate they name. A reviewer that could
edit what it reviews is not an independent read of the work; it is a second
author, and the second author agreeing with the first tells you nothing.

Holding the digest is what makes the read pin down: the review is a statement
about the artifact that hashed to this value. If a different round is submitted,
its digest differs, and a review quoting the old one is visibly about something
else.

Immutable after the decision
-----------------------------
Every mutation refuses once the review is ``DECIDED``. The decision is the
artifact; a review that gained a finding afterwards would describe a judgement
nobody made, and the runtime has already acted on the one that was reported.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Final, Optional

from backend.contracts._contract import Contract
from backend.contracts.approval import HashAlgorithm, PayloadDigest
from backend.contracts.errors import ContractViolation
from backend.contexts.review.domain.decision import ReviewDecision
from backend.contexts.review.domain.errors import (
    ApprovalWithOpenBlockers,
    DigestMismatch,
    DigestNotComputed,
    ReviewDecided,
    ReviewNotStarted,
    ReviewIsSuperseded,
    UnexaminedFiles,
    UnknownFinding,
)
from backend.contexts.review.domain.findings import (
    Resolution,
    ReviewComment,
    ReviewFinding,
)
from backend.contexts.review.domain.identifiers import FindingId, ReviewId
from backend.contexts.review.domain.lenses import ReviewLens
from backend.platform.hashing import compute_digest, digests_match

__all__ = [
    "ReviewStatus",
    "ReviewRecord",
    "ARTIFACT_KIND",
    "CANONICAL_FORM_VERSION",
    "GOVERNED_FIELDS",
]

ARTIFACT_KIND: Final[str] = "cortexprime.engineering.reviewrecord"
CANONICAL_FORM_VERSION: Final[int] = 1

#: What the digest covers. Excludes status, timestamps, and the digest itself --
#: including status would invalidate the digest on the first legal transition,
#: and superseding a decided review is legal.
GOVERNED_FIELDS: Final[tuple] = (
    "work_id",
    "round",
    "lens",
    "implementation_id",
    "implementation_digest",
    "revision",
    "adr_references",
    "files_under_review",
    "files_examined",
    "findings",
    "comments",
    "decision",
    "decision_rationale",
    "reviewer",
)


class ReviewStatus(str, Enum):
    REQUESTED = "requested"
    IN_PROGRESS = "in_progress"
    DECIDED = "decided"
    SUPERSEDED = "superseded"

    @property
    def is_open(self) -> bool:
        """Whether the review may still change."""
        return self in (ReviewStatus.REQUESTED, ReviewStatus.IN_PROGRESS)

    @property
    def accepts_findings(self) -> bool:
        """Only a review someone has taken up. A finding on an unstarted review
        cannot say who looked."""
        return self is ReviewStatus.IN_PROGRESS

    @property
    def is_reportable(self) -> bool:
        """Whether the runtime may read an outcome from this. One status only."""
        return self is ReviewStatus.DECIDED


@dataclass(frozen=True)
class ReviewRecord(Contract):
    """One lens's review of one implementation round."""

    CONTRACT_NAME = "cortexprime.engineering.review_record"

    review_id: ReviewId
    work_id: str
    round: int
    lens: ReviewLens
    implementation_id: str
    implementation_digest: str
    revision: str

    adr_references: frozenset = field(default_factory=frozenset)
    files_under_review: tuple = ()
    files_examined: tuple = ()
    findings: tuple = ()
    comments: tuple = ()

    status: ReviewStatus = ReviewStatus.REQUESTED
    decision: Optional[ReviewDecision] = None
    decision_rationale: Optional[str] = None
    digest: Optional[str] = None

    requested_by: str = "engineering-runtime"
    reviewer: Optional[str] = None
    requested_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    decided_at: Optional[datetime] = None
    superseded_by: Optional[ReviewId] = None

    # ------------------------------------------------------------------
    # Invariants
    # ------------------------------------------------------------------

    def __post_init__(self) -> None:
        if not isinstance(self.review_id, ReviewId):
            raise ContractViolation("review_id must be a ReviewId")

        for label, value in (
            ("work_id", self.work_id),
            ("implementation_id", self.implementation_id),
            ("implementation_digest", self.implementation_digest),
            ("revision", self.revision),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ContractViolation(
                    f"{label} must be non-blank text; a review that cannot say which "
                    "artifact it read is not a review of anything"
                )

        if not isinstance(self.round, int) or self.round < 1:
            raise ContractViolation("round must be a positive integer starting at 1")

        if not isinstance(self.lens, ReviewLens):
            raise ContractViolation("lens must be a ReviewLens")

        for label, items, expected in (
            ("findings", self.findings, ReviewFinding),
            ("comments", self.comments, ReviewComment),
        ):
            if not isinstance(items, tuple):
                raise ContractViolation(f"{label} must be a tuple")
            for item in items:
                if not isinstance(item, expected):
                    raise ContractViolation(
                        f"{label} contains {item!r}, which is not a {expected.__name__}"
                    )

        for label in ("files_under_review", "files_examined"):
            value = getattr(self, label)
            if not isinstance(value, tuple):
                raise ContractViolation(f"{label} must be a tuple")
            for item in value:
                if not isinstance(item, str) or not item.strip():
                    raise ContractViolation(f"{label} contains a blank entry")
            object.__setattr__(self, label, tuple(sorted({v.strip() for v in value})))

        if not isinstance(self.adr_references, (frozenset, set)):
            raise ContractViolation("adr_references must be a set")
        for item in self.adr_references:
            if not isinstance(item, str) or not item.strip():
                raise ContractViolation("adr_references contains a blank entry")
        object.__setattr__(
            self, "adr_references", frozenset(v.strip() for v in self.adr_references)
        )

        finding_ids = [str(f.finding_id) for f in self.findings]
        if len(set(finding_ids)) != len(finding_ids):
            raise ContractViolation("findings contains duplicate finding ids")

        comment_ids = [str(c.comment_id) for c in self.comments]
        if len(set(comment_ids)) != len(comment_ids):
            raise ContractViolation("comments contains duplicate comment ids")

        # Every finding is about this review's subject.
        for finding in self.findings:
            if finding.work_id != self.work_id:
                raise ContractViolation(
                    f"finding {finding.finding_id} is against WorkOrder "
                    f"{finding.work_id!r} but the review is of {self.work_id!r}"
                )
            if finding.implementation_id != self.implementation_id:
                raise ContractViolation(
                    f"finding {finding.finding_id} is against implementation "
                    f"{finding.implementation_id!r} but the review is of "
                    f"{self.implementation_id!r}"
                )

        if not isinstance(self.status, ReviewStatus):
            raise ContractViolation("status must be a ReviewStatus")

        # A decision belongs to a review that reached one. Superseding is the one
        # transition permitted afterwards, and it does not erase what was said --
        # so a superseded review legitimately still carries its decision.
        if self.status is ReviewStatus.DECIDED and self.decision is None:
            raise ContractViolation("a decided review must carry its decision")
        if self.decision is not None and self.status not in (
            ReviewStatus.DECIDED,
            ReviewStatus.SUPERSEDED,
        ):
            raise ContractViolation(
                f"a review that is {self.status.value} carries no decision"
            )

        # Whatever the decision was, it binds the digest and names its reviewer.
        if self.decision is not None:
            if not self.digest:
                raise ContractViolation(
                    "a decided review must carry the digest computed at decision; "
                    "without it the judgement on record cannot be shown to be the "
                    "one that was issued"
                )
            if self.decided_at is None:
                raise ContractViolation("a decided review must record when")
            if not (self.reviewer and self.reviewer.strip()):
                raise ContractViolation(
                    "a decided review must name its reviewer; an unattributed "
                    "judgement has nobody behind it"
                )
            if self.decision.requires_rationale and not (
                self.decision_rationale and self.decision_rationale.strip()
            ):
                raise ContractViolation(
                    f"a {self.decision.value!r} decision must say why; the next round "
                    "is built from the reason"
                )
            # The invariant the runtime asserts on its own event, held here too.
            if self.decision.is_approval and any(f.blocks_approval for f in self.findings):
                raise ContractViolation(
                    "a review cannot be approved with blocking findings open"
                )

        if self.status is ReviewStatus.IN_PROGRESS and not (
            self.reviewer and self.reviewer.strip()
        ):
            raise ContractViolation("a review in progress must name its reviewer")

        if self.status is ReviewStatus.SUPERSEDED and self.superseded_by is None:
            raise ContractViolation("a superseded review must name its successor")

        if self.superseded_by is not None and not isinstance(self.superseded_by, ReviewId):
            raise ContractViolation("superseded_by must be a ReviewId")

        for label in ("requested_at", "started_at", "decided_at"):
            value = getattr(self, label)
            if value is not None and value.tzinfo is None:
                raise ContractViolation(f"{label} must be timezone-aware")

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    @property
    def is_open(self) -> bool:
        return self.status.is_open

    @property
    def open_findings(self) -> tuple:
        return tuple(f for f in self.findings if f.is_open)

    @property
    def open_blockers(self) -> tuple:
        """Blocking findings still outstanding. What refuses an approval."""
        return tuple(f for f in self.findings if f.blocks_approval)

    @property
    def blocking_findings(self) -> tuple:
        """Every blocking finding raised, resolved or not.

        Distinct from :attr:`open_blockers` and the distinction matters: the
        runtime reports what a lens *found*, and a blocker that was raised and
        fixed within the round is a fact about the round worth keeping.
        """
        return tuple(f for f in self.findings if f.severity.blocks_approval)

    @property
    def advisory_findings(self) -> tuple:
        return tuple(f for f in self.findings if f.severity.is_advisory)

    @property
    def accepted_risks(self) -> tuple:
        """Findings living in the tree by decision rather than by oversight."""
        return tuple(
            f
            for f in self.findings
            if f.resolution is not None and f.resolution.leaves_hazard
        )

    @property
    def unexamined_files(self) -> tuple:
        """Files in the change set nobody looked at. What refuses an approval."""
        return tuple(sorted(set(self.files_under_review) - set(self.files_examined)))

    @property
    def coverage_ratio(self) -> float:
        if not self.files_under_review:
            return 1.0
        examined = len(set(self.files_under_review) & set(self.files_examined))
        return examined / len(self.files_under_review)

    @property
    def all_evidence_ids(self) -> tuple:
        return tuple(sorted({e for f in self.findings for e in f.evidence_ids}))

    def finding(self, finding_id: FindingId) -> Optional[ReviewFinding]:
        for candidate in self.findings:
            if candidate.finding_id == finding_id:
                return candidate
        return None

    # ------------------------------------------------------------------
    # Digest
    # ------------------------------------------------------------------

    def digest_payload(self) -> dict[str, Any]:
        """The exact structure the digest covers.

        Exposed so a verifier can recompute it and name the member that diverged,
        rather than reporting only that two hex strings differ.
        """
        return {
            "__artifact__": ARTIFACT_KIND,
            "__canonical_form__": CANONICAL_FORM_VERSION,
            "work_id": self.work_id,
            "round": self.round,
            "lens": self.lens.value,
            "implementation_id": self.implementation_id,
            "implementation_digest": self.implementation_digest,
            "revision": self.revision,
            "adr_references": sorted(self.adr_references),
            "files_under_review": list(self.files_under_review),
            "files_examined": list(self.files_examined),
            "findings": sorted(
                (
                    {
                        "finding_id": str(f.finding_id),
                        "summary": f.summary,
                        "severity": f.severity.value,
                        "category": f.category.value,
                        "location": str(f.location) if f.location else None,
                        "evidence": list(f.evidence_ids),
                        "required_change": f.required_change,
                        "state": f.state.value,
                        "resolution": f.resolution.value if f.resolution else None,
                    }
                    for f in self.findings
                ),
                key=lambda item: item["finding_id"],
            ),
            "comments": sorted(
                (
                    {
                        "comment_id": str(c.comment_id),
                        "body": c.body,
                        "author": c.author,
                        "location": str(c.location) if c.location else None,
                    }
                    for c in self.comments
                ),
                key=lambda item: item["comment_id"],
            ),
            "decision": self.decision.value if self.decision else None,
            "decision_rationale": self.decision_rationale,
            "reviewer": self.reviewer,
        }

    def compute_digest(self, algorithm: HashAlgorithm = HashAlgorithm.SHA256) -> PayloadDigest:
        return compute_digest(self.digest_payload(), algorithm)

    def verify_digest(self) -> None:
        """Raise unless the review still hashes to the digest bound at decision."""
        if not self.digest:
            raise DigestNotComputed(str(self.review_id))
        recomputed = self.compute_digest()
        if not digests_match(
            recomputed, PayloadDigest(algorithm=recomputed.algorithm, value=self.digest)
        ):
            raise DigestMismatch(
                review_id=str(self.review_id),
                recorded=self.digest,
                recomputed=recomputed.value,
            )

    # ------------------------------------------------------------------
    # Guards
    # ------------------------------------------------------------------

    def _require_open(self, operation: str) -> None:
        if self.status is ReviewStatus.SUPERSEDED:
            raise ReviewIsSuperseded(
                review_id=str(self.review_id), successor=str(self.superseded_by)
            )
        if not self.status.is_open:
            raise ReviewDecided(review_id=str(self.review_id), operation=operation)

    def _require_started(self, operation: str) -> None:
        self._require_open(operation)
        if not self.status.accepts_findings:
            raise ReviewNotStarted(review_id=str(self.review_id), operation=operation)

    # ------------------------------------------------------------------
    # Conducting the review
    # ------------------------------------------------------------------

    def start(self, reviewer: str) -> "ReviewRecord":
        """Take up the review. Findings need a reviewer to attribute them to."""
        self._require_open("starting")
        if self.status is ReviewStatus.IN_PROGRESS:
            raise ContractViolation(
                f"review {self.review_id} is already in progress with {self.reviewer!r}"
            )
        if not reviewer or not reviewer.strip():
            raise ContractViolation("a review must name the reviewer conducting it")
        return replace(
            self,
            status=ReviewStatus.IN_PROGRESS,
            reviewer=reviewer.strip(),
            started_at=datetime.now(timezone.utc),
        )

    def examine(self, *paths: str) -> "ReviewRecord":
        """Record that these paths were read.

        Paths outside the change set are accepted deliberately: reading a caller
        to understand what a change breaks is review, and refusing to record it
        would make the coverage figure a measure of obedience rather than of what
        was actually read.
        """
        self._require_started("examining a file")
        cleaned = []
        for path in paths:
            if not isinstance(path, str) or not path.strip():
                raise ContractViolation("an examined path must be non-blank text")
            cleaned.append(path.strip())
        if not cleaned:
            raise ContractViolation("examining nothing records nothing")
        return replace(self, files_examined=tuple(self.files_examined) + tuple(cleaned))

    def add_finding(self, finding: ReviewFinding) -> "ReviewRecord":
        """Raise a defect against the artifact under review."""
        self._require_started("adding a finding")
        if not isinstance(finding, ReviewFinding):
            raise ContractViolation("finding must be a ReviewFinding")
        return replace(self, findings=self.findings + (finding,))

    def resolve_finding(
        self,
        finding_id: FindingId,
        resolution: Resolution,
        *,
        note: Optional[str] = None,
        by: Optional[str] = None,
    ) -> "ReviewRecord":
        """Clear a finding within the round.

        Resolution happens while the review is open -- a reviewer raises
        something, the implementer addresses it, the reviewer marks it. After the
        decision the review is sealed, and a finding carried into the next round
        is the next review's to raise against the next implementation.
        """
        self._require_started("resolving a finding")
        existing = self.finding(finding_id)
        if existing is None:
            raise UnknownFinding(
                review_id=str(self.review_id), finding_id=str(finding_id)
            )
        resolved = existing.resolve(
            resolution, note=note, by=by or self.reviewer or "reviewer"
        )
        return replace(
            self,
            findings=tuple(
                resolved if f.finding_id == finding_id else f for f in self.findings
            ),
        )

    def add_comment(self, comment: ReviewComment) -> "ReviewRecord":
        self._require_started("adding a comment")
        if not isinstance(comment, ReviewComment):
            raise ContractViolation("comment must be a ReviewComment")
        if comment.in_reply_to is not None and self.finding(comment.in_reply_to) is None:
            raise UnknownFinding(
                review_id=str(self.review_id), finding_id=str(comment.in_reply_to)
            )
        return replace(self, comments=self.comments + (comment,))

    # ------------------------------------------------------------------
    # Deciding
    # ------------------------------------------------------------------

    def decide(
        self,
        decision: ReviewDecision,
        *,
        rationale: Optional[str] = None,
        decided_by: Optional[str] = None,
    ) -> "ReviewRecord":
        """Seal the review and bind its digest.

        The two refusals that matter are checked here as well as in the policy:
        approving over an open blocker, and approving without having examined the
        change set. Policy decides *whether* a decision may be issued and reports
        every reason at once; these two are held in the aggregate too because
        they are the failures that make an unreviewed change look reviewed, and a
        record assembled from storage bypasses the service.
        """
        self._require_started("deciding")
        if not isinstance(decision, ReviewDecision):
            raise ContractViolation("decision must be a ReviewDecision")

        if decision.is_approval:
            blockers = self.open_blockers
            if blockers:
                raise ApprovalWithOpenBlockers(
                    review_id=str(self.review_id), open_findings=blockers
                )
            unexamined = self.unexamined_files
            if unexamined:
                raise UnexaminedFiles(
                    review_id=str(self.review_id), unexamined=unexamined
                )

        signed_by = (decided_by or "").strip() or self.reviewer
        pending = replace(
            self,
            decision_rationale=rationale.strip() if rationale and rationale.strip() else None,
            reviewer=signed_by,
            decided_at=datetime.now(timezone.utc),
        )

        # The digest is computed over the *decided* content, but a record cannot
        # hold a decision before it is decided and cannot be decided without a
        # digest. So the payload is assembled directly rather than by building an
        # intermediate that would violate one invariant to satisfy the other. It
        # is byte-identical to what the sealed record reports, which is what makes
        # ``verify_digest`` on the result pass -- and a test asserts exactly that.
        payload = pending.digest_payload()
        payload["decision"] = decision.value
        digest = compute_digest(payload).value

        return replace(
            pending,
            status=ReviewStatus.DECIDED,
            decision=decision,
            digest=digest,
        )

    def supersede(self, successor: ReviewId) -> "ReviewRecord":
        """Record that a later review replaces this one.

        Permitted on a decided review, unlike every other mutation: superseding
        does not change what the review *said*, only whether it is current. The
        digest still verifies afterwards, and a test asserts that.
        """
        if not isinstance(successor, ReviewId):
            raise ContractViolation("successor must be a ReviewId")
        if successor == self.review_id:
            raise ContractViolation("a review cannot supersede itself")
        if self.superseded_by is not None:
            raise ContractViolation(
                f"review {self.review_id} is already superseded by {self.superseded_by}"
            )
        return replace(self, status=ReviewStatus.SUPERSEDED, superseded_by=successor)
