"""World Plane observation ledger: the first durable epistemic store.

Phase 7.2, ADR-064. One new table, nothing altered, dropped or moved.

Why cw_ and not cp_
--------------------
The ``cp_*`` tables are the platform/execution fabric. ``cw_observation`` is the
World Plane — a separate ledger the execution fabric neither reads nor writes.
It follows the same durable template (tenant NOT NULL, application-clock
timestamps, digest identity, append-only) because that template is the one
correct one in the repository (Phase 7.0), but it is a distinct concern:
what CortexPrime *knows*, not what it *did*.

Why append-only, and how this migration enforces it
----------------------------------------------------
An observation is immutable evidence: a newer observation is a new row, never
an overwrite (the destructive-upsert pattern the Phase 7.0 audit found in the
V1 infra JSON is exactly what this replaces). This schema offers no state a
mutation would maintain — no status-that-changes, no updated_at — and the
repository exposes no UPDATE or DELETE. The unique constraint on
``identity_digest`` is the idempotency mechanism: a duplicate delivery of the
same external observation collides and is refused, so at-least-once ingestion
never becomes uncontrolled duplicate world state. This is NOT exactly-once.

Why observed_at is separate from recorded_at
---------------------------------------------
``observed_at`` is when the world was in the observed state, as the instrument
reported it. ``recorded_at`` is when CortexPrime wrote the row. ``retrieved_at``
is when the instrument was queried. A deployment that changed at 10:00,
retrieved at 10:04, recorded at 10:05 stores three distinct times — collapsing
them is the defect this ledger exists to fix.

No secret material
--------------------
The ingestion boundary runs a field-aware secret firewall over every value
before it reaches this table; a value carrying credential material is refused,
never stored. Provenance is references only.

Revision ID: 0015_world_observation
Revises: 0014_harness_trace
Create Date: 2026-08-11
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP

revision: str = "0015_world_observation"
down_revision: str | None = "0014_harness_trace"
branch_labels = None
depends_on = None

_TS = TIMESTAMP(timezone=True)
_DOC = JSONB().with_variant(sa.JSON(), "sqlite")


def upgrade() -> None:
    op.create_table(
        "cw_observation",
        sa.Column("observation_id", sa.Text(), primary_key=True),
        sa.Column("identity_digest", sa.String(128), nullable=False),
        sa.Column("tenant_id", sa.String(128), nullable=False),
        sa.Column("source_kind", sa.String(32), nullable=False),
        sa.Column("source_ref", sa.Text(), nullable=False),
        sa.Column("subject_ref", sa.Text(), nullable=False),
        sa.Column("predicate", sa.Text(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("observed_at", _TS, nullable=False),
        sa.Column("retrieved_at", _TS, nullable=False),
        sa.Column("recorded_at", _TS, nullable=False),
        sa.Column("record", _DOC, nullable=False),
        sa.Column("produced_by", sa.Text(), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
    )
    op.create_unique_constraint(
        "uq_cw_observation_identity", "cw_observation", ["identity_digest"])
    op.create_index(
        "ix_cw_observation_tenant_subject", "cw_observation",
        ["tenant_id", "subject_ref"])
    op.create_index(
        "ix_cw_observation_observed_at", "cw_observation", ["observed_at"])
    op.create_index(
        "ix_cw_observation_source", "cw_observation", ["source_kind", "source_ref"])


def downgrade() -> None:
    op.drop_index("ix_cw_observation_source", table_name="cw_observation")
    op.drop_index("ix_cw_observation_observed_at", table_name="cw_observation")
    op.drop_index("ix_cw_observation_tenant_subject", table_name="cw_observation")
    op.drop_constraint("uq_cw_observation_identity", "cw_observation", type_="unique")
    op.drop_table("cw_observation")
