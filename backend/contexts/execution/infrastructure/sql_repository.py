"""Durable execution persistence. The compare-and-swap becomes real.

What changed, and what deliberately did not
---------------------------------------------
The in-memory repository's ``compare_and_swap`` held the compare and the swap
under one Python lock, which guaranteed nothing across processes — stated plainly
in ADR-039 rather than implied away. This is the same method against a database:

    UPDATE cp_execution SET record = :r, revision = :next
     WHERE execution_id = :id AND revision = :expected

and a rowcount of zero is the refusal. Two dispatchers reading revision 7 and
both writing back cannot both update, because the second one's ``WHERE`` no
longer matches. The loser gets ``ConcurrentExecutionUpdate`` — the same exception
the in-memory one raises — so nothing above this layer changes.

The aggregate is stored whole
-------------------------------
``to_record``/``from_record`` already flatten ``Execution`` into primitives,
re-run every invariant on the way back in, and **restore digests rather than
recomputing them**. That mapping is reused unchanged. Shredding the aggregate
into node/attempt/checkpoint tables would mean writing it a second time in SQL,
and the first divergence between the two is a run that loads with a digest that
always matches — a check that cannot fail, on the record of what happened to
production.

The columns beside the document are for querying, constraining and racing. They
are derived from the record on write and never read back into the aggregate, so
there is no second source of truth for anything the domain owns.

Tenancy
---------
Every method takes an ``ExecutionContext`` first and derives tenancy from it
through ``RepositoryGuard`` — the same guard, the same binding, the same
``TENANT-REPOSITORY-CONTEXT`` obligation. Reads are narrowed by the guard's scope
filter *in SQL*, so another tenant's row is not fetched and then rejected; it is
never selected. A cross-tenant read is indistinguishable from a miss.

Transactions
--------------
Every method accepts an optional ``UnitOfWork``. Given one it enlists; given
none it opens and commits its own. The pairs that must be atomic — a state
mutation and the outbox event announcing it — are always given one by the
application service, which is the only layer that knows they belong together.
"""

from __future__ import annotations

from typing import Any, Optional, Sequence

import sqlalchemy as sa

from backend.contracts.storage import StorageOperation
from backend.contexts.execution.domain.errors import (
    DuplicateExecution,
    ExecutionNotFound,
)
from backend.contexts.execution.domain.execution import Execution
from backend.contexts.execution.domain.identifiers import ExecutionId
from backend.contexts.execution.infrastructure.persistence import from_record, to_record
from backend.contexts.execution.infrastructure.repository import (
    EXECUTION_BINDING,
    ConcurrentExecutionUpdate,
)
from backend.database.durable.errors import ConstraintConflict
from backend.database.durable.session import (
    DurableStore,
    NoDurableStore,
    UnitOfWork,
    enlisted,
)
from backend.database.durable.tables import execution_table
from backend.platform.storage import RepositoryGuard

__all__ = ["SqlExecutionRepository"]


class SqlExecutionRepository:
    """The durable ``ExecutionRepository``. Same port, same exceptions."""

    def __init__(self, store: DurableStore) -> None:
        if not isinstance(store, DurableStore):
            raise NoDurableStore(
                "a durable execution repository requires a store; there is no "
                "in-memory fallback, because a process that quietly used one "
                "would lose every run on restart and look healthy doing it"
            )
        self._store = store
        self._guard = RepositoryGuard(EXECUTION_BINDING)

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def save(
        self, context: Any, execution: Execution, *, unit: Optional[UnitOfWork] = None
    ) -> None:
        """Store a new run. Refuses to overwrite one that exists.

        The refusal comes from the **primary key**, not from a read-then-write:
        two processes starting the same execution id both INSERT, and exactly one
        succeeds. A check-then-insert would let both pass the check.
        """
        access = self._guard.authorize(StorageOperation.WRITE, context)
        with self._scope(unit) as work:
            record = to_record(execution, tenant_id=access.tenant_id)
            try:
                work.execute(
                    sa.insert(execution_table).values(
                        **self._columns(record, revision=1, now=work.now)
                    )
                )
            except ConstraintConflict:
                # The database expressing "somebody got here first" in the only
                # vocabulary it has. Translated into the domain's own refusal.
                raise DuplicateExecution(str(execution.execution_id)) from None

    def replace(
        self, context: Any, execution: Execution, *, unit: Optional[UnitOfWork] = None
    ) -> None:
        """Overwrite in place, without a revision check.

        Named for what it does, exactly as the in-memory one is. It is the
        unguarded write and is correct only where the caller genuinely owns the
        row; anything reconciling a concurrent decision uses
        ``compare_and_swap`` instead.
        """
        access = self._guard.authorize(StorageOperation.WRITE, context)
        with self._scope(unit) as work:
            record = to_record(execution, tenant_id=access.tenant_id)
            result = work.execute(
                sa.update(execution_table)
                .where(
                    execution_table.c.execution_id == str(execution.execution_id),
                    *self._tenant_predicate(access),
                )
                .values(
                    record=record,
                    revision=execution_table.c.revision + 1,
                    state=record["state"],
                    digest=record.get("digest"),
                    updated_at=work.now,
                )
            )
            if result.rowcount == 0:
                # Absent, or another tenant's. Indistinguishable on purpose:
                # confirming that another tenant's run exists is a disclosure.
                raise ExecutionNotFound(str(execution.execution_id))

    # ------------------------------------------------------------------
    # Concurrency
    # ------------------------------------------------------------------

    def revision_of(
        self,
        context: Any,
        execution_id: ExecutionId,
        *,
        unit: Optional[UnitOfWork] = None,
    ) -> Optional[int]:
        """What revision a reader saw. Passed back to ``compare_and_swap``."""
        access = self._guard.authorize(StorageOperation.READ, context)
        with self._scope(unit) as work:
            row = work.execute(
                sa.select(execution_table.c.revision).where(
                    execution_table.c.execution_id == str(execution_id),
                    *self._tenant_predicate(access),
                )
            ).first()
        return int(row[0]) if row else None

    def compare_and_swap(
        self,
        context: Any,
        execution: Execution,
        *,
        expected_revision: int,
        unit: Optional[UnitOfWork] = None,
    ) -> int:
        """Write only if nothing else has written since ``expected_revision``.

        **This is the method Phase 5 exists for.** The compare and the swap are
        one statement, so there is no window between them — not a small window,
        none. Two application instances that both read revision 7 and both decide
        cannot both write: the database matches ``revision = 7`` once.

        A rowcount of zero means either the revision moved or the row is not
        visible to this tenant. Those are distinguished by a follow-up read
        *within the same transaction*, so the answer cannot itself be racy — and
        an invisible row reports as absent rather than as a conflict, because
        reporting a conflict would confirm it exists.
        """
        access = self._guard.authorize(StorageOperation.WRITE, context)
        with self._scope(unit) as work:
            record = to_record(execution, tenant_id=access.tenant_id)
            key = str(execution.execution_id)
            result = work.execute(
                sa.update(execution_table)
                .where(
                    execution_table.c.execution_id == key,
                    execution_table.c.revision == expected_revision,
                    *self._tenant_predicate(access),
                )
                .values(
                    record=record,
                    revision=expected_revision + 1,
                    state=record["state"],
                    digest=record.get("digest"),
                    updated_at=work.now,
                )
            )
            if result.rowcount == 1:
                return expected_revision + 1

            current = work.execute(
                sa.select(execution_table.c.revision).where(
                    execution_table.c.execution_id == key,
                    *self._tenant_predicate(access),
                )
            ).first()
            if current is None:
                raise ExecutionNotFound(key)
            raise ConcurrentExecutionUpdate(
                execution_id=key,
                expected=expected_revision,
                actual=int(current[0]),
            )

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def find(
        self,
        context: Any,
        execution_id: ExecutionId,
        *,
        unit: Optional[UnitOfWork] = None,
    ) -> Optional[Execution]:
        """One run, or nothing. Another tenant's run is nothing."""
        access = self._guard.authorize(StorageOperation.READ, context)
        with self._scope(unit) as work:
            row = work.execute(
                sa.select(execution_table.c.record).where(
                    execution_table.c.execution_id == str(execution_id),
                    *self._tenant_predicate(access),
                )
            ).first()
        return from_record(row[0]) if row else None

    def find_with_revision(
        self,
        context: Any,
        execution_id: ExecutionId,
        *,
        unit: Optional[UnitOfWork] = None,
    ) -> tuple:
        """The run **and the revision it was read at**, in one statement.

        Reading them separately is a race, and not a theoretical one: it was
        measured. ``find`` then ``revision_of`` lets another process commit
        between the two, so the caller holds an aggregate that still says the
        node is free alongside a revision that already includes the lease. The
        compare-and-swap then *matches* and the winner's lease is overwritten —
        the very defect the revision check was added to close, reintroduced one
        statement away from it. Four processes racing twelve nodes produced
        twelve double-leases (Phase 11.3).

        One ``SELECT`` of both columns cannot be interleaved, so the revision a
        caller passes to ``compare_and_swap`` is always the revision of the copy
        it actually decided from.

        Returns ``(None, None)`` for a run this tenant cannot see.
        """
        access = self._guard.authorize(StorageOperation.READ, context)
        with self._scope(unit) as work:
            row = work.execute(
                sa.select(execution_table.c.record, execution_table.c.revision).where(
                    execution_table.c.execution_id == str(execution_id),
                    *self._tenant_predicate(access),
                )
            ).first()
        if row is None:
            return (None, None)
        return (from_record(row[0]), int(row[1]))

    def all(self, context: Any, *, unit: Optional[UnitOfWork] = None) -> Sequence[Execution]:
        """Every run visible to this context.

        Narrowed in SQL by the guard's scope filter. There is no unfiltered
        variant and deliberately no ``get_all()``: an unscoped listing of every
        tenant's executions is not a convenience, it is the disclosure.
        """
        access = self._guard.authorize(StorageOperation.READ, context)
        with self._scope(unit) as work:
            rows = work.execute(
                sa.select(execution_table.c.record)
                .where(*self._tenant_predicate(access))
                .order_by(execution_table.c.execution_id)
            ).all()
        return tuple(from_record(row[0]) for row in rows)

    def find_by_state(
        self,
        context: Any,
        states: Sequence[str],
        *,
        limit: int = 100,
        unit: Optional[UnitOfWork] = None,
    ) -> Sequence[Execution]:
        """Runs in given lifecycle states, for recovery to reconcile after a restart.

        The query recovery needs and the in-memory store could not answer without
        loading everything: after a crash, which runs were mid-flight? Bounded,
        tenant-narrowed, and read-only.
        """
        access = self._guard.authorize(StorageOperation.READ, context)
        with self._scope(unit) as work:
            rows = work.execute(
                sa.select(execution_table.c.record)
                .where(
                    execution_table.c.state.in_(list(states)),
                    *self._tenant_predicate(access),
                )
                .order_by(execution_table.c.updated_at)
                .limit(limit)
            ).all()
        return tuple(from_record(row[0]) for row in rows)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _tenant_predicate(self, access: Any) -> tuple:
        """The tenant narrowing, as SQL. Empty only for platform-internal access.

        ``scope_filter`` returning ``None`` means "authorised to see everything",
        which is the one case where no predicate applies. Treating it as "no
        filter was needed" is the mistake the guard's docstring names, so it is
        spelled out here rather than defaulted.
        """
        scope = self._guard.scope_filter(access)
        if scope is None:
            return ()
        column, value = scope
        return (execution_table.c[column] == value,)

    @staticmethod
    def _columns(record: dict, *, revision: int, now: Any) -> dict:
        """Promote the queryable, constrainable fields out of the document.

        Derived from the record on the way in and never read back into the
        aggregate — the document is authoritative for the domain, these columns
        are authoritative for lookup and concurrency, and neither is a second
        model of the other.
        """
        return {
            "execution_id": record["execution_id"],
            "tenant_id": record["tenant_id"],
            "revision": revision,
            "workflow_id": record["workflow_id"],
            "workflow_digest": record.get("workflow_digest"),
            "mission_id": record.get("mission_id"),
            "state": record["state"],
            "digest": record.get("digest"),
            "record": record,
            "created_at": now,
            "updated_at": now,
        }

    def _scope(self, unit: Optional[UnitOfWork]):
        """Enlist in the caller's transaction, or open one for this statement."""
        return enlisted(self._store, unit)
