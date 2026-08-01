"""Fix cost_tracking id type: integer → uuid (match UUIDPrimaryKeyMixin).

Revision ID: 0006_fix_cost_tracking_id_type
Revises: 0005_cost_tracking_updated_at
Create Date: 2026-07-05
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# --------------------------------------------------------------------------- #
# Revision chain
# --------------------------------------------------------------------------- #
revision: str = "0006_fix_cost_tracking_id_type"
down_revision: str | None = "0005_cost_tracking_updated_at"
branch_labels = None
depends_on = None


# --------------------------------------------------------------------------- #
# Migrations
# --------------------------------------------------------------------------- #

def upgrade() -> None:
    op.execute("ALTER TABLE cost_tracking ALTER COLUMN id DROP DEFAULT")
    op.alter_column(
        "cost_tracking",
        "id",
        type_=sa.Uuid(),
        postgresql_using="gen_random_uuid()",
    )
    op.alter_column("cost_tracking", "id", server_default=sa.text("gen_random_uuid()"))


def downgrade() -> None:
    op.alter_column("cost_tracking", "id", type_=sa.Integer(), server_default=None)
    op.execute("ALTER TABLE cost_tracking ALTER COLUMN id DROP DEFAULT")
