"""Mapping between a CapabilityDefinition and a storable record.

Storage-agnostic: a plain mapping of primitives.

The contract digest is **restored, not recomputed**. Recomputing would make the
check always pass -- and this is the record that says what an approval was
about, so a stored definition edited after registration must be detectable
rather than silently re-blessed on load.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping, Optional

from backend.contracts.errors import ContractViolation
from backend.contracts.identity import PrincipalKind, PrincipalRef
from backend.contexts.connectivity.domain.contract import CapabilityContract
from backend.contexts.connectivity.domain.definition import (
    CapabilityDefinition,
    CapabilitySource,
    CapabilityTenancy,
)
from backend.contexts.connectivity.domain.identifiers import (
    CapabilityId,
    CapabilityVersion,
)
from backend.contexts.connectivity.domain.lifecycle import CapabilityStatus, TrustState

__all__ = ["RECORD_SCHEMA_VERSION", "to_record", "from_record"]

RECORD_SCHEMA_VERSION = 1


def to_record(
    definition: CapabilityDefinition, *, tenant_id: Optional[str]
) -> dict[str, Any]:
    """Flatten for storage.

    ``tenant_id`` on the row comes from the definition, not the caller's
    context: a platform capability legitimately has none, and taking the
    caller's tenant would silently re-scope it to whoever happened to write it.
    """
    return {
        "schema_version": RECORD_SCHEMA_VERSION,
        "tenant_id": definition.tenant_id,
        "reference": definition.reference.value,
        "capability_id": definition.capability_id.value,
        "version": definition.version.number,
        "name": definition.name,
        "description": definition.description,
        "provider": definition.provider,
        "category": definition.category,
        "contract": definition.contract.to_dict(),
        "owner": {
            "principal_id": definition.owner.principal_id,
            "kind": definition.owner.kind.value,
            "display_name": definition.owner.display_name,
        },
        "tenancy": definition.tenancy.value,
        "shared_with": sorted(definition.shared_with),
        "source": definition.source.value,
        "status": definition.status.value,
        "trust": definition.trust.value,
        "digest": definition.digest,
        "registered_at": definition.registered_at.isoformat(),
        "updated_at": (
            definition.updated_at.isoformat() if definition.updated_at else None
        ),
        "status_note": definition.status_note,
        "supersedes": definition.supersedes,
        "metadata": dict(definition.metadata),
    }


def from_record(data: Mapping[str, Any]) -> CapabilityDefinition:
    schema = data.get("schema_version")
    if schema != RECORD_SCHEMA_VERSION:
        raise ContractViolation(
            f"record schema version {schema!r} is not {RECORD_SCHEMA_VERSION}; "
            "refusing to guess at a shape this build does not know"
        )

    owner = data["owner"]
    return CapabilityDefinition(
        capability_id=CapabilityId.parse(data["capability_id"]),
        version=CapabilityVersion(data["version"]),
        name=data["name"],
        description=data["description"],
        provider=data["provider"],
        contract=CapabilityContract.from_dict(data["contract"]),
        owner=PrincipalRef(
            principal_id=owner["principal_id"],
            kind=PrincipalKind(owner["kind"]),
            display_name=owner.get("display_name"),
        ),
        tenancy=CapabilityTenancy(data["tenancy"]),
        source=CapabilitySource(data["source"]),
        tenant_id=data.get("tenant_id"),
        shared_with=tuple(data.get("shared_with", ())),
        category=data.get("category"),
        status=CapabilityStatus(data["status"]),
        trust=TrustState(data["trust"]),
        digest=data.get("digest"),
        registered_at=datetime.fromisoformat(data["registered_at"]),
        updated_at=(
            datetime.fromisoformat(data["updated_at"]) if data.get("updated_at") else None
        ),
        status_note=data.get("status_note"),
        supersedes=data.get("supersedes"),
        metadata=data.get("metadata", {}),
    )
