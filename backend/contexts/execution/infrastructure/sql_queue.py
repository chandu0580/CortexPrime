"""The durable work queue. Availability, never state.

The distinction this module rests on
--------------------------------------
``Execution.ready_nodes()`` is the domain answer to *what could run*. It is
derived from the graph and correct by construction. The queue is the
*operational* answer to *what should an instance pick up next*, and it exists
because rederiving that across a fleet means every instance scanning every run.

**The queue is not a second source of truth.** The execution aggregate remains
authoritative. A queue row is a reference — tenant, execution, node, kind, and
enough identity to find the real thing — and everything that decides whether the
work may actually run is re-derived downstream from the aggregate, the binding
and the authorization. Losing the queue loses ordering and claims, not work:
``ready_nodes()`` recomputes it.

That is also why no authority is reconstructed from a queue row. A row saying
"node n1 of execution E" is a hint that E is worth loading. It is not a grant,
and there is deliberately nothing on it — no capability, no principal, no digest
— that could be mistaken for one.

Claiming is one statement
---------------------------
    UPDATE cp_queue
       SET claimed_by = :instance, claimed_until = :until
     WHERE (execution_id, node_id) IN (…candidates…)
       AND (claimed_until IS NULL OR claimed_until <= now)

then read back **what this instance actually holds**. Two dispatchers claiming
concurrently cannot both take an item: the second one's predicate no longer
matches. Reading back the request rather than the result is how two instances
both believe they own the same node, so the read-back filters on ``claimed_by``.

There is no ``SELECT`` → Python ``if`` → ``UPDATE`` anywhere in this module.

Claims expire, they do not delete
-----------------------------------
A claim is a lease. An instance that dies between claiming an item and
establishing an execution lease leaves an item that returns to the queue rather
than one that vanished — the same reasoning as the execution lease itself, one
level up. ``claim_count`` records how many times that has happened, which is what
distinguishes "busy" from "an item nothing can process".

Ordering, and what is actually guaranteed
-------------------------------------------
    priority DESC, available_at ASC, sequence ASC

``sequence`` is database-assigned and unique, so the order is **total** — two
items with equal priority and equal availability still have exactly one order,
and it is the order they were enqueued in. Nothing depends on dictionary order,
object identity, randomness, or a wall clock as a tiebreak.

What that guarantee is *not*: it is per-claim-batch ordering, not global
processing order. Several instances claiming concurrently each take the head of
what they can see, so item 5 can finish before item 3. Claiming order is
deterministic; completion order is not, and this module does not pretend
otherwise.
"""

from __future__ import annotations

import logging

from datetime import datetime, timedelta, timezone
from typing import Any, Optional, Sequence

import sqlalchemy as sa

from backend.contracts.errors import ContractViolation
from backend.contracts.storage import StorageBinding, StorageOperation
from backend.contexts.execution.domain.worker import WorkerKind
from backend.contexts.execution.infrastructure.queue import QueueItem
from backend.database.durable.errors import ConstraintConflict
from backend.database.durable.session import (
    DurableStore,
    NoDurableStore,
    UnitOfWork,
    enlisted,
)
from backend.database.durable.tables import queue_table
from backend.platform.storage import RepositoryGuard

__all__ = ["SqlExecutionQueue", "QUEUE_BINDING", "QUEUE_METRICS"]

log = logging.getLogger(__name__)

QUEUE_BINDING = StorageBinding(
    record_type="QueueItem", scope_column="tenant_id", platform_internal_allowed=True
)

QUEUE_METRICS = (
    "queue.enqueue",
    "queue.claim",
    "queue.claim_conflict",
    "queue.release",
    "queue.remove",
)


class SqlExecutionQueue:
    """The durable ``ExecutionQueue``. Same port, cross-process guarantee."""

    def __init__(self, store: DurableStore, *, metrics: Optional[Any] = None) -> None:
        if not isinstance(store, DurableStore):
            raise NoDurableStore(
                "a durable queue requires a store; an in-process queue across a "
                "fleet means every instance holds a different idea of what is "
                "available, and two of them claim the same node"
            )
        self._store = store
        self._guard = RepositoryGuard(QUEUE_BINDING)
        self._metrics = metrics

    # ------------------------------------------------------------------
    # Enqueue
    # ------------------------------------------------------------------

    def enqueue(
        self,
        context: Any,
        item: QueueItem,
        *,
        workflow_id: Optional[str] = None,
        workflow_digest: Optional[str] = None,
        attempt_id: Optional[str] = None,
        available_at: Optional[datetime] = None,
        unit: Optional[UnitOfWork] = None,
    ) -> bool:
        """Make work available. Enqueuing the same node twice is a no-op.

        The deduplication is the **primary key**, not a check: two dispatchers
        deciding the same node is ready both INSERT and the second collides. A
        read-then-insert would let both pass, and the node would be claimed twice.

        ``available_at`` in the future is how a planned retry waits out its
        backoff durably. Holding it in memory would lose it on the restart that
        made the retry necessary in the first place.
        """
        access = self._guard.authorize(StorageOperation.WRITE, context)
        with enlisted(self._store, unit) as work:
            now = work.now
            try:
                work.execute(
                    sa.insert(queue_table).values(
                        execution_id=item.execution_id,
                        node_id=item.node_id,
                        tenant_id=access.tenant_id,
                        workflow_id=workflow_id,
                        workflow_digest=workflow_digest,
                        worker_kind=item.worker_kind.value,
                        attempt_id=attempt_id,
                        priority=item.priority,
                        available_at=available_at or item.enqueued_at or now,
                        enqueued_at=item.enqueued_at or now,
                        sequence=self._next_sequence(work),
                        claimed_by=None,
                        claimed_until=None,
                        claim_count=0,
                    )
                )
            except ConstraintConflict:
                # Already queued. Not an error -- it is the primary key doing
                # what it is here for.
                return False
        self._count("queue.enqueue", access.tenant_id)
        return True

    # ------------------------------------------------------------------
    # Claim
    # ------------------------------------------------------------------

    def claim(
        self,
        context: Any,
        worker_id: str,
        kinds: Sequence[WorkerKind],
        seconds: int,
        *,
        now: Optional[datetime] = None,
        limit: int = 1,
        unit: Optional[UnitOfWork] = None,
    ) -> Optional[QueueItem]:
        """Take one item this instance can run, for a bounded time.

        Returns ``None`` when there is nothing — the ordinary case for a healthy
        fleet, and never an exception.

        Satisfies the ``ExecutionQueue`` port, so a caller written against the
        in-memory queue works against this one unchanged. ``claim_batch`` is the
        multi-item form for a dispatcher that wants several.
        """
        taken = self.claim_batch(
            context, worker_id, kinds, seconds, now=now, limit=limit, unit=unit
        )
        return taken[0] if taken else None

    def claim_batch(
        self,
        context: Any,
        worker_id: str,
        kinds: Sequence[WorkerKind],
        seconds: int,
        *,
        now: Optional[datetime] = None,
        limit: int = 1,
        unit: Optional[UnitOfWork] = None,
    ) -> tuple:
        """Claim up to ``limit`` items, exclusively, across processes."""
        if not isinstance(worker_id, str) or not worker_id.strip():
            raise ContractViolation(
                "a claim must name the instance taking it; an anonymous claim "
                "cannot be released by whoever made it, and cannot be fenced"
            )
        if seconds < 1:
            raise ContractViolation("a claim must last at least a second")
        wanted = [k.value for k in kinds]
        if not wanted:
            return ()

        access = self._guard.authorize(StorageOperation.WRITE, context)
        with enlisted(self._store, unit) as work:
            moment = now or work.now
            free = sa.or_(
                queue_table.c.claimed_until.is_(None),
                queue_table.c.claimed_until <= moment,
            )
            candidates = work.execute(
                sa.select(queue_table.c.execution_id, queue_table.c.node_id)
                .where(
                    queue_table.c.worker_kind.in_(wanted),
                    queue_table.c.available_at <= moment,
                    free,
                    *self._tenant_predicate(access),
                )
                # The total order. Priority first, then when it became
                # available, then the enqueue sequence -- which is unique, so
                # there is never a tie left for something non-deterministic to
                # break.
                .order_by(
                    queue_table.c.priority.desc(),
                    queue_table.c.available_at.asc(),
                    queue_table.c.sequence.asc(),
                )
                .limit(limit)
            ).all()
            if not candidates:
                return ()

            keys = [(row[0], row[1]) for row in candidates]
            work.execute(
                sa.update(queue_table)
                .where(
                    sa.tuple_(queue_table.c.execution_id, queue_table.c.node_id).in_(keys)
                    if _supports_tuple_in(work)
                    else sa.or_(
                        *[
                            sa.and_(
                                queue_table.c.execution_id == e,
                                queue_table.c.node_id == n,
                            )
                            for e, n in keys
                        ]
                    ),
                    # The exclusivity. A rival that claimed between the select
                    # and here no longer matches, so this instance takes fewer
                    # items rather than taking the same ones twice.
                    free,
                    *self._tenant_predicate(access),
                )
                .values(
                    claimed_by=worker_id,
                    claimed_until=moment + timedelta(seconds=seconds),
                    claim_count=queue_table.c.claim_count + 1,
                )
            )
            # Read back **what this instance holds**, not what it asked for.
            rows = work.execute(
                sa.select(queue_table)
                .where(
                    queue_table.c.claimed_by == worker_id,
                    queue_table.c.claimed_until > moment,
                    *self._tenant_predicate(access),
                )
                .order_by(
                    queue_table.c.priority.desc(),
                    queue_table.c.available_at.asc(),
                    queue_table.c.sequence.asc(),
                )
                .limit(limit)
            ).mappings().all()

        if len(rows) < len(keys):
            self._count("queue.claim_conflict", access.tenant_id)
        if rows:
            self._count("queue.claim", access.tenant_id)
        return tuple(_item(row) for row in rows)

    # ------------------------------------------------------------------
    # Release and removal
    # ------------------------------------------------------------------

    def release(
        self,
        context: Any,
        execution_id: str,
        node_id: str,
        *,
        available_at: Optional[datetime] = None,
        unit: Optional[UnitOfWork] = None,
    ) -> None:
        """Return a claimed item without removing it.

        ``available_at`` moves it into the future, which is how a planned retry's
        backoff becomes durable rather than a sleep somebody is holding.
        """
        access = self._guard.authorize(StorageOperation.WRITE, context)
        with enlisted(self._store, unit) as work:
            values: dict = {"claimed_by": None, "claimed_until": None}
            if available_at is not None:
                values["available_at"] = available_at
            work.execute(
                sa.update(queue_table)
                .where(
                    queue_table.c.execution_id == execution_id,
                    queue_table.c.node_id == node_id,
                    *self._tenant_predicate(access),
                )
                .values(**values)
            )
        self._count("queue.release", access.tenant_id)

    def remove(
        self,
        context: Any,
        execution_id: str,
        node_id: str,
        *,
        unit: Optional[UnitOfWork] = None,
    ) -> None:
        """Take the item out. Called when the node reached a terminal state.

        Deleting is correct here and only here: the queue holds availability, and
        a finished node is not available. The *record* of what happened lives on
        the aggregate and in the outbox, neither of which this touches.
        """
        access = self._guard.authorize(StorageOperation.DELETE, context)
        with enlisted(self._store, unit) as work:
            work.execute(
                sa.delete(queue_table).where(
                    queue_table.c.execution_id == execution_id,
                    queue_table.c.node_id == node_id,
                    *self._tenant_predicate(access),
                )
            )
        self._count("queue.remove", access.tenant_id)

    # ------------------------------------------------------------------
    # Observation
    # ------------------------------------------------------------------

    def depth(self, context: Any, *, unit: Optional[UnitOfWork] = None) -> int:
        access = self._guard.authorize(StorageOperation.READ, context)
        with enlisted(self._store, unit) as work:
            return int(
                work.execute(
                    sa.select(sa.func.count())
                    .select_from(queue_table)
                    .where(*self._tenant_predicate(access))
                ).scalar()
                or 0
            )

    def pending(
        self,
        context: Any,
        *,
        now: Optional[datetime] = None,
        limit: int = 100,
        unit: Optional[UnitOfWork] = None,
    ) -> tuple:
        """Items nobody holds and that are available. What a depth gauge means."""
        access = self._guard.authorize(StorageOperation.READ, context)
        with enlisted(self._store, unit) as work:
            moment = now or work.now
            rows = work.execute(
                sa.select(queue_table)
                .where(
                    queue_table.c.available_at <= moment,
                    sa.or_(
                        queue_table.c.claimed_until.is_(None),
                        queue_table.c.claimed_until <= moment,
                    ),
                    *self._tenant_predicate(access),
                )
                .order_by(
                    queue_table.c.priority.desc(),
                    queue_table.c.available_at.asc(),
                    queue_table.c.sequence.asc(),
                )
                .limit(limit)
            ).mappings().all()
        return tuple(_item(row) for row in rows)

    def tenant_depths(
        self, context: Any, *, unit: Optional[UnitOfWork] = None
    ) -> dict:
        """Depth per tenant, for an operator watching for monopolisation.

        **Observation, not enforcement.** There is no tenant quota in this
        platform's policy, and inventing one here would be a rate limit nobody
        decided on — §5 of the Phase 5.2 directive forbids exactly that. What
        this provides is the seam: the number an operator or a future policy
        would need, produced deterministically and durably.

        Requires platform-internal authority, because a per-tenant breakdown is
        a disclosure to anybody who is not the platform.
        """
        access = self._guard.authorize(StorageOperation.READ, context)
        if self._guard.scope_filter(access) is not None:
            raise ContractViolation(
                "a per-tenant queue breakdown requires platform-internal "
                "authority; showing one tenant how much work another has is a "
                "disclosure"
            )
        with enlisted(self._store, unit) as work:
            rows = work.execute(
                sa.select(queue_table.c.tenant_id, sa.func.count())
                .group_by(queue_table.c.tenant_id)
                .order_by(queue_table.c.tenant_id)
            ).all()
        return {row[0]: int(row[1]) for row in rows}

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _next_sequence(work: UnitOfWork) -> int:
        """The next enqueue sequence, allocated inside this transaction.

        ``MAX + 1`` under the transaction, with a unique constraint behind it.
        Two instances enqueuing concurrently can read the same maximum; the
        constraint refuses the second, which the caller sees as
        ``ConstraintConflict`` and treats as "already queued" — the same answer
        the primary key gives, and safe because the item it wanted is present
        either way.

        A database sequence would avoid the retry, and would also be
        PostgreSQL-specific in a module that must run on both. The trade is
        recorded rather than hidden.
        """
        current = work.execute(sa.select(sa.func.max(queue_table.c.sequence))).scalar()
        return int(current or 0) + 1

    def _tenant_predicate(self, access: Any) -> tuple:
        scope = self._guard.scope_filter(access)
        if scope is None:
            return ()
        column, value = scope
        return (queue_table.c[column] == value,)

    def _count(self, name: str, tenant: Optional[str]) -> None:
        if self._metrics is None or name not in QUEUE_METRICS:
            return
        try:
            self._metrics.increment(name, labels={"tenant": tenant or "platform"})
        except Exception:  # noqa: BLE001 - measurement never changes an outcome
            log.debug("queue metric failed", exc_info=False)


def _supports_tuple_in(work: UnitOfWork) -> bool:
    """Whether this dialect can compare a row tuple against a list.

    PostgreSQL can; SQLite's support has been version-dependent. The fallback is
    an ``OR`` of equality pairs, which is identical in meaning and slightly
    longer in SQL — a portability accommodation, not a behavioural difference.
    """
    return work.dialect == "postgresql"


def _item(row: Any) -> QueueItem:
    """Rebuild the port's ``QueueItem``. **A reference, never authority.**

    Carries what a dispatcher needs to find the real thing and nothing that
    could be mistaken for permission — no capability, no principal, no digest.
    Whether the work may run is re-derived from the aggregate and the binding
    every time.
    """
    return QueueItem(
        execution_id=row["execution_id"],
        node_id=row["node_id"],
        worker_kind=WorkerKind(row["worker_kind"]),
        enqueued_at=_aware(row["enqueued_at"]),
        claimed_by=row["claimed_by"],
        claimed_until=_aware(row["claimed_until"]),
        priority=int(row["priority"]),
    )


def _aware(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
