# ADR-044 — Durable state foundation

**Status:** Accepted
**Date:** 2026-08-08
**Phase:** 5.1 — Durable state foundation
**Extends:** ADR-043 (production connectivity), ADR-039 (lifecycle and recovery),
ADR-038 (invocation gateway), ADR-036 (worker contract), ADR-035 (binding),
ADR-032 (capability identity), ADR-031 (durable execution core), ADR-018 (storage
boundary tenant guard)

---

## 1. The one question

    "Which of this platform's invariants survive a restart, a second process,
     and a lost commit?"

Phase 4 answered "durability: not ready" honestly. This makes the *state* durable
and stops there. Distributing *work* across instances — a durable queue, a
durable scheduler, leader election — is Phase 5.2 and is not claimed here.

## 2. System of record

**PostgreSQL, through the existing SQLAlchemy 2.0 engine and Alembic migrations.**
Reused, not replaced. No second database technology was introduced; Redis, Neo4j,
RabbitMQ and MinIO keep the roles they already had and **none of them becomes the
system of record for execution state**.

One authoritative store for: Execution, NodeRun, Attempt, Checkpoint, Lease,
Capability, Worker registration, Binding, Authorization record, Outbox entry, and
the delegation seam.

## 3. Ownership

| Object | Owner | Table | Mutated by | Transaction | Event |
| --- | --- | --- | --- | --- | --- |
| Execution (with runs, attempts, checkpoints) | BC-5 | `cp_execution` | `ExecutionService` via CAS | one per command | ADR-029 events via outbox |
| Node lease | BC-5 | `cp_node_lease` | lease store, holder only | with the aggregate move | none (a claim is not a decision) |
| Idempotency key | BC-5 | `cp_idempotency` | claimant only | with the action | none |
| Outbox entry | BC-5 | `cp_outbox` | recorder, then one claiming publisher | with the state change | *is* the event |
| Worker registration | BC-5 | `cp_worker` | directory lifecycle methods | one per transition | ADR-037 worker events |
| Capability | BC-8 | `cp_capability` | registry `register`/`replace` | one per registration | registry events |
| Binding | BC-8 | `cp_binding` | `save` only, once | with resolution | binding events |
| Authorization record | BC-8 | `cp_authorization` | append-only | with the decision | none (evidence) |
| Delegation grant | BC-8 | `cp_delegation` | **seam; nothing issues one** | — | — |

## 4. Architecture — the domain never learns about a database

```
Domain            no sqlalchemy, no asyncpg, no session, no Table
   ↑
Application       Protocol ports: ExecutionRepository, ExecutionOutbox,
                  WorkerDirectory, CapabilityRepository, BindingRepository
   ↑
Infrastructure    Sql* implementations, in each context's own infrastructure/
   ↑
Database          backend/database/durable — engine, schema, transaction scope
```

Verified structurally: no module under any `domain/` or `application/` imports
`sqlalchemy`, `asyncpg`, `psycopg` or `redis`.

The transaction helper `enlisted` lives in `backend/database/durable/session.py`
rather than in a context, because every context's repositories need it and one
owning it would make the others import across a bounded-context boundary for a
piece of plumbing. **This was caught by the architecture checker**, not by
review — see §17.

## 5. The aggregate is a document, not a table per part

`Execution` already had a storage-agnostic projection (`to_record`/`from_record`)
that flattens the whole aggregate, re-runs every invariant on the way back in,
and **restores digests rather than recomputing them**. That mapping is reused
unchanged.

Shredding the aggregate into `node_run` / `attempt` / `checkpoint` tables would
mean writing it a second time in SQL, with a second set of invariants to keep in
step. The first divergence between the two is a run that loads with a digest that
always matches — a check that cannot fail, on the record of what happened to
production.

So the document is authoritative for the domain, and the columns beside it —
`tenant_id`, `revision`, `state`, `workflow_id` — are authoritative for lookup
and concurrency. Neither is a second model of the other, because the columns are
derived on write and never read back into the aggregate.

A separate table earns its place only where a **cross-process invariant** needs a
database constraint a document cannot express: one holder per node, one
idempotency key per tenant, one row per event id, one contract per capability
version, one row per binding id, one registration per worker id.

## 6. Concurrency — the mechanism per invariant

| Invariant | Mechanism | Why not something else |
| --- | --- | --- |
| One decision survives concurrent aggregate writes | `UPDATE … WHERE revision = :expected`, rowcount is the answer | The compare and the swap are one statement, so there is no window — not a small one, none |
| Exactly one worker holds a node | primary key on `(execution_id, node_id)`; takeover only via `WHERE released_at IS NOT NULL OR expires_at <= now` | A read-then-write lets two workers both decide the node is free |
| One idempotency key per tenant | primary key | An in-memory set survives neither a restart nor a second process |
| One row per event id | unique `(tenant_id, event_id)` | Delivery stays at-least-once; *recording* becomes exactly-once |
| One contract per capability version | unique `(capability_id, version)` | A lock held two registrations apart in two processes holds nothing |
| A binding is never overwritten | primary key | The refusal *is* the collision, not a check before one |
| Exclusive outbox claim | `UPDATE … WHERE status = pending AND (claimed_until IS NULL OR < now)`, then read back **what this publisher holds** | Returning what was requested rather than what was won is how two publishers hand over the same event |

No Python lock, process mutex or global dictionary is the production concurrency
mechanism anywhere in this phase.

**`SELECT … FOR UPDATE` is deliberately not used.** Every invariant above is
expressible as a conditional write or a constraint, both of which are one
statement and hold on any dialect. Pessimistic locking would add a lock-ordering
problem and a deadlock class in exchange for nothing.

## 7. Transaction boundaries

Every repository method takes an optional `UnitOfWork`. Handed one it enlists and
**cannot commit**; handed none it opens and commits a single-statement
transaction. The pairs that must be atomic are always handed one, by
`DurableExecutionStore`, which is the only code that knows which writes belong
together.

Atomic:

* execution state change **+** its outbox events (`record_outcome`)
* execution creation **+** its opening events (`start`)
* lease claim **+** the aggregate move **+** its events (`claim_node`)

**Not atomic, and cannot be:** outbox publication and provider delivery. The
target is outside this database, so no transaction spans it. That is precisely
why the outbox exists, and why delivery is at-least-once. A consumer that
deduplicates on `event_id` is correct; one that assumes single delivery is not.

No hidden autocommit, no implicit transaction, no repository that commits behind
its caller's back.

## 8. Session lifecycle

`DurableStore` holds an **engine** — a pool, which is a resource. There is no
module-level session, no session singleton, no session on a domain object and no
ambient transaction. Connections are opened inside a `with` block that always
closes and always rolls back on failure, in a `finally`.

There is no `DurableStore.default()`. A security-relevant store that can be
reached without being passed is one that gets reached from somewhere nobody
wired.

## 9. Failure semantics

Every driver exception is classified from its **SQLSTATE or type name**, never its
message — a message is content the database composed, sometimes from the row.

`TransactionUnavailable`, `ConnectionFailed`, `SerializationConflict`,
`DeadlockDetected`, `TransactionTimeout`, `ConstraintConflict`,
`UnknownCommitOutcome`.

**A database failure is never a success.** Nothing here retries: a serialization
conflict is retryable *in principle*, and whether repeating this particular
mutation is safe depends on effect semantics this layer cannot see. Execution
decides, exactly as it does for a provider failure.

### The defect this phase found

The transaction wrapper's `except Exception` was catching **domain refusals**
raised inside the `with` block — `LeaseHeld`, `ConcurrentExecutionUpdate`,
`ConflictingRegistration`, `WorkerAlreadyRegistered` — and reclassifying them as
`DurabilityError`.

That is a semantic regression smuggled in as a durability change: a caller that
catches `LeaseHeld` would have started seeing an infrastructure error and would
either stop handling the refusal or start treating a refusal as a fault. Found by
the concurrency tests, not by review. Fixed: only exceptions raised *by the
commit* are classified; a body exception rolls back and travels unchanged.

## 10. Unknown commit outcome

If COMMIT is sent and the connection dies before the acknowledgement, **the
transaction may have committed**. `UnknownCommitOutcome` is its own class, is
`settled = False`, and is not a subclass of anything that reads as failure.

Reconciliation is by transaction-owned identity, which is why every durable write
in this phase chooses its identity *before* the transaction: execution id, lease
id, entry id, decision id, delegation id. A caller that lost a commit reads back
by that id rather than repeating the mutation.

`classify_database_error(..., during_commit=True)` is conservative by design —
an unrecognised failure during a commit is `UNKNOWN`, not a failure.

## 11. Tenant isolation

Every tenant-owned table carries `tenant_id NOT NULL`. Every repository takes an
`ExecutionContext` first and derives tenancy through `RepositoryGuard` — the same
guard, the same bindings, the same `TENANT-REPOSITORY-CONTEXT` obligation.

Narrowing happens **in SQL**. Another tenant's row is not fetched and then
rejected; it is never selected. A cross-tenant read is indistinguishable from a
miss, and a cross-tenant write fails as `ExecutionNotFound` rather than as a
conflict — reporting a conflict would confirm the row exists.

There is deliberately no `get_all()` without an authority context, and no generic
`update()` / `save()` / `set_status()` anywhere: the lifecycle is the security
model, and a repository with a generic setter is one through which it can be
bypassed.

### No fake tenant

Searched and confirmed absent: `TenantRef("system")`, `tenant_id="system"`,
default tenant, ambient tenant.

Platform-scoped rows carry `scope_owner = "@platform"`, chosen to be **unusable
as a tenant id** — it contains a character the tenant validators reject, so it
cannot arrive from a request and be mistaken for a real tenant. It exists only
where the domain already says the object has no tenant
(`CapabilityTenancy.PLATFORM`, `WorkerScope.PLATFORM`). A nullable owner was
rejected: a row the tenant predicate cannot decide about resolves to "visible" in
every query somebody writes in a hurry.

## 12. Digests

Preserved exactly, and **never recomputed on load**:

* execution digest and checkpoint digest — restored by `from_record`
* capability contract digest — restored by `from_record`
* binding digest — restored *and verified* by `binding_from_record`, which calls
  the domain's own `verify_digest`
* worker implementation digest — recomputed and **compared** against the stored
  value; a mismatch refuses to load
* decision digest — stored as the decision computed it; this layer has no policy
  engine to recompute it with, which is the point

A recomputed digest always matches. A check that cannot fail is not one, and
these are the records that say what an approval was about.

## 13. Clocks

One injected application clock, held by `DurableStore` and handed to every
repository through `UnitOfWork.now`. Everything written in one unit agrees about
when it happened.

**No timestamp column has `server_default NOW()`.** A row stamped by the database
and a decision made by the application would be two clocks inside one authority
calculation — the defect Phase 4.4 closed at the invocation gateway, and it does
not return one layer down. All timestamps are UTC and timezone-aware; SQLite
returns them naive, so lease reads restore awareness at the one place a lease
expiry is decided rather than at twenty call sites.

## 14. Leases

Durable: holder, lease id, granted, expires, heartbeat, released, attempt, and a
**fence** that increments on every grant. A worker that was partitioned and comes
back believing it holds a node can be told otherwise by comparing fences — which
a timestamp cannot do, because the two machines' clocks disagree and that is the
whole problem. Nothing in this phase acts on the fence beyond recording it.

Recovery reads four states from durable state alone: `ACTIVE`, `EXPIRED`,
`RELEASED`, `AMBIGUOUS`. The fourth is not a hedge — a lease past its expiry whose
holder was heartbeating moments ago may still be running, so reclaiming it would
run the node twice and refusing forever would strand it. It is reported;
recovery decides.

**A heartbeat does not extend the expiry.** It moves `heartbeat_at` and nothing
else. A worker that keeps saying "still here" does not thereby hold authority
indefinitely, and a heartbeat from a worker that no longer holds the lease is
refused — which is how a reclaimed worker finds out.

## 15. Outbox

Durable, ordered by a database-assigned `sequence` (the primary key — an
auto-incrementing value is generated portably only there, and causal order is
what this table exists to get right). Ordering never comes from a timestamp: two
events in the same microsecond tie on a clock, and a tie means two publishers can
disagree about which fact came first.

Claim is exclusive across processes and **expires**, so a publisher that dies
mid-batch does not strand its entries. Dead-lettering after ten attempts is
unchanged from the in-memory outbox — changing a threshold while adding
durability would be a semantic change smuggled in.

**Still at-least-once, and still saying so.** Nothing in this schema makes
delivery exactly-once, and nothing claims it does.

Events are stored as their `to_dict`. An event that cannot be serialised is
refused rather than stored as a string that looks like one — it could not be
republished after a restart, and a consumer receiving something it cannot parse
drops it.

## 16. Bootstrap, readiness, and no fallback

Production verifies five things separately, because they fail for different
reasons: configuration, connectivity, transaction capability, schema presence,
schema version. A process that cannot pass all five **refuses to assemble**.

There is no in-memory fallback and no code path that produces one. A process that
quietly used a dictionary when the database was unreachable would lose every
guarantee this phase provides and would look healthy doing it.

`build_development_persistence` is a separately named function — not a flag —
which creates its own schema, which production refuses.

Readiness is separate from liveness and mutates nothing. It reports
`durable_state: true` and `durable_scheduling: false`, so a deployment cannot
mistake one for the other.

Production configuration additionally refuses: creating its own schema, disabling
TLS, and SQLite as a system of record.

## 17. What the tests found

Two defects, both found by tests rather than by reading:

1. **Domain refusals reclassified as database errors** (§9). Found by the
   cross-process concurrency tests, which expected `LeaseHeld` and got
   `DurabilityError`.
2. **Connectivity importing an Execution helper.** The `_Enlisted` transaction
   scope was defined in Execution's SQL repository and imported by Connectivity's
   — a bounded-context violation caught by `BND-CONTEXT-ISOLATION`. Moved to the
   transaction layer, where it belonged.

## 18. Migration

`0010_durable_state_foundation`, chained onto `0009`. **Purely additive**: nine
new tables, no column altered, no table dropped, no data moved.

Nothing existing reads or writes them, so applying it changes no behaviour — the
durable repositories are wired at the composition root, and a deployment that has
not wired them keeps its in-memory ones. A migration that both created a schema
and switched the system onto it would make two changes one irreversible step.

The downgrade drops what the upgrade created and is **destructive in the only
sense it can be**: the durable execution history goes with it. That is stated in
the migration rather than implied to be reversible.

A test parses the migration's AST and compares every created table and column
against `tables.py`. Two descriptions of one schema is two things to keep in
step, and a column in one and not the other is a query that fails only in
production.

## 19. Delegation seam

Phase 4.4 refuses **every** on-behalf-of invocation, because
`AuthorizationRequest` has no delegation concept and absence is not permission.

`cp_delegation` gives that answer somewhere durable to live: actor, delegated
principal, tenant, scope, validity window, issuer, revocation state, digest.

**It is a seam and stays one.** There is no route, no command and no service that
issues a grant; `DelegationAuthority` remains unwired at the composition root.
`SqlDelegationRepository.issue` exists so the shape is exercisable, and it refuses
a self-delegation, an empty scope (which would read as a delegation of
everything) and an already-expired window.

**The default remains safe.** An empty table means `grant_for` returns `None`,
which `_check_delegation` turns into `DELEGATION_NOT_AUTHORIZED`. Having a table
does not make delegation work. Building the workflow is Phase 5.2; building the
table now is what stops Phase 5.2 inventing a shape under time pressure.

## 20. What did not change

No retry policy, no compensation policy, no `UNKNOWN` semantics, no effect
semantics, no capability trust model, no worker trust model, no binding
immutability, no authorization rule, no connectivity authority, no MCP
governance, no V1 gate. The in-memory repositories are untouched and still
correct for development.

Registration is still not enablement. Two eligible workers still refuse as
`AMBIGUOUS_WORKER` rather than being ranked. Replay is still inert — verified by
search for the store, the session, the repositories and SQLAlchemy.

## 21. Verification

**106 focused checks, 0 failures**, against a real file-backed database with
genuinely separate processes (`ProcessPoolExecutor`, spawn, file barriers so both
parties read before either writes).

Covered: restart persistence, cross-process CAS, cross-process lease claim, lease
expiry/heartbeat/ambiguity/takeover/fencing, idempotency across processes,
outbox ordering and uniqueness and exclusive claim and dead-lettering, state+event
atomicity in both directions, transaction rollback, concurrent capability
registration, binding immutability, worker lifecycle durability and ambiguity
refusal, tenant isolation on reads/writes/leases, digest preservation, failure
classification including unknown commit, production fail-closed, bootstrap
readiness, replay inertness, no fake tenant, no driver import in domain or
application, and migration/schema agreement.

**Honest limit: PostgreSQL was not reachable in this environment.** The tests ran
on SQLite, which provides real ACID transactions, real unique constraints, real
rollback and real cross-process visibility — the three properties the in-memory
stores lacked. It does **not** exercise PostgreSQL's serialization failures,
deadlock detection or `BIGSERIAL`. The repositories are written in portable Core
SQL with no dialect-specific behaviour on the write paths, and the DDL was
compiled against the PostgreSQL dialect, but **no PostgreSQL-specific durability
claim is made** and the suite should be re-run against one before production.

## 22. Limitations, stated

* **Not exactly-once.** Delivery is at-least-once and nothing here changes that.
* **Not a durable scheduler.** State is durable; distributing work across
  instances is Phase 5.2.
* **Adapters are not persisted.** Registrations are; the code is not, and an
  instance without the adapter refuses rather than substituting.
* **No cross-process work queue.** `InMemoryExecutionQueue` is untouched.
* **Bindings shared with other tenants** are narrowed coarsely in SQL and decided
  finely by the domain's `visible_to`, because `shared_with` lives in the
  document. Correct, and one extra row fetched for a shared capability.
* **The V1 SQLAlchemy models are untouched.** They were not audited for
  transaction boundaries and are not part of this system of record.

## 23. Phase 5.2 boundary

In scope for 5.2, and explicitly **not** built here:

* a durable work queue and a durable scheduler; leader election; instance fencing
* the delegation *workflow* — issuing, approving, revoking — over the seam here
* recovery that acts on durable lease state after a crash, including the
  `AMBIGUOUS` case
* an outbox publisher process with real delivery to the event bus
* PostgreSQL-specific concerns: isolation level selection, `SERIALIZABLE` retry
  policy where genuinely needed, connection-pool sizing under load
* migrating the V1 SQLAlchemy models, or deciding they stay where they are

Not in scope for 5.2 and not implied by anything here: an LLM participating in
tool selection, provider selection, capability ranking or authorization
reasoning; or any relaxation of the V1 strangler gates.
