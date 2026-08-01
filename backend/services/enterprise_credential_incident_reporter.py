"""
Enterprise Credential Incident Reporter
===========================================

Turns a detected credential problem (authentication failing, or a token
nearing its known expiry) into a real Jira ticket. Same discipline as the
other incident reporters: fact-only, no speculation about *why* a
credential died — that's for a human to investigate.

Wired from: enterprise_credential_monitor.check_all_credentials
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

log = logging.getLogger(__name__)

CREDENTIAL_JIRA_PROJECT_KEY_ENV = "CREDENTIAL_JIRA_PROJECT_KEY"
CREDENTIAL_JIRA_ISSUE_TYPE_ENV = "CREDENTIAL_JIRA_ISSUE_TYPE"
DEFAULT_JIRA_PROJECT_KEY = "OPS"
DEFAULT_ISSUE_TYPE = "Bug"


def build_credential_incident_description(
    connector_type: str,
    kind: str,
    error: Optional[str] = None,
    expires_at: Optional[str] = None,
    expires_at_source: Optional[str] = None,
    days_until_expiry: Optional[int] = None,
) -> str:
    lines = [f"Automated credential monitoring flagged the {connector_type} connector.", ""]

    if kind == "failing":
        lines.append(f"Authentication is currently failing: {error}")
        lines.append("")
        lines.append(
            "This means the credential is already invalid — check the token/secret "
            "configured for this connector, it may be revoked, rotated elsewhere, or expired."
        )
    else:
        lines.append(f"Token expires in {days_until_expiry} day(s) (expires_at: {expires_at}).")
        lines.append("")
        if expires_at_source == "advisory_header":
            lines.append(
                "This expiry date comes from GitHub's authentication-expiration response "
                "header, which is advisory only — GitHub has documented accuracy issues "
                "with this header for fine-grained PATs. Verify the real expiry in GitHub "
                "settings before treating this date as exact."
            )
        else:
            lines.append("This expiry date comes from the provider's own token-introspection API.")
        lines.append("Rotate the token before it expires to avoid an authentication outage.")

    lines.append("")
    lines.append("This ticket was filed automatically by credential monitoring.")
    return "\n".join(lines)


async def report_credential_incident(
    connector_type: str,
    kind: str,
    error: Optional[str] = None,
    expires_at: Optional[str] = None,
    expires_at_source: Optional[str] = None,
    days_until_expiry: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    """File a Jira ticket for a credential problem. Returns the created
    issue dict on success, None if Jira isn't available or filing failed.
    """
    from backend.connectors.registry import connector_registry

    jira = connector_registry.get("jira")
    if jira is None:
        log.warning("Jira connector not registered — cannot file credential ticket for %s", connector_type)
        return None

    health = await jira.health()
    if health.get("status") != "available":
        log.warning("Jira connector unavailable — cannot file credential ticket for %s", connector_type)
        return None

    title = (
        f"Credential failing: {connector_type}" if kind == "failing"
        else f"Credential expiring soon: {connector_type} ({days_until_expiry}d)"
    )
    description = build_credential_incident_description(
        connector_type, kind, error, expires_at, expires_at_source, days_until_expiry,
    )

    try:
        issue = await jira.create_issue(
            project_key=os.getenv(CREDENTIAL_JIRA_PROJECT_KEY_ENV, DEFAULT_JIRA_PROJECT_KEY),
            issue_type=os.getenv(CREDENTIAL_JIRA_ISSUE_TYPE_ENV, DEFAULT_ISSUE_TYPE),
            title=title,
            description=description,
        )
        log.warning("Filed credential incident ticket for %s: %s", connector_type, issue.get("key", issue))
        return issue
    except Exception as exc:
        log.error("Failed to file credential incident ticket for %s: %s", connector_type, exc)
        return None
