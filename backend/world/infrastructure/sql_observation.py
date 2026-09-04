"""The durable observation repository — append-only over cw_observation.

Append-only by construction (Part K): the class exposes ``record`` and reads,
and issues no UPDATE and no DELETE anywhere. An observation is immutable
evidence; a newer observation is a new row. Idempotency is the unique
constraint on ``identity_digest``: a duplicate delivery collides and is
refused by the database, returned as "already recorded" rather than raised —
at-least-once ingestion, never uncontrolled duplication (Part J), never
exactly-once.

Tenant scope (Part D): reads are tenant-predicated. A read for tenant B never
returns tenant A's observation; the caller's tenant is required and a mismatch
returns nothing (fail closed), it never widens.
"""

from __future__ import annotations

from typing import Any, Optional

import sqlalchemy as sa

from backend.contracts.world import Observation
from backend.database.durable.errors import ConstraintConflict
from backend.database.durable.session import DurableStore
from backend.database.durable.tables import world_observation_table as T

__all__ = ["SqlObservationRepository", "ObservationPersistenceError"]


class ObservationPersistenceError(RuntimeError):
    """An observation could not be persisted (a genuine store failure, not a
    duplicate — duplicates are handled and returned as 'already recorded')."""


class SqlObservationRepository:
    """``ObservationRepository`` over ``cw_observation``."""

    __slots__ = ("_store",)

    def __init__(self, store: DurableStore) -> None:
        if not isinstance(store, DurableStore):
            raise ObservationPersistenceError(
                "the observation repository requires a DurableStore")
        self._store = store

    def record(self, observation: Observation, *, identity_digest: str) -> bool:
        """Insert the observation, or return False if an observation with the
        same identity already exists (idempotent dedupe). Append-only: no
        prior row is ever updated."""
        try:
            with self._store.atomic() as work:
                work.execute(
                    sa.insert(T).values(
                        observation_id=observation.record_id,
                        identity_digest=identity_digest,
                        tenant_id=observation.tenant.tenant_id,
                        source_kind=observation.source.kind.value,
                        source_ref=observation.source.source_ref,
                        subject_ref=observation.subject_ref,
                        predicate=observation.predicate,
                        status=observation.status.value,
                        observed_at=observation.instant.observed_at,
                        retrieved_at=observation.instant.retrieved_at,
                        recorded_at=work.now,
                        record=observation.to_dict(),
                        produced_by=observation.provenance.produced_by,
                        schema_version=type(observation).CONTRACT_VERSION,
                    )
                )
            return True
        except ConstraintConflict:
            # The same external observation delivered twice. The unique
            # constraint on identity_digest is precisely how at-least-once
            # delivery stops being duplicate world state. Not an error.
            return False
        except Exception as exc:  # a real store failure
            raise ObservationPersistenceError(
                f"observation {observation.record_id} was not persisted: "
                f"{type(exc).__name__}") from exc

    # -- reads (tenant-scoped, fail closed) --------------------------------

    def get(self, *, tenant_id: str, observation_id: str) -> Optional[dict[str, Any]]:
        """One observation's record document, only if it belongs to ``tenant_id``.
        A cross-tenant id returns None (fail closed), never another tenant's row."""
        with self._store.atomic() as work:
            row = work.execute(
                sa.select(T.c.record).where(
                    T.c.observation_id == observation_id,
                    T.c.tenant_id == tenant_id,
                )
            ).fetchone()
        return row[0] if row else None

    def get_observation(
        self, *, tenant_id: str, observation_id: str
    ) -> Optional[Observation]:
        """The reconstructed :class:`Observation`, only if it belongs to
        ``tenant_id`` (Part D/E/F: the full round-trip).

        The stored ``record`` document is the observation's own
        ``to_dict()`` envelope, so ``Observation.from_dict`` rebuilds a
        value-equal object — provenance, both instants, the recording time, the
        source and the status all survive PostgreSQL unchanged. Cross-tenant
        access fails closed (returns None), exactly as :meth:`get`."""
        document = self.get(tenant_id=tenant_id, observation_id=observation_id)
        if document is None:
            return None
        return Observation.from_dict(document)

    def list_for_subject(
        self, *, tenant_id: str, subject_ref: str, predicate: str
    ) -> tuple["Observation", ...]:
        """Every observation for a (subject, predicate), tenant-scoped, oldest
        first — the corroboration input (Phase 7.5). A cross-tenant read returns
        nothing (fail closed). Reconstructs full Observation objects from the
        stored documents so corroboration sees source, both times, and value.

        Unlike the fact ledger, the observation ledger keeps *every* observation
        (a second source agreeing is its own row), which is exactly what
        independent-source corroboration needs."""
        from backend.contracts.world import Observation
        with self._store.atomic() as work:
            rows = work.execute(
                sa.select(T.c.record).where(
                    T.c.tenant_id == tenant_id,
                    T.c.subject_ref == subject_ref,
                    T.c.predicate == predicate,
                ).order_by(T.c.observed_at)
            ).fetchall()
        return tuple(Observation.from_dict(r[0]) for r in rows)

    def latest_for_subject(
        self, *, tenant_id: str, subject_ref: str, predicate: str
    ) -> Optional["Observation"]:
        """The most recently *recorded* observation for a (subject, predicate).

        Added for Phase 9.3 (ADR-083), and it is a read — no new table, no new
        column, no new authority. A provider stream's position is recoverable
        from the ledger that already holds it, so the ledger stays the one place
        that knows.

        Ordered by ``recorded_at``, deliberately, not by ``observed_at`` and
        never by the value: ``observed_at`` is the instrument's clock and a
        resourceVersion is opaque text with no order at all. "The last position
        this process durably committed" is a question about when CortexPrime
        wrote, which is exactly what ``recorded_at`` is. ``observation_id`` is
        the tie-break — a ULID, so it is monotonic within a millisecond.

        Tenant-predicated like every read here: another tenant's stream position
        is not visible, and a cross-tenant read returns ``None`` rather than
        widening.
        """
        from backend.contracts.world import Observation
        with self._store.atomic() as work:
            row = work.execute(
                sa.select(T.c.record).where(
                    T.c.tenant_id == tenant_id,
                    T.c.subject_ref == subject_ref,
                    T.c.predicate == predicate,
                ).order_by(T.c.recorded_at.desc(), T.c.observation_id.desc()).limit(1)
            ).fetchone()
        return Observation.from_dict(row[0]) if row is not None else None

    def count_for_subject(self, *, tenant_id: str, subject_ref: str) -> int:
        with self._store.atomic() as work:
            return int(work.execute(
                sa.select(sa.func.count()).select_from(T).where(
                    T.c.tenant_id == tenant_id,
                    T.c.subject_ref == subject_ref,
                )
            ).scalar_one())

    def count_all(self) -> int:
        with self._store.atomic() as work:
            return int(work.execute(
                sa.select(sa.func.count()).select_from(T)).scalar_one())
