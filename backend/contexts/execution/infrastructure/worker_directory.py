"""The worker directory: which implementations exist, and what is true of them.

Not a capability registry
---------------------------
This holds *mechanisms*. It has no capability definitions, no discovery, no
authorization and no resolution, and nothing here is consulted about whether an
ability exists or whether a principal may use it. Those live in BC-8, which this
module may not import and does not need to.

Registration is not enablement, and never becomes it
------------------------------------------------------
``register`` records an implementation as ``REGISTERED`` / ``UNVERIFIED`` /
``UNAVAILABLE``. Three further deliberate acts stand between that and it being
handed real work, and there is no argument to ``register`` that skips them. A
convenience flag would be the whole security property, optional.

Tenancy, stated rather than inferred
--------------------------------------
Platform workers are visible to every tenant; tenant workers to exactly one. A
tenant may not register a worker under an id a platform worker already holds --
shadowing would let a tenant redirect platform work into an adapter it controls,
which is a privilege escalation that looks like a naming collision.

Cross-tenant reads fail closed: asking for another tenant's worker returns
``None``, the same answer as asking for one that does not exist. Distinguishing
them would confirm the worker exists to somebody not entitled to know.

Concurrency
-------------
In-memory and guarded by a lock. Every mutation replaces an immutable entry, so
a reader that already holds one cannot have it changed underneath, and the
entry a selection was made from is comparable by digest against the entry the
TOCTOU re-read returns.
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from backend.contracts.errors import ContractViolation
from backend.contexts.execution.domain.worker import WorkerKind
from backend.contexts.execution.domain.worker_directory import (
    WorkerAvailability,
    WorkerEntry,
    WorkerImplementation,
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
from backend.platform.events import EventMetadata

__all__ = ["InMemoryWorkerDirectory", "WorkerAlreadyRegistered", "UnregisteredWorker"]


class WorkerAlreadyRegistered(ContractViolation):
    """That worker id is taken, and replacing it silently is not on offer."""


class UnregisteredWorker(ContractViolation):
    """No such worker in this directory, for this tenant."""


def _key(implementation: WorkerImplementation) -> Tuple[str, str]:
    """Identity within the directory: scope owner, then id.

    Platform entries live under ``""``. A tenant cannot reach the platform slot
    and cannot occupy it, which is what makes shadowing impossible rather than
    merely discouraged.
    """
    return (implementation.tenant_id or "", implementation.worker_id)


class InMemoryWorkerDirectory:
    """The authoritative record of registered worker implementations.

    Satisfies Execution's ``WorkerDirectory`` port. Holds the adapters too --
    kept together because an entry that is enabled with nothing wired behind it,
    and an adapter wired with nothing governing it, are both states worth being
    unable to reach.

    Every lifecycle method returns ``(entry, event)``. The event is returned
    rather than published: this is a store, publishing is the composition root's,
    and a store that published would decide when a fact became visible.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._entries: Dict[Tuple[str, str], WorkerEntry] = {}
        self._adapters: Dict[Tuple[str, str], Any] = {}

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
    ) -> Tuple[WorkerEntry, WorkerRegistered]:
        """Record an implementation. It is not usable when this returns.

        The adapter is required: a governed entry with nothing behind it would be
        selectable and then unrunnable, burning an attempt to discover it.
        """
        if not isinstance(implementation, WorkerImplementation):
            raise ContractViolation("implementation must be a WorkerImplementation")
        if adapter is None:
            raise ContractViolation(
                f"worker {implementation.worker_id!r} was registered with no adapter; "
                "an entry nothing implements is selectable and then unrunnable"
            )
        self._assert_context_matches(context, implementation)

        moment = now or datetime.now(timezone.utc)
        key = _key(implementation)
        with self._lock:
            if key in self._entries:
                raise WorkerAlreadyRegistered(
                    f"worker {implementation.worker_id!r} is already registered; "
                    "silently replacing an implementation would change what runs "
                    "without anybody deciding, and the digest would not say so"
                )
            if implementation.scope is WorkerScope.TENANT and (
                "",
                implementation.worker_id,
            ) in self._entries:
                raise WorkerAlreadyRegistered(
                    f"a platform worker already holds the id "
                    f"{implementation.worker_id!r}; a tenant registration under it "
                    "would shadow platform work into a tenant-controlled adapter"
                )

            entry = WorkerEntry(
                implementation=implementation,
                lifecycle=WorkerLifecycle.REGISTERED,
                trust=WorkerTrust.UNVERIFIED,
                availability=WorkerAvailability.UNAVAILABLE,
                registered_at=moment,
                updated_at=moment,
            )
            self._entries[key] = entry
            self._adapters[key] = adapter

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

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def validate(
        self, context: Any, *, worker_id: str, tenant_id: str, note: str = ""
    ) -> Tuple[WorkerEntry, WorkerValidated]:
        entry = self._require(context, worker_id, tenant_id)
        moved = self._replace(entry, entry.validated())
        return moved, WorkerValidated(
            metadata=self._metadata(context, moved), **self._identity(moved), note=note
        )

    def enable(
        self, context: Any, *, worker_id: str, tenant_id: str
    ) -> Tuple[WorkerEntry, WorkerEnabled]:
        """Make it eligible for selection. Trust and availability still vote."""
        entry = self._require(context, worker_id, tenant_id)
        moved = self._replace(entry, entry.enabled())
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
        entry = self._require(context, worker_id, tenant_id)
        moved = self._replace(entry, entry.disabled(reason))
        return moved, WorkerDisabled(
            metadata=self._metadata(context, moved),
            **self._identity(moved),
            reason=reason,
        )

    def revoke(
        self, context: Any, *, worker_id: str, tenant_id: str, reason: str
    ) -> Tuple[WorkerEntry, WorkerRevoked]:
        """Withdraw permanently. The entry stays; the adapter goes.

        The record remains because deleting it would erase the evidence that this
        implementation existed and was withdrawn. The adapter is dropped so a
        revoked worker is unreachable even if some future lookup forgets to check
        the lifecycle.
        """
        entry = self._require(context, worker_id, tenant_id)
        moved = self._replace(entry, entry.revoked(reason))
        with self._lock:
            self._adapters.pop(_key(moved.implementation), None)
        return moved, WorkerRevoked(
            metadata=self._metadata(context, moved),
            **self._identity(moved),
            reason=reason,
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
        entry = self._require(context, worker_id, tenant_id)
        previous = entry.trust
        moved = self._replace(entry, entry.with_trust(trust, reason))
        return moved, WorkerTrustChanged(
            metadata=self._metadata(context, moved),
            **self._identity(moved),
            previous_trust=previous.value,
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
        """Record reachability. No event: an observation is not a decision.

        Availability changes as often as the network does. Emitting a domain
        event for each would bury the ones that record somebody deciding
        something in a stream of things merely happening.
        """
        entry = self._require(context, worker_id, tenant_id)
        return self._replace(entry, entry.with_availability(availability))

    # ------------------------------------------------------------------
    # The port Execution reads
    # ------------------------------------------------------------------

    def candidates(
        self, context: Any, *, worker_kind: WorkerKind, tenant_id: str
    ) -> tuple:
        """Every entry of that kind this tenant may be offered. Unranked.

        Returned in a stable order (platform before tenant, then by id) so a
        refusal lists candidates the same way twice -- an ordering for *reading*,
        never a preference. Selection refuses two eligible workers rather than
        taking the first.
        """
        with self._lock:
            entries = list(self._entries.values())
        return tuple(
            sorted(
                (
                    entry
                    for entry in entries
                    if entry.worker_kind is worker_kind
                    and entry.implementation.visible_to(tenant_id)
                ),
                key=lambda e: (e.implementation.scope is WorkerScope.TENANT, e.worker_id),
            )
        )

    def entry(
        self, context: Any, *, worker_id: str, tenant_id: str
    ) -> Optional[WorkerEntry]:
        """The authoritative read. What closes the TOCTOU window.

        Checked for visibility as well as existence: a worker belonging to
        another tenant answers ``None``, exactly as a nonexistent one does.
        """
        with self._lock:
            found = self._entries.get((tenant_id, worker_id)) or self._entries.get(
                ("", worker_id)
            )
        if found is None or not found.implementation.visible_to(tenant_id):
            return None
        return found

    def adapter_for(
        self, context: Any, *, worker_id: str, tenant_id: str
    ) -> Optional[Any]:
        """The live adapter, by worker id -- never by kind.

        Only for a worker that is currently executable. The gate checks this too;
        checking here as well means a caller that reached past the gate still
        cannot obtain a disabled worker's adapter.
        """
        found = self.entry(context, worker_id=worker_id, tenant_id=tenant_id)
        if found is None or not found.is_executable:
            return None
        with self._lock:
            return self._adapters.get(_key(found.implementation))

    # ------------------------------------------------------------------
    # Inspection
    # ------------------------------------------------------------------

    def all_entries(self, context: Any, *, tenant_id: str) -> tuple:
        with self._lock:
            entries = list(self._entries.values())
        return tuple(
            sorted(
                (e for e in entries if e.implementation.visible_to(tenant_id)),
                key=lambda e: e.worker_id,
            )
        )

    def __len__(self) -> int:
        with self._lock:
            return len(self._entries)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _require(self, context: Any, worker_id: str, tenant_id: str) -> WorkerEntry:
        found = self.entry(context, worker_id=worker_id, tenant_id=tenant_id)
        if found is None:
            raise UnregisteredWorker(
                f"no worker {worker_id!r} is registered for tenant {tenant_id!r}"
            )
        self._assert_context_tenant(context, tenant_id)
        if (
            found.implementation.scope is WorkerScope.PLATFORM
            and self._context_tenant(context) is not None
            and not self._is_platform_context(context)
        ):
            # Visible to a tenant, governed by the platform. A tenant that could
            # disable a platform worker could stop everybody else's work.
            raise ContractViolation(
                f"worker {worker_id!r} is platform-scoped; a tenant may see it and "
                "may not govern it"
            )
        return found

    def _replace(self, previous: WorkerEntry, moved: WorkerEntry) -> WorkerEntry:
        key = _key(moved.implementation)
        with self._lock:
            current = self._entries.get(key)
            if current is not None and current.worker_digest != previous.worker_digest:
                raise ContractViolation(
                    f"worker {moved.worker_id!r} changed implementation while it was "
                    "being governed; the move would have been applied to a different "
                    "build than the one it was decided against"
                )
            self._entries[key] = moved
        return moved

    @staticmethod
    def _identity(entry: WorkerEntry) -> dict:
        return {
            "worker_id": entry.worker_id,
            "worker_kind": entry.worker_kind.value,
            "worker_version": entry.worker_version,
            "worker_digest": entry.worker_digest,
            "scope": entry.implementation.scope.value,
        }

    @staticmethod
    def _context_tenant(context: Any) -> Optional[str]:
        return getattr(context, "tenant_id", None)

    @staticmethod
    def _is_platform_context(context: Any) -> bool:
        return bool(getattr(context, "is_platform_internal", False))

    def _assert_context_tenant(self, context: Any, tenant_id: str) -> None:
        """The caller's context must be the tenant it claims to act for.

        No ambient tenant, no default, and no ``TenantRef("system")``. A caller
        that could name a tenant its context does not carry could govern anybody's
        workers by passing a different string.
        """
        actual = self._context_tenant(context)
        if actual is None:
            raise ContractViolation(
                "worker governance requires an ExecutionContext carrying a tenant; "
                "there is no ambient tenant and no default"
            )
        if actual != tenant_id and not self._is_platform_context(context):
            raise ContractViolation(
                f"the context is for tenant {actual!r} but the operation names "
                f"{tenant_id!r}; one of them is somebody else's"
            )

    def _assert_context_matches(
        self, context: Any, implementation: WorkerImplementation
    ) -> None:
        actual = self._context_tenant(context)
        if actual is None:
            raise ContractViolation(
                "worker registration requires an ExecutionContext carrying a tenant"
            )
        if implementation.scope is WorkerScope.PLATFORM:
            if not self._is_platform_context(context):
                raise ContractViolation(
                    "a platform-scoped worker may only be registered from a "
                    "platform-internal context; a tenant registering one would be "
                    "registering an implementation for everybody"
                )
            return
        if implementation.tenant_id != actual and not self._is_platform_context(context):
            raise ContractViolation(
                f"the context is for tenant {actual!r} but the worker names "
                f"{implementation.tenant_id!r}"
            )

    @staticmethod
    def _metadata(context: Any, entry: WorkerEntry) -> EventMetadata:
        return EventMetadata.create(
            aggregate_id=entry.worker_id,
            aggregate_type=WORKER_AGGREGATE_TYPE,
            scope=context.scope,
            actor=getattr(getattr(context, "identity", None), "principal", None),
        )
