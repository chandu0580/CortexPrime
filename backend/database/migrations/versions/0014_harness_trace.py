"""Harness trace store: attribution-grade spans, separate from the audit chain.

Phase 6.1, L14. One new table, nothing altered, dropped or moved.

Why a separate store and not the audit chain
----------------------------------------------
The audit runtime explicitly bans traces and metrics from the chain
(platform/audit/runtime.py): governance facts are evidence of *authority*;
trace spans are evidence of *explanation*. They join on ``correlation_id`` —
the platform ``ExecutionContext`` stamps the same correlation into both — so
no second correlation mechanism exists.

Why append-only
-----------------
A trace that can be edited is not evidence. The recorder interface exposes no
update, no delete, no replace; this schema offers no state a mutation would
maintain. Failure attribution reads spans as they were written, joined to the
harness version that produced them — cohort analysis across versions is the
strongest attribution signal available (Phase 6.0 §20), and it is only as
trustworthy as this table's immutability.

No secret material
--------------------
Spans are redacted **at construction** (``build_model_span`` /
``build_action_span`` apply ``scrub_text`` / ``redact_mapping`` before the
object exists), so this table never sees an unredacted prompt, output, or
tool payload. ``context_reconstructable`` records honestly whether the stored
recipe reconstructs the exact model input; Phase 6.1 always stores ``false``
because scrubbing is lossy.

Revision ID: 0014_harness_trace
Revises: 0013_fenced_audit_storage
Create Date: 2026-08-11
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP

revision: str = "0014_harness_trace"
down_revision: str | None = "0013_fenced_audit_storage"
branch_labels = None
depends_on = None

_TS = TIMESTAMP(timezone=True)
_DOC = JSONB().with_variant(sa.JSON(), "sqlite")


def upgrade() -> None:
    op.create_table(
        "cp_harness_trace",
        sa.Column("span_record_id", sa.Text(), primary_key=True),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("mission_id", sa.Text(), nullable=False),
        sa.Column("iteration", sa.Integer(), nullable=False),
        sa.Column("step_id", sa.Text(), nullable=False),
        sa.Column("harness_version", sa.Text(), nullable=False),
        sa.Column("correlation_id", sa.Text(), nullable=False),
        sa.Column("trace_id", sa.Text(), nullable=False),
        sa.Column("trace_span_id", sa.Text(), nullable=False),
        sa.Column("started_at", sa.Text(), nullable=False),
        sa.Column("finished_at", sa.Text(), nullable=False),
        sa.Column("record", _DOC, nullable=False),
        sa.Column("recorded_at", _TS, nullable=False),
    )
    op.create_index(
        "ix_cp_harness_trace_correlation",
        "cp_harness_trace",
        ["correlation_id"],
    )
    op.create_index(
        "ix_cp_harness_trace_mission",
        "cp_harness_trace",
        ["mission_id", "iteration"],
    )
    op.create_index(
        "ix_cp_harness_trace_version",
        "cp_harness_trace",
        ["harness_version"],
    )


def downgrade() -> None:
    op.drop_index("ix_cp_harness_trace_version", table_name="cp_harness_trace")
    op.drop_index("ix_cp_harness_trace_mission", table_name="cp_harness_trace")
    op.drop_index("ix_cp_harness_trace_correlation", table_name="cp_harness_trace")
    op.drop_table("cp_harness_trace")
