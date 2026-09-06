"""Authority grants: the durable, attributed home authority never had.

Phase 10.8, ADR-101. One new table, nothing altered, dropped or moved.

Why a new table
---------------
Phases 10.5-10.7 built scoped approver and executor authority and then read the
grants backing it out of ``data/tenants/tenant_users.json`` -- a gitignored
file holding bare strings, with no issuer, no timestamps, no digest and no
audit event. Enforcement was governed; creation was not.

Reuse was evaluated and refused:

* ``cp_delegation`` carries identity BORROWING and is read by
  ``DurableDelegationAuthority`` to permit on-behalf-of invocation at the
  execution gateway. An authority grant written there would silently become a
  delegation of identity -- a privilege escalation, not a tidy reuse.
* ``cp_approval`` binds a capability INVOCATION through
  ``canonical_approval_digest``. A grant is not an invocation; forcing one in
  would produce an approval whose digest covers a fiction.
* The audit ledger records what happened. It is not a store of what is
  currently true, and making it authoritative would turn revocation into an
  event replay.

Guarantees
----------
Tenant-scoped (``tenant_id NOT NULL``, tenant-first index). Attributed --
``issued_by`` and ``issue_reason`` are NOT NULL, so an unattributed grant
cannot be stored. Revocation is a set field, never a delete, so an auditor can
always tell revoked from never-issued. ``digest`` covers every authority-bearing
field, so a tampered row stops matching itself and stops authorizing.

This table decides nothing. ``resolve_scoped_authority`` still answers whether
a human may act; this only changes where the grant it reads comes from.

Revision ID: 0020_authority_grant
Revises: 0019_world_investigation
Create Date: 2026-09-06
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import TIMESTAMP

revision: str = "0020_authority_grant"
down_revision: str | None = "0019_world_investigation"
branch_labels = None
depends_on = None

_TS = TIMESTAMP(timezone=True)


def upgrade() -> None:
    op.create_table(
        "cp_authority_grant",
        sa.Column("grant_id", sa.String(64), primary_key=True),
        sa.Column("tenant_id", sa.String(128), nullable=False),
        sa.Column("subject_principal_id", sa.String(256), nullable=False),
        # approve | execute. Never merged, and never "issue": issuance
        # authority is not itself issuable, which is what makes transitive
        # delegation structurally impossible rather than merely forbidden.
        sa.Column("authority_type", sa.String(16), nullable=False),
        sa.Column("capability_ref", sa.Text(), nullable=False),
        sa.Column("capability_version", sa.String(32), nullable=False),
        sa.Column("environment", sa.String(32), nullable=False),
        sa.Column("max_risk", sa.String(16), nullable=True),
        sa.Column("issued_by", sa.String(256), nullable=False),
        sa.Column("issued_at", _TS, nullable=False),
        sa.Column("issue_reason", sa.String(1024), nullable=False),
        sa.Column("revoked_at", _TS, nullable=True),
        sa.Column("revoked_by", sa.String(256), nullable=True),
        sa.Column("revocation_reason", sa.String(1024), nullable=True),
        sa.Column("digest", sa.String(128), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
    )
    op.create_unique_constraint(
        "uq_cp_authority_grant", "cp_authority_grant",
        ["tenant_id", "subject_principal_id", "authority_type",
         "capability_ref", "environment", "issued_at"])
    op.create_index(
        "ix_cp_authority_grant_subject", "cp_authority_grant",
        ["tenant_id", "subject_principal_id", "authority_type"])


def downgrade() -> None:
    op.drop_index("ix_cp_authority_grant_subject",
                  table_name="cp_authority_grant")
    op.drop_constraint("uq_cp_authority_grant", "cp_authority_grant",
                       type_="unique")
    op.drop_table("cp_authority_grant")
