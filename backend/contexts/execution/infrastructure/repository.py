"""Execution persistence.

Every method takes an ``ExecutionContext`` first and derives tenancy from it.
``TENANT-REPOSITORY-CONTEXT`` blocks the merge for any repository method without
one, and this repository is not on the grandfathered list -- that list may only
shrink.

In-memory only. ``STATE-NO-NEW-FILE-STORES`` forbids a new JSON-backed store; the
Protocol is the seam for a durable one.

Concurrency, and the boundary of what it buys
-----------------------------------------------
Two dispatchers reading the same execution, deciding independently, and writing
back would lose one of the two decisions -- last write wins, silently. So this
carries a **revision** per execution and a ``compare_and_swap`` that refuses a
write made against a revision that has since moved.

The revision is a *persistence* concern and lives here, not on the aggregate: it
answers "has this row changed since I read it", which is a question about storage,
not about execution. Keeping it out of the record means no schema bump and no
domain change.

**What this does not buy.** The guarantee holds within one process, because the
compare and the swap happen under one lock. Across processes there is no shared
store to compare against, so it buys nothing — that is a limitation of having no
database, not of this design, and the same method against a real one becomes a
genuine ``UPDATE ... WHERE revision = ?``. Documented in ADR-039 rather than
implied away.
"""

from __future__ import annotations

import threading
from typing import Any, Mapping, Optional, Protocol, Sequence, runtime_checkable

from backend.contracts.storage import StorageBinding, StorageOperation
from backend.contexts.execution.domain.errors import (
    DuplicateExecution,
    ExecutionError,
    ExecutionNotFound,
)
from backend.contexts.execution.domain.identifiers import ExecutionId
from backend.contexts.execution.domain.execution import Execution
from backend.contexts.execution.infrastructure.persistence import from_record, to_record
from backend.platform.storage import RepositoryGuard

__all__ = [
    "ExecutionRepository",
    "InMemoryExecutionRepository",
    "EXECUTION_BINDING",
    "ConcurrentExecutionUpdate",
]


class ConcurrentExecutionUpdate(ExecutionError):
    """Somebody else wrote this execution since it was read.

    An explicit conflict rather than a silent overwrite. The caller re-reads and
    decides again -- it does not retry the write, because the decision it made
    was made against a run that has since moved.
    """

    def __init__(self, *, execution_id: str, expected: int, actual: int) -> None:
        super().__init__(
            f"execution {execution_id} was at revision {expected} when it was read "
            f"and is now at {actual}; the write is refused rather than overwriting "
            "a decision made in between"
        )
        self.execution_id = execution_id
        self.expected = expected
        self.actual = actual


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

    def revision_of(self, context: Any, execution_id: ExecutionId) -> Optional[int]: ...

    def compare_and_swap(
        self, context: Any, execution: Execution, *, expected_revision: int
    ) -> int: ...

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
        self._revisions: dict = {}
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
            self._revisions[key] = 1

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
            self._revisions[key] = self._revisions.get(key, 0) + 1

    # ------------------------------------------------------------------
    # Concurrency
    # ------------------------------------------------------------------

    def revision_of(self, context: Any, execution_id: ExecutionId) -> Optional[int]:
        """What revision a reader saw. Passed back to ``compare_and_swap``."""
        self._guard.authorize(StorageOperation.READ, context)
        with self._lock:
            return self._revisions.get(str(execution_id))

    def compare_and_swap(
        self, context: Any, execution: Execution, *, expected_revision: int
    ) -> int:
        """Write only if nothing else has written since ``expected_revision``.

        Raises ``ConcurrentExecutionUpdate`` on a mismatch rather than
        overwriting. A lost update here is a lost *decision* -- one dispatcher
        recording a result while another records a lease, with the second write
        erasing the first -- and the run would afterwards look consistent while
        being wrong about what happened.

        The compare and the swap happen under one lock, so the check cannot be
        raced within this process. Across processes it guarantees nothing; see
        the module docstring.
        """
        access = self._guard.authorize(StorageOperation.WRITE, context)
        stored = to_record(execution, tenant_id=access.tenant_id)

        key = str(execution.execution_id)
        with self._lock:
            if key not in self._executions:
                raise ExecutionNotFound(key)
            self._guard.assert_in_scope(_Row(self._executions[key]), access)
            current = self._revisions.get(key, 0)
            if current != expected_revision:
                raise ConcurrentExecutionUpdate(
                    execution_id=key,
                    expected=expected_revision,
                    actual=current,
                )
            self._executions[key] = stored
            self._revisions[key] = current + 1
            return current + 1

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
