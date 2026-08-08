"""Mapping between the Intent aggregate and a storable record.

Storage-agnostic: a plain mapping of primitives.

Every invariant is re-checked on the way in, and the approval digest is
**restored, not recomputed**. Recomputing would make it always match -- a check
that cannot fail -- and this is the artifact planning acts on, so that check is
how anyone knows the mandate on file is the one that was approved.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping

from backend.contracts.errors import ContractViolation
from backend.contracts.identity import SecurityContext
from backend.contracts.mission import MissionIntent
from backend.contexts.intent.domain.constraints import (
    ConstraintEnforcement,
    ConstraintKind,
    IntentConstraint,
)
from backend.contexts.intent.domain.identifiers import (
    ConstraintId,
    CriterionId,
    IntentId,
    RiskId,
)
from backend.contexts.intent.domain.intent import Intent
from backend.contexts.intent.domain.metadata import IntentMetadata, IntentOrigin
from backend.contexts.intent.domain.objective import (
    IntentObjective,
    OutcomeKind,
    SuccessCriterion,
)
from backend.contexts.intent.domain.priority import (
    AcknowledgedRisk,
    ImpactLevel,
    IntentPriority,
    RiskAppetite,
)
from backend.contexts.intent.domain.scope import Environment, IntentScope, ScopeTarget
from backend.contexts.intent.domain.status import IntentStatus

__all__ = ["RECORD_SCHEMA_VERSION", "to_record", "from_record"]

RECORD_SCHEMA_VERSION = 1


def _optional_time(value):
    return datetime.fromisoformat(value) if value else None


def to_record(intent: Intent, *, tenant_id: str) -> dict[str, Any]:
    if not isinstance(tenant_id, str) or not tenant_id.strip():
        raise ContractViolation(
            "tenant_id must be non-blank; it is derived from the context"
        )

    return {
        "schema_version": RECORD_SCHEMA_VERSION,
        "tenant_id": tenant_id,
        "intent_id": str(intent.intent_id),
        "raw": {
            "stated_goal": intent.raw.stated_goal,
            "requested_by": intent.raw.requested_by.to_dict(),
            "requested_at": intent.raw.requested_at.isoformat(),
        },
        "metadata": {
            "title": intent.metadata.title,
            "origin": intent.metadata.origin.value,
            "tags": sorted(intent.metadata.tags),
            "requested_for": intent.metadata.requested_for,
            "derived_from": intent.metadata.derived_from,
        },
        "objective": (
            {
                "outcome": intent.objective.outcome,
                "kind": intent.objective.kind.value,
                "rationale": intent.objective.rationale,
                "subject": intent.objective.subject,
            }
            if intent.objective
            else None
        ),
        "constraints": [
            {
                "constraint_id": str(c.constraint_id),
                "kind": c.kind.value,
                "statement": c.statement,
                "limit": c.limit,
                "enforcement": c.enforcement.value,
                "rationale": c.rationale,
                "declared_at": c.declared_at.isoformat(),
            }
            for c in intent.constraints
        ],
        "scope": (
            {
                "included": [
                    {"identifier": t.identifier, "target_type": t.target_type}
                    for t in sorted(intent.scope.included)
                ],
                "excluded": [
                    {"identifier": t.identifier, "target_type": t.target_type}
                    for t in sorted(intent.scope.excluded)
                ],
                "environments": sorted(e.value for e in intent.scope.environments),
                "note": intent.scope.note,
            }
            if intent.scope
            else None
        ),
        "priority": intent.priority.value,
        "risk_appetite": intent.risk_appetite.value,
        "acknowledged_risks": [
            {
                "risk_id": str(r.risk_id),
                "statement": r.statement,
                "impact": r.impact.value,
                "accepted_by": r.accepted_by,
                "declared_at": r.declared_at.isoformat(),
            }
            for r in intent.acknowledged_risks
        ],
        "success_criteria": [
            {
                "criterion_id": str(c.criterion_id),
                "statement": c.statement,
                "measure": c.measure,
                "threshold": c.threshold,
                "baseline": c.baseline,
                "declared_at": c.declared_at.isoformat(),
            }
            for c in intent.success_criteria
        ],
        "status": intent.status.value,
        "validated_at": intent.validated_at.isoformat() if intent.validated_at else None,
        "approved_at": intent.approved_at.isoformat() if intent.approved_at else None,
        "approved_by": intent.approved_by,
        "rejection_reason": intent.rejection_reason,
        "digest": intent.digest,
        "expansion_count": intent.expansion_count,
        "created_at": intent.created_at.isoformat(),
        "superseded_by": str(intent.superseded_by) if intent.superseded_by else None,
    }


def from_record(data: Mapping[str, Any]) -> Intent:
    schema = data.get("schema_version")
    if schema != RECORD_SCHEMA_VERSION:
        raise ContractViolation(
            f"record schema version {schema!r} is not {RECORD_SCHEMA_VERSION}; refusing "
            "to guess at a shape this build does not know"
        )

    raw = data["raw"]
    metadata = data["metadata"]
    stored_objective = data.get("objective")
    stored_scope = data.get("scope")

    return Intent(
        intent_id=IntentId(data["intent_id"]),
        raw=MissionIntent(
            stated_goal=raw["stated_goal"],
            requested_by=SecurityContext.from_dict(raw["requested_by"]),
            requested_at=datetime.fromisoformat(raw["requested_at"]),
        ),
        metadata=IntentMetadata(
            title=metadata["title"],
            origin=IntentOrigin(metadata["origin"]),
            tags=frozenset(metadata["tags"]),
            requested_for=metadata.get("requested_for"),
            derived_from=metadata.get("derived_from"),
        ),
        objective=(
            IntentObjective(
                outcome=stored_objective["outcome"],
                kind=OutcomeKind(stored_objective["kind"]),
                rationale=stored_objective.get("rationale", ""),
                subject=stored_objective.get("subject"),
            )
            if stored_objective
            else None
        ),
        constraints=tuple(
            IntentConstraint(
                constraint_id=ConstraintId(c["constraint_id"]),
                kind=ConstraintKind(c["kind"]),
                statement=c["statement"],
                limit=c.get("limit"),
                enforcement=ConstraintEnforcement(c["enforcement"]),
                rationale=c.get("rationale", ""),
                declared_at=datetime.fromisoformat(c["declared_at"]),
            )
            for c in data["constraints"]
        ),
        scope=(
            IntentScope(
                included=frozenset(
                    ScopeTarget(t["identifier"], t["target_type"])
                    for t in stored_scope["included"]
                ),
                excluded=frozenset(
                    ScopeTarget(t["identifier"], t["target_type"])
                    for t in stored_scope["excluded"]
                ),
                environments=frozenset(
                    Environment(e) for e in stored_scope["environments"]
                ),
                note=stored_scope.get("note"),
            )
            if stored_scope
            else None
        ),
        priority=IntentPriority(data["priority"]),
        risk_appetite=RiskAppetite(data["risk_appetite"]),
        acknowledged_risks=tuple(
            AcknowledgedRisk(
                risk_id=RiskId(r["risk_id"]),
                statement=r["statement"],
                impact=ImpactLevel(r["impact"]),
                accepted_by=r.get("accepted_by"),
                declared_at=datetime.fromisoformat(r["declared_at"]),
            )
            for r in data["acknowledged_risks"]
        ),
        success_criteria=tuple(
            SuccessCriterion(
                criterion_id=CriterionId(c["criterion_id"]),
                statement=c["statement"],
                measure=c["measure"],
                threshold=c.get("threshold"),
                baseline=c.get("baseline"),
                declared_at=datetime.fromisoformat(c["declared_at"]),
            )
            for c in data["success_criteria"]
        ),
        status=IntentStatus(data["status"]),
        validated_at=_optional_time(data.get("validated_at")),
        approved_at=_optional_time(data.get("approved_at")),
        approved_by=data.get("approved_by"),
        rejection_reason=data.get("rejection_reason"),
        digest=data.get("digest"),
        expansion_count=data["expansion_count"],
        created_at=datetime.fromisoformat(data["created_at"]),
        superseded_by=IntentId(data["superseded_by"]) if data.get("superseded_by") else None,
    )
