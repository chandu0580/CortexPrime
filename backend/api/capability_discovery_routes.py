"""Capability Discovery API (BC-8 Connectivity, Phase 3.2.2).

Mounted at ``/api/v1/capability-discovery``.

**The architectural gap is visible in the routes themselves.** There is no
endpoint that discovers and enables, no endpoint that discovers and trusts, and
no parameter anywhere that would make one. The furthest any request here can
move a capability is REGISTERED/UNVERIFIED — which is not executable.

Making something usable takes three further deliberate calls against a different
API (`validate`, `enable`, `trust` on ``/api/v1/capabilities``), and those are
where Phase 3.2.3's authorization will sit.

``ingest`` defaults to **false**: looking at what a source offers and recording
it are separate decisions.

Status codes:

``200`` — the run completed. Note that a run over an unreachable source is still
a successful run: it reports ``health: unavailable``, which is the useful answer.
A ``5xx`` here would say the *platform* failed, which is a different fact.

``409`` — a candidate offered a different contract for a registered version.

``400`` — an endpoint or submission this context refuses to record.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Path, Query, status
from pydantic import BaseModel, Field

from backend.api.capability_discovery_composition import (
    agent_source,
    connector_source,
    manual_source,
    mcp_source,
)
from backend.contracts.errors import ContractViolation
from backend.contexts.connectivity import (
    CapabilityDiscoveryService,
    CapabilitySource,
    DiscoveryBudget,
    DiscoveryEndpoint,
    RawObservation,
    UnsafeEndpoint,
    normalize,
)
from backend.platform.context import ExecutionContext

router = APIRouter(
    prefix="/api/v1/capability-discovery", tags=["Capability Discovery"]
)

_SOURCES = {"mcp": mcp_source, "connector": connector_source, "agent": agent_source}


def _service() -> CapabilityDiscoveryService:
    # Shares the process-wide registry the capability API serves, so a candidate
    # ingested here is the same record that API then validates and enables.
    from backend.api import capability_routes

    return CapabilityDiscoveryService(registry=capability_routes._service)


def _context() -> ExecutionContext:
    return ExecutionContext.platform_internal(
        reason="capability-discovery-api",
        component="capability-discovery",
        source="http",
    )


# ----------------------------------------------------------------------
# Schemas
# ----------------------------------------------------------------------

_SIDE_EFFECT = "^(read|reversible_write|irreversible_write|destructive)$"
_EFFECT = "^(read_only|idempotent_write|non_idempotent_write|unknown)$"
_ISOLATION = "^(ambient|contained|sealed)$"
_INTERFACE = "^(execution_worker|connector|mcp_tool|agent|skill|service)$"


class DiscoverIn(BaseModel):
    sources: List[str] = Field(
        default_factory=lambda: ["mcp", "connector", "agent"],
        description="Which local adapters to ask. None of them makes a network call.",
    )
    ingest: bool = Field(
        False,
        description=(
            "Record usable candidates in the registry as REGISTERED/UNVERIFIED. "
            "Never enables and never trusts anything."
        ),
    )
    max_capabilities_per_source: Optional[int] = Field(None, ge=1, le=5000)


class SubmitIn(BaseModel):
    """A manually submitted candidate. Takes the identical validation path."""

    name: str
    description: str = ""
    provider: str
    capability: Optional[str] = None
    operation: Optional[str] = None
    namespace: str = Field("platform", pattern="^(platform|tenant)$")
    version: int = Field(1, ge=1)
    interface: str = Field("service", pattern=_INTERFACE)
    endpoint: Optional[str] = None
    server_name: Optional[str] = None

    side_effect_class: Optional[str] = Field(None, pattern=_SIDE_EFFECT)
    effect_semantics: Optional[str] = Field(None, pattern=_EFFECT)
    isolation_tier: Optional[str] = Field(None, pattern=_ISOLATION)
    supported_environments: List[str] = Field(default_factory=list)
    idempotency_supported: bool = False
    retryable: bool = False
    cancellable: bool = False
    timeout_seconds: Optional[int] = Field(None, ge=1)
    input_schema: Optional[Dict[str, Any]] = None
    output_schema: Optional[Dict[str, Any]] = None

    ingest: bool = Field(
        False, description="Register it if complete. Still lands UNVERIFIED."
    )


def _raw_from(payload: SubmitIn) -> RawObservation:
    endpoint = None
    if payload.endpoint:
        endpoint = DiscoveryEndpoint.parse(payload.endpoint)
    return RawObservation(
        source_id="manual",
        source_type=CapabilitySource.MANUAL,
        name=payload.name,
        description=payload.description,
        provider=payload.provider,
        namespace=payload.namespace,
        capability=payload.capability or payload.name,
        operation=payload.operation,
        version=payload.version,
        interface=payload.interface,
        endpoint=endpoint,
        server_name=payload.server_name,
        side_effect_class=payload.side_effect_class,
        effect_semantics=payload.effect_semantics,
        isolation_tier=payload.isolation_tier,
        supported_environments=tuple(payload.supported_environments),
        idempotency_supported=payload.idempotency_supported,
        retryable=payload.retryable,
        cancellable=payload.cancellable,
        timeout_seconds=payload.timeout_seconds,
        input_schema=payload.input_schema,
        output_schema=payload.output_schema,
        raw={"submitted": True},
    )


def _handle(operation):
    try:
        return operation()
    except UnsafeEndpoint as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            {"error": "unsafe_endpoint", "message": str(exc), "reason": exc.reason},
        ) from exc
    except ContractViolation as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc


# ----------------------------------------------------------------------
# Routes
# ----------------------------------------------------------------------


@router.get("/sources", summary="The discovery adapters this deployment can offer")
async def sources_route():
    return {
        "sources": [
            {
                "name": name,
                "source_type": builder().source_type.value,
                "performs_network_calls": False,
                "note": (
                    "Reads locally held metadata. Supplies no side-effect class, "
                    "so candidates are incomplete until a human states one."
                ),
            }
            for name, builder in _SOURCES.items()
        ],
        "budget": DiscoveryBudget().to_dict(),
    }


@router.post("/runs", summary="Ask sources what they offer. Never enables anything")
async def discover_route(payload: DiscoverIn):
    def run():
        unknown = [s for s in payload.sources if s not in _SOURCES]
        if unknown:
            raise ContractViolation(
                f"unknown discovery sources: {', '.join(unknown)}; available: "
                f"{', '.join(sorted(_SOURCES))}"
            )
        budget = DiscoveryBudget()
        if payload.max_capabilities_per_source:
            budget = DiscoveryBudget(
                max_capabilities_per_source=payload.max_capabilities_per_source
            )
        service = CapabilityDiscoveryService(
            registry=_service()._registry, budget=budget
        )
        result = service.discover(
            _context(),
            [_SOURCES[name]() for name in payload.sources],
            ingest=payload.ingest,
        )
        body = result.to_dict()
        body["guarantee"] = (
            "anything registered by this run is REGISTERED/UNVERIFIED and not "
            "executable; enabling and trust are separate deliberate operations"
        )
        return body

    return _handle(run)


@router.post("/candidates", summary="Submit a candidate by hand. Same validation path")
async def submit_route(payload: SubmitIn):
    def run():
        service = _service()
        source = manual_source([_raw_from(payload)])
        result = service.discover(_context(), [source], ingest=payload.ingest)
        return result.to_dict()

    return _handle(run)


@router.post("/candidates/preview", summary="Normalise without recording anything")
async def preview_route(payload: SubmitIn):
    def run():
        candidate = normalize(_raw_from(payload))
        return {
            "candidate": candidate.to_dict(),
            "may_be_ingested": candidate.may_be_ingested,
            "missing": list(candidate.missing),
            "rejections": list(candidate.rejections),
        }

    return _handle(run)


@router.post("/candidates/compare", summary="How a candidate relates to the registry")
async def compare_route(payload: SubmitIn):
    def run():
        service = _service()
        candidate = normalize(_raw_from(payload))
        change = (
            service.classify(_context(), candidate).value
            if candidate.may_be_ingested
            else None
        )
        return {
            "reference": candidate.reference.value,
            "status": candidate.status.value,
            "change": change,
            "observation_digest": candidate.observation_digest,
            "missing": list(candidate.missing),
        }

    return _handle(run)


@router.get("/endpoints/inspect", summary="Whether an endpoint is safe to record")
async def inspect_endpoint_route(value: str = Query(..., min_length=1)):
    return _handle(lambda: DiscoveryEndpoint.parse(value).to_dict())
