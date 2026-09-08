"""Approval store: migration coverage for the one durable table that had none.

Phase 10.19, ADR-113. One new table, nothing altered, dropped or moved.

Why this migration exists
-------------------------
``cp_approval`` is the durable home of the approval system (Phase 10.3,
ADR-096): the row a human writes in one request and the execution gateway reads
back in another. It has been defined on ``DURABLE_METADATA`` since Phase 10.3
and used in production code since -- but no migration ever created it. Its
twenty-four sibling durable tables each have one (``0010`` through ``0022``).

The consequence, proven in the Phase 10.17 drift discovery (ADR-112): a
database built solely by ``alembic upgrade head`` has no ``cp_approval``, and
``verify_durability`` reports ``missing_tables=["cp_approval"]``,
``ready=False``. The production persistence builder refuses to create schema by
design, so nothing fills the gap. Every phase harness since 10.3 built its
database with ``build_development_store``, which runs ``create_all`` -- which is
why the platform's own fail-closed readiness check was never seen to fail.

What this migration is derived from
-----------------------------------
``backend/database/durable/tables.py::approval_table``, column for column. NOT
from an autogenerate diff, which is contaminated by 134 unrelated operations.
The production repository (``SqlApprovalRepository``) uses ``approval_table``
exclusively and references no column outside it, so the Table is the single
authority and this migration reproduces it exactly.

What it does not do
-------------------
It does not decide about approvals. Whether an approval covers an action is
still answered by ``ApprovalFacts.is_valid_for`` and re-answered by the
gateway's action-digest comparison. Adding a second decider is the specific
mistake ADR-090 exists to prevent. Nothing about approval semantics, the
contract, the repository or the routes changes here.

The already-present case
------------------------
Every development and harness database already has ``cp_approval``, created by
``create_all`` outside Alembic. An unconditional ``create_table`` would fail on
all of them. ``0023_retire_iam`` set the convention for a table that may already
exist outside the lineage -- an existence check against the catalogue -- and
this migration follows it, for the table and for each index by name. A database
that already has the table is left exactly as it is.

Revision ID: 0024_approval_store
Revises: 0023_retire_iam
Create Date: 2026-09-08
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP

revision: str = "0024_approval_store"
down_revision: str | None = "0023_retire_iam"
branch_labels = None
depends_on = None

_TS = TIMESTAMP(timezone=True)
_DOC = JSONB().with_variant(sa.JSON(), "sqlite")

_TABLE = "cp_approval"
_INDEXES = (
    ("ix_cp_approval_tenant", ["tenant_id", "requested_at"]),
    ("ix_cp_approval_investigation", ["tenant_id", "investigation_ref"]),
)


def _table_present() -> bool:
    return _TABLE in sa.inspect(op.get_bind()).get_table_names()


def _index_present(name: str) -> bool:
    return any(ix["name"] == name for ix in sa.inspect(op.get_bind()).get_indexes(_TABLE))


def upgrade() -> None:
    if not _table_present():
        op.create_table(
            _TABLE,
            sa.Column("approval_id", sa.Text(), primary_key=True),
            # Deterministic identity for idempotency: the same request
            # re-submitted collides and returns the existing approval.
            sa.Column("identity_digest", sa.String(128), nullable=False, unique=True),
            sa.Column("tenant_id", sa.String(128), nullable=False),
            sa.Column("capability_ref", sa.Text(), nullable=False),
            sa.Column("capability_digest", sa.String(128), nullable=False),
            # Two operations, deliberately separate: the provider operation this
            # approval performs, and the verb AUTHORIZATION is asked about.
            sa.Column("operation", sa.String(128), nullable=False),
            sa.Column("authorization_operation", sa.String(32), nullable=False),
            sa.Column("environment", sa.String(32), nullable=False),
            sa.Column("principal_id", sa.Text(), nullable=False),
            sa.Column("payload", _DOC, nullable=False),
            # The ADR-090 canonical approval digest, computed by the platform.
            sa.Column("approval_digest", sa.String(128), nullable=False),
            sa.Column("outcome", sa.String(32), nullable=False),
            sa.Column("requested_by", sa.Text(), nullable=False),
            sa.Column("decided_by", sa.Text(), nullable=True),
            sa.Column("justification", sa.Text(), nullable=True),
            # An approval that never expires is a standing authorization nobody granted.
            sa.Column("expires_at", _TS, nullable=False),
            sa.Column("requested_at", _TS, nullable=False),
            sa.Column("decided_at", _TS, nullable=True),
            sa.Column("consumed_by_execution", sa.Text(), nullable=True),
            sa.Column("investigation_ref", sa.Text(), nullable=True),
            sa.Column("schema_version", sa.Integer(), nullable=False),
        )
    for name, columns in _INDEXES:
        if not _index_present(name):
            op.create_index(name, _TABLE, columns)


def downgrade() -> None:
    if not _table_present():
        return
    for name, _ in reversed(_INDEXES):
        if _index_present(name):
            op.drop_index(name, table_name=_TABLE)
    op.drop_table(_TABLE)
