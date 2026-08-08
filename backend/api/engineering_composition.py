"""Composition root for the Engineering Runtime.

**This is the only module that imports both bounded contexts**, and that is why
it lives at the API layer rather than inside either of them.

The runtime defines ports; the WorkOrder context implements a service. Something
must join them. Putting the adapter inside the runtime would make the runtime
import the WorkOrder context; putting it inside the WorkOrder context would
reverse the coupling and be no better. Layer 3 may import layer 2, so the
composition root is the one place where the join is legal *and* where it belongs
-- composition is what a composition root is for.

Keeping it in one small named module, rather than scattered through the route
handlers, means the coupling is greppable. Anyone asking "what does the runtime
actually talk to?" reads this file and nothing else.
"""

from __future__ import annotations

from typing import Any, Optional, Sequence

from backend.contexts.engineering import (
    Collaborators,
    ContextBundleRef,
    EngineeringRuntime,
    EngineeringRuntimeQueries,
    ReviewOutcome,
    VerificationOutcome,
    WorkOrderPhase,
    WorkOrderSnapshot,
    default_policy,
)
from backend.contexts.context_bundle import (
    AssembleBundle,
    ContextBundleService,
    GetBundle,
    InMemoryContextRepository,
    ResolveBundle,
)
from backend.contexts.engineering_verification import (
    ClaimInput,
    GetOutcome,
    InMemoryVerificationRepository,
    RequestVerification,
    VerificationService,
    VerificationStatus,
)
from backend.contexts.implementation_record import (
    ImplementationRecordService,
    InMemoryImplementationRepository,
)
from backend.contexts.review import (
    DuplicateReview,
    InMemoryReviewRepository,
    RequestReview,
    ReviewDecision,
    ReviewService,
)
from backend.contexts.workorder import (
    FilesystemReferenceResolver,
    InMemoryWorkOrderRepository,
    RejectionType,
    TransitionWorkOrder,
    WorkOrderService,
    WorkOrderState,
)
from backend.contexts.workorder.application.commands import SupersedeWorkOrder
from backend.contexts.workorder.domain.errors import WorkOrderNotFound
from backend.contexts.workorder.infrastructure.adr_resolver import (
    constraints_from_architecture_gate,
)

__all__ = [
    "WorkOrderServiceAdapter",
    "VerificationServiceAdapter",
    "ContextBundleServiceAdapter",
    "ReviewServiceAdapter",
    "ImplementationClaimSource",
    "ImplementationArtifactSource",
    "build_engineering_runtime",
    "EngineeringStack",
]


class WorkOrderServiceAdapter:
    """Presents the WorkOrder context through the runtime's ``WorkOrderPort``.

    Translation only. It maps phases to states and aggregates to snapshots, and
    holds no rules of its own -- an adapter that decided anything would be a
    third place the lifecycle lives.
    """

    def __init__(self, service: WorkOrderService) -> None:
        self._service = service

    # -- translation ---------------------------------------------------

    @staticmethod
    def _to_snapshot(work_order: Any) -> WorkOrderSnapshot:
        return WorkOrderSnapshot(
            work_id=str(work_order.work_id),
            version=work_order.version,
            phase=WorkOrderPhase(work_order.state.value),
            digest=work_order.digest.value if work_order.digest else None,
            priority=work_order.priority.value,
            intent=work_order.intent,
            blast_radius_allowed=tuple(
                sorted(str(p) for p in work_order.blast_radius.allowed)
            ),
            constraints=tuple(sorted(str(c) for c in work_order.constraints)),
            unresolved_assumptions=len(work_order.unresolved_assumptions),
            blocking_assumptions=len(work_order.blocking_assumptions),
            dependencies=tuple(sorted(str(d) for d in work_order.dependencies)),
            superseded_by=(
                str(work_order.superseded_by) if work_order.superseded_by else None
            ),
        )

    # -- WorkOrderPort --------------------------------------------------

    def snapshot(self, context: Any, work_id: str) -> Optional[WorkOrderSnapshot]:
        from backend.contexts.workorder import GetWorkOrder

        try:
            return self._to_snapshot(self._service.get(context, GetWorkOrder(work_id=work_id)))
        except WorkOrderNotFound:
            return None

    def transition(
        self, context: Any, work_id: str, to_phase: WorkOrderPhase, actor: str
    ) -> WorkOrderSnapshot:
        result = self._service.transition(
            context,
            TransitionWorkOrder(
                work_id=work_id, to_state=WorkOrderState(to_phase.value), actor=actor
            ),
        )
        return self._to_snapshot(result.work_order)

    def reject(
        self, context: Any, work_id: str, rejection_type: str, detail: str, raised_by: str
    ) -> WorkOrderSnapshot:
        from backend.contexts.workorder import RejectWorkOrder

        result = self._service.reject(
            context,
            RejectWorkOrder(
                work_id=work_id,
                rejection_type=RejectionType(rejection_type),
                detail=detail,
                raised_by=raised_by,
            ),
        )
        return self._to_snapshot(result.work_order)

    def supersede(
        self, context: Any, work_id: str, successor_id: str, actor: str
    ) -> WorkOrderSnapshot:
        result = self._service.supersede(
            context,
            SupersedeWorkOrder(work_id=work_id, successor_id=successor_id, actor=actor),
        )
        return self._to_snapshot(result.work_order)

    def active(self, context: Any) -> Sequence[WorkOrderSnapshot]:
        from backend.contexts.workorder import ListWorkOrders

        return tuple(
            self._to_snapshot(w)
            for w in self._service.list(context, ListWorkOrders(active_only=True))
        )


class ImplementationClaimSource:
    """Reads a completed ImplementationRecord and yields what a verifier can attack.

    This is the join ADR-021 named as its remaining risk: Verification was
    receiving a placeholder claim because nothing carried what the implementer
    asserted. It now does.

    **Only ``COMPLETED`` records are read.** An in-progress record is work in
    flight; verifying it would produce a verdict about a document that can still
    change. ``completed_for`` enforces that, and this adapter does not reach past
    it.

    **Nothing is invented.** A claim's evidence travels across as *asserted*
    evidence -- the implementer's references, untrusted by construction. The
    Verification context refuses to promote an ``AssertedEvidenceRef`` into a
    ``VerifiedEvidence``; a verifier has to collect its own. Carrying the
    references across gives the verifier somewhere to start, not a reason to
    believe.
    """

    def __init__(self, service: ImplementationRecordService) -> None:
        self._service = service

    def claims_for(self, context: Any, work_id: str, round: Optional[int] = None):
        """Return ``(claims, base_commit)`` or ``None`` when no record is sealed."""
        record = self._service.completed_for(context, work_id, round=round)
        if record is None or not record.claims:
            return None
        claims = tuple(
            ClaimInput(
                statement=c.statement,
                claim_type=c.claim_type.value,
                asserted_evidence=tuple(sorted(c.evidence_ids)),
                hint=c.reproduction_hint,
            )
            for c in record.claims
        )
        return claims, record.revision


class VerificationServiceAdapter:
    """Presents the Verification context through the runtime's ``VerificationPort``.

    Translation only, and the translation that matters is on the way out: a
    verification is reported to the runtime as ``complete`` **only** when the
    context says ``COMPLETE``. Every other status -- failed, incomplete,
    invalidated, stale, still running -- is reported as itself.

    That mapping is the whole reason this adapter exists rather than the runtime
    reading a boolean. ``VerificationOutcome.complete`` additionally requires zero
    contradicted and zero unreproducible claims, so a status of ``complete``
    carrying either would still not satisfy the runtime. Two independent checks
    for one fact, because the fact is whether work may be merged.
    """

    def __init__(
        self,
        service: VerificationService,
        claims: Optional[ImplementationClaimSource] = None,
    ) -> None:
        self._service = service
        self._claims = claims

    def request(self, context: Any, work_id: str, attempt: int) -> str:
        """Ask for a verification, carrying the implementer's real claims.

        The claims come from the completed ImplementationRecord for this
        WorkOrder, along with the revision they were made against -- so the
        verification is anchored to a tree rather than to ``unrecorded``, and
        Verification's own staleness check has something real to compare.

        **When no record is sealed, the placeholder remains.** That is deliberate.
        A WorkOrder can reach verification without an ImplementationRecord (an
        older run, a lifecycle driven directly through the runtime), and the
        domain refuses a verification with no claims at all. The placeholder
        states the one thing the runtime knows on its own authority -- that the
        WorkOrder reached this phase through legal transitions -- and nothing
        more. Fabricating implementation claims nobody made would be worse than
        an obviously thin one.
        """
        sourced = self._claims.claims_for(context, work_id) if self._claims else None
        if sourced is not None:
            claims, base_commit = sourced
        else:
            claims = (
                ClaimInput(
                    statement=(
                        f"WorkOrder {work_id} reached verification attempt {attempt} "
                        "through legal transitions"
                    ),
                    claim_type="behaviour",
                ),
            )
            base_commit = "unrecorded"

        result = self._service.request(
            context,
            RequestVerification(
                work_id=work_id,
                attempt=attempt,
                base_commit=base_commit,
                requested_by="engineering-runtime",
                claims=claims,
            ),
        )
        return str(result.record.verification_id)

    def outcome(self, context: Any, work_id: str, attempt: int):
        record = self._service.outcome(
            context, GetOutcome(work_id=work_id, attempt=attempt)
        )
        if record is None:
            return None
        return VerificationOutcome(
            work_id=work_id,
            attempt=attempt,
            status=record.status.value,
            claims_reproduced=sum(
                1 for r in record.results if r.verdict.value == "reproduced"
            ),
            claims_contradicted=len(record.contradicted),
            claims_unreproducible=len(record.unreproducible),
        )


class ImplementationArtifactSource:
    """Reads the completed ImplementationRecord a review will be conducted against.

    Review needs three things the WorkOrder snapshot cannot supply: which artifact
    is under review, the digest that pins it, and the files an approval has to
    cover. All three live on the ImplementationRecord.

    **Only ``COMPLETED`` records are read.** Reviewing work in flight produces a
    judgement about a document that can still change.
    """

    def __init__(self, service: ImplementationRecordService) -> None:
        self._service = service

    def artifact_for(self, context: Any, work_id: str, round: Optional[int] = None):
        """Return ``(implementation_id, digest, revision, files)`` or ``None``."""
        record = self._service.completed_for(context, work_id, round=round)
        if record is None:
            return None
        files = tuple(sorted(record.changes.all_paths_touched))
        return (
            str(record.implementation_id),
            record.digest or "",
            record.revision,
            files,
        )


class ReviewServiceAdapter:
    """Presents the Review context through the runtime's ``ReviewPort``.

    Translation only, and there are two translations worth naming.

    **Decision to verdict.** The runtime reads ``verdict == "pass"``; this context
    speaks in decisions. Approval maps to ``pass`` and everything else maps to
    itself, so a ``changes_requested`` review is never reported as a rejection --
    they send the WorkOrder to different phases. A context that knew the
    orchestrator's verdict strings would be coupled to the orchestrator, which S2
    forbids; a drift test asserts the runtime still accepts what this emits.

    **Which blockers count.** ``ReviewOutcome.blocking_findings`` is the count of
    *open* blockers, not of every blocker raised. A blocker found and fixed inside
    the round is a fact about the round, but reporting it here would make
    ``ReviewOutcome.passed`` false for a review that legitimately approved --
    punishing the reviewer who found something and got it fixed.
    """

    def __init__(
        self,
        service: ReviewService,
        artifacts: Optional[ImplementationArtifactSource] = None,
    ) -> None:
        self._service = service
        self._artifacts = artifacts

    # -- ReviewPort ----------------------------------------------------

    def required_lenses(self) -> Sequence[str]:
        return self._service.required_lenses()

    def request(
        self, context: Any, work_id: str, round: int, lenses: Sequence[str]
    ) -> Sequence[str]:
        """Open one review per lens, bound to the artifact under review.

        **When no record is sealed the reviews are still opened, bound to
        ``"unrecorded"`` with no change set.** That is deliberate and it is the
        weaker of two bad options. Refusing would make ``implementation ->
        review`` unreachable for any lifecycle driven without an
        ImplementationRecord -- which is the whole path this PR exists to open --
        and fabricating a digest would defeat the binding entirely. The
        placeholder is visible on the record and in the API response, so a review
        conducted against nothing is identifiable as such rather than
        indistinguishable from one conducted against a diff.
        """
        sourced = self._artifacts.artifact_for(context, work_id) if self._artifacts else None
        if sourced is not None:
            implementation_id, digest, revision, files = sourced
        else:
            implementation_id, digest, revision, files = (
                f"unrecorded:{work_id}",
                "unrecorded",
                "unrecorded",
                (),
            )

        opened: list = []
        for lens in lenses:
            try:
                result = self._service.request(
                    context,
                    RequestReview(
                        work_id=work_id,
                        lens=lens,
                        implementation_id=implementation_id,
                        implementation_digest=digest,
                        revision=revision,
                        round=round,
                        files_under_review=files,
                        requested_by="engineering-runtime",
                    ),
                )
                opened.append(str(result.review.review_id))
            except DuplicateReview:
                # The lens already has a live review for this round. Re-entering
                # review must not open a second one, and must not fail either --
                # a retried transition is not an error.
                existing = [
                    r
                    for r in self._service.decided_for(context, work_id, round)
                    if r.lens.value == lens
                ]
                opened.extend(str(r.review_id) for r in existing)
        return tuple(opened)

    def outcomes(self, context: Any, work_id: str, round: int) -> Sequence[ReviewOutcome]:
        return tuple(
            ReviewOutcome(
                work_id=work_id,
                round=round,
                lens=review.lens.value,
                verdict=(
                    "pass"
                    if review.decision is ReviewDecision.APPROVED
                    else (review.decision.value if review.decision else "undecided")
                ),
                blocking_findings=len(review.open_blockers),
                advisory_findings=len(review.advisory_findings),
            )
            for review in self._service.decided_for(context, work_id, round)
        )


class ContextBundleServiceAdapter:
    """Presents the ContextBundle context through the runtime's ``ContextPort``.

    Translation only. The runtime asks for a bundle when a WorkOrder enters
    spec-tests or implementation; this assembles one and hands back a reference.

    **What this adapter cannot do, and why it matters.** The runtime knows the
    WorkOrder id and version. It does not know which files are in scope -- that
    lives on the WorkOrder aggregate, which the runtime deliberately cannot see
    (ADR-020: the snapshot carries what orchestration needs, not the whole
    aggregate). So the adapter reads the snapshot's *declared* blast radius and
    constraints, and resolves no file contents.

    The bundle it produces is structurally complete and materially thin: the
    right scope, no contents. Filling it needs a repository reader, which is
    neither this PR nor this context. Stated plainly rather than hidden behind a
    plausible-looking bundle.
    """

    def __init__(self, service: ContextBundleService, work_orders: Any) -> None:
        self._service = service
        self._work_orders = work_orders

    def assemble(self, context: Any, work_id: str, work_order_version: int) -> ContextBundleRef:
        snapshot = self._work_orders.snapshot(context, work_id)
        allowed = (
            tuple(snapshot.blast_radius_allowed)
            if snapshot and snapshot.blast_radius_allowed
            else ("backend/**",)
        )
        constraints = tuple(snapshot.constraints) if snapshot else ()

        result = self._service.assemble(
            context,
            AssembleBundle(
                work_id=work_id,
                work_order_version=work_order_version,
                base_commit="unrecorded",
                blast_radius_allowed=allowed,
                searchable=("**",),
                adr_references=tuple(c for c in constraints if c.upper().startswith("ADR-")),
                assembled_by="engineering-runtime",
            ),
        )
        bundle = result.bundle
        return ContextBundleRef(
            work_id=bundle.work_id,
            work_order_version=bundle.work_order_version,
            base_commit=bundle.base_commit,
            manifest_digest=bundle.manifest_digest or "",
            bundle_version=bundle.version,
        )

    def current(self, context: Any, work_id: str) -> Optional[ContextBundleRef]:
        bundle = self._service.current_for(context, work_id)
        if bundle is None:
            return None
        return ContextBundleRef(
            work_id=bundle.work_id,
            work_order_version=bundle.work_order_version,
            base_commit=bundle.base_commit,
            manifest_digest=bundle.manifest_digest or "",
            bundle_version=bundle.version,
        )


class EngineeringStack:
    """Everything wired together, for a caller that wants the whole thing."""

    def __init__(
        self,
        service: WorkOrderService,
        runtime: EngineeringRuntime,
        verification_service: Optional[VerificationService] = None,
        context_service: Optional[ContextBundleService] = None,
        implementation_service: Optional[ImplementationRecordService] = None,
        verification_adapter: Optional["VerificationServiceAdapter"] = None,
        review_service: Optional[ReviewService] = None,
        review_adapter: Optional["ReviewServiceAdapter"] = None,
    ) -> None:
        self.work_order_service = service
        self.runtime = runtime
        self.verification_service = verification_service
        self.context_service = context_service
        self.implementation_service = implementation_service
        self.review_service = review_service
        #: The adapters the runtime holds. Exposed so a test can exercise a
        #: request path directly rather than only through a transition.
        self.verification_adapter = verification_adapter
        self.review_adapter = review_adapter
        self.queries = EngineeringRuntimeQueries(runtime)


def build_engineering_runtime(
    *,
    service: Optional[WorkOrderService] = None,
    verification_service: Optional[VerificationService] = None,
    context_service: Optional[ContextBundleService] = None,
    implementation_service: Optional[ImplementationRecordService] = None,
    review_service: Optional[ReviewService] = None,
    wire_verification: bool = True,
    wire_context: bool = True,
    wire_implementation: bool = True,
    wire_review: bool = True,
    run_architecture_gate: bool = False,
) -> EngineeringStack:
    """Assemble the runtime.

    **Every port is now wired.** PR-E6 supplied the last one: with Review built,
    ``implementation -> review -> verification`` is reachable, and no phase is
    refused for want of a collaborator.

    ImplementationRecord is not a port on the runtime -- it is the source
    Verification draws its claims from and Review draws its artifact from, so it
    is wired into those two adapters rather than into ``Collaborators``.

    ``wire_verification=False``, ``wire_context=False``,
    ``wire_implementation=False`` and ``wire_review=False`` exist so the previous
    behaviour stays testable: a test asserting an unwired port is refused, or
    that the placeholder claim still appears with no record, needs a way to
    unwire it.

    ``run_architecture_gate`` is off by default. The gate takes eight minutes,
    which is right for a pipeline and wrong for an HTTP request.
    """
    work_order_service = service or WorkOrderService(
        repository=InMemoryWorkOrderRepository(),
        resolver=FilesystemReferenceResolver(
            known_constraints=constraints_from_architecture_gate()
        ),
    )

    verification = None
    if wire_verification:
        verification = verification_service or VerificationService(
            repository=InMemoryVerificationRepository()
        )

    bundles = None
    if wire_context:
        bundles = context_service or ContextBundleService(
            repository=InMemoryContextRepository()
        )

    implementations = None
    if wire_implementation:
        implementations = implementation_service or ImplementationRecordService(
            repository=InMemoryImplementationRepository()
        )

    reviews = None
    if wire_review:
        reviews = review_service or ReviewService(repository=InMemoryReviewRepository())

    work_order_adapter = WorkOrderServiceAdapter(work_order_service)
    verification_adapter = (
        VerificationServiceAdapter(
            verification,
            ImplementationClaimSource(implementations) if implementations else None,
        )
        if verification
        else None
    )
    review_adapter = (
        ReviewServiceAdapter(
            reviews,
            ImplementationArtifactSource(implementations) if implementations else None,
        )
        if reviews
        else None
    )
    runtime = EngineeringRuntime(
        Collaborators(
            work_order=work_order_adapter,
            review=review_adapter,
            verification=verification_adapter,
            context_bundles=(
                ContextBundleServiceAdapter(bundles, work_order_adapter) if bundles else None
            ),
        ),
        policy=default_policy(run_architecture_gate=run_architecture_gate),
    )
    return EngineeringStack(
        work_order_service,
        runtime,
        verification,
        bundles,
        implementations,
        verification_adapter,
        reviews,
        review_adapter,
    )
