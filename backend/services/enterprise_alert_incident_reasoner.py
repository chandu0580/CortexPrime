"""
Enterprise Alert Incident Reasoner
======================================

When enterprise_alert_correlator.correlate_and_report finds a second (or
further) alert-worthy signal for a service within the correlation window,
this asks an LLM to synthesize why they might be related — tying together
signals that can come from different detectors (deploy-regression,
flaky-test) with different shapes, so the ticket comment reads as one
coherent incident rather than a bare list of unrelated-looking events.

Same discipline as the other reasoners in this codebase: an honest
"the signals don't obviously connect" beats a confident-sounding guess.

Wired from: enterprise_alert_correlator.correlate_and_report
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are a senior software engineer investigating multiple alerts that "
    "fired for the same service within a short time window. You will be "
    "given each signal's source (e.g. deploy_regression, flaky_test, "
    "rollback), a short summary, and when it fired. Form a hypothesis for "
    "how they might be related ONLY if the signals plausibly connect (e.g. "
    "a deploy regression followed minutes later by a rollback failure on "
    "the same service is very likely the same incident; a flaky test on an "
    "unrelated workflow around the same time may just be coincidence). If "
    "the signals don't obviously connect, say so plainly rather than "
    "inventing a plausible-sounding link. Be concise: 2-3 sentences, then "
    "one line suggesting what a human should check next."
)


def _format_signals(signals: List[Dict[str, Any]]) -> str:
    lines = []
    for s in signals:
        lines.append(f"- [{s.get('detected_at', '?')}] {s.get('source', 'unknown')}: {s.get('summary', '')}")
    return "\n".join(lines) if lines else "(no signals)"


def build_prompt(service: str, signals: List[Dict[str, Any]]) -> str:
    return (
        f"Service: {service}\n\n"
        f"Correlated signals (most recent last):\n{_format_signals(signals)}\n\n"
        "What, if anything, does this sequence of signals suggest about a shared root cause?"
    )


async def generate_incident_hypothesis(
    service: str,
    signals: List[Dict[str, Any]],
) -> Optional[str]:
    """Return an LLM-generated hypothesis tying the correlated signals
    together, or None if there's nothing usable or the LLM call failed.
    Never raises — best-effort enrichment, not required to correlate or
    comment on the ticket.
    """
    if len(signals) < 2:
        return None

    try:
        from backend.llm.llm_router import TaskType, llm_router

        prompt = build_prompt(service, signals)
        result = await llm_router.route(
            prompt=prompt,
            system=SYSTEM_PROMPT,
            task_type=TaskType.REASONING,
            agent_type="alert_incident_reasoner",
        )
        if not result.success:
            log.debug("Incident reasoning: LLM call failed for %s: %s", service, result.error)
            return None
        return result.output
    except Exception as exc:
        log.debug("Incident reasoning: LLM call raised for %s: %s", service, exc)
        return None
