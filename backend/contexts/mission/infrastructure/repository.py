"""Mission persistence.

Every method takes an ``ExecutionContext`` first and derives tenancy from it.
``TENANT-REPOSITORY-CONTEXT`` blocks the merge for any repository method without
one, and this repository is not on the grandfathered list -- that list may only
shrink.

In-memory only. ``STATE-NO-NEW-FILE-STORES`` forbids a new JSON-backed store; the
Protocol is the seam for a durable one.

Thread-safe because missions are long-running by definition: a monitor mission
records checkpoints from an executor while an operator reads its timeline, and a
dictionary mutated from two threads loses writes silently.
"""

from __future__ import annotations

import threading
from typing import Any, Mapping, Optional, Protocol, Sequence, runtime_checkable

from backend.contracts.storage import StorageBinding, StorageOperation
from backend.contexts.mission.domain.errors import DuplicateMission, MissionNotFound
from backend.contexts.mission.domain.identifiers import MissionId
from backend.contexts.mission.domain.mission import Mission
from backend.contexts.mission.infrastructure.persistence import from_record, to_record
from backend.platform.storage import RepositoryGuard

__all__ = ["MissionRepository", "InMemoryMissionRepository", "MISSION_BINDING"]


MISSION_BINDING = StorageBinding(
    record_type="Mission",
    scope_column="tenant_id",
    platform_internal_allowed=True,
)


@runtime_checkable
class MissionRepository(Protocol):
    """The persistence surface the application layer depends on."""

    def save(self, context: Any, mission: Mission) -> None: ...

    def replace(self, context: Any, mission: Mission) -> None: ...

    def find(self, context: Any, mission_id: MissionId) -> Optional[Mission]: ...

    def all(self, context: Any) -> Sequence[Mission]: ...


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


class InMemoryMissionRepository:
    """In-process storage, guarded exactly as a durable one would be."""

    def __init__(self) -> None:
        self._guard = RepositoryGuard(MISSION_BINDING)
        self._missions: dict = {}
        self._lock = threading.RLock()

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def save(self, context: Any, mission: Mission) -> None:
        """Store a new mission. Refuses to overwrite one that exists."""
        access = self._guard.authorize(StorageOperation.WRITE, context)
        stored = to_record(mission, tenant_id=access.tenant_id)
        self._guard.assert_in_scope(_Row(stored), access)

        key = str(mission.mission_id)
        with self._lock:
            if key in self._missions:
                raise DuplicateMission(key)
            self._missions[key] = stored

    def replace(self, context: Any, mission: Mission) -> None:
        """Overwrite an existing mission in place.

        Named for what it does. A running mission legitimately rewrites as its
        timeline grows; collapsing this into an upsert would make an accidental
        overwrite indistinguishable from an intended one.
        """
        access = self._guard.authorize(StorageOperation.WRITE, context)
        stored = to_record(mission, tenant_id=access.tenant_id)

        key = str(mission.mission_id)
        with self._lock:
            if key not in self._missions:
                raise MissionNotFound(key)
            self._guard.assert_in_scope(_Row(self._missions[key]), access)
            self._missions[key] = stored

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def _visible(self, access) -> list:
        scope = self._guard.scope_filter(access)
        with self._lock:
            missions = list(self._missions.values())
        if scope is None:
            return missions
        column, value = scope
        return [m for m in missions if m.get(column) == value]

    def find(self, context: Any, mission_id: MissionId) -> Optional[Mission]:
        access = self._guard.authorize(StorageOperation.READ, context)
        for stored in self._visible(access):
            if stored["mission_id"] == str(mission_id):
                self._guard.assert_in_scope(_Row(stored), access)
                return from_record(stored)
        return None

    def all(self, context: Any) -> Sequence[Mission]:
        access = self._guard.authorize(StorageOperation.READ, context)
        return tuple(
            from_record(m)
            for m in sorted(self._visible(access), key=lambda m: m["mission_id"])
        )

    # ------------------------------------------------------------------
    # Maintenance
    # ------------------------------------------------------------------

    def clear(self, context: Any) -> int:
        """Remove every mission visible to ``context``. Returns the count."""
        access = self._guard.authorize(StorageOperation.DELETE, context)
        scope = self._guard.scope_filter(access)
        with self._lock:
            if scope is None:
                removed = len(self._missions)
                self._missions.clear()
                return removed
            column, value = scope
            doomed = [k for k, m in self._missions.items() if m.get(column) == value]
            for key in doomed:
                del self._missions[key]
            return len(doomed)

    def __len__(self) -> int:
        with self._lock:
            return len(self._missions)
