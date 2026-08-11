"""Distributed coordination — durable work queue and fenced leadership.

Phase 5.2. Two tables on top of the Phase 5.1 foundation.

**Purely additive.** No column altered, no table dropped, no data moved. Nothing
existing reads or writes either table until a deployment wires the durable queue
and the leadership store at the composition root, so applying this changes no
behaviour — the same discipline as 0010, and for the same reason: a migration
that both created a schema and switched the system onto it would make two changes
one irreversible step.

Why the fencing token lives on a long-lived row
-------------------------------------------------
``cp_leadership`` holds **one row per role, forever**. Leaders come and go; the
row does not. That is what makes ``fencing_token`` monotonic — it is incremented
in place on each acquisition, so it never repeats and never goes backwards, which
a UUID (no order) and a timestamp (two clocks disagree) both fail to provide.

Deleting a leadership row would reset the counter and let a stalled process from
before the deletion pass a fence check it should fail. So nothing deletes them,
and the downgrade below is the only thing that ever removes one.

Revision ID: 0011_distributed_coordination
Revises: 0010_durable_state_foundation
Create Date: 2026-08-08
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP

revision: str = "0011_distributed_coordination"
down_revision: str | None = "0010_durable_state_foundation"
branch_labels = None
depends_on = None

#: Application clock, UTC, as in 0010. No ``server_default NOW()`` on anything
#: this platform reasons about: a row stamped by the database and a decision made
#: by the application would be two clocks inside one authority calculation.
_TS = TIMESTAMP(timezone=True)


def upgrade() -> None:
    # ------------------------------------------------------------------
    # Work queue — availability, never state
    # ------------------------------------------------------------------
    op.create_table(
        "cp_queue",
        # One row per (execution, node). The primary key is what makes enqueuing
        # the same node twice a no-op rather than a duplicate: two dispatchers
        # deciding a node is ready both INSERT, and the second collides.
        sa.Column("execution_id", sa.String(64), primary_key=True),
        sa.Column("node_id", sa.String(128), primary_key=True),
        sa.Column("tenant_id", sa.String(128), nullable=False),
        # References, never authority. What may actually run is re-derived from
        # the aggregate, the binding and the authorization on every claim.
        sa.Column("workflow_id", sa.String(128), nullable=True),
        sa.Column("workflow_digest", sa.String(128), nullable=True),
        sa.Column("worker_kind", sa.String(32), nullable=False),
        sa.Column("attempt_id", sa.String(64), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=False),
        # A planned retry is enqueued with a future availability rather than
        # held in memory until its backoff elapses -- memory does not survive
        # the restart that made the retry necessary.
        sa.Column("available_at", _TS, nullable=False),
        sa.Column("enqueued_at", _TS, nullable=False),
        # The deterministic tiebreak. Unique, so two items with equal priority
        # and equal availability still have exactly one order.
        sa.Column("sequence", sa.BigInteger(), nullable=False, unique=True),
        sa.Column("claimed_by", sa.String(128), nullable=True),
        sa.Column("claimed_until", _TS, nullable=True),
        sa.Column("claim_count", sa.Integer(), nullable=False),
    )
    op.create_index(
        "ix_cp_queue_claimable",
        "cp_queue",
        ["tenant_id", "worker_kind", "available_at", "priority", "sequence"],
    )

    # ------------------------------------------------------------------
    # Leadership — singleton roles, fenced
    # ------------------------------------------------------------------
    op.create_table(
        "cp_leadership",
        # ``scope`` is the tenant for a tenant-scoped role or the platform
        # sentinel for a platform one -- part of the key so a tenant cannot take
        # a platform role by naming it.
        sa.Column("scope", sa.String(128), primary_key=True),
        sa.Column("role", sa.String(64), primary_key=True),
        sa.Column("instance_id", sa.String(128), nullable=True),
        # Monotonic, durable, incremented in place. The only thing a stalled
        # process can be caught by, and the reason this row is never deleted.
        sa.Column("fencing_token", sa.BigInteger(), nullable=False),
        sa.Column("acquired_at", _TS, nullable=True),
        sa.Column("heartbeat_at", _TS, nullable=True),
        sa.Column("expires_at", _TS, nullable=True),
        sa.Column("released_at", _TS, nullable=True),
        sa.Column("status", sa.String(16), nullable=False),
    )
    op.create_index("ix_cp_leadership_expiry", "cp_leadership", ["expires_at"])


def downgrade() -> None:
    """Drop what the upgrade created, and nothing else.

    Destructive in two senses worth naming. Queued work is lost — survivable,
    because ``ready_nodes()`` recomputes it from the aggregate, which is exactly
    why the queue is not a source of truth.

    Leadership is worse: dropping ``cp_leadership`` **resets every fencing token
    to zero**. A process that stalled before the downgrade and wakes after it
    would present a token the fresh row has not reached yet, and would pass a
    check it should fail. A deployment downgrading this must ensure no instance
    from before it can still be running.
    """
    op.drop_table("cp_leadership")
    op.drop_table("cp_queue")
