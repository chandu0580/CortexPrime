"""Database failure classification. **A database failure is never a success.**

Why this exists rather than letting SQLAlchemy exceptions travel
------------------------------------------------------------------
Everything above this layer already reasons in a failure taxonomy where
"definitely did not happen" and "nobody can say" are different answers, and the
retry rules read that difference. A raw ``OperationalError`` carries neither.
Worse, it carries the statement it was executing, which for a credential or a
payload row is content nobody wants in a log line.

So every driver exception is classified here, once, and the classification
preserves the one distinction that matters: **was the transaction settled?**

    settled          the outcome is known — it committed, or it did not
    unsettled        the outcome is unknown, and must not be guessed

The unknown-commit case
-------------------------
If a COMMIT is sent and the connection is lost before the acknowledgement
arrives, the transaction **may have committed**. There is no way to tell from
this side, and there never will be. Blindly retrying a non-idempotent mutation
after one of these is how a duplicate lease, a duplicate attempt or a duplicate
outbox entry appears.

``UnknownCommitOutcome`` is therefore its own class and is deliberately *not* a
subclass of anything that reads as failure. Callers reconcile by querying for the
transaction-owned identity — the execution id, the lease id, the entry id — which
is why every durable write in this phase carries one it chose in advance.

Nothing here retries
----------------------
Classification is not a decision. A serialization conflict is retryable *in
principle*; whether repeating this particular mutation is safe depends on the
effect semantics the domain declared, which this layer cannot see. Execution
decides (ADR-031), exactly as it decides for a provider failure.
"""

from __future__ import annotations

from typing import Optional

__all__ = [
    "DurabilityError",
    "TransactionUnavailable",
    "SerializationConflict",
    "DeadlockDetected",
    "ConstraintConflict",
    "ConnectionFailed",
    "TransactionTimeout",
    "UnknownCommitOutcome",
    "classify_database_error",
    "DURABILITY_METRICS",
]

#: Persistence counters, emitted through the existing metrics port. No new
#: telemetry framework, and no label carries a statement, a parameter or a row.
DURABILITY_METRICS = (
    "db.transaction.failure",
    "db.serialization.conflict",
    "db.deadlock",
    "db.timeout",
    "db.constraint.conflict",
    "db.unknown_commit",
    "outbox.claim",
    "outbox.publish",
    "outbox.dead_letter",
    "lease.reclaim",
    "idempotency.conflict",
)


class DurabilityError(RuntimeError):
    """A durable write or read did not complete. The outcome may be known.

    ``settled`` is the field callers actually branch on: ``True`` means the
    transaction provably did not commit, so nothing happened and the caller may
    act on that. ``False`` means nobody can say.
    """

    settled: bool = True

    retryable: bool = False
    """Whether **the database transaction** may be attempted again.

    Narrow on purpose, and the narrowness is the point. ``True`` means the
    database aborted this transaction for a reason that a fresh attempt can
    resolve — a serialization conflict, a deadlock victim — so replaying the
    *same statements* is correct and expected.

    It says nothing whatever about the work the transaction was recording. A
    provider call that already happened does not un-happen because PostgreSQL
    chose this transaction as the deadlock victim, and a caller that read this
    flag as permission to invoke the provider again would duplicate a real
    side effect on somebody else's system. Retrying the transaction means
    re-running the SQL, never re-running the operation.

    ``False`` is the default and the safe answer. ``UnknownCommitOutcome``
    leaves it ``False`` even though a retry is sometimes correct there, because
    that decision requires reconciling by durable identity first — it is not a
    flag anybody should act on without looking.
    """

    def __init__(self, message: str, *, cause: Optional[str] = None) -> None:
        super().__init__(message)
        self.cause = cause
        """The *type name* of the driver exception, never its text. A driver
        exception's ``str`` routinely contains the statement and its bound
        parameters, and a durable write's parameters are the row."""

    def to_dict(self) -> dict:
        return {
            "error": type(self).__name__,
            "settled": self.settled,
            "cause": self.cause,
            "reason": str(self),
        }


class TransactionUnavailable(DurabilityError):
    """No transaction could be started. Nothing was attempted."""


class ConnectionFailed(DurabilityError):
    """The connection failed before or between statements.

    Settled: a connection lost outside a COMMIT leaves an uncommitted
    transaction, which the server rolls back. The dangerous case — a connection
    lost *during* COMMIT — is ``UnknownCommitOutcome`` and is raised separately.
    """


class SerializationConflict(DurabilityError):
    """Two transactions could not both be serialised. This one was rolled back.

    SQLSTATE 40001. Provably rolled back, and provably safe to *re-execute the
    statements* -- which is what ``retryable`` means here and all it means.

    Settled, and safe to re-derive from a fresh read: the database has proved
    nothing of this transaction survived. Whether to re-derive is the caller's
    decision, not this layer's.
    """

    retryable = True


class DeadlockDetected(DurabilityError):
    """The database broke a cycle by aborting this transaction. Rolled back.

    SQLSTATE 40P01. Kept distinct from ``SerializationConflict`` even though
    both are retryable: a deadlock means two transactions took locks in opposite
    orders, which is a design signal an operator should see, and collapsing it
    into "serialization conflict" would hide a recurring lock-ordering bug
    inside a number that looks like ordinary contention.
    """

    retryable = True


class TransactionTimeout(DurabilityError):
    """A statement or lock wait exceeded its bound. Rolled back."""


class ConstraintConflict(DurabilityError):
    """A uniqueness or integrity constraint refused the write.

    **Usually not an error at all** — it is how the durable store expresses
    "somebody else got there first". A duplicate execution id, a second lease on
    one node, a repeated idempotency key and a re-recorded event all arrive here,
    and each has a domain-level meaning the repository translates into the
    refusal the domain already defines.
    """

    def __init__(
        self,
        message: str,
        *,
        constraint: Optional[str] = None,
        cause: Optional[str] = None,
    ) -> None:
        super().__init__(message, cause=cause)
        self.constraint = constraint


class UnknownCommitOutcome(DurabilityError):
    """COMMIT was sent and the answer never arrived. **It may have committed.**

    The one case that must never be treated as failure. A caller that retried a
    non-idempotent mutation here would duplicate it; a caller that reported
    failure would be asserting something it cannot know.

    Reconcile by reading back the transaction-owned identity. Every durable write
    in this phase chooses its identity *before* the transaction, precisely so
    that this is answerable.
    """

    settled = False


#: Fragments of driver exception *type names* mapped onto the taxonomy. Matched
#: on the type name rather than the message: a message is content the database
#: composed, sometimes from the row, and matching on it would make the
#: classification depend on data.
_BY_TYPE = (
    (("deadlock",), DeadlockDetected),
    (("serializ",), SerializationConflict),
    (("integrity", "uniqueviolation", "notnullviolation"), ConstraintConflict),
    (("timeout",), TransactionTimeout),
    (("disconnect", "interfaceerror", "connectionerror"), ConnectionFailed),
    (("operational",), ConnectionFailed),
)

#: SQLSTATE classes, which are stable across drivers and far better than a name.
#:     40001 serialization_failure     40P01 deadlock_detected
#:     23xxx integrity_constraint      57014 query_canceled
#:     08xxx connection_exception      55P03 lock_not_available
_BY_SQLSTATE = {
    "40001": SerializationConflict,
    "40P01": DeadlockDetected,
    "57014": TransactionTimeout,
    "55P03": TransactionTimeout,
}

#: SQLSTATEs that mean **the database itself does not know** whether the
#: transaction committed. These are not connection failures that happen to be
#: ambiguous -- they are the standard's way of saying the outcome is
#: indeterminate, and they say it whether or not the caller believed it was
#: committing.
#:
#:     40003 statement_completion_unknown
#:     08007 transaction_resolution_unknown
#:
#: So they are checked **before** ``during_commit`` is consulted and before the
#: ``08`` prefix rule, which would otherwise classify ``08007`` as a plain
#: ``ConnectionFailed`` for any caller that did not set the flag -- and a
#: ``ConnectionFailed`` is safe to retry, which is exactly what must not happen
#: to a transaction that may already have committed.
_UNKNOWN_OUTCOME_SQLSTATES = frozenset({"40003", "08007"})


def classify_database_error(
    exc: BaseException, *, during_commit: bool = False
) -> DurabilityError:
    """Turn a driver exception into a classified, secret-free durability error.

    ``during_commit`` is the caller's own knowledge and cannot be inferred: only
    the code that sent the COMMIT knows it did. A connection failure with it set
    becomes ``UnknownCommitOutcome`` — conservative on purpose, because the cost
    of being wrong in the other direction is a duplicated production change.
    """
    name = type(exc).__name__.lower()
    sqlstate = _sqlstate_of(exc)
    cause = type(exc).__name__

    if sqlstate and sqlstate in _UNKNOWN_OUTCOME_SQLSTATES:
        # Unconditional. The database said it does not know; the caller's belief
        # about whether it was committing cannot make that knowable.
        return UnknownCommitOutcome(
            f"the database reported an indeterminate transaction outcome "
            f"({sqlstate}); whether it committed is unknown and it must not be "
            "blindly repeated",
            cause=cause,
        )
    if sqlstate and sqlstate in _BY_SQLSTATE:
        return _BY_SQLSTATE[sqlstate](
            f"the database refused the transaction ({sqlstate})", cause=cause
        )
    if sqlstate and sqlstate.startswith("23"):
        return ConstraintConflict(
            "a database constraint refused the write",
            constraint=_constraint_of(exc),
            cause=cause,
        )
    if sqlstate and sqlstate.startswith("08"):
        if during_commit:
            return UnknownCommitOutcome(
                "the connection was lost while committing; the transaction may "
                "have committed and must not be blindly repeated",
                cause=cause,
            )
        return ConnectionFailed("the database connection failed", cause=cause)

    for fragments, kind in _BY_TYPE:
        if any(fragment in name for fragment in fragments):
            if kind is ConnectionFailed and during_commit:
                return UnknownCommitOutcome(
                    "the connection was lost while committing; the transaction "
                    "may have committed and must not be blindly repeated",
                    cause=cause,
                )
            if kind is ConstraintConflict:
                return ConstraintConflict(
                    "a database constraint refused the write",
                    constraint=_constraint_of(exc),
                    cause=cause,
                )
            return kind(f"the database operation failed ({cause})", cause=cause)

    if during_commit:
        # Unrecognised, and we were committing. The only honest answer.
        return UnknownCommitOutcome(
            f"the commit failed in a way this build does not recognise ({cause}); "
            "whether it committed is unknown",
            cause=cause,
        )
    return DurabilityError(f"the database operation failed ({cause})", cause=cause)


def _sqlstate_of(exc: BaseException) -> Optional[str]:
    """Dig a SQLSTATE out of whatever the driver wrapped. Never the message."""
    for candidate in (exc, getattr(exc, "orig", None), getattr(exc, "__cause__", None)):
        if candidate is None:
            continue
        for attribute in ("sqlstate", "pgcode"):
            value = getattr(candidate, attribute, None)
            if isinstance(value, str) and value:
                return value
        diag = getattr(candidate, "diag", None)
        value = getattr(diag, "sqlstate", None)
        if isinstance(value, str) and value:
            return value
    return None


def _constraint_of(exc: BaseException) -> Optional[str]:
    """The constraint *name*, when the driver publishes one.

    A name is schema metadata and safe to record. It is what turns "a constraint
    refused this" into "the unique event id refused this", which is the
    difference between an incident and an ordinary duplicate.
    """
    for candidate in (exc, getattr(exc, "orig", None)):
        diag = getattr(candidate, "diag", None)
        value = getattr(diag, "constraint_name", None)
        if isinstance(value, str) and value:
            return value
    # SQLite and some drivers publish nothing structured. The message would
    # carry the constraint but also the values, so it is not read.
    return None
