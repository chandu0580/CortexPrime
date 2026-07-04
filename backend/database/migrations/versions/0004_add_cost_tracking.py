"""Add cost_tracking table for Mission Cost Engine.

Revision ID: 0004_add_cost_tracking
Revises: 0003_consolidate_reflection_tables
Create Date: 2026-06-07
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# --------------------------------------------------------------------------- #
# Revision chain
# --------------------------------------------------------------------------- #
revision: str = "0004_add_cost_tracking"
down_revision: str | None = "0003_consolidate_reflection_tables"
branch_labels = None
depends_on = None


# --------------------------------------------------------------------------- #
# Migrations
# --------------------------------------------------------------------------- #

def upgrade() -> None:
    op.create_table(
        "cost_tracking",
        sa.Column("id",               sa.Integer(),    nullable=False, autoincrement=True),
        sa.Column("mission_id",       sa.String(255),  nullable=True),
        sa.Column("user_id",          sa.String(255),  nullable=True),
        sa.Column("session_id",       sa.String(255),  nullable=True),
        sa.Column("provider",         sa.String(64),   nullable=False),
        sa.Column("service",          sa.String(64),   nullable=False),
        sa.Column("model",            sa.String(128),  nullable=True),
        sa.Column("prompt_tokens",    sa.Integer(),    nullable=False, server_default="0"),
        sa.Column("completion_tokens",sa.Integer(),    nullable=False, server_default="0"),
        sa.Column("total_tokens",     sa.Integer(),    nullable=False, server_default="0"),
        sa.Column("units",            sa.Float(),      nullable=False, server_default="0"),
        sa.Column("cost_usd",         sa.Float(),      nullable=False, server_default="0"),
        sa.Column("report_date",      sa.Date(),       nullable=False),
        sa.Column("extra",            sa.JSON(),       nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Indexes for the query patterns used by cost_engine.py
    op.create_index("ix_cost_tracking_mission_date",  "cost_tracking", ["mission_id",  "report_date"])
    op.create_index("ix_cost_tracking_user_date",     "cost_tracking", ["user_id",     "report_date"])
    op.create_index("ix_cost_tracking_provider_date", "cost_tracking", ["provider",    "report_date"])
    op.create_index("ix_cost_tracking_report_date",   "cost_tracking", ["report_date"])


def downgrade() -> None:
    op.drop_index("ix_cost_tracking_report_date",   table_name="cost_tracking")
    op.drop_index("ix_cost_tracking_provider_date", table_name="cost_tracking")
    op.drop_index("ix_cost_tracking_user_date",     table_name="cost_tracking")
    op.drop_index("ix_cost_tracking_mission_date",  table_name="cost_tracking")
    op.drop_table("cost_tracking")
