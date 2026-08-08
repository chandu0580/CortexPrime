"""Capability Authorization API (BC-8, Phase 3.2.3).

Mounted at ``/api/v1/capability-authorization``.

**This API decides. It never acts.** There is no execute route, no invoke route,
and nothing here calls a worker, a connector, or an MCP server. The most it
produces is a signed-shaped, expiring, bound decision that some later phase may
present at admission.

Two operations, separately observable:

``POST /decisions``   — authorize. *Is this principal permitted?*
``POST /admissions``  — admit. *May this proceed right now?* Re-reads the
                        authoritative record, so a capability revoked since the
                        decision is refused here.

Status codes:

``200`` — a decision was reached. **Including a denial.** A refusal is a
successful evaluation with a negative answer, and returning 4xx for it would
conflate "you may not" with "your request was malformed" — which matters,
because the first is an audited security fact and the second is not.

``400`` — the request could not be understood well enough to decide.

Cross-tenant requests receive ``capability_not_found``, never a reason that
would confirm the capability exists.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from backend.contracts.errors import ContractViolation
from backend.contracts.identity import PrincipalKind, PrincipalRef
from backend.contexts.connectivity import (
    AuthorizationRequest,
    BreakGlass,
    CapabilityEnvironment,
    CapabilityOperation,
    CapabilityRef,
)
from backend.platform.context import ExecutionContext
from backend.platform.context.identity import IdentityContext

router = APIRouter(
    prefix="/api/v1/capability-authorization", tags=["Capability Authorization"]
)

_OPERATION = (
    "^(invoke|inspect|register|validate|enable|disable|deprecate|revoke|trust|quarantine)$"
)
_PRINCIPAL_KIND = "^(human|platform|external_system)$"
_ENVIRONMENT = "^(development|staging|production)$"


def _authorization():
    from backend.api import capability_authorization_composition as composition
    from backend.api import capability_routes

    global _SERVICE
    if _SERVICE is None:
        _SERVICE = composition.build_authorization(capability_routes._service)
    return _SERVICE


_SERVICE = None


class PrincipalIn(BaseModel):
    principal_id: str
    kind: str = Field("human", pattern=_PRINCIPAL_KIND)
    display_name: Optional[str] = None


class BreakGlassIn(BaseModel):
    reason: str = Field(..., min_length=1)
    expires_at: datetime
    ticket_reference: Optional[str] = None


class DecisionIn(BaseModel):
    """An authorization question.

    ``capability_ref`` is pinned (``id@version``) and ``expected_digest`` is
    required for ``invoke``: a request that does not state which contract it
    believes it is authorizing is asking about whatever the version currently
    says.
    """

    tenant_id: str
    principal: PrincipalIn
    capability_ref: str = Field(
        ..., description="Pinned reference, e.g. platform.github.create_issue@1"
    )
    operation: str = Field(..., pattern=_OPERATION)
    expected_digest: Optional[str] = None
    environment: Optional[str] = Field(None, pattern=_ENVIRONMENT)
    grants: List[str] = Field(
        default_factory=list,
        description=(
            "Grants the caller's identity carries. In a deployed system these "
            "come from the authenticated session, not the request body."
        ),
    )
    mission_id: Optional[str] = None
    workflow_id: Optional[str] = None
    execution_id: Optional[str] = None
    node_id: Optional[str] = None
    approval_artifact_id: Optional[str] = None
    justification: Optional[str] = None
    break_glass: Optional[BreakGlassIn] = None


class AdmissionIn(DecisionIn):
    """Re-present a decision at the moment it becomes actionable."""

    decision_digest: str = Field(
        ..., description="The digest of the decision being presented"
    )
    decided_at: datetime
    expires_at: datetime
    capability_digest: str
    policy_version: str
    risk: str = Field(
        ...,
        pattern="^(low|medium|high|critical)$",
        description=(
            "The risk the decision recorded. Part of the decision digest, so it "
            "must be presented back for the integrity check to recompute."
        ),
    )


def _context(payload: DecisionIn) -> ExecutionContext:
    return ExecutionContext.for_tenant(
        tenant_id=payload.tenant_id,
        identity=IdentityContext(
            principal=PrincipalRef(
                principal_id=payload.principal.principal_id,
                kind=PrincipalKind(payload.principal.kind),
                display_name=payload.principal.display_name,
            ),
            capabilities=tuple(payload.grants),
        ),
        source="http",
    )


def _request(payload: DecisionIn) -> AuthorizationRequest:
    return AuthorizationRequest(
        tenant_id=payload.tenant_id,
        principal=PrincipalRef(
            principal_id=payload.principal.principal_id,
            kind=PrincipalKind(payload.principal.kind),
            display_name=payload.principal.display_name,
        ),
        capability_ref=CapabilityRef.parse(payload.capability_ref),
        operation=CapabilityOperation(payload.operation),
        expected_digest=payload.expected_digest,
        environment=(
            CapabilityEnvironment(payload.environment) if payload.environment else None
        ),
        mission_id=payload.mission_id,
        workflow_id=payload.workflow_id,
        execution_id=payload.execution_id,
        node_id=payload.node_id,
        approval_artifact_id=payload.approval_artifact_id,
        justification=payload.justification,
        break_glass=(
            BreakGlass(
                invoked_by=PrincipalRef(
                    principal_id=payload.principal.principal_id,
                    kind=PrincipalKind(payload.principal.kind),
                ),
                reason=payload.break_glass.reason,
                expires_at=payload.break_glass.expires_at,
                ticket_reference=payload.break_glass.ticket_reference,
            )
            if payload.break_glass
            else None
        ),
    )


def _handle(operation):
    try:
        return operation()
    except ContractViolation as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc


@router.post("/decisions", summary="Authorize. Produces a decision, never an action")
async def authorize_route(payload: DecisionIn):
    def run():
        decision = _authorization().authorize(_context(payload), _request(payload))
        return {
            "decision": decision.to_dict(),
            "allowed": decision.allowed,
            "requires_approval": decision.requires_approval,
            "reasons": list(decision.reason_codes),
        }

    return _handle(run)


@router.post(
    "/admissions",
    summary="Admit. Re-checks authoritative state at the point of action",
)
async def admit_route(payload: AdmissionIn):
    def run():
        from backend.contexts.connectivity import AuthorizationDecision
        from backend.contracts.policy import PolicyEffect, RiskLevel

        request = _request(payload)
        # The presented decision is reconstructed and re-checked; it is never
        # trusted as a token. Admission re-reads the registry regardless.
        presented = AuthorizationDecision(
            effect=PolicyEffect.ALLOW,
            request=request,
            policy_version=payload.policy_version,
            decided_at=payload.decided_at,
            expires_at=payload.expires_at,
            binding_key=request.binding_key,
            capability_digest=payload.capability_digest,
            risk=RiskLevel(payload.risk),
        ).sealed()

        if presented.digest != payload.decision_digest:
            # A decision whose digest does not recompute was altered in transit.
            return {
                "admitted": False,
                "reasons": ["binding_mismatch"],
                "detail": "the presented decision does not match its own digest",
            }

        outcome = _authorization().admit(_context(payload), presented, request)
        return {
            "admitted": outcome.allowed,
            "reasons": list(outcome.reason_codes),
            "decision": outcome.to_dict(),
        }

    return _handle(run)


@router.get("/policy", summary="Which policy this deployment is running")
async def policy_route():
    service = _authorization()
    return {
        "policy_version": service.policy_version,
        "fails_closed": True,
        "approvals_wired": not type(service._approvals).__name__ == "NoApprovals",  # noqa: SLF001
        "note": (
            "A policy engine that is unavailable, raises, or returns anything "
            "malformed produces DENY. There is no permissive fallback."
        ),
    }


@router.get("/operations", summary="The operations that can be authorized")
async def operations_route():
    return {
        "operations": [
            {
                "operation": op.value,
                "required_grant": op.required_grant,
                "is_lifecycle": op.is_lifecycle,
                "grants_availability": op.grants_availability,
                "reduces_exposure": op.reduces_exposure,
            }
            for op in CapabilityOperation
        ],
        "note": (
            "Each operation is authorized as itself. A principal permitted to "
            "register is not thereby permitted to enable or to trust."
        ),
    }
