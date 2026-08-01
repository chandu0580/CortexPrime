"""
Deploy Rollback History Store
===============================

Durable record of automated-rollback attempts triggered by
enterprise_deploy_rollback_executor.trigger_rollback, so a UI/dashboard can
show what was rolled back, to which known-good target, and why — the audit
trail half of rollback automation.

Scope note: this records that a rollback was TRIGGERED (the API call to
redeploy the last-known-good ref succeeded or failed), not whether the
resulting redeploy itself later succeeds — that would need its own
webhook-driven closed loop (tracking the new deployment/pipeline id through
to its own completion), which is real follow-up work, not silently folded
in here.
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
_ROLLBACK_HISTORY_FILE = _DATA_DIR / "rollback_history.json"
MAX_ROLLBACK_HISTORY = 200


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


class RollbackHistoryStore:
    """Durable record of automated rollback attempts, triggered and
    outcome-of-trigger both recorded — success here means "the redeploy
    at the known-good ref was successfully requested", not that the
    redeploy itself has finished."""

    def __init__(self, file_path: Optional[Path] = None) -> None:
        self._file_path = file_path or _ROLLBACK_HISTORY_FILE
        self._history: List[Dict[str, Any]] = _load_json(self._file_path)

    def record(
        self,
        provider: str,
        service: str,
        environment: str,
        bad_deployment_id: str,
        reasons: List[str],
        triggered: bool,
        target_sha: Optional[str] = None,
        target_deployment_id: Optional[Any] = None,
        rollback_deployment_id: Optional[Any] = None,
        ticket_key: Optional[str] = None,
        error: Optional[str] = None,
    ) -> Dict[str, Any]:
        entry = {
            "history_id": str(uuid.uuid4()),
            "provider": provider,
            "service": service,
            "environment": environment,
            "bad_deployment_id": bad_deployment_id,
            "reasons": reasons,
            "triggered": triggered,
            "target_sha": target_sha,
            "target_deployment_id": target_deployment_id,
            "rollback_deployment_id": rollback_deployment_id,
            "ticket_key": ticket_key,
            "error": error,
            "triggered_at": _now(),
        }
        self._history.insert(0, entry)
        self._history = self._history[:MAX_ROLLBACK_HISTORY]
        _save_json(self._file_path, self._history)
        return entry

    def update_ticket_key(self, history_id: str, ticket_key: str) -> None:
        for h in self._history:
            if h.get("history_id") == history_id:
                h["ticket_key"] = ticket_key
                _save_json(self._file_path, self._history)
                return

    def list_recent(self, limit: int = 20) -> List[Dict[str, Any]]:
        return self._history[:limit]

    def clear(self) -> None:
        self._history = []
        _save_json(self._file_path, [])


rollback_history_store = RollbackHistoryStore()
