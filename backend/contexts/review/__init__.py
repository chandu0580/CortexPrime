"""The Review bounded context.

Independent engineering review of what an implementer produced. One review is one
*lens* reading one round: the runtime asks for every required lens and refuses to
call the round reviewed until each has reported, because a missing lens is not a
passing lens.

Three rules the context exists to make unbreakable:

* **Review never changes the implementation.** Structurally, not by convention --
  this context imports nothing from ``implementation_record`` and holds the
  artifact's id and digest as opaque strings. A reviewer that could edit what it
  reviews is a second author, and a second author agreeing with the first tells
  you nothing.
* **A finding points at something.** A location or evidence, refused at
  construction. A finding that points at nothing turns the next round into
  guesswork about what the reviewer meant.
* **An approval cannot outrun the reading.** Approving over an open blocking
  finding, or without examining every file in the change set, is refused by the
  aggregate and by the policy. That is the rubber stamp, and it is the failure
  Review most needs to be unable to commit.

    domain/          pure -- lenses, findings, decisions, the record
    application/     commands, queries, the service
    infrastructure/  repository, record mapping

This context imports ``contracts/`` and ``platform/`` and nothing else.
See ADR-024.
"""

from backend.contexts.review.application import (
    AddComment,
    AddFinding,
    CommandResult,
    DecideReview,
    ExamineFiles,
    GetReview,
    LensCoverage,
    ListReviews,
    RequestReview,
    ResolveFinding,
    ReviewService,
    StartReview,
    SupersedeReview,
)
from backend.contexts.review.domain import (
    ARTIFACT_KIND,
    ApprovalWithOpenBlockers,
    BlockingFindingCannotBeWaived,
    BlockingFindingWithoutRemedy,
    CANONICAL_FORM_VERSION,
    ChangesRequested,
    CodeLocation,
    CommentId,
    DecisionRefused,
    DigestMismatch,
    DigestNotComputed,
    DuplicateReview,
    EvidenceRef,
    FindingAdded,
    FindingAlreadyResolved,
    FindingCategory,
    FindingId,
    FindingResolved,
    FindingState,
    FindingWithoutAnchor,
    GOVERNED_FIELDS,
    PolicyFinding,
    PolicyReport,
    REQUIRED_LENSES,
    REVIEW_EVENT_TYPES,
    Resolution,
    ReviewApproved,
    ReviewComment,
    ReviewDecided,
    ReviewDecision,
    ReviewError,
    ReviewFinding,
    ReviewId,
    ReviewIsSuperseded,
    ReviewLens,
    ReviewNotFound,
    ReviewNotStarted,
    ReviewPolicy,
    ReviewRecord,
    ReviewRejected,
    ReviewRequested,
    ReviewSeverity,
    ReviewStarted,
    ReviewStatus,
    ReviewSuperseded,
    Severity,
    UnexaminedFiles,
    UnknownFinding,
    UnknownLens,
    coerce_lens,
    comment,
    default_policy,
    finding,
    location,
    request_review,
    required_lens_values,
)
from backend.contexts.review.infrastructure import (
    InMemoryReviewRepository,
    ReviewRepository,
)

__all__ = [
    # Aggregate and vocabulary
    "ReviewRecord",
    "ReviewStatus",
    "ReviewDecision",
    "ReviewLens",
    "REQUIRED_LENSES",
    "coerce_lens",
    "required_lens_values",
    "ReviewId",
    "FindingId",
    "CommentId",
    "ReviewFinding",
    "ReviewComment",
    "ReviewSeverity",
    "FindingCategory",
    "FindingState",
    "Resolution",
    "CodeLocation",
    "EvidenceRef",
    # Policy
    "ReviewPolicy",
    "PolicyReport",
    "PolicyFinding",
    "Severity",
    "default_policy",
    # Digest
    "ARTIFACT_KIND",
    "CANONICAL_FORM_VERSION",
    "GOVERNED_FIELDS",
    # Factories
    "request_review",
    "finding",
    "comment",
    "location",
    # Application
    "ReviewService",
    "CommandResult",
    "LensCoverage",
    "RequestReview",
    "StartReview",
    "ExamineFiles",
    "AddFinding",
    "ResolveFinding",
    "AddComment",
    "DecideReview",
    "SupersedeReview",
    "GetReview",
    "ListReviews",
    # Infrastructure
    "ReviewRepository",
    "InMemoryReviewRepository",
    # Events
    "ReviewRequested",
    "ReviewStarted",
    "FindingAdded",
    "FindingResolved",
    "ReviewApproved",
    "ChangesRequested",
    "ReviewRejected",
    "ReviewSuperseded",
    "REVIEW_EVENT_TYPES",
    # Errors
    "ReviewError",
    "ReviewDecided",
    "ReviewNotStarted",
    "ReviewIsSuperseded",
    "FindingWithoutAnchor",
    "BlockingFindingWithoutRemedy",
    "BlockingFindingCannotBeWaived",
    "FindingAlreadyResolved",
    "UnknownFinding",
    "ApprovalWithOpenBlockers",
    "UnexaminedFiles",
    "DecisionRefused",
    "DigestMismatch",
    "DigestNotComputed",
    "ReviewNotFound",
    "DuplicateReview",
    "UnknownLens",
]
