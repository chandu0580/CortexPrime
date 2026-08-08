"""Plan persistence.

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
from backend.contexts.planner.domain.errors import DuplicatePlan, PlanNotFound
from backend.contexts.planner.domain.identifiers import PlanId
from backend.contexts.planner.domain.plan import Plan
from backend.contexts.planner.infrastructure.persistence import from_record, to_record
from backend.platform.storage import RepositoryGuard

__all__ = ["PlanRepository", "InMemoryPlanRepository", "PLAN_BINDING"]


PLAN_BINDING = StorageBinding(
    record_type="Plan",
    scope_column="tenant_id",
    platform_internal_allowed=True,
)


@runtime_checkable
class PlanRepository(Protocol):
    """The persistence surface the application layer depends on."""

    def save(self, context: Any, plan: Plan) -> None: ...

    def replace(self, context: Any, plan: Plan) -> None: ...

    def find(self, context: Any, plan_id: PlanId) -> Optional[Plan]: ...

    def all(self, context: Any) -> Sequence[Plan]: ...


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


class InMemoryPlanRepository:
    """In-process storage, guarded exactly as a durable one would be."""

    def __init__(self) -> None:
        self._guard = RepositoryGuard(PLAN_BINDING)
        self._plans: dict = {}
        self._lock = threading.RLock()

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def save(self, context: Any, plan: Plan) -> None:
        """Store a new intent. Refuses to overwrite one that exists."""
        access = self._guard.authorize(StorageOperation.WRITE, context)
        stored = to_record(plan, tenant_id=access.tenant_id)
        self._guard.assert_in_scope(_Row(stored), access)

        key = str(plan.plan_id)
        with self._lock:
            if key in self._plans:
                raise DuplicatePlan(key)
            self._plans[key] = stored

    def replace(self, context: Any, plan: Plan) -> None:
        """Overwrite an existing intent in place.

        Named for what it does. A draft legitimately rewrites as tasks are added;
        collapsing this into an upsert would make an accidental overwrite
        indistinguishable from an intended one.
        """
        access = self._guard.authorize(StorageOperation.WRITE, context)
        stored = to_record(plan, tenant_id=access.tenant_id)

        key = str(plan.plan_id)
        with self._lock:
            if key not in self._plans:
                raise PlanNotFound(key)
            self._guard.assert_in_scope(_Row(self._plans[key]), access)
            self._plans[key] = stored

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def _visible(self, access) -> list:
        scope = self._guard.scope_filter(access)
        with self._lock:
            plans = list(self._plans.values())
        if scope is None:
            return plans
        column, value = scope
        return [p for p in plans if p.get(column) == value]

    def find(self, context: Any, plan_id: PlanId) -> Optional[Plan]:
        access = self._guard.authorize(StorageOperation.READ, context)
        for stored in self._visible(access):
            if stored["plan_id"] == str(plan_id):
                self._guard.assert_in_scope(_Row(stored), access)
                return from_record(stored)
        return None

    def all(self, context: Any) -> Sequence[Plan]:
        access = self._guard.authorize(StorageOperation.READ, context)
        return tuple(
            from_record(p)
            for p in sorted(self._visible(access), key=lambda p: p["plan_id"])
        )

    # ------------------------------------------------------------------
    # Maintenance
    # ------------------------------------------------------------------

    def clear(self, context: Any) -> int:
        """Remove every plan visible to ``context``. Returns the count."""
        access = self._guard.authorize(StorageOperation.DELETE, context)
        scope = self._guard.scope_filter(access)
        with self._lock:
            if scope is None:
                removed = len(self._plans)
                self._plans.clear()
                return removed
            column, value = scope
            doomed = [k for k, p in self._plans.items() if p.get(column) == value]
            for key in doomed:
                del self._plans[key]
            return len(doomed)

    def __len__(self) -> int:
        with self._lock:
            return len(self._plans)
