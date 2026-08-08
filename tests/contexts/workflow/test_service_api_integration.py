"""Service, policy, repository, replay, concurrency, API, Constitution compliance.

The integration section pins what PR-M4 claims: the Workflow context turns an
approved plan into an executable graph, refuses the graphs that cannot be run
safely, and runs nothing itself.
"""

from __future__ import annotations

import ast
import pathlib
import threading

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api import workflow_routes as routes
from backend.contracts.errors import ContractViolation
from backend.contexts.workflow import (
    AddCompensation,
    AddEdge,
    AddNode,
    AddParallelGroup,
    AddResumePoint,
    ApproveWorkflowCommand,
    CompileGraph,
    CompileWorkflow,
    CyclicWorkflow,
    DuplicateWorkflow,
    GetGraph,
    GetWorkflow,
    InMemoryWorkflowRepository,
    ListWorkflows,
    RemoveNode,
    ReviseWorkflow,
    SetWorkflowTimeout,
    ValidateWorkflow,
    WorkflowApprovedError,
    WorkflowNotFound,
    WorkflowRefused,
    WorkflowService,
    WorkflowStatus,
)
from backend.contexts.workflow.infrastructure.persistence import (
    RECORD_SCHEMA_VERSION,
    from_record,
    to_record,
)
from backend.platform.context import ExecutionContext
from backend.platform.storage import MissingExecutionContext


@pytest.fixture
def context() -> ExecutionContext:
    return ExecutionContext.platform_internal(
        reason="workflow-tests", component="tests", source="pytest"
    )


@pytest.fixture
def tenant_context() -> ExecutionContext:
    from backend.platform.context.identity import IdentityContext

    return ExecutionContext.for_tenant(
        tenant_id="tenant-a", identity=IdentityContext.platform("tests"), source="pytest"
    )


@pytest.fixture
def repository() -> InMemoryWorkflowRepository:
    return InMemoryWorkflowRepository()


@pytest.fixture
def service(repository) -> WorkflowService:
    return WorkflowService(repository=repository)


def _compile(**overrides) -> CompileWorkflow:
    fields = dict(
        plan_id="P-1",
        plan_digest="9f2c1a7b",
        mission_id="M-1",
        title="Rightsize instances",
        plan_task_ids=("audit", "resize"),
    )
    fields.update(overrides)
    return CompileWorkflow(**fields)


def _wired(service, context, **overrides) -> str:
    workflow_id = str(service.compile_workflow(context, _compile(**overrides)).workflow.workflow_id)
    service.add_node(
        context,
        AddNode(
            workflow_id=workflow_id,
            node_id="audit",
            purpose="list utilisation",
            plan_task_id="audit",
            timeout_seconds=60,
        ),
    )
    service.add_node(
        context,
        AddNode(
            workflow_id=workflow_id,
            node_id="resize",
            purpose="resize instances",
            plan_task_id="resize",
            side_effect="reversible_write",
            max_attempts=2,
            backoff="exponential",
            initial_delay_seconds=1,
            idempotency_key="resize-key",
            timeout_seconds=120,
        ),
    )
    service.add_node(
        context,
        AddNode(
            workflow_id=workflow_id,
            node_id="restore",
            purpose="restore sizes",
            kind="compensation",
            compensates="resize",
            side_effect="reversible_write",
            timeout_seconds=60,
        ),
    )
    service.add_edge(
        context, AddEdge(workflow_id=workflow_id, from_node="audit", to_node="resize")
    )
    service.add_edge(
        context,
        AddEdge(
            workflow_id=workflow_id,
            from_node="resize",
            to_node="restore",
            kind="on_failure",
        ),
    )
    service.add_compensation(
        context,
        AddCompensation(
            workflow_id=workflow_id, compensates="resize", performed_by="restore"
        ),
    )
    service.set_timeout(context, SetWorkflowTimeout(workflow_id=workflow_id, seconds=900))
    return workflow_id


def _approved(service, context, **overrides) -> str:
    workflow_id = _wired(service, context, **overrides)
    service.validate(context, ValidateWorkflow(workflow_id=workflow_id))
    service.compile_graph(context, CompileGraph(workflow_id=workflow_id))
    service.approve(
        context, ApproveWorkflowCommand(workflow_id=workflow_id, approved_by="sre-lead")
    )
    return workflow_id


# ----------------------------------------------------------------------
# Compiling from a plan
# ----------------------------------------------------------------------


def test_compiling_emits_one_event_and_binds_the_plan(service, context) -> None:
    result = service.compile_workflow(context, _compile())
    assert result.event_types == ("workflow.runtime.created",)
    assert result.workflow.plan_digest == "9f2c1a7b"
    assert result.workflow.status is WorkflowStatus.DRAFT


def test_a_workflow_without_a_plan_digest_is_refused_before_the_service() -> None:
    with pytest.raises(ContractViolation):
        _compile(plan_digest="  ")


def test_a_workflow_without_plan_task_ids_is_refused() -> None:
    """Without them nothing can check coverage."""
    with pytest.raises(ContractViolation):
        _compile(plan_task_ids=())


def test_saving_the_same_workflow_twice_is_refused(service, context, repository) -> None:
    workflow = service.compile_workflow(context, _compile()).workflow
    with pytest.raises(DuplicateWorkflow):
        repository.save(context, workflow)


def test_a_task_node_must_name_its_plan_task_at_the_command() -> None:
    with pytest.raises(ContractViolation):
        AddNode(workflow_id="W", node_id="n", purpose="do a thing")


def test_a_retried_mutation_needs_idempotency_at_the_command() -> None:
    with pytest.raises(ContractViolation):
        AddNode(
            workflow_id="W",
            node_id="n",
            purpose="write",
            plan_task_id="t",
            side_effect="destructive",
            max_attempts=3,
        )


# ----------------------------------------------------------------------
# Graph construction through the service
# ----------------------------------------------------------------------


def test_adding_a_node_emits_with_its_shape(service, context) -> None:
    workflow_id = str(service.compile_workflow(context, _compile()).workflow.workflow_id)
    result = service.add_node(
        context,
        AddNode(
            workflow_id=workflow_id,
            node_id="audit",
            purpose="read",
            plan_task_id="audit",
            timeout_seconds=30,
        ),
    )
    assert result.event_types == ("workflow.runtime.node_added",)
    assert result.events[0].has_timeout


def test_a_cycle_is_refused_by_the_service(service, context) -> None:
    workflow_id = _wired(service, context)
    with pytest.raises(CyclicWorkflow):
        service.add_edge(
            context,
            AddEdge(workflow_id=workflow_id, from_node="resize", to_node="audit"),
        )


def test_a_branch_emits_its_own_event(service, context) -> None:
    from backend.contexts.workflow import AddBranch

    workflow_id = _wired(service, context)
    result = service.add_branch(
        context,
        AddBranch(
            workflow_id=workflow_id,
            node_id="choose",
            purpose="pick a resize strategy",
            arms=(
                {
                    "to_node": "resize",
                    "condition_kind": "on_output",
                    "source": "audit",
                    "expression": "count > 10",
                },
                {"to_node": "restore", "condition_kind": "always"},
            ),
        ),
    )
    assert result.event_types == ("workflow.runtime.branch_created",)
    assert result.events[0].has_default


def test_a_parallel_group_emits_its_own_event(service, context) -> None:
    workflow_id = str(
        service.compile_workflow(
            context, _compile(plan_task_ids=("a", "b", "c"))
        ).workflow.workflow_id
    )
    for node_id, task in (("start", "a"), ("left", "b"), ("right", "c")):
        service.add_node(
            context,
            AddNode(
                workflow_id=workflow_id,
                node_id=node_id,
                purpose="work",
                plan_task_id=task,
                timeout_seconds=5,
            ),
        )
    service.add_edge(context, AddEdge(workflow_id=workflow_id, from_node="start", to_node="left"))
    service.add_edge(context, AddEdge(workflow_id=workflow_id, from_node="start", to_node="right"))

    result = service.add_parallel_group(
        context,
        AddParallelGroup(
            workflow_id=workflow_id,
            label="fan",
            members=("left", "right"),
            max_concurrency=2,
        ),
    )
    assert result.event_types == ("workflow.runtime.parallel_group_created",)
    assert result.events[0].members == 2


# ----------------------------------------------------------------------
# Policy
# ----------------------------------------------------------------------


def test_the_policy_reports_every_failure_not_the_first(service, context) -> None:
    workflow_id = str(service.compile_workflow(context, _compile()).workflow.workflow_id)
    report = service.evaluate(context, workflow_id, "validated")
    rules = {f.rule for f in report.blocking}
    assert "W1-required-elements" in rules
    assert "W2-plan-task-covered" in rules
    assert len(report.blocking) > 2


def test_an_uncompensated_mutation_is_refused(service, context) -> None:
    """Its failure mode is 'leave it half-applied and call somebody'."""
    workflow_id = str(service.compile_workflow(context, _compile()).workflow.workflow_id)
    service.add_node(
        context,
        AddNode(
            workflow_id=workflow_id,
            node_id="audit",
            purpose="read",
            plan_task_id="audit",
            timeout_seconds=10,
        ),
    )
    service.add_node(
        context,
        AddNode(
            workflow_id=workflow_id,
            node_id="resize",
            purpose="write",
            plan_task_id="resize",
            side_effect="reversible_write",
            timeout_seconds=10,
        ),
    )
    service.add_edge(context, AddEdge(workflow_id=workflow_id, from_node="audit", to_node="resize"))
    service.set_timeout(context, SetWorkflowTimeout(workflow_id=workflow_id, seconds=600))

    with pytest.raises(WorkflowRefused) as caught:
        service.validate(context, ValidateWorkflow(workflow_id=workflow_id))
    assert any(f.rule == "W3-mutation-compensated" for f in caught.value.failures)


def test_an_uncancellable_mutation_without_a_timeout_is_refused(service, context) -> None:
    """A run that must be stopped has no mechanism to stop it."""
    workflow_id = str(service.compile_workflow(context, _compile()).workflow.workflow_id)
    service.add_node(
        context,
        AddNode(
            workflow_id=workflow_id,
            node_id="audit",
            purpose="read",
            plan_task_id="audit",
            timeout_seconds=10,
        ),
    )
    service.add_node(
        context,
        AddNode(
            workflow_id=workflow_id,
            node_id="resize",
            purpose="write",
            plan_task_id="resize",
            side_effect="reversible_write",
            cancellable=False,
        ),
    )
    service.add_node(
        context,
        AddNode(
            workflow_id=workflow_id,
            node_id="restore",
            purpose="restore",
            kind="compensation",
            compensates="resize",
            side_effect="reversible_write",
            timeout_seconds=10,
        ),
    )
    service.add_edge(context, AddEdge(workflow_id=workflow_id, from_node="audit", to_node="resize"))
    service.add_edge(
        context,
        AddEdge(workflow_id=workflow_id, from_node="resize", to_node="restore", kind="on_failure"),
    )
    service.add_compensation(
        context, AddCompensation(workflow_id=workflow_id, compensates="resize", performed_by="restore")
    )
    service.set_timeout(context, SetWorkflowTimeout(workflow_id=workflow_id, seconds=600))

    report = service.evaluate(context, workflow_id, "validated")
    assert any(f.rule == "W4-stoppable" for f in report.blocking)


def test_an_abandoned_mutation_in_an_any_join_is_refused(service, context) -> None:
    """A member not waited for may still be applying changes."""
    workflow_id = str(
        service.compile_workflow(
            context, _compile(plan_task_ids=("a", "b", "c"))
        ).workflow.workflow_id
    )
    service.add_node(
        context,
        AddNode(workflow_id=workflow_id, node_id="start", purpose="w", plan_task_id="a", timeout_seconds=5),
    )
    service.add_node(
        context,
        AddNode(
            workflow_id=workflow_id,
            node_id="left",
            purpose="w",
            plan_task_id="b",
            side_effect="reversible_write",
            timeout_seconds=5,
        ),
    )
    service.add_node(
        context,
        AddNode(workflow_id=workflow_id, node_id="right", purpose="w", plan_task_id="c", timeout_seconds=5),
    )
    service.add_edge(context, AddEdge(workflow_id=workflow_id, from_node="start", to_node="left"))
    service.add_edge(context, AddEdge(workflow_id=workflow_id, from_node="start", to_node="right"))
    service.add_parallel_group(
        context,
        AddParallelGroup(
            workflow_id=workflow_id, label="fan", members=("left", "right"), join="any"
        ),
    )
    service.set_timeout(context, SetWorkflowTimeout(workflow_id=workflow_id, seconds=600))

    report = service.evaluate(context, workflow_id, "validated")
    assert any(f.rule == "W5-abandoned-mutation" for f in report.blocking)


def test_unused_concurrency_is_advisory(service, context) -> None:
    workflow_id = str(
        service.compile_workflow(
            context, _compile(plan_task_ids=("a", "b", "c"))
        ).workflow.workflow_id
    )
    for node_id, task in (("start", "a"), ("left", "b"), ("right", "c")):
        service.add_node(
            context,
            AddNode(
                workflow_id=workflow_id, node_id=node_id, purpose="read", plan_task_id=task, timeout_seconds=5
            ),
        )
    service.add_edge(context, AddEdge(workflow_id=workflow_id, from_node="start", to_node="left"))
    service.add_edge(context, AddEdge(workflow_id=workflow_id, from_node="start", to_node="right"))
    service.set_timeout(context, SetWorkflowTimeout(workflow_id=workflow_id, seconds=600))

    report = service.evaluate(context, workflow_id, "validated")
    assert report.may_proceed
    assert any(f.rule == "W8-unused-concurrency" for f in report.advisory)


# ----------------------------------------------------------------------
# Validate, compile, approve
# ----------------------------------------------------------------------


def test_a_sound_workflow_validates(service, context) -> None:
    workflow_id = _wired(service, context)
    result = service.validate(context, ValidateWorkflow(workflow_id=workflow_id))
    assert result.event_types == ("workflow.runtime.validated",)
    assert result.events[0].nodes == 3


def test_compiling_freezes_the_order_and_emits(service, context) -> None:
    workflow_id = _wired(service, context)
    service.validate(context, ValidateWorkflow(workflow_id=workflow_id))
    result = service.compile_graph(context, CompileGraph(workflow_id=workflow_id))

    assert result.event_types == ("workflow.runtime.compiled",)
    assert result.events[0].execution_order_length == 3
    assert result.workflow.execution_order == ("audit", "resize", "restore")
    result.workflow.verify_digest()


def test_approving_emits_and_makes_it_executable(service, context) -> None:
    workflow_id = _approved(service, context)
    workflow = service.get(context, GetWorkflow(workflow_id=workflow_id))
    assert workflow.is_executable
    assert service.executable_for(context, "M-1") is not None


def test_an_approved_workflow_refuses_edits(service, context) -> None:
    workflow_id = _approved(service, context)
    with pytest.raises(WorkflowApprovedError):
        service.remove_node(context, RemoveNode(workflow_id=workflow_id, node_id="audit"))


def test_revising_supersedes_the_original(service, context) -> None:
    workflow_id = _approved(service, context)
    result = service.revise(context, ReviseWorkflow(workflow_id=workflow_id))

    assert result.event_types == ("workflow.runtime.versioned",)
    assert result.workflow.version == 2
    original = service.get(context, GetWorkflow(workflow_id=workflow_id))
    assert original.status is WorkflowStatus.SUPERSEDED
    assert service.executable_for(context, "M-1") is None


def test_the_graph_is_queryable(service, context) -> None:
    workflow_id = _wired(service, context)
    graph = service.graph(context, GetGraph(workflow_id=workflow_id))
    assert graph.entry_points == ("audit",)
    assert graph.forward_reachable == ("audit", "resize")


def test_listing_filters(service, context) -> None:
    _wired(service, context)
    _approved(service, context, mission_id="M-2")

    assert len(service.list(context, ListWorkflows())) == 2
    assert len(service.list(context, ListWorkflows(mission_id="M-2"))) == 1
    assert len(service.list(context, ListWorkflows(executable_only=True))) == 1


def test_an_unknown_workflow_is_reported_as_missing(service, context) -> None:
    from backend.contexts.workflow import WorkflowId

    with pytest.raises(WorkflowNotFound):
        service.get(context, GetWorkflow(workflow_id=str(WorkflowId.new())))


# ----------------------------------------------------------------------
# Repository
# ----------------------------------------------------------------------


def test_every_repository_method_requires_an_execution_context(repository) -> None:
    from backend.contexts.workflow import WorkflowId

    for call in (
        lambda: repository.find(None, WorkflowId.new()),
        lambda: repository.all(None),
    ):
        with pytest.raises(MissingExecutionContext):
            call()


def test_a_tenant_cannot_see_another_tenants_workflow(repository, tenant_context) -> None:
    from backend.platform.context.identity import IdentityContext
    from backend.platform.storage import CrossTenantAccess

    service = WorkflowService(repository=repository)
    workflow = service.compile_workflow(tenant_context, _compile()).workflow

    other = ExecutionContext.for_tenant(
        tenant_id="tenant-b", identity=IdentityContext.platform("tests"), source="pytest"
    )
    assert repository.find(other, workflow.workflow_id) is None
    with pytest.raises(CrossTenantAccess):
        repository.replace(other, workflow)


def test_the_repository_is_not_grandfathered() -> None:
    from backend.platform.architecture.tenancy_rules import GRANDFATHERED_REPOSITORIES

    offenders = [
        entry
        for entry in GRANDFATHERED_REPOSITORIES
        if "contexts.workflow" in entry or "contexts/workflow" in entry
    ]
    assert offenders == []


# ----------------------------------------------------------------------
# Replay
# ----------------------------------------------------------------------


def test_a_workflow_survives_the_round_trip_unchanged(service, context) -> None:
    workflow_id = _approved(service, context)
    approved = service.get(context, GetWorkflow(workflow_id=workflow_id))
    assert from_record(to_record(approved, tenant_id="tenant-a")) == approved


def test_the_graph_is_revalidated_on_load(service, context) -> None:
    """A stored workflow edited into a cycle refuses to load."""
    workflow_id = _wired(service, context)
    workflow = service.get(context, GetWorkflow(workflow_id=workflow_id))

    stored = to_record(workflow, tenant_id="tenant-a")
    stored["edges"].append(
        {
            "from_node": "resize",
            "to_node": "audit",
            "kind": "normal",
            "condition": {
                "kind": "always",
                "source_node": None,
                "expression": None,
                "description": "",
            },
            "label": "",
        }
    )
    with pytest.raises(CyclicWorkflow):
        from_record(stored)


def test_the_digest_is_restored_not_recomputed(service, context) -> None:
    from backend.contexts.workflow import DigestMismatch

    workflow_id = _approved(service, context)
    approved = service.get(context, GetWorkflow(workflow_id=workflow_id))

    stored = to_record(approved, tenant_id="tenant-a")
    stored["title"] = "something else entirely"
    with pytest.raises(DigestMismatch):
        from_record(stored).verify_digest()


def test_a_workflow_from_an_unknown_schema_version_is_refused(service, context) -> None:
    workflow = service.compile_workflow(context, _compile()).workflow
    stored = to_record(workflow, tenant_id="tenant-a")
    stored["schema_version"] = RECORD_SCHEMA_VERSION + 1
    with pytest.raises(ContractViolation):
        from_record(stored)


def test_a_workflow_stored_without_a_tenant_is_refused(service, context) -> None:
    workflow = service.compile_workflow(context, _compile()).workflow
    with pytest.raises(ContractViolation):
        to_record(workflow, tenant_id="  ")


# ----------------------------------------------------------------------
# Concurrency
# ----------------------------------------------------------------------


def test_concurrent_compilation_all_persists(service, context) -> None:
    errors: list = []

    def compile_one(index: int) -> None:
        try:
            service.compile_workflow(context, _compile(title=f"workflow-{index}"))
        except Exception as exc:  # pragma: no cover - failure path
            errors.append(exc)

    threads = [threading.Thread(target=compile_one, args=(i,)) for i in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == []
    assert len(service.list(context, ListWorkflows())) == 8


def test_concurrent_reads_during_writes_do_not_tear(service, context) -> None:
    seen: list = []
    errors: list = []
    stop = threading.Event()

    def write() -> None:
        try:
            for index in range(6):
                service.compile_workflow(context, _compile(title=f"w-{index}"))
        except Exception as exc:  # pragma: no cover - failure path
            errors.append(exc)
        finally:
            stop.set()

    def read() -> None:
        while not stop.is_set():
            try:
                seen.append(len(service.list(context, ListWorkflows())))
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
        routes, "_service", WorkflowService(repository=InMemoryWorkflowRepository())
    )
    app = FastAPI()
    app.include_router(routes.router)
    return TestClient(app)


def _compile_via_api(client, **overrides) -> str:
    payload = dict(
        plan_id="P-1",
        plan_digest="9f2c1a7b",
        mission_id="M-1",
        title="Rightsize instances",
        plan_task_ids=["audit", "resize"],
    )
    payload.update(overrides)
    response = client.post("/api/v1/workflows", json=payload)
    assert response.status_code == 201, response.text
    return response.json()["workflow"]["workflow_id"]


def _wired_via_api(client) -> str:
    workflow_id = _compile_via_api(client)
    client.post(
        f"/api/v1/workflows/{workflow_id}/nodes",
        json={
            "node_id": "audit",
            "purpose": "list utilisation",
            "plan_task_id": "audit",
            "timeout_seconds": 60,
        },
    )
    client.post(
        f"/api/v1/workflows/{workflow_id}/nodes",
        json={
            "node_id": "resize",
            "purpose": "resize",
            "plan_task_id": "resize",
            "side_effect": "reversible_write",
            "max_attempts": 2,
            "backoff": "exponential",
            "initial_delay_seconds": 1,
            "idempotency_key": "k",
            "timeout_seconds": 120,
        },
    )
    client.post(
        f"/api/v1/workflows/{workflow_id}/nodes",
        json={
            "node_id": "restore",
            "purpose": "restore",
            "kind": "compensation",
            "compensates": "resize",
            "side_effect": "reversible_write",
            "timeout_seconds": 60,
        },
    )
    client.post(
        f"/api/v1/workflows/{workflow_id}/edges",
        json={"from_node": "audit", "to_node": "resize"},
    )
    client.post(
        f"/api/v1/workflows/{workflow_id}/edges",
        json={"from_node": "resize", "to_node": "restore", "kind": "on_failure"},
    )
    client.post(
        f"/api/v1/workflows/{workflow_id}/compensations",
        json={"compensates": "resize", "performed_by": "restore"},
    )
    client.put(f"/api/v1/workflows/{workflow_id}/timeout", json={"seconds": 900})
    return workflow_id


def test_the_api_compiles_and_fetches(client) -> None:
    workflow_id = _compile_via_api(client)
    body = client.get(f"/api/v1/workflows/{workflow_id}").json()
    assert body["status"] == "draft"
    assert body["uncovered_plan_tasks"] == ["audit", "resize"]


def test_the_api_runs_a_workflow_to_approval(client) -> None:
    workflow_id = _wired_via_api(client)
    assert client.post(f"/api/v1/workflows/{workflow_id}/validate").status_code == 200
    compiled = client.post(f"/api/v1/workflows/{workflow_id}/compile")
    assert compiled.status_code == 200, compiled.text
    assert compiled.json()["workflow"]["execution_order"] == ["audit", "resize", "restore"]

    approved = client.post(
        f"/api/v1/workflows/{workflow_id}/approve", json={"approved_by": "sre-lead"}
    )
    assert approved.status_code == 200
    assert approved.json()["workflow"]["is_executable"]


def test_the_api_exposes_the_graph(client) -> None:
    workflow_id = _wired_via_api(client)
    body = client.get(f"/api/v1/workflows/{workflow_id}/graph").json()
    assert body["entry_points"] == ["audit"]
    assert body["forward_reachable"] == ["audit", "resize"]


def test_the_api_refuses_a_cycle_and_names_it(client) -> None:
    workflow_id = _wired_via_api(client)
    response = client.post(
        f"/api/v1/workflows/{workflow_id}/edges",
        json={"from_node": "resize", "to_node": "audit"},
    )
    assert response.status_code == 400
    assert response.json()["detail"]["error"] == "cyclic_workflow"


def test_the_api_refuses_an_unmeetable_deadline(client) -> None:
    workflow_id = _wired_via_api(client)
    client.put(f"/api/v1/workflows/{workflow_id}/timeout", json={"seconds": 10})
    response = client.post(f"/api/v1/workflows/{workflow_id}/validate")
    assert response.status_code == 422
    rules = {f["rule"] for f in response.json()["detail"]["failures"]}
    assert rules  # policy reported it rather than raising bare


def test_the_api_refuses_a_retry_without_idempotency(client) -> None:
    workflow_id = _compile_via_api(client)
    response = client.post(
        f"/api/v1/workflows/{workflow_id}/nodes",
        json={
            "node_id": "purge",
            "purpose": "delete",
            "plan_task_id": "audit",
            "side_effect": "destructive",
            "max_attempts": 3,
        },
    )
    assert response.status_code == 400


def test_the_api_reports_every_validation_failure(client) -> None:
    workflow_id = _compile_via_api(client)
    response = client.post(f"/api/v1/workflows/{workflow_id}/validate")
    assert response.status_code == 422
    rules = {f["rule"] for f in response.json()["detail"]["failures"]}
    assert "W1-required-elements" in rules


def test_the_policy_endpoint_reports_without_transitioning(client) -> None:
    workflow_id = _compile_via_api(client)
    body = client.get(
        f"/api/v1/workflows/{workflow_id}/policy?to_status=validated"
    ).json()
    assert not body["may_proceed"]
    assert client.get(f"/api/v1/workflows/{workflow_id}").json()["status"] == "draft"


def test_the_api_returns_409_on_an_approved_workflow(client) -> None:
    workflow_id = _wired_via_api(client)
    client.post(f"/api/v1/workflows/{workflow_id}/validate")
    client.post(f"/api/v1/workflows/{workflow_id}/compile")
    client.post(f"/api/v1/workflows/{workflow_id}/approve", json={"approved_by": "sre"})
    response = client.delete(f"/api/v1/workflows/{workflow_id}/nodes/audit")
    assert response.status_code == 409


def test_the_api_returns_404_for_an_unknown_workflow(client) -> None:
    from backend.contexts.workflow import WorkflowId

    assert client.get(f"/api/v1/workflows/{WorkflowId.new()}").status_code == 404


def test_the_api_revises_into_a_new_version(client) -> None:
    workflow_id = _wired_via_api(client)
    client.post(f"/api/v1/workflows/{workflow_id}/validate")
    client.post(f"/api/v1/workflows/{workflow_id}/compile")
    client.post(f"/api/v1/workflows/{workflow_id}/approve", json={"approved_by": "sre"})

    response = client.post(f"/api/v1/workflows/{workflow_id}/revise", json={})
    assert response.status_code == 200
    assert response.json()["workflow"]["version"] == 2
    assert client.get(f"/api/v1/workflows/{workflow_id}").json()["status"] == "superseded"


def test_the_api_reports_the_critical_path(client) -> None:
    workflow_id = _wired_via_api(client)
    body = client.get(f"/api/v1/workflows/{workflow_id}").json()
    assert body["critical_path"]["path"] == ["audit", "resize"]
    assert body["critical_path"]["seconds"] > 0


def test_the_api_rejects_an_unknown_node_kind(client) -> None:
    workflow_id = _compile_via_api(client)
    response = client.post(
        f"/api/v1/workflows/{workflow_id}/nodes",
        json={"node_id": "n", "purpose": "p", "kind": "teleport"},
    )
    assert response.status_code == 422


def test_the_api_lists_and_filters(client) -> None:
    _compile_via_api(client)
    _compile_via_api(client, mission_id="M-2")
    assert client.get("/api/v1/workflows").json()["count"] == 2
    assert client.get("/api/v1/workflows?mission_id=M-2").json()["count"] == 1


# ----------------------------------------------------------------------
# Constitution compliance
# ----------------------------------------------------------------------


def _modules() -> list:
    root = pathlib.Path("backend/contexts/workflow")
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
    permitted = ("backend.contracts", "backend.platform", "backend.contexts.workflow")
    offences = [
        f"{path}: {imported}"
        for path in _modules()
        for imported in _imports(path)
        if imported.startswith("backend.") and not imported.startswith(permitted)
    ]
    assert offences == [], offences


def test_the_context_imports_no_other_bounded_context() -> None:
    """S2. Workflow never modifies plans -- it cannot even see one."""
    offences = [
        f"{path}: {imported}"
        for path in _modules()
        for imported in _imports(path)
        if imported.startswith("backend.contexts.")
        and not imported.startswith("backend.contexts.workflow")
    ]
    assert offences == [], offences


def test_workflow_never_executes_and_never_invokes_tools() -> None:
    """``backend.contracts.execution`` is permitted and is not an exception:
    that module says of itself that it holds declarations, not invocations.
    ``backend.execution`` -- the thing that performs work -- must stay
    unreachable."""
    forbidden = (
        "backend.execution",
        "backend.orchestrator",
        "backend.orchestration",
        "backend.llm",
        "backend.ai",
        "backend.agents",
        "backend.agent_sdk",
        "backend.connector",
        "backend.connectors",
        "backend.knowledge",
        "backend.services",
        "backend.workflow_designer",
        "backend.database",
        "backend.tools",
        "backend.mcp",
    )
    offences = [
        f"{path}: {imported}"
        for path in _modules()
        for imported in _imports(path)
        if imported.startswith(forbidden)
    ]
    assert offences == [], offences


def test_the_domain_layer_does_no_io() -> None:
    banned = {"pathlib", "os", "socket", "requests", "httpx", "sqlite3", "json"}
    root = pathlib.Path("backend/contexts/workflow/domain")
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
    from backend.contexts.intent import INTENT_EVENT_TYPES
    from backend.contexts.mission import MISSION_EVENT_TYPES
    from backend.contexts.planner import PLAN_EVENT_TYPES
    from backend.contexts.review import REVIEW_EVENT_TYPES
    from backend.contexts.workflow import WORKFLOW_EVENT_TYPES

    ours = {e.EVENT_TYPE for e in WORKFLOW_EVENT_TYPES}
    assert all(e.startswith("workflow.runtime.") for e in ours)
    assert len(ours) == 8
    for other in (
        CONTEXT_EVENT_TYPES,
        RUNTIME_EVENT_TYPES,
        VERIFICATION_EVENT_TYPES,
        IMPLEMENTATION_EVENT_TYPES,
        INTENT_EVENT_TYPES,
        MISSION_EVENT_TYPES,
        PLAN_EVENT_TYPES,
        REVIEW_EVENT_TYPES,
    ):
        assert ours.isdisjoint({e.EVENT_TYPE for e in other})


def test_the_route_module_does_not_import_a_second_context() -> None:
    path = pathlib.Path("backend/api/workflow_routes.py")
    contexts = {
        imported.split(".")[2]
        for imported in _imports(path)
        if imported.startswith("backend.contexts.") and len(imported.split(".")) > 2
    }
    assert contexts == {"workflow"}, contexts
