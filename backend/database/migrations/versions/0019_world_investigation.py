"""Intelligence Plane investigation ledger: event-sourced, append-only workflow.

Phase 8.1, ADR-072. One new table, nothing altered, dropped or moved.

Why persist (and why event-sourced)
------------------------------------
An investigation is a stateful workflow — a status machine plus a differential
(hypothesis set), open questions, referenced evidence, and a checkpoint. That
loop position cannot be reconstructed from the World ledgers (which hold
evidence/facts/verifications, not the investigation's phase), so it is persisted.
It is event-sourced: each row is one immutable event carrying the full new
aggregate snapshot; the latest committed snapshot (max ``seq`` per investigation)
is the authoritative current state. Crash recovery restores that snapshot — it
never fabricates progress, never turns UNKNOWN into success, never skips
verification.

Guarantees
----------
Append-only (no row updated or deleted); tenant-scoped (``tenant_id NOT NULL``,
reads fail closed); provenance/reference-bearing; secret-free (the service runs
the field-aware firewall before any row is written; no credentials, no
chain-of-thought). Idempotent + optimistic concurrency via the unique
``identity_digest`` over (tenant, investigation, seq). At-least-once, NOT
exactly-once.

Revision ID: 0019_world_investigation
Revises: 0018_world_reasoning
Create Date: 2026-08-12
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP

revision: str = "0019_world_investigation"
down_revision: str | None = "0018_world_reasoning"
branch_labels = None
depends_on = None

_TS = TIMESTAMP(timezone=True)
_DOC = JSONB().with_variant(sa.JSON(), "sqlite")


def upgrade() -> None:
    op.create_table(
        "cw_investigation",
        sa.Column("event_id", sa.Text(), primary_key=True),
        sa.Column("identity_digest", sa.String(128), nullable=False),
        sa.Column("investigation_id", sa.Text(), nullable=False),
        sa.Column("tenant_id", sa.String(128), nullable=False),
        sa.Column("incident_ref", sa.Text(), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("event_kind", sa.String(32), nullable=False),
        sa.Column("from_status", sa.String(32), nullable=True),
        sa.Column("to_status", sa.String(32), nullable=False),
        sa.Column("autonomy_level", sa.String(32), nullable=False),
        sa.Column("state", _DOC, nullable=False),
        sa.Column("payload", _DOC, nullable=False),
        sa.Column("recorded_at", _TS, nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
    )
    op.create_unique_constraint(
        "uq_cw_investigation_identity", "cw_investigation", ["identity_digest"])
    op.create_index("ix_cw_investigation_seq", "cw_investigation",
                    ["tenant_id", "investigation_id", "seq"])
    op.create_index("ix_cw_investigation_incident", "cw_investigation",
                    ["tenant_id", "incident_ref"])
    op.create_index("ix_cw_investigation_recorded_at", "cw_investigation", ["recorded_at"])


def downgrade() -> None:
    op.drop_index("ix_cw_investigation_recorded_at", table_name="cw_investigation")
    op.drop_index("ix_cw_investigation_incident", table_name="cw_investigation")
    op.drop_index("ix_cw_investigation_seq", table_name="cw_investigation")
    op.drop_constraint("uq_cw_investigation_identity", "cw_investigation", type_="unique")
    op.drop_table("cw_investigation")
