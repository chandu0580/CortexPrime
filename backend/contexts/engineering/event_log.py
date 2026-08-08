"""The append-only engineering event log, and the dispatcher that drains it.

This is where rollback and replay are actually solved, so the reasoning matters
more than the code.

The problem
-----------
A transition does two things that must both happen or neither: it changes state,
and it emits events. Do them in the obvious order -- persist, then dispatch --
and a subscriber that raises leaves state changed with events lost. Reverse the
order and a failed persist leaves events describing something that never
happened.

The resolution: an outbox
-------------------------
Events are **recorded** in the same critical section as the state change, and
**delivered** afterwards from the log. Delivery failure cannot lose an event,
because the event is already durable in the log; it can only delay one. Redelivery
is re-reading the log from a cursor.

That also makes replay fall out for free: replay is exactly a delivery pass from
sequence zero, and a projection rebuilt from the log must equal the state the
live system reached.

Ordering and gaps
-----------------
Sequence numbers are gapless and assigned under the lock. Deletion of a record
leaves an intact-looking sequence *only* if every later number is rewritten, so a
gap is detectable -- the same property the product's own audit chain relies on,
and for the same reason: the record someone would most want gone is a rejection.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Iterator, Optional, Sequence

from backend.contracts.errors import ContractViolation

__all__ = ["LoggedEvent", "EngineeringEventLog", "EngineeringEventDispatcher", "DeliveryFailure"]


@dataclass(frozen=True)
class LoggedEvent:
    """One event, positioned in the log."""

    sequence: int
    work_id: str
    event_type: str
    event: Any

    def __str__(self) -> str:  # pragma: no cover - diagnostic only
        return f"#{self.sequence} {self.event_type} ({self.work_id})"


@dataclass(frozen=True)
class DeliveryFailure:
    """A subscriber that raised. The event stays in the log."""

    sequence: int
    subscriber: str
    error: BaseException


class EngineeringEventLog:
    """Append-only, ordered, gapless.

    Thread-safe: the runtime transitions WorkOrders concurrently, and a list
    appended from two threads without a lock loses entries silently.
    """

    def __init__(self) -> None:
        self._entries: list = []
        self._lock = threading.RLock()

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def append(self, work_id: str, events: Sequence[Any]) -> tuple:
        """Record events atomically. Returns what was written.

        All-or-nothing within one call: a transition's events belong together,
        and a partial append would leave a consumer able to observe the second
        half of a transition without the first.
        """
        if not work_id or not isinstance(work_id, str):
            raise ContractViolation("work_id must be a non-blank string")

        prepared: list = []
        for event in events:
            event_type = getattr(type(event), "EVENT_TYPE", None)
            if not event_type:
                raise ContractViolation(
                    f"{type(event).__name__} has no EVENT_TYPE; only domain events may be logged"
                )
            prepared.append((work_id, event_type, event))

        with self._lock:
            start = len(self._entries)
            written = tuple(
                LoggedEvent(sequence=start + offset, work_id=wid, event_type=etype, event=evt)
                for offset, (wid, etype, evt) in enumerate(prepared)
            )
            self._entries.extend(written)
            return written

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def since(self, cursor: int = 0) -> tuple:
        with self._lock:
            return tuple(self._entries[cursor:])

    def for_work_order(self, work_id: str) -> tuple:
        with self._lock:
            return tuple(e for e in self._entries if e.work_id == work_id)

    def __len__(self) -> int:
        with self._lock:
            return len(self._entries)

    def __iter__(self) -> Iterator:
        return iter(self.since(0))

    # ------------------------------------------------------------------
    # Integrity
    # ------------------------------------------------------------------

    def verify(self) -> tuple:
        """Every defect found in the log's ordering. Empty means intact.

        Checks the sequence is gapless and monotonic. A gap means a record was
        removed; a repeat means one was inserted.
        """
        defects: list = []
        with self._lock:
            for position, entry in enumerate(self._entries):
                if entry.sequence != position:
                    defects.append(
                        f"entry at position {position} carries sequence {entry.sequence}; "
                        "the log has a gap or a duplicate"
                    )
        return tuple(defects)


class EngineeringEventDispatcher:
    """Delivers logged events to subscribers, and remembers where it got to.

    Delivery is separate from recording on purpose (see the module docstring). A
    subscriber that raises does not stop the others and does not roll back the
    transition -- it produces a :class:`DeliveryFailure` and the cursor does not
    advance past the failure on the next drain unless the caller says so.
    """

    def __init__(self, log: EngineeringEventLog) -> None:
        self._log = log
        self._subscribers: list = []
        self._cursor = 0
        self._lock = threading.RLock()

    @property
    def log(self) -> EngineeringEventLog:
        return self._log

    @property
    def cursor(self) -> int:
        with self._lock:
            return self._cursor

    def subscribe(self, name: str, handler: Callable[[LoggedEvent], None], *, event_types: Optional[Sequence[str]] = None) -> None:
        """Register a handler, optionally narrowed to specific event types.

        Named rather than anonymous so a delivery failure can say *which*
        subscriber raised. An unnamed handler produces a failure report nobody
        can act on.
        """
        if not name or not isinstance(name, str):
            raise ContractViolation("a subscriber must be named")
        with self._lock:
            if any(existing == name for existing, _, _ in self._subscribers):
                raise ContractViolation(f"a subscriber named {name!r} is already registered")
            self._subscribers.append(
                (name, handler, frozenset(event_types) if event_types else None)
            )

    def drain(self) -> tuple:
        """Deliver everything since the cursor. Returns any failures.

        Advances the cursor past delivered events regardless of failures, and
        reports what failed. Holding the cursor back would redeliver every
        subsequent event to every healthy subscriber to retry one broken pair,
        which turns a single bad handler into a storm.
        """
        with self._lock:
            pending = self._log.since(self._cursor)
            self._cursor = len(self._log)

        failures: list = []
        for entry in pending:
            for name, handler, wanted in self._subscribers:
                if wanted is not None and entry.event_type not in wanted:
                    continue
                try:
                    handler(entry)
                except Exception as exc:  # noqa: BLE001 - a subscriber may raise anything
                    failures.append(
                        DeliveryFailure(sequence=entry.sequence, subscriber=name, error=exc)
                    )
        return tuple(failures)

    def replay(self, *, into: Callable[[LoggedEvent], None], cursor: int = 0) -> int:
        """Re-deliver the log to one handler without touching the live cursor.

        The mechanism behind rebuilding a projection: replay is a delivery pass
        from sequence zero, and a projection built this way must equal the state
        the live system reached. If it does not, either the log is incomplete or
        the live path mutated something it never recorded.
        """
        delivered = 0
        for entry in self._log.since(cursor):
            into(entry)
            delivered += 1
        return delivered
