"""
Enterprise Mission Orchestrator — autonomous execution of cross-connector workflows.

Takes a MissionTemplate and runtime parameters, then:
1. Resolves template variables ({{var}} → value)
2. Creates an ExecutionContext
3. Runs cognition pipeline stages (planning, reasoning, etc.)
4. Executes the connector chain sequentially, passing outputs as inputs
5. Verifies each step (optional)
6. Handles recovery: retry → alternative → rollback → escalation
7. Records all events to replay_store and event_bus

Reuses existing services without duplication:
  - MissionRuntime / ExecutionContext / CognitionPipeline
  - ConnectorRegistry (for connector operations)
  - VerificationService (for post-step verification)
  - ApprovalQueue (for human approval gates)
  - GuardrailsEngine (for input/tool safety checks)
  - ReplayStore (for event recording)
  - OrchestrationTracer (for trace spans)
  - EventBus (for real-time WebSocket events)
"""
from __future__ import annotations

import asyncio
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from backend.connectors.registry import connector_registry
from backend.events.enterprise_event_types import EnterpriseEventTypes as EET
from backend.orchestration.execution_context import ExecutionContext, execution_context_manager
from backend.orchestration.orchestration_tracer import orchestration_tracer
from backend.safety.approval_queue import approval_queue
from backend.services.enterprise_event_hub import enterprise_hub
from backend.services.enterprise_graph_service import enterprise_graph
from backend.services.mission_replay_store import replay_store
from backend.services.mission_templates import (
    ConnectorStep,
    MissionTemplate,
    RecoveryRule,
)

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Legacy → Standardized event type mapping
# ---------------------------------------------------------------------------

_LEGACY_TO_STANDARD: Dict[str, str] = {
    "enterprise_mission_started":        EET.MISSION_LAUNCHED,
    "enterprise_mission_completed":      EET.MISSION_COMPLETED,
    "enterprise_mission_failed":         EET.MISSION_FAILED,
    "enterprise_step_completed":         EET.MISSION_STEP,
    "enterprise_step_retry":             EET.RECOVERY_RETRY,
    "enterprise_step_retries_exhausted": EET.RECOVERY_RETRY,
    "enterprise_step_alternative":       EET.RECOVERY_FALLBACK,
    "enterprise_approval_required":      EET.APPROVAL_REQUIRED,
    "enterprise_approval_approved":      EET.APPROVAL_GRANTED,
    "enterprise_approval_rejected":      EET.APPROVAL_REJECTED,
    "enterprise_approval_timeout":       EET.APPROVAL_TIMED_OUT,
    "enterprise_rollback_started":       EET.RECOVERY_ROLLBACK,
    "enterprise_rollback_completed":     EET.RECOVERY_ROLLBACK,
    "enterprise_escalation":             EET.RECOVERY_ESCALATION,
}

# ---------------------------------------------------------------------------
# Parameter resolution
# ---------------------------------------------------------------------------

def _resolve_template(text: str, params: Dict[str, Any]) -> str:
    """Replace {{variable}} placeholders with actual values."""

    def _replacer(m: re.Match) -> str:
        key = m.group(1).strip()
        return str(params.get(key, m.group(0)))

    return re.sub(r"\{\{(\w+)\}\}", _replacer, text)


def _resolve_params(
    raw: Dict[str, Any],
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Recursively resolve template variables in a parameter dict."""
    resolved: Dict[str, Any] = {}
    for k, v in raw.items():
        if isinstance(v, str):
            resolved[k] = _resolve_template(v, params)
        elif isinstance(v, dict):
            resolved[k] = _resolve_params(v, params)
        elif isinstance(v, list):
            resolved[k] = [
                _resolve_template(item, params) if isinstance(item, str) else item
                for item in v
            ]
        else:
            resolved[k] = v
    return resolved


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

class EnterpriseMissionOrchestrator:
    """Orchestrates end-to-end enterprise missions from templates."""

    def __init__(self) -> None:
        self._active_missions: Dict[str, Dict[str, Any]] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def launch(
        self,
        template: MissionTemplate,
        params: Dict[str, Any],
        launched_by: str = "system",
    ) -> Dict[str, Any]:
        """Launch an enterprise mission from a template.

        Quarantined (Phase 5.15, ADR-058): this path invokes connector
        operations by ``getattr`` with caller-supplied params — real provider
        writes with no tenant, no capability authorization, and no durable
        audit — and it is reachable from an always-on watcher timer with no
        HTTP request in the stack. It refuses unless the legacy execution
        flag is set, exactly like every other V1 execution surface. The
        governed replacement is a capability-declared operation through the
        invocation gateway; until those declarations exist this stays a
        deliberate, logged bypass, never a default.
        """
        from backend.api.legacy_execution_boundary import guard_legacy_internal

        guard_legacy_internal("enterprise_mission_orchestrator.launch")
        execution_id = str(uuid.uuid4())
        merged_params = {**template.default_params, **params}

        # Validate required params
        missing = [r for r in template.required_params if r not in merged_params]
        if missing:
            raise ValueError(f"Missing required parameters: {missing}")

        start_time = datetime.now(timezone.utc)

        # Create execution context
        ctx = execution_context_manager.create(
            objective=f"[{template.name}] {merged_params.get('title', merged_params.get('bug_title', merged_params.get('incident_title', merged_params.get('change_title', 'Enterprise mission'))))}",
            template_id=template.id,
            params=merged_params,
        )

        # Record active mission
        mission_record: Dict[str, Any] = {
            "execution_id": execution_id,
            "template_id": template.id,
            "template_name": template.name,
            "params": merged_params,
            "status": "running",
            "launched_by": launched_by,
            "started_at": start_time.isoformat(),
            "steps": [],
            "current_step": -1,
            "error": None,
        }
        self._active_missions[execution_id] = mission_record

        # Record to Neo4j knowledge graph
        asyncio.ensure_future(enterprise_graph.record_mission_launch(
            execution_id=execution_id,
            template_id=template.id,
            template_name=template.name,
            objective=merged_params.get("title",
                       merged_params.get("bug_title",
                       merged_params.get("incident_title",
                       merged_params.get("change_title",
                       template.name)))),
            params=merged_params,
            launched_by=launched_by,
        ))

        # Emit launch event
        await self._emit_event(execution_id, template.name, "enterprise_mission_started",
                               status="running", message=f"Launching {template.name}")

        try:
            # Phase 1: Cognition pipeline stages
            await self._run_pipeline_stages(ctx, template)

            # Phase 2: Connector chain
            await self._run_connector_chain(ctx, template, merged_params, execution_id, mission_record)

            # Mark completed
            mission_record["status"] = "completed"
            mission_record["completed_at"] = datetime.now(timezone.utc).isoformat()

            await self._emit_event(execution_id, template.name, "enterprise_mission_completed",
                                   status="completed", message=f"{template.name} completed successfully")

        except Exception as exc:
            log.error("Enterprise mission %s failed: %s", execution_id, exc)
            mission_record["status"] = "failed"
            mission_record["error"] = str(exc)
            await self._emit_event(execution_id, template.name, "enterprise_mission_failed",
                                   status="failed", message=str(exc))

        # Record completion/failure to Neo4j
        asyncio.ensure_future(enterprise_graph.record_mission_completion(
            execution_id=execution_id,
            status=mission_record["status"],
            error=mission_record.get("error"),
        ))

        # Record outcome
        outcome_summary = (
            f"{template.name} completed successfully"
            if mission_record["status"] == "completed"
            else f"{template.name} failed: {mission_record.get('error', '')}"
        )
        asyncio.ensure_future(enterprise_graph.record_outcome(
            execution_id=execution_id,
            outcome_id=str(uuid.uuid4()),
            outcome_type="success" if mission_record["status"] == "completed" else "failure",
            summary=outcome_summary,
            details={"step_count": len(mission_record["steps"]),
                     "template": template.name,
                     "launched_by": launched_by},
        ))

        # Record to replay store
        await self._record_replay(execution_id, mission_record)

        return {
            "execution_id": execution_id,
            "status": mission_record["status"],
            "template": template.name,
            "started_at": mission_record["started_at"],
            "steps_completed": len(mission_record["steps"]),
            "error": mission_record.get("error"),
        }

    def get_mission(self, execution_id: str) -> Optional[Dict[str, Any]]:
        return self._active_missions.get(execution_id)

    def list_active(self) -> List[Dict[str, Any]]:
        return [
            m for m in self._active_missions.values()
            if m["status"] in ("running", "pending_approval")
        ]

    def list_all(self) -> List[Dict[str, Any]]:
        return list(self._active_missions.values())

    # ------------------------------------------------------------------
    # Phase 1: Cognition pipeline
    # ------------------------------------------------------------------

    async def _run_pipeline_stages(
        self, ctx: ExecutionContext, template: MissionTemplate,
    ) -> None:
        """Run the standard cognition pipeline stages for this mission."""
        if not template.pipeline_stages:
            return

        try:
            from backend.orchestration.cognition_pipeline import cognition_pipeline
            await cognition_pipeline.run(ctx, stages=template.pipeline_stages)
        except ImportError:
            log.warning("Cognition pipeline unavailable — skipping phase 1")
        except Exception as exc:
            log.warning("Cognition pipeline error (non-fatal): %s", exc)

    # ------------------------------------------------------------------
    # Phase 2: Connector chain
    # ------------------------------------------------------------------

    async def _run_connector_chain(
        self,
        ctx: ExecutionContext,
        template: MissionTemplate,
        params: Dict[str, Any],
        execution_id: str,
        mission_record: Dict[str, Any],
    ) -> None:
        """Execute the ordered connector chain with auto-chaining and recovery."""
        if not template.connector_chain:
            return

        chain_output: Dict[str, Any] = {}
        step_count = len(template.connector_chain)

        previous_action_id: Optional[str] = None

        for idx, step in enumerate(template.connector_chain):
            mission_record["current_step"] = idx

            # Resolve params (includes previous step outputs via chain_output)
            step_params = _resolve_params(step.params, {**params, **chain_output})

            approval_result = await self._check_approval_gate(template, idx, execution_id, step)
            if approval_result == "rejected":
                raise RuntimeError(f"Approval rejected at step {idx}: {step.description}")

            # Guardrails check on the tool call
            self._guardrail_tool(step, step_params)

            step_result = await self._execute_step_with_recovery(
                step, step_params, template.recovery, execution_id, idx, step_count,
            )

            # Merge step output into chain output for next step
            if isinstance(step_result, dict):
                for src_key, dst_key in step.output_mapping.items():
                    if src_key in step_result:
                        chain_output[dst_key] = step_result[src_key]

                chain_output[f"step_{idx}_output"] = step_result

            # Record step
            action_id = str(uuid.uuid4())
            mission_record["steps"].append({
                "index": idx,
                "action_id": action_id,
                "connector": step.connector_type,
                "operation": step.operation,
                "description": step.description,
                "status": "completed",
                "output": step_result,
            })

            # Record to Neo4j knowledge graph
            asyncio.ensure_future(enterprise_graph.record_connector_action(
                execution_id=execution_id,
                step_idx=idx,
                action_id=action_id,
                connector_type=step.connector_type,
                operation=step.operation,
                description=step.description,
                status="completed",
                params=step_params,
                output=str(step_result)[:500] if step_result else None,
                previous_action_id=previous_action_id,
            ))
            previous_action_id = action_id

            # Record artifact if output has an id
            if isinstance(step_result, dict):
                for id_key in ("id", "issue_number", "pull_number", "work_item_id",
                               "run_id", "sys_id", "page_id", "key"):
                    if id_key in step_result:
                        asyncio.ensure_future(enterprise_graph.record_artifact(
                            action_id=action_id,
                            artifact_key=f"{step.connector_type}_{step_result[id_key]}",
                            artifact_type=f"{step.connector_type}_{step.operation}_output",
                            name=str(step_result.get("title", step_result.get("name", step_result[id_key]))),
                            description=step.description,
                            url=step_result.get("html_url", step_result.get("url", None)),
                        ))
                        break

            # Trace span
            orchestration_tracer.start_span(execution_id, step.connector_type, step.operation)
            orchestration_tracer.finish_span(
                orchestration_tracer.start_span(execution_id, step.connector_type, step.operation),
                status="completed",
            )

            await self._emit_event(execution_id, template.name, "enterprise_step_completed",
                                   status="completed",
                                   message=f"Step {idx + 1}/{step_count}: {step.description}",
                                   metadata={"step": idx, "connector": step.connector_type})

            # Emit standardized connector action event
            asyncio.ensure_future(enterprise_hub.emit_connector_action(
                execution_id=execution_id,
                connector_type=step.connector_type,
                operation=step.operation,
                status="completed",
                description=step.description,
                metadata={"step_idx": idx, "action_id": action_id},
            ))

            # Verify step output
            if template.verify_each_step:
                await self._verify_step(step, step_result, step_params, execution_id)

    # ------------------------------------------------------------------
    # Step execution with recovery
    # ------------------------------------------------------------------

    async def _execute_step_with_recovery(
        self,
        step: ConnectorStep,
        params: Dict[str, Any],
        recovery: RecoveryRule,
        execution_id: str,
        step_idx: int,
        total_steps: int,
    ) -> Any:
        """Execute a single connector step with full recovery logic."""
        last_error: Optional[str] = None

        # Attempt 1: Primary execution
        for attempt in range(1 + recovery.max_retries):
            try:
                result = await self._call_connector(step.connector_type, step.operation, params)
                if result is not None:
                    return result
                last_error = f"Connector returned None for {step.connector_type}.{step.operation}"
            except Exception as exc:
                last_error = str(exc)
                log.warning("Step %s.%s attempt %d failed: %s",
                            step.connector_type, step.operation, attempt + 1, exc)

                if attempt < recovery.max_retries:
                    await self._emit_event(execution_id, step.description, "enterprise_step_retry",
                                           status="retrying",
                                           message=f"Retry {attempt + 1}/{recovery.max_retries}: {exc}")
                    await asyncio.sleep(1.0 * (attempt + 1))
                else:
                    await self._emit_event(execution_id, step.description, "enterprise_step_retries_exhausted",
                                           status="failed",
                                           message=f"All retries exhausted: {exc}")

        # Attempt 2: Alternative connector/operation
        if recovery.alternative_connector:
            alt_connector = recovery.alternative_connector
            alt_op = recovery.alternative_operation or step.operation
            try:
                log.info("Falling back to alternative: %s.%s", alt_connector, alt_op)
                await self._emit_event(execution_id, step.description, "enterprise_step_alternative",
                                       status="fallback",
                                       message=f"Falling back to {alt_connector}.{alt_op}")

                asyncio.ensure_future(enterprise_graph.record_recovery(
                    execution_id=execution_id,
                    recovery_id=str(uuid.uuid4()),
                    recovery_type="alternative",
                    description=f"Alternative: {alt_connector}.{alt_op} for {step.connector_type}.{step.operation}",
                ))

                result = await self._call_connector(alt_connector, alt_op, params)
                if result is not None:
                    return result
            except Exception as alt_exc:
                log.warning("Alternative %s.%s also failed: %s", alt_connector, alt_op, alt_exc)

        # Attempt 3: Rollback
        if recovery.rollback_steps:
            await self._rollback_steps(recovery.rollback_steps, execution_id)

            asyncio.ensure_future(enterprise_graph.record_recovery(
                execution_id=execution_id,
                recovery_id=str(uuid.uuid4()),
                recovery_type="rollback",
                description=f"Rolled back steps {recovery.rollback_steps} after {step.connector_type}.{step.operation} failure",
            ))

        # Attempt 4: Escalation
        if recovery.escalate_after_retries:
            await self._escalate(step, last_error or "Unknown error", execution_id)

        raise RuntimeError(
            f"Step {step.connector_type}.{step.operation} failed after all recovery attempts. "
            f"Last error: {last_error}"
        )

    # ------------------------------------------------------------------
    # Connector call
    # ------------------------------------------------------------------

    async def _call_connector(
        self, connector_type: str, operation: str, params: Dict[str, Any],
    ) -> Any:
        """Call a connector operation via the registry."""
        connector = connector_registry.get(connector_type)
        if connector is None:
            raise ValueError(f"Connector '{connector_type}' is not registered")

        method = getattr(connector, operation, None)
        if method is None:
            raise ValueError(f"Operation '{operation}' not found on connector '{connector_type}'")

        if asyncio.iscoroutinefunction(method):
            return await method(**params)
        return method(**params)

    # ------------------------------------------------------------------
    # Approval gates
    # ------------------------------------------------------------------

    async def _check_approval_gate(
        self,
        template: MissionTemplate,
        step_idx: int,
        execution_id: str,
        step: ConnectorStep,
    ) -> str:
        """Check if an approval gate blocks this step. Returns 'approved', 'rejected', or 'none'."""
        for gate in template.approval_gates:
            if gate.after_step == step_idx:
                request_id = str(uuid.uuid4())
                await self._emit_event(execution_id, f"Approval: {step.description}",
                                       "enterprise_approval_required",
                                       status="pending_approval",
                                       message=gate.reason)

                mission = self._active_missions.get(execution_id)
                if mission:
                    mission["status"] = "pending_approval"

                # Record approval gate to Neo4j
                asyncio.ensure_future(enterprise_graph.record_approval(
                    request_id=request_id,
                    execution_id=execution_id,
                    action_id=None,
                    step_idx=step_idx,
                    status="pending",
                    reason=gate.reason,
                ))

                try:
                    request = approval_queue.submit(
                        execution_id=execution_id,
                        reason=gate.reason,
                        timeout=gate.timeout_seconds,
                    )
                    result = await request.wait()
                    decision = "approved" if result else "rejected"

                    # Record decision to Neo4j
                    decision_id = str(uuid.uuid4())
                    asyncio.ensure_future(enterprise_graph.record_decision(
                        decision_id=decision_id,
                        execution_id=execution_id,
                        decision_type="approval_gate",
                        outcome=decision,
                        reason=f"Approval {decision} for {step.description} at step {step_idx}",
                    ))
                    asyncio.ensure_future(enterprise_graph.record_approval(
                        request_id=request_id,
                        execution_id=execution_id,
                        action_id=None,
                        step_idx=step_idx,
                        status=decision,
                        reason=gate.reason,
                    ))

                    await self._emit_event(execution_id, f"Approval: {step.description}",
                                           f"enterprise_approval_{decision}",
                                           status=decision,
                                           message=f"Approval {decision} for {step.description}")
                    if mission:
                        mission["status"] = "running"
                    return decision
                except TimeoutError:
                    await self._emit_event(execution_id, f"Approval: {step.description}",
                                           "enterprise_approval_timeout",
                                           status="timeout",
                                           message=f"Approval timed out for {step.description}")
                    if mission:
                        mission["status"] = "running"

                    # Record timeout to Neo4j
                    asyncio.ensure_future(enterprise_graph.record_approval(
                        request_id=request_id,
                        execution_id=execution_id,
                        action_id=None,
                        step_idx=step_idx,
                        status="timed_out",
                        reason=gate.reason,
                    ))

                    return "rejected"

        return "none"

    # ------------------------------------------------------------------
    # Verification
    # ------------------------------------------------------------------

    async def _verify_step(
        self,
        step: ConnectorStep,
        result: Any,
        params: Dict[str, Any],
        execution_id: str,
    ) -> None:
        """Verify a step's output using the VerificationService."""
        try:
            from backend.services.verification_service import verification_service
            verification_result = await verification_service.verify_operation(
                connector=connector_registry.get(step.connector_type),
                operation=step.operation,
                params=params,
                execution_id=execution_id,
            )

            # Record verification evidence to Neo4j
            if isinstance(verification_result, dict):
                evidence_id = str(uuid.uuid4())
                verified = verification_result.get("verified", False)
                next(
                    (s["index"] for s in self._active_missions.get(execution_id, {}).get("steps", [])
                     if s.get("connector") == step.connector_type and s.get("operation") == step.operation),
                    None
                )
                action_id = next(
                    (s.get("action_id") for s in self._active_missions.get(execution_id, {}).get("steps", [])
                     if s.get("connector") == step.connector_type and s.get("operation") == step.operation),
                    None
                )
                asyncio.ensure_future(enterprise_graph.record_evidence(
                    evidence_id=evidence_id,
                    action_id=action_id or str(uuid.uuid4()),
                    verified=verified,
                    method_used=verification_result.get("method_used", "unknown"),
                    evidence_data=verification_result.get("evidence"),
                ))

                # Emit standardized verification event
                asyncio.ensure_future(enterprise_hub.emit_verification(
                    execution_id=execution_id,
                    connector_type=step.connector_type,
                    operation=step.operation,
                    verified=verified,
                    status="completed" if verified else "failed",
                ))
        except ImportError:
            log.warning("Verification service unavailable — skipping verification")
        except Exception as exc:
            log.warning("Verification failed for %s.%s: %s",
                        step.connector_type, step.operation, exc)

    # ------------------------------------------------------------------
    # Recovery helpers
    # ------------------------------------------------------------------

    async def _rollback_steps(self, step_indices: List[int], execution_id: str) -> None:
        """Rollback specified steps by calling their inverse operations."""
        log.info("Rolling back steps %s for mission %s", step_indices, execution_id)
        mission = self._active_missions.get(execution_id)
        if not mission:
            return

        await self._emit_event(execution_id, "rollback", "enterprise_rollback_started",
                               status="rolling_back",
                               message=f"Rolling back steps {step_indices}")

        for idx in reversed(sorted(step_indices)):
            if idx < len(mission.get("steps", [])):
                step_info = mission["steps"][idx]
                try:
                    conn = connector_registry.get(step_info["connector"])
                    if conn and hasattr(conn, f"undo_{step_info['operation']}"):
                        undo = getattr(conn, f"undo_{step_info['operation']}")
                        if asyncio.iscoroutinefunction(undo):
                            await undo()
                        else:
                            undo()
                except Exception as exc:
                    log.warning("Rollback of step %d failed: %s", idx, exc)

        await self._emit_event(execution_id, "rollback", "enterprise_rollback_completed",
                               status="rolled_back",
                               message=f"Rolled back steps {step_indices}")

    async def _escalate(self, step: ConnectorStep, error: str, execution_id: str) -> None:
        """Escalate a failed step to human operators."""
        log.warning("Escalating failed step %s.%s: %s",
                    step.connector_type, step.operation, error)
        await self._emit_event(execution_id, f"Escalation: {step.description}",
                               "enterprise_escalation",
                               status="escalated",
                               message=f"Manual intervention required: {error}")

        asyncio.ensure_future(enterprise_graph.record_recovery(
            execution_id=execution_id,
            recovery_id=str(uuid.uuid4()),
            recovery_type="escalation",
            description=f"Escalated: {step.connector_type}.{step.operation} failed: {error}",
        ))

    # ------------------------------------------------------------------
    # Guardrails
    # ------------------------------------------------------------------

    def _guardrail_tool(self, step: ConnectorStep, params: Dict[str, Any]) -> None:
        """Run guardrails check on a connector operation."""
        try:
            from backend.safety.guardrails_engine import guardrails_engine
            result = guardrails_engine.check_tool(
                tool_name=step.connector_type,
                action=step.operation,
                params=params,
            )
            if result.get("decision") == "block":
                raise PermissionError(
                    f"Guardrails blocked {step.connector_type}.{step.operation}: "
                    f"{result.get('reason', 'No reason')}"
                )
        except ImportError:
            pass

    # ------------------------------------------------------------------
    # Events & Replay
    # ------------------------------------------------------------------

    async def _emit_event(
        self,
        execution_id: str,
        agent: str,
        event_type: str,
        status: str,
        message: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Emit an event with standardized enterprise event types.
        Maps legacy event_type strings to EnterpriseEventTypes and
        routes through EnterpriseEventHub for WebSocket + cross-service sync.
        """
        try:
            # Map legacy event types to standardized EnterpriseEventTypes
            standard_type = _LEGACY_TO_STANDARD.get(event_type, event_type)
            meta = {"execution_id": execution_id, **(metadata or {})}

            # Use EventHub's emit for standardized routing
            await enterprise_hub.emit(
                event_type=standard_type,
                agent=agent,
                status=status,
                message=message,
                execution_id=execution_id,
                metadata=meta,
            )
        except Exception as exc:
            log.warning("Failed to emit event: %s", exc)

    async def _record_replay(self, execution_id: str, record: Dict[str, Any]) -> None:
        try:
            await replay_store.record({
                "execution_id": execution_id,
                "type": "enterprise_mission",
                "template": record["template_id"],
                "status": record["status"],
                "started_at": record["started_at"],
                "completed_at": record.get("completed_at"),
                "steps": record["steps"],
                "error": record.get("error"),
            })
        except Exception as exc:
            log.warning("Failed to record replay: %s", exc)


# Module singleton
enterprise_orchestrator = EnterpriseMissionOrchestrator()
