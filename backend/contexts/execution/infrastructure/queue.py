"""The dispatch queue: a Protocol, and one honest implementation.

Why a queue is infrastructure and not domain
----------------------------------------------
``Execution.ready_nodes()`` is the domain answer to *what could run*. It is
derived from the graph and is correct by construction. A queue is the *operational*
answer to *what should a worker pick up next*, which depends on things the domain
has no view of: how many workers there are, what else is queued, whether a burst
of one kind of work is starving another.

Keeping them apart means the domain stays testable without a queue, and the queue
can be replaced -- Redis, SQS, a database table -- without the domain noticing.

What this implementation is honest about
------------------------------------------
It is in-process and non-durable. A restart loses whatever was queued, which for
this context is *survivable but not free*: the work is not lost, because
``ready_nodes()`` recomputes it from the aggregate. What is lost is the ordering
and any claim already made on an item. That is the right failure mode for a
queue whose contents are derivable, and it is why the domain never depends on it.

Claims, not deletes
--------------------
Taking an item claims it for a bounded time rather than removing it. A worker
that dies between claiming and leasing leaves an item that returns to the queue,
rather than one that vanished -- the same reasoning as the lease itself, one
level up.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta, timezone
from typing import Any, Optional, Protocol, Sequence, runtime_checkable

from backend.contracts.errors import ContractViolation
from backend.contexts.execution.domain.identifiers import normalise_node_id
from backend.contexts.execution.domain.worker import WorkerKind

__all__ = ["QueueItem", "ExecutionQueue", "InMemoryExecutionQueue"]


@dataclass(frozen=True)
class QueueItem:
    """One dispatchable piece of work."""

    execution_id: str
    node_id: str
    worker_kind: WorkerKind
    enqueued_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    claimed_by: Optional[str] = None
    claimed_until: Optional[datetime] = None
    priority: int = 0

    def __post_init__(self) -> None:
        for label, value in (
            ("execution_id", self.execution_id),
            ("node_id", self.node_id),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ContractViolation(f"{label} must be non-blank text")
        normalise_node_id(self.node_id)
        if not isinstance(self.worker_kind, WorkerKind):
            raise ContractViolation("worker_kind must be a WorkerKind")
        if self.claimed_by is not None and self.claimed_until is None:
            raise ContractViolation(
                "a claimed item must say when the claim lapses; one that never lapses "
                "is a delete wearing a different name"
            )
        for label in ("enqueued_at", "claimed_until"):
            value = getattr(self, label)
            if value is not None and value.tzinfo is None:
                raise ContractViolation(f"{label} must be timezone-aware")

    @property
    def key(self) -> str:
        return f"{self.execution_id}:{self.node_id}"

    def is_claimed_at(self, moment: datetime) -> bool:
        return self.claimed_by is not None and moment < self.claimed_until

    def claimed(self, worker_id: str, seconds: int, *, now: datetime) -> "QueueItem":
        return replace(
            self,
            claimed_by=worker_id,
            claimed_until=now + timedelta(seconds=seconds),
        )

    def unclaimed(self) -> "QueueItem":
        return replace(self, claimed_by=None, claimed_until=None)


@runtime_checkable
class ExecutionQueue(Protocol):
    """What a dispatch queue must do.

    Narrow on purpose. The runtime does not need priorities, delays, or dead
    letters to be correct -- ``ready_nodes()`` is the source of truth and the
    queue is an optimisation over asking it.
    """

    def enqueue(self, context: Any, item: QueueItem) -> None: ...

    def claim(
        self, context: Any, worker_id: str, kinds: Sequence[WorkerKind], seconds: int
    ) -> Optional[QueueItem]: ...

    def release(self, context: Any, execution_id: str, node_id: str) -> None: ...

    def remove(self, context: Any, execution_id: str, node_id: str) -> None: ...

    def depth(self, context: Any) -> int: ...


class InMemoryExecutionQueue:
    """In-process, non-durable, and thread-safe.

    Thread-safe because it has to be: the whole point is several workers claiming
    from it at once, and a dictionary mutated from two threads loses writes
    silently -- which here would mean two workers holding one item.
    """

    def __init__(self) -> None:
        self._items: dict = {}
        self._lock = threading.RLock()

    def enqueue(self, context: Any, item: QueueItem) -> None:
        """Add work. Enqueuing the same node twice is a no-op, not a duplicate."""
        with self._lock:
            if item.key not in self._items:
                self._items[item.key] = item

    def claim(
        self,
        context: Any,
        worker_id: str,
        kinds: Sequence[WorkerKind],
        seconds: int,
        *,
        now: Optional[datetime] = None,
    ) -> Optional[QueueItem]:
        """Take one item this worker can run, for a bounded time.

        Returns ``None`` when there is nothing -- which is the ordinary case for
        a healthy pool and must not be an exception.
        """
        moment = now or datetime.now(timezone.utc)
        wanted = set(kinds)
        with self._lock:
            candidates = [
                item
                for item in self._items.values()
                if item.worker_kind in wanted and not item.is_claimed_at(moment)
            ]
            if not candidates:
                return None
            # Highest priority, then oldest. Stable so two workers asking at the
            # same moment get a deterministic answer rather than a race.
            chosen = min(candidates, key=lambda i: (-i.priority, i.enqueued_at, i.key))
            claimed = chosen.claimed(worker_id, seconds, now=moment)
            self._items[claimed.key] = claimed
            return claimed

    def release(self, context: Any, execution_id: str, node_id: str) -> None:
        """Return a claimed item to the pool without removing it."""
        key = f"{execution_id}:{node_id}"
        with self._lock:
            item = self._items.get(key)
            if item is not None:
                self._items[key] = item.unclaimed()

    def remove(self, context: Any, execution_id: str, node_id: str) -> None:
        with self._lock:
            self._items.pop(f"{execution_id}:{node_id}", None)

    def depth(self, context: Any) -> int:
        with self._lock:
            return len(self._items)

    def pending(self, context: Any, *, now: Optional[datetime] = None) -> tuple:
        """Items nobody currently holds. What a depth gauge actually means."""
        moment = now or datetime.now(timezone.utc)
        with self._lock:
            return tuple(
                sorted(
                    (i for i in self._items.values() if not i.is_claimed_at(moment)),
                    key=lambda i: i.key,
                )
            )

    def clear(self, context: Any) -> int:
        with self._lock:
            removed = len(self._items)
            self._items.clear()
            return removed

    def __len__(self) -> int:
        with self._lock:
            return len(self._items)
