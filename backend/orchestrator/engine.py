from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple
from uuid import uuid4

from backend.orchestrator.artifact_manager import artifact_manager
from backend.orchestrator.event_pipeline import event_pipeline
from backend.orchestrator.models import (
    ExecutionMode,
    MissionLifecycleState,
    OrchestratorMission,
    OrchestratorStatus,
    StageResult,
)
from backend.orchestrator.recovery import FailureClassifier, RecoveryManager, recovery_manager
from backend.orchestrator.state_machine import MissionStateMachine

log = logging.getLogger(__name__)


StageHandler = Callable[[OrchestratorMission, Dict[str, Any]], Tuple[bool, Any, str]]

_STAGE_RUNTIME_MAP: dict[str, str] = {
    "mission_analyzed": "MissionIntelligenceService",
    "mission_planned": "MissionIntelligenceService",
    "knowledge_retrieved": "KnowledgeService",
    "learning_retrieved": "LearningService",
    "governance_evaluated": "GovernanceService",
    "execution_planned": "ExecutionService",
    "execution_started": "ExecutionService",
    "execution_completed": "ExecutionService",
    "verification": "MissionIntelligenceService",
    "knowledge_updated": "KnowledgeService",
    "learning_updated": "LearningService",
}


class OrchestrationEngine:
    def __init__(
        self,
        recovery_mgr: Optional[RecoveryManager] = None,
    ) -> None:
        self._stage_handlers: Dict[str, StageHandler] = {}
        self._stage_mode: Dict[str, ExecutionMode] = {}
        self._stage_timeouts: Dict[str, float] = {}
        self._conditional_branches: Dict[str, Callable[[OrchestratorMission, Dict[str, Any]], str]] = {}
        self._recovery_mgr = recovery_mgr or recovery_manager
        self._running_missions: Dict[str, OrchestratorMission] = {}
        self._paused_missions: Dict[str, asyncio.Event] = {}
        self._publish_event = event_pipeline.emit
        self._handlers_wired: bool = False

    def wire_runtime_handlers(self) -> None:
        if self._handlers_wired:
            return
        try:
            from backend.orchestrator.handlers import wire_runtime_handlers as _wire
            _wire(self)
            self._handlers_wired = True
            log.info("Runtime handlers wired into engine")
        except Exception as exc:
            log.warning("Failed to wire runtime handlers: %s", exc)

    def _ensure_runtime_handlers(self) -> None:
        if self._handlers_wired:
            return
        if self._stage_handlers:
            return
        try:
            from backend.orchestrator.handlers import wire_runtime_handlers as _wire
            _wire(self)
            self._handlers_wired = True
        except Exception as exc:
            log.debug("Runtime handler wiring deferred: %s", exc)

    def register_stage(
        self,
        state: MissionLifecycleState,
        handler: StageHandler,
        mode: ExecutionMode = ExecutionMode.SEQUENTIAL,
        timeout_seconds: float = 0.0,
    ) -> None:
        self._stage_handlers[state.value] = handler
        self._stage_mode[state.value] = mode
        if timeout_seconds > 0:
            self._stage_timeouts[state.value] = timeout_seconds

    def register_conditional_branch(
        self,
        state: MissionLifecycleState,
        resolver: Callable[[OrchestratorMission, Dict[str, Any]], str],
    ) -> None:
        self._conditional_branches[state.value] = resolver

    def _get_next_sequential_state(self, current: str) -> List[str]:
        next_s = MissionStateMachine.next_state(current)
        if next_s == current:
            return []
        return [next_s]

    def _check_paused(self, mission_id: str) -> bool:
        return mission_id in self._paused_missions

    async def _wait_if_paused(self, mission_id: str) -> None:
        while mission_id in self._paused_missions:
            event = self._paused_missions.get(mission_id)
            if event:
                await event.wait()

    def _should_archive_on_failure(self, state: str) -> bool:
        terminal_failures = {
            MissionLifecycleState.ARCHIVED.value,
        }
        return state in terminal_failures

    async def _execute_single_stage(
        self,
        mission: OrchestratorMission,
        state: MissionLifecycleState,
        context: Dict[str, Any],
    ) -> StageResult:
        start = datetime.now(timezone.utc)
        runtime = _STAGE_RUNTIME_MAP.get(state.value, "")
        handler = self._stage_handlers.get(state.value)
        if not handler:
            stage_result = StageResult(
                state=state,
                success=True,
                result=None,
                duration_seconds=0.0,
                runtime=runtime,
                metadata={"skipped": True, "reason": "No handler registered"},
            )
            mission.set_state(state)
            mission.stage_results[state.value] = stage_result
            return stage_result

        timeout = self._stage_timeouts.get(state.value, 0.0)
        try:
            if timeout > 0:
                result = await asyncio.wait_for(handler(mission, context), timeout=timeout)
            else:
                result = await handler(mission, context)

            success, data, error = result if isinstance(result, tuple) and len(result) == 3 else (True, result, "")
            duration = (datetime.now(timezone.utc) - start).total_seconds()

            stage_result = StageResult(
                state=state,
                success=success,
                result=data,
                error=error,
                duration_seconds=round(duration, 3),
                runtime=runtime,
            )

            if success:
                mission.set_state(state)
                self._recovery_mgr.save_checkpoint(mission.mission_id, state, {"result": data, **context})
            else:
                mission.error = error

            mission.stage_results[state.value] = stage_result
            return stage_result

        except asyncio.TimeoutError:
            duration = (datetime.now(timezone.utc) - start).total_seconds()
            stage_result = StageResult(
                state=state,
                success=False,
                error=f"Stage timed out after {timeout}s",
                duration_seconds=round(duration, 3),
                runtime=runtime,
            )
            mission.error = f"Timeout in {state.value}"
            mission.stage_results[state.value] = stage_result
            return stage_result

        except Exception as exc:
            duration = (datetime.now(timezone.utc) - start).total_seconds()
            stage_result = StageResult(
                state=state,
                success=False,
                error=str(exc),
                duration_seconds=round(duration, 3),
                runtime=runtime,
            )
            mission.error = str(exc)
            mission.stage_results[state.value] = stage_result
            return stage_result

    async def _handle_stage_failure(
        self,
        mission: OrchestratorMission,
        state: MissionLifecycleState,
        context: Dict[str, Any],
    ) -> OrchestratorStatus:
        stage_result = mission.stage_results.get(state.value)
        runtime = stage_result.runtime if stage_result else _STAGE_RUNTIME_MAP.get(state.value, "")
        category, strategy = FailureClassifier.classify(
            mission.error, state.value, runtime=runtime, metadata=mission.metadata
        )
        mission.failure_category = category.value

        if strategy.value == "retry" and self._recovery_mgr.should_retry(mission.mission_id, state.value, 1):
            self._recovery_mgr.record_retry(mission.mission_id, state.value)
            self._publish_event(
                mission.mission_id, state, "stage.retry", "orchestrator",
                f"Retrying {state.value} (retry #{self._recovery_mgr.get_checkpoint(mission.mission_id).get('retry_count', {}).get(state.value, 0)})",
                metadata={"failure_category": category.value},
            )
            result = await self._execute_single_stage(mission, state, context)
            if result.success:
                return OrchestratorStatus.RUNNING

        if strategy.value == "compensate":
            self._recovery_mgr.execute_compensation(mission.mission_id, state, context)
            self._publish_event(
                mission.mission_id, state, "stage.compensated", "orchestrator",
                f"Compensation executed for {state.value}",
                metadata={"failure_category": category.value},
            )

        if strategy.value == "skip":
            self._publish_event(
                mission.mission_id, state, "stage.skipped", "orchestrator",
                f"Skipping {state.value}",
                metadata={"failure_category": category.value},
            )
            return OrchestratorStatus.RUNNING

        self._publish_event(
            mission.mission_id, state, "stage.failed", "orchestrator",
            f"Stage {state.value} failed: {mission.error}",
            metadata={"failure_category": category.value, "error": mission.error},
        )
        return OrchestratorStatus.FAILED

    async def run_mission(
        self,
        mission: OrchestratorMission,
        context: Optional[Dict[str, Any]] = None,
    ) -> OrchestratorMission:
        if mission.status not in (OrchestratorStatus.PENDING, OrchestratorStatus.FAILED):
            return mission

        self._ensure_runtime_handlers()
        mission.status = OrchestratorStatus.RUNNING
        mission.started_at = datetime.now(timezone.utc).isoformat()
        ctx = context or {}
        self._running_missions[mission.mission_id] = mission

        self._publish_event(
            mission.mission_id, mission.current_state, "mission.start", "orchestrator",
            f"Mission {mission.mission_id} started: {mission.goal}",
        )

        while mission.current_state != MissionLifecycleState.ARCHIVED.value:
            if self._check_paused(mission.mission_id):
                await self._wait_if_paused(mission.mission_id)

            if mission.status == OrchestratorStatus.CANCELLED.value:
                break

            current_state = MissionLifecycleState(mission.current_state)

            mode = self._stage_mode.get(current_state.value, ExecutionMode.SEQUENTIAL)

            resolved_state = current_state.value
            if current_state.value in self._conditional_branches:
                resolver = self._conditional_branches[current_state.value]
                resolved_state = resolver(mission, ctx)
                if resolved_state != current_state.value:
                    current_state = MissionLifecycleState(resolved_state)

            self._publish_event(
                mission.mission_id, current_state, "stage.start", "orchestrator",
                f"Starting stage {current_state.value}",
            )

            stage_result = await self._execute_single_stage(mission, current_state, ctx)

            if stage_result.success:
                artifact_manager.add(
                    mission.mission_id,
                    f"{current_state.value}_result",
                    "stage_result",
                    stage_result.result,
                    source="orchestrator",
                    state=current_state,
                )

                self._publish_event(
                    mission.mission_id, current_state, "stage.complete", "orchestrator",
                    f"Stage {current_state.value} completed in {stage_result.duration_seconds}s",
                    metadata={"duration": stage_result.duration_seconds},
                )

                next_state_str = MissionStateMachine.next_state(mission.current_state)
                if next_state_str != mission.current_state:
                    mission.set_state(MissionLifecycleState(next_state_str))
            else:
                outcome = await self._handle_stage_failure(mission, current_state, ctx)
                if outcome == OrchestratorStatus.FAILED:
                    mission.status = OrchestratorStatus.FAILED
                    break
                elif outcome == OrchestratorStatus.CANCELLED:
                    break
                next_state_str = MissionStateMachine.next_state(mission.current_state)
                if next_state_str != mission.current_state:
                    mission.set_state(MissionLifecycleState(next_state_str))

        if mission.status == OrchestratorStatus.RUNNING:
            mission.status = OrchestratorStatus.COMPLETED
            mission.completed_at = datetime.now(timezone.utc).isoformat()
            mission.set_state(MissionLifecycleState.ARCHIVED)
            self._publish_event(
                mission.mission_id, MissionLifecycleState.ARCHIVED, "mission.complete", "orchestrator",
                f"Mission {mission.mission_id} completed",
            )

        self._running_missions.pop(mission.mission_id, None)
        return mission

    async def pause_mission(self, mission_id: str) -> bool:
        if mission_id not in self._running_missions:
            return False
        self._paused_missions[mission_id] = asyncio.Event()
        mission = self._running_missions[mission_id]
        mission.status = OrchestratorStatus.PAUSED
        self._publish_event(
            mission.mission_id, mission.current_state, "mission.pause", "orchestrator",
            "Mission paused",
        )
        return True

    async def resume_mission(self, mission_id: str) -> bool:
        event = self._paused_missions.pop(mission_id, None)
        if event is None:
            return False
        event.set()
        mission = self._running_missions.get(mission_id)
        if mission:
            mission.status = OrchestratorStatus.RUNNING
            self._publish_event(
                mission.mission_id, mission.current_state, "mission.resume", "orchestrator",
                "Mission resumed",
            )
        return True

    async def cancel_mission(self, mission_id: str) -> bool:
        mission = self._running_missions.get(mission_id)
        if not mission:
            return False
        mission.status = OrchestratorStatus.CANCELLED
        mission.completed_at = datetime.now(timezone.utc).isoformat()
        self._publish_event(
            mission.mission_id, mission.current_state, "mission.cancel", "orchestrator",
            "Mission cancelled",
        )

        event = self._paused_missions.pop(mission_id, None)
        if event:
            event.set()
        self._running_missions.pop(mission_id, None)
        return True


engine = OrchestrationEngine()
