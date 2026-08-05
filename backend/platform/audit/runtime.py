"""The audit runtime: the single place a security-critical decision is recorded.

Constitution I3 -- append-only and independently verifiable -- and S8, which
adds that the trail is "designed for a hostile reader": it must survive a
dispute without the reader trusting the running system.

Chaining
--------
Each record's ``entry_digest`` covers its own content **including the previous
record's digest**, so altering any earlier record invalidates every digest after
it. The runtime holds the chain head and appends under a lock, which is what
makes concurrent appends produce one linear, verifiable chain rather than a
fork.

Recovery
--------
On construction the runtime reads the chain head from the store. A restart
therefore continues the existing chain rather than starting a second one from
sequence zero -- two chains in one store cannot be verified as either.

What belongs here
-----------------
Compliance evidence: approvals, executions, policy decisions, integrity
failures, identity events, configuration changes, connector operations.

What does not: application logging, metrics, traces, debugging output. Those are
observability, they are sampled and expired, and mixing them into an evidence
trail devalues both.
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any, Mapping, Optional

from backend.contracts import (
    AuditEvent,
    AuditEventKind,
    HashAlgorithm,
    PayloadDigest,
    PrincipalRef,
    TenantScope,
)
from backend.platform.audit.exceptions import (
    AuditChainError,
    AuditCorruptionError,
    AuditStorageError,
)
from backend.platform.audit.store import AuditQuery, AuditStore, InMemoryAuditStore
from backend.platform.hashing import compute_digest
from backend.platform.identity import monotonic_ulid

__all__ = ["AuditRuntime", "AUDIT_SCHEMA_VERSION"]

AUDIT_SCHEMA_VERSION = 1
"""Schema version of the audit record body. Recorded in every entry's detail so
a future reader can interpret older records without guessing. Distinct from
``AuditEvent.CONTRACT_VERSION``, which versions the wire format."""

_ALGORITHM = HashAlgorithm.SHA256


def _chain_body(
    *,
    sequence: int,
    kind: AuditEventKind,
    subject_reference: Optional[str],
    recorded_at: datetime,
    detail: Mapping[str, Any],
    previous_digest: Optional[PayloadDigest],
    correlation_id: Optional[str],
    causation_id: Optional[str],
    payload_digest: Optional[PayloadDigest],
    tenant_id: str,
    actor_id: Optional[str],
) -> dict[str, Any]:
    """The exact structure an entry digest is taken over.

    Every field an auditor would rely on is included. Anything omitted here
    could be altered without breaking the chain, so the list is deliberately
    exhaustive rather than convenient.
    """
    return {
        "schema_version": AUDIT_SCHEMA_VERSION,
        "sequence": sequence,
        "kind": kind.value,
        "subject_reference": subject_reference,
        "recorded_at": recorded_at.isoformat(),
        "detail": dict(detail),
        "previous_digest": previous_digest.value if previous_digest else None,
        "correlation_id": correlation_id,
        "causation_id": causation_id,
        "payload_digest": payload_digest.value if payload_digest else None,
        "tenant_id": tenant_id,
        "actor_id": actor_id,
    }


class AuditRuntime:
    """Records security-critical decisions into an append-only chain."""

    __slots__ = ("_lock", "_store", "_head", "_next_sequence")

    def __init__(self, store: Optional[AuditStore] = None) -> None:
        self._lock = threading.RLock()
        self._store: AuditStore = store if store is not None else InMemoryAuditStore()
        self._head: Optional[PayloadDigest] = None
        self._next_sequence = 0
        self._recover()

    # ------------------------------------------------------------------
    # Recovery
    # ------------------------------------------------------------------

    def _recover(self) -> None:
        """Resume an existing chain rather than starting a parallel one.

        A corrupted store raises rather than starting a fresh chain. Silently
        beginning again at sequence zero would leave two chains in one store,
        which cannot be verified as either -- and would quietly discard whatever
        evidence preceded the damage.

        :class:`AuditCorruptionError` propagates unwrapped: it names the exact
        line, and an operator needs that more than a generic storage error.
        """
        try:
            last = self._store.last()
        except AuditCorruptionError:
            raise
        except Exception as exc:  # noqa: BLE001 - any other read failure
            raise AuditStorageError(f"could not read audit chain head: {exc}") from exc
        if last is not None:
            self._head = last.entry_digest
            self._next_sequence = last.sequence + 1

    @property
    def store(self) -> AuditStore:
        return self._store

    @property
    def head_digest(self) -> Optional[PayloadDigest]:
        """Digest of the most recent record. The value to publish or notarize."""
        with self._lock:
            return self._head

    @property
    def next_sequence(self) -> int:
        with self._lock:
            return self._next_sequence

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def record_in_context(
        self,
        kind: AuditEventKind,
        context: Any,
        *,
        subject_reference: Optional[str] = None,
        detail: Optional[Mapping[str, Any]] = None,
        payload_digest: Optional[PayloadDigest] = None,
        recorded_at: Optional[datetime] = None,
    ) -> AuditEvent:
        """Record an entry from an :class:`ExecutionContext` (PR-09).

        The preferred entry point. Tenant, principal, correlation, trace, and
        request identity all come from one value, so an audit record cannot be
        written with a tenant from one operation and a principal from another.

        Typed as ``Any`` rather than importing ``ExecutionContext`` because
        ``platform.audit`` must not depend on ``platform.context`` — the audit
        runtime is the more foundational of the two, and a cycle between them
        would make either impossible to test alone.
        """
        merged = dict(detail or {})
        merged.update(context.audit_detail())
        return self.record(
            kind,
            context.scope,
            subject_reference=subject_reference,
            detail=merged,
            actor=context.identity.principal,
            correlation_id=context.correlation.correlation_id,
            causation_id=context.correlation.causation_id,
            payload_digest=payload_digest,
            recorded_at=recorded_at,
        )

    def record(
        self,
        kind: AuditEventKind,
        scope: TenantScope,
        *,
        subject_reference: Optional[str] = None,
        detail: Optional[Mapping[str, Any]] = None,
        actor: Optional[PrincipalRef] = None,
        correlation_id: Optional[str] = None,
        causation_id: Optional[str] = None,
        payload_digest: Optional[PayloadDigest] = None,
        recorded_at: Optional[datetime] = None,
    ) -> AuditEvent:
        """Append one record to the chain and return it.

        Raises :class:`AuditStorageError` if the record cannot be persisted.
        The chain head is advanced **only after** a successful append, so a
        failed write leaves the chain intact and the next record links to the
        last one that actually reached storage.
        """
        with self._lock:
            sequence = self._next_sequence
            previous = self._head
            moment = recorded_at or datetime.now(timezone.utc)
            body_detail = dict(detail or {})
            body_detail.setdefault("schema_version", AUDIT_SCHEMA_VERSION)

            actor_id = actor.principal_id if actor is not None else None
            entry_digest = compute_digest(
                _chain_body(
                    sequence=sequence,
                    kind=kind,
                    subject_reference=subject_reference,
                    recorded_at=moment,
                    detail=body_detail,
                    previous_digest=previous,
                    correlation_id=correlation_id,
                    causation_id=causation_id,
                    payload_digest=payload_digest,
                    tenant_id=scope.tenant.tenant_id,
                    actor_id=actor_id,
                ),
                _ALGORITHM,
            )

            record = AuditEvent(
                event_id=monotonic_ulid(),
                kind=kind,
                scope=scope,
                recorded_at=moment,
                sequence=sequence,
                entry_digest=entry_digest,
                previous_digest=previous,
                actor=actor,
                subject_reference=subject_reference,
                detail=body_detail,
                correlation_id=correlation_id,
                causation_id=causation_id,
                payload_digest=payload_digest,
            )

            self._store.append(record)  # raises on failure; head not advanced

            self._head = entry_digest
            self._next_sequence = sequence + 1
            return record

    # ------------------------------------------------------------------
    # Reading
    # ------------------------------------------------------------------

    def query(self, criteria: Optional[AuditQuery] = None) -> tuple[AuditEvent, ...]:
        """Return records matching ``criteria`` (all records when omitted)."""
        if criteria is None:
            return tuple(self._store.read_all())
        return tuple(self._store.query(criteria))

    def count(self) -> int:
        return self._store.count()

    def recompute_digest(self, record: AuditEvent) -> PayloadDigest:
        """Recompute a record's digest from its own content.

        The operation an integrity check depends on: if the recomputed value
        differs from the stored one, the record was altered after it was
        written.
        """
        actor_id = record.actor.principal_id if record.actor is not None else None
        return compute_digest(
            _chain_body(
                sequence=record.sequence,
                kind=record.kind,
                subject_reference=record.subject_reference,
                recorded_at=record.recorded_at,
                detail=dict(record.detail),
                previous_digest=record.previous_digest,
                correlation_id=record.correlation_id,
                causation_id=record.causation_id,
                payload_digest=record.payload_digest,
                tenant_id=record.scope.tenant.tenant_id,
                actor_id=actor_id,
            ),
            record.entry_digest.algorithm,
        )
