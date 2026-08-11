"""The durable outbox. The event survives the process that recorded it.

What durability changes here
------------------------------
The in-memory outbox was honest about being a contract with a placeholder behind
it: a restart lost every pending entry, exactly as the in-memory repository lost
every run. The guarantee it *described* — the event is recorded in the same
transaction as the state, so publication may fail, retry or duplicate without
ever losing the fact — is now real, because the transaction is real.

Nothing in the contract changed. ``record``, ``claim``, ``mark_published`` and
``mark_failed`` mean what they meant; the difference is what happens when the
process dies between them.

Still at-least-once, and still saying so
------------------------------------------
An entry can be published, the acknowledgement lost, and the entry published
again. That is the honest guarantee for any outbox without a distributed
transaction across the publisher's target, and **it is not upgraded here**.
``event_id`` is unique per tenant so the same event is never *recorded* twice,
and a consumer that deduplicates on it is correct. A consumer that assumes single
delivery is not, and no column in this table makes it so.

Ordering
----------
``sequence`` is database-assigned and monotonic. Causal order comes from it and
never from ``recorded_at``: two events recorded in the same microsecond tie on a
clock, and a tie means two publishers can disagree about which fact came first.

Exclusive claim, across processes
-----------------------------------
``claim`` is one ``UPDATE ... WHERE`` over a bounded set of ids, and the rowcount
is the answer. Two publishers claiming simultaneously cannot both take an entry:
the second one's predicate no longer matches, because the first one's update set
``claimed_by``. The claim **expires**, so a publisher that dies does not strand
the entry forever — which is the whole reason it is a lease and not a flag.

Events are stored serialized
------------------------------
The in-memory outbox held the live event object. A durable one cannot, so the
row carries the event's own ``to_dict``. The returned ``OutboxEntry`` still
carries the live object when one was supplied, so callers that publish
immediately after recording are unchanged; a publisher reading rows back after a
restart gets the serialized payload, which is what a restart can offer.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any, Optional, Sequence

import sqlalchemy as sa

from backend.contracts.errors import ContractViolation
from backend.contexts.execution.infrastructure.outbox import OutboxEntry, OutboxStatus
from backend.database.durable.errors import ConstraintConflict
from backend.database.durable.session import (
    DurableStore,
    NoDurableStore,
    UnitOfWork,
    enlisted,
)
from backend.database.durable.tables import outbox_table

__all__ = ["SqlExecutionOutbox", "MAX_PUBLISH_ATTEMPTS"]

log = logging.getLogger(__name__)

#: Kept identical to the in-memory outbox. Changing the dead-letter threshold
#: when persistence arrived would be a semantic change smuggled in as a
#: durability change.
MAX_PUBLISH_ATTEMPTS = 10


class SqlExecutionOutbox:
    """The durable ``ExecutionOutbox``. Same contract, real guarantee."""

    def __init__(self, store: DurableStore, *, metrics: Optional[Any] = None) -> None:
        if not isinstance(store, DurableStore):
            raise NoDurableStore(
                "a durable outbox requires a store; an outbox that claims "
                "durability it does not have is worse than none, because it "
                "invites callers to rely on a guarantee that is not there"
            )
        self._store = store
        self._metrics = metrics

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def record(
        self,
        context: Any,
        execution_id: str,
        events: Sequence[Any],
        *,
        unit: Optional[UnitOfWork] = None,
    ) -> tuple:
        """Append events. **Give this the caller's unit to get atomicity.**

        Handed a ``unit``, the rows commit with whatever state change that unit
        is writing — which is the entire point of an outbox. Handed none it
        commits on its own, which is correct for an event that accompanies no
        state change and is *not* correct for one that does. The application
        service decides, because it is the only layer that knows.
        """
        tenant_id = _tenant_of(context)
        recorded: list = []
        with self._scope(unit) as work:
            for event in events:
                event_id = str(getattr(event, "event_id", "") or "")
                entry_id = f"{execution_id}:{event_id or _fallback_id(event)}"
                payload = _serialise(event)
                try:
                    # Savepointed. This handler **swallows** the conflict and lets the
                    # caller carry on, and the caller is frequently inside a larger
                    # transaction -- the outbox write shares one with the state change
                    # that produced the event, by design. On PostgreSQL a failed
                    # statement aborts that whole transaction, so swallowing the error
                    # without a savepoint would leave the caller committing into a
                    # transaction the database had already abandoned.
                    with work.attempt():
                        result = work.execute(
                            sa.insert(outbox_table).values(
                                entry_id=entry_id,
                                tenant_id=tenant_id,
                                execution_id=execution_id,
                                event_type=getattr(type(event), "EVENT_TYPE", "unknown"),
                                event_id=event_id or None,
                                payload=payload,
                                status=OutboxStatus.PENDING.value,
                                attempts=0,
                                recorded_at=work.now,
                            )
                        )
                        row = result.inserted_primary_key
                except ConstraintConflict:
                    # The same event recorded twice. Not an error: a command
                    # replayed after an unknown commit outcome legitimately
                    # arrives here, and the unique constraint is precisely how
                    # that stops being a duplicated log entry.
                    log.info(
                        "outbox event already recorded; the duplicate was refused "
                        "by the unique constraint rather than appended"
                    )
                    row = work.execute(
                        sa.select(outbox_table.c.sequence).where(
                            outbox_table.c.entry_id == entry_id,
                            outbox_table.c.tenant_id == tenant_id,
                        )
                    ).first()
                sequence = int(row[0]) if row else 0
                recorded.append(
                    OutboxEntry(
                        entry_id=entry_id,
                        execution_id=execution_id,
                        tenant_id=tenant_id,
                        event_type=getattr(type(event), "EVENT_TYPE", "unknown"),
                        # The live object, so a caller publishing immediately
                        # after recording is unchanged by durability.
                        event=event,
                        recorded_at=work.now,
                        sequence=sequence,
                        event_id=event_id,
                    )
                )
        return tuple(recorded)

    # ------------------------------------------------------------------
    # Reading
    # ------------------------------------------------------------------

    def pending(self, context: Any, limit: int = 100) -> tuple:
        """Unpublished entries in causal order. Sequence, never timestamp."""
        tenant_id = _tenant_of(context)
        with self._store.reading() as work:
            rows = work.execute(
                sa.select(outbox_table)
                .where(
                    outbox_table.c.tenant_id == tenant_id,
                    outbox_table.c.status == OutboxStatus.PENDING.value,
                )
                .order_by(outbox_table.c.sequence)
                .limit(limit)
            ).mappings().all()
        return tuple(_entry(row) for row in rows)

    def dead_lettered(self, context: Any) -> tuple:
        """Entries publication gave up on. Never deleted — this is what somebody
        looks for after an incident, and deleting it would erase the evidence."""
        tenant_id = _tenant_of(context)
        with self._store.reading() as work:
            rows = work.execute(
                sa.select(outbox_table)
                .where(
                    outbox_table.c.tenant_id == tenant_id,
                    outbox_table.c.status == OutboxStatus.ABANDONED.value,
                )
                .order_by(outbox_table.c.sequence)
            ).mappings().all()
        return tuple(_entry(row) for row in rows)

    #: The name the in-memory outbox also exposes. Kept so a caller written
    #: against one works against the other.
    abandoned = dead_lettered

    def entries_for(self, context: Any, execution_id: str) -> tuple:
        """Every entry for one run, oldest first, published ones included."""
        tenant_id = _tenant_of(context)
        with self._store.reading() as work:
            rows = work.execute(
                sa.select(outbox_table)
                .where(
                    outbox_table.c.tenant_id == tenant_id,
                    outbox_table.c.execution_id == execution_id,
                )
                .order_by(outbox_table.c.sequence)
            ).mappings().all()
        return tuple(_entry(row) for row in rows)

    # ------------------------------------------------------------------
    # Claiming
    # ------------------------------------------------------------------

    def claim(
        self,
        context: Any,
        *,
        publisher_id: str,
        limit: int = 100,
        seconds: int = 60,
        now: Optional[Any] = None,
    ) -> tuple:
        """Take exclusive publication rights, in sequence order, across processes.

        Two steps in one transaction: select the candidate ids in order, then
        ``UPDATE ... WHERE`` those ids *and* still-unclaimed. The second step is
        where exclusivity comes from — a rival publisher that claimed between the
        two no longer matches the predicate, so this one takes fewer entries
        rather than taking the same ones twice.

        The claim expires. A publisher that dies mid-batch does not strand its
        entries; another picks them up once ``claimed_until`` passes, which is
        the difference between a lease and a flag.
        """
        if not isinstance(publisher_id, str) or not publisher_id.strip():
            raise ContractViolation(
                "a claim must name its publisher; an anonymous claim cannot be "
                "released by whoever made it"
            )
        tenant_id = _tenant_of(context)
        with self._store.atomic(now=now) as work:
            moment = work.now
            candidates = work.execute(
                sa.select(outbox_table.c.entry_id)
                .where(
                    outbox_table.c.tenant_id == tenant_id,
                    outbox_table.c.status == OutboxStatus.PENDING.value,
                    sa.or_(
                        outbox_table.c.claimed_until.is_(None),
                        outbox_table.c.claimed_until < moment,
                    ),
                )
                .order_by(outbox_table.c.sequence)
                .limit(limit)
            ).scalars().all()
            if not candidates:
                return ()

            work.execute(
                sa.update(outbox_table)
                .where(
                    outbox_table.c.entry_id.in_(list(candidates)),
                    outbox_table.c.tenant_id == tenant_id,
                    outbox_table.c.status == OutboxStatus.PENDING.value,
                    sa.or_(
                        outbox_table.c.claimed_until.is_(None),
                        outbox_table.c.claimed_until < moment,
                    ),
                )
                .values(
                    claimed_by=publisher_id,
                    claimed_until=moment + timedelta(seconds=seconds),
                )
            )
            # Read back **what this publisher actually holds**, not what it asked
            # for. A rival that won some of the candidates leaves them stamped
            # with its own id, and returning the request rather than the result
            # is how two publishers both hand over the same event.
            rows = work.execute(
                sa.select(outbox_table)
                .where(
                    outbox_table.c.entry_id.in_(list(candidates)),
                    outbox_table.c.claimed_by == publisher_id,
                )
                .order_by(outbox_table.c.sequence)
            ).mappings().all()
        self._count("outbox.claim", len(rows))
        return tuple(_entry(row) for row in rows)

    # ------------------------------------------------------------------
    # Acknowledgement
    # ------------------------------------------------------------------

    def mark_published(
        self, context: Any, entry_id: str, *, unit: Optional[UnitOfWork] = None
    ) -> None:
        tenant_id = _tenant_of(context)
        with self._scope(unit) as work:
            work.execute(
                sa.update(outbox_table)
                .where(
                    outbox_table.c.entry_id == entry_id,
                    outbox_table.c.tenant_id == tenant_id,
                )
                .values(
                    status=OutboxStatus.PUBLISHED.value,
                    published_at=work.now,
                    attempts=outbox_table.c.attempts + 1,
                    claimed_by=None,
                    claimed_until=None,
                )
            )
        self._count("outbox.publish", 1)

    def mark_failed(
        self,
        context: Any,
        entry_id: str,
        error: str,
        *,
        unit: Optional[UnitOfWork] = None,
    ) -> None:
        """Record a failed publication, dead-lettering once attempts run out.

        The threshold is applied in SQL with a ``CASE`` so the read and the write
        are one statement: computing the new status from a value read a moment
        ago would let two publishers each see attempt 9 and each write 10.
        """
        tenant_id = _tenant_of(context)
        with self._scope(unit) as work:
            work.execute(
                sa.update(outbox_table)
                .where(
                    outbox_table.c.entry_id == entry_id,
                    outbox_table.c.tenant_id == tenant_id,
                )
                .values(
                    attempts=outbox_table.c.attempts + 1,
                    last_error=str(error)[:512],
                    claimed_by=None,
                    claimed_until=None,
                    status=sa.case(
                        (
                            outbox_table.c.attempts + 1 >= MAX_PUBLISH_ATTEMPTS,
                            OutboxStatus.ABANDONED.value,
                        ),
                        else_=OutboxStatus.PENDING.value,
                    ),
                )
            )
            abandoned = work.execute(
                sa.select(outbox_table.c.status).where(
                    outbox_table.c.entry_id == entry_id,
                    outbox_table.c.tenant_id == tenant_id,
                )
            ).scalar()
        if abandoned == OutboxStatus.ABANDONED.value:
            self._count("outbox.dead_letter", 1)

    # ------------------------------------------------------------------

    def _scope(self, unit: Optional[UnitOfWork]):
        return enlisted(self._store, unit)

    def _count(self, name: str, amount: int) -> None:
        if self._metrics is None or amount <= 0:
            return
        try:
            self._metrics.increment(name, labels={})
        except Exception:  # noqa: BLE001 - measurement never changes an outcome
            log.debug("outbox metric failed", exc_info=False)


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------


def _tenant_of(context: Any) -> str:
    tenant = getattr(context, "tenant_id", None)
    if not tenant:
        raise ContractViolation(
            "an outbox entry must be attributable to a tenant; recording one "
            "without a context would produce an event nobody owns"
        )
    return str(tenant)


def _serialise(event: Any) -> dict:
    """The event as storable primitives, or a refusal.

    No fallback to ``repr``. An event that cannot be serialised cannot be
    republished after a restart, and storing a string that looks like an event is
    how a consumer receives something it cannot parse and drops it.
    """
    to_dict = getattr(event, "to_dict", None)
    if callable(to_dict):
        payload = to_dict()
        if isinstance(payload, dict):
            return payload
    raise ContractViolation(
        f"{type(event).__name__} cannot be recorded durably: it has no "
        "dictionary form, so it could not be republished after a restart"
    )


def _fallback_id(event: Any) -> str:
    """An entry id for an event carrying no identity of its own.

    Derived from the event's content so the same event produces the same entry
    id — which keeps the duplicate-refusal property even for events that predate
    carrying an ``event_id``.
    """
    from backend.platform.hashing import compute_digest

    try:
        return compute_digest(_serialise(event)).value[:32]
    except Exception:  # noqa: BLE001
        raise ContractViolation(
            f"{type(event).__name__} has neither an event id nor a stable "
            "content digest, so a duplicate could not be detected"
        ) from None


def _entry(row: Any) -> OutboxEntry:
    """Rebuild the entry from a row. The payload, not a live event object.

    A restart cannot produce the original object, and pretending otherwise would
    hand a publisher something it cannot serialise. ``event`` is the stored
    mapping, which is what a publisher after a restart actually has.
    """
    return OutboxEntry(
        entry_id=row["entry_id"],
        execution_id=row["execution_id"],
        tenant_id=row["tenant_id"],
        event_type=row["event_type"],
        event=row["payload"],
        recorded_at=row["recorded_at"],
        status=OutboxStatus(row["status"]),
        attempts=row["attempts"],
        published_at=row["published_at"],
        last_error=row["last_error"],
        sequence=int(row["sequence"]),
        event_id=row["event_id"] or "",
        claimed_by=row["claimed_by"],
        claimed_until=row["claimed_until"],
    )
