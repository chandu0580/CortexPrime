"""ContextBundle REST API.

Translation only. Every rule lives in the ContextBundle context.

Mounted at ``/api/v1/engineering/context``. Expansion is three endpoints rather
than one — request, decide, apply — mirroring the three domain steps. A single
"expand" endpoint would make a grant whose assembly then failed
indistinguishable from a denial.

Status codes:

``409`` — the bundle is superseded or invalidated, the request is already
decided, or the expansion was denied. All mean the request was well-formed and
conflicts with what is recorded.

``410`` — the bundle is stale: the tree moved under it. Gone, in the sense that
matters — the thing it described no longer exists.

``400`` — a malformed value, including an attempt at implicit expansion.
"""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, HTTPException, Path, Query, status
from pydantic import BaseModel, Field

from backend.contracts.errors import ContractViolation
from backend.contexts.context_bundle import (
    ApplyExpansion,
    AssembleBundle,
    BundleInvalidated,
    BundleNotFound,
    BundleSuperseded,
    ContextBundleService,
    DecideExpansion,
    ExpansionAlreadyDecided,
    ExpansionDenied,
    GetBoundarySignals,
    GetBundle,
    ImplicitExpansion,
    InMemoryContextRepository,
    InvalidateBundle,
    LayerViolation,
    ListBundles,
    ManifestMismatch,
    RequestExpansion,
    ResolveBundle,
    StaleBaseCommit,
    UnknownExpansion,
)
from backend.platform.context import ExecutionContext

router = APIRouter(prefix="/api/v1/engineering/context", tags=["Engineering — ContextBundle"])

_service = ContextBundleService(repository=InMemoryContextRepository())


def _context() -> ExecutionContext:
    return ExecutionContext.platform_internal(
        reason="engineering-context-api", component="context-bundle-api", source="http"
    )


# ----------------------------------------------------------------------
# Schemas
# ----------------------------------------------------------------------


class DependencyIn(BaseModel):
    name: str
    interface_paths: List[str] = Field(..., min_length=1)
    implementation_paths: List[str] = Field(
        default_factory=list,
        description="Recorded but never included; naming them makes the omission visible",
    )


class ReferenceIn(BaseModel):
    path: str
    layer: str = Field(
        ..., pattern="^(minimal|owned|dependencies|adr_bundle|search)$"
    )
    content_digest: Optional[str] = None


class AssembleIn(BaseModel):
    work_id: str
    work_order_version: int = Field(1, ge=1)
    base_commit: str = Field(..., description="A bundle describes a particular tree")
    blast_radius_allowed: List[str] = Field(..., min_length=1)
    searchable: List[str] = Field(..., min_length=1)
    blast_radius_forbidden: List[str] = Field(default_factory=list)
    blast_radius_read_only: List[str] = Field(default_factory=list)
    excluded_from_search: List[str] = Field(default_factory=list)
    adr_references: List[str] = Field(default_factory=list)
    superseded_adrs: List[str] = Field(default_factory=list)
    dependencies: List[DependencyIn] = Field(default_factory=list)
    references: List[ReferenceIn] = Field(default_factory=list)
    assembled_by: str = "orchestrator"


class RequestExpansionIn(BaseModel):
    requested_path: str
    question: str = Field(..., description="What this answers. A request without one is browsing.")
    requested_by: str
    target_layer: str = Field(
        "dependencies", pattern="^(minimal|dependencies|adr_bundle|search)$"
    )


class DecideIn(BaseModel):
    grant: bool
    decided_by: str
    reason: Optional[str] = None


class ApplyIn(BaseModel):
    references: List[ReferenceIn] = Field(default_factory=list)


class ResolveIn(BaseModel):
    resolved_for: str = Field(..., description="Who is receiving the context")
    current_commit: Optional[str] = None


class InvalidateIn(BaseModel):
    reason: str
    current_commit: Optional[str] = None


# ----------------------------------------------------------------------
# Rendering
# ----------------------------------------------------------------------


def _render(bundle) -> dict:
    return {
        "bundle_id": str(bundle.bundle_id),
        "work_id": bundle.work_id,
        "work_order_version": bundle.work_order_version,
        "version": bundle.version,
        "base_commit": bundle.base_commit,
        "status": bundle.status.value,
        "manifest_digest": bundle.manifest_digest,
        "repository_scope": {
            "searchable": list(bundle.repository_scope.searchable),
            "excluded": list(bundle.repository_scope.excluded),
        },
        "adr_bundle": {
            "references": list(bundle.adr_bundle.references),
            "superseded": list(bundle.adr_bundle.superseded),
        },
        "blast_radius": {
            "allowed": list(bundle.blast_radius.allowed),
            "forbidden": list(bundle.blast_radius.forbidden),
            "read_only": list(bundle.blast_radius.read_only),
        },
        "dependencies": [
            {"name": d.name, "interface_paths": list(d.interface_paths)}
            for d in bundle.dependencies
        ],
        "references": [
            {"path": r.path, "layer": r.layer.value, "access": r.access.value}
            for r in bundle.references
        ],
        "expansions": [
            {
                "request_id": str(e.request_id),
                "requested_path": e.requested_path,
                "question": e.question,
                "disposition": e.disposition.value,
                "decided_by": e.decided_by,
                "reason": e.decision_reason,
            }
            for e in bundle.expansions
        ],
        "supersedes": str(bundle.supersedes) if bundle.supersedes else None,
        "superseded_by": str(bundle.superseded_by) if bundle.superseded_by else None,
        "invalidation_reason": bundle.invalidation_reason,
    }


def _handle(operation):
    try:
        return operation()
    except BundleNotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except UnknownExpansion as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except StaleBaseCommit as exc:
        raise HTTPException(
            status.HTTP_410_GONE,
            {
                "error": "stale_base_commit",
                "message": str(exc),
                "assembled_at": exc.assembled_at,
                "current": exc.current,
            },
        ) from exc
    except (BundleSuperseded, BundleInvalidated, ExpansionAlreadyDecided) as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    except ExpansionDenied as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            {
                "error": "expansion_denied",
                "message": str(exc),
                "path": exc.path,
                "reason": exc.reason,
            },
        ) from exc
    except ImplicitExpansion as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            {"error": "implicit_expansion", "message": str(exc), "path": exc.path},
        ) from exc
    except (ManifestMismatch, LayerViolation) as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    except ContractViolation as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc


# ----------------------------------------------------------------------
# Routes
# ----------------------------------------------------------------------


@router.post("", status_code=status.HTTP_201_CREATED, summary="Assemble a context bundle")
async def assemble_route(payload: AssembleIn):
    def run():
        result = _service.assemble(
            _context(),
            AssembleBundle(
                work_id=payload.work_id,
                work_order_version=payload.work_order_version,
                base_commit=payload.base_commit,
                blast_radius_allowed=tuple(payload.blast_radius_allowed),
                blast_radius_forbidden=tuple(payload.blast_radius_forbidden),
                blast_radius_read_only=tuple(payload.blast_radius_read_only),
                searchable=tuple(payload.searchable),
                excluded_from_search=tuple(payload.excluded_from_search),
                adr_references=tuple(payload.adr_references),
                superseded_adrs=tuple(payload.superseded_adrs),
                dependencies=tuple(
                    (d.name, tuple(d.interface_paths), tuple(d.implementation_paths))
                    for d in payload.dependencies
                ),
                references=tuple(
                    (r.path, r.layer, r.content_digest) for r in payload.references
                ),
                assembled_by=payload.assembled_by,
            ),
        )
        return {"bundle": _render(result.bundle), "events": list(result.event_types)}

    return _handle(run)


@router.get("", summary="List bundles")
async def list_route(
    work_id: Optional[str] = Query(None), active_only: bool = Query(False)
):
    def run():
        found = _service.list(
            _context(), ListBundles(work_id=work_id, active_only=active_only)
        )
        return {"count": len(found), "bundles": [_render(b) for b in found]}

    return _handle(run)


@router.get("/signals", summary="Paths requested often enough to suggest a wrong boundary")
async def signals_route(minimum_requests: int = Query(2, ge=1)):
    def run():
        signals = _service.boundary_signals(_context(), minimum_requests=minimum_requests)
        return {
            "count": len(signals),
            "signals": [
                {
                    "path": s.path,
                    "request_count": s.request_count,
                    "work_orders": list(s.work_orders),
                    "questions": list(s.questions),
                    "denied_count": s.denied_count,
                    "crosses_work_orders": s.crosses_work_orders,
                }
                for s in signals
            ],
        }

    return _handle(run)


@router.get("/{bundle_id}", summary="Fetch a bundle")
async def get_route(bundle_id: str = Path(...)):
    return _handle(lambda: _render(_service.get(_context(), GetBundle(bundle_id=bundle_id))))


@router.post("/{bundle_id}/resolve", summary="Hand the bundle to an agent")
async def resolve_route(payload: ResolveIn, bundle_id: str = Path(...)):
    def run():
        resolved, events = _service.resolve(
            _context(),
            ResolveBundle(
                bundle_id=bundle_id,
                resolved_for=payload.resolved_for,
                current_commit=payload.current_commit,
            ),
        )
        return {
            "resolved": {
                "bundle_id": resolved.bundle_id,
                "work_id": resolved.work_id,
                "version": resolved.version,
                "base_commit": resolved.base_commit,
                "writable": list(resolved.writable),
                "readable": list(resolved.readable),
                "searchable": list(resolved.searchable),
                "adr_references": list(resolved.adr_references),
                "dependencies": list(resolved.dependencies),
                "manifest_digest": resolved.manifest_digest,
            },
            "events": [e.EVENT_TYPE for e in events],
        }

    return _handle(run)


@router.post("/{bundle_id}/expansions", summary="Request an expansion")
async def request_expansion_route(payload: RequestExpansionIn, bundle_id: str = Path(...)):
    def run():
        result = _service.request_expansion(
            _context(),
            RequestExpansion(
                bundle_id=bundle_id,
                requested_path=payload.requested_path,
                question=payload.question,
                requested_by=payload.requested_by,
                target_layer=payload.target_layer,
            ),
        )
        return {"bundle": _render(result.bundle)}

    return _handle(run)


@router.post("/{bundle_id}/expansions/{request_id}/decide", summary="Grant or deny a request")
async def decide_route(payload: DecideIn, bundle_id: str = Path(...), request_id: str = Path(...)):
    def run():
        result = _service.decide_expansion(
            _context(),
            DecideExpansion(
                bundle_id=bundle_id,
                request_id=request_id,
                grant=payload.grant,
                decided_by=payload.decided_by,
                reason=payload.reason,
            ),
        )
        return {"bundle": _render(result.bundle)}

    return _handle(run)


@router.post("/{bundle_id}/expansions/{request_id}/apply", summary="Widen and version")
async def apply_route(payload: ApplyIn, bundle_id: str = Path(...), request_id: str = Path(...)):
    def run():
        result = _service.apply_expansion(
            _context(),
            bundle_id,
            request_id,
            tuple((r.path, r.layer, r.content_digest) for r in payload.references),
        )
        return {"bundle": _render(result.bundle), "events": list(result.event_types)}

    return _handle(run)


@router.post("/{bundle_id}/invalidate", summary="Mark the bundle no longer usable")
async def invalidate_route(payload: InvalidateIn, bundle_id: str = Path(...)):
    def run():
        result = _service.invalidate(
            _context(),
            InvalidateBundle(
                bundle_id=bundle_id,
                reason=payload.reason,
                current_commit=payload.current_commit,
            ),
        )
        return {"bundle": _render(result.bundle), "events": list(result.event_types)}

    return _handle(run)
