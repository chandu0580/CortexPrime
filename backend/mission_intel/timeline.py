from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from backend.mission_intel.models import (
    ExecutionPlan,
    MissionAnalysis,
    MissionDecomposition,
    MissionTimeline,
    PipelineStep,
    TimelineEntry,
)

log = logging.getLogger(__name__)


class MissionTimelineBuilder:

    async def build(
        self,
        analysis: MissionAnalysis,
        decomposition: MissionDecomposition,
        execution_plan: ExecutionPlan,
        context: Optional[Dict[str, Any]] = None,
    ) -> MissionTimeline:
        now = datetime.now(timezone.utc).isoformat()
        entries: List[TimelineEntry] = []
        pipeline_steps: List[PipelineStep] = []

        entries.append(TimelineEntry(
            timestamp=now,
            source="mission_intel",
            event_type="analysis_complete",
            detail=f"Mission goal analyzed as '{analysis.category}' with {analysis.risk.value} risk",
            correlation_id=decomposition.mission_id,
            metadata={"goal": analysis.goal[:100]},
        ))

        for task in decomposition.tasks:
            entries.append(TimelineEntry(
                timestamp=now,
                source="mission_intel",
                event_type="task_defined",
                detail=f"Task '{task.name}' requires '{task.required_capability}'",
                correlation_id=decomposition.mission_id,
                metadata={"task_id": task.id},
            ))

        for i, step in enumerate(decomposition.steps):
            pipeline_step = PipelineStep(
                pipeline_id=decomposition.mission_id,
                name=step.name,
                phase=f"execution_{i}",
                status="pending",
                duration_ms=0.0,
                output=None,
            )
            pipeline_steps.append(pipeline_step)
            entries.append(TimelineEntry(
                timestamp=now,
                source="mission_intel",
                event_type="step_planned",
                detail=f"Step {i}: {step.name} via {step.connector_type}.{step.operation}",
                correlation_id=decomposition.mission_id,
                metadata={"step_id": step.id, "order": i},
            ))

        for conn in execution_plan.connectors_needed:
            entries.append(TimelineEntry(
                timestamp=now,
                source="mission_intel",
                event_type="connector_required",
                detail=f"Connector '{conn}' required for execution",
                correlation_id=decomposition.mission_id,
            ))

        if analysis.constraints:
            for c in analysis.constraints:
                entries.append(TimelineEntry(
                    timestamp=now,
                    source="mission_intel",
                    event_type="constraint_noted",
                    detail=f"Constraint: {c}",
                    correlation_id=decomposition.mission_id,
                ))

        if analysis.dependencies:
            for d in analysis.dependencies:
                entries.append(TimelineEntry(
                    timestamp=now,
                    source="mission_intel",
                    event_type="dependency_noted",
                    detail=f"Dependency: {d}",
                    correlation_id=decomposition.mission_id,
                ))

        connectors_used = list(execution_plan.connectors_needed)
        artifacts_referenced = [t.name for t in decomposition.tasks]

        return MissionTimeline(
            entries=entries,
            pipeline_steps=pipeline_steps,
            connectors_used=connectors_used,
            artifacts_referenced=artifacts_referenced,
        )


mission_timeline_builder = MissionTimelineBuilder()
