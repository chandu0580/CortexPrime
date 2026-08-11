"""Governed delegation and tenant-scoped connector configuration.

Phase 5.3. Two new tables, and four nullable columns added to ``cp_delegation``.

**Additive.** Nothing is altered, dropped or moved. The four new columns are
nullable because rows written before this migration exist and cannot retroactively
acquire an approval — and making them ``NOT NULL`` would either fail on those rows
or require inventing evidence for them, which is the one thing an approval record
must never contain.

The enforcement that they are present is in the application, where it can say
why: ``SqlDelegationRepository.issue`` requires all three as keyword arguments
with no defaults, so a grant written from now on cannot lack them. A NULL
``request_id`` therefore reads as "issued before there was a way to ask", which is
a true statement about the past rather than a hole in the current rule.

Why a request is a table and not a column
-------------------------------------------
A delegation request is a durable thing with its own lifecycle — opened, decided,
issued — and its own evidence: who asked, who decided, against which digest. Two
of those facts (approver, approval digest) exist before any grant does, so they
cannot live on the grant row. And a denied request produces no grant at all while
still being something an audit needs to see.

Why the connector configuration has no secret column
------------------------------------------------------
``credential_ref`` is 256 characters and holds a reference of the form
``cred://<tenant>/<id>``. There is no column here that a provider token fits in
and no column that one belongs in: the material stays in the credential broker,
is fetched at invocation time, and never reaches this table, an event, a log line
or an execution record.

This is the durable replacement for the V1 ``POST /api/connectors/{id}/connect``
body — ``credentials: Dict[str, str]`` on an untenanted process-wide store, gated
off in Phase 4.4 and given a correct shape here.

Revision ID: 0012_governed_delegation
Revises: 0011_distributed_coordination
Create Date: 2026-08-08
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP

revision: str = "0012_governed_delegation"
down_revision: str | None = "0011_distributed_coordination"
branch_labels = None
depends_on = None

#: Application clock, UTC, as in 0010 and 0011. No ``server_default NOW()`` on
#: anything the platform reasons about — least of all on an approval timestamp,
#: where a database clock and an application clock disagreeing would put two
#: different moments into one authority calculation.
_TS = TIMESTAMP(timezone=True)
_DOC = JSONB().with_variant(sa.JSON(), "sqlite")


def upgrade() -> None:
    # ------------------------------------------------------------------
    # Delegation requests — evidence of an ask, never authority
    # ------------------------------------------------------------------
    op.create_table(
        "cp_delegation_request",
        sa.Column("request_id", sa.String(64), primary_key=True),
        sa.Column("tenant_id", sa.String(128), nullable=False),
        sa.Column("requested_by", sa.String(128), nullable=False),
        sa.Column("actor_principal_id", sa.String(128), nullable=False),
        sa.Column("delegated_principal_id", sa.String(128), nullable=False),
        sa.Column("scope", _DOC, nullable=False),
        # Not optional. Identity borrowing approved on a blank reason is
        # identity borrowing nobody actually reviewed.
        sa.Column("reason", sa.String(1024), nullable=False),
        sa.Column("requested_validity_seconds", sa.Integer, nullable=False),
        sa.Column("requested_at", _TS, nullable=False),
        sa.Column("expires_at", _TS, nullable=False),
        # What an approval binds to. Widen the scope after approval and this
        # moves, the approval stops matching, and issuance refuses.
        sa.Column("request_digest", sa.String(128), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("approved_by", sa.String(128), nullable=True),
        sa.Column("approved_at", _TS, nullable=True),
        sa.Column("approval_artifact_id", sa.String(64), nullable=True),
        sa.Column("approval_digest", sa.String(128), nullable=True),
        sa.Column("decision_reason", sa.String(1024), nullable=True),
        sa.Column("issued_delegation_id", sa.String(64), nullable=True),
    )
    op.create_index(
        "ix_cp_delreq_tenant_status", "cp_delegation_request", ["tenant_id", "status"]
    )
    op.create_index(
        "ix_cp_delreq_pair",
        "cp_delegation_request",
        ["tenant_id", "actor_principal_id", "delegated_principal_id"],
    )

    # ------------------------------------------------------------------
    # Issuance and revocation evidence on the grant itself
    # ------------------------------------------------------------------
    op.add_column(
        "cp_delegation", sa.Column("request_id", sa.String(64), nullable=True)
    )
    op.add_column(
        "cp_delegation", sa.Column("approval_artifact_id", sa.String(64), nullable=True)
    )
    op.add_column(
        "cp_delegation", sa.Column("approved_by", sa.String(128), nullable=True)
    )
    op.add_column(
        "cp_delegation", sa.Column("revoked_by", sa.String(128), nullable=True)
    )

    # ------------------------------------------------------------------
    # Connector configuration — tenant-scoped, references only
    # ------------------------------------------------------------------
    op.create_table(
        "cp_connector_config",
        # Tenant first in the key so a configuration cannot exist without one.
        # The surface this replaces had no tenant at all, which is how one
        # authenticated user could set a provider credential for the whole
        # process.
        sa.Column("tenant_id", sa.String(128), primary_key=True),
        sa.Column("provider_id", sa.String(128), primary_key=True),
        sa.Column("environment", sa.String(16), primary_key=True),
        sa.Column("endpoint", sa.String(2048), nullable=False),
        # A reference, never material. Short on purpose: a token does not fit,
        # and the repository refuses one before it gets this far.
        sa.Column("credential_ref", sa.String(256), nullable=True),
        sa.Column("credential_scope", _DOC, nullable=False),
        sa.Column("policy", _DOC, nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("digest", sa.String(128), nullable=False),
        sa.Column("configured_by", sa.String(128), nullable=False),
        sa.Column("created_at", _TS, nullable=False),
        sa.Column("updated_at", _TS, nullable=False),
    )
    op.create_index(
        "ix_cp_connector_config_provider",
        "cp_connector_config",
        ["provider_id", "environment"],
    )


def downgrade() -> None:
    """Drop what the upgrade created, and nothing else.

    Destructive in the only sense that matters here: the evidence of who asked
    for a delegation, who approved it and against which digest is deleted, while
    the grants issued under those approvals survive in ``cp_delegation`` with
    their provenance columns removed. The authority keeps working and the reason
    it exists does not.

    A deployment downgrading this should revoke outstanding delegations first.
    """
    op.drop_table("cp_connector_config")
    op.drop_column("cp_delegation", "revoked_by")
    op.drop_column("cp_delegation", "approved_by")
    op.drop_column("cp_delegation", "approval_artifact_id")
    op.drop_column("cp_delegation", "request_id")
    op.drop_table("cp_delegation_request")
