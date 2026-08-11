"""The audit chain in the store the fence can reach. Phase 5.12, ADR-055.

Why this file exists
----------------------
ADR-054 closed audit-writer *admission* through the existing leadership model
and stated its limitation plainly: a filesystem append cannot join the fencing
predicate, so a runtime that held ``AUDIT_WRITER``, lost it, and still appends
gets its write into the JSONL file. The ownership check and the ``write()`` are
two steps, which is exactly the stale-check race ``fenced_where`` exists to
eliminate.

Closing that gap is a storage decision, not a locking one: move the chain tail
somewhere the fence can participate in the mutation itself. That store already
exists -- the same PostgreSQL that holds ``cp_leadership`` -- and the fence
already exists -- ``SqlLeadershipStore.fenced_where``. Nothing here elects,
leases, locks, or counts anything of its own.

The append transaction
------------------------
One :meth:`DurableStore.atomic` unit, three statements, in a fixed order::

    1. UPDATE cp_leadership   SET heartbeat_at = :now
       WHERE  <fenced_where(handle)>                  -- THE fence, as a mutation
    2. UPDATE cp_audit_chain  SET next_sequence = :seq + 1, head_digest = :digest
       WHERE  chain_id = :chain AND next_sequence = :seq
          AND head_digest extends this record's previous_digest
    3. INSERT INTO cp_audit_record (...)

Statement 1 is not a check followed by a write -- it *is* a write, on the very
row a successor's acquisition mutates. Two consequences, and they are the whole
point:

* If a successor acquired token N+1 before this transaction, statement 1
  matches zero rows, :class:`StaleAuditWriter` is raised, the transaction rolls
  back, and the record **never becomes durable**. There is no window in which
  it briefly existed.
* If the two race, the database serializes them on the leadership row's lock.
  Either this append commits first (and the successor's acquisition follows
  it), or the acquisition commits first (and statement 1 re-evaluates against
  the committed token and matches nothing). "A wrote after B took the role"
  is not an ordering the database will produce.

Statement 2 is the second, independent guarantee: the tail is advanced only
from the exact sequence and head this record extends, so two admitted-looking
writers still cannot interleave -- one of them finds the tail already moved and
is refused. The chain cannot fork even if leadership were misconfigured.

Zero rows anywhere means refusal, and refusal means the exception propagates
and the transaction aborts. Nothing here retries, reacquires, or advances a
token: a stale writer that responded to refusal by taking the role back would
be a second writer manufacturing its own authority.

What this store does *not* decide
-----------------------------------
Failure here remains an observation-layer failure. ``AuditRuntime`` and its
callers preserve Phase 5.8 semantics: a failed audit append never grants
authority, never denies an otherwise-authorized action, and never reaches a
provider. The exceptions raised here are :class:`AuditError` types precisely so
no caller can mistake them for an authorization outcome.
"""

from __future__ import annotations

import logging
from typing import Any, Iterator, Optional

import sqlalchemy as sa

from backend.contracts import AuditEvent
from backend.database.durable.errors import ConstraintConflict, DurabilityError
from backend.database.durable.leadership import SqlLeadershipStore
from backend.database.durable.session import DurableStore, NoDurableStore
from backend.database.durable.tables import (
    PLATFORM_SCOPE,
    audit_chain_table,
    audit_record_table,
    leadership_table,
)
from backend.platform.audit.exceptions import (
    AuditCorruptionError,
    AuditStorageError,
    AuditWriterNotOwned,
    StaleAuditWriter,
)
from backend.platform.audit.store import AuditQuery

__all__ = ["SqlAuditStore"]

log = logging.getLogger(__name__)


class SqlAuditStore:
    """Append-only audit storage with the chain tail under the SQL fence.

    Implements the existing ``AuditStore`` protocol -- append, read_all, query,
    last, count. No update and no delete, same as every other implementation:
    the operations do not exist to call.

    ``fence``
        The audit writer's leadership, as composed at the root (the same
        adapter that answers ``AuditRuntime``'s ownership port). It must expose
        a ``handle`` attribute holding the current
        :class:`~backend.database.durable.leadership.LeadershipHandle` or
        ``None``. ``fence=None`` is the single-writer deployment: appends are
        unfenced but still tail-conditional, so even there the chain cannot
        fork or skip.

    The store is deliberately *given* its fence rather than acquiring one: a
    store that could take ``AUDIT_WRITER`` for itself would be a second path to
    the role, and the composition root is the only place allowed to wire
    authority.
    """

    __slots__ = ("_store", "_chain_id", "_fence")

    def __init__(
        self,
        store: DurableStore,
        *,
        chain_id: str = PLATFORM_SCOPE,
        fence: Optional[Any] = None,
    ) -> None:
        if not isinstance(store, DurableStore):
            raise NoDurableStore("a SQL audit store requires a durable store")
        if not isinstance(chain_id, str) or not chain_id.strip():
            raise AuditStorageError("an audit chain must be named")
        self._store = store
        self._chain_id = chain_id
        self._fence = fence

    @property
    def chain_id(self) -> str:
        return self._chain_id

    # ------------------------------------------------------------------
    # Append — the fenced transaction
    # ------------------------------------------------------------------

    def append(self, record: AuditEvent) -> None:
        """Persist one record iff this writer's fence is still current.

        Raises :class:`StaleAuditWriter` when the fencing token has been
        superseded, :class:`AuditWriterNotOwned` when a fence is configured but
        no role is held, and :class:`AuditStorageError` for everything else.
        On any raise the transaction has rolled back and **no row exists**.
        """
        if not isinstance(record, AuditEvent):
            raise AuditStorageError("only an AuditEvent can be appended to the audit chain")

        handle = getattr(self._fence, "handle", None) if self._fence is not None else None
        if self._fence is not None and handle is None:
            # A fence was composed but this process holds nothing. Refusing
            # here keeps the semantics identical to the runtime's admission
            # check even if a caller reaches the store directly.
            raise AuditWriterNotOwned(
                "a leadership fence is configured and this process holds no "
                "AUDIT_WRITER handle; the append is refused before any write"
            )

        document = record.to_dict()
        try:
            with self._store.atomic() as work:
                if handle is not None:
                    # THE fence. A mutation on the row a successor's
                    # acquisition mutates, carrying the token in its predicate.
                    # Zero rows means the durable record of leadership has
                    # moved past this writer -- and because this statement is
                    # in the same transaction as the INSERT below, refusing it
                    # refuses the record itself, physically.
                    fenced = work.execute(
                        sa.update(leadership_table)
                        .where(*SqlLeadershipStore.fenced_where(handle))
                        .values(heartbeat_at=work.now)
                    )
                    if fenced.rowcount != 1:
                        raise StaleAuditWriter(
                            f"fencing token {handle.fencing_token} for "
                            f"{handle.role.value} no longer matches the durable "
                            "leadership record; a successor has acquired the "
                            "role and this append was refused inside the same "
                            "transaction that would have written it"
                        )

                self._ensure_chain(work)

                # The tail advance. Conditional on the exact sequence and on
                # the durable head being the digest this record extends, so a
                # record that would fork or skip the chain changes zero rows.
                previous = record.previous_digest
                advanced = work.execute(
                    sa.update(audit_chain_table)
                    .where(
                        audit_chain_table.c.chain_id == self._chain_id,
                        audit_chain_table.c.next_sequence == record.sequence,
                        (
                            audit_chain_table.c.head_digest.is_(None)
                            if previous is None
                            else audit_chain_table.c.head_digest == previous.value
                        ),
                    )
                    .values(
                        next_sequence=record.sequence + 1,
                        head_digest=record.entry_digest.value,
                    )
                )
                if advanced.rowcount != 1:
                    raise AuditStorageError(
                        f"the audit chain tail did not match sequence "
                        f"{record.sequence} extending "
                        f"{previous.value[:16] + '...' if previous else 'genesis'}; "
                        "the durable tail has moved or the runtime's view of the "
                        "chain is stale. The append was refused and nothing was "
                        "written; re-reading the chain head is the caller's only "
                        "correct next step"
                    )

                actor_id = record.actor.principal_id if record.actor is not None else None
                work.execute(
                    sa.insert(audit_record_table).values(
                        chain_id=self._chain_id,
                        sequence=record.sequence,
                        event_id=record.event_id,
                        tenant_id=record.scope.tenant.tenant_id,
                        kind=record.kind.value,
                        recorded_at=record.recorded_at,
                        subject_reference=record.subject_reference,
                        correlation_id=record.correlation_id,
                        actor_id=actor_id,
                        entry_digest=record.entry_digest.value,
                        previous_digest=previous.value if previous else None,
                        writer_token=handle.fencing_token if handle else None,
                        document=document,
                    )
                )
        except (AuditWriterNotOwned, AuditStorageError):
            raise
        except DurabilityError as exc:
            # Classified by the durable layer; renamed here so no audit caller
            # has to import database errors. Serialization conflicts included:
            # the append did not happen, and retrying is the caller's decision,
            # never this store's.
            raise AuditStorageError(
                f"the audit append could not be persisted "
                f"({type(exc).__name__}): {exc}"
            ) from exc

    def _ensure_chain(self, work: Any) -> None:
        """Create the chain row once, savepointed, same shape as leadership's.

        The collision is the ordinary path after the first append, and on
        PostgreSQL a failed statement outside a savepoint would abort the
        whole append transaction (25P02) -- see ``UnitOfWork.attempt``.
        """
        try:
            with work.attempt():
                work.execute(
                    sa.insert(audit_chain_table).values(
                        chain_id=self._chain_id,
                        next_sequence=0,
                        head_digest=None,
                    )
                )
        except ConstraintConflict:
            return

    # ------------------------------------------------------------------
    # Reading
    # ------------------------------------------------------------------

    def read_all(self) -> Iterator[AuditEvent]:
        """Yield every record in chain order.

        The rows are fetched inside one read transaction so the sequence is a
        coherent snapshot, then restored outside it so a slow consumer does not
        hold a connection open.
        """
        yield from self._restore_rows(self._fetch())

    def query(self, criteria: AuditQuery) -> Iterator[AuditEvent]:
        """Yield records matching ``criteria`` in chain order.

        The promoted columns narrow the read in SQL -- tenant, kind, time
        window, sequence range, correlation -- and ``criteria.matches`` then
        runs over every restored record anyway. The pushdown is an efficiency;
        the Python predicate remains the single definition of what matches, so
        the two cannot drift.
        """
        conditions = []
        if criteria.tenant_id is not None:
            conditions.append(audit_record_table.c.tenant_id == criteria.tenant_id)
        if criteria.kinds is not None:
            conditions.append(
                audit_record_table.c.kind.in_([k.value for k in criteria.kinds])
            )
        if criteria.correlation_id is not None:
            conditions.append(
                audit_record_table.c.correlation_id == criteria.correlation_id
            )
        if criteria.actor_id is not None:
            conditions.append(audit_record_table.c.actor_id == criteria.actor_id)
        if criteria.since is not None:
            conditions.append(audit_record_table.c.recorded_at >= criteria.since)
        if criteria.until is not None:
            conditions.append(audit_record_table.c.recorded_at < criteria.until)
        if criteria.min_sequence is not None:
            conditions.append(audit_record_table.c.sequence >= criteria.min_sequence)
        if criteria.max_sequence is not None:
            conditions.append(audit_record_table.c.sequence <= criteria.max_sequence)

        emitted = 0
        for record in self._restore_rows(self._fetch(*conditions)):
            if criteria.matches(record):
                yield record
                emitted += 1
                if criteria.limit is not None and emitted >= criteria.limit:
                    return

    def last(self) -> Optional[AuditEvent]:
        """The most recent record -- the chain head the runtime recovers from."""
        rows = self._fetch(order_desc=True, limit=1)
        restored = list(self._restore_rows(rows))
        return restored[0] if restored else None

    def count(self) -> int:
        try:
            with self._store.reading() as work:
                value = work.execute(
                    sa.select(sa.func.count())
                    .select_from(audit_record_table)
                    .where(audit_record_table.c.chain_id == self._chain_id)
                ).scalar()
        except DurabilityError as exc:
            raise AuditStorageError(
                f"the audit chain could not be counted ({type(exc).__name__})"
            ) from exc
        return int(value or 0)

    # ------------------------------------------------------------------

    def _fetch(
        self,
        *conditions: Any,
        order_desc: bool = False,
        limit: Optional[int] = None,
    ) -> list:
        order = (
            audit_record_table.c.sequence.desc()
            if order_desc
            else audit_record_table.c.sequence.asc()
        )
        statement = (
            sa.select(audit_record_table.c.sequence, audit_record_table.c.document)
            .where(audit_record_table.c.chain_id == self._chain_id, *conditions)
            .order_by(order)
        )
        if limit is not None:
            statement = statement.limit(limit)
        try:
            with self._store.reading() as work:
                return list(work.execute(statement))
        except DurabilityError as exc:
            raise AuditStorageError(
                f"the audit chain could not be read ({type(exc).__name__})"
            ) from exc

    def _restore_rows(self, rows: list) -> Iterator[AuditEvent]:
        """Restore stored documents. Digests are restored, never recomputed.

        Recomputing on the way out would make ``verify_chain``'s tamper check
        a check that cannot fail -- the same argument that keeps execution
        digests restored in ``infrastructure/persistence``. A document that no
        longer decodes is corruption and is named as such, with its sequence.
        """
        for sequence, document in rows:
            try:
                yield AuditEvent.from_dict(document)
            except Exception as exc:  # noqa: BLE001 - any decode failure is corruption
                raise AuditCorruptionError(
                    f"cp_audit_record sequence {sequence} is not a decodable "
                    f"audit record: {exc}"
                ) from exc
