"""Composition root: the durable repositories, and the transaction that binds them.

What crosses here
-------------------
The contexts declare ports and never construct a store. This module builds the
one ``DurableStore`` and hands it to each context's SQL repository, exactly as
``capability_execution_composition`` hands services to the invocation gateway.
It is the only module that knows both which database exists and which contexts
need one.

The state/event pair, which is why this module has a function rather than only
a builder
-----------------------------------------------------------------------------
``DurableExecutionStore.record_outcome`` is the one operation in this phase that
*must* be atomic: an execution's state change and the outbox event announcing it
have to commit together, or the run and everything downstream disagree about what
happened and nothing detects it.

Repositories cannot arrange that themselves — each would open its own
transaction. So the boundary is here, in one ``with store.atomic()`` block that
both writes enlist in. That is the whole reason ``UnitOfWork`` is a parameter on
every repository method.

Which pairs are atomic, and which are honestly not
----------------------------------------------------
    execution state + outbox event      atomic (one transaction)
    lease claim + execution state       atomic when written in one unit
    outbox publish + provider delivery  **not atomic, and cannot be**

The third is the honest limit. Publication reaches something outside this
database, so no transaction spans it — which is exactly why the outbox exists and
why delivery is at-least-once. A consumer that deduplicates on ``event_id`` is
correct; one that assumes single delivery is not.

Production cannot fall back
-----------------------------
``build_durable_persistence`` raises when the store is unavailable. There is no
argument that returns in-memory repositories, and the in-memory ones are reached
only through their own constructors — which a person has to type, and which a
failure cannot trigger.
"""

from __future__ import annotations

import logging
from typing import Any, Optional, Sequence

from backend.contracts.execution import ExecutionEnvironment
from backend.database.durable import (
    BootstrapReport,
    DurabilityConfig,
    DurableStore,
    build_development_store,
    build_durable_store,
    verify_durability,
)

__all__ = [
    "DurablePersistence",
    "DurableExecutionStore",
    "DurableReadiness",
    "SchedulerLeadership",
    "build_durable_persistence",
    "build_development_persistence",
]

log = logging.getLogger(__name__)


class DurableExecutionStore:
    """The application-level transaction boundary for execution writes.

    Not a repository and not a service: it is the small amount of code that
    knows *which writes belong in one transaction*. Everything it does is
    delegate, and the only thing it adds is the ``with`` block.
    """

    __slots__ = ("_store", "executions", "outbox", "leases", "idempotency")

    def __init__(
        self,
        store: DurableStore,
        *,
        executions: Any,
        outbox: Any,
        leases: Any,
        idempotency: Any,
    ) -> None:
        self._store = store
        self.executions = executions
        self.outbox = outbox
        self.leases = leases
        self.idempotency = idempotency

    # ------------------------------------------------------------------

    def record_outcome(
        self,
        context: Any,
        execution: Any,
        events: Sequence[Any],
        *,
        expected_revision: int,
    ) -> int:
        """State change and its events, in one transaction. **The critical pair.**

        Either the run moves and the events exist, or neither happened. The
        failure this closes is the one an outbox is for: state written, process
        dies, event never published, and the runtime and everything downstream
        disagree while the run looks fine from the inside.

        ``compare_and_swap`` inside the same unit means a concurrent writer also
        loses the events it would have recorded — which is right. A decision that
        was refused should not leave its announcement behind.
        """
        with self._store.atomic() as unit:
            revision = self.executions.compare_and_swap(
                context, execution, expected_revision=expected_revision, unit=unit
            )
            if events:
                self.outbox.record(
                    context, str(execution.execution_id), events, unit=unit
                )
            return revision

    def start(self, context: Any, execution: Any, events: Sequence[Any] = ()) -> None:
        """Create a run and its opening events together."""
        with self._store.atomic() as unit:
            self.executions.save(context, execution, unit=unit)
            if events:
                self.outbox.record(
                    context, str(execution.execution_id), events, unit=unit
                )

    def claim_node(
        self,
        context: Any,
        *,
        execution: Any,
        node_id: str,
        worker_id: str,
        lease_id: str,
        seconds: int,
        attempt_id: Optional[str] = None,
        expected_revision: Optional[int] = None,
        events: Sequence[Any] = (),
    ) -> dict:
        """Take a node and record the aggregate move in one transaction.

        The lease INSERT is the race. Losing it raises before anything else in
        this unit is written, so a worker that lost cannot leave a half-recorded
        attempt behind — which is the difference between a lease that is a
        durable claim and a lease that is a note in a document.
        """
        with self._store.atomic() as unit:
            lease = self.leases.acquire(
                context,
                execution_id=str(execution.execution_id),
                node_id=node_id,
                worker_id=worker_id,
                lease_id=lease_id,
                seconds=seconds,
                attempt_id=attempt_id,
                unit=unit,
            )
            if expected_revision is not None:
                self.executions.compare_and_swap(
                    context, execution, expected_revision=expected_revision, unit=unit
                )
            if events:
                self.outbox.record(
                    context, str(execution.execution_id), events, unit=unit
                )
            return lease

    def atomic(self, **kwargs: Any):
        """The raw boundary, for a caller that needs a pair this class does not
        name. Exposed rather than hidden so a new pair is written as one
        transaction instead of as two calls that usually both succeed."""
        return self._store.atomic(**kwargs)


class DurablePersistence:
    """Every durable repository, assembled once, with the store behind them."""

    __slots__ = (
        "store",
        "config",
        "executions",
        "outbox",
        "leases",
        "idempotency",
        "workers",
        "capabilities",
        "bindings",
        "authorizations",
        "delegations",
        "delegation_requests",
        "delegation_workflow",
        "connector_config",
        "execution_store",
        "queue",
        "leadership",
        "readiness_port",
        "instance_id",
        "audit_writer",
        "audit",
    )

    def __init__(
        self,
        *,
        store: DurableStore,
        config: DurabilityConfig,
        instance_id=None,
        metrics=None,
    ) -> None:
        from backend.contexts.connectivity.application.delegation import (
            DelegationWorkflow,
        )
        from backend.contexts.connectivity.infrastructure.sql_authority import (
            SqlAuthorizationRecordRepository,
            SqlDelegationRepository,
            SqlDelegationRequestRepository,
        )
        from backend.contexts.connectivity.infrastructure.sql_connector_config import (
            SqlConnectorConfigRepository,
        )
        from backend.contexts.connectivity.infrastructure.sql_repository import (
            SqlBindingRepository,
            SqlCapabilityRepository,
        )
        from backend.contexts.execution.infrastructure.sql_coordination import (
            SqlIdempotencyStore,
            SqlNodeLeaseStore,
        )
        from backend.contexts.execution.infrastructure.sql_outbox import SqlExecutionOutbox
        from backend.contexts.execution.infrastructure.sql_repository import (
            SqlExecutionRepository,
        )
        from backend.contexts.execution.infrastructure.sql_worker_directory import (
            SqlWorkerDirectory,
        )

        self.store = store
        self.config = config
        self.executions = SqlExecutionRepository(store)
        self.outbox = SqlExecutionOutbox(store)
        self.leases = SqlNodeLeaseStore(store)
        self.idempotency = SqlIdempotencyStore(store)
        self.workers = SqlWorkerDirectory(store)
        self.capabilities = SqlCapabilityRepository(store)
        self.bindings = SqlBindingRepository(store)
        self.authorizations = SqlAuthorizationRecordRepository(store)
        # Phase 5.3. The grant repository, the request repository, and the
        # workflow that is the only thing able to assemble the approval evidence
        # ``SqlDelegationRepository.issue`` demands.
        #
        # An empty table still means every on-behalf-of invocation is refused,
        # which remains the default. What changed is that there is now a
        # governed way to stop it being empty, rather than no way at all.
        self.delegations = SqlDelegationRepository(store)
        self.delegation_requests = SqlDelegationRequestRepository(store)
        self.delegation_workflow = DelegationWorkflow(
            requests=self.delegation_requests,
            delegations=self.delegations,
            store=store,
            metrics=metrics,
        )
        # Tenant-scoped connector configuration. Holds references; the credential
        # broker resolves them at invocation time, and no secret reaches this
        # repository -- it refuses material before the write.
        self.connector_config = SqlConnectorConfigRepository(store)
        self.execution_store = DurableExecutionStore(
            store,
            executions=self.executions,
            outbox=self.outbox,
            leases=self.leases,
            idempotency=self.idempotency,
        )

        # -- Phase 5.2: coordination over the durable state ---------------
        from backend.contexts.execution.infrastructure.sql_queue import SqlExecutionQueue
        from backend.database.durable.leadership import SqlLeadershipStore
        from backend.platform.identity import monotonic_ulid

        # This process's identity, for leadership and for queue claims.
        #
        # Generated per process rather than per host: two processes on one host
        # are two claimants, and a shared identity would let one release the
        # other's claim. It is deliberately not stable across a restart -- a
        # restarted process is a new claimant and must acquire rather than
        # resume, which is exactly what the fencing token is there to enforce.
        self.instance_id = instance_id or f"instance-{monotonic_ulid()}"
        self.queue = SqlExecutionQueue(store, metrics=metrics)
        self.leadership = SqlLeadershipStore(
            store, instance_id=self.instance_id, metrics=metrics
        )
        self.readiness_port = DurableReadiness(self)

        # -- Phase 5.13: the production audit authority (ADR-055/056) ------
        # The fenced PostgreSQL chain, composed here so that any process with
        # durable persistence has THE audit sink — the same store, the same
        # leadership table, the same fencing token as everything else. There
        # is deliberately no JSONL and no in-memory branch in this
        # constructor: a process that reaches this line has a verified durable
        # store, and a process without one never gets a DurablePersistence to
        # take an audit runtime from. Fail-closed is structural, not checked.
        #
        # The adapter is constructed unacquired. Appends refuse with
        # ``AuditWriterNotOwned`` until this process wins the role — taking it
        # is a startup act (``audit_writer.acquire()``), never a side effect
        # of composing, and never a side effect of appending.
        from backend.database.durable.audit import SqlAuditStore
        from backend.platform.audit import AuditRuntime

        self.audit_writer = AuditWriterLeadership(self.leadership)
        self.audit = AuditRuntime(
            SqlAuditStore(store, fence=self.audit_writer),
            ownership=self.audit_writer,
        )

    def readiness(self) -> dict:
        """Whether durable execution can operate safely, checked not assumed.

        Separate from process liveness on purpose: a process can be alive while
        the store is unavailable, and a health check that conflated them would
        take a healthy instance out of rotation for a database problem or, worse,
        leave a useless one in.

        Reads only. Nothing here mutates state, so it is safe to call on a
        schedule.
        """
        report: BootstrapReport = verify_durability(self.store)
        return {
            **report.to_dict(),
            "config": self.config.to_dict(),
            # Phase 4 said durability was not ready. Phase 5.1 makes state
            # durable and stops there: the scheduler, the dispatcher fleet and
            # cross-process work distribution are 5.2, so this reports what is
            # true rather than what is implied.
            "durable_state": report.ready,
            # Phase 5.2. Coordination now exists: a durable queue, fenced
            # leadership and a durable recovery connection. What is still not
            # claimed is a worker -- the execution directory is deliberately
            # empty, and the platform refuses execution without one.
            "durable_scheduling": report.ready,
            "durable_scheduling_note": (
                "Phase 5.2 provides a durable queue, fenced leadership and "
                "durable recovery. It provides no worker: the platform still "
                "refuses execution until one is registered and enabled"
            ),
            "instance_id": self.instance_id,
            "leadership": list(self.leadership.roles()) if report.ready else [],
        }

    def to_dict(self) -> dict:
        return {
            "dialect": self.store.dialect,
            "repositories": [
                "executions",
                "outbox",
                "leases",
                "idempotency",
                "workers",
                "capabilities",
                "bindings",
                "authorizations",
                "delegations",
            ],
            "config": self.config.to_dict(),
        }


# ----------------------------------------------------------------------
# Assembly
# ----------------------------------------------------------------------


def build_durable_persistence(
    *,
    config: DurabilityConfig,
    clock: Optional[Any] = None,
    metrics: Optional[Any] = None,
    dsn: Optional[str] = None,
    instance_id: Optional[str] = None,
) -> DurablePersistence:
    """Assemble the durable repositories, or refuse.

    **There is no in-memory fallback.** ``build_durable_store`` verifies
    configuration, connectivity, transaction capability and schema before this
    returns, and raises otherwise — so a process that starts has a durable store,
    and a process without one does not start.
    """
    store = build_durable_store(config, clock=clock, metrics=metrics, dsn=dsn)
    return DurablePersistence(
        store=store, config=config, instance_id=instance_id, metrics=metrics
    )


def build_development_persistence(
    *,
    dsn: str,
    environment: ExecutionEnvironment = ExecutionEnvironment.DEVELOPMENT,
    clock: Optional[Any] = None,
    metrics: Optional[Any] = None,
    instance_id: Optional[str] = None,
) -> DurablePersistence:
    """Durable repositories over a development database. **Never production.**

    A separately named function rather than a flag, for the reason every other
    development builder in this codebase is one: a flag is something a
    configuration file sets by accident and a differently named function is
    something a person has to type. It creates the schema directly, which is
    exactly what the production builder refuses.
    """
    if environment is ExecutionEnvironment.PRODUCTION:
        from backend.database.durable import DurabilityMisconfigured

        raise DurabilityMisconfigured(
            "build_development_persistence cannot serve production; it creates "
            "its own schema, which is how a deployment drifts from its migration "
            "history without anybody noticing"
        )
    store = build_development_store(dsn=dsn, clock=clock, metrics=metrics)
    return DurablePersistence(
        store=store,
        instance_id=instance_id,
        metrics=metrics,
        # ``create_schema`` is on here and refused by the config for production,
        # so the difference between the two builders is visible in the object a
        # caller ends up holding rather than only in which function they called.
        config=DurabilityConfig(environment=environment, create_schema=True),
    )


class DurableReadiness:
    """Whether durable state is usable, asked repeatedly rather than once.

    Implements the scheduler's and the publisher's ``ReadinessPort``. Read every
    tick on purpose: a database that went away after the process started is
    exactly the case this exists for, and a check performed once at startup would
    let a scheduler keep dispatching work it can no longer record.

    Fails closed on anything it cannot establish. "Not known to be broken" is not
    "known working", and treating it as such is how a fleet keeps accepting work
    during the incident.
    """

    __slots__ = ("_persistence",)

    def __init__(self, persistence: "DurablePersistence") -> None:
        self._persistence = persistence

    def is_ready(self) -> bool:
        try:
            return bool(verify_durability(self._persistence.store).ready)
        except Exception:  # noqa: BLE001 - unverifiable durability is unusable
            log.warning("durability readiness check failed", exc_info=False)
            return False


class SchedulerLeadership:
    """The scheduler's ``LeadershipPort``, over the durable leadership store.

    A three-method adapter, and deliberately nothing more: the execution context
    does not need to know what a fencing token is, only whether it holds the
    role. The token travels on the handle for the one caller that must carry it
    into a write -- durable recovery -- and is otherwise invisible.
    """

    __slots__ = ("_store", "_role", "_lease_seconds")

    def __init__(self, store, *, role=None, lease_seconds: int = 30) -> None:
        from backend.database.durable.leadership import LeadershipRole

        if lease_seconds < 1:
            raise ValueError("a leadership lease must last at least a second")
        self._store = store
        self._role = role or LeadershipRole.SCHEDULER
        self._lease_seconds = lease_seconds

    def acquire(self):
        return self._store.acquire(role=self._role, lease_seconds=self._lease_seconds)

    def heartbeat(self, handle):
        return self._store.heartbeat(handle, lease_seconds=self._lease_seconds)

    def release(self, handle) -> bool:
        return self._store.release(handle)

    def assert_current(self, handle) -> None:
        self._store.assert_current(handle)


class AuditWriterLeadership:
    """The audit writer's ownership *and* fence, over the durable leadership.

    One adapter answers both ports because they must agree on one handle:

    * ``is_writer`` is ``AuditRuntime``'s ownership port -- admission, checked
      before every append, kept from Phase 5.11 unchanged.
    * ``handle`` is ``SqlAuditStore``'s fence -- the token the append
      transaction carries into ``fenced_where``, which is what makes a stale
      writer's append physically impossible rather than merely refused when
      detected (ADR-055).

    Same three-line shape as :class:`SchedulerLeadership`, same store, same
    role table, same token. Nothing here elects, locks, or counts anything of
    its own; losing the role makes ``heartbeat`` return ``None``, which drops
    the handle, which makes both ports refuse.
    """

    __slots__ = ("_store", "_role", "_lease_seconds", "handle")

    def __init__(self, store, *, lease_seconds: int = 30) -> None:
        from backend.database.durable.leadership import LeadershipRole

        if lease_seconds < 1:
            raise ValueError("a leadership lease must last at least a second")
        self._store = store
        self._role = LeadershipRole.AUDIT_WRITER
        self._lease_seconds = lease_seconds
        self.handle = None

    def acquire(self):
        self.handle = self._store.acquire(
            role=self._role, lease_seconds=self._lease_seconds
        )
        return self.handle

    def release(self) -> bool:
        if self.handle is None:
            return False
        released = self._store.release(self.handle)
        self.handle = None
        return released

    def is_writer(self) -> bool:
        """The admission answer, renewed through the same lease every call.

        Advisory by design -- the physical guarantee is the fence the store
        carries into its append transaction, not this check. This exists so an
        unowned runtime refuses early with a clear error instead of paying for
        a doomed transaction.
        """
        if self.handle is None:
            return False
        renewed = self._store.heartbeat(self.handle, lease_seconds=self._lease_seconds)
        if renewed is None:
            self.handle = None
            return False
        self.handle = renewed
        return True
