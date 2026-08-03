"""
Enterprise Cost Anomaly Fix Executor
========================================

The "actually fix it" step: temporarily disable an over-spending LLM
provider via the real router primitive (llm_router.force_circuit_open —
added alongside this detector, reusing the router's existing, already-
live circuit-breaker skip logic in route() rather than inventing a
second skip path).

Approval gate: routed through the real Approval Center. Unlike a routine
container restart (reversible, doesn't touch anything live), disabling a
real LLM provider mid-operation can break real user-facing functionality
if the anomaly assessment is ever wrong — so this always requires at
least one manager approval, never auto-approves (same reasoning as
branch-protection's real merge-rule change). If blocked, the args needed
to replay this exact call are stashed in
enterprise_approval_action_dispatcher's pending-action store (keyed by
workflow_id); once a human approves via POST /api/approval-center/
workflows/{id}/approve, the dispatcher calls this function again — the
get_workflow_by_execution check below finds the now-approved workflow and
proceeds straight to the real force_circuit_open call.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

log = logging.getLogger(__name__)

ACTION_TYPE = "cost_anomaly_fix"

# How long to hold the provider's circuit open once a human approves the
# fix — long enough to actually review the ticket, unlike the router's
# own fixed 60s failure-based cooldown.
DISABLE_DURATION_SECS = 1800  # 30 minutes


async def disable_provider_temporarily(
    provider: str,
    today_cost: float,
    ticket_key: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Temporarily disable `provider` (via the router's circuit breaker)
    to stop further spend while the anomaly is investigated. Returns
    {"disabled": True, ...} on success, None if blocked pending approval
    or the attempt failed for any reason (never raises — this is a
    best-effort extra, the Jira ticket is the real actionable artifact
    regardless)."""
    from backend.approval_center.models import RiskLevel, WorkflowStatus
    from backend.approval_center.workflows import approval_workflow_engine
    from backend.llm.llm_router import llm_router

    execution_id = f"costanomaly-{provider}"
    workflow = approval_workflow_engine.get_workflow_by_execution(execution_id)
    if workflow is None:
        workflow = await approval_workflow_engine.create_workflow(
            execution_id=execution_id,
            mission_id="enterprise.cost_anomaly_autofix",
            objective=f"Temporarily disable provider {provider} (${today_cost:.2f} spent today)"[:200],
            risk_level=RiskLevel.MEDIUM,
        )
    if workflow.status not in (WorkflowStatus.APPROVED, WorkflowStatus.BREAK_GLASS):
        log.warning(
            "Cost anomaly fix for %s requires approval before applying — workflow %s "
            "is %s. Approve via POST /api/approval-center/workflows/%s/approve (or break-glass) "
            "and it will be replayed automatically.",
            provider, workflow.workflow_id, workflow.status.value, workflow.workflow_id,
        )
        from backend.services.enterprise_approval_action_dispatcher import pending_action_store
        pending_action_store.save(workflow.workflow_id, ACTION_TYPE, {
            "provider": provider, "today_cost": today_cost, "ticket_key": ticket_key,
        })
        return None

    ok = llm_router.force_circuit_open(provider, DISABLE_DURATION_SECS)
    if not ok:
        log.error("Failed to disable provider %s: not a recognized provider", provider)
        return None

    log.warning("Disabled provider %s for %ds (ticket %s)", provider, DISABLE_DURATION_SECS, ticket_key)
    return {"disabled": True, "provider": provider, "duration_secs": DISABLE_DURATION_SECS}
