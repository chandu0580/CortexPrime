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

Approval integrity (PR-04)
--------------------------
Every stashed record carries a digest over its own content, and dispatch
recomputes that digest and refuses on any mismatch — Constitution I2.
Before this, the dispatcher executed whatever it read back from
``pending_approval_actions.json``, so anything able to write that file
between approval-request and approval-grant achieved arbitrary *approved*
execution.

The rule is fail-closed without exception: a missing record, missing
digest, unparsable digest, unknown record version, workflow mismatch, or
an already-dispatched workflow all refuse. Records written before this
change carry no digest and therefore no longer dispatch; they must be
re-requested. See ``docs/adr/ADR-013-approval-integrity.md``.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, Optional

from backend.contracts import HashAlgorithm, PayloadDigest
from backend.services.enterprise_approval_decision import approval_decision_store
from backend.services.enterprise_approval_integrity import (
    IntegrityFailure,
    build_record,
    consumed_ledger,
    record_digest,
    verify_record,
)
from backend.services.enterprise_integrity_audit import integrity_audit

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
    """Durable map of workflow_id -> digest-bound approval record.

    Each stored record carries a digest over its own content (Constitution I2).
    The digest is computed *here*, in :meth:`save`, rather than by the five
    executors that call it. A caller obliged to remember a security step will
    eventually forget, and the failure would be silent -- so the only way to
    stash an action is to stash a bound one.

    See ``enterprise_approval_integrity`` for what the digest covers and why.
    """

    def __init__(self, file_path: Optional[Path] = None) -> None:
        self._file_path = file_path or _PENDING_ACTIONS_FILE
        self._pending: Dict[str, Any] = _load_json(self._file_path)

    def save(self, workflow_id: str, action_type: str, payload: Dict[str, Any]) -> str:
        """Stash an action pending approval. Returns the binding digest.

        Writes to *two* stores: the artifact here, and its authoritative digest
        to the approval decision store (PR-05). Recording the digest before any
        human sees the request means the authority predates any opportunity to
        tamper with the artifact.

        The digest is returned so a caller can log or display it; it is already
        stored, so nothing depends on the caller doing anything with it.
        """
        record = build_record(workflow_id, action_type, payload)
        self._pending[workflow_id] = record
        _save_json(self._file_path, self._pending)

        digest = PayloadDigest(
            algorithm=HashAlgorithm(record["digest"]["algorithm"]),
            value=record["digest"]["value"],
        )
        approval_decision_store.record_request(workflow_id, action_type, digest)

        return record["digest"]["value"]

    def peek(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        """Read a record without removing it. Does not verify."""
        entry = self._pending.get(workflow_id)
        return dict(entry) if isinstance(entry, dict) else entry

    def pop(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        """Remove and return a record. Does **not** verify integrity.

        Kept for the discard path (rejected/expired workflows) and for
        administrative cleanup. Any caller intending to *execute* must use
        :func:`verify_record` on the result first -- or better, go through
        :func:`handle_approval_event`, which cannot skip verification.
        """
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


async def _dispatch_cost_anomaly_fix(payload: Dict[str, Any]) -> None:
    from backend.services.enterprise_cost_anomaly_fix_executor import disable_provider_temporarily
    await disable_provider_temporarily(**payload)


_DISPATCH_HANDLERS: Dict[str, Callable[[Dict[str, Any]], Awaitable[None]]] = {
    "rollback": _dispatch_rollback,
    "vulnerability_fix_pr": _dispatch_vulnerability_fix_pr,
    "branch_protection_fix": _dispatch_branch_protection_fix,
    "docker_health_fix": _dispatch_docker_health_fix,
    "cost_anomaly_fix": _dispatch_cost_anomaly_fix,
}


def _extract_approver(payload: Dict[str, Any]) -> Optional[str]:
    """Find the human who resolved this workflow, from the real event shape.

    The EventBus payload is ``ApprovalWorkflow.to_dict()``, which carries no
    top-level ``resolved_by``. Identity lives in one of three places depending
    on how the workflow was resolved:

    * ``break_glass_by``  — emergency override
    * ``overridden_by``   — administrative override
    * ``steps[].resolved_by`` — ordinary approval, on the last resolved step

    Flat ``resolved_by``/``approved_by`` keys are also accepted because other
    callers and tests construct simplified payloads.

    Returns ``None`` when no identity can be found, which the decision store
    treats as a refusal (Constitution: the platform must never authorize
    itself). This is deliberate -- inventing an identity to make a dispatch
    succeed would defeat the entire binding.
    """
    for key in ("resolved_by", "approved_by", "break_glass_by", "overridden_by"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value

    steps = payload.get("steps")
    if isinstance(steps, list):
        # Walk backwards: the most recently resolved step carries the approver
        # whose decision completed the workflow.
        for step in reversed(steps):
            if not isinstance(step, dict):
                continue
            resolver = step.get("resolved_by")
            if isinstance(resolver, str) and resolver.strip():
                return resolver
    return None


async def handle_approval_event(payload: Dict[str, Any]) -> Optional[str]:
    """Replay a pending action once its workflow resolves -- if, and only if,
    the stored record still matches the digest taken when it was approved.

    This is the enforcement point for Constitution I2. The order of operations
    is deliberate and must not be rearranged:

    1. Read the record **without** removing it.
    2. Verify its digest against a freshly recomputed one.
    3. Refuse and audit on any mismatch, leaving the record in place as
       evidence.
    4. Only on success, claim the workflow in the consumed ledger, remove the
       record, and dispatch.

    Verifying before removing means a refused record survives for
    investigation. Claiming the ledger before dispatching means two concurrent
    resolutions of the same workflow cannot both execute.

    Returns the dispatched ``action_type``, or ``None`` when there was nothing
    pending, the status is not terminal, or execution was refused.
    """
    workflow_id = payload.get("workflow_id")
    status = payload.get("status")
    if not workflow_id or status not in (_RESOLVED_STATUSES | _DISCARDED_STATUSES):
        return None

    operator = _extract_approver(payload)
    mission_id = payload.get("mission_id")

    # Rejected and expired workflows discard without verifying: nothing is
    # going to execute, so integrity is moot and a refusal audit would be noise.
    if status in _DISCARDED_STATUSES:
        entry = pending_action_store.pop(workflow_id)
        approval_decision_store.revoke(workflow_id)
        if entry is None:
            return None
        log.info(
            "Discarding pending action %s for %s workflow %s (not replayed)",
            entry.get("action_type") if isinstance(entry, dict) else None,
            status,
            workflow_id,
        )
        return None

    record = pending_action_store.peek(workflow_id)
    if record is None:
        # Most Approval Center workflows have nothing to do with these
        # executors. Not an error, and not auditable as a refusal.
        return None

    verdict = verify_record(workflow_id, record)

    if verdict.refused:
        integrity_audit.record_refusal(
            workflow_id=workflow_id,
            action_type=verdict.action_type,
            reason=verdict.reason(),
            failure=verdict.failure.value if verdict.failure else "unknown",
            expected_digest=verdict.expected_digest,
            actual_digest=verdict.actual_digest,
            mission_id=mission_id,
            operator=operator,
            tamper_evidence=bool(verdict.failure and verdict.failure.is_tamper_evidence),
        )
        # The record is deliberately left in place. It is evidence, and
        # removing it would destroy the only copy of what was tampered with.
        return None

    action_type = verdict.action_type
    assert action_type is not None  # guaranteed by a verified verdict

    # ------------------------------------------------------------------
    # PR-05: the authoritative check.
    #
    # verify_record() above proved the artifact is internally consistent --
    # that its payload matches the digest stored *beside* it. That alone
    # cannot detect a forgery, because an attacker who rewrites the payload
    # can rewrite that digest in the same file write.
    #
    # This compares the artifact against the digest recorded in a *separate*
    # store when the action was submitted, and sealed with the approver's
    # identity when a human granted it. Forging now requires writing two
    # stores consistently and, where a signing key is configured, producing
    # an HMAC the attacker does not hold.
    # ------------------------------------------------------------------
    approval_decision_store.record_grant(
        workflow_id, approver_id=operator, approver_kind="human"
    )

    current_digest = record_digest(
        workflow_id, action_type, verdict.payload or {}, record.get("record_version")
    )
    approval_verdict = approval_decision_store.verify_for_execution(
        workflow_id, current_digest, action_type
    )

    if approval_verdict.refused:
        integrity_audit.record_refusal(
            workflow_id=workflow_id,
            action_type=action_type,
            reason=approval_verdict.reason(),
            failure=approval_verdict.failure.value if approval_verdict.failure else "unknown",
            expected_digest=approval_verdict.approved_digest,
            actual_digest=approval_verdict.current_digest,
            mission_id=mission_id,
            operator=operator,
            tamper_evidence=bool(
                approval_verdict.failure and approval_verdict.failure.is_tamper_evidence
            ),
        )
        # Evidence is retained in both stores. Nothing is removed on refusal.
        return None

    handler = _DISPATCH_HANDLERS.get(action_type)
    if handler is None:
        integrity_audit.record_refusal(
            workflow_id=workflow_id,
            action_type=action_type,
            reason=f"no dispatch handler registered for action type {action_type!r}",
            failure="no_handler",
            expected_digest=verdict.expected_digest,
            mission_id=mission_id,
            operator=operator,
        )
        return None

    # Claim the workflow before dispatching. If two resolutions race, exactly
    # one wins here and the other is refused as already consumed.
    if not consumed_ledger.mark_consumed(workflow_id):
        integrity_audit.record_refusal(
            workflow_id=workflow_id,
            action_type=action_type,
            reason="this workflow's action has already been dispatched",
            failure=IntegrityFailure.ALREADY_CONSUMED.value,
            expected_digest=verdict.expected_digest,
            mission_id=mission_id,
            operator=operator,
            tamper_evidence=True,
        )
        return None

    # Burn the approval so it cannot authorize a second execution, then remove
    # the artifact. Both stores are single-use from here.
    approval_decision_store.mark_consumed(workflow_id)
    pending_action_store.pop(workflow_id)

    integrity_audit.record_verified_dispatch(
        workflow_id=workflow_id,
        action_type=action_type,
        digest=approval_verdict.approved_digest or verdict.expected_digest or "",
        operator=operator,
    )

    try:
        await handler(dict(verdict.payload or {}))
        log.warning("Replayed approved action %s for workflow %s", action_type, workflow_id)
    except Exception as exc:
        log.error(
            "Failed to replay approved action %s for workflow %s: %s",
            action_type, workflow_id, exc,
        )
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
