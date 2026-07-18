from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from backend.connector.models import Capability
from backend.mission_intel.models import (
    ExecutionPlan,
    MissionDecomposition,
    MissionVerification,
)

log = logging.getLogger(__name__)


class MissionVerifier:

    async def verify(
        self,
        decomposition: MissionDecomposition,
        execution_plan: ExecutionPlan,
        context: Optional[Dict[str, Any]] = None,
    ) -> MissionVerification:
        success_criteria: List[Dict[str, Any]] = []
        verification_steps: List[Dict[str, Any]] = []
        rollback_criteria: List[str] = []
        completion_criteria: List[str] = []
        verification_methods: Dict[str, str] = {}

        for i, task in enumerate(decomposition.tasks):
            crit = {
                "task_id": task.id,
                "name": task.name,
                "description": f"Verify {task.description} completed successfully",
                "metric": "execution_success",
                "threshold": 1.0,
            }
            success_criteria.append(crit)

            vstep = {
                "step_id": f"v_{i}",
                "task_id": task.id,
                "method": self._select_verification_method(task.required_capability),
                "expected": "success",
            }
            verification_steps.append(vstep)
            verification_methods[task.id] = vstep["method"]

        if decomposition.critical_path:
            rollback_criteria.append(
                "Rollback if any step on critical path fails"
            )
            completion_criteria.append(
                f"All {len(decomposition.critical_path)} critical path steps completed"
            )

        if execution_plan.max_retries > 0:
            rollback_criteria.append(
                f"Rollback if all {execution_plan.max_retries} retries are exhausted"
            )

        completion_criteria.extend([
            f"All {len(success_criteria)} success criteria met",
            "Execution plan completed without unrecoverable errors",
        ])

        if execution_plan.verification_plan:
            verification_methods["_plan"] = execution_plan.verification_plan

        return MissionVerification(
            success_criteria=success_criteria,
            verification_steps=verification_steps,
            rollback_criteria=rollback_criteria,
            completion_criteria=completion_criteria,
            verification_methods=verification_methods,
        )

    def _select_verification_method(self, capability: str) -> str:
        method_map: Dict[str, str] = {
            "deploy": "health_check",
            "rollback": "version_check",
            "observe": "metric_query",
            "scale": "count_check",
            "restart": "health_check",
            "build": "artifact_check",
            "test": "result_parse",
            "notify": "delivery_check",
            "provision": "exists_check",
            "destroy": "absent_check",
            "search": "result_count",
            "execute": "exit_code_check",
            "configure": "diff_check",
        }
        return method_map.get(capability, "status_check")


mission_verifier = MissionVerifier()
