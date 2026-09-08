# Phase 10.19 — Migrate the Governed Approval Store
## Verification Report

**STATUS: COMPLETE.** All pre-implementation stop conditions cleared; every
verification section passed by execution.

**One file added:** `backend/database/migrations/versions/0024_approval_store.py`.
**Nothing else changed** — not `approval_table`, not the repository, not the
routes, not the readiness check, not any prior migration.

Every claim was produced by running something. Where a verification degraded
and was re-run, it says so and why.

---

## 1. Section results

| § | Verification | Result |
|---|---|---|
| A | Fresh database | **PASS** — 24 migrations, 56 tables, `cp_approval` present, prior 55 identical |
| B | Schema comparison vs `approval_table` | **PASS** — 21/21 columns, order, PK, unique, both indexes, no FKs, no defaults |
| C | Governed approval persistence path | **PASS** — 14/14, persistence only |
| D | Production readiness | **PASS** — `ready: true`, `missing_tables: []`, check unmodified |
| E.1 | Existing head DB, `cp_approval` genuinely absent | **PASS** — 1 migration ran, everything else fingerprint-identical |
| E.2 | Existing DB, `cp_approval` already present via `create_all` | **PASS** — no-op: same table OID, pre-existing row survived |
| F | Prior phases 10.7–10.14 + 10.16 probe | **PASS** — all at full historical counts (§8) |
| G | Negative safety | **PASS** — 0 provider writes from this phase |
| H | `alembic check` | **as expected** — `cp_approval` gone from the diff; 135 → 132 ops, delta exactly its 3 |
| I | Autogenerate | **PASS** — no `create_table('cp_approval')`; artifact deleted |
| J | Migration history | **PASS** — one new file, single head `0024_approval_store`, `0001`–`0023` unchanged |
| — | Architecture gate | **155 passed** |
| — | Backend regression | 75 failed / 6775 passed / 36 skipped / 58 xfailed / 24 errors — **byte-identical to the Phase 10.18 baseline**, which was proven pre-existing by reverting the tree; unchanged by this migration |

---

## 2. Pre-implementation stop conditions — cleared before any code

| Condition | Evidence |
|---|---|
| `approval_table` ambiguous | **No.** One definition, `durable/tables.py:879-940` |
| `cp_approval` already in lineage | **No.** Only `0020`'s docstring mentions it, as a reason *not* to reuse it |
| Equivalent persistence elsewhere | **No.** ADR-112's map: 24 durable tables migrated, this one not |
| Definition ≠ production repository | **No.** `SqlApprovalRepository` imports `approval_table as T`; **0** `sa.text()` raw SQL; all 13 `T.c.<name>` references are Table columns |
| Would change semantics | **No.** Schema coverage only |
| Other governed table must change | **No** |
| Data migration required | **No** — absent ⇒ empty on every Alembic-built DB |
| Destructive operation | **No** in `upgrade()`; `downgrade()` is the symmetric drop every sibling has |
| Head ambiguous | **No.** `alembic heads` → `0023_retire_iam`, single |

---

## 3. § A — fresh database [PASS]

```
upgrade EXIT=0   migrations run: 24
Running upgrade 0023_retire_iam -> 0024_approval_store, Approval store: migration coverage ...
tables=56   rev=0024_approval_store   cp_approval present: 1
previous 55 all still present + nothing else new:
   IDENTICAL to the pre-migration head set (55) + cp_approval = 56
```

The 55-table set was diffed against the set captured in the drift discovery
before this migration existed; the only difference is `cp_approval`.

---

## 4. § B — schema comparison, `approval_table` as authority [PASS]

Reflected from the migration-built database and compared column by column:

| column | authority | db | null | |
|---|---|---|---|---|
| `approval_id` | TEXT | TEXT | F/F | OK · **PK** |
| `identity_digest` | VARCHAR(128) | VARCHAR(128) | F/F | OK · **UNIQUE** |
| `tenant_id` | VARCHAR(128) | VARCHAR(128) | F/F | OK |
| `capability_ref` | TEXT | TEXT | F/F | OK |
| `capability_digest` | VARCHAR(128) | VARCHAR(128) | F/F | OK |
| `operation` | VARCHAR(128) | VARCHAR(128) | F/F | OK |
| `authorization_operation` | VARCHAR(32) | VARCHAR(32) | F/F | OK |
| `environment` | VARCHAR(32) | VARCHAR(32) | F/F | OK |
| `principal_id` | TEXT | TEXT | F/F | OK |
| `payload` | JSONB | JSONB | F/F | OK |
| `approval_digest` | VARCHAR(128) | VARCHAR(128) | F/F | OK |
| `outcome` | VARCHAR(32) | VARCHAR(32) | F/F | OK |
| `requested_by` | TEXT | TEXT | F/F | OK |
| `decided_by` | TEXT | TEXT | T/T | OK |
| `justification` | TEXT | TEXT | T/T | OK |
| `expires_at` | TIMESTAMPTZ | TIMESTAMPTZ | F/F | OK |
| `requested_at` | TIMESTAMPTZ | TIMESTAMPTZ | F/F | OK |
| `decided_at` | TIMESTAMPTZ | TIMESTAMPTZ | T/T | OK |
| `consumed_by_execution` | TEXT | TEXT | T/T | OK |
| `investigation_ref` | TEXT | TEXT | T/T | OK |
| `schema_version` | INTEGER | INTEGER | F/F | OK |

```
columns in DB but not authority: none      order identical: True
PK      ['approval_id'] == ['approval_id']
UNIQUE  ['identity_digest'] == ['identity_digest']
INDEXES [('ix_cp_approval_investigation', ['tenant_id','investigation_ref']),
         ('ix_cp_approval_tenant', ['tenant_id','requested_at'])]   == db
FKs     none == none          server defaults none == none
RESULT: cp_approval MATCHES approval_table
```

The migration was written from `approval_table`, not from the autogenerate
diff. §4 is what proves that produced the right table.

---

## 5. § C — the existing approval persistence path [PASS 14/14]

`SqlApprovalRepository` — the production `ApprovalLookup` — driven directly
against the migration-built database. Persistence only; no engine, no worker,
no provider, no new behaviour.

```
C1  request persists (returns True)
C2  retrieve by id — pending, correct tenant, digest intact
C3  retrieve by identity digest (idempotency key)
C4  cross-tenant read is refused (returns None)
C5  duplicate identity_digest refused by the UNIQUE constraint the migration created
C6  decide GRANTED on a pending approval
C7  stored outcome is granted with decider recorded
C8  a SECOND decision on a decided approval is a no-op (returns False)
C9  mark_consumed records the execution
C10 decide DENIED
C11 withdraw a granted approval (revocation)
C12 expiry is answered by the record (is_expired_at), not invented here
C13 list_for_tenant sees all four; other tenant sees none
C14 gateway-side find() returns ApprovalFacts — id, outcome, tenant scope, bound digest
C RESULT: 14/14 PASS
rows: denied=2 granted=2 pending=3 withdrawn=2
```

Two probe defects were mine and are recorded: C5 first passed
`requested_by="r"` and the repository correctly refused a non-namespaced
identity; C14 first read `approval_id` off an `ApprovalFacts`, whose field is
`artifact_id`. Both were probe bugs; the repository was right both times.

---

## 6. § D — production readiness [PASS]

The **unmodified** `verify_durability(create_schema=False)` — the production
path, no `create_all`:

```
cortex_p1019_fresh   -> ready: true  schema_present: true  missing_tables: []
cortex_p1014_legacy  -> ready: true  schema_present: true  missing_tables: []
durable/config.py: UNCHANGED
```

The finding that opened this phase — `missing_tables: ["cp_approval"]`,
`ready: false` on any Alembic-built database — is closed.

---

## 7. § E — existing databases, both states [PASS]

**E.1 — genuinely absent.** `cortex_p1014_legacy`, at `0023`, no
`cp_approval`. Fingerprint = md5 over every `table.column:type:null:default`
except `cp_approval`, plus counts.

```
BEFORE: 48b30be333e3a532be3430e98732ec97 tables=55 rev=0023_retire_iam cp_approval=0
upgrade EXIT=0  migrations run: 1
AFTER : 48b30be333e3a532be3430e98732ec97 tables=56 rev=0024_approval_store cp_approval=1
indexes: cp_approval_identity_digest_key, cp_approval_pkey,
         ix_cp_approval_investigation, ix_cp_approval_tenant
```

**E.2 — already present outside Alembic.** Fresh DB → `upgrade 0023` →
`DURABLE_METADATA.create_all` (what every harness and dev database did) → one
row inserted → `upgrade head`:

```
after create_all: cp_approval=1  oid_before=61002
upgrade head EXIT=0  migrations run: 1  errors: 0
after: rev=0024_approval_store  oid_after=61002  rows_survived=1
```

**Same OID, row intact, no error** — the migration recognised the table and did
nothing to it. This is `0023_retire_iam`'s existence-guard convention applied
one migration later, not a workaround introduced here.

---

## 8. § F — prior phases [PASS]

| Phase | Result | Note |
|---|---|---|
| 10.7 | **155/155 VERIFIED** | its one commissioned write, as always |
| 10.8 | **118/118 VERIFIED** | |
| 10.9 | **107/107 VERIFIED** | |
| 10.10 | **107/107 VERIFIED** | |
| 10.11 | **68/68 VERIFIED** | solo re-run — see below |
| 10.13 | **60/60 VERIFIED** | report complete; process hung at shutdown, killed |
| 10.14 | **53/53 VERIFIED** | solo re-run; same post-report shutdown hang, guard-killed |
| 10.16 probe | metadata closure holds | 39 tables, 0 unresolved FK targets |

**What the chain did, honestly.** In the sequential chain, 10.11 reported
66/68: every product-API case in its negative matrix returned **HTTP 500**, and
its shutdown raised `RuntimeError: This portal is not running` — the TestClient's
anyio portal had died mid-run. 10.13 completed its 60/60 report and then hung
in the same shutdown for 23 minutes, blocking the chain until killed. 10.14 then
crashed on `.json()` of an empty body — the same dead-portal signature Phase
10.16 recorded under contention.

**None of it is the migration.** The 10.11 harness contains no Alembic call;
harness databases are `create_all`-built with no `alembic_version`, so `0024`
cannot reach them. Re-run solo, sequentially, with nothing else running:
**10.11 68/68 and 10.14 53/53**, both at their full historical counts, 0 provider
writes. The 10.11 "2 provider writes" in the chain was the harness's own
failure marker — `record_negative` passes iff `writes == 0`, and N1/N2 were
given `1` to force a fail on a non-200 — while its `K-FINAL` check, which reads
real deployment generations, measured **0**.

The TestClient shutdown hang is an environment finding, recorded in §11.

---

## 9. § G, H, I — safety, check, autogenerate

**G.** This phase issues no provider call. The only non-zero
`provider_writes` anywhere in §8 is 10.7's own commissioned restart, exactly
as in every prior phase. No credential path, no authority, no approval
semantics touched.

**H.** `alembic check` still exits non-zero — **global pass was not required
and is not claimed.** What changed is exact:

```
ops before=135 across 40 tables; after=132 across 39 tables; delta=3
cp_approval ops before: {'create_table': 1, 'create_index': 2}  after: ABSENT
every OTHER table's operations unchanged: True
```

The remaining 132 operations are the 10 dead-model tables and 27 index-drift
tables ADR-112 classified, byte-for-byte unchanged. Not suppressed.

**I.** Disposable autogenerate against the new head:

```
create_table ops now: [cost_optimization_recommendations, cost_provider_rates, cost_records,
  fleet_agents, fleet_deployments, fleet_metrics_snapshots, fleets,
  workflow_edges, workflow_nodes, workflows]
cp_approval create_table: ABSENT
captured + deleted: 7e57ff68cdbc_p1019_disposable.py
```

---

## 10. § J — migration history [PASS]

```
0024 parses            line endings: CRLF=0 LF-only=122
alembic heads   -> 0024_approval_store (head)        (exactly one)
alembic history -> 0023_retire_iam -> 0024_approval_store (head)
git diff --quiet 0001..0023 -> UNCHANGED
git status migrations/ -> ?? versions/0024_approval_store.py   (the only change)
```

---

## 11. Known limitations

1. **The TestClient shutdown hang.** Three harnesses in one chain today showed
   the anyio-portal death/hang (`This portal is not running`; post-report hang).
   Solo re-runs pass at full counts, so it is environmental, not a regression —
   but it is now reproducible enough to deserve its own look. Not this phase's.
2. **No production or staging database was inspected.** Readiness was proven
   against databases built by this repository's own migrations, which ADR-109
   defines production to be.
3. **`downgrade()` drops `cp_approval`**, and with it every approval row. That
   is the symmetric inverse the brief asked for and what every sibling does; it
   is stated so nobody runs it casually.
4. **The existence guard means an already-present table is trusted as-is.** If
   a `create_all`-built `cp_approval` ever diverged from `approval_table`, this
   migration would not correct it. Today they cannot diverge — both are
   generated from the same `Table` object — but the guard trades that
   correction for the ability to run on every existing database.
5. **Global `alembic check` still fails**, by design, on the pre-existing drift
   ADR-112 classified. 132 operations remain and are unchanged.
6. Two of my probe inputs were wrong (§5); the repository refused both
   correctly.
