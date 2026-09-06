"""The product's approval and remediation surface — Phase 10.3 (ADR-096).

This is the **only** module in the product API that accepts a non-GET request.
It is a separate file from ``routes.py`` for exactly that reason: the mutation
surface of the product should be one short file a reviewer can read end to end,
rather than three verbs scattered through a hundred lines of read projections.

What a client may send
----------------------
Three request bodies exist, and between them they carry a decision word, an
optional justification, and nothing else. Every model sets ``extra="forbid"``,
so a request carrying ``tenant_id``, ``action_digest``, ``risk``,
``autonomy_level``, ``actor``, ``capability`` or any other authority field is
**rejected with 422** rather than accepted-and-ignored.

Ignoring would be safe. Rejecting is honest: it turns an attempt to smuggle
authority into a visible refusal instead of an invisible success, and it means
nobody can later add a field to a handler and have old clients silently start
being trusted.

Where authority actually lives
------------------------------
* tenant and principal: the verified JWT, via ``product_context``
* capability, payload, digests, environment: reconstructed by ``RemediationService``
* whether an approval covers an action: ``ApprovalFacts.is_valid_for``
* whether it covers *this* action: the gateway's action-digest comparison
* whether the action may run at all: ``CapabilityAuthorizationService``
* what actually happened: the World Plane and Assurance, never a worker response
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from pydantic import BaseModel, ConfigDict, Field

from backend.api.product.context import ProductContext, product_context
from backend.api.product.schemas import (
    ApprovalList,
    ApprovalQueue,
    ApprovalQueueItem,
    ApprovalView,
    ErrorResponse,
    RemediationOutcomeView,
    RemediationProposalView,
)

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["CortexPrime Remediation"])

_ERRORS = {
    401: {"model": ErrorResponse, "description": "Not authenticated"},
    403: {"model": ErrorResponse, "description": "No tenant, or tenant inactive"},
    404: {"model": ErrorResponse, "description": "Not found for this tenant"},
    409: {"model": ErrorResponse, "description": "Not in a state that allows this"},
}

#: The complete set of non-GET routes in the product API. The harness asserts the
#: application's actual mutating routes equal this exactly, so a fourth one
#: cannot appear without the assertion failing.
MUTATING_ROUTES = (
    ("POST", "/api/v1/investigations/{investigation_ref}/remediation/approval-request"),
    ("POST", "/api/v1/approvals/{approval_id}/decision"),
    ("POST", "/api/v1/approvals/{approval_id}/execute"),
)

#: The one operation Phase 9 commissioned. Named here rather than accepted from a
#: request: a client that could choose the operation could choose a capability
#: the platform never intended to expose to a product caller.
COMMISSIONED_OPERATION = "kubernetes.workload.rollout_restart"


# ----------------------------------------------------------------------
# Request bodies. Deliberately almost empty.
# ----------------------------------------------------------------------

class ApprovalRequestBody(BaseModel):
    """What a human may say when asking for an action to be approved.

    A justification, and nothing else. The action itself is not in here because
    the action is not the client's to describe.
    """

    model_config = ConfigDict(extra="forbid")

    justification: Optional[str] = Field(
        default=None, max_length=2000,
        description="Free text for the audit record. Carries no authority.")


class DecisionBody(BaseModel):
    """A human's decision. One word, plus optional reasoning."""

    model_config = ConfigDict(extra="forbid")

    decision: str = Field(pattern="^(approve|reject)$")
    justification: Optional[str] = Field(default=None, max_length=2000)
    #: Typed by the operator to confirm they read the preview. Checked against
    #: the workload the SERVER stored, so it is a confirmation, not an input:
    #: getting it wrong refuses, and getting it right changes nothing about what
    #: will run.
    confirm_workload: Optional[str] = Field(default=None, max_length=200)


class ExecuteBody(BaseModel):
    """Empty on purpose. Everything needed is already stored."""

    model_config = ConfigDict(extra="forbid")


# ----------------------------------------------------------------------

def _engine():
    from backend.api.product.routes import get_engine
    return get_engine()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _require(feature: Any, what: str):
    if feature is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"{what} is not composed in this process")
    return feature


def _principal_ref(ctx: ProductContext) -> str:
    """The approver's identity, as a namespaced reference.

    Built from the verified session. There is no code path that reads an actor
    from a request, so ``"admin"`` in a body is not ignored -- it is impossible
    to express, because the field does not exist on any model above.
    """
    return f"human:{ctx.principal.principal_id}"



def _scoped_authority(ctx: ProductContext, record, *, action: str):
    """Scope for ONE stored approval, for one action (Phase 10.7).

    Every dimension is read from the approval row and the capability contract:
    the capability it names, the environment it was raised in, and the risk the
    platform derives from the declared effect. Nothing here is read from the
    request -- the request models forbid extra fields, so an attempt to supply a
    capability, environment or risk is a 422 rather than a silent ignore.

    Risk is derived with ``implied_risk_for``, the platform's own function, so a
    grant's ceiling is compared against the same classification authorization
    would use. An approval whose capability cannot be resolved gets CRITICAL --
    the safe end -- rather than a permissive default.
    """
    from backend.auth.approver import resolve_scoped_authority
    from backend.contexts.connectivity.domain.authorization import implied_risk_for

    engine = _engine()
    definitions = getattr(
        getattr(engine, "remediation", None), "_definitions", {}) or {}
    definition = definitions.get(record.operation)
    contract = getattr(definition, "contract", None)
    risk = implied_risk_for(getattr(contract, "effect_semantics", None),
                            getattr(contract, "side_effect_class", None)).value

    return resolve_scoped_authority(
        principal_id=ctx.principal.principal_id,
        tenant_id=ctx.tenant_id,
        action=action,
        capability_ref=record.capability_ref,
        environment=record.environment,
        risk=risk,
        grants=getattr(engine, "grants", None),
        memberships=getattr(engine, "memberships", None),
    )


def _proposal_for(ctx: ProductContext, investigation_ref: str):
    from backend.api.product.routes import _load

    engine = _engine()
    service = _require(getattr(engine, "remediation", None), "remediation")
    investigation = _load(ctx, investigation_ref)
    from backend.api.product.remediation import RemediationUnavailable
    try:
        return investigation, service.propose(
            investigation=investigation,
            tenant_id=ctx.tenant_id,
            principal_id=ctx.principal.principal_id,
            operation=COMMISSIONED_OPERATION,
        )
    except RemediationUnavailable as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=str(exc)) from None


def _proposal_view(proposal) -> RemediationProposalView:
    return RemediationProposalView(
        investigation_ref=proposal.investigation_ref,
        capability_ref=proposal.capability_ref,
        capability_version=proposal.capability_version,
        capability_digest=proposal.capability_digest,
        operation=proposal.operation,
        provider=proposal.provider,
        tenant_id=proposal.tenant_id,
        principal_id=proposal.principal_id,
        environment=proposal.environment,
        namespace=proposal.namespace,
        workload=proposal.workload,
        parameters=dict(proposal.payload),
        side_effect_class=proposal.side_effect_class,
        effect_semantics=proposal.effect_semantics,
        code_trust=proposal.code_trust,
        isolation_tier=proposal.isolation_tier,
        reversible=proposal.reversible,
        blast_radius=(f"one Deployment ({proposal.workload}) in one namespace "
                      f"({proposal.namespace}); its pods are replaced"),
        approval_required=proposal.approval_required,
        autonomy_ceiling=proposal.autonomy_ceiling,
        approval_digest=proposal.approval_digest,
        evidence_refs=proposal.evidence_refs,
        diagnosis=proposal.diagnosis,
    )


def _approval_view(record) -> ApprovalView:
    return ApprovalView(
        approval_id=record.approval_id,
        investigation_ref=record.investigation_ref,
        capability_ref=record.capability_ref,
        capability_digest=record.capability_digest,
        operation=record.operation,
        environment=record.environment,
        namespace=str((record.payload or {}).get("namespace") or ""),
        workload=str((record.payload or {}).get("name") or ""),
        parameters=dict(record.payload or {}),
        approval_digest=record.approval_digest,
        state=record.outcome,
        requested_by=record.requested_by,
        decided_by=record.decided_by,
        justification=record.justification,
        requested_at=_iso(record.requested_at),
        decided_at=_iso(record.decided_at),
        expires_at=_iso(record.expires_at),
        expired=record.is_expired_at(_now()),
        consumed_by_execution=record.consumed_by_execution,
    )


def _iso(moment) -> Optional[str]:
    return moment.isoformat() if isinstance(moment, datetime) else None


def _load_approval(ctx: ProductContext, approval_id: str):
    engine = _engine()
    approvals = _require(getattr(engine, "approvals", None), "the approval store")
    record = approvals.get(tenant_id=ctx.tenant_id, approval_id=approval_id)
    if record is None:
        # A cross-tenant approval and a nonexistent one answer identically, for
        # the reason recorded in ADR-094: the difference is the disclosure.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="no such approval for this tenant")
    return record


# ----------------------------------------------------------------------
# Reads
# ----------------------------------------------------------------------

@router.get("/investigations/{investigation_ref}/remediation",
            response_model=RemediationProposalView, responses=_ERRORS,
            summary="The governed remediation the platform would perform, with "
                    "every value derived from the capability contract")
def get_remediation(
    investigation_ref: str = Path(min_length=1, max_length=200),
    ctx: ProductContext = Depends(product_context),
) -> RemediationProposalView:
    _, proposal = _proposal_for(ctx, investigation_ref)
    return _proposal_view(proposal)


#: Which stored outcomes each queue filter selects. A filter names a STATE a
#: responder thinks in; the mapping to stored outcomes happens here, server-side,
#: so a client cannot ask for a raw outcome value the projection does not model.
_STATUS_FILTERS = {
    "actionable": ("pending",),
    "pending": ("pending",),
    "decided": ("granted", "denied", "withdrawn"),
    "approved": ("granted",),
    "rejected": ("denied",),
    "revoked": ("withdrawn",),
    "all": None,
}


@router.get("/approvals", response_model=ApprovalQueue, responses=_ERRORS,
            summary="The tenant's approval queue, across every investigation")
def list_approvals(
    ctx: ProductContext = Depends(product_context),
    limit: int = Query(25, ge=1, le=100),
    status: str = Query(
        "all",
        pattern="^(actionable|pending|decided|approved|rejected|revoked|all)$"),
    risk: Optional[str] = Query(default=None, pattern="^(low|medium|high|critical)$"),
    capability_ref: Optional[str] = Query(default=None, max_length=200),
    operation: Optional[str] = Query(default=None, max_length=200),
    investigation_ref: Optional[str] = Query(default=None, max_length=200),
    older_than_minutes: Optional[int] = Query(default=None, ge=0, le=525600),
) -> ApprovalQueue:
    """Every approval this tenant may see, from one place.

    The primary product goal: a responder should not have to know which
    investigation raised a request in order to find it.

    Tenant scope is applied by the repository as the FIRST predicate, and every
    filter narrows that set. No filter can widen it and none is evaluated before
    it -- a filter that could be would be a filter that escapes the tenant
    boundary.
    """
    from backend.api.product.approval_queue import (
        ACTIONABLE_STATES, order_queue, project_queue_item, utc_now,
    )
    from backend.api.product.context import approver_authority

    # Resolved ONCE per request, from the store. The queue reports whether this
    # caller may decide each row; it does not decide anything, and the answer it
    # shows is the same one the decision route will enforce.
    authority = approver_authority(ctx)
    engine = _engine()
    approvals = _require(getattr(engine, "approvals", None), "the approval store")
    now = utc_now()

    requested_before = None
    if older_than_minutes is not None:
        requested_before = now - timedelta(minutes=older_than_minutes)

    records = approvals.list_for_tenant(
        tenant_id=ctx.tenant_id,
        # Over-fetch before the derived filters below, so a page is not silently
        # short. Still bounded, and still tenant-scoped in SQL.
        limit=min(limit * 4, 400),
        investigation_ref=investigation_ref,
        outcomes=_STATUS_FILTERS.get(status),
        capability_ref=capability_ref,
        operation=operation,
        requested_before=requested_before,
    )

    definitions = getattr(
        getattr(engine, "remediation", None), "_definitions", {}) or {}

    # Two passes, deliberately.
    #
    # The first projects every candidate WITHOUT investigation context, because
    # none of the governed fields, the derived state or the ordering depends on
    # it -- they come from the approval row and the capability contract. The
    # second enriches only the rows that survived filtering and truncation.
    #
    # Reconstructing an investigation is an event-sourced replay. Doing it for
    # every over-fetched candidate meant replaying up to four times more
    # investigations than the page returns, which measured as a slow list for no
    # benefit to the caller. This is an algorithmic fix, not an index added to
    # flatter a benchmark.
    candidates = []
    for record in records:
        item = project_queue_item(
            record, definition=definitions.get(record.operation), now=now,
            authority=authority, actor=_principal_ref(ctx),
            approve_scope=_scoped_authority(ctx, record, action="approve"),
            execute_scope=_scoped_authority(ctx, record, action="execute"))
        # Derived filters, applied AFTER the tenant-scoped read. "actionable" is
        # a derived state -- a pending approval past its expiry is not
        # actionable -- so it cannot be expressed as a stored-outcome predicate.
        if status == "actionable" and item["state"] not in ACTIONABLE_STATES:
            continue
        if risk is not None and item["risk"] != risk:
            continue
        candidates.append((record, item))

    page = order_queue([item for _, item in candidates])[:limit]
    wanted = {item["approval_id"] for item in page}
    context = {
        record.approval_id: _investigation_context(ctx, record)
        for record, _ in candidates if record.approval_id in wanted
    }
    ordered = [
        project_queue_item(
            record, definition=definitions.get(record.operation), now=now,
            investigation=context.get(record.approval_id), authority=authority,
            actor=_principal_ref(ctx),
            approve_scope=_scoped_authority(ctx, record, action="approve"),
            execute_scope=_scoped_authority(ctx, record, action="execute"))
        for record, item in candidates if item["approval_id"] in wanted
    ]
    ordered = order_queue(ordered)[:limit]
    return ApprovalQueue(
        items=tuple(ApprovalQueueItem(**item) for item in ordered),
        count=len(ordered),
        actionable_count=sum(1 for i in ordered if i["actionable"]),
        limit=limit,
        filters={
            "status": status, "risk": risk, "capability_ref": capability_ref,
            "operation": operation, "investigation_ref": investigation_ref,
            "older_than_minutes": older_than_minutes,
        },
        note=("Every approval this tenant may see, from every investigation. "
              "Only rows marked actionable can still be decided, and only by a "
              "caller holding approver authority in this tenant."),
        viewer_can_approve=authority.permitted,
        viewer_authority_reason=authority.reason,
    )


def _investigation_context(ctx: ProductContext, record):
    """Triage context for one approval, or nothing.

    Read under the AUTHENTICATED tenant through the same service the workspace
    uses, so an approval cannot become a way to reach an investigation the
    caller could not otherwise read. A failure here degrades the row's context
    and never its safety: every governed field comes from the approval row and
    the capability contract, not from here.
    """
    if not getattr(record, "investigation_ref", None):
        return None
    try:
        engine = _engine()
        return engine.investigations.reconstruct(
            tenant=ctx.tenant, investigation_ref=record.investigation_ref)
    except Exception:  # noqa: BLE001 - context is optional; safety is not
        return None


@router.get("/approvals/{approval_id}", response_model=ApprovalQueueItem,
            responses=_ERRORS,
            summary="One approval, with the full authoritative action preview")
def get_approval(
    approval_id: str = Path(min_length=1, max_length=200),
    ctx: ProductContext = Depends(product_context),
) -> ApprovalQueueItem:
    """The same projection the queue shows, for one approval.

    Deliberately the SAME function as the list. Two projections of one approval
    would be two chances to show different actions for the same digest, and the
    row a responder triaged must be the action they decide on.
    """
    from backend.api.product.approval_queue import project_queue_item, utc_now
    from backend.api.product.context import approver_authority

    engine = _engine()
    record = _load_approval(ctx, approval_id)
    definitions = getattr(
        getattr(engine, "remediation", None), "_definitions", {}) or {}
    return ApprovalQueueItem(**project_queue_item(
        record, definition=definitions.get(record.operation), now=utc_now(),
        investigation=_investigation_context(ctx, record),
        authority=approver_authority(ctx), actor=_principal_ref(ctx),
        approve_scope=_scoped_authority(ctx, record, action="approve"),
        execute_scope=_scoped_authority(ctx, record, action="execute")))


@router.get("/remediations/{execution_ref}", response_model=RemediationOutcomeView,
            responses=_ERRORS,
            summary="What is actually established about a remediation")
def get_remediation_outcome(
    execution_ref: str = Path(min_length=1, max_length=200),
    ctx: ProductContext = Depends(product_context),
) -> RemediationOutcomeView:
    """Only stages backend evidence establishes.

    In particular ``world_changed`` comes from an INDEPENDENT World observation
    and ``assurance_verdict`` from Assurance. A worker's own reply that it
    succeeded establishes nothing here -- Phase 9.10's finding was that a POST
    to a worker is not a mutation of Kubernetes, and this endpoint is where a
    product would most easily forget it.
    """
    engine = _engine()
    approvals = _require(getattr(engine, "approvals", None), "the approval store")
    record = None
    for candidate in approvals.list_for_tenant(tenant_id=ctx.tenant_id, limit=200):
        if candidate.consumed_by_execution == execution_ref:
            record = candidate
            break
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="no such remediation for this tenant")

    subject = (f"kubernetes:deployment:{(record.payload or {}).get('namespace')}"
               f"/{(record.payload or {}).get('name')}")
    world_status = None
    world_value = None
    observed_at = None
    world_query = getattr(engine, "world_query", None)
    if world_query is not None:
        try:
            result = world_query.current(
                tenant=ctx.tenant, subject_ref=subject,
                predicate="deployed_revision", now=_now())
            world_status = str(getattr(getattr(result, "effective_status", None), "value", "") or "")
            value = getattr(result, "effective_value", None)
            world_value = None if value is None else str(value)[:400]
            evidence = getattr(result, "evidence", ()) or ()
            observed_at = _iso(getattr(evidence[0], "observed_at", None)) if evidence else None
        except Exception:  # noqa: BLE001 - a failed read is not a failed remediation
            log.warning("world read failed for remediation outcome", exc_info=True)

    verdicts = []
    verifications = getattr(engine, "verifications", None)
    if verifications is not None:
        try:
            for verification in verifications.list_for_subject(
                    tenant_id=ctx.tenant_id, subject_ref=subject,
                    predicate="deployed_revision"):
                verdicts.append(str(getattr(getattr(verification, "verdict", None),
                                            "value", "") or ""))
        except Exception:  # noqa: BLE001
            log.warning("assurance read failed", exc_info=True)

    return RemediationOutcomeView(
        execution_ref=execution_ref,
        approval_id=record.approval_id,
        subject_ref=subject,
        action_requested=True,
        action_approved=record.outcome == "granted",
        execution_started=True,
        # Established by an independent read, not by anything the worker said.
        world_status=world_status,
        world_value=world_value,
        world_observed_at=observed_at,
        assurance_verdicts=tuple(verdicts),
        read_at=_now().isoformat(),
    )


# ----------------------------------------------------------------------
# The three mutating routes
# ----------------------------------------------------------------------

@router.post("/investigations/{investigation_ref}/remediation/approval-request",
             response_model=ApprovalView, responses=_ERRORS, status_code=201,
             summary="Ask a human to approve the governed remediation")
def request_approval(
    body: ApprovalRequestBody,
    investigation_ref: str = Path(min_length=1, max_length=200),
    ctx: ProductContext = Depends(product_context),
) -> ApprovalView:
    """The request identifies an investigation. Nothing else.

    The action is rebuilt from the investigation and the capability contract, and
    the approval digest is computed here with the platform's own function -- so
    the approval is bound to an action the client never got to describe.
    """
    engine = _engine()
    service = _require(getattr(engine, "remediation", None), "remediation")
    from backend.api.product.remediation import RemediationUnavailable

    _, proposal = _proposal_for(ctx, investigation_ref)
    try:
        approval_id = service.request_approval(
            proposal=proposal, requested_by=_principal_ref(ctx),
            justification=body.justification, now=_now())
    except RemediationUnavailable as exc:
        # A refusal, not a crash. Returning 500 here would report a governed
        # decision as a malfunction.
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail=str(exc)) from None
    return _approval_view(_load_approval(ctx, approval_id))


@router.post("/approvals/{approval_id}/decision", response_model=ApprovalView,
             responses=_ERRORS, summary="A human grants or refuses this exact action")
def decide_approval(
    body: DecisionBody,
    approval_id: str = Path(min_length=1, max_length=200),
    ctx: ProductContext = Depends(product_context),
) -> ApprovalView:
    """Explicit, per-action, and attributed to the authenticated human.

    There is no "approve all", no tenant-wide grant and no auto-approval,
    because there is no route that could express one: this handler decides
    exactly the approval named in the path and nothing else.
    """
    from backend.api.product.context import approver_authority
    from backend.auth.approver import APPROVE_ACTION, decision_separation
    from backend.contracts.approval import ApprovalOutcome

    engine = _engine()
    approvals = _require(getattr(engine, "approvals", None), "the approval store")

    # Phase 10.5. Tenant membership is no longer sufficient to decide an
    # irreversible action: the caller must hold an explicit approver grant in
    # THIS tenant, resolved live from the authoritative store.
    #
    # It is checked here, before the approval is even loaded, so a caller
    # without authority learns nothing about which approvals exist. And it is
    # read from the store rather than the token, so a revoked grant stops
    # working on the next request instead of at token expiry.
    authority = approver_authority(ctx)
    if authority.denied:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"no approver authority in this tenant ({authority.reason})")

    record = _load_approval(ctx, approval_id)

    # Phase 10.7. Holding approver authority in the tenant is no longer enough:
    # the grant must cover THIS capability, in THIS environment, within its
    # declared risk ceiling. Checked against the stored approval, never against
    # anything the caller sent.
    scope = _scoped_authority(ctx, record, action=APPROVE_ACTION)
    if scope.denied:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(f"{scope.reason}: your approval authority does not cover "
                    "this action"))

    # Phase 10.6. The human who asked for this action may not be the one who
    # allows it -- for EITHER decision. A rule that stopped the requester
    # approving but let them reject would leave them able to bury their own
    # request, which is the same authority wearing a different hat.
    #
    # Position is inherited, not invented: CapabilityPolicy.evaluate checks
    # authorization first, separation of duties second, and state concerns
    # after. So an approval that is both expired AND self-decided answers
    # SEPARATION_OF_DUTIES, while an independent approver on that same expired
    # approval gets the expiry.
    separation = decision_separation(
        requested_by=record.requested_by, actor=_principal_ref(ctx))
    if separation.denied:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(f"{separation.reason}: the human who requested this "
                    "remediation may not decide it"))

    if body.decision == "approve":
        # A confirmation, checked against what the SERVER stored. It cannot
        # change what runs; getting it wrong only refuses.
        expected = str((record.payload or {}).get("name") or "")
        if body.confirm_workload is not None and body.confirm_workload != expected:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="the confirmation does not match the workload this "
                       "approval is bound to")
        if record.is_expired_at(_now()):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                                detail="this approval request has expired")

    # The authority actually used is recorded alongside the reason. An audit
    # trail that says who decided but not what entitled them to is an audit
    # trail that cannot answer the question it exists for.
    justification = body.justification or ""
    provenance = (f"[authority={authority.reason}"
                  f" scope={scope.matched_grant}"
                  f" membership_role={authority.membership_role}]")
    decided = approvals.decide(
        approval_id=approval_id, tenant_id=ctx.tenant_id,
        outcome=(ApprovalOutcome.GRANTED if body.decision == "approve"
                 else ApprovalOutcome.DENIED),
        decided_by=_principal_ref(ctx), decided_at=_now(),
        justification=(f"{justification} {provenance}".strip())[:2000])
    if not decided:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="this approval has already been decided")
    return _approval_view(_load_approval(ctx, approval_id))


@router.post("/approvals/{approval_id}/execute",
             response_model=RemediationOutcomeView, responses=_ERRORS,
             summary="Run the approved action through the existing governed chain")
def execute_approval(
    body: ExecuteBody,
    approval_id: str = Path(min_length=1, max_length=200),
    ctx: ProductContext = Depends(product_context),
) -> RemediationOutcomeView:
    """No new execution path.

    This calls ``GovernedCapabilityWriter.write`` with the payload from the
    stored approval row. Authorization re-evaluates policy, the gateway
    re-checks the approval against the action digest, resolution binds a worker,
    and the CONTAINED worker performs the write. If any of them refuses, this
    returns that refusal; it has no way to proceed past one.
    """
    engine = _engine()
    service = _require(getattr(engine, "remediation", None), "remediation")
    runtime = _require(getattr(engine, "runtime", None), "the governed runtime")
    context_factory = _require(
        getattr(engine, "execution_context_factory", None), "the execution context")
    record = _load_approval(ctx, approval_id)

    if record.outcome != "granted":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="this action has not been approved")

    # Phase 10.7. Until now ANY tenant member could execute ANY granted
    # approval. Executing is a third act, distinct from requesting it and from
    # allowing it, and it now needs its own scoped grant covering this
    # capability and environment.
    #
    # Deliberately NOT a separation rule: the requester may execute, the
    # approver may execute, a third party may execute -- each only if they hold
    # execution scope. Phase 10.6's invariant is `requester != approver` and
    # nothing more; turning it into `requester != executor` here would be
    # inventing governance.
    from backend.auth.approver import EXECUTE_ACTION

    executor = _scoped_authority(ctx, record, action=EXECUTE_ACTION)
    if executor.denied:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(f"{executor.reason}: you are not authorized to execute "
                    "this action"))

    from backend.contracts.identity import PrincipalKind, PrincipalRef

    principal = PrincipalRef(principal_id=record.principal_id,
                             kind=PrincipalKind.HUMAN)
    try:
        outcome = service.execute(
            runtime=runtime,
            context=context_factory(ctx.tenant_id, record.principal_id),
            approval_record=record, principal=principal)
    except Exception as exc:  # noqa: BLE001 - a refusal is an answer, not a crash
        log.warning("governed remediation refused", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"the governed chain refused this action: {type(exc).__name__}"
        ) from None

    # A refusal from the governed chain is RETURNED, not raised: the writer
    # answers with an outcome carrying ``succeeded=False``. Reporting that as
    # HTTP 200 would make a refused action indistinguishable from a performed
    # one to any client that trusts the status code -- which is precisely the
    # "a green tick that means only HTTP 200" failure this phase forbids.
    #
    # Found by the negative matrix: an approval bound to billing-api's digest
    # was correctly refused by governance (zero cluster mutations) and this
    # endpoint still answered 200.
    if not getattr(outcome, "succeeded", False):
        reason = str(getattr(outcome, "failure_reason", "") or "refused")[:200]
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"the governed chain refused this action: {reason}")

    execution_ref = str(getattr(outcome, "execution_ref", None)
                        or getattr(outcome, "execution_id", None) or "")
    if execution_ref:
        approvals = getattr(engine, "approvals", None)
        if approvals is not None:
            approvals.mark_consumed(approval_id=approval_id,
                                    tenant_id=ctx.tenant_id,
                                    execution_ref=execution_ref)

    subject = (f"kubernetes:deployment:{(record.payload or {}).get('namespace')}"
               f"/{(record.payload or {}).get('name')}")
    return RemediationOutcomeView(
        execution_ref=execution_ref,
        approval_id=approval_id,
        subject_ref=subject,
        action_requested=True,
        action_approved=True,
        execution_started=True,
        # Deliberately absent here. What the world now looks like is a separate
        # question answered by a separate, independent read -- not by whatever
        # the execution returned a moment ago.
        world_status=None,
        world_value=None,
        world_observed_at=None,
        assurance_verdicts=(),
        read_at=_now().isoformat(),
        note="Execution accepted by the governed chain. Whether the world "
             "changed is established by an independent World observation, not "
             "by this response.",
    )
