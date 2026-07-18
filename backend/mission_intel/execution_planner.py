from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from backend.mission_intel.models import (
    CapabilityPlan,
    ExecutionPlan,
    ExecutionSubPlan,
    GovernancePlan,
    MissionDecomposition,
    PlanStatus,
)

log = logging.getLogger(__name__)


class ExecutionPlanner:

    async def plan(
        self,
        decomposition: MissionDecomposition,
        capability_plan: CapabilityPlan,
        governance_plan: GovernancePlan,
        context: Optional[Dict[str, Any]] = None,
    ) -> ExecutionPlan:
        ctx = context or {}
        mission_id = decomposition.mission_id
        sub_plans: List[ExecutionSubPlan] = []
        connectors_needed: List[str] = []

        seen_connectors: set = set()
        for step in decomposition.steps:
            conn = capability_plan.connector_mappings.get(step.task_id, step.connector_type)
            if conn and conn not in seen_connectors:
                seen_connectors.add(conn)
                connectors_needed.append(conn)

        sequential_steps: List[str] = []
        for step in decomposition.steps:
            sequential_steps.append(step.id)

        if sequential_steps:
            sub_plans.append(ExecutionSubPlan(
                type="sequential",
                steps=sequential_steps,
                params={"order": "strict", "fail_fast": True},
            ))

        for group in decomposition.groups:
            if len(group.task_ids) > 1:
                step_ids = [
                    s.id for s in decomposition.steps
                    if s.task_id in group.task_ids
                ]
                if step_ids:
                    sub_plans.append(ExecutionSubPlan(
                        type="parallel",
                        steps=step_ids,
                        params={"timeout_seconds": 300},
                    ))

        max_retries = 2
        if ctx.get("retries") is not None:
            max_retries = int(ctx["retries"])

        rollback_plan = (
            "Reverse sequential rollback from last completed step"
            if len(decomposition.steps) > 1
            else "Rollback single step"
        )

        verification_plan = (
            "Verify each step after execution using connector health check"
            if any(s.verification_required for s in decomposition.steps)
            else "No verification required"
        )

        estimated = decomposition.estimated_duration_seconds
        for gate in governance_plan.approval_gates:
            estimated += gate.get("timeout_seconds", 300)

        return ExecutionPlan(
            mission_id=mission_id,
            status=PlanStatus.PENDING,
            sub_plans=sub_plans,
            connectors_needed=connectors_needed,
            estimated_duration_seconds=estimated,
            max_retries=max_retries,
            rollback_plan=rollback_plan,
            verification_plan=verification_plan,
            created_at=None,
        )


execution_planner = ExecutionPlanner()
