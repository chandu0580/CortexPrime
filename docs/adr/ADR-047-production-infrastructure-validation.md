# ADR-047 — Production Infrastructure Validation and Real Execution

**Status:** Accepted
**Date:** 2026-08-09
**Phase:** 5.4
**Amends:** ADR-044 (durable state), ADR-045 (coordination), ADR-046 (delegation)

---

## Context

Phases 5.1 through 5.3 built durable state, distributed coordination and governed
delegation, and verified all three against **file-backed SQLite**, because no
PostgreSQL was reachable. Each phase said so and refused to claim otherwise.

Phase 5.4 found PostgreSQL. Docker Desktop was installed but its engine was not
running; once started, the project's own `cortex-postgres` service
(`pgvector/pgvector:pg16`, already defined in `docker-compose.yml`) came up and
answered as PostgreSQL 16.14.

**Every claim in the three previous phases that depended on the database was
therefore untested against the database it was written for.** That turned out to
matter more than expected.

## What the first real PostgreSQL run found

Seven defects, none of which SQLite could have exposed. Ranked by how badly they
would have behaved in production.

### 1. Migrations never committed anything (critical)

`env.py` used `engine.connect()`. Under SQLAlchemy 2.0 that is commit-as-you-go:
the DDL ran inside an implicit transaction that was **rolled back** when the
block exited. `alembic upgrade head` printed a complete, correct-looking list of
twelve applied revisions and left the target database with zero tables and no
`alembic_version` row. Verified directly, twice, against two different databases.

This is the worst failure shape a migration runner can have — silent, and
indistinguishable from success in the log. Fixed with `engine.begin()`.

**Consequence for earlier phases:** migrations 0010, 0011 and 0012 had never been
applied to any database. The development database sits at `0009` for exactly this
reason.

### 2. A blank database could not reach head

Alembic creates `alembic_version.version_num` as `VARCHAR(32)` and exposes no
supported way to widen it. Two revision identifiers are longer —
`0003_consolidate_reflection_tables` (34) and
`0009_consolidate_connector_activity` (35) — so a fresh database failed at 0003
with `StringDataRightTruncationError`. That is precisely what a new production
deployment does.

It had gone unnoticed because the development database's column is
`VARCHAR(64)`, widened out of band by somebody who hit the same wall locally.
Fixed by widening the column in `env.py` before Alembic touches it, idempotently.
The proper fix is revision identifiers under 32 characters; renaming them now
would orphan every database already stamped with the long ones, so that is
recorded rather than done.

### 3. Autogenerate would have dropped the entire durable state layer

`target_metadata = Base.metadata` described 41 ORM tables and **none** of the 13
`cp_*` Core tables, which live on `DURABLE_METADATA`. Alembic compares a live
database against the model and emits `drop_table` for anything surplus, so
`alembic revision --autogenerate` would have generated a migration deleting
execution state, leases, idempotency, the outbox, the worker directory,
capabilities, bindings, authorizations, delegation and connector configuration.

Nobody had run autogenerate since Phase 5.1, which is the only reason this had
not already happened. Fixed with `target_metadata = [Base.metadata, DURABLE_METADATA]`.

### 4. Catch-then-continue is a PostgreSQL bug (five sites)

PostgreSQL aborts the **entire transaction** when any statement fails: every
subsequent statement returns `25P02 in_failed_sql_transaction`. So this shape,
used throughout the persistence layer —

```python
try:
    work.execute(insert)            # expected to collide
except ConstraintConflict:
    work.execute(update_or_select)  # decide what to do instead
```

— cannot work on PostgreSQL. SQLite tolerates it, which is why every phase up to
5.3 passed. Five sites were affected:

| site | what broke |
|---|---|
| `SqlNodeLeaseStore.acquire` | **taking over an expired lease never worked** |
| `SqlIdempotencyStore.claim` | a repeated key raised instead of returning `False` |
| `SqlCapabilityRepository.register` | a duplicate registration could not be compared |
| `SqlLeadershipStore._ensure_row` | **every election after the first failed** |
| `SqlExecutionOutbox.record` | a duplicate event poisoned the caller's transaction |

The last is the most insidious: the outbox shares a transaction with the state
change that produced the event *by design*, so swallowing a duplicate without a
savepoint left the caller committing into a transaction the database had already
abandoned.

Fixed by adding `UnitOfWork.attempt()` — a savepoint context manager — and
wrapping the failing statement at each site. On SQLite the savepoint is real too,
so behaviour is identical on both.

### 5. Alembic could not run from its own directory

`_root = parents[4]` resolves to `C:\projects`, one level above the repository.
Migrations only ever worked when run from the repository root, where the current
directory already supplies `backend`. Fixed to `parents[3]`.

### 6. SQLSTATE 40003 was unclassified

`classify_database_error` handled 40001, 40P01, 23xxx, 57014 and 55P03, but not
`40003 statement_completion_unknown` or `08007 transaction_resolution_unknown`.
Both mean *the database does not know whether the transaction committed*, and
`08007` fell through to the `08` prefix rule and was classified as a plain
`ConnectionFailed` — which is settled, and therefore safe to retry. Retrying a
transaction that may already have committed is how a duplicate appears.

Both now map to `UnknownCommitOutcome` **unconditionally**, checked before
`during_commit` is consulted: the caller's belief cannot make an indeterminate
outcome knowable.

### 7. Two ungated code-execution surfaces

Found by the 5.4.20 sweep, run as AST call detection rather than text matching
(the text version flagged the transport adapter's own comment saying "there is no
`verify=False` here"):

* `ComputerTaskEngine.open_application` called `subprocess.Popen(app)` on a
  caller-supplied name — no allow-list, no isolation, no resource ceiling, no
  kill path — and was registered as a tool handler at import.
* `ScriptSandbox` called `exec()` with restricted builtins and a denied-substring
  list, and was **registered in `SandboxRegistry` under the name "sandbox"**.
  Restricted builtins are routinely escaped by walking object internals; a
  blocklist over a Turing-complete language enumerates what somebody thought of.
  The name was the dangerous part: a dispatcher asking the registry for
  containment received something that provides none.

Both are quarantined behind explicit fail-closed flags, defaulting to refused.
`ScriptSandbox` is no longer registered at all. The refusals are deliberately at
*use* rather than at import — an earlier attempt refused in the constructor and
broke application start-up, trading a hazard for an outage.

## Decisions

### PostgreSQL is now the verified database

Schema built by `alembic upgrade head` on a blank database and nothing else.
Verified: JSONB document columns, `timestamptz` authority timestamps, no
server-side `NOW()` default on any column the platform reasons about, `BIGSERIAL`
monotonicity, and all 13 durable tables present.

### Concurrency is verified across real OS processes

`ProcessPoolExecutor` with a file barrier so the contending operations genuinely
overlap. Verified on PostgreSQL: execution CAS (one winner, revision advances
once), queue claim exclusivity, lease exclusivity, heartbeat rejection for
non-holders, four-way leader election, fencing-token monotonicity across
handover, outbox claim exclusivity, capability registration, worker registration,
idempotency, delegation issuance and delegation revocation.

**One honest non-guarantee.** Under contention a queue claimant can return empty
while work is available: it selected candidates, blocked on the winner's row
locks, and its predicate no longer matched when it woke. Nothing is lost — the
items stay queued and the next tick takes them — but the tick is wasted. This is
recorded as a finding rather than asserted away, and it is not fixed here because
the fix is a scheduling policy and this platform has deliberately not adopted one.

### Unknown commit stays unknown

Verified against real PostgreSQL by terminating the backend with
`pg_terminate_backend` mid-transaction. A commit interrupted by connection loss
classifies as `UnknownCommitOutcome` with `settled = False`, and is reconciled by
reading back the durable identity chosen *before* the transaction. Loss before
commit leaves no row. Pool exhaustion raises rather than growing unbounded.
Statement cancellation classifies as `TransactionTimeout`.

### `retryable` means the transaction, never the operation

A new flag on `DurabilityError`, `True` only for 40001 and 40P01. The docstring
is explicit that it authorises re-running the *SQL* and never the provider call:
a provider operation that already happened does not un-happen because PostgreSQL
chose this transaction as the deadlock victim.

### Crash recovery is verified with real kills

Processes terminated with `os._exit(9)` — no finalisers, no rollback, no cleanup,
which is what a killed container does. Verified: a claim held by a dead process
keeps the item durable and unclaimable until the claim lapses, then recovers; a
lease held by a dead worker becomes **AMBIGUOUS** (expired, recent heartbeat) and
is *not* reclaimable, which is the whole reason the fourth lease state exists; an
unacknowledged outbox entry is republished after its claim lapses **with the same
event id**, so the duplicate is a recovery rather than a second event.

**At-least-once remains the honest guarantee.** Duplicate provider execution is
possible and is not hidden.

### Ten readiness dimensions, never one boolean

`backend/api/production_readiness.py`. `ready = True` is the field a load
balancer reads, and a single boolean turns ten different outages into one. Each
dimension answers for itself with a reason; `overall` is the conjunction of those
a deployment declares it needs, derived on read rather than stored.

Notably `provider_ready` does **not** mean a provider answered. That is not
knowable without calling one, and a health check that called a provider would
spend a rate limit on every liveness probe.

## Verification status — stated exactly

| | status |
|---|---|
| **PostgreSQL** | **VERIFIED.** PostgreSQL 16.14, project's own container, 65 checks. |
| **Real transport** | **VERIFIED.** Real HTTPS 200 from `api.github.com` through `TransportBroker`, real certificate validation, real repository document returned, no credential in the serialised outcome. |
| **Real provider (authorized read)** | **NOT VERIFIED — credential unavailable.** |

`.env` carries a `GITHUB_TOKEN` of 26 characters beginning `ghp_`. A classic PAT
is 40. The value matches a placeholder pattern. `repository.get_repository`
therefore could not be performed as an authorized read. **The provider was not
faked, no mock stood in for it, and no result is claimed.**

What this leaves specifically unverified: the credential broker minting a real
GitHub credential; the adapter presenting it; GitHub's authenticated response;
normalization of a real authenticated payload; and the failure taxonomy against
real provider errors (invalid credential, insufficient permission, nonexistent
resource, rate limit).

## Deferred, with reasons rather than silence

**Tenant fairness — DEFERRED.** The repository was searched for an authoritative
policy defining tenant concurrency, quota, priority or starvation prevention.
None exists. `claim_batch` orders by priority, `available_at`, `sequence`;
`tenant_depths()` makes starvation observable and nothing acts on it. Inventing a
quota policy here would be inventing product strategy inside a claim query.

**MCP over SSE — DEFERRED.** The security primitives were assessed against the
5.4.15 list. TLS, SSRF protection, tenant isolation and credential isolation all
exist. What does not: `TransportOutcome` carries **one response body, not a
stream**, so there is no shape in which a streaming read can be expressed, and no
per-frame authority-window enforcement or cancellation for a long-lived
connection. That is a contract change, not an adapter. The kind stays absent from
`PRODUCTION_TRANSPORT_KINDS` and `HttpxTransportAdapter` refuses it outright.

**Sandboxed stdio — DEFERRED.** No isolation boundary exists. Phase 5.4 in fact
*removed* the thing that looked like one. Claiming `CONTAINED` on a
`subprocess.Popen` would unlock the irreversible-write refusals without providing
the containment they were refused for — the single most dangerous change
available in this codebase.

## Consequences

**Gained.** A database whose schema only Alembic can author, and which migrations
actually reach. A persistence layer that works on the database it was written
for. SQLSTATE classification covering the four mandated codes. Crash recovery
verified with real process kills. Two code-execution hazards closed. A readiness
model that cannot report a green light it did not earn.

**Accepted.** A wasted scheduler tick under queue contention. `alembic_version`
widened by DDL in `env.py` rather than by shortening revision ids. At-least-once
delivery, and therefore possible duplicate provider execution.

**Unchanged.** Every V1 gate is still default-off and was re-verified as such:
the global credential store, the arbitrary-URL connector, legacy connector
routes, legacy execution surfaces and `init_db` all refuse. Nothing became
reachable because Phase 5.4 is enabled.

## Phase 5.5 boundary — exactly

Phase 5.5 begins at, and is limited to:

1. **The real provider operation.** Supply a valid GitHub credential through the
   credential broker and perform `github.repository.get_repository` end to end.
   Then the 5.4.8 failure matrix against the real provider.
2. **The full chain in one run.** PostgreSQL → queue → scheduler → lease →
   delegation → authorization → binding → worker selection → gateway →
   credential → transport → adapter → provider → durable result → checkpoint →
   outbox → replay, as a single governed execution with no bypass. Phase 5.4
   verified the segments; it did not run them as one chain.
3. **The queue-contention tick**, if measurement shows it matters.

Phase 5.5 does **not** include MCP SSE, sandboxed stdio or tenant fairness. Each
needs a decision or a contract change that is not a 5.5 edit.
