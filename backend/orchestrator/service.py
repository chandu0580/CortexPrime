from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from uuid import uuid4

from backend.orchestrator.artifact_manager import artifact_manager
from backend.orchestrator.context import OrchestratorContext
from backend.orchestrator.engine import OrchestrationEngine, engine
from backend.orchestrator.event_pipeline import event_pipeline
from backend.orchestrator.models import (
    MissionLifecycleState,
    OrchestratorMission,
    OrchestratorStatus,
)
from backend.orchestrator.observability import metrics_collector
from backend.orchestrator.recovery import FailureClassifier, RecoveryManager, recovery_manager
from backend.orchestrator.runtime_resolver import get_cognitive_memory_service

log = logging.getLogger(__name__)


def _classify_failure(error: str, stage: str, runtime: str = "") -> str:
    cat, _ = FailureClassifier.classify(error, stage, runtime=runtime)
    return cat.value


class AutonomousMissionOrchestrator:
    def __init__(
        self,
        orchestration_engine: Optional[OrchestrationEngine] = None,
        recovery_mgr: Optional[RecoveryManager] = None,
    ) -> None:
        self._engine = orchestration_engine or engine
        self._missions: Dict[str, OrchestratorMission] = {}
        self._recovery_mgr = recovery_mgr or recovery_manager

    def start_mission(
        self,
        goal: str,
        mission_id: str = "",
        tenant_id: str = "",
        user_id: str = "",
        trace_id: str = "",
        correlation_id: str = "",
        permissions: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> OrchestratorMission:
        mid = mission_id or uuid4().hex[:12]
        ctx = OrchestratorContext(
            tenant_id=tenant_id,
            user_id=user_id,
            mission_id=mid,
            trace_id=trace_id,
            correlation_id=correlation_id,
            permissions=permissions or [],
            metadata=metadata or {},
        )
        mission = OrchestratorMission(
            mission_id=mid,
            goal=goal,
            current_state=MissionLifecycleState.RECEIVED,
            status=OrchestratorStatus.PENDING,
            metadata={
                **(metadata or {}),
                "tenant_id": ctx.tenant_id,
                "user_id": ctx.user_id,
                "trace_id": ctx.trace_id,
                "correlation_id": ctx.correlation_id,
                "permissions": ctx.permissions,
                "execution_id": ctx.execution_id,
            },
            context=ctx.to_dict(),
        )
        self._missions[mid] = mission
        event_pipeline.emit(
            mid, MissionLifecycleState.RECEIVED, "mission.received", "orchestrator",
            f"Mission received: {goal}",
            correlation_id=ctx.correlation_id,
        )

        mem = get_cognitive_memory_service()
        if mem:
            try:
                mem.create_context(
                    mission_id=mid,
                    user_id=tenant_id or "",
                    tenant_id=user_id or "",
                    trace_id=ctx.trace_id,
                    correlation_id=ctx.correlation_id,
                    initial_goal=goal,
                    mission_name=metadata.get("name", goal) if metadata else goal,
                    objective=metadata.get("objective", "") if metadata else "",
                    category=metadata.get("category", "") if metadata else "",
                )
            except Exception as exc:
                log.debug("Failed to create cognitive memory context: %s", exc)

        return mission

    async def run_mission(self, mission_id: str) -> Optional[OrchestratorMission]:
        mission = self._missions.get(mission_id)
        if not mission:
            return None
        return await self._engine.run_mission(mission)

    async def pause_mission(self, mission_id: str) -> bool:
        return await self._engine.pause_mission(mission_id)

    async def resume_mission(self, mission_id: str) -> bool:
        return await self._engine.resume_mission(mission_id)

    async def cancel_mission(self, mission_id: str) -> bool:
        return await self._engine.cancel_mission(mission_id)

    def get_mission(self, mission_id: str) -> Optional[OrchestratorMission]:
        return self._missions.get(mission_id)

    def get_mission_timeline(self, mission_id: str) -> List[Dict[str, Any]]:
        return [{
            "mission_id": e.mission_id,
            "state": e.state.value,
            "event_type": e.event_type,
            "source": e.source,
            "message": e.message,
            "timestamp": e.timestamp,
            "correlation_id": e.correlation_id,
        } for e in event_pipeline.get_events(mission_id)]

    def list_missions(
        self,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> List[OrchestratorMission]:
        missions = list(self._missions.values())
        if status:
            missions = [m for m in missions if m.status.value == status]
        return missions[:limit]

    def list_active_missions(self) -> List[OrchestratorMission]:
        active = {OrchestratorStatus.RUNNING.value, OrchestratorStatus.PAUSED.value, OrchestratorStatus.PENDING.value}
        return [m for m in self._missions.values() if m.status.value in active]

    async def restart_from_checkpoint(self, mission_id: str) -> Optional[OrchestratorMission]:
        mission = self._missions.get(mission_id)
        if not mission:
            return None
        checkpoint = self._recovery_mgr.get_checkpoint(mission_id)
        if not checkpoint:
            return await self.run_mission(mission_id)

        last_successful = self._recovery_mgr.get_last_successful_state(
            mission_id, mission.stage_results
        )
        if last_successful:
            mission.current_state = MissionLifecycleState(last_successful)
            mission.status = OrchestratorStatus.PENDING
            mission.error = ""
            event_pipeline.emit(
                mission_id, mission.current_state, "mission.restart", "orchestrator",
                f"Mission restarting from {last_successful}",
            )
            return await self._engine.run_mission(mission, context=checkpoint.get("context", {}))
        return await self.run_mission(mission)

    def get_artifacts(self, mission_id: str) -> List[Dict[str, Any]]:
        return [{
            "artifact_id": a.artifact_id,
            "name": a.name,
            "artifact_type": a.artifact_type,
            "source": a.source,
            "state": a.state.value,
            "created_at": a.created_at,
        } for a in artifact_manager.list_by_mission(mission_id)]

    def get_events(self, mission_id: str) -> List[Dict[str, Any]]:
        return [{
            "mission_id": e.mission_id,
            "state": e.state.value,
            "event_type": e.event_type,
            "source": e.source,
            "message": e.message,
            "timestamp": e.timestamp,
            "correlation_id": e.correlation_id,
        } for e in event_pipeline.get_events(mission_id)]

    def get_mission_summary(self, mission_id: str) -> Optional[Dict[str, Any]]:
        mission = self._missions.get(mission_id)
        if not mission:
            return None
        stage_summary = {}
        for state_str, result in mission.stage_results.items():
            stage_summary[state_str] = {
                "success": result.success,
                "error": result.error,
                "duration": result.duration_seconds,
                "runtime": result.runtime,
            }
        raw_metrics = metrics_collector.get_metrics(mission_id)
        stage_metrics = {}
        for stage_name, sm in raw_metrics.items():
            stage_metrics[stage_name] = {
                "runtime_invoked": sm.runtime_invoked,
                "connector_invoked": sm.connector_invoked,
                "duration_seconds": sm.duration_seconds,
                "success": sm.success,
                "artifacts_produced": sm.artifacts_produced,
                "errors": sm.errors,
                "decision_rationale": sm.decision_rationale,
            }
        return {
            "mission_id": mission.mission_id,
            "goal": mission.goal,
            "current_state": mission.current_state.value,
            "status": mission.status.value,
            "error": mission.error,
            "failure_category": mission.failure_category,
            "context": mission.context,
            "created_at": mission.created_at,
            "started_at": mission.started_at,
            "completed_at": mission.completed_at,
            "stages": stage_summary,
            "stage_metrics": stage_metrics,
            "artifact_count": len(artifact_manager.list_by_mission(mission_id)),
            "event_count": len(event_pipeline.get_events(mission_id)),
        }

    def health(self) -> Dict[str, Any]:
        return {
            "status": "healthy",
            "active_missions": len([m for m in self._missions.values() if m.status == OrchestratorStatus.RUNNING]),
            "total_missions": len(self._missions),
            "paused_missions": len([m for m in self._missions.values() if m.status == OrchestratorStatus.PAUSED]),
        }


orchestrator_service = AutonomousMissionOrchestrator()
