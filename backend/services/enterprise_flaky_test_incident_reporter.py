"""
Enterprise Flaky Test Incident Reporter
==========================================

Turns a flaky test that's crossed its occurrence threshold into a real
Jira ticket, so a human actually owns fixing it instead of it silently
being retried forever. Same evidence-first discipline as the deploy
incident reporter: facts (occurrence history) first, any LLM-generated
hypothesis kept in its own clearly-labeled, clearly-unverified section.

Wired from: enterprise_flaky_test_detector's threshold check, once a
workflow/pipeline crosses DEFAULT_FLAKY_THRESHOLD_COUNT occurrences.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

# Independently configurable from the deploy-regression ticket target —
# an org may want flaky-test debt routed to a different project/issue
# type (e.g. "Test Debt" instead of "Bug"). Same defaults as deploy's
# incident reporter for consistency when unset.
FLAKY_JIRA_PROJECT_KEY_ENV = "FLAKY_JIRA_PROJECT_KEY"
FLAKY_JIRA_ISSUE_TYPE_ENV = "FLAKY_JIRA_ISSUE_TYPE"
DEFAULT_JIRA_PROJECT_KEY = "OPS"
DEFAULT_ISSUE_TYPE = "Bug"


def build_flaky_incident_description(
    service: str,
    workflow_name: str,
    occurrences: List[Dict[str, Any]],
    latest_evidence: str,
    hypothesis: Optional[str] = None,
) -> str:
    """Build a ticket description from real occurrence history — no
    fabricated narrative. `occurrences` is the recent history entries for
    this service+workflow (most recent first)."""
    lines = [
        f"Automated flaky-test detection flagged \"{workflow_name}\" in {service} "
        f"as flaky — it has failed and then passed on an identical re-run "
        f"{len(occurrences)} time(s) in the configured window.",
        "",
        "Most recent occurrence evidence:",
        latest_evidence,
        "",
        "Occurrence history (most recent first):",
    ]
    for occ in occurrences[:10]:
        lines.append(f"- {occ.get('detected_at', 'unknown time')} (run {occ.get('run_key', 'unknown')})")
    if len(occurrences) > 10:
        lines.append(f"... and {len(occurrences) - 10} more not shown")
    lines.append("")
    lines.append(
        "This ticket was filed automatically because the same CI job/pipeline "
        "passed on re-run with no code change — a real symptom of test "
        "unreliability, not proof of a specific cause. It should be triaged "
        "and fixed (or the underlying instability addressed) rather than "
        "left to keep auto-retrying indefinitely."
    )

    if hypothesis:
        lines.append("")
        lines.append("AI-generated hypothesis (unverified — check the job logs yourself before acting):")
        lines.append(hypothesis)

    return "\n".join(lines)


async def report_flaky_incident(
    service: str,
    workflow_name: str,
    latest_evidence: str,
    attempt_jobs: List[Dict[str, Any]],
    history_store: Optional[Any] = None,
) -> Optional[Dict[str, Any]]:
    """File a Jira ticket for a workflow/pipeline that's crossed the flaky
    threshold. Returns the created issue dict on success, None if the Jira
    connector isn't available or ticket creation failed.
    """
    from backend.connectors.registry import connector_registry

    jira = connector_registry.get("jira")
    if jira is None:
        log.warning("Jira connector not registered — cannot file flaky-test ticket for %s/%s", service, workflow_name)
        return None

    health = await jira.health()
    if health.get("status") != "available":
        log.warning("Jira connector unavailable — cannot file flaky-test ticket for %s/%s", service, workflow_name)
        return None

    from backend.services.enterprise_flaky_test_detector import flaky_test_history_store
    from backend.services.enterprise_flaky_test_root_cause_reasoner import generate_flaky_hypothesis

    store = history_store or flaky_test_history_store
    occurrences = [
        h for h in store.list_recent(limit=200)
        if h.get("service") == service and h.get("workflow_name") == workflow_name
    ]

    hypothesis = await generate_flaky_hypothesis(service, workflow_name, attempt_jobs)

    title = f"Flaky CI: {workflow_name} ({service})"
    description = build_flaky_incident_description(service, workflow_name, occurrences, latest_evidence, hypothesis)

    try:
        issue = await jira.create_issue(
            project_key=os.getenv(FLAKY_JIRA_PROJECT_KEY_ENV, DEFAULT_JIRA_PROJECT_KEY),
            issue_type=os.getenv(FLAKY_JIRA_ISSUE_TYPE_ENV, DEFAULT_ISSUE_TYPE),
            title=title,
            description=description,
        )
        log.warning("Filed flaky-test ticket for %s/%s: %s", service, workflow_name, issue.get("key", issue))
        return issue
    except Exception as exc:
        log.error("Failed to file flaky-test ticket for %s/%s: %s", service, workflow_name, exc)
        return None
