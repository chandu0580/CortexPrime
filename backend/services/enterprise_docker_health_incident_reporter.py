"""
Enterprise Docker Health Incident Reporter
=============================================

Turns a detected container-health gap (crash-loop, OOM-kill, dead with no
recovery) into a real Jira ticket, and — the "actually fix it" half —
optionally kicks off restarting the container via
enterprise_docker_health_fix_executor.

Wired from: enterprise_docker_health_monitor.check_all_containers
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

DOCKER_HEALTH_JIRA_PROJECT_KEY_ENV = "DOCKER_HEALTH_JIRA_PROJECT_KEY"
DOCKER_HEALTH_JIRA_ISSUE_TYPE_ENV = "DOCKER_HEALTH_JIRA_ISSUE_TYPE"
DEFAULT_JIRA_PROJECT_KEY = "OPS"
DEFAULT_ISSUE_TYPE = "Bug"

DOCKER_HEALTH_AUTO_FIX_ENV = "DOCKER_HEALTH_AUTO_FIX"


def build_docker_health_incident_description(
    container: str,
    gaps: List[Dict[str, str]],
    severity: str,
) -> str:
    lines = [
        f"Automated container health monitoring found a problem with '{container}'.",
        "",
        f"Overall severity: {severity}",
        "",
        "Gaps found:",
    ]
    for gap in gaps:
        lines.append(f"  - {gap['description']} ({gap['severity']})")
    lines.append("")
    lines.append(
        "A crash-looping or OOM-killed container is actively unavailable or "
        "unstable right now — check its logs (docker logs) and recent config/"
        "resource-limit changes."
    )
    lines.append("")
    lines.append("This ticket was filed automatically by Docker container health monitoring.")
    return "\n".join(lines)


async def report_docker_health_incident(
    container: str,
    container_id: str,
    gaps: List[Dict[str, str]],
    severity: str,
) -> Optional[Dict[str, Any]]:
    """File a Jira ticket for a detected container-health gap, and trigger
    an automated restart if auto-fix is enabled. Returns the created issue
    dict on success, None if Jira isn't available or filing failed.
    """
    from backend.connectors.registry import connector_registry

    jira = connector_registry.get("jira")
    if jira is None:
        log.warning("Jira connector not registered — cannot file docker health ticket for %s", container)
        return None

    health = await jira.health()
    if health.get("status") != "available":
        log.warning("Jira connector unavailable — cannot file docker health ticket for %s", container)
        return None

    title = f"Container health gap: {container} ({severity})"
    description = build_docker_health_incident_description(container, gaps, severity)

    try:
        issue = await jira.create_issue(
            project_key=os.getenv(DOCKER_HEALTH_JIRA_PROJECT_KEY_ENV, DEFAULT_JIRA_PROJECT_KEY),
            issue_type=os.getenv(DOCKER_HEALTH_JIRA_ISSUE_TYPE_ENV, DEFAULT_ISSUE_TYPE),
            title=title,
            description=description,
        )
        log.warning("Filed docker health incident ticket for %s: %s", container, issue.get("key", issue))
    except Exception as exc:
        log.error("Failed to file docker health incident ticket for %s: %s", container, exc)
        return None

    if os.getenv(DOCKER_HEALTH_AUTO_FIX_ENV, "false").lower() == "true":
        try:
            from backend.services.enterprise_docker_health_fix_executor import restart_crashlooping_container

            await restart_crashlooping_container(
                container_name=container, container_id=container_id, ticket_key=issue.get("key"),
            )
        except Exception as exc:
            log.error("Auto-fix attempt failed for %s: %s", container, exc)

    return issue
