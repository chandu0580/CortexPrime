"""The durable reasoning repository — append-only over cw_reasoning.

Append-only by construction: ``record`` inserts, and there is no update or
delete — a reasoning record is immutable (a revision is a new row). Idempotency
is the unique constraint on ``identity_digest`` (at-least-once, deterministic
identity, never exactly-once). Reads are tenant-predicated and fail closed.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

import sqlalchemy as sa

from backend.database.durable.errors import ConstraintConflict
from backend.database.durable.session import DurableStore
from backend.database.durable.tables import world_reasoning_table as T
from backend.world.application.reasoning import ReasoningKind, ReasoningRecord

__all__ = ["SqlReasoningRepository", "ReasoningPersistenceError"]


class ReasoningPersistenceError(RuntimeError):
    """A reasoning record could not be persisted (a genuine store failure, not a
    duplicate — duplicates are handled and returned as 'already recorded')."""


def _to_record(row) -> ReasoningRecord:
    return ReasoningRecord(
        reasoning_id=row.reasoning_id, tenant_id=row.tenant_id,
        kind=ReasoningKind(row.kind), subject_ref=row.subject_ref,
        predicate=row.predicate, record=row.record, refs=row.refs,
        recorded_at=row.recorded_at)


class SqlReasoningRepository:
    """``ReasoningRepository`` over ``cw_reasoning``."""

    __slots__ = ("_store",)

    def __init__(self, store: DurableStore) -> None:
        if not isinstance(store, DurableStore):
            raise ReasoningPersistenceError(
                "the reasoning repository requires a DurableStore")
        self._store = store

    def record(
        self, *, reasoning_id: str, identity_digest: str, tenant_id: str,
        kind: str, subject_ref: str, predicate: Optional[str], record: dict,
        refs: dict, recorded_at: datetime,
    ) -> bool:
        try:
            with self._store.atomic() as work:
                work.execute(
                    sa.insert(T).values(
                        reasoning_id=reasoning_id, identity_digest=identity_digest,
                        tenant_id=tenant_id, kind=kind, subject_ref=subject_ref,
                        predicate=predicate, record=record, refs=refs,
                        recorded_at=recorded_at, schema_version=1,
                    )
                )
            return True
        except ConstraintConflict:
            return False
        except Exception as exc:  # a real store failure
            raise ReasoningPersistenceError(
                f"reasoning record {reasoning_id} was not persisted: "
                f"{type(exc).__name__}") from exc

    # -- reads (tenant-scoped, fail closed) --------------------------------

    def get(self, *, tenant_id: str, reasoning_id: str) -> Optional[ReasoningRecord]:
        with self._store.atomic() as work:
            row = work.execute(
                sa.select(T).where(
                    T.c.reasoning_id == reasoning_id, T.c.tenant_id == tenant_id)
            ).fetchone()
        return _to_record(row) if row else None

    def list_for_subject(
        self, *, tenant_id: str, subject_ref: str
    ) -> tuple[ReasoningRecord, ...]:
        with self._store.atomic() as work:
            rows = work.execute(
                sa.select(T).where(
                    T.c.tenant_id == tenant_id, T.c.subject_ref == subject_ref
                ).order_by(T.c.recorded_at)
            ).fetchall()
        return tuple(_to_record(r) for r in rows)

    def count_all(self) -> int:
        with self._store.atomic() as work:
            return int(work.execute(
                sa.select(sa.func.count()).select_from(T)).scalar_one())
