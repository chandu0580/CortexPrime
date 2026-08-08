"""Mission Control Plane handoff: approved workflow -> started run.

Mounted at ``/api/v1/mission-control``. This module imports the composition root
and neither bounded context directly -- the join stays in one greppable place.

Status codes:

``409`` — the workflow is not approved, or the mission has no approved workflow.
Running it would execute work nobody signed off, and that is a conflict about the
state of the artifact rather than a malformed request.

``400`` — nothing said which kind of worker runs a node. Phase 2 has no
capability routing, so this is answered by the caller, not guessed at here.
"""

from __future__ import annotations

from typing import Dict, Optional

from fastapi import APIRouter, HTTPException, Path, status
from pydantic import BaseModel, Field

from backend.api.execution_routes import _render as _render_execution
from backend.api.mission_control_composition import (
    ExplicitWorkerKinds,
    UnresolvedWorkerKind,
    WorkflowExecutionLauncher,
    WorkflowNotExecutable,
)
from backend.contracts.errors import ContractViolation
from backend.platform.context import ExecutionContext

router = APIRouter(prefix="/api/v1/mission-control", tags=["Mission Control Plane"])


def _launcher() -> WorkflowExecutionLauncher:
    # Both services are the process-wide instances the two route modules already
    # serve, so a workflow approved over the Workflow API is the one this reads.
    from backend.api import execution_routes, workflow_routes

    return WorkflowExecutionLauncher(
        workflows=workflow_routes._service, executions=execution_routes._service
    )


def _context() -> ExecutionContext:
    return ExecutionContext.platform_internal(
        reason="mission-control-handoff", component="mission-control", source="http"
    )


class LaunchIn(BaseModel):
    workflow_id: Optional[str] = Field(
        None, description="Run a named workflow. Give this or mission_id, not both."
    )
    mission_id: Optional[str] = Field(
        None, description="Run whichever approved workflow this mission has."
    )
    worker_kinds: Dict[str, str] = Field(
        default_factory=dict,
        description=(
            "node_id -> worker kind. Phase 2 has no capability routing, so this is "
            "stated rather than discovered; unresolved nodes are refused, not defaulted."
        ),
    )
    requested_by: str = "mission-runtime"


@router.post(
    "/executions",
    status_code=status.HTTP_201_CREATED,
    summary="Start a run from an approved workflow",
)
async def launch_route(payload: LaunchIn):
    try:
        result = _launcher().launch(
            _context(),
            mission_id=payload.mission_id,
            workflow_id=payload.workflow_id,
            resolver=ExplicitWorkerKinds(payload.worker_kinds),
            requested_by=payload.requested_by,
        )
    except WorkflowNotExecutable as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            {"error": "workflow_not_executable", "message": str(exc)},
        ) from exc
    except UnresolvedWorkerKind as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            {
                "error": "unresolved_worker_kind",
                "message": str(exc),
                "node_id": exc.node_id,
            },
        ) from exc
    except ContractViolation as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    return {
        "execution": _render_execution(result.execution),
        "events": list(result.event_types),
    }


@router.get(
    "/missions/{mission_id}/executable-workflow",
    summary="The approved workflow a run would be started from",
)
async def executable_workflow_route(mission_id: str = Path(...)):
    try:
        workflow = _launcher().executable_workflow(_context(), mission_id)
    except WorkflowNotExecutable as exc:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            {"error": "no_approved_workflow", "message": str(exc)},
        ) from exc

    return {
        "workflow_id": str(workflow.workflow_id),
        "version": workflow.version,
        "status": workflow.status.value,
        "digest": workflow.digest,
        "mission_id": workflow.mission_id,
        "plan_id": workflow.plan_id,
        "plan_digest": workflow.plan_digest,
        "approved_by": workflow.approved_by,
        "runnable_nodes": [
            n.node_id for n in workflow.nodes if n.kind.value != "compensation"
        ],
    }
