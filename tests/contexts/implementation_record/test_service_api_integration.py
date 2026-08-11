"""Service, repository, replay, concurrency, API, and the runtime wiring.

The integration section pins the claim this PR rests on: Verification stops
receiving a placeholder claim and starts receiving what the implementer actually
asserted, anchored to the revision it was asserted against. That was ADR-021's
named remaining risk, and a test that only checked "an ImplementationRecord
exists" would not have closed it.
"""

from __future__ import annotations

import ast
import pathlib
import threading

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api import implementation_record_routes as routes
from backend.api.engineering_composition import (
    ImplementationClaimSource,
    build_engineering_runtime,
)
from backend.contexts.implementation_record import (
    AbandonImplementation,
    AddClaim,
    CompleteImplementation,
    DeclareRisk,
    DuplicateRecord,
    GetImplementation,
    ImplementationRecordService,
    ImplementationStatus,
    IncompleteRecord,
    InMemoryImplementationRepository,
    ListImplementations,
    NoteDeviation,
    OutsideBlastRadius,
    RecordBuild,
    RecordCompleted,
    RecordCoverage,
    RecordFile,
    RecordNotFound,
    RecordTests,
    ResolveAssumption,
    StartImplementation,
    SupersedeImplementation,
)
from backend.contexts.implementation_record.infrastructure.persistence import (
    RECORD_SCHEMA_VERSION,
    from_record,
    to_record,
)
from backend.contracts.errors import ContractViolation
from backend.platform.context import ExecutionContext
from backend.platform.storage import MissingExecutionContext

REVISION = "a1b2c3d4e5f6"
RADIUS = ("backend/contexts/implementation_record/**",)


@pytest.fixture
def context() -> ExecutionContext:
    return ExecutionContext.platform_internal(
        reason="implementation-record-tests", component="tests", source="pytest"
    )


@pytest.fixture
def tenant_context() -> ExecutionContext:
    from backend.platform.context.identity import IdentityContext

    return ExecutionContext.for_tenant(
        tenant_id="tenant-a", identity=IdentityContext.platform("tests"), source="pytest"
    )


@pytest.fixture
def repository() -> InMemoryImplementationRepository:
    return InMemoryImplementationRepository()


@pytest.fixture
def service(repository) -> ImplementationRecordService:
    return ImplementationRecordService(repository=repository)


def _start(**overrides) -> StartImplementation:
    fields = dict(
        work_id="WO-1",
        context_bundle_id="CB-1",
        revision=REVISION,
        blast_radius_allowed=RADIUS,
        adr_references=("ADR-023",),
    )
    fields.update(overrides)
    return StartImplementation(**fields)


def _submittable(service, context, **overrides) -> str:
    """Drive a record to the point the policy accepts it."""
    record_id = str(service.start(context, _start(**overrides)).record.implementation_id)
    service.record_file(
        context,
        RecordFile(
            implementation_id=record_id,
            path="backend/contexts/implementation_record/domain/record.py",
            kind="added",
            lines_added=617,
        ),
    )
    service.add_claim(
        context,
        AddClaim(
            implementation_id=record_id,
            statement="the record refuses every mutation once completed",
            claim_type="behaviour",
            evidence=("EV-1",),
        ),
    )
    service.record_tests(
        context,
        RecordTests(
            implementation_id=record_id,
            command="python -m pytest tests/contexts/implementation_record -q",
            status="passed",
            passed=98,
        ),
    )
    return record_id


# ----------------------------------------------------------------------
# Record creation
# ----------------------------------------------------------------------


def test_starting_a_record_binds_the_four_references_and_emits_one_event(
    service, context
) -> None:
    result = service.start(context, _start())
    assert result.record.status is ImplementationStatus.IN_PROGRESS
    assert result.record.work_id == "WO-1"
    assert result.record.context_bundle_id == "CB-1"
    assert result.record.revision == REVISION
    assert result.event_types == ("engineering.implementation.started",)


def test_a_start_command_with_an_empty_radius_is_refused_before_the_service() -> None:
    """Refused at the command, so no code path reaches the service with one."""
    with pytest.raises(ContractViolation, match="authorises nothing"):
        _start(blast_radius_allowed=())


def test_a_start_command_without_a_revision_is_refused() -> None:
    """The same paths against a different commit describe a different change."""
    with pytest.raises(ContractViolation, match="revision is required"):
        _start(revision="   ")


def test_two_rounds_for_one_workorder_coexist(service, context) -> None:
    first = service.start(context, _start(round=1)).record
    second = service.start(context, _start(round=2)).record
    found = service.list(context, ListImplementations(work_id="WO-1"))
    assert {r.round for r in found} == {1, 2}
    assert first.implementation_id != second.implementation_id


def test_saving_the_same_record_twice_is_refused(repository, context) -> None:
    from backend.contexts.implementation_record.domain.factory import start_implementation

    record = start_implementation(
        work_id="WO-1", context_bundle_id="CB-1", revision=REVISION, blast_radius=RADIUS
    )
    repository.save(context, record)
    with pytest.raises(DuplicateRecord):
        repository.save(context, record)


# ----------------------------------------------------------------------
# File tracking and blast radius
# ----------------------------------------------------------------------


def test_recording_a_file_accumulates_the_change_set(service, context) -> None:
    record_id = str(service.start(context, _start()).record.implementation_id)
    for name, added in (("a.py", 10), ("b.py", 5)):
        service.record_file(
            context,
            RecordFile(
                implementation_id=record_id,
                path=f"backend/contexts/implementation_record/{name}",
                kind="added",
                lines_added=added,
            ),
        )
    record = service.get(context, GetImplementation(implementation_id=record_id))
    assert record.changes.lines_added == 15
    assert len(record.changes.files) == 2


def test_a_file_outside_the_radius_is_refused_by_the_service(service, context) -> None:
    record_id = str(service.start(context, _start()).record.implementation_id)
    with pytest.raises(OutsideBlastRadius):
        service.record_file(
            context,
            RecordFile(implementation_id=record_id, path="frontend/app/page.tsx"),
        )


def test_a_refused_file_is_not_persisted(service, context) -> None:
    """A refusal that half-applied would leave the store holding a change the
    domain says cannot exist."""
    record_id = str(service.start(context, _start()).record.implementation_id)
    with pytest.raises(OutsideBlastRadius):
        service.record_file(
            context,
            RecordFile(implementation_id=record_id, path="frontend/app/page.tsx"),
        )
    reloaded = service.get(context, GetImplementation(implementation_id=record_id))
    assert reloaded.changes.is_empty


# ----------------------------------------------------------------------
# Completion
# ----------------------------------------------------------------------


def test_completion_reports_every_failure_at_once(service, context) -> None:
    record_id = str(
        service.start(context, _start(expected_assumptions=("A1",))).record.implementation_id
    )
    with pytest.raises(IncompleteRecord) as caught:
        service.complete(context, CompleteImplementation(implementation_id=record_id))
    rules = {f.rule for f in caught.value.failures}
    assert {
        "C1-something-changed",
        "C3-assumptions-resolved",
        "C5-at-least-one-claim",
        "C6-tests-run",
    } <= rules


def test_evaluate_reports_the_same_failures_without_completing(service, context) -> None:
    """What an implementer checks before submitting."""
    record_id = str(service.start(context, _start()).record.implementation_id)
    report = service.evaluate(context, record_id)
    assert not report.may_complete
    still_open = service.get(context, GetImplementation(implementation_id=record_id))
    assert still_open.status is ImplementationStatus.IN_PROGRESS


def test_completion_seals_the_record_and_emits_the_digest(service, context) -> None:
    record_id = _submittable(service, context)
    result = service.complete(context, CompleteImplementation(implementation_id=record_id))
    assert result.record.status is ImplementationStatus.COMPLETED
    assert result.record.digest
    assert result.event_types == (
        "engineering.implementation.digest_computed",
        "engineering.implementation.completed",
    )
    result.record.verify_digest()


def test_a_completed_record_refuses_further_recording_through_the_service(
    service, context
) -> None:
    record_id = _submittable(service, context)
    service.complete(context, CompleteImplementation(implementation_id=record_id))
    with pytest.raises(RecordCompleted):
        service.note_deviation(
            context, NoteDeviation(implementation_id=record_id, deviation="late")
        )


def test_abandoning_records_why(service, context) -> None:
    record_id = str(service.start(context, _start()).record.implementation_id)
    result = service.abandon(
        context,
        AbandonImplementation(
            implementation_id=record_id, reason="the WorkOrder's premise was false"
        ),
    )
    assert result.record.status is ImplementationStatus.ABANDONED
    assert result.record.closing_note == "the WorkOrder's premise was false"


# ----------------------------------------------------------------------
# Which record Review and Verification consume
# ----------------------------------------------------------------------


def test_completed_for_ignores_a_record_still_in_progress(service, context) -> None:
    """An in-progress record is work in flight, not an artifact."""
    _submittable(service, context)
    assert service.completed_for(context, "WO-1") is None


def test_completed_for_returns_the_latest_completed_round(service, context) -> None:
    first = _submittable(service, context, round=1)
    service.complete(context, CompleteImplementation(implementation_id=first))
    second = _submittable(service, context, round=2)
    service.complete(context, CompleteImplementation(implementation_id=second))

    latest = service.completed_for(context, "WO-1")
    assert latest is not None and latest.round == 2
    assert str(service.completed_for(context, "WO-1", round=1).implementation_id) == first


def test_current_for_skips_a_superseded_round(service, context) -> None:
    first = _submittable(service, context, round=1)
    service.complete(context, CompleteImplementation(implementation_id=first))
    second = _submittable(service, context, round=2)
    service.supersede(
        context,
        SupersedeImplementation(implementation_id=first, successor_id=second),
    )
    current = service.current_for(context, "WO-1")
    assert str(current.implementation_id) == second


def test_superseding_leaves_the_digest_verifiable(service, context) -> None:
    first = _submittable(service, context, round=1)
    sealed = service.complete(
        context, CompleteImplementation(implementation_id=first)
    ).record
    second = _submittable(service, context, round=2)
    result = service.supersede(
        context, SupersedeImplementation(implementation_id=first, successor_id=second)
    )
    assert result.record.digest == sealed.digest
    result.record.verify_digest()


# ----------------------------------------------------------------------
# Assumptions, risks, coverage through the service
# ----------------------------------------------------------------------


def test_resolving_every_assumption_unblocks_completion(service, context) -> None:
    record_id = _submittable(service, context, expected_assumptions=("A1",))
    assert not service.evaluate(context, record_id).may_complete
    service.resolve_assumption(
        context,
        ResolveAssumption(
            implementation_id=record_id,
            assumption_id="A1",
            statement="the guard is applied at every repository",
            outcome="confirmed",
            evidence=("EV-2",),
        ),
    )
    assert service.evaluate(context, record_id).may_complete


def test_a_medium_risk_without_mitigation_is_refused_by_the_service(
    service, context
) -> None:
    record_id = _submittable(service, context)
    with pytest.raises(ContractViolation, match="must state its mitigation"):
        service.declare_risk(
            context,
            DeclareRisk(
                implementation_id=record_id,
                statement="the matcher is duplicated",
                level="medium",
            ),
        )


def test_a_mitigated_risk_does_not_block(service, context) -> None:
    record_id = _submittable(service, context)
    service.declare_risk(
        context,
        DeclareRisk(
            implementation_id=record_id,
            statement="the blast-radius matcher is duplicated from the WorkOrder context",
            level="medium",
            mitigation="test_paths.py runs both over a shared corpus and asserts agreement",
        ),
    )
    assert service.evaluate(context, record_id).may_complete


def test_coverage_is_recorded_once_per_criterion(service, context) -> None:
    record_id = _submittable(service, context)
    service.record_coverage(
        context,
        RecordCoverage(
            implementation_id=record_id,
            criterion="records are immutable after completion",
            covering_tests=("test_domain.py::test_every_mutation_refuses",),
        ),
    )
    with pytest.raises(ContractViolation, match="already has a coverage entry"):
        service.record_coverage(
            context,
            RecordCoverage(
                implementation_id=record_id,
                criterion="records are immutable after completion",
                covering_tests=("another_test",),
            ),
        )


def test_a_failing_build_blocks_and_is_reported(service, context) -> None:
    record_id = _submittable(service, context)
    service.record_build(
        context,
        RecordBuild(
            implementation_id=record_id,
            name="architecture gate",
            command="python -m backend.platform.architecture",
            status="failed",
            detail="TENANT-REPOSITORY-CONTEXT",
        ),
    )
    report = service.evaluate(context, record_id)
    assert not report.may_complete
    assert any(f.rule == "C7-builds-green" for f in report.blocking)


def test_an_unknown_record_is_reported_as_missing(service, context) -> None:
    with pytest.raises(RecordNotFound):
        service.get(context, GetImplementation(implementation_id="01KZ000000000000000000000A"))


# ----------------------------------------------------------------------
# Storage boundary (PR-10)
# ----------------------------------------------------------------------


def test_every_repository_method_requires_an_execution_context(repository) -> None:
    from backend.contexts.implementation_record.domain.factory import start_implementation
    from backend.contexts.implementation_record.domain.identifiers import ImplementationId

    record = start_implementation(
        work_id="WO-1", context_bundle_id="CB-1", revision=REVISION, blast_radius=RADIUS
    )
    calls = (
        lambda: repository.save(None, record),
        lambda: repository.replace(None, record),
        lambda: repository.find(None, ImplementationId.new()),
        lambda: repository.for_work_order(None, "WO-1"),
        lambda: repository.all(None),
        lambda: repository.clear(None),
    )
    for call in calls:
        with pytest.raises(MissingExecutionContext):
            call()


def test_a_tenant_cannot_see_another_tenants_record(
    repository, tenant_context, context
) -> None:
    from backend.platform.context.identity import IdentityContext
    from backend.contexts.implementation_record.domain.factory import start_implementation

    record = start_implementation(
        work_id="WO-1", context_bundle_id="CB-1", revision=REVISION, blast_radius=RADIUS
    )
    repository.save(tenant_context, record)

    other = ExecutionContext.for_tenant(
        tenant_id="tenant-b", identity=IdentityContext.platform("tests"), source="pytest"
    )
    assert repository.find(other, record.implementation_id) is None
    assert repository.all(other) == ()
    assert len(repository.all(tenant_context)) == 1


def test_the_repository_is_not_grandfathered() -> None:
    from backend.platform.architecture.tenancy_rules import GRANDFATHERED_REPOSITORIES

    for name in ("ImplementationRepository", "InMemoryImplementationRepository"):
        assert name not in GRANDFATHERED_REPOSITORIES


# ----------------------------------------------------------------------
# Persistence and replay
# ----------------------------------------------------------------------


def test_a_record_survives_the_round_trip_unchanged(service, context) -> None:
    record_id = _submittable(service, context, expected_assumptions=("A1",))
    service.resolve_assumption(
        context,
        ResolveAssumption(
            implementation_id=record_id,
            assumption_id="A1",
            statement="holds",
            outcome="confirmed",
            evidence=("EV-2",),
        ),
    )
    service.declare_risk(
        context,
        DeclareRisk(
            implementation_id=record_id,
            statement="log volume rises",
            level="low",
        ),
    )
    service.record_coverage(
        context,
        RecordCoverage(
            implementation_id=record_id, criterion="C1", covering_tests=("t",)
        ),
    )
    service.note_deviation(
        context, NoteDeviation(implementation_id=record_id, deviation="matcher duplicated")
    )
    sealed = service.complete(
        context, CompleteImplementation(implementation_id=record_id)
    ).record

    stored = to_record(sealed, tenant_id="tenant-a")
    restored = from_record(stored)

    assert restored == sealed
    restored.verify_digest()


def test_the_digest_is_restored_not_recomputed() -> None:
    """A digest recomputed on load always matches, which makes the check useless.

    This is the one artifact where that check is the whole point: it is how a
    reviewer knows the record under review is the one that was submitted.
    """
    source = pathlib.Path(
        "backend/contexts/implementation_record/infrastructure/persistence.py"
    ).read_text(encoding="utf-8")
    tree = ast.parse(source)
    from_record_fn = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "from_record"
    )
    calls = {
        node.func.attr
        for node in ast.walk(from_record_fn)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert "compute_digest" not in calls
    assert "complete" not in calls


def test_a_tampered_stored_record_fails_verification() -> None:
    """The whole reason the digest is restored rather than recomputed."""
    from backend.contexts.implementation_record.domain.factory import (
        changed,
        claim,
        start_implementation,
        test_run,
    )
    from backend.contexts.implementation_record.domain.claims import ClaimType

    record = start_implementation(
        work_id="WO-1", context_bundle_id="CB-1", revision=REVISION, blast_radius=RADIUS
    )
    record = record.record_file(
        changed("backend/contexts/implementation_record/a.py", added=1)
    )
    record = record.add_claim(claim("it holds", ClaimType.BEHAVIOUR, ["EV-1"]))
    record = record.record_tests(test_run("pytest", REVISION, passed=1))
    sealed = record.complete()

    stored = to_record(sealed, tenant_id="tenant-a")
    stored["claims"][0]["statement"] = "it holds, and also does something else"

    from backend.contexts.implementation_record.domain.errors import DigestMismatch

    with pytest.raises(DigestMismatch):
        from_record(stored).verify_digest()


def test_a_record_from_an_unknown_schema_version_is_refused() -> None:
    """Refusing to guess at a shape this build does not know."""
    from backend.contexts.implementation_record.domain.factory import start_implementation

    stored = to_record(
        start_implementation(
            work_id="WO-1",
            context_bundle_id="CB-1",
            revision=REVISION,
            blast_radius=RADIUS,
        ),
        tenant_id="tenant-a",
    )
    stored["schema_version"] = RECORD_SCHEMA_VERSION + 1
    with pytest.raises(ContractViolation, match="schema version"):
        from_record(stored)


def test_a_record_stored_without_a_tenant_is_refused() -> None:
    from backend.contexts.implementation_record.domain.factory import start_implementation

    with pytest.raises(ContractViolation, match="tenant_id must be non-blank"):
        to_record(
            start_implementation(
                work_id="WO-1",
                context_bundle_id="CB-1",
                revision=REVISION,
                blast_radius=RADIUS,
            ),
            tenant_id="   ",
        )


# ----------------------------------------------------------------------
# Concurrency
# ----------------------------------------------------------------------


def test_concurrent_starts_all_persist(service, context) -> None:
    """A dictionary mutated from two threads loses writes silently."""
    errors: list = []

    def start(index: int) -> None:
        try:
            service.start(context, _start(work_id=f"WO-{index}"))
        except Exception as exc:  # pragma: no cover - only on failure
            errors.append(exc)

    threads = [threading.Thread(target=start, args=(i,)) for i in range(24)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == []
    assert len(service.list(context, ListImplementations())) == 24


def test_concurrent_reads_during_writes_do_not_tear(service, context) -> None:
    for index in range(8):
        service.start(context, _start(work_id=f"WO-{index}"))

    seen: list = []
    errors: list = []

    def read() -> None:
        try:
            for _ in range(20):
                seen.append(len(service.list(context, ListImplementations())))
        except Exception as exc:  # pragma: no cover - only on failure
            errors.append(exc)

    def write(index: int) -> None:
        try:
            service.start(context, _start(work_id=f"WO-late-{index}"))
        except Exception as exc:  # pragma: no cover - only on failure
            errors.append(exc)

    threads = [threading.Thread(target=read) for _ in range(4)]
    threads += [threading.Thread(target=write, args=(i,)) for i in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == []
    assert all(8 <= count <= 16 for count in seen), seen


# ----------------------------------------------------------------------
# API
# ----------------------------------------------------------------------


@pytest.fixture
def client(monkeypatch) -> TestClient:
    monkeypatch.setattr(
        routes,
        "_service",
        ImplementationRecordService(repository=InMemoryImplementationRepository()),
    )
    app = FastAPI()
    app.include_router(routes.router)
    return TestClient(app)


BASE = "/api/v1/engineering/implementation"


def _api_start(client, **overrides) -> str:
    payload = {
        "work_id": "WO-1",
        "context_bundle_id": "CB-1",
        "revision": REVISION,
        "blast_radius_allowed": list(RADIUS),
        "adr_references": ["ADR-023"],
    }
    payload.update(overrides)
    response = client.post(BASE, json=payload)
    assert response.status_code == 201, response.text
    return response.json()["implementation"]["implementation_id"]


def test_the_api_creates_and_fetches_a_record(client) -> None:
    record_id = _api_start(client)
    fetched = client.get(f"{BASE}/{record_id}")
    assert fetched.status_code == 200
    assert fetched.json()["work_id"] == "WO-1"
    assert fetched.json()["status"] == "in_progress"


def test_the_structured_refusal_body_does_not_survive_the_real_app(client) -> None:
    """A limitation this suite cannot catch on its own, pinned so it is not lost.

    ``TestClient`` over a bare ``FastAPI()`` installs none of the application's
    exception handlers, so the body asserted by the test below is the body this
    module *sends* -- not the body a deployed client *receives*. The real app's
    ``http_exception_handler`` discards ``exc.detail`` and substitutes a canned
    message per status code.

    Verified by running the server: a path outside the blast radius comes back as
    ``{"code": "UNPROCESSABLE_ENTITY", "message": "The request body failed
    validation."}``. Pre-existing and app-wide -- PR-E1's and PR-E4's routes lose
    their details the same way -- so it is recorded (ADR-023 remaining risk 8)
    rather than fixed here.

    This test asserts the handler is still the one with that behaviour, so that
    when someone fixes it, this fails and the ADR gets corrected with it.
    """
    import inspect

    from backend.core import exception_handlers

    source = inspect.getsource(exception_handlers)
    assert "return http_error_response(request, exc.status_code)" in source, (
        "the global HTTP exception handler changed; if it now forwards "
        "exc.detail, ADR-023 remaining risk 8 is stale and should be removed"
    )


def test_the_api_refuses_a_file_outside_the_radius_with_the_reason(client) -> None:
    """A client told only "refused" has to guess which of two responses to take.

    Asserts what this module sends. See the test above for what the deployed
    application actually delivers.
    """
    record_id = _api_start(client)
    response = client.post(
        f"{BASE}/{record_id}/files", json={"path": "frontend/app/page.tsx"}
    )
    assert response.status_code == 422
    body = response.json()["detail"]
    assert body["error"] == "outside_blast_radius"
    assert body["path"] == "frontend/app/page.tsx"
    assert "outside the declared blast radius" in body["reason"]


def test_the_api_refuses_a_claim_with_no_evidence(client) -> None:
    record_id = _api_start(client)
    response = client.post(
        f"{BASE}/{record_id}/claims", json={"statement": "it works", "evidence": []}
    )
    assert response.status_code == 422  # rejected by the request schema


def test_the_api_reports_every_completion_failure(client) -> None:
    record_id = _api_start(client)
    response = client.post(f"{BASE}/{record_id}/complete")
    assert response.status_code == 422
    body = response.json()["detail"]
    assert body["error"] == "incomplete_record"
    assert {f["rule"] for f in body["failures"]} >= {
        "C1-something-changed",
        "C5-at-least-one-claim",
        "C6-tests-run",
    }


def test_the_policy_endpoint_reports_without_completing(client) -> None:
    record_id = _api_start(client)
    response = client.get(f"{BASE}/{record_id}/policy")
    assert response.status_code == 200
    assert response.json()["may_complete"] is False
    assert client.get(f"{BASE}/{record_id}").json()["status"] == "in_progress"


def test_the_api_completes_a_full_record(client) -> None:
    record_id = _api_start(client)
    client.post(
        f"{BASE}/{record_id}/files",
        json={
            "path": "backend/contexts/implementation_record/domain/record.py",
            "kind": "added",
            "lines_added": 617,
        },
    )
    client.post(
        f"{BASE}/{record_id}/claims",
        json={
            "statement": "the record is immutable after completion",
            "claim_type": "behaviour",
            "evidence": ["EV-1"],
        },
    )
    client.post(
        f"{BASE}/{record_id}/tests",
        json={"command": "pytest -q", "status": "passed", "passed": 98},
    )
    response = client.post(f"{BASE}/{record_id}/complete")
    assert response.status_code == 200, response.text
    body = response.json()["implementation"]
    assert body["status"] == "completed"
    assert body["digest"]


def test_the_api_returns_409_when_the_record_is_already_complete(client) -> None:
    record_id = _api_start(client)
    client.post(
        f"{BASE}/{record_id}/files",
        json={"path": "backend/contexts/implementation_record/a.py", "kind": "added"},
    )
    client.post(
        f"{BASE}/{record_id}/claims",
        json={"statement": "it holds", "evidence": ["EV-1"]},
    )
    client.post(f"{BASE}/{record_id}/tests", json={"command": "pytest", "passed": 1})
    assert client.post(f"{BASE}/{record_id}/complete").status_code == 200

    late = client.post(
        f"{BASE}/{record_id}/deviations", json={"deviation": "one more thing"}
    )
    assert late.status_code == 409


def test_the_api_returns_404_for_an_unknown_record(client) -> None:
    assert client.get(f"{BASE}/01KZ000000000000000000000A").status_code == 404


def test_the_api_lists_and_filters(client) -> None:
    _api_start(client, work_id="WO-1")
    _api_start(client, work_id="WO-2")
    assert client.get(BASE).json()["count"] == 2
    assert client.get(BASE, params={"work_id": "WO-1"}).json()["count"] == 1
    assert client.get(BASE, params={"status": "completed"}).json()["count"] == 0


def test_the_api_refuses_an_assumption_the_workorder_never_declared(client) -> None:
    record_id = _api_start(client, expected_assumptions=["A1"])
    response = client.post(
        f"{BASE}/{record_id}/assumptions",
        json={
            "assumption_id": "A2",
            "statement": "invented",
            "outcome": "confirmed",
            "evidence": ["EV-1"],
        },
    )
    assert response.status_code == 404


def test_the_api_surfaces_unresolved_assumptions(client) -> None:
    record_id = _api_start(client, expected_assumptions=["A1", "A2"])
    client.post(
        f"{BASE}/{record_id}/assumptions",
        json={
            "assumption_id": "A1",
            "statement": "holds",
            "outcome": "confirmed",
            "evidence": ["EV-1"],
        },
    )
    body = client.get(f"{BASE}/{record_id}").json()
    assert body["unresolved_assumptions"] == ["A2"]


# ----------------------------------------------------------------------
# The runtime wiring -- what this PR actually closes
# ----------------------------------------------------------------------


def _drive_to_implementation(stack, ctx):
    """Draft, approve, and walk a WorkOrder as far as the lifecycle allows.

    **As far as ``implementation``, and no further.** ``implementation ->
    verification`` is refused by the runtime -- skipping review would leave the
    party that must reproduce claims as the only adversarial read -- and the
    Review context does not exist. So the verification *request* path is
    exercised through the adapter directly, which is what the runtime calls
    anyway. Pretending the lifecycle reached verification would be testing a
    path that does not exist.
    """
    from backend.contexts.workorder import (
        ApproveWorkOrder,
        BlastRadius,
        DraftWorkOrder,
    )

    drafted = stack.work_order_service.draft(
        ctx,
        DraftWorkOrder(
            intent="A stated outcome",
            acceptance_criteria=("something is refused",),
            blast_radius=BlastRadius.of(list(RADIUS)),
            adr_references=("ADR-023",),
            evidence=("EV-1",),
            constraints=("I6",),
        ),
    )
    work_id = str(drafted.work_order.work_id)
    stack.work_order_service.approve(
        ctx, ApproveWorkOrder(work_id=work_id, approved_by="founder")
    )
    for phase in ("assigned", "spec_tests", "implementation"):
        stack.runtime.transition(ctx, work_id, phase, actor="orchestrator")
    return work_id


def _latest_verification(stack, ctx, work_id, verification_id):
    from backend.contexts.engineering_verification import ListVerifications

    return next(
        r
        for r in stack.verification_service.list(ctx, ListVerifications(work_id=work_id))
        if str(r.verification_id) == verification_id
    )


@pytest.fixture
def stack():
    from backend.contexts.workorder import (
        InMemoryWorkOrderRepository,
        StaticReferenceResolver,
        WorkOrderService,
    )

    return build_engineering_runtime(
        service=WorkOrderService(
            repository=InMemoryWorkOrderRepository(),
            resolver=StaticReferenceResolver(
                known_adrs=frozenset({"ADR-023"}),
                known_evidence=frozenset({"EV-1"}),
                enforceable_constraints=frozenset({"I6"}),
            ),
        )
    )


def test_the_runtime_wires_the_implementation_record_service(stack) -> None:
    assert stack.implementation_service is not None
    assert stack.verification_adapter is not None


def test_verification_is_still_unreachable_through_the_lifecycle(stack, context) -> None:
    """Stated rather than worked around.

    This PR does not make ``implementation -> verification`` legal, and no test
    here should imply it did. The runtime refuses the move because skipping
    review would leave the party that must reproduce claims as the only
    adversarial read -- and Review does not exist.
    """
    from backend.contexts.engineering.errors import IllegalTransition

    work_id = _drive_to_implementation(stack, context)
    with pytest.raises(IllegalTransition, match="skipping review"):
        stack.runtime.transition(context, work_id, "verification", actor="orchestrator")


def test_verification_receives_the_implementers_real_claims(stack, context) -> None:
    """The claim this PR rests on, and ADR-021's named remaining risk.

    Before this wiring, Verification received one placeholder claim stating that
    the WorkOrder reached the phase legitimately -- true, and not what anyone
    wanted verified.
    """
    work_id = _drive_to_implementation(stack, context)

    record_id = _submittable(stack.implementation_service, context, work_id=work_id)
    stack.implementation_service.add_claim(
        context,
        AddClaim(
            implementation_id=record_id,
            statement="the blast-radius matcher agrees with the WorkOrder context",
            claim_type="equivalence",
            evidence=("EV-2",),
        ),
    )
    stack.implementation_service.complete(
        context, CompleteImplementation(implementation_id=record_id)
    )

    verification_id = stack.verification_adapter.request(context, work_id, attempt=1)
    latest = _latest_verification(stack, context, work_id, verification_id)

    statements = {c.statement for c in latest.request.claims}
    assert "the record refuses every mutation once completed" in statements
    assert "the blast-radius matcher agrees with the WorkOrder context" in statements
    assert not any("through legal transitions" in s for s in statements)


def test_the_verification_request_is_anchored_to_the_real_revision(
    stack, context
) -> None:
    """``unrecorded`` gave Verification's staleness check nothing to compare."""
    work_id = _drive_to_implementation(stack, context)
    record_id = _submittable(stack.implementation_service, context, work_id=work_id)
    stack.implementation_service.complete(
        context, CompleteImplementation(implementation_id=record_id)
    )

    verification_id = stack.verification_adapter.request(context, work_id, attempt=1)
    latest = _latest_verification(stack, context, work_id, verification_id)
    assert latest.base_commit == REVISION


def test_the_implementers_evidence_travels_across_as_asserted_not_verified(
    stack, context
) -> None:
    """Carrying the references gives the verifier somewhere to start, not a
    reason to believe. There is no conversion to ``VerifiedEvidence`` (ADR-021).
    """
    work_id = _drive_to_implementation(stack, context)
    record_id = _submittable(stack.implementation_service, context, work_id=work_id)
    stack.implementation_service.complete(
        context, CompleteImplementation(implementation_id=record_id)
    )
    verification_id = stack.verification_adapter.request(context, work_id, attempt=1)
    latest = _latest_verification(stack, context, work_id, verification_id)

    claim = next(iter(latest.request.claims))
    assert {str(e) for e in claim.asserted_evidence} == {"EV-1"}
    # Nothing is verified by having been asserted: the record carries no results.
    assert latest.results == ()


def test_an_in_progress_record_does_not_reach_verification(stack, context) -> None:
    """Only ``COMPLETED`` is submittable; the placeholder holds until then."""
    work_id = _drive_to_implementation(stack, context)
    _submittable(stack.implementation_service, context, work_id=work_id)  # not completed

    verification_id = stack.verification_adapter.request(context, work_id, attempt=1)
    latest = _latest_verification(stack, context, work_id, verification_id)
    statements = {c.statement for c in latest.request.claims}
    assert any("through legal transitions" in s for s in statements)
    assert latest.base_commit == "unrecorded"


def test_the_placeholder_remains_when_no_record_exists(stack, context) -> None:
    """Deliberate, not an oversight.

    A WorkOrder can reach verification without an ImplementationRecord, and the
    domain refuses a verification with no claims at all.
    """
    work_id = _drive_to_implementation(stack, context)
    verification_id = stack.verification_adapter.request(context, work_id, attempt=1)
    latest = _latest_verification(stack, context, work_id, verification_id)
    assert any("through legal transitions" in c.statement for c in latest.request.claims)


def test_an_abandoned_record_does_not_reach_verification(stack, context) -> None:
    """Abandoned is not submittable either, and the placeholder is what remains."""
    work_id = _drive_to_implementation(stack, context)
    record_id = _submittable(stack.implementation_service, context, work_id=work_id)
    stack.implementation_service.abandon(
        context,
        AbandonImplementation(implementation_id=record_id, reason="premise was false"),
    )
    verification_id = stack.verification_adapter.request(context, work_id, attempt=1)
    latest = _latest_verification(stack, context, work_id, verification_id)
    assert any("through legal transitions" in c.statement for c in latest.request.claims)


def test_the_previous_behaviour_is_still_testable(context) -> None:
    """A test asserting the placeholder path needs a way to unwire the source."""
    from backend.contexts.workorder import (
        InMemoryWorkOrderRepository,
        StaticReferenceResolver,
        WorkOrderService,
    )

    unwired = build_engineering_runtime(
        service=WorkOrderService(
            repository=InMemoryWorkOrderRepository(),
            resolver=StaticReferenceResolver(
                known_adrs=frozenset({"ADR-023"}),
                known_evidence=frozenset({"EV-1"}),
                enforceable_constraints=frozenset({"I6"}),
            ),
        ),
        wire_implementation=False,
    )
    assert unwired.implementation_service is None

    work_id = _drive_to_implementation(unwired, context)
    verification_id = unwired.verification_adapter.request(context, work_id, attempt=1)
    latest = _latest_verification(unwired, context, work_id, verification_id)
    assert any("through legal transitions" in c.statement for c in latest.request.claims)


def test_the_claim_source_reports_nothing_rather_than_guessing(context) -> None:
    source = ImplementationClaimSource(
        ImplementationRecordService(repository=InMemoryImplementationRepository())
    )
    assert source.claims_for(context, "WO-nothing") is None


# ----------------------------------------------------------------------
# Architecture compliance
# ----------------------------------------------------------------------


def _imports(path: pathlib.Path) -> set:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                found.add(alias.name)
    return found


def _modules() -> list:
    root = pathlib.Path("backend/contexts/implementation_record")
    return [p for p in root.rglob("*.py") if "__pycache__" not in p.parts]


def test_the_context_imports_only_contracts_and_platform() -> None:
    permitted = (
        "backend.contracts",
        "backend.platform",
        "backend.contexts.implementation_record",
    )
    offences = [
        f"{path}: {imported}"
        for path in _modules()
        for imported in _imports(path)
        if imported.startswith("backend.") and not imported.startswith(permitted)
    ]
    assert offences == [], offences


def test_the_context_imports_no_other_bounded_context() -> None:
    """S2: contexts communicate by published contract only.

    The two duplications this PR makes -- the blast-radius matcher and the claim
    vocabulary -- exist *because* of this rule, and are covered by drift tests
    rather than by an import.
    """
    offences = [
        f"{path}: {imported}"
        for path in _modules()
        for imported in _imports(path)
        if imported.startswith("backend.contexts.")
        and not imported.startswith("backend.contexts.implementation_record")
    ]
    assert offences == [], offences


def test_the_domain_layer_does_no_io() -> None:
    banned = {"pathlib", "os", "socket", "requests", "httpx", "sqlite3", "json"}
    root = pathlib.Path("backend/contexts/implementation_record/domain")
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

    ours = {e.EVENT_TYPE for e in IMPLEMENTATION_EVENT_TYPES}
    assert all(e.startswith("engineering.implementation.") for e in ours)
    for other in (CONTEXT_EVENT_TYPES, RUNTIME_EVENT_TYPES, VERIFICATION_EVENT_TYPES):
        assert ours.isdisjoint({e.EVENT_TYPE for e in other})


def test_the_composition_root_is_the_only_module_importing_two_contexts() -> None:
    """The one place the join is legal, and where it belongs.

    Wiring ImplementationRecord to Verification could have gone inside either
    context. Both would have been an S2 violation.
    """
    root = pathlib.Path("backend/api")
    offenders = []
    for path in root.rglob("*.py"):
        if "__pycache__" in path.parts or path.name in (
            # Superseded (Phase 6.2, documenting Phase 5): "the composition
            # root" became composition rootS — each of these is a named,
            # ADR-recorded root that must import two contexts to compose them
            # (ADR-030 workflow→execution handoff, ADR-035 binding projection,
            # ADR-044/057 durable + application composition). Route modules
            # still may not.
            "engineering_composition.py",
            "application_runtime.py",
            "capability_execution_composition.py",
            "durability_composition.py",
            "mission_control_composition.py",
        ):
            continue
        contexts = {
            imported.split(".")[2]
            for imported in _imports(path)
            if imported.startswith("backend.contexts.")
            and len(imported.split(".")) > 2
        }
        if len(contexts) > 1:
            offenders.append(f"{path}: {sorted(contexts)}")
    assert offenders == [], offenders
