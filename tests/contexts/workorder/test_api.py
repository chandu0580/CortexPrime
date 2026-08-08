"""The REST API.

Driven through FastAPI's TestClient against the real router, real service, and
real domain. The status-code mapping is most of what is being tested: a client
that gets 400 where it should get 409 will retry a request that can never
succeed.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api import engineering_work_order_routes as routes


@pytest.fixture
def client(monkeypatch) -> TestClient:
    """A fresh service per test.

    The module holds one at import time so the app has a single instance. Tests
    need isolation, so each gets its own -- otherwise WorkOrders leak between
    tests and blast-radius conflicts fire for reasons the failing test did not
    cause.
    """
    monkeypatch.setattr(routes, "_service", routes._build_service())
    app = FastAPI()
    app.include_router(routes.router)
    return TestClient(app)


def _draft_body(**overrides) -> dict:
    body = {
        "intent": "The storage boundary refuses operations without an ExecutionContext",
        "acceptance_criteria": ["A read with no context is refused"],
        "blast_radius": {"allowed": ["backend/contexts/workorder/**"]},
        "adr_references": ["ADR-018"],
        "constraints": ["I6"],
        "definition_of_done": ["the guard refuses an unattributed write"],
    }
    body.update(overrides)
    return body


# ----------------------------------------------------------------------
# Drafting
# ----------------------------------------------------------------------


def test_draft_returns_201_and_the_work_order(client):
    response = client.post("/api/v1/engineering/work-orders", json=_draft_body())
    assert response.status_code == 201
    body = response.json()
    assert body["work_order"]["state"] == "draft"
    assert body["work_order"]["digest"] is None
    assert body["events"] == ["engineering.work_order.drafted"]


def test_draft_pairs_each_assumption_with_a_rejection_ground(client):
    response = client.post(
        "/api/v1/engineering/work-orders",
        json=_draft_body(
            assumptions=[
                {"statement": "models carry a tenant column", "verification_method": "grep"}
            ]
        ),
    )
    work_order = response.json()["work_order"]
    assert len(work_order["assumptions"]) == 1
    assert len(work_order["rejection_grounds"]) == 1
    assert work_order["rejection_grounds"][0]["triggering_assumption"] == (
        work_order["assumptions"][0]["assumption_id"]
    )


def test_an_empty_blast_radius_is_a_422_from_the_schema(client):
    response = client.post(
        "/api/v1/engineering/work-orders", json=_draft_body(blast_radius={"allowed": []})
    )
    assert response.status_code == 422


def test_a_blast_radius_spanning_too_many_packages_is_a_400(client):
    """A domain refusal, not a schema one -- the request was well-formed."""
    response = client.post(
        "/api/v1/engineering/work-orders",
        json=_draft_body(blast_radius={"allowed": ["a/**", "b/**", "c/**", "d/**"]}),
    )
    assert response.status_code == 400
    assert "justification" in response.json()["detail"]


# ----------------------------------------------------------------------
# Validation and approval
# ----------------------------------------------------------------------


def test_evidence_cannot_resolve_because_no_evidence_store_exists(client):
    """V4 fails closed, which is the honest state of the system.

    The Evidence context is not built. A resolver that answered "yes" would make
    V4 unfalsifiable, so any evidence reference blocks approval until there is
    something real to resolve it against.
    """
    created = client.post(
        "/api/v1/engineering/work-orders", json=_draft_body(evidence=["EV-1"])
    ).json()
    work_id = created["work_order"]["work_id"]

    report = client.get(f"/api/v1/engineering/work-orders/{work_id}/validation").json()
    assert report["approvable"] is False
    assert any(f["rule"] == "V4" for f in report["blocking"])


def test_a_work_order_citing_only_real_adrs_and_rules_is_approvable(client):
    """The happy path reaches approval against the real repository.

    ADR-018 exists on disk and I6 is a real invariant in the architecture gate,
    so V5 and V9 resolve for real rather than against a supplied list.
    """
    created = client.post("/api/v1/engineering/work-orders", json=_draft_body()).json()
    work_id = created["work_order"]["work_id"]

    report = client.get(f"/api/v1/engineering/work-orders/{work_id}/validation").json()
    assert report["approvable"] is True, report["blocking"]

    approved = client.post(
        f"/api/v1/engineering/work-orders/{work_id}/approve", json={"approved_by": "founder"}
    )
    assert approved.status_code == 200
    assert approved.json()["work_order"]["digest"] is not None


def test_approve_of_an_unapprovable_work_order_is_422_with_findings(client):
    created = client.post(
        "/api/v1/engineering/work-orders", json=_draft_body(adr_references=["ADR-999"])
    ).json()
    work_id = created["work_order"]["work_id"]

    response = client.post(
        f"/api/v1/engineering/work-orders/{work_id}/approve", json={"approved_by": "founder"}
    )
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["error"] == "validation_failed"
    assert detail["findings"]


def test_approve_requires_a_named_approver(client):
    created = client.post("/api/v1/engineering/work-orders", json=_draft_body()).json()
    work_id = created["work_order"]["work_id"]
    response = client.post(
        f"/api/v1/engineering/work-orders/{work_id}/approve", json={"approved_by": "   "}
    )
    assert response.status_code in (400, 422)


# ----------------------------------------------------------------------
# Retrieval
# ----------------------------------------------------------------------


def test_get_an_unknown_work_order_is_404(client):
    from backend.contexts.workorder.domain import WorkOrderId

    response = client.get(f"/api/v1/engineering/work-orders/{WorkOrderId.new()}")
    assert response.status_code == 404


def test_a_malformed_work_id_is_400_not_500(client):
    response = client.get("/api/v1/engineering/work-orders/not-a-ulid")
    assert response.status_code == 400


def test_list_returns_active_work_orders(client):
    client.post("/api/v1/engineering/work-orders", json=_draft_body())
    client.post("/api/v1/engineering/work-orders", json=_draft_body(intent="A second outcome"))
    body = client.get("/api/v1/engineering/work-orders?active_only=true").json()
    assert body["count"] == 2


def test_versions_of_an_unknown_work_order_is_404(client):
    from backend.contexts.workorder.domain import WorkOrderId

    response = client.get(f"/api/v1/engineering/work-orders/{WorkOrderId.new()}/versions")
    assert response.status_code == 404


# ----------------------------------------------------------------------
# Transitions
# ----------------------------------------------------------------------


def test_an_unknown_state_is_400_and_lists_the_valid_ones(client):
    created = client.post("/api/v1/engineering/work-orders", json=_draft_body()).json()
    work_id = created["work_order"]["work_id"]
    response = client.post(
        f"/api/v1/engineering/work-orders/{work_id}/transition",
        json={"to_state": "shipped", "actor": "orchestrator"},
    )
    assert response.status_code == 400
    assert "draft" in response.json()["detail"]


def test_an_invalid_transition_is_409(client):
    """Well-formed request, conflicting state. 400 would tell a client to fix a fine request."""
    created = client.post("/api/v1/engineering/work-orders", json=_draft_body()).json()
    work_id = created["work_order"]["work_id"]

    response = client.post(
        f"/api/v1/engineering/work-orders/{work_id}/transition",
        json={"to_state": "assigned", "actor": "orchestrator"},
    )
    assert response.status_code == 409
    assert "blast-radius lock" in response.json()["detail"]


def test_rejecting_reports_who_resolves_it(client):
    created = client.post("/api/v1/engineering/work-orders", json=_draft_body()).json()
    work_id = created["work_order"]["work_id"]

    response = client.post(
        f"/api/v1/engineering/work-orders/{work_id}/reject",
        json={
            "rejection_type": "constraint_conflict",
            "detail": "criterion X and invariant I6 cannot both hold when Y",
            "raised_by": "reviewer",
        },
    )
    assert response.status_code == 200
    assert response.json()["resolver"] == "founder"


def test_rejecting_from_a_terminal_state_is_409(client):
    created = client.post("/api/v1/engineering/work-orders", json=_draft_body()).json()
    work_id = created["work_order"]["work_id"]
    payload = {
        "rejection_type": "premise_false",
        "detail": "grep returned nothing",
        "raised_by": "implementer",
    }
    client.post(f"/api/v1/engineering/work-orders/{work_id}/reject", json=payload)

    response = client.post(f"/api/v1/engineering/work-orders/{work_id}/reject", json=payload)
    assert response.status_code == 409
    assert "terminal" in response.json()["detail"]


def test_an_unknown_rejection_type_is_400(client):
    created = client.post("/api/v1/engineering/work-orders", json=_draft_body()).json()
    work_id = created["work_order"]["work_id"]
    response = client.post(
        f"/api/v1/engineering/work-orders/{work_id}/reject",
        json={"rejection_type": "because_i_said_so", "detail": "x", "raised_by": "y"},
    )
    assert response.status_code == 400
    assert "premise_false" in response.json()["detail"]


def test_a_rejection_without_detail_is_refused(client):
    created = client.post("/api/v1/engineering/work-orders", json=_draft_body()).json()
    work_id = created["work_order"]["work_id"]
    response = client.post(
        f"/api/v1/engineering/work-orders/{work_id}/reject",
        json={"rejection_type": "premise_false", "detail": "   ", "raised_by": "y"},
    )
    assert response.status_code in (400, 422)


# ----------------------------------------------------------------------
# Conflicts
# ----------------------------------------------------------------------


def test_conflicts_endpoint_reports_none_when_nothing_is_assigned(client):
    body = client.post(
        "/api/v1/engineering/blast-radius/conflicts", json={"allowed": ["backend/**"]}
    ).json()
    assert body["conflicting"] == 0


# ----------------------------------------------------------------------
# Versioning and documentation
# ----------------------------------------------------------------------


def test_every_route_is_versioned(client):
    for route in client.app.routes:
        path = getattr(route, "path", "")
        if "engineering" in path:
            assert path.startswith("/api/v1/engineering"), path


def test_openapi_documents_every_endpoint(client):
    schema = client.app.openapi()
    engineering = [p for p in schema["paths"] if "engineering" in p]
    assert len(engineering) == 11
    for path, methods in schema["paths"].items():
        if "engineering" not in path:
            continue
        for operation in methods.values():
            assert operation.get("summary"), f"{path} has no summary"
