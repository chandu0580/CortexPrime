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

__all__ = [
    "RECORD_SCHEMA_VERSION",
    "BINDING_RECORD_SCHEMA_VERSION",
    "to_record",
    "from_record",
    "binding_to_record",
    "binding_from_record",
]

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


# ----------------------------------------------------------------------
# Bindings
# ----------------------------------------------------------------------

BINDING_RECORD_SCHEMA_VERSION = 1


def binding_to_record(binding: "Any") -> dict[str, Any]:
    """Flatten a ``CapabilityBinding`` for storage.

    Written explicitly rather than reusing ``to_dict``: that projection is
    shaped for audit and drops what a caller does not need to see, and a record
    that cannot rebuild the object is a record that loses the binding.

    The digest travels as stored. ``binding_from_record`` verifies it rather
    than recomputing it — this is the artifact that says what was authorized, so
    a row edited after the fact must be detectable.
    """
    return {
        "schema_version": BINDING_RECORD_SCHEMA_VERSION,
        "binding_id": binding.binding_id,
        "tenant_id": binding.tenant_id,
        "principal": {
            "principal_id": binding.principal.principal_id,
            "kind": binding.principal.kind.value,
            "display_name": binding.principal.display_name,
        },
        "capability_id": binding.capability_id.value,
        "version": binding.version.number,
        "capability_digest": binding.capability_digest,
        "provider": binding.provider,
        "operation": binding.operation.value,
        "provider_operation": binding.provider_operation,
        "authorization_digest": binding.authorization_digest,
        "authorization_policy_version": binding.authorization_policy_version,
        "resolution_policy_version": binding.resolution_policy_version,
        "resolved_at": binding.resolved_at.isoformat(),
        "expires_at": binding.expires_at.isoformat(),
        "approval_artifact_id": binding.approval_artifact_id,
        "code_trust": (
            binding.code_trust.value if binding.code_trust else None
        ),
        "side_effect_class": (
            binding.side_effect_class.value if binding.side_effect_class else None
        ),
        "effect_semantics": (
            binding.effect_semantics.value if binding.effect_semantics else None
        ),
        "mission_id": binding.mission_id,
        "workflow_id": binding.workflow_id,
        "execution_id": binding.execution_id,
        "node_id": binding.node_id,
        "selection_reasons": list(binding.selection_reasons),
        "rejected_candidates": [
            [reference, reason] for reference, reason in binding.rejected_candidates
        ],
        "candidate_count": binding.candidate_count,
        "digest": binding.digest,
    }


def binding_from_record(data: Mapping[str, Any]):
    """Rebuild a binding and **verify** its digest. Refuses a tampered row.

    ``verify_digest`` is the domain's own check and raises ``BindingUnusable``
    when the stored digest does not match the rebuilt payload. Calling it here
    is what makes an edited row fail to load rather than loading as authority
    nobody granted.
    """
    from backend.contracts.connector import CodeTrust
    from backend.contracts.execution import EffectSemantics, SideEffectClass
    from backend.contexts.connectivity.domain.binding import CapabilityBinding
    from backend.contexts.connectivity.domain.authorization import CapabilityOperation

    schema = data.get("schema_version")
    if schema != BINDING_RECORD_SCHEMA_VERSION:
        raise ContractViolation(
            f"binding record schema version {schema!r} is not "
            f"{BINDING_RECORD_SCHEMA_VERSION}; refusing to guess at a shape this "
            "build does not know"
        )
    principal = data["principal"]
    binding = CapabilityBinding(
        binding_id=data["binding_id"],
        tenant_id=data["tenant_id"],
        principal=PrincipalRef(
            principal_id=principal["principal_id"],
            kind=PrincipalKind(principal["kind"]),
            display_name=principal.get("display_name"),
        ),
        capability_id=CapabilityId.parse(data["capability_id"]),
        version=CapabilityVersion(data["version"]),
        capability_digest=data["capability_digest"],
        provider=data["provider"],
        operation=CapabilityOperation(data["operation"]),
        # ``get`` rather than ``[]``: bindings written before Phase 5.5
        # have no such key, and a stored binding must still load.
        provider_operation=data.get("provider_operation"),
        authorization_digest=data["authorization_digest"],
        authorization_policy_version=data["authorization_policy_version"],
        resolution_policy_version=data["resolution_policy_version"],
        resolved_at=datetime.fromisoformat(data["resolved_at"]),
        expires_at=datetime.fromisoformat(data["expires_at"]),
        approval_artifact_id=data.get("approval_artifact_id"),
        code_trust=(
            CodeTrust(data["code_trust"]) if data.get("code_trust") else None
        ),
        side_effect_class=(
            SideEffectClass(data["side_effect_class"])
            if data.get("side_effect_class")
            else None
        ),
        effect_semantics=(
            EffectSemantics(data["effect_semantics"])
            if data.get("effect_semantics")
            else None
        ),
        mission_id=data.get("mission_id"),
        workflow_id=data.get("workflow_id"),
        execution_id=data.get("execution_id"),
        node_id=data.get("node_id"),
        selection_reasons=tuple(data.get("selection_reasons", ())),
        rejected_candidates=tuple(
            (entry[0], entry[1]) for entry in data.get("rejected_candidates", ())
        ),
        candidate_count=data.get("candidate_count", 0),
        digest=data.get("digest"),
    )
    binding.verify_digest()
    return binding
