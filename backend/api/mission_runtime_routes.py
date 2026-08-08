"""Mission Runtime REST API.

Translation only. Every rule lives in the Mission Runtime context.

Mounted at ``/api/v1/missions``. Deliberately distinct from V1's
``/api/enterprise/missions`` and ``/api/mission-library``: this is the V2 runtime
and the two coexist while the strangler migration runs. Sharing a prefix would
make which implementation answered a request depend on registration order.

Status codes:

``409`` — the mission is archived, an execution is already open, or the move is
illegal for the state the mission is in. The request was well-formed and
conflicts with what exists.

``422`` — policy refused the transition. Findings travel in the body; a client
told only "refused" has to guess.

``404`` — no such mission, or no such checkpoint on it.

``400`` — a malformed value.
"""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, HTTPException, Path, Query, status
from pydantic import BaseModel, Field

from backend.contracts.errors import ContractViolation
from backend.contexts.mission import (
    AdvanceExecution,
    ArchiveMission,
    CancelMission,
    CompleteMission,
    CreateMission,
    DeclarePrecondition,
    ExecutionAlreadyOpen,
    FailMission,
    GetMission,
    GetTimeline,
    IllegalExecutionTransition,
    IllegalStatusTransition,
    InMemoryMissionRepository,
    ListMissions,
    MissionArchivedError,
    MissionNotFound,
    MissionService,
    NoOpenExecution,
    NoPlanRecorded,
    PauseMission,
    PreconditionsUnmet,
    RecordCheckpoint,
    RecordPlan,
    ResumeMission,
    SatisfyPrecondition,
    StartMission,
    TransitionMission,
    TransitionRefused,
    UnknownCheckpoint,
    VerificationNotReached,
)
from backend.platform.context import ExecutionContext

router = APIRouter(prefix="/api/v1/missions", tags=["Mission Runtime"])

_service = MissionService(repository=InMemoryMissionRepository())


def _context() -> ExecutionContext:
    return ExecutionContext.platform_internal(
        reason="mission-runtime-api", component="mission-runtime", source="http"
    )


# ----------------------------------------------------------------------
# Schemas
# ----------------------------------------------------------------------

_KIND = "^(monitor|investigate|optimize|remediate|validate|audit)$"
_PRIORITY = "^(routine|elevated|urgent|critical)$"
_STATUS = "^(draft|planned|ready|running|paused|completed|failed|cancelled|archived)$"
_EXEC_STATE = (
    "^(received|interpreted|gathering|reasoning|planned|awaiting_decision|executing"
    "|verifying|compensating|concluded|blocked|abandoned|failed)$"
)


class CreateIn(BaseModel):
    stated_goal: str = Field(
        ..., description="The requester's own words, preserved verbatim"
    )
    title: str
    kind: str = Field(..., pattern=_KIND)
    priority: str = Field("routine", pattern=_PRIORITY)
    target: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    preconditions: List[str] = Field(default_factory=list)


class PlanIn(BaseModel):
    plan_id: str = Field(..., description="Where the plan lives. Mission Runtime does not plan")
    produced_by: str = "planner"
    revision: Optional[str] = None
    reason: str = "a plan was produced"
    actor: str = "planner"


class PreconditionIn(BaseModel):
    key: str
    description: str = ""


class SatisfyIn(BaseModel):
    satisfied_by: str
    note: Optional[str] = None


class TransitionIn(BaseModel):
    to_status: str = Field(..., pattern=_STATUS)
    reason: str = Field(..., description="Constitution S4: no state is exited without one")
    actor: str


class MovementIn(BaseModel):
    reason: str
    actor: str = "operator"


class StartIn(BaseModel):
    reason: str = "cleared to run"
    actor: str = "orchestrator"
    executor_ref: Optional[str] = None


class ResumeIn(BaseModel):
    reason: str = "resuming"
    actor: str = "operator"
    from_checkpoint: Optional[str] = None
    executor_ref: Optional[str] = None


class AdvanceIn(BaseModel):
    to_state: str = Field(..., pattern=_EXEC_STATE)
    reason: str
    actor: str = "execution"


class CheckpointIn(BaseModel):
    label: str
    payload_ref: Optional[str] = None
    payload_digest: Optional[str] = None
    actor: str = "execution"


# ----------------------------------------------------------------------
# Rendering
# ----------------------------------------------------------------------


def _render(mission) -> dict:
    current = mission.current_execution
    latest = mission.latest_checkpoint
    return {
        "mission_id": str(mission.mission_id),
        "stated_goal": mission.stated_goal,
        "title": mission.metadata.title,
        "kind": mission.metadata.kind.value,
        "priority": mission.metadata.priority.value,
        "target": mission.metadata.target,
        "tags": sorted(mission.metadata.tags),
        "status": mission.status.value,
        "execution_state": mission.execution_state.value,
        "is_verified": mission.is_verified,
        "permitted_transitions": list(mission.permitted_transitions()),
        "plan_ref": str(mission.plan_ref) if mission.plan_ref else None,
        "preconditions": [
            {
                "key": p.key,
                "description": p.description,
                "satisfied": p.satisfied,
                "satisfied_by": p.satisfied_by,
            }
            for p in mission.preconditions
        ],
        "outstanding_preconditions": list(mission.outstanding_preconditions),
        "current_execution": (
            {
                "execution_id": str(current.execution_id),
                "attempt": current.attempt,
                "state": current.state.value,
                "resumed_from_checkpoint": current.resumed_from_checkpoint,
            }
            if current
            else None
        ),
        "executions": [
            {
                "execution_id": str(e.execution_id),
                "attempt": e.attempt,
                "state": e.state.value,
                "outcome": e.outcome.value,
            }
            for e in mission.executions
        ],
        "checkpoints": [
            {
                "checkpoint_id": str(c.checkpoint_id),
                "sequence": c.sequence,
                "label": c.label,
                "execution_state": c.execution_state.value,
                "digest": c.digest,
            }
            for c in mission.checkpoints
        ],
        "latest_checkpoint": str(latest.checkpoint_id) if latest else None,
        "timeline_entries": len(mission.timeline),
        "timeline_agrees": mission.timeline_agrees(),
        "outcome_note": mission.outcome_note,
        "digest": mission.digest,
    }


def _render_timeline(timeline) -> list:
    return [
        {
            "sequence": e.sequence,
            "kind": e.kind.value,
            "reason": e.reason,
            "actor": e.actor,
            "occurred_at": e.occurred_at.isoformat(),
            "from_status": e.from_status.value if e.from_status else None,
            "to_status": e.to_status.value if e.to_status else None,
            "from_execution_state": (
                e.from_execution_state.value if e.from_execution_state else None
            ),
            "to_execution_state": (
                e.to_execution_state.value if e.to_execution_state else None
            ),
            "checkpoint_id": e.checkpoint_id,
            "detail": e.detail,
        }
        for e in timeline
    ]


def _handle(operation):
    try:
        return operation()
    except (MissionNotFound, UnknownCheckpoint) as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except TransitionRefused as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            {
                "error": "transition_refused",
                "message": str(exc),
                "target": exc.target,
                "failures": [
                    {"rule": f.rule, "detail": f.detail, "subject": f.subject}
                    for f in exc.failures
                ],
            },
        ) from exc
    except VerificationNotReached as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            {
                "error": "verification_not_reached",
                "message": str(exc),
                "execution_state": exc.execution_state,
            },
        ) from exc
    except PreconditionsUnmet as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            {
                "error": "preconditions_unmet",
                "message": str(exc),
                "outstanding": list(exc.outstanding),
            },
        ) from exc
    except IllegalStatusTransition as exc:
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
    except (MissionArchivedError, ExecutionAlreadyOpen) as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    except (NoOpenExecution, NoPlanRecorded) as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    except IllegalExecutionTransition as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    except ContractViolation as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc


# ----------------------------------------------------------------------
# Routes
# ----------------------------------------------------------------------


@router.post("", status_code=status.HTTP_201_CREATED, summary="Draft a mission")
async def create_route(payload: CreateIn):
    def run():
        result = _service.create(
            _context(),
            CreateMission(
                stated_goal=payload.stated_goal,
                title=payload.title,
                kind=payload.kind,
                priority=payload.priority,
                target=payload.target,
                tags=tuple(payload.tags),
                preconditions=tuple(payload.preconditions),
            ),
        )
        return {"mission": _render(result.mission), "events": list(result.event_types)}

    return _handle(run)


@router.get("", summary="List missions")
async def list_route(
    mission_status: Optional[str] = Query(None, alias="status"),
    kind: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    live_only: bool = Query(False),
):
    def run():
        found = _service.list(
            _context(),
            ListMissions(
                status=mission_status, kind=kind, priority=priority, live_only=live_only
            ),
        )
        return {"count": len(found), "missions": [_render(m) for m in found]}

    return _handle(run)


@router.get("/{mission_id}", summary="Fetch a mission")
async def get_route(mission_id: str = Path(...)):
    return _handle(
        lambda: _render(_service.get(_context(), GetMission(mission_id=mission_id)))
    )


@router.get("/{mission_id}/timeline", summary="The append-only record of what happened")
async def timeline_route(mission_id: str = Path(...)):
    def run():
        timeline = _service.timeline(_context(), GetTimeline(mission_id=mission_id))
        return {"count": len(timeline), "entries": _render_timeline(timeline)}

    return _handle(run)


@router.get("/{mission_id}/policy", summary="Run mission policy without transitioning")
async def policy_route(
    mission_id: str = Path(...), to_status: str = Query(..., pattern=_STATUS)
):
    def run():
        report = _service.evaluate(_context(), mission_id, to_status)
        return {
            "to_status": to_status,
            "may_transition": report.may_transition,
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


@router.post("/{mission_id}/plan", summary="Record where the plan lives")
async def plan_route(payload: PlanIn, mission_id: str = Path(...)):
    def run():
        result = _service.record_plan(
            _context(),
            RecordPlan(
                mission_id=mission_id,
                plan_id=payload.plan_id,
                produced_by=payload.produced_by,
                revision=payload.revision,
                reason=payload.reason,
                actor=payload.actor,
            ),
        )
        return {"mission": _render(result.mission)}

    return _handle(run)


@router.post("/{mission_id}/preconditions", summary="Declare a precondition")
async def declare_precondition_route(payload: PreconditionIn, mission_id: str = Path(...)):
    def run():
        result = _service.declare_precondition(
            _context(),
            DeclarePrecondition(
                mission_id=mission_id, key=payload.key, description=payload.description
            ),
        )
        return {"mission": _render(result.mission)}

    return _handle(run)


@router.post("/{mission_id}/preconditions/{key}/satisfy", summary="Clear a precondition")
async def satisfy_precondition_route(
    payload: SatisfyIn, mission_id: str = Path(...), key: str = Path(...)
):
    def run():
        result = _service.satisfy_precondition(
            _context(),
            SatisfyPrecondition(
                mission_id=mission_id,
                key=key,
                satisfied_by=payload.satisfied_by,
                note=payload.note,
            ),
        )
        return {"mission": _render(result.mission)}

    return _handle(run)


@router.post("/{mission_id}/transition", summary="Move to planned or ready")
async def transition_route(payload: TransitionIn, mission_id: str = Path(...)):
    def run():
        result = _service.transition(
            _context(),
            TransitionMission(
                mission_id=mission_id,
                to_status=payload.to_status,
                reason=payload.reason,
                actor=payload.actor,
            ),
        )
        return {"mission": _render(result.mission)}

    return _handle(run)


@router.post("/{mission_id}/start", summary="Open an execution and begin running")
async def start_route(payload: StartIn, mission_id: str = Path(...)):
    def run():
        result = _service.start(
            _context(),
            StartMission(
                mission_id=mission_id,
                reason=payload.reason,
                actor=payload.actor,
                executor_ref=payload.executor_ref,
            ),
        )
        return {"mission": _render(result.mission), "events": list(result.event_types)}

    return _handle(run)


@router.post("/{mission_id}/pause", summary="Suspend the run")
async def pause_route(payload: MovementIn, mission_id: str = Path(...)):
    def run():
        result = _service.pause(
            _context(),
            PauseMission(mission_id=mission_id, reason=payload.reason, actor=payload.actor),
        )
        return {"mission": _render(result.mission), "events": list(result.event_types)}

    return _handle(run)


@router.post("/{mission_id}/resume", summary="Resume from a checkpoint")
async def resume_route(payload: ResumeIn, mission_id: str = Path(...)):
    def run():
        result = _service.resume(
            _context(),
            ResumeMission(
                mission_id=mission_id,
                reason=payload.reason,
                actor=payload.actor,
                from_checkpoint=payload.from_checkpoint,
                executor_ref=payload.executor_ref,
            ),
        )
        return {"mission": _render(result.mission), "events": list(result.event_types)}

    return _handle(run)


@router.post("/{mission_id}/execution/advance", summary="Record an S4 execution movement")
async def advance_route(payload: AdvanceIn, mission_id: str = Path(...)):
    def run():
        result = _service.advance_execution(
            _context(),
            AdvanceExecution(
                mission_id=mission_id,
                to_state=payload.to_state,
                reason=payload.reason,
                actor=payload.actor,
            ),
        )
        return {"mission": _render(result.mission)}

    return _handle(run)


@router.post("/{mission_id}/checkpoints", summary="Record a recoverable position")
async def checkpoint_route(payload: CheckpointIn, mission_id: str = Path(...)):
    def run():
        result = _service.record_checkpoint(
            _context(),
            RecordCheckpoint(
                mission_id=mission_id,
                label=payload.label,
                payload_ref=payload.payload_ref,
                payload_digest=payload.payload_digest,
                actor=payload.actor,
            ),
        )
        return {"mission": _render(result.mission), "events": list(result.event_types)}

    return _handle(run)


@router.post("/{mission_id}/complete", summary="Finish on verified work")
async def complete_route(payload: MovementIn, mission_id: str = Path(...)):
    def run():
        result = _service.complete(
            _context(),
            CompleteMission(
                mission_id=mission_id, reason=payload.reason, actor=payload.actor
            ),
        )
        return {"mission": _render(result.mission), "events": list(result.event_types)}

    return _handle(run)


@router.post("/{mission_id}/fail", summary="Record that the mission did not achieve its objective")
async def fail_route(payload: MovementIn, mission_id: str = Path(...)):
    def run():
        result = _service.fail(
            _context(),
            FailMission(mission_id=mission_id, reason=payload.reason, actor=payload.actor),
        )
        return {"mission": _render(result.mission), "events": list(result.event_types)}

    return _handle(run)


@router.post("/{mission_id}/cancel", summary="Call the mission off")
async def cancel_route(payload: MovementIn, mission_id: str = Path(...)):
    def run():
        result = _service.cancel(
            _context(),
            CancelMission(
                mission_id=mission_id, reason=payload.reason, actor=payload.actor
            ),
        )
        return {"mission": _render(result.mission), "events": list(result.event_types)}

    return _handle(run)


@router.post("/{mission_id}/archive", summary="Seal the record and bind its digest")
async def archive_route(payload: MovementIn, mission_id: str = Path(...)):
    def run():
        result = _service.archive(
            _context(),
            ArchiveMission(
                mission_id=mission_id, reason=payload.reason, actor=payload.actor
            ),
        )
        return {"mission": _render(result.mission), "events": list(result.event_types)}

    return _handle(run)
