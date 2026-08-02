"""
Enterprise Branch Protection Incident Reporter
=================================================

Turns a detected branch-protection gap into a real Jira ticket, and —
the "actually fix it" half — optionally kicks off enabling a minimal
protection baseline via enterprise_branch_protection_fix_executor.

Wired from: enterprise_branch_protection_monitor.check_all_repos
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

BRANCH_PROTECTION_JIRA_PROJECT_KEY_ENV = "BRANCH_PROTECTION_JIRA_PROJECT_KEY"
BRANCH_PROTECTION_JIRA_ISSUE_TYPE_ENV = "BRANCH_PROTECTION_JIRA_ISSUE_TYPE"
DEFAULT_JIRA_PROJECT_KEY = "OPS"
DEFAULT_ISSUE_TYPE = "Bug"

BRANCH_PROTECTION_AUTO_FIX_ENV = "BRANCH_PROTECTION_AUTO_FIX"


def build_branch_protection_incident_description(
    owner: str,
    repo: str,
    branch: str,
    gaps: List[Dict[str, str]],
    severity: str,
) -> str:
    lines = [
        f"Automated branch protection monitoring found a governance gap on {owner}/{repo}@{branch}.",
        "",
        f"Overall severity: {severity}",
        "",
        "Gaps found:",
    ]
    for gap in gaps:
        lines.append(f"  - {gap['description']} ({gap['severity']})")
    lines.append("")
    lines.append(
        "This means a change can reach this branch without the safety checks a "
        "team would normally rely on — review and tighten branch protection "
        "settings (Settings -> Branches) unless this is intentional."
    )
    lines.append("")
    lines.append("This ticket was filed automatically by branch protection monitoring.")
    return "\n".join(lines)


async def report_branch_protection_incident(
    owner: str,
    repo: str,
    branch: str,
    gaps: List[Dict[str, str]],
    severity: str,
) -> Optional[Dict[str, Any]]:
    """File a Jira ticket for a detected branch-protection gap, and trigger
    an automated fix if auto-fix is enabled. Returns the created issue dict
    on success, None if Jira isn't available or filing failed.
    """
    from backend.connectors.registry import connector_registry

    jira = connector_registry.get("jira")
    if jira is None:
        log.warning("Jira connector not registered — cannot file branch protection ticket for %s/%s", owner, repo)
        return None

    health = await jira.health()
    if health.get("status") != "available":
        log.warning("Jira connector unavailable — cannot file branch protection ticket for %s/%s", owner, repo)
        return None

    title = f"Branch protection gap: {owner}/{repo}@{branch} ({severity})"
    description = build_branch_protection_incident_description(owner, repo, branch, gaps, severity)

    try:
        issue = await jira.create_issue(
            project_key=os.getenv(BRANCH_PROTECTION_JIRA_PROJECT_KEY_ENV, DEFAULT_JIRA_PROJECT_KEY),
            issue_type=os.getenv(BRANCH_PROTECTION_JIRA_ISSUE_TYPE_ENV, DEFAULT_ISSUE_TYPE),
            title=title,
            description=description,
        )
        log.warning("Filed branch protection incident ticket for %s/%s@%s: %s", owner, repo, branch, issue.get("key", issue))
    except Exception as exc:
        log.error("Failed to file branch protection incident ticket for %s/%s@%s: %s", owner, repo, branch, exc)
        return None

    if os.getenv(BRANCH_PROTECTION_AUTO_FIX_ENV, "false").lower() == "true":
        try:
            from backend.services.enterprise_branch_protection_fix_executor import enable_minimal_protection

            await enable_minimal_protection(
                owner=owner, repo=repo, branch=branch, ticket_key=issue.get("key"),
            )
        except Exception as exc:
            log.error("Auto-fix attempt failed for %s/%s@%s: %s", owner, repo, branch, exc)

    return issue
