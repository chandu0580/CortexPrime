"""Execution persistence.

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
from backend.contexts.execution.domain.errors import DuplicateExecution, ExecutionNotFound
from backend.contexts.execution.domain.identifiers import ExecutionId
from backend.contexts.execution.domain.execution import Execution
from backend.contexts.execution.infrastructure.persistence import from_record, to_record
from backend.platform.storage import RepositoryGuard

__all__ = ["ExecutionRepository", "InMemoryExecutionRepository", "EXECUTION_BINDING"]


EXECUTION_BINDING = StorageBinding(
    record_type="Execution",
    scope_column="tenant_id",
    platform_internal_allowed=True,
)


@runtime_checkable
class ExecutionRepository(Protocol):
    """The persistence surface the application layer depends on."""

    def save(self, context: Any, execution: Execution) -> None: ...

    def replace(self, context: Any, execution: Execution) -> None: ...

    def find(self, context: Any, execution_id: ExecutionId) -> Optional[Execution]: ...

    def all(self, context: Any) -> Sequence[Execution]: ...


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


class InMemoryExecutionRepository:
    """In-process storage, guarded exactly as a durable one would be."""

    def __init__(self) -> None:
        self._guard = RepositoryGuard(EXECUTION_BINDING)
        self._executions: dict = {}
        self._lock = threading.RLock()

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def save(self, context: Any, execution: Execution) -> None:
        """Store a new intent. Refuses to overwrite one that exists."""
        access = self._guard.authorize(StorageOperation.WRITE, context)
        stored = to_record(execution, tenant_id=access.tenant_id)
        self._guard.assert_in_scope(_Row(stored), access)

        key = str(execution.execution_id)
        with self._lock:
            if key in self._executions:
                raise DuplicateExecution(key)
            self._executions[key] = stored

    def replace(self, context: Any, execution: Execution) -> None:
        """Overwrite an existing intent in place.

        Named for what it does. A draft legitimately rewrites as tasks are added;
        collapsing this into an upsert would make an accidental overwrite
        indistinguishable from an intended one.
        """
        access = self._guard.authorize(StorageOperation.WRITE, context)
        stored = to_record(execution, tenant_id=access.tenant_id)

        key = str(execution.execution_id)
        with self._lock:
            if key not in self._executions:
                raise ExecutionNotFound(key)
            self._guard.assert_in_scope(_Row(self._executions[key]), access)
            self._executions[key] = stored

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def _visible(self, access) -> list:
        scope = self._guard.scope_filter(access)
        with self._lock:
            executions = list(self._executions.values())
        if scope is None:
            return executions
        column, value = scope
        return [e for e in executions if e.get(column) == value]

    def find(self, context: Any, execution_id: ExecutionId) -> Optional[Execution]:
        access = self._guard.authorize(StorageOperation.READ, context)
        for stored in self._visible(access):
            if stored["execution_id"] == str(execution_id):
                self._guard.assert_in_scope(_Row(stored), access)
                return from_record(stored)
        return None

    def all(self, context: Any) -> Sequence[Execution]:
        access = self._guard.authorize(StorageOperation.READ, context)
        return tuple(
            from_record(e)
            for e in sorted(self._visible(access), key=lambda e: e["execution_id"])
        )

    # ------------------------------------------------------------------
    # Maintenance
    # ------------------------------------------------------------------

    def clear(self, context: Any) -> int:
        """Remove every execution visible to ``context``. Returns the count."""
        access = self._guard.authorize(StorageOperation.DELETE, context)
        scope = self._guard.scope_filter(access)
        with self._lock:
            if scope is None:
                removed = len(self._executions)
                self._executions.clear()
                return removed
            column, value = scope
            doomed = [k for k, e in self._executions.items() if e.get(column) == value]
            for key in doomed:
                del self._executions[key]
            return len(doomed)

    def __len__(self) -> int:
        with self._lock:
            return len(self._executions)
