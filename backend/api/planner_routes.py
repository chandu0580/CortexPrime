"""Planner REST API.

Translation only. Every rule lives in the Planner context.

Mounted at ``/api/v1/plans``.

Status codes:

``409`` — the plan is approved or superseded, the task id is taken, or the move
is illegal for the state it is in. The request was well-formed and conflicts with
what exists.

``422`` — policy refused, or the plan is incomplete. Findings travel in the body;
for a graph this matters more than elsewhere, because a plan can have a cycle
*and* an orphan task *and* an understated risk, and fixing them one round-trip at
a time is how planning becomes the slow part.

``400`` — a value this context refuses on principle: a cycle, a dangling
dependency, an understated risk, a mutation with no declared way back.

``404`` — no such plan, task, or goal.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Path, Query, status
from pydantic import BaseModel, Field

from backend.contracts.errors import ContractViolation
from backend.contexts.planner import (
    AddDependency,
    AddGoal,
    AddTask,
    ApprovePlan,
    AssessRisk,
    CyclicDependency,
    DanglingDependency,
    DeclareCriteria,
    DraftPlan,
    DuplicateTask,
    GetGraph,
    GetPlan,
    GoalWithoutTasks,
    IllegalPlanTransition,
    InMemoryPlanRepository,
    IncompletePlan,
    ListPlans,
    OrphanTask,
    PlanApprovedError,
    PlanIsSuperseded,
    PlanNotFound,
    PlanRefused,
    PlannerService,
    RejectPlan,
    RemoveTask,
    RevisePlan,
    RiskUnderstated,
    RollbackNotDeclared,
    SetExecutionStrategy,
    SetRollbackStrategy,
    UncoveredCriterion,
    UnknownGoal,
    UnknownTask,
    ValidatePlan,
)
from backend.platform.context import ExecutionContext

router = APIRouter(prefix="/api/v1/plans", tags=["Planner"])

_service = PlannerService(repository=InMemoryPlanRepository())


def _context() -> ExecutionContext:
    return ExecutionContext.platform_internal(
        reason="planner-api", component="planner", source="http"
    )


# ----------------------------------------------------------------------
# Schemas
# ----------------------------------------------------------------------

_SIDE_EFFECT = "^(read|reversible_write|irreversible_write|destructive)$"
_MODE = "^(sequential|parallel|phased)$"
_ON_FAILURE = "^(halt|compensate|continue)$"
_ROLLBACK = "^(compensating_tasks|snapshot_restore|forward_fix_only|none_required)$"
_RISK = "^(low|moderate|elevated|severe)$"
_STATUS = "^(draft|validated|approved|rejected|superseded)$"


class DraftIn(BaseModel):
    mission_id: str
    intent_id: str
    intent_digest: str = Field(
        ..., description="Binds the plan to the mandate that was actually approved"
    )
    title: str
    planned_by: str = "planner"


class GoalIn(BaseModel):
    statement: str
    satisfies: List[str] = Field(
        ..., min_length=1, description="Intent criterion ids this goal serves"
    )
    rationale: str = ""


class TaskIn(BaseModel):
    task_id: str = Field(..., description="A readable id; dependencies name it")
    purpose: str
    goals: List[str] = Field(..., min_length=1)
    depends_on: List[str] = Field(default_factory=list)
    side_effect: str = Field("read", pattern=_SIDE_EFFECT)
    compensating_task: Optional[str] = None
    inverse_action: Optional[str] = None
    irreversible_accepted_by: Optional[str] = None
    execution_key: Optional[str] = None


class DependencyIn(BaseModel):
    depends_on: str


class CriteriaIn(BaseModel):
    criteria: List[str] = Field(..., min_length=1)


class ExecutionStrategyIn(BaseModel):
    mode: str = Field("sequential", pattern=_MODE)
    on_failure: str = Field("halt", pattern=_ON_FAILURE)
    max_parallelism: int = Field(1, ge=1)
    checkpoint_after: List[str] = Field(default_factory=list)
    continue_justification: str = ""


class RollbackStrategyIn(BaseModel):
    kind: str = Field("none_required", pattern=_ROLLBACK)
    description: str = ""
    accepted_by: Optional[str] = None
    snapshot_of: List[str] = Field(default_factory=list)


class RiskIn(BaseModel):
    overall: str = Field("low", pattern=_RISK)
    risks: List[Dict[str, Any]] = Field(default_factory=list)
    assessed_by: str = "planner"
    note: str = ""


class ApproveIn(BaseModel):
    approved_by: str


class RejectIn(BaseModel):
    reason: str
    rejected_by: str = "reviewer"


class ReviseIn(BaseModel):
    reason: str = "a revised version replaces this one"


# ----------------------------------------------------------------------
# Rendering
# ----------------------------------------------------------------------


def _render(plan) -> dict:
    graph = plan.graph if plan.tasks else None
    floor, driver = plan.implied_risk_floor
    return {
        "plan_id": str(plan.plan_id),
        "version": plan.version,
        "mission_id": plan.mission_id,
        "intent_id": plan.intent_id,
        "intent_digest": plan.intent_digest,
        "title": plan.title,
        "status": plan.status.value,
        "permitted_transitions": list(plan.permitted_transitions()),
        "is_complete": plan.is_complete,
        "missing_elements": list(plan.missing_elements),
        "is_executable": plan.is_executable,
        "goals": [
            {
                "goal_id": str(g.goal_id),
                "statement": g.statement,
                "satisfies": list(g.criterion_ids),
                "task_count": len(plan.tasks_for_goal(str(g.goal_id))),
            }
            for g in plan.goals
        ],
        "tasks": [
            {
                "task_id": t.task_id,
                "purpose": t.purpose,
                "goal_ids": sorted(t.goal_ids),
                "depends_on": list(t.depends_on),
                "side_effect": t.side_effect.value,
                "mutates": t.mutates,
                "reversible": t.is_reversible,
                "irreversible_accepted_by": t.irreversible_accepted_by,
                "execution_key": t.execution_key,
            }
            for t in plan.tasks
        ],
        "success_criteria": sorted(c.criterion_id for c in plan.success_criteria),
        "uncovered_criteria": list(plan.uncovered_criteria),
        "orphan_tasks": list(plan.orphan_tasks),
        "idle_goals": list(plan.idle_goals),
        "graph": (
            {
                "depth": graph.depth,
                "widest_layer": graph.widest_layer,
                "roots": list(graph.roots),
                "leaves": list(graph.leaves),
                "layers": [list(layer) for layer in graph.layers()],
            }
            if graph
            else None
        ),
        "execution_strategy": {
            "mode": plan.execution_strategy.mode.value,
            "on_failure": plan.execution_strategy.on_failure.value,
            "max_parallelism": plan.execution_strategy.max_parallelism,
            "checkpoint_after": list(plan.execution_strategy.checkpoint_after),
        },
        "rollback_strategy": {
            "kind": plan.rollback_strategy.kind.value,
            "description": plan.rollback_strategy.description,
            "accepted_by": plan.rollback_strategy.accepted_by,
            "provides_a_way_back": plan.rollback_strategy.provides_a_way_back,
        },
        "risk": (
            {
                "overall": plan.risk_assessment.overall.value,
                "assessed_by": plan.risk_assessment.assessed_by,
                "risks": [
                    {
                        "risk_id": str(r.risk_id),
                        "statement": r.statement,
                        "level": r.level.value,
                        "likelihood": r.likelihood.value,
                        "mitigation": r.mitigation,
                    }
                    for r in plan.risk_assessment.risks
                ],
            }
            if plan.risk_assessment
            else None
        ),
        "implied_risk_floor": {"level": floor.value, "driver": driver},
        "mutating_tasks": len(plan.mutating_tasks),
        "approved_by": plan.approved_by,
        "rejection_reason": plan.rejection_reason,
        "digest": plan.digest,
        "supersedes": str(plan.supersedes) if plan.supersedes else None,
        "superseded_by": str(plan.superseded_by) if plan.superseded_by else None,
    }


def _handle(operation):
    try:
        return operation()
    except (PlanNotFound, UnknownTask, UnknownGoal) as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except PlanRefused as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            {
                "error": "plan_refused",
                "message": str(exc),
                "target": exc.target,
                "failures": [
                    {"rule": f.rule, "detail": f.detail, "subject": f.subject}
                    for f in exc.failures
                ],
            },
        ) from exc
    except IncompletePlan as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            {
                "error": "incomplete_plan",
                "message": str(exc),
                "missing": list(exc.missing),
            },
        ) from exc
    except CyclicDependency as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            {"error": "cyclic_dependency", "message": str(exc), "cycle": list(exc.cycle)},
        ) from exc
    except DanglingDependency as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            {
                "error": "dangling_dependency",
                "message": str(exc),
                "task_id": exc.task_id,
                "missing": list(exc.missing),
            },
        ) from exc
    except RiskUnderstated as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            {
                "error": "risk_understated",
                "message": str(exc),
                "declared": exc.declared,
                "implied": exc.implied,
            },
        ) from exc
    except RollbackNotDeclared as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            {
                "error": "rollback_not_declared",
                "message": str(exc),
                "mutating": list(exc.mutating),
            },
        ) from exc
    except (OrphanTask, UncoveredCriterion, GoalWithoutTasks) as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            {"error": "incoherent_plan", "message": str(exc)},
        ) from exc
    except IllegalPlanTransition as exc:
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
    except (PlanApprovedError, PlanIsSuperseded, DuplicateTask) as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    except ContractViolation as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc


# ----------------------------------------------------------------------
# Routes
# ----------------------------------------------------------------------


@router.post("", status_code=status.HTTP_201_CREATED, summary="Draft a plan")
async def draft_route(payload: DraftIn):
    def run():
        result = _service.draft(
            _context(),
            DraftPlan(
                mission_id=payload.mission_id,
                intent_id=payload.intent_id,
                intent_digest=payload.intent_digest,
                title=payload.title,
                planned_by=payload.planned_by,
            ),
        )
        return {"plan": _render(result.plan), "events": list(result.event_types)}

    return _handle(run)


@router.get("", summary="List plans")
async def list_route(
    mission_id: Optional[str] = Query(None),
    intent_id: Optional[str] = Query(None),
    plan_status: Optional[str] = Query(None, alias="status"),
    executable_only: bool = Query(False),
):
    def run():
        found = _service.list(
            _context(),
            ListPlans(
                mission_id=mission_id,
                intent_id=intent_id,
                status=plan_status,
                executable_only=executable_only,
            ),
        )
        return {"count": len(found), "plans": [_render(p) for p in found]}

    return _handle(run)


@router.get("/{plan_id}", summary="Fetch a plan")
async def get_route(plan_id: str = Path(...)):
    return _handle(lambda: _render(_service.get(_context(), GetPlan(plan_id=plan_id))))


@router.get("/{plan_id}/graph", summary="The dependency graph")
async def graph_route(plan_id: str = Path(...)):
    def run():
        graph = _service.graph(_context(), GetGraph(plan_id=plan_id))
        return {
            "tasks": list(graph.task_ids),
            "depth": graph.depth,
            "widest_layer": graph.widest_layer,
            "roots": list(graph.roots),
            "leaves": list(graph.leaves),
            "layers": [list(layer) for layer in graph.layers()],
            "blast_radius": {t: graph.blast_of(t) for t in graph.task_ids},
        }

    return _handle(run)


@router.get("/{plan_id}/policy", summary="Run plan policy without transitioning")
async def policy_route(
    plan_id: str = Path(...), to_status: str = Query("validated", pattern=_STATUS)
):
    def run():
        report = _service.evaluate(_context(), plan_id, to_status)
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


@router.post("/{plan_id}/criteria", summary="Declare the criteria the plan serves")
async def criteria_route(payload: CriteriaIn, plan_id: str = Path(...)):
    def run():
        result = _service.declare_criteria(
            _context(), DeclareCriteria(plan_id=plan_id, criteria=tuple(payload.criteria))
        )
        return {"plan": _render(result.plan)}

    return _handle(run)


@router.post("/{plan_id}/goals", summary="Add a goal")
async def add_goal_route(payload: GoalIn, plan_id: str = Path(...)):
    def run():
        result = _service.add_goal(
            _context(),
            AddGoal(
                plan_id=plan_id,
                statement=payload.statement,
                satisfies=tuple(payload.satisfies),
                rationale=payload.rationale,
            ),
        )
        return {"plan": _render(result.plan)}

    return _handle(run)


@router.post("/{plan_id}/tasks", summary="Add a unit of planned work")
async def add_task_route(payload: TaskIn, plan_id: str = Path(...)):
    def run():
        result = _service.add_task(
            _context(),
            AddTask(
                plan_id=plan_id,
                task_id=payload.task_id,
                purpose=payload.purpose,
                goals=tuple(payload.goals),
                depends_on=tuple(payload.depends_on),
                side_effect=payload.side_effect,
                compensating_task=payload.compensating_task,
                inverse_action=payload.inverse_action,
                irreversible_accepted_by=payload.irreversible_accepted_by,
                execution_key=payload.execution_key,
            ),
        )
        return {"plan": _render(result.plan), "events": list(result.event_types)}

    return _handle(run)


@router.delete("/{plan_id}/tasks/{task_id}", summary="Remove a task")
async def remove_task_route(plan_id: str = Path(...), task_id: str = Path(...)):
    def run():
        result = _service.remove_task(
            _context(), RemoveTask(plan_id=plan_id, task_id=task_id)
        )
        return {"plan": _render(result.plan)}

    return _handle(run)


@router.post("/{plan_id}/tasks/{task_id}/dependencies", summary="Make a task wait")
async def add_dependency_route(
    payload: DependencyIn, plan_id: str = Path(...), task_id: str = Path(...)
):
    def run():
        result = _service.add_dependency(
            _context(),
            AddDependency(
                plan_id=plan_id, task_id=task_id, depends_on=payload.depends_on
            ),
        )
        return {"plan": _render(result.plan), "events": list(result.event_types)}

    return _handle(run)


@router.put("/{plan_id}/execution-strategy", summary="How the plan would be run")
async def execution_strategy_route(payload: ExecutionStrategyIn, plan_id: str = Path(...)):
    def run():
        result = _service.set_execution_strategy(
            _context(),
            SetExecutionStrategy(
                plan_id=plan_id,
                mode=payload.mode,
                on_failure=payload.on_failure,
                max_parallelism=payload.max_parallelism,
                checkpoint_after=tuple(payload.checkpoint_after),
                continue_justification=payload.continue_justification,
            ),
        )
        return {"plan": _render(result.plan)}

    return _handle(run)


@router.put("/{plan_id}/rollback-strategy", summary="How the plan would be walked back")
async def rollback_strategy_route(payload: RollbackStrategyIn, plan_id: str = Path(...)):
    def run():
        result = _service.set_rollback_strategy(
            _context(),
            SetRollbackStrategy(
                plan_id=plan_id,
                kind=payload.kind,
                description=payload.description,
                accepted_by=payload.accepted_by,
                snapshot_of=tuple(payload.snapshot_of),
            ),
        )
        return {"plan": _render(result.plan)}

    return _handle(run)


@router.put("/{plan_id}/risk", summary="Assess the risk, floored by what the tasks do")
async def risk_route(payload: RiskIn, plan_id: str = Path(...)):
    def run():
        result = _service.assess_risk(
            _context(),
            AssessRisk(
                plan_id=plan_id,
                overall=payload.overall,
                risks=tuple(payload.risks),
                assessed_by=payload.assessed_by,
                note=payload.note,
            ),
        )
        return {"plan": _render(result.plan), "events": list(result.event_types)}

    return _handle(run)


@router.post("/{plan_id}/validate", summary="Check the plan holds together")
async def validate_route(plan_id: str = Path(...)):
    def run():
        result = _service.validate(_context(), ValidatePlan(plan_id=plan_id))
        return {"plan": _render(result.plan), "events": list(result.event_types)}

    return _handle(run)


@router.post("/{plan_id}/approve", summary="Seal the plan for execution")
async def approve_route(payload: ApproveIn, plan_id: str = Path(...)):
    def run():
        result = _service.approve(
            _context(), ApprovePlan(plan_id=plan_id, approved_by=payload.approved_by)
        )
        return {"plan": _render(result.plan), "events": list(result.event_types)}

    return _handle(run)


@router.post("/{plan_id}/reject", summary="Refuse the plan, with the reason")
async def reject_route(payload: RejectIn, plan_id: str = Path(...)):
    def run():
        result = _service.reject(
            _context(),
            RejectPlan(
                plan_id=plan_id, reason=payload.reason, rejected_by=payload.rejected_by
            ),
        )
        return {"plan": _render(result.plan), "events": list(result.event_types)}

    return _handle(run)


@router.post("/{plan_id}/revise", summary="Open the next version")
async def revise_route(payload: ReviseIn, plan_id: str = Path(...)):
    def run():
        result = _service.revise(
            _context(), RevisePlan(plan_id=plan_id, reason=payload.reason)
        )
        return {"plan": _render(result.plan), "events": list(result.event_types)}

    return _handle(run)
