"""The durable verification repository — append-only over cw_verification.

Append-only by construction: ``record`` inserts, and there is no update or
delete — a verification is an immutable historical decision; a re-check is a new
row. Idempotency is the unique constraint on ``identity_digest`` (at-least-once,
deterministic identity, never exactly-once). Reads are tenant-predicated and fail
closed.
"""

from __future__ import annotations

from typing import Optional

import sqlalchemy as sa

from backend.contracts.world import WorldVerification
from backend.database.durable.errors import ConstraintConflict
from backend.database.durable.session import DurableStore
from backend.database.durable.tables import world_verification_table as T

__all__ = ["SqlVerificationRepository", "VerificationPersistenceError"]


class VerificationPersistenceError(RuntimeError):
    """A verification could not be persisted (a genuine store failure, not a
    duplicate — duplicates are handled and returned as 'already recorded')."""


class SqlVerificationRepository:
    """``VerificationRepository`` over ``cw_verification``."""

    __slots__ = ("_store",)

    def __init__(self, store: DurableStore) -> None:
        if not isinstance(store, DurableStore):
            raise VerificationPersistenceError(
                "the verification repository requires a DurableStore")
        self._store = store

    def record(
        self,
        verification: WorldVerification,
        *,
        identity_digest: str,
        predicate: str,
        producer_reasoning_path: str,
        verified_at,
    ) -> bool:
        """Insert the verification, or return False if one with the same identity
        already exists (idempotent dedupe). Append-only."""
        try:
            with self._store.atomic() as work:
                work.execute(
                    sa.insert(T).values(
                        verification_id=verification.record_id,
                        identity_digest=identity_digest,
                        tenant_id=verification.tenant.tenant_id,
                        subject_ref=verification.subject_ref,
                        predicate=predicate,
                        procedure_ref=verification.procedure_ref,
                        verdict=verification.verdict.value,
                        verifier_id=verification.verifier.verifier_id,
                        verifier_reasoning_path=verification.verifier.reasoning_path_id,
                        producer_reasoning_path=producer_reasoning_path,
                        verified_at=verified_at,
                        recorded_at=work.now,
                        record=verification.to_dict(),
                        schema_version=type(verification).CONTRACT_VERSION,
                    )
                )
            return True
        except ConstraintConflict:
            return False
        except Exception as exc:  # a real store failure
            raise VerificationPersistenceError(
                f"verification {verification.record_id} was not persisted: "
                f"{type(exc).__name__}") from exc

    # -- reads (tenant-scoped, fail closed) --------------------------------

    def get(self, *, tenant_id: str, verification_id: str) -> Optional[WorldVerification]:
        """One verification, reconstructed, only if it belongs to ``tenant_id``.
        A cross-tenant id returns None (fail closed)."""
        with self._store.atomic() as work:
            row = work.execute(
                sa.select(T.c.record).where(
                    T.c.verification_id == verification_id,
                    T.c.tenant_id == tenant_id,
                )
            ).fetchone()
        return WorldVerification.from_dict(row[0]) if row else None

    def list_for_subject(
        self, *, tenant_id: str, subject_ref: str, predicate: str
    ) -> tuple[WorldVerification, ...]:
        """Every verification for a (subject, predicate), tenant-scoped, oldest
        first — the assurance history."""
        with self._store.atomic() as work:
            rows = work.execute(
                sa.select(T.c.record).where(
                    T.c.tenant_id == tenant_id,
                    T.c.subject_ref == subject_ref,
                    T.c.predicate == predicate,
                ).order_by(T.c.recorded_at)
            ).fetchall()
        return tuple(WorldVerification.from_dict(r[0]) for r in rows)

    def count_all(self) -> int:
        with self._store.atomic() as work:
            return int(work.execute(
                sa.select(sa.func.count()).select_from(T)).scalar_one())
