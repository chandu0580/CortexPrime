"""Capability persistence.

Every method takes an ``ExecutionContext`` first and derives tenancy from it.
``TENANT-REPOSITORY-CONTEXT`` blocks the merge for any repository method without
one, and this repository is not on the grandfathered list -- that list may only
shrink.

In-memory only. ``STATE-NO-NEW-FILE-STORES`` forbids a JSON-backed registry, and
this Protocol is the seam for a durable one. **Nothing here is durable**: a
restart loses every registration.

No generic mutation
---------------------
There is no ``update``, no ``set_status``, and no ``save(anything)``. The only
write that creates is ``register``, and the only write that changes is
``replace``, which takes a whole definition the domain already moved. A
repository with a generic setter is a repository through which the lifecycle can
be bypassed, and the lifecycle is the security model.

Tenant visibility is enforced here rather than trusted to callers: a
tenant-scoped capability is invisible to another tenant even if it asks for it
by exact reference.
"""

from __future__ import annotations

import threading
from typing import Any, Mapping, Optional, Protocol, Sequence, runtime_checkable

from backend.contracts.storage import StorageBinding, StorageOperation
from backend.contexts.connectivity.domain.definition import CapabilityDefinition
from backend.contexts.connectivity.domain.errors import (
    CapabilityNotFound,
    CapabilityVersionNotFound,
    ConflictingRegistration,
)
from backend.contexts.connectivity.domain.identifiers import CapabilityId, CapabilityRef
from backend.contexts.connectivity.infrastructure.persistence import (
    from_record,
    to_record,
)
from backend.platform.storage import RepositoryGuard

__all__ = [
    "CapabilityRepository",
    "InMemoryCapabilityRepository",
    "CAPABILITY_BINDING",
]


CAPABILITY_BINDING = StorageBinding(
    record_type="CapabilityDefinition",
    scope_column="tenant_id",
    # Platform capabilities have no tenant by design -- that is what
    # CapabilityTenancy.PLATFORM means -- so platform-internal access is part of
    # the model rather than an exemption from it.
    platform_internal_allowed=True,
)


@runtime_checkable
class CapabilityRepository(Protocol):
    """The persistence surface the application layer depends on."""

    def register(self, context: Any, definition: CapabilityDefinition) -> None: ...

    def replace(self, context: Any, definition: CapabilityDefinition) -> None: ...

    def find(self, context: Any, reference: CapabilityRef) -> Optional[CapabilityDefinition]: ...

    def versions_of(self, context: Any, capability_id: CapabilityId) -> Sequence[CapabilityDefinition]: ...

    def all(self, context: Any) -> Sequence[CapabilityDefinition]: ...

    def exists(self, context: Any, reference: CapabilityRef) -> bool: ...


class _Row:
    """Adapts a record mapping to the attribute access the guard expects."""

    __slots__ = ("_data",)

    def __init__(self, data: Mapping[str, Any]) -> None:
        self._data = data

    def __getattr__(self, name: str) -> Any:
        try:
            return self._data[name]
        except KeyError as exc:  # pragma: no cover - defensive
            raise AttributeError(name) from exc


class InMemoryCapabilityRepository:
    """In-process, tenant-aware, and **not durable**.

    Thread-safe because registration can arrive from several places at once, and
    the duplicate-contract check plus the write must be one atomic step: doing
    them separately is how two processes both decide they are the first
    registrant and the second silently wins.
    """

    def __init__(self) -> None:
        self._records: dict = {}
        self._guard = RepositoryGuard(CAPABILITY_BINDING)
        self._lock = threading.RLock()

    # -- helpers -------------------------------------------------------

    @staticmethod
    def _tenant_of(context: Any) -> Optional[str]:
        return getattr(context, "tenant_id", None)

    def _visible(self, context: Any, definition: CapabilityDefinition) -> bool:
        tenant = self._tenant_of(context)
        if getattr(context, "is_platform_internal", False):
            return True
        return definition.visible_to(tenant)

    # -- writes --------------------------------------------------------

    def register(self, context: Any, definition: CapabilityDefinition) -> None:
        """Record a new version.

        Refuses a different contract for a version already registered. The
        comparison and the write happen under one lock: checking first and
        writing after is the race that lets a second registrant redefine a
        version something has already been approved against.
        """
        record = to_record(definition, tenant_id=self._tenant_of(context))
        access = self._guard.authorize(StorageOperation.WRITE, context)
        self._guard.assert_in_scope(_Row(record), access)
        key = definition.reference.value
        with self._lock:
            existing = self._records.get(key)
            if existing is not None:
                registered = from_record(existing)
                if registered.digest != definition.digest:
                    raise ConflictingRegistration(
                        capability_ref=key,
                        registered_digest=registered.digest or "",
                        offered_digest=definition.digest or "",
                    )
                # Same identity, same version, same digest: an idempotent
                # re-registration. The stored definition wins, because it may
                # have been validated or trusted since, and overwriting would
                # silently undo those decisions.
                return
            self._records[key] = record

    def replace(self, context: Any, definition: CapabilityDefinition) -> None:
        """Store a definition the domain has already moved."""
        record = to_record(definition, tenant_id=self._tenant_of(context))
        access = self._guard.authorize(StorageOperation.WRITE, context)
        self._guard.assert_in_scope(_Row(record), access)
        key = definition.reference.value
        with self._lock:
            if key not in self._records:
                raise CapabilityVersionNotFound(
                    definition.capability_id.value, definition.version.number
                )
            self._records[key] = record

    # -- reads ---------------------------------------------------------

    def find(self, context: Any, reference: CapabilityRef) -> Optional[CapabilityDefinition]:
        self._guard.authorize(StorageOperation.READ, context)
        with self._lock:
            record = self._records.get(reference.value)
        if record is None:
            return None
        definition = from_record(record)
        # Invisible is indistinguishable from absent. Returning a "forbidden"
        # would confirm that another tenant's capability exists.
        return definition if self._visible(context, definition) else None

    def require(self, context: Any, reference: CapabilityRef) -> CapabilityDefinition:
        found = self.find(context, reference)
        if found is None:
            known = [d.version.number for d in self.versions_of(context, reference.capability_id)]
            if not known:
                raise CapabilityNotFound(reference.capability_id.value)
            raise CapabilityVersionNotFound(
                reference.capability_id.value, reference.version.number, known
            )
        return found

    def versions_of(self, context: Any, capability_id: CapabilityId) -> Sequence[CapabilityDefinition]:
        self._guard.authorize(StorageOperation.READ, context)
        with self._lock:
            records = list(self._records.values())
        found = [
            definition
            for definition in (from_record(r) for r in records)
            if definition.capability_id == capability_id
            and self._visible(context, definition)
        ]
        return tuple(sorted(found, key=lambda d: d.version.number))

    def all(self, context: Any) -> Sequence[CapabilityDefinition]:
        self._guard.authorize(StorageOperation.READ, context)
        with self._lock:
            records = list(self._records.values())
        found = [
            definition
            for definition in (from_record(r) for r in records)
            if self._visible(context, definition)
        ]
        return tuple(sorted(found, key=lambda d: (d.capability_id.value, d.version.number)))

    def exists(self, context: Any, reference: CapabilityRef) -> bool:
        return self.find(context, reference) is not None

    def clear(self, context: Any) -> int:
        with self._lock:
            removed = len(self._records)
            self._records.clear()
            return removed

    def __len__(self) -> int:
        with self._lock:
            return len(self._records)
