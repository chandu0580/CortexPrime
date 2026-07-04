from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

from backend.approval_center.models import (
    ApprovalPolicy,
    ApprovalStep,
    ApprovalWorkflow,
    ApproverRole,
    BreakGlassRecord,
    Delegation,
    RiskLevel,
    StepStatus,
    WorkflowStatus,
    new_break_glass_id,
    new_delegation_id,
    new_step_id,
    new_workflow_id,
    utc_now,
)
from backend.approval_center.policies import (
    get_policy_for_mission,
    get_policy_for_risk,
)

log = logging.getLogger(__name__)


class ApprovalWorkflowEngine:
    """
    Multi-level approval workflow engine.

    Manages the lifecycle of approval workflows, including:
    - Multi-step approval chains with configurable roles per step
    - Escalation when approvers do not act within time limits
    - Expiration of stale approval requests
    - Delegation of approval authority
    - Break-glass emergency override
    - Integration with existing ApprovalQueue, AuditLogger, EventBus
    """

    def __init__(self) -> None:
        self._workflows: Dict[str, ApprovalWorkflow] = {}
        self._delegations: Dict[str, Delegation] = {}
        self._break_glass_records: Dict[str, BreakGlassRecord] = {}
        self._escalation_tasks: Dict[str, asyncio.Task] = {}

    # ------------------------------------------------------------------
    # Create a new approval workflow for a mission
    # ------------------------------------------------------------------

    async def create_workflow(
        self,
        execution_id: str,
        mission_id: str,
        objective: str,
        risk_level: RiskLevel,
        policy: Optional[ApprovalPolicy] = None,
    ) -> ApprovalWorkflow:
        if policy is None:
            policy = get_policy_for_mission(mission_id, risk_level)

        steps: List[ApprovalStep] = []
        for i, role in enumerate(policy.required_roles):
            steps.append(ApprovalStep(
                step_id=new_step_id(),
                level=i + 1,
                required_roles=[role],
                status=StepStatus.PENDING,
            ))

        workflow = ApprovalWorkflow(
            workflow_id=new_workflow_id(),
            execution_id=execution_id,
            mission_id=mission_id,
            policy_id=policy.policy_id,
            objective=objective,
            risk_level=risk_level,
            current_step=0,
            steps=steps,
            status=WorkflowStatus.PENDING,
        )

        self._workflows[workflow.workflow_id] = workflow

        log.info(
            "Approval workflow created: %s for execution %s (risk=%s, steps=%d)",
            workflow.workflow_id, execution_id, risk_level.value, len(steps),
        )

        await self._emit_event("approval_workflow_created", workflow)
        await self._audit("workflow_created", workflow)

        if policy.required_levels == 0:
            workflow.status = WorkflowStatus.APPROVED
            await self._emit_event("approval_workflow_completed", workflow)
        else:
            self._schedule_escalation(workflow)
            self._schedule_expiration(workflow)

        return workflow

    # ------------------------------------------------------------------
    # Approve the current step of a workflow
    # ------------------------------------------------------------------

    async def approve_step(
        self,
        workflow_id: str,
        approver: str,
        role: ApproverRole,
        reason: Optional[str] = None,
    ) -> ApprovalWorkflow:
        workflow = self._get_workflow(workflow_id)
        if workflow.status not in (WorkflowStatus.PENDING, WorkflowStatus.IN_PROGRESS):
            raise ValueError(f"Workflow {workflow_id} is in state {workflow.status.value}")

        step = workflow.current_step_obj
        if step is None:
            raise ValueError(f"Workflow {workflow_id} has no current step")

        if ApproverRole(role) not in step.required_roles:
            raise ValueError(
                f"Role {role.value} cannot approve step {step.level} "
                f"(requires: {[r.value for r in step.required_roles]})"
            )

        step.status = StepStatus.APPROVED
        step.resolved_by = approver
        step.resolved_at = utc_now()
        step.reason = reason
        workflow.updated_at = utc_now()

        await self._audit("step_approved", workflow, f"by {approver}: {reason or 'approved'}")

        # Advance to next step or complete
        if workflow.current_step + 1 >= len(workflow.steps):
            workflow.status = WorkflowStatus.APPROVED
            workflow.updated_at = utc_now()
            self._cancel_timers(workflow_id)

            # Unblock the underlying ApprovalQueue
            await self._resolve_approval_queue(workflow, approved=True)

            await self._emit_event("approval_workflow_completed", workflow)
            await self._audit("workflow_completed", workflow, "all steps approved")
            log.info("Approval workflow %s completed (all steps)", workflow_id)
        else:
            workflow.current_step += 1
            workflow.status = WorkflowStatus.IN_PROGRESS
            next_step = workflow.current_step_obj
            if next_step:
                self._schedule_escalation(workflow)
                self._schedule_expiration(workflow)
            await self._emit_event("approval_step_completed", workflow)

        return workflow

    # ------------------------------------------------------------------
    # Reject the current step of a workflow
    # ------------------------------------------------------------------

    async def reject_step(
        self,
        workflow_id: str,
        approver: str,
        reason: str,
    ) -> ApprovalWorkflow:
        workflow = self._get_workflow(workflow_id)
        step = workflow.current_step_obj
        if step:
            step.status = StepStatus.REJECTED
            step.resolved_by = approver
            step.resolved_at = utc_now()
            step.reason = reason

        workflow.status = WorkflowStatus.REJECTED
        workflow.updated_at = utc_now()

        self._cancel_timers(workflow_id)
        await self._resolve_approval_queue(workflow, approved=False)
        await self._emit_event("approval_workflow_rejected", workflow)
        await self._audit("workflow_rejected", workflow, f"by {approver}: {reason}")
        log.info("Approval workflow %s rejected by %s: %s", workflow_id, approver, reason)

        return workflow

    # ------------------------------------------------------------------
    # Delegate approval authority
    # ------------------------------------------------------------------

    async def delegate(
        self,
        workflow_id: str,
        from_user: str,
        to_user: str,
        reason: str,
    ) -> ApprovalWorkflow:
        workflow = self._get_workflow(workflow_id)
        step = workflow.current_step_obj
        if step is None:
            raise ValueError("No active step to delegate")

        delegation = Delegation(
            delegation_id=new_delegation_id(),
            from_role=step.required_roles[0],
            from_user=from_user,
            to_role=step.required_roles[0],
            to_user=to_user,
            reason=reason,
        )
        self._delegations[delegation.delegation_id] = delegation

        step.status = StepStatus.DELEGATED
        step.delegated_to = to_user
        step.reason = f"Delegated from {from_user} to {to_user}: {reason}"
        workflow.updated_at = utc_now()

        await self._emit_event("approval_delegated", workflow)
        await self._audit("step_delegated", workflow,
                          f"from {from_user} to {to_user}: {reason}")

        return workflow

    # ------------------------------------------------------------------
    # Emergency override / break-glass
    # ------------------------------------------------------------------

    async def break_glass(
        self,
        workflow_id: str,
        overridden_by: str,
        role: ApproverRole,
        reason: str,
        justification: Optional[str] = None,
    ) -> ApprovalWorkflow:
        workflow = self._get_workflow(workflow_id)
        policy = get_policy_for_risk(workflow.risk_level)

        if policy and not policy.requires_break_glass:
            raise ValueError(f"Policy {policy.policy_id} does not allow break-glass")

        if policy and role not in policy.break_glass_roles:
            raise ValueError(
                f"Role {role.value} is not authorized for break-glass "
                f"(requires: {[r.value for r in policy.break_glass_roles]})"
            )

        record = BreakGlassRecord(
            record_id=new_break_glass_id(),
            execution_id=workflow.execution_id,
            mission_id=workflow.mission_id,
            overridden_by=overridden_by,
            role=role,
            reason=reason,
            risk_level=workflow.risk_level,
            original_assessment=f"Policy {workflow.policy_id} required "
                                f"{len(workflow.steps)} approval level(s)",
            justification_documentation=justification,
        )
        self._break_glass_records[record.record_id] = record

        workflow.break_glass = True
        workflow.break_glass_by = overridden_by
        workflow.break_glass_reason = reason
        workflow.status = WorkflowStatus.BREAK_GLASS
        workflow.updated_at = utc_now()

        self._cancel_timers(workflow_id)
        await self._resolve_approval_queue(workflow, approved=True)
        await self._emit_event("approval_break_glass", workflow)
        await self._audit("break_glass_activated", workflow,
                          f"by {overridden_by} ({role.value}): {reason}")
        log.warning(
            "BREAK-GLASS activated for workflow %s by %s (%s): %s",
            workflow_id, overridden_by, role.value, reason,
        )

        return workflow

    # ------------------------------------------------------------------
    # Internal: schedule escalation timer for current step
    # ------------------------------------------------------------------

    def _schedule_escalation(self, workflow: ApprovalWorkflow) -> None:
        policy = get_policy_for_risk(workflow.risk_level)
        if not policy or policy.escalation_minutes <= 0:
            return
        delay = policy.escalation_minutes * 60

        async def _escalate() -> None:
            await asyncio.sleep(delay)
            wf = self._workflows.get(workflow.workflow_id)
            if wf is None or wf.status not in (
                WorkflowStatus.PENDING, WorkflowStatus.IN_PROGRESS
            ):
                return
            step = wf.current_step_obj
            if step and step.status == StepStatus.PENDING:
                step.status = StepStatus.ESCALATED
                step.escalation_count += 1
                wf.status = WorkflowStatus.ESCALATED
                wf.updated_at = utc_now()
                await self._emit_event("approval_escalated", wf)
                await self._audit("step_escalated", wf,
                                  f"step {step.level} timed out after {policy.escalation_minutes}m")
                log.warning("Approval step %d escalated for workflow %s",
                            step.level, workflow.workflow_id)

        task = asyncio.create_task(_escalate())
        self._escalation_tasks[workflow.workflow_id] = task

    def _schedule_expiration(self, workflow: ApprovalWorkflow) -> None:
        policy = get_policy_for_risk(workflow.risk_level)
        if not policy or policy.expiration_minutes <= 0:
            return
        delay = policy.expiration_minutes * 60

        async def _expire() -> None:
            await asyncio.sleep(delay)
            wf = self._workflows.get(workflow.workflow_id)
            if wf is None or wf.status not in (
                WorkflowStatus.PENDING, WorkflowStatus.IN_PROGRESS
            ):
                return
            wf.status = WorkflowStatus.EXPIRED
            wf.updated_at = utc_now()
            self._cancel_timers(workflow.workflow_id)
            await self._resolve_approval_queue(workflow, approved=False)
            await self._emit_event("approval_expired", wf)
            await self._audit("workflow_expired", wf,
                              f"expired after {policy.expiration_minutes}m")
            log.warning("Approval workflow %s expired", workflow.workflow_id)

        task = asyncio.create_task(_expire())
        self._escalation_tasks[f"expire_{workflow.workflow_id}"] = task

    def _cancel_timers(self, workflow_id: str) -> None:
        for key in (workflow_id, f"expire_{workflow_id}"):
            task = self._escalation_tasks.pop(key, None)
            if task and not task.done():
                task.cancel()

    # ------------------------------------------------------------------
    # Resolve the underlying ApprovalQueue for the mission
    # ------------------------------------------------------------------

    async def _resolve_approval_queue(
        self,
        workflow: ApprovalWorkflow,
        approved: bool,
    ) -> None:
        try:
            from backend.safety.approval_queue import approval_queue
            if approved:
                await approval_queue.approve(
                    request_id=workflow.execution_id,
                    resolved_by="approval_workflow_engine",
                    reason=f"Workflow {workflow.workflow_id} completed",
                )
            else:
                await approval_queue.reject(
                    request_id=workflow.execution_id,
                    resolved_by="approval_workflow_engine",
                    reason=f"Workflow {workflow.workflow_id} {workflow.status.value}",
                )
        except Exception as exc:
            log.warning("ApprovalQueue resolve failed: %s", exc)

    # ------------------------------------------------------------------
    # Query methods
    # ------------------------------------------------------------------

    def get_workflow(self, workflow_id: str) -> Optional[ApprovalWorkflow]:
        return self._workflows.get(workflow_id)

    def get_workflow_by_execution(self, execution_id: str) -> Optional[ApprovalWorkflow]:
        for wf in self._workflows.values():
            if wf.execution_id == execution_id:
                return wf
        return None

    def list_workflows(
        self,
        status: Optional[WorkflowStatus] = None,
    ) -> List[ApprovalWorkflow]:
        if status:
            return [w for w in self._workflows.values() if w.status == status]
        return list(self._workflows.values())

    def list_delegations(self) -> List[Delegation]:
        return list(self._delegations.values())

    def list_break_glass_records(self) -> List[BreakGlassRecord]:
        return list(self._break_glass_records.values())

    def get_workflow_summary(self) -> Dict[str, Any]:
        counts = {s: 0 for s in WorkflowStatus}
        for wf in self._workflows.values():
            counts[wf.status] = counts.get(wf.status, 0) + 1
        total = len(self._workflows)
        active = counts.get(WorkflowStatus.PENDING, 0) + counts.get(WorkflowStatus.IN_PROGRESS, 0)
        return {
            "total_workflows": total,
            "active": active,
            "by_status": {k.value: v for k, v in counts.items()},
            "break_glass_count": len(self._break_glass_records),
            "active_delegations": sum(1 for d in self._delegations.values() if d.active),
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_workflow(self, workflow_id: str) -> ApprovalWorkflow:
        if workflow_id not in self._workflows:
            raise ValueError(f"Unknown workflow: {workflow_id}")
        return self._workflows[workflow_id]

    async def _emit_event(self, event_type: str, workflow: ApprovalWorkflow) -> None:
        try:
            from backend.events.event_bus import event_bus
            from backend.events.event_models import CognitionEvent
            await event_bus.publish(CognitionEvent(
                agent="approval_center",
                event_type=event_type,
                status=workflow.status.value,
                message=f"Approval workflow {workflow.workflow_id}: {event_type}",
                execution_id=workflow.execution_id,
                payload=workflow.to_dict(),
            ))
        except Exception as exc:
            log.debug("Approval event emit failed: %s", exc)

    async def _audit(
        self,
        action: str,
        workflow: ApprovalWorkflow,
        reason: Optional[str] = None,
    ) -> None:
        try:
            from backend.safety.audit_logger import audit_logger
            audit_logger.log(
                execution_id=workflow.execution_id,
                agent="approval_center",
                action=action,
                target=f"workflow:{workflow.workflow_id}",
                risk_level=workflow.risk_level.value,
                outcome=workflow.status.value,
                reason=reason or action,
                metadata={
                    "workflow_id": workflow.workflow_id,
                    "mission_id": workflow.mission_id,
                    "policy_id": workflow.policy_id,
                    "break_glass": workflow.break_glass,
                    "current_step": workflow.current_step,
                    "steps": [s.to_dict() for s in workflow.steps],
                },
            )
        except Exception as exc:
            log.debug("Approval audit failed: %s", exc)


approval_workflow_engine = ApprovalWorkflowEngine()