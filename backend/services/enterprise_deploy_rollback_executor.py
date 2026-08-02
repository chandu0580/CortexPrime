"""
Deploy Rollback Executor
===========================

The automated-remediation half of deploy-regression detection. When
enterprise_deploy_regression_detector.DeployRegressionDetector confirms a
regression, this module finds the last known-good deployment for the same
service+environment and triggers a fresh redeploy at that ref — GitHub via
a new Deployment (the standard way to signal a real CD listener to act),
GitLab via a new pipeline run — so the bad deploy is rolled back without
waiting on a human.

Provider dispatch reads ctx["source"], mirroring the pattern already used
by enterprise_deploy_root_cause_reasoner._DIFF_FETCHERS, since
_run_deploy_regression_check (enterprise_github_integration.py) is called
verbatim by both GitHub and GitLab wiring — the shared function has no
other way to know which provider a given ctx came from.

Scope note: this triggers the rollback and records that the trigger
succeeded or failed. It does not track whether the resulting redeploy
itself later completes successfully — that's a distinct, larger piece of
work (a second webhook-driven closed loop), not silently folded in here.

Approval gate: before actually touching anything, this routes through the
real Approval Center (backend.approval_center) — a production rollback is
always at least MEDIUM risk, escalating to HIGH (manager + executive
approval) for a production/prod/live/critical environment, which is the
common case here. Only an APPROVED or BREAK_GLASS workflow proceeds to the
actual rollback; otherwise this stashes the minimal args needed to replay
the rollback in enterprise_approval_action_dispatcher's pending-action
store (keyed by workflow_id) and records a "blocked pending approval"
entry. Once a human approves via POST /api/approval-center/workflows/{id}
/approve, the dispatcher's EventBus subscription picks up the resulting
approval_workflow_completed event and replays this exact rollback for
real — approving is not a dead end.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from backend.approval_center.models import RiskLevel, WorkflowStatus
from backend.approval_center.policies import assess_risk_from_context
from backend.approval_center.workflows import approval_workflow_engine
from backend.services.enterprise_deploy_regression_detector import RegressionVerdict
from backend.services.enterprise_deploy_rollback_store import rollback_history_store

log = logging.getLogger(__name__)

ACTION_TYPE = "rollback"


async def _rollback_via_github(verdict: RegressionVerdict, ctx: Dict[str, Any]) -> Dict[str, Any]:
    from backend.connectors.registry import connector_registry

    environment = ctx.get("environment") or "production"
    gh = connector_registry.get("github")
    if gh is None:
        return {"triggered": False, "error": "GitHub connector not registered"}

    parts = verdict.service.split("/", 1)
    if len(parts) != 2:
        return {"triggered": False, "error": f"Unrecognized service format: {verdict.service}"}
    owner, repo = parts

    try:
        bad_deployment_id: Optional[int] = int(verdict.deployment_id)
    except (TypeError, ValueError):
        bad_deployment_id = None

    good = await gh.get_last_successful_deployment(owner, repo, environment, before_deployment_id=bad_deployment_id)
    if not good:
        return {"triggered": False, "error": "No known-good deployment found to roll back to"}

    sha = good.get("sha")
    if not sha:
        return {"triggered": False, "error": "Known-good deployment had no sha"}

    deployment = await gh.create_deployment(
        owner, repo, ref=sha, environment=environment, task="rollback",
        description=f"Automated rollback from deployment {verdict.deployment_id} — {'; '.join(verdict.reasons)}"[:255],
    )
    return {
        "triggered": True,
        "target_sha": sha,
        "target_deployment_id": good.get("id"),
        "rollback_deployment_id": deployment.get("id"),
    }


async def _rollback_via_gitlab(verdict: RegressionVerdict, ctx: Dict[str, Any]) -> Dict[str, Any]:
    from backend.connectors.registry import connector_registry

    environment = ctx.get("environment") or "production"
    gl = connector_registry.get("gitlab_ci")
    if gl is None:
        return {"triggered": False, "error": "GitLab connector not registered"}

    project_id = ctx.get("project_id")
    if not project_id:
        return {"triggered": False, "error": "No project_id in ctx"}

    try:
        bad_deployment_id: Optional[int] = int(verdict.deployment_id)
    except (TypeError, ValueError):
        bad_deployment_id = None

    good = await gl.get_last_successful_deployment(project_id, environment, before_deployment_id=bad_deployment_id)
    if not good:
        return {"triggered": False, "error": "No known-good deployment found to roll back to"}

    sha = good.get("sha") or good.get("ref")
    if not sha:
        return {"triggered": False, "error": "Known-good deployment had no sha/ref"}

    pipeline = await gl.create_pipeline(
        project_id, ref=sha,
        variables={"ROLLBACK": "true", "ROLLBACK_REASON": "; ".join(verdict.reasons)[:255]},
    )
    return {
        "triggered": True,
        "target_sha": sha,
        "target_deployment_id": good.get("id"),
        "rollback_deployment_id": pipeline.get("id"),
    }


_ROLLBACK_HANDLERS = {
    "github_webhook": _rollback_via_github,
    "gitlab_webhook": _rollback_via_gitlab,
}


async def _execute_rollback(verdict: RegressionVerdict, ctx: Dict[str, Any], ticket_key: Optional[str] = None) -> Dict[str, Any]:
    """The real action, run only once a workflow is APPROVED/BREAK_GLASS —
    called directly by trigger_rollback on the happy path, and by
    replay_rollback (via the approval-action dispatcher) once a
    previously-blocked rollback gets approved."""
    handler = _ROLLBACK_HANDLERS[ctx["source"]]
    environment = ctx.get("environment") or "production"
    provider = "github" if ctx.get("source") == "github_webhook" else "gitlab"

    try:
        result = await handler(verdict, ctx)
    except Exception as exc:
        log.warning("Automated rollback failed for %s: %s", verdict.service, exc)
        result = {"triggered": False, "error": str(exc)}

    if result.get("triggered"):
        log.warning(
            "Automated rollback triggered for %s (deployment %s) -> sha %s",
            verdict.service, verdict.deployment_id, result.get("target_sha"),
        )
    else:
        log.warning(
            "Automated rollback not triggered for %s (deployment %s): %s",
            verdict.service, verdict.deployment_id, result.get("error"),
        )

    recorded = rollback_history_store.record(
        provider=provider,
        service=verdict.service,
        environment=environment,
        bad_deployment_id=verdict.deployment_id,
        reasons=verdict.reasons,
        triggered=result.get("triggered", False),
        target_sha=result.get("target_sha"),
        target_deployment_id=result.get("target_deployment_id"),
        rollback_deployment_id=result.get("rollback_deployment_id"),
        ticket_key=ticket_key,
        error=result.get("error"),
    )

    try:
        from backend.services.enterprise_alert_correlator import attach_signal
        summary = (
            f"Rollback to {result.get('target_sha')} triggered" if result.get("triggered")
            else f"Rollback not triggered: {result.get('error')}"
        )
        await attach_signal(source="rollback", service=verdict.service, summary=summary,
                             severity="info" if result.get("triggered") else "warning")
    except Exception as exc:
        log.debug("Incident signal attach skipped for %s: %s", verdict.service, exc)

    return recorded


async def replay_rollback(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Reconstruct a minimal RegressionVerdict from a stashed pending-action
    payload and run the real rollback. Called by
    enterprise_approval_action_dispatcher once a blocked rollback's
    workflow becomes APPROVED/BREAK_GLASS."""
    verdict = RegressionVerdict(
        service=payload["service"], deployment_id=payload["deployment_id"],
        regressed=True, reasons=payload["reasons"],
    )
    return await _execute_rollback(verdict, payload["ctx"], payload.get("ticket_key"))


async def trigger_rollback(verdict: RegressionVerdict, ctx: Dict[str, Any], ticket_key: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Attempt an automated rollback for a confirmed regression and record
    the outcome. Returns the history entry, or None if verdict isn't a
    regression or the source is unrecognized — callers must not treat a
    "triggered": False entry as an exception, just an informative record
    of why no rollback happened (e.g. no known-good target)."""
    if not verdict.regressed:
        return None

    handler = _ROLLBACK_HANDLERS.get(ctx.get("source"))
    if handler is None:
        log.debug("Rollback skipped — unrecognized ctx source: %s", ctx.get("source"))
        return None

    environment = ctx.get("environment") or "production"
    provider = "github" if ctx.get("source") == "github_webhook" else "gitlab"
    execution_id = f"rollback-{verdict.service}-{verdict.deployment_id}"

    workflow = approval_workflow_engine.get_workflow_by_execution(execution_id)
    if workflow is None:
        workflow = await approval_workflow_engine.create_workflow(
            execution_id=execution_id,
            mission_id="enterprise.automated_rollback",
            objective=f"Automated rollback of {verdict.service} (deployment {verdict.deployment_id}): "
                      f"{'; '.join(verdict.reasons)}"[:200],
            risk_level=assess_risk_from_context(
                RiskLevel.MEDIUM, target_environment=environment, affected_systems=[verdict.service],
            ),
        )

    if workflow.status not in (WorkflowStatus.APPROVED, WorkflowStatus.BREAK_GLASS):
        log.warning(
            "Rollback for %s (deployment %s) requires approval before executing — workflow %s "
            "is %s. Approve via POST /api/approval-center/workflows/%s/approve (or break-glass) "
            "and it will be replayed automatically.",
            verdict.service, verdict.deployment_id, workflow.workflow_id, workflow.status.value, workflow.workflow_id,
        )
        from backend.services.enterprise_approval_action_dispatcher import pending_action_store
        pending_action_store.save(workflow.workflow_id, ACTION_TYPE, {
            "service": verdict.service, "deployment_id": verdict.deployment_id,
            "reasons": verdict.reasons, "ctx": ctx, "ticket_key": ticket_key,
        })
        recorded = rollback_history_store.record(
            provider=provider,
            service=verdict.service,
            environment=environment,
            bad_deployment_id=verdict.deployment_id,
            reasons=verdict.reasons,
            triggered=False,
            ticket_key=ticket_key,
            error=f"Awaiting approval (workflow {workflow.workflow_id}, status {workflow.status.value})",
        )
        try:
            from backend.services.enterprise_alert_correlator import attach_signal
            await attach_signal(
                source="rollback", service=verdict.service,
                summary=f"Rollback blocked pending approval (workflow {workflow.workflow_id})",
                severity="warning",
            )
        except Exception as exc:
            log.debug("Incident signal attach skipped for %s: %s", verdict.service, exc)
        return recorded

    return await _execute_rollback(verdict, ctx, ticket_key)
