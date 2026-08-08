"""The Review application service.

Where the aggregate's per-item invariants meet the review policy and the
repository's facts. Events are returned, never published -- this context owns no
bus, the same arrangement as every other engineering context.

Decisions are gated, not asserted
----------------------------------
``decide`` runs the policy first and refuses with **every** failure rather than
the first. A decision refused one reason at a time takes five attempts to land,
and the fifth is made by someone who has stopped reading the refusals.

The aggregate holds the two refusals that matter (approving over an open blocker,
approving without examining the change set) as well, because a record assembled
from storage bypasses this service and those two are the failures that make
unreviewed work look reviewed.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Optional

from backend.contracts.tenant import TenantRef, TenantScope
from backend.contexts.review.application.commands import (
    AddComment,
    AddFinding,
    DecideReview,
    ExamineFiles,
    GetReview,
    ListReviews,
    RequestReview,
    ResolveFinding,
    StartReview,
    SupersedeReview,
)
from backend.contexts.review.domain.decision import ReviewDecision
from backend.contexts.review.domain.errors import (
    DecisionRefused,
    DuplicateReview,
    ReviewDecided,
    ReviewIsSuperseded,
    ReviewNotFound,
)
from backend.contexts.review.domain.events import (
    AGGREGATE_TYPE,
    ChangesRequested,
    FindingAdded,
    FindingResolved,
    ReviewApproved,
    ReviewRejected,
    ReviewRequested,
    ReviewStarted,
    ReviewSuperseded,
)
from backend.contexts.review.domain.factory import comment, finding, location, request_review
from backend.contexts.review.domain.findings import (
    FindingCategory,
    Resolution,
    ReviewSeverity,
)
from backend.contexts.review.domain.identifiers import FindingId, ReviewId
from backend.contexts.review.domain.lenses import coerce_lens, required_lens_values
from backend.contexts.review.domain.policy import ReviewPolicy, default_policy
from backend.contexts.review.domain.record import ReviewRecord, ReviewStatus
from backend.platform.events import EventMetadata

__all__ = ["ReviewService", "CommandResult", "LensCoverage"]


@dataclass(frozen=True)
class CommandResult:
    review: ReviewRecord
    events: tuple

    @property
    def event_types(self) -> tuple:
        return tuple(getattr(type(e), "EVENT_TYPE", "?") for e in self.events)


@dataclass(frozen=True)
class LensCoverage:
    """Which lenses have reported on a round, and which have not.

    The runtime treats a missing lens as a failure rather than a pass (ADR-020),
    so the interesting half of this is :attr:`missing`.
    """

    work_id: str
    round: int
    required: tuple
    decided: tuple
    approved: tuple
    missing: tuple

    @property
    def complete(self) -> bool:
        return not self.missing

    @property
    def fully_approved(self) -> bool:
        return self.complete and set(self.approved) == set(self.required)


class ReviewService:
    def __init__(
        self, repository: Any, policy: Optional[ReviewPolicy] = None
    ) -> None:
        self._repository = repository
        self._policy = policy or default_policy()

    @property
    def policy(self) -> ReviewPolicy:
        return self._policy

    @staticmethod
    def required_lenses() -> tuple:
        return required_lens_values()

    @staticmethod
    def _metadata(context: Any, review: ReviewRecord) -> EventMetadata:
        scope = getattr(context, "scope", None)
        if scope is None:
            scope = TenantScope(tenant=TenantRef(tenant_id=context.tenant_id))
        return EventMetadata.create(
            aggregate_id=str(review.review_id),
            aggregate_type=AGGREGATE_TYPE,
            scope=scope,
        )

    def _load(self, context: Any, review_id: str) -> ReviewRecord:
        found = self._repository.find(context, ReviewId(review_id))
        if found is None:
            raise ReviewNotFound(review_id)
        return found

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def request(self, context: Any, command: RequestReview) -> CommandResult:
        """Open a review for one lens on one round.

        Refuses a second live review for the same lens and round: two would let
        one reviewer approve what another blocked, and the runtime -- which reads
        one outcome per lens -- would report whichever it happened to see.
        """
        lens = coerce_lens(command.lens)
        existing = [
            r
            for r in self._repository.for_round(context, command.work_id, command.round)
            if r.lens is lens and r.status is not ReviewStatus.SUPERSEDED
        ]
        if existing:
            raise DuplicateReview(
                work_id=command.work_id, round=command.round, lens=lens.value
            )

        review = request_review(
            work_id=command.work_id,
            round=command.round,
            lens=lens,
            implementation_id=command.implementation_id,
            implementation_digest=command.implementation_digest,
            revision=command.revision,
            files_under_review=command.files_under_review,
            adr_references=command.adr_references,
            requested_by=command.requested_by,
        )
        self._repository.save(context, review)
        return CommandResult(
            review=review,
            events=(
                ReviewRequested(
                    metadata=self._metadata(context, review),
                    review_id=str(review.review_id),
                    work_id=review.work_id,
                    round=review.round,
                    lens=review.lens.value,
                    implementation_id=review.implementation_id,
                    implementation_digest=review.implementation_digest,
                    files_under_review=len(review.files_under_review),
                ),
            ),
        )

    def start(self, context: Any, command: StartReview) -> CommandResult:
        review = self._load(context, command.review_id).start(command.reviewer)
        self._repository.replace(context, review)
        return CommandResult(
            review=review,
            events=(
                ReviewStarted(
                    metadata=self._metadata(context, review),
                    review_id=str(review.review_id),
                    work_id=review.work_id,
                    lens=review.lens.value,
                    reviewer=review.reviewer or "",
                ),
            ),
        )

    def decide(self, context: Any, command: DecideReview) -> CommandResult:
        """Seal the review, or refuse with every failure at once."""
        review = self._load(context, command.review_id)
        decision = ReviewDecision(command.decision)

        # A closed review is a conflict, not a policy refusal, and the two want
        # different answers: "this decision is unsound" is worth reporting in
        # full, while "this review is already decided" is worth reporting once.
        # Raised before the policy so the caller gets the specific error rather
        # than R0 wrapped in a list of one.
        if not review.status.is_open:
            if review.status is ReviewStatus.SUPERSEDED:
                raise ReviewIsSuperseded(
                    review_id=str(review.review_id),
                    successor=str(review.superseded_by),
                )
            raise ReviewDecided(review_id=str(review.review_id), operation="deciding")

        # The policy reads a record, and the rationale and reviewer supplied with
        # this command are not on the record yet. Rather than teaching the policy
        # to take them as extra arguments -- which would let a caller evaluate
        # against one value and decide with another -- build the record the
        # decision *would* produce and evaluate that.
        candidate = review
        if command.rationale:
            candidate = replace(candidate, decision_rationale=command.rationale)
        if command.decided_by:
            candidate = replace(candidate, reviewer=command.decided_by)

        report = self._policy.evaluate(candidate, decision)
        if not report.may_decide:
            raise DecisionRefused(
                review_id=command.review_id,
                decision=decision.value,
                failures=report.blocking,
            )

        decided = review.decide(
            decision, rationale=command.rationale, decided_by=command.decided_by
        )
        self._repository.replace(context, decided)

        return CommandResult(review=decided, events=(self._decision_event(context, decided),))

    def _decision_event(self, context: Any, review: ReviewRecord):
        metadata = self._metadata(context, review)
        common = dict(
            review_id=str(review.review_id),
            work_id=review.work_id,
            round=review.round,
            lens=review.lens.value,
            reviewer=review.reviewer or "",
            digest=review.digest or "",
        )
        if review.decision is ReviewDecision.APPROVED:
            return ReviewApproved(
                metadata=metadata,
                files_examined=len(review.files_examined),
                unexamined_files=len(review.unexamined_files),
                advisory_findings=len(review.advisory_findings),
                open_blocking_findings=len(review.open_blockers),
                **common,
            )
        if review.decision is ReviewDecision.CHANGES_REQUESTED:
            return ChangesRequested(
                metadata=metadata,
                blocking_findings=len(review.blocking_findings),
                advisory_findings=len(review.advisory_findings),
                rationale=review.decision_rationale or "",
                **common,
            )
        return ReviewRejected(
            metadata=metadata,
            blocking_findings=len(review.blocking_findings),
            rationale=review.decision_rationale or "",
            **common,
        )

    def supersede(self, context: Any, command: SupersedeReview) -> CommandResult:
        review = self._load(context, command.review_id)
        superseded = review.supersede(ReviewId(command.successor_id))
        self._repository.replace(context, superseded)
        return CommandResult(
            review=superseded,
            events=(
                ReviewSuperseded(
                    metadata=self._metadata(context, superseded),
                    review_id=str(superseded.review_id),
                    work_id=superseded.work_id,
                    superseded_by=command.successor_id,
                    reason=command.reason,
                ),
            ),
        )

    # ------------------------------------------------------------------
    # Conducting the review
    # ------------------------------------------------------------------

    def examine(self, context: Any, command: ExamineFiles) -> CommandResult:
        review = self._load(context, command.review_id).examine(*command.paths)
        self._repository.replace(context, review)
        return CommandResult(review=review, events=())

    def add_finding(self, context: Any, command: AddFinding) -> CommandResult:
        review = self._load(context, command.review_id)
        raised = finding(
            work_id=review.work_id,
            implementation_id=review.implementation_id,
            summary=command.summary,
            severity=ReviewSeverity(command.severity),
            category=FindingCategory(command.category),
            detail=command.detail,
            at=(
                location(command.path, command.line, command.end_line)
                if command.path
                else None
            ),
            evidence=tuple(command.evidence),
            required_change=command.required_change,
            raised_by=command.raised_by or review.reviewer or "reviewer",
        )
        updated = review.add_finding(raised)
        self._repository.replace(context, updated)
        return CommandResult(
            review=updated,
            events=(
                FindingAdded(
                    metadata=self._metadata(context, updated),
                    review_id=str(updated.review_id),
                    work_id=updated.work_id,
                    finding_id=str(raised.finding_id),
                    severity=raised.severity.value,
                    category=raised.category.value,
                    summary=raised.summary,
                    anchor=raised.anchor,
                    blocking=raised.severity.blocks_approval,
                ),
            ),
        )

    def resolve_finding(self, context: Any, command: ResolveFinding) -> CommandResult:
        review = self._load(context, command.review_id)
        resolution = Resolution(command.resolution)
        updated = review.resolve_finding(
            FindingId(command.finding_id),
            resolution,
            note=command.note,
            by=command.resolved_by,
        )
        resolved = updated.finding(FindingId(command.finding_id))
        self._repository.replace(context, updated)
        return CommandResult(
            review=updated,
            events=(
                FindingResolved(
                    metadata=self._metadata(context, updated),
                    review_id=str(updated.review_id),
                    work_id=updated.work_id,
                    finding_id=command.finding_id,
                    resolution=resolution.value,
                    severity=resolved.severity.value if resolved else "",
                    note=(resolved.resolution_note or "") if resolved else "",
                    resolved_by=(resolved.resolved_by or "") if resolved else "",
                ),
            ),
        )

    def add_comment(self, context: Any, command: AddComment) -> CommandResult:
        review = self._load(context, command.review_id)
        written = comment(
            command.body,
            author=command.author or review.reviewer or "reviewer",
            at=location(command.path, command.line) if command.path else None,
            in_reply_to=FindingId(command.in_reply_to) if command.in_reply_to else None,
        )
        updated = review.add_comment(written)
        self._repository.replace(context, updated)
        return CommandResult(review=updated, events=())

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get(self, context: Any, query: GetReview) -> ReviewRecord:
        return self._load(context, query.review_id)

    def evaluate(self, context: Any, review_id: str, decision: str):
        """Run the review policy without deciding.

        What a reviewer checks before concluding. Discovering four failures one
        refusal at a time is how a decision takes four attempts.
        """
        return self._policy.evaluate(
            self._load(context, review_id), ReviewDecision(decision)
        )

    def list(self, context: Any, query: ListReviews) -> tuple:
        found = (
            self._repository.for_work_order(context, query.work_id)
            if query.work_id
            else self._repository.all(context)
        )
        if query.round is not None:
            found = tuple(r for r in found if r.round == query.round)
        if query.lens:
            wanted_lens = coerce_lens(query.lens)
            found = tuple(r for r in found if r.lens is wanted_lens)
        if query.status:
            wanted = ReviewStatus(query.status)
            found = tuple(r for r in found if r.status is wanted)
        return tuple(found)

    def decided_for(self, context: Any, work_id: str, round: int) -> tuple:
        """Every decided, non-superseded review for a round.

        What the runtime reads. A superseded review is not the current judgement,
        and an undecided one is not a judgement at all.
        """
        return tuple(
            r
            for r in self._repository.for_round(context, work_id, round)
            if r.status is ReviewStatus.DECIDED
        )

    def lens_coverage(self, context: Any, work_id: str, round: int) -> LensCoverage:
        """Which required lenses have reported, and which have not."""
        decided = self.decided_for(context, work_id, round)
        reported = {r.lens.value for r in decided}
        approved = {
            r.lens.value for r in decided if r.decision is ReviewDecision.APPROVED
        }
        required = set(required_lens_values())
        return LensCoverage(
            work_id=work_id,
            round=round,
            required=tuple(sorted(required)),
            decided=tuple(sorted(reported)),
            approved=tuple(sorted(approved)),
            missing=tuple(sorted(required - reported)),
        )

