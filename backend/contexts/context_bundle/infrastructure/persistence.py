"""Mapping between the ContextBundle aggregate and a storable record.

Storage-agnostic: a plain mapping of primitives, carrying no SQL and no
document-store idiom.

Every invariant is re-checked on the way in, and the manifest digest is **not**
recomputed -- it is restored as recorded. That distinction matters: recomputing
would make the digest always match, which is a check that cannot fail. Restoring
it means a tampered record fails ``verify_manifest`` exactly as it should.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping

from backend.contracts.errors import ContractViolation
from backend.contexts.context_bundle.domain.bundle import BundleStatus, ContextBundle
from backend.contexts.context_bundle.domain.expansion import Disposition, ExpansionRequest
from backend.contexts.context_bundle.domain.identifiers import BundleId, ExpansionRequestId
from backend.contexts.context_bundle.domain.layers import ContextLayer, ContextReference
from backend.contexts.context_bundle.domain.scope import (
    AdrBundle,
    BlastRadiusSpec,
    DependencyContract,
    RepositoryScope,
)

__all__ = ["RECORD_SCHEMA_VERSION", "to_record", "from_record"]

RECORD_SCHEMA_VERSION = 1


def _expansion_record(request: ExpansionRequest) -> dict:
    return {
        "request_id": str(request.request_id),
        "requested_path": request.requested_path,
        "question": request.question,
        "requested_by": request.requested_by,
        "target_layer": request.target_layer.value,
        "disposition": request.disposition.value,
        "decided_by": request.decided_by,
        "decision_reason": request.decision_reason,
        "requested_at": request.requested_at.isoformat(),
        "decided_at": request.decided_at.isoformat() if request.decided_at else None,
    }


def _expansion_from(data: Mapping[str, Any]) -> ExpansionRequest:
    return ExpansionRequest(
        request_id=ExpansionRequestId(data["request_id"]),
        requested_path=data["requested_path"],
        question=data["question"],
        requested_by=data["requested_by"],
        target_layer=ContextLayer(data["target_layer"]),
        disposition=Disposition(data["disposition"]),
        decided_by=data.get("decided_by"),
        decision_reason=data.get("decision_reason"),
        requested_at=datetime.fromisoformat(data["requested_at"]),
        decided_at=(
            datetime.fromisoformat(data["decided_at"]) if data.get("decided_at") else None
        ),
    )


def to_record(bundle: ContextBundle, *, tenant_id: str) -> dict[str, Any]:
    if not isinstance(tenant_id, str) or not tenant_id.strip():
        raise ContractViolation("tenant_id must be non-blank; it is derived from the context")

    return {
        "schema_version": RECORD_SCHEMA_VERSION,
        "tenant_id": tenant_id,
        "bundle_id": str(bundle.bundle_id),
        "work_id": bundle.work_id,
        "work_order_version": bundle.work_order_version,
        "base_commit": bundle.base_commit,
        "version": bundle.version,
        "repository_scope": {
            "searchable": list(bundle.repository_scope.searchable),
            "excluded": list(bundle.repository_scope.excluded),
            "rationale": bundle.repository_scope.rationale,
        },
        "adr_bundle": {
            "references": list(bundle.adr_bundle.references),
            "superseded": list(bundle.adr_bundle.superseded),
            "index_digest": bundle.adr_bundle.index_digest,
        },
        "dependencies": [
            {
                "name": d.name,
                "interface_paths": list(d.interface_paths),
                "implementation_paths": list(d.implementation_paths),
                "reason": d.reason,
            }
            for d in bundle.dependencies
        ],
        "blast_radius": {
            "allowed": list(bundle.blast_radius.allowed),
            "forbidden": list(bundle.blast_radius.forbidden),
            "read_only": list(bundle.blast_radius.read_only),
        },
        "references": [
            {
                "path": r.path,
                "layer": r.layer.value,
                "content_digest": r.content_digest,
                "note": r.note,
            }
            for r in bundle.references
        ],
        "expansions": [_expansion_record(e) for e in bundle.expansions],
        "status": bundle.status.value,
        "manifest_digest": bundle.manifest_digest,
        "assembled_by": bundle.assembled_by,
        "assembled_at": bundle.assembled_at.isoformat(),
        "supersedes": str(bundle.supersedes) if bundle.supersedes else None,
        "superseded_by": str(bundle.superseded_by) if bundle.superseded_by else None,
        "invalidation_reason": bundle.invalidation_reason,
    }


def from_record(data: Mapping[str, Any]) -> ContextBundle:
    schema = data.get("schema_version")
    if schema != RECORD_SCHEMA_VERSION:
        raise ContractViolation(
            f"record schema version {schema!r} is not {RECORD_SCHEMA_VERSION}; refusing "
            "to guess at a shape this build does not know"
        )

    scope = data["repository_scope"]
    adrs = data["adr_bundle"]
    radius = data["blast_radius"]

    return ContextBundle(
        bundle_id=BundleId(data["bundle_id"]),
        work_id=data["work_id"],
        work_order_version=data["work_order_version"],
        base_commit=data["base_commit"],
        version=data["version"],
        repository_scope=RepositoryScope(
            searchable=tuple(scope["searchable"]),
            excluded=tuple(scope["excluded"]),
            rationale=scope.get("rationale"),
        ),
        adr_bundle=AdrBundle(
            references=tuple(adrs["references"]),
            superseded=tuple(adrs["superseded"]),
            index_digest=adrs.get("index_digest"),
        ),
        dependencies=tuple(
            DependencyContract(
                name=d["name"],
                interface_paths=tuple(d["interface_paths"]),
                implementation_paths=tuple(d["implementation_paths"]),
                reason=d.get("reason"),
            )
            for d in data["dependencies"]
        ),
        blast_radius=BlastRadiusSpec(
            allowed=tuple(radius["allowed"]),
            forbidden=tuple(radius["forbidden"]),
            read_only=tuple(radius["read_only"]),
        ),
        references=tuple(
            ContextReference(
                path=r["path"],
                layer=ContextLayer(r["layer"]),
                content_digest=r.get("content_digest"),
                note=r.get("note"),
            )
            for r in data["references"]
        ),
        expansions=tuple(_expansion_from(e) for e in data["expansions"]),
        status=BundleStatus(data["status"]),
        manifest_digest=data.get("manifest_digest"),
        assembled_by=data["assembled_by"],
        assembled_at=datetime.fromisoformat(data["assembled_at"]),
        supersedes=BundleId(data["supersedes"]) if data.get("supersedes") else None,
        superseded_by=BundleId(data["superseded_by"]) if data.get("superseded_by") else None,
        invalidation_reason=data.get("invalidation_reason"),
    )
