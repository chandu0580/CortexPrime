"""
Alert / Incident Noise Reduction
===================================

CortexPrime already has three independent detectors that each file their
own Jira ticket when something goes wrong with a service: deploy-regression
detection, flaky-test detection, and (linking, not filing) rollback
automation. Today, if a bad deploy triggers a regression AND its rollback
attempt fails AND a flaky test flares up on the same service within
minutes, that's three separate tickets for what a human would recognize
as one incident — exactly the "noisy alerts" problem this module exists to
fix.

This is deliberately NOT a fourth independent alert silo. It sits in front
of the existing report_incident/report_flaky_incident calls: the FIRST
alert-worthy signal for a service still files its own ticket exactly as it
does today (unchanged, low-risk). Any FURTHER signal for the same service
within CORRELATION_WINDOW_MINUTES is correlated into that same incident —
its own ticket is suppressed, an LLM hypothesis ties the signals together,
and a comment linking them is added to the original ticket instead.

Two entry points, matching how the existing detectors differ:
  correlate_and_report() — for signals that would file their OWN ticket
                            (deploy-regression, flaky-test). Gates whether
                            the caller's reporter() runs at all.
  attach_signal()         — for signals that don't file their own ticket
                            but should still be recorded onto an already-
                            open incident if one exists (rollback attempts,
                            which only ever follow a regression that would
                            already have opened the incident).
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
_INCIDENT_HISTORY_FILE = _DATA_DIR / "alert_incident_history.json"
MAX_INCIDENT_HISTORY = 200

CORRELATION_WINDOW_MINUTES = 30


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


def _parse(iso: str) -> Optional[datetime]:
    try:
        return datetime.fromisoformat(iso)
    except (TypeError, ValueError):
        return None


class IncidentHistoryStore:
    """Durable record of correlated incidents — one entry per service+window,
    growing a signals list as further alerts correlate into it, so a
    dashboard can show what was suppressed and why."""

    def __init__(self, file_path: Optional[Path] = None) -> None:
        self._file_path = file_path or _INCIDENT_HISTORY_FILE
        self._incidents: List[Dict[str, Any]] = _load_json(self._file_path)

    def find_open(self, service: str, window_minutes: int = CORRELATION_WINDOW_MINUTES) -> Optional[Dict[str, Any]]:
        """Most recent incident for this service still within the
        correlation window, or None if there isn't one (first signal, or
        the previous incident has gone stale)."""
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)
        candidates = [i for i in self._incidents if i.get("service") == service]
        for incident in candidates:
            last_at = _parse(incident.get("last_signal_at", ""))
            if last_at and last_at >= cutoff:
                return incident
        return None

    def open_incident(self, service: str, ticket_key: Optional[str], signal: Dict[str, Any]) -> Dict[str, Any]:
        entry = {
            "incident_id": str(uuid.uuid4()),
            "service": service,
            "ticket_key": ticket_key,
            "signals": [signal],
            "suppressed_count": 0,
            "hypothesis": None,
            "opened_at": _now(),
            "last_signal_at": _now(),
        }
        self._incidents.insert(0, entry)
        self._incidents = self._incidents[:MAX_INCIDENT_HISTORY]
        _save_json(self._file_path, self._incidents)
        return entry

    def append_signal(self, incident_id: str, signal: Dict[str, Any], hypothesis: Optional[str] = None) -> Optional[Dict[str, Any]]:
        for incident in self._incidents:
            if incident.get("incident_id") == incident_id:
                incident["signals"].append(signal)
                incident["suppressed_count"] += 1
                incident["last_signal_at"] = _now()
                if hypothesis:
                    incident["hypothesis"] = hypothesis
                _save_json(self._file_path, self._incidents)
                return incident
        return None

    def list_recent(self, limit: int = 20) -> List[Dict[str, Any]]:
        return self._incidents[:limit]

    def clear(self) -> None:
        self._incidents = []
        _save_json(self._file_path, [])


incident_history_store = IncidentHistoryStore()


def _signal(source: str, summary: str, severity: str) -> Dict[str, Any]:
    return {"source": source, "summary": summary, "severity": severity, "detected_at": _now()}


async def correlate_and_report(
    source: str,
    service: str,
    summary: str,
    reporter: Callable[[], Awaitable[Optional[Dict[str, Any]]]],
    severity: str = "warning",
    history_store: Optional[IncidentHistoryStore] = None,
) -> Optional[Dict[str, Any]]:
    """Gate a ticket-filing detector's own reporter() behind incident
    correlation. First signal for a service in the window: reporter() runs
    exactly as it always has, and an incident opens around its ticket.
    Any further signal within the window: reporter() is NOT called (the
    duplicate-ticket suppression), the signal is folded into the open
    incident, an LLM hypothesis is (re)generated across all signals, and a
    comment linking them is added to the original ticket.

    Returns reporter()'s own result for a first/fresh signal, or a
    {"suppressed": True, ...} dict when correlated into an existing
    incident — callers should treat both as "handled", not branch on it.
    """
    hstore = history_store or incident_history_store
    signal = _signal(source, summary, severity)

    open_incident = hstore.find_open(service)
    if open_incident is None:
        issue = await reporter()
        ticket_key = issue.get("key") if issue else None
        hstore.open_incident(service, ticket_key, signal)
        return issue

    hypothesis = None
    try:
        from backend.services.enterprise_alert_incident_reasoner import generate_incident_hypothesis
        hypothesis = await generate_incident_hypothesis(service, open_incident["signals"] + [signal])
    except Exception as exc:
        log.debug("Incident hypothesis generation failed for %s: %s", service, exc)

    updated = hstore.append_signal(open_incident["incident_id"], signal, hypothesis)

    ticket_key = open_incident.get("ticket_key")
    if ticket_key:
        try:
            from backend.services.enterprise_alert_incident_reporter import comment_correlated_signal
            await comment_correlated_signal(ticket_key, source, summary, hypothesis)
        except Exception as exc:
            log.warning("Failed to comment correlated signal on %s for %s: %s", ticket_key, service, exc)

    log.warning(
        "Alert suppressed as duplicate — %s (%s) correlated into open incident %s for %s (ticket %s)",
        source, summary, open_incident["incident_id"], service, ticket_key,
    )
    return {
        "suppressed": True,
        "incident_id": open_incident["incident_id"],
        "ticket_key": ticket_key,
        "signal_count": len((updated or open_incident)["signals"]),
    }


async def attach_signal(
    source: str,
    service: str,
    summary: str,
    severity: str = "info",
    history_store: Optional[IncidentHistoryStore] = None,
) -> Optional[Dict[str, Any]]:
    """Record a non-ticket-filing signal (e.g. a rollback attempt) onto an
    already-open incident for this service, if one exists. Does nothing —
    not an error — when there's no open incident to attach to, since a
    signal like this always follows one that would have opened it."""
    hstore = history_store or incident_history_store
    open_incident = hstore.find_open(service)
    if open_incident is None:
        return None
    signal = _signal(source, summary, severity)
    return hstore.append_signal(open_incident["incident_id"], signal)
