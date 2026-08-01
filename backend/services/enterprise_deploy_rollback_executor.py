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
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from backend.services.enterprise_deploy_regression_detector import RegressionVerdict
from backend.services.enterprise_deploy_rollback_store import rollback_history_store

log = logging.getLogger(__name__)


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

    try:
        result = await handler(verdict, ctx)
    except Exception as exc:
        log.warning("Automated rollback failed for %s: %s", verdict.service, exc)
        result = {"triggered": False, "error": str(exc)}

    provider = "github" if ctx.get("source") == "github_webhook" else "gitlab"
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
        environment=ctx.get("environment") or "production",
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
