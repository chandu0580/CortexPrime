"""Verification persistence.

Every method takes an ``ExecutionContext`` first and derives tenancy from it.
``TENANT-REPOSITORY-CONTEXT`` blocks the merge for any repository method without
one, and this repository is not on the grandfathered list -- that list may only
shrink.

Tenancy runs through the platform's storage guard rather than by hand, so this
repository gets the same refusals every other guarded store does: no operation
without a context, no cross-tenant read, no caller-supplied tenant.

In-memory only. ``STATE-NO-NEW-FILE-STORES`` forbids a new JSON-backed store, and
a durable one belongs with the schema work. The Protocol is the seam.
"""

from __future__ import annotations

import threading
from typing import Any, Mapping, Optional, Protocol, Sequence, runtime_checkable

from backend.contracts.storage import StorageBinding, StorageOperation
from backend.contexts.engineering_verification.domain.errors import DuplicateVerification
from backend.contexts.engineering_verification.domain.identifiers import VerificationId
from backend.contexts.engineering_verification.domain.record import VerificationRecord
from backend.contexts.engineering_verification.infrastructure.persistence import (
    from_record,
    to_record,
)
from backend.platform.storage import RepositoryGuard

__all__ = [
    "VerificationRepository",
    "InMemoryVerificationRepository",
    "VERIFICATION_BINDING",
]


#: Engineering work belongs to the platform building CortexPrime, not to a
#: customer tenant, so platform-internal reads are permitted. The guard still
#: refuses to write a record with no tenant recorded.
VERIFICATION_BINDING = StorageBinding(
    record_type="VerificationRecord",
    scope_column="tenant_id",
    platform_internal_allowed=True,
)


@runtime_checkable
class VerificationRepository(Protocol):
    """The persistence surface the application layer depends on."""

    def save(self, context: Any, record: VerificationRecord) -> None: ...

    def replace(self, context: Any, record: VerificationRecord) -> None: ...

    def find(
        self, context: Any, verification_id: VerificationId
    ) -> Optional[VerificationRecord]: ...

    def for_work_order(self, context: Any, work_id: str) -> Sequence[VerificationRecord]: ...

    def all(self, context: Any) -> Sequence[VerificationRecord]: ...


class _Row:
    """Adapts a record mapping to the attribute access the guard expects.

    The guard reads ``record.<scope_column>`` because it was written against ORM
    rows. Wrapping keeps that boundary honest -- the guard should not learn about
    mappings to accommodate one caller.
    """

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


class InMemoryVerificationRepository:
    """In-process storage, guarded exactly as a durable one would be.

    Thread-safe: verifications run concurrently, and a dictionary mutated from
    two threads loses writes silently rather than raising.
    """

    def __init__(self) -> None:
        self._guard = RepositoryGuard(VERIFICATION_BINDING)
        self._records: dict = {}
        self._lock = threading.RLock()

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def save(self, context: Any, record: VerificationRecord) -> None:
        """Store a new record. Refuses to overwrite an existing one."""
        access = self._guard.authorize(StorageOperation.WRITE, context)
        stored = to_record(record, tenant_id=access.tenant_id)
        self._guard.assert_in_scope(_Row(stored), access)

        key = str(record.verification_id)
        with self._lock:
            if key in self._records:
                raise DuplicateVerification(work_id=record.work_id, attempt=record.attempt)
            self._records[key] = stored

    def replace(self, context: Any, record: VerificationRecord) -> None:
        """Overwrite an existing record in place.

        Named for what it does rather than folded into an upsert, so an
        accidental overwrite is distinguishable from an intended one.
        """
        access = self._guard.authorize(StorageOperation.WRITE, context)
        stored = to_record(record, tenant_id=access.tenant_id)

        key = str(record.verification_id)
        with self._lock:
            if key not in self._records:
                from backend.contexts.engineering_verification.domain.errors import (
                    VerificationNotFound,
                )

                raise VerificationNotFound(key)
            existing = self._records[key]
            self._guard.assert_in_scope(_Row(existing), access)
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

    def find(
        self, context: Any, verification_id: VerificationId
    ) -> Optional[VerificationRecord]:
        access = self._guard.authorize(StorageOperation.READ, context)
        for stored in self._visible(access):
            if stored["verification_id"] == str(verification_id):
                self._guard.assert_in_scope(_Row(stored), access)
                return from_record(stored)
        return None

    def for_work_order(self, context: Any, work_id: str) -> Sequence[VerificationRecord]:
        access = self._guard.authorize(StorageOperation.READ, context)
        matching = [r for r in self._visible(access) if r["work_id"] == work_id]
        return tuple(
            from_record(r)
            for r in sorted(matching, key=lambda r: (r["attempt"], r["verification_id"]))
        )

    def all(self, context: Any) -> Sequence[VerificationRecord]:
        access = self._guard.authorize(StorageOperation.READ, context)
        return tuple(
            from_record(r)
            for r in sorted(self._visible(access), key=lambda r: r["verification_id"])
        )

    # ------------------------------------------------------------------
    # Maintenance
    # ------------------------------------------------------------------

    def clear(self, context: Any) -> int:
        """Remove every record visible to ``context``. Returns the count.

        Takes a context like everything else: it is the most destructive
        operation here, and a clear that ignored tenancy would be a cross-tenant
        delete wearing a maintenance method's name.
        """
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
