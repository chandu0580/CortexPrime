"""Binding persistence.

Every method takes an ``ExecutionContext``. In-memory only: no new file store,
and **nothing here is durable** — a restart loses every binding. Since bindings
expire in minutes and a lost one simply means re-resolving, that is a survivable
limitation rather than a hidden one, but it is stated rather than implied.

Append-only by construction
-----------------------------
There is ``save`` and there is ``find``. There is no ``update``, no ``replace``,
and no ``delete``. A binding is a record of a decision that was made; changing
one would mean the thing that runs could differ from the thing that was
authorized while the same binding id vouched for both.

``save`` refuses to overwrite an existing binding id for the same reason.
"""

from __future__ import annotations

import threading
from typing import Any, Optional, Protocol, Sequence, runtime_checkable

from backend.contracts.errors import ContractViolation
from backend.contracts.storage import StorageBinding, StorageOperation
from backend.contexts.connectivity.domain.binding import CapabilityBinding
from backend.platform.storage import RepositoryGuard

__all__ = [
    "BindingRepository",
    "InMemoryBindingRepository",
    "BINDING_STORAGE_BINDING",
]

BINDING_STORAGE_BINDING = StorageBinding(
    record_type="CapabilityBinding",
    scope_column="tenant_id",
    platform_internal_allowed=True,
)


@runtime_checkable
class BindingRepository(Protocol):
    """Deliberately narrow. Write once, read back, list for a run."""

    def save(self, context: Any, binding: CapabilityBinding) -> None: ...

    def find(self, context: Any, binding_id: str) -> Optional[CapabilityBinding]: ...

    def for_execution(self, context: Any, execution_id: str) -> Sequence[CapabilityBinding]: ...


class _Row:
    __slots__ = ("_data",)

    def __init__(self, data: dict) -> None:
        self._data = data

    def __getattr__(self, name: str) -> Any:
        try:
            return self._data[name]
        except KeyError as exc:  # pragma: no cover - defensive
            raise AttributeError(name) from exc


class InMemoryBindingRepository:
    """In-process, tenant-guarded, append-only. Not durable."""

    def __init__(self) -> None:
        self._bindings: dict = {}
        self._guard = RepositoryGuard(BINDING_STORAGE_BINDING)
        self._lock = threading.RLock()

    def save(self, context: Any, binding: CapabilityBinding) -> None:
        access = self._guard.authorize(StorageOperation.WRITE, context)
        self._guard.assert_in_scope(_Row({"tenant_id": binding.tenant_id}), access)
        with self._lock:
            if binding.binding_id in self._bindings:
                raise ContractViolation(
                    f"binding {binding.binding_id} already exists; bindings are "
                    "immutable, and a new choice is a new binding"
                )
            self._bindings[binding.binding_id] = binding

    def find(self, context: Any, binding_id: str) -> Optional[CapabilityBinding]:
        self._guard.authorize(StorageOperation.READ, context)
        with self._lock:
            found = self._bindings.get(binding_id)
        if found is None:
            return None
        # Another tenant's binding is absent, not forbidden.
        tenant = getattr(context, "tenant_id", None)
        if getattr(context, "is_platform_internal", False) or found.tenant_id == tenant:
            return found
        return None

    def for_execution(self, context: Any, execution_id: str) -> Sequence[CapabilityBinding]:
        self._guard.authorize(StorageOperation.READ, context)
        tenant = getattr(context, "tenant_id", None)
        platform = getattr(context, "is_platform_internal", False)
        with self._lock:
            found = [
                b
                for b in self._bindings.values()
                if b.execution_id == execution_id
                and (platform or b.tenant_id == tenant)
            ]
        return tuple(sorted(found, key=lambda b: b.binding_id))

    def __len__(self) -> int:
        with self._lock:
            return len(self._bindings)
