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
)
