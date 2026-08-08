"""Capability Resolution API (BC-8, Phase 3.2.4).

Mounted at ``/api/v1/capability-resolution``.

**Selects. Never runs.** There is no execute route and nothing here calls a
worker, connector, or MCP server. The output is a binding — a frozen, expiring,
digest-bound record of which contract from which provider was chosen — which
Phase 3.3 will later hand to a worker through `WorkerKindResolver`.

Note the absent routes, which are the point: there is no `choose_provider`, no
`force_provider`, no `bind_without_authorization`, no `ignore_trust`, and no
generic PATCH. Provider preference is expressible only as `pinned_provider`,
which *narrows* eligibility and can never widen it — naming a provider cannot
conjure one that trust and tenancy would otherwise exclude.

Every request must carry an authorization decision obtained from
`/api/v1/capability-authorization/decisions`. Resolution re-verifies it rather
than trusting that it was obtained.

Status codes:

``200`` — resolution completed, **including a refusal**. A refusal is a
successful evaluation with a negative answer.

``400`` — the request could not be understood well enough to resolve.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Path, Query, status
from pydantic import BaseModel, Field

from backend.contracts.errors import ContractViolation
from backend.contracts.execution import EffectSemantics
from backend.contracts.identity import PrincipalKind, PrincipalRef
from backend.contracts.policy import PolicyEffect, RiskLevel
from backend.contexts.connectivity import (
    AuthorizationDecision,
    AuthorizationRequest,
    CapabilityEnvironment,
    CapabilityId,
    CapabilityOperation,
    CapabilityRef,
    CapabilityVersion,
    ResolutionRequest,
    VersionSelection,
)
from backend.platform.context import ExecutionContext
from backend.platform.context.identity import IdentityContext

router = APIRouter(
    prefix="/api/v1/capability-resolution", tags=["Capability Resolution"]
)

_OPERATION = "^(invoke|inspect)$"
_ENVIRONMENT = "^(development|staging|production)$"
_EFFECT = "^(read_only|idempotent_write|non_idempotent_write|unknown)$"
_SELECTION = "^(exact|highest_authorized)$"

_SERVICE = None


def _service():
    from backend.api import capability_resolution_composition as composition
    from backend.api import capability_routes

    global _SERVICE
    if _SERVICE is None:
        _SERVICE = composition.build_resolution(capability_routes._service)
    return _SERVICE


class PrincipalIn(BaseModel):
    principal_id: str
    kind: str = Field("human", pattern="^(human|platform|external_system)$")


class AuthorizationIn(BaseModel):
    """The decision obtained from the authorization API, presented back.

    Re-verified here: it must recompute to its own digest and must be about this
    exact request. A decision edited in transit is not a decision.
    """

    capability_ref: str
    operation: str
    capability_digest: str
    policy_version: str
    decided_at: datetime
    expires_at: datetime
    risk: str = Field(..., pattern="^(low|medium|high|critical)$")
    digest: str
    execution_id: Optional[str] = None
    node_id: Optional[str] = None
    workflow_id: Optional[str] = None
    mission_id: Optional[str] = None


class ResolveIn(BaseModel):
    tenant_id: str
    principal: PrincipalIn
    capability_id: str = Field(
        ..., description="Logical identity, e.g. platform.github.create_issue"
    )
    operation: str = Field(..., pattern=_OPERATION)
    authorization: AuthorizationIn
    version: Optional[int] = Field(None, ge=1)
    version_selection: str = Field("exact", pattern=_SELECTION)
    environment: Optional[str] = Field(None, pattern=_ENVIRONMENT)
    max_effect: Optional[str] = Field(
        None,
        pattern=_EFFECT,
        description="The strongest effect the caller will accept.",
    )
    required_input_schema_digest: Optional[str] = None
    required_output_schema_digest: Optional[str] = None
    pinned_provider: Optional[str] = Field(
        None,
        description=(
            "Narrows eligibility only. Naming a provider cannot make an "
            "ineligible one selectable."
        ),
    )
    mission_id: Optional[str] = None
    workflow_id: Optional[str] = None
    execution_id: Optional[str] = None
    node_id: Optional[str] = None
    bind: bool = Field(True, description="Freeze the choice into a binding.")


def _principal(payload: PrincipalIn) -> PrincipalRef:
    return PrincipalRef(
        principal_id=payload.principal_id, kind=PrincipalKind(payload.kind)
    )


def _decision(payload: ResolveIn) -> AuthorizationDecision:
    auth = payload.authorization
    principal = _principal(payload.principal)
    request = AuthorizationRequest(
        tenant_id=payload.tenant_id,
        principal=principal,
        capability_ref=CapabilityRef.parse(auth.capability_ref),
        operation=CapabilityOperation(auth.operation),
        expected_digest=auth.capability_digest,
        mission_id=auth.mission_id,
        workflow_id=auth.workflow_id,
        execution_id=auth.execution_id,
        node_id=auth.node_id,
    )
    return AuthorizationDecision(
        effect=PolicyEffect.ALLOW,
        request=request,
        policy_version=auth.policy_version,
        decided_at=auth.decided_at,
        expires_at=auth.expires_at,
        binding_key=request.binding_key,
        capability_digest=auth.capability_digest,
        risk=RiskLevel(auth.risk),
    ).sealed()


def _context(payload: ResolveIn) -> ExecutionContext:
    return ExecutionContext.for_tenant(
        tenant_id=payload.tenant_id,
        identity=IdentityContext(principal=_principal(payload.principal)),
        source="http",
    )


def _handle(operation):
    try:
        return operation()
    except ContractViolation as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc


@router.post("/resolutions", summary="Select one capability and freeze the choice")
async def resolve_route(payload: ResolveIn):
    def run():
        decision = _decision(payload)
        # If the presented decision does not recompute, the service refuses it
        # with AUTHORIZATION_UNVERIFIED -- checked there, not here, so there is
        # exactly one place that decides what a valid authorization is.
        if decision.digest != payload.authorization.digest:
            return {
                "resolved": False,
                "failure": "authorization_unverified",
                "detail": "the presented authorization does not match its own digest",
            }

        request = ResolutionRequest(
            tenant_id=payload.tenant_id,
            principal=_principal(payload.principal),
            capability_id=CapabilityId.parse(payload.capability_id),
            operation=CapabilityOperation(payload.operation),
            authorization=decision,
            version=CapabilityVersion(payload.version) if payload.version else None,
            version_selection=VersionSelection(payload.version_selection),
            environment=(
                CapabilityEnvironment(payload.environment)
                if payload.environment
                else None
            ),
            max_effect=(
                EffectSemantics(payload.max_effect) if payload.max_effect else None
            ),
            required_input_schema_digest=payload.required_input_schema_digest,
            required_output_schema_digest=payload.required_output_schema_digest,
            pinned_provider=payload.pinned_provider,
            mission_id=payload.mission_id,
            workflow_id=payload.workflow_id,
            execution_id=payload.execution_id,
            node_id=payload.node_id,
        )
        outcome = _service().resolve(_context(payload), request, bind=payload.bind)
        # Redacted: security-relevant rejections are withheld so the resolver
        # never becomes a provider inventory leak.
        return outcome.to_dict(redacted=True)

    return _handle(run)


@router.get("/bindings/{binding_id}", summary="Inspect a binding")
async def get_binding_route(binding_id: str = Path(...), tenant_id: str = Query(...)):
    def run():
        context = ExecutionContext.for_tenant(
            tenant_id=tenant_id,
            identity=IdentityContext(
                principal=PrincipalRef(
                    principal_id="inspector", kind=PrincipalKind.PLATFORM
                )
            ),
            source="http",
        )
        service = _service()
        found = service._bindings.find(context, binding_id)  # noqa: SLF001
        if found is None:
            # Another tenant's binding is absent, not forbidden.
            raise HTTPException(status.HTTP_404_NOT_FOUND, "no such binding")
        return found.to_dict()

    return _handle(run)


@router.get(
    "/bindings/{binding_id}/validity",
    summary="Whether a binding may still be used, re-checked against the registry",
)
async def binding_validity_route(
    binding_id: str = Path(...),
    tenant_id: str = Query(...),
    principal_id: str = Query(...),
    execution_id: Optional[str] = Query(None),
):
    def run():
        context = ExecutionContext.for_tenant(
            tenant_id=tenant_id,
            identity=IdentityContext(
                principal=PrincipalRef(
                    principal_id=principal_id, kind=PrincipalKind.PLATFORM
                )
            ),
            source="http",
        )
        service = _service()
        found = service._bindings.find(context, binding_id)  # noqa: SLF001
        if found is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "no such binding")
        invalidations = service.validate_binding(
            context,
            found,
            tenant_id=tenant_id,
            principal_id=principal_id,
            execution_id=execution_id,
        )
        return {
            "binding_id": binding_id,
            "usable": not invalidations,
            "invalidations": [i.value for i in invalidations],
            "note": (
                "Re-read from the authoritative registry. A binding proves what "
                "was chosen, not that the world has not changed since."
            ),
        }

    return _handle(run)


@router.get("/policy", summary="The resolution policy this deployment runs")
async def policy_route():
    from backend.contexts.connectivity import RESOLUTION_POLICY_VERSION

    return {
        "resolution_policy_version": RESOLUTION_POLICY_VERSION,
        "deterministic": True,
        "ranking_dimensions": [
            "exact_version",
            "trust_rank",
            "tenant_local",
            "effect_declared",
        ],
        "tie_breaker": ["provider", "capability_digest"],
        "notes": [
            "Ineligible candidates are filtered before ranking, so no score can "
            "promote a revoked, untrusted or cross-tenant candidate.",
            "Version number is not a ranking dimension: preferring the higher "
            "version would silently choose between providers.",
            "No LLM, no embeddings, no semantic search participates in selection.",
        ],
    }
