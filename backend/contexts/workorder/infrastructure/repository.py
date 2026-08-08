"""WorkOrder persistence.

Every method takes an ``ExecutionContext`` first and derives tenancy from it.
That is not decoration: ``TENANT-REPOSITORY-CONTEXT`` is an architecture rule
that blocks the merge for any repository method without one, and this repository
is the first written after that rule existed. It is not on the grandfathered
list and will not be added to it -- that list may only shrink.

Tenancy is enforced through the platform's storage guard rather than by hand, so
this repository gets the same refusals every other guarded store gets: no
operation without a context, no cross-tenant read, no caller-supplied tenant.
Engineering work is platform-internal, so the binding opts in to that; the guard
still refuses an unattributed write, which is why ``save`` stamps the tenant
onto the record rather than leaving it null.

The only implementation here is in-memory. That is a deliberate limit, not an
omission: ``STATE-NO-NEW-FILE-STORES`` forbids a new JSON-backed store, and a
durable one belongs with the schema work rather than smuggled into this PR.
"""

from __future__ import annotations

import threading
from typing import Any, Iterable, Mapping, Optional, Protocol, runtime_checkable

from backend.contracts.storage import StorageBinding, StorageOperation
from backend.contexts.workorder.domain.errors import DuplicateWorkOrder, WorkOrderNotFound
from backend.contexts.workorder.domain.identifiers import WorkOrderId
from backend.contexts.workorder.domain.states import WorkOrderState
from backend.contexts.workorder.domain.work_order import WorkOrder
from backend.contexts.workorder.infrastructure.persistence import from_record, to_record
from backend.platform.storage import RepositoryGuard

__all__ = ["WorkOrderRepository", "InMemoryWorkOrderRepository", "WORK_ORDER_BINDING"]


#: Engineering work is platform-internal: a WorkOrder belongs to the platform
#: building CortexPrime, not to a customer tenant. Opting in is what lets a
#: platform-internal context read across the whole log; the guard still refuses
#: to write a row with no tenant recorded.
WORK_ORDER_BINDING = StorageBinding(
    record_type="WorkOrder",
    scope_column="tenant_id",
    platform_internal_allowed=True,
)


@runtime_checkable
class WorkOrderRepository(Protocol):
    """The persistence surface the application layer depends on.

    A Protocol rather than an abstract base, so an implementation need not
    inherit from this context to satisfy it -- which keeps the eventual durable
    store free to live wherever the schema work puts it.
    """

    def save(self, context: Any, work_order: WorkOrder) -> None: ...

    def get(
        self, context: Any, work_id: WorkOrderId, version: Optional[int] = None
    ) -> WorkOrder: ...

    def find(
        self, context: Any, work_id: WorkOrderId, version: Optional[int] = None
    ) -> Optional[WorkOrder]: ...

    def versions(self, context: Any, work_id: WorkOrderId) -> tuple: ...

    def list_by_state(self, context: Any, state: WorkOrderState) -> tuple: ...

    def list_active(self, context: Any) -> tuple: ...

    def dependency_graph(self, context: Any) -> dict: ...


class InMemoryWorkOrderRepository:
    """In-process storage, guarded exactly as a durable one would be.

    Thread-safe: the orchestrator runs implementers concurrently, and a
    dictionary mutated from two threads loses writes silently rather than
    raising.
    """

    def __init__(self) -> None:
        self._guard = RepositoryGuard(WORK_ORDER_BINDING)
        self._records: dict = {}
        self._lock = threading.RLock()

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def save(self, context: Any, work_order: WorkOrder) -> None:
        """Store a version. Refuses to overwrite one that already exists.

        A WorkOrder version is immutable once written: its digest is what an
        approval binds to. Overwriting would let the content behind an approval
        change with no record that it had.
        """
        access = self._guard.authorize(StorageOperation.WRITE, context)
        record = to_record(work_order, tenant_id=access.tenant_id)
        # The tenant was derived from the access a line above, so this cannot
        # fail today. It is here because it is the check that would catch that
        # line being changed to take the tenant from anywhere else.
        self._guard.assert_in_scope(_Row(record), access)

        key = (str(work_order.work_id), work_order.version)
        with self._lock:
            if key in self._records:
                raise DuplicateWorkOrder(
                    work_order_id=str(work_order.work_id), version=work_order.version
                )
            self._records[key] = record

    def replace_version(self, context: Any, work_order: WorkOrder) -> None:
        """Overwrite an existing version in place.

        Separate from :meth:`save` and named for what it does. State transitions
        legitimately rewrite a version -- the digest covers content, not state --
        but the operation is distinct from creating one, and collapsing the two
        into an upsert would make an accidental overwrite indistinguishable from
        an intended one.
        """
        access = self._guard.authorize(StorageOperation.WRITE, context)
        record = to_record(work_order, tenant_id=access.tenant_id)

        key = (str(work_order.work_id), work_order.version)
        with self._lock:
            if key not in self._records:
                raise WorkOrderNotFound(str(work_order.work_id))
            self._records[key] = record

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
        self, context: Any, work_id: WorkOrderId, version: Optional[int] = None
    ) -> Optional[WorkOrder]:
        access = self._guard.authorize(StorageOperation.READ, context)
        candidates = [r for r in self._visible(access) if r["work_id"] == str(work_id)]
        if not candidates:
            return None
        if version is None:
            chosen = max(candidates, key=lambda r: r["version"])
        else:
            matching = [r for r in candidates if r["version"] == version]
            if not matching:
                return None
            chosen = matching[0]
        self._guard.assert_in_scope(_Row(chosen), access)
        return from_record(chosen)

    def get(
        self, context: Any, work_id: WorkOrderId, version: Optional[int] = None
    ) -> WorkOrder:
        found = self.find(context, work_id, version)
        if found is None:
            raise WorkOrderNotFound(str(work_id))
        return found

    def versions(self, context: Any, work_id: WorkOrderId) -> tuple:
        access = self._guard.authorize(StorageOperation.READ, context)
        records = [r for r in self._visible(access) if r["work_id"] == str(work_id)]
        return tuple(from_record(r) for r in sorted(records, key=lambda r: r["version"]))

    def list_by_state(self, context: Any, state: WorkOrderState) -> tuple:
        access = self._guard.authorize(StorageOperation.READ, context)
        records = [r for r in self._visible(access) if r["state"] == state.value]
        return tuple(
            from_record(r) for r in sorted(records, key=lambda r: (r["work_id"], r["version"]))
        )

    def list_active(self, context: Any) -> tuple:
        """Every non-terminal WorkOrder, latest version only.

        The basis for blast-radius conflict detection: a lock is held from
        Assigned through Merged, and a terminal WorkOrder holds nothing.
        """
        access = self._guard.authorize(StorageOperation.READ, context)
        latest: dict = {}
        for record in self._visible(access):
            if WorkOrderState(record["state"]).is_terminal:
                continue
            current = latest.get(record["work_id"])
            if current is None or record["version"] > current["version"]:
                latest[record["work_id"]] = record
        return tuple(from_record(r) for r in sorted(latest.values(), key=lambda r: r["work_id"]))

    def dependency_graph(self, context: Any) -> dict:
        """``work_id -> set of dependency work_ids``, for cycle detection."""
        access = self._guard.authorize(StorageOperation.READ, context)
        graph: dict = {}
        for record in self._visible(access):
            existing = graph.setdefault(record["work_id"], set())
            existing.update(record["dependencies"])
        return graph

    # ------------------------------------------------------------------
    # Maintenance
    # ------------------------------------------------------------------

    def clear(self, context: Any) -> int:
        """Remove every WorkOrder visible to ``context``. Returns the count.

        Takes a context like everything else here, and not merely to satisfy the
        rule: this is the most destructive operation the repository offers, and
        it was the one method that originally lacked one. The architecture rule
        caught it, which is a better argument for the rule than any test of the
        rule itself.

        Scoped, so a tenant context clears only its own records. A clear that
        ignored tenancy would be a cross-tenant delete wearing a maintenance
        method's name.
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


class _Row:
    """Adapts a record mapping to the attribute access the guard expects.

    The guard reads ``record.<scope_column>`` because it was written against ORM
    rows. Wrapping rather than changing the guard keeps that boundary honest --
    the guard should not learn about mappings to accommodate one caller.
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
