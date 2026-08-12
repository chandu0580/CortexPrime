"""Durable reasoning trail: the non-reconstructable, model-authored artifacts.

Phase 7.8, ADR-070. One new table, nothing altered, dropped or moved.

Why persist (and why only these)
--------------------------------
Observations and facts are durable; beliefs and world queries are derived
projections that reconstruct from them; verifications live in cw_verification.
What remains non-reconstructable is the *model-authored* reasoning: a grounded
hypothesis, a prediction, and the evaluation that pairs a prediction with a real
outcome (the calibration payload — expected proposition, horizon, actual outcome,
result, evidence refs). Those cannot be re-derived from the World ledgers and are
externally meaningful, so they are persisted here — and only they. Append-only: a
revised hypothesis is a new row, never an overwrite.

Guarantees
----------
Immutable, tenant-scoped, provenance-bearing (``refs`` carries the graph edges),
idempotent (unique ``identity_digest`` — at-least-once, NOT exactly-once), and
secret-free (the ingestion service runs the field-aware firewall before a row is
written). No credential material ever enters the reasoning ledger.

Revision ID: 0018_world_reasoning
Revises: 0017_world_verification
Create Date: 2026-08-12
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP

revision: str = "0018_world_reasoning"
down_revision: str | None = "0017_world_verification"
branch_labels = None
depends_on = None

_TS = TIMESTAMP(timezone=True)
_DOC = JSONB().with_variant(sa.JSON(), "sqlite")


def upgrade() -> None:
    op.create_table(
        "cw_reasoning",
        sa.Column("reasoning_id", sa.Text(), primary_key=True),
        sa.Column("identity_digest", sa.String(128), nullable=False),
        sa.Column("tenant_id", sa.String(128), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("subject_ref", sa.Text(), nullable=False),
        sa.Column("predicate", sa.Text(), nullable=True),
        sa.Column("record", _DOC, nullable=False),
        sa.Column("refs", _DOC, nullable=False),
        sa.Column("recorded_at", _TS, nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
    )
    op.create_unique_constraint(
        "uq_cw_reasoning_identity", "cw_reasoning", ["identity_digest"])
    op.create_index("ix_cw_reasoning_subject", "cw_reasoning", ["tenant_id", "subject_ref"])
    op.create_index("ix_cw_reasoning_kind", "cw_reasoning", ["tenant_id", "kind"])
    op.create_index("ix_cw_reasoning_recorded_at", "cw_reasoning", ["recorded_at"])


def downgrade() -> None:
    op.drop_index("ix_cw_reasoning_recorded_at", table_name="cw_reasoning")
    op.drop_index("ix_cw_reasoning_kind", table_name="cw_reasoning")
    op.drop_index("ix_cw_reasoning_subject", table_name="cw_reasoning")
    op.drop_constraint("uq_cw_reasoning_identity", "cw_reasoning", type_="unique")
    op.drop_table("cw_reasoning")
