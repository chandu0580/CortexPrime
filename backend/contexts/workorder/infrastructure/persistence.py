"""Mapping between the WorkOrder aggregate and a storable record.

Storage-agnostic on purpose. A record here is a plain mapping of primitives; it
carries no SQL, no document-store idiom, and no file format. Whichever store
eventually holds these -- and the state guard forbids that being a JSON file --
maps from this shape rather than from the aggregate.

The separation buys two things. The aggregate stays free of persistence
concerns, and the round trip is testable without a database, which is what makes
the property test in ``test_persistence.py`` cheap enough to run on every commit.

The record carries a ``tenant_id`` the aggregate does not have. Tenancy is a
storage concern here, derived from the execution context at write time and never
from the aggregate -- a repository that read tenancy from the thing being stored
would let the caller choose its own isolation boundary.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping

from backend.contracts.approval import HashAlgorithm, PayloadDigest
from backend.contracts.errors import ContractViolation
from backend.contexts.workorder.domain.assumption import Assumption, AssumptionResolution
from backend.contexts.workorder.domain.blast_radius import BlastRadius, PathPattern
from backend.contexts.workorder.domain.identifiers import (
    AdrRef,
    AssumptionId,
    ConstraintRef,
    EvidenceRef,
    RejectionGroundId,
    WorkOrderId,
)
from backend.contexts.workorder.domain.rejection import RejectionGround, RejectionType
from backend.contexts.workorder.domain.states import WorkOrderState
from backend.contexts.workorder.domain.work_order import Priority, WorkOrder

__all__ = ["RECORD_SCHEMA_VERSION", "to_record", "from_record"]

#: Version of the record shape. Independent of the aggregate's own version and
#: of the canonical digest form -- conflating the three is how a storage
#: migration silently invalidates every stored approval.
RECORD_SCHEMA_VERSION = 1


def _assumption_record(assumption: Assumption) -> dict:
    return {
        "assumption_id": str(assumption.assumption_id),
        "statement": assumption.statement,
        "verification_method": assumption.verification_method,
        "resolution": assumption.resolution.value if assumption.resolution else None,
        "resolution_evidence": (
            str(assumption.resolution_evidence) if assumption.resolution_evidence else None
        ),
    }


def _ground_record(ground: RejectionGround) -> dict:
    return {
        "ground_id": str(ground.ground_id),
        "condition": ground.condition,
        "rejection_type": ground.rejection_type.value,
        "triggering_assumption": (
            str(ground.triggering_assumption) if ground.triggering_assumption else None
        ),
    }


def to_record(work_order: WorkOrder, *, tenant_id: str) -> dict[str, Any]:
    """Flatten an aggregate into a storable mapping."""
    if not isinstance(tenant_id, str) or not tenant_id.strip():
        raise ContractViolation("tenant_id must be non-blank; it is derived from the context")

    return {
        "schema_version": RECORD_SCHEMA_VERSION,
        "tenant_id": tenant_id,
        "work_id": str(work_order.work_id),
        "version": work_order.version,
        "intent": work_order.intent,
        "acceptance_criteria": sorted(work_order.acceptance_criteria),
        "adr_references": sorted(str(a) for a in work_order.adr_references),
        "evidence": sorted(str(e) for e in work_order.evidence),
        "constraints": sorted(str(c) for c in work_order.constraints),
        "blast_radius": {
            "allowed": sorted(str(p) for p in work_order.blast_radius.allowed),
            "forbidden": sorted(str(p) for p in work_order.blast_radius.forbidden),
            "read_only": sorted(str(p) for p in work_order.blast_radius.read_only),
            "justification": work_order.blast_radius.justification,
        },
        "assumptions": [_assumption_record(a) for a in work_order.assumptions],
        "rejection_grounds": [_ground_record(g) for g in work_order.rejection_grounds],
        "dependencies": sorted(str(d) for d in work_order.dependencies),
        "definition_of_done": sorted(work_order.definition_of_done),
        "state": work_order.state.value,
        "priority": work_order.priority.value,
        "digest": (
            {
                "algorithm": work_order.digest.algorithm.value,
                "value": work_order.digest.value,
            }
            if work_order.digest
            else None
        ),
        "created_at": work_order.created_at.isoformat(),
        "created_by": work_order.created_by,
        "supersedes": str(work_order.supersedes) if work_order.supersedes else None,
        "superseded_by": str(work_order.superseded_by) if work_order.superseded_by else None,
        "rejection_type": (
            work_order.rejection_type.value if work_order.rejection_type else None
        ),
        "rejection_detail": work_order.rejection_detail,
    }


def from_record(record: Mapping[str, Any]) -> WorkOrder:
    """Rebuild an aggregate from a stored mapping.

    Every invariant is re-checked on the way in, because a record read back from
    storage is untrusted input. Skipping validation here on the grounds that it
    "was valid when written" assumes the store was never edited by anything but
    this code -- which is exactly the assumption the product's own audit chain
    exists because nobody should make.
    """
    schema = record.get("schema_version")
    if schema != RECORD_SCHEMA_VERSION:
        raise ContractViolation(
            f"record schema version {schema!r} is not {RECORD_SCHEMA_VERSION}; refusing "
            "to guess at a shape this build does not know"
        )

    digest_data = record.get("digest")
    digest = (
        PayloadDigest(
            algorithm=HashAlgorithm(digest_data["algorithm"]), value=digest_data["value"]
        )
        if digest_data
        else None
    )

    radius_data = record["blast_radius"]
    radius = BlastRadius(
        allowed=frozenset(PathPattern(p) for p in radius_data["allowed"]),
        forbidden=frozenset(PathPattern(p) for p in radius_data["forbidden"]),
        read_only=frozenset(PathPattern(p) for p in radius_data["read_only"]),
        justification=radius_data.get("justification"),
    )

    assumptions = tuple(
        Assumption(
            assumption_id=AssumptionId(item["assumption_id"]),
            statement=item["statement"],
            verification_method=item["verification_method"],
            resolution=(
                AssumptionResolution(item["resolution"]) if item.get("resolution") else None
            ),
            resolution_evidence=(
                EvidenceRef(item["resolution_evidence"])
                if item.get("resolution_evidence")
                else None
            ),
        )
        for item in record["assumptions"]
    )

    grounds = tuple(
        RejectionGround(
            ground_id=RejectionGroundId(item["ground_id"]),
            condition=item["condition"],
            rejection_type=RejectionType(item["rejection_type"]),
            triggering_assumption=(
                AssumptionId(item["triggering_assumption"])
                if item.get("triggering_assumption")
                else None
            ),
        )
        for item in record["rejection_grounds"]
    )

    return WorkOrder(
        work_id=WorkOrderId(record["work_id"]),
        version=record["version"],
        intent=record["intent"],
        acceptance_criteria=frozenset(record["acceptance_criteria"]),
        adr_references=frozenset(AdrRef(a) for a in record["adr_references"]),
        evidence=frozenset(EvidenceRef(e) for e in record["evidence"]),
        constraints=frozenset(ConstraintRef(c) for c in record["constraints"]),
        blast_radius=radius,
        assumptions=assumptions,
        rejection_grounds=grounds,
        dependencies=frozenset(WorkOrderId(d) for d in record["dependencies"]),
        definition_of_done=frozenset(record["definition_of_done"]),
        state=WorkOrderState(record["state"]),
        priority=Priority(record["priority"]),
        digest=digest,
        created_at=datetime.fromisoformat(record["created_at"]),
        created_by=record["created_by"],
        supersedes=WorkOrderId(record["supersedes"]) if record.get("supersedes") else None,
        superseded_by=(
            WorkOrderId(record["superseded_by"]) if record.get("superseded_by") else None
        ),
        rejection_type=(
            RejectionType(record["rejection_type"]) if record.get("rejection_type") else None
        ),
        rejection_detail=record.get("rejection_detail"),
    )
