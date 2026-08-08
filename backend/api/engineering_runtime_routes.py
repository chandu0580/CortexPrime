"""Engineering Runtime REST API.

Translation only. Every rule lives in the runtime; this maps HTTP to commands and
runtime refusals to status codes.

Mounted under ``/api/v1/engineering/runtime``, beside the WorkOrder API from
PR-E1. The two are deliberately separate paths: one manipulates the artifact,
the other drives the lifecycle, and collapsing them would suggest a client can
approve a WorkOrder by advancing it.

Status codes:

``409`` — an illegal transition, a failed precondition, a terminal state, or a
concurrent modification. All mean the request was well-formed and conflicts with
current state.

``422`` — policy refused. Findings travel in the body; a client told only
"refused" has to guess.

``503`` — a collaborator the phase needs has no adapter wired. Not the client's
fault and not permanent, which is exactly what 503 means. Returning 409 would
suggest retrying with different state; returning 500 would suggest a bug.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Path, Query, status
from pydantic import BaseModel, Field

from backend.api.engineering_composition import build_engineering_runtime
from backend.contracts.errors import ContractViolation
from backend.contexts.engineering import (
    AdvanceWorkOrder,
    CollaboratorUnavailable,
    ConcurrentModification,
    GetEventHistory,
    GetLifecycleCapability,
    GetRuntimeState,
    IllegalTransition,
    PhaseUnknown,
    PolicyRefused,
    PreconditionFailed,
    RejectWorkOrderCommand,
    ReplayWorkOrder,
    SupersedeWorkOrderCommand,
    TransitionRolledBack,
    WorkOrderUnknown,
)
from backend.platform.context import ExecutionContext

router = APIRouter(
    prefix="/api/v1/engineering/runtime", tags=["Engineering — Runtime"]
)

_stack = build_engineering_runtime()


def _context() -> ExecutionContext:
    """Engineering work is platform-internal; the reason is stated and greppable."""
    return ExecutionContext.platform_internal(
        reason="engineering-runtime-api", component="engineering-runtime", source="http"
    )


# ----------------------------------------------------------------------
# Schemas
# ----------------------------------------------------------------------


class AdvanceIn(BaseModel):
    to_phase: str = Field(..., description="Target lifecycle phase")
    actor: str = Field(..., description="Who is performing the transition")
    expected_phase: Optional[str] = Field(
        None, description="Optimistic concurrency: refuse if the phase moved"
    )


class RejectIn(BaseModel):
    rejection_type: str
    detail: str = Field(..., description="Must cite the evidence the type requires")
    raised_by: str
    expected_phase: Optional[str] = None


class SupersedeIn(BaseModel):
    successor_id: str
    actor: str


# ----------------------------------------------------------------------
# Error translation
# ----------------------------------------------------------------------


def _handle(operation):
    try:
        return operation()
    except WorkOrderUnknown as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except CollaboratorUnavailable as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            {
                "error": "collaborator_unavailable",
                "message": str(exc),
                "port": exc.port,
                "needed_for": exc.needed_for,
            },
        ) from exc
    except PolicyRefused as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            {
                "error": "policy_refused",
                "message": str(exc),
                "transition": exc.transition,
                "failures": [
                    {"check": f.check, "detail": f.detail, "subject": f.subject}
                    for f in exc.failures
                ],
            },
        ) from exc
    except (IllegalTransition, PreconditionFailed, ConcurrentModification) as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    except TransitionRolledBack as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    except PhaseUnknown as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    except ContractViolation as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc


def _render_result(result) -> dict:
    return {
        "work_id": result.snapshot.work_id,
        "version": result.snapshot.version,
        "phase": result.snapshot.phase.value,
        "transition": result.decision.label,
        "events": list(result.event_types),
        "advisory": [
            {"check": f.check, "detail": f.detail} for f in result.advisory
        ],
    }


# ----------------------------------------------------------------------
# Routes
# ----------------------------------------------------------------------


@router.get("/work-orders/{work_id}/state", summary="Where a WorkOrder is and can go")
async def runtime_state_route(work_id: str = Path(...)):
    def run():
        state = _stack.queries.state(_context(), GetRuntimeState(work_id=work_id))
        return {
            "work_id": state.work_id,
            "version": state.version,
            "phase": state.phase,
            "digest": state.digest,
            "legal_next": list(state.legal_next),
            "reachable_next": list(state.reachable_next),
            "blocked_next": list(state.blocked_next),
            "events_recorded": state.events_recorded,
            "round": state.round,
            "attempt": state.attempt,
        }

    return _handle(run)


@router.post("/work-orders/{work_id}/advance", summary="Execute a lifecycle transition")
async def advance_route(payload: AdvanceIn, work_id: str = Path(...)):
    def run():
        command = AdvanceWorkOrder(
            work_id=work_id,
            to_phase=payload.to_phase,
            actor=payload.actor,
            expected_phase=payload.expected_phase,
        )
        result = _stack.runtime.transition(
            _context(),
            command.work_id,
            command.to_phase,
            actor=command.actor,
            expected_phase=command.expected_phase,
        )
        return _render_result(result)

    return _handle(run)


@router.post("/work-orders/{work_id}/reject", summary="Route a typed rejection")
async def reject_route(payload: RejectIn, work_id: str = Path(...)):
    def run():
        command = RejectWorkOrderCommand(
            work_id=work_id,
            rejection_type=payload.rejection_type,
            detail=payload.detail,
            raised_by=payload.raised_by,
            expected_phase=payload.expected_phase,
        )
        result = _stack.runtime.reject(
            _context(),
            command.work_id,
            rejection_type=command.rejection_type,
            detail=command.detail,
            raised_by=command.raised_by,
            expected_phase=command.expected_phase,
        )
        return _render_result(result)

    return _handle(run)


@router.get("/work-orders/{work_id}/events", summary="Recorded events for a WorkOrder")
async def work_order_events_route(work_id: str = Path(...)):
    def run():
        entries = _stack.queries.history(GetEventHistory(work_id=work_id))
        return {
            "count": len(entries),
            "events": [
                {"sequence": e.sequence, "event_type": e.event_type, "work_id": e.work_id}
                for e in entries
            ],
        }

    return _handle(run)


@router.get("/events", summary="The engineering event log")
async def events_route(since: int = Query(0, ge=0)):
    def run():
        entries = _stack.queries.history(GetEventHistory(since=since))
        return {
            "count": len(entries),
            "cursor": _stack.runtime.dispatcher.cursor,
            "events": [
                {"sequence": e.sequence, "event_type": e.event_type, "work_id": e.work_id}
                for e in entries
            ],
        }

    return _handle(run)


@router.get("/capability", summary="Which collaborators are wired")
async def capability_route():
    return _handle(lambda: _stack.queries.capability(GetLifecycleCapability()))


@router.get("/integrity", summary="Defects in the event log's ordering")
async def integrity_route():
    def run():
        defects = _stack.queries.integrity()
        return {"intact": not defects, "defects": list(defects)}

    return _handle(run)


@router.get("/work-orders/{work_id}/replay", summary="Replay a WorkOrder's event sequence")
async def replay_route(work_id: str = Path(...)):
    def run():
        entries = _stack.queries.replay(ReplayWorkOrder(work_id=work_id))
        return {
            "count": len(entries),
            "sequence": [
                {"sequence": e.sequence, "event_type": e.event_type} for e in entries
            ],
        }

    return _handle(run)
