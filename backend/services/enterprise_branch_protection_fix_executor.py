"""
Enterprise Branch Protection Fix Executor
============================================

The "actually fix it" step: enable a minimal, sane branch-protection
baseline on a repo's branch via the real GitHub connector primitives
(get_branch_protection/update_branch_protection — both already existed,
just never wired to anything before tonight).

Minimal baseline applied: require at least 1 approving PR review, and
enforce that rule for admins too (no bypass). Deliberately does NOT force
specific required status-check contexts — we don't know which CI checks
exist for an arbitrary repo, and requiring a nonexistent check name would
permanently block merges rather than protect anything.

Approval gate: routed through the real Approval Center. Unlike the
vulnerability auto-fix PR (reversible, doesn't touch anything running),
changing a repo's real merge rules is a genuine workflow-affecting action
— it changes how every future PR on this branch gets merged — so this
always requires at least one manager approval, never auto-approves.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

log = logging.getLogger(__name__)


async def enable_minimal_protection(
    owner: str,
    repo: str,
    branch: str,
    ticket_key: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Enable a minimal branch-protection baseline (1 required PR approval,
    enforced for admins too) on `branch`. Returns the updated protection
    dict on success, None if blocked pending approval or the attempt
    failed for any reason (never raises — this is a best-effort extra, the
    Jira ticket is the real actionable artifact regardless)."""
    from backend.approval_center.models import RiskLevel, WorkflowStatus
    from backend.approval_center.workflows import approval_workflow_engine
    from backend.connectors.registry import connector_registry

    workflow = await approval_workflow_engine.create_workflow(
        execution_id=f"branchprotect-{owner}-{repo}-{branch}",
        mission_id="enterprise.branch_protection_autofix",
        objective=f"Enable minimal branch protection on {owner}/{repo}@{branch}"[:200],
        risk_level=RiskLevel.MEDIUM,
    )
    if workflow.status not in (WorkflowStatus.APPROVED, WorkflowStatus.BREAK_GLASS):
        log.warning(
            "Branch protection fix for %s/%s@%s requires approval before applying — workflow %s "
            "is %s. Approve via POST /api/approval-center/workflows/%s/approve (or break-glass).",
            owner, repo, branch, workflow.workflow_id, workflow.status.value, workflow.workflow_id,
        )
        return None

    gh = connector_registry.get("github")
    if gh is None:
        return None

    try:
        result = await gh.update_branch_protection(
            owner, repo, branch,
            required_status_checks=None,
            enforce_admins=True,
            required_pull_request_reviews={"required_approving_review_count": 1},
            restrictions=None,
        )
        log.warning("Enabled minimal branch protection on %s/%s@%s (ticket %s)", owner, repo, branch, ticket_key)
        return result
    except Exception as exc:
        log.error("Failed to enable branch protection on %s/%s@%s: %s", owner, repo, branch, exc)
        return None
