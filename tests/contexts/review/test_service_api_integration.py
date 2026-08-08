"""Service, policy, repository, replay, concurrency, API, and the runtime wiring.

The integration section pins the claim this PR rests on: ``implementation ->
review -> verification`` is reachable, every required lens is asked, and a lens
that never reported is visible as missing rather than assumed to have passed.
"""

from __future__ import annotations

import ast
import pathlib
import threading

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api import review_routes as routes
from backend.api.engineering_composition import (
    ImplementationArtifactSource,
    ReviewServiceAdapter,
    build_engineering_runtime,
)
from backend.contexts.engineering import ReviewOutcome, ReviewPort
from backend.contexts.review import (
    AddComment,
    AddFinding,
    DecideReview,
    DecisionRefused,
    DuplicateReview,
    ExamineFiles,
    GetReview,
    InMemoryReviewRepository,
    ListReviews,
    RequestReview,
    ResolveFinding,
    ReviewDecision,
    ReviewLens,
    ReviewNotFound,
    ReviewService,
    ReviewStatus,
    StartReview,
    SupersedeReview,
    required_lens_values,
)
from backend.contexts.review.infrastructure.persistence import (
    RECORD_SCHEMA_VERSION,
    from_record,
    to_record,
)
from backend.contracts.errors import ContractViolation
from backend.platform.context import ExecutionContext
from backend.platform.storage import MissingExecutionContext

WORK = "WO-1"
IMPL = "IMP-1"
DIGEST = "9f2c1a7b3e4d5c6a"
REVISION = "a1b2c3d4"
FILES = ("backend/a.py", "backend/b.py")


@pytest.fixture
def context() -> ExecutionContext:
    return ExecutionContext.platform_internal(
        reason="review-tests", component="tests", source="pytest"
    )


@pytest.fixture
def tenant_context() -> ExecutionContext:
    from backend.platform.context.identity import IdentityContext

    return ExecutionContext.for_tenant(
        tenant_id="tenant-a", identity=IdentityContext.platform("tests"), source="pytest"
    )


@pytest.fixture
def repository() -> InMemoryReviewRepository:
    return InMemoryReviewRepository()


@pytest.fixture
def service(repository) -> ReviewService:
    return ReviewService(repository=repository)


def _request(**overrides) -> RequestReview:
    fields = dict(
        work_id=WORK,
        lens="correctness",
        implementation_id=IMPL,
        implementation_digest=DIGEST,
        revision=REVISION,
        files_under_review=FILES,
        adr_references=("ADR-024",),
    )
    fields.update(overrides)
    return RequestReview(**fields)


def _in_progress(service, context, **overrides) -> str:
    review_id = str(service.request(context, _request(**overrides)).review.review_id)
    service.start(context, StartReview(review_id=review_id, reviewer="alice"))
    return review_id


def _approvable(service, context, **overrides) -> str:
    review_id = _in_progress(service, context, **overrides)
    service.examine(context, ExamineFiles(review_id=review_id, paths=FILES))
    return review_id


def _blocking(review_id: str, **overrides) -> AddFinding:
    fields = dict(
        review_id=review_id,
        summary="tenant is read from the payload",
        severity="blocking",
        category="security",
        path="backend/a.py",
        line=20,
        required_change="derive the tenant from the execution context",
    )
    fields.update(overrides)
    return AddFinding(**fields)


# ----------------------------------------------------------------------
# Review creation
# ----------------------------------------------------------------------


def test_requesting_a_review_binds_the_artifact_and_emits_one_event(service, context) -> None:
    result = service.request(context, _request())
    assert result.event_types == ("engineering.review.requested",)
    assert result.review.implementation_digest == DIGEST
    assert result.review.files_under_review == tuple(sorted(FILES))
    assert result.review.status is ReviewStatus.REQUESTED


def test_a_request_without_an_artifact_digest_is_refused_before_the_service() -> None:
    with pytest.raises(ContractViolation):
        _request(implementation_digest="  ")


def test_a_request_without_a_lens_is_refused() -> None:
    with pytest.raises(ContractViolation):
        _request(lens="")


def test_one_lens_reviews_one_round_once(service, context) -> None:
    """Two would let one reviewer approve what another blocked."""
    service.request(context, _request())
    with pytest.raises(DuplicateReview):
        service.request(context, _request())


def test_different_lenses_on_one_round_coexist(service, context) -> None:
    for lens in required_lens_values():
        service.request(context, _request(lens=lens))
    found = service.list(context, ListReviews(work_id=WORK, round=1))
    assert {r.lens.value for r in found} == set(required_lens_values())


def test_a_superseded_review_frees_the_lens_for_a_new_one(service, context) -> None:
    first = str(service.request(context, _request()).review.review_id)
    second = str(service.request(context, _request(lens="security")).review.review_id)
    service.supersede(
        context, SupersedeReview(review_id=first, successor_id=second)
    )
    reopened = service.request(context, _request())
    assert reopened.review.lens is ReviewLens.CORRECTNESS


def test_two_rounds_for_one_workorder_coexist(service, context) -> None:
    service.request(context, _request(round=1))
    service.request(context, _request(round=2))
    assert len(service.list(context, ListReviews(work_id=WORK))) == 2


# ----------------------------------------------------------------------
# Finding lifecycle through the service
# ----------------------------------------------------------------------


def test_a_finding_carries_the_reviews_references(service, context) -> None:
    review_id = _in_progress(service, context)
    result = service.add_finding(context, _blocking(review_id))
    raised = result.review.findings[0]
    assert raised.work_id == WORK
    assert raised.implementation_id == IMPL
    assert result.event_types == ("engineering.review.finding_added",)


def test_a_finding_with_no_anchor_is_refused_by_the_command() -> None:
    with pytest.raises(ContractViolation):
        AddFinding(review_id="R", summary="something is wrong")


def test_a_blocking_finding_without_a_remedy_is_refused_by_the_command() -> None:
    with pytest.raises(ContractViolation):
        AddFinding(review_id="R", summary="wrong", severity="blocking", path="a.py")


def test_resolving_a_finding_emits_the_resolution(service, context) -> None:
    review_id = _in_progress(service, context)
    finding_id = str(service.add_finding(context, _blocking(review_id)).review.findings[0].finding_id)
    result = service.resolve_finding(
        context,
        ResolveFinding(review_id=review_id, finding_id=finding_id, resolution="fixed"),
    )
    assert result.event_types == ("engineering.review.finding_resolved",)
    assert result.review.open_blockers == ()


def test_waiving_a_blocking_finding_is_refused_by_the_service(service, context) -> None:
    from backend.contexts.review import BlockingFindingCannotBeWaived

    review_id = _in_progress(service, context)
    finding_id = str(service.add_finding(context, _blocking(review_id)).review.findings[0].finding_id)
    with pytest.raises(BlockingFindingCannotBeWaived):
        service.resolve_finding(
            context,
            ResolveFinding(
                review_id=review_id,
                finding_id=finding_id,
                resolution="accepted_risk",
                note="later",
            ),
        )


def test_accepting_a_risk_without_a_note_is_refused_by_the_command() -> None:
    with pytest.raises(ContractViolation):
        ResolveFinding(review_id="R", finding_id="F", resolution="accepted_risk")


def test_a_comment_is_recorded_without_becoming_a_finding(service, context) -> None:
    review_id = _in_progress(service, context)
    result = service.add_comment(
        context, AddComment(review_id=review_id, body="why is this ordering significant?")
    )
    assert len(result.review.comments) == 1
    assert result.review.findings == ()


# ----------------------------------------------------------------------
# Approval flow
# ----------------------------------------------------------------------


def test_the_policy_reports_every_failure_not_the_first(service, context) -> None:
    review_id = _in_progress(service, context)
    service.add_finding(context, _blocking(review_id))

    report = service.evaluate(context, review_id, "approved")
    rules = {f.rule for f in report.blocking}
    assert "R1-no-open-blockers" in rules
    assert "R2-change-set-examined" in rules
    assert not report.may_decide


def test_evaluate_reports_without_deciding(service, context) -> None:
    review_id = _approvable(service, context)
    assert service.evaluate(context, review_id, "approved").may_decide
    assert service.get(context, GetReview(review_id=review_id)).status is ReviewStatus.IN_PROGRESS


def test_approving_seals_the_review_and_binds_the_digest(service, context) -> None:
    review_id = _approvable(service, context)
    result = service.decide(
        context, DecideReview(review_id=review_id, decision="approved", decided_by="alice")
    )
    assert result.event_types == ("engineering.review.approved",)
    assert result.review.digest
    result.review.verify_digest()


def test_approving_over_an_open_blocker_is_refused_by_the_service(service, context) -> None:
    review_id = _approvable(service, context)
    service.add_finding(context, _blocking(review_id))
    with pytest.raises(DecisionRefused) as caught:
        service.decide(context, DecideReview(review_id=review_id, decision="approved"))
    assert any(f.rule == "R1-no-open-blockers" for f in caught.value.failures)


def test_approving_an_unexamined_change_set_is_refused_by_the_service(service, context) -> None:
    review_id = _in_progress(service, context)
    with pytest.raises(DecisionRefused) as caught:
        service.decide(context, DecideReview(review_id=review_id, decision="approved"))
    assert any(f.rule == "R2-change-set-examined" for f in caught.value.failures)


def test_a_clean_approval_is_flagged_advisory_not_blocked(service, context) -> None:
    review_id = _approvable(service, context)
    report = service.evaluate(context, review_id, "approved")
    assert report.may_decide
    assert any(f.rule == "R8-nothing-recorded" for f in report.advisory)


def test_an_accepted_risk_travels_forward_as_advisory(service, context) -> None:
    review_id = _approvable(service, context)
    finding_id = str(
        service.add_finding(
            context,
            AddFinding(
                review_id=review_id,
                summary="the retry has no jitter",
                severity="major",
                category="performance",
                path="backend/a.py",
            ),
        ).review.findings[0].finding_id
    )
    service.resolve_finding(
        context,
        ResolveFinding(
            review_id=review_id,
            finding_id=finding_id,
            resolution="accepted_risk",
            note="the path is behind a flag that is off",
        ),
    )
    report = service.evaluate(context, review_id, "approved")
    assert report.may_decide
    assert any(f.rule == "R7-accepted-risk" for f in report.advisory)


def test_a_decided_review_refuses_further_recording_through_the_service(service, context) -> None:
    from backend.contexts.review import ReviewDecided

    review_id = _approvable(service, context)
    service.decide(context, DecideReview(review_id=review_id, decision="approved"))
    with pytest.raises(ReviewDecided):
        service.add_finding(context, _blocking(review_id))


# ----------------------------------------------------------------------
# Rejection and changes-requested flows
# ----------------------------------------------------------------------


def test_requesting_changes_emits_its_own_event(service, context) -> None:
    """Not folded into rejection: they send the WorkOrder to different phases."""
    review_id = _approvable(service, context)
    service.add_finding(context, _blocking(review_id))
    result = service.decide(
        context,
        DecideReview(
            review_id=review_id,
            decision="changes_requested",
            rationale="the tenancy hole must close first",
        ),
    )
    assert result.event_types == ("engineering.review.changes_requested",)
    assert result.review.decision is ReviewDecision.CHANGES_REQUESTED


def test_requesting_changes_with_nothing_outstanding_is_refused(service, context) -> None:
    """The round would go back with nothing to act on."""
    review_id = _approvable(service, context)
    with pytest.raises(DecisionRefused) as caught:
        service.decide(
            context,
            DecideReview(
                review_id=review_id, decision="changes_requested", rationale="please fix"
            ),
        )
    assert any(f.rule == "R4-changes-need-a-finding" for f in caught.value.failures)


def test_rejecting_emits_its_own_event_and_needs_no_finding(service, context) -> None:
    """A round can be rejected because the WorkOrder's premise turned out false."""
    review_id = _approvable(service, context)
    result = service.decide(
        context,
        DecideReview(
            review_id=review_id,
            decision="rejected",
            rationale="the premise the WorkOrder rests on does not hold",
        ),
    )
    assert result.event_types == ("engineering.review.rejected",)


def test_a_refusal_without_a_reason_is_refused_by_the_command() -> None:
    with pytest.raises(ContractViolation):
        DecideReview(review_id="R", decision="rejected")


def test_rejecting_does_not_require_examining_everything(service, context) -> None:
    """Coverage gates approval only. A reviewer who finds a fatal flaw on the
    first file should not have to read the rest to say so."""
    review_id = _in_progress(service, context)
    service.add_finding(context, _blocking(review_id))
    result = service.decide(
        context,
        DecideReview(
            review_id=review_id, decision="rejected", rationale="fatal on first read"
        ),
    )
    assert result.review.decision is ReviewDecision.REJECTED


# ----------------------------------------------------------------------
# Lens coverage
# ----------------------------------------------------------------------


def test_lens_coverage_reports_what_never_reported(service, context) -> None:
    """A missing lens is not a passing lens."""
    review_id = _approvable(service, context, lens="correctness")
    service.decide(context, DecideReview(review_id=review_id, decision="approved"))

    coverage = service.lens_coverage(context, WORK, 1)
    assert coverage.decided == ("correctness",)
    assert set(coverage.missing) == set(required_lens_values()) - {"correctness"}
    assert not coverage.complete
    assert not coverage.fully_approved


def test_lens_coverage_is_complete_when_every_required_lens_decided(service, context) -> None:
    for lens in required_lens_values():
        review_id = _approvable(service, context, lens=lens)
        service.decide(context, DecideReview(review_id=review_id, decision="approved"))

    coverage = service.lens_coverage(context, WORK, 1)
    assert coverage.complete
    assert coverage.fully_approved


def test_one_rejected_lens_means_not_fully_approved(service, context) -> None:
    for lens in required_lens_values():
        review_id = _approvable(service, context, lens=lens)
        decision = "rejected" if lens == "security" else "approved"
        service.decide(
            context,
            DecideReview(
                review_id=review_id, decision=decision, rationale="unsafe" if decision == "rejected" else None
            ),
        )
    coverage = service.lens_coverage(context, WORK, 1)
    assert coverage.complete
    assert not coverage.fully_approved


def test_an_undecided_review_is_not_reported_to_the_runtime(service, context) -> None:
    _approvable(service, context)
    assert service.decided_for(context, WORK, 1) == ()


def test_a_superseded_review_is_not_reported_to_the_runtime(service, context) -> None:
    first = _approvable(service, context)
    service.decide(context, DecideReview(review_id=first, decision="approved"))
    second = str(service.request(context, _request(lens="security")).review.review_id)
    service.supersede(context, SupersedeReview(review_id=first, successor_id=second))
    assert service.decided_for(context, WORK, 1) == ()


# ----------------------------------------------------------------------
# Repository
# ----------------------------------------------------------------------


def test_every_repository_method_requires_an_execution_context(repository) -> None:
    from backend.contexts.review.domain.identifiers import ReviewId

    for call in (
        lambda: repository.find(None, ReviewId.new()),
        lambda: repository.all(None),
        lambda: repository.for_work_order(None, WORK),
        lambda: repository.for_round(None, WORK, 1),
    ):
        with pytest.raises(MissingExecutionContext):
            call()


def test_a_tenant_cannot_see_another_tenants_review(repository, tenant_context) -> None:
    from backend.platform.context.identity import IdentityContext
    from backend.platform.storage import CrossTenantAccess

    service = ReviewService(repository=repository)
    review = service.request(tenant_context, _request()).review

    other = ExecutionContext.for_tenant(
        tenant_id="tenant-b", identity=IdentityContext.platform("tests"), source="pytest"
    )
    assert repository.find(other, review.review_id) is None
    with pytest.raises(CrossTenantAccess):
        repository.replace(other, review)


def test_the_repository_is_not_grandfathered() -> None:
    """The grandfather list may only shrink; a new repository never joins it."""
    from backend.platform.architecture.tenancy_rules import GRANDFATHERED_REPOSITORIES

    assert not any("review" in entry.lower() for entry in GRANDFATHERED_REPOSITORIES)


def test_an_unknown_review_is_reported_as_missing(service, context) -> None:
    from backend.contexts.review.domain.identifiers import ReviewId

    with pytest.raises(ReviewNotFound):
        service.get(context, GetReview(review_id=str(ReviewId.new())))


# ----------------------------------------------------------------------
# Replay
# ----------------------------------------------------------------------


def test_a_review_survives_the_round_trip_unchanged(service, context) -> None:
    review_id = _approvable(service, context)
    finding_id = str(service.add_finding(context, _blocking(review_id)).review.findings[0].finding_id)
    service.resolve_finding(
        context,
        ResolveFinding(review_id=review_id, finding_id=finding_id, resolution="fixed"),
    )
    service.add_comment(context, AddComment(review_id=review_id, body="thanks for fixing"))
    decided = service.decide(
        context, DecideReview(review_id=review_id, decision="approved", decided_by="alice")
    ).review

    restored = from_record(to_record(decided, tenant_id="tenant-a"))
    assert restored == decided


def test_the_digest_is_restored_not_recomputed(service, context) -> None:
    """Recomputing on load would make verification always pass -- a check that
    cannot fail."""
    review_id = _approvable(service, context)
    decided = service.decide(
        context, DecideReview(review_id=review_id, decision="approved")
    ).review

    stored = to_record(decided, tenant_id="tenant-a")
    stored["files_examined"] = ["backend/a.py"]

    from backend.contexts.review import DigestMismatch

    with pytest.raises(DigestMismatch):
        from_record(stored).verify_digest()


def test_a_review_from_an_unknown_schema_version_is_refused(service, context) -> None:
    review = service.request(context, _request()).review
    stored = to_record(review, tenant_id="tenant-a")
    stored["schema_version"] = RECORD_SCHEMA_VERSION + 1
    with pytest.raises(ContractViolation):
        from_record(stored)


def test_a_review_stored_without_a_tenant_is_refused(service, context) -> None:
    review = service.request(context, _request()).review
    with pytest.raises(ContractViolation):
        to_record(review, tenant_id="  ")


# ----------------------------------------------------------------------
# Concurrency
# ----------------------------------------------------------------------


def test_concurrent_lens_requests_all_persist(service, context) -> None:
    """The runtime opens every required lens at once; this is the normal case."""
    errors: list = []

    def open_one(lens: str) -> None:
        try:
            service.request(context, _request(lens=lens))
        except Exception as exc:  # pragma: no cover - failure path
            errors.append(exc)

    threads = [
        threading.Thread(target=open_one, args=(lens,)) for lens in required_lens_values()
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == []
    assert len(service.list(context, ListReviews(work_id=WORK, round=1))) == len(
        required_lens_values()
    )


def test_concurrent_reads_during_writes_do_not_tear(service, context) -> None:
    seen: list = []
    errors: list = []
    stop = threading.Event()

    def write() -> None:
        try:
            for index, lens in enumerate(required_lens_values()):
                service.request(context, _request(lens=lens, round=index + 1))
        except Exception as exc:  # pragma: no cover - failure path
            errors.append(exc)
        finally:
            stop.set()

    def read() -> None:
        while not stop.is_set():
            try:
                seen.append(len(service.list(context, ListReviews(work_id=WORK))))
            except Exception as exc:  # pragma: no cover - failure path
                errors.append(exc)

    writer, reader = threading.Thread(target=write), threading.Thread(target=read)
    writer.start()
    reader.start()
    writer.join()
    reader.join()

    assert errors == []
    assert seen == sorted(seen)


# ----------------------------------------------------------------------
# API
# ----------------------------------------------------------------------


@pytest.fixture
def client(monkeypatch) -> TestClient:
    monkeypatch.setattr(
        routes, "_service", ReviewService(repository=InMemoryReviewRepository())
    )
    app = FastAPI()
    app.include_router(routes.router)
    return TestClient(app)


def _open_via_api(client, **overrides) -> str:
    payload = dict(
        work_id=WORK,
        lens="correctness",
        implementation_id=IMPL,
        implementation_digest=DIGEST,
        revision=REVISION,
        files_under_review=list(FILES),
    )
    payload.update(overrides)
    response = client.post("/api/v1/engineering/review", json=payload)
    assert response.status_code == 201, response.text
    return response.json()["review"]["review_id"]


def test_the_api_reports_the_required_lenses(client) -> None:
    body = client.get("/api/v1/engineering/review/lenses").json()
    assert set(body["required"]) == set(required_lens_values())
    assert any(lens["lens"] == "performance" and not lens["required"] for lens in body["all"])


def test_the_api_opens_and_fetches_a_review(client) -> None:
    review_id = _open_via_api(client)
    body = client.get(f"/api/v1/engineering/review/{review_id}").json()
    assert body["lens"] == "correctness"
    assert body["implementation_digest"] == DIGEST
    assert body["unexamined_files"] == sorted(FILES)


def test_the_api_refuses_a_second_review_for_one_lens(client) -> None:
    _open_via_api(client)
    response = client.post(
        "/api/v1/engineering/review",
        json=dict(
            work_id=WORK,
            lens="correctness",
            implementation_id=IMPL,
            implementation_digest=DIGEST,
            revision=REVISION,
        ),
    )
    assert response.status_code == 409


def test_the_api_refuses_a_finding_with_no_anchor(client) -> None:
    review_id = _open_via_api(client)
    client.post(f"/api/v1/engineering/review/{review_id}/start", json={"reviewer": "alice"})
    response = client.post(
        f"/api/v1/engineering/review/{review_id}/findings",
        json={"summary": "something is wrong"},
    )
    assert response.status_code == 400


def test_the_api_refuses_a_finding_before_the_review_is_started(client) -> None:
    review_id = _open_via_api(client)
    response = client.post(
        f"/api/v1/engineering/review/{review_id}/findings",
        json={"summary": "wrong", "path": "backend/a.py"},
    )
    assert response.status_code == 409


def test_the_api_reports_every_approval_failure(client) -> None:
    review_id = _open_via_api(client)
    client.post(f"/api/v1/engineering/review/{review_id}/start", json={"reviewer": "alice"})
    client.post(
        f"/api/v1/engineering/review/{review_id}/findings",
        json={
            "summary": "tenant from payload",
            "severity": "blocking",
            "path": "backend/a.py",
            "required_change": "derive from context",
        },
    )
    response = client.post(
        f"/api/v1/engineering/review/{review_id}/decide", json={"decision": "approved"}
    )
    assert response.status_code == 422
    rules = {f["rule"] for f in response.json()["detail"]["failures"]}
    assert {"R1-no-open-blockers", "R2-change-set-examined"} <= rules


def test_the_policy_endpoint_reports_without_deciding(client) -> None:
    review_id = _open_via_api(client)
    client.post(f"/api/v1/engineering/review/{review_id}/start", json={"reviewer": "alice"})
    body = client.get(
        f"/api/v1/engineering/review/{review_id}/policy?decision=approved"
    ).json()
    assert not body["may_decide"]
    assert any(f["rule"] == "R2-change-set-examined" for f in body["blocking"])
    assert client.get(f"/api/v1/engineering/review/{review_id}").json()["status"] == "in_progress"


def test_the_api_runs_a_full_review_to_approval(client) -> None:
    review_id = _open_via_api(client)
    client.post(f"/api/v1/engineering/review/{review_id}/start", json={"reviewer": "alice"})
    client.post(
        f"/api/v1/engineering/review/{review_id}/examine", json={"paths": list(FILES)}
    )
    raised = client.post(
        f"/api/v1/engineering/review/{review_id}/findings",
        json={
            "summary": "off by one",
            "severity": "blocking",
            "path": "backend/a.py",
            "line": 3,
            "required_change": "use <=",
        },
    ).json()
    finding_id = raised["review"]["findings"][0]["finding_id"]
    client.post(
        f"/api/v1/engineering/review/{review_id}/findings/{finding_id}/resolve",
        json={"resolution": "fixed"},
    )
    response = client.post(
        f"/api/v1/engineering/review/{review_id}/decide",
        json={"decision": "approved", "decided_by": "alice"},
    )
    assert response.status_code == 200, response.text
    body = response.json()["review"]
    assert body["decision"] == "approved"
    assert body["digest"]
    assert body["coverage_ratio"] == 1.0


def test_the_api_refuses_waiving_a_blocking_finding(client) -> None:
    review_id = _open_via_api(client)
    client.post(f"/api/v1/engineering/review/{review_id}/start", json={"reviewer": "alice"})
    raised = client.post(
        f"/api/v1/engineering/review/{review_id}/findings",
        json={
            "summary": "unsafe",
            "severity": "blocking",
            "path": "backend/a.py",
            "required_change": "fix it",
        },
    ).json()
    finding_id = raised["review"]["findings"][0]["finding_id"]
    response = client.post(
        f"/api/v1/engineering/review/{review_id}/findings/{finding_id}/resolve",
        json={"resolution": "accepted_risk", "note": "ship it"},
    )
    assert response.status_code == 422


def test_the_api_returns_409_once_decided(client) -> None:
    review_id = _open_via_api(client)
    client.post(f"/api/v1/engineering/review/{review_id}/start", json={"reviewer": "alice"})
    client.post(f"/api/v1/engineering/review/{review_id}/examine", json={"paths": list(FILES)})
    client.post(f"/api/v1/engineering/review/{review_id}/decide", json={"decision": "approved"})
    response = client.post(
        f"/api/v1/engineering/review/{review_id}/decide", json={"decision": "approved"}
    )
    assert response.status_code == 409


def test_the_api_returns_404_for_an_unknown_review(client) -> None:
    from backend.contexts.review.domain.identifiers import ReviewId

    assert client.get(f"/api/v1/engineering/review/{ReviewId.new()}").status_code == 404


def test_the_api_reports_lens_coverage(client) -> None:
    review_id = _open_via_api(client)
    client.post(f"/api/v1/engineering/review/{review_id}/start", json={"reviewer": "alice"})
    client.post(f"/api/v1/engineering/review/{review_id}/examine", json={"paths": list(FILES)})
    client.post(f"/api/v1/engineering/review/{review_id}/decide", json={"decision": "approved"})

    body = client.get(f"/api/v1/engineering/review/coverage?work_id={WORK}&round=1").json()
    assert body["decided"] == ["correctness"]
    assert not body["complete"]
    assert set(body["missing"]) == set(required_lens_values()) - {"correctness"}


def test_the_api_lists_and_filters(client) -> None:
    _open_via_api(client, lens="correctness")
    _open_via_api(client, lens="security")
    assert client.get(f"/api/v1/engineering/review?work_id={WORK}").json()["count"] == 2
    filtered = client.get(f"/api/v1/engineering/review?work_id={WORK}&lens=security").json()
    assert filtered["count"] == 1


def test_the_structured_refusal_body_does_not_survive_the_real_app(client) -> None:
    """Pre-existing and app-wide, recorded rather than papered over.

    ``backend/core/exception_handlers.py`` discards ``exc.detail`` and
    substitutes a canned message per status code, so the structured body these
    routes raise reaches a real client as generic prose. The status codes do
    survive, and ``GET /policy`` is unaffected because it reports findings in a
    200 body rather than through an exception -- which is where the detail
    matters most, since it is what a reviewer reads before deciding.

    This test asserts the *route-level* body, which is what ``TestClient`` over a
    bare ``FastAPI()`` sees. ADR-024 records the divergence.
    """
    review_id = _open_via_api(client)
    client.post(f"/api/v1/engineering/review/{review_id}/start", json={"reviewer": "alice"})
    response = client.post(
        f"/api/v1/engineering/review/{review_id}/decide", json={"decision": "approved"}
    )
    assert response.status_code == 422
    assert response.json()["detail"]["error"] == "decision_refused"


# ----------------------------------------------------------------------
# Runtime wiring
# ----------------------------------------------------------------------


def _approved_work_order(stack, context) -> str:
    from backend.contexts.workorder import ApproveWorkOrder, BlastRadius, DraftWorkOrder

    drafted = stack.work_order_service.draft(
        context,
        DraftWorkOrder(
            intent="Review reads the diff independently",
            acceptance_criteria=("Each required lens reports",),
            blast_radius=BlastRadius.of(["backend/contexts/review/**"]),
            adr_references=("ADR-019",),
            evidence=("EV-1",),
            constraints=("I6",),
            definition_of_done=("a lens that never reported is visible",),
        ),
    )
    work_id = str(drafted.work_order.work_id)
    stack.work_order_service.approve(
        context, ApproveWorkOrder(work_id=work_id, approved_by="founder")
    )
    return work_id


@pytest.fixture
def stack():
    from backend.contexts.workorder import (
        InMemoryWorkOrderRepository,
        StaticReferenceResolver,
        WorkOrderService,
    )

    service = WorkOrderService(
        repository=InMemoryWorkOrderRepository(),
        resolver=StaticReferenceResolver(
            known_adrs=frozenset({"ADR-019"}),
            known_evidence=frozenset({"EV-1"}),
            enforceable_constraints=frozenset({"I6"}),
        ),
    )
    return build_engineering_runtime(service=service)


def test_the_adapter_satisfies_the_port_structurally() -> None:
    adapter = ReviewServiceAdapter(ReviewService(repository=InMemoryReviewRepository()))
    assert isinstance(adapter, ReviewPort)


def test_the_runtime_wires_the_review_service(stack) -> None:
    from backend.contexts.engineering import GetLifecycleCapability

    capability = stack.queries.capability(GetLifecycleCapability())
    assert "review" in capability["wired"]
    assert capability["missing"] == []


def test_entering_review_opens_every_required_lens(stack, context) -> None:
    """A missing lens is not a passing lens, so every one is asked for."""
    work_id = _approved_work_order(stack, context)
    for phase in ("assigned", "spec_tests", "implementation", "review"):
        stack.runtime.transition(context, work_id, phase, actor="orchestrator")

    opened = stack.review_service.list(context, ListReviews(work_id=work_id, round=1))
    assert {r.lens.value for r in opened} == set(required_lens_values())


def test_the_review_is_bound_to_the_real_implementation_artifact(stack, context) -> None:
    """The claim this PR rests on: reviews read a specific, pinned artifact."""
    from backend.contexts.implementation_record import (
        AddClaim,
        CompleteImplementation,
        RecordFile,
        RecordTests,
        StartImplementation,
    )

    work_id = _approved_work_order(stack, context)
    for phase in ("assigned", "spec_tests"):
        stack.runtime.transition(context, work_id, phase, actor="orchestrator")

    implementations = stack.implementation_service
    record_id = str(
        implementations.start(
            context,
            StartImplementation(
                work_id=work_id,
                context_bundle_id="CB-1",
                revision="rev-abc",
                blast_radius_allowed=("backend/contexts/review/**",),
            ),
        ).record.implementation_id
    )
    implementations.record_file(
        context,
        RecordFile(
            implementation_id=record_id,
            path="backend/contexts/review/domain/record.py",
            kind="added",
            lines_added=400,
        ),
    )
    implementations.add_claim(
        context,
        AddClaim(
            implementation_id=record_id,
            statement="approval refuses over an open blocker",
            evidence=("EV-9",),
        ),
    )
    implementations.record_tests(
        context,
        RecordTests(
            implementation_id=record_id, command="pytest tests/contexts/review", passed=90
        ),
    )
    sealed = implementations.complete(
        context, CompleteImplementation(implementation_id=record_id)
    ).record

    for phase in ("implementation", "review"):
        stack.runtime.transition(context, work_id, phase, actor="orchestrator")

    opened = stack.review_service.list(context, ListReviews(work_id=work_id, round=1))
    assert opened
    for review in opened:
        assert review.implementation_id == str(sealed.implementation_id)
        assert review.implementation_digest == sealed.digest
        assert review.revision == "rev-abc"
        assert review.files_under_review == (
            "backend/contexts/review/domain/record.py",
        )


def test_the_placeholder_is_visible_when_no_record_is_sealed(stack, context) -> None:
    """Reviews still open, and say plainly that they read nothing recorded.

    Refusing would make ``implementation -> review`` unreachable for a lifecycle
    driven without an ImplementationRecord; fabricating a digest would defeat the
    binding. The placeholder is the visible middle, and ADR-024 records it as a
    remaining risk rather than a feature.
    """
    work_id = _approved_work_order(stack, context)
    for phase in ("assigned", "spec_tests", "implementation", "review"):
        stack.runtime.transition(context, work_id, phase, actor="orchestrator")

    opened = stack.review_service.list(context, ListReviews(work_id=work_id, round=1))
    assert all(r.implementation_digest == "unrecorded" for r in opened)
    assert all(r.files_under_review == () for r in opened)


def test_the_adapter_reports_approval_as_the_verdict_the_runtime_accepts(stack, context) -> None:
    """The drift test for the one string this context does not own.

    ``ReviewOutcome.passed`` is the runtime's rule. If it ever stopped accepting
    ``"pass"``, or started counting blockers differently, this fails here rather
    than silently reporting an unreviewed round as reviewed.
    """
    work_id = _approved_work_order(stack, context)
    for phase in ("assigned", "spec_tests", "implementation", "review"):
        stack.runtime.transition(context, work_id, phase, actor="orchestrator")

    for review in stack.review_service.list(context, ListReviews(work_id=work_id, round=1)):
        review_id = str(review.review_id)
        stack.review_service.start(context, StartReview(review_id=review_id, reviewer="alice"))
        stack.review_service.decide(
            context, DecideReview(review_id=review_id, decision="approved")
        )

    outcomes = stack.review_adapter.outcomes(context, work_id, 1)
    assert len(outcomes) == len(required_lens_values())
    for outcome in outcomes:
        assert isinstance(outcome, ReviewOutcome)
        assert outcome.verdict == "pass"
        assert outcome.passed


def test_a_fixed_blocker_does_not_fail_the_round(stack, context) -> None:
    """``blocking_findings`` on the outcome counts *open* blockers.

    Reporting every blocker ever raised would make ``passed`` false for a review
    that legitimately approved -- punishing the reviewer who found something and
    got it fixed.
    """
    work_id = _approved_work_order(stack, context)
    for phase in ("assigned", "spec_tests", "implementation", "review"):
        stack.runtime.transition(context, work_id, phase, actor="orchestrator")

    reviews = stack.review_service.list(context, ListReviews(work_id=work_id, round=1))
    first = str(reviews[0].review_id)
    stack.review_service.start(context, StartReview(review_id=first, reviewer="alice"))
    finding_id = str(
        stack.review_service.add_finding(context, _blocking(first)).review.findings[0].finding_id
    )
    stack.review_service.resolve_finding(
        context, ResolveFinding(review_id=first, finding_id=finding_id, resolution="fixed")
    )
    stack.review_service.decide(context, DecideReview(review_id=first, decision="approved"))

    outcome = next(
        o for o in stack.review_adapter.outcomes(context, work_id, 1)
        if o.lens == reviews[0].lens.value
    )
    assert outcome.blocking_findings == 0
    assert outcome.passed


def test_changes_requested_is_never_reported_as_a_rejection(stack, context) -> None:
    """They send the WorkOrder to different phases."""
    work_id = _approved_work_order(stack, context)
    for phase in ("assigned", "spec_tests", "implementation", "review"):
        stack.runtime.transition(context, work_id, phase, actor="orchestrator")

    reviews = stack.review_service.list(context, ListReviews(work_id=work_id, round=1))
    first = str(reviews[0].review_id)
    stack.review_service.start(context, StartReview(review_id=first, reviewer="alice"))
    stack.review_service.add_finding(context, _blocking(first))
    stack.review_service.decide(
        context,
        DecideReview(
            review_id=first, decision="changes_requested", rationale="close the hole"
        ),
    )

    outcome = next(
        o for o in stack.review_adapter.outcomes(context, work_id, 1)
        if o.lens == reviews[0].lens.value
    )
    assert outcome.verdict == "changes_requested"
    assert not outcome.passed


def test_the_lifecycle_now_reaches_verification_through_review(stack, context) -> None:
    """The claim PR-E6 exists to make true."""
    work_id = _approved_work_order(stack, context)
    for phase in ("assigned", "spec_tests", "implementation", "review"):
        stack.runtime.transition(context, work_id, phase, actor="orchestrator")

    for review in stack.review_service.list(context, ListReviews(work_id=work_id, round=1)):
        review_id = str(review.review_id)
        stack.review_service.start(context, StartReview(review_id=review_id, reviewer="alice"))
        stack.review_service.decide(
            context, DecideReview(review_id=review_id, decision="approved")
        )

    result = stack.runtime.transition(context, work_id, "verification", actor="orchestrator")
    assert result.snapshot.phase.value == "verification"


def test_re_entering_review_does_not_open_a_second_review_per_lens(stack, context) -> None:
    """A retried transition is not an error, and must not double the reviews."""
    work_id = _approved_work_order(stack, context)
    for phase in ("assigned", "spec_tests", "implementation", "review"):
        stack.runtime.transition(context, work_id, phase, actor="orchestrator")

    before = len(stack.review_service.list(context, ListReviews(work_id=work_id, round=1)))
    stack.review_adapter.request(context, work_id, 1, required_lens_values())
    after = len(stack.review_service.list(context, ListReviews(work_id=work_id, round=1)))
    assert before == after == len(required_lens_values())


def test_the_previous_behaviour_is_still_testable(context) -> None:
    """A test asserting an unwired port is refused needs a way to unwire it."""
    from backend.contexts.engineering import CollaboratorUnavailable, GetLifecycleCapability
    from backend.contexts.workorder import (
        InMemoryWorkOrderRepository,
        StaticReferenceResolver,
        WorkOrderService,
    )

    stack = build_engineering_runtime(
        service=WorkOrderService(
            repository=InMemoryWorkOrderRepository(),
            resolver=StaticReferenceResolver(
                known_adrs=frozenset({"ADR-019"}),
                known_evidence=frozenset({"EV-1"}),
                enforceable_constraints=frozenset({"I6"}),
            ),
        ),
        wire_review=False,
    )
    capability = stack.queries.capability(GetLifecycleCapability())
    assert set(capability["missing"]) == {"review"}

    work_id = _approved_work_order(stack, context)
    for phase in ("assigned", "spec_tests", "implementation"):
        stack.runtime.transition(context, work_id, phase, actor="orchestrator")
    with pytest.raises(CollaboratorUnavailable):
        stack.runtime.transition(context, work_id, "review", actor="x")


def test_the_artifact_source_reports_nothing_rather_than_guessing(context) -> None:
    from backend.contexts.implementation_record import (
        ImplementationRecordService,
        InMemoryImplementationRepository,
    )

    source = ImplementationArtifactSource(
        ImplementationRecordService(repository=InMemoryImplementationRepository())
    )
    assert source.artifact_for(context, "WO-NONE") is None


# ----------------------------------------------------------------------
# Constitution compliance
# ----------------------------------------------------------------------


def _modules() -> list:
    root = pathlib.Path("backend/contexts/review")
    return [p for p in root.rglob("*.py") if "__pycache__" not in p.parts]


def _imports(path: pathlib.Path) -> list:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: list = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.append(node.module)
    return found


def test_the_context_imports_only_contracts_and_platform() -> None:
    permitted = ("backend.contracts", "backend.platform", "backend.contexts.review")
    offences = [
        f"{path}: {imported}"
        for path in _modules()
        for imported in _imports(path)
        if imported.startswith("backend.") and not imported.startswith(permitted)
    ]
    assert offences == [], offences


def test_review_never_reaches_the_implementation_it_reviews() -> None:
    """S2, and the rule that makes Review an independent read.

    A reviewer that could edit what it reviews is a second author, and a second
    author agreeing with the first tells you nothing. Enforced structurally: this
    context holds the implementation's id and digest as opaque strings and has no
    import path to the aggregate they name.
    """
    offences = [
        f"{path}: {imported}"
        for path in _modules()
        for imported in _imports(path)
        if imported.startswith("backend.contexts.")
        and not imported.startswith("backend.contexts.review")
    ]
    assert offences == [], offences


def test_the_domain_layer_does_no_io() -> None:
    banned = {"pathlib", "os", "socket", "requests", "httpx", "sqlite3", "json"}
    root = pathlib.Path("backend/contexts/review/domain")
    offences = [
        f"{path}: {imported}"
        for path in root.rglob("*.py")
        if "__pycache__" not in path.parts
        for imported in _imports(path)
        if imported.split(".")[0] in banned
    ]
    assert offences == [], offences


def test_event_types_are_namespaced_and_disjoint() -> None:
    from backend.contexts.context_bundle import CONTEXT_EVENT_TYPES
    from backend.contexts.engineering import RUNTIME_EVENT_TYPES
    from backend.contexts.engineering_verification import VERIFICATION_EVENT_TYPES
    from backend.contexts.implementation_record import IMPLEMENTATION_EVENT_TYPES
    from backend.contexts.review import REVIEW_EVENT_TYPES

    ours = {e.EVENT_TYPE for e in REVIEW_EVENT_TYPES}
    assert all(e.startswith("engineering.review.") for e in ours)
    for other in (
        CONTEXT_EVENT_TYPES,
        RUNTIME_EVENT_TYPES,
        VERIFICATION_EVENT_TYPES,
        IMPLEMENTATION_EVENT_TYPES,
    ):
        assert ours.isdisjoint({e.EVENT_TYPE for e in other})


def test_the_runtime_owns_a_different_review_requested_event() -> None:
    """Two facts, both worth having: the orchestrator asked, and the context
    opened a record. They coincide today and will not once requests are queued."""
    from backend.contexts.engineering import ReviewRequested as RuntimeReviewRequested
    from backend.contexts.review import ReviewRequested as ContextReviewRequested

    assert RuntimeReviewRequested.EVENT_TYPE != ContextReviewRequested.EVENT_TYPE


def test_the_composition_root_is_the_only_module_importing_two_contexts() -> None:
    root = pathlib.Path("backend/api")
    offenders = []
    for path in root.rglob("*.py"):
        if "__pycache__" in path.parts or path.name == "engineering_composition.py":
            continue
        contexts = {
            imported.split(".")[2]
            for imported in _imports(path)
            if imported.startswith("backend.contexts.") and len(imported.split(".")) > 2
        }
        if len(contexts) > 1:
            offenders.append(f"{path}: {sorted(contexts)}")
    assert offenders == [], offenders
