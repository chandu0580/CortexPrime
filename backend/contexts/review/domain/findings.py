"""Findings, comments, and the vocabulary that classifies them.

A finding asserts a defect. A comment does not. Keeping them as different types
rather than one type with a flag is what stops "have you considered X?" from
being counted as a defect the implementer must clear -- and what stops a real
defect from being softened into a question nobody has to answer.

Every finding points at something
---------------------------------
A location, or an evidence reference, or both. Refused at construction rather
than flagged by policy: an anchorless finding recorded during a review is
consumed by the implementer the moment it appears, and by then the round is
already being spent guessing what the reviewer meant.

Only one severity blocks
-------------------------
``BLOCKING`` stops the round; everything below it is advice the implementer
weighs. That is a deliberate refusal to have three severities that all mean
"must fix" -- if every severity blocks, classification carries no information and
the reviewer is choosing an adjective rather than making a decision. Blocking is
an act with a cost, and the cost is what makes it mean something.

A blocking finding therefore has to say what would clear it. Stopping work
without stating the remedy is the most expensive thing a reviewer can do.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Sequence

from backend.contracts._contract import Contract
from backend.contracts.errors import ContractViolation
from backend.contexts.review.domain.errors import (
    BlockingFindingCannotBeWaived,
    BlockingFindingWithoutRemedy,
    FindingAlreadyResolved,
    FindingWithoutAnchor,
)
from backend.contexts.review.domain.identifiers import CommentId, FindingId

__all__ = [
    "ReviewSeverity",
    "FindingCategory",
    "FindingState",
    "Resolution",
    "CodeLocation",
    "EvidenceRef",
    "ReviewFinding",
    "ReviewComment",
]


class ReviewSeverity(str, Enum):
    """How much a finding costs the round.

    Ordered by weight. Only ``BLOCKING`` stops anything; the rest travel to the
    implementer as advice, and the implementer's judgement about advice is part
    of what the next review reads.
    """

    BLOCKING = "blocking"
    MAJOR = "major"
    MINOR = "minor"
    NIT = "nit"

    @property
    def blocks_approval(self) -> bool:
        """Only one severity blocks, and that is what makes it mean something."""
        return self is ReviewSeverity.BLOCKING

    @property
    def is_advisory(self) -> bool:
        return not self.blocks_approval

    @property
    def rank(self) -> int:
        return _SEVERITY_RANK[self]

    @property
    def requires_remedy(self) -> bool:
        """Blocking findings must state what would clear them."""
        return self.blocks_approval


_SEVERITY_RANK = {
    ReviewSeverity.BLOCKING: 3,
    ReviewSeverity.MAJOR: 2,
    ReviewSeverity.MINOR: 1,
    ReviewSeverity.NIT: 0,
}


class FindingCategory(str, Enum):
    """What kind of defect this is.

    Deliberately independent of the lens that found it. A correctness reviewer
    who notices a tenancy hole should record it as ``SECURITY`` -- forcing the
    category to match the lens would either lose the finding or mislabel it, and
    both are worse than a security finding arriving from an unexpected reader.
    """

    CORRECTNESS = "correctness"
    ARCHITECTURE = "architecture"
    SECURITY = "security"
    TESTING = "testing"
    PERFORMANCE = "performance"
    MAINTAINABILITY = "maintainability"
    CONSTITUTION = "constitution"


class FindingState(str, Enum):
    OPEN = "open"
    RESOLVED = "resolved"

    @property
    def is_open(self) -> bool:
        return self is FindingState.OPEN


class Resolution(str, Enum):
    """How a finding stopped being outstanding.

    Three genuinely different facts, and collapsing them loses the one that
    matters most. ``FIXED`` says the code changed. ``WITHDRAWN`` says the
    reviewer was wrong. ``ACCEPTED_RISK`` says neither -- the finding stands and
    is being lived with, which is the only one of the three that leaves a hazard
    in the tree.
    """

    FIXED = "fixed"
    WITHDRAWN = "withdrawn"
    ACCEPTED_RISK = "accepted_risk"

    @property
    def requires_justification(self) -> bool:
        """Accepting a risk must say why. The other two are self-explaining:
        fixed points at a revision, withdrawn is the reviewer retracting."""
        return self is Resolution.ACCEPTED_RISK

    @property
    def leaves_hazard(self) -> bool:
        return self is Resolution.ACCEPTED_RISK


@dataclass(frozen=True, order=True)
class CodeLocation:
    """Where in the change set a finding points.

    A path is required; a line is not. Requiring a line would push reviewers into
    inventing one for findings that are genuinely about a whole file, and an
    invented line number is worse than an absent one.
    """

    path: str
    line: Optional[int] = None
    end_line: Optional[int] = None

    def __post_init__(self) -> None:
        if not isinstance(self.path, str) or not self.path.strip():
            raise ContractViolation("a location must name a path")
        if self.path != self.path.strip():
            raise ContractViolation("a location path must not have surrounding whitespace")
        for label, value in (("line", self.line), ("end_line", self.end_line)):
            if value is not None and (not isinstance(value, int) or value < 1):
                raise ContractViolation(f"{label} must be a positive integer when given")
        if self.end_line is not None:
            if self.line is None:
                raise ContractViolation("end_line without line does not name a range")
            if self.end_line < self.line:
                raise ContractViolation(
                    f"end_line {self.end_line} precedes line {self.line}"
                )

    def __str__(self) -> str:
        if self.line is None:
            return self.path
        if self.end_line is None:
            return f"{self.path}:{self.line}"
        return f"{self.path}:{self.line}-{self.end_line}"


@dataclass(frozen=True, order=True)
class EvidenceRef:
    """An identifier a reviewer offers as support. Opaque here.

    The Evidence context does not exist, and this context does not resolve these.
    A resolver that answered "yes" would make the reference unfalsifiable. What
    it buys today is that the implementer knows what the reviewer was looking at.
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
class ReviewFinding(Contract):
    """One defect a reviewer asserts, against one implementation.

    Carries ``work_id`` and ``implementation_id`` itself rather than inheriting
    them from the review. That looks redundant until a finding is quoted
    somewhere else -- in a rejection, in the next round's context bundle, in an
    audit -- at which point a finding that cannot say what it was about is
    unusable. The aggregate refuses one whose references disagree with its own.
    """

    CONTRACT_NAME = "cortexprime.engineering.review_finding"

    finding_id: FindingId
    work_id: str
    implementation_id: str
    summary: str
    severity: ReviewSeverity
    category: FindingCategory
    detail: str = ""
    location: Optional[CodeLocation] = None
    evidence: frozenset = field(default_factory=frozenset)
    required_change: Optional[str] = None
    raised_by: str = "reviewer"
    raised_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    state: FindingState = FindingState.OPEN
    resolution: Optional[Resolution] = None
    resolution_note: Optional[str] = None
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[str] = None

    def __post_init__(self) -> None:
        for label, value in (
            ("work_id", self.work_id),
            ("implementation_id", self.implementation_id),
            ("summary", self.summary),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ContractViolation(f"{label} must be non-blank text")

        if not isinstance(self.finding_id, FindingId):
            raise ContractViolation("finding_id must be a FindingId")
        if not isinstance(self.severity, ReviewSeverity):
            raise ContractViolation("severity must be a ReviewSeverity")
        if not isinstance(self.category, FindingCategory):
            raise ContractViolation("category must be a FindingCategory")

        if self.location is not None and not isinstance(self.location, CodeLocation):
            raise ContractViolation("location must be a CodeLocation")

        if not isinstance(self.evidence, (frozenset, set)):
            raise ContractViolation("evidence must be a set")
        refs = frozenset(
            e if isinstance(e, EvidenceRef) else EvidenceRef(e) for e in self.evidence
        )
        object.__setattr__(self, "evidence", refs)

        # Anchored, or it cannot be acted on.
        if self.location is None and not refs:
            raise FindingWithoutAnchor(self.summary)

        # Blocking says what would clear it.
        if self.severity.requires_remedy and not (
            self.required_change and self.required_change.strip()
        ):
            raise BlockingFindingWithoutRemedy(self.summary)

        if not isinstance(self.state, FindingState):
            raise ContractViolation("state must be a FindingState")

        if self.state is FindingState.RESOLVED:
            if self.resolution is None:
                raise ContractViolation(
                    "a resolved finding must say how it was resolved; 'resolved' "
                    "without an outcome hides whether the code changed"
                )
            if self.resolution.requires_justification and not (
                self.resolution_note and self.resolution_note.strip()
            ):
                raise ContractViolation(
                    "accepting a risk must say why; an unexplained acceptance is "
                    "indistinguishable from an oversight"
                )
            if self.resolved_at is None:
                raise ContractViolation("a resolved finding must record when")
        elif self.resolution is not None:
            raise ContractViolation("an open finding cannot carry a resolution")

        for label, value in (("raised_at", self.raised_at), ("resolved_at", self.resolved_at)):
            if value is not None and value.tzinfo is None:
                raise ContractViolation(f"{label} must be timezone-aware")

    # -- queries -------------------------------------------------------

    @property
    def is_open(self) -> bool:
        return self.state.is_open

    @property
    def blocks_approval(self) -> bool:
        """Blocking *and* still open. A fixed blocker blocks nothing."""
        return self.severity.blocks_approval and self.is_open

    @property
    def evidence_ids(self) -> tuple:
        return tuple(sorted(str(e) for e in self.evidence))

    @property
    def anchor(self) -> str:
        """What this finding points at, for a message that has to be short."""
        if self.location is not None:
            return str(self.location)
        return ", ".join(self.evidence_ids)

    # -- transitions ---------------------------------------------------

    def resolve(
        self,
        resolution: Resolution,
        *,
        note: Optional[str] = None,
        by: str = "reviewer",
    ) -> "ReviewFinding":
        """Clear the finding, refusing a waiver of a blocker."""
        if not isinstance(resolution, Resolution):
            raise ContractViolation("resolution must be a Resolution")
        if self.state is FindingState.RESOLVED:
            raise FindingAlreadyResolved(
                finding_id=str(self.finding_id),
                resolution=self.resolution.value if self.resolution else "?",
            )
        if resolution is Resolution.ACCEPTED_RISK and self.severity.blocks_approval:
            raise BlockingFindingCannotBeWaived(
                finding_id=str(self.finding_id), summary=self.summary
            )
        return replace(
            self,
            state=FindingState.RESOLVED,
            resolution=resolution,
            resolution_note=note.strip() if note and note.strip() else None,
            resolved_at=datetime.now(timezone.utc),
            resolved_by=by,
        )

    # -- construction --------------------------------------------------

    @classmethod
    def create(
        cls,
        *,
        work_id: str,
        implementation_id: str,
        summary: str,
        severity: ReviewSeverity,
        category: FindingCategory,
        detail: str = "",
        location: Optional[CodeLocation] = None,
        evidence: Sequence[str] = (),
        required_change: Optional[str] = None,
        raised_by: str = "reviewer",
    ) -> "ReviewFinding":
        return cls(
            finding_id=FindingId.new(),
            work_id=work_id,
            implementation_id=implementation_id,
            summary=summary,
            severity=severity,
            category=category,
            detail=detail,
            location=location,
            evidence=frozenset(EvidenceRef(e) for e in evidence),
            required_change=required_change,
            raised_by=raised_by,
        )


@dataclass(frozen=True)
class ReviewComment(Contract):
    """Prose attached to a review. Never blocks anything.

    A comment is how a reviewer says something that is not a defect -- a
    question, a piece of context, a note for the next round. Separating it from
    findings means the finding count is a count of defects, which is what the
    runtime reports and what a trend over rounds is worth reading.
    """

    CONTRACT_NAME = "cortexprime.engineering.review_comment"

    comment_id: CommentId
    body: str
    author: str = "reviewer"
    location: Optional[CodeLocation] = None
    in_reply_to: Optional[FindingId] = None
    written_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if not isinstance(self.comment_id, CommentId):
            raise ContractViolation("comment_id must be a CommentId")
        if not isinstance(self.body, str) or not self.body.strip():
            raise ContractViolation("a comment must say something")
        if not isinstance(self.author, str) or not self.author.strip():
            raise ContractViolation("a comment must name its author")
        if self.location is not None and not isinstance(self.location, CodeLocation):
            raise ContractViolation("location must be a CodeLocation")
        if self.in_reply_to is not None and not isinstance(self.in_reply_to, FindingId):
            raise ContractViolation("in_reply_to must be a FindingId")
        if self.written_at.tzinfo is None:
            raise ContractViolation("written_at must be timezone-aware")

    @classmethod
    def create(
        cls,
        body: str,
        *,
        author: str = "reviewer",
        location: Optional[CodeLocation] = None,
        in_reply_to: Optional[FindingId] = None,
    ) -> "ReviewComment":
        return cls(
            comment_id=CommentId.new(),
            body=body,
            author=author,
            location=location,
            in_reply_to=in_reply_to,
        )
