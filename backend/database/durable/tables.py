"""The durable schema for Phase 5.1. SQLAlchemy Core, no ORM, no domain types.

Why Core and not the ORM
--------------------------
An ORM gives an identity map, lazy loading and implicit flushes — three ways for
a write to happen at a moment the application did not choose. Phase 5.1's whole
point is that transaction boundaries are explicit, so the mapping layer is
deliberately the one that does nothing on its own.

Why the aggregate is a document, not a table per part
-------------------------------------------------------
``Execution`` already has a storage-agnostic projection —
``infrastructure/persistence.to_record`` — that flattens the whole aggregate,
runs every invariant again on the way back in, and **restores digests rather
than recomputing them**. Shredding it into ``execution`` / ``node_run`` /
``attempt`` / ``checkpoint`` tables would mean writing that mapping a second
time, in SQL, with a second set of invariants to keep in step. The first
divergence between the two is a run that loads with a digest that always matches
— a check that cannot fail.

So the aggregate is stored whole, in one column, and the fields that must be
*queried on*, *constrained* or *raced on* are promoted alongside it. The document
is authoritative for the aggregate; the columns are authoritative for
concurrency and lookup. Neither is a second domain model.

Where a separate table earns its place, it is because a **cross-process
invariant** needs a database constraint that a document cannot express:

    lease          one holder per node — a primary key
    idempotency    one key per tenant — a unique index
    outbox         one row per event id, ordered by one sequence
    capability     one contract per (id, version) — a unique index
    binding        one row per binding id, never overwritten
    worker         one registration per (scope owner, worker id)

Every one of those is an invariant two processes can violate simultaneously, and
therefore one only the database can hold.

Tenancy is a column, never a convention
-----------------------------------------
Every tenant-owned table carries ``tenant_id`` NOT NULL and every read is
narrowed by it through ``RepositoryGuard``. Platform-scoped rows — a platform
capability, a platform worker — carry the explicit sentinel below rather than
``NULL``, because a nullable owner is a row the tenant predicate cannot decide
about, and "cannot decide" resolves to "visible" in every query somebody writes
in a hurry.

That sentinel is **not a fake tenant**. It is never accepted from a request, is
refused as a tenant id by the guard's own validation, and exists only where the
domain already says the object has no tenant (``CapabilityTenancy.PLATFORM``,
``WorkerScope.PLATFORM``).

Portability
-------------
Written against SQLAlchemy Core with a ``JSONB`` variant for PostgreSQL. The same
DDL runs on SQLite, which is what makes the durability tests real — file-backed,
multi-process, with genuine transactions and genuine constraint violations —
rather than mocks.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

__all__ = [
    "DURABLE_METADATA",
    "queue_table",
    "leadership_table",
    "delegation_request_table",
    "connector_config_table",
    "PLATFORM_SCOPE",
    "SCHEMA_VERSION",
    "execution_table",
    "node_lease_table",
    "idempotency_table",
    "outbox_table",
    "worker_table",
    "capability_table",
    "binding_table",
    "authorization_table",
    "delegation_table",
    "audit_chain_table",
    "audit_record_table",
    "DURABLE_TABLES",
]

#: Bumped when the durable schema changes shape. Read at bootstrap and compared,
#: so a process running against a schema it was not built for refuses rather than
#: writing rows the next version cannot read.
SCHEMA_VERSION = 4

#: The explicit owner of a platform-scoped row.
#:
#: Chosen to be **unusable as a tenant id**: it contains characters the tenant
#: validators reject, so it cannot arrive from a request, a token or a header and
#: be mistaken for a real tenant. That is the difference between this and
#: ``tenant_id="system"``, which is a fake tenant and is forbidden.
PLATFORM_SCOPE = "@platform"

DURABLE_METADATA = sa.MetaData()

#: JSON on SQLite, JSONB on PostgreSQL. The document column type.
_DOC = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")

#: Timezone-aware everywhere. Every timestamp written by this layer is UTC and
#: comes from the **injected application clock**, never from the database — see
#: ADR-044 on the two-clock defect.
_TS = sa.DateTime(timezone=True)


# ----------------------------------------------------------------------
# Execution — the aggregate, its concurrency column, and its lookup keys
# ----------------------------------------------------------------------

execution_table = sa.Table(
    "cp_execution",
    DURABLE_METADATA,
    sa.Column("execution_id", sa.String(64), primary_key=True),
    sa.Column("tenant_id", sa.String(128), nullable=False),
    # The compare-and-swap column. ``UPDATE ... WHERE revision = :expected``
    # with a rowcount check is the whole cross-process guarantee: two dispatchers
    # reading the same run and writing back cannot both succeed, and the loser
    # gets a deterministic refusal rather than silently losing its decision.
    sa.Column("revision", sa.Integer, nullable=False),
    sa.Column("workflow_id", sa.String(128), nullable=False),
    sa.Column("workflow_digest", sa.String(128), nullable=True),
    sa.Column("mission_id", sa.String(128), nullable=True),
    sa.Column("state", sa.String(32), nullable=False),
    sa.Column("digest", sa.String(128), nullable=True),
    sa.Column("record", _DOC, nullable=False),
    sa.Column("created_at", _TS, nullable=False),
    sa.Column("updated_at", _TS, nullable=False),
    sa.Index("ix_cp_execution_tenant_state", "tenant_id", "state"),
    sa.Index("ix_cp_execution_tenant_workflow", "tenant_id", "workflow_id"),
)


# ----------------------------------------------------------------------
# Leases — one holder per node, enforced by the database
# ----------------------------------------------------------------------

node_lease_table = sa.Table(
    "cp_node_lease",
    DURABLE_METADATA,
    # One row per node, ever. The primary key *is* the invariant: a second
    # worker's INSERT collides rather than creating a rival lease, so "exactly
    # one worker holds this node" is held by the database and not by hope.
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
    # Increments on every grant for this node. A worker that was partitioned and
    # comes back holding a stale lease can be told so by comparing fences, which
    # a timestamp cannot do -- clocks disagree and a fence does not.
    sa.Column("fence", sa.Integer, nullable=False),
    sa.Index("ix_cp_lease_tenant_expiry", "tenant_id", "expires_at"),
)


# ----------------------------------------------------------------------
# Idempotency — one key per tenant, surviving restart
# ----------------------------------------------------------------------

idempotency_table = sa.Table(
    "cp_idempotency",
    DURABLE_METADATA,
    sa.Column("tenant_id", sa.String(128), primary_key=True),
    sa.Column("idempotency_key", sa.String(256), primary_key=True),
    sa.Column("execution_id", sa.String(64), nullable=False),
    sa.Column("node_id", sa.String(128), nullable=True),
    sa.Column("action_digest", sa.String(128), nullable=True),
    sa.Column("outcome", sa.String(32), nullable=True),
    sa.Column("created_at", _TS, nullable=False),
    sa.Column("updated_at", _TS, nullable=False),
)


# ----------------------------------------------------------------------
# Outbox — ordered, exclusively claimable, at-least-once
# ----------------------------------------------------------------------

outbox_table = sa.Table(
    "cp_outbox",
    DURABLE_METADATA,
    # Database-assigned and monotonic, and the **primary key** rather than a
    # side column: an auto-incrementing value is generated portably only as the
    # integer primary key, and causal order is the thing this table exists to
    # get right. Order comes from here and never from a timestamp -- two events
    # recorded in the same microsecond tie on a clock, and a tie means two
    # publishers can disagree about which fact came first.
    # ``BigInteger`` everywhere except SQLite, which auto-increments only an
    # ``INTEGER PRIMARY KEY``. The variant keeps one schema definition working on
    # the production database and on the one the durability tests actually run
    # against, rather than testing a different table than production uses.
    sa.Column(
        "sequence",
        sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
        primary_key=True,
        autoincrement=True,
    ),
    # The stable, caller-derivable identity. Unique rather than primary so that
    # re-recording the same event collides here instead of appending.
    sa.Column("entry_id", sa.String(96), nullable=False, unique=True),
    sa.Column("tenant_id", sa.String(128), nullable=False),
    sa.Column("execution_id", sa.String(64), nullable=False),
    sa.Column("event_type", sa.String(128), nullable=False),
    sa.Column("event_id", sa.String(64), nullable=True),
    sa.Column("payload", _DOC, nullable=False),
    sa.Column("status", sa.String(16), nullable=False),
    sa.Column("attempts", sa.Integer, nullable=False),
    sa.Column("claimed_by", sa.String(128), nullable=True),
    sa.Column("claimed_until", _TS, nullable=True),
    sa.Column("published_at", _TS, nullable=True),
    sa.Column("last_error", sa.String(512), nullable=True),
    sa.Column("recorded_at", _TS, nullable=False),
    # One row per event identity. Delivery stays **at-least-once** — a consumer
    # can be handed the same event twice and must deduplicate — but the same
    # event is never *recorded* twice, so a replayed command cannot silently
    # double the log.
    sa.UniqueConstraint("tenant_id", "event_id", name="uq_cp_outbox_event_id"),
    sa.Index("ix_cp_outbox_claimable", "tenant_id", "status", "sequence"),
    sa.Index("ix_cp_outbox_execution", "tenant_id", "execution_id", "sequence"),
)


# ----------------------------------------------------------------------
# Worker directory — registrations, not adapters
# ----------------------------------------------------------------------

worker_table = sa.Table(
    "cp_worker",
    DURABLE_METADATA,
    # ``scope_owner`` is the tenant for a tenant worker and ``PLATFORM_SCOPE``
    # for a platform one. Part of the key so a tenant cannot occupy the platform
    # slot for an id — shadowing would redirect platform work into an adapter a
    # tenant controls, which is a privilege escalation that looks like a naming
    # collision.
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
    sa.Column("record", _DOC, nullable=False),
    sa.Column("reason", sa.String(512), nullable=True),
    sa.Column("registered_at", _TS, nullable=False),
    sa.Column("updated_at", _TS, nullable=False),
    sa.Index("ix_cp_worker_kind", "worker_kind"),
)


# ----------------------------------------------------------------------
# Capability registry — identity immutable, contract immutable
# ----------------------------------------------------------------------

capability_table = sa.Table(
    "cp_capability",
    DURABLE_METADATA,
    sa.Column("reference", sa.String(512), primary_key=True),
    sa.Column("capability_id", sa.String(256), nullable=False),
    sa.Column("version", sa.Integer, nullable=False),
    # ``PLATFORM_SCOPE`` for a platform capability. Not NULL, so the tenant
    # predicate always has something to decide about.
    sa.Column("scope_owner", sa.String(128), nullable=False),
    sa.Column("tenant_id", sa.String(128), nullable=True),
    sa.Column("provider", sa.String(128), nullable=False),
    sa.Column("status", sa.String(24), nullable=False),
    sa.Column("trust", sa.String(24), nullable=False),
    # The contract digest, stored exactly as registered and never recomputed on
    # load. This is the value an approval was granted against.
    sa.Column("digest", sa.String(128), nullable=True),
    sa.Column("record", _DOC, nullable=False),
    sa.Column("registered_at", _TS, nullable=False),
    sa.Column("updated_at", _TS, nullable=True),
    sa.UniqueConstraint("capability_id", "version", name="uq_cp_capability_version"),
    sa.Index("ix_cp_capability_scope", "scope_owner", "capability_id"),
)


# ----------------------------------------------------------------------
# Bindings — append-only, never updated
# ----------------------------------------------------------------------

binding_table = sa.Table(
    "cp_binding",
    DURABLE_METADATA,
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
    sa.Column("record", _DOC, nullable=False),
    sa.Column("created_at", _TS, nullable=False),
    sa.Index("ix_cp_binding_execution", "tenant_id", "execution_id"),
)


# ----------------------------------------------------------------------
# Authorization decisions — evidence, not a second engine
# ----------------------------------------------------------------------

authorization_table = sa.Table(
    "cp_authorization",
    DURABLE_METADATA,
    sa.Column("decision_id", sa.String(64), primary_key=True),
    sa.Column("tenant_id", sa.String(128), nullable=False),
    sa.Column("principal_id", sa.String(128), nullable=False),
    # Recorded when the decision was about delegated execution. Distinct from
    # ``principal_id`` because an actor acting for somebody and an actor acting
    # for themselves are different authorities.
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
    sa.Column("record", _DOC, nullable=False),
    sa.Index("ix_cp_authz_tenant_action", "tenant_id", "action_digest"),
    sa.Index("ix_cp_authz_digest", "decision_digest"),
)


# ----------------------------------------------------------------------
# Delegation — the persistence seam only (ADR-043 §4, ADR-044)
# ----------------------------------------------------------------------

delegation_table = sa.Table(
    "cp_delegation",
    DURABLE_METADATA,
    # **A seam, not a workflow.** Phase 4.4 refuses every on-behalf-of
    # invocation because no authoritative delegation model exists. This table is
    # the shape such a model needs; issuing, approving and revoking are Phase 5.2
    # work and are deliberately not implemented.
    #
    # Default remains safe: an empty table means no delegation exists, and no
    # delegation means every on-behalf-of invocation is refused.
    sa.Column("delegation_id", sa.String(64), primary_key=True),
    sa.Column("tenant_id", sa.String(128), nullable=False),
    sa.Column("actor_principal_id", sa.String(128), nullable=False),
    sa.Column("delegated_principal_id", sa.String(128), nullable=False),
    # What the actor may do *as* the delegated principal -- capability
    # references and operations. A delegation with no scope would be a
    # delegation of everything, so an empty scope is refused by the repository
    # rather than stored and read as permissive later.
    sa.Column("scope", _DOC, nullable=False),
    sa.Column("issued_by", sa.String(128), nullable=False),
    sa.Column("issued_at", _TS, nullable=False),
    sa.Column("expires_at", _TS, nullable=False),
    sa.Column("revoked_at", _TS, nullable=True),
    sa.Column("revocation_reason", sa.String(512), nullable=True),
    sa.Column("digest", sa.String(128), nullable=False),
    # Phase 5.3 issuance evidence. Nullable because Phase 5.1 rows predate the
    # workflow; the workflow itself refuses to issue without them, so a grant
    # with no request is one that was created before there was a way to ask.
    sa.Column("request_id", sa.String(64), nullable=True),
    sa.Column("approval_artifact_id", sa.String(64), nullable=True),
    sa.Column("approved_by", sa.String(128), nullable=True),
    sa.Column("revoked_by", sa.String(128), nullable=True),
    sa.UniqueConstraint(
        "tenant_id",
        "actor_principal_id",
        "delegated_principal_id",
        "issued_at",
        name="uq_cp_delegation_grant",
    ),
    sa.Index("ix_cp_delegation_lookup", "tenant_id", "actor_principal_id"),
)


# ----------------------------------------------------------------------
# Work queue — availability, never state (Phase 5.2)
# ----------------------------------------------------------------------

queue_table = sa.Table(
    "cp_queue",
    DURABLE_METADATA,
    # One row per (execution, node). The primary key is what makes enqueuing the
    # same node twice a no-op rather than a duplicate: two dispatchers deciding a
    # node is ready both INSERT, and the second collides.
    sa.Column("execution_id", sa.String(64), primary_key=True),
    sa.Column("node_id", sa.String(128), primary_key=True),
    sa.Column("tenant_id", sa.String(128), nullable=False),
    # **References, never authority.** The queue says a node may be worth looking
    # at; what may actually run is re-derived from the execution aggregate, the
    # binding and the authorization every time. Reconstructing authority from
    # these columns would make a queue row a grant.
    sa.Column("workflow_id", sa.String(128), nullable=True),
    sa.Column("workflow_digest", sa.String(128), nullable=True),
    sa.Column("worker_kind", sa.String(32), nullable=False),
    sa.Column("attempt_id", sa.String(64), nullable=True),
    sa.Column("priority", sa.Integer, nullable=False),
    # When this becomes eligible. A planned retry is enqueued with a future
    # value rather than held in memory until its backoff elapses -- memory does
    # not survive the restart that made the retry necessary.
    sa.Column("available_at", _TS, nullable=False),
    sa.Column("enqueued_at", _TS, nullable=False),
    # Database-assigned and monotonic. The deterministic tiebreak: two items with
    # equal priority and equal availability still have exactly one order, and it
    # is the order they were enqueued in rather than whatever the rows come back
    # in.
    sa.Column(
        "sequence",
        sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
        nullable=False,
        unique=True,
        autoincrement=False,
    ),
    sa.Column("claimed_by", sa.String(128), nullable=True),
    sa.Column("claimed_until", _TS, nullable=True),
    sa.Column("claim_count", sa.Integer, nullable=False),
    sa.Index(
        "ix_cp_queue_claimable",
        "tenant_id",
        "worker_kind",
        "available_at",
        "priority",
        "sequence",
    ),
)


# ----------------------------------------------------------------------
# Leadership — singleton roles, fenced (Phase 5.2)
# ----------------------------------------------------------------------

leadership_table = sa.Table(
    "cp_leadership",
    DURABLE_METADATA,
    # One row per role, forever. The row outlives every leader, which is what
    # makes the fencing token monotonic: it is incremented in place on each
    # acquisition and therefore never repeats and never goes backwards.
    #
    # ``scope`` is the tenant for a tenant-scoped role or the platform sentinel
    # for a platform one -- part of the key so a tenant cannot take a platform
    # role by naming it.
    sa.Column("scope", sa.String(128), primary_key=True),
    sa.Column("role", sa.String(64), primary_key=True),
    sa.Column("instance_id", sa.String(128), nullable=True),
    # Monotonic, durable, and the only thing a stale process can be caught by.
    # Never a UUID and never a timestamp: a UUID has no order and two clocks
    # disagree, and "which of these two writers is newer" is exactly the
    # question a fence has to answer.
    sa.Column("fencing_token", sa.BigInteger, nullable=False),
    sa.Column("acquired_at", _TS, nullable=True),
    sa.Column("heartbeat_at", _TS, nullable=True),
    sa.Column("expires_at", _TS, nullable=True),
    sa.Column("released_at", _TS, nullable=True),
    sa.Column("status", sa.String(16), nullable=False),
    sa.Index("ix_cp_leadership_expiry", "expires_at"),
)


# ----------------------------------------------------------------------
# Delegation request and approval evidence (Phase 5.3)
# ----------------------------------------------------------------------

delegation_request_table = sa.Table(
    "cp_delegation_request",
    DURABLE_METADATA,
    # **A request is not authority.** This table records that somebody asked;
    # nothing here authorizes anything, and the delegation it may eventually
    # produce lives in ``cp_delegation`` behind an approval.
    sa.Column("request_id", sa.String(64), primary_key=True),
    sa.Column("tenant_id", sa.String(128), nullable=False),
    sa.Column("requested_by", sa.String(128), nullable=False),
    sa.Column("actor_principal_id", sa.String(128), nullable=False),
    sa.Column("delegated_principal_id", sa.String(128), nullable=False),
    sa.Column("scope", _DOC, nullable=False),
    sa.Column("reason", sa.String(1024), nullable=False),
    sa.Column("requested_validity_seconds", sa.Integer, nullable=False),
    sa.Column("requested_at", _TS, nullable=False),
    sa.Column("expires_at", _TS, nullable=False),
    # The digest an approval binds to. Changing the actor, the delegated
    # principal, the scope or the validity changes this, so an approval granted
    # against the old value stops matching -- which is the whole mechanism.
    sa.Column("request_digest", sa.String(128), nullable=False),
    sa.Column("status", sa.String(16), nullable=False),
    # Approval evidence, written only by the approval step.
    sa.Column("approved_by", sa.String(128), nullable=True),
    sa.Column("approved_at", _TS, nullable=True),
    sa.Column("approval_artifact_id", sa.String(64), nullable=True),
    sa.Column("approval_digest", sa.String(128), nullable=True),
    sa.Column("decision_reason", sa.String(1024), nullable=True),
    sa.Column("issued_delegation_id", sa.String(64), nullable=True),
    sa.Index("ix_cp_delreq_tenant_status", "tenant_id", "status"),
    sa.Index("ix_cp_delreq_pair", "tenant_id", "actor_principal_id",
             "delegated_principal_id"),
)


# ----------------------------------------------------------------------
# Connector configuration — references, never secrets (Phase 5.3)
# ----------------------------------------------------------------------

connector_config_table = sa.Table(
    "cp_connector_config",
    DURABLE_METADATA,
    # One configuration per (tenant, provider, environment). Tenant first in the
    # key so a configuration cannot exist without one -- the V1 surface this
    # replaces had no tenant at all, which is why one authenticated user could
    # set a provider credential for the whole process.
    sa.Column("tenant_id", sa.String(128), primary_key=True),
    sa.Column("provider_id", sa.String(128), primary_key=True),
    sa.Column("environment", sa.String(16), primary_key=True),
    sa.Column("endpoint", sa.String(2048), nullable=False),
    # **A reference, never material.** The column is short on purpose: a
    # credential reference is ``cred://<tenant>/<id>`` and a token is not, so a
    # secret pasted here does not fit -- and the repository refuses one before
    # it gets this far.
    sa.Column("credential_ref", sa.String(256), nullable=True),
    sa.Column("credential_scope", _DOC, nullable=False),
    sa.Column("policy", _DOC, nullable=False),
    sa.Column("status", sa.String(16), nullable=False),
    sa.Column("digest", sa.String(128), nullable=False),
    sa.Column("configured_by", sa.String(128), nullable=False),
    sa.Column("created_at", _TS, nullable=False),
    sa.Column("updated_at", _TS, nullable=False),
    sa.Index("ix_cp_connector_config_provider", "provider_id", "environment"),
)


# ----------------------------------------------------------------------
# Audit chain — the tail in a store the fence can reach (Phase 5.12)
# ----------------------------------------------------------------------

audit_chain_table = sa.Table(
    "cp_audit_chain",
    DURABLE_METADATA,
    # One row per chain, forever -- the same shape as ``cp_leadership``: a row
    # that outlives every writer, mutated conditionally, never deleted. The
    # chain identity is the platform sentinel for the platform's single
    # evidence chain; the column exists so the schema does not have to change
    # if a future ADR ever shards the trail.
    sa.Column("chain_id", sa.String(128), primary_key=True),
    # The next sequence to be written, advanced by the same transaction that
    # inserts the record. ``UPDATE ... WHERE next_sequence = :expected`` is the
    # single authoritative tail: two writers cannot both advance it past the
    # same value, so the chain physically cannot fork -- an invariant only the
    # database can hold, which is what earns this table its place (see the
    # module docstring).
    sa.Column("next_sequence", sa.BigInteger, nullable=False),
    # Digest value of the most recent record. Carried in the tail-advance
    # predicate so an append whose ``previous_digest`` does not extend the
    # durable head is refused by rowcount rather than discovered by an auditor.
    sa.Column("head_digest", sa.String(128), nullable=True),
)


audit_record_table = sa.Table(
    "cp_audit_record",
    DURABLE_METADATA,
    # The chain position is the identity. A primary key on (chain, sequence)
    # makes "two records at one sequence" a constraint violation rather than a
    # verification finding -- the second copy of the Phase 5.10 corruption
    # cannot be written at all.
    sa.Column("chain_id", sa.String(128), primary_key=True),
    sa.Column("sequence", sa.BigInteger, primary_key=True),
    sa.Column("event_id", sa.String(64), nullable=False, unique=True),
    # Promoted for reads: ``AuditQuery`` narrows on these in SQL rather than
    # loading a chain into memory to discard most of it. The document below
    # remains authoritative for the record; these columns are authoritative for
    # lookup -- the same split every other durable aggregate here uses.
    sa.Column("tenant_id", sa.String(128), nullable=False),
    sa.Column("kind", sa.String(64), nullable=False),
    sa.Column("recorded_at", _TS, nullable=False),
    sa.Column("subject_reference", sa.String(512), nullable=True),
    sa.Column("correlation_id", sa.String(128), nullable=True),
    sa.Column("actor_id", sa.String(128), nullable=True),
    # The chain fields, promoted so an operator can inspect linkage in SQL.
    # Digest *values*; the algorithm travels inside the document.
    sa.Column("entry_digest", sa.String(128), nullable=False),
    sa.Column("previous_digest", sa.String(128), nullable=True),
    # Which fencing token wrote this record. Evidence, not enforcement: the
    # enforcement is the fenced transaction that inserted the row. NULL means
    # the append was unfenced -- the single-writer development deployment.
    sa.Column("writer_token", sa.BigInteger, nullable=True),
    # The full record, exactly as ``AuditEvent.to_dict()`` produced it.
    # Restored with ``AuditEvent.from_dict`` and digests are **restored, never
    # recomputed** on the way out -- recomputation is what verification does,
    # deliberately, in ``verify_chain``. Canonical hashing sorts object keys,
    # so JSONB's key reordering cannot perturb a digest; verified explicitly in
    # Phase 5.12.
    sa.Column("document", _DOC, nullable=False),
    sa.Index("ix_cp_audit_record_tenant", "chain_id", "tenant_id", "sequence"),
    sa.Index("ix_cp_audit_record_recorded", "recorded_at"),
    sa.Index("ix_cp_audit_record_correlation", "correlation_id"),
)


harness_trace_table = sa.Table(
    "cp_harness_trace",
    DURABLE_METADATA,
    # Phase 6.1, L14. Append-only harness evidence, joined to the audit chain
    # by correlation_id — never part of it (the audit runtime bans traces from
    # the chain). Spans arrive redacted-at-construction; this table never sees
    # an unredacted prompt, output, or tool payload.
    sa.Column("span_record_id", sa.Text(), primary_key=True),
    sa.Column("kind", sa.Text(), nullable=False),
    sa.Column("mission_id", sa.Text(), nullable=False),
    sa.Column("iteration", sa.Integer(), nullable=False),
    sa.Column("step_id", sa.Text(), nullable=False),
    sa.Column("harness_version", sa.Text(), nullable=False),
    sa.Column("correlation_id", sa.Text(), nullable=False),
    sa.Column("trace_id", sa.Text(), nullable=False),
    sa.Column("trace_span_id", sa.Text(), nullable=False),
    sa.Column("started_at", sa.Text(), nullable=False),
    sa.Column("finished_at", sa.Text(), nullable=False),
    sa.Column("record", _DOC, nullable=False),
    sa.Column("recorded_at", _TS, nullable=False),
    sa.Index("ix_cp_harness_trace_correlation", "correlation_id"),
    sa.Index("ix_cp_harness_trace_mission", "mission_id", "iteration"),
    sa.Index("ix_cp_harness_trace_version", "harness_version"),
)


world_observation_table = sa.Table(
    "cw_observation",
    DURABLE_METADATA,
    # Phase 7.2, ADR-064. The World Plane's first durable ledger: raw external
    # observations, append-only and immutable. An observation is NOT a fact —
    # it carries no valid-time interval and no authority; deriving facts is a
    # later phase. It never holds credential material (the ingestion boundary
    # runs a field-aware secret firewall before this table sees a value).
    #
    # ``cw_`` (world) not ``cp_`` (platform/execution): a separate ledger the
    # execution fabric neither reads nor writes. Same durable template — tenant
    # NOT NULL, app-clock timestamps, digest identity — as the cp_* tables.
    sa.Column("observation_id", sa.Text(), primary_key=True),
    # Deterministic identity for idempotency: a digest over
    # (tenant, source, subject, predicate, observed_at, value). A duplicate
    # delivery of the same external observation collides here and is refused by
    # the unique constraint rather than creating uncontrolled duplicate world
    # state. At-least-once ingestion, deterministic identity — NOT exactly-once.
    sa.Column("identity_digest", sa.String(128), nullable=False, unique=True),
    sa.Column("tenant_id", sa.String(128), nullable=False),
    # Source: an instrument reference (connector/probe/execution/human), never
    # a model. The kind is validated against ObservationSourceKind, which has
    # no MODEL member.
    sa.Column("source_kind", sa.String(32), nullable=False),
    sa.Column("source_ref", sa.Text(), nullable=False),
    sa.Column("subject_ref", sa.Text(), nullable=False),
    sa.Column("predicate", sa.Text(), nullable=False),
    # SourceStatus (contracts.evidence): returned_data / returned_empty /
    # unavailable / not_configured — empty is not unavailable is not
    # not-configured.
    sa.Column("status", sa.String(32), nullable=False),
    # observed_at (when the world was in the observed state, per the instrument)
    # is DISTINCT from recorded_at (when CortexPrime wrote the row). Both are
    # app-clock, tz-aware. retrieved_at is when the instrument was queried.
    sa.Column("observed_at", _TS, nullable=False),
    sa.Column("retrieved_at", _TS, nullable=False),
    sa.Column("recorded_at", _TS, nullable=False),
    # The full Observation contract document (subject/predicate/value/status/
    # instant/source/provenance) as its canonical to_dict — the authoritative
    # record; the promoted columns above are for lookup. Redacted-at-ingestion:
    # a value that carried a secret was refused before reaching here.
    sa.Column("record", _DOC, nullable=False),
    # Provenance producer label, promoted for lookup (references only, no
    # secrets — enforced by the ProvenanceRef contract + the secret firewall).
    sa.Column("produced_by", sa.Text(), nullable=False),
    sa.Column("schema_version", sa.Integer(), nullable=False),
    sa.Index("ix_cw_observation_tenant_subject", "tenant_id", "subject_ref"),
    sa.Index("ix_cw_observation_observed_at", "observed_at"),
    sa.Index("ix_cw_observation_source", "source_kind", "source_ref"),
)


world_fact_table = sa.Table(
    "cw_fact",
    DURABLE_METADATA,
    # Phase 7.3, ADR-065. The World Plane's bitemporal FACT ledger, derived
    # deterministically from cw_observation. Append-only *version* records: a
    # correction or a world-state change is a NEW row, never an overwrite —
    # historical world state stays reconstructable (STEP 7/13). A Fact is NOT an
    # Observation: it carries valid-time (validity) and an authority tier, and it
    # is grounded in a real Observation (never a model). Same durable template as
    # cw_observation.
    #
    # Two independent temporal axes are kept distinct (the whole point):
    #   valid_from / valid_to  — WORLD/VALID time: when the state was true.
    #   recorded_at            — KNOWLEDGE/TRANSACTION time: when CortexPrime
    #                            recorded this version. A value valid_from 09:58
    #                            can be recorded_at 10:10 and neither overwrites
    #                            the other. valid_to is usually NULL (open, "as
    #                            asserted"); the effective end is DERIVED from
    #                            succeeding versions at query time, so no prior
    #                            row is ever mutated.
    sa.Column("fact_id", sa.Text(), primary_key=True),
    # Deterministic version identity for idempotency: a digest over
    # (semantic_identity, value_digest, valid_from). The same observation derived
    # twice collides here and is refused — at-least-once derivation, deterministic
    # identity, NOT exactly-once (mirrors cw_observation).
    sa.Column("version_digest", sa.String(128), nullable=False, unique=True),
    # The SEMANTIC identity of the real-world proposition: a digest over
    # (tenant, subject_ref, predicate). Every version/state of "deployment/
    # payments spec.replicas" shares this; it is NOT a random UUID. Indexed
    # because every temporal query narrows on it.
    sa.Column("semantic_identity", sa.String(128), nullable=False),
    sa.Column("tenant_id", sa.String(128), nullable=False),
    sa.Column("subject_ref", sa.Text(), nullable=False),
    sa.Column("predicate", sa.Text(), nullable=False),
    # The value digest promotes value-equality to a column; the full structured
    # value lives in the record document (never prose — a fact is structured
    # observation-derived state, not an interpretation).
    sa.Column("value_digest", sa.String(128), nullable=False),
    sa.Column("valid_from", _TS, nullable=False),
    sa.Column("valid_to", _TS, nullable=True),
    # EpistemicStatus at assertion (affirmed/conflicted/... — never FALSE from
    # absence). The query-time projection is authoritative for the *current*
    # status of a valid instant; this is the status as written.
    sa.Column("status", sa.String(32), nullable=False),
    # KnowledgeAuthority tier (authoritative/advisory). A single uncorroborated
    # source derives ADVISORY — authority is provenance-derived, never a number
    # a model invents.
    sa.Column("authority", sa.String(32), nullable=False),
    sa.Column("recorded_at", _TS, nullable=False),
    # The full Fact contract document (Fact.to_dict) — authoritative for the
    # version; the promoted columns are for lookup. Carries no credential
    # material (grounded in an observation the ingestion firewall already
    # cleared; provenance is references only).
    sa.Column("record", _DOC, nullable=False),
    sa.Column("produced_by", sa.Text(), nullable=False),
    # Grounding: the observation this fact was derived from (never a model).
    sa.Column("observation_ref", sa.Text(), nullable=False),
    # Supersession/conflict lineage: the prior fact version this one succeeds or
    # conflicts with. References, not deletion — the prior row remains.
    sa.Column("parent_claim_ref", sa.Text(), nullable=True),
    sa.Column("schema_version", sa.Integer(), nullable=False),
    sa.Index("ix_cw_fact_identity", "tenant_id", "semantic_identity"),
    sa.Index("ix_cw_fact_recorded_at", "recorded_at"),
)


world_verification_table = sa.Table(
    "cw_verification",
    DURABLE_METADATA,
    # Phase 7.7, ADR-069. The Assurance Plane's append-only ledger of independent
    # verification decisions. A verification is an externally-meaningful
    # historical decision ("at this knowledge time the platform verified/refuted
    # claim X against independent evidence Y") that cannot be safely re-derived —
    # the claim being verified is ephemeral model output. Immutable: a re-check is
    # a new row, never an overwrite. Same durable template as cw_observation /
    # cw_fact.
    sa.Column("verification_id", sa.Text(), primary_key=True),
    # Deterministic identity for idempotency: digest over (tenant, procedure kind,
    # subject, predicate, expected, producer reasoning path, verified_at). The
    # same verification re-run collides and is refused. At-least-once, NOT
    # exactly-once.
    sa.Column("identity_digest", sa.String(128), nullable=False, unique=True),
    sa.Column("tenant_id", sa.String(128), nullable=False),
    sa.Column("subject_ref", sa.Text(), nullable=False),
    sa.Column("predicate", sa.Text(), nullable=False),
    sa.Column("procedure_ref", sa.Text(), nullable=False),
    # SUPPORTED / UNSUPPORTED / INSUFFICIENT_EVIDENCE — never FALSE, never
    # "timeout = success". A missing/stale/conflicted/unknown adjudication is
    # INSUFFICIENT, not SUPPORTED.
    sa.Column("verdict", sa.String(32), nullable=False),
    # Explicit verifier identity. model_identifier is NULL for the deterministic
    # platform verifier. reasoning_path distinct from the producer's — recorded so
    # independence is auditable, not assumed.
    sa.Column("verifier_id", sa.Text(), nullable=False),
    sa.Column("verifier_reasoning_path", sa.Text(), nullable=False),
    sa.Column("producer_reasoning_path", sa.Text(), nullable=False),
    # verified_at is the knowledge time of the decision; recorded_at is when the
    # row was written. Both app-clock, tz-aware.
    sa.Column("verified_at", _TS, nullable=False),
    sa.Column("recorded_at", _TS, nullable=False),
    # The full WorldVerification document (subject/procedure/verifier/verdict/
    # evidence_refs) as its canonical to_dict — authoritative; the columns are for
    # lookup. Carries references only, no credential material.
    sa.Column("record", _DOC, nullable=False),
    sa.Column("schema_version", sa.Integer(), nullable=False),
    sa.Index("ix_cw_verification_subject", "tenant_id", "subject_ref"),
    sa.Index("ix_cw_verification_recorded_at", "recorded_at"),
)


world_reasoning_table = sa.Table(
    "cw_reasoning",
    DURABLE_METADATA,
    # Phase 7.8, ADR-070. The durable reasoning trail — the smallest append-only
    # representation of the model-authored reasoning artifacts that cannot be
    # reconstructed from the observation/fact ledgers: a grounded hypothesis, a
    # prediction, and (the calibration payload) a prediction evaluation. Beliefs
    # stay derived projections; observations/facts/verifications live in their own
    # ledgers; this holds only what is genuinely non-derivable and externally
    # meaningful. Immutable — a revised hypothesis is a new row, never an
    # overwrite. Same durable template as the other cw_* ledgers.
    sa.Column("reasoning_id", sa.Text(), primary_key=True),
    # Deterministic identity for idempotency: digest over (tenant, kind, subject,
    # predicate, record). Re-recording the same reasoning artifact collides and is
    # refused. At-least-once, NOT exactly-once.
    sa.Column("identity_digest", sa.String(128), nullable=False, unique=True),
    sa.Column("tenant_id", sa.String(128), nullable=False),
    # hypothesis / prediction / prediction_evaluation.
    sa.Column("kind", sa.String(32), nullable=False),
    sa.Column("subject_ref", sa.Text(), nullable=False),
    sa.Column("predicate", sa.Text(), nullable=True),
    # The full contract/record document (Hypothesis / Prediction /
    # PredictionEvaluation to_dict) — authoritative; the columns are for lookup.
    # Runs through the field-aware secret firewall before it reaches here: no
    # credential material, references and digests only.
    sa.Column("record", _DOC, nullable=False),
    # The provenance-graph cross-references (hypothesis_ref, prediction_ref,
    # execution_ref, outcome_ref, evidence_refs) promoted so the chain is
    # queryable without loading every document.
    sa.Column("refs", _DOC, nullable=False),
    sa.Column("recorded_at", _TS, nullable=False),
    sa.Column("schema_version", sa.Integer(), nullable=False),
    sa.Index("ix_cw_reasoning_subject", "tenant_id", "subject_ref"),
    sa.Index("ix_cw_reasoning_kind", "tenant_id", "kind"),
    sa.Index("ix_cw_reasoning_recorded_at", "recorded_at"),
)


world_investigation_table = sa.Table(
    "cw_investigation",
    DURABLE_METADATA,
    # Phase 8.1, ADR-072. The Intelligence Plane's durable investigation ledger.
    # An investigation is a stateful workflow (status machine + differential +
    # open questions + checkpoint) that is NOT reconstructable from the World
    # ledgers — those hold evidence/facts/verifications, not the loop's phase. So
    # it is event-sourced here: each row is one immutable event carrying the full
    # new aggregate SNAPSHOT; the latest committed snapshot (max seq) is the
    # authoritative current state. Crash recovery restores that snapshot and never
    # fabricates progress. Append-only: no row is ever updated or deleted.
    sa.Column("event_id", sa.Text(), primary_key=True),
    # One event per (investigation, seq). The unique digest gives optimistic
    # concurrency (two writers at the same seq collide) and idempotency. At-least-
    # once, deterministic identity — NOT exactly-once.
    sa.Column("identity_digest", sa.String(128), nullable=False, unique=True),
    sa.Column("investigation_id", sa.Text(), nullable=False),
    sa.Column("tenant_id", sa.String(128), nullable=False),
    sa.Column("incident_ref", sa.Text(), nullable=False),
    sa.Column("seq", sa.Integer(), nullable=False),
    sa.Column("event_kind", sa.String(32), nullable=False),
    sa.Column("from_status", sa.String(32), nullable=True),
    sa.Column("to_status", sa.String(32), nullable=False),
    # Platform-set autonomy (A0..A4); never promotable by a model.
    sa.Column("autonomy_level", sa.String(32), nullable=False),
    # The full Investigation aggregate snapshot after this event — authoritative
    # for reconstruction. Secret-firewalled before it reaches here (references and
    # digests only, no credential material, no chain-of-thought).
    sa.Column("state", _DOC, nullable=False),
    # The event-specific payload (the question/hypothesis/test/human-event/refs).
    sa.Column("payload", _DOC, nullable=False),
    sa.Column("recorded_at", _TS, nullable=False),
    sa.Column("schema_version", sa.Integer(), nullable=False),
    sa.Index("ix_cw_investigation_seq", "tenant_id", "investigation_id", "seq"),
    sa.Index("ix_cw_investigation_incident", "tenant_id", "incident_ref"),
    sa.Index("ix_cw_investigation_recorded_at", "recorded_at"),
)


approval_table = sa.Table(
    "cp_approval",
    DURABLE_METADATA,
    # Phase 10.3, ADR-096. The durable home of the approval system that had a
    # contract, a port and a gateway check but no storage: until now the only
    # ApprovalLookup implementations were NoApprovals (fail-closed) and an
    # in-memory dict inside a harness. A product cannot use that -- a human
    # approves in one request and the execution reads it back in another.
    #
    # This table stores approvals. It does NOT decide about them: whether an
    # approval covers an action is still answered by ApprovalFacts.is_valid_for
    # and re-answered by the gateway's action-digest comparison. Adding a second
    # decider here is the specific mistake ADR-090 exists to prevent.
    sa.Column("approval_id", sa.Text(), primary_key=True),
    # Deterministic identity for idempotency: a digest over the request. The
    # same request re-submitted collides and returns the existing approval
    # rather than creating a second one that could be decided differently.
    sa.Column("identity_digest", sa.String(128), nullable=False, unique=True),
    sa.Column("tenant_id", sa.String(128), nullable=False),
    # What was asked for, as the PLATFORM reconstructed it. No value in this row
    # was supplied by a browser.
    sa.Column("capability_ref", sa.Text(), nullable=False),
    sa.Column("capability_digest", sa.String(128), nullable=False),
    # TWO operations, deliberately separate. ``operation`` is the provider
    # operation this approval will perform (kubernetes.workload.rollout_restart);
    # ``authorization_operation`` is the verb AUTHORIZATION is asked about
    # (invoke / inspect / ...), which is what ApprovalFacts.is_valid_for
    # compares. Storing one value for both looks tidier and silently breaks the
    # check that stops an approval to READ authorizing a DELETE.
    sa.Column("operation", sa.String(128), nullable=False),
    sa.Column("authorization_operation", sa.String(32), nullable=False),
    sa.Column("environment", sa.String(32), nullable=False),
    sa.Column("principal_id", sa.Text(), nullable=False),
    # The validated input the approval covers. Stored so an auditor can see what
    # was approved rather than only its digest -- and so the digest can be
    # recomputed and checked rather than trusted.
    sa.Column("payload", _DOC, nullable=False),
    # The ADR-090 canonical approval digest. This is the binding that stops an
    # approval for workload A authorizing workload B, and it is computed by the
    # platform's own function at request time, never accepted from a caller.
    sa.Column("approval_digest", sa.String(128), nullable=False),
    # GRANTED / DENIED / PENDING, as the ApprovalOutcome contract names them.
    sa.Column("outcome", sa.String(32), nullable=False),
    # The authenticated human who decided. A namespaced identity reference
    # ("human:<id>"), taken from the verified session -- never from a request
    # body, and never the string "admin".
    sa.Column("requested_by", sa.Text(), nullable=False),
    sa.Column("decided_by", sa.Text(), nullable=True),
    sa.Column("justification", sa.Text(), nullable=True),
    # An approval that never expires is a standing authorization nobody granted.
    sa.Column("expires_at", _TS, nullable=False),
    sa.Column("requested_at", _TS, nullable=False),
    sa.Column("decided_at", _TS, nullable=True),
    # Set once the approval has authorized an execution, so a second use is
    # visible. It does NOT by itself refuse the second use -- at-least-once is
    # the platform contract and this table does not get to change it.
    sa.Column("consumed_by_execution", sa.Text(), nullable=True),
    sa.Column("investigation_ref", sa.Text(), nullable=True),
    sa.Column("schema_version", sa.Integer(), nullable=False),
    sa.Index("ix_cp_approval_tenant", "tenant_id", "requested_at"),
    sa.Index("ix_cp_approval_investigation", "tenant_id", "investigation_ref"),
)


# ----------------------------------------------------------------------
# Authority grants — the durable home authority never had (Phase 10.8)
# ----------------------------------------------------------------------

authority_grant_table = sa.Table(
    "cp_authority_grant",
    DURABLE_METADATA,
    # Phase 10.8, ADR-101. Phases 10.5-10.7 built scoped approver and executor
    # authority and then read it out of ``data/tenants/tenant_users.json`` -- a
    # gitignored file, holding bare strings, with no issuer, no timestamps, no
    # digest and no audit. Enforcement was governed; creation was not.
    #
    # This table does NOT decide anything. ``resolve_scoped_authority`` still
    # answers "may this human take this action on this approval", exactly as it
    # did in 10.7. What changes is where the grant it reads comes from, and the
    # fact that a row here can only have been written by an attributed issuer.
    #
    # Why not an existing table:
    #   cp_delegation carries identity BORROWING and is read by
    #   DurableDelegationAuthority to permit on-behalf-of invocation. Putting an
    #   authority grant there would convert it into a delegation of identity.
    #   cp_approval binds a capability INVOCATION via canonical_approval_digest;
    #   a grant is not an invocation and the digest would cover a fiction.
    sa.Column("grant_id", sa.String(64), primary_key=True),
    sa.Column("tenant_id", sa.String(128), nullable=False),
    # Who HOLDS the authority. Namespaced identity from the verified session at
    # issuance time, never a display name.
    sa.Column("subject_principal_id", sa.String(256), nullable=False),
    # ``approve`` or ``execute``, never merged into one generic permission and
    # never ``issue``: issuance authority is not itself issuable, which is what
    # makes transitive delegation structurally impossible rather than merely
    # forbidden.
    sa.Column("authority_type", sa.String(16), nullable=False),
    # Version-pinned, as Phase 10.7 established: reference.value carries "@1",
    # so a capability version bump does not silently carry a grant forward.
    sa.Column("capability_ref", sa.Text(), nullable=False),
    sa.Column("capability_version", sa.String(32), nullable=False),
    sa.Column("environment", sa.String(32), nullable=False),
    # Optional ceiling. NULL means "bounded by the capability's own declared
    # risk", which issuance validates -- not "any risk".
    sa.Column("max_risk", sa.String(16), nullable=True),
    # The attribution that did not exist before this phase. An issued grant
    # always names a human; the bootstrap path names itself as bootstrap.
    sa.Column("issued_by", sa.String(256), nullable=False),
    sa.Column("issued_at", _TS, nullable=False),
    sa.Column("issue_reason", sa.String(1024), nullable=False),
    # Revocation is the half that matters. Set, never deleted: a grant that
    # vanishes leaves an auditor unable to tell revoked from never-issued.
    sa.Column("revoked_at", _TS, nullable=True),
    sa.Column("revoked_by", sa.String(256), nullable=True),
    sa.Column("revocation_reason", sa.String(1024), nullable=True),
    # Deterministic identity over every authority-bearing field. Changing any
    # of them changes this, so a tampered row no longer matches its own digest
    # and stops authorizing -- authority is immutable by construction.
    sa.Column("digest", sa.String(128), nullable=False),
    sa.Column("schema_version", sa.Integer(), nullable=False),
    # One live grant per (tenant, subject, authority, capability, environment).
    # Re-issuing the same authority collides rather than creating a second row
    # that a later revocation would miss.
    sa.UniqueConstraint(
        "tenant_id", "subject_principal_id", "authority_type",
        "capability_ref", "environment", "issued_at",
        name="uq_cp_authority_grant",
    ),
    sa.Index("ix_cp_authority_grant_subject",
             "tenant_id", "subject_principal_id", "authority_type"),
)


# ----------------------------------------------------------------------
# Tenant membership — who belongs here (Phase 10.9)
# ----------------------------------------------------------------------

tenant_membership_table = sa.Table(
    "cp_tenant_membership",
    DURABLE_METADATA,
    # Phase 10.9, ADR-102. Phase 10.8 gave authority a durable, attributed home
    # and left it pointing at subjects defined by ``data/tenants/
    # tenant_users.json`` -- a gitignored file with no delete, no deactivate and
    # no audit, whose only mutation path was a V1 route that took the tenant
    # from the URL.
    #
    # This table answers exactly one question: **is this subject a member of
    # this tenant, and is that membership live?** It answers nothing about what
    # they may DO. Approval, execution and issuance remain the explicit scoped
    # grants of Phase 10.8, and no column here maps to any of them.
    #
    # It is deliberately NOT a user table. There is no credential, no display
    # name and no profile: it stores the RELATION and its state, so it cannot
    # become a second identity system.
    sa.Column("membership_id", sa.String(64), primary_key=True),
    sa.Column("tenant_id", sa.String(128), nullable=False),
    # The same identity Phase 10.8's grants already use in
    # ``subject_principal_id``. Changing the format here would orphan every
    # existing grant, which is why this phase inherits it rather than improving
    # it.
    sa.Column("subject_principal_id", sa.String(256), nullable=False),
    # active | inactive. **Never deleted.** A membership row that vanishes
    # leaves historical grants and approvals pointing at an identity nobody can
    # resolve, so removal is a state change and the row stays.
    sa.Column("status", sa.String(16), nullable=False),
    # Informational, and staying that way. Phase 10.5 established that a tenant
    # owner is not an approver; nothing reads this column to decide anything,
    # and a role that started deciding would be the second RBAC this phase is
    # forbidden to build.
    sa.Column("role", sa.String(32), nullable=False),
    # ``migrated`` (imported from the JSON bootstrap) or ``admitted`` (created
    # through the governed path). An auditor can tell provenance at a glance.
    sa.Column("source", sa.String(16), nullable=False),
    sa.Column("created_by", sa.String(256), nullable=False),
    sa.Column("created_at", _TS, nullable=False),
    sa.Column("updated_by", sa.String(256), nullable=True),
    sa.Column("updated_at", _TS, nullable=True),
    sa.Column("schema_version", sa.Integer(), nullable=False),
    # One membership per (tenant, subject). Admitting somebody twice collides
    # rather than creating a second row that a later deactivation would miss --
    # the same reasoning that shapes cp_authority_grant.
    sa.UniqueConstraint("tenant_id", "subject_principal_id",
                        name="uq_cp_tenant_membership"),
    sa.Index("ix_cp_tenant_membership_subject",
             "subject_principal_id", "status"),
)


#: Every durable table, in creation order. Used by the migration and by the
#: bootstrap check that the schema a process needs is the schema it found.
DURABLE_TABLES = (
    execution_table,
    node_lease_table,
    idempotency_table,
    outbox_table,
    worker_table,
    capability_table,
    binding_table,
    authorization_table,
    delegation_table,
    queue_table,
    leadership_table,
    delegation_request_table,
    connector_config_table,
    audit_chain_table,
    audit_record_table,
    harness_trace_table,
    world_observation_table,
    world_fact_table,
    world_verification_table,
    world_reasoning_table,
    world_investigation_table,
    approval_table,
    authority_grant_table,
    tenant_membership_table,
)
