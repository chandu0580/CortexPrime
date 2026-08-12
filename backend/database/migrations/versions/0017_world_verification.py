"""Assurance Plane verification ledger: independent, append-only decisions.

Phase 7.7, ADR-069. One new table, nothing altered, dropped or moved.

Why a durable ledger (and why this one is not a derived projection)
-------------------------------------------------------------------
Corroboration and belief are derived projections — they reconstruct from the
observation/fact ledgers. A *verification* cannot: it adjudicates a claim
(ephemeral model output) against the world at a knowledge time, and that decision
is an externally-meaningful historical record governance and humans rely on.
Nothing in the World ledgers records "the platform verified claim X at time T",
so it is persisted. Append-only: a re-check is a new row, never an overwrite.

Honesty guarantees carried in the schema
-----------------------------------------
``verdict`` is SUPPORTED / UNSUPPORTED / INSUFFICIENT_EVIDENCE — never FALSE,
never "timeout = success". ``verifier_reasoning_path`` is recorded distinct from
``producer_reasoning_path`` so independence is auditable rather than assumed.
Evidence lives as references in the document; no credential material is stored.
Idempotency is the unique constraint on ``identity_digest`` — at-least-once,
deterministic identity, NOT exactly-once.

Revision ID: 0017_world_verification
Revises: 0016_world_fact
Create Date: 2026-08-12
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP

revision: str = "0017_world_verification"
down_revision: str | None = "0016_world_fact"
branch_labels = None
depends_on = None

_TS = TIMESTAMP(timezone=True)
_DOC = JSONB().with_variant(sa.JSON(), "sqlite")


def upgrade() -> None:
    op.create_table(
        "cw_verification",
        sa.Column("verification_id", sa.Text(), primary_key=True),
        sa.Column("identity_digest", sa.String(128), nullable=False),
        sa.Column("tenant_id", sa.String(128), nullable=False),
        sa.Column("subject_ref", sa.Text(), nullable=False),
        sa.Column("predicate", sa.Text(), nullable=False),
        sa.Column("procedure_ref", sa.Text(), nullable=False),
        sa.Column("verdict", sa.String(32), nullable=False),
        sa.Column("verifier_id", sa.Text(), nullable=False),
        sa.Column("verifier_reasoning_path", sa.Text(), nullable=False),
        sa.Column("producer_reasoning_path", sa.Text(), nullable=False),
        sa.Column("verified_at", _TS, nullable=False),
        sa.Column("recorded_at", _TS, nullable=False),
        sa.Column("record", _DOC, nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
    )
    op.create_unique_constraint(
        "uq_cw_verification_identity", "cw_verification", ["identity_digest"])
    op.create_index(
        "ix_cw_verification_subject", "cw_verification", ["tenant_id", "subject_ref"])
    op.create_index(
        "ix_cw_verification_recorded_at", "cw_verification", ["recorded_at"])


def downgrade() -> None:
    op.drop_index("ix_cw_verification_recorded_at", table_name="cw_verification")
    op.drop_index("ix_cw_verification_subject", table_name="cw_verification")
    op.drop_constraint("uq_cw_verification_identity", "cw_verification", type_="unique")
    op.drop_table("cw_verification")
