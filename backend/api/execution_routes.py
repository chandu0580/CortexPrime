"""Execution Runtime REST API.

Translation only. Every rule lives in the Execution context.

Mounted at ``/api/v1/executions``. Deliberately distinct from V1's execution
modules; the two coexist while the strangler migration runs.

Status codes:

``409`` — the run is finished, the node is already leased, a result was offered
without the lease, or the move is illegal for the state the run is in. These are
the conflicts that matter most here: they are what a second worker gets.

``422`` — policy refused. Findings travel in the body.

``400`` — a value this context refuses on principle: dispatching a node whose
dependencies are unsatisfied, retrying an ambiguous mutation with no idempotency
key, offering a node to a worker that cannot run it.

``404`` — no such execution, node, or worker.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Path, Query, status
from pydantic import BaseModel, Field

from backend.contracts.errors import ContractViolation
from backend.contexts.execution import (
    AmbiguousRetry,
    AssignNode,
    AttemptsExhausted,
    CancelExecution,
    CheckpointAhead,
    CompensateNode,
    CompleteExecution,
    CreateCheckpoint,
    DependenciesUnsatisfied,
    ExecutionFinished,
    ExecutionNotFound,
    ExecutionRefused,
    ExecutionService,
    FailExecution,
    Heartbeat,
    PlanRecovery,
    ReplayExecution,
    RetryRefused,
    profile_for,
    GetExecution,
    GetReadyNodes,
    IllegalExecutionTransition,
    IllegalNodeTransition,
    InMemoryExecutionOutbox,
    InMemoryExecutionRepository,
    IncompleteExecution,
    LeaseExpired,
    LeaseNotHeld,
    ListExecutions,
    NoCheckpoint,
    NodeAlreadyLeased,
    NodeNotRunning,
    PauseExecution,
    ReclaimNode,
    RecordFailure,
    RecordSuccess,
    RegisterWorker,
    ResumeExecution,
    RetryNode,
    SkipNode,
    StartExecution,
    TimeOutExecution,
    UnknownNode,
    UnknownWorker,
    WorkerCannotRun,
)
from backend.platform.context import ExecutionContext

router = APIRouter(prefix="/api/v1/executions", tags=["Execution Runtime"])

_service = ExecutionService(
    repository=InMemoryExecutionRepository(), outbox=InMemoryExecutionOutbox()
)

# ---------------------------------------------------------------------------
# The direct-start trust boundary
# ---------------------------------------------------------------------------
#
# ``POST /api/v1/executions`` takes a workflow id, a workflow digest and a node
# list from whoever calls it. Nothing here can check that the digest names a real
# workflow, that the workflow was approved, or that the nodes are the ones that
# were approved -- this module may not import the Workflow context, and that
# restriction is correct.
#
# So this route is the one path in the platform that can start a run over work
# nobody signed off. The authoritative path is
# ``POST /api/v1/mission-control/executions``, which loads the workflow, requires
# APPROVED, verifies the digest, and derives the nodes (ADR-030).
#
# It is kept rather than deleted because it is a genuine internal surface: it is
# how the runtime is exercised without standing up a whole control plane. It is
# **disabled by default** so that keeping it costs nothing in production --
# security fails closed, and an operator who wants it must say so.
DIRECT_START_ENABLED = os.getenv("CORTEXPRIME_ALLOW_DIRECT_EXECUTION_START") == "1"


def _context() -> ExecutionContext:
    return ExecutionContext.platform_internal(
        reason="execution-runtime-api", component="execution-runtime", source="http"
    )


# ----------------------------------------------------------------------
# Schemas
# ----------------------------------------------------------------------

_WORKER_KIND = "^(shell|python|http|git|database|docker|kubernetes|terraform|browser)$"
_SIDE_EFFECT = "^(read|reversible_write|irreversible_write|destructive)$"
_STATE = "^(pending|running|paused|completed|failed|cancelled|timed_out)$"


class NodeIn(BaseModel):
    node_id: str
    worker_kind: str = Field(..., pattern=_WORKER_KIND)
    depends_on: List[str] = Field(default_factory=list)
    side_effect: str = Field("read", pattern=_SIDE_EFFECT)
    max_attempts: int = Field(1, ge=1)
    timeout_seconds: Optional[int] = Field(None, ge=1)
    idempotency_key: Optional[str] = None
    compensates: Optional[str] = None
    cancellable: bool = True
    execution_key: Optional[str] = None


class StartIn(BaseModel):
    workflow_id: str
    workflow_digest: str = Field(
        ..., description="Binds the run to the exact compiled graph it executes"
    )
    mission_id: str
    nodes: List[NodeIn] = Field(..., min_length=1)
    attempt: int = Field(1, ge=1)
    requested_by: str = "mission-runtime"


class WorkerIn(BaseModel):
    worker_id: str
    kinds: List[str] = Field(..., min_length=1)
    max_concurrent: int = Field(1, ge=1)
    lease_seconds: int = Field(300, ge=1)
    labels: List[str] = Field(default_factory=list)


class AssignIn(BaseModel):
    node_id: str
    worker_id: str


class SuccessIn(BaseModel):
    node_id: str
    worker_id: str = Field(
        ..., description="Checked against the lease; a result without it is refused"
    )
    execution_key: str
    detail: Optional[Dict[str, Any]] = None


_FAILURE_CLASS = (
    "^(validation_failure|authorization_failure|transient_failure|permanent_failure"
    "|timeout|cancellation|worker_failure|network_failure|external_system_failure"
    "|unknown_outcome|concurrency_conflict|policy_refusal|recovery_required)$"
)


class FailureIn(BaseModel):
    node_id: str
    worker_id: str
    reason: str
    execution_key: Optional[str] = None
    failure_class: str = Field("transient_failure", pattern=_FAILURE_CLASS)
    failure_source: Optional[str] = None


class HeartbeatIn(BaseModel):
    node_id: str
    worker_id: str


class NodeRefIn(BaseModel):
    node_id: str


class SkipIn(BaseModel):
    node_id: str
    reason: str


class CheckpointIn(BaseModel):
    label: str
    payload_ref: Optional[str] = None
    recorded_by: str = "execution-runtime"


class ReasonIn(BaseModel):
    reason: str


class CancelIn(BaseModel):
    reason: str
    cancelled_by: str = "operator"


class ResumeIn(BaseModel):
    from_checkpoint: Optional[str] = None


class TimeoutIn(BaseModel):
    deadline_seconds: int = Field(0, ge=0)


# ----------------------------------------------------------------------
# Rendering
# ----------------------------------------------------------------------


def _render(execution) -> dict:
    finished, total = execution.progress
    return {
        "execution_id": str(execution.execution_id),
        "workflow_id": execution.workflow_id,
        "workflow_digest": execution.workflow_digest,
        "mission_id": execution.mission_id,
        "attempt": execution.attempt,
        "state": execution.state.value,
        "permitted_transitions": list(execution.permitted_transitions()),
        "progress": {"finished": finished, "total": total},
        "ready_nodes": list(execution.ready_nodes()),
        "leased_nodes": list(execution.leased_nodes),
        "ambiguous_nodes": list(execution.ambiguous_nodes),
        "failed_nodes": list(execution.failed_nodes),
        "blocked_nodes": list(execution.blocked_nodes()),
        "outstanding_nodes": list(execution.outstanding_nodes),
        "mutated_nodes": list(execution.mutated_nodes),
        "nodes": [
            {
                "node_id": r.node_id,
                "state": r.state.value,
                "worker_kind": r.spec.worker_kind.value,
                "side_effect": r.spec.side_effect.value,
                "mutates": r.spec.mutates,
                "idempotent": r.spec.is_idempotent,
                "depends_on": list(r.spec.depends_on),
                "attempts": r.attempt_count,
                "attempts_remaining": r.attempts_remaining,
                "held_by": r.held_by,
                "skipped_reason": r.skipped_reason,
            }
            for r in sorted(execution.runs, key=lambda r: r.node_id)
        ],
        "checkpoints": [
            {
                "checkpoint_id": str(c.checkpoint_id),
                "sequence": c.sequence,
                "label": c.label,
                "finished_nodes": sorted(c.finished_nodes),
                "digest": c.digest,
            }
            for c in execution.checkpoints
        ],
        "published_results": [
            {"node_id": node_id, "status": published.value}
            for node_id, published in execution.published_results()
        ],
        "outcome_note": execution.outcome_note,
        "digest": execution.digest,
        "resumed_from": execution.resumed_from,
    }


def _handle(operation):
    try:
        return operation()
    except (ExecutionNotFound, UnknownNode, UnknownWorker) as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except ExecutionRefused as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            {
                "error": "execution_refused",
                "message": str(exc),
                "target": exc.target,
                "failures": [
                    {"rule": f.rule, "detail": f.detail, "subject": f.subject}
                    for f in exc.failures
                ],
            },
        ) from exc
    except IncompleteExecution as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            {
                "error": "incomplete_execution",
                "message": str(exc),
                "outstanding": list(exc.outstanding),
            },
        ) from exc
    except LeaseNotHeld as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            {
                "error": "lease_not_held",
                "message": str(exc),
                "node_id": exc.node_id,
                "held_by": exc.held_by,
            },
        ) from exc
    except NodeAlreadyLeased as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            {
                "error": "node_already_leased",
                "message": str(exc),
                "held_by": exc.held_by,
            },
        ) from exc
    except LeaseExpired as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            {"error": "lease_expired", "message": str(exc), "node_id": exc.node_id},
        ) from exc
    except RetryRefused as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            {
                "error": "retry_refused",
                "message": str(exc),
                "node_id": exc.node_id,
                "verdict": exc.verdict,
                "reason": exc.reason,
            },
        ) from exc
    except (ExecutionFinished, NodeNotRunning) as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    except IllegalExecutionTransition as exc:
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
    except IllegalNodeTransition as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    except DependenciesUnsatisfied as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            {
                "error": "dependencies_unsatisfied",
                "message": str(exc),
                "waiting_on": list(exc.waiting_on),
            },
        ) from exc
    except AmbiguousRetry as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            {
                "error": "ambiguous_retry",
                "message": str(exc),
                "node_id": exc.node_id,
            },
        ) from exc
    except WorkerCannotRun as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            {
                "error": "worker_cannot_run",
                "message": str(exc),
                "needs": exc.needs,
                "has": list(exc.has),
            },
        ) from exc
    except (AttemptsExhausted, NoCheckpoint, CheckpointAhead) as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            {"error": "execution_refused_value", "message": str(exc)},
        ) from exc
    except ContractViolation as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc


# ----------------------------------------------------------------------
# Workers
# ----------------------------------------------------------------------


@router.post("/workers", summary="Register a worker and what it can run")
async def register_worker_route(payload: WorkerIn):
    def run():
        registration = _service.register_worker(
            RegisterWorker(
                worker_id=payload.worker_id,
                kinds=tuple(payload.kinds),
                max_concurrent=payload.max_concurrent,
                lease_seconds=payload.lease_seconds,
                labels=tuple(payload.labels),
            )
        )
        return {
            "worker_id": registration.worker_id,
            "kinds": sorted(k.value for k in registration.kinds),
            "lease_seconds": registration.lease_seconds,
            "health": registration.health.value,
        }

    return _handle(run)


@router.get("/workers", summary="The worker pool")
async def list_workers_route():
    return {
        "count": len(_service.pool),
        "workers": [
            {
                "worker_id": w.worker_id,
                "kinds": sorted(k.value for k in w.kinds),
                "health": w.health.value,
                "max_concurrent": w.max_concurrent,
            }
            for w in _service.pool.all()
        ],
    }


# ----------------------------------------------------------------------
# Runs
# ----------------------------------------------------------------------


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Start a run directly (internal; disabled by default)",
)
async def start_route(payload: StartIn):
    if not DIRECT_START_ENABLED:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            {
                "error": "direct_start_disabled",
                "message": (
                    "starting a run from a caller-supplied workflow digest and node "
                    "list bypasses workflow approval. Use POST "
                    "/api/v1/mission-control/executions, which requires an approved "
                    "workflow and derives the nodes from it"
                ),
                "authoritative_path": "/api/v1/mission-control/executions",
            },
        )

    def run():
        result = _service.start(
            _context(),
            StartExecution(
                workflow_id=payload.workflow_id,
                workflow_digest=payload.workflow_digest,
                mission_id=payload.mission_id,
                nodes=tuple(node.model_dump() for node in payload.nodes),
                attempt=payload.attempt,
                requested_by=payload.requested_by,
            ),
        )
        return {"execution": _render(result.execution), "events": list(result.event_types)}

    return _handle(run)


@router.get("", summary="List runs")
async def list_route(
    mission_id: Optional[str] = Query(None),
    workflow_id: Optional[str] = Query(None),
    execution_state: Optional[str] = Query(None, alias="state"),
    live_only: bool = Query(False),
):
    def run():
        found = _service.list(
            _context(),
            ListExecutions(
                mission_id=mission_id,
                workflow_id=workflow_id,
                state=execution_state,
                live_only=live_only,
            ),
        )
        return {"count": len(found), "executions": [_render(e) for e in found]}

    return _handle(run)


@router.get("/{execution_id}", summary="Fetch a run")
async def get_route(execution_id: str = Path(...)):
    return _handle(
        lambda: _render(_service.get(_context(), GetExecution(execution_id=execution_id)))
    )


@router.get("/{execution_id}/stream", summary="A snapshot shaped for streaming")
async def stream_route(execution_id: str = Path(...)):
    return _handle(lambda: _service.stream_state(_context(), execution_id))


@router.get("/{execution_id}/ready", summary="What could be dispatched now")
async def ready_route(execution_id: str = Path(...)):
    def run():
        ready = _service.ready_nodes(_context(), GetReadyNodes(execution_id=execution_id))
        return {"count": len(ready), "ready": list(ready)}

    return _handle(run)


@router.get("/{execution_id}/reclaimable", summary="Nodes whose leases have lapsed")
async def reclaimable_route(execution_id: str = Path(...)):
    def run():
        nodes = _service.reclaimable(_context(), execution_id)
        return {"count": len(nodes), "reclaimable": list(nodes)}

    return _handle(run)


@router.get("/{execution_id}/policy", summary="Run execution policy without moving")
async def policy_route(
    execution_id: str = Path(...), to_state: str = Query("completed", pattern=_STATE)
):
    def run():
        report = _service.evaluate(_context(), execution_id, to_state)
        return {
            "to_state": to_state,
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


# ----------------------------------------------------------------------
# Dispatch
# ----------------------------------------------------------------------


@router.post("/{execution_id}/assign", summary="Lease a node to a worker")
async def assign_route(payload: AssignIn, execution_id: str = Path(...)):
    def run():
        result = _service.assign(
            _context(),
            AssignNode(
                execution_id=execution_id,
                node_id=payload.node_id,
                worker_id=payload.worker_id,
            ),
        )
        return {"execution": _render(result.execution), "events": list(result.event_types)}

    return _handle(run)


@router.get(
    "/{execution_id}/nodes/{node_id}/run-context",
    summary="What a worker is handed to run a node",
)
async def run_context_route(execution_id: str = Path(...), node_id: str = Path(...)):
    def run():
        run_context = _service.run_context_for(_context(), execution_id, node_id)
        return {
            "execution_id": run_context.execution_id,
            "node_id": run_context.node_id,
            "attempt": run_context.attempt,
            "worker_kind": run_context.worker_kind.value,
            "side_effect": run_context.side_effect.value,
            "execution_key": run_context.execution_key,
            "idempotency_key": run_context.idempotency_key,
            "deadline_seconds": run_context.deadline_seconds,
            "is_retry": run_context.is_retry,
        }

    return _handle(run)


@router.post("/{execution_id}/results", summary="Record a success from the lease holder")
async def record_success_route(payload: SuccessIn, execution_id: str = Path(...)):
    def run():
        result = _service.record_success(
            _context(),
            RecordSuccess(
                execution_id=execution_id,
                node_id=payload.node_id,
                worker_id=payload.worker_id,
                execution_key=payload.execution_key,
                detail=payload.detail,
            ),
        )
        return {"execution": _render(result.execution)}

    return _handle(run)


@router.post("/{execution_id}/failures", summary="Record a failure from the lease holder")
async def record_failure_route(payload: FailureIn, execution_id: str = Path(...)):
    def run():
        result = _service.record_failure(
            _context(),
            RecordFailure(
                execution_id=execution_id,
                node_id=payload.node_id,
                worker_id=payload.worker_id,
                reason=payload.reason,
                execution_key=payload.execution_key,
                failure_class=payload.failure_class,
                failure_source=payload.failure_source,
            ),
        )
        return {"execution": _render(result.execution)}

    return _handle(run)


@router.post("/{execution_id}/reclaim", summary="Take back a node whose lease lapsed")
async def reclaim_route(payload: NodeRefIn, execution_id: str = Path(...)):
    def run():
        result = _service.reclaim(
            _context(), ReclaimNode(execution_id=execution_id, node_id=payload.node_id)
        )
        return {"execution": _render(result.execution)}

    return _handle(run)


@router.post("/{execution_id}/retry", summary="Return a node to the ready pool")
async def retry_route(payload: NodeRefIn, execution_id: str = Path(...)):
    def run():
        result = _service.retry(
            _context(), RetryNode(execution_id=execution_id, node_id=payload.node_id)
        )
        return {"execution": _render(result.execution), "events": list(result.event_types)}

    return _handle(run)


@router.post("/{execution_id}/skip", summary="Skip a node, with the reason")
async def skip_route(payload: SkipIn, execution_id: str = Path(...)):
    def run():
        result = _service.skip(
            _context(),
            SkipNode(
                execution_id=execution_id, node_id=payload.node_id, reason=payload.reason
            ),
        )
        return {"execution": _render(result.execution)}

    return _handle(run)


@router.post("/{execution_id}/compensate", summary="Record that a node was walked back")
async def compensate_route(payload: NodeRefIn, execution_id: str = Path(...)):
    def run():
        result = _service.compensate(
            _context(),
            CompensateNode(execution_id=execution_id, node_id=payload.node_id),
        )
        return {"execution": _render(result.execution)}

    return _handle(run)


# ----------------------------------------------------------------------
# Lifecycle
# ----------------------------------------------------------------------


@router.post("/{execution_id}/checkpoints", summary="Record a resumable position")
async def checkpoint_route(payload: CheckpointIn, execution_id: str = Path(...)):
    def run():
        result = _service.checkpoint(
            _context(),
            CreateCheckpoint(
                execution_id=execution_id,
                label=payload.label,
                payload_ref=payload.payload_ref,
                recorded_by=payload.recorded_by,
            ),
        )
        return {"execution": _render(result.execution), "events": list(result.event_types)}

    return _handle(run)


@router.post("/{execution_id}/pause", summary="Stop dispatching; leased nodes keep running")
async def pause_route(payload: ReasonIn, execution_id: str = Path(...)):
    def run():
        result = _service.pause(
            _context(), PauseExecution(execution_id=execution_id, reason=payload.reason)
        )
        return {"execution": _render(result.execution), "events": list(result.event_types)}

    return _handle(run)


@router.post("/{execution_id}/resume", summary="Continue, optionally from a checkpoint")
async def resume_route(payload: ResumeIn, execution_id: str = Path(...)):
    def run():
        result = _service.resume(
            _context(),
            ResumeExecution(
                execution_id=execution_id, from_checkpoint=payload.from_checkpoint
            ),
        )
        return {"execution": _render(result.execution), "events": list(result.event_types)}

    return _handle(run)


@router.post("/{execution_id}/complete", summary="Report success over finished work")
async def complete_route(execution_id: str = Path(...)):
    def run():
        result = _service.complete(
            _context(), CompleteExecution(execution_id=execution_id)
        )
        return {"execution": _render(result.execution), "events": list(result.event_types)}

    return _handle(run)


@router.post("/{execution_id}/fail", summary="Report failure, with the reason")
async def fail_route(payload: ReasonIn, execution_id: str = Path(...)):
    def run():
        result = _service.fail(
            _context(), FailExecution(execution_id=execution_id, reason=payload.reason)
        )
        return {"execution": _render(result.execution), "events": list(result.event_types)}

    return _handle(run)


@router.post("/{execution_id}/cancel", summary="Call the run off")
async def cancel_route(payload: CancelIn, execution_id: str = Path(...)):
    def run():
        result = _service.cancel(
            _context(),
            CancelExecution(
                execution_id=execution_id,
                reason=payload.reason,
                cancelled_by=payload.cancelled_by,
            ),
        )
        return {"execution": _render(result.execution), "events": list(result.event_types)}

    return _handle(run)


@router.post("/{execution_id}/time-out", summary="Record that the deadline fired")
async def time_out_route(payload: TimeoutIn, execution_id: str = Path(...)):
    def run():
        result = _service.time_out(
            _context(),
            TimeOutExecution(
                execution_id=execution_id, deadline_seconds=payload.deadline_seconds
            ),
        )
        return {"execution": _render(result.execution), "events": list(result.event_types)}

    return _handle(run)


# ----------------------------------------------------------------------
# Durable-execution surface (Phase 3.1)
#
# Queries that show a decision before anything acts on it, plus the
# heartbeat. Deliberately no generic status-mutation endpoint: every state
# change goes through an application command, so there is no PATCH here that
# could move a run without the domain agreeing.
# ----------------------------------------------------------------------


@router.post("/{execution_id}/heartbeat", summary="A worker reporting it is alive")
async def heartbeat_route(payload: HeartbeatIn, execution_id: str = Path(...)):
    return _handle(
        lambda: _service.heartbeat(
            _context(),
            Heartbeat(
                execution_id=execution_id,
                node_id=payload.node_id,
                worker_id=payload.worker_id,
            ),
        )
    )


@router.get("/{execution_id}/silent-workers", summary="Holders that have gone quiet")
async def silent_workers_route(
    execution_id: str = Path(...), silence_seconds: int = Query(60, ge=1)
):
    def run():
        found = _service.silent_workers(
            _context(), execution_id, silence_seconds=silence_seconds
        )
        return {"count": len(found), "silent": list(found)}

    return _handle(run)


@router.get(
    "/{execution_id}/nodes/{node_id}/retry-decision",
    summary="Whether a node may run again, and why",
)
async def retry_decision_route(execution_id: str = Path(...), node_id: str = Path(...)):
    def run():
        decision = _service.plan_retry(_context(), execution_id, node_id)
        return decision.to_dict()

    return _handle(run)


@router.get(
    "/{execution_id}/nodes/{node_id}/effect",
    summary="What running this node does, and whether repeating it is safe",
)
async def effect_route(execution_id: str = Path(...), node_id: str = Path(...)):
    def run():
        execution = _service.get(_context(), GetExecution(execution_id=execution_id))
        run_for = execution.run_for(node_id)
        if run_for is None:
            raise UnknownNode(execution_id=execution_id, node_id=node_id)
        return profile_for(run_for.spec).to_dict()

    return _handle(run)


@router.get("/{execution_id}/recovery-plan", summary="What recovery would decide")
async def recovery_plan_route(
    execution_id: str = Path(...),
    trigger: str = Query(
        "operator_request",
        pattern="^(process_restart|lease_expired|worker_lost|timeout|operator_request|resume_request)$",
    ),
):
    def run():
        decision = _service.plan_recovery(
            _context(), PlanRecovery(execution_id=execution_id, trigger=trigger)
        )
        return decision.to_dict()

    return _handle(run)


@router.get("/{execution_id}/history", summary="The recorded events for a run")
async def history_route(execution_id: str = Path(...)):
    def run():
        events = _service.history(_context(), execution_id)
        return {
            "count": len(events),
            "events": [
                {
                    "event_type": getattr(type(e), "EVENT_TYPE", "unknown"),
                    "event_id": getattr(e, "event_id", None),
                    "correlation_id": getattr(e, "correlation_id", None),
                    "causation_id": getattr(e, "causation_id", None),
                    "occurred_at": (
                        e.occurred_at.isoformat()
                        if getattr(e, "occurred_at", None)
                        else None
                    ),
                }
                for e in events
            ],
        }

    return _handle(run)


@router.get(
    "/{execution_id}/replay",
    summary="Reconstruct the run's state from history. Executes nothing",
)
async def replay_route(execution_id: str = Path(...)):
    return _handle(
        lambda: _service.replay(
            _context(), ReplayExecution(execution_id=execution_id)
        ).to_dict()
    )
