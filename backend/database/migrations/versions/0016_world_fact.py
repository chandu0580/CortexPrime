"""World Plane bitemporal fact ledger: deterministic derivation from observations.

Phase 7.3, ADR-065. One new table, nothing altered, dropped or moved.

Why a second World ledger, append-only, versioned
-------------------------------------------------
``cw_observation`` (0015) holds raw evidence. ``cw_fact`` holds *derived* world
claims: the deterministic reconciler folds observations into facts. It is
append-only *version* records — a correction or a world-state change is a NEW
row, never an overwrite — so historical world state stays reconstructable and a
supersession never destroys what it superseded.

Two temporal axes, kept distinct
---------------------------------
``valid_from`` / ``valid_to`` is WORLD/VALID time (when the state was true, from
the grounding observation's ``observed_at``). ``recorded_at`` is KNOWLEDGE/
transaction time (when CortexPrime wrote the version). A value valid_from 09:58
can be recorded_at 10:10; an as-of-valid query returns what was true then, an
as-known query returns what we had recorded then, and neither overwrites the
other. ``valid_to`` is usually NULL (open, "as asserted"); the *effective* end is
derived from succeeding versions at query time, so no prior row is ever mutated.

Identity, not a UUID
--------------------
``semantic_identity`` is a digest over (tenant, subject_ref, predicate): every
version of "deployment/payments spec.replicas" shares it. ``version_digest`` is a
digest over (semantic_identity, value_digest, valid_from) and is unique — the
same observation derived twice collides and is refused. At-least-once derivation
with deterministic identity — NOT exactly-once.

Revision ID: 0016_world_fact
Revises: 0015_world_observation
Create Date: 2026-08-12
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP

revision: str = "0016_world_fact"
down_revision: str | None = "0015_world_observation"
branch_labels = None
depends_on = None

_TS = TIMESTAMP(timezone=True)
_DOC = JSONB().with_variant(sa.JSON(), "sqlite")


def upgrade() -> None:
    op.create_table(
        "cw_fact",
        sa.Column("fact_id", sa.Text(), primary_key=True),
        sa.Column("version_digest", sa.String(128), nullable=False),
        sa.Column("semantic_identity", sa.String(128), nullable=False),
        sa.Column("tenant_id", sa.String(128), nullable=False),
        sa.Column("subject_ref", sa.Text(), nullable=False),
        sa.Column("predicate", sa.Text(), nullable=False),
        sa.Column("value_digest", sa.String(128), nullable=False),
        sa.Column("valid_from", _TS, nullable=False),
        sa.Column("valid_to", _TS, nullable=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("authority", sa.String(32), nullable=False),
        sa.Column("recorded_at", _TS, nullable=False),
        sa.Column("record", _DOC, nullable=False),
        sa.Column("produced_by", sa.Text(), nullable=False),
        sa.Column("observation_ref", sa.Text(), nullable=False),
        sa.Column("parent_claim_ref", sa.Text(), nullable=True),
        sa.Column("schema_version", sa.Integer(), nullable=False),
    )
    op.create_unique_constraint(
        "uq_cw_fact_version", "cw_fact", ["version_digest"])
    op.create_index(
        "ix_cw_fact_identity", "cw_fact", ["tenant_id", "semantic_identity"])
    op.create_index(
        "ix_cw_fact_recorded_at", "cw_fact", ["recorded_at"])


def downgrade() -> None:
    op.drop_index("ix_cw_fact_recorded_at", table_name="cw_fact")
    op.drop_index("ix_cw_fact_identity", table_name="cw_fact")
    op.drop_constraint("uq_cw_fact_version", "cw_fact", type_="unique")
    op.drop_table("cw_fact")
