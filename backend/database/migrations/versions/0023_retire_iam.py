"""Retire the dead IAM subsystem: iam_api_keys, iam_roles, iam_users.

Phase 10.14, ADR-107. Three tables dropped, nothing created.

Why these three together
------------------------
Migration ``0007_add_bounded_context_tables`` created all three, and
``iam_api_keys.user_id`` is a foreign key to ``iam_users``. They are one
subsystem: dropping the two obvious ones would fail on the third.

Why forward rather than by rewriting 0007
-----------------------------------------
``0007`` is part of the current, unbroken lineage (``0001 → … → 0022``), so any
database that has ever migrated has run it. History is not rewritten; this
drops what it created.

Why it is safe
--------------
Phases 10.12, 10.13 and 10.14 each established a piece:

* nothing **queries** them — ``UserRepository``, ``RoleRepository`` and
  ``ApiKeyRepository`` were instantiated only by three ``RepositoryFactory``
  accessors that were never called;
* nothing **imports** them any more — Phase 10.14 cut all three edges
  (``providers.py``, ``factory.py``, ``models/__init__.py``), so the models no
  longer reach ``Base.metadata`` and ``init_db()``'s ``create_all`` cannot
  recreate what this drops;
* they hold **no data** — checked across every database on the instance before
  writing this: the one database that has them reports 0 users, 0 roles,
  0 api keys.

Authentication never used them. It is ``verify_credentials`` against
``CORTEX_USER`` / ``CORTEX_PASSWORD_HASH``, and the tenant claim comes from
``cp_tenant_membership`` and ``cp_tenant``.

Tolerating absence
------------------
Most databases here were built by ``DURABLE_METADATA.create_all``, which knows
nothing of the V1 ORM, so these tables were never created there. Each drop is
guarded by an existence check: a fresh database migrates to head without
tripping over a table that never existed.

Revision ID: 0023_retire_iam
Revises: 0022_tenant_record
Create Date: 2026-09-07
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP

revision: str = "0023_retire_iam"
down_revision: str | None = "0022_tenant_record"
branch_labels = None
depends_on = None

#: Foreign-key order. ``iam_api_keys.user_id`` references ``iam_users``, so the
#: child goes first; ``downgrade`` recreates in the reverse order.
_DROP_ORDER = ("iam_api_keys", "iam_roles", "iam_users")


def _present(name: str) -> bool:
    return name in sa.inspect(op.get_bind()).get_table_names()


def upgrade() -> None:
    for table in _DROP_ORDER:
        if _present(table):
            op.drop_table(table)


def downgrade() -> None:
    """Recreate the three tables exactly as ``0007`` defined them.

    Reversible on purpose -- a retirement that cannot be undone is a one-way
    door. The definitions below are copied from ``0007`` column for column,
    including ``gen_random_uuid()`` defaults, the ``NOW()`` timestamps, and
    ``iam_api_keys``'s ``last_prefix`` / ``is_active`` / string ``expires_at``.
    A downgrade that produced a *different* schema would be worse than none,
    and the first draft of this function did exactly that until it was checked
    against the original.
    """
    if not _present("iam_users"):
        op.create_table(
            "iam_users",
            sa.Column("id", sa.Uuid(), primary_key=True,
                      server_default=sa.text("gen_random_uuid()")),
            sa.Column("email", sa.String(320), nullable=False),
            sa.Column("display_name", sa.String(256), nullable=False),
            sa.Column("password_hash", sa.String(256), nullable=True),
            sa.Column("status", sa.String(32), nullable=False,
                      server_default="active"),
            sa.Column("is_sso", sa.Boolean(), nullable=False,
                      server_default=sa.text("false")),
            sa.Column("sso_provider", sa.String(64), nullable=True),
            sa.Column("sso_subject", sa.String(256), nullable=True),
            sa.Column("roles", JSONB, nullable=False, server_default="[]"),
            sa.Column("metadata", JSONB, nullable=True),
            sa.Column("created_at", TIMESTAMP(timezone=True), nullable=False,
                      server_default=sa.text("NOW()")),
            sa.Column("updated_at", TIMESTAMP(timezone=True), nullable=False,
                      server_default=sa.text("NOW()")),
        )
        op.create_index("idx_iam_users_email", "iam_users", ["email"],
                        unique=True)
        op.create_index("idx_iam_users_status", "iam_users", ["status"])
        op.create_index("idx_iam_users_sso", "iam_users",
                        ["sso_provider", "sso_subject"])

    if not _present("iam_roles"):
        op.create_table(
            "iam_roles",
            sa.Column("id", sa.Uuid(), primary_key=True,
                      server_default=sa.text("gen_random_uuid()")),
            sa.Column("name", sa.String(128), nullable=False),
            sa.Column("description", sa.String(1024), nullable=True),
            sa.Column("permissions", JSONB, nullable=False,
                      server_default="[]"),
            sa.Column("is_system", sa.Boolean(), nullable=False,
                      server_default=sa.text("false")),
            sa.Column("created_at", TIMESTAMP(timezone=True), nullable=False,
                      server_default=sa.text("NOW()")),
            sa.Column("updated_at", TIMESTAMP(timezone=True), nullable=False,
                      server_default=sa.text("NOW()")),
        )
        op.create_index("idx_iam_roles_name", "iam_roles", ["name"],
                        unique=True)

    if not _present("iam_api_keys"):
        op.create_table(
            "iam_api_keys",
            sa.Column("id", sa.Uuid(), primary_key=True,
                      server_default=sa.text("gen_random_uuid()")),
            sa.Column("user_id", sa.Uuid(),
                      sa.ForeignKey("iam_users.id", ondelete="CASCADE"),
                      nullable=False),
            sa.Column("name", sa.String(128), nullable=False),
            sa.Column("key_hash", sa.String(256), nullable=False),
            sa.Column("last_prefix", sa.String(8), nullable=False),
            sa.Column("expires_at", sa.String(64), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False,
                      server_default=sa.text("true")),
            sa.Column("created_at", TIMESTAMP(timezone=True), nullable=False,
                      server_default=sa.text("NOW()")),
            sa.Column("updated_at", TIMESTAMP(timezone=True), nullable=False,
                      server_default=sa.text("NOW()")),
        )
        op.create_index("idx_iam_ak_user", "iam_api_keys", ["user_id"])
        op.create_index("idx_iam_ak_hash", "iam_api_keys", ["key_hash"],
                        unique=True)
