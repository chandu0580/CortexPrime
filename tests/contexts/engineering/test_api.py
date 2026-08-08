"""The Engineering Runtime REST API.

Status-code mapping is most of what matters here. A client told 409 retries with
different state; told 503 it retries later; told 400 it fixes its request. Getting
these wrong sends a client into a loop it can never exit.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api import engineering_runtime_routes as routes
from backend.api.engineering_composition import build_engineering_runtime
from backend.contexts.workorder import (
    ApproveWorkOrder,
    BlastRadius,
    DraftWorkOrder,
    InMemoryWorkOrderRepository,
    StaticReferenceResolver,
    WorkOrderService,
)
from backend.platform.context import ExecutionContext


@pytest.fixture
def client(monkeypatch) -> TestClient:
    """A fresh stack per test, so WorkOrders do not leak between them."""
    service = WorkOrderService(
        repository=InMemoryWorkOrderRepository(),
        resolver=StaticReferenceResolver(
            known_adrs=frozenset({"ADR-019"}),
            known_evidence=frozenset({"EV-1"}),
            enforceable_constraints=frozenset({"I6"}),
        ),
    )
    monkeypatch.setattr(routes, "_stack", build_engineering_runtime(service=service))
    app = FastAPI()
    app.include_router(routes.router)
    return TestClient(app)


def _approved(client) -> str:
    stack = routes._stack  # noqa: SLF001 - the test owns this stack
    context = ExecutionContext.platform_internal(
        reason="api-tests", component="tests", source="pytest"
    )
    drafted = stack.work_order_service.draft(
        context,
        DraftWorkOrder(
            intent="The runtime executes only legal transitions",
            acceptance_criteria=("An illegal transition is refused",),
            blast_radius=BlastRadius.of(["backend/contexts/engineering/**"]),
            adr_references=("ADR-019",),
            evidence=("EV-1",),
            constraints=("I6",),
        ),
    )
    work_id = str(drafted.work_order.work_id)
    stack.work_order_service.approve(
        context, ApproveWorkOrder(work_id=work_id, approved_by="founder")
    )
    return work_id


# ----------------------------------------------------------------------
# State
# ----------------------------------------------------------------------


def test_state_reports_phase_and_what_is_next(client):
    work_id = _approved(client)
    body = client.get(f"/api/v1/engineering/runtime/work-orders/{work_id}/state").json()

    assert body["phase"] == "approved"
    assert body["legal_next"] == ["assigned", "blocked"]
    assert body["digest"] is not None


def test_state_of_an_unknown_work_order_is_404(client):
    from backend.contexts.workorder.domain import WorkOrderId

    response = client.get(
        f"/api/v1/engineering/runtime/work-orders/{WorkOrderId.new()}/state"
    )
    assert response.status_code == 404


# ----------------------------------------------------------------------
# Advance
# ----------------------------------------------------------------------


def test_a_legal_advance_returns_the_new_phase(client):
    work_id = _approved(client)
    response = client.post(
        f"/api/v1/engineering/runtime/work-orders/{work_id}/advance",
        json={"to_phase": "assigned", "actor": "orchestrator"},
    )
    assert response.status_code == 200
    assert response.json()["phase"] == "assigned"
    assert response.json()["transition"] == "approved -> assigned"


def test_an_illegal_advance_is_409(client):
    """Well-formed request, conflicting state."""
    work_id = _approved(client)
    response = client.post(
        f"/api/v1/engineering/runtime/work-orders/{work_id}/advance",
        json={"to_phase": "review", "actor": "x"},
    )
    assert response.status_code == 409
    assert "may only move to" in response.json()["detail"]


def test_an_unknown_phase_is_400(client):
    work_id = _approved(client)
    response = client.post(
        f"/api/v1/engineering/runtime/work-orders/{work_id}/advance",
        json={"to_phase": "shipped", "actor": "x"},
    )
    assert response.status_code == 400
    assert "draft" in response.json()["detail"]


def test_a_stale_precondition_is_409(client):
    work_id = _approved(client)
    response = client.post(
        f"/api/v1/engineering/runtime/work-orders/{work_id}/advance",
        json={"to_phase": "assigned", "actor": "x", "expected_phase": "draft"},
    )
    assert response.status_code == 409
    assert "moved after this command" in response.json()["detail"]


def test_a_missing_collaborator_is_503_not_409(monkeypatch):
    """Not the client's fault and not permanent, which is what 503 means.

    Every port is wired as of PR-E6, so this drives a stack with Review
    deliberately unwired. The rule under test belongs to the API -- an unwired
    collaborator is a 503 rather than a 409 -- and it needs an unwired port to
    exercise, not a particular port that happens to be unbuilt.
    """
    service = WorkOrderService(
        repository=InMemoryWorkOrderRepository(),
        resolver=StaticReferenceResolver(
            known_adrs=frozenset({"ADR-019"}),
            known_evidence=frozenset({"EV-1"}),
            enforceable_constraints=frozenset({"I6"}),
        ),
    )
    monkeypatch.setattr(
        routes,
        "_stack",
        build_engineering_runtime(service=service, wire_review=False),
    )
    app = FastAPI()
    app.include_router(routes.router)
    client = TestClient(app)

    work_id = _approved(client)
    for phase in ("assigned", "spec_tests", "implementation"):
        client.post(
            f"/api/v1/engineering/runtime/work-orders/{work_id}/advance",
            json={"to_phase": phase, "actor": "orchestrator"},
        )
    response = client.post(
        f"/api/v1/engineering/runtime/work-orders/{work_id}/advance",
        json={"to_phase": "review", "actor": "x"},
    )
    assert response.status_code == 503
    detail = response.json()["detail"]
    assert detail["error"] == "collaborator_unavailable"
    assert detail["port"] == "review"


def test_an_actor_is_required(client):
    work_id = _approved(client)
    response = client.post(
        f"/api/v1/engineering/runtime/work-orders/{work_id}/advance",
        json={"to_phase": "assigned", "actor": "   "},
    )
    assert response.status_code == 400


# ----------------------------------------------------------------------
# Reject
# ----------------------------------------------------------------------


def test_a_rejection_from_a_phase_that_forbids_one_is_409(client):
    work_id = _approved(client)
    response = client.post(
        f"/api/v1/engineering/runtime/work-orders/{work_id}/reject",
        json={
            "rejection_type": "premise_false",
            "detail": "grep returned nothing",
            "raised_by": "implementer",
        },
    )
    assert response.status_code == 409


def test_a_rejection_without_detail_is_refused(client):
    work_id = _approved(client)
    response = client.post(
        f"/api/v1/engineering/runtime/work-orders/{work_id}/reject",
        json={"rejection_type": "premise_false", "detail": "  ", "raised_by": "x"},
    )
    assert response.status_code in (400, 422)


# ----------------------------------------------------------------------
# Events, capability, integrity
# ----------------------------------------------------------------------


def test_capability_reports_the_missing_adapters(monkeypatch):
    """Asserts what is still missing rather than the full wired list.

    Pinning the wired list makes this test fail every time a context is built,
    which trains people to update it without reading it. What matters is that
    the unbuilt ports are reported as unbuilt -- so this drives the endpoint
    with a stack that has one deliberately unwired.
    """
    monkeypatch.setattr(
        routes, "_stack", build_engineering_runtime(wire_review=False)
    )
    app = FastAPI()
    app.include_router(routes.router)
    body = TestClient(app).get("/api/v1/engineering/runtime/capability").json()
    assert "work_order" in body["wired"]
    assert set(body["missing"]) == {"review"}


def test_capability_reports_everything_wired_by_default(client):
    """PR-E6 supplied the last port; the default stack reports none missing."""
    body = client.get("/api/v1/engineering/runtime/capability").json()
    assert body["missing"] == []


def test_the_event_log_starts_empty_and_stays_intact(client):
    events = client.get("/api/v1/engineering/runtime/events").json()
    assert events["count"] == 0

    integrity = client.get("/api/v1/engineering/runtime/integrity").json()
    assert integrity["intact"] is True
    assert integrity["defects"] == []


def test_replay_of_an_unknown_work_order_is_empty(client):
    from backend.contexts.workorder.domain import WorkOrderId

    body = client.get(
        f"/api/v1/engineering/runtime/work-orders/{WorkOrderId.new()}/replay"
    ).json()
    assert body["count"] == 0


def test_work_order_events_are_scoped_to_that_work_order(client):
    work_id = _approved(client)
    body = client.get(
        f"/api/v1/engineering/runtime/work-orders/{work_id}/events"
    ).json()
    assert body["count"] == 0
    assert all(e["work_id"] == work_id for e in body["events"])


# ----------------------------------------------------------------------
# Shape
# ----------------------------------------------------------------------


def test_every_route_is_versioned(client):
    for route in client.app.routes:
        path = getattr(route, "path", "")
        if "engineering" in path:
            assert path.startswith("/api/v1/engineering/runtime"), path


def test_the_runtime_api_does_not_collide_with_the_workorder_api():
    """Two paths, deliberately. Collapsing them would suggest a client can
    approve a WorkOrder by advancing it."""
    from backend.api.engineering_work_order_routes import router as work_order_router

    runtime_paths = {r.path for r in routes.router.routes}
    work_order_paths = {r.path for r in work_order_router.routes}
    assert runtime_paths.isdisjoint(work_order_paths)


def test_openapi_documents_every_endpoint(client):
    schema = client.app.openapi()
    runtime_paths = [p for p in schema["paths"] if "runtime" in p]
    assert len(runtime_paths) == 8
    for path in runtime_paths:
        for operation in schema["paths"][path].values():
            assert operation.get("summary"), f"{path} has no summary"
