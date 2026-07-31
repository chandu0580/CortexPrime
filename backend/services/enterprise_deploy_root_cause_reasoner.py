"""
Enterprise Deploy Root Cause Reasoner
=======================================

When a deploy regression is detected, this pulls the actual commit that
was deployed (message + diff) and asks an LLM to form a genuine
root-cause hypothesis grounded in that diff and the measured evidence —
not a canned template, and not confident speculation beyond what the
diff actually supports. If the diff doesn't obviously explain the
regression, the model is explicitly instructed to say so rather than
invent a plausible-sounding story.

Wired from: backend.services.enterprise_deploy_incident_reporter.report_incident
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from backend.services.enterprise_deploy_regression_detector import RegressionVerdict

log = logging.getLogger(__name__)

MAX_FILES = 8
MAX_PATCH_CHARS_PER_FILE = 2000

SYSTEM_PROMPT = (
    "You are a senior site reliability engineer investigating a production "
    "regression. You will be given measured evidence (before/after metrics) "
    "and the actual code diff that was deployed. Form a root-cause hypothesis "
    "ONLY if the diff plausibly explains the measured regression. If the diff "
    "doesn't obviously explain it, say so plainly instead of guessing "
    "confidently — an honest 'unclear from this diff' is more useful than a "
    "fabricated-sounding explanation. Be concise: 2-4 sentences, then one "
    "line for a suggested fix or next investigation step if you have one."
)


def _build_diff_summary(commit: Dict[str, Any]) -> str:
    message = commit.get("commit", {}).get("message", "")
    files = commit.get("files", []) or []
    lines = [f"Commit message: {message}", "", f"Files changed: {len(files)}"]
    for f in files[:MAX_FILES]:
        filename = f.get("filename", "unknown")
        status = f.get("status", "")
        patch = (f.get("patch") or "")[:MAX_PATCH_CHARS_PER_FILE]
        lines.append(f"\n--- {filename} ({status}) ---")
        lines.append(patch or "(no textual diff available — binary or too large)")
    if len(files) > MAX_FILES:
        lines.append(f"\n... and {len(files) - MAX_FILES} more file(s) not shown")
    return "\n".join(lines)


def build_prompt(verdict: RegressionVerdict, diff_summary: str) -> str:
    evidence = "\n".join(f"- {r}" for r in verdict.reasons)
    return (
        f"Service: {verdict.service}\n"
        f"Deployment: {verdict.deployment_id}\n\n"
        f"Measured regression evidence:\n{evidence}\n\n"
        f"Deployed code diff:\n{diff_summary}\n\n"
        "What, if anything, in this diff plausibly explains the measured regression?"
    )


async def generate_hypothesis(verdict: RegressionVerdict, ctx: Dict[str, Any]) -> Optional[str]:
    """Return an LLM-generated root-cause hypothesis grounded in the actual
    deployed diff, or None if the commit/diff couldn't be fetched or the
    LLM call failed. Never raises — this is a best-effort enrichment, not
    a required step in filing an incident.
    """
    if not verdict.regressed:
        return None

    repo_full_name = ctx.get("repo_full_name", "")
    if "/" not in repo_full_name:
        return None
    owner, repo = repo_full_name.split("/", 1)

    try:
        from backend.connectors.registry import connector_registry

        gh = connector_registry.get("github")
        if gh is None:
            return None

        deployment = await gh.get_deployment(owner, repo, int(verdict.deployment_id))
        sha = deployment.get("sha", "")
        if not sha:
            return None

        commit = await gh.get_commit(owner, repo, sha)
        diff_summary = _build_diff_summary(commit)
    except Exception as exc:
        log.debug("Root cause reasoning: could not fetch commit diff for %s: %s", verdict.service, exc)
        return None

    try:
        from backend.llm.llm_router import TaskType, llm_router

        prompt = build_prompt(verdict, diff_summary)
        result = await llm_router.route(
            prompt=prompt,
            system=SYSTEM_PROMPT,
            task_type=TaskType.REASONING,
            agent_type="deploy_root_cause_reasoner",
        )
        if not result.success:
            log.debug("Root cause reasoning: LLM call failed for %s: %s", verdict.service, result.error)
            return None
        return result.output
    except Exception as exc:
        log.debug("Root cause reasoning: LLM call raised for %s: %s", verdict.service, exc)
        return None
