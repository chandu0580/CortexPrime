"""
Enterprise Flaky Test Root Cause Reasoner
============================================

When a CI failure is confirmed flaky (failed, then passed on a real
re-run with no code change — see enterprise_flaky_test_detector), this
asks an LLM to hypothesize *why*, grounded in which job/step actually
failed and on which attempt. Same discipline as the deploy-regression
reasoner: an honest "unclear from this evidence" beats a confident-sounding
guess, since the evidence here (job/step names, not full logs) is thinner
than a code diff.

Wired from: enterprise_flaky_test_incident_reporter.report_flaky_incident
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from backend.services.enterprise_flaky_test_detector import summarize_evidence

log = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are a senior software engineer investigating a flaky CI failure. "
    "You will be given which job/step failed on the first run, and which "
    "job/step (if any) failed or passed on a real re-run of the identical "
    "code. Form a hypothesis for why this might be flaky ONLY if the "
    "job/step names plausibly suggest a cause (e.g. a step named "
    "'integration tests' suggests network/external-service timing; "
    "'parallel' or 'concurrent' in a name suggests a race condition). If "
    "the evidence doesn't suggest anything specific, say so plainly rather "
    "than inventing a plausible-sounding explanation — this evidence is "
    "thinner than a full log or diff, so honesty about that limit matters "
    "more here, not less. Be concise: 2-3 sentences, then one line "
    "suggesting what log/artifact a human should check next."
)




def build_prompt(service: str, workflow_name: str, evidence_summary: str) -> str:
    return (
        f"Service: {service}\n"
        f"Workflow/pipeline: {workflow_name}\n\n"
        f"Job/step evidence across attempts:\n{evidence_summary}\n\n"
        "What, if anything, does this evidence suggest about why this is flaky?"
    )


async def generate_flaky_hypothesis(
    service: str,
    workflow_name: str,
    attempt_jobs: List[Dict[str, Any]],
) -> Optional[str]:
    """Return an LLM-generated flakiness hypothesis, or None if there's no
    usable evidence or the LLM call failed. Never raises — best-effort
    enrichment, not required to record a flaky occurrence or file a ticket.
    """
    evidence_summary = summarize_evidence(attempt_jobs)

    try:
        from backend.llm.llm_router import TaskType, llm_router

        prompt = build_prompt(service, workflow_name, evidence_summary)
        result = await llm_router.route(
            prompt=prompt,
            system=SYSTEM_PROMPT,
            task_type=TaskType.REASONING,
            agent_type="flaky_test_root_cause_reasoner",
        )
        if not result.success:
            log.debug("Flaky test reasoning: LLM call failed for %s/%s: %s", service, workflow_name, result.error)
            return None
        return result.output
    except Exception as exc:
        log.debug("Flaky test reasoning: LLM call raised for %s/%s: %s", service, workflow_name, exc)
        return None
