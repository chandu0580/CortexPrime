"""Capability Registry REST API (BC-8 Connectivity).

Translation only. Every rule lives in the Connectivity context.

Mounted at ``/api/v1/capabilities``.

**There is deliberately no ``PATCH``.** A generic field-mutation endpoint would
be a way to change what a capability *is* — its effect class, its isolation tier,
its owner — without going through the lifecycle that makes those changes
reviewable. Every route here maps to one named domain operation, and the ones
that change availability or trust require a reason.

Registration is a privileged operation and this API does not yet enforce that:
``RegistrationGuard`` is the seam and its current implementation refuses nothing
(Phase 3.2.3). Stated here rather than left to be discovered.

Status codes:

``409`` — the same version was offered with a different contract, or the move is
illegal for the state the capability is in. Both are conflicts about what the
capability already is.

``404`` — no such capability, no such version, or it is not visible to this
tenant. Invisible and absent are deliberately indistinguishable.

``422`` — registered, but not something that may run (status or trust withholds it).

``400`` — a value the registry refuses on principle.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Path, Query, status
from pydantic import BaseModel, Field

from backend.contracts.errors import ContractViolation
from backend.contexts.connectivity import (
    CapabilityNotExecutable,
    CapabilityNotFound,
    CapabilityRevokedError,
    CapabilityService,
    CapabilityVersionNotFound,
    ConflictingRegistration,
    DeprecateCapability,
    DisableCapability,
    EnableCapability,
    GetCapability,
    IllegalCapabilityTransition,
    IllegalTrustTransition,
    InMemoryCapabilityRepository,
    InspectContract,
    ListCapabilities,
    ListVersions,
    OwnerRequired,
    RegisterCapability,
    RevokeCapability,
    SetCapabilityTrust,
    TenancyViolation,
    ValidateCapability,
)
from backend.platform.context import ExecutionContext

router = APIRouter(prefix="/api/v1/capabilities", tags=["Capability Registry"])

_service = CapabilityService(repository=InMemoryCapabilityRepository())


def _context() -> ExecutionContext:
    return ExecutionContext.platform_internal(
        reason="capability-registry-api", component="capability-registry", source="http"
    )


# ----------------------------------------------------------------------
# Schemas
# ----------------------------------------------------------------------

_INTERFACE = "^(execution_worker|connector|mcp_tool|agent|skill|service)$"
_SIDE_EFFECT = "^(read|reversible_write|irreversible_write|destructive)$"
_EFFECT = "^(read_only|idempotent_write|non_idempotent_write|unknown)$"
_ISOLATION = "^(ambient|contained|sealed)$"
_MODE = "^(synchronous|asynchronous|streaming)$"
_TENANCY = "^(platform|tenant|shared)$"
_SOURCE = "^(internal|manual|connector_package|mcp|agent|discovery|import)$"
_OWNER_KIND = "^(human|platform|external_system)$"
_ENVIRONMENT = "^(development|staging|production)$"
_STATUS = "^(draft|registered|validated|enabled|disabled|deprecated|revoked)$"
_TRUST = "^(unverified|verified|trusted|quarantined|untrusted)$"


class SchemaRefIn(BaseModel):
    name: str
    digest: str
    media_type: str = "application/schema+json"


class RegisterIn(BaseModel):
    capability_id: str = Field(
        ..., description="namespace.provider.capability[.operation]"
    )
    version: int = Field(
        ...,
        ge=1,
        description="An exact version. 'latest' is not accepted: a run bound to a "
        "moving target can have the capability change after approval.",
    )
    name: str
    description: str
    provider: str

    interface: str = Field(..., pattern=_INTERFACE)
    side_effect_class: str = Field(..., pattern=_SIDE_EFFECT)
    effect_semantics: str = Field(
        ...,
        pattern=_EFFECT,
        description="Whether repeating this is safe. 'unknown' is never treated as safe.",
    )
    isolation_tier: str = Field(..., pattern=_ISOLATION)
    execution_mode: str = Field("synchronous", pattern=_MODE)

    owner_id: str = Field(..., description="Never 'system'; every capability is owned")
    owner_kind: str = Field(..., pattern=_OWNER_KIND)
    owner_display_name: Optional[str] = None

    tenancy: str = Field(..., pattern=_TENANCY)
    source: str = Field(..., pattern=_SOURCE)
    tenant_id: Optional[str] = None
    shared_with: List[str] = Field(default_factory=list)

    supported_environments: List[str] = Field(..., min_length=1)
    category: Optional[str] = None
    input_schema: Optional[SchemaRefIn] = None
    output_schema: Optional[SchemaRefIn] = None
    required_permissions: List[str] = Field(default_factory=list)

    idempotency_supported: bool = False
    retryable: bool = False
    cancellable: bool = False
    compensation_capability: Optional[str] = None
    timeout_seconds: Optional[int] = Field(None, ge=1)
    supersedes: Optional[int] = Field(None, ge=1)
    metadata: Optional[Dict[str, Any]] = None


class NoteIn(BaseModel):
    note: str = "contract checked"


class ReasonIn(BaseModel):
    reason: str = Field(..., min_length=1)


class DeprecateIn(BaseModel):
    reason: str = Field(..., min_length=1)
    successor_version: Optional[int] = Field(None, ge=1)


class TrustIn(BaseModel):
    trust: str = Field(..., pattern=_TRUST)
    reason: str = Field(
        ...,
        min_length=1,
        description="Trust is what lets a capability near production; an "
        "unexplained change cannot be reviewed.",
    )


# ----------------------------------------------------------------------
# Rendering
# ----------------------------------------------------------------------


def _render(definition) -> dict:
    return {
        "reference": definition.reference.value,
        "capability_id": definition.capability_id.value,
        "version": definition.version.number,
        "namespace": definition.capability_id.namespace.value,
        "name": definition.name,
        "description": definition.description,
        "provider": definition.provider,
        "category": definition.category,
        "status": definition.status.value,
        "trust": definition.trust.value,
        "is_executable": definition.is_executable,
        "is_discoverable": definition.is_discoverable,
        "permitted_transitions": list(definition.permitted_transitions()),
        "permitted_trust_transitions": list(definition.permitted_trust_transitions()),
        "owner": {
            "principal_id": definition.owner.principal_id,
            "kind": definition.owner.kind.value,
            "display_name": definition.owner.display_name,
        },
        "tenancy": definition.tenancy.value,
        "tenant_id": definition.tenant_id,
        "shared_with": sorted(definition.shared_with),
        "source": definition.source.value,
        "contract": definition.contract.to_dict(),
        "effect_declared": definition.effect_is_declared,
        "digest": definition.digest,
        "registered_at": definition.registered_at.isoformat(),
        "updated_at": (
            definition.updated_at.isoformat() if definition.updated_at else None
        ),
        "status_note": definition.status_note,
        "supersedes": definition.supersedes,
    }


def _handle(operation):
    try:
        return operation()
    except (CapabilityNotFound, CapabilityVersionNotFound) as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except ConflictingRegistration as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            {
                "error": "conflicting_registration",
                "message": str(exc),
                "capability_ref": exc.capability_ref,
                "registered_digest": exc.registered_digest,
                "offered_digest": exc.offered_digest,
            },
        ) from exc
    except CapabilityRevokedError as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            {"error": "capability_revoked", "message": str(exc)},
        ) from exc
    except IllegalCapabilityTransition as exc:
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
    except IllegalTrustTransition as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            {
                "error": "illegal_trust_transition",
                "message": str(exc),
                "source": exc.source,
                "target": exc.target,
                "permitted": list(exc.permitted),
            },
        ) from exc
    except CapabilityNotExecutable as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            {
                "error": "capability_not_executable",
                "message": str(exc),
                "status": exc.status,
                "trust": exc.trust,
            },
        ) from exc
    except (OwnerRequired, TenancyViolation) as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            {"error": "invalid_capability", "message": str(exc)},
        ) from exc
    except ContractViolation as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc


# ----------------------------------------------------------------------
# Registration and queries
# ----------------------------------------------------------------------


@router.post("", status_code=status.HTTP_201_CREATED, summary="Register a capability version")
async def register_route(payload: RegisterIn):
    def run():
        result = _service.register(
            _context(),
            RegisterCapability(
                capability_id=payload.capability_id,
                version=payload.version,
                name=payload.name,
                description=payload.description,
                provider=payload.provider,
                interface=payload.interface,
                side_effect_class=payload.side_effect_class,
                effect_semantics=payload.effect_semantics,
                isolation_tier=payload.isolation_tier,
                execution_mode=payload.execution_mode,
                owner_id=payload.owner_id,
                owner_kind=payload.owner_kind,
                owner_display_name=payload.owner_display_name,
                tenancy=payload.tenancy,
                source=payload.source,
                tenant_id=payload.tenant_id,
                shared_with=tuple(payload.shared_with),
                supported_environments=tuple(payload.supported_environments),
                category=payload.category,
                input_schema=(
                    payload.input_schema.model_dump() if payload.input_schema else None
                ),
                output_schema=(
                    payload.output_schema.model_dump() if payload.output_schema else None
                ),
                required_permissions=tuple(payload.required_permissions),
                idempotency_supported=payload.idempotency_supported,
                retryable=payload.retryable,
                cancellable=payload.cancellable,
                compensation_capability=payload.compensation_capability,
                timeout_seconds=payload.timeout_seconds,
                supersedes=payload.supersedes,
                metadata=payload.metadata,
            ),
        )
        return {
            "capability": _render(result.capability),
            "events": list(result.event_types),
            "idempotent": result.events[0].idempotent_registration,
        }

    return _handle(run)


@router.get("", summary="List capabilities visible to this caller")
async def list_route(
    provider: Optional[str] = Query(None),
    interface: Optional[str] = Query(None, pattern=_INTERFACE),
    capability_status: Optional[str] = Query(None, alias="status", pattern=_STATUS),
    trust: Optional[str] = Query(None, pattern=_TRUST),
    environment: Optional[str] = Query(None, pattern=_ENVIRONMENT),
    executable_only: bool = Query(False),
    include_undiscoverable: bool = Query(False),
):
    def run():
        found = _service.list(
            _context(),
            ListCapabilities(
                provider=provider,
                interface=interface,
                status=capability_status,
                trust=trust,
                environment=environment,
                executable_only=executable_only,
                include_undiscoverable=include_undiscoverable,
            ),
        )
        return {"count": len(found), "capabilities": [_render(d) for d in found]}

    return _handle(run)


@router.get("/{capability_id}/versions", summary="Every registered version")
async def versions_route(capability_id: str = Path(...)):
    def run():
        found = _service.versions(_context(), ListVersions(capability_id=capability_id))
        return {
            "capability_id": capability_id,
            "count": len(found),
            "versions": [_render(d) for d in found],
        }

    return _handle(run)


@router.get("/{capability_id}/versions/{version}", summary="One capability version")
async def get_route(capability_id: str = Path(...), version: int = Path(..., ge=1)):
    return _handle(
        lambda: _render(
            _service.get(
                _context(), GetCapability(capability_id=capability_id, version=version)
            )
        )
    )


@router.get(
    "/{capability_id}/versions/{version}/contract",
    summary="The digest-bound contract this version promises",
)
async def contract_route(capability_id: str = Path(...), version: int = Path(..., ge=1)):
    return _handle(
        lambda: _service.inspect_contract(
            _context(), InspectContract(capability_id=capability_id, version=version)
        )
    )


@router.get(
    "/{capability_id}/versions/{version}/executable",
    summary="Whether this may actually run; 422 with the reason if not",
)
async def executable_route(capability_id: str = Path(...), version: int = Path(..., ge=1)):
    def run():
        definition = _service.executable(_context(), f"{capability_id}@{version}")
        return {"reference": definition.reference.value, "executable": True}

    return _handle(run)


# ----------------------------------------------------------------------
# Lifecycle — one named operation each, never a generic field write
# ----------------------------------------------------------------------


@router.post("/{capability_id}/versions/{version}/validate", summary="Record that the contract was checked")
async def validate_route(
    payload: NoteIn, capability_id: str = Path(...), version: int = Path(..., ge=1)
):
    def run():
        result = _service.validate(
            _context(),
            ValidateCapability(
                capability_id=capability_id, version=version, note=payload.note
            ),
        )
        return {"capability": _render(result.capability), "events": list(result.event_types)}

    return _handle(run)


@router.post("/{capability_id}/versions/{version}/enable", summary="Make available, subject to trust")
async def enable_route(
    payload: NoteIn, capability_id: str = Path(...), version: int = Path(..., ge=1)
):
    def run():
        result = _service.enable(
            _context(),
            EnableCapability(
                capability_id=capability_id, version=version, note=payload.note
            ),
        )
        return {"capability": _render(result.capability), "events": list(result.event_types)}

    return _handle(run)


@router.post("/{capability_id}/versions/{version}/disable", summary="Switch off, reversibly")
async def disable_route(
    payload: ReasonIn, capability_id: str = Path(...), version: int = Path(..., ge=1)
):
    def run():
        result = _service.disable(
            _context(),
            DisableCapability(
                capability_id=capability_id, version=version, reason=payload.reason
            ),
        )
        return {"capability": _render(result.capability), "events": list(result.event_types)}

    return _handle(run)


@router.post("/{capability_id}/versions/{version}/deprecate", summary="Discourage new adoption")
async def deprecate_route(
    payload: DeprecateIn, capability_id: str = Path(...), version: int = Path(..., ge=1)
):
    def run():
        result = _service.deprecate(
            _context(),
            DeprecateCapability(
                capability_id=capability_id,
                version=version,
                reason=payload.reason,
                successor_version=payload.successor_version,
            ),
        )
        return {"capability": _render(result.capability), "events": list(result.event_types)}

    return _handle(run)


@router.post(
    "/{capability_id}/versions/{version}/revoke",
    summary="Withdraw permanently. Terminal — there is no un-revoke",
)
async def revoke_route(
    payload: ReasonIn, capability_id: str = Path(...), version: int = Path(..., ge=1)
):
    def run():
        result = _service.revoke(
            _context(),
            RevokeCapability(
                capability_id=capability_id, version=version, reason=payload.reason
            ),
        )
        return {"capability": _render(result.capability), "events": list(result.event_types)}

    return _handle(run)


@router.post(
    "/{capability_id}/versions/{version}/trust",
    summary="Move how much the platform vouches for this capability",
)
async def trust_route(
    payload: TrustIn, capability_id: str = Path(...), version: int = Path(..., ge=1)
):
    def run():
        result = _service.set_trust(
            _context(),
            SetCapabilityTrust(
                capability_id=capability_id,
                version=version,
                trust=payload.trust,
                reason=payload.reason,
            ),
        )
        return {"capability": _render(result.capability), "events": list(result.event_types)}

    return _handle(run)
