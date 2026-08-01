"""
Enterprise Alert Incident Reporter
======================================

When enterprise_alert_correlator.correlate_and_report suppresses a
duplicate ticket for a correlated signal, this adds a comment to the
ORIGINAL ticket instead — the actual noise-reduction payoff: one ticket
per incident, with each further correlated signal appended to it rather
than spawning its own.

Wired from: enterprise_alert_correlator.correlate_and_report
"""
from __future__ import annotations

import logging
from typing import Optional

log = logging.getLogger(__name__)


def build_correlated_comment(source: str, summary: str, hypothesis: Optional[str] = None) -> str:
    lines = [
        f"Correlated alert: {source} — {summary}",
        "",
        "This signal fired for the same service within the correlation window of "
        "an already-open incident, so no separate ticket was filed for it.",
    ]
    if hypothesis:
        lines.append("")
        lines.append("AI-generated hypothesis tying this to the incident (unverified):")
        lines.append(hypothesis)
    return "\n".join(lines)


async def comment_correlated_signal(
    ticket_key: str,
    source: str,
    summary: str,
    hypothesis: Optional[str] = None,
) -> bool:
    """Add a comment linking a suppressed duplicate signal to its incident's
    original ticket. Returns True on success, False if the Jira connector
    isn't available or the comment failed — never raises, since a missed
    comment shouldn't break the correlation itself.
    """
    from backend.connectors.registry import connector_registry

    jira = connector_registry.get("jira")
    if jira is None:
        log.warning("Jira connector not registered — cannot comment on %s", ticket_key)
        return False

    health = await jira.health()
    if health.get("status") != "available":
        log.warning("Jira connector unavailable — cannot comment on %s", ticket_key)
        return False

    try:
        await jira.add_comment(ticket_key, build_correlated_comment(source, summary, hypothesis))
        log.warning("Added correlated-signal comment to %s (%s: %s)", ticket_key, source, summary)
        return True
    except Exception as exc:
        log.error("Failed to comment correlated signal on %s: %s", ticket_key, exc)
        return False
