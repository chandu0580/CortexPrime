"""
Enterprise Docker Health Fix Executor
========================================

The "actually fix it" step: restart a crash-looping or OOM-killed container
via the real Docker connector primitive (restart_container — added
alongside this detector; DockerConnector was 100% read-only before today).

Approval gate: routed through the real Approval Center. A container
restart is routine and reversible (that's literally what `restart:
unless-stopped` does automatically in production) — unlike a real
branch-protection-rule change, so this defaults to LOW risk (auto-approves,
same as the vulnerability auto-fix PR path), and is only escalated to
MEDIUM when the container is one of this repo's own data-plane services
(postgres/redis/rabbitmq/neo4j — see
enterprise_docker_health_monitor.is_critical_container), since restarting
one of those does affect live running state (dropped connections, brief
unavailability). If blocked, the args needed to replay this exact call are
stashed in enterprise_approval_action_dispatcher's pending-action store
(keyed by workflow_id); once approved via POST /api/approval-center/
workflows/{id}/approve, the dispatcher calls this function again — the
get_workflow_by_execution check below finds the now-approved workflow and
proceeds straight to the real restart_container call.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

log = logging.getLogger(__name__)

ACTION_TYPE = "docker_health_fix"


async def restart_crashlooping_container(
    container_name: str,
    container_id: str,
    ticket_key: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Restart `container_name` (identified by container_id) to recover it
    from a crash-loop or OOM-kill. Returns {"restarted": True, ...} on
    success, None if blocked pending approval or the attempt failed for any
    reason (never raises — this is a best-effort extra, the Jira ticket is
    the real actionable artifact regardless)."""
    from backend.approval_center.models import RiskLevel, WorkflowStatus
    from backend.approval_center.policies import assess_risk_from_context
    from backend.approval_center.workflows import approval_workflow_engine
    from backend.connectors.registry import connector_registry
    from backend.services.enterprise_docker_health_monitor import is_critical_container

    execution_id = f"dockerhealth-{container_name}"
    workflow = approval_workflow_engine.get_workflow_by_execution(execution_id)
    if workflow is None:
        # assess_risk_from_context's affected_systems check only escalates
        # MEDIUM->HIGH / HIGH->CRITICAL, never LOW->MEDIUM (matches
        # vulnerability_fix_executor's pattern) — so the base risk itself
        # must already be MEDIUM for this repo's own data-plane containers.
        # Not also passing affected_systems here: that would stack a SECOND
        # escalation (MEDIUM->HIGH) on top of the one already applied via
        # base_risk, which isn't the intent — assess_risk_from_context is
        # kept only for its other context (target_environment) checks.
        base_risk = RiskLevel.MEDIUM if is_critical_container(container_name) else RiskLevel.LOW
        risk_level = assess_risk_from_context(base_risk)
        workflow = await approval_workflow_engine.create_workflow(
            execution_id=execution_id,
            mission_id="enterprise.docker_health_autofix",
            objective=f"Restart crash-looping/OOM-killed container {container_name}"[:200],
            risk_level=risk_level,
        )
    if workflow.status not in (WorkflowStatus.APPROVED, WorkflowStatus.BREAK_GLASS):
        log.warning(
            "Docker health fix for %s requires approval before applying — workflow %s "
            "is %s. Approve via POST /api/approval-center/workflows/%s/approve (or break-glass) "
            "and it will be replayed automatically.",
            container_name, workflow.workflow_id, workflow.status.value, workflow.workflow_id,
        )
        from backend.services.enterprise_approval_action_dispatcher import pending_action_store
        pending_action_store.save(workflow.workflow_id, ACTION_TYPE, {
            "container_name": container_name, "container_id": container_id, "ticket_key": ticket_key,
        })
        return None

    docker = connector_registry.get("docker")
    if docker is None:
        return None

    try:
        await docker.restart_container(container_id)
        log.warning("Restarted container %s (ticket %s)", container_name, ticket_key)
        return {"restarted": True, "container": container_name, "container_id": container_id}
    except Exception as exc:
        log.error("Failed to restart container %s: %s", container_name, exc)
        return None
