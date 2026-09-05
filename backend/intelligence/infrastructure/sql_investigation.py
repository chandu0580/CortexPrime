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

    def latest_state_as_known(
        self, *, tenant_id: str, investigation_id: str, known_at: datetime
    ) -> Optional[dict]:
        """The latest committed snapshot whose knowledge time is at or before
        ``known_at`` — temporal safety (Part K): reconstruct WHAT THE INVESTIGATOR
        KNEW at a past time, never leaking events recorded later. Tenant-scoped."""
        with self._store.atomic() as work:
            row = work.execute(
                sa.select(T.c.state).where(
                    T.c.tenant_id == tenant_id,
                    T.c.investigation_id == investigation_id,
                    T.c.recorded_at <= known_at,
                ).order_by(T.c.seq.desc()).limit(1)
            ).fetchone()
        return row[0] if row else None

    def list_terminal(
        self, *, tenant_id: str, limit: int = 200
    ) -> tuple[dict, ...]:
        """The latest snapshots of TERMINAL investigations for a tenant, newest
        first — the reusable experience source (Part D/G). Tenant-scoped in SQL (a
        stronger boundary than application filtering, Part J). Read-only."""
        terminal = ("completed", "failed", "abandoned")
        with self._store.atomic() as work:
            latest = sa.select(
                T.c.investigation_id, sa.func.max(T.c.seq).label("mseq")
            ).where(T.c.tenant_id == tenant_id).group_by(T.c.investigation_id).subquery()
            rows = work.execute(
                sa.select(T.c.state).select_from(T).join(
                    latest, sa.and_(T.c.investigation_id == latest.c.investigation_id,
                                    T.c.seq == latest.c.mseq)
                ).where(
                    T.c.tenant_id == tenant_id, T.c.to_status.in_(terminal)
                ).order_by(T.c.recorded_at.desc()).limit(limit)
            ).fetchall()
        return tuple(r[0] for r in rows)

    def list_active(
        self, *, tenant_id: str, limit: int = 200
    ) -> tuple[dict, ...]:
        """The latest snapshots of NON-terminal investigations for a tenant.

        The exact query ``list_terminal`` runs, with the status filter inverted.
        It exists because an incident workspace that can only list finished
        investigations is a report archive: the investigation a human most needs
        to see is the one still running.

        Tenant-scoped in SQL for the same reason ``list_terminal`` is -- a WHERE
        clause the database enforces is a stronger boundary than a filter the
        application remembers to apply. Read-only.
        """
        terminal = ("completed", "failed", "abandoned")
        with self._store.atomic() as work:
            latest = sa.select(
                T.c.investigation_id, sa.func.max(T.c.seq).label("mseq")
            ).where(T.c.tenant_id == tenant_id).group_by(T.c.investigation_id).subquery()
            rows = work.execute(
                sa.select(T.c.state).select_from(T).join(
                    latest, sa.and_(T.c.investigation_id == latest.c.investigation_id,
                                    T.c.seq == latest.c.mseq)
                ).where(
                    T.c.tenant_id == tenant_id, T.c.to_status.notin_(terminal)
                ).order_by(T.c.recorded_at.desc()).limit(limit)
            ).fetchall()
        return tuple(r[0] for r in rows)

    def list_events(
        self, *, tenant_id: str, investigation_id: str, limit: int = 500
    ) -> tuple[dict, ...]:
        """Every recorded event for one investigation, oldest first.

        The ledger is already append-only and already stores each transition, so
        a timeline is a read of what happened -- not a reconstruction, and never
        an inference about what probably happened between two events.

        ``recorded_at`` is returned under its own name. It is when CortexPrime
        committed the event, which is NOT when the world changed; a consumer that
        conflates the two would be inventing an event time, so this method does
        not rename it to anything friendlier.
        """
        with self._store.atomic() as work:
            rows = work.execute(
                sa.select(
                    T.c.seq, T.c.event_kind, T.c.from_status, T.c.to_status,
                    T.c.autonomy_level, T.c.recorded_at, T.c.payload,
                ).where(
                    T.c.tenant_id == tenant_id,
                    T.c.investigation_id == investigation_id,
                ).order_by(T.c.seq.asc()).limit(limit)
            ).fetchall()
        return tuple(
            {
                "seq": int(r[0]),
                "event_kind": r[1],
                "from_status": r[2],
                "to_status": r[3],
                "autonomy_level": r[4],
                "recorded_at": r[5],
                "payload": r[6] if isinstance(r[6], dict) else {},
            }
            for r in rows
        )

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
