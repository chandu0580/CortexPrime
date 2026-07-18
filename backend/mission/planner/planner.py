from __future__ import annotations

import uuid
from typing import Any, Optional

from backend.mission.planner.interfaces import (
    MissionArtifact,
    MissionConstraint,
    MissionDependency,
    MissionPlan,
    MissionPlanner,
    MissionStep,
)


class StructuredMissionPlanner(MissionPlanner):
    def __init__(self) -> None:
        self._plans: dict[str, MissionPlan] = {}

    async def create_plan(self, mission_id: str, title: str, objective: str,
                          context: dict[str, Any]) -> MissionPlan:
        plan_id = f"plan-{uuid.uuid4().hex[:12]}"
        steps = [
            MissionStep(
                step_id=f"{plan_id}-step-1",
                order=1,
                name="Initialise",
                description="Prepare mission context and validate inputs",
                timeout_seconds=60,
            ),
            MissionStep(
                step_id=f"{plan_id}-step-2",
                order=2,
                name="Execute",
                description="Execute the primary mission objective",
                dependencies=[f"{plan_id}-step-1"],
                timeout_seconds=600,
                max_retries=3,
            ),
            MissionStep(
                step_id=f"{plan_id}-step-3",
                order=3,
                name="Verify",
                description="Verify mission results against objectives",
                dependencies=[f"{plan_id}-step-2"],
                timeout_seconds=120,
            ),
            MissionStep(
                step_id=f"{plan_id}-step-4",
                order=4,
                name="Complete",
                description="Finalise mission and record outcomes",
                dependencies=[f"{plan_id}-step-3"],
                timeout_seconds=60,
            ),
        ]
        plan = MissionPlan(
            plan_id=plan_id,
            mission_id=mission_id,
            steps=steps,
            estimated_duration_ms=5 * 60 * 1000,
            metadata={"title": title, "objective": objective},
        )
        self._plans[plan_id] = plan
        return plan

    async def get_plan(self, plan_id: str) -> Optional[MissionPlan]:
        return self._plans.get(plan_id)

    async def get_plan_for_mission(self, mission_id: str) -> Optional[MissionPlan]:
        for plan in self._plans.values():
            if plan.mission_id == mission_id:
                return plan
        return None
