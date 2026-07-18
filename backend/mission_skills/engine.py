from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

from backend.connectors.registry import connector_registry
from backend.events.event_bus import event_bus
from backend.events.event_models import CognitionEvent
from backend.mission_skills.models import (
    MissionStateModel,
    RetryPolicy,
    StepResult,
    WorkflowDefinition,
    WorkflowStepDef,
)
from backend.safety.approval_queue import approval_queue
from backend.safety.audit_logger import audit_logger

log = logging.getLogger(__name__)


class MissionSkillEngine:
    """
    Generic engine that executes any ``WorkflowDefinition``.

    Responsibilities:
      - Step execution via ConnectorRegistry
      - Approval gates via ApprovalQueue
      - Parameter rendering (``$params.*``, ``$steps.*``)
      - Retry with exponential backoff
      - Per-step timeout
      - Condition evaluation (skip step)
      - State persistence via MissionStateModel
      - Replay event emission
      - Audit logging
      - Resume from last completed step
    """

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    async def execute(
        self,
        definition: WorkflowDefinition,
        execution_id: str,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Execute all steps in *definition* in order with persistence + recovery.

        Returns a summary dict with completed/failed steps, resources, and
        per-step results.
        """
        state = await MissionStateModel.load(execution_id)
        if state is None:
            state = MissionStateModel(
                execution_id=execution_id,
                skill_type=definition.skill_type,
            )
            await state.save()

        previous_results: Dict[str, Any] = {}
        step_results: List[StepResult] = []
        workflow_failed = False

        for step_def in definition.steps:
            # ── Resume: skip already-completed steps ──────────────
            if state.is_last_step_completed(step_def.id):
                log.info(
                    "Engine step %s already completed — skipping (resume)",
                    step_def.id,
                )
                step_results.append(StepResult(
                    step_id=step_def.id, success=True, skipped=True,
                ))
                continue

            # ── Execute one step ──────────────────────────────────
            result = await self._execute_step(step_def, state, context, previous_results)
            step_results.append(result)

            if result.success:
                state.complete_step(step_def.id)
                if result.output.get("resource_id"):
                    state.add_resource(
                        resource_type=step_def.id,
                        resource_id=result.output["resource_id"],
                        metadata={"operation": step_def.operation},
                    )
                previous_results[step_def.id] = result.output
            else:
                state.fail_step(step_def.id)
                if step_def.on_failure == "fail":
                    workflow_failed = True
                    await state.save()
                    raise RuntimeError(
                        f"Workflow {definition.skill_type} failed at step "
                        f"'{step_def.id}': {result.error}"
                    )
                # on_failure == "skip" or "continue" — proceed

            await state.save()

        state.status = "completed" if not workflow_failed else "failed"
        if workflow_failed:
            state.status = "failed"
        await state.save()

        return self._build_summary(definition, state, step_results, context)

    # ------------------------------------------------------------------
    # Single step execution  (connector call or approval gate)
    # ------------------------------------------------------------------

    async def _execute_step(
        self,
        step_def: WorkflowStepDef,
        state: MissionStateModel,
        context: Dict[str, Any],
        previous_results: Dict[str, Any],
    ) -> StepResult:
        """
        Execute one workflow step: render params, check condition, possibly
        run an approval gate, then invoke the connector operation with retry.
        """
        execution_id = state.execution_id
        session_id = context.get("session_id")

        # ── Condition check — skip step when falsy ────────────────
        if step_def.condition:
            rendered_condition = self._render_value(
                step_def.condition, context, previous_results,
            )
            if not rendered_condition:
                log.info("Engine step %s condition falsy — skipping", step_def.id)
                return StepResult(
                    step_id=step_def.id, success=True, skipped=True,
                )

        # ── Emit step_started ─────────────────────────────────────
        await self._emit_event(
            execution_id, step_def, "workflow_step_started", "running",
            f"Starting step: {step_def.name}", session_id,
        )

        # ── Approval gate (runs BEFORE the operation) ─────────────
        if step_def.approval:
            pr_number = previous_results.get("create_pull_request", {}).get("pr_number", 0)
            approved = await self._execute_approval(
                step_def, state, context, pr_number, previous_results,
            )
            if not approved:
                msg = f"Step '{step_def.id}' approval rejected"
                await self._emit_event(
                    execution_id, step_def, "workflow_step_failed", "failed",
                    msg, session_id, {"error": msg},
                )
                return StepResult(
                    step_id=step_def.id, success=False,
                    error="Approval rejected",
                )

        # ── Connector operation with retry ────────────────────────
        if step_def.connector and step_def.operation != "__approval__":
            return await self._execute_connector_op(
                step_def, state, context, previous_results,
            )

        # Approval-only step (no connector op afterwards)
        return StepResult(step_id=step_def.id, success=True, output={"approved": True})

    # ------------------------------------------------------------------
    # Connector operation with retry + timeout
    # ------------------------------------------------------------------

    async def _execute_connector_op(
        self,
        step_def: WorkflowStepDef,
        state: MissionStateModel,
        context: Dict[str, Any],
        previous_results: Dict[str, Any],
    ) -> StepResult:
        execution_id = state.execution_id
        session_id = context.get("session_id")

        connector = connector_registry.get(step_def.connector)
        if connector is None:
            return StepResult(
                step_id=step_def.id, success=False,
                error=f"Connector '{step_def.connector}' not registered",
            )

        method = getattr(connector, step_def.operation, None)
        if method is None:
            return StepResult(
                step_id=step_def.id, success=False,
                error=f"Method '{step_def.operation}' not found on {step_def.connector}",
            )

        rendered_params = self._render_params(step_def.params, context, previous_results)
        max_retries = step_def.retry.max_retries
        last_error: Optional[str] = None
        started_at = time.monotonic()

        for attempt in range(1 + max_retries):
            try:
                if step_def.timeout:
                    raw = await asyncio.wait_for(
                        method(**rendered_params),
                        timeout=step_def.timeout,
                    )
                else:
                    raw = await method(**rendered_params)

                elapsed_ms = int((time.monotonic() - started_at) * 1000)
                output = self._extract_output(raw, step_def)

                audit_logger.log(
                    execution_id=execution_id,
                    agent=f"skill:{state.skill_type}",
                    action=step_def.operation,
                    target=f"{step_def.connector}/{step_def.id}",
                    outcome="completed",
                    reason=f"Step '{step_def.id}' OK ({elapsed_ms}ms, {attempt} retries)",
                    session_id=session_id,
                )
                await self._emit_event(
                    execution_id, step_def, "workflow_step_completed", "completed",
                    f"Step '{step_def.name}' completed ({elapsed_ms}ms)",
                    session_id,
                    {"duration_ms": elapsed_ms, "retries": attempt},
                )

                return StepResult(
                    step_id=step_def.id, success=True,
                    output=output, duration_ms=elapsed_ms,
                    retries=attempt,
                )

            except Exception as exc:
                last_error = str(exc)
                elapsed_ms = int((time.monotonic() - started_at) * 1000)

                if attempt < max_retries:
                    backoff = self._compute_backoff(step_def.retry, attempt)
                    log.warning(
                        "Engine step %s attempt %d/%d failed (%dms) — "
                        "retrying in %.1fs: %s",
                        step_def.id, attempt + 1, max_retries + 1,
                        elapsed_ms, backoff, last_error,
                    )
                    await asyncio.sleep(backoff)
                else:
                    audit_logger.log(
                        execution_id=execution_id,
                        agent=f"skill:{state.skill_type}",
                        action=step_def.operation,
                        target=f"{step_def.connector}/{step_def.id}",
                        outcome="failed",
                        reason=f"Step '{step_def.id}' failed after {attempt} retries: {last_error}",
                        session_id=session_id,
                    )
                    await self._emit_event(
                        execution_id, step_def, "workflow_step_failed", "failed",
                        f"Step '{step_def.name}' failed: {last_error}",
                        session_id,
                        {"duration_ms": elapsed_ms, "retries": attempt, "error": last_error},
                    )

                    return StepResult(
                        step_id=step_def.id, success=False,
                        error=last_error, duration_ms=elapsed_ms,
                        retries=attempt,
                    )

        return StepResult(
            step_id=step_def.id, success=False,
            error=last_error or "Unknown error",
        )

    # ------------------------------------------------------------------
    # Approval gate
    # ------------------------------------------------------------------

    async def _execute_approval(
        self,
        step_def: WorkflowStepDef,
        state: MissionStateModel,
        context: Dict[str, Any],
        pr_number: int = 0,
        previous_results: Optional[Dict[str, Any]] = None,
    ) -> bool:
        config = step_def.approval
        execution_id = state.execution_id
        session_id = context.get("session_id")
        prev = previous_results or {}

        # Render template fields from config
        rendered_required = self._render_value(
            config.required, context, prev,
        )
        if not rendered_required:
            audit_logger.log(
                execution_id=execution_id,
                agent=f"skill:{state.skill_type}",
                action="approval",
                target=step_def.id,
                outcome="skipped",
                reason="Approval not required",
                session_id=session_id,
            )
            return True

        raw_description = config.description_template or f"Approve step '{step_def.name}'"
        description = self._render_template_string(raw_description, context, prev)
        await self._emit_event(
            execution_id, step_def, "workflow_approval_required", "pending",
            description, session_id,
            {"pr_number": pr_number},
        )

        req = await approval_queue.request(
            execution_id=execution_id,
            agent=f"skill:{state.skill_type}",
            action=config.action,
            description=description,
            risk_level=config.risk_level,
            context={"step_id": step_def.id, "pr_number": pr_number},
            session_id=session_id,
            timeout=config.timeout,
        )

        state.set_approval(step_def.id, req.status.value, {
            "request_id": req.request_id,
            "resolved_by": req.resolved_by,
            "reject_reason": req.reject_reason,
        })
        await state.save()

        if req.status.value != "approved":
            audit_logger.log(
                execution_id=execution_id,
                agent=f"skill:{state.skill_type}",
                action="approval",
                target=step_def.id,
                outcome=req.status.value,
                reason=req.reject_reason or "Not approved",
                session_id=session_id,
            )
            await self._emit_event(
                execution_id, step_def, "workflow_approval_rejected", "failed",
                f"Approval rejected: {req.reject_reason}",
                session_id,
                {"request_id": req.request_id},
            )
            return False

        audit_logger.log(
            execution_id=execution_id,
            agent=f"skill:{state.skill_type}",
            action="approval",
            target=step_def.id,
            outcome="approved",
            reason="Step approved",
            session_id=session_id,
        )
        await self._emit_event(
            execution_id, step_def, "workflow_approval_granted", "completed",
            f"Step '{step_def.name}' approved",
            session_id,
            {"approved_by": req.resolved_by, "request_id": req.request_id},
        )
        return True

    # ------------------------------------------------------------------
    # Parameter rendering
    # ------------------------------------------------------------------

    def _render_params(
        self,
        params: Dict[str, Any],
        context: Dict[str, Any],
        previous_results: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Recursively resolve ``$params.*`` and ``$steps.*`` references."""
        rendered: Dict[str, Any] = {}
        for key, value in params.items():
            rendered[key] = self._render_value(value, context, previous_results)
        return rendered

    def _render_value(
        self,
        value: Any,
        context: Dict[str, Any],
        previous_results: Dict[str, Any],
    ) -> Any:
        if isinstance(value, str):
            if value.startswith("$params."):
                parts = value[1:].split(".")
                # parts = ["params", "owner", ...] → skip "params"
                return self._deep_get(context.get("release_params", {}), parts[1:])
            if value.startswith("$steps."):
                parts = value[1:].split(".")
                # parts = ["steps", "step_id", "field", ...]
                step_id = parts[1]
                field_path = parts[2:]
                result = previous_results.get(step_id, {})
                return self._deep_get(result, field_path)
            return value
        if isinstance(value, dict):
            return {k: self._render_value(v, context, previous_results) for k, v in value.items()}
        if isinstance(value, list):
            return [self._render_value(item, context, previous_results) for item in value]
        return value

    def _render_template_string(
        self,
        template: str,
        context: Dict[str, Any],
        previous_results: Dict[str, Any],
    ) -> str:
        """Replace ``$params.xxx`` and ``$steps.xxx`` references inside a string."""
        import re

        def _replacer(m: re.Match) -> str:
            ref = m.group(1)
            val = self._render_value(f"${ref}", context, previous_results)
            return str(val) if val is not None else ""

        return re.sub(r"\$([\w.]+)", _replacer, template)

    @staticmethod
    def _deep_get(obj: Any, path: List[str]) -> Any:
        """Walk a dotted path into a nested dict, returning ``""`` for missing keys."""
        current = obj
        for key in path:
            if isinstance(current, dict):
                current = current.get(key, "")
            else:
                return ""
        return current

    # ------------------------------------------------------------------
    # Output extraction
    # ------------------------------------------------------------------

    def _extract_output(
        self,
        raw: Any,
        step_def: WorkflowStepDef,
    ) -> Dict[str, Any]:
        """
        Extract structured output from the raw connector result.
        If *step_def.outputs* is set, map fields using ``$.field`` selectors.
        Otherwise return the raw result as-is (if dict) or wrapped.
        """
        if not isinstance(raw, dict):
            return {"result": raw}

        if step_def.outputs:
            output: Dict[str, Any] = {}
            for field_key, selector in step_def.outputs.items():
                if selector.startswith("$."):
                    field_name = selector[2:]
                    output[field_key] = raw.get(field_name, "")
                else:
                    output[field_key] = selector
            # Include raw result fields for $steps references
            output.update(raw)
            return output

        return raw

    # ------------------------------------------------------------------
    # Backoff calculation
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_backoff(policy: RetryPolicy, attempt: int) -> float:
        if policy.backoff_strategy == "none":
            return 0.0
        if policy.backoff_strategy == "fixed":
            return policy.base_delay_s
        return policy.base_delay_s * (2 ** attempt)

    # ------------------------------------------------------------------
    # Replay event emission
    # ------------------------------------------------------------------

    @staticmethod
    async def _emit_event(
        execution_id: str,
        step_def: WorkflowStepDef,
        event_type: str,
        status: str,
        message: str,
        session_id: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None,
    ) -> None:
        try:
            await event_bus.publish(CognitionEvent(
                agent="skill_engine",
                event_type=event_type,
                status=status,
                phase=f"workflow:{step_def.id}",
                execution_id=execution_id,
                message=message,
                payload={
                    "step_id": step_def.id,
                    "step_name": step_def.name,
                    "operation": step_def.operation,
                    "connector": step_def.connector,
                    **(payload or {}),
                },
                session_id=session_id,
            ))
        except Exception as exc:
            log.warning("Engine _emit_event failed: %s", exc)

    # ------------------------------------------------------------------
    # Summary builder
    # ------------------------------------------------------------------

    @staticmethod
    def _build_summary(
        definition: WorkflowDefinition,
        state: MissionStateModel,
        step_results: List[StepResult],
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Build a structured execution summary from step results."""
        return {
            "status": state.status,
            "execution_id": state.execution_id,
            "skill_type": definition.skill_type,
            "completed_steps": state.completed_steps,
            "failed_steps": state.failed_steps,
            "step_attempts": state.step_attempts,
            "resources_created": state.resources_created,
            "approval_state": state.approval_state,
            "created_at": state.created_at,
            "updated_at": state.updated_at,
            "step_results": [
                {
                    "step_id": sr.step_id,
                    "success": sr.success,
                    "duration_ms": sr.duration_ms,
                    "retries": sr.retries,
                    "skipped": sr.skipped,
                    "error": sr.error,
                }
                for sr in step_results
            ],
        }


# Singleton
skill_engine = MissionSkillEngine()
