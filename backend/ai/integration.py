from __future__ import annotations

import logging
import time
import uuid
from concurrent.futures import Future
from typing import Any, Callable, Optional

from backend.ai.context import ContextPropagator, RuntimeContext
from backend.ai.models import PlanStep, RuntimeTarget
from backend.ai.result import RuntimeResult
from backend.core.dependency_container import container

log = logging.getLogger(__name__)

RuntimeHandler = Callable[[PlanStep, RuntimeContext], "Future[RuntimeResult]"]


class RuntimeIntegrationFactory:
    def __init__(self, context_propagator: Optional[ContextPropagator] = None) -> None:
        self._propagator = context_propagator or ContextPropagator()
        self._handlers: dict[RuntimeTarget, RuntimeHandler] = {}
        self._register_all()

    def _register_all(self) -> None:
        self._handlers[RuntimeTarget.IDENTITY] = self._identity_handler
        self._handlers[RuntimeTarget.MISSION] = self._mission_handler
        self._handlers[RuntimeTarget.GOVERNANCE] = self._governance_handler
        self._handlers[RuntimeTarget.KNOWLEDGE] = self._knowledge_handler
        self._handlers[RuntimeTarget.LEARNING] = self._learning_handler
        self._handlers[RuntimeTarget.EXECUTION] = self._execution_handler
        self._handlers[RuntimeTarget.CONNECTOR] = self._connector_handler
        self._handlers[RuntimeTarget.AI] = self._ai_handler

    def get_handler(self, target: RuntimeTarget) -> Optional[RuntimeHandler]:
        return self._handlers.get(target)

    def has_handler(self, target: RuntimeTarget) -> bool:
        return target in self._handlers

    # ------------------------------------------------------------------
    # Identity Runtime integration
    # ------------------------------------------------------------------

    async def _identity_handler(self, step: PlanStep, ctx: RuntimeContext) -> RuntimeResult:
        start = time.monotonic()
        action = step.action
        params = ctx.enrich_step_params(step)
        try:
            session_runtime = container.resolve("identity_session_runtime")
        except (KeyError, Exception):
            log.warning("Identity session runtime not available, using default")
            return RuntimeResult(
                runtime=RuntimeTarget.IDENTITY,
                step_id=step.step_id,
                status="success",
                data={"action": action, "note": "identity runtime unavailable, returning default"},
                duration_ms=(time.monotonic() - start) * 1000,
                correlation_id=ctx.correlation_id,
            )
        try:
            if action == "validate_session" and params.get("session_id"):
                is_valid = session_runtime.validate_session(params["session_id"])
                result = RuntimeResult(
                    runtime=RuntimeTarget.IDENTITY,
                    step_id=step.step_id,
                    status="success" if is_valid else "failed",
                    data={"session_valid": is_valid, "session_id": params["session_id"]},
                    duration_ms=(time.monotonic() - start) * 1000,
                    correlation_id=ctx.correlation_id,
                )
            elif action == "get_session" and params.get("session_id"):
                session = session_runtime.get_session(params["session_id"])
                result = RuntimeResult(
                    runtime=RuntimeTarget.IDENTITY,
                    step_id=step.step_id,
                    status="success" if session else "failed",
                    data={"session": _to_dict(session) if session else None},
                    duration_ms=(time.monotonic() - start) * 1000,
                    correlation_id=ctx.correlation_id,
                )
            else:
                session_id = params.get("session_id") or ctx.session_id
                is_valid = session_runtime.validate_session(session_id) if session_id else True
                result = RuntimeResult(
                    runtime=RuntimeTarget.IDENTITY,
                    step_id=step.step_id,
                    status="success",
                    data={"session_valid": is_valid, "session_id": session_id},
                    duration_ms=(time.monotonic() - start) * 1000,
                    correlation_id=ctx.correlation_id,
                )
            return result
        except Exception as exc:
            log.warning("Identity handler error: %s", exc)
            return RuntimeResult(
                runtime=RuntimeTarget.IDENTITY,
                step_id=step.step_id,
                status="failed",
                error=str(exc),
                duration_ms=(time.monotonic() - start) * 1000,
                correlation_id=ctx.correlation_id,
            )

    # ------------------------------------------------------------------
    # Mission Runtime integration
    # ------------------------------------------------------------------

    async def _mission_handler(self, step: PlanStep, ctx: RuntimeContext) -> RuntimeResult:
        start = time.monotonic()
        action = step.action
        params = ctx.enrich_step_params(step)
        try:
            mission_service = container.resolve("mission_runtime_service")
        except (KeyError, Exception):
            try:
                mission_service = container.resolve("mission_service")
            except (KeyError, Exception):
                log.warning("Mission service not available")
                return RuntimeResult(
                    runtime=RuntimeTarget.MISSION,
                    step_id=step.step_id,
                    status="success",
                    data={"action": action, "note": "mission runtime unavailable"},
                    duration_ms=(time.monotonic() - start) * 1000,
                    correlation_id=ctx.correlation_id,
                )
        try:
            if action == "create_mission":
                title = params.get("prompt", "AI-generated mission")[:100]
                objective = params.get("prompt", "")
                entity = mission_service.create_mission(title=title, objective=objective)
                result = RuntimeResult(
                    runtime=RuntimeTarget.MISSION,
                    step_id=step.step_id,
                    status="success",
                    data={"mission": _to_dict(entity) if entity else {}, "action": action},
                    duration_ms=(time.monotonic() - start) * 1000,
                    correlation_id=ctx.correlation_id,
                )
            elif action in ("list_missions", "list_mission_history"):
                missions = mission_service.list_missions(limit=20)
                result = RuntimeResult(
                    runtime=RuntimeTarget.MISSION,
                    step_id=step.step_id,
                    status="success",
                    data={"missions": [_to_dict(m) for m in missions], "count": len(missions)},
                    duration_ms=(time.monotonic() - start) * 1000,
                    correlation_id=ctx.correlation_id,
                )
            elif action == "get_mission":
                mission_id = params.get("mission_id") or ctx.mission_id
                entity = mission_service.get_mission(uuid.UUID(mission_id)) if mission_id else None
                result = RuntimeResult(
                    runtime=RuntimeTarget.MISSION,
                    step_id=step.step_id,
                    status="success" if entity else "failed",
                    data={"mission": _to_dict(entity) if entity else None},
                    duration_ms=(time.monotonic() - start) * 1000,
                    correlation_id=ctx.correlation_id,
                )
            else:
                missions = mission_service.list_missions(limit=5)
                result = RuntimeResult(
                    runtime=RuntimeTarget.MISSION,
                    step_id=step.step_id,
                    status="success",
                    data={"missions": [_to_dict(m) for m in missions], "action": action},
                    duration_ms=(time.monotonic() - start) * 1000,
                    correlation_id=ctx.correlation_id,
                )
            return result
        except Exception as exc:
            log.warning("Mission handler error: %s", exc)
            return RuntimeResult(
                runtime=RuntimeTarget.MISSION,
                step_id=step.step_id,
                status="failed",
                error=str(exc),
                duration_ms=(time.monotonic() - start) * 1000,
                correlation_id=ctx.correlation_id,
            )

    # ------------------------------------------------------------------
    # Governance Runtime integration
    # ------------------------------------------------------------------

    async def _governance_handler(self, step: PlanStep, ctx: RuntimeContext) -> RuntimeResult:
        start = time.monotonic()
        action = step.action
        params = ctx.enrich_step_params(step)
        try:
            governance_service = container.resolve("governance_service")
        except (KeyError, Exception):
            log.warning("Governance service not available")
            return RuntimeResult(
                runtime=RuntimeTarget.GOVERNANCE,
                step_id=step.step_id,
                status="success",
                data={"action": action, "note": "governance runtime unavailable"},
                duration_ms=(time.monotonic() - start) * 1000,
                correlation_id=ctx.correlation_id,
            )
        try:
            from backend.governance.service import DecisionRequest
            request = DecisionRequest(
                action=action,
                resource_type=f"ai_{action}",
                resource_id=params.get("step_id", ""),
                context=params,
                actor=ctx.user_id or "ai_runtime",
            )
            response = governance_service.evaluate(request)
            result = RuntimeResult(
                runtime=RuntimeTarget.GOVERNANCE,
                step_id=step.step_id,
                status="success" if response.allowed else "failed",
                data={
                    "allowed": response.allowed,
                    "decision": response.decision,
                    "reason": response.reason,
                    "action": action,
                },
                duration_ms=(time.monotonic() - start) * 1000,
                correlation_id=ctx.correlation_id,
            )
            if not response.allowed:
                result.error = response.reason or "Policy denied"
            return result
        except Exception as exc:
            log.warning("Governance handler error: %s", exc)
            return RuntimeResult(
                runtime=RuntimeTarget.GOVERNANCE,
                step_id=step.step_id,
                status="failed",
                error=str(exc),
                duration_ms=(time.monotonic() - start) * 1000,
                correlation_id=ctx.correlation_id,
            )

    # ------------------------------------------------------------------
    # Knowledge Runtime integration
    # ------------------------------------------------------------------

    async def _knowledge_handler(self, step: PlanStep, ctx: RuntimeContext) -> RuntimeResult:
        start = time.monotonic()
        action = step.action
        params = ctx.enrich_step_params(step)
        try:
            knowledge_service = container.resolve("knowledge_service")
        except (KeyError, Exception):
            log.warning("Knowledge service not available")
            return RuntimeResult(
                runtime=RuntimeTarget.KNOWLEDGE,
                step_id=step.step_id,
                status="success",
                data={"action": action, "note": "knowledge runtime unavailable"},
                duration_ms=(time.monotonic() - start) * 1000,
                correlation_id=ctx.correlation_id,
            )
        try:
            from backend.knowledge.models import KnowledgeQuery
            query_text = params.get("prompt", params.get("query", ""))
            kq = KnowledgeQuery(query=query_text, limit=10)
            search_result = knowledge_service.search(kq)
            entries = []
            if hasattr(search_result, "entries"):
                entries = [_to_dict(e) for e in search_result.entries]
            elif hasattr(search_result, "results"):
                entries = [_to_dict(e) for e in search_result.results]
            result = RuntimeResult(
                runtime=RuntimeTarget.KNOWLEDGE,
                step_id=step.step_id,
                status="success",
                data={"entries": entries, "count": len(entries), "query": query_text},
                duration_ms=(time.monotonic() - start) * 1000,
                correlation_id=ctx.correlation_id,
            )
            return result
        except Exception as exc:
            log.warning("Knowledge handler error: %s", exc)
            return RuntimeResult(
                runtime=RuntimeTarget.KNOWLEDGE,
                step_id=step.step_id,
                status="failed",
                error=str(exc),
                duration_ms=(time.monotonic() - start) * 1000,
                correlation_id=ctx.correlation_id,
            )

    # ------------------------------------------------------------------
    # Learning Runtime integration
    # ------------------------------------------------------------------

    async def _learning_handler(self, step: PlanStep, ctx: RuntimeContext) -> RuntimeResult:
        start = time.monotonic()
        action = step.action
        params = ctx.enrich_step_params(step)
        try:
            learning_service = container.resolve("learning_service")
        except (KeyError, Exception):
            log.warning("Learning service not available")
            return RuntimeResult(
                runtime=RuntimeTarget.LEARNING,
                step_id=step.step_id,
                status="success",
                data={"action": action, "note": "learning runtime unavailable"},
                duration_ms=(time.monotonic() - start) * 1000,
                correlation_id=ctx.correlation_id,
            )
        try:
            if action == "get_pattern_insights":
                patterns = learning_service.list_patterns(limit=10)
                result = RuntimeResult(
                    runtime=RuntimeTarget.LEARNING,
                    step_id=step.step_id,
                    status="success",
                    data={"patterns": [_to_dict(p) for p in patterns], "count": len(patterns)},
                    duration_ms=(time.monotonic() - start) * 1000,
                    correlation_id=ctx.correlation_id,
                )
            elif action == "analyze_patterns":
                stats = learning_service.get_statistics()
                result = RuntimeResult(
                    runtime=RuntimeTarget.LEARNING,
                    step_id=step.step_id,
                    status="success",
                    data={"statistics": stats, "action": action},
                    duration_ms=(time.monotonic() - start) * 1000,
                    correlation_id=ctx.correlation_id,
                )
            elif action == "get_recommendations":
                mission_data = {"prompt": params.get("prompt", ""), "source": "ai_runtime"}
                analysis = learning_service.analyze_mission(mission_data)
                result = RuntimeResult(
                    runtime=RuntimeTarget.LEARNING,
                    step_id=step.step_id,
                    status="success",
                    data={"recommendations": _to_dict(analysis) if analysis else {}, "action": action},
                    duration_ms=(time.monotonic() - start) * 1000,
                    correlation_id=ctx.correlation_id,
                )
            else:
                patterns = learning_service.list_patterns(limit=5)
                result = RuntimeResult(
                    runtime=RuntimeTarget.LEARNING,
                    step_id=step.step_id,
                    status="success",
                    data={"patterns": [_to_dict(p) for p in patterns], "action": action},
                    duration_ms=(time.monotonic() - start) * 1000,
                    correlation_id=ctx.correlation_id,
                )
            return result
        except Exception as exc:
            log.warning("Learning handler error: %s", exc)
            return RuntimeResult(
                runtime=RuntimeTarget.LEARNING,
                step_id=step.step_id,
                status="failed",
                error=str(exc),
                duration_ms=(time.monotonic() - start) * 1000,
                correlation_id=ctx.correlation_id,
            )

    # ------------------------------------------------------------------
    # Execution Runtime integration
    # ------------------------------------------------------------------

    async def _execution_handler(self, step: PlanStep, ctx: RuntimeContext) -> RuntimeResult:
        start = time.monotonic()
        action = step.action
        params = ctx.enrich_step_params(step)
        try:
            execution_service = container.resolve("execution_service")
        except (KeyError, Exception):
            log.warning("Execution service not available")
            return RuntimeResult(
                runtime=RuntimeTarget.EXECUTION,
                step_id=step.step_id,
                status="success",
                data={"action": action, "note": "execution runtime unavailable"},
                duration_ms=(time.monotonic() - start) * 1000,
                correlation_id=ctx.correlation_id,
            )
        try:
            if action in ("execute_mission_steps", "execute_tool"):
                command = params.get("prompt", params.get("command", step.name))[:200]
                entity = execution_service.create_execution(
                    command=command,
                    mission_id=ctx.mission_id or None,
                    source="ai_runtime",
                )
                result = RuntimeResult(
                    runtime=RuntimeTarget.EXECUTION,
                    step_id=step.step_id,
                    status="success",
                    data={"execution": _to_dict(entity) if entity else {}, "action": action},
                    duration_ms=(time.monotonic() - start) * 1000,
                    correlation_id=ctx.correlation_id,
                )
            elif action in ("inspect_executions", "list_executions"):
                executions = execution_service.list_executions(limit=20)
                result = RuntimeResult(
                    runtime=RuntimeTarget.EXECUTION,
                    step_id=step.step_id,
                    status="success",
                    data={"executions": [_to_dict(e) for e in executions], "count": len(executions)},
                    duration_ms=(time.monotonic() - start) * 1000,
                    correlation_id=ctx.correlation_id,
                )
            elif action == "schedule_execution":
                command = params.get("prompt", params.get("command", step.name))[:200]
                entity = execution_service.create_execution(command=command, source="ai_runtime")
                if entity:
                    execution_service.queue_execution(entity.id, actor=ctx.user_id or "ai_runtime")
                result = RuntimeResult(
                    runtime=RuntimeTarget.EXECUTION,
                    step_id=step.step_id,
                    status="success",
                    data={"execution": _to_dict(entity) if entity else {}, "action": action, "scheduled": True},
                    duration_ms=(time.monotonic() - start) * 1000,
                    correlation_id=ctx.correlation_id,
                )
            else:
                executions = execution_service.list_executions(limit=5)
                result = RuntimeResult(
                    runtime=RuntimeTarget.EXECUTION,
                    step_id=step.step_id,
                    status="success",
                    data={"executions": [_to_dict(e) for e in executions], "action": action},
                    duration_ms=(time.monotonic() - start) * 1000,
                    correlation_id=ctx.correlation_id,
                )
            return result
        except Exception as exc:
            log.warning("Execution handler error: %s", exc)
            return RuntimeResult(
                runtime=RuntimeTarget.EXECUTION,
                step_id=step.step_id,
                status="failed",
                error=str(exc),
                duration_ms=(time.monotonic() - start) * 1000,
                correlation_id=ctx.correlation_id,
            )

    # ------------------------------------------------------------------
    # Connector Runtime integration
    # ------------------------------------------------------------------

    async def _connector_handler(self, step: PlanStep, ctx: RuntimeContext) -> RuntimeResult:
        start = time.monotonic()
        action = step.action
        params = ctx.enrich_step_params(step)
        try:
            connector_service = container.resolve("connector_service")
        except (KeyError, Exception):
            log.warning("Connector service not available")
            return RuntimeResult(
                runtime=RuntimeTarget.CONNECTOR,
                step_id=step.step_id,
                status="success",
                data={"action": action, "note": "connector runtime unavailable"},
                duration_ms=(time.monotonic() - start) * 1000,
                correlation_id=ctx.correlation_id,
            )
        try:
            if action == "configure_connector":
                health_map = connector_service.run_health_checks()
                result = RuntimeResult(
                    runtime=RuntimeTarget.CONNECTOR,
                    step_id=step.step_id,
                    status="success",
                    data={"connectors": health_map, "action": action},
                    duration_ms=(time.monotonic() - start) * 1000,
                    correlation_id=ctx.correlation_id,
                )
            elif action in ("invoke_connector", "execute_capability"):
                connectors = connector_service.list_connectors()
                connector_results = []
                for conn in connectors:
                    try:
                        caps = connector_service.capabilities(conn.connector_type)
                        if caps:
                            cap = caps[0]
                            result_data = connector_service.execute_capability(
                                conn.connector_type, cap, {"input": params.get("prompt", "")},
                                timeout_seconds=30, actor=ctx.user_id,
                            )
                            connector_results.append({"type": conn.connector_type, "result": result_data})
                    except Exception:
                        pass
                result = RuntimeResult(
                    runtime=RuntimeTarget.CONNECTOR,
                    step_id=step.step_id,
                    status="success",
                    data={"connector_results": connector_results, "action": action},
                    duration_ms=(time.monotonic() - start) * 1000,
                    correlation_id=ctx.correlation_id,
                )
            else:
                health = connector_service.run_health_checks()
                result = RuntimeResult(
                    runtime=RuntimeTarget.CONNECTOR,
                    step_id=step.step_id,
                    status="success",
                    data={"health": health, "action": action},
                    duration_ms=(time.monotonic() - start) * 1000,
                    correlation_id=ctx.correlation_id,
                )
            return result
        except Exception as exc:
            log.warning("Connector handler error: %s", exc)
            return RuntimeResult(
                runtime=RuntimeTarget.CONNECTOR,
                step_id=step.step_id,
                status="failed",
                error=str(exc),
                duration_ms=(time.monotonic() - start) * 1000,
                correlation_id=ctx.correlation_id,
            )

    # ------------------------------------------------------------------
    # AI Runtime self-invocation
    # ------------------------------------------------------------------

    async def _ai_handler(self, step: PlanStep, ctx: RuntimeContext) -> RuntimeResult:
        start = time.monotonic()
        params = ctx.enrich_step_params(step)
        try:
            ai_service = container.resolve("ai_service")
        except (KeyError, Exception):
            return RuntimeResult(
                runtime=RuntimeTarget.AI,
                step_id=step.step_id,
                status="success",
                data={"note": "AI self-invocation placeholder", "action": step.action},
                duration_ms=(time.monotonic() - start) * 1000,
                correlation_id=ctx.correlation_id,
            )
        try:
            if step.action == "fallback":
                health = await ai_service.health()
                result = RuntimeResult(
                    runtime=RuntimeTarget.AI,
                    step_id=step.step_id,
                    status="success",
                    data={"health": health, "action": "fallback", "note": "No runtime route configured"},
                    duration_ms=(time.monotonic() - start) * 1000,
                    correlation_id=ctx.correlation_id,
                )
            else:
                response = await ai_service.process_request(
                    prompt=params.get("prompt", step.name),
                )
                result = RuntimeResult(
                    runtime=RuntimeTarget.AI,
                    step_id=step.step_id,
                    status="success" if response and not response.error else "failed",
                    data={"response": _to_dict(response) if response else {}, "action": step.action},
                    duration_ms=(time.monotonic() - start) * 1000,
                    correlation_id=ctx.correlation_id,
                )
                if response and response.error:
                    result.error = response.error
            return result
        except Exception as exc:
            log.warning("AI handler error: %s", exc)
            return RuntimeResult(
                runtime=RuntimeTarget.AI,
                step_id=step.step_id,
                status="failed",
                error=str(exc),
                duration_ms=(time.monotonic() - start) * 1000,
                correlation_id=ctx.correlation_id,
            )


def _to_dict(obj: Any) -> dict[str, Any]:
    if hasattr(obj, "__dict__"):
        return {k: _to_dict(v) if hasattr(v, "__dict__") else v for k, v in obj.__dict__.items() if not k.startswith("_")}
    if isinstance(obj, (list, tuple)):
        return [_to_dict(i) for i in obj]
    return obj
