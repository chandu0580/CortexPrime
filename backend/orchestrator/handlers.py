from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Tuple
from uuid import uuid4

from backend.orchestrator.engine import OrchestrationEngine, StageHandler
from backend.orchestrator.models import MissionLifecycleState, OrchestratorMission
from backend.orchestrator.observability import metrics_collector
from backend.orchestrator.runtime_resolver import (
    get_cognitive_memory_service,
    get_connector_service,
    get_execution_service,
    get_governance_service,
    get_knowledge_service,
    get_learning_service,
    get_mission_intel_service,
)

log = logging.getLogger(__name__)


def _get_mem() -> Any:
    return get_cognitive_memory_service()


def _record_metric(
    mission_id: str,
    stage: str,
    runtime: str = "",
    connector: str = "",
    duration: float = 0.0,
    success: bool = False,
    artifacts: int = 0,
    error: str = "",
    rationale: str = "",
) -> None:
    metrics_collector.record(
        mission_id=mission_id,
        stage=stage,
        runtime_invoked=runtime,
        connector_invoked=connector,
        duration_seconds=duration,
        success=success,
        artifacts_produced=artifacts,
        error=error,
        decision_rationale=rationale,
    )


def _update_cognitive_memory(
    mission_id: str,
    state: str,
    result: Any,
    error: str = "",
) -> None:
    mem = _get_mem()
    if not mem:
        return
    try:
        ctx = mem.get_context(mission_id)
        if ctx:
            mem.update_context(mission_id, {
                "working_memory.current_phase": state,
                "working_memory.completed_steps": [state],
            })
            if error:
                mem.record_error(mission_id, source=f"stage.{state}", error=error)
            mem.add_reasoning_step(
                mission_id,
                description=f"Stage {state} completed",
                decision=str(result)[:500] if result else "",
                confidence=0.0 if error else 1.0,
                critical=error != "",
            )
            mem.add_artifact(
                mission_id,
                name=f"{state}_result",
                artifact_type="stage_result",
                data=result,
                source=f"orchestrator.{state}",
            )
    except Exception as exc:
        log.debug("Cognitive memory update failed for %s: %s", mission_id, exc)


async def handle_analyze(
    mission: OrchestratorMission,
    ctx: Dict[str, Any],
) -> Tuple[bool, Any, str]:
    start = datetime.now(timezone.utc)
    svc = get_mission_intel_service()
    if not svc:
        return False, None, "MissionIntelligenceService unavailable"
    try:
        result = svc.analyze(goal=mission.goal, context=ctx)
        _update_cognitive_memory(mission.mission_id, "mission_analyzed", result)
        dur = (datetime.now(timezone.utc) - start).total_seconds()
        _record_metric(mission.mission_id, "mission_analyzed",
                       runtime="MissionIntelligenceService", duration=dur, success=True,
                       rationale=f"Analysis completed: {result.category if hasattr(result, 'category') else 'ok'}")
        return True, result, ""
    except Exception as exc:
        dur = (datetime.now(timezone.utc) - start).total_seconds()
        _record_metric(mission.mission_id, "mission_analyzed",
                       runtime="MissionIntelligenceService", duration=dur, success=False, error=str(exc))
        return False, None, str(exc)


async def handle_plan(
    mission: OrchestratorMission,
    ctx: Dict[str, Any],
) -> Tuple[bool, Any, str]:
    start = datetime.now(timezone.utc)
    svc = get_mission_intel_service()
    if not svc:
        return False, None, "MissionIntelligenceService unavailable"
    try:
        analysis = ctx.get("mission_analyzed")
        if not analysis:
            return False, None, "No analysis available for planning"
        decompose_result = svc.decompose(analysis)
        cap_plan = svc.plan_capability(decompose_result)
        knowledge_insight = svc.plan_knowledge(analysis)
        learning_insight = svc.plan_learning(analysis, knowledge_insight)
        gov_plan = svc.plan_governance(analysis, learning_insight)
        exec_plan = svc.plan_execution(decompose_result, cap_plan, gov_plan)
        plan_data = {
            "decomposition": decompose_result,
            "capability_plan": cap_plan,
            "knowledge_insight": knowledge_insight,
            "learning_insight": learning_insight,
            "governance_plan": gov_plan,
            "execution_plan": exec_plan,
        }
        _update_cognitive_memory(mission.mission_id, "mission_planned", plan_data)
        dur = (datetime.now(timezone.utc) - start).total_seconds()
        _record_metric(mission.mission_id, "mission_planned",
                       runtime="MissionIntelligenceService", duration=dur, success=True,
                       rationale=f"Plan created: {len(decompose_result.tasks) if hasattr(decompose_result, 'tasks') else 0} tasks")
        return True, plan_data, ""
    except Exception as exc:
        dur = (datetime.now(timezone.utc) - start).total_seconds()
        _record_metric(mission.mission_id, "mission_planned",
                       runtime="MissionIntelligenceService", duration=dur, success=False, error=str(exc))
        return False, None, str(exc)


async def handle_knowledge_retrieve(
    mission: OrchestratorMission,
    ctx: Dict[str, Any],
) -> Tuple[bool, Any, str]:
    start = datetime.now(timezone.utc)
    svc = get_knowledge_service()
    if not svc:
        _record_metric(mission.mission_id, "knowledge_retrieved", duration=0, success=True,
                       rationale="Knowledge service unavailable, skipping")
        return True, {"skipped": True, "reason": "KnowledgeService unavailable"}, ""
    try:
        from backend.knowledge.models import KnowledgeQuery
        kq = KnowledgeQuery(query=mission.goal, limit=10)
        result = await svc.search(kq)
        artifacts_produced = len(result.entries) if hasattr(result, "entries") else 0
        _update_cognitive_memory(mission.mission_id, "knowledge_retrieved", {
            "entries": str([e.title[:50] for e in result.entries])[:500] if hasattr(result, "entries") else [],
            "total": result.total if hasattr(result, "total") else 0,
        })
        dur = (datetime.now(timezone.utc) - start).total_seconds()
        _record_metric(mission.mission_id, "knowledge_retrieved",
                       runtime="KnowledgeService", duration=dur, success=True,
                       artifacts=artifacts_produced,
                       rationale=f"Retrieved {artifacts_produced} knowledge entries")
        return True, result, ""
    except Exception as exc:
        dur = (datetime.now(timezone.utc) - start).total_seconds()
        _record_metric(mission.mission_id, "knowledge_retrieved",
                       runtime="KnowledgeService", duration=dur, success=False, error=str(exc))
        return False, None, str(exc)


async def handle_learning_retrieve(
    mission: OrchestratorMission,
    ctx: Dict[str, Any],
) -> Tuple[bool, Any, str]:
    start = datetime.now(timezone.utc)
    svc = get_learning_service()
    if not svc:
        _record_metric(mission.mission_id, "learning_retrieved", duration=0, success=True,
                       rationale="Learning service unavailable, skipping")
        return True, {"skipped": True, "reason": "LearningService unavailable"}, ""
    try:
        patterns = await svc.list_patterns(category="mission", min_confidence=0.3, limit=10)
        _update_cognitive_memory(mission.mission_id, "learning_retrieved", {
            "patterns": len(patterns),
            "details": str([p.name[:50] for p in patterns])[:500] if patterns else [],
        })
        dur = (datetime.now(timezone.utc) - start).total_seconds()
        _record_metric(mission.mission_id, "learning_retrieved",
                       runtime="LearningService", duration=dur, success=True,
                       artifacts=len(patterns),
                       rationale=f"Retrieved {len(patterns)} learning patterns")
        return True, {"patterns": patterns}, ""
    except Exception as exc:
        dur = (datetime.now(timezone.utc) - start).total_seconds()
        _record_metric(mission.mission_id, "learning_retrieved",
                       runtime="LearningService", duration=dur, success=False, error=str(exc))
        return False, None, str(exc)


async def handle_governance_evaluate(
    mission: OrchestratorMission,
    ctx: Dict[str, Any],
) -> Tuple[bool, Any, str]:
    start = datetime.now(timezone.utc)
    svc = get_governance_service()
    if not svc:
        _record_metric(mission.mission_id, "governance_evaluated", duration=0, success=True,
                       rationale="Governance service unavailable, skipping")
        return True, {"skipped": True, "reason": "GovernanceService unavailable"}, ""
    try:
        from backend.governance.models import DecisionRequest
        request = DecisionRequest(
            request_id=uuid4().hex[:12],
            requester=ctx.get("user_id", "orchestrator"),
            user=ctx.get("user_id", "orchestrator"),
            role=ctx.get("permissions", ["admin"])[0] if ctx.get("permissions") else "admin",
            tenant=ctx.get("tenant_id", ""),
            mission_id=mission.mission_id,
            resource_type="mission",
            resource_id=mission.mission_id,
            action="execute",
            scope="mission",
            risk_level=mission.metadata.get("risk_level", "low"),
            context={"goal": mission.goal, **ctx},
            metadata=mission.metadata,
            timestamp=datetime.now(timezone.utc),
        )
        response = await svc.evaluate_mission(request)
        if hasattr(response, "denied") and response.denied:
            _update_cognitive_memory(mission.mission_id, "governance_evaluated",
                                     {"decision": "DENIED", "reason": response.message}, error=response.message)
            dur = (datetime.now(timezone.utc) - start).total_seconds()
            _record_metric(mission.mission_id, "governance_evaluated",
                           runtime="GovernanceService", duration=dur, success=False,
                           error=response.message,
                           rationale=f"Governance denied: {response.message}")
            return False, None, f"Governance denied: {response.message}"
        _update_cognitive_memory(mission.mission_id, "governance_evaluated", {
            "decision": response.decision.value if hasattr(response.decision, 'value') else str(response.decision),
            "message": response.message,
        })
        dur = (datetime.now(timezone.utc) - start).total_seconds()
        _record_metric(mission.mission_id, "governance_evaluated",
                       runtime="GovernanceService", duration=dur, success=True,
                       rationale=f"Governance: {response.decision}")
        return True, response, ""
    except Exception as exc:
        dur = (datetime.now(timezone.utc) - start).total_seconds()
        _record_metric(mission.mission_id, "governance_evaluated",
                       runtime="GovernanceService", duration=dur, success=False, error=str(exc))
        return False, None, str(exc)


async def handle_execution_plan(
    mission: OrchestratorMission,
    ctx: Dict[str, Any],
) -> Tuple[bool, Any, str]:
    start = datetime.now(timezone.utc)
    svc = get_execution_service()
    if not svc:
        _record_metric(mission.mission_id, "execution_planned", duration=0, success=True,
                       rationale="Execution service unavailable, skipping")
        return True, {"skipped": True, "reason": "ExecutionService unavailable"}, ""
    try:
        entity = await svc.create_execution(
            command=mission.goal,
            mission_id=mission.mission_id,
            source="orchestrator",
            tags=["orchestrator", "autonomous"],
        )
        _update_cognitive_memory(mission.mission_id, "execution_planned", {
            "execution_id": entity.execution_id if hasattr(entity, 'execution_id') else str(getattr(entity, 'id', '')),
        })
        dur = (datetime.now(timezone.utc) - start).total_seconds()
        _record_metric(mission.mission_id, "execution_planned",
                       runtime="ExecutionService", duration=dur, success=True,
                       rationale=f"Execution created: {entity.execution_id}")
        return True, entity, ""
    except Exception as exc:
        dur = (datetime.now(timezone.utc) - start).total_seconds()
        _record_metric(mission.mission_id, "execution_planned",
                       runtime="ExecutionService", duration=dur, success=False, error=str(exc))
        return False, None, str(exc)


async def handle_execution_start(
    mission: OrchestratorMission,
    ctx: Dict[str, Any],
) -> Tuple[bool, Any, str]:
    start = datetime.now(timezone.utc)
    exec_svc = get_execution_service()
    conn_svc = get_connector_service()
    if not exec_svc:
        _record_metric(mission.mission_id, "execution_started", duration=0, success=True,
                       rationale="Execution service unavailable, skipping")
        return True, {"skipped": True, "reason": "ExecutionService unavailable"}, ""
    try:
        exec_id = ctx.get("execution_id", "")
        if exec_id:
            entity = await exec_svc.start_execution(exec_id, actor="orchestrator")
        else:
            entity = await exec_svc.run_execution(
                command=mission.goal,
                mission_id=mission.mission_id,
                source="orchestrator",
                timeout_seconds=300,
            )

        connector_results = []
        if conn_svc:
            connectors = await conn_svc.list_connectors()
            for conn in (connectors or [])[:3]:
                try:
                    ctype = getattr(conn, "connector_type", getattr(conn, "name", ""))
                    if ctype:
                        caps = await conn_svc.capabilities(ctype)
                        if caps:
                            result = await conn_svc.execute_capability(
                                ctype, caps[0], {"mission_id": mission.mission_id},
                                actor="orchestrator",
                            )
                            connector_results.append({"connector": ctype, "result": result})
                except Exception as conn_err:
                    connector_results.append({"connector": str(getattr(conn, "connector_type", "unknown")),
                                              "error": str(conn_err)})

        _update_cognitive_memory(mission.mission_id, "execution_started", {
            "execution": str(entity.execution_id if hasattr(entity, 'execution_id') else ''),
            "connectors": connector_results,
        })
        dur = (datetime.now(timezone.utc) - start).total_seconds()
        _record_metric(mission.mission_id, "execution_started",
                       runtime="ExecutionService", connector=str(len(connector_results)),
                       duration=dur, success=True,
                       artifacts=len(connector_results),
                       rationale=f"Execution started, {len(connector_results)} connectors invoked")
        return True, {"execution": entity, "connectors": connector_results}, ""
    except Exception as exc:
        dur = (datetime.now(timezone.utc) - start).total_seconds()
        _record_metric(mission.mission_id, "execution_started",
                       runtime="ExecutionService", duration=dur, success=False, error=str(exc))
        return False, None, str(exc)


async def handle_execution_complete(
    mission: OrchestratorMission,
    ctx: Dict[str, Any],
) -> Tuple[bool, Any, str]:
    start = datetime.now(timezone.utc)
    exec_svc = get_execution_service()
    if not exec_svc:
        _record_metric(mission.mission_id, "execution_completed", duration=0, success=True,
                       rationale="Execution service unavailable, skipping")
        return True, {"skipped": True, "reason": "ExecutionService unavailable"}, ""
    try:
        exec_id = ctx.get("execution_id", "")
        if exec_id:
            entity = await exec_svc.get_execution(exec_id)
            if entity:
                status = getattr(entity, "status", None)
                status_str = str(status.value) if hasattr(status, 'value') else str(status)
                if status_str in ("FAILED", "CANCELLED", "TIMED_OUT"):
                    _record_metric(mission.mission_id, "execution_completed",
                                   runtime="ExecutionService", duration=(datetime.now(timezone.utc)-start).total_seconds(),
                                   success=False, error=f"Execution ended with {status_str}")
                    return False, None, f"Execution ended with {status_str}"
        _update_cognitive_memory(mission.mission_id, "execution_completed", {"status": "completed"})
        dur = (datetime.now(timezone.utc) - start).total_seconds()
        _record_metric(mission.mission_id, "execution_completed",
                       runtime="ExecutionService", duration=dur, success=True,
                       rationale="Execution completed")
        return True, {"status": "completed"}, ""
    except Exception as exc:
        dur = (datetime.now(timezone.utc) - start).total_seconds()
        _record_metric(mission.mission_id, "execution_completed",
                       runtime="ExecutionService", duration=dur, success=False, error=str(exc))
        return False, None, str(exc)


async def handle_verify(
    mission: OrchestratorMission,
    ctx: Dict[str, Any],
) -> Tuple[bool, Any, str]:
    start = datetime.now(timezone.utc)
    svc = get_mission_intel_service()
    if not svc:
        _record_metric(mission.mission_id, "verification", duration=0, success=True,
                       rationale="MissionIntel service unavailable, skipping")
        return True, {"skipped": True, "reason": "MissionIntelligenceService unavailable"}, ""
    try:
        decomposition = ctx.get("decomposition")
        execution_plan = ctx.get("execution_plan")
        if not decomposition or not execution_plan:
            _record_metric(mission.mission_id, "verification", duration=0, success=True,
                           rationale="No plan data to verify, skipping")
            return True, {"skipped": True, "reason": "No plan data"}, ""
        result = svc.verify(decomposition, execution_plan)
        _update_cognitive_memory(mission.mission_id, "verification", result)
        dur = (datetime.now(timezone.utc) - start).total_seconds()
        _record_metric(mission.mission_id, "verification",
                       runtime="MissionIntelligenceService", duration=dur, success=True,
                       rationale="Verification completed")
        return True, result, ""
    except Exception as exc:
        dur = (datetime.now(timezone.utc) - start).total_seconds()
        _record_metric(mission.mission_id, "verification",
                       runtime="MissionIntelligenceService", duration=dur, success=False, error=str(exc))
        return False, None, str(exc)


async def handle_knowledge_update(
    mission: OrchestratorMission,
    ctx: Dict[str, Any],
) -> Tuple[bool, Any, str]:
    start = datetime.now(timezone.utc)
    svc = get_knowledge_service()
    if not svc:
        _record_metric(mission.mission_id, "knowledge_updated", duration=0, success=True,
                       rationale="Knowledge service unavailable, skipping")
        return True, {"skipped": True, "reason": "KnowledgeService unavailable"}, ""
    try:
        result = await svc.index_mission(
            mission_id=mission.mission_id,
            title=mission.goal,
            objective=mission.metadata.get("objective", ""),
            status=mission.status.value,
            owner=ctx.get("user_id", "orchestrator"),
            result=mission.error or "completed",
            metadata={"stages": str(list(mission.stage_results.keys()))[:500]},
        )
        _update_cognitive_memory(mission.mission_id, "knowledge_updated", result)
        dur = (datetime.now(timezone.utc) - start).total_seconds()
        _record_metric(mission.mission_id, "knowledge_updated",
                       runtime="KnowledgeService", duration=dur, success=True,
                       rationale="Mission indexed to knowledge")
        return True, result, ""
    except Exception as exc:
        dur = (datetime.now(timezone.utc) - start).total_seconds()
        _record_metric(mission.mission_id, "knowledge_updated",
                       runtime="KnowledgeService", duration=dur, success=False, error=str(exc))
        return False, None, str(exc)


async def handle_learning_update(
    mission: OrchestratorMission,
    ctx: Dict[str, Any],
) -> Tuple[bool, Any, str]:
    start = datetime.now(timezone.utc)
    svc = get_learning_service()
    if not svc:
        _record_metric(mission.mission_id, "learning_updated", duration=0, success=True,
                       rationale="Learning service unavailable, skipping")
        return True, {"skipped": True, "reason": "LearningService unavailable"}, ""
    try:
        result = await svc.analyze_mission({
            "mission_id": mission.mission_id,
            "goal": mission.goal,
            "status": mission.status.value,
            "error": mission.error,
            "stage_count": len(mission.stage_results),
            "successful_stages": sum(1 for s in mission.stage_results.values() if s.success),
        })
        _update_cognitive_memory(mission.mission_id, "learning_updated", result)
        dur = (datetime.now(timezone.utc) - start).total_seconds()
        _record_metric(mission.mission_id, "learning_updated",
                       runtime="LearningService", duration=dur, success=True,
                       rationale="Mission analyzed for learning")
        return True, result, ""
    except Exception as exc:
        dur = (datetime.now(timezone.utc) - start).total_seconds()
        _record_metric(mission.mission_id, "learning_updated",
                       runtime="LearningService", duration=dur, success=False, error=str(exc))
        return False, None, str(exc)


_RUNTIME_HANDLERS: list[tuple[MissionLifecycleState, StageHandler, float]] = [
    (MissionLifecycleState.ANALYZED, handle_analyze, 120),
    (MissionLifecycleState.PLANNED, handle_plan, 120),
    (MissionLifecycleState.KNOWLEDGE_RETRIEVED, handle_knowledge_retrieve, 60),
    (MissionLifecycleState.LEARNING_RETRIEVED, handle_learning_retrieve, 60),
    (MissionLifecycleState.GOVERNANCE_EVALUATED, handle_governance_evaluate, 60),
    (MissionLifecycleState.EXECUTION_PLANNED, handle_execution_plan, 60),
    (MissionLifecycleState.EXECUTION_STARTED, handle_execution_start, 300),
    (MissionLifecycleState.EXECUTION_COMPLETED, handle_execution_complete, 120),
    (MissionLifecycleState.VERIFIED, handle_verify, 60),
    (MissionLifecycleState.KNOWLEDGE_UPDATED, handle_knowledge_update, 60),
    (MissionLifecycleState.LEARNING_UPDATED, handle_learning_update, 60),
]


def wire_runtime_handlers(engine: OrchestrationEngine, only_missing: bool = False) -> None:
    count = 0
    for state, handler, timeout in _RUNTIME_HANDLERS:
        if only_missing and state.value in engine._stage_handlers:
            continue
        engine.register_stage(state, handler, timeout_seconds=timeout)
        count += 1
    log.info("Runtime handlers wired: %d stages (%s)", count, "missing only" if only_missing else "all")
