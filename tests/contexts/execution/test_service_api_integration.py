"""Service, workers, the REST surface, and Constitution compliance.

The compliance section pins what PR-M5 claims: the Execution context runs a
compiled workflow graph, refuses the moves that would lose track of what
happened to production, and contains no worker implementation of its own.
"""

from __future__ import annotations

import ast
import pathlib

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api import execution_routes as routes
from backend.contracts.errors import ContractViolation
from backend.contexts.execution import (
    AssignNode,
    CancelExecution,
    CompensateNode,
    CompleteExecution,
    CreateCheckpoint,
    ExecutionNotFound,
    ExecutionRefused,
    ExecutionService,
    ExecutionState,
    ExecutionWorker,
    FailExecution,
    GetExecution,
    GetReadyNodes,
    InMemoryExecutionRepository,
    ListExecutions,
    PauseExecution,
    ReclaimNode,
    RecordFailure,
    RecordSuccess,
    RegisterWorker,
    ResumeExecution,
    RetryNode,
    RunContext,
    SkipNode,
    StartExecution,
    TimeOutExecution,
    UnknownWorker,
    WorkerCannotRun,
    WorkerKind,
)
from backend.platform.context import ExecutionContext


@pytest.fixture
def context() -> ExecutionContext:
    return ExecutionContext.platform_internal(
        reason="execution-tests", component="tests", source="pytest"
    )


@pytest.fixture
def service() -> ExecutionService:
    built = ExecutionService(repository=InMemoryExecutionRepository())
    built.register_worker(
        RegisterWorker(worker_id="w-1", kinds=("shell",), lease_seconds=300)
    )
    return built


def _start(**overrides) -> StartExecution:
    fields = dict(
        workflow_id="W-1",
        workflow_digest="deadbeef",
        mission_id="M-1",
        nodes=(
            {"node_id": "audit", "worker_kind": "shell"},
            {"node_id": "resize", "worker_kind": "shell", "depends_on": ["audit"]},
        ),
    )
    fields.update(overrides)
    return StartExecution(**fields)


def _running(service, context, **overrides) -> str:
    return str(service.start(context, _start(**overrides)).execution.execution_id)


def _finish_node(service, context, execution_id: str, node_id: str):
    service.assign(
        context, AssignNode(execution_id=execution_id, node_id=node_id, worker_id="w-1")
    )
    return service.record_success(
        context,
        RecordSuccess(
            execution_id=execution_id,
            node_id=node_id,
            worker_id="w-1",
            execution_key=f"{node_id}-key",
        ),
    )


# ----------------------------------------------------------------------
# Commands
# ----------------------------------------------------------------------


class TestCommands:
    def test_a_run_without_a_workflow_digest_is_refused(self) -> None:
        with pytest.raises(ContractViolation):
            _start(workflow_digest="  ")

    def test_a_run_with_no_nodes_is_refused(self) -> None:
        with pytest.raises(ContractViolation):
            _start(nodes=())

    def test_a_retryable_mutation_without_an_idempotency_key_is_refused(self) -> None:
        with pytest.raises(ContractViolation, match="idempotency"):
            _start(
                nodes=(
                    {
                        "node_id": "resize",
                        "worker_kind": "shell",
                        "side_effect": "irreversible_write",
                        "max_attempts": 3,
                    },
                )
            )

    def test_a_result_must_say_who_is_offering_it(self) -> None:
        with pytest.raises(ContractViolation):
            RecordSuccess(
                execution_id="E-1", node_id="audit", worker_id="", execution_key="k"
            )

    def test_a_failure_must_say_why(self) -> None:
        with pytest.raises(ContractViolation):
            RecordFailure(
                execution_id="E-1", node_id="audit", worker_id="w-1", reason="   "
            )

    def test_a_skip_must_say_why(self) -> None:
        with pytest.raises(ContractViolation):
            SkipNode(execution_id="E-1", node_id="audit", reason="")

    def test_a_worker_that_can_run_nothing_is_refused(self) -> None:
        with pytest.raises(ContractViolation):
            RegisterWorker(worker_id="w-9", kinds=())


# ----------------------------------------------------------------------
# Service
# ----------------------------------------------------------------------


class TestService:
    def test_starting_a_run_emits_the_event_and_promotes_the_entry_node(
        self, service, context
    ) -> None:
        result = service.start(context, _start())
        assert result.event_types == ("execution.runtime.started",)
        assert result.execution.ready_nodes() == ("audit",)
        assert result.execution.state is ExecutionState.RUNNING

    def test_a_started_run_can_be_fetched_and_listed(self, service, context) -> None:
        execution_id = _running(service, context)
        assert str(
            service.get(context, GetExecution(execution_id=execution_id)).execution_id
        ) == execution_id
        assert len(service.list(context, ListExecutions(mission_id="M-1"))) == 1
        assert service.list(context, ListExecutions(mission_id="other")) == ()

    def test_listing_live_only_excludes_finished_runs(self, service, context) -> None:
        execution_id = _running(service, context)
        service.cancel(
            context, CancelExecution(execution_id=execution_id, reason="called off")
        )
        assert service.list(context, ListExecutions(live_only=True)) == ()
        assert len(service.list(context, ListExecutions())) == 1

    def test_an_unknown_run_is_named_not_guessed_at(self, service, context) -> None:
        with pytest.raises(ExecutionNotFound):
            service.get(context, GetExecution(execution_id="01JZZZZZZZZZZZZZZZZZZZZZZZ"))

    def test_assigning_requires_a_registered_worker(self, service, context) -> None:
        execution_id = _running(service, context)
        with pytest.raises(UnknownWorker):
            service.assign(
                context,
                AssignNode(execution_id=execution_id, node_id="audit", worker_id="ghost"),
            )

    def test_a_worker_is_never_given_work_it_cannot_run(self, service, context) -> None:
        service.register_worker(RegisterWorker(worker_id="k8s-1", kinds=("kubernetes",)))
        execution_id = _running(service, context)
        with pytest.raises(WorkerCannotRun):
            service.assign(
                context,
                AssignNode(execution_id=execution_id, node_id="audit", worker_id="k8s-1"),
            )

    def test_the_run_context_tells_a_worker_exactly_what_to_do(
        self, service, context
    ) -> None:
        execution_id = _running(service, context)
        service.assign(
            context,
            AssignNode(execution_id=execution_id, node_id="audit", worker_id="w-1"),
        )
        run_context = service.run_context_for(context, execution_id, "audit")
        assert isinstance(run_context, RunContext)
        assert run_context.node_id == "audit"
        assert run_context.attempt == 1
        assert run_context.worker_kind is WorkerKind.SHELL
        assert not run_context.is_retry

    def test_a_success_moves_the_graph_forward(self, service, context) -> None:
        execution_id = _running(service, context)
        result = _finish_node(service, context, execution_id, "audit")
        assert result.execution.ready_nodes() == ("resize",)

    def test_a_full_run_completes_verifiably(self, service, context) -> None:
        execution_id = _running(service, context)
        _finish_node(service, context, execution_id, "audit")
        _finish_node(service, context, execution_id, "resize")
        result = service.complete(context, CompleteExecution(execution_id=execution_id))
        assert result.event_types == ("execution.runtime.completed",)
        result.execution.verify_digest()

    def test_completing_early_is_refused_by_policy_with_findings(
        self, service, context
    ) -> None:
        execution_id = _running(service, context)
        with pytest.raises(ExecutionRefused) as caught:
            service.complete(context, CompleteExecution(execution_id=execution_id))
        assert {f.rule for f in caught.value.failures} >= {"X1-all-nodes-finished"}

    def test_pause_and_resume_round_trip_through_a_checkpoint(
        self, service, context
    ) -> None:
        execution_id = _running(service, context)
        _finish_node(service, context, execution_id, "audit")
        checkpointed = service.checkpoint(
            context, CreateCheckpoint(execution_id=execution_id, label="audit done")
        )
        assert checkpointed.event_types == ("execution.runtime.checkpoint_created",)
        service.pause(
            context, PauseExecution(execution_id=execution_id, reason="change window")
        )
        checkpoint_id = str(checkpointed.execution.latest_checkpoint.checkpoint_id)
        resumed = service.resume(
            context,
            ResumeExecution(execution_id=execution_id, from_checkpoint=checkpoint_id),
        )
        assert resumed.execution.state is ExecutionState.RUNNING
        assert resumed.execution.resumed_from == checkpoint_id

    def test_a_reclaimed_node_is_reported_before_it_is_taken_back(
        self, service, context
    ) -> None:
        execution_id = _running(service, context)
        service.assign(
            context,
            AssignNode(execution_id=execution_id, node_id="audit", worker_id="w-1"),
        )
        # Nothing is reclaimable while the lease is live.
        assert service.reclaimable(context, execution_id) == ()

    def test_a_failure_then_a_retry_returns_the_node_to_ready(
        self, service, context
    ) -> None:
        execution_id = _running(
            service,
            context,
            nodes=({"node_id": "audit", "worker_kind": "shell", "max_attempts": 2},),
        )
        service.assign(
            context,
            AssignNode(execution_id=execution_id, node_id="audit", worker_id="w-1"),
        )
        service.record_failure(
            context,
            RecordFailure(
                execution_id=execution_id,
                node_id="audit",
                worker_id="w-1",
                reason="transient",
            ),
        )
        retried = service.retry(context, RetryNode(execution_id=execution_id, node_id="audit"))
        assert retried.event_types == ("execution.runtime.retried",)
        assert retried.execution.ready_nodes() == ("audit",)

    def test_a_skip_records_the_reason(self, service, context) -> None:
        execution_id = _running(service, context)
        result = service.skip(
            context,
            SkipNode(
                execution_id=execution_id, node_id="audit", reason="already rightsized"
            ),
        )
        assert result.execution.run_for("audit").skipped_reason == "already rightsized"

    def test_compensation_settles_an_ambiguous_node(self, service, context) -> None:
        execution_id = _running(
            service,
            context,
            nodes=(
                {
                    "node_id": "audit",
                    "worker_kind": "shell",
                    "side_effect": "reversible_write",
                },
            ),
        )
        _finish_node(service, context, execution_id, "audit")
        result = service.compensate(
            context, CompensateNode(execution_id=execution_id, node_id="audit")
        )
        assert result.execution.run_for("audit").state.value == "compensated"

    def test_failing_and_cancelling_both_record_why(self, service, context) -> None:
        failed = service.fail(
            context,
            FailExecution(
                execution_id=_running(service, context), reason="worker pool gone"
            ),
        )
        assert failed.execution.outcome_note == "worker pool gone"
        cancelled = service.cancel(
            context,
            CancelExecution(
                execution_id=_running(service, context), reason="operator stopped it"
            ),
        )
        assert cancelled.execution.outcome_note == "operator stopped it"

    def test_a_timeout_is_recorded_as_its_own_ending(self, service, context) -> None:
        result = service.time_out(
            context, TimeOutExecution(execution_id=_running(service, context))
        )
        assert result.execution.state is ExecutionState.TIMED_OUT
        assert result.event_types == ("execution.runtime.timed_out",)

    def test_the_stream_snapshot_carries_progress_and_node_states(
        self, service, context
    ) -> None:
        execution_id = _running(service, context)
        _finish_node(service, context, execution_id, "audit")
        snapshot = service.stream_state(context, execution_id)
        assert snapshot["progress"] == {"finished": 1, "total": 2}
        assert snapshot["ready"] == ["resize"]

    def test_ready_nodes_is_a_query_not_a_dispatch(self, service, context) -> None:
        execution_id = _running(service, context)
        before = service.ready_nodes(context, GetReadyNodes(execution_id=execution_id))
        after = service.ready_nodes(context, GetReadyNodes(execution_id=execution_id))
        assert before == after == ("audit",)


class TestWorkerPool:
    def test_a_worker_is_only_offered_kinds_it_declared(self, service) -> None:
        service.register_worker(RegisterWorker(worker_id="tf-1", kinds=("terraform",)))
        available = service.pool.available_for(WorkerKind.TERRAFORM)
        assert [w.worker_id for w in available] == ["tf-1"]
        assert service.pool.available_for(WorkerKind.BROWSER) == ()

    def test_deregistering_removes_a_worker(self, service) -> None:
        service.pool.deregister("w-1")
        with pytest.raises(UnknownWorker):
            service.pool.get("w-1")

    def test_the_worker_port_is_a_protocol_with_no_implementation_here(self) -> None:
        # PR-M5 owns the interface. Shell, Docker, Kubernetes and browser workers
        # are somebody else's PR; building one here would put execution machinery
        # inside the context that decides what may execute.
        assert getattr(ExecutionWorker, "_is_protocol", False)
        root = pathlib.Path("backend/contexts/execution")
        # The docker/kubernetes markers are import-shaped: a governed capability's
        # *name* legitimately contains the provider id ("kubernetes.pods.list" in
        # the declared catalog, Phase 9.1) — the invariant is that no SDK is
        # imported or driven here, which BND-PROVIDER-SDK also enforces with an
        # AST pass over the whole backend.
        offenders = [
            str(path)
            for path in root.rglob("*.py")
            if "__pycache__" not in path.parts
            and any(
                marker in path.read_text(encoding="utf-8")
                for marker in (
                    "subprocess.",
                    "import docker",
                    "from docker",
                    "import kubernetes",
                    "from kubernetes import",
                    "playwright",
                )
            )
        ]
        assert offenders == [], offenders


# ----------------------------------------------------------------------
# API
# ----------------------------------------------------------------------


@pytest.fixture
def client(monkeypatch) -> TestClient:
    service = ExecutionService(repository=InMemoryExecutionRepository())
    service.register_worker(RegisterWorker(worker_id="w-1", kinds=("shell",)))
    monkeypatch.setattr(routes, "_service", service)
    # The direct-start route bypasses workflow approval and is disabled by
    # default (Phase 3.1). These tests exercise the runtime rather than the
    # trust boundary, so they opt in explicitly -- which is the point of the
    # switch: using it has to be a deliberate act.
    monkeypatch.setattr(routes, "DIRECT_START_ENABLED", True)
    app = FastAPI()
    app.include_router(routes.router)
    return TestClient(app)


def _start_via_api(client, **overrides) -> str:
    payload = dict(
        workflow_id="W-1",
        workflow_digest="deadbeef",
        mission_id="M-1",
        nodes=[
            {"node_id": "audit", "worker_kind": "shell"},
            {"node_id": "resize", "worker_kind": "shell", "depends_on": ["audit"]},
        ],
    )
    payload.update(overrides)
    response = client.post("/api/v1/executions", json=payload)
    assert response.status_code == 201, response.text
    return response.json()["execution"]["execution_id"]


class TestApi:
    def test_starting_a_run_returns_201_with_the_ready_set(self, client) -> None:
        response = client.post(
            "/api/v1/executions",
            json={
                "workflow_id": "W-1",
                "workflow_digest": "deadbeef",
                "mission_id": "M-1",
                "nodes": [{"node_id": "audit", "worker_kind": "shell"}],
            },
        )
        assert response.status_code == 201
        assert response.json()["execution"]["ready_nodes"] == ["audit"]

    def test_a_missing_digest_is_a_400(self, client) -> None:
        response = client.post(
            "/api/v1/executions",
            json={
                "workflow_id": "W-1",
                "workflow_digest": "   ",
                "mission_id": "M-1",
                "nodes": [{"node_id": "audit", "worker_kind": "shell"}],
            },
        )
        assert response.status_code == 400

    def test_an_unknown_worker_kind_is_rejected_by_validation(self, client) -> None:
        response = client.post(
            "/api/v1/executions",
            json={
                "workflow_id": "W-1",
                "workflow_digest": "deadbeef",
                "mission_id": "M-1",
                "nodes": [{"node_id": "audit", "worker_kind": "quantum"}],
            },
        )
        assert response.status_code == 422

    def test_an_unknown_run_is_a_404(self, client) -> None:
        assert client.get("/api/v1/executions/01JZZZZZZZZZZZZZZZZZZZZZZZ").status_code == 404

    def test_a_second_worker_taking_a_leased_node_is_a_409(self, client) -> None:
        execution_id = _start_via_api(client)
        client.post("/api/v1/executions/workers", json={"worker_id": "w-2", "kinds": ["shell"]})
        first = client.post(
            f"/api/v1/executions/{execution_id}/assign",
            json={"node_id": "audit", "worker_id": "w-1"},
        )
        assert first.status_code == 200
        second = client.post(
            f"/api/v1/executions/{execution_id}/assign",
            json={"node_id": "audit", "worker_id": "w-2"},
        )
        assert second.status_code == 409
        assert second.json()["detail"]["error"] == "node_already_leased"

    def test_a_result_from_a_worker_without_the_lease_is_a_409(self, client) -> None:
        execution_id = _start_via_api(client)
        client.post("/api/v1/executions/workers", json={"worker_id": "w-2", "kinds": ["shell"]})
        client.post(
            f"/api/v1/executions/{execution_id}/assign",
            json={"node_id": "audit", "worker_id": "w-1"},
        )
        response = client.post(
            f"/api/v1/executions/{execution_id}/results",
            json={"node_id": "audit", "worker_id": "w-2", "execution_key": "k"},
        )
        assert response.status_code == 409
        assert response.json()["detail"]["error"] == "lease_not_held"

    def test_dispatching_a_node_whose_dependencies_are_unmet_is_a_400(self, client) -> None:
        execution_id = _start_via_api(client)
        response = client.post(
            f"/api/v1/executions/{execution_id}/assign",
            json={"node_id": "resize", "worker_id": "w-1"},
        )
        assert response.status_code == 400
        assert response.json()["detail"]["waiting_on"] == ["audit"]

    def test_completing_early_is_a_422_carrying_the_findings(self, client) -> None:
        execution_id = _start_via_api(client)
        response = client.post(f"/api/v1/executions/{execution_id}/complete")
        assert response.status_code == 422
        rules = {f["rule"] for f in response.json()["detail"]["failures"]}
        assert "X1-all-nodes-finished" in rules

    def test_a_full_run_through_the_api_completes_and_publishes_results(
        self, client
    ) -> None:
        execution_id = _start_via_api(client)
        for node_id in ("audit", "resize"):
            client.post(
                f"/api/v1/executions/{execution_id}/assign",
                json={"node_id": node_id, "worker_id": "w-1"},
            )
            client.post(
                f"/api/v1/executions/{execution_id}/results",
                json={
                    "node_id": node_id,
                    "worker_id": "w-1",
                    "execution_key": f"{node_id}-key",
                },
            )
        response = client.post(f"/api/v1/executions/{execution_id}/complete")
        assert response.status_code == 200
        body = response.json()["execution"]
        assert body["state"] == "completed"
        assert body["digest"]
        assert {r["status"] for r in body["published_results"]} == {"succeeded"}

    def test_driving_a_finished_run_is_a_409(self, client) -> None:
        execution_id = _start_via_api(client)
        client.post(
            f"/api/v1/executions/{execution_id}/cancel", json={"reason": "called off"}
        )
        response = client.post(
            f"/api/v1/executions/{execution_id}/pause", json={"reason": "too late"}
        )
        assert response.status_code == 409

    def test_the_policy_endpoint_reports_without_moving_the_run(self, client) -> None:
        execution_id = _start_via_api(client)
        response = client.get(f"/api/v1/executions/{execution_id}/policy?to_state=completed")
        assert response.status_code == 200
        assert response.json()["may_proceed"] is False
        assert client.get(f"/api/v1/executions/{execution_id}").json()["state"] == "running"

    def test_the_run_context_endpoint_hands_a_worker_its_instructions(self, client) -> None:
        execution_id = _start_via_api(client)
        client.post(
            f"/api/v1/executions/{execution_id}/assign",
            json={"node_id": "audit", "worker_id": "w-1"},
        )
        response = client.get(
            f"/api/v1/executions/{execution_id}/nodes/audit/run-context"
        )
        assert response.status_code == 200
        assert response.json()["worker_kind"] == "shell"

    def test_pause_resume_and_checkpoint_are_reachable_over_http(self, client) -> None:
        execution_id = _start_via_api(client)
        assert (
            client.post(
                f"/api/v1/executions/{execution_id}/checkpoints", json={"label": "start"}
            ).status_code
            == 200
        )
        assert (
            client.post(
                f"/api/v1/executions/{execution_id}/pause", json={"reason": "window"}
            ).status_code
            == 200
        )
        resumed = client.post(f"/api/v1/executions/{execution_id}/resume", json={})
        assert resumed.status_code == 200
        assert resumed.json()["execution"]["state"] == "running"

    def test_the_stream_and_ready_endpoints_answer_without_changing_anything(
        self, client
    ) -> None:
        execution_id = _start_via_api(client)
        assert client.get(f"/api/v1/executions/{execution_id}/ready").json()["ready"] == [
            "audit"
        ]
        assert client.get(f"/api/v1/executions/{execution_id}/stream").json()["progress"] == {
            "finished": 0,
            "total": 2,
        }
        assert client.get(f"/api/v1/executions/{execution_id}/reclaimable").json()["count"] == 0

    def test_listing_filters_by_mission(self, client) -> None:
        _start_via_api(client)
        assert client.get("/api/v1/executions?mission_id=M-1").json()["count"] == 1
        assert client.get("/api/v1/executions?mission_id=none").json()["count"] == 0

    def test_the_worker_registry_is_visible(self, client) -> None:
        response = client.get("/api/v1/executions/workers")
        assert response.status_code == 200
        assert response.json()["workers"][0]["worker_id"] == "w-1"

    def test_the_surface_is_versioned_and_documented(self, client) -> None:
        app = FastAPI()
        app.include_router(routes.router)
        schema = app.openapi()
        paths = list(schema["paths"])
        assert paths and all(p.startswith("/api/v1/executions") for p in paths)
        for path, operations in schema["paths"].items():
            for method, operation in operations.items():
                assert operation.get("summary"), f"{method} {path} has no summary"


# ----------------------------------------------------------------------
# Constitution compliance
# ----------------------------------------------------------------------


def _modules() -> list:
    root = pathlib.Path("backend/contexts/execution")
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
    permitted = (
        "backend.contracts", "backend.platform", "backend.contexts.execution",
        # Superseded (Phase 6.2, documenting Phase 5): ADR-044 put the durable
        # Core tables in backend.database.durable, deliberately outside the
        # declarative V1 registry; the context's SQL infrastructure is their
        # one sanctioned consumer. The rest of backend.database stays banned.
        "backend.database.durable",
    )
    offences = [
        f"{path}: {imported}"
        for path in _modules()
        for imported in _imports(path)
        if imported.startswith("backend.") and not imported.startswith(permitted)
    ]
    assert offences == [], offences


def test_the_context_imports_no_v1_module() -> None:
    forbidden = (
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
        and not imported.startswith("backend.database.durable")
    ]
    assert offences == [], offences


def test_the_domain_layer_does_no_io() -> None:
    banned = {"pathlib", "os", "socket", "requests", "httpx", "sqlite3", "json"}
    root = pathlib.Path("backend/contexts/execution/domain")
    offences = [
        f"{path}: {imported}"
        for path in root.rglob("*.py")
        if "__pycache__" not in path.parts
        for imported in _imports(path)
        if imported.split(".")[0] in banned
    ]
    assert offences == [], offences


def test_event_types_are_namespaced_and_disjoint() -> None:
    from backend.contexts.execution import EXECUTION_EVENT_TYPES
    from backend.contexts.intent import INTENT_EVENT_TYPES
    from backend.contexts.mission import MISSION_EVENT_TYPES
    from backend.contexts.planner import PLAN_EVENT_TYPES
    from backend.contexts.review import REVIEW_EVENT_TYPES
    from backend.contexts.workflow import WORKFLOW_EVENT_TYPES

    ours = {e.EVENT_TYPE for e in EXECUTION_EVENT_TYPES}
    assert all(e.startswith("execution.runtime.") for e in ours)
    assert len(ours) == len(EXECUTION_EVENT_TYPES)
    for other in (
        INTENT_EVENT_TYPES,
        MISSION_EVENT_TYPES,
        PLAN_EVENT_TYPES,
        REVIEW_EVENT_TYPES,
        WORKFLOW_EVENT_TYPES,
    ):
        assert ours.isdisjoint({e.EVENT_TYPE for e in other})


def test_the_route_module_does_not_import_a_second_context() -> None:
    path = pathlib.Path("backend/api/execution_routes.py")
    contexts = {
        imported.split(".")[2]
        for imported in _imports(path)
        if imported.startswith("backend.contexts.") and len(imported.split(".")) > 2
    }
    assert contexts == {"execution"}, contexts


def test_the_context_plans_nothing() -> None:
    # Execution runs a compiled graph. Anything that decides *what* the graph
    # should contain belongs to Planner or Workflow.
    banned = ("critical_path", "estimate", "risk_level", "decompose", "compile_graph")
    offences = [
        f"{path}: {marker}"
        for path in _modules()
        for marker in banned
        if marker in path.read_text(encoding="utf-8")
    ]
    assert offences == [], offences


def test_the_architecture_gate_still_passes() -> None:
    from backend.platform.architecture import analyze

    report = analyze()
    assert report.gate_passed, [str(v) for v in report.blocking_violations]


def test_direct_start_is_disabled_unless_explicitly_enabled(monkeypatch) -> None:
    """The one path that can start a run over unapproved work fails closed."""
    service = ExecutionService(repository=InMemoryExecutionRepository())
    monkeypatch.setattr(routes, "_service", service)
    monkeypatch.setattr(routes, "DIRECT_START_ENABLED", False)
    app = FastAPI()
    app.include_router(routes.router)
    response = TestClient(app).post(
        "/api/v1/executions",
        json={
            "workflow_id": "W-1",
            "workflow_digest": "anything-i-like",
            "mission_id": "M-1",
            "nodes": [{"node_id": "purge", "worker_kind": "shell"}],
        },
    )
    assert response.status_code == 403
    detail = response.json()["detail"]
    assert detail["error"] == "direct_start_disabled"
    assert detail["authoritative_path"] == "/api/v1/mission-control/executions"
