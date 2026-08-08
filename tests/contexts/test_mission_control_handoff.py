"""The Workflow -> Execution handoff at the composition root.

This is the seam the whole control plane narrows to: an approved workflow
becoming a run. The tests below are mostly about what must be *refused* there,
because everything downstream of this point touches production.
"""

from __future__ import annotations

import ast
import pathlib

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.mission_control_composition import (
    ExplicitWorkerKinds,
    UnresolvedWorkerKind,
    WorkerKindResolver,
    WorkflowExecutionLauncher,
    WorkflowNotExecutable,
)
from backend.contracts.errors import ContractViolation
from backend.contexts.execution import (
    AssignNode,
    CompleteExecution,
    ExecutionService,
    ExecutionState,
    InMemoryExecutionRepository,
    RecordSuccess,
    RegisterWorker,
)
from backend.contexts.workflow import (
    AddCompensation,
    AddEdge,
    AddNode,
    ApproveWorkflowCommand,
    CompileGraph,
    CompileWorkflow,
    GetWorkflow,
    InMemoryWorkflowRepository,
    SetWorkflowTimeout,
    ValidateWorkflow,
    WorkflowService,
)
from backend.platform.context import ExecutionContext


@pytest.fixture
def context() -> ExecutionContext:
    return ExecutionContext.platform_internal(
        reason="handoff-tests", component="tests", source="pytest"
    )


@pytest.fixture
def workflows() -> WorkflowService:
    return WorkflowService(repository=InMemoryWorkflowRepository())


@pytest.fixture
def executions() -> ExecutionService:
    service = ExecutionService(repository=InMemoryExecutionRepository())
    service.register_worker(RegisterWorker(worker_id="w-1", kinds=("shell",)))
    return service


@pytest.fixture
def launcher(workflows, executions) -> WorkflowExecutionLauncher:
    return WorkflowExecutionLauncher(workflows=workflows, executions=executions)


KINDS = ExplicitWorkerKinds({"audit": "shell", "resize": "shell"})


def _drafted(workflows, context, mission_id="M-1") -> str:
    workflow_id = str(
        workflows.compile_workflow(
            context,
            CompileWorkflow(
                plan_id="P-1",
                plan_digest="plan-digest",
                mission_id=mission_id,
                title="Rightsize instances",
                plan_task_ids=("audit", "resize"),
            ),
        ).workflow.workflow_id
    )
    workflows.add_node(
        context,
        AddNode(
            workflow_id=workflow_id,
            node_id="audit",
            purpose="list utilisation",
            plan_task_id="audit",
            timeout_seconds=60,
        ),
    )
    workflows.add_node(
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
    workflows.add_node(
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
    workflows.add_edge(
        context, AddEdge(workflow_id=workflow_id, from_node="audit", to_node="resize")
    )
    workflows.add_edge(
        context,
        AddEdge(
            workflow_id=workflow_id,
            from_node="resize",
            to_node="restore",
            kind="on_failure",
        ),
    )
    workflows.add_compensation(
        context,
        AddCompensation(
            workflow_id=workflow_id, compensates="resize", performed_by="restore"
        ),
    )
    workflows.set_timeout(
        context, SetWorkflowTimeout(workflow_id=workflow_id, seconds=600)
    )
    return workflow_id


def _approved(workflows, context, mission_id="M-1") -> str:
    workflow_id = _drafted(workflows, context, mission_id)
    workflows.validate(context, ValidateWorkflow(workflow_id=workflow_id))
    workflows.compile_graph(context, CompileGraph(workflow_id=workflow_id))
    workflows.approve(
        context, ApproveWorkflowCommand(workflow_id=workflow_id, approved_by="cto")
    )
    return workflow_id


class TestApprovalIsRequired:
    def test_an_unapproved_workflow_cannot_be_run(self, launcher, workflows, context):
        workflow_id = _drafted(workflows, context)
        with pytest.raises(WorkflowNotExecutable, match="not approved"):
            launcher.launch(context, workflow_id=workflow_id, resolver=KINDS)

    def test_a_validated_but_unapproved_workflow_cannot_be_run(
        self, launcher, workflows, context
    ):
        workflow_id = _drafted(workflows, context)
        workflows.validate(context, ValidateWorkflow(workflow_id=workflow_id))
        workflows.compile_graph(context, CompileGraph(workflow_id=workflow_id))
        with pytest.raises(WorkflowNotExecutable):
            launcher.launch(context, workflow_id=workflow_id, resolver=KINDS)

    def test_a_mission_with_no_approved_workflow_has_nothing_to_run(
        self, launcher, workflows, context
    ):
        _drafted(workflows, context)
        with pytest.raises(WorkflowNotExecutable, match="no approved workflow"):
            launcher.launch(context, mission_id="M-1", resolver=KINDS)

    def test_an_approved_workflow_runs(self, launcher, workflows, context):
        workflow_id = _approved(workflows, context)
        result = launcher.launch(context, workflow_id=workflow_id, resolver=KINDS)
        assert result.execution.state is ExecutionState.RUNNING


class TestDigestBinding:
    def test_the_run_carries_the_workflows_own_digest_not_a_callers_string(
        self, launcher, workflows, context
    ):
        workflow_id = _approved(workflows, context)
        result = launcher.launch(context, workflow_id=workflow_id, resolver=KINDS)
        approved = workflows.get(context, GetWorkflow(workflow_id=workflow_id))
        assert result.execution.workflow_digest == approved.digest
        assert result.execution.workflow_id == workflow_id

    def test_the_workflow_must_still_be_the_one_that_was_approved(
        self, launcher, workflows, context
    ):
        # verify_digest is what stands between "approved this" and "ran that".
        workflow_id = _approved(workflows, context)
        workflows.get(context, GetWorkflow(workflow_id=workflow_id)).verify_digest()
        launcher.launch(context, workflow_id=workflow_id, resolver=KINDS)

    def test_the_mission_identity_comes_from_the_workflow(
        self, launcher, workflows, context
    ):
        _approved(workflows, context, mission_id="M-42")
        result = launcher.launch(context, mission_id="M-42", resolver=KINDS)
        assert result.execution.mission_id == "M-42"


class TestProjection:
    def test_dependencies_are_derived_from_sequence_edges(
        self, launcher, workflows, context
    ):
        result = launcher.launch(
            context, workflow_id=_approved(workflows, context), resolver=KINDS
        )
        deps = {r.node_id: list(r.spec.depends_on) for r in result.execution.runs}
        assert deps == {"audit": [], "resize": ["audit"]}

    def test_a_failure_edge_is_not_a_dependency(self, launcher, workflows, context):
        # A node waiting on a failure edge waits for a failure a healthy run
        # never produces.
        result = launcher.launch(
            context, workflow_id=_approved(workflows, context), resolver=KINDS
        )
        assert result.execution.ready_nodes() == ("audit",)

    def test_compensation_nodes_are_not_projected_into_the_run(
        self, launcher, workflows, context
    ):
        result = launcher.launch(
            context, workflow_id=_approved(workflows, context), resolver=KINDS
        )
        assert {r.node_id for r in result.execution.runs} == {"audit", "resize"}

    def test_a_successful_run_can_actually_complete(
        self, launcher, workflows, executions, context
    ):
        # The reason compensation nodes are excluded: Execution requires every
        # node it was given to finish. A compensation node reachable only on
        # failure would leave every successful run permanently outstanding --
        # unable to complete and unable to fail.
        result = launcher.launch(
            context, workflow_id=_approved(workflows, context), resolver=KINDS
        )
        execution_id = str(result.execution.execution_id)
        for node_id in ("audit", "resize"):
            executions.assign(
                context,
                AssignNode(
                    execution_id=execution_id, node_id=node_id, worker_id="w-1"
                ),
            )
            executions.record_success(
                context,
                RecordSuccess(
                    execution_id=execution_id,
                    node_id=node_id,
                    worker_id="w-1",
                    execution_key=f"{node_id}-key",
                ),
            )
        done = executions.complete(
            context, CompleteExecution(execution_id=execution_id)
        )
        assert done.execution.state is ExecutionState.COMPLETED
        done.execution.verify_digest()

    def test_retry_and_idempotency_survive_the_projection(
        self, launcher, workflows, context
    ):
        result = launcher.launch(
            context, workflow_id=_approved(workflows, context), resolver=KINDS
        )
        resize = result.execution.run_for("resize")
        assert resize.spec.max_attempts == 2
        assert resize.spec.idempotency_key == "resize-key"
        assert resize.spec.mutates

    def test_timeouts_survive_the_projection(self, launcher, workflows, context):
        result = launcher.launch(
            context, workflow_id=_approved(workflows, context), resolver=KINDS
        )
        assert result.execution.run_for("audit").spec.timeout_seconds == 60


class TestWorkerKindPort:
    def test_a_node_with_no_resolved_worker_kind_is_refused_not_defaulted(
        self, launcher, workflows, context
    ):
        # Workflow describes how work should execute; it does not name a runtime
        # capability. Defaulting one here would hand real work to whatever
        # happened to be first in an enum. Capability routing is Phase 3.
        workflow_id = _approved(workflows, context)
        with pytest.raises(UnresolvedWorkerKind) as caught:
            launcher.launch(
                context,
                workflow_id=workflow_id,
                resolver=ExplicitWorkerKinds({"audit": "shell"}),
            )
        assert caught.value.node_id == "resize"

    def test_the_resolver_is_a_port_with_no_registry_behind_it(self):
        assert getattr(WorkerKindResolver, "_is_protocol", False)
        assert isinstance(ExplicitWorkerKinds({}), WorkerKindResolver)

    def test_naming_both_or_neither_target_is_refused(
        self, launcher, workflows, context
    ):
        workflow_id = _approved(workflows, context)
        with pytest.raises(ContractViolation):
            launcher.launch(
                context, workflow_id=workflow_id, mission_id="M-1", resolver=KINDS
            )
        with pytest.raises(ContractViolation):
            launcher.launch(context, resolver=KINDS)


class TestApi:
    @pytest.fixture
    def client(self, monkeypatch, workflows, executions) -> TestClient:
        from backend.api import execution_routes, workflow_routes, mission_control_routes

        monkeypatch.setattr(workflow_routes, "_service", workflows)
        monkeypatch.setattr(execution_routes, "_service", executions)
        app = FastAPI()
        app.include_router(mission_control_routes.router)
        return TestClient(app)

    def test_launching_an_unapproved_workflow_is_a_409(
        self, client, workflows, context
    ):
        workflow_id = _drafted(workflows, context)
        response = client.post(
            "/api/v1/mission-control/executions",
            json={"workflow_id": workflow_id, "worker_kinds": {"audit": "shell"}},
        )
        assert response.status_code == 409
        assert response.json()["detail"]["error"] == "workflow_not_executable"

    def test_launching_without_a_worker_kind_is_a_400_naming_the_node(
        self, client, workflows, context
    ):
        workflow_id = _approved(workflows, context)
        response = client.post(
            "/api/v1/mission-control/executions",
            json={"workflow_id": workflow_id, "worker_kinds": {"audit": "shell"}},
        )
        assert response.status_code == 400
        assert response.json()["detail"]["node_id"] == "resize"

    def test_launching_an_approved_workflow_is_a_201(self, client, workflows, context):
        workflow_id = _approved(workflows, context)
        response = client.post(
            "/api/v1/mission-control/executions",
            json={
                "workflow_id": workflow_id,
                "worker_kinds": {"audit": "shell", "resize": "shell"},
            },
        )
        assert response.status_code == 201, response.text
        body = response.json()["execution"]
        assert body["state"] == "running"
        assert body["ready_nodes"] == ["audit"]

    def test_the_executable_workflow_can_be_inspected_before_launching(
        self, client, workflows, context
    ):
        _approved(workflows, context)
        response = client.get(
            "/api/v1/mission-control/missions/M-1/executable-workflow"
        )
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "approved"
        assert body["digest"]
        assert body["runnable_nodes"] == ["audit", "resize"]

    def test_a_mission_with_nothing_approved_is_a_404(self, client, workflows, context):
        _drafted(workflows, context)
        response = client.get(
            "/api/v1/mission-control/missions/M-1/executable-workflow"
        )
        assert response.status_code == 404


def _imports(path: pathlib.Path) -> list:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: list = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.append(node.module)
    return found


def test_the_composition_root_is_the_only_module_joining_the_two_contexts() -> None:
    # If this starts failing, the coupling has stopped being greppable.
    joiners = []
    for path in pathlib.Path("backend").rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        imported = _imports(path)
        if any(i.startswith("backend.contexts.workflow") for i in imported) and any(
            i.startswith("backend.contexts.execution") for i in imported
        ):
            joiners.append(str(path).replace("\\", "/"))
    assert joiners == ["backend/api/mission_control_composition.py"], joiners


def test_neither_context_imports_the_other() -> None:
    for context_name, other in (("workflow", "execution"), ("execution", "workflow")):
        root = pathlib.Path(f"backend/contexts/{context_name}")
        offences = [
            f"{path}: {imported}"
            for path in root.rglob("*.py")
            if "__pycache__" not in path.parts
            for imported in _imports(path)
            if imported.startswith(f"backend.contexts.{other}")
        ]
        assert offences == [], offences


def test_the_handoff_builds_no_phase_three_capability_machinery() -> None:
    # A port is permitted here. An implementation behind it is not.
    banned = (
        "CapabilityRegistry",
        "ToolRegistry",
        "ConnectorRegistry",
        "WorkerFleet",
        "subprocess",
        "docker",
        "kubernetes",
        "boto3",
    )
    source = pathlib.Path("backend/api/mission_control_composition.py").read_text(
        encoding="utf-8"
    )
    assert [marker for marker in banned if marker in source] == []
