"""Construction helpers.

The aggregate's constructor takes strongly-typed values and enforces every
invariant, which is correct and verbose. These are the ergonomic paths in: a plan
always names the mandate it was built from, a goal always traces to a criterion,
and a mutating task always answers the reversibility question.
"""

from __future__ import annotations

from typing import Optional, Sequence

from backend.contracts.execution import SideEffectClass
from backend.contexts.planner.domain.goals import PlanGoal, SuccessCriterionRef
from backend.contexts.planner.domain.identifiers import PlanId
from backend.contexts.planner.domain.plan import Plan
from backend.contexts.planner.domain.risk import (
    Likelihood,
    PlanRisk,
    RiskAssessment,
    RiskLevel,
)
from backend.contexts.planner.domain.tasks import PlanTask, Reversal

__all__ = ["draft_plan", "goal", "task", "reversal", "risk", "assessment", "criterion"]


def draft_plan(
    *,
    mission_id: str,
    intent_id: str,
    intent_digest: str,
    title: str,
    planned_by: str = "planner",
) -> Plan:
    """An empty plan bound to the mandate it will serve.

    The binding comes first and has no default. A plan that could be drafted
    without naming the intent it serves would be a plan for whatever somebody
    later decided it was for.
    """
    return Plan(
        plan_id=PlanId.new(),
        mission_id=mission_id,
        intent_id=intent_id,
        intent_digest=intent_digest,
        title=title,
        planned_by=planned_by,
    )


def criterion(criterion_id: str, statement: str = "") -> SuccessCriterionRef:
    return SuccessCriterionRef(criterion_id=criterion_id, statement=statement)


def goal(statement: str, satisfies: Sequence, *, rationale: str = "") -> PlanGoal:
    return PlanGoal.create(statement, satisfies, rationale=rationale)


def reversal(
    *,
    compensating_task: Optional[str] = None,
    inverse_action: Optional[str] = None,
    note: str = "",
) -> Reversal:
    return Reversal(
        compensating_task=compensating_task, inverse_action=inverse_action, note=note
    )


def task(
    task_id: str,
    purpose: str,
    *,
    goals: Sequence[str] = (),
    depends_on: Sequence[str] = (),
    side_effect: SideEffectClass = SideEffectClass.READ,
    reverses_with: Optional[Reversal] = None,
    irreversible_accepted_by: Optional[str] = None,
    execution_key: Optional[str] = None,
) -> PlanTask:
    """A planned task. ``side_effect`` defaults to READ, the only safe default.

    Defaulting to anything that mutates would let a task that changes production
    be added without anyone stating that it does -- and the reversibility
    question would never be asked.
    """
    return PlanTask.create(
        task_id,
        purpose,
        goal_ids=goals,
        depends_on=depends_on,
        side_effect=side_effect,
        reversal=reverses_with,
        irreversible_accepted_by=irreversible_accepted_by,
        execution_key=execution_key,
    )


def risk(
    statement: str,
    level: RiskLevel = RiskLevel.LOW,
    *,
    likelihood: Likelihood = Likelihood.POSSIBLE,
    mitigation: Optional[str] = None,
    affected_tasks: Sequence[str] = (),
) -> PlanRisk:
    return PlanRisk.create(
        statement,
        level,
        likelihood=likelihood,
        mitigation=mitigation,
        affected_tasks=affected_tasks,
    )


def assessment(
    overall: RiskLevel = RiskLevel.LOW,
    *,
    risks: Sequence = (),
    assessed_by: str = "planner",
    note: str = "",
) -> RiskAssessment:
    return RiskAssessment.create(
        overall, risks=risks, assessed_by=assessed_by, note=note
    )
