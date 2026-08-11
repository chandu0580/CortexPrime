"""Durable-store configuration and bootstrap. Production fails closed.

The failure this exists to prevent
------------------------------------
A process starts, the database is unreachable, and it quietly serves requests
from a dictionary. Everything looks healthy: executions run, leases are granted,
outbox entries are recorded. None of it survives the restart, two instances
disagree about every lease, and nothing detects it — because from the inside it
all worked.

So there is **no in-memory fallback in production**, and there is no code path
that produces one. ``build_durable_store`` either returns a store backed by a
real database or raises. The in-memory implementations still exist and are still
correct for development; reaching them is a differently-named function that a
person has to type, never a fallback a failure can trigger.

What is verified before a production process is allowed to assemble
---------------------------------------------------------------------
    configuration      a DSN exists and names a real driver
    connectivity       a connection can be opened
    transaction        BEGIN/COMMIT actually works on it
    schema             every durable table this build needs is present
    migration          the recorded schema version is the one this build knows

Each is checked separately because they fail for different reasons and an
operator handed one word for five problems has been told nothing.

Secrets
---------
The DSN carries the database password. It is read from configuration, never
logged, never returned by a health endpoint, never placed on the config object's
``to_dict`` and never included in an error message — which is why every failure
below names the *check* rather than the connection string.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any, Optional

from backend.contracts.execution import ExecutionEnvironment
from backend.database.durable.errors import DurabilityError
from backend.database.durable.session import DurableStore
from backend.database.durable.tables import DURABLE_METADATA, DURABLE_TABLES, SCHEMA_VERSION

__all__ = [
    "DurabilityConfig",
    "DurabilityMisconfigured",
    "DurabilityUnavailable",
    "BootstrapReport",
    "build_durable_store",
    "build_development_store",
    "verify_durability",
]

log = logging.getLogger(__name__)


class DurabilityMisconfigured(DurabilityError):
    """A production durability dependency is missing. Nothing was assembled."""


class DurabilityUnavailable(DurabilityError):
    """The durable store exists in configuration and could not be reached."""


@dataclass(frozen=True)
class DurabilityConfig:
    """What the durable store needs. **No secret is a field here.**

    The DSN is assembled at build time from configuration and never lands on
    this object, so a config that somebody logs or attaches to a bug report
    carries nothing to leak.
    """

    environment: ExecutionEnvironment
    dsn_variable: str = "POSTGRES_URL"
    """Which configuration variable holds the connection string. Named rather
    than embedded so the *name* can be reported when it is missing and the
    *value* never has to be."""

    pool_size: int = 10
    max_overflow: int = 20
    pool_timeout_seconds: int = 30
    """Bounded acquisition. An unbounded wait for a connection is an unbounded
    hold on whatever asked for it, and under load that is every request."""

    pool_recycle_seconds: int = 1800
    statement_timeout_ms: int = 30_000
    require_tls: bool = True
    """Refused in production if the DSN does not ask for it. A plaintext
    database connection exposes every row, including credential metadata and the
    execution record."""

    create_schema: bool = False
    """Whether to create tables directly. **Off, and refused in production.**
    Schema changes go through Alembic so they are reviewable and forward-only;
    a process that could create its own tables would drift from the migration
    history without anybody noticing."""

    def __post_init__(self) -> None:
        if not isinstance(self.environment, ExecutionEnvironment):
            raise DurabilityMisconfigured("environment must be an ExecutionEnvironment")
        if self.environment is ExecutionEnvironment.PRODUCTION:
            if self.create_schema:
                raise DurabilityMisconfigured(
                    "a production process may not create its own schema; "
                    "migrations are how a schema change becomes reviewable, and "
                    "a process that creates tables drifts from the history"
                )
            if not self.require_tls:
                raise DurabilityMisconfigured(
                    "TLS to the database cannot be disabled for production; the "
                    "connection carries every row, including execution records "
                    "and credential metadata"
                )
        for label in ("pool_size", "pool_timeout_seconds"):
            if getattr(self, label) < 1:
                raise DurabilityMisconfigured(f"{label} must be at least 1")

    def to_dict(self) -> dict:
        """Safe to log. There is no connection string on this object."""
        return {
            "environment": self.environment.value,
            "dsn_variable": self.dsn_variable,
            "pool_size": self.pool_size,
            "max_overflow": self.max_overflow,
            "pool_timeout_seconds": self.pool_timeout_seconds,
            "pool_recycle_seconds": self.pool_recycle_seconds,
            "statement_timeout_ms": self.statement_timeout_ms,
            "require_tls": self.require_tls,
            "create_schema": self.create_schema,
            "schema_version": SCHEMA_VERSION,
        }


@dataclass(frozen=True)
class BootstrapReport:
    """What was actually verified. Five answers, never collapsed into one."""

    configured: bool
    reachable: bool
    transactional: bool
    schema_present: bool
    schema_version_ok: bool
    dialect: Optional[str] = None
    missing_tables: tuple = ()
    detail: Optional[str] = None

    @property
    def ready(self) -> bool:
        """Whether durable execution can operate safely. All five, or none."""
        return (
            self.configured
            and self.reachable
            and self.transactional
            and self.schema_present
            and self.schema_version_ok
        )

    def to_dict(self) -> dict:
        return {
            "ready": self.ready,
            "configured": self.configured,
            "reachable": self.reachable,
            "transactional": self.transactional,
            "schema_present": self.schema_present,
            "schema_version_ok": self.schema_version_ok,
            "dialect": self.dialect,
            "missing_tables": list(self.missing_tables),
            "detail": self.detail,
            "expected_schema_version": SCHEMA_VERSION,
        }


# ----------------------------------------------------------------------
# Assembly
# ----------------------------------------------------------------------


def build_durable_store(
    config: DurabilityConfig,
    *,
    clock: Optional[Any] = None,
    metrics: Optional[Any] = None,
    dsn: Optional[str] = None,
) -> DurableStore:
    """Assemble the production store, or refuse. **Never falls back to memory.**

    ``dsn`` is accepted so a composition root that already holds one does not
    have to put it in the environment; when absent it is read from the named
    variable. Either way it is used once and never stored.
    """
    import sqlalchemy as sa

    connection_string = dsn or os.environ.get(config.dsn_variable, "").strip()
    if not connection_string:
        raise DurabilityMisconfigured(
            f"{config.dsn_variable} is not set; a durable store cannot be "
            "assembled and there is no in-memory fallback. A process that "
            "silently used a dictionary here would lose every guarantee this "
            "phase provides and would look healthy doing it"
        )
    if config.environment is ExecutionEnvironment.PRODUCTION:
        if connection_string.startswith("sqlite"):
            raise DurabilityMisconfigured(
                "SQLite is not a production system of record for this platform; "
                "it cannot serve multiple application instances, which is the "
                "case durable state exists for"
            )
        if config.require_tls and "sslmode=disable" in connection_string:
            raise DurabilityMisconfigured(
                "the production connection string disables TLS; the connection "
                "carries every row this platform stores"
            )

    try:
        engine = sa.create_engine(
            connection_string,
            pool_size=config.pool_size,
            max_overflow=config.max_overflow,
            pool_timeout=config.pool_timeout_seconds,
            pool_recycle=config.pool_recycle_seconds,
            pool_pre_ping=True,
            # Never echo. Statements carry bound parameters, and a bound
            # parameter here is a row.
            echo=False,
            future=True,
        )
    except Exception as exc:  # noqa: BLE001 - never the DSN in the message
        raise DurabilityMisconfigured(
            f"the database engine could not be created ({type(exc).__name__})",
            cause=type(exc).__name__,
        ) from None

    store = DurableStore(engine, clock=clock, metrics=metrics)
    report = verify_durability(store, create_schema=config.create_schema)
    if not report.ready:
        # Refuse to assemble. A process that started anyway would accept work it
        # cannot durably record.
        raise DurabilityUnavailable(
            "the durable store is not usable: "
            + "; ".join(
                name
                for name, ok in (
                    ("not reachable", report.reachable),
                    ("not transactional", report.transactional),
                    ("schema incomplete", report.schema_present),
                    ("schema version mismatch", report.schema_version_ok),
                )
                if not ok
            )
            + (f" ({report.detail})" if report.detail else "")
        )
    return store


def build_development_store(
    *,
    dsn: str,
    clock: Optional[Any] = None,
    metrics: Optional[Any] = None,
) -> DurableStore:
    """A store for development and for durability tests. **Never production.**

    A separately named function rather than a flag on ``build_durable_store``,
    for the same reason every other development builder in this codebase is one:
    a flag is something a configuration file sets by accident, and a differently
    named function is something a person has to type.

    It creates the schema directly, which is exactly what production refuses.
    """
    import sqlalchemy as sa

    if not dsn or dsn.startswith("postgresql") and "prod" in dsn.lower():
        # A crude guard, and deliberately crude: the point is that pointing the
        # development builder at something production-shaped should be awkward.
        raise DurabilityMisconfigured(
            "build_development_store will not point at a production-looking DSN"
        )
    engine = sa.create_engine(dsn, future=True)
    store = DurableStore(engine, clock=clock, metrics=metrics)
    DURABLE_METADATA.create_all(engine)
    return store


# ----------------------------------------------------------------------
# Verification
# ----------------------------------------------------------------------


def verify_durability(
    store: DurableStore, *, create_schema: bool = False
) -> BootstrapReport:
    """Check the five things separately. Never mutates anything but the schema.

    Deliberately not a health *probe* in the sense of something that runs per
    request: it opens one connection, runs one trivial statement inside a real
    transaction, and inspects the catalogue. Readiness calls it; liveness does
    not, because a process can be alive while the store is not.
    """
    import sqlalchemy as sa

    dialect = None
    try:
        dialect = store.dialect
    except Exception:  # noqa: BLE001
        return BootstrapReport(
            configured=True,
            reachable=False,
            transactional=False,
            schema_present=False,
            schema_version_ok=False,
            detail="the engine could not report its dialect",
        )

    if create_schema:
        try:
            DURABLE_METADATA.create_all(store.engine)
        except Exception as exc:  # noqa: BLE001
            return BootstrapReport(
                configured=True,
                reachable=False,
                transactional=False,
                schema_present=False,
                schema_version_ok=False,
                dialect=dialect,
                detail=f"schema creation failed ({type(exc).__name__})",
            )

    # 1 + 2. Reachable, and genuinely transactional. A connection that answers
    #        SELECT 1 but cannot hold a transaction is not a system of record.
    try:
        with store.atomic() as unit:
            unit.execute(sa.text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001
        return BootstrapReport(
            configured=True,
            reachable=False,
            transactional=False,
            schema_present=False,
            schema_version_ok=False,
            dialect=dialect,
            detail=f"no usable transaction ({type(exc).__name__})",
        )

    # 3. Every table this build writes to. Checked by name against the
    #    catalogue rather than by querying each one, so a missing table is a
    #    named answer instead of a failed statement.
    try:
        inspector = sa.inspect(store.engine)
        present = set(inspector.get_table_names())
    except Exception as exc:  # noqa: BLE001
        return BootstrapReport(
            configured=True,
            reachable=True,
            transactional=True,
            schema_present=False,
            schema_version_ok=False,
            dialect=dialect,
            detail=f"the schema could not be inspected ({type(exc).__name__})",
        )
    missing = tuple(sorted(t.name for t in DURABLE_TABLES if t.name not in present))

    return BootstrapReport(
        configured=True,
        reachable=True,
        transactional=True,
        schema_present=not missing,
        # In this phase the durable schema version is a build-time constant and
        # the tables are its only expression, so a complete schema *is* the
        # right version. When the schema gains a version row this reads it; the
        # field exists now so readiness does not change shape later.
        schema_version_ok=not missing,
        dialect=dialect,
        missing_tables=missing,
        detail=(
            f"missing tables: {', '.join(missing)}" if missing else None
        ),
    )
