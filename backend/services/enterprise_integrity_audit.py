"""Tamper-evident audit trail for approval-integrity decisions.

Constitution I3: the audit record is append-only and independently verifiable.
S8 adds that it is "designed for a hostile reader" -- it must survive a dispute
without the reader trusting the running system.

A control that fires silently cannot be shown to have fired. Every refusal, and
every successful verification that authorizes a real action, is recorded here
with enough detail to reconstruct the decision: which workflow, which action,
what digest was expected, what was actually found, and why execution was
refused.

Chaining
--------
Each entry's digest covers its own content *including the previous entry's
digest*, so altering any earlier entry invalidates every digest after it.
:func:`verify_chain` walks the chain and reports the first break.

Storage (PR-06)
---------------
Entries are now written through ``backend.platform.audit.AuditRuntime`` to a
durable append-only store, and additionally emitted as structured logs at ERROR
(violations) or INFO (verified dispatches). A restart resumes the existing
chain rather than starting a second one.

This class is kept as a thin façade over the runtime rather than being deleted:
five call sites in the dispatcher use it, and preserving the interface makes
PR-06 a substitution rather than a rewrite. New code should use
``AuditRuntime`` directly.

Remaining limitation: the backing store is an append-only file, not a
transactional table. PostgreSQL arrives in PR-11 behind the same
``AuditStore`` interface, which is why that interface exists.
"""

from __future__ import annotations

import json
import logging
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pathlib import Path

from backend.contracts import (
    AuditEvent,
    AuditEventKind,
    PrincipalKind,
    PrincipalRef,
    TenantRef,
    TenantScope,
)
import dataclasses

from backend.platform.context import (
    CorrelationContext,
    ExecutionContext,
    IdentityContext,
)
from backend.platform.audit import (
    AuditRuntime,
    InMemoryAuditStore,
    IntegrityReport,
    JsonlAuditStore,
    verify_chain,
)

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"

log = logging.getLogger(__name__)

__all__ = [
    "IntegrityAuditLog",
    "integrity_audit",
    "SYSTEM_SCOPE",
    "PLATFORM_PRINCIPAL",
]

_DISPATCHER_CONTEXT = ExecutionContext.platform_internal(
    reason=(
        "approval dispatch replays an EventBus payload that carries no tenant; "
        "tenancy is captured when the approval store moves to the database (PR-11)"
    ),
    component="cortexprime.approval_dispatcher",
    source="eventbus",
)
"""Context for the legacy dispatch path (PR-09).

Replaces the former ``TenantScope(TenantRef("system"))`` placeholder. That
invented an owner and made a real tenant named "system" indistinguishable from
the absence of one. This marks the absence explicitly: the reserved
``__platform_internal__`` id cannot be claimed by a real tenant, and the stated
reason reaches every audit record so the gap is legible rather than disguised.

Every use is an attribution gap. PR-11 closes it by capturing tenancy when the
approval record is written."""

SYSTEM_SCOPE = _DISPATCHER_CONTEXT.scope
"""Retained for callers that still expect a scope. Prefer the context."""

PLATFORM_PRINCIPAL = PrincipalRef(
    principal_id="cortexprime.approval_dispatcher", kind=PrincipalKind.PLATFORM
)
"""The actor when the platform itself refuses an action. Note this principal
cannot grant an approval -- ``PrincipalRef.can_approve`` is False for
PLATFORM -- which is the point: the system records its own refusals but never
authorizes itself."""



class IntegrityAuditLog:
    """Façade over the durable audit runtime, kept for its existing callers.

    Accepts an :class:`AuditRuntime`; defaults to a process-wide durable one
    writing to ``backend/data/integrity_audit.jsonl``. Tests pass an in-memory
    runtime for isolation.
    """

    __slots__ = ("_runtime", "_context")

    def __init__(
        self,
        runtime: Optional[AuditRuntime] = None,
        context: Optional[ExecutionContext] = None,
    ) -> None:
        # ``None`` stays ``None`` until first use (see ``_active``). The module
        # global below is constructed at import time, and resolving a default
        # store *here* would open the legacy JSONL chain in every process --
        # including one whose composition root is about to bind the durable
        # authority. Lazy resolution means a rebind before the first record
        # leaves the legacy chain untouched entirely.
        self._runtime = runtime
        self._context = context if context is not None else _DISPATCHER_CONTEXT

    def rebind(self, runtime: AuditRuntime) -> None:
        """Point this facade at the authoritative audit runtime (ADR-057).

        Called by the application's composition root when the durable governed
        composition is active, so approval-dispatch observations join **the**
        fenced PostgreSQL chain instead of a private legacy file. This is the
        strangler seam: the facade keeps its typed interface (the approval
        semantics), and the sink underneath becomes the platform authority.

        Refuses ``None`` rather than treating it as "back to the default" --
        unbinding an authority silently is exactly the fallback behaviour this
        phase removed.
        """
        if runtime is None:
            raise ValueError("rebind requires a runtime; there is no unbind")
        self._runtime = runtime

    @property
    def _active(self) -> AuditRuntime:
        if self._runtime is None:
            self._runtime = _default_runtime()
        return self._runtime

    @property
    def runtime(self) -> AuditRuntime:
        """The underlying runtime, for callers needing query or export."""
        return self._active

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def _append(
        self,
        kind: AuditEventKind,
        subject_reference: str,
        detail: Dict[str, Any],
        actor: Optional[PrincipalRef] = None,
        correlation_id: Optional[str] = None,
    ) -> AuditEvent:
        context = self._context
        if actor is not None:
            context = context.with_identity(
                IdentityContext(principal=actor, capabilities=())
            )
        if correlation_id is not None:
            context = dataclasses.replace(
                context,
                correlation=CorrelationContext.join(correlation_id),
            )
        return self._active.record_in_context(
            kind,
            context,
            subject_reference=subject_reference,
            detail=detail,
        )

    def record_refusal(
        self,
        *,
        workflow_id: str,
        action_type: Optional[str],
        reason: str,
        failure: str,
        expected_digest: Optional[str] = None,
        actual_digest: Optional[str] = None,
        mission_id: Optional[str] = None,
        operator: Optional[str] = None,
        tamper_evidence: bool = False,
    ) -> AuditEvent:
        """Record that execution was refused, and why.

        ``tamper_evidence`` distinguishes deliberate modification from a record
        that merely predates the check. Both refuse; only the former warrants
        an alert.
        """
        detail: Dict[str, Any] = {
            "workflow_id": workflow_id,
            "action_type": action_type,
            "failure": failure,
            "reason": reason,
            "expected_digest": expected_digest,
            "actual_digest": actual_digest,
            "mission_id": mission_id,
            "operator": operator,
            "execution_refused": True,
            "tamper_evidence": tamper_evidence,
        }
        kind = (
            AuditEventKind.INTEGRITY_VIOLATION_DETECTED
            if tamper_evidence
            else AuditEventKind.EXECUTION_REFUSED
        )
        event = self._append(kind, workflow_id, detail)

        log.error(
            "APPROVAL INTEGRITY REFUSAL %s",
            json.dumps({**detail, "audit_event_id": event.event_id}, default=str),
        )
        return event

    def record_verified_dispatch(
        self,
        *,
        workflow_id: str,
        action_type: str,
        digest: str,
        operator: Optional[str] = None,
    ) -> AuditEvent:
        """Record that a verified action was dispatched.

        Recording successes as well as refusals is what makes the trail
        complete: an auditor can confirm that every executed action passed
        verification, not merely that failures were noticed.
        """
        detail: Dict[str, Any] = {
            "workflow_id": workflow_id,
            "action_type": action_type,
            "verified_digest": digest,
            "operator": operator,
            "execution_refused": False,
        }
        event = self._append(AuditEventKind.EXECUTION_STARTED, workflow_id, detail)
        log.info(
            "APPROVAL INTEGRITY VERIFIED %s",
            json.dumps({**detail, "audit_event_id": event.event_id}, default=str),
        )
        return event

    # ------------------------------------------------------------------
    # Inspection
    # ------------------------------------------------------------------

    def entries(self) -> tuple[AuditEvent, ...]:
        """Every recorded entry, oldest first.

        Now reads from durable storage rather than an in-memory ring, so this
        no longer silently truncates after 1000 entries as it did in PR-04.
        """
        return self._active.query()

    def verify_chain(self) -> tuple[bool, Optional[int]]:
        """Verify the chain. Returns ``(ok, first_defective_sequence)``.

        Delegates to :func:`~backend.platform.audit.verify_chain`, which detects
        tampering, broken links, **and deleted records** -- the last of which the
        PR-04 implementation could not see, because a deletion leaves the
        survivors internally consistent.
        """
        report = verify_chain(self._active)
        if report.ok:
            return True, None
        first = report.first_defect
        return False, first.sequence if first else None

    def integrity_report(self) -> IntegrityReport:
        """Full report, including every defect found and the head digest."""
        return verify_chain(self._active)

    def clear(self) -> None:
        """Reset to a fresh in-memory runtime. Test isolation only.

        Deliberately does **not** delete durable records: an audit log that can
        erase itself on request is not an audit log.
        """
        self._runtime = AuditRuntime(InMemoryAuditStore())


def _is_production_environment() -> bool:
    """The application's own environment convention (see ``main.py``)."""
    import os

    value = (os.getenv("ENVIRONMENT") or os.getenv("ENV") or "development")
    return value.lower() in ("production", "prod")


def _default_runtime() -> AuditRuntime:
    """The legacy default sink, resolved lazily and gated by environment.

    This default exists only for the composition the platform is moving away
    from: a process that never bound the durable audit authority (ADR-057).
    Where the governed composition is active, the application root calls
    ``integrity_audit.rebind(persistence.audit)`` before anything records, and
    this function never runs.

    **Production fails closed.** The previous behaviour -- fall back to an
    in-memory store and log -- meant a production approval trail could
    silently stop surviving restarts. An approval-integrity record that only
    ever existed in one process's memory is not evidence; refusing to record
    is at least a visible failure with a named remedy (bind the durable
    authority, or fix the file store).

    **Development keeps the JSONL default, explicitly.** Single-writer
    admission only, never fenced (ADR-055) -- a development convenience, not
    an authority. The in-memory fallback survives only outside production and
    only with a loud error naming what was lost.
    """
    try:
        return AuditRuntime(JsonlAuditStore(_DATA_DIR / "integrity_audit.jsonl"))
    except Exception as exc:  # noqa: BLE001 - classified below, never silent
        if _is_production_environment():
            raise RuntimeError(
                "the integrity audit store could not be opened and this is "
                "production; there is no in-memory fallback here -- an "
                "approval trail that vanishes on restart is not evidence. "
                "Bind the durable audit authority (ADR-057) or repair the "
                f"store ({type(exc).__name__}: {exc})"
            ) from exc
        log.error(
            "Durable integrity audit unavailable (%s); NON-PRODUCTION in-memory "
            "fallback engaged. Records will NOT survive a restart. This branch "
            "does not exist in production, which fails closed instead.",
            exc,
        )
        return AuditRuntime(InMemoryAuditStore())


integrity_audit = IntegrityAuditLog()
