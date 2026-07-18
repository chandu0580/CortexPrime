"""Add updated_at column to cost_tracking (TimestampMixin).

Revision ID: 0005_add_cost_tracking_updated_at
Revises: 0004_add_cost_tracking
Create Date: 2026-07-05
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# --------------------------------------------------------------------------- #
# Revision chain
# --------------------------------------------------------------------------- #
revision: str = "0005_cost_tracking_updated_at"
down_revision: str | None = "0004_add_cost_tracking"
branch_labels = None
depends_on = None


# --------------------------------------------------------------------------- #
# Migrations
# --------------------------------------------------------------------------- #

def upgrade() -> None:
    op.add_column(
        "cost_tracking",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )


def downgrade() -> None:
    op.drop_column("cost_tracking", "updated_at")
