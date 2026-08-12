"""The durable investigation repository — append-only event log over cw_investigation.

Append-only by construction: ``append`` inserts one immutable event; there is no
update or delete. ``latest_state`` returns the max-seq snapshot for an
investigation, tenant-scoped and fail-closed. Idempotency + optimistic
concurrency is the unique constraint on ``identity_digest`` (one event per
(tenant, investigation, seq)): a duplicate/racing append collides and is returned
as "already recorded" rather than raised.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

import sqlalchemy as sa

from backend.database.durable.errors import ConstraintConflict
from backend.database.durable.session import DurableStore
from backend.database.durable.tables import world_investigation_table as T

__all__ = ["SqlInvestigationRepository", "InvestigationPersistenceError"]


class InvestigationPersistenceError(RuntimeError):
    """An investigation event could not be persisted (a genuine store failure,
    not a duplicate — duplicates are handled and returned as 'already recorded')."""


class SqlInvestigationRepository:
    """``InvestigationRepository`` over ``cw_investigation``."""

    __slots__ = ("_store",)

    def __init__(self, store: DurableStore) -> None:
        if not isinstance(store, DurableStore):
            raise InvestigationPersistenceError(
                "the investigation repository requires a DurableStore")
        self._store = store

    def append(
        self, *, event_id: str, identity_digest: str, investigation_id: str,
        tenant_id: str, incident_ref: str, seq: int, event_kind: str,
        from_status: Optional[str], to_status: str, autonomy_level: str,
        state: dict, payload: dict, recorded_at: datetime,
    ) -> bool:
        """Append one event; False if this (tenant, investigation, seq) already
        exists (optimistic-concurrency dedupe). Append-only."""
        try:
            with self._store.atomic() as work:
                work.execute(
                    sa.insert(T).values(
                        event_id=event_id, identity_digest=identity_digest,
                        investigation_id=investigation_id, tenant_id=tenant_id,
                        incident_ref=incident_ref, seq=seq, event_kind=event_kind,
                        from_status=from_status, to_status=to_status,
                        autonomy_level=autonomy_level, state=state, payload=payload,
                        recorded_at=recorded_at, schema_version=1)
                )
            return True
        except ConstraintConflict:
            return False
        except Exception as exc:  # a real store failure
            raise InvestigationPersistenceError(
                f"investigation event {event_id} was not persisted: "
                f"{type(exc).__name__}") from exc

    # -- reads (tenant-scoped, fail closed) --------------------------------

    def latest_state(
        self, *, tenant_id: str, investigation_id: str
    ) -> Optional[dict]:
        """The latest committed aggregate snapshot for this investigation, only if
        it belongs to ``tenant_id`` (cross-tenant returns None, fail closed)."""
        with self._store.atomic() as work:
            row = work.execute(
                sa.select(T.c.state).where(
                    T.c.tenant_id == tenant_id,
                    T.c.investigation_id == investigation_id,
                ).order_by(T.c.seq.desc()).limit(1)
            ).fetchone()
        return row[0] if row else None

    def event_count(self, *, tenant_id: str, investigation_id: str) -> int:
        with self._store.atomic() as work:
            return int(work.execute(
                sa.select(sa.func.count()).select_from(T).where(
                    T.c.tenant_id == tenant_id,
                    T.c.investigation_id == investigation_id,
                )).scalar_one())

    def count_all(self) -> int:
        with self._store.atomic() as work:
            return int(work.execute(
                sa.select(sa.func.count()).select_from(T)).scalar_one())
