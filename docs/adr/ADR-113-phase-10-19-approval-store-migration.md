# ADR-113 — `cp_approval` gets the migration it never had

- **Status:** ACCEPTED
- **Date:** 2026-09-08
- **Phase:** 10.19
- **Parents:** `c95d370` (10.16, ADR-111) → `3016754` (drift discovery, ADR-112)
- **Evidence:** `docs/PHASE_10_19_VERIFICATION_REPORT.md`,
  `docs/PHASE_10_19_IMPLEMENTATION_MAP.md`
- **Change:** one file, `backend/database/migrations/versions/0024_approval_store.py`

> **Numbering.** Next available is **113**. 107 is used twice; 108–112 once
> each. Nothing existing was overwritten.

## Context

ADR-112 found that `cp_approval` — the durable approval store since Phase 10.3,
consumed by the production `SqlApprovalRepository` and the product approval
queue — was the only one of twenty-five durable tables with no migration. A
database built by `alembic upgrade head` had no approval store, and the
production readiness check said so: `ready: false`,
`missing_tables: ["cp_approval"]`. Every phase harness since 10.3 had built its
database with the development builder, which runs `create_all`, so the
platform's own fail-closed check was never seen to fail.

This phase was scoped to exactly that table. Nothing else in ADR-112's
inventory — `cost_tracking`, the ten dead models, the 27 index-drift tables —
was touched.

## Decision

**Add migration `0024_approval_store`, derived column for column from
`approval_table` on `DURABLE_METADATA`, and nothing else.**

Not derived from the autogenerate diff. That diff was contaminated by 134
unrelated operations, and the brief forbade it as a source. The Table is the
single authority: the production repository imports it as `T`, contains no raw
SQL, and every column it references is in the Table. Reflecting the
migration-built table back against `approval_table` matched on all 21 columns,
their order, the primary key, the unique constraint, both composite indexes,
and the absence of foreign keys and server defaults.

**The already-present case is handled by the repository's own convention, not a
new one.** Every development and harness database already has `cp_approval`
from `create_all`; an unconditional `create_table` would fail on all of them.
`0023_retire_iam` established the existence check against the catalogue for a
table that may exist outside the lineage, and `0024` uses it — for the table and
for each index by name. Proven both ways: a database genuinely missing the table
got it with one migration and an otherwise identical fingerprint; a database
that already had it from `create_all` came through with the **same table OID**
and its pre-existing row intact.

## What it fixes

`verify_durability(create_schema=False)` — the production path, unmodified —
now reports `ready: true, missing_tables: []` on a fresh Alembic-built database
and on an existing one migrated forward. The existing `SqlApprovalRepository`
was driven against the migration-built table: request, retrieve by id and by
identity digest, cross-tenant refusal, the unique-constraint collision, grant,
the no-op second decision, consume, deny, withdraw, expiry, tenant listing, and
the gateway-side `find()` returning `ApprovalFacts` — 14 of 14, persistence
only, zero provider writes.

`alembic check` went from 135 operations to 132: a delta of exactly
`cp_approval`'s `create_table` and two `create_index`, with every other
table's operations byte-for-byte unchanged. It still fails globally on the
pre-existing drift ADR-112 classified, and that was neither required nor
claimed.

## Consequences

**Governance impact: schema coverage only.** No approval semantics, contract,
repository, route, authority, tenant, membership or execution code changed.
The migration stores approvals; it does not decide about them, which remains
`ApprovalFacts.is_valid_for` and the gateway's digest comparison, exactly as
ADR-090 requires.

**Migration history is unchanged except for the new revision** — single head
`0024_approval_store`, `0001`–`0023` byte-identical.

**Prior phases are intact**: 10.7 155/155, 10.8 118/118, 10.9 107/107, 10.10
107/107, 10.11 68/68, 10.13 60/60, 10.14 53/53, and Phase 10.16's
metadata-closure probe. Architecture gate **155 passed**; the backend regression is byte-identical to the Phase 10.18 baseline (75 failed / 6775 passed / 24 errors, all pre-existing and proven so on a reverted tree).

**One environment finding, reported.** In the sequential harness chain, three
harnesses showed the TestClient's anyio portal dying or hanging — every request
answering 500, then `RuntimeError: This portal is not running` at shutdown, or a
post-report hang that blocked the chain until killed. Solo re-runs passed at
full counts, so it is not a regression; but it has now happened in two phases
and deserves its own look. Not this phase's.

**`downgrade()` drops the table and every approval row in it.** That is the
symmetric inverse the brief asked for and what every sibling migration does;
it is stated so that nobody runs it casually.

## What was not done, deliberately

`cost_tracking` still writes to a column that does not exist and swallows the
error; the ten dead models still declare tables no migration creates; the 27
index-drift tables still differ from their models; `alembic check` is still red.
All four were in scope for ADR-112's inventory and out of scope here, by the
brief's first line: *stop scope at `cp_approval`.*

## Next

Not started. ADR-112's dependency order continues: reconcile `cost_tracking`
(register and correct the model, add a write-path test), retire the ten dead
models after confirming in-memory persistence is intended, then decide the
index convention once and protect the expression indexes. After those,
`alembic check` is a working drift detector.
