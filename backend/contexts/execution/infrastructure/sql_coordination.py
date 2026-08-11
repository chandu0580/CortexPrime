"""Durable node leases and durable idempotency. Two cross-process invariants.

Why these are tables and not part of the execution document
-------------------------------------------------------------
Everything else about a run lives in the aggregate. These two do not, and the
reason is the same for both: **they are invariants two processes can violate
simultaneously**, so only the database can hold them.

    "exactly one worker holds this node"    a primary key
    "this idempotency key is used once"     a primary key

Written as fields inside the execution document they would be enforced by
whoever read the document last, which is precisely the guarantee that does not
survive a second process.

The lease is not the aggregate's lease
----------------------------------------
``NodeRun.lease`` remains the domain's record of who holds a node, unchanged, and
it is still what the aggregate's invariants read. This table is the *claim*: the
thing two workers race for, decided by an INSERT that one of them loses. The
aggregate then records the outcome of a race it did not have to arbitrate.

That is deliberately not one thing. Making the aggregate's lease the arbiter
would mean the domain had to know about database constraints; making this the
domain's lease would mean a durable row could contradict an aggregate that
refuses to load.

Fencing
---------
Every grant increments ``fence``. A worker that was partitioned, missed its
expiry, and comes back believing it still holds the node can be told otherwise by
comparing the fence it was granted against the current one — which a timestamp
cannot do, because the two machines' clocks disagree and that is the whole
problem. Nothing in this phase *acts* on the fence beyond returning it; it is
recorded now so a later phase has something truthful to act on.

Heartbeats do not extend authority
------------------------------------
``heartbeat`` moves ``heartbeat_at`` and leaves ``expires_at`` alone. A worker
that keeps saying "still here" does not thereby keep permission indefinitely: the
lease expires when it was granted to expire, and renewing it is a separate,
explicit act with its own bound. A heartbeat that extended the expiry would make
an unresponsive-but-alive worker hold a node forever.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional, Sequence

import sqlalchemy as sa

from backend.contracts.errors import ContractViolation
from backend.contracts.storage import StorageBinding, StorageOperation
from backend.database.durable.errors import ConstraintConflict
from backend.database.durable.session import (
    DurableStore,
    NoDurableStore,
    UnitOfWork,
    enlisted,
)
from backend.database.durable.tables import idempotency_table, node_lease_table
from backend.platform.storage import RepositoryGuard

__all__ = [
    "SqlNodeLeaseStore",
    "SqlIdempotencyStore",
    "LeaseState",
    "LeaseHeld",
    "IdempotencyConflict",
    "NODE_LEASE_BINDING",
    "IDEMPOTENCY_BINDING",
]

NODE_LEASE_BINDING = StorageBinding(
    record_type="NodeLease", scope_column="tenant_id", platform_internal_allowed=True
)
IDEMPOTENCY_BINDING = StorageBinding(
    record_type="IdempotencyKey", scope_column="tenant_id", platform_internal_allowed=True
)


class LeaseHeld(ContractViolation):
    """Another worker holds this node, and the lease has not expired.

    A deterministic refusal, which is the property that matters: the loser of a
    race is told it lost and by whom, rather than being handed a second lease or
    silently overwriting the first.
    """

    def __init__(self, *, execution_id: str, node_id: str, worker_id: str) -> None:
        super().__init__(
            f"node {node_id} of execution {execution_id} is leased to "
            f"{worker_id}; the lease is refused rather than granted twice"
        )
        self.execution_id = execution_id
        self.node_id = node_id
        self.worker_id = worker_id


class IdempotencyConflict(ContractViolation):
    """This idempotency key has been used, by a different action.

    Distinguished from a repeat of the *same* action, which is not a conflict —
    it is the key doing its job.
    """

    def __init__(self, *, key: str, existing_execution: str) -> None:
        super().__init__(
            f"idempotency key {key!r} is already recorded against execution "
            f"{existing_execution}; reusing it for a different action would make "
            "two operations one"
        )
        self.key = key
        self.existing_execution = existing_execution


class LeaseState:
    """What a lease row says, in the vocabulary recovery reads.

    Four answers, and the fourth is not a hedge. ``AMBIGUOUS`` is a lease past
    its expiry whose holder was heartbeating recently enough that it may still be
    running — reclaiming it would run the node twice, and refusing forever would
    strand it. Recovery decides; this reports.
    """

    ACTIVE = "active"
    EXPIRED = "expired"
    RELEASED = "released"
    AMBIGUOUS = "ambiguous"


class SqlNodeLeaseStore:
    """One row per node. The primary key is the concurrency mechanism."""

    def __init__(self, store: DurableStore) -> None:
        if not isinstance(store, DurableStore):
            raise NoDurableStore("a durable lease store requires a store")
        self._store = store
        self._guard = RepositoryGuard(NODE_LEASE_BINDING)

    # ------------------------------------------------------------------

    def acquire(
        self,
        context: Any,
        *,
        execution_id: str,
        node_id: str,
        worker_id: str,
        lease_id: str,
        seconds: int,
        attempt_id: Optional[str] = None,
        unit: Optional[UnitOfWork] = None,
    ) -> dict:
        """Claim a node, or lose the race deterministically.

        Two workers arriving together both attempt the INSERT; the primary key
        lets exactly one through and the other gets ``ConstraintConflict``, which
        becomes either a grant (the existing lease had expired and this worker
        took it over) or ``LeaseHeld``. There is no read-then-write, so there is
        no window between deciding it is free and taking it.
        """
        from datetime import timedelta

        if seconds < 1:
            raise ContractViolation("a lease must last at least a second")
        access = self._guard.authorize(StorageOperation.WRITE, context)
        with self._scope(unit) as work:
            now = work.now
            expires = now + timedelta(seconds=seconds)
            try:
                # Savepointed. The INSERT is *expected* to fail whenever a lease
                # row already exists, and PostgreSQL treats a failed statement as
                # a failed transaction -- so without this the takeover UPDATE
                # below would run in an aborted transaction and raise 25P02.
                with work.attempt():
                    work.execute(
                        sa.insert(node_lease_table).values(
                            execution_id=execution_id,
                            node_id=node_id,
                            tenant_id=access.tenant_id,
                            lease_id=lease_id,
                            worker_id=worker_id,
                            attempt_id=attempt_id,
                            granted_at=now,
                            expires_at=expires,
                            heartbeat_at=now,
                            released_at=None,
                            fence=1,
                        )
                    )
                return self._describe(
                    execution_id, node_id, worker_id, lease_id, now, expires, 1
                )
            except ConstraintConflict:
                pass  # A row exists. Whether it is still authoritative is next.

            # Take over only from a lease that is provably finished: released, or
            # expired. The predicate is the check -- a rival that renews between
            # our read and our write no longer matches it, so the takeover fails
            # rather than stealing a live lease.
            result = work.execute(
                sa.update(node_lease_table)
                .where(
                    node_lease_table.c.execution_id == execution_id,
                    node_lease_table.c.node_id == node_id,
                    *self._tenant_predicate(access),
                    sa.or_(
                        node_lease_table.c.released_at.isnot(None),
                        node_lease_table.c.expires_at <= now,
                    ),
                )
                .values(
                    lease_id=lease_id,
                    worker_id=worker_id,
                    attempt_id=attempt_id,
                    granted_at=now,
                    expires_at=expires,
                    heartbeat_at=now,
                    released_at=None,
                    fence=node_lease_table.c.fence + 1,
                )
            )
            if result.rowcount == 1:
                row = self._row(work, access, execution_id, node_id)
                return self._describe(
                    execution_id, node_id, worker_id, lease_id, now, expires,
                    int(row["fence"]),
                )

            row = self._row(work, access, execution_id, node_id)
            if row is None:
                # Present a moment ago, gone now, and not ours. Refused rather
                # than retried: something else is mutating this node.
                raise LeaseHeld(
                    execution_id=execution_id, node_id=node_id, worker_id="unknown"
                )
            raise LeaseHeld(
                execution_id=execution_id,
                node_id=node_id,
                worker_id=row["worker_id"],
            )

    def heartbeat(
        self,
        context: Any,
        *,
        execution_id: str,
        node_id: str,
        lease_id: str,
        unit: Optional[UnitOfWork] = None,
    ) -> bool:
        """Say "still here". **Does not extend the expiry.**

        Returns whether the heartbeat was accepted — it is refused for a lease
        this worker no longer holds, which is how a worker that was reclaimed
        finds out rather than continuing to believe it owns the node.
        """
        access = self._guard.authorize(StorageOperation.WRITE, context)
        with self._scope(unit) as work:
            result = work.execute(
                sa.update(node_lease_table)
                .where(
                    node_lease_table.c.execution_id == execution_id,
                    node_lease_table.c.node_id == node_id,
                    node_lease_table.c.lease_id == lease_id,
                    node_lease_table.c.released_at.is_(None),
                    *self._tenant_predicate(access),
                )
                .values(heartbeat_at=work.now)
            )
            return result.rowcount == 1

    def release(
        self,
        context: Any,
        *,
        execution_id: str,
        node_id: str,
        lease_id: str,
        unit: Optional[UnitOfWork] = None,
    ) -> bool:
        """Give the node back. Only the holder may, identified by lease id."""
        access = self._guard.authorize(StorageOperation.WRITE, context)
        with self._scope(unit) as work:
            result = work.execute(
                sa.update(node_lease_table)
                .where(
                    node_lease_table.c.execution_id == execution_id,
                    node_lease_table.c.node_id == node_id,
                    node_lease_table.c.lease_id == lease_id,
                    *self._tenant_predicate(access),
                )
                .values(released_at=work.now)
            )
            return result.rowcount == 1

    # ------------------------------------------------------------------

    def state_of(
        self,
        context: Any,
        *,
        execution_id: str,
        node_id: str,
        ambiguity_seconds: int = 30,
        unit: Optional[UnitOfWork] = None,
    ) -> Optional[dict]:
        """What recovery needs to know, from durable state alone.

        The point of this method: after a restart the process has no memory of
        any lease, and this answers "is anybody holding this node" from the row
        rather than from what some process remembers.
        """
        access = self._guard.authorize(StorageOperation.READ, context)
        with self._scope(unit) as work:
            row = self._row(work, access, execution_id, node_id)
            if row is None:
                return None
            now = work.now
            if row["released_at"] is not None:
                state = LeaseState.RELEASED
            elif _aware(row["expires_at"]) > now:
                state = LeaseState.ACTIVE
            else:
                beat = _aware(row["heartbeat_at"])
                recent = beat is not None and (now - beat).total_seconds() <= ambiguity_seconds
                # Expired, but heartbeating until moments ago. The worker may
                # still be running the node; reclaiming would run it twice.
                state = LeaseState.AMBIGUOUS if recent else LeaseState.EXPIRED
            return {
                "execution_id": row["execution_id"],
                "node_id": row["node_id"],
                "worker_id": row["worker_id"],
                "lease_id": row["lease_id"],
                "attempt_id": row["attempt_id"],
                "state": state,
                "reclaimable": state in (LeaseState.EXPIRED, LeaseState.RELEASED),
                "fence": int(row["fence"]),
                "granted_at": row["granted_at"],
                "expires_at": row["expires_at"],
                "heartbeat_at": row["heartbeat_at"],
            }

    def reclaimable(
        self, context: Any, *, limit: int = 100, unit: Optional[UnitOfWork] = None
    ) -> Sequence[dict]:
        """Leases whose holder is provably finished. What recovery sweeps."""
        access = self._guard.authorize(StorageOperation.READ, context)
        with self._scope(unit) as work:
            rows = work.execute(
                sa.select(node_lease_table)
                .where(
                    node_lease_table.c.released_at.is_(None),
                    node_lease_table.c.expires_at <= work.now,
                    *self._tenant_predicate(access),
                )
                .order_by(node_lease_table.c.expires_at)
                .limit(limit)
            ).mappings().all()
        return tuple(dict(row) for row in rows)

    # ------------------------------------------------------------------

    def _row(self, work: UnitOfWork, access: Any, execution_id: str, node_id: str):
        return work.execute(
            sa.select(node_lease_table).where(
                node_lease_table.c.execution_id == execution_id,
                node_lease_table.c.node_id == node_id,
                *self._tenant_predicate(access),
            )
        ).mappings().first()

    @staticmethod
    def _describe(execution_id, node_id, worker_id, lease_id, granted, expires, fence):
        return {
            "execution_id": execution_id,
            "node_id": node_id,
            "worker_id": worker_id,
            "lease_id": lease_id,
            "granted_at": granted,
            "expires_at": expires,
            "fence": fence,
            "state": LeaseState.ACTIVE,
        }

    def _tenant_predicate(self, access: Any) -> tuple:
        scope = self._guard.scope_filter(access)
        if scope is None:
            return ()
        column, value = scope
        return (node_lease_table.c[column] == value,)

    def _scope(self, unit: Optional[UnitOfWork]):
        return enlisted(self._store, unit)


class SqlIdempotencyStore:
    """Idempotency keys that survive a restart, a retry and a second process."""

    def __init__(self, store: DurableStore, *, metrics: Optional[Any] = None) -> None:
        if not isinstance(store, DurableStore):
            raise NoDurableStore("a durable idempotency store requires a store")
        self._store = store
        self._guard = RepositoryGuard(IDEMPOTENCY_BINDING)
        self._metrics = metrics

    def claim(
        self,
        context: Any,
        *,
        key: str,
        execution_id: str,
        node_id: Optional[str] = None,
        action_digest: Optional[str] = None,
        unit: Optional[UnitOfWork] = None,
    ) -> bool:
        """Reserve a key. ``True`` if this caller got it, ``False`` if it repeats.

        The distinction that matters: a *repeat of the same action* returns
        ``False`` and is not an error — it is the key doing its job. A **different**
        action reusing the key raises, because letting it through would make two
        operations one, which is worse than either of them failing.

        Uniqueness is the primary key, so it holds across processes and across a
        restart. An in-memory set held none of that.
        """
        if not isinstance(key, str) or not key.strip():
            raise ContractViolation("an idempotency key must be non-blank text")
        access = self._guard.authorize(StorageOperation.WRITE, context)
        with self._scope(unit) as work:
            try:
                # Savepointed: a duplicate key is the *expected* path here,
                # and on PostgreSQL a failed statement poisons the whole
                # transaction, so the read-back below could not run.
                with work.attempt():
                    work.execute(
                        sa.insert(idempotency_table).values(
                            tenant_id=access.tenant_id,
                            idempotency_key=key,
                            execution_id=execution_id,
                            node_id=node_id,
                            action_digest=action_digest,
                            created_at=work.now,
                            updated_at=work.now,
                        )
                    )
                    return True
            except ConstraintConflict:
                existing = work.execute(
                    sa.select(idempotency_table).where(
                        idempotency_table.c.tenant_id == access.tenant_id,
                        idempotency_table.c.idempotency_key == key,
                    )
                ).mappings().first()
        if existing is None:  # pragma: no cover - the row vanished mid-transaction
            raise IdempotencyConflict(key=key, existing_execution="unknown")
        self._count("idempotency.conflict")
        if existing["execution_id"] != execution_id or (
            action_digest is not None
            and existing["action_digest"] is not None
            and existing["action_digest"] != action_digest
        ):
            raise IdempotencyConflict(
                key=key, existing_execution=existing["execution_id"]
            )
        return False

    def find(
        self, context: Any, *, key: str, unit: Optional[UnitOfWork] = None
    ) -> Optional[dict]:
        access = self._guard.authorize(StorageOperation.READ, context)
        with self._scope(unit) as work:
            row = work.execute(
                sa.select(idempotency_table).where(
                    idempotency_table.c.idempotency_key == key,
                    *self._tenant_predicate(access),
                )
            ).mappings().first()
        return dict(row) if row else None

    def record_outcome(
        self,
        context: Any,
        *,
        key: str,
        outcome: str,
        unit: Optional[UnitOfWork] = None,
    ) -> None:
        """Attach what happened, so a repeat can be answered without re-running."""
        access = self._guard.authorize(StorageOperation.WRITE, context)
        with self._scope(unit) as work:
            work.execute(
                sa.update(idempotency_table)
                .where(
                    idempotency_table.c.idempotency_key == key,
                    *self._tenant_predicate(access),
                )
                .values(outcome=outcome, updated_at=work.now)
            )

    def _tenant_predicate(self, access: Any) -> tuple:
        scope = self._guard.scope_filter(access)
        if scope is None:
            return ()
        column, value = scope
        return (idempotency_table.c[column] == value,)

    def _scope(self, unit: Optional[UnitOfWork]):
        return enlisted(self._store, unit)

    def _count(self, name: str) -> None:
        if self._metrics is None:
            return
        try:
            self._metrics.increment(name, labels={})
        except Exception:  # noqa: BLE001
            pass


def _aware(value: Any) -> Optional[datetime]:
    """Restore UTC awareness to a timestamp a driver returned naive.

    SQLite has no timezone type, so a round-tripped timestamp comes back naive.
    Comparing a naive value against an aware clock reading raises, and the
    comparison it would have made is a lease-expiry decision — so the repair
    happens here rather than at the twenty call sites that read one.
    """
    from datetime import timezone

    if value is None:
        return None
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
