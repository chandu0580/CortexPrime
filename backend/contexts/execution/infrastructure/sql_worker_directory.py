"""The durable worker directory. Registrations persist; adapters do not.

The distinction this module rests on
--------------------------------------
A worker *registration* is state: an identity, a digest, a lifecycle, a trust
level, a tenant scope. It belongs in the database and it must survive a restart,
because "this adapter was quarantined" is a decision somebody made and a restart
must not undo it.

A worker *adapter* is code. It is an object with a transport behind it, and it
cannot be persisted by any means. So this stores the entry durably and keeps the
adapter in this process, wired at composition.

The consequence is stated rather than hidden: ``adapter_for`` returns ``None`` in
a process where the adapter has not been wired, even though the registration is
present. Execution already treats that as ``worker_adapter_unavailable`` — a
refusal, not a substitution — which is the correct behaviour for "this instance
cannot perform that work". A second instance that *has* wired it can.

What durability changes
-------------------------
The in-memory directory held the duplicate check and the write under one Python
lock. Two application instances registering the same worker id both passed that
check. Here the identity is a **primary key** on ``(scope_owner, worker_id)``, so
the second INSERT collides and exactly one registration wins.

Shadowing is still impossible for the same reason: a tenant registering under an
id a platform worker holds writes to a different key, and the explicit check
against the platform slot happens inside the same transaction as the insert.

What durability deliberately does not change
----------------------------------------------
Registration is still not enablement. ``register`` writes ``REGISTERED`` /
``UNVERIFIED`` / ``UNAVAILABLE`` and there is no argument that skips the three
deliberate acts that follow. Lifecycle and trust transitions still go through the
domain's own ``WorkerEntry`` methods, which own the legality table — this stores
the result rather than deciding it, so there is no path where a database write
performs a transition the domain forbids.

Ambiguity is still a refusal. ``candidates`` returns entries unranked, in a
stable order for *reading*, and selection refuses two eligible workers rather
than taking the first. Nothing about a database changes that.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional, Tuple

import sqlalchemy as sa

from backend.contracts.connector import IsolationTier
from backend.contracts.errors import ContractViolation
from backend.contracts.execution import EffectSemantics, ExecutionEnvironment
from backend.contexts.execution.domain.worker import WorkerKind
from backend.contexts.execution.domain.worker_contract import CancellationSupport
from backend.contexts.execution.domain.worker_directory import (
    WorkerAvailability,
    WorkerEntry,
    WorkerImplementation,
    WorkerInterface,
    WorkerLifecycle,
    WorkerScope,
    WorkerTrust,
)
from backend.contexts.execution.domain.worker_events import (
    WORKER_AGGREGATE_TYPE,
    WorkerDisabled,
    WorkerEnabled,
    WorkerRegistered,
    WorkerRevoked,
    WorkerTrustChanged,
    WorkerValidated,
)
from backend.contexts.execution.infrastructure.worker_directory import (
    UnregisteredWorker,
    WorkerAlreadyRegistered,
)
from backend.database.durable.errors import ConstraintConflict
from backend.database.durable.session import (
    DurableStore,
    NoDurableStore,
    UnitOfWork,
    enlisted,
)
from backend.database.durable.tables import PLATFORM_SCOPE, worker_table
from backend.platform.events import EventMetadata

__all__ = ["SqlWorkerDirectory"]


class SqlWorkerDirectory:
    """The durable ``WorkerDirectory``. Same port, same refusals, same events."""

    def __init__(self, store: DurableStore) -> None:
        if not isinstance(store, DurableStore):
            raise NoDurableStore("a durable worker directory requires a store")
        self._store = store
        # Adapters are code, not state. Held per process and wired at
        # composition; a process without one refuses rather than substituting.
        self._adapters: dict = {}

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(
        self,
        context: Any,
        implementation: WorkerImplementation,
        adapter: Any,
        *,
        now: Optional[datetime] = None,
        unit: Optional[UnitOfWork] = None,
    ) -> Tuple[WorkerEntry, WorkerRegistered]:
        """Record an implementation. It is not usable when this returns."""
        if not isinstance(implementation, WorkerImplementation):
            raise ContractViolation("implementation must be a WorkerImplementation")
        if adapter is None:
            raise ContractViolation(
                f"worker {implementation.worker_id!r} was registered with no adapter; "
                "an entry nothing implements is selectable and then unrunnable"
            )
        self._assert_context_matches(context, implementation)

        scope_owner = implementation.tenant_id or PLATFORM_SCOPE
        with self._scope(unit) as work:
            moment = now or work.now
            if implementation.scope is WorkerScope.TENANT:
                # Checked inside the transaction, so a platform registration
                # landing concurrently cannot slip between the check and the
                # insert. Shadowing would redirect platform work into an adapter
                # a tenant controls -- a privilege escalation that looks like a
                # naming collision.
                clash = work.execute(
                    sa.select(worker_table.c.worker_id).where(
                        worker_table.c.scope_owner == PLATFORM_SCOPE,
                        worker_table.c.worker_id == implementation.worker_id,
                    )
                ).first()
                if clash is not None:
                    raise WorkerAlreadyRegistered(
                        f"a platform worker already holds the id "
                        f"{implementation.worker_id!r}; a tenant registration "
                        "under it would shadow platform work into a "
                        "tenant-controlled adapter"
                    )

            entry = WorkerEntry(
                implementation=implementation,
                lifecycle=WorkerLifecycle.REGISTERED,
                trust=WorkerTrust.UNVERIFIED,
                availability=WorkerAvailability.UNAVAILABLE,
                registered_at=moment,
                updated_at=moment,
            )
            try:
                work.execute(
                    sa.insert(worker_table).values(
                        **self._columns(entry, scope_owner, moment, moment)
                    )
                )
            except ConstraintConflict:
                # The database expressing "that id is taken". Silently replacing
                # would change what runs without anybody deciding, and the digest
                # would not say so.
                raise WorkerAlreadyRegistered(
                    f"worker {implementation.worker_id!r} is already registered"
                ) from None

        self._adapters[(scope_owner, implementation.worker_id)] = adapter
        return entry, WorkerRegistered(
            metadata=self._metadata(context, entry),
            worker_id=entry.worker_id,
            worker_kind=entry.worker_kind.value,
            worker_version=entry.worker_version,
            worker_digest=entry.worker_digest,
            scope=implementation.scope.value,
            interface=implementation.interface.value,
            implementation=implementation.implementation,
            isolation=implementation.isolation.value,
            protocol_version=implementation.protocol_version,
            environments=tuple(sorted(e.value for e in implementation.supported_environments)),
            providers=tuple(sorted(implementation.supported_providers)),
        )

    def attach_adapter(self, implementation: WorkerImplementation, adapter: Any) -> None:
        """Wire the code for an entry this process did not register.

        The method a second application instance needs: the registration is
        already durable, and this instance holds the adapter that performs it.
        Deliberately separate from ``register`` — attaching code is not
        registering a worker, and merging them would let a restart re-run a
        registration decision.
        """
        if adapter is None:
            raise ContractViolation("an adapter is required")
        self._adapters[
            (implementation.tenant_id or PLATFORM_SCOPE, implementation.worker_id)
        ] = adapter

    # ------------------------------------------------------------------
    # Lifecycle — the domain decides, this records
    # ------------------------------------------------------------------

    def validate(
        self, context: Any, *, worker_id: str, tenant_id: str, note: str = ""
    ) -> Tuple[WorkerEntry, WorkerValidated]:
        moved = self._transition(context, worker_id, tenant_id, lambda e: e.validated())
        return moved, WorkerValidated(
            metadata=self._metadata(context, moved), **self._identity(moved), note=note
        )

    def enable(
        self, context: Any, *, worker_id: str, tenant_id: str
    ) -> Tuple[WorkerEntry, WorkerEnabled]:
        moved = self._transition(context, worker_id, tenant_id, lambda e: e.enabled())
        return moved, WorkerEnabled(
            metadata=self._metadata(context, moved),
            **self._identity(moved),
            trust=moved.trust.value,
            availability=moved.availability.value,
            executable=moved.is_executable,
        )

    def disable(
        self, context: Any, *, worker_id: str, tenant_id: str, reason: str
    ) -> Tuple[WorkerEntry, WorkerDisabled]:
        moved = self._transition(
            context, worker_id, tenant_id, lambda e: e.disabled(reason)
        )
        return moved, WorkerDisabled(
            metadata=self._metadata(context, moved), **self._identity(moved), reason=reason
        )

    def revoke(
        self, context: Any, *, worker_id: str, tenant_id: str, reason: str
    ) -> Tuple[WorkerEntry, WorkerRevoked]:
        """Withdraw permanently. The row stays; the adapter goes.

        The record remains because deleting it would erase the evidence that this
        implementation existed and was withdrawn. The adapter is dropped from
        this process so a revoked worker is unreachable even if a future lookup
        forgets to check the lifecycle — and because the lifecycle is durable,
        every other process refuses it too.
        """
        moved = self._transition(
            context, worker_id, tenant_id, lambda e: e.revoked(reason)
        )
        self._adapters.pop(self._key(moved.implementation), None)
        return moved, WorkerRevoked(
            metadata=self._metadata(context, moved), **self._identity(moved), reason=reason
        )

    def set_trust(
        self,
        context: Any,
        *,
        worker_id: str,
        tenant_id: str,
        trust: WorkerTrust,
        reason: str,
    ) -> Tuple[WorkerEntry, WorkerTrustChanged]:
        previous: list = []

        def move(entry: WorkerEntry) -> WorkerEntry:
            previous.append(entry.trust)
            return entry.with_trust(trust, reason)

        moved = self._transition(context, worker_id, tenant_id, move)
        return moved, WorkerTrustChanged(
            metadata=self._metadata(context, moved),
            **self._identity(moved),
            previous_trust=previous[0].value,
            trust=moved.trust.value,
            reason=reason,
        )

    def set_availability(
        self,
        context: Any,
        *,
        worker_id: str,
        tenant_id: str,
        availability: WorkerAvailability,
    ) -> WorkerEntry:
        """Record reachability. No event: an observation is not a decision."""
        return self._transition(
            context, worker_id, tenant_id, lambda e: e.with_availability(availability)
        )

    # ------------------------------------------------------------------
    # The port Execution reads
    # ------------------------------------------------------------------

    def candidates(
        self, context: Any, *, worker_kind: WorkerKind, tenant_id: str
    ) -> tuple:
        """Every entry of that kind this tenant may be offered. **Unranked.**

        Ordered for *reading* — platform before tenant, then by id — so a refusal
        lists candidates the same way twice. It is never a preference: selection
        refuses two eligible workers rather than taking the first, and a stable
        order must not be mistaken for a tie-break.
        """
        with self._store.reading() as work:
            rows = work.execute(
                sa.select(worker_table)
                .where(
                    worker_table.c.worker_kind == worker_kind.value,
                    sa.or_(
                        worker_table.c.scope_owner == PLATFORM_SCOPE,
                        worker_table.c.scope_owner == tenant_id,
                    ),
                )
                .order_by(worker_table.c.scope_owner != PLATFORM_SCOPE, worker_table.c.worker_id)
            ).mappings().all()
        return tuple(_entry(row) for row in rows)

    def entry(
        self, context: Any, *, worker_id: str, tenant_id: str
    ) -> Optional[WorkerEntry]:
        """The authoritative read. What closes the TOCTOU window.

        Another tenant's worker answers ``None``, the same answer as one that
        does not exist. Distinguishing them would confirm the worker exists to
        somebody not entitled to know.
        """
        with self._store.reading() as work:
            row = self._row(work, worker_id, tenant_id)
        return _entry(row) if row is not None else None

    def adapter_for(
        self, context: Any, *, worker_id: str, tenant_id: str
    ) -> Optional[Any]:
        """The live adapter, by worker id — never by kind, and only if executable.

        Two independent gates: the durable entry must permit execution, and this
        process must hold the code. Either missing is a refusal; neither is a
        reason to substitute another implementation.
        """
        entry = self.entry(context, worker_id=worker_id, tenant_id=tenant_id)
        if entry is None or not entry.is_executable:
            return None
        return self._adapters.get(self._key(entry.implementation))

    def all_entries(self, context: Any, *, tenant_id: str) -> tuple:
        with self._store.reading() as work:
            rows = work.execute(
                sa.select(worker_table)
                .where(
                    sa.or_(
                        worker_table.c.scope_owner == PLATFORM_SCOPE,
                        worker_table.c.scope_owner == tenant_id,
                    )
                )
                .order_by(worker_table.c.worker_id)
            ).mappings().all()
        return tuple(_entry(row) for row in rows)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _transition(
        self, context: Any, worker_id: str, tenant_id: str, move: Any
    ) -> WorkerEntry:
        """Read, let the **domain** decide the move, write under a digest check.

        The transition legality lives on ``WorkerEntry`` and is not restated
        here; a database that could perform a move the domain forbids would be a
        second lifecycle model. The write is conditioned on the row still saying
        what it said when it was read, so two operators moving one worker
        concurrently cannot both succeed.
        """
        with self._store.atomic() as work:
            row = self._row(work, worker_id, tenant_id)
            if row is None:
                raise UnregisteredWorker(
                    f"worker {worker_id!r} is not registered for this tenant"
                )
            current = _entry(row)
            moved = move(current)
            result = work.execute(
                sa.update(worker_table)
                .where(
                    worker_table.c.scope_owner == row["scope_owner"],
                    worker_table.c.worker_id == worker_id,
                    worker_table.c.lifecycle == current.lifecycle.value,
                    worker_table.c.trust == current.trust.value,
                    worker_table.c.availability == current.availability.value,
                )
                .values(
                    lifecycle=moved.lifecycle.value,
                    trust=moved.trust.value,
                    availability=moved.availability.value,
                    reason=moved.reason,
                    record=_record(moved),
                    updated_at=work.now,
                )
            )
            if result.rowcount != 1:
                raise WorkerAlreadyRegistered(
                    f"worker {worker_id!r} changed while this transition was "
                    "being decided; the move is refused rather than applied to a "
                    "state nobody looked at"
                )
        return moved

    def _row(self, work: UnitOfWork, worker_id: str, tenant_id: str):
        return work.execute(
            sa.select(worker_table).where(
                worker_table.c.worker_id == worker_id,
                sa.or_(
                    worker_table.c.scope_owner == PLATFORM_SCOPE,
                    worker_table.c.scope_owner == tenant_id,
                ),
            )
        ).mappings().first()

    @staticmethod
    def _key(implementation: WorkerImplementation) -> tuple:
        return (implementation.tenant_id or PLATFORM_SCOPE, implementation.worker_id)

    @staticmethod
    def _columns(entry: WorkerEntry, scope_owner: str, registered, updated) -> dict:
        implementation = entry.implementation
        return {
            "scope_owner": scope_owner,
            "worker_id": implementation.worker_id,
            "tenant_id": implementation.tenant_id,
            "scope": implementation.scope.value,
            "worker_kind": implementation.worker_kind.value,
            "interface": implementation.interface.value,
            "implementation": implementation.implementation,
            "implementation_version": implementation.implementation_version,
            # Stored exactly as computed and never recomputed on load. This is
            # the value a selection was recorded against.
            "worker_digest": implementation.digest,
            "lifecycle": entry.lifecycle.value,
            "trust": entry.trust.value,
            "availability": entry.availability.value,
            "record": _record(entry),
            "reason": entry.reason,
            "registered_at": registered,
            "updated_at": updated,
        }

    @staticmethod
    def _assert_context_matches(context: Any, implementation: WorkerImplementation) -> None:
        if implementation.scope is not WorkerScope.TENANT:
            return
        tenant = getattr(context, "tenant_id", None)
        if getattr(context, "is_platform_internal", False):
            return
        if tenant != implementation.tenant_id:
            raise ContractViolation(
                "a tenant worker must be registered by its own tenant; "
                "registering one for somebody else would place an adapter under "
                "an owner who did not choose it"
            )

    @staticmethod
    def _identity(entry: WorkerEntry) -> dict:
        return {
            "worker_id": entry.worker_id,
            "worker_kind": entry.worker_kind.value,
            "worker_version": entry.worker_version,
            "worker_digest": entry.worker_digest,
        }

    @staticmethod
    def _metadata(context: Any, entry: WorkerEntry) -> EventMetadata:
        return EventMetadata.create(
            aggregate_id=entry.worker_id,
            aggregate_type=WORKER_AGGREGATE_TYPE,
            scope=getattr(context, "scope", None),
            correlation_id=getattr(getattr(context, "correlation", None), "correlation_id", None),
        )

    def _scope(self, unit: Optional[UnitOfWork]):
        return enlisted(self._store, unit)


# ----------------------------------------------------------------------
# Record mapping
# ----------------------------------------------------------------------


def _record(entry: WorkerEntry) -> dict:
    """The whole entry as primitives. Digest stored, never recomputed on load."""
    implementation = entry.implementation
    return {
        "worker_id": implementation.worker_id,
        "worker_kind": implementation.worker_kind.value,
        "interface": implementation.interface.value,
        "implementation": implementation.implementation,
        "implementation_version": implementation.implementation_version,
        "protocol_version": implementation.protocol_version,
        "isolation": implementation.isolation.value,
        "scope": implementation.scope.value,
        "tenant_id": implementation.tenant_id,
        "supported_environments": sorted(
            e.value for e in implementation.supported_environments
        ),
        "supported_effects": sorted(e.value for e in implementation.supported_effects),
        "supported_providers": sorted(implementation.supported_providers),
        "supported_capability_refs": sorted(implementation.supported_capability_refs),
        "supported_operations": sorted(implementation.supported_operations),
        "pinned_capability_digests": sorted(implementation.pinned_capability_digests),
        "cancellation": implementation.cancellation.value,
        "supports_provider_idempotency": implementation.supports_provider_idempotency,
        "lifecycle": entry.lifecycle.value,
        "trust": entry.trust.value,
        "availability": entry.availability.value,
        "reason": entry.reason,
        "registered_at": entry.registered_at.isoformat(),
        "updated_at": entry.updated_at.isoformat(),
        "digest": implementation.digest,
    }


def _entry(row: Any) -> WorkerEntry:
    """Rebuild a ``WorkerEntry``, then check the digest survived the round trip.

    Recomputing the implementation digest and comparing it against the stored one
    is the check that a row edited outside the application is detected rather
    than silently loaded. It is the same argument the execution and capability
    records make: a digest that is recomputed on load can never disagree, and a
    check that cannot fail is not one.
    """
    data = row["record"]
    implementation = WorkerImplementation(
        worker_id=data["worker_id"],
        worker_kind=WorkerKind(data["worker_kind"]),
        interface=WorkerInterface(data["interface"]),
        implementation=data["implementation"],
        implementation_version=data["implementation_version"],
        isolation=IsolationTier(data["isolation"]),
        scope=WorkerScope(data["scope"]),
        tenant_id=data.get("tenant_id"),
        protocol_version=data["protocol_version"],
        supported_environments=frozenset(
            ExecutionEnvironment(e) for e in data["supported_environments"]
        ),
        supported_effects=frozenset(
            EffectSemantics(e) for e in data["supported_effects"]
        ),
        supported_providers=frozenset(data["supported_providers"]),
        supported_capability_refs=frozenset(data.get("supported_capability_refs", ())),
        supported_operations=frozenset(data.get("supported_operations", ())),
        pinned_capability_digests=frozenset(data.get("pinned_capability_digests", ())),
        cancellation=CancellationSupport(data["cancellation"]),
        supports_provider_idempotency=data["supports_provider_idempotency"],
    )
    stored_digest = data.get("digest") or row["worker_digest"]
    if implementation.digest != stored_digest:
        raise ContractViolation(
            f"worker {implementation.worker_id!r} does not digest to the value it "
            "was registered with; the stored registration has been changed "
            "outside the application and is refused rather than loaded"
        )
    return WorkerEntry(
        implementation=implementation,
        lifecycle=WorkerLifecycle(data["lifecycle"]),
        trust=WorkerTrust(data["trust"]),
        availability=WorkerAvailability(data["availability"]),
        registered_at=_time(data["registered_at"]),
        updated_at=_time(data["updated_at"]),
        reason=data.get("reason"),
    )


def _time(value: Any) -> datetime:
    moment = datetime.fromisoformat(value) if isinstance(value, str) else value
    return moment if moment.tzinfo is not None else moment.replace(tzinfo=timezone.utc)
