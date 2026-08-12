"""The durable fact repository — append-only bitemporal versions over cw_fact.

Append-only by construction (Part 7/13): the class exposes ``record`` and reads,
and issues no UPDATE and no DELETE anywhere. A correction or a world-state change
is a new version row, never an overwrite — historical world state stays
reconstructable. Idempotency is the unique constraint on ``version_digest``: the
same observation derived twice collides and is refused, returned as "already
recorded" rather than raised (at-least-once, deterministic identity, never
exactly-once).

Tenant scope (Part 17): reads are tenant-predicated. A read for tenant B never
returns tenant A's fact versions; the caller's tenant is required and a mismatch
returns nothing (fail closed).
"""

from __future__ import annotations

from typing import Optional

import sqlalchemy as sa

from backend.contracts.world import EpistemicStatus, Fact
from backend.database.durable.errors import ConstraintConflict
from backend.database.durable.session import DurableStore
from backend.database.durable.tables import world_fact_table as T
from backend.world.application.bitemporal import FactVersion

__all__ = ["SqlFactRepository", "FactPersistenceError"]


class FactPersistenceError(RuntimeError):
    """A fact version could not be persisted (a genuine store failure, not a
    duplicate — duplicates are handled and returned as 'already recorded')."""


def _to_version(row) -> FactVersion:
    """Build the projection-facing :class:`FactVersion` from a cw_fact row.

    The structured value lives in the ``record`` document (the fact's own
    ``to_dict``); the promoted columns carry identity, the two temporal axes, and
    lineage. The value is read from the document so it survives JSONB unchanged.
    """
    document = row.record
    return FactVersion(
        fact_id=row.fact_id,
        semantic_identity=row.semantic_identity,
        tenant_id=row.tenant_id,
        subject_ref=row.subject_ref,
        predicate=row.predicate,
        value=document.get("value"),
        value_digest=row.value_digest,
        valid_from=row.valid_from,
        recorded_at=row.recorded_at,
        status=EpistemicStatus(row.status),
        authority=row.authority,
        observation_ref=row.observation_ref,
        parent_claim_ref=row.parent_claim_ref,
    )


class SqlFactRepository:
    """``FactRepository`` over ``cw_fact``."""

    __slots__ = ("_store",)

    def __init__(self, store: DurableStore) -> None:
        if not isinstance(store, DurableStore):
            raise FactPersistenceError(
                "the fact repository requires a DurableStore")
        self._store = store

    def record(
        self,
        fact: Fact,
        *,
        version_digest: str,
        semantic_identity: str,
        value_digest: str,
    ) -> bool:
        """Insert the fact version, or return False if a version with the same
        identity already exists (idempotent dedupe). Append-only: no prior row is
        ever updated."""
        validity = fact.validity
        try:
            with self._store.atomic() as work:
                work.execute(
                    sa.insert(T).values(
                        fact_id=fact.record_id,
                        version_digest=version_digest,
                        semantic_identity=semantic_identity,
                        tenant_id=fact.tenant.tenant_id,
                        subject_ref=fact.subject_ref,
                        predicate=fact.predicate,
                        value_digest=value_digest,
                        valid_from=validity.valid_from,
                        valid_to=validity.valid_to,
                        status=fact.status.value,
                        authority=fact.authority.value,
                        recorded_at=fact.recorded_at,
                        record=fact.to_dict(),
                        produced_by=fact.provenance.produced_by,
                        observation_ref=fact.provenance.observation_ref,
                        parent_claim_ref=fact.provenance.parent_claim_ref,
                        schema_version=type(fact).CONTRACT_VERSION,
                    )
                )
            return True
        except ConstraintConflict:
            # The same fact version derived twice. The unique constraint on
            # version_digest is how at-least-once derivation stops being
            # duplicate world state. Not an error.
            return False
        except Exception as exc:  # a real store failure
            raise FactPersistenceError(
                f"fact {fact.record_id} was not persisted: "
                f"{type(exc).__name__}") from exc

    # -- reads (tenant-scoped, fail closed) --------------------------------

    def versions_for(
        self, *, tenant_id: str, semantic_identity: str
    ) -> tuple[FactVersion, ...]:
        """Every version for a semantic identity, tenant-scoped. A cross-tenant
        identity returns nothing (fail closed), never another tenant's rows."""
        with self._store.atomic() as work:
            rows = work.execute(
                sa.select(T).where(
                    T.c.tenant_id == tenant_id,
                    T.c.semantic_identity == semantic_identity,
                )
            ).fetchall()
        return tuple(_to_version(r) for r in rows)

    def get(self, *, tenant_id: str, fact_id: str) -> Optional[Fact]:
        """One fact version, reconstructed, only if it belongs to ``tenant_id``.
        A cross-tenant id returns None (fail closed)."""
        with self._store.atomic() as work:
            row = work.execute(
                sa.select(T.c.record).where(
                    T.c.fact_id == fact_id,
                    T.c.tenant_id == tenant_id,
                )
            ).fetchone()
        return Fact.from_dict(row[0]) if row else None

    def count_all(self) -> int:
        with self._store.atomic() as work:
            return int(work.execute(
                sa.select(sa.func.count()).select_from(T)).scalar_one())
