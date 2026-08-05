"""Audit storage abstraction.

The runtime never knows where records live. That matters because the target is
PostgreSQL (PR-11) and the interim is a file, and an audit trail that has to be
rewritten to change storage is an audit trail that will be rewritten badly.

The interface is deliberately narrow -- append, read, query, count, last. There
is **no update and no delete**, not as a convention but because the operations
do not exist to call. A store that cannot express mutation cannot be mutated by
mistake.

Two implementations ship here:

``InMemoryAuditStore``
    For tests and for a process that genuinely has no durable requirement.
``JsonlAuditStore``
    Durable, append-only. One JSON object per line, opened in append mode,
    flushed and fsynced per record.

On JSONL versus the repository's JSON anti-pattern
--------------------------------------------------
The Phase 1 review names file-based state as an anti-pattern, and it is -- for
*mutable* state, where every write rewrites the whole document and a crash
mid-write loses everything. Append-only JSONL is a different shape: a record is
one line, appended and fsynced, never revisited. A torn write damages at most
the final line, which chain verification detects and reports rather than
silently accepting.

It is still an interim. PostgreSQL gives transactional guarantees this does not,
which is why the interface exists.
"""

from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator, Optional, Protocol, runtime_checkable

from backend.contracts import AuditEvent, AuditEventKind
from backend.platform.audit.exceptions import (
    AuditCorruptionError,
    AuditStorageError,
)

__all__ = ["AuditQuery", "AuditStore", "InMemoryAuditStore", "JsonlAuditStore"]


@dataclass(frozen=True)
class AuditQuery:
    """Filter criteria for reading audit history.

    Every field is optional and combines with AND. Filtering happens in the
    store so a future SQL implementation can push predicates down rather than
    loading a chain into memory to discard most of it.
    """

    kinds: Optional[frozenset[AuditEventKind]] = None
    tenant_id: Optional[str] = None
    correlation_id: Optional[str] = None
    subject_reference: Optional[str] = None
    actor_id: Optional[str] = None
    since: Optional[datetime] = None
    until: Optional[datetime] = None
    min_sequence: Optional[int] = None
    max_sequence: Optional[int] = None
    security_relevant_only: bool = False
    limit: Optional[int] = None

    def matches(self, record: AuditEvent) -> bool:
        """Whether ``record`` satisfies every stated criterion."""
        if self.kinds is not None and record.kind not in self.kinds:
            return False
        if self.security_relevant_only and not record.kind.is_security_relevant:
            return False
        if self.tenant_id is not None and record.scope.tenant.tenant_id != self.tenant_id:
            return False
        if self.correlation_id is not None and record.correlation_id != self.correlation_id:
            return False
        if (
            self.subject_reference is not None
            and record.subject_reference != self.subject_reference
        ):
            return False
        if self.actor_id is not None:
            actor = record.actor
            if actor is None or actor.principal_id != self.actor_id:
                return False
        if self.since is not None and record.recorded_at < self.since:
            return False
        if self.until is not None and record.recorded_at >= self.until:
            return False
        if self.min_sequence is not None and record.sequence < self.min_sequence:
            return False
        if self.max_sequence is not None and record.sequence > self.max_sequence:
            return False
        return True


@runtime_checkable
class AuditStore(Protocol):
    """Append-only storage for audit records.

    Implementations must be safe to call from multiple threads and must
    preserve insertion order. There is intentionally no ``update`` or
    ``delete``; retention is handled by an explicit, audited archival path
    (see ``retention.py``), never by a store-level mutation.
    """

    def append(self, record: AuditEvent) -> None:
        """Persist a record. Must be durable before returning."""
        ...

    def read_all(self) -> Iterator[AuditEvent]:
        """Yield every record in insertion order."""
        ...

    def query(self, criteria: AuditQuery) -> Iterator[AuditEvent]:
        """Yield records matching ``criteria``, in insertion order."""
        ...

    def last(self) -> Optional[AuditEvent]:
        """Return the most recent record, or ``None`` if the store is empty."""
        ...

    def count(self) -> int:
        """Return the number of stored records."""
        ...


class InMemoryAuditStore:
    """Non-durable store for tests and ephemeral processes."""

    __slots__ = ("_lock", "_records")

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._records: list[AuditEvent] = []

    def append(self, record: AuditEvent) -> None:
        with self._lock:
            self._records.append(record)

    def read_all(self) -> Iterator[AuditEvent]:
        with self._lock:
            snapshot = list(self._records)
        yield from snapshot

    def query(self, criteria: AuditQuery) -> Iterator[AuditEvent]:
        emitted = 0
        for record in self.read_all():
            if criteria.matches(record):
                yield record
                emitted += 1
                if criteria.limit is not None and emitted >= criteria.limit:
                    return

    def last(self) -> Optional[AuditEvent]:
        with self._lock:
            return self._records[-1] if self._records else None

    def count(self) -> int:
        with self._lock:
            return len(self._records)

    def clear(self) -> None:
        """Test-only. Not part of :class:`AuditStore`, deliberately."""
        with self._lock:
            self._records.clear()


class JsonlAuditStore:
    """Durable append-only store: one JSON record per line.

    Each append opens in append mode, writes one line, flushes, and fsyncs
    before returning. That is slower than buffering and is the correct trade:
    an audit record that is lost in a crash is an audit record that was never
    written, and the whole purpose is evidence that survives.

    A tail cache holds the last record so the runtime can chain without reading
    the file each time. Correctness never depends on the cache -- :meth:`last`
    falls back to reading the file when the cache is cold.
    """

    __slots__ = ("_lock", "_path", "_cached_last", "_cached_count")

    def __init__(self, path: Path) -> None:
        self._lock = threading.RLock()
        self._path = Path(path)
        self._cached_last: Optional[AuditEvent] = None
        self._cached_count: Optional[int] = None
        self._path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def path(self) -> Path:
        return self._path

    def append(self, record: AuditEvent) -> None:
        line = json.dumps(record.to_dict(), separators=(",", ":"), sort_keys=True)
        if "\n" in line:
            raise AuditStorageError("serialized record contains a newline; refusing to append")
        try:
            with self._lock:
                with open(self._path, "a", encoding="utf-8") as handle:
                    handle.write(line + "\n")
                    handle.flush()
                    os.fsync(handle.fileno())
                self._cached_last = record
                if self._cached_count is not None:
                    self._cached_count += 1
        except OSError as exc:
            raise AuditStorageError(f"failed to append audit record: {exc}") from exc

    def read_all(self) -> Iterator[AuditEvent]:
        if not self._path.exists():
            return
        with open(self._path, "r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    yield AuditEvent.from_dict(json.loads(stripped))
                except Exception as exc:  # noqa: BLE001 - any decode failure is corruption
                    raise AuditCorruptionError(
                        f"{self._path.name} line {line_number} is not a decodable audit record: {exc}",
                        line_number=line_number,
                    ) from exc

    def query(self, criteria: AuditQuery) -> Iterator[AuditEvent]:
        emitted = 0
        for record in self.read_all():
            if criteria.matches(record):
                yield record
                emitted += 1
                if criteria.limit is not None and emitted >= criteria.limit:
                    return

    def last(self) -> Optional[AuditEvent]:
        with self._lock:
            if self._cached_last is not None:
                return self._cached_last
        latest: Optional[AuditEvent] = None
        for record in self.read_all():
            latest = record
        with self._lock:
            self._cached_last = latest
        return latest

    def count(self) -> int:
        with self._lock:
            if self._cached_count is not None:
                return self._cached_count
        total = sum(1 for _ in self.read_all())
        with self._lock:
            self._cached_count = total
        return total
