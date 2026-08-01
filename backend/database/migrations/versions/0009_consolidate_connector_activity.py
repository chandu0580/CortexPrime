"""Consolidate connector_activity: drop the unused connector_activity_bc
duplicate created by 0007, create the real connector_activity table.

Audit finding: 0007 created a bounded-context ConnectorActivityModel mapped
to "connector_activity_bc" for backend/learning/detector.py to read, while
the actual write path (backend/connectors/activity_service.py, invoked on
every connector operation) uses a *different* ConnectorActivityModel
(backend/database/models/connector_activity.py) mapped to "connector_activity"
— a table that was never created by any migration. Same split-write/read
anti-pattern that 0003 fixed for reflection_log/reflection_history, except
here the read-side table existed and the write-side table didn't, so every
connector activity write failed with "relation connector_activity does not
exist" and the learning detector's connector-reliability pattern always
read zero rows.

Fix: create connector_activity (the real, actively-written table) and drop
connector_activity_bc (repositories/connectors.py's duplicate model was
removed in the same change; nothing references this table anymore).

Revision ID: 0009_consolidate_connector_activity
Revises: 0008_add_connector_status
Create Date: 2026-08-01
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID

revision: str = "0009_consolidate_connector_activity"
down_revision: str | None = "0008_add_connector_status"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("idx_connector_activity_status", table_name="connector_activity_bc")
    op.drop_index("idx_connector_activity_name", table_name="connector_activity_bc")
    op.drop_table("connector_activity_bc")

    op.create_table(
        "connector_activity",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("connector_name", sa.String(256), nullable=False),
        sa.Column("connector_type", sa.String(64), nullable=False),
        sa.Column("operation", sa.String(64), nullable=False),
        sa.Column("resource", sa.String(256), nullable=True),
        sa.Column("resource_id", sa.String(256), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="success"),
        sa.Column("initiated_by", sa.String(256), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("request_id", UUID(as_uuid=True), nullable=True),
        sa.Column("correlation_id", UUID(as_uuid=True), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("metadata", JSONB, nullable=True),
        sa.Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("idx_ca_connector_type_created", "connector_activity", ["connector_type", "created_at"])
    op.create_index("idx_ca_status_created", "connector_activity", ["status", "created_at"])
    op.create_index("idx_ca_operation_created", "connector_activity", ["operation", "created_at"])
    op.create_index("idx_ca_initiated_by", "connector_activity", ["initiated_by"])
    op.create_index("idx_ca_created", "connector_activity", ["created_at"])
    op.create_index("idx_ca_connector_name", "connector_activity", ["connector_name"])
    op.create_index("idx_ca_request_id", "connector_activity", ["request_id"])
    op.create_index("idx_ca_correlation_id", "connector_activity", ["correlation_id"])


def downgrade() -> None:
    op.drop_table("connector_activity")

    op.create_table(
        "connector_activity_bc",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("connector_name", sa.String(128), nullable=False),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="success"),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("request_summary", sa.Text(), nullable=True),
        sa.Column("response_summary", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("metadata", JSONB, nullable=True),
        sa.Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("idx_connector_activity_name", "connector_activity_bc", ["connector_name", "created_at"])
    op.create_index("idx_connector_activity_status", "connector_activity_bc", ["status"])
