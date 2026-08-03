"""
Enterprise Cost Anomaly Incident Reporter
=============================================

Turns a detected LLM-provider spend spike into a real Jira ticket, and —
the "actually fix it" half — optionally kicks off temporarily disabling
the provider via enterprise_cost_anomaly_fix_executor.

Wired from: enterprise_cost_anomaly_monitor.check_all_providers
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

COST_ANOMALY_JIRA_PROJECT_KEY_ENV = "COST_ANOMALY_JIRA_PROJECT_KEY"
COST_ANOMALY_JIRA_ISSUE_TYPE_ENV = "COST_ANOMALY_JIRA_ISSUE_TYPE"
DEFAULT_JIRA_PROJECT_KEY = "OPS"
DEFAULT_ISSUE_TYPE = "Bug"

COST_ANOMALY_AUTO_FIX_ENV = "COST_ANOMALY_AUTO_FIX"


def build_cost_anomaly_incident_description(
    provider: str,
    today_cost: float,
    gaps: List[Dict[str, str]],
    severity: str,
) -> str:
    lines = [
        f"Automated cost monitoring found a spend anomaly for provider '{provider}'.",
        "",
        f"Today's spend: ${today_cost:.4f}",
        f"Overall severity: {severity}",
        "",
        "Gaps found:",
    ]
    for gap in gaps:
        lines.append(f"  - {gap['description']} ({gap['severity']})")
    lines.append("")
    lines.append(
        "A sudden spend spike usually means a runaway loop, a misconfigured "
        "model, or a leaked API key being abused — check recent mission "
        "activity and token usage for this provider."
    )
    lines.append("")
    lines.append("This ticket was filed automatically by cost anomaly monitoring.")
    return "\n".join(lines)


async def report_cost_anomaly_incident(
    provider: str,
    today_cost: float,
    gaps: List[Dict[str, str]],
    severity: str,
) -> Optional[Dict[str, Any]]:
    """File a Jira ticket for a detected cost anomaly, and trigger an
    automated provider disable if auto-fix is enabled. Returns the created
    issue dict on success, None if Jira isn't available or filing failed.
    """
    from backend.connectors.registry import connector_registry

    jira = connector_registry.get("jira")
    if jira is None:
        log.warning("Jira connector not registered — cannot file cost anomaly ticket for %s", provider)
        return None

    health = await jira.health()
    if health.get("status") != "available":
        log.warning("Jira connector unavailable — cannot file cost anomaly ticket for %s", provider)
        return None

    title = f"Cost anomaly: {provider} (${today_cost:.2f} today, {severity})"
    description = build_cost_anomaly_incident_description(provider, today_cost, gaps, severity)

    try:
        issue = await jira.create_issue(
            project_key=os.getenv(COST_ANOMALY_JIRA_PROJECT_KEY_ENV, DEFAULT_JIRA_PROJECT_KEY),
            issue_type=os.getenv(COST_ANOMALY_JIRA_ISSUE_TYPE_ENV, DEFAULT_ISSUE_TYPE),
            title=title,
            description=description,
        )
        log.warning("Filed cost anomaly incident ticket for %s: %s", provider, issue.get("key", issue))
    except Exception as exc:
        log.error("Failed to file cost anomaly incident ticket for %s: %s", provider, exc)
        return None

    if os.getenv(COST_ANOMALY_AUTO_FIX_ENV, "false").lower() == "true":
        try:
            from backend.services.enterprise_cost_anomaly_fix_executor import disable_provider_temporarily

            await disable_provider_temporarily(
                provider=provider, today_cost=today_cost, ticket_key=issue.get("key"),
            )
        except Exception as exc:
            log.error("Auto-fix attempt failed for %s: %s", provider, exc)

    return issue
