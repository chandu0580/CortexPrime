"""Tenant membership: the durable answer to "who belongs to this tenant".

Phase 10.9, ADR-102. One new table, nothing altered, dropped or moved.

Why a new table
---------------
Phase 10.8 gave authority grants a durable, attributed home and left every one
of them pointing at a subject whose membership was defined by
``data/tenants/tenant_users.json`` — a gitignored file with no delete method,
no deactivate method and no audit trail.

Reuse was searched for and refused:

* ``iam_users`` (migration 0007) has email, status and roles — and **no tenant
  column**, so it is a user table, not a membership. Its repository has zero
  references anywhere in the codebase; it is dead.
* ``organizations`` is live, but an organization is not a tenant and carries no
  membership.
* No join table between users and tenants exists anywhere in the repository.

What this table is not
----------------------
It is **not a user table**. There is no credential, no display name, no
profile. It stores the relation (subject ∈ tenant) and its state, so it cannot
grow into a second identity system.

It also confers **nothing**. Membership means "this subject belongs here". What
they may do remains the explicit scoped grants of Phase 10.8, and no column
here maps to approve, execute or issue.

Guarantees
----------
Tenant-scoped, unique per (tenant, subject). Attributed — ``created_by`` is
NOT NULL. **Never deleted**: removal is a status change, so historical grants
and approvals keep pointing at a resolvable identity.

Deliberately **no digest**. Membership is intentionally mutable — activating,
deactivating and changing a role are legitimate operations — so a hash over
those fields would be recomputed by every legitimate change and would prove
nothing. Phase 10.8's grant digest works because a grant's authority-bearing
fields are immutable after issuance. Integrity here comes from the audit trail.

Revision ID: 0021_tenant_membership
Revises: 0020_authority_grant
Create Date: 2026-09-06
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import TIMESTAMP

revision: str = "0021_tenant_membership"
down_revision: str | None = "0020_authority_grant"
branch_labels = None
depends_on = None

_TS = TIMESTAMP(timezone=True)


def upgrade() -> None:
    op.create_table(
        "cp_tenant_membership",
        sa.Column("membership_id", sa.String(64), primary_key=True),
        sa.Column("tenant_id", sa.String(128), nullable=False),
        sa.Column("subject_principal_id", sa.String(256), nullable=False),
        # active | inactive. Never deleted.
        sa.Column("status", sa.String(16), nullable=False),
        # Informational only. Nothing reads this to decide anything.
        sa.Column("role", sa.String(32), nullable=False),
        # migrated | admitted
        sa.Column("source", sa.String(16), nullable=False),
        sa.Column("created_by", sa.String(256), nullable=False),
        sa.Column("created_at", _TS, nullable=False),
        sa.Column("updated_by", sa.String(256), nullable=True),
        sa.Column("updated_at", _TS, nullable=True),
        sa.Column("schema_version", sa.Integer(), nullable=False),
    )
    op.create_unique_constraint(
        "uq_cp_tenant_membership", "cp_tenant_membership",
        ["tenant_id", "subject_principal_id"])
    op.create_index(
        "ix_cp_tenant_membership_subject", "cp_tenant_membership",
        ["subject_principal_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_cp_tenant_membership_subject",
                  table_name="cp_tenant_membership")
    op.drop_constraint("uq_cp_tenant_membership", "cp_tenant_membership",
                       type_="unique")
    op.drop_table("cp_tenant_membership")
