"""Durable state foundation — execution, leases, idempotency, outbox, registry.

Phase 5.1. Creates the tables that turn the Phase 3 and Phase 4 in-memory stores
into a durable system of record.

**Purely additive.** Nine new tables, no column altered, no table dropped, no
data moved. Nothing existing reads or writes any of them, so applying this
changes no current behaviour: the durable repositories are wired at the
composition root and a deployment that has not wired them keeps its in-memory
ones. That is deliberate — a migration that both created a schema and switched
the system onto it would make the schema change and the behaviour change one
irreversible step.

The downgrade drops what the upgrade created and nothing else. It is destructive
in the only sense a downgrade can be — the durable execution history goes with
it — so a deployment that has run real executions against these tables should
export before downgrading rather than treating this as reversible.

Revision ID: 0010_durable_state_foundation
Revises: 0009_consolidate_connector_activity
Create Date: 2026-08-08
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP

revision: str = "0010_durable_state_foundation"
down_revision: str | None = "0009_consolidate_connector_activity"
branch_labels = None
depends_on = None

#: Timestamps are written by the **application clock**, in UTC. There is
#: deliberately no ``server_default=NOW()`` on any timestamp this platform
#: reasons about: a row stamped by the database and a decision made by the
#: application would be two clocks inside one authority calculation, which is
#: the defect Phase 4.4 closed at the invocation gateway.
_TS = TIMESTAMP(timezone=True)


def upgrade() -> None:
    # ------------------------------------------------------------------
    # Execution — the aggregate as a document, plus what must be raced on
    # ------------------------------------------------------------------
    op.create_table(
        "cp_execution",
        sa.Column("execution_id", sa.String(64), primary_key=True),
        sa.Column("tenant_id", sa.String(128), nullable=False),
        # The compare-and-swap column. ``UPDATE ... WHERE revision = :expected``
        # is what makes the Phase 3 in-process guarantee real across instances.
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("workflow_id", sa.String(128), nullable=False),
        sa.Column("workflow_digest", sa.String(128), nullable=True),
        sa.Column("mission_id", sa.String(128), nullable=True),
        sa.Column("state", sa.String(32), nullable=False),
        sa.Column("digest", sa.String(128), nullable=True),
        sa.Column("record", JSONB, nullable=False),
        sa.Column("created_at", _TS, nullable=False),
        sa.Column("updated_at", _TS, nullable=False),
    )
    op.create_index("ix_cp_execution_tenant_state", "cp_execution", ["tenant_id", "state"])
    op.create_index(
        "ix_cp_execution_tenant_workflow", "cp_execution", ["tenant_id", "workflow_id"]
    )

    # ------------------------------------------------------------------
    # Leases — one holder per node, held by the primary key
    # ------------------------------------------------------------------
    op.create_table(
        "cp_node_lease",
        sa.Column("execution_id", sa.String(64), primary_key=True),
        sa.Column("node_id", sa.String(128), primary_key=True),
        sa.Column("tenant_id", sa.String(128), nullable=False),
        sa.Column("lease_id", sa.String(64), nullable=False, unique=True),
        sa.Column("worker_id", sa.String(128), nullable=False),
        sa.Column("attempt_id", sa.String(64), nullable=True),
        sa.Column("granted_at", _TS, nullable=False),
        sa.Column("expires_at", _TS, nullable=False),
        sa.Column("heartbeat_at", _TS, nullable=True),
        sa.Column("released_at", _TS, nullable=True),
        sa.Column("fence", sa.Integer(), nullable=False),
    )
    op.create_index(
        "ix_cp_lease_tenant_expiry", "cp_node_lease", ["tenant_id", "expires_at"]
    )

    # ------------------------------------------------------------------
    # Idempotency — one key per tenant, surviving restart and retry
    # ------------------------------------------------------------------
    op.create_table(
        "cp_idempotency",
        sa.Column("tenant_id", sa.String(128), primary_key=True),
        sa.Column("idempotency_key", sa.String(256), primary_key=True),
        sa.Column("execution_id", sa.String(64), nullable=False),
        sa.Column("node_id", sa.String(128), nullable=True),
        sa.Column("action_digest", sa.String(128), nullable=True),
        sa.Column("outcome", sa.String(32), nullable=True),
        sa.Column("created_at", _TS, nullable=False),
        sa.Column("updated_at", _TS, nullable=False),
    )

    # ------------------------------------------------------------------
    # Outbox — ordered by a database-assigned sequence, one row per event id
    # ------------------------------------------------------------------
    op.create_table(
        "cp_outbox",
        sa.Column("sequence", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("entry_id", sa.String(96), nullable=False, unique=True),
        sa.Column("tenant_id", sa.String(128), nullable=False),
        sa.Column("execution_id", sa.String(64), nullable=False),
        sa.Column("event_type", sa.String(128), nullable=False),
        sa.Column("event_id", sa.String(64), nullable=True),
        sa.Column("payload", JSONB, nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("claimed_by", sa.String(128), nullable=True),
        sa.Column("claimed_until", _TS, nullable=True),
        sa.Column("published_at", _TS, nullable=True),
        sa.Column("last_error", sa.String(512), nullable=True),
        sa.Column("recorded_at", _TS, nullable=False),
        # Delivery stays at-least-once; this only stops the same event being
        # *recorded* twice, which is what makes a replayed command safe.
        sa.UniqueConstraint("tenant_id", "event_id", name="uq_cp_outbox_event_id"),
    )
    op.create_index(
        "ix_cp_outbox_claimable", "cp_outbox", ["tenant_id", "status", "sequence"]
    )
    op.create_index(
        "ix_cp_outbox_execution", "cp_outbox", ["tenant_id", "execution_id", "sequence"]
    )

    # ------------------------------------------------------------------
    # Worker directory — registrations, never adapters
    # ------------------------------------------------------------------
    op.create_table(
        "cp_worker",
        # ``scope_owner`` is the tenant, or the explicit platform sentinel. Part
        # of the key so a tenant cannot occupy the platform slot for an id.
        sa.Column("scope_owner", sa.String(128), primary_key=True),
        sa.Column("worker_id", sa.String(128), primary_key=True),
        sa.Column("tenant_id", sa.String(128), nullable=True),
        sa.Column("scope", sa.String(16), nullable=False),
        sa.Column("worker_kind", sa.String(32), nullable=False),
        sa.Column("interface", sa.String(32), nullable=False),
        sa.Column("implementation", sa.String(512), nullable=False),
        sa.Column("implementation_version", sa.String(64), nullable=False),
        sa.Column("worker_digest", sa.String(128), nullable=False),
        sa.Column("lifecycle", sa.String(16), nullable=False),
        sa.Column("trust", sa.String(16), nullable=False),
        sa.Column("availability", sa.String(16), nullable=False),
        sa.Column("record", JSONB, nullable=False),
        sa.Column("reason", sa.String(512), nullable=True),
        sa.Column("registered_at", _TS, nullable=False),
        sa.Column("updated_at", _TS, nullable=False),
    )
    op.create_index("ix_cp_worker_kind", "cp_worker", ["worker_kind"])

    # ------------------------------------------------------------------
    # Capability registry — one contract per (identity, version)
    # ------------------------------------------------------------------
    op.create_table(
        "cp_capability",
        sa.Column("reference", sa.String(512), primary_key=True),
        sa.Column("capability_id", sa.String(256), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("scope_owner", sa.String(128), nullable=False),
        sa.Column("tenant_id", sa.String(128), nullable=True),
        sa.Column("provider", sa.String(128), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("trust", sa.String(24), nullable=False),
        sa.Column("digest", sa.String(128), nullable=True),
        sa.Column("record", JSONB, nullable=False),
        sa.Column("registered_at", _TS, nullable=False),
        sa.Column("updated_at", _TS, nullable=True),
        # Registration becomes atomic across processes. Two instances offering
        # different contracts for one version cannot both win.
        sa.UniqueConstraint("capability_id", "version", name="uq_cp_capability_version"),
    )
    op.create_index(
        "ix_cp_capability_scope", "cp_capability", ["scope_owner", "capability_id"]
    )

    # ------------------------------------------------------------------
    # Bindings — append-only; the primary key is the immutability
    # ------------------------------------------------------------------
    op.create_table(
        "cp_binding",
        sa.Column("binding_id", sa.String(64), primary_key=True),
        sa.Column("tenant_id", sa.String(128), nullable=False),
        sa.Column("principal_id", sa.String(128), nullable=False),
        sa.Column("capability_ref", sa.String(512), nullable=False),
        sa.Column("capability_digest", sa.String(128), nullable=False),
        sa.Column("binding_digest", sa.String(128), nullable=True),
        sa.Column("provider", sa.String(128), nullable=False),
        sa.Column("operation", sa.String(256), nullable=False),
        sa.Column("execution_id", sa.String(64), nullable=True),
        sa.Column("node_id", sa.String(128), nullable=True),
        sa.Column("expires_at", _TS, nullable=False),
        sa.Column("record", JSONB, nullable=False),
        sa.Column("created_at", _TS, nullable=False),
    )
    op.create_index("ix_cp_binding_execution", "cp_binding", ["tenant_id", "execution_id"])

    # ------------------------------------------------------------------
    # Authorization decisions — evidence of a decision made elsewhere
    # ------------------------------------------------------------------
    op.create_table(
        "cp_authorization",
        sa.Column("decision_id", sa.String(64), primary_key=True),
        sa.Column("tenant_id", sa.String(128), nullable=False),
        sa.Column("principal_id", sa.String(128), nullable=False),
        sa.Column("delegated_principal_id", sa.String(128), nullable=True),
        sa.Column("capability_ref", sa.String(512), nullable=False),
        sa.Column("operation", sa.String(256), nullable=False),
        sa.Column("action_digest", sa.String(128), nullable=True),
        sa.Column("policy_version", sa.String(64), nullable=False),
        sa.Column("effect", sa.String(32), nullable=False),
        sa.Column("risk", sa.String(24), nullable=False),
        sa.Column("approval_artifact_id", sa.String(64), nullable=True),
        sa.Column("decision_digest", sa.String(128), nullable=False),
        sa.Column("expires_at", _TS, nullable=False),
        sa.Column("recorded_at", _TS, nullable=False),
        sa.Column("record", JSONB, nullable=False),
    )
    op.create_index(
        "ix_cp_authz_tenant_action", "cp_authorization", ["tenant_id", "action_digest"]
    )
    op.create_index("ix_cp_authz_digest", "cp_authorization", ["decision_digest"])

    # ------------------------------------------------------------------
    # Delegation — the seam. No workflow issues rows into this table.
    # ------------------------------------------------------------------
    op.create_table(
        "cp_delegation",
        sa.Column("delegation_id", sa.String(64), primary_key=True),
        sa.Column("tenant_id", sa.String(128), nullable=False),
        sa.Column("actor_principal_id", sa.String(128), nullable=False),
        sa.Column("delegated_principal_id", sa.String(128), nullable=False),
        sa.Column("scope", JSONB, nullable=False),
        sa.Column("issued_by", sa.String(128), nullable=False),
        sa.Column("issued_at", _TS, nullable=False),
        sa.Column("expires_at", _TS, nullable=False),
        sa.Column("revoked_at", _TS, nullable=True),
        sa.Column("revocation_reason", sa.String(512), nullable=True),
        sa.Column("digest", sa.String(128), nullable=False),
        sa.UniqueConstraint(
            "tenant_id",
            "actor_principal_id",
            "delegated_principal_id",
            "issued_at",
            name="uq_cp_delegation_grant",
        ),
    )
    op.create_index(
        "ix_cp_delegation_lookup", "cp_delegation", ["tenant_id", "actor_principal_id"]
    )


def downgrade() -> None:
    """Drop what the upgrade created, and nothing else.

    Destructive in the only sense a downgrade of this migration can be: the
    durable execution history, the outbox and the registry go with the tables. A
    deployment that has run real executions against these should export first —
    this is not a reversible step dressed as one.
    """
    for table in (
        "cp_delegation",
        "cp_authorization",
        "cp_binding",
        "cp_capability",
        "cp_worker",
        "cp_outbox",
        "cp_idempotency",
        "cp_node_lease",
        "cp_execution",
    ):
        op.drop_table(table)
