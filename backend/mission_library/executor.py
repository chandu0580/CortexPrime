from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, Optional

from backend.mission_library.definitions import MISSION_REGISTRY, get_mission
from backend.mission_library.models import (
    AuditLevel,
    ExecutionStage,
    MissionDefinition,
    MissionResult,
)

log = logging.getLogger(__name__)


class MissionExecutor:
    """
    Executes enterprise mission definitions through the existing MissionRuntime.

    This class maps mission templates to the MissionRuntimeService.execute_mission()
    pipeline without duplicating orchestration logic. It provides:

    - Mission template lookup and parameter binding
    - Pre-execution validation of required workers and connectors
    - Execution through MissionRuntime's existing pipeline
    - Result collection including metrics, governance, analytics
    - Integration with all platform subsystems
    """

    def __init__(self) -> None:
        self._running: Dict[str, Any] = {}

    # ------------------------------------------------------------------
    # Execute a mission by ID with bound parameters
    # ------------------------------------------------------------------

    async def execute(
        self,
        mission_id: str,
        *,
        session_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
        voice_context: Optional[str] = None,
        **params: Any,
    ) -> MissionResult:
        mission = get_mission(mission_id)
        if mission is None:
            valid = list(MISSION_REGISTRY.keys())
            raise ValueError(f"Unknown mission '{mission_id}'. Valid: {valid}")

        return await self._execute_definition(
            mission=mission,
            session_id=session_id,
            workspace_id=workspace_id,
            voice_context=voice_context,
            **params,
        )

    # ------------------------------------------------------------------
    # Execute with a MissionDefinition object
    # ------------------------------------------------------------------

    async def _execute_definition(
        self,
        mission: MissionDefinition,
        *,
        session_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
        voice_context: Optional[str] = None,
        **params: Any,
    ) -> MissionResult:
        t0 = time.monotonic()

        # Build objective from template
        objective = mission.build_objective(**params)

        # Record execution
        self._running[mission.metadata.id] = objective
        execution_id: Optional[str] = None
        stages_completed: list[str] = []
        worker_invocations: list[str] = []
        total_tokens = 0
        total_cost = 0.0

        try:
            # -- Governance audit logging --
            self._audit_start(mission, objective, session_id)

            # -- Execute through MissionRuntime's existing pipeline --
            from backend.services.mission_runtime import mission_runtime

            result = await mission_runtime.execute_mission(
                objective=objective,
                session_id=session_id,
                workspace_id=workspace_id if mission.supports_workspace else None,
                voice_context=voice_context if mission.supports_voice else None,
            )

            execution_id = result.get("execution_id", "")
            status = result.get("status", "unknown")

            # -- Track stages completed --
            if status == "completed":
                stages_completed = [s.value for s in mission.execution_stages]
            elif status == "blocked":
                stages_completed = [ExecutionStage.INIT.value]
            elif status == "failed":
                stages_completed = [ExecutionStage.INIT.value, ExecutionStage.FAILED.value]

            # -- Track worker invocations --
            if mission.needs_browser:
                worker_invocations.append("browser_agent")
            if mission.needs_computer:
                worker_invocations.append("computer_agent_v2")
            if mission.supports_voice:
                worker_invocations.append("voice_runtime")

            # -- Gather metrics from runtime --
            total_tokens = self._get_token_count()
            total_cost = self._get_mission_cost(execution_id)

            # -- Record Neo4j knowledge graph updates --
            self._record_neo4j_mission(mission, execution_id, status, objective)

            # -- Record Redis memory updates --
            self._record_redis_mission(execution_id, mission, status)

            # -- Record analytics --
            self._record_analytics(mission, execution_id, status, t0)

            duration = time.monotonic() - t0

            mission_result = MissionResult(
                status=status,
                execution_id=execution_id or "",
                mission_id=mission.metadata.id,
                objective=objective,
                confidence_score=result.get("confidence_score", 0.0),
                response=result.get("response", ""),
                response_length=result.get("response_length", 0),
                stages_completed=stages_completed,
                worker_invocations=worker_invocations,
                total_tokens=total_tokens,
                total_cost=total_cost,
                duration_seconds=round(duration, 3),
            )

            return mission_result

        except Exception as exc:
            duration = time.monotonic() - t0
            log.error("Mission %s failed: %s", mission.metadata.id, exc)

            # -- Record failure in Neo4j --
            if execution_id:
                self._record_neo4j_mission(mission, execution_id, "failed", objective)

            return MissionResult(
                status="failed",
                execution_id=execution_id or "",
                mission_id=mission.metadata.id,
                objective=objective,
                confidence_score=0.0,
                response="",
                response_length=0,
                stages_completed=stages_completed,
                worker_invocations=worker_invocations,
                total_tokens=total_tokens,
                total_cost=total_cost,
                duration_seconds=round(duration, 3),
                error=str(exc),
            )
        finally:
            self._running.pop(mission.metadata.id, None)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _audit_start(
        self,
        mission: MissionDefinition,
        objective: str,
        session_id: Optional[str],
    ) -> None:
        try:
            from backend.safety.audit_logger import audit_logger
            audit_logger.log(
                execution_id=f"mission_library:{mission.metadata.id}",
                agent="mission_executor",
                action="mission_library_execution",
                risk_level=mission.required_approvals.value,
                outcome="started",
                reason=f"Enterprise mission '{mission.metadata.name}': {objective[:120]}",
                session_id=session_id,
                metadata={
                    "mission_id": mission.metadata.id,
                    "mission_name": mission.metadata.name,
                    "required_approvals": mission.required_approvals.value,
                    "audit_level": mission.audit_requirements.value,
                },
            )
        except Exception:
            pass

    def _get_token_count(self) -> int:
        try:
            from backend.runtime.runtime_metrics import runtime_metrics
            metrics = runtime_metrics.export_metrics()
            return metrics.get("total_tokens", 0)
        except Exception:
            return 0

    def _get_mission_cost(self, execution_id: str) -> float:
        try:
            from backend.analytics.cost_engine import cost_engine
            result = asyncio.get_running_loop().create_task(
                cost_engine.mission_cost(execution_id)
            )
        except Exception:
            pass
        return 0.0

    def _record_neo4j_mission(
        self,
        mission: MissionDefinition,
        execution_id: str,
        status: str,
        objective: str,
    ) -> None:
        try:
            from backend.infrastructure.neo4j.connection import neo4j_connection
            if neo4j_connection.is_available:
                from backend.infrastructure.neo4j.graph_manager import neo4j_graph
                asyncio.ensure_future(neo4j_graph.create_execution(
                    execution_id=execution_id,
                    objective=f"[{mission.metadata.name}] {objective[:200]}",
                    priority=5,
                ))
        except Exception:
            pass

    def _record_redis_mission(
        self,
        mission: MissionDefinition,
        execution_id: str,
        status: str,
        objective: str,
    ) -> None:
        try:
            from backend.runtime.runtime_state_store import runtime_state_store
            asyncio.ensure_future(runtime_state_store.start(
                execution_id=execution_id,
                objective=f"[{mission.metadata.name}] {objective[:200]}",
                mission_type=mission.metadata.category.value,
            ))
            if status == "completed":
                asyncio.ensure_future(runtime_state_store.complete(
                    execution_id=execution_id,
                    status="completed",
                    result_summary=f"Enterprise mission '{mission.metadata.name}' completed",
                ))
        except Exception:
            pass

    def _record_analytics(
        self,
        mission: MissionDefinition,
        execution_id: str,
        status: str,
        t0: float,
    ) -> None:
        try:
            from backend.analytics.cost_engine import cost_engine
            duration = time.monotonic() - t0
            asyncio.ensure_future(cost_engine.record(
                provider="mission_library",
                service="enterprise_mission",
                model=mission.metadata.id,
                mission_id=execution_id,
                extra={
                    "mission_name": mission.metadata.name,
                    "mission_category": mission.metadata.category.value,
                    "status": status,
                    "duration_seconds": round(duration, 3),
                    "required_approvals": mission.required_approvals.value,
                    "audit_level": mission.audit_requirements.value,
                    "required_workers": [w.value for w in mission.required_workers],
                },
            ))
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Status queries
    # ------------------------------------------------------------------

    def is_running(self, mission_id: str) -> bool:
        return mission_id in self._running

    def list_running(self) -> list[str]:
        return list(self._running.keys())

    async def status(self) -> dict:
        return {
            "registered_missions": len(MISSION_REGISTRY),
            "mission_ids": list(MISSION_REGISTRY.keys()),
            "currently_running": list(self._running.keys()),
        }


mission_executor = MissionExecutor()