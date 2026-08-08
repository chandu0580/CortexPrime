"""ReviewRecord persistence.

Every method takes an ``ExecutionContext`` first and derives tenancy from it.
``TENANT-REPOSITORY-CONTEXT`` blocks the merge for any repository method without
one, and this repository is not on the grandfathered list -- that list may only
shrink.

In-memory only. ``STATE-NO-NEW-FILE-STORES`` forbids a new JSON-backed store; the
Protocol is the seam for a durable one.

Thread-safe because it has to be: the runtime requests every required lens for a
round at once, and four reviewers working concurrently on one round is the normal
case rather than the exceptional one.
"""

from __future__ import annotations

import threading
from typing import Any, Mapping, Optional, Protocol, Sequence, runtime_checkable

from backend.contracts.storage import StorageBinding, StorageOperation
from backend.contexts.review.domain.errors import DuplicateReview, ReviewNotFound
from backend.contexts.review.domain.identifiers import ReviewId
from backend.contexts.review.domain.record import ReviewRecord
from backend.contexts.review.infrastructure.persistence import from_record, to_record
from backend.platform.storage import RepositoryGuard

__all__ = ["ReviewRepository", "InMemoryReviewRepository", "REVIEW_BINDING"]


REVIEW_BINDING = StorageBinding(
    record_type="ReviewRecord",
    scope_column="tenant_id",
    platform_internal_allowed=True,
)


@runtime_checkable
class ReviewRepository(Protocol):
    """The persistence surface the application layer depends on."""

    def save(self, context: Any, review: ReviewRecord) -> None: ...

    def replace(self, context: Any, review: ReviewRecord) -> None: ...

    def find(self, context: Any, review_id: ReviewId) -> Optional[ReviewRecord]: ...

    def for_work_order(self, context: Any, work_id: str) -> Sequence[ReviewRecord]: ...

    def for_round(
        self, context: Any, work_id: str, round: int
    ) -> Sequence[ReviewRecord]: ...

    def all(self, context: Any) -> Sequence[ReviewRecord]: ...


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


class InMemoryReviewRepository:
    """In-process storage, guarded exactly as a durable one would be."""

    def __init__(self) -> None:
        self._guard = RepositoryGuard(REVIEW_BINDING)
        self._reviews: dict = {}
        self._lock = threading.RLock()

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def save(self, context: Any, review: ReviewRecord) -> None:
        """Store a new review. Refuses to overwrite one that exists."""
        access = self._guard.authorize(StorageOperation.WRITE, context)
        stored = to_record(review, tenant_id=access.tenant_id)
        self._guard.assert_in_scope(_Row(stored), access)

        key = str(review.review_id)
        with self._lock:
            if key in self._reviews:
                raise DuplicateReview(
                    work_id=review.work_id, round=review.round, lens=review.lens.value
                )
            self._reviews[key] = stored

    def replace(self, context: Any, review: ReviewRecord) -> None:
        """Overwrite an existing review in place.

        Named for what it does. An open review legitimately rewrites as findings
        are recorded; collapsing this into an upsert would make an accidental
        overwrite indistinguishable from an intended one.
        """
        access = self._guard.authorize(StorageOperation.WRITE, context)
        stored = to_record(review, tenant_id=access.tenant_id)

        key = str(review.review_id)
        with self._lock:
            if key not in self._reviews:
                raise ReviewNotFound(key)
            self._guard.assert_in_scope(_Row(self._reviews[key]), access)
            self._reviews[key] = stored

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def _visible(self, access) -> list:
        scope = self._guard.scope_filter(access)
        with self._lock:
            reviews = list(self._reviews.values())
        if scope is None:
            return reviews
        column, value = scope
        return [r for r in reviews if r.get(column) == value]

    def find(self, context: Any, review_id: ReviewId) -> Optional[ReviewRecord]:
        access = self._guard.authorize(StorageOperation.READ, context)
        for stored in self._visible(access):
            if stored["review_id"] == str(review_id):
                self._guard.assert_in_scope(_Row(stored), access)
                return from_record(stored)
        return None

    def for_work_order(self, context: Any, work_id: str) -> Sequence[ReviewRecord]:
        access = self._guard.authorize(StorageOperation.READ, context)
        matching = [r for r in self._visible(access) if r["work_id"] == work_id]
        return tuple(
            from_record(r)
            for r in sorted(matching, key=lambda r: (r["round"], r["lens"], r["review_id"]))
        )

    def for_round(self, context: Any, work_id: str, round: int) -> Sequence[ReviewRecord]:
        access = self._guard.authorize(StorageOperation.READ, context)
        matching = [
            r
            for r in self._visible(access)
            if r["work_id"] == work_id and r["round"] == round
        ]
        return tuple(
            from_record(r) for r in sorted(matching, key=lambda r: (r["lens"], r["review_id"]))
        )

    def all(self, context: Any) -> Sequence[ReviewRecord]:
        access = self._guard.authorize(StorageOperation.READ, context)
        return tuple(
            from_record(r)
            for r in sorted(self._visible(access), key=lambda r: r["review_id"])
        )

    # ------------------------------------------------------------------
    # Maintenance
    # ------------------------------------------------------------------

    def clear(self, context: Any) -> int:
        """Remove every review visible to ``context``. Returns the count."""
        access = self._guard.authorize(StorageOperation.DELETE, context)
        scope = self._guard.scope_filter(access)
        with self._lock:
            if scope is None:
                removed = len(self._reviews)
                self._reviews.clear()
                return removed
            column, value = scope
            doomed = [k for k, r in self._reviews.items() if r.get(column) == value]
            for key in doomed:
                del self._reviews[key]
            return len(doomed)

    def __len__(self) -> int:
        with self._lock:
            return len(self._reviews)
