"""Transaction scope. Explicit boundaries, no global session, no autocommit.

The rule this module exists to make structural
------------------------------------------------
**A repository never decides when to commit.** The application service owns the
boundary, because it is the only layer that knows which writes belong together —
and "state mutation and its outbox event commit together" is the single most
important pair in this phase (ADR-044 §11).

So a repository is handed a ``UnitOfWork`` or nothing. Handed one, it enlists in
a transaction somebody else opened and somebody else will commit. Handed
nothing, it opens a one-statement transaction of its own and commits it — which
is correct for a standalone read or an independent write, and is *not* available
for the pairs that must be atomic, because those are always given a unit.

No global session
-------------------
There is no module-level session, no session singleton, no session on a domain
object and no implicit ambient transaction. ``DurableStore`` holds an *engine* —
a connection pool, which is a resource and not a transaction — and hands out
short-lived connections inside a ``with`` block that always closes and always
rolls back on failure.

An engine is global-shaped and a session is not, and the difference is that a
pool has no state anybody can accidentally read as "the current transaction".

Failure is classified, never leaked
-------------------------------------
Every exception crossing this boundary becomes a ``DurabilityError``. The
important one is ``UnknownCommitOutcome``: if the connection dies while
committing, the transaction **may have committed**, and this layer knows it was
committing because it is the code that sent the COMMIT. Nothing above could infer
that, which is exactly why the classification happens here.

Clocks
--------
The store carries the **application clock**, injected once, and hands the same
reading to every repository in a unit of work. Nothing calls
``datetime.now()`` inside a repository and nothing uses the database's ``now()``
for an authority calculation. Two clock readings inside one authority decision is
the defect Phase 4.4 closed at the invocation gateway, and a durable store with
its own idea of the time would reintroduce it one layer down.
"""

from __future__ import annotations

import logging
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Callable, Iterator, Optional

from backend.database.durable.errors import (
    DurabilityError,
    TransactionUnavailable,
    UnknownCommitOutcome,
    classify_database_error,
)

__all__ = ["UnitOfWork", "DurableStore", "NoDurableStore", "enlisted"]

log = logging.getLogger(__name__)


class NoDurableStore(DurabilityError):
    """A durable repository was constructed with no store behind it.

    Raised at construction, not at first use. A repository that accepted
    ``None`` and refused later would look wired and fail during a production
    change, which is the worst moment to discover a deployment problem.
    """


class UnitOfWork:
    """One open transaction, and the clock reading it was opened with.

    Passed *down* into repositories; never created by one. Holding the clock
    alongside the connection is what makes "everything written in this unit
    agrees about when it happened" true rather than usually true.
    """

    __slots__ = ("connection", "now", "_closed", "_metrics")

    def __init__(self, connection: Any, now: datetime, metrics: Optional[Any] = None) -> None:
        if now.tzinfo is None:
            raise DurabilityError("a unit of work must be opened with a UTC clock reading")
        self.connection = connection
        self.now = now
        self._closed = False
        self._metrics = metrics

    @property
    def dialect(self) -> str:
        return self.connection.dialect.name

    def execute(self, statement: Any, parameters: Any = None) -> Any:
        """Run one statement inside this transaction. Classifies on failure."""
        if self._closed:
            raise TransactionUnavailable(
                "this unit of work has already been closed; a statement after "
                "commit would run in a transaction nobody opened"
            )
        try:
            if parameters is None:
                return self.connection.execute(statement)
            return self.connection.execute(statement, parameters)
        except Exception as exc:  # noqa: BLE001 - classified, never leaked
            raise classify_database_error(exc) from None

    @contextmanager
    def attempt(self):
        """A savepoint. **Required around any statement whose failure is caught.**

        PostgreSQL aborts the entire transaction when a statement fails: every
        subsequent statement returns ``25P02 in_failed_sql_transaction`` until
        the block ends. So the pattern this codebase uses in several places --

            try:
                work.execute(insert)          # may violate a unique constraint
            except ConstraintConflict:
                work.execute(update_or_select)  # decide what to do instead

        -- cannot work on PostgreSQL as written. The recovery statement runs in
        a transaction the database has already given up on, fails with 25P02,
        and surfaces as an unclassified ``DurabilityError``.

        SQLite does not behave this way, which is exactly why this survived
        every phase up to 5.3: the durability tests ran on file-backed SQLite,
        where the pattern works, and the first real PostgreSQL run turned three
        of these sites into failures at once.

        Wrapping the failing statement in a savepoint contains the damage. The
        savepoint rolls back, the enclosing transaction stays usable, and the
        recovery statement runs normally:

            with work.attempt():
                work.execute(insert)

        On SQLite the savepoint is real too, so behaviour is identical on both.
        """
        if self._closed:
            raise TransactionUnavailable(
                "this unit of work has already been closed; a savepoint after "
                "commit would nest inside a transaction nobody opened"
            )
        savepoint = self.connection.begin_nested()
        try:
            yield self
        except Exception:
            # Roll back to the savepoint only. The outer transaction survives,
            # which is the entire point, and the exception continues to the
            # caller's ``except`` unchanged.
            if savepoint.is_active:
                savepoint.rollback()
            raise
        else:
            if savepoint.is_active:
                savepoint.commit()

    def _close(self) -> None:
        self._closed = True


class DurableStore:
    """The durable system of record. Holds an engine; never holds a transaction.

    Constructed once at the composition root from an explicit engine. There is
    deliberately no ``DurableStore.default()`` and no module-level instance: a
    security-relevant store that can be reached without being passed is a store
    that gets reached from somewhere nobody wired.
    """

    def __init__(
        self,
        engine: Any,
        *,
        clock: Optional[Callable[[], datetime]] = None,
        metrics: Optional[Any] = None,
    ) -> None:
        if engine is None:
            raise NoDurableStore(
                "a durable store requires an engine. There is no in-memory "
                "fallback: a production process that silently used a dictionary "
                "when the database was unavailable would lose every guarantee "
                "this phase exists to provide, and would look healthy doing it"
            )
        self._engine = engine
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._metrics = metrics
        self._lock = threading.Lock()

    @property
    def engine(self) -> Any:
        return self._engine

    @property
    def dialect(self) -> str:
        return self._engine.dialect.name

    def now(self) -> datetime:
        """The application clock. The only clock this layer reads."""
        return self._clock()

    # ------------------------------------------------------------------
    # Transaction scope
    # ------------------------------------------------------------------

    @contextmanager
    def atomic(self, *, now: Optional[datetime] = None) -> Iterator[UnitOfWork]:
        """Open one transaction. Commit on clean exit, roll back on anything else.

        This is the boundary. Everything written inside one ``with`` block
        commits together or not at all — which is how a state mutation and the
        outbox event announcing it become one fact rather than two writes that
        usually both happen.

        ``now`` may be supplied by a caller that already read the clock, so an
        application command that made a decision at one instant persists it with
        the same instant rather than a slightly later one.
        """
        moment = now or self._clock()
        try:
            connection = self._engine.connect()
        except Exception as exc:  # noqa: BLE001 - nothing was attempted
            self._count("db.transaction.failure")
            raise TransactionUnavailable(
                f"a database transaction could not be started ({type(exc).__name__})",
                cause=type(exc).__name__,
            ) from None

        unit = UnitOfWork(connection, moment, metrics=self._metrics)
        committing = False
        try:
            transaction = connection.begin()
            yield unit
            committing = True
            transaction.commit()
        except DurabilityError:
            # Already classified, by ``UnitOfWork.execute`` or by a repository.
            _rollback(connection)
            self._count("db.transaction.failure")
            raise
        except Exception as exc:  # noqa: BLE001
            _rollback(connection)
            if not committing:
                # **The body raised, not the commit.** Almost always a domain
                # refusal -- a lease already held, a conflicting registration, a
                # binding that may not be overwritten -- and it travels
                # unchanged.
                #
                # Wrapping it would be a semantic regression smuggled in as a
                # durability change: a caller that catches ``LeaseHeld`` would
                # start seeing ``DurabilityError`` and would either stop
                # handling the refusal or start treating a refusal as an
                # infrastructure fault. Driver errors never reach here, because
                # ``UnitOfWork.execute`` classified them on the way past.
                raise
            classified = classify_database_error(exc, during_commit=True)
            if isinstance(classified, UnknownCommitOutcome):
                # The one case that must not read as failure anywhere above.
                self._count("db.unknown_commit")
                log.error(
                    "commit outcome unknown; reconcile by transaction-owned "
                    "identity rather than repeating the mutation"
                )
            else:
                self._count("db.transaction.failure")
            raise classified from None
        finally:
            unit._close()
            connection.close()

    @contextmanager
    def reading(self, *, now: Optional[datetime] = None) -> Iterator[UnitOfWork]:
        """A read-only scope. Still a transaction, so a multi-row read is coherent.

        Separate from ``atomic`` only so the intent is visible at the call site;
        it commits nothing because nothing was written, and a read that
        accidentally wrote would be caught by the rollback rather than committed
        by a helper that assumed it was harmless.
        """
        with self.atomic(now=now) as unit:
            yield unit

    # ------------------------------------------------------------------

    def _count(self, name: str) -> None:
        if self._metrics is None:
            return
        try:
            self._metrics.increment(name, labels={"dialect": self.dialect})
        except Exception:  # noqa: BLE001 - measurement never changes an outcome
            log.debug("durability metric failed", exc_info=False)

    def __repr__(self) -> str:
        # Never the DSN: it carries the password.
        return f"<DurableStore dialect={self.dialect}>"


def _rollback(connection: Any) -> None:
    """Roll back, and never let the rollback's own failure replace the cause."""
    try:
        if connection.in_transaction():
            connection.rollback()
    except Exception:  # noqa: BLE001
        log.warning("rollback failed after a durable operation error", exc_info=False)


class _Enlisted:
    """A no-op scope around a transaction somebody else owns.

    Exists so a repository method reads the same whether it was handed a unit or
    opened its own — and, more importantly, so that being handed one means the
    method **cannot** commit. Committing somebody else's transaction is how a
    state write lands without the event that was supposed to accompany it.

    Lives here rather than in a context because it is part of the transaction
    contract, not part of anybody's domain. Every repository in every context
    needs it, and one of them owning it would make the others import across a
    bounded-context boundary for a piece of plumbing.
    """

    __slots__ = ("_unit",)

    def __init__(self, unit: UnitOfWork) -> None:
        self._unit = unit

    def __enter__(self) -> UnitOfWork:
        return self._unit

    def __exit__(self, *exc: Any) -> bool:
        return False


def enlisted(store: "DurableStore", unit: Optional[UnitOfWork]):
    """Enlist in the caller's transaction, or open one for a single statement.

    The one expression every repository uses to decide its transaction scope.
    Written once so the decision -- and the rule that an enlisted method never
    commits -- cannot drift between repositories.
    """
    if unit is not None:
        return _Enlisted(unit)
    return store.atomic()
