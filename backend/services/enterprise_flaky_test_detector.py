"""
Enterprise Flaky Test Detector
================================

Distinguishes a flaky CI failure from a real one using the one signal
that actually proves it either way: does the exact same code pass on a
real re-run? Deliberately plain logic, not a guess from timing patterns
or historical statistics — those come later, once this baseline signal
is proven trustworthy.

Granularity: whole workflow-run (GitHub) / pipeline (GitLab), using each
provider's real "re-run failed jobs" API — not individual test-function
parsing (that needs JUnit/test-report parsing, a v2 concern).

State machine, driven by CI completion webhooks:
  1st completion, conclusion=failure  -> trigger a real re-run of just the
                                          failed jobs, record pending state
  2nd completion (the re-run), for a run_id we're tracking:
    conclusion=success -> flaky confirmed; record occurrence in history
    conclusion=failure -> not flaky, a real failure; drop pending state,
                           do nothing further (existing process owns it)

Wired from: backend.services.enterprise_github_integration.process_and_wire
on "workflow_run" events, and the GitLab equivalent for pipeline events.
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional

log = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_PENDING_RETRY_FILE = _DATA_DIR / "flaky_test_pending_retries.json"
_FLAKY_TEST_HISTORY_FILE = _DATA_DIR / "flaky_test_history.json"

MAX_FLAKY_TEST_HISTORY = 500

# Tunable — calibrate against real occurrences before trusting this in
# production, same caveat as the deploy-regression thresholds.
DEFAULT_FLAKY_THRESHOLD_COUNT = 3
DEFAULT_FLAKY_THRESHOLD_WINDOW_DAYS = 14


def _load_json(path: Path) -> List[Dict[str, Any]]:
    try:
        if path.exists():
            with open(path) as f:
                return json.load(f)
    except Exception as exc:
        log.warning("Failed to load %s: %s", path.name, exc)
    return []


def _save_json(path: Path, data: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as exc:
        log.warning("Failed to save %s: %s", path.name, exc)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class PendingRetryStore:
    """Durable record of workflow-run/pipeline retries we triggered
    ourselves, so we know which "completed" webhooks to react to and
    which to ignore (e.g. a developer manually re-running a job — not
    ours to react to)."""

    def __init__(self, file_path: Optional[Path] = None) -> None:
        self._file_path = file_path or _PENDING_RETRY_FILE
        self._pending: List[Dict[str, Any]] = _load_json(self._file_path)

    def add(self, run_key: str, service: str, workflow_name: str, ctx: Dict[str, Any]) -> None:
        self._pending = [p for p in self._pending if p.get("run_key") != run_key]
        self._pending.append({
            "run_key": run_key,
            "service": service,
            "workflow_name": workflow_name,
            "ctx": ctx,
            "triggered_at": _now(),
        })
        _save_json(self._file_path, self._pending)

    def get(self, run_key: str) -> Optional[Dict[str, Any]]:
        for p in self._pending:
            if p.get("run_key") == run_key:
                return p
        return None

    def remove(self, run_key: str) -> None:
        self._pending = [p for p in self._pending if p.get("run_key") != run_key]
        _save_json(self._file_path, self._pending)

    def list_pending(self) -> List[Dict[str, Any]]:
        return list(self._pending)

    def clear(self) -> None:
        self._pending = []
        _save_json(self._file_path, [])


class FlakyTestHistoryStore:
    """Durable record of confirmed-flaky occurrences — every time a
    workflow/pipeline failed, was re-run with no code change, and passed."""

    def __init__(self, file_path: Optional[Path] = None) -> None:
        self._file_path = file_path or _FLAKY_TEST_HISTORY_FILE
        self._history: List[Dict[str, Any]] = _load_json(self._file_path)

    def record(
        self,
        service: str,
        workflow_name: str,
        run_key: str,
        evidence: str,
        hypothesis: Optional[str] = None,
        ticket_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        entry = {
            "history_id": str(uuid.uuid4()),
            "service": service,
            "workflow_name": workflow_name,
            "run_key": run_key,
            "evidence": evidence,
            "hypothesis": hypothesis,
            "ticket_key": ticket_key,
            "detected_at": _now(),
        }
        self._history.insert(0, entry)
        self._history = self._history[:MAX_FLAKY_TEST_HISTORY]
        _save_json(self._file_path, self._history)
        return entry

    def list_recent(self, limit: int = 20) -> List[Dict[str, Any]]:
        return self._history[:limit]

    def update_ticket_key(self, history_id: str, ticket_key: str) -> None:
        """Link a filed Jira ticket back to the occurrence that triggered
        it. record() always runs before the ticket exists (the threshold
        check needs this occurrence counted first), so the link has to be
        written back after the fact rather than passed to record() itself.
        """
        for h in self._history:
            if h.get("history_id") == history_id:
                h["ticket_key"] = ticket_key
                _save_json(self._file_path, self._history)
                return

    def count_since(self, service: str, workflow_name: str, since: datetime) -> int:
        since_iso = since.isoformat()
        return sum(
            1 for h in self._history
            if h.get("service") == service
            and h.get("workflow_name") == workflow_name
            and h.get("detected_at", "") >= since_iso
        )

    def clear(self) -> None:
        self._history = []
        _save_json(self._file_path, [])


pending_retry_store = PendingRetryStore()
flaky_test_history_store = FlakyTestHistoryStore()


def crosses_flaky_threshold(
    service: str,
    workflow_name: str,
    threshold_count: int = DEFAULT_FLAKY_THRESHOLD_COUNT,
    window_days: int = DEFAULT_FLAKY_THRESHOLD_WINDOW_DAYS,
    history_store: Optional[FlakyTestHistoryStore] = None,
) -> bool:
    store = history_store or flaky_test_history_store
    since = datetime.now(timezone.utc) - timedelta(days=window_days)
    return store.count_since(service, workflow_name, since) >= threshold_count


def summarize_evidence(attempt_jobs: List[Dict[str, Any]]) -> str:
    """Plain-text summary of per-attempt job/step evidence, used both as
    the history store's evidence field and as the ticket's evidence
    section — same format the reasoner's prompt is built from, so what a
    human sees in the ticket matches what the LLM actually reasoned over.
    """
    lines = []
    for entry in attempt_jobs:
        attempt = entry.get("attempt", "?")
        job_name = entry.get("job_name", "unknown job")
        conclusion = entry.get("conclusion", "unknown")
        failed_steps = entry.get("failed_steps", [])
        line = f"Attempt {attempt}: job \"{job_name}\" -> {conclusion}"
        if failed_steps:
            line += f" (failed step(s): {', '.join(failed_steps)})"
        lines.append(line)
    return "\n".join(lines) if lines else "(no job/step evidence available)"


async def handle_ci_completion(
    service: str,
    workflow_name: str,
    run_key: str,
    conclusion: str,
    ctx: Dict[str, Any],
    trigger_retry: Callable[[], Awaitable[bool]],
    fetch_evidence: Callable[[], Awaitable[List[Dict[str, Any]]]],
    pending_store: Optional[PendingRetryStore] = None,
    history_store: Optional[FlakyTestHistoryStore] = None,
) -> Optional[Dict[str, Any]]:
    """Provider-agnostic state machine — call this on every CI
    workflow-run/pipeline completion webhook, regardless of provider.

    run_key must be a stable, provider-namespaced identifier for this
    specific run (e.g. "gh:{owner}/{repo}:{run_id}" or
    "gl:{project_id}:{pipeline_id}") — its only job is letting this
    function recognize "this completion is the result of a retry I
    triggered" vs "this is a fresh completion I haven't seen."

    trigger_retry / fetch_evidence are injected so this stays provider-
    agnostic: GitHub passes rerun_failed_jobs/list_jobs_for_run, GitLab
    passes retry_pipeline/list_jobs, and this function never needs to
    know which.

    Returns the filed Jira ticket dict if the threshold was crossed and
    a ticket was created, else None.
    """
    pstore = pending_store or pending_retry_store
    hstore = history_store or flaky_test_history_store

    if conclusion not in ("success", "failure"):
        return None

    pending = pstore.get(run_key)

    if pending is not None:
        # This completion is the result of a retry we triggered ourselves.
        pstore.remove(run_key)
        if conclusion == "success":
            try:
                attempt_jobs = await fetch_evidence()
            except Exception as exc:
                log.debug("Flaky-test evidence fetch failed for %s/%s (%s): %s", service, workflow_name, run_key, exc)
                attempt_jobs = []
            evidence_summary = summarize_evidence(attempt_jobs)
            recorded = hstore.record(service, workflow_name, run_key, evidence_summary)
            if crosses_flaky_threshold(service, workflow_name, history_store=hstore):
                from backend.services.enterprise_alert_correlator import correlate_and_report
                from backend.services.enterprise_flaky_test_incident_reporter import report_flaky_incident
                issue = await correlate_and_report(
                    source="flaky_test",
                    service=service,
                    summary=f"{workflow_name}: {evidence_summary.splitlines()[0] if evidence_summary else 'flaky test confirmed'}",
                    reporter=lambda: report_flaky_incident(
                        service, workflow_name, evidence_summary, attempt_jobs, history_store=hstore,
                    ),
                    severity="warning",
                )
                ticket_key = issue.get("key") or issue.get("ticket_key") if issue else None
                if ticket_key:
                    hstore.update_ticket_key(recorded["history_id"], ticket_key)
                return issue
        # conclusion == "failure" again -> real failure, not flaky. Nothing
        # further to do; the existing CI-failure process owns it.
        return None

    # Not something we're already tracking.
    if conclusion == "failure":
        triggered = False
        try:
            triggered = await trigger_retry()
        except Exception as exc:
            log.debug("Flaky-test retry trigger failed for %s/%s (%s): %s", service, workflow_name, run_key, exc)
        if triggered:
            pstore.add(run_key, service, workflow_name, ctx)
    return None
