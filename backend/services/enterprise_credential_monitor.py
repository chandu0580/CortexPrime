"""
Enterprise Credential Monitor
=================================

Detects connector credentials (GitHub, GitLab CI, Jira) that are already
failing authentication, or — where the provider actually supports it —
nearing a known expiry, before they silently break the other detectors
this session's already built (a dead Jira token means deploy-regression
tickets stop filing with no visible error anywhere but a debug log line).

Two real signals per connector.check_credential(), not invented ones:
  - PermissionError on the underlying auth call — uniform across all
    three connectors, always available, always reliable.
  - expires_at — a genuine token-introspection field for GitLab, an
    advisory response header for GitHub (documented accuracy issues on
    fine-grained PATs), and simply absent for Jira (Atlassian API tokens
    have no expiry-introspection endpoint at all).

Deliberately does NOT add a new always-on background polling loop —
backend.services.enterprise_watchers.WatcherManager already has one
(start_polling) but it's never actually started anywhere in this
codebase, and this session found the hard way (a multi-hour test-suite
hang investigation) how easy it is for an uncancellable background task
to quietly break things. check_all_credentials() is instead triggered
once at app startup and via an on-demand API endpoint — the same
request-triggered shape every other detector in this codebase uses.

Routes through enterprise_alert_correlator.correlate_and_report rather
than filing its own ticket unconditionally, same as the other detectors.
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_CREDENTIAL_HISTORY_FILE = _DATA_DIR / "credential_check_history.json"
MAX_CREDENTIAL_HISTORY = 200

MONITORED_CONNECTORS = ["github", "gitlab_ci", "jira"]
DEFAULT_EXPIRY_WARNING_DAYS = 14


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


def _days_until(expires_at: Optional[str]) -> Optional[int]:
    if not expires_at:
        return None
    for fmt_parser in (
        lambda s: datetime.fromisoformat(s.replace("Z", "+00:00")),
        # GitHub's advisory expiry header — "2026-10-29 12:25:55 UTC", not
        # ISO 8601. GitHub documents this header as always UTC.
        lambda s: datetime.strptime(s.removesuffix(" UTC"), "%Y-%m-%d %H:%M:%S"),
    ):
        try:
            dt = fmt_parser(expires_at)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return (dt - datetime.now(timezone.utc)).days
        except (ValueError, TypeError):
            continue
    log.debug("Could not parse expires_at for day-count: %s", expires_at)
    return None


class CredentialCheckHistoryStore:
    """Durable record of credential checks — every check is recorded
    (healthy or not) so the dashboard can show current status per
    connector, not just the alert-worthy ones."""

    def __init__(self, file_path: Optional[Path] = None) -> None:
        self._file_path = file_path or _CREDENTIAL_HISTORY_FILE
        self._history: List[Dict[str, Any]] = _load_json(self._file_path)

    def record(
        self,
        connector_type: str,
        valid: bool,
        expires_at: Optional[str] = None,
        expires_at_source: Optional[str] = None,
        error: Optional[str] = None,
        days_until_expiry: Optional[int] = None,
        ticket_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        entry = {
            "history_id": str(uuid.uuid4()),
            "connector_type": connector_type,
            "valid": valid,
            "expires_at": expires_at,
            "expires_at_source": expires_at_source,
            "days_until_expiry": days_until_expiry,
            "error": error,
            "ticket_key": ticket_key,
            "checked_at": _now(),
        }
        self._history.insert(0, entry)
        self._history = self._history[:MAX_CREDENTIAL_HISTORY]
        _save_json(self._file_path, self._history)
        return entry

    def list_recent(self, limit: int = 20) -> List[Dict[str, Any]]:
        return self._history[:limit]

    def list_latest_per_connector(self) -> List[Dict[str, Any]]:
        seen = set()
        latest = []
        for entry in self._history:
            ct = entry.get("connector_type")
            if ct in seen:
                continue
            seen.add(ct)
            latest.append(entry)
        return latest

    def clear(self) -> None:
        self._history = []
        _save_json(self._file_path, [])


credential_history_store = CredentialCheckHistoryStore()


async def check_all_credentials(
    history_store: Optional[CredentialCheckHistoryStore] = None,
    expiry_warning_days: int = DEFAULT_EXPIRY_WARNING_DAYS,
) -> List[Dict[str, Any]]:
    """Check every monitored connector's credential once. Returns the
    recorded history entry for each connector actually checked (skips
    unregistered connectors — nothing to check, not an error)."""
    from backend.connectors.registry import connector_registry
    from backend.services.enterprise_alert_correlator import correlate_and_report
    from backend.services.enterprise_credential_incident_reporter import report_credential_incident

    hstore = history_store or credential_history_store
    results: List[Dict[str, Any]] = []

    for connector_type in MONITORED_CONNECTORS:
        connector = connector_registry.get(connector_type)
        if connector is None or not hasattr(connector, "check_credential"):
            continue

        try:
            check = await connector.check_credential()
        except Exception as exc:
            log.warning("Credential check raised for %s: %s", connector_type, exc)
            check = {"valid": False, "expires_at": None, "expires_at_source": None, "error": str(exc)}

        days_until_expiry = _days_until(check.get("expires_at"))
        ticket_key: Optional[str] = None

        if not check.get("valid"):
            error = check.get("error")
            issue = await correlate_and_report(
                source="credential_expiry",
                service=connector_type,
                summary=f"{connector_type} authentication failing: {error}",
                reporter=lambda ct=connector_type, err=error: report_credential_incident(ct, "failing", error=err),
                severity="critical",
            )
            ticket_key = issue.get("key") or issue.get("ticket_key") if issue else None
        elif days_until_expiry is not None and days_until_expiry <= expiry_warning_days:
            expires_at = check.get("expires_at")
            expires_at_source = check.get("expires_at_source")
            issue = await correlate_and_report(
                source="credential_expiry",
                service=connector_type,
                summary=f"{connector_type} token expires in {days_until_expiry} day(s) ({expires_at})",
                reporter=lambda ct=connector_type, d=days_until_expiry, ea=expires_at, eas=expires_at_source: report_credential_incident(
                    ct, "expiring_soon", expires_at=ea, expires_at_source=eas, days_until_expiry=d,
                ),
                severity="warning",
            )
            ticket_key = issue.get("key") or issue.get("ticket_key") if issue else None

        entry = hstore.record(
            connector_type=connector_type,
            valid=check.get("valid", False),
            expires_at=check.get("expires_at"),
            expires_at_source=check.get("expires_at_source"),
            error=check.get("error"),
            days_until_expiry=days_until_expiry,
            ticket_key=ticket_key,
        )
        results.append(entry)

    return results
