"""Workflow persistence.

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
from backend.contexts.workflow.domain.errors import DuplicateWorkflow, WorkflowNotFound
from backend.contexts.workflow.domain.identifiers import WorkflowId
from backend.contexts.workflow.domain.workflow import Workflow
from backend.contexts.workflow.infrastructure.persistence import from_record, to_record
from backend.platform.storage import RepositoryGuard

__all__ = ["WorkflowRepository", "InMemoryWorkflowRepository", "WORKFLOW_BINDING"]


WORKFLOW_BINDING = StorageBinding(
    record_type="Workflow",
    scope_column="tenant_id",
    platform_internal_allowed=True,
)


@runtime_checkable
class WorkflowRepository(Protocol):
    """The persistence surface the application layer depends on."""

    def save(self, context: Any, workflow: Workflow) -> None: ...

    def replace(self, context: Any, workflow: Workflow) -> None: ...

    def find(self, context: Any, workflow_id: WorkflowId) -> Optional[Workflow]: ...

    def all(self, context: Any) -> Sequence[Workflow]: ...


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


class InMemoryWorkflowRepository:
    """In-process storage, guarded exactly as a durable one would be."""

    def __init__(self) -> None:
        self._guard = RepositoryGuard(WORKFLOW_BINDING)
        self._workflows: dict = {}
        self._lock = threading.RLock()

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def save(self, context: Any, workflow: Workflow) -> None:
        """Store a new intent. Refuses to overwrite one that exists."""
        access = self._guard.authorize(StorageOperation.WRITE, context)
        stored = to_record(workflow, tenant_id=access.tenant_id)
        self._guard.assert_in_scope(_Row(stored), access)

        key = str(workflow.workflow_id)
        with self._lock:
            if key in self._workflows:
                raise DuplicateWorkflow(key)
            self._workflows[key] = stored

    def replace(self, context: Any, workflow: Workflow) -> None:
        """Overwrite an existing intent in place.

        Named for what it does. A draft legitimately rewrites as tasks are added;
        collapsing this into an upsert would make an accidental overwrite
        indistinguishable from an intended one.
        """
        access = self._guard.authorize(StorageOperation.WRITE, context)
        stored = to_record(workflow, tenant_id=access.tenant_id)

        key = str(workflow.workflow_id)
        with self._lock:
            if key not in self._workflows:
                raise WorkflowNotFound(key)
            self._guard.assert_in_scope(_Row(self._workflows[key]), access)
            self._workflows[key] = stored

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def _visible(self, access) -> list:
        scope = self._guard.scope_filter(access)
        with self._lock:
            workflows = list(self._workflows.values())
        if scope is None:
            return workflows
        column, value = scope
        return [w for w in workflows if w.get(column) == value]

    def find(self, context: Any, workflow_id: WorkflowId) -> Optional[Workflow]:
        access = self._guard.authorize(StorageOperation.READ, context)
        for stored in self._visible(access):
            if stored["workflow_id"] == str(workflow_id):
                self._guard.assert_in_scope(_Row(stored), access)
                return from_record(stored)
        return None

    def all(self, context: Any) -> Sequence[Workflow]:
        access = self._guard.authorize(StorageOperation.READ, context)
        return tuple(
            from_record(w)
            for w in sorted(self._visible(access), key=lambda w: w["workflow_id"])
        )

    # ------------------------------------------------------------------
    # Maintenance
    # ------------------------------------------------------------------

    def clear(self, context: Any) -> int:
        """Remove every workflow visible to ``context``. Returns the count."""
        access = self._guard.authorize(StorageOperation.DELETE, context)
        scope = self._guard.scope_filter(access)
        with self._lock:
            if scope is None:
                removed = len(self._workflows)
                self._workflows.clear()
                return removed
            column, value = scope
            doomed = [k for k, w in self._workflows.items() if w.get(column) == value]
            for key in doomed:
                del self._workflows[key]
            return len(doomed)

    def __len__(self) -> int:
        with self._lock:
            return len(self._workflows)
