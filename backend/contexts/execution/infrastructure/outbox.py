"""The durable-publication seam: state committed, event not lost.

The failure this exists to prevent
------------------------------------
A run's state is written, the process dies, and the event announcing it is never
published. The runtime and everything downstream now disagree about what
happened, and nothing detects it -- the run looks fine from the inside.

The fix is the standard one: the event is recorded **in the same transaction as
the state**, and publication happens afterwards from that record. Publication
may then fail, retry, or duplicate without ever losing the fact.

What this module honestly is
------------------------------
The contract, plus an in-memory implementation that matches the persistence the
rest of this context has today. **It is not durable.** A restart loses pending
entries, exactly as the in-memory repository loses runs.

That is stated plainly rather than papered over, because an outbox that claims
durability it does not have is worse than none: it invites callers to rely on a
guarantee that is not there. When the repository becomes a real database, this
contract is implemented against the same transaction and the guarantee becomes
real without any caller changing.

Deliberately not a second event bus. Entries carry already-built domain events;
this decides *when they are handed over*, never what they mean.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional, Protocol, Sequence, runtime_checkable

from backend.contracts.errors import ContractViolation

__all__ = [
    "OutboxStatus",
    "OutboxEntry",
    "ExecutionOutbox",
    "InMemoryExecutionOutbox",
]

_MAX_PUBLISH_ATTEMPTS = 10


class OutboxStatus(str, Enum):
    PENDING = "pending"
    PUBLISHED = "published"
    ABANDONED = "abandoned"
    """Given up on after repeated failures. Kept, never deleted: an event that
    could not be published is precisely the one somebody needs to find later."""


@dataclass(frozen=True)
class OutboxEntry:
    """One event recorded alongside the state change that produced it."""

    entry_id: str
    execution_id: str
    tenant_id: str
    event_type: str
    event: Any
    recorded_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    status: OutboxStatus = OutboxStatus.PENDING
    attempts: int = 0
    published_at: Optional[datetime] = None
    last_error: Optional[str] = None

    def __post_init__(self) -> None:
        for label in ("entry_id", "execution_id", "tenant_id", "event_type"):
            value = getattr(self, label)
            if not isinstance(value, str) or not value.strip():
                raise ContractViolation(f"{label} must be non-blank text")
        if self.status is OutboxStatus.PUBLISHED and self.published_at is None:
            raise ContractViolation(
                "a published entry must record when; without it nobody can tell a "
                "publication from a claim that one happened"
            )

    def published(self, *, now: Optional[datetime] = None) -> "OutboxEntry":
        return replace(
            self,
            status=OutboxStatus.PUBLISHED,
            published_at=now or datetime.now(timezone.utc),
            attempts=self.attempts + 1,
        )

    def failed(self, error: str) -> "OutboxEntry":
        attempts = self.attempts + 1
        return replace(
            self,
            attempts=attempts,
            last_error=error,
            status=(
                OutboxStatus.ABANDONED
                if attempts >= _MAX_PUBLISH_ATTEMPTS
                else OutboxStatus.PENDING
            ),
        )


@runtime_checkable
class ExecutionOutbox(Protocol):
    """Record events with the state change, hand them over afterwards."""

    def record(self, context: Any, execution_id: str, events: Sequence[Any]) -> tuple: ...

    def pending(self, context: Any, limit: int = 100) -> tuple: ...

    def mark_published(self, context: Any, entry_id: str) -> None: ...

    def mark_failed(self, context: Any, entry_id: str, error: str) -> None: ...


class InMemoryExecutionOutbox:
    """In-process and **not durable**. See the module docstring.

    Thread-safe because several workers report outcomes concurrently, and a
    dictionary mutated from two threads loses writes silently -- which here
    would mean an event that no longer exists anywhere.
    """

    def __init__(self) -> None:
        self._entries: dict = {}
        self._lock = threading.RLock()
        self._sequence = 0

    @staticmethod
    def _tenant_of(context: Any) -> str:
        tenant = getattr(context, "tenant_id", None)
        if not tenant:
            raise ContractViolation(
                "an outbox entry must be attributable to a tenant; recording one "
                "without a context would produce an event nobody owns"
            )
        return str(tenant)

    def record(self, context: Any, execution_id: str, events: Sequence[Any]) -> tuple:
        tenant_id = self._tenant_of(context)
        recorded: list = []
        with self._lock:
            for event in events:
                self._sequence += 1
                entry = OutboxEntry(
                    entry_id=f"{execution_id}:{self._sequence}",
                    execution_id=execution_id,
                    tenant_id=tenant_id,
                    event_type=getattr(type(event), "EVENT_TYPE", "unknown"),
                    event=event,
                )
                self._entries[entry.entry_id] = entry
                recorded.append(entry)
        return tuple(recorded)

    def pending(self, context: Any, limit: int = 100) -> tuple:
        tenant_id = self._tenant_of(context)
        with self._lock:
            found = [
                e
                for e in self._entries.values()
                if e.status is OutboxStatus.PENDING and e.tenant_id == tenant_id
            ]
        return tuple(sorted(found, key=lambda e: e.recorded_at)[:limit])

    def mark_published(self, context: Any, entry_id: str) -> None:
        with self._lock:
            entry = self._entries.get(entry_id)
            if entry is not None:
                self._entries[entry_id] = entry.published()

    def mark_failed(self, context: Any, entry_id: str, error: str) -> None:
        with self._lock:
            entry = self._entries.get(entry_id)
            if entry is not None:
                self._entries[entry_id] = entry.failed(error)

    def entries_for(self, context: Any, execution_id: str) -> tuple:
        """Every entry for one run, oldest first -- published ones included.

        Entries are never deleted, which is what makes this usable as the run's
        recorded history until a real event store exists.
        """
        tenant_id = self._tenant_of(context)
        with self._lock:
            found = [
                e
                for e in self._entries.values()
                if e.execution_id == execution_id and e.tenant_id == tenant_id
            ]
        return tuple(sorted(found, key=lambda e: e.recorded_at))

    def abandoned(self, context: Any) -> tuple:
        """Entries publication gave up on. What an operator needs to see."""
        tenant_id = self._tenant_of(context)
        with self._lock:
            return tuple(
                e
                for e in self._entries.values()
                if e.status is OutboxStatus.ABANDONED and e.tenant_id == tenant_id
            )

    def __len__(self) -> int:
        with self._lock:
            return len(self._entries)
