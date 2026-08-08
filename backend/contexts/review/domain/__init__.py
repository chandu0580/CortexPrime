"""The Review domain: pure, no I/O, no framework.

    lenses      the reading stances a round is examined through
    findings    what a review asserts, and what classifies it
    decision    the three conclusions, and what each requires
    record      the aggregate, its invariants, and its digest
    policy      whether a decision may be issued, reporting every reason
"""

from backend.contexts.review.domain.decision import ReviewDecision
from backend.contexts.review.domain.errors import (
    ApprovalWithOpenBlockers,
    BlockingFindingCannotBeWaived,
    BlockingFindingWithoutRemedy,
    DecisionRefused,
    DigestMismatch,
    DigestNotComputed,
    DuplicateReview,
    FindingAlreadyResolved,
    FindingWithoutAnchor,
    InvalidIdentifier,
    ReviewDecided,
    ReviewError,
    ReviewNotFound,
    ReviewNotStarted,
    ReviewIsSuperseded,
    UnexaminedFiles,
    UnknownFinding,
    UnknownLens,
)
from backend.contexts.review.domain.events import (
    AGGREGATE_TYPE,
    ChangesRequested,
    FindingAdded,
    FindingResolved,
    REVIEW_EVENT_TYPES,
    ReviewApproved,
    ReviewRejected,
    ReviewRequested,
    ReviewStarted,
    ReviewSuperseded,
)
from backend.contexts.review.domain.factory import comment, finding, location, request_review
from backend.contexts.review.domain.findings import (
    CodeLocation,
    EvidenceRef,
    FindingCategory,
    FindingState,
    Resolution,
    ReviewComment,
    ReviewFinding,
    ReviewSeverity,
)
from backend.contexts.review.domain.identifiers import CommentId, FindingId, ReviewId
from backend.contexts.review.domain.lenses import (
    REQUIRED_LENSES,
    ReviewLens,
    coerce_lens,
    required_lens_values,
)
from backend.contexts.review.domain.policy import (
    PolicyFinding,
    PolicyReport,
    ReviewPolicy,
    Severity,
    default_policy,
)
from backend.contexts.review.domain.record import (
    ARTIFACT_KIND,
    CANONICAL_FORM_VERSION,
    GOVERNED_FIELDS,
    ReviewRecord,
    ReviewStatus,
)

__all__ = [
    "ReviewRecord",
    "ReviewStatus",
    "ReviewDecision",
    "ReviewId",
    "FindingId",
    "CommentId",
    "ReviewLens",
    "REQUIRED_LENSES",
    "coerce_lens",
    "required_lens_values",
    "ReviewFinding",
    "ReviewComment",
    "ReviewSeverity",
    "FindingCategory",
    "FindingState",
    "Resolution",
    "CodeLocation",
    "EvidenceRef",
    "ReviewPolicy",
    "PolicyReport",
    "PolicyFinding",
    "Severity",
    "default_policy",
    "ARTIFACT_KIND",
    "CANONICAL_FORM_VERSION",
    "GOVERNED_FIELDS",
    "request_review",
    "finding",
    "comment",
    "location",
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
    "ReviewError",
    "InvalidIdentifier",
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
