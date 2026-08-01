"""
Enterprise Deploy Incident Reporter
=====================================

Turns a detected deploy regression into a real Jira ticket. The evidence
section is always fact-only, pulled directly from the RegressionVerdict
and the GitHub webhook context — no LLM involved. If an LLM-generated
root-cause hypothesis is available (see
enterprise_deploy_root_cause_reasoner.generate_hypothesis), it's included
as a clearly separate, clearly labeled section — never blended into the
evidence, never presented as a confirmed cause.

Wired from: backend.services.enterprise_github_integration._check_deploy_regression
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

from backend.services.enterprise_deploy_regression_detector import RegressionVerdict

log = logging.getLogger(__name__)

# "OPS" was a placeholder project key that doesn't exist in every Jira
# instance — real instances have whatever project(s) their org actually
# created. Configurable per-deployment rather than hardcoded.
DEPLOY_JIRA_PROJECT_KEY_ENV = "DEPLOY_JIRA_PROJECT_KEY"
DEPLOY_JIRA_ISSUE_TYPE_ENV = "DEPLOY_JIRA_ISSUE_TYPE"
DEFAULT_JIRA_PROJECT_KEY = "OPS"
DEFAULT_ISSUE_TYPE = "Bug"


def build_incident_description(
    verdict: RegressionVerdict,
    ctx: Dict[str, Any],
    hypothesis: Optional[str] = None,
) -> str:
    """Build a ticket description from real measured evidence — no fabricated narrative.

    `hypothesis`, if given, is an LLM-generated root-cause guess grounded in
    the actual deployed diff — kept in its own clearly-labeled section, never
    mixed into the fact-only evidence above it.
    """
    lines = [
        f"Automated regression detection flagged deployment {verdict.deployment_id} to {verdict.service}.",
        "",
        "Evidence:",
    ]
    lines.extend(f"- {reason}" for reason in verdict.reasons)
    lines.append("")

    if verdict.before and verdict.after:
        lines.append(
            f"Before window — p95 latency: {verdict.before.p95_latency_seconds}, "
            f"error rate: {verdict.before.error_rate}"
        )
        lines.append(
            f"After window — p95 latency: {verdict.after.p95_latency_seconds}, "
            f"error rate: {verdict.after.error_rate}"
        )
        lines.append("")

    lines.append(f"Environment: {ctx.get('environment', 'unknown')}")
    lines.append(f"Triggered by: {ctx.get('sender', 'unknown')}")
    log_url = ctx.get("deployment_log_url", "")
    if log_url:
        lines.append(f"Deployment log: {log_url}")
    lines.append("")
    lines.append(
        "This ticket was filed automatically. It reports a statistical correlation "
        "between this deployment and the metric changes above — it is not a "
        "confirmed root cause and should be verified before action is taken."
    )

    if hypothesis:
        lines.append("")
        lines.append("AI-generated root-cause hypothesis (unverified — read the diff yourself before acting):")
        lines.append(hypothesis)

    return "\n".join(lines)


async def report_incident(verdict: RegressionVerdict, ctx: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """File a Jira ticket for a detected regression.

    Returns the created issue dict on success, None if there was nothing to
    report, the Jira connector isn't available, or ticket creation failed.
    """
    if not verdict.regressed:
        return None

    from backend.connectors.registry import connector_registry

    jira = connector_registry.get("jira")
    if jira is None:
        log.warning("Jira connector not registered — cannot file incident ticket for %s", verdict.service)
        return None

    health = await jira.health()
    if health.get("status") != "available":
        log.warning("Jira connector unavailable — cannot file incident ticket for %s", verdict.service)
        return None

    from backend.services.enterprise_deploy_root_cause_reasoner import generate_hypothesis

    hypothesis = await generate_hypothesis(verdict, ctx)

    title = f"Deploy regression: {verdict.service} (deployment {verdict.deployment_id})"
    description = build_incident_description(verdict, ctx, hypothesis)

    try:
        issue = await jira.create_issue(
            project_key=os.getenv(DEPLOY_JIRA_PROJECT_KEY_ENV, DEFAULT_JIRA_PROJECT_KEY),
            issue_type=os.getenv(DEPLOY_JIRA_ISSUE_TYPE_ENV, DEFAULT_ISSUE_TYPE),
            title=title,
            description=description,
        )
        log.warning("Filed incident ticket for %s: %s", verdict.service, issue.get("key", issue))
        return issue
    except Exception as exc:
        log.error("Failed to file incident ticket for %s: %s", verdict.service, exc)
        return None
