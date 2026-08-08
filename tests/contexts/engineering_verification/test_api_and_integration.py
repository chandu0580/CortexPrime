"""The REST API, the runtime wiring, and architecture compliance.

The integration section pins the claim that shapes this PR: wiring Verification
unblocks two transitions and does **not** unblock the path to them, because the
context and review ports are still missing.
"""

from __future__ import annotations

import ast
import pathlib

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api import engineering_verification_routes as routes
from backend.api.engineering_composition import (
    VerificationServiceAdapter,
    build_engineering_runtime,
)
from backend.contexts.engineering import (
    CollaboratorUnavailable,
    GetLifecycleCapability,
    VerificationPort,
    WorkOrderPhase,
)
from backend.contexts.engineering_verification import (
    InMemoryVerificationRepository,
    VerificationService,
)
from backend.platform.context import ExecutionContext

BASE = "abc123def456"


@pytest.fixture
def client(monkeypatch) -> TestClient:
    """A fresh service per test, so records do not leak between them."""
    monkeypatch.setattr(
        routes, "_service", VerificationService(repository=InMemoryVerificationRepository())
    )
    app = FastAPI()
    app.include_router(routes.router)
    return TestClient(app)


def _request_body(**overrides) -> dict:
    body = {
        "work_id": "WO-1",
        "base_commit": BASE,
        "claims": [{"statement": "a read with no context is refused", "claim_type": "behaviour"}],
    }
    body.update(overrides)
    return body


def _created(client) -> dict:
    return client.post("/api/v1/engineering/verification", json=_request_body()).json()


# ----------------------------------------------------------------------
# API
# ----------------------------------------------------------------------


def test_request_returns_201(client):
    response = client.post("/api/v1/engineering/verification", json=_request_body())
    assert response.status_code == 201
    body = response.json()
    assert body["verification"]["status"] == "requested"
    assert body["events"] == ["engineering.verification.requested"]


def test_a_request_with_no_claims_is_422_from_the_schema(client):
    response = client.post("/api/v1/engineering/verification", json=_request_body(claims=[]))
    assert response.status_code == 422


def test_a_request_without_a_base_commit_is_422(client):
    body = _request_body()
    del body["base_commit"]
    assert client.post("/api/v1/engineering/verification", json=body).status_code == 422


def test_results_before_starting_are_409(client):
    created = _created(client)
    vid = created["verification"]["verification_id"]
    claim_id = created["verification"]["claims"][0]["claim_id"]

    response = client.post(
        f"/api/v1/engineering/verification/{vid}/results",
        json={
            "claim_id": claim_id, "verdict": "reproduced", "observed": "held",
            "specification": "ran it", "evidence_summary": "ran it and it held",
        },
    )
    assert response.status_code == 409


def test_a_full_successful_verification(client):
    created = _created(client)
    vid = created["verification"]["verification_id"]
    claim_id = created["verification"]["claims"][0]["claim_id"]

    client.post(f"/api/v1/engineering/verification/{vid}/start", json={"verifier": "verifier-1"})
    client.post(
        f"/api/v1/engineering/verification/{vid}/results",
        json={
            "claim_id": claim_id, "verdict": "reproduced", "observed": "raised as expected",
            "specification": "called authorize(READ, None)",
            "evidence_summary": "MissingExecutionContext raised",
            "evidence_base_commit": BASE,
        },
    )
    closed = client.post(
        f"/api/v1/engineering/verification/{vid}/close", json={"current_commit": BASE}
    ).json()

    assert closed["verification"]["status"] == "complete"
    assert closed["events"] == ["engineering.verification.succeeded"]


def test_a_failed_verification_reports_failed_not_complete(client):
    created = _created(client)
    vid = created["verification"]["verification_id"]
    claim_id = created["verification"]["claims"][0]["claim_id"]

    client.post(f"/api/v1/engineering/verification/{vid}/start", json={"verifier": "v"})
    client.post(
        f"/api/v1/engineering/verification/{vid}/results",
        json={
            "claim_id": claim_id, "verdict": "contradicted", "observed": "it returned the row",
            "specification": "called authorize(READ, None)",
            "evidence_summary": "no exception was raised", "evidence_base_commit": BASE,
        },
    )
    closed = client.post(
        f"/api/v1/engineering/verification/{vid}/close", json={"current_commit": BASE}
    ).json()

    assert closed["verification"]["status"] == "failed"
    assert closed["events"] == ["engineering.verification.failed"]


def test_missing_evidence_is_refused(client):
    """A verdict with no evidence is an opinion."""
    created = _created(client)
    vid = created["verification"]["verification_id"]
    claim_id = created["verification"]["claims"][0]["claim_id"]
    client.post(f"/api/v1/engineering/verification/{vid}/start", json={"verifier": "v"})

    response = client.post(
        f"/api/v1/engineering/verification/{vid}/results",
        json={
            "claim_id": claim_id, "verdict": "reproduced", "observed": "held",
            "specification": "ran it", "evidence_summary": "",
        },
    )
    assert response.status_code == 400


def test_invalid_evidence_trust_is_rejected_by_the_schema(client):
    """``asserted`` is not offered as an option at the boundary."""
    created = _created(client)
    vid = created["verification"]["verification_id"]
    claim_id = created["verification"]["claims"][0]["claim_id"]
    client.post(f"/api/v1/engineering/verification/{vid}/start", json={"verifier": "v"})

    response = client.post(
        f"/api/v1/engineering/verification/{vid}/results",
        json={
            "claim_id": claim_id, "verdict": "reproduced", "observed": "held",
            "specification": "ran it", "evidence_summary": "ran it",
            "evidence_trust": "asserted",
        },
    )
    assert response.status_code == 422


def test_an_absence_claim_settled_by_a_green_suite_is_409(client):
    created = client.post(
        "/api/v1/engineering/verification",
        json=_request_body(
            claims=[{"statement": "no cross-tenant read is possible", "claim_type": "absence"}]
        ),
    ).json()
    vid = created["verification"]["verification_id"]
    claim_id = created["verification"]["claims"][0]["claim_id"]
    client.post(f"/api/v1/engineering/verification/{vid}/start", json={"verifier": "v"})

    response = client.post(
        f"/api/v1/engineering/verification/{vid}/results",
        json={
            "claim_id": claim_id, "verdict": "reproduced", "observed": "suite green",
            "method": "command_execution", "specification": "pytest tests/ -q",
            "evidence_summary": "312 passed", "evidence_base_commit": BASE,
        },
    )
    assert response.status_code == 409
    assert "adversarial_construction" in response.json()["detail"]


def test_a_result_for_an_unknown_claim_is_404(client):
    from backend.contexts.engineering_verification import ClaimId

    created = _created(client)
    vid = created["verification"]["verification_id"]
    client.post(f"/api/v1/engineering/verification/{vid}/start", json={"verifier": "v"})

    response = client.post(
        f"/api/v1/engineering/verification/{vid}/results",
        json={
            "claim_id": str(ClaimId.new()), "verdict": "reproduced", "observed": "held",
            "specification": "ran it", "evidence_summary": "ran it",
        },
    )
    assert response.status_code == 404


def test_the_policy_endpoint_reports_without_closing(client):
    created = _created(client)
    vid = created["verification"]["verification_id"]
    client.post(f"/api/v1/engineering/verification/{vid}/start", json={"verifier": "v"})

    report = client.get(f"/api/v1/engineering/verification/{vid}/policy").json()
    assert report["may_complete"] is False
    assert report["outcome"] == "incomplete"

    still_open = client.get(f"/api/v1/engineering/verification/{vid}").json()
    assert still_open["status"] == "running"


def test_an_unknown_verification_is_404(client):
    from backend.contexts.engineering_verification import VerificationId

    assert client.get(
        f"/api/v1/engineering/verification/{VerificationId.new()}"
    ).status_code == 404


def test_a_malformed_id_is_400_not_500(client):
    assert client.get("/api/v1/engineering/verification/not-a-ulid").status_code == 400


def test_every_route_is_versioned(client):
    for route in client.app.routes:
        path = getattr(route, "path", "")
        if "verification" in path:
            assert path.startswith("/api/v1/engineering/verification"), path


def test_openapi_documents_every_endpoint(client):
    schema = client.app.openapi()
    paths = [p for p in schema["paths"] if "verification" in p]
    assert len(paths) == 9
    for path in paths:
        for operation in schema["paths"][path].values():
            assert operation.get("summary"), f"{path} has no summary"


# ----------------------------------------------------------------------
# Runtime wiring
# ----------------------------------------------------------------------


def test_the_adapter_satisfies_the_port():
    adapter = VerificationServiceAdapter(
        VerificationService(repository=InMemoryVerificationRepository())
    )
    assert isinstance(adapter, VerificationPort)


def test_wiring_verification_makes_the_phase_reachable():
    stack = build_engineering_runtime()
    capability = stack.queries.capability(GetLifecycleCapability())

    assert "verification" in capability["wired"]
    assert "verification" in capability["reachable_phases"]


def test_the_path_to_verification_is_blocked_only_by_review():
    """PR-E3's finding, updated by PR-E4.

    When Verification was wired, ``spec_tests`` and ``implementation`` still
    needed the *context* port, so the path to verification was blocked in three
    places. PR-E4 wired Context and closed two of them. ``review`` is the last.

    PR-E6 built Review, so ``wire_review=False`` holds this world fixed --
    without it the test would assert PR-E6's claim rather than PR-E3's.
    """
    stack = build_engineering_runtime(wire_review=False)
    capability = stack.queries.capability(GetLifecycleCapability())

    assert set(capability["missing"]) == {"review"}
    for reachable in ("spec_tests", "implementation", "verification"):
        assert reachable in capability["reachable_phases"]
    assert "review" not in capability["reachable_phases"]


def test_the_previous_behaviour_is_still_testable():
    """A test asserting an unwired port is refused needs a way to unwire it."""
    stack = build_engineering_runtime(wire_verification=False)
    capability = stack.queries.capability(GetLifecycleCapability())
    assert "verification" in capability["missing"]


def test_the_runtime_reports_only_complete_as_complete():
    """Every other status is reported as itself.

    ``VerificationOutcome.complete`` additionally requires zero contradicted and
    zero unreproducible claims -- two independent checks for one fact, because
    the fact is whether work may be merged.
    """
    from backend.contexts.engineering import VerificationOutcome

    assert VerificationOutcome(work_id="w", attempt=1, status="complete").complete
    assert not VerificationOutcome(work_id="w", attempt=1, status="failed").complete
    assert not VerificationOutcome(work_id="w", attempt=1, status="incomplete").complete
    assert not VerificationOutcome(
        work_id="w", attempt=1, status="complete", claims_contradicted=1
    ).complete


def test_the_adapter_reports_none_for_an_unverified_work_order():
    adapter = VerificationServiceAdapter(
        VerificationService(repository=InMemoryVerificationRepository())
    )
    context = ExecutionContext.platform_internal(
        reason="tests", component="tests", source="pytest"
    )
    assert adapter.outcome(context, "WO-never-verified", 1) is None


def test_the_adapter_request_creates_a_real_record():
    service = VerificationService(repository=InMemoryVerificationRepository())
    adapter = VerificationServiceAdapter(service)
    context = ExecutionContext.platform_internal(
        reason="tests", component="tests", source="pytest"
    )

    verification_id = adapter.request(context, "WO-1", 1)
    outcome = adapter.outcome(context, "WO-1", 1)

    assert verification_id
    assert outcome is not None
    assert outcome.status == "requested"
    assert not outcome.complete


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
    root = pathlib.Path("backend/contexts/engineering_verification")
    return [p for p in root.rglob("*.py") if "__pycache__" not in p.parts]


def test_the_context_imports_only_contracts_and_platform():
    permitted = (
        "backend.contracts",
        "backend.platform",
        "backend.contexts.engineering_verification",
    )
    offences = [
        f"{path}: {imported}"
        for path in _modules()
        for imported in _imports(path)
        if imported.startswith("backend.") and not imported.startswith(permitted)
    ]
    assert offences == [], offences


def test_the_context_imports_no_other_bounded_context():
    offences = [
        f"{path}: {imported}"
        for path in _modules()
        for imported in _imports(path)
        if imported.startswith("backend.contexts.")
        and not imported.startswith("backend.contexts.engineering_verification")
    ]
    assert offences == [], offences


def test_the_domain_layer_does_no_io():
    banned = {"pathlib", "os", "socket", "requests", "httpx", "sqlite3", "json"}
    root = pathlib.Path("backend/contexts/engineering_verification/domain")
    offences = [
        f"{path}: {imported}"
        for path in root.rglob("*.py")
        if "__pycache__" not in path.parts
        for imported in _imports(path)
        if imported.split(".")[0] in banned
    ]
    assert offences == [], offences


def test_the_context_writes_no_state_file():
    """STATE-NO-NEW-FILE-STORES."""
    writers = {"json", "pickle", "yaml", "shelve", "sqlite3"}
    offences = [
        f"{path}: {imported}"
        for path in _modules()
        for imported in _imports(path)
        if imported.split(".")[0] in writers
    ]
    assert offences == [], offences


def test_the_repository_is_not_grandfathered():
    """It must pass TENANT-REPOSITORY-CONTEXT on merit; the ratchet may only shrink."""
    from backend.platform.architecture.tenancy_rules import GRANDFATHERED_REPOSITORIES

    for name in ("VerificationRepository", "InMemoryVerificationRepository"):
        assert name not in GRANDFATHERED_REPOSITORIES


def test_it_does_not_squat_the_product_verification_context():
    """``verification`` is BC-4: 'did the fix actually work?'.

    A different concept with the same name. Taking that path would leave the
    product's own Verification context nowhere to go.
    """
    from backend.platform.architecture.boundary_rules import BOUNDED_CONTEXTS

    assert "verification" in BOUNDED_CONTEXTS
    assert not pathlib.Path("backend/contexts/verification").exists()
    assert pathlib.Path("backend/contexts/engineering_verification").is_dir()


def test_event_types_do_not_collide_with_the_runtime():
    """CONTRACT_NAME is globally unique; a clash raises at import time."""
    from backend.contexts.engineering import RUNTIME_EVENT_TYPES
    from backend.contexts.engineering_verification import VERIFICATION_EVENT_TYPES

    runtime = {e.EVENT_TYPE for e in RUNTIME_EVENT_TYPES}
    verification = {e.EVENT_TYPE for e in VERIFICATION_EVENT_TYPES}
    assert runtime.isdisjoint(verification)
    assert all(e.startswith("engineering.verification.") for e in verification)
