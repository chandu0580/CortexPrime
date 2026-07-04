"""Add audit_logs table.

The audit_logs table is the authoritative, durable audit trail for every
governance decision, mission lifecycle event, browser/computer-agent action,
and approval workflow outcome.  Entries survive server restarts, Docker
restarts, and deployments.

Revision ID: 0002_add_audit_logs
Revises    : 0001_initial_schema
Create Date: 2026-06-06
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP

# revision identifiers
revision: str       = "0002_add_audit_logs"
down_revision: str | None = "0001_initial_schema"
branch_labels: str | None = None
depends_on:    str | None = None


def upgrade() -> None:
    op.create_table(
        "audit_logs",
        # Primary key
        sa.Column(
            "id",
            sa.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        # Timestamps (reuses set_updated_at() trigger from 0001)
        sa.Column(
            "created_at",
            TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        # Audit payload columns
        sa.Column("execution_id", sa.String(128), nullable=False),
        sa.Column(
            "user_id", sa.String(128), nullable=False, server_default="system"
        ),
        sa.Column("agent",  sa.String(128), nullable=False),
        sa.Column("action", sa.String(256), nullable=False),
        sa.Column(
            "risk_level", sa.String(32), nullable=False, server_default="low"
        ),
        sa.Column(
            "outcome", sa.String(32), nullable=False, server_default="allowed"
        ),
        sa.Column("reason", sa.Text, nullable=False, server_default=""),
        sa.Column("metadata", JSONB, nullable=True),
        sa.Column("session_id", sa.String(128), nullable=True),
        sa.Column("request_id", sa.String(128), nullable=True),
    )

    # ── Single-column indexes (ORM index=True columns) ──────────────────────
    op.create_index("ix_audit_logs_execution_id", "audit_logs", ["execution_id"])
    op.create_index("ix_audit_logs_agent",        "audit_logs", ["agent"])
    op.create_index("ix_audit_logs_risk_level",   "audit_logs", ["risk_level"])
    op.create_index("ix_audit_logs_outcome",      "audit_logs", ["outcome"])
    op.create_index("ix_audit_logs_session_id",   "audit_logs", ["session_id"])
    op.create_index("ix_audit_logs_request_id",   "audit_logs", ["request_id"])

    # ── Composite indexes (ORM __table_args__) ───────────────────────────────
    op.create_index(
        "idx_audit_execution_created", "audit_logs", ["execution_id", "created_at"]
    )
    op.create_index(
        "idx_audit_outcome_created", "audit_logs", ["outcome", "created_at"]
    )
    op.create_index(
        "idx_audit_risk_created", "audit_logs", ["risk_level", "created_at"]
    )
    op.create_index(
        "idx_audit_agent_created", "audit_logs", ["agent", "created_at"]
    )
    op.create_index("idx_audit_created", "audit_logs", ["created_at"])

    # ── updated_at trigger (set_updated_at() created in 0001) ───────────────
    op.execute("""
        CREATE TRIGGER trg_audit_logs_updated_at
        BEFORE UPDATE ON audit_logs
        FOR EACH ROW EXECUTE FUNCTION set_updated_at()
    """)


def downgrade() -> None:
    # DROP TABLE cascades triggers and indexes automatically
    op.drop_table("audit_logs")
