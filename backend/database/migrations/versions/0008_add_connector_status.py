"""Add status column to connector_configs.

Revision ID: 0008_add_connector_status
Revises: 0007_add_bounded_context_tables
Create Date: 2026-07-17
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0008_add_connector_status"
down_revision: str | None = "0007_add_bounded_context_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "connector_configs",
        sa.Column("status", sa.String(32), nullable=False, server_default="REGISTERED"),
    )
    op.create_index("idx_connector_status", "connector_configs", ["status"])


def downgrade() -> None:
    op.drop_index("idx_connector_status", table_name="connector_configs")
    op.drop_column("connector_configs", "status")
