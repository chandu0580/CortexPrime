"""
Enterprise Approval Action Dispatcher
========================================

Closes the loop that three gated executors (deploy rollback, vulnerability
auto-fix PR, branch-protection auto-fix) deliberately left open: none of
them auto-resumed once a human approved the blocking workflow via
POST /api/approval-center/workflows/{id}/approve — approving just
unblocked the audit record, the real action never actually ran. That's a
dead end relative to the "detect -> gate -> (human approves) -> act" loop
the whole approval-gate integration was built for.

When one of those executors blocks pending approval, it stashes the
minimal args needed to replay the call in pending_action_store, keyed by
workflow_id. This module subscribes to the EventBus for
approval_workflow_completed / approval_break_glass events (emitted by
backend.approval_center.workflows._emit_event) and, when the resolved
workflow is APPROVED or BREAK_GLASS, replays the original call for real —
each gated function is itself idempotent-safe (checks
get_workflow_by_execution before creating a new workflow), so calling it
again simply proceeds straight past the now-approved gate.

REJECTED/EXPIRED workflows are popped from the pending store and
discarded without executing anything — that IS the point of rejecting.
Not every approval_workflow_completed event corresponds to a pending
action here (the Approval Center is a general-purpose system, not
exclusive to these three executors) — a miss in pending_action_store is
silently a no-op, not an error.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, Optional

log = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_PENDING_ACTIONS_FILE = _DATA_DIR / "pending_approval_actions.json"

_RESOLVED_STATUSES = {"approved", "break_glass"}
_DISCARDED_STATUSES = {"rejected", "expired"}


def _load_json(path: Path) -> Dict[str, Any]:
    try:
        if path.exists():
            with open(path) as f:
                return json.load(f)
    except Exception as exc:
        log.warning("Failed to load %s: %s", path.name, exc)
    return {}


def _save_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as exc:
        log.warning("Failed to save %s: %s", path.name, exc)


class PendingActionStore:
    """Durable map of workflow_id -> {"action_type", "payload"} for actions
    blocked pending approval, so the dispatcher can replay the ORIGINAL
    call once a human approves — without this, approving a workflow via
    the API is a dead end that does nothing to the real system."""

    def __init__(self, file_path: Optional[Path] = None) -> None:
        self._file_path = file_path or _PENDING_ACTIONS_FILE
        self._pending: Dict[str, Any] = _load_json(self._file_path)

    def save(self, workflow_id: str, action_type: str, payload: Dict[str, Any]) -> None:
        self._pending[workflow_id] = {"action_type": action_type, "payload": payload}
        _save_json(self._file_path, self._pending)

    def pop(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        entry = self._pending.pop(workflow_id, None)
        if entry is not None:
            _save_json(self._file_path, self._pending)
        return entry

    def list_pending(self) -> Dict[str, Any]:
        return dict(self._pending)

    def clear(self) -> None:
        self._pending = {}
        _save_json(self._file_path, {})


pending_action_store = PendingActionStore()


async def _dispatch_rollback(payload: Dict[str, Any]) -> None:
    from backend.services.enterprise_deploy_rollback_executor import replay_rollback
    await replay_rollback(payload)


async def _dispatch_vulnerability_fix_pr(payload: Dict[str, Any]) -> None:
    from backend.services.enterprise_vulnerability_fix_executor import open_dependency_fix_pr
    await open_dependency_fix_pr(**payload)


async def _dispatch_branch_protection_fix(payload: Dict[str, Any]) -> None:
    from backend.services.enterprise_branch_protection_fix_executor import enable_minimal_protection
    await enable_minimal_protection(**payload)


async def _dispatch_docker_health_fix(payload: Dict[str, Any]) -> None:
    from backend.services.enterprise_docker_health_fix_executor import restart_crashlooping_container
    await restart_crashlooping_container(**payload)


_DISPATCH_HANDLERS: Dict[str, Callable[[Dict[str, Any]], Awaitable[None]]] = {
    "rollback": _dispatch_rollback,
    "vulnerability_fix_pr": _dispatch_vulnerability_fix_pr,
    "branch_protection_fix": _dispatch_branch_protection_fix,
    "docker_health_fix": _dispatch_docker_health_fix,
}


async def handle_approval_event(payload: Dict[str, Any]) -> Optional[str]:
    """Given an approval-workflow event payload (workflow.to_dict() shape:
    workflow_id + status), replay any pending action for that workflow if
    it resolved as approved/break-glass, or discard it if rejected/expired.
    Returns the action_type that was dispatched, or None if there was
    nothing pending for this workflow (not an error — most Approval Center
    workflows have nothing to do with these three executors) or the status
    isn't a terminal one yet."""
    workflow_id = payload.get("workflow_id")
    status = payload.get("status")
    if not workflow_id or status not in (_RESOLVED_STATUSES | _DISCARDED_STATUSES):
        return None

    entry = pending_action_store.pop(workflow_id)
    if entry is None:
        return None

    action_type = entry["action_type"]
    if status in _DISCARDED_STATUSES:
        log.info("Discarding pending action %s for %s workflow %s (not replayed)", action_type, status, workflow_id)
        return None

    handler = _DISPATCH_HANDLERS.get(action_type)
    if handler is None:
        log.warning("No dispatch handler for pending action type %s (workflow %s)", action_type, workflow_id)
        return None

    try:
        await handler(entry["payload"])
        log.warning("Replayed approved action %s for workflow %s", action_type, workflow_id)
    except Exception as exc:
        log.error("Failed to replay approved action %s for workflow %s: %s", action_type, workflow_id, exc)
    return action_type


def _on_event(event: Any) -> Optional[Awaitable[None]]:
    if getattr(event, "agent", None) != "approval_center":
        return None
    if getattr(event, "event_type", None) not in ("approval_workflow_completed", "approval_break_glass"):
        return None
    payload = getattr(event, "payload", None) or {}
    return handle_approval_event(payload)


def initialize() -> None:
    """Subscribe to the EventBus for approval-resolution events. Idempotent
    to call more than once — EventBus.subscribe() already no-ops if the
    same handler is already registered."""
    from backend.events.event_bus import event_bus
    event_bus.subscribe(_on_event)
    log.info("Approval action dispatcher subscribed to EventBus")
