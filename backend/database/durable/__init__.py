"""The durable state foundation (Phase 5.1).

What this package is
----------------------
The transaction boundary, the schema, and the failure vocabulary. It holds no
domain type, decides nothing about capabilities, workers or executions, and has
no idea what an authorization is — it moves rows and classifies what the database
said about moving them.

The repositories that use it live in each bounded context's ``infrastructure/``,
because a repository implements that context's port and belongs with the context
whose invariants it preserves. Putting them here would create one package that
knows both Execution and Connectivity, which is the thing the composition root
exists to be the only example of.

    errors    the failure taxonomy, and the unknown-commit case
    tables    the schema: a document per aggregate, columns for what is raced on
    session   ``UnitOfWork`` and ``DurableStore`` — explicit transaction scope
    config    fail-closed configuration and the five-part bootstrap check

The three rules
-----------------
**No global session.** ``DurableStore`` holds an engine, which is a pool. A
session is a transaction, and a transaction reachable without being passed is one
that gets joined by code nobody wired.

**No in-memory fallback in production.** ``build_durable_store`` returns a real
store or raises. A process that quietly used a dictionary when the database was
unreachable would lose every guarantee this phase provides and would look healthy
doing it.

**A database failure is never a success.** Every driver exception is classified,
and the one that matters is ``UnknownCommitOutcome``: a connection lost while
committing may have committed, so it is neither failure nor success and must be
reconciled by transaction-owned identity rather than repeated.
"""

from backend.database.durable.config import (
    BootstrapReport,
    DurabilityConfig,
    DurabilityMisconfigured,
    DurabilityUnavailable,
    build_development_store,
    build_durable_store,
    verify_durability,
)
from backend.database.durable.errors import (
    DURABILITY_METRICS,
    ConnectionFailed,
    ConstraintConflict,
    DeadlockDetected,
    DurabilityError,
    SerializationConflict,
    TransactionTimeout,
    TransactionUnavailable,
    UnknownCommitOutcome,
    classify_database_error,
)
from backend.database.durable.audit import SqlAuditStore
from backend.database.durable.session import (
    DurableStore,
    NoDurableStore,
    UnitOfWork,
)
from backend.database.durable.tables import (
    DURABLE_METADATA,
    DURABLE_TABLES,
    PLATFORM_SCOPE,
    SCHEMA_VERSION,
)

__all__ = [
    "DurableStore",
    "SqlAuditStore",
    "UnitOfWork",
    "NoDurableStore",
    "DurabilityConfig",
    "DurabilityMisconfigured",
    "DurabilityUnavailable",
    "BootstrapReport",
    "build_durable_store",
    "build_development_store",
    "verify_durability",
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
    "DURABLE_METADATA",
    "DURABLE_TABLES",
    "PLATFORM_SCOPE",
    "SCHEMA_VERSION",
]
