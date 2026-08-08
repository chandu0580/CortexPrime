"""ContextBundle persistence.

Every method takes an ``ExecutionContext`` first and derives tenancy from it.
``TENANT-REPOSITORY-CONTEXT`` blocks the merge for any repository method without
one, and this repository is not on the grandfathered list -- that list may only
shrink.

In-memory only. ``STATE-NO-NEW-FILE-STORES`` forbids a new JSON-backed store; the
Protocol is the seam for a durable one.
"""

from __future__ import annotations

import threading
from typing import Any, Mapping, Optional, Protocol, Sequence, runtime_checkable

from backend.contracts.storage import StorageBinding, StorageOperation
from backend.contexts.context_bundle.domain.bundle import ContextBundle
from backend.contexts.context_bundle.domain.errors import BundleNotFound, DuplicateBundle
from backend.contexts.context_bundle.domain.identifiers import BundleId
from backend.contexts.context_bundle.infrastructure.persistence import from_record, to_record
from backend.platform.storage import RepositoryGuard

__all__ = ["ContextRepository", "InMemoryContextRepository", "CONTEXT_BUNDLE_BINDING"]


CONTEXT_BUNDLE_BINDING = StorageBinding(
    record_type="ContextBundle",
    scope_column="tenant_id",
    platform_internal_allowed=True,
)


@runtime_checkable
class ContextRepository(Protocol):
    """The persistence surface the application layer depends on."""

    def save(self, context: Any, bundle: ContextBundle) -> None: ...

    def replace(self, context: Any, bundle: ContextBundle) -> None: ...

    def find(self, context: Any, bundle_id: BundleId) -> Optional[ContextBundle]: ...

    def for_work_order(self, context: Any, work_id: str) -> Sequence[ContextBundle]: ...

    def all(self, context: Any) -> Sequence[ContextBundle]: ...


class _Row:
    """Adapts a record mapping to the attribute access the guard expects."""

    __slots__ = ("_data",)

    def __init__(self, data: Mapping[str, Any]) -> None:
        object.__setattr__(self, "_data", dict(data))

    def __getattr__(self, name: str) -> Any:
        try:
            return self._data[name]
        except KeyError as exc:  # pragma: no cover - defensive
            raise AttributeError(name) from exc

    def __setattr__(self, name: str, value: Any) -> None:
        self._data[name] = value


class InMemoryContextRepository:
    """In-process storage, guarded exactly as a durable one would be.

    Thread-safe: bundles are assembled and expanded concurrently, and a
    dictionary mutated from two threads loses writes silently.
    """

    def __init__(self) -> None:
        self._guard = RepositoryGuard(CONTEXT_BUNDLE_BINDING)
        self._records: dict = {}
        self._lock = threading.RLock()

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def save(self, context: Any, bundle: ContextBundle) -> None:
        """Store a new bundle version. Refuses to overwrite one that exists.

        A bundle version is immutable: its manifest digest is what makes "this is
        what the agent saw" checkable. Overwriting would let the contents behind
        a digest change with no record.
        """
        access = self._guard.authorize(StorageOperation.WRITE, context)
        stored = to_record(bundle, tenant_id=access.tenant_id)
        self._guard.assert_in_scope(_Row(stored), access)

        key = str(bundle.bundle_id)
        with self._lock:
            if key in self._records:
                raise DuplicateBundle(work_id=bundle.work_id, version=bundle.version)
            self._records[key] = stored

    def replace(self, context: Any, bundle: ContextBundle) -> None:
        """Overwrite an existing record in place.

        Named for what it does. Status changes -- superseded, invalidated -- do
        rewrite a version, and collapsing this into an upsert would make an
        accidental overwrite indistinguishable from an intended one.
        """
        access = self._guard.authorize(StorageOperation.WRITE, context)
        stored = to_record(bundle, tenant_id=access.tenant_id)

        key = str(bundle.bundle_id)
        with self._lock:
            if key not in self._records:
                raise BundleNotFound(key)
            self._guard.assert_in_scope(_Row(self._records[key]), access)
            self._records[key] = stored

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def _visible(self, access) -> list:
        scope = self._guard.scope_filter(access)
        with self._lock:
            records = list(self._records.values())
        if scope is None:
            return records
        column, value = scope
        return [r for r in records if r.get(column) == value]

    def find(self, context: Any, bundle_id: BundleId) -> Optional[ContextBundle]:
        access = self._guard.authorize(StorageOperation.READ, context)
        for stored in self._visible(access):
            if stored["bundle_id"] == str(bundle_id):
                self._guard.assert_in_scope(_Row(stored), access)
                return from_record(stored)
        return None

    def for_work_order(self, context: Any, work_id: str) -> Sequence[ContextBundle]:
        access = self._guard.authorize(StorageOperation.READ, context)
        matching = [r for r in self._visible(access) if r["work_id"] == work_id]
        return tuple(
            from_record(r) for r in sorted(matching, key=lambda r: (r["version"], r["bundle_id"]))
        )

    def all(self, context: Any) -> Sequence[ContextBundle]:
        access = self._guard.authorize(StorageOperation.READ, context)
        return tuple(
            from_record(r) for r in sorted(self._visible(access), key=lambda r: r["bundle_id"])
        )

    # ------------------------------------------------------------------
    # Maintenance
    # ------------------------------------------------------------------

    def clear(self, context: Any) -> int:
        """Remove every bundle visible to ``context``. Returns the count."""
        access = self._guard.authorize(StorageOperation.DELETE, context)
        scope = self._guard.scope_filter(access)
        with self._lock:
            if scope is None:
                removed = len(self._records)
                self._records.clear()
                return removed
            column, value = scope
            doomed = [k for k, r in self._records.items() if r.get(column) == value]
            for key in doomed:
                del self._records[key]
            return len(doomed)

    def __len__(self) -> int:
        with self._lock:
            return len(self._records)
