"""Review lifecycle events.

Namespaced ``engineering.review.*``. ``CONTRACT_NAME`` is globally unique and a
clash raises at import time, and PR-E2's runtime already owns
``engineering.runtime.review_requested``.

The two are different facts and both are worth having. The runtime's says *the
orchestrator asked for review and named the lenses*; this one says *the Review
context opened a record for one lens*. They coincide today and will not once
review requests are queued -- and the gap between them is where a lens that was
asked for but never opened would hide.

Why there are eight events for seven named ones
------------------------------------------------
The Engineering Artifact Specification names ``ReviewApproved`` and
``ReviewRejected``. Review has three decisions, because ``review`` has three
doors out of it in the lifecycle: verification, back to implementation, and
rejected. ``ChangesRequested`` is the third. Folding it into ``ReviewRejected``
would tell the runtime to abandon a WorkOrder whose premise is sound and whose
implementation merely needs another pass -- a materially different and far more
expensive answer, and one no consumer could distinguish after the fact.
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.contracts.errors import ContractViolation
from backend.platform.events import DomainEvent

__all__ = [
    "AGGREGATE_TYPE",
    "ReviewRequested",
    "ReviewStarted",
    "FindingAdded",
    "FindingResolved",
    "ReviewApproved",
    "ChangesRequested",
    "ReviewRejected",
    "ReviewSuperseded",
    "REVIEW_EVENT_TYPES",
]

AGGREGATE_TYPE = "review_record"


def _require_text(label: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ContractViolation(f"{label} must be non-blank text")


@dataclass(frozen=True)
class ReviewRequested(DomainEvent):
    """A review was opened for one lens against one implementation round."""

    EVENT_TYPE = "engineering.review.requested"

    review_id: str = ""
    work_id: str = ""
    round: int = 1
    lens: str = ""
    implementation_id: str = ""
    implementation_digest: str = ""
    files_under_review: int = 0

    def __post_init__(self) -> None:
        super().__post_init__()
        _require_text("review_id", self.review_id)
        _require_text("work_id", self.work_id)
        _require_text("lens", self.lens)
        _require_text("implementation_id", self.implementation_id)
        _require_text("implementation_digest", self.implementation_digest)


@dataclass(frozen=True)
class ReviewStarted(DomainEvent):
    """A reviewer took the review up.

    Carries the reviewer because everything recorded from here is attributed to
    them, and an unattributed finding is an assertion with nobody behind it.
    """

    EVENT_TYPE = "engineering.review.started"

    review_id: str = ""
    work_id: str = ""
    lens: str = ""
    reviewer: str = ""

    def __post_init__(self) -> None:
        super().__post_init__()
        _require_text("review_id", self.review_id)
        _require_text("reviewer", self.reviewer)


@dataclass(frozen=True)
class FindingAdded(DomainEvent):
    """A defect was asserted against the artifact under review."""

    EVENT_TYPE = "engineering.review.finding_added"

    review_id: str = ""
    work_id: str = ""
    finding_id: str = ""
    severity: str = ""
    category: str = ""
    summary: str = ""
    anchor: str = ""
    blocking: bool = False

    def __post_init__(self) -> None:
        super().__post_init__()
        _require_text("review_id", self.review_id)
        _require_text("finding_id", self.finding_id)
        _require_text("severity", self.severity)
        _require_text("summary", self.summary)
        _require_text(
            "anchor",
            self.anchor,
        )
        if not isinstance(self.blocking, bool):
            raise ContractViolation("blocking must be a bool")


@dataclass(frozen=True)
class FindingResolved(DomainEvent):
    """A finding stopped being outstanding, and how.

    ``resolution`` is the field that matters. ``fixed`` says the code changed;
    ``withdrawn`` says the reviewer was wrong; ``accepted_risk`` says neither, and
    is the only one that leaves a hazard behind.
    """

    EVENT_TYPE = "engineering.review.finding_resolved"

    review_id: str = ""
    work_id: str = ""
    finding_id: str = ""
    resolution: str = ""
    severity: str = ""
    note: str = ""
    resolved_by: str = ""

    def __post_init__(self) -> None:
        super().__post_init__()
        _require_text("review_id", self.review_id)
        _require_text("finding_id", self.finding_id)
        _require_text("resolution", self.resolution)
        if self.resolution == "accepted_risk" and not (self.note and self.note.strip()):
            raise ContractViolation(
                "accepting a risk must say why; an unexplained acceptance is "
                "indistinguishable from an oversight"
            )


@dataclass(frozen=True)
class ReviewApproved(DomainEvent):
    """The lens passed the round.

    Refuses construction with blocking findings open, mirroring the runtime's
    ``ReviewCompleted``. An event that could describe an impossible approval
    would make the log a worse record than the aggregate.
    """

    EVENT_TYPE = "engineering.review.approved"

    review_id: str = ""
    work_id: str = ""
    round: int = 1
    lens: str = ""
    reviewer: str = ""
    digest: str = ""
    files_examined: int = 0
    unexamined_files: int = 0
    advisory_findings: int = 0
    open_blocking_findings: int = 0

    def __post_init__(self) -> None:
        super().__post_init__()
        _require_text("review_id", self.review_id)
        _require_text("work_id", self.work_id)
        _require_text("lens", self.lens)
        _require_text("reviewer", self.reviewer)
        _require_text("digest", self.digest)
        if self.open_blocking_findings:
            raise ContractViolation(
                "a review cannot be approved with blocking findings outstanding"
            )
        # The rubber stamp, stated as the aggregate states it: nothing in the
        # change set was left unread. Counting examined files instead would
        # refuse an approval of a round whose change set was never recorded --
        # weak, but a different failure, and one the placeholder digest already
        # makes visible.
        if self.unexamined_files:
            raise ContractViolation(
                f"a review cannot be approved with {self.unexamined_files} file(s) in "
                "the change set unexamined; such an approval reports downstream "
                "exactly like one that read all of it"
            )


@dataclass(frozen=True)
class ChangesRequested(DomainEvent):
    """The lens sent the round back to implementation.

    Distinct from rejection: the WorkOrder stands, the implementation does not.
    """

    EVENT_TYPE = "engineering.review.changes_requested"

    review_id: str = ""
    work_id: str = ""
    round: int = 1
    lens: str = ""
    reviewer: str = ""
    digest: str = ""
    blocking_findings: int = 0
    advisory_findings: int = 0
    rationale: str = ""

    def __post_init__(self) -> None:
        super().__post_init__()
        _require_text("review_id", self.review_id)
        _require_text("work_id", self.work_id)
        _require_text("lens", self.lens)
        _require_text("digest", self.digest)
        _require_text("rationale", self.rationale)
        if self.blocking_findings + self.advisory_findings < 1:
            raise ContractViolation(
                "changes were requested with no finding; the round goes back with "
                "nothing to act on"
            )


@dataclass(frozen=True)
class ReviewRejected(DomainEvent):
    """The lens rejected the round outright.

    The heaviest outcome available to a reviewer, and the rationale is mandatory
    because it is what the WorkOrder's rejection will cite.
    """

    EVENT_TYPE = "engineering.review.rejected"

    review_id: str = ""
    work_id: str = ""
    round: int = 1
    lens: str = ""
    reviewer: str = ""
    digest: str = ""
    blocking_findings: int = 0
    rationale: str = ""

    def __post_init__(self) -> None:
        super().__post_init__()
        _require_text("review_id", self.review_id)
        _require_text("work_id", self.work_id)
        _require_text("lens", self.lens)
        _require_text("digest", self.digest)
        _require_text("rationale", self.rationale)


@dataclass(frozen=True)
class ReviewSuperseded(DomainEvent):
    EVENT_TYPE = "engineering.review.superseded"

    review_id: str = ""
    work_id: str = ""
    superseded_by: str = ""
    reason: str = ""

    def __post_init__(self) -> None:
        super().__post_init__()
        _require_text("review_id", self.review_id)
        _require_text("superseded_by", self.superseded_by)
        if self.review_id == self.superseded_by:
            raise ContractViolation("a review cannot supersede itself")


REVIEW_EVENT_TYPES = (
    ReviewRequested,
    ReviewStarted,
    FindingAdded,
    FindingResolved,
    ReviewApproved,
    ChangesRequested,
    ReviewRejected,
    ReviewSuperseded,
)
