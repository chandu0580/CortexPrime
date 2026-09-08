# Phase 10.19 — Migrate the Governed Approval Store
## Implementation Map

**Written before the migration, as this phase family requires.**

- **Parents:** `c95d370` (10.16, ADR-111) → `3016754` (drift discovery, ADR-112)
- **Scope:** exactly one migration creating `cp_approval`. Nothing else.
- **ADR for this phase:** ADR-113 (107 is used twice; 108–112 once each)

---

## 1. Pre-implementation stop conditions — all cleared before a line was written

| Condition | Finding |
|---|---|
| `approval_table` is ambiguous | **No.** One definition, `backend/database/durable/tables.py:879-940`: 21 columns, `approval_id` PK, `identity_digest` unique, two composite indexes, no foreign keys, two type helpers (`_DOC`, `_TS`) |
| `cp_approval` already in the lineage | **No.** `grep` over `versions/` hits only `0020`'s docstring, which names it as a reason *not* to reuse it |
| Another migration creates equivalent persistence | **No.** ADR-112 mapped every durable table: 24 have migrations `0010`–`0022`; this one has none |
| Definition differs from the production repository | **No.** `SqlApprovalRepository` (`contexts/connectivity/infrastructure/sql_approval.py`) imports `approval_table as T`, contains **zero** `sa.text()` raw SQL, and every column it references — 13 distinct `T.c.<name>` — is in the Table |
| Would change approval semantics | **No.** Schema coverage only; the repository, contract, gateway check and routes are untouched |
| Another governed table must change | **No** |
| Data migration required | **No.** On every Alembic-built database the table is absent and therefore empty |
| Destructive operation proposed | **No** in `upgrade()`. `downgrade()` drops the table, which is the symmetric inverse the brief asks for and what every sibling migration does |
| Current head ambiguous | **No.** `alembic heads` → exactly `0023_retire_iam` |

---

## 2. The migration

**File:** `backend/database/migrations/versions/0024_approval_store.py`
**Revision:** `0024_approval_store` · **Revises:** `0023_retire_iam`

Derived **column for column from `approval_table`**, not from the autogenerate
diff (which the brief forbids as a source, and which ADR-112 showed is
contaminated by 134 unrelated operations).

| # | Column | Type | Null | Notes |
|---|---|---|---|---|
| 1 | `approval_id` | `Text` | no | **PK** |
| 2 | `identity_digest` | `String(128)` | no | **unique** |
| 3 | `tenant_id` | `String(128)` | no | |
| 4 | `capability_ref` | `Text` | no | |
| 5 | `capability_digest` | `String(128)` | no | |
| 6 | `operation` | `String(128)` | no | |
| 7 | `authorization_operation` | `String(32)` | no | |
| 8 | `environment` | `String(32)` | no | |
| 9 | `principal_id` | `Text` | no | |
| 10 | `payload` | `_DOC` → JSONB | no | |
| 11 | `approval_digest` | `String(128)` | no | |
| 12 | `outcome` | `String(32)` | no | |
| 13 | `requested_by` | `Text` | no | |
| 14 | `decided_by` | `Text` | yes | |
| 15 | `justification` | `Text` | yes | |
| 16 | `expires_at` | `_TS` → TIMESTAMPTZ | no | |
| 17 | `requested_at` | `_TS` | no | |
| 18 | `decided_at` | `_TS` | yes | |
| 19 | `consumed_by_execution` | `Text` | yes | |
| 20 | `investigation_ref` | `Text` | yes | |
| 21 | `schema_version` | `Integer` | no | |

Indexes: `ix_cp_approval_tenant (tenant_id, requested_at)`,
`ix_cp_approval_investigation (tenant_id, investigation_ref)`.
Foreign keys: none (the Table declares none). Server defaults: none (the Table
declares none — timestamps come from the injected application clock, ADR-044).

**Conventions copied from siblings:** rationale docstring; string revision ids;
`_TS = TIMESTAMP(timezone=True)` (`0022`); `_DOC = JSONB().with_variant(sa.JSON(),
"sqlite")` (`0019`); inline `unique=True` (`0022`); `op.create_index` after the
table; downgrade drops indexes then table.

### The already-present case — the repository's own convention, one migration earlier

Every phase harness since 10.3, and every development database, was built by
`build_development_store`, which runs `DURABLE_METADATA.create_all` — so those
databases **already have `cp_approval`**, created outside Alembic. An
unconditional `create_table` would fail on every one of them.

Migration `0023_retire_iam` faced the same situation in reverse and set the
convention: an existence check via `sa.inspect(op.get_bind()).get_table_names()`
(`0023:63-64`). This migration uses it — for the table, and separately for each
index by name — so that:

- a database where `cp_approval` is **absent** gets the table and both indexes;
- a database where it is **already present** is left exactly as it is;
- a partial state (table without indexes) gets the missing indexes only.

This is not a workaround introduced for this phase; it is the established
treatment for a table that may already exist outside the lineage.

---

## 3. What is NOT changed

`approval_table` itself, `SqlApprovalRepository`, `ApprovalFacts`, the gateway
digest check, `approval_routes.py`, `approval_queue.py`, `cost_tracking`, the
ten dead models, the 27 index-drift tables, `env.py`, every existing migration.

---

## 4. Verification plan

| § | Method |
|---|---|
| A | Fresh DB → `upgrade head` → 56 tables, `cp_approval` present, the previous 55 still present, nothing else |
| B | Reflect `cp_approval`; compare to `approval_table` column by column, plus PK, unique, indexes |
| C | `SqlApprovalRepository` against the migration-built DB: create, retrieve, grant, deny, consume, expiry |
| D | `verify_durability(create_schema=False)` → `ready: true`, `missing_tables: []` |
| E | E.1: `cortex_p1014_legacy` (at `0023`, table absent) → migrate; E.2: fresh DB → `0023` → `DURABLE_METADATA.create_all` → migrate — both must succeed, second must be a no-op |
| F | 10.7 / 10.8 / 10.9 / 10.10 / 10.11 / 10.13 / 10.14 / 10.16-relevant checks |
| G | Persistence-only; 0 provider writes from this phase |
| H | `alembic check`: `cp_approval` no longer an `add_table`; remaining 134 ops unchanged |
| I | disposable autogenerate: no `create_table('cp_approval')`; artifact deleted |
| J | exactly one new file; single head `0024_approval_store`; `git diff` over prior migrations empty |
