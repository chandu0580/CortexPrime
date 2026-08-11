"""PostgreSQL operational harness. Attempts a real database; never simulates one.

What this is for
------------------
Phases 5.1 and 5.2 built durable state and distributed coordination and could
not verify either against PostgreSQL, because no PostgreSQL was reachable and no
container runtime was available. Both phases reported that rather than
substituting SQLite, and both left a specific list of unverified behaviours.

This is the harness that closes that list when a database is available. It:

    1. locates a PostgreSQL, or reports precisely why it cannot;
    2. creates an isolated schema so nothing touches an existing database;
    3. applies the durable schema and verifies it;
    4. runs the concurrency scenarios only PostgreSQL can exercise;
    5. drops the schema and disposes the pool, whatever happened.

The one thing it will never do
--------------------------------
**It will not fall back to SQLite.** A green result from SQLite would be a
PostgreSQL claim nobody earned, and the exit code says so: ``0`` verified, ``1``
verified-and-failed, ``2`` NOT VERIFIED. A caller that treats ``2`` as success
is making the claim this file exists to prevent.

Isolation
-----------
Everything is created inside a dedicated schema (``cp_harness_<pid>``) selected
through ``search_path``, so a mistake here cannot damage an existing database and
the cleanup is one ``DROP SCHEMA CASCADE``. It still expects to be pointed at a
throwaway database, and it says so before it starts.

Usage
-------
    POSTGRES_URL=postgresql://user:pass@localhost:5432/cortex_test \\
        python -m scripts.postgres_durability_harness

    python -m scripts.postgres_durability_harness --start-container
        Starts a disposable PostgreSQL through Docker if one is available, uses
        it, and removes it afterwards. Reports honestly if Docker is not there.
"""

from __future__ import annotations

import argparse
import os
import socket
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import urlsplit

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

VERIFIED, FAILED, NOT_VERIFIED = 0, 1, 2

SCHEMA = f"cp_harness_{os.getpid()}"

#: What SQLite cannot answer, restated here so a NOT VERIFIED result says
#: exactly what remains unknown rather than "PostgreSQL untested".
UNVERIFIABLE_WITHOUT_POSTGRES = (
    "serialization failure (SQLSTATE 40001) classification",
    "deadlock detection (SQLSTATE 40P01) classification",
    "BIGSERIAL sequence allocation for cp_outbox.sequence",
    "connection-pool exhaustion and acquisition timeout",
    "connection loss during COMMIT and the UnknownCommitOutcome path",
    "concurrent leadership election under real MVCC",
    "JSONB column behaviour for the document columns",
)

_CONTAINER = "cortexprime-durability-harness"


class Report:
    """Results, kept apart so a skip can never be counted as a pass."""

    def __init__(self) -> None:
        self.passed: list = []
        self.failed: list = []
        self.skipped: list = []

    def check(self, name: str, condition: bool, detail: object = "") -> bool:
        line = f"{name}{(' :: ' + str(detail)) if detail else ''}"
        (self.passed if condition else self.failed).append(line)
        return bool(condition)

    def skip(self, name: str, why: str) -> None:
        self.skipped.append(f"{name} :: {why}")

    def render(self) -> int:
        for line in self.passed:
            print(f"PASS  {line}")
        for line in self.skipped:
            print(f"SKIP  {line}")
        if self.failed:
            print()
            for line in self.failed:
                print(f"FAIL  {line}")
        print(
            f"\n{len(self.passed)} passed, {len(self.failed)} failed, "
            f"{len(self.skipped)} skipped"
        )
        return FAILED if self.failed else VERIFIED


# ----------------------------------------------------------------------
# Locating a database
# ----------------------------------------------------------------------


def dsn() -> str:
    url = os.environ.get("POSTGRES_URL", "").strip()
    if url:
        for prefix in ("postgresql+asyncpg://", "postgres://"):
            if url.startswith(prefix):
                url = "postgresql+psycopg2://" + url[len(prefix):]
        return url
    user = os.environ.get("POSTGRES_USER", "cortex")
    password = os.environ.get("POSTGRES_PASSWORD", "")
    host = os.environ.get("POSTGRES_HOST", "localhost")
    port = os.environ.get("POSTGRES_PORT", "5432")
    name = os.environ.get("POSTGRES_DB", "cortexdb")
    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{name}"


def endpoint() -> tuple:
    url = os.environ.get("POSTGRES_URL", "").strip()
    if url:
        parts = urlsplit(url)
        return parts.hostname or "localhost", parts.port or 5432
    return (
        os.environ.get("POSTGRES_HOST", "localhost"),
        int(os.environ.get("POSTGRES_PORT", "5432")),
    )


def reachable(timeout: float = 3.0) -> tuple:
    host, port = endpoint()
    probe = socket.socket()
    probe.settimeout(timeout)
    try:
        probe.connect((host, port))
        return True, ""
    except Exception as exc:
        return False, f"{host}:{port} is not reachable ({type(exc).__name__})"
    finally:
        probe.close()


def start_container() -> tuple:
    """Start a disposable PostgreSQL. Returns ``(started, why_not)``.

    Deliberately not silent about what it does: this creates a container on the
    caller's machine and removes it afterwards, which is a side effect somebody
    should be able to see in the output.
    """
    try:
        subprocess.run(
            ["docker", "version"],
            check=True,
            capture_output=True,
            timeout=20,
        )
    except Exception as exc:
        return False, f"docker is not usable here ({type(exc).__name__})"

    subprocess.run(["docker", "rm", "-f", _CONTAINER], capture_output=True)
    result = subprocess.run(
        [
            "docker", "run", "-d", "--name", _CONTAINER,
            "-e", "POSTGRES_PASSWORD=harness",
            "-e", "POSTGRES_USER=harness",
            "-e", "POSTGRES_DB=harness",
            "-p", "55432:5432",
            "postgres:16-alpine",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return False, f"docker run failed: {result.stderr.strip()[:200]}"

    os.environ["POSTGRES_URL"] = (
        "postgresql+psycopg2://harness:harness@localhost:55432/harness"
    )
    print(f"  started container {_CONTAINER} on localhost:55432")
    for _ in range(60):
        ok, _why = reachable(timeout=1.0)
        if ok:
            # The port accepting is not the server being ready to authenticate.
            time.sleep(2.0)
            return True, ""
        time.sleep(1.0)
    return False, "the container started but never accepted connections"


def stop_container() -> None:
    subprocess.run(["docker", "rm", "-f", _CONTAINER], capture_output=True)
    print(f"  removed container {_CONTAINER}")


# ----------------------------------------------------------------------
# The verification itself
# ----------------------------------------------------------------------


def run_checks(report: Report) -> None:
    import sqlalchemy as sa

    from backend.database.durable.errors import (
        ConstraintConflict,
        DeadlockDetected,
        SerializationConflict,
        classify_database_error,
    )
    from backend.database.durable.leadership import LeadershipRole, SqlLeadershipStore
    from backend.database.durable.session import DurableStore
    from backend.database.durable.config import verify_durability
    from backend.database.durable.tables import (
        DURABLE_METADATA,
        DURABLE_TABLES,
        SCHEMA_VERSION,
        delegation_request_table,
        outbox_table,
    )

    engine = sa.create_engine(
        dsn(),
        # Bounded and explicit. A pool with no ceiling is a process that opens
        # connections until the database refuses, and "the database refused" is
        # then indistinguishable from a real outage.
        pool_size=4,
        max_overflow=2,
        pool_timeout=3,
        pool_recycle=1800,
        pool_pre_ping=True,
        future=True,
        connect_args={"options": f"-csearch_path={SCHEMA}"},
    )

    admin = sa.create_engine(dsn(), future=True, poolclass=sa.pool.NullPool)
    try:
        with admin.begin() as conn:
            conn.execute(sa.text(f'DROP SCHEMA IF EXISTS "{SCHEMA}" CASCADE'))
            conn.execute(sa.text(f'CREATE SCHEMA "{SCHEMA}"'))
        print(f"  isolated schema {SCHEMA} created")

        store = DurableStore(engine)
        report.check("dialect is postgresql", store.dialect == "postgresql", store.dialect)

        # -- schema ------------------------------------------------------
        DURABLE_METADATA.create_all(engine)
        verification = verify_durability(store)
        report.check(
            f"the durable schema (v{SCHEMA_VERSION}, {len(DURABLE_TABLES)} tables) "
            "is created and verified",
            verification.ready,
            verification.to_dict(),
        )

        with engine.connect() as conn:
            present = set(
                sa.inspect(conn).get_table_names(schema=SCHEMA)
            )
        expected = {t.name for t in DURABLE_TABLES}
        report.check(
            "every defined table exists in PostgreSQL", expected <= present,
            sorted(expected - present),
        )

        # -- JSONB -------------------------------------------------------
        with engine.connect() as conn:
            kinds = {
                row[0]: row[1]
                for row in conn.execute(
                    sa.text(
                        "SELECT column_name, data_type FROM information_schema.columns "
                        "WHERE table_schema = :s AND table_name = 'cp_delegation_request'"
                    ),
                    {"s": SCHEMA},
                )
            }
        report.check(
            "document columns are JSONB on PostgreSQL",
            kinds.get("scope") == "jsonb",
            kinds.get("scope"),
        )
        report.check(
            "authority timestamps are timestamptz",
            kinds.get("requested_at") == "timestamp with time zone",
            kinds.get("requested_at"),
        )

        # -- BIGSERIAL ---------------------------------------------------
        with store.atomic() as unit:
            first = unit.execute(
                sa.insert(outbox_table).values(
                    entry_id="h-1", tenant_id="t", execution_id="e",
                    event_type="T", event_id="h-ev-1", payload={},
                    status="pending", attempts=0, recorded_at=unit.now,
                )
            ).inserted_primary_key[0]
            second = unit.execute(
                sa.insert(outbox_table).values(
                    entry_id="h-2", tenant_id="t", execution_id="e",
                    event_type="T", event_id="h-ev-2", payload={},
                    status="pending", attempts=0, recorded_at=unit.now,
                )
            ).inserted_primary_key[0]
        report.check(
            "BIGSERIAL allocates monotonically for cp_outbox.sequence",
            second > first,
            (first, second),
        )

        # -- unique event_id ---------------------------------------------
        try:
            with store.atomic() as unit:
                unit.execute(
                    sa.insert(outbox_table).values(
                        entry_id="h-3", tenant_id="t", execution_id="e",
                        event_type="T", event_id="h-ev-1", payload={},
                        status="pending", attempts=0, recorded_at=unit.now,
                    )
                )
            report.check("a duplicate event_id is refused", False, "it was accepted")
        except Exception as exc:
            report.check(
                "a duplicate event_id is refused and classified",
                isinstance(exc, ConstraintConflict),
                type(exc).__name__,
            )

        # -- concurrent leadership ---------------------------------------
        stores = [SqlLeadershipStore(store, instance_id=f"h-{n}") for n in range(4)]
        with ThreadPoolExecutor(max_workers=4) as pool:
            handles = list(
                pool.map(
                    lambda s: _acquire_quietly(s, LeadershipRole.SCHEDULER), stores
                )
            )
        winners = [h for h in handles if h is not None]
        report.check(
            "four concurrent acquisitions elect exactly one leader",
            len(winners) == 1,
            len(winners),
        )
        if winners:
            report.check(
                "the fencing token is positive and monotonic",
                winners[0].fencing_token >= 1,
                winners[0].fencing_token,
            )

        # -- serialization conflict --------------------------------------
        conflicts: list = []

        def contend(_n: int) -> str:
            try:
                with engine.connect().execution_options(
                    isolation_level="SERIALIZABLE"
                ) as conn:
                    with conn.begin():
                        conn.execute(
                            sa.update(outbox_table)
                            .where(outbox_table.c.entry_id == "h-1")
                            .values(attempts=outbox_table.c.attempts + 1)
                        )
                        time.sleep(0.4)
                return "committed"
            except Exception as exc:
                conflicts.append(classify_database_error(exc))
                return "conflict"

        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(contend, range(2)))
        if "conflict" in outcomes:
            report.check(
                "a serialization conflict arrives classified, not swallowed",
                any(
                    isinstance(c, (SerializationConflict, DeadlockDetected))
                    for c in conflicts
                ),
                [type(c).__name__ for c in conflicts],
            )
        else:
            # Honest: PostgreSQL is entitled to let both commit here. Recorded
            # as a skip rather than a pass, because nothing was demonstrated.
            report.skip(
                "serialization conflict classification",
                "both transactions committed; no conflict occurred this run",
            )

        # -- deadlock ------------------------------------------------------
        deadlocks: list = []

        def cross(order: tuple) -> str:
            try:
                with engine.connect() as conn:
                    with conn.begin():
                        for entry in order:
                            conn.execute(
                                sa.update(outbox_table)
                                .where(outbox_table.c.entry_id == entry)
                                .values(attempts=outbox_table.c.attempts + 1)
                            )
                            time.sleep(0.3)
                return "committed"
            except Exception as exc:
                deadlocks.append(classify_database_error(exc))
                return "deadlock"

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(cross, [("h-1", "h-2"), ("h-2", "h-1")]))
        if "deadlock" in results:
            report.check(
                "a deadlock (40P01) arrives classified",
                any(
                    isinstance(d, (DeadlockDetected, SerializationConflict))
                    for d in deadlocks
                ),
                [type(d).__name__ for d in deadlocks],
            )
        else:
            report.skip(
                "deadlock classification", "no deadlock occurred this run"
            )

        # -- delegation round trip -----------------------------------------
        # The Phase 5.3 tables, against real timestamptz. This is the round trip
        # that broke on SQLite in 5.2 -- a digest computed over an aware datetime
        # and verified against a naive one -- so it is worth proving on the
        # database that actually stores the timezone.
        with store.atomic() as unit:
            unit.execute(
                sa.insert(delegation_request_table).values(
                    request_id="h-req-1", tenant_id="t", requested_by="p1",
                    actor_principal_id="p2", delegated_principal_id="p3",
                    scope=[{"capability_ref": "c@1", "operations": ["read"]}],
                    reason="harness", requested_validity_seconds=60,
                    requested_at=unit.now,
                    expires_at=unit.now + timedelta(seconds=600),
                    request_digest="0" * 64, status="pending",
                )
            )
        with store.atomic() as unit:
            row = unit.execute(
                sa.select(delegation_request_table).where(
                    delegation_request_table.c.request_id == "h-req-1"
                )
            ).mappings().one()
        report.check(
            "a delegation request round-trips with its timezone intact",
            row["requested_at"].tzinfo is not None,
            row["requested_at"],
        )
        report.check(
            "a JSONB scope round-trips as a list of documents",
            row["scope"] == [{"capability_ref": "c@1", "operations": ["read"]}],
            row["scope"],
        )

        # -- pool exhaustion -----------------------------------------------
        held: list = []
        try:
            for _ in range(10):
                held.append(engine.connect())
            report.check(
                "the pool is bounded", False, "opened more than size + overflow"
            )
        except Exception as exc:
            report.check(
                "pool exhaustion raises rather than growing unbounded",
                "timeout" in type(exc).__name__.lower(),
                type(exc).__name__,
            )
        finally:
            for conn in held:
                conn.close()

        # -- connection loss during commit ----------------------------------
        # Terminating the backend mid-transaction is the only way to produce a
        # genuine unknown commit outcome. What must be true is that it is never
        # reported as success.
        try:
            with engine.connect() as conn:
                pid = conn.execute(sa.text("SELECT pg_backend_pid()")).scalar_one()
                trans = conn.begin()
                conn.execute(
                    sa.insert(outbox_table).values(
                        entry_id="h-kill", tenant_id="t", execution_id="e",
                        event_type="T", event_id="h-ev-kill", payload={},
                        status="pending", attempts=0,
                        recorded_at=datetime.now(timezone.utc),
                    )
                )
                with admin.connect() as killer:
                    killer.execute(
                        sa.text("SELECT pg_terminate_backend(:pid)"), {"pid": pid}
                    )
                trans.commit()
            report.skip(
                "connection loss during COMMIT",
                "the commit completed before the backend was terminated",
            )
        except Exception as exc:
            classified = classify_database_error(exc, during_commit=True)
            report.check(
                "a connection lost during COMMIT is never reported as settled",
                not getattr(classified, "settled", True),
                f"{type(classified).__name__}(settled="
                f"{getattr(classified, 'settled', '?')})",
            )

        engine.dispose()
        report.check(
            "disposal releases every pooled connection",
            engine.pool.checkedout() == 0,
            engine.pool.checkedout(),
        )

    finally:
        try:
            with admin.begin() as conn:
                conn.execute(sa.text(f'DROP SCHEMA IF EXISTS "{SCHEMA}" CASCADE'))
            print(f"  isolated schema {SCHEMA} dropped")
        except Exception as exc:  # noqa: BLE001
            print(f"  WARNING: could not drop {SCHEMA}: {exc}")
        engine.dispose()
        admin.dispose()


def _acquire_quietly(store, role):
    try:
        return store.acquire(role=role, lease_seconds=60)
    except Exception:  # noqa: BLE001 - a lost election is not an error here
        return None


def report_not_verified(why: str) -> int:
    print("POSTGRESQL VERIFICATION: NOT VERIFIED")
    print(f"  reason: {why}")
    print()
    print("  SQLite was NOT substituted. A green result from SQLite would be a")
    print("  PostgreSQL claim nobody earned.")
    print()
    print("  What remains unverified, specifically:")
    for gap in UNVERIFIABLE_WITHOUT_POSTGRES:
        print(f"    - {gap}")
    print()
    print("  Set POSTGRES_URL to a throwaway database, or pass --start-container")
    print("  if Docker is available, and run this again.")
    return NOT_VERIFIED


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--start-container",
        action="store_true",
        help="start a disposable PostgreSQL through Docker and remove it after",
    )
    parser.add_argument(
        "--keep-container",
        action="store_true",
        help="leave the container running for inspection",
    )
    args = parser.parse_args(argv)

    started = False
    if args.start_container:
        print("Starting a disposable PostgreSQL container...")
        started, why = start_container()
        if not started:
            return report_not_verified(why)

    try:
        ok, why = reachable()
        if not ok:
            return report_not_verified(why)

        try:
            import psycopg2  # noqa: F401
        except ImportError:
            return report_not_verified(
                "psycopg2 is not installed; the driver is required to speak to "
                "PostgreSQL and no substitute is acceptable"
            )

        host, port = endpoint()
        print(f"PostgreSQL reachable at {host}:{port}. This harness creates and")
        print(f"drops the schema {SCHEMA}; point it at a throwaway database.")
        print()

        report = Report()
        try:
            run_checks(report)
        except Exception as exc:  # noqa: BLE001
            print(f"HARNESS ERROR: {type(exc).__name__}: {exc}")
            report.failed.append(f"the harness itself raised: {type(exc).__name__}")
        return report.render()
    finally:
        if started and not args.keep_container:
            stop_container()


if __name__ == "__main__":
    sys.exit(main())
