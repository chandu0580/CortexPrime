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
    # Real UUID values have no meaningful integer equivalent — this
    # migration exists specifically because integer was the WRONG type
    # for this column, so downgrading is inherently a best-effort,
    # data-losing operation on a table with existing rows. The explicit
    # USING cast is required syntactically for Postgres to accept the
    # type change at all (it has no automatic uuid->integer cast), and
    # is a correct no-op on an empty table (the common case for a
    # migration-test downgrade).
    #
    # Order matters, mirroring upgrade()'s own pattern: the existing
    # gen_random_uuid() default must be dropped BEFORE the type change,
    # not alongside it — Postgres tries to validate the old default
    # against the new type otherwise and fails with "default ... cannot
    # be cast automatically".
    op.execute("ALTER TABLE cost_tracking ALTER COLUMN id DROP DEFAULT")
    op.alter_column(
        "cost_tracking",
        "id",
        type_=sa.Integer(),
        postgresql_using="id::text::integer",
    )
