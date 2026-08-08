"""Mapping between the Plan aggregate and a storable record.

Storage-agnostic: a plain mapping of primitives.

Every invariant is re-checked on the way in -- including the graph, which is
rebuilt and re-validated by ``Plan.__post_init__``. So a stored plan whose tasks
were edited into a cycle refuses to load rather than loading and stalling an
executor later.

The approval digest is **restored, not recomputed**. Recomputing would make it
always match -- a check that cannot fail -- and this is the artifact execution
acts on, so that check is how anyone knows the plan on file is the one approved.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping

from backend.contracts.errors import ContractViolation
from backend.contracts.execution import SideEffectClass
from backend.contexts.planner.domain.goals import PlanGoal, SuccessCriterionRef
from backend.contexts.planner.domain.identifiers import GoalId, PlanId, RiskId
from backend.contexts.planner.domain.plan import Plan
from backend.contexts.planner.domain.risk import (
    Likelihood,
    PlanRisk,
    RiskAssessment,
    RiskLevel,
)
from backend.contexts.planner.domain.status import PlanStatus
from backend.contexts.planner.domain.strategy import (
    ExecutionMode,
    ExecutionStrategy,
    FailureResponse,
    RollbackKind,
    RollbackStrategy,
)
from backend.contexts.planner.domain.tasks import PlanTask, Reversal

__all__ = ["RECORD_SCHEMA_VERSION", "to_record", "from_record"]

RECORD_SCHEMA_VERSION = 1


def _optional_time(value):
    return datetime.fromisoformat(value) if value else None


def to_record(plan: Plan, *, tenant_id: str) -> dict[str, Any]:
    if not isinstance(tenant_id, str) or not tenant_id.strip():
        raise ContractViolation(
            "tenant_id must be non-blank; it is derived from the context"
        )

    return {
        "schema_version": RECORD_SCHEMA_VERSION,
        "tenant_id": tenant_id,
        "plan_id": str(plan.plan_id),
        "mission_id": plan.mission_id,
        "intent_id": plan.intent_id,
        "intent_digest": plan.intent_digest,
        "title": plan.title,
        "version": plan.version,
        "goals": [
            {
                "goal_id": str(g.goal_id),
                "statement": g.statement,
                "satisfies": [
                    {"criterion_id": ref.criterion_id, "statement": ref.statement}
                    for ref in sorted(g.satisfies)
                ],
                "rationale": g.rationale,
            }
            for g in plan.goals
        ],
        "tasks": [
            {
                "task_id": t.task_id,
                "purpose": t.purpose,
                "goal_ids": sorted(t.goal_ids),
                "depends_on": list(t.depends_on),
                "side_effect": t.side_effect.value,
                "reversal": (
                    {
                        "compensating_task": t.reversal.compensating_task,
                        "inverse_action": t.reversal.inverse_action,
                        "note": t.reversal.note,
                    }
                    if t.reversal
                    else None
                ),
                "irreversible_accepted_by": t.irreversible_accepted_by,
                "execution_key": t.execution_key,
                "estimate_note": t.estimate_note,
            }
            for t in plan.tasks
        ],
        "success_criteria": [
            {"criterion_id": c.criterion_id, "statement": c.statement}
            for c in sorted(plan.success_criteria)
        ],
        "execution_strategy": {
            "mode": plan.execution_strategy.mode.value,
            "on_failure": plan.execution_strategy.on_failure.value,
            "max_parallelism": plan.execution_strategy.max_parallelism,
            "checkpoint_after": list(plan.execution_strategy.checkpoint_after),
            "continue_justification": plan.execution_strategy.continue_justification,
        },
        "rollback_strategy": {
            "kind": plan.rollback_strategy.kind.value,
            "description": plan.rollback_strategy.description,
            "accepted_by": plan.rollback_strategy.accepted_by,
            "snapshot_of": list(plan.rollback_strategy.snapshot_of),
        },
        "risk_assessment": (
            {
                "overall": plan.risk_assessment.overall.value,
                "assessed_by": plan.risk_assessment.assessed_by,
                "note": plan.risk_assessment.note,
                "risks": [
                    {
                        "risk_id": str(r.risk_id),
                        "statement": r.statement,
                        "level": r.level.value,
                        "likelihood": r.likelihood.value,
                        "mitigation": r.mitigation,
                        "affected_tasks": list(r.affected_tasks),
                        "declared_at": r.declared_at.isoformat(),
                    }
                    for r in plan.risk_assessment.risks
                ],
            }
            if plan.risk_assessment
            else None
        ),
        "status": plan.status.value,
        "validated_at": plan.validated_at.isoformat() if plan.validated_at else None,
        "approved_at": plan.approved_at.isoformat() if plan.approved_at else None,
        "approved_by": plan.approved_by,
        "rejection_reason": plan.rejection_reason,
        "digest": plan.digest,
        "supersedes": str(plan.supersedes) if plan.supersedes else None,
        "superseded_by": str(plan.superseded_by) if plan.superseded_by else None,
        "planned_by": plan.planned_by,
        "created_at": plan.created_at.isoformat(),
    }


def from_record(data: Mapping[str, Any]) -> Plan:
    schema = data.get("schema_version")
    if schema != RECORD_SCHEMA_VERSION:
        raise ContractViolation(
            f"record schema version {schema!r} is not {RECORD_SCHEMA_VERSION}; refusing "
            "to guess at a shape this build does not know"
        )

    strategy = data["execution_strategy"]
    rollback = data["rollback_strategy"]
    stored_risk = data.get("risk_assessment")

    return Plan(
        plan_id=PlanId(data["plan_id"]),
        mission_id=data["mission_id"],
        intent_id=data["intent_id"],
        intent_digest=data["intent_digest"],
        title=data["title"],
        version=data["version"],
        goals=tuple(
            PlanGoal(
                goal_id=GoalId(g["goal_id"]),
                statement=g["statement"],
                satisfies=frozenset(
                    SuccessCriterionRef(
                        criterion_id=ref["criterion_id"], statement=ref["statement"]
                    )
                    for ref in g["satisfies"]
                ),
                rationale=g.get("rationale", ""),
            )
            for g in data["goals"]
        ),
        tasks=tuple(
            PlanTask(
                task_id=t["task_id"],
                purpose=t["purpose"],
                goal_ids=frozenset(t["goal_ids"]),
                depends_on=tuple(t["depends_on"]),
                side_effect=SideEffectClass(t["side_effect"]),
                reversal=(
                    Reversal(
                        compensating_task=t["reversal"].get("compensating_task"),
                        inverse_action=t["reversal"].get("inverse_action"),
                        note=t["reversal"].get("note", ""),
                    )
                    if t.get("reversal")
                    else None
                ),
                irreversible_accepted_by=t.get("irreversible_accepted_by"),
                execution_key=t.get("execution_key"),
                estimate_note=t.get("estimate_note", ""),
            )
            for t in data["tasks"]
        ),
        success_criteria=frozenset(
            SuccessCriterionRef(
                criterion_id=c["criterion_id"], statement=c["statement"]
            )
            for c in data["success_criteria"]
        ),
        execution_strategy=ExecutionStrategy(
            mode=ExecutionMode(strategy["mode"]),
            on_failure=FailureResponse(strategy["on_failure"]),
            max_parallelism=strategy["max_parallelism"],
            checkpoint_after=tuple(strategy["checkpoint_after"]),
            continue_justification=strategy.get("continue_justification", ""),
        ),
        rollback_strategy=RollbackStrategy(
            kind=RollbackKind(rollback["kind"]),
            description=rollback.get("description", ""),
            accepted_by=rollback.get("accepted_by"),
            snapshot_of=tuple(rollback["snapshot_of"]),
        ),
        risk_assessment=(
            RiskAssessment(
                overall=RiskLevel(stored_risk["overall"]),
                assessed_by=stored_risk["assessed_by"],
                note=stored_risk.get("note", ""),
                risks=tuple(
                    PlanRisk(
                        risk_id=RiskId(r["risk_id"]),
                        statement=r["statement"],
                        level=RiskLevel(r["level"]),
                        likelihood=Likelihood(r["likelihood"]),
                        mitigation=r.get("mitigation"),
                        affected_tasks=tuple(r["affected_tasks"]),
                        declared_at=datetime.fromisoformat(r["declared_at"]),
                    )
                    for r in stored_risk["risks"]
                ),
            )
            if stored_risk
            else None
        ),
        status=PlanStatus(data["status"]),
        validated_at=_optional_time(data.get("validated_at")),
        approved_at=_optional_time(data.get("approved_at")),
        approved_by=data.get("approved_by"),
        rejection_reason=data.get("rejection_reason"),
        digest=data.get("digest"),
        supersedes=PlanId(data["supersedes"]) if data.get("supersedes") else None,
        superseded_by=PlanId(data["superseded_by"]) if data.get("superseded_by") else None,
        planned_by=data["planned_by"],
        created_at=datetime.fromisoformat(data["created_at"]),
    )
