"""Intent persistence.

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
from backend.contexts.intent.domain.errors import DuplicateIntent, IntentNotFound
from backend.contexts.intent.domain.identifiers import IntentId
from backend.contexts.intent.domain.intent import Intent
from backend.contexts.intent.infrastructure.persistence import from_record, to_record
from backend.platform.storage import RepositoryGuard

__all__ = ["IntentRepository", "InMemoryIntentRepository", "INTENT_BINDING"]


INTENT_BINDING = StorageBinding(
    record_type="Intent",
    scope_column="tenant_id",
    platform_internal_allowed=True,
)


@runtime_checkable
class IntentRepository(Protocol):
    """The persistence surface the application layer depends on."""

    def save(self, context: Any, intent: Intent) -> None: ...

    def replace(self, context: Any, intent: Intent) -> None: ...

    def find(self, context: Any, intent_id: IntentId) -> Optional[Intent]: ...

    def all(self, context: Any) -> Sequence[Intent]: ...


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


class InMemoryIntentRepository:
    """In-process storage, guarded exactly as a durable one would be."""

    def __init__(self) -> None:
        self._guard = RepositoryGuard(INTENT_BINDING)
        self._intents: dict = {}
        self._lock = threading.RLock()

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def save(self, context: Any, intent: Intent) -> None:
        """Store a new intent. Refuses to overwrite one that exists."""
        access = self._guard.authorize(StorageOperation.WRITE, context)
        stored = to_record(intent, tenant_id=access.tenant_id)
        self._guard.assert_in_scope(_Row(stored), access)

        key = str(intent.intent_id)
        with self._lock:
            if key in self._intents:
                raise DuplicateIntent(key)
            self._intents[key] = stored

    def replace(self, context: Any, intent: Intent) -> None:
        """Overwrite an existing intent in place.

        Named for what it does. A draft legitimately rewrites as it is expanded;
        collapsing this into an upsert would make an accidental overwrite
        indistinguishable from an intended one.
        """
        access = self._guard.authorize(StorageOperation.WRITE, context)
        stored = to_record(intent, tenant_id=access.tenant_id)

        key = str(intent.intent_id)
        with self._lock:
            if key not in self._intents:
                raise IntentNotFound(key)
            self._guard.assert_in_scope(_Row(self._intents[key]), access)
            self._intents[key] = stored

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def _visible(self, access) -> list:
        scope = self._guard.scope_filter(access)
        with self._lock:
            intents = list(self._intents.values())
        if scope is None:
            return intents
        column, value = scope
        return [i for i in intents if i.get(column) == value]

    def find(self, context: Any, intent_id: IntentId) -> Optional[Intent]:
        access = self._guard.authorize(StorageOperation.READ, context)
        for stored in self._visible(access):
            if stored["intent_id"] == str(intent_id):
                self._guard.assert_in_scope(_Row(stored), access)
                return from_record(stored)
        return None

    def all(self, context: Any) -> Sequence[Intent]:
        access = self._guard.authorize(StorageOperation.READ, context)
        return tuple(
            from_record(i)
            for i in sorted(self._visible(access), key=lambda i: i["intent_id"])
        )

    # ------------------------------------------------------------------
    # Maintenance
    # ------------------------------------------------------------------

    def clear(self, context: Any) -> int:
        """Remove every intent visible to ``context``. Returns the count."""
        access = self._guard.authorize(StorageOperation.DELETE, context)
        scope = self._guard.scope_filter(access)
        with self._lock:
            if scope is None:
                removed = len(self._intents)
                self._intents.clear()
                return removed
            column, value = scope
            doomed = [k for k, i in self._intents.items() if i.get(column) == value]
            for key in doomed:
                del self._intents[key]
            return len(doomed)

    def __len__(self) -> int:
        with self._lock:
            return len(self._intents)
