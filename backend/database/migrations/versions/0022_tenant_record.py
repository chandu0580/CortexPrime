"""Tenant records: the durable answer to "what is the authoritative tenant".

Phase 10.10, ADR-103. One new table, nothing altered, dropped or moved.

Why a new table
---------------
Phase 10.8 made authority durable and Phase 10.9 made membership durable. Both
still rested on ``data/tenants/tenants.json`` — a gitignored file that
``require_tenant`` consulted on every request, so an edit to it disabled
governance for an entire tenant.

Reuse was searched for and refused:

* ``organizations`` has **no tenant_id**, no membership, and no relationship to
  any authority, approval or execution record. It is an org-chart entity with
  departments, served by ``organization_routes``. The names look alike; the
  concepts are not. Overloading it is exactly what a "prove semantic
  equivalence first" rule exists to prevent.
* ``iam_users`` was already dismissed in Phase 10.9: zero references anywhere,
  and no tenant column.
* ``cp_tenant_membership`` stores the *relation*, not the boundary.

What this table is not
----------------------
It is not a permission. A tenant row means an authoritative organizational
boundary exists — nothing about who belongs to it (``cp_tenant_membership``)
and nothing about what they may do (``cp_authority_grant``).

Guarantees
----------
Attributed (``created_by`` NOT NULL). **Never deleted** — removal is a status
change, so historical approvals, grants and memberships keep pointing at a
resolvable boundary. ``slug`` is UNIQUE and display/lookup only; ``tenant_id``
is the authority-bearing identity every other table already keys on.

Deliberately **no digest**, and tenant state deliberately does **not** enter the
capability, approval or grant digests. Tenant state is intentionally mutable, so
a hash over it would be recomputed by every legitimate change; and folding it
into the historical digests would mean deactivating a tenant silently
invalidated every approval and grant ever bound in it — rewriting history.

Revision ID: 0022_tenant_record
Revises: 0021_tenant_membership
Create Date: 2026-09-06
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import TIMESTAMP

revision: str = "0022_tenant_record"
down_revision: str | None = "0021_tenant_membership"
branch_labels = None
depends_on = None

_TS = TIMESTAMP(timezone=True)


def upgrade() -> None:
    op.create_table(
        "cp_tenant",
        sa.Column("tenant_id", sa.String(128), primary_key=True),
        sa.Column("slug", sa.String(128), nullable=False, unique=True),
        sa.Column("name", sa.String(256), nullable=False),
        # active | inactive. Never deleted.
        sa.Column("status", sa.String(16), nullable=False),
        # migrated | provisioned
        sa.Column("source", sa.String(16), nullable=False),
        sa.Column("created_by", sa.String(256), nullable=False),
        sa.Column("created_at", _TS, nullable=False),
        sa.Column("updated_by", sa.String(256), nullable=True),
        sa.Column("updated_at", _TS, nullable=True),
        sa.Column("schema_version", sa.Integer(), nullable=False),
    )
    op.create_index("ix_cp_tenant_status", "cp_tenant", ["status"])


def downgrade() -> None:
    op.drop_index("ix_cp_tenant_status", table_name="cp_tenant")
    op.drop_table("cp_tenant")
