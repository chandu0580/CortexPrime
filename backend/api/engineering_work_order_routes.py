"""WorkOrder REST API.

Translation only. Every rule lives in the WorkOrder context; this module maps
HTTP to commands, domain refusals to status codes, and aggregates to response
shapes. ``BND-INTERFACE-PURITY`` is the rule being honoured -- an interface that
reached the repository directly would have skipped the context that owns the
decision.

Versioned under ``/api/v1/engineering`` from the first commit. Retrofitting a
version prefix means either breaking every client or maintaining two paths
forever, and this API has no clients yet, which is the only moment the choice is
free.

Status-code mapping, and the reasoning for the ones that are not obvious:

``409`` for an invalid transition, a terminal state, a duplicate, or a digest
mismatch -- all four mean the request was well-formed but conflicts with the
resource's current state, which is exactly what 409 is for. Returning 400 would
tell a client to fix its request when the request was fine.

``422`` for validation failure -- the WorkOrder is syntactically valid and
semantically unapprovable. The findings travel in the body, because a client
that learns only "invalid" has to guess.
"""

from __future__ import annotations

from typing import Any, List, Optional

from fastapi import APIRouter, HTTPException, Path, Query, status
from pydantic import BaseModel, Field

from backend.contracts.errors import ContractViolation
from backend.contexts.workorder import (
    ApproveWorkOrder,
    AssumptionSpec,
    BlastRadius,
    CheckBlastRadiusConflicts,
    DraftWorkOrder,
    ExpandBlastRadius,
    FilesystemReferenceResolver,
    GetWorkOrder,
    InMemoryWorkOrderRepository,
    ListWorkOrders,
    Priority,
    RejectionType,
    RejectWorkOrder,
    Reprioritise,
    ResolveAssumption,
    TransitionWorkOrder,
    WorkOrderService,
    WorkOrderState,
)
from backend.contexts.workorder.domain.assumption import AssumptionResolution
from backend.contexts.workorder.domain.errors import (
    DigestMismatch,
    DuplicateWorkOrder,
    ImmutableAfterApproval,
    InvalidTransition,
    TerminalState,
    ValidationFailed,
    WorkOrderNotFound,
)
from backend.contexts.workorder.infrastructure.adr_resolver import (
    constraints_from_architecture_gate,
)
from backend.platform.context import ExecutionContext
from backend.platform.context.identity import IdentityContext

router = APIRouter(prefix="/api/v1/engineering", tags=["Engineering — WorkOrder"])


# ----------------------------------------------------------------------
# Composition
# ----------------------------------------------------------------------


def _build_service() -> WorkOrderService:
    """Assemble the service.

    In-memory for now. ``STATE-NO-NEW-FILE-STORES`` forbids a JSON-backed store,
    and a durable one belongs with the schema work rather than being smuggled in
    here. Restarting the process loses WorkOrders, and that is a stated
    limitation rather than a hidden one.
    """
    return WorkOrderService(
        repository=InMemoryWorkOrderRepository(),
        resolver=FilesystemReferenceResolver(
            known_constraints=constraints_from_architecture_gate()
        ),
    )


_service = _build_service()


def _context() -> ExecutionContext:
    """The execution context every command is issued under.

    Engineering work is platform-internal: a WorkOrder belongs to the platform
    building CortexPrime, not to a customer tenant. The reason is stated because
    every platform-internal context is a gap in tenant attribution, and making
    them greppable is what keeps the count honest.
    """
    return ExecutionContext.platform_internal(
        reason="engineering-work-order-api",
        component="workorder-api",
        source="http",
    )


# ----------------------------------------------------------------------
# Schemas
# ----------------------------------------------------------------------


class BlastRadiusIn(BaseModel):
    allowed: List[str] = Field(..., min_length=1, description="Paths that may be modified")
    forbidden: List[str] = Field(default_factory=list, description="Paths that may not be, even if allowed matches")
    read_only: List[str] = Field(default_factory=list, description="Paths readable but never written")
    justification: Optional[str] = Field(None, description="Required when the scope exceeds the thresholds")


class AssumptionIn(BaseModel):
    statement: str = Field(..., description="The belief held without evidence")
    verification_method: str = Field(..., description="How the receiver should check it")
    rejection_condition: Optional[str] = Field(None, description="Defaults to 'the assumption does not hold'")


class DraftIn(BaseModel):
    intent: str = Field(..., description="The outcome, not the method. One sentence.")
    acceptance_criteria: List[str] = Field(..., min_length=1)
    blast_radius: BlastRadiusIn
    definition_of_done: List[str] = Field(default_factory=list)
    adr_references: List[str] = Field(default_factory=list)
    evidence: List[str] = Field(default_factory=list)
    constraints: List[str] = Field(default_factory=list)
    assumptions: List[AssumptionIn] = Field(default_factory=list)
    dependencies: List[str] = Field(default_factory=list)
    priority: str = Field("p1", pattern="^(p0|p1|p2)$")
    created_by: str = Field("architect")


class ApproveIn(BaseModel):
    approved_by: str = Field(..., description="Approval is an act by a named person")


class TransitionIn(BaseModel):
    to_state: str
    actor: str


class RejectIn(BaseModel):
    rejection_type: str
    detail: str = Field(..., description="Must cite the evidence the rejection type requires")
    raised_by: str


class ResolveAssumptionIn(BaseModel):
    resolution: str = Field(..., pattern="^(confirmed|contradicted|unverifiable)$")
    evidence: str
    resolved_by: str = Field("implementer")


class ExpandIn(BaseModel):
    radius: BlastRadiusIn
    justification: str
    requested_by: str = Field("implementer")


class ReprioritiseIn(BaseModel):
    priority: str = Field(..., pattern="^(p0|p1|p2)$")
    actor: str = Field("founder")


def _radius(payload: BlastRadiusIn) -> BlastRadius:
    return BlastRadius.of(
        payload.allowed,
        forbidden=payload.forbidden,
        read_only=payload.read_only,
        justification=payload.justification,
    )


def _render(work_order) -> dict:
    return {
        "work_id": str(work_order.work_id),
        "version": work_order.version,
        "state": work_order.state.value,
        "priority": work_order.priority.value,
        "intent": work_order.intent,
        "acceptance_criteria": sorted(work_order.acceptance_criteria),
        "definition_of_done": sorted(work_order.definition_of_done),
        "adr_references": sorted(str(a) for a in work_order.adr_references),
        "evidence": sorted(str(e) for e in work_order.evidence),
        "constraints": sorted(str(c) for c in work_order.constraints),
        "dependencies": sorted(str(d) for d in work_order.dependencies),
        "blast_radius": {
            "allowed": sorted(str(p) for p in work_order.blast_radius.allowed),
            "forbidden": sorted(str(p) for p in work_order.blast_radius.forbidden),
            "read_only": sorted(str(p) for p in work_order.blast_radius.read_only),
            "justification": work_order.blast_radius.justification,
        },
        "assumptions": [
            {
                "assumption_id": str(a.assumption_id),
                "statement": a.statement,
                "verification_method": a.verification_method,
                "resolution": a.resolution.value if a.resolution else None,
                "resolution_evidence": (
                    str(a.resolution_evidence) if a.resolution_evidence else None
                ),
            }
            for a in work_order.assumptions
        ],
        "rejection_grounds": [
            {
                "ground_id": str(g.ground_id),
                "condition": g.condition,
                "rejection_type": g.rejection_type.value,
                "resolver": g.resolver.value,
                "triggering_assumption": (
                    str(g.triggering_assumption) if g.triggering_assumption else None
                ),
            }
            for g in work_order.rejection_grounds
        ],
        "digest": (
            {"algorithm": work_order.digest.algorithm.value, "value": work_order.digest.value}
            if work_order.digest
            else None
        ),
        "rejection": (
            {"type": work_order.rejection_type.value, "detail": work_order.rejection_detail}
            if work_order.rejection_type
            else None
        ),
        "created_at": work_order.created_at.isoformat(),
        "created_by": work_order.created_by,
        "superseded_by": str(work_order.superseded_by) if work_order.superseded_by else None,
    }


# ----------------------------------------------------------------------
# Error translation
# ----------------------------------------------------------------------


def _handle(operation):
    """Run a command, mapping domain refusals to status codes.

    A decorator would read better and would also swallow the traceback of an
    unexpected error, which is the one case worth keeping. Explicit is worth the
    repetition here.
    """
    try:
        return operation()
    except WorkOrderNotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except ValidationFailed as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            {
                "error": "validation_failed",
                "message": str(exc),
                "findings": [
                    {
                        "rule": f.rule,
                        "severity": f.severity.value,
                        "decidability": f.decidability.value,
                        "detail": f.detail,
                        "subject": f.subject,
                    }
                    for f in exc.findings
                ],
            },
        ) from exc
    except (InvalidTransition, TerminalState, DuplicateWorkOrder, DigestMismatch) as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    except ImmutableAfterApproval as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    except ContractViolation as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc


# ----------------------------------------------------------------------
# Routes
# ----------------------------------------------------------------------


@router.post("/work-orders", status_code=status.HTTP_201_CREATED, summary="Draft a WorkOrder")
async def draft_work_order_route(payload: DraftIn):
    def run():
        command = DraftWorkOrder(
            intent=payload.intent,
            acceptance_criteria=tuple(payload.acceptance_criteria),
            blast_radius=_radius(payload.blast_radius),
            definition_of_done=tuple(payload.definition_of_done),
            adr_references=tuple(payload.adr_references),
            evidence=tuple(payload.evidence),
            constraints=tuple(payload.constraints),
            assumptions=tuple(
                AssumptionSpec(
                    a.statement, a.verification_method, rejection_condition=a.rejection_condition
                )
                for a in payload.assumptions
            ),
            dependencies=tuple(payload.dependencies),
            priority=Priority(payload.priority),
            created_by=payload.created_by,
        )
        result = _service.draft(_context(), command)
        return {
            "work_order": _render(result.work_order),
            "events": [e.EVENT_TYPE for e in result.events],
        }

    return _handle(run)


@router.get("/work-orders", summary="List WorkOrders")
async def list_work_orders_route(
    state: Optional[str] = Query(None, description="Filter by lifecycle state"),
    active_only: bool = Query(False, description="Only non-terminal WorkOrders"),
):
    def run():
        parsed = WorkOrderState(state) if state else None
        found = _service.list(_context(), ListWorkOrders(state=parsed, active_only=active_only))
        return {"count": len(found), "work_orders": [_render(w) for w in found]}

    return _handle(run)


@router.get("/work-orders/{work_id}", summary="Fetch a WorkOrder")
async def get_work_order_route(
    work_id: str = Path(...),
    version: Optional[int] = Query(None, ge=1, description="Defaults to the latest"),
):
    return _handle(
        lambda: _render(_service.get(_context(), GetWorkOrder(work_id=work_id, version=version)))
    )


@router.get("/work-orders/{work_id}/versions", summary="Every version of a WorkOrder")
async def get_versions_route(work_id: str = Path(...)):
    def run():
        versions = _service.versions(_context(), work_id)
        if not versions:
            raise WorkOrderNotFound(work_id)
        return {"count": len(versions), "versions": [_render(w) for w in versions]}

    return _handle(run)


@router.get("/work-orders/{work_id}/validation", summary="Run every validation rule")
async def validate_route(work_id: str = Path(...)):
    def run():
        report = _service.validate(_context(), work_id)
        return {
            "approvable": report.approvable,
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


@router.post("/work-orders/{work_id}/approve", summary="Ratify a Draft and bind its digest")
async def approve_route(payload: ApproveIn, work_id: str = Path(...)):
    def run():
        result = _service.approve(
            _context(), ApproveWorkOrder(work_id=work_id, approved_by=payload.approved_by)
        )
        return {
            "work_order": _render(result.work_order),
            "events": [e.EVENT_TYPE for e in result.events],
        }

    return _handle(run)


@router.post("/work-orders/{work_id}/transition", summary="Move along the lifecycle")
async def transition_route(payload: TransitionIn, work_id: str = Path(...)):
    def run():
        try:
            target = WorkOrderState(payload.to_state)
        except ValueError as exc:
            raise ContractViolation(
                f"{payload.to_state!r} is not a WorkOrder state; valid states are: "
                + ", ".join(s.value for s in WorkOrderState)
            ) from exc
        result = _service.transition(
            _context(),
            TransitionWorkOrder(work_id=work_id, to_state=target, actor=payload.actor),
        )
        return {
            "work_order": _render(result.work_order),
            "events": [e.EVENT_TYPE for e in result.events],
        }

    return _handle(run)


@router.post("/work-orders/{work_id}/reject", summary="Close with a typed verdict")
async def reject_route(payload: RejectIn, work_id: str = Path(...)):
    def run():
        try:
            rejection_type = RejectionType(payload.rejection_type)
        except ValueError as exc:
            raise ContractViolation(
                f"{payload.rejection_type!r} is not a rejection type; valid types are: "
                + ", ".join(t.value for t in RejectionType)
            ) from exc
        result = _service.reject(
            _context(),
            RejectWorkOrder(
                work_id=work_id,
                rejection_type=rejection_type,
                detail=payload.detail,
                raised_by=payload.raised_by,
            ),
        )
        return {
            "work_order": _render(result.work_order),
            "resolver": rejection_type.resolver.value,
            "events": [e.EVENT_TYPE for e in result.events],
        }

    return _handle(run)


@router.post(
    "/work-orders/{work_id}/assumptions/{assumption_id}/resolve",
    summary="Record the outcome of checking an assumption",
)
async def resolve_assumption_route(
    payload: ResolveAssumptionIn,
    work_id: str = Path(...),
    assumption_id: str = Path(...),
):
    def run():
        result = _service.resolve_assumption(
            _context(),
            ResolveAssumption(
                work_id=work_id,
                assumption_id=assumption_id,
                resolution=AssumptionResolution(payload.resolution),
                evidence=payload.evidence,
                resolved_by=payload.resolved_by,
            ),
        )
        return {
            "work_order": _render(result.work_order),
            "events": [e.EVENT_TYPE for e in result.events],
        }

    return _handle(run)


@router.post("/work-orders/{work_id}/blast-radius/expand", summary="Widen scope and re-approve")
async def expand_route(payload: ExpandIn, work_id: str = Path(...)):
    def run():
        result = _service.expand_blast_radius(
            _context(),
            ExpandBlastRadius(
                work_id=work_id,
                radius=_radius(payload.radius),
                justification=payload.justification,
                requested_by=payload.requested_by,
            ),
        )
        return {
            "work_order": _render(result.work_order),
            "events": [e.EVENT_TYPE for e in result.events],
        }

    return _handle(run)


@router.post("/work-orders/{work_id}/priority", summary="Change scheduling order")
async def reprioritise_route(payload: ReprioritiseIn, work_id: str = Path(...)):
    def run():
        result = _service.reprioritise(
            _context(),
            Reprioritise(work_id=work_id, priority=Priority(payload.priority), actor=payload.actor),
        )
        return {"work_order": _render(result.work_order)}

    return _handle(run)


@router.post("/blast-radius/conflicts", summary="Which active WorkOrders contend for these paths")
async def conflicts_route(payload: BlastRadiusIn):
    def run():
        found = _service.conflicts(
            _context(), CheckBlastRadiusConflicts(radius=_radius(payload))
        )
        return {
            "conflicting": len(found),
            "conflicts": [
                {"work_id": c.work_id, "state": c.state, "patterns": list(c.patterns)}
                for c in found
            ],
        }

    return _handle(run)
