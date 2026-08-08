"""Commands and queries for the Review context.

Frozen values naming one intent each, carrying primitives rather than domain
objects so a command can be serialised, queued, and replayed without dragging the
domain across the wire.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from backend.contracts.errors import ContractViolation

__all__ = [
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
]


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ContractViolation(message)


@dataclass(frozen=True)
class RequestReview:
    work_id: str
    lens: str
    implementation_id: str
    implementation_digest: str
    revision: str
    round: int = 1
    files_under_review: tuple = ()
    adr_references: tuple = ()
    requested_by: str = "engineering-runtime"

    def __post_init__(self) -> None:
        _require(bool(self.work_id), "work_id is required")
        _require(bool(self.lens), "lens is required; a review with no lens read nothing")
        _require(
            bool(self.implementation_id),
            "implementation_id is required; a review is always of something",
        )
        _require(
            bool(self.implementation_digest and self.implementation_digest.strip()),
            "implementation_digest is required; without it the review cannot be shown "
            "to be about the artifact that was submitted",
        )
        _require(
            bool(self.revision and self.revision.strip()),
            "revision is required; the same paths against a different commit are a "
            "different change",
        )
        _require(self.round >= 1, "round starts at 1")


@dataclass(frozen=True)
class StartReview:
    review_id: str
    reviewer: str

    def __post_init__(self) -> None:
        _require(bool(self.review_id), "review_id is required")
        _require(
            bool(self.reviewer and self.reviewer.strip()),
            "a review must name the reviewer conducting it; everything recorded from "
            "here is attributed to them",
        )


@dataclass(frozen=True)
class ExamineFiles:
    review_id: str
    paths: tuple = ()

    def __post_init__(self) -> None:
        _require(bool(self.review_id), "review_id is required")
        _require(bool(self.paths), "examining nothing records nothing")


@dataclass(frozen=True)
class AddFinding:
    review_id: str
    summary: str
    severity: str = "minor"
    category: str = "correctness"
    detail: str = ""
    path: Optional[str] = None
    line: Optional[int] = None
    end_line: Optional[int] = None
    evidence: tuple = ()
    required_change: Optional[str] = None
    raised_by: Optional[str] = None

    def __post_init__(self) -> None:
        _require(bool(self.review_id), "review_id is required")
        _require(
            bool(self.summary and self.summary.strip()),
            "a finding must state what is wrong",
        )
        _require(
            bool(self.path) or bool(self.evidence),
            "a finding must name a location or cite evidence; one that points at "
            "nothing cannot be acted on",
        )
        _require(
            self.severity != "blocking"
            or bool(self.required_change and self.required_change.strip()),
            "a blocking finding must state the required change; blocking work without "
            "saying what would clear it stops the round on a guess",
        )


@dataclass(frozen=True)
class ResolveFinding:
    review_id: str
    finding_id: str
    resolution: str = "fixed"
    note: Optional[str] = None
    resolved_by: Optional[str] = None

    def __post_init__(self) -> None:
        _require(bool(self.review_id), "review_id is required")
        _require(bool(self.finding_id), "finding_id is required")
        _require(
            self.resolution != "accepted_risk" or bool(self.note and self.note.strip()),
            "accepting a risk must say why; an unexplained acceptance is "
            "indistinguishable from an oversight",
        )


@dataclass(frozen=True)
class AddComment:
    review_id: str
    body: str
    author: Optional[str] = None
    path: Optional[str] = None
    line: Optional[int] = None
    in_reply_to: Optional[str] = None

    def __post_init__(self) -> None:
        _require(bool(self.review_id), "review_id is required")
        _require(bool(self.body and self.body.strip()), "a comment must say something")


@dataclass(frozen=True)
class DecideReview:
    review_id: str
    decision: str
    rationale: Optional[str] = None
    decided_by: Optional[str] = None

    def __post_init__(self) -> None:
        _require(bool(self.review_id), "review_id is required")
        _require(bool(self.decision), "decision is required")
        _require(
            self.decision == "approved" or bool(self.rationale and self.rationale.strip()),
            "a decision other than approval must say why; the implementer's next "
            "round is built from the reason",
        )


@dataclass(frozen=True)
class SupersedeReview:
    review_id: str
    successor_id: str
    reason: str = "a later round replaces this one"

    def __post_init__(self) -> None:
        _require(bool(self.review_id), "review_id is required")
        _require(bool(self.successor_id), "successor_id is required")
        _require(
            self.review_id != self.successor_id, "a review cannot supersede itself"
        )


@dataclass(frozen=True)
class GetReview:
    review_id: str


@dataclass(frozen=True)
class ListReviews:
    work_id: Optional[str] = None
    round: Optional[int] = None
    lens: Optional[str] = None
    status: Optional[str] = None
