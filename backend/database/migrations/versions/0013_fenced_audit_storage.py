"""Fenced audit storage: the chain tail in the store the fence can reach.

Phase 5.12, ADR-055. Two new tables, nothing altered, dropped or moved.

Why the audit chain moves into the database
---------------------------------------------
ADR-054 gave the audit writer *admission* through ``LeadershipRole.AUDIT_WRITER``
and stated its limitation plainly: a filesystem append cannot join the fencing
predicate. The ownership check and the ``write()`` are two separate steps, so a
runtime that held the role, lost it, and still appends gets its write into the
JSONL file — the same stale-check race ``fenced_where`` eliminates for every
durable write.

These tables close that gap without a second coordination system. The append
becomes one transaction — a fenced ``UPDATE`` on ``cp_leadership`` (the existing
role row, the existing token), a conditional advance of ``cp_audit_chain``, and
the ``INSERT`` into ``cp_audit_record`` — so a stale writer's record rolls back
with the refused fence rather than landing beside it.

Why a chain-tail table and not just records
---------------------------------------------
``next_sequence`` on ``cp_audit_chain`` is a cross-process invariant only the
database can hold: two writers cannot both advance the tail past one value, so
the chain physically cannot fork — the Phase 5.10 corruption (interleaved
records, broken links, an orphan origin) becomes an unwritable state rather than
a verification finding. The primary key on ``(chain_id, sequence)`` is the same
invariant restated on the records themselves.

Why there is no update and no delete path
-------------------------------------------
The audit store's interface has no mutation to express (Constitution I3), and
retention remains **plan-only** (ADR-053): nothing in this phase deletes a
record, and ``KeepForever`` stays the default.

No secret material
--------------------
``cp_audit_record`` stores what ``AuditEvent`` carries: digests, effects,
refusal codes, outcomes. Credential material never reaches an audit record —
enforced at the recording call sites and verified in every phase since 5.8 —
so there is no column here a token belongs in.

Revision ID: 0013_fenced_audit_storage
Revises: 0012_governed_delegation
Create Date: 2026-08-10
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP

revision: str = "0013_fenced_audit_storage"
down_revision: str | None = "0012_governed_delegation"
branch_labels = None
depends_on = None

#: Application clock, UTC, as in 0010–0012. No ``server_default NOW()`` —
#: ``recorded_at`` is the moment the runtime chained the record, and a database
#: clock disagreeing with the application clock would put two moments into one
#: evidence trail.
_TS = TIMESTAMP(timezone=True)
_DOC = JSONB().with_variant(sa.JSON(), "sqlite")


def upgrade() -> None:
    # ------------------------------------------------------------------
    # The chain tail — one row per chain, outlives every writer
    # ------------------------------------------------------------------
    op.create_table(
        "cp_audit_chain",
        sa.Column("chain_id", sa.String(128), primary_key=True),
        # Advanced only by the same transaction that inserts the record, and
        # only from the exact value it expects: the single authoritative tail.
        sa.Column("next_sequence", sa.BigInteger, nullable=False),
        # Digest value of the most recent record, carried in the tail-advance
        # predicate so an append that does not extend the durable head is
        # refused by rowcount.
        sa.Column("head_digest", sa.String(128), nullable=True),
    )

    # ------------------------------------------------------------------
    # The records — chain position is the identity
    # ------------------------------------------------------------------
    op.create_table(
        "cp_audit_record",
        sa.Column("chain_id", sa.String(128), primary_key=True),
        sa.Column("sequence", sa.BigInteger, primary_key=True),
        sa.Column("event_id", sa.String(64), nullable=False, unique=True),
        # Promoted for reads; the document stays authoritative for the record.
        sa.Column("tenant_id", sa.String(128), nullable=False),
        sa.Column("kind", sa.String(64), nullable=False),
        sa.Column("recorded_at", _TS, nullable=False),
        sa.Column("subject_reference", sa.String(512), nullable=True),
        sa.Column("correlation_id", sa.String(128), nullable=True),
        sa.Column("actor_id", sa.String(128), nullable=True),
        sa.Column("entry_digest", sa.String(128), nullable=False),
        sa.Column("previous_digest", sa.String(128), nullable=True),
        # Which fencing token wrote the record. Evidence, not enforcement —
        # the enforcement is the fenced transaction that inserted the row.
        sa.Column("writer_token", sa.BigInteger, nullable=True),
        sa.Column("document", _DOC, nullable=False),
    )
    op.create_index(
        "ix_cp_audit_record_tenant",
        "cp_audit_record",
        ["chain_id", "tenant_id", "sequence"],
    )
    op.create_index("ix_cp_audit_record_recorded", "cp_audit_record", ["recorded_at"])
    op.create_index(
        "ix_cp_audit_record_correlation", "cp_audit_record", ["correlation_id"]
    )


def downgrade() -> None:
    """Drop what the upgrade created, and nothing else.

    Destructive in the fullest sense: this deletes audit evidence. A deployment
    that has written to these tables should export the chain — and publish the
    head digest somewhere the platform cannot reach — before running this.
    """
    op.drop_table("cp_audit_record")
    op.drop_table("cp_audit_chain")
