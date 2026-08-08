"""Workflow Runtime REST API.

Translation only. Every rule lives in the Workflow context.

Mounted at ``/api/v1/workflows``.

Status codes:

``409`` — the workflow is approved or superseded, the node id is taken, or the
move is illegal for the state it is in.

``422`` — policy refused, or the workflow is incomplete. Findings travel in the
body; for a graph this matters more than elsewhere, because a workflow can have
an unreachable node *and* an uncompensated mutation *and* an unmeetable deadline.

``400`` — a value this context refuses on principle: a cycle, an unreachable
node, a dependent parallel group, an unmeetable timeout, a retry on a
non-idempotent action.

``404`` — no such workflow or node.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Path, Query, status
from pydantic import BaseModel, Field

from backend.contracts.errors import ContractViolation
from backend.contexts.workflow import (
    AddBranch,
    AddCompensation,
    AddEdge,
    AddNode,
    AddParallelGroup,
    AddResumePoint,
    ApproveWorkflowCommand,
    BranchTooNarrow,
    BranchWithoutDefault,
    CompensationTargetInvalid,
    CompileGraph,
    CompileWorkflow,
    ConditionNotUpstream,
    CyclicWorkflow,
    DanglingEdge,
    DuplicateNode,
    GetGraph,
    GetWorkflow,
    IllegalWorkflowTransition,
    InMemoryWorkflowRepository,
    IncompleteWorkflow,
    ListWorkflows,
    ParallelGroupTooSmall,
    ParallelMembersDependent,
    RemoveNode,
    ResumePointInsideGroup,
    RetryWithoutIdempotency,
    ReviseWorkflow,
    SetWorkflowTimeout,
    TaskInvented,
    TaskNotCovered,
    TimeoutUnsatisfiable,
    UnknownNode,
    UnreachableNode,
    ValidateWorkflow,
    WorkflowApprovedError,
    WorkflowIsSuperseded,
    WorkflowNotFound,
    WorkflowRefused,
    WorkflowService,
)
from backend.platform.context import ExecutionContext

router = APIRouter(prefix="/api/v1/workflows", tags=["Workflow Runtime"])

_service = WorkflowService(repository=InMemoryWorkflowRepository())


def _context() -> ExecutionContext:
    return ExecutionContext.platform_internal(
        reason="workflow-runtime-api", component="workflow-runtime", source="http"
    )


# ----------------------------------------------------------------------
# Schemas
# ----------------------------------------------------------------------

_NODE_KIND = "^(task|branch|parallel|join|compensation)$"
_SIDE_EFFECT = "^(read|reversible_write|irreversible_write|destructive)$"
_EDGE_KIND = "^(normal|on_failure|compensating)$"
_CONDITION = "^(always|on_success|on_failure|on_output)$"
_JOIN = "^(all|any|quorum)$"
_BACKOFF = "^(none|fixed|exponential)$"
_ON_TIMEOUT = "^(fail|compensate|cancel)$"
_TRIGGER = "^(on_failure|on_timeout|on_cancel|always)$"
_STATUS = "^(draft|validated|compiled|approved|superseded)$"


class CompileIn(BaseModel):
    plan_id: str
    plan_digest: str = Field(
        ..., description="Binds the workflow to the plan that was actually approved"
    )
    mission_id: str
    title: str
    plan_task_ids: List[str] = Field(
        ..., min_length=1, description="Every task the plan authorised"
    )
    compiled_by: str = "workflow-runtime"


class NodeIn(BaseModel):
    node_id: str = Field(..., description="A readable id; edges name it")
    purpose: str
    kind: str = Field("task", pattern=_NODE_KIND)
    plan_task_id: Optional[str] = None
    side_effect: str = Field("read", pattern=_SIDE_EFFECT)
    max_attempts: int = Field(1, ge=1)
    backoff: str = Field("none", pattern=_BACKOFF)
    initial_delay_seconds: int = Field(0, ge=0)
    idempotency_key: Optional[str] = None
    timeout_seconds: Optional[int] = Field(None, ge=1)
    on_timeout: str = Field("fail", pattern=_ON_TIMEOUT)
    compensates: Optional[str] = None
    cancellable: bool = True
    execution_key: Optional[str] = None


class EdgeIn(BaseModel):
    from_node: str
    to_node: str
    kind: str = Field("normal", pattern=_EDGE_KIND)
    condition_kind: str = Field("always", pattern=_CONDITION)
    condition_source: Optional[str] = None
    condition_expression: Optional[str] = None
    label: str = ""


class BranchIn(BaseModel):
    node_id: str
    purpose: str
    arms: List[Dict[str, Any]] = Field(..., min_length=2)


class ParallelGroupIn(BaseModel):
    label: str
    members: List[str] = Field(..., min_length=2)
    join: str = Field("all", pattern=_JOIN)
    quorum: Optional[int] = Field(None, ge=1)
    max_concurrency: Optional[int] = Field(None, ge=2)


class CompensationIn(BaseModel):
    compensates: str
    performed_by: str
    trigger: str = Field("on_failure", pattern=_TRIGGER)


class ResumePointIn(BaseModel):
    node_id: str
    label: str = ""


class TimeoutIn(BaseModel):
    seconds: int = Field(..., ge=1)
    on_timeout: str = Field("fail", pattern=_ON_TIMEOUT)
    grace_seconds: int = Field(0, ge=0)


class ApproveIn(BaseModel):
    approved_by: str


class ReviseIn(BaseModel):
    reason: str = "a revised version replaces this one"


# ----------------------------------------------------------------------
# Rendering
# ----------------------------------------------------------------------


def _render(workflow) -> dict:
    graph = workflow.graph if workflow.nodes else None
    needed, path = workflow.critical_path() if workflow.nodes else (0, ())
    return {
        "workflow_id": str(workflow.workflow_id),
        "version": workflow.version,
        "plan_id": workflow.plan_id,
        "plan_digest": workflow.plan_digest,
        "mission_id": workflow.mission_id,
        "title": workflow.title,
        "status": workflow.status.value,
        "permitted_transitions": list(workflow.permitted_transitions()),
        "is_executable": workflow.is_executable,
        "missing_elements": list(workflow.missing_elements),
        "plan_task_ids": sorted(workflow.plan_task_ids),
        "uncovered_plan_tasks": list(workflow.uncovered_plan_tasks),
        "invented_tasks": list(workflow.invented_tasks),
        "nodes": [
            {
                "node_id": n.node_id,
                "kind": n.kind.value,
                "purpose": n.purpose,
                "plan_task_id": n.plan_task_id,
                "side_effect": n.side_effect.value,
                "mutates": n.mutates,
                "compensates": n.compensates,
                "cancellable": n.cancellable,
                "retry": {
                    "max_attempts": n.retry.max_attempts,
                    "backoff": n.retry.backoff.value,
                    "idempotency_key": n.retry.idempotency_key,
                },
                "timeout_seconds": n.timeout.total_seconds if n.timeout else None,
                "worst_case_seconds": n.worst_case_seconds,
                "arms": [
                    {"to_node": a.to_node, "condition": str(a.condition)} for a in n.arms
                ],
            }
            for n in workflow.nodes
        ],
        "edges": [
            {
                "from": e.from_node,
                "to": e.to_node,
                "kind": e.kind.value,
                "condition": str(e.condition),
            }
            for e in workflow.edges
        ],
        "parallel_groups": [
            {
                "group_id": str(g.group_id),
                "label": g.label,
                "members": list(g.members),
                "join": g.join.value,
                "quorum": g.quorum,
                "effective_concurrency": g.effective_concurrency,
            }
            for g in workflow.parallel_groups
        ],
        "compensations": [
            {
                "compensates": c.compensates,
                "performed_by": c.performed_by,
                "trigger": c.trigger,
            }
            for c in workflow.compensations
        ],
        "uncompensated_mutations": list(workflow.uncompensated_mutations),
        "resume_points": [p.node_id for p in workflow.resume_points],
        "workflow_timeout_seconds": (
            workflow.workflow_timeout.total_seconds if workflow.workflow_timeout else None
        ),
        "critical_path": {"seconds": needed, "path": list(path)},
        "graph": (
            {
                "depth": graph.depth,
                "widest_layer": graph.widest_layer,
                "entry_points": list(graph.entry_points),
                "exit_points": list(graph.exit_points),
                "layers": [list(layer) for layer in graph.layers()],
            }
            if graph
            else None
        ),
        "execution_order": list(workflow.execution_order),
        "compensation_order": list(workflow.compensation_order),
        "approved_by": workflow.approved_by,
        "digest": workflow.digest,
        "supersedes": str(workflow.supersedes) if workflow.supersedes else None,
        "superseded_by": str(workflow.superseded_by) if workflow.superseded_by else None,
    }


def _handle(operation):
    try:
        return operation()
    except (WorkflowNotFound, UnknownNode) as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except WorkflowRefused as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            {
                "error": "workflow_refused",
                "message": str(exc),
                "target": exc.target,
                "failures": [
                    {"rule": f.rule, "detail": f.detail, "subject": f.subject}
                    for f in exc.failures
                ],
            },
        ) from exc
    except IncompleteWorkflow as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            {
                "error": "incomplete_workflow",
                "message": str(exc),
                "missing": list(exc.missing),
            },
        ) from exc
    except CyclicWorkflow as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            {"error": "cyclic_workflow", "message": str(exc), "cycle": list(exc.cycle)},
        ) from exc
    except UnreachableNode as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            {
                "error": "unreachable_node",
                "message": str(exc),
                "unreachable": list(exc.unreachable),
            },
        ) from exc
    except DanglingEdge as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            {"error": "dangling_edge", "message": str(exc), "missing": list(exc.missing)},
        ) from exc
    except TimeoutUnsatisfiable as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            {
                "error": "timeout_unsatisfiable",
                "message": str(exc),
                "workflow_timeout": exc.workflow_timeout,
                "critical_path": exc.critical_path,
                "path": list(exc.path),
            },
        ) from exc
    except ParallelMembersDependent as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            {
                "error": "parallel_members_dependent",
                "message": str(exc),
                "dependent": exc.dependent,
                "depends_on": exc.depends_on,
            },
        ) from exc
    except RetryWithoutIdempotency as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            {
                "error": "retry_without_idempotency",
                "message": str(exc),
                "node_id": exc.node_id,
            },
        ) from exc
    except (TaskNotCovered, TaskInvented) as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            {"error": "plan_coverage", "message": str(exc)},
        ) from exc
    except (
        ConditionNotUpstream,
        BranchWithoutDefault,
        BranchTooNarrow,
        ParallelGroupTooSmall,
        CompensationTargetInvalid,
        ResumePointInsideGroup,
    ) as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            {"error": "invalid_control_flow", "message": str(exc)},
        ) from exc
    except IllegalWorkflowTransition as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            {
                "error": "illegal_transition",
                "message": str(exc),
                "source": exc.source,
                "target": exc.target,
                "permitted": list(exc.permitted),
            },
        ) from exc
    except (WorkflowApprovedError, WorkflowIsSuperseded, DuplicateNode) as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    except ContractViolation as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc


# ----------------------------------------------------------------------
# Routes
# ----------------------------------------------------------------------


@router.post("", status_code=status.HTTP_201_CREATED, summary="Open a workflow for a plan")
async def compile_route(payload: CompileIn):
    def run():
        result = _service.compile_workflow(
            _context(),
            CompileWorkflow(
                plan_id=payload.plan_id,
                plan_digest=payload.plan_digest,
                mission_id=payload.mission_id,
                title=payload.title,
                plan_task_ids=tuple(payload.plan_task_ids),
                compiled_by=payload.compiled_by,
            ),
        )
        return {"workflow": _render(result.workflow), "events": list(result.event_types)}

    return _handle(run)


@router.get("", summary="List workflows")
async def list_route(
    plan_id: Optional[str] = Query(None),
    mission_id: Optional[str] = Query(None),
    workflow_status: Optional[str] = Query(None, alias="status"),
    executable_only: bool = Query(False),
):
    def run():
        found = _service.list(
            _context(),
            ListWorkflows(
                plan_id=plan_id,
                mission_id=mission_id,
                status=workflow_status,
                executable_only=executable_only,
            ),
        )
        return {"count": len(found), "workflows": [_render(w) for w in found]}

    return _handle(run)


@router.get("/{workflow_id}", summary="Fetch a workflow")
async def get_route(workflow_id: str = Path(...)):
    return _handle(
        lambda: _render(_service.get(_context(), GetWorkflow(workflow_id=workflow_id)))
    )


@router.get("/{workflow_id}/graph", summary="The control-flow graph")
async def graph_route(workflow_id: str = Path(...)):
    def run():
        graph = _service.graph(_context(), GetGraph(workflow_id=workflow_id))
        return {
            "nodes": list(graph.nodes),
            "depth": graph.depth,
            "widest_layer": graph.widest_layer,
            "entry_points": list(graph.entry_points),
            "exit_points": list(graph.exit_points),
            "layers": [list(layer) for layer in graph.layers()],
            "forward_reachable": list(graph.forward_reachable),
        }

    return _handle(run)


@router.get("/{workflow_id}/policy", summary="Run workflow policy without transitioning")
async def policy_route(
    workflow_id: str = Path(...),
    to_status: str = Query("validated", pattern=_STATUS),
):
    def run():
        report = _service.evaluate(_context(), workflow_id, to_status)
        return {
            "to_status": to_status,
            "may_proceed": report.may_proceed,
            "blocking": [
                {"rule": f.rule, "detail": f.detail, "subject": f.subject}
                for f in report.blocking
            ],
            "advisory": [
                {"rule": f.rule, "detail": f.detail, "subject": f.subject}
                for f in report.advisory
            ],
        }

    return _handle(run)


@router.post("/{workflow_id}/nodes", summary="Add a node")
async def add_node_route(payload: NodeIn, workflow_id: str = Path(...)):
    def run():
        result = _service.add_node(
            _context(),
            AddNode(
                workflow_id=workflow_id,
                node_id=payload.node_id,
                purpose=payload.purpose,
                kind=payload.kind,
                plan_task_id=payload.plan_task_id,
                side_effect=payload.side_effect,
                max_attempts=payload.max_attempts,
                backoff=payload.backoff,
                initial_delay_seconds=payload.initial_delay_seconds,
                idempotency_key=payload.idempotency_key,
                timeout_seconds=payload.timeout_seconds,
                on_timeout=payload.on_timeout,
                compensates=payload.compensates,
                cancellable=payload.cancellable,
                execution_key=payload.execution_key,
            ),
        )
        return {"workflow": _render(result.workflow), "events": list(result.event_types)}

    return _handle(run)


@router.delete("/{workflow_id}/nodes/{node_id}", summary="Remove a node")
async def remove_node_route(workflow_id: str = Path(...), node_id: str = Path(...)):
    def run():
        result = _service.remove_node(
            _context(), RemoveNode(workflow_id=workflow_id, node_id=node_id)
        )
        return {"workflow": _render(result.workflow)}

    return _handle(run)


@router.post("/{workflow_id}/edges", summary="Connect two nodes")
async def add_edge_route(payload: EdgeIn, workflow_id: str = Path(...)):
    def run():
        result = _service.add_edge(
            _context(),
            AddEdge(
                workflow_id=workflow_id,
                from_node=payload.from_node,
                to_node=payload.to_node,
                kind=payload.kind,
                condition_kind=payload.condition_kind,
                condition_source=payload.condition_source,
                condition_expression=payload.condition_expression,
                label=payload.label,
            ),
        )
        return {"workflow": _render(result.workflow)}

    return _handle(run)


@router.post("/{workflow_id}/branches", summary="Add a decision point")
async def add_branch_route(payload: BranchIn, workflow_id: str = Path(...)):
    def run():
        result = _service.add_branch(
            _context(),
            AddBranch(
                workflow_id=workflow_id,
                node_id=payload.node_id,
                purpose=payload.purpose,
                arms=tuple(payload.arms),
            ),
        )
        return {"workflow": _render(result.workflow), "events": list(result.event_types)}

    return _handle(run)


@router.post("/{workflow_id}/parallel-groups", summary="Declare a fan-out")
async def add_group_route(payload: ParallelGroupIn, workflow_id: str = Path(...)):
    def run():
        result = _service.add_parallel_group(
            _context(),
            AddParallelGroup(
                workflow_id=workflow_id,
                label=payload.label,
                members=tuple(payload.members),
                join=payload.join,
                quorum=payload.quorum,
                max_concurrency=payload.max_concurrency,
            ),
        )
        return {"workflow": _render(result.workflow), "events": list(result.event_types)}

    return _handle(run)


@router.post("/{workflow_id}/compensations", summary="Declare a walk-back")
async def add_compensation_route(payload: CompensationIn, workflow_id: str = Path(...)):
    def run():
        result = _service.add_compensation(
            _context(),
            AddCompensation(
                workflow_id=workflow_id,
                compensates=payload.compensates,
                performed_by=payload.performed_by,
                trigger=payload.trigger,
            ),
        )
        return {"workflow": _render(result.workflow)}

    return _handle(run)


@router.post("/{workflow_id}/resume-points", summary="Mark a resumption point")
async def add_resume_point_route(payload: ResumePointIn, workflow_id: str = Path(...)):
    def run():
        result = _service.add_resume_point(
            _context(),
            AddResumePoint(
                workflow_id=workflow_id, node_id=payload.node_id, label=payload.label
            ),
        )
        return {"workflow": _render(result.workflow)}

    return _handle(run)


@router.put("/{workflow_id}/timeout", summary="Set the workflow deadline")
async def set_timeout_route(payload: TimeoutIn, workflow_id: str = Path(...)):
    def run():
        result = _service.set_timeout(
            _context(),
            SetWorkflowTimeout(
                workflow_id=workflow_id,
                seconds=payload.seconds,
                on_timeout=payload.on_timeout,
                grace_seconds=payload.grace_seconds,
            ),
        )
        return {"workflow": _render(result.workflow)}

    return _handle(run)


@router.post("/{workflow_id}/validate", summary="Check the graph is well-formed")
async def validate_route(workflow_id: str = Path(...)):
    def run():
        result = _service.validate(_context(), ValidateWorkflow(workflow_id=workflow_id))
        return {"workflow": _render(result.workflow), "events": list(result.event_types)}

    return _handle(run)


@router.post("/{workflow_id}/compile", summary="Freeze the execution order and bind the digest")
async def compile_graph_route(workflow_id: str = Path(...)):
    def run():
        result = _service.compile_graph(_context(), CompileGraph(workflow_id=workflow_id))
        return {"workflow": _render(result.workflow), "events": list(result.event_types)}

    return _handle(run)


@router.post("/{workflow_id}/approve", summary="Authorise the workflow for execution")
async def approve_route(payload: ApproveIn, workflow_id: str = Path(...)):
    def run():
        result = _service.approve(
            _context(),
            ApproveWorkflowCommand(
                workflow_id=workflow_id, approved_by=payload.approved_by
            ),
        )
        return {"workflow": _render(result.workflow), "events": list(result.event_types)}

    return _handle(run)


@router.post("/{workflow_id}/revise", summary="Open the next version")
async def revise_route(payload: ReviseIn, workflow_id: str = Path(...)):
    def run():
        result = _service.revise(
            _context(), ReviseWorkflow(workflow_id=workflow_id, reason=payload.reason)
        )
        return {"workflow": _render(result.workflow), "events": list(result.event_types)}

    return _handle(run)
