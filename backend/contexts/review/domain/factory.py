"""Construction helpers.

The aggregate's constructor takes strongly-typed values and enforces every
invariant, which is correct and verbose. These are the ergonomic paths in, and
they exist so the common cases cannot be built wrong: a review always names the
artifact it reads, and a finding always carries the WorkOrder and implementation
it is about.
"""

from __future__ import annotations

from typing import Iterable, Optional, Sequence

from backend.contexts.review.domain.findings import (
    CodeLocation,
    FindingCategory,
    ReviewComment,
    ReviewFinding,
    ReviewSeverity,
)
from backend.contexts.review.domain.identifiers import FindingId, ReviewId
from backend.contexts.review.domain.lenses import coerce_lens
from backend.contexts.review.domain.record import ReviewRecord

__all__ = ["request_review", "finding", "comment", "location"]


def request_review(
    *,
    work_id: str,
    round: int,
    lens,
    implementation_id: str,
    implementation_digest: str,
    revision: str,
    files_under_review: Sequence[str] = (),
    adr_references: Iterable[str] = (),
    requested_by: str = "engineering-runtime",
) -> ReviewRecord:
    """An open review bound to the artifact it will read."""
    return ReviewRecord(
        review_id=ReviewId.new(),
        work_id=work_id,
        round=round,
        lens=coerce_lens(lens),
        implementation_id=implementation_id,
        implementation_digest=implementation_digest,
        revision=revision,
        files_under_review=tuple(files_under_review),
        adr_references=frozenset(adr_references),
        requested_by=requested_by,
    )


def location(path: str, line: Optional[int] = None, end_line: Optional[int] = None) -> CodeLocation:
    return CodeLocation(path=path, line=line, end_line=end_line)


def finding(
    *,
    work_id: str,
    implementation_id: str,
    summary: str,
    severity: ReviewSeverity = ReviewSeverity.MINOR,
    category: FindingCategory = FindingCategory.CORRECTNESS,
    detail: str = "",
    at: Optional[CodeLocation] = None,
    evidence: Sequence[str] = (),
    required_change: Optional[str] = None,
    raised_by: str = "reviewer",
) -> ReviewFinding:
    """A finding, anchored. Construction refuses one that points at nothing."""
    return ReviewFinding.create(
        work_id=work_id,
        implementation_id=implementation_id,
        summary=summary,
        severity=severity,
        category=category,
        detail=detail,
        location=at,
        evidence=evidence,
        required_change=required_change,
        raised_by=raised_by,
    )


def comment(
    body: str,
    *,
    author: str = "reviewer",
    at: Optional[CodeLocation] = None,
    in_reply_to: Optional[FindingId] = None,
) -> ReviewComment:
    return ReviewComment.create(body, author=author, location=at, in_reply_to=in_reply_to)
