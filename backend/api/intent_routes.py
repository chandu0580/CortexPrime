"""Intent Runtime REST API.

Translation only. Every rule lives in the Intent context.

Mounted at ``/api/v1/intents``.

Status codes:

``409`` — the intent is approved or superseded, or the move is illegal for the
state it is in. The request was well-formed and conflicts with what exists.

``422`` — policy refused. Findings travel in the body; a client told only
"refused" has to guess which of six elements was wrong.

``400`` — a value this context refuses on principle: an unmeasurable criterion,
an unbounded quantitative constraint, an empty or contradictory scope.

``404`` — no such intent, constraint, or criterion.
"""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, HTTPException, Path, Query, status
from pydantic import BaseModel, Field

from backend.contracts.errors import ContractViolation
from backend.contexts.intent import (
    AcknowledgeRisk,
    AddConstraint,
    AddSuccessCriterion,
    ApproveIntent,
    CaptureIntent,
    ContradictoryScope,
    DuplicateConstraint,
    EmptyScope,
    GetIntent,
    IllegalIntentTransition,
    InMemoryIntentRepository,
    IncompleteIntent,
    IntentApprovedError,
    IntentIsSuperseded,
    IntentNotFound,
    IntentService,
    ListIntents,
    RejectIntent,
    RemoveConstraint,
    RemoveSuccessCriterion,
    SetObjective,
    SetPriority,
    SetRiskAppetite,
    SetScope,
    SupersedeIntent,
    UnboundedConstraint,
    UnknownConstraint,
    UnknownCriterion,
    UnmeasurableCriterion,
    ValidateIntent,
    ValidationRefused,
)
from backend.platform.context import ExecutionContext

router = APIRouter(prefix="/api/v1/intents", tags=["Intent Runtime"])

_service = IntentService(repository=InMemoryIntentRepository())


def _context() -> ExecutionContext:
    return ExecutionContext.platform_internal(
        reason="intent-runtime-api", component="intent-runtime", source="http"
    )


# ----------------------------------------------------------------------
# Schemas
# ----------------------------------------------------------------------

_ORIGIN = "^(human|scheduled|escalation|derived)$"
_OUTCOME = "^(understand|detect|reduce|restore|protect|prove)$"
_PRIORITY = "^(routine|elevated|urgent|critical)$"
_APPETITE = "^(averse|measured|tolerant)$"
_IMPACT = "^(low|medium|high)$"
_ENVIRONMENT = "^(development|staging|production)$"
_STATUS = "^(draft|validated|approved|rejected|superseded)$"
_CONSTRAINT_KIND = (
    "^(budget|deadline|rate|availability|compliance|safety|approval|data_residency)$"
)


class CaptureIn(BaseModel):
    stated_goal: str = Field(..., description="The requester's own words, kept verbatim")
    title: str
    origin: str = Field("human", pattern=_ORIGIN)
    tags: List[str] = Field(default_factory=list)
    requested_for: Optional[str] = None
    derived_from: Optional[str] = None


class ObjectiveIn(BaseModel):
    outcome: str
    kind: str = Field("understand", pattern=_OUTCOME)
    rationale: str = ""
    subject: Optional[str] = None


class ScopeIn(BaseModel):
    included: List[str] = Field(..., min_length=1)
    excluded: List[str] = Field(default_factory=list)
    environments: List[str] = Field(default_factory=lambda: ["development"], min_length=1)
    target_type: str = "system"
    note: Optional[str] = None


class PriorityIn(BaseModel):
    priority: str = Field(..., pattern=_PRIORITY)


class AppetiteIn(BaseModel):
    appetite: str = Field(..., pattern=_APPETITE)


class ConstraintIn(BaseModel):
    kind: str = Field(..., pattern=_CONSTRAINT_KIND)
    statement: str
    limit: Optional[str] = Field(
        None, description="Required for budget, deadline and rate constraints"
    )
    enforcement: str = Field("hard", pattern="^(hard|soft)$")
    rationale: str = ""


class CriterionIn(BaseModel):
    statement: str
    measure: str = Field(
        ..., description="How this is settled. A criterion nobody can check is a wish"
    )
    threshold: Optional[str] = None
    baseline: Optional[str] = None


class RiskIn(BaseModel):
    statement: str
    impact: str = Field("low", pattern=_IMPACT)
    accepted_by: Optional[str] = None


class ApproveIn(BaseModel):
    approved_by: str


class RejectIn(BaseModel):
    reason: str
    rejected_by: str = "reviewer"


class SupersedeIn(BaseModel):
    successor_id: str
    reason: str = "a revised intent replaces this one"


# ----------------------------------------------------------------------
# Rendering
# ----------------------------------------------------------------------


def _render(intent) -> dict:
    return {
        "intent_id": str(intent.intent_id),
        "stated_goal": intent.stated_goal,
        "title": intent.metadata.title,
        "origin": intent.metadata.origin.value,
        "tags": sorted(intent.metadata.tags),
        "derived_from": intent.metadata.derived_from,
        "status": intent.status.value,
        "permitted_transitions": list(intent.permitted_transitions()),
        "is_complete": intent.is_complete,
        "missing_elements": list(intent.missing_elements),
        "is_planable": intent.is_planable,
        "objective": (
            {
                "outcome": intent.objective.outcome,
                "kind": intent.objective.kind.value,
                "rationale": intent.objective.rationale,
                "subject": intent.objective.subject,
                "changes_the_world": intent.objective.changes_the_world,
            }
            if intent.objective
            else None
        ),
        "constraints": [
            {
                "constraint_id": str(c.constraint_id),
                "kind": c.kind.value,
                "statement": c.statement,
                "limit": c.limit,
                "enforcement": c.enforcement.value,
                "inviolable": c.kind.is_inviolable,
            }
            for c in intent.constraints
        ],
        "scope": (
            {
                "included": list(intent.scope.included_identifiers),
                "excluded": list(intent.scope.excluded_identifiers),
                "environments": sorted(e.value for e in intent.scope.environments),
                "breadth": intent.scope.breadth,
                "touches_production": intent.scope.touches_production,
                "note": intent.scope.note,
            }
            if intent.scope
            else None
        ),
        "priority": intent.priority.value,
        "risk_appetite": intent.risk_appetite.value,
        "acknowledged_risks": [
            {
                "risk_id": str(r.risk_id),
                "statement": r.statement,
                "impact": r.impact.value,
                "accepted_by": r.accepted_by,
            }
            for r in intent.acknowledged_risks
        ],
        "success_criteria": [
            {
                "criterion_id": str(c.criterion_id),
                "statement": c.statement,
                "measure": c.measure,
                "threshold": c.threshold,
                "baseline": c.baseline,
            }
            for c in intent.success_criteria
        ],
        "expansion_count": intent.expansion_count,
        "approved_by": intent.approved_by,
        "rejection_reason": intent.rejection_reason,
        "digest": intent.digest,
        "superseded_by": str(intent.superseded_by) if intent.superseded_by else None,
    }


def _handle(operation):
    try:
        return operation()
    except (IntentNotFound, UnknownConstraint, UnknownCriterion) as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except ValidationRefused as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            {
                "error": "validation_refused",
                "message": str(exc),
                "target": exc.target,
                "failures": [
                    {"rule": f.rule, "detail": f.detail, "subject": f.subject}
                    for f in exc.failures
                ],
            },
        ) from exc
    except IncompleteIntent as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            {
                "error": "incomplete_intent",
                "message": str(exc),
                "missing": list(exc.missing),
            },
        ) from exc
    except IllegalIntentTransition as exc:
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
    except (IntentApprovedError, IntentIsSuperseded, DuplicateConstraint) as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    except UnmeasurableCriterion as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            {"error": "unmeasurable_criterion", "message": str(exc)},
        ) from exc
    except UnboundedConstraint as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            {"error": "unbounded_constraint", "message": str(exc), "kind": exc.kind},
        ) from exc
    except (EmptyScope, ContradictoryScope) as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, {"error": "invalid_scope", "message": str(exc)}
        ) from exc
    except ContractViolation as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc


# ----------------------------------------------------------------------
# Routes
# ----------------------------------------------------------------------


@router.post("", status_code=status.HTTP_201_CREATED, summary="Capture a stated goal")
async def capture_route(payload: CaptureIn):
    def run():
        result = _service.capture(
            _context(),
            CaptureIntent(
                stated_goal=payload.stated_goal,
                title=payload.title,
                origin=payload.origin,
                tags=tuple(payload.tags),
                requested_for=payload.requested_for,
                derived_from=payload.derived_from,
            ),
        )
        return {"intent": _render(result.intent), "events": list(result.event_types)}

    return _handle(run)


@router.get("", summary="List intents")
async def list_route(
    intent_status: Optional[str] = Query(None, alias="status"),
    priority: Optional[str] = Query(None),
    origin: Optional[str] = Query(None),
    planable_only: bool = Query(False),
):
    def run():
        found = _service.list(
            _context(),
            ListIntents(
                status=intent_status,
                priority=priority,
                origin=origin,
                planable_only=planable_only,
            ),
        )
        return {"count": len(found), "intents": [_render(i) for i in found]}

    return _handle(run)


@router.get("/{intent_id}", summary="Fetch an intent")
async def get_route(intent_id: str = Path(...)):
    return _handle(
        lambda: _render(_service.get(_context(), GetIntent(intent_id=intent_id)))
    )


@router.get("/{intent_id}/policy", summary="Run intent policy without transitioning")
async def policy_route(
    intent_id: str = Path(...),
    to_status: str = Query("validated", pattern=_STATUS),
):
    def run():
        report = _service.evaluate(_context(), intent_id, to_status)
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


@router.put("/{intent_id}/objective", summary="State what should become true")
async def objective_route(payload: ObjectiveIn, intent_id: str = Path(...)):
    def run():
        result = _service.set_objective(
            _context(),
            SetObjective(
                intent_id=intent_id,
                outcome=payload.outcome,
                kind=payload.kind,
                rationale=payload.rationale,
                subject=payload.subject,
            ),
        )
        return {"intent": _render(result.intent), "events": list(result.event_types)}

    return _handle(run)


@router.put("/{intent_id}/scope", summary="State what is in and out of scope")
async def scope_route(payload: ScopeIn, intent_id: str = Path(...)):
    def run():
        result = _service.set_scope(
            _context(),
            SetScope(
                intent_id=intent_id,
                included=tuple(payload.included),
                excluded=tuple(payload.excluded),
                environments=tuple(payload.environments),
                target_type=payload.target_type,
                note=payload.note,
            ),
        )
        return {"intent": _render(result.intent), "events": list(result.event_types)}

    return _handle(run)


@router.put("/{intent_id}/priority", summary="Set urgency")
async def priority_route(payload: PriorityIn, intent_id: str = Path(...)):
    def run():
        result = _service.set_priority(
            _context(), SetPriority(intent_id=intent_id, priority=payload.priority)
        )
        return {"intent": _render(result.intent), "events": list(result.event_types)}

    return _handle(run)


@router.put("/{intent_id}/risk-appetite", summary="Set how much risk is acceptable")
async def appetite_route(payload: AppetiteIn, intent_id: str = Path(...)):
    def run():
        result = _service.set_risk_appetite(
            _context(), SetRiskAppetite(intent_id=intent_id, appetite=payload.appetite)
        )
        return {"intent": _render(result.intent), "events": list(result.event_types)}

    return _handle(run)


@router.post("/{intent_id}/constraints", summary="Declare a boundary")
async def add_constraint_route(payload: ConstraintIn, intent_id: str = Path(...)):
    def run():
        result = _service.add_constraint(
            _context(),
            AddConstraint(
                intent_id=intent_id,
                kind=payload.kind,
                statement=payload.statement,
                limit=payload.limit,
                enforcement=payload.enforcement,
                rationale=payload.rationale,
            ),
        )
        return {"intent": _render(result.intent), "events": list(result.event_types)}

    return _handle(run)


@router.delete("/{intent_id}/constraints/{constraint_id}", summary="Drop a boundary")
async def remove_constraint_route(intent_id: str = Path(...), constraint_id: str = Path(...)):
    def run():
        result = _service.remove_constraint(
            _context(),
            RemoveConstraint(intent_id=intent_id, constraint_id=constraint_id),
        )
        return {"intent": _render(result.intent), "events": list(result.event_types)}

    return _handle(run)


@router.post("/{intent_id}/success-criteria", summary="State how success is measured")
async def add_criterion_route(payload: CriterionIn, intent_id: str = Path(...)):
    def run():
        result = _service.add_success_criterion(
            _context(),
            AddSuccessCriterion(
                intent_id=intent_id,
                statement=payload.statement,
                measure=payload.measure,
                threshold=payload.threshold,
                baseline=payload.baseline,
            ),
        )
        return {"intent": _render(result.intent), "events": list(result.event_types)}

    return _handle(run)


@router.delete(
    "/{intent_id}/success-criteria/{criterion_id}", summary="Drop a success criterion"
)
async def remove_criterion_route(intent_id: str = Path(...), criterion_id: str = Path(...)):
    def run():
        result = _service.remove_success_criterion(
            _context(),
            RemoveSuccessCriterion(intent_id=intent_id, criterion_id=criterion_id),
        )
        return {"intent": _render(result.intent), "events": list(result.event_types)}

    return _handle(run)


@router.post("/{intent_id}/risks", summary="Acknowledge a risk up front")
async def add_risk_route(payload: RiskIn, intent_id: str = Path(...)):
    def run():
        result = _service.acknowledge_risk(
            _context(),
            AcknowledgeRisk(
                intent_id=intent_id,
                statement=payload.statement,
                impact=payload.impact,
                accepted_by=payload.accepted_by,
            ),
        )
        return {"intent": _render(result.intent), "events": list(result.event_types)}

    return _handle(run)


@router.post("/{intent_id}/validate", summary="Check the mandate holds together")
async def validate_route(intent_id: str = Path(...)):
    def run():
        result = _service.validate(_context(), ValidateIntent(intent_id=intent_id))
        return {"intent": _render(result.intent), "events": list(result.event_types)}

    return _handle(run)


@router.post("/{intent_id}/approve", summary="Seal the mandate for planning")
async def approve_route(payload: ApproveIn, intent_id: str = Path(...)):
    def run():
        result = _service.approve(
            _context(),
            ApproveIntent(intent_id=intent_id, approved_by=payload.approved_by),
        )
        return {"intent": _render(result.intent), "events": list(result.event_types)}

    return _handle(run)


@router.post("/{intent_id}/reject", summary="Refuse the mandate, with the reason")
async def reject_route(payload: RejectIn, intent_id: str = Path(...)):
    def run():
        result = _service.reject(
            _context(),
            RejectIntent(
                intent_id=intent_id, reason=payload.reason, rejected_by=payload.rejected_by
            ),
        )
        return {"intent": _render(result.intent), "events": list(result.event_types)}

    return _handle(run)


@router.post("/{intent_id}/supersede", summary="Replace with a revised intent")
async def supersede_route(payload: SupersedeIn, intent_id: str = Path(...)):
    def run():
        result = _service.supersede(
            _context(),
            SupersedeIntent(
                intent_id=intent_id,
                successor_id=payload.successor_id,
                reason=payload.reason,
            ),
        )
        return {"intent": _render(result.intent), "events": list(result.event_types)}

    return _handle(run)
