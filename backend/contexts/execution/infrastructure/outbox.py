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
from datetime import datetime, timedelta, timezone
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

    sequence: int = 0
    """Monotonic within this outbox. **What ordering is derived from**, not
    ``recorded_at``: two events recorded in the same microsecond would tie on a
    timestamp, and a tie means two publishers can disagree about which fact came
    first. Causal order is the one thing an event log has to get right."""

    event_id: str = ""
    """The domain event's own identity, lifted out of the envelope.

    Delivery here is **at-least-once**, not exactly-once: an entry can be
    published, the acknowledgement lost, and the entry published again. That is
    the honest guarantee for any outbox without a distributed transaction, so
    this is carried where a consumer can reach it — a consumer that deduplicates
    on it is correct, and one that assumes single delivery is not."""

    claimed_by: Optional[str] = None
    claimed_until: Optional[datetime] = None
    """Who is publishing this and until when. Prevents two publishers handing the
    same event over twice; the expiry means a publisher that dies does not strand
    the entry forever."""

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
            claimed_by=None,
            claimed_until=None,
        )

    def claimed(
        self, publisher_id: str, seconds: int, *, now: Optional[datetime] = None
    ) -> "OutboxEntry":
        moment = now or datetime.now(timezone.utc)
        return replace(
            self,
            claimed_by=publisher_id,
            claimed_until=moment + timedelta(seconds=seconds),
        )

    def is_claimed_at(self, moment: datetime) -> bool:
        return (
            self.claimed_by is not None
            and self.claimed_until is not None
            and moment < self.claimed_until
        )

    def failed(self, error: str) -> "OutboxEntry":
        attempts = self.attempts + 1
        return replace(
            self,
            attempts=attempts,
            last_error=error,
            claimed_by=None,
            claimed_until=None,
            status=(
                # The dead-letter state. Kept, never deleted: an event that could
                # not be published is precisely the one somebody needs to find.
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

    def claim(
        self,
        context: Any,
        *,
        publisher_id: str,
        limit: int = 100,
        seconds: int = 60,
    ) -> tuple:
        """Take exclusive publication rights, in sequence order.

        The difference between this and ``pending``: two publishers calling
        ``pending`` both get the same entries and both hand them over. Claiming
        makes one of them the owner for a bounded time — bounded so a publisher
        that dies does not strand the entry, which is why the claim expires
        rather than being held until released.
        """
        ...

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
                    sequence=self._sequence,
                    # The event's own identity, so a consumer can deduplicate a
                    # re-delivery without unwrapping the envelope.
                    event_id=str(getattr(event, "event_id", "") or ""),
                )
                self._entries[entry.entry_id] = entry
                recorded.append(entry)
        return tuple(recorded)

    def pending(self, context: Any, limit: int = 100) -> tuple:
        """Unpublished entries in causal order. Sequence, never timestamp."""
        tenant_id = self._tenant_of(context)
        with self._lock:
            found = [
                e
                for e in self._entries.values()
                if e.status is OutboxStatus.PENDING and e.tenant_id == tenant_id
            ]
        return tuple(sorted(found, key=lambda e: e.sequence)[:limit])

    def claim(
        self,
        context: Any,
        *,
        publisher_id: str,
        limit: int = 100,
        seconds: int = 60,
        now: Optional[datetime] = None,
    ) -> tuple:
        """Claim unpublished entries exclusively, oldest first.

        The claim and the check happen under one lock, so two publishers in this
        process cannot both take the same entry. Across processes it guarantees
        nothing — there is no shared store to claim in — and that limitation is
        the outbox's, not this method's.
        """
        if not isinstance(publisher_id, str) or not publisher_id.strip():
            raise ContractViolation(
                "a claim must name its publisher; an anonymous claim cannot be "
                "released by whoever made it"
            )
        tenant_id = self._tenant_of(context)
        moment = now or datetime.now(timezone.utc)
        taken: list = []
        with self._lock:
            available = sorted(
                (
                    e
                    for e in self._entries.values()
                    if e.status is OutboxStatus.PENDING
                    and e.tenant_id == tenant_id
                    and not e.is_claimed_at(moment)
                ),
                key=lambda e: e.sequence,
            )
            for entry in available[:limit]:
                claimed = entry.claimed(publisher_id, seconds, now=moment)
                self._entries[entry.entry_id] = claimed
                taken.append(claimed)
        return tuple(taken)

    def dead_lettered(self, context: Any) -> tuple:
        """Entries given up on. Never deleted -- this is what somebody looks for."""
        tenant_id = self._tenant_of(context)
        with self._lock:
            found = [
                e
                for e in self._entries.values()
                if e.status is OutboxStatus.ABANDONED and e.tenant_id == tenant_id
            ]
        return tuple(sorted(found, key=lambda e: e.sequence))

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
        return tuple(sorted(found, key=lambda e: e.sequence))

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
