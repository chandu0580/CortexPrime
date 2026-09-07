# Phase 10.17 — Resolve Competing Schema Authorities for `missions`
## Schema Ownership Discovery (DISCOVERY ONLY — no production code, no migration, no Docker change)

**STATUS: GO**, with two named preconditions and one finding more urgent than
the one the phase was called to settle.

Every claim is labelled. Evidence is a source read, a configuration read, a
reflection of a real PostgreSQL database, or a command that was actually run.

---

## 0. Summary

The competing-authority question has a clean answer: **Alembic is the canonical
application-schema owner, and `infra/postgres/init.sql` owns nothing that
anything still needs.** Its exclusive contributions are two tables with no
consumer and four triggers that provably never fire; everything else it creates
is a duplicate of what migration `0001` creates, in a *different shape*.

While proving that, a **second and more dangerous defect** was found and
verified by execution: `backend/entrypoint.sh` contains a pre-stamp block that
writes `alembic_version = '0008'` into **any** database where that table is
empty — **including a brand-new empty one**. `alembic upgrade head` then
prefix-resolves `'0008'` to `0008_add_connector_status`, **skips migrations
`0001`–`0008` entirely**, and dies inside `0009`. The database is left with
**one table**. The block is gated on `DATABASE_URL`, which no compose file
sets — but `docs/ADMINISTRATOR_GUIDE.md:265` **tells operators to set it**.

That defect can silently destroy a fresh production deployment's schema, and it
is independent of `missions`.

---

## 1. Task A — every schema-creation mechanism [VERIFIED]

| # | Mechanism | Invoked by | When | Creates | Still used | Creates `alembic_version` | Authority |
|---|---|---|---|---|---|---|---|
| 1 | **Alembic migrations** `0001`→`0023` | `backend/entrypoint.sh` (`alembic upgrade head`); Dockerfile `ENTRYPOINT` | every container start | 55 tables incl. all `cp_*`/`cw_*` | **yes** | yes (alembic itself, `VARCHAR(128)`) | **authoritative** |
| 2 | `infra/postgres/init.sql` | Postgres image, via `/docker-entrypoint-initdb.d` | **first init of a fresh volume only** | 8 tables, 3 extensions, 1 function, 6 triggers, 3 GRANTs | mounted by dev + staging compose | **no** | bootstrap — and in conflict (§3) |
| 3 | **entrypoint pre-stamp** | `backend/entrypoint.sh` when `DATABASE_URL` is set | before `upgrade head` | `alembic_version` only, stamped `'0008'` | **yes, if `DATABASE_URL` set** | **yes — hand-rolled, `VARCHAR(32)`** | **defective (§5)** |
| 4 | `init_db()` → `Base.metadata.create_all` | `backend/main.py` step 7 | boot, dev only | would create V1 `Base` tables | gated, refused by default, **currently raises** (Phase 10.15) | no | dev convenience only |
| 5 | `DURABLE_METADATA.create_all` | phase harnesses / `build_development_store` | harness setup | `cp_*` / `cw_*` only (25) | **yes** | no | disposable harness only |
| 6 | Local `Base` + SQLite `create_all` | `tests/architecture/probes.py:156`, `tests/database/test_tenant_scoped_repository.py:111` | test run | 1 throwaway table each | yes | no | test-local, own metadata |

**No other mechanism exists.** `helm/cortexprime` contains **no** alembic,
init.sql, migration Job or initContainer reference — the Kubernetes path relies
on mechanism 1 through the image ENTRYPOINT. `docker-compose.prod.yml`'s
`entrypoint:` at line 150 belongs to the **backup sidecar** (crond + `pg_dump`),
not the backend.

---

## 2. Task B — the lifecycle of every supported environment [VERIFIED from configuration; §2.6 notes what was and was not executed]

| Environment | CREATE | MIGRATE | RUN | Deterministic today? |
|---|---|---|---|---|
| **Docker Compose (dev)** `docker-compose.yml` | `init.sql` on fresh volume → 8 tables, init.sql shape, **no `alembic_version`** | `entrypoint.sh` → pre-stamp **skipped** (`DATABASE_URL` unset) → `alembic upgrade head` → **`DuplicateTableError: relation "missions" already exists`** → 10 retries → all fail | `BLOCK_ON_MIGRATION_FAILURE` **unset ⇒ false** ⇒ *"continuing anyway"*; then `main.py` step 7 raises because `_migration_ok` is false | **NO — broken** |
| **Docker Compose (staging)** | same `init.sql` mount (`:185`) | same failure | `BLOCK_ON_MIGRATION_FAILURE: "true"` (`:88`) ⇒ **aborts explicitly** | **NO — fails closed** |
| **Production** `docker-compose.prod.yml` | **no `init.sql` mount** — empty database | `entrypoint.sh` → `alembic upgrade head` from `0001` | `BLOCK_ON_MIGRATION_FAILURE=true` (`:18`) | **YES**, *unless* `DATABASE_URL` is set (§5) |
| **Air-gapped** `docker-compose.airgap.yml` | **no `init.sql` mount** | same as production | `BLOCK_ON_MIGRATION_FAILURE: "true"` (`:42`) | **YES**, same caveat |
| **Kubernetes / Helm** | empty database | image ENTRYPOINT → `entrypoint.sh` | chart has no migration hook | **YES**, same caveat |
| **CI — unit tests** `.github/workflows/test.yml` | bare `pgvector/pgvector:pg16` service, **no `init.sql`** | **none — `SKIP_DB_MIGRATIONS: "true"`** | pytest directly; `entrypoint.sh` never runs | yes — **no application schema at all**; DB tests self-skip |
| **CI — compose smoke** `test.yml:248` | `docker compose up -d cortex-postgres cortex-redis` → **`init.sql` runs** | **never** — only `pg_isready`, then `docker compose down -v` | backend never started | yes, but **exercises nothing** |
| **Disposable harnesses** | `DURABLE_METADATA.create_all`, or `alembic upgrade head` on a purpose-made DB | explicit, per harness | harness process | yes |

**The critical structural finding:** the two environments that mount `init.sql`
are the only two that are broken, and **no CI job ever runs the compose
bootstrap and the migrations together.** The compose smoke test starts Postgres,
checks `pg_isready`, and tears down — it never starts the backend. That is why a
mutually incompatible bootstrap has survived undetected.

### 2.6 What was executed vs. read

- **Executed** [VERIFIED]: `init.sql` against a disposable database, then
  `alembic upgrade head` → `DuplicateTableError` (Phase 10.16, re-confirmed);
  the entrypoint's exact pre-stamp SQL against a fresh empty database, then
  `alembic upgrade head` → skipped to `0009` and failed (§5).
- **Read, not executed**: the compose stacks themselves were not brought up —
  they start Postgres, Redis, RabbitMQ, Neo4j, OpenSearch, Vault and the
  backend. The lifecycle table is derived from the compose files, the Dockerfile
  ENTRYPOINT, `entrypoint.sh` and `main.py`, with the decisive database step
  proven in isolation.

---

## 3. Task C — `init.sql` analysed table by table [VERIFIED]

`infra/postgres/init.sql`, 270 lines, creates **8 tables**:

| Table | Also created by Alembic? | Definition identical? | Ownership |
|---|---|---|---|
| `episodic_memory` | `0001` | **no** (`uuid_generate_v4()` vs `gen_random_uuid()`) | **duplicated** |
| `semantic_memory` | `0001` | **no** (same) | **duplicated** |
| `missions` | `0001` | **no — six differences (§4)** | **duplicated, conflicting** |
| `reflection_history` | `0001` | **no** | **duplicated** |
| `runtime_analytics` | `0001` | **no** | **duplicated** |
| `embedding_cache` | `0001` | **no** | **duplicated** |
| `cognition_events` | **no migration** | n/a | **bootstrap-only** |
| `agent_sessions` | **no migration** | n/a | **bootstrap-only** |

**Six of eight tables are duplicated schema ownership.** The two exclusive ones
have **no consumer**: a search across all Python finds `agent_sessions`
**nowhere**, and `cognition_events` only as an unrelated *Neo4j* variable name
in `backend/infrastructure/neo4j/traversal.py:296` and in `0001`'s own
`downgrade()`. Neither has an ORM model.

> `0001`'s downgrade comment claims *"cognition_events is created outside
> Alembic entirely via `Base.metadata.create_all()`"*. That is **stale**: no
> model declares it, and it is absent from the 38 tables on `Base.metadata`.

### Non-table content — is it infrastructure or application?

| Content | Also in Alembic? | Classification |
|---|---|---|
| `CREATE EXTENSION vector`, `"uuid-ossp"`, `pg_trgm` (lines 14-16) | **yes — `0001` creates all three** | infrastructure, **redundant** |
| `set_updated_at()` function (line 232) | **yes — `0001:89`** | **redundant** |
| 6 `updated_at` triggers (240-260) | **only 2** — `0001` creates episodic + semantic; `0002` adds audit_logs | **4 are init.sql-exclusive** |
| 3 `GRANT`s to role `cortex` (268-270) | no | effectively **no-op** — `cortex` is `POSTGRES_USER`, i.e. the owner, and the grants run before Alembic creates anything |
| Seed data | none — **no `INSERT`** anywhere | n/a |
| Roles / users / schemas | none created | n/a |

**The four exclusive triggers never fire** [VERIFIED]. They cover `missions`,
`reflection_history`, `runtime_analytics` and `embedding_cache`. A search for
`UPDATE` against any of those four tables in Python returns **no matches** —
every write path is either an INSERT (raw SQL, `reflection_store.py`) or goes
through the ORM, and `TimestampMixin` already maintains `updated_at` in Python
via `onupdate=_utcnow` (`backend/database/models/mixins.py`). Confirmed by
count: the Alembic-built `cortex_p99b` has exactly **3** non-internal triggers.

**Conclusion: `init.sql` owns nothing that anything still needs.**

---

## 4. Task D — migration `0001` [VERIFIED]

- **What it represents:** the original CortexPrime memory schema —
  `missions`, `episodic_memory`, `semantic_memory`, `reflection_history`,
  `runtime_analytics`, `embedding_cache`, plus the three extensions and the
  `set_updated_at()` function.
- **Is it the true canonical lineage?** Yes. It is `down_revision = None`, the
  root of a single unbroken chain `0001 → 0023_retire_iam` with no branches, and
  the only lineage `alembic upgrade head` can replay.
- **Is it expected to run on an empty database?** **Yes.** `upgrade()` calls
  `op.create_table("missions", ...)` with **no `IF NOT EXISTS` guard** — its
  first statement after the extensions. It cannot tolerate a pre-existing table.
- **Are its objects expected to be created by Compose beforehand?** **No** — and
  the evidence is explicit. `0001`'s `downgrade()` distinguishes the two cases in
  prose: `reflection_log` and `cognition_events` *"predate this migration chain
  (bootstrapped by the legacy init.sql, **not created by any upgrade() here**)"*,
  and are removed with `DROP TABLE IF EXISTS`, while everything `0001` creates is
  removed with a plain `op.drop_table`. The author knew `init.sql` existed and
  treated it as **legacy**.
- **Baseline/stamp mechanism?** One exists, in `backend/entrypoint.sh`, and it
  is broken — §5.

### The six differences on `missions`

| # | Aspect | `0001` | `init.sql` | Real migrated DB |
|---|---|---|---|---|
| 1 | `id` default | `gen_random_uuid()` | `uuid_generate_v4()` | **`gen_random_uuid()`** |
| 2 | `status` | `VARCHAR(32)` | `TEXT` | **`character varying(32)`** |
| 3 | `created_at` | NOT NULL | NULL | **NOT NULL** |
| 4 | `updated_at` | NOT NULL | NULL | **NOT NULL** |
| 5 | check constraint | `ck_missions_status` | `missions_status_check` | **`ck_missions_status`** |
| 6 | index | `(status, created_at)` | `(status, created_at DESC)` | **ascending** |

Reflected identically from `cortex_p99b` and `cortex_p1014_fresh`, both at
`0023_retire_iam`. Corroborating: `TimestampMixin` declares both timestamps
`nullable=False` and `UUIDPrimaryKeyMixin` uses `gen_random_uuid()` — **the ORM
convention already agrees with `0001`, not with `init.sql`.**

---

## 5. Task E — `alembic_version`, and a defect worse than the one being investigated [VERIFIED BY EXECUTION]

Every place it is touched:

| Location | Action |
|---|---|
| Alembic itself | creates it (`VARCHAR(128)` in `cortex_p99b`) and updates it per revision |
| **`backend/entrypoint.sh:36-47`** | **creates it as `VARCHAR(32)` and INSERTs `'0008'` if empty** |
| `backend/database/migrator.py` | reads current revisions only — **no stamp, no baseline, no `DuplicateTable` handling** (grepped) |
| `infra/postgres/init.sql` | **never mentions alembic** |

The pre-stamp block:

```sql
CREATE TABLE IF NOT EXISTS alembic_version (
    version_num VARCHAR(32) NOT NULL, ...);
INSERT INTO alembic_version (version_num)
SELECT '0008'
WHERE NOT EXISTS (SELECT 1 FROM alembic_version);
```

Its comment says it is for *"a DB restored from a pre-Alembic backup"*. **Its
condition does not say that.** It fires whenever `alembic_version` is empty —
which is also true of a **brand-new, completely empty database**.

**Executed against a fresh empty database:**

```
INSERT 0 1                       -- stamped '0008'
tables in public schema: 1       -- only alembic_version

$ alembic upgrade head
sqlalchemy.exc.ProgrammingError: UndefinedObjectError:
index "idx_connector_activity_status" does not exist
[SQL: DROP INDEX idx_connector_activity_status]

tables in public schema: 1
```

**What happens:** `'0008'` is a *partial* revision id, and Alembic resolves
partial ids by unique prefix — it matches `0008_add_connector_status`. Alembic
therefore believes migrations `0001`–`0008` have already run, starts at
`0009_consolidate_connector_activity`, and immediately fails trying to drop an
index that was never created. **The database ends with one table and no
application schema whatsoever.**

Three distinct defects in nine lines:

1. **It stamps empty databases**, not just restored ones — the condition tests
   the wrong thing.
2. **`'0008'` is not a revision id.** The real one is
   `0008_add_connector_status`. It only "works" by accident of prefix matching,
   which is what makes the skip silent instead of an error.
3. **`VARCHAR(32)` is too narrow.** Real revision ids reach **35** characters
   (`0009_consolidate_connector_activity`) and **34**
   (`0003_consolidate_reflection_tables`). Alembic's own table is `VARCHAR(128)`.
   Where the entrypoint wins the race to create it, storing those revisions
   would overflow.

**Reachability** [VERIFIED]: the block is gated on `DATABASE_URL`. **No compose
file sets it, and no Python module reads it** — the application uses
`POSTGRES_URL`. But **`docs/ADMINISTRATOR_GUIDE.md:265` instructs operators to
set `DATABASE_URL`** in their environment file. An operator following the
administrator guide arms this. The same variable also gates the advisory
migration lock, which is therefore a silent no-op today (`|| true`) in every
compose deployment.

### What *should* happen to an `init.sql` database?

**Nothing can.** `init.sql`'s schema is not equal to any point in the lineage —
it is a *different shape* (§4), not an earlier one. **There is no revision it
could honestly be stamped at.** That state is therefore not repairable by
stamping; it must be prevented. It is **not supported**, and today it is
produced by default in dev and staging.

---

## 6. Task F — what Compose actually needs from `/docker-entrypoint-initdb.d`

Separating infrastructure bootstrap from application schema:

| Need | Required from `init.sql`? | Evidence |
|---|---|---|
| **Extensions** (`vector`, `uuid-ossp`, `pg_trgm`) | **No** — `0001` creates all three, `IF NOT EXISTS` | `0001:24-26` |
| **Users / roles** | **No** — none created; the role comes from `POSTGRES_USER` | grepped: no `CREATE ROLE`/`CREATE USER` |
| **Schemas** | **No** — only `public` | grepped: no `CREATE SCHEMA` |
| **Application tables** | **No** — 6 duplicated by `0001`, 2 with no consumer | §3 |
| **Seed data** | **No** — no `INSERT` anywhere | grepped |
| **Functions** | **No** — `set_updated_at()` is created by `0001:89` | §3 |
| **Indexes / constraints** | **No** — Alembic creates its own | §3 |
| **Triggers** | **No** — 2 duplicated, 4 exclusive but proven never to fire | §3 |
| **GRANTs** | **No** — grantee is the owner; runs before Alembic creates anything | §3 |

**`init.sql` can disappear entirely without losing a capability.** That
conclusion was tested against the brief's warning not to assume it: every
category was checked, and each is either created by Alembic or has no consumer.
The one nuance is `uuid-ossp`, which only `init.sql`'s own DDL uses — Alembic
uses `gen_random_uuid()` — and `0001` creates that extension anyway.

---

## 7. Task G — ownership options

### OPTION A — Alembic owns the application schema; `init.sql` keeps only infrastructure (**RECOMMENDED**)

In practice this means reducing `init.sql` to nothing, or to the three
`CREATE EXTENSION` lines as belt-and-braces, and unmounting it from both compose
files.

| Dimension | Outcome |
|---|---|
| Fresh database | empty → `0001`…`0023` replay cleanly. **Deterministic** |
| Compose | dev and staging become identical to prod and Helm |
| `alembic upgrade` | works from `0001`; no duplicate-table failure |
| `alembic check` | usable once Phase 10.16 lands the ORM model; no drift from this change |
| Production safety | **no change** — prod never mounted `init.sql`. Existing prod databases are already Option-A shaped |
| Staging safety | staging stops failing closed; **requires a fresh volume** |
| CI/test | unchanged; the compose smoke job stops producing an unmigratable database |
| Migration history | **untouched — nothing rewritten** |
| Existing data | **none affected.** `/docker-entrypoint-initdb.d` runs only on a *fresh* volume, so this changes only future initialisations |
| Rollback | re-add the mount; nothing is destroyed |
| Operational complexity | **reduced** — one authority, one lifecycle |
| Risks | existing dev/staging volumes already in the broken state must be recreated. They cannot be repaired by stamping (§5), and they were never usable |

### OPTION B — `init.sql` authoritative; Alembic starts from a baseline/stamp

| Dimension | Outcome |
|---|---|
| Fresh database | `init.sql` shape, stamped at some revision |
| `alembic upgrade` | **impossible to make correct.** `init.sql`'s shape matches no revision, so no stamp is honest. Stamping past `0001` also skips `episodic_memory`, `semantic_memory`, `embedding_cache` index/vector DDL that `0001` performs with raw SQL |
| Production | prod databases are `0001`-shaped; adopting `init.sql` would make **every existing production database wrong** |
| Existing data | would need a data-migration to reconcile `VARCHAR(32)`/`TEXT` and nullability |
| Migration history | would have to be rewritten or superseded |
| Verdict | **Rejected.** It inverts the evidence and breaks every database that exists |

### OPTION C — keep both authorities in parallel

| Dimension | Outcome |
|---|---|
| Everything | This **is** the current state, and it is proven mutually incompatible: dev and staging cannot start from a fresh volume (§2) |
| Verdict | **Rejected.** Not a choice — it is the defect |

### OPTION D — a different bootstrap architecture (e.g. a dedicated migration Job / initContainer)

| Dimension | Outcome |
|---|---|
| Merit | Real: migrations currently run inside the app's ENTRYPOINT, so every replica races for an advisory lock that is a **no-op** without `DATABASE_URL` (§5). A dedicated migration Job would fix that properly |
| Cost | New deployment artefacts for compose **and** Helm; larger than the question this phase asks |
| Verdict | **Deferred, not rejected.** It is orthogonal to schema *ownership* and should follow it. Recorded as the natural successor to the entrypoint repair |

---

## 8. Task H — the canonical source, by category

**Alembic migrations are the single canonical owner of the application schema.**
Not by convenience — by evidence: it is the only mechanism present in *every*
environment, the only one production and Helm use, the only one with a
replayable lineage, the shape every existing migrated database actually has, and
the shape the ORM conventions (`TimestampMixin`, `UUIDPrimaryKeyMixin`) already
match.

| Category | Owner |
|---|---|
| Table structure | **Alembic** |
| Indexes | **Alembic** |
| Constraints | **Alembic** |
| Defaults | **Alembic** |
| Triggers / functions | **Alembic** (`0001` already creates `set_updated_at()` and the two triggers that matter) |
| **Extensions** | **Alembic** primarily (`0001` creates all three). May *also* be pre-created by an infrastructure bootstrap for images lacking them — harmless, `IF NOT EXISTS`, and the only category where a second mechanism is defensible |
| Roles / users / database creation | **the container image and its `POSTGRES_*` environment** — not `init.sql`, which creates none |
| Initial data | **nobody** — none exists, and none should be introduced by a bootstrap file |
| Durable governed store (`cp_*`, `cw_*`) | **Alembic** (`0010`+). `DURABLE_METADATA.create_all` stays a disposable-harness convenience only |

---

## 9. Task I — the correct treatment of `missions`

Only after the above: **option 1 + option 5 together.**

1. **`0001` remains canonical.** ✅ It matches every migrated database and every
   ORM convention.
2. Align `init.sql` to `0001`? ❌ Pointless — it would still duplicate ownership
   and still collide on `upgrade`.
3. Change `0001`? ❌ It is live, correct, and replayed by every database.
4. A baseline migration? ❌ Not required, and not honest (§5).
5. **The Compose bootstrap should stop creating `missions`** — and the other
   seven tables with it. ✅
6. Something else? Only the **entrypoint pre-stamp removal**, which is separate
   and more urgent.

Phase 10.16's blocked model — copied from `0001`, fully specified in
`docs/PHASE_10_16_IMPLEMENTATION_MAP.md` §6 — becomes correct and unambiguous
the moment `init.sql` stops being a competing authority.

---

## 10. Task J — migration safety

| Question | Answer |
|---|---|
| Can an existing database upgrade safely? | **Yes.** The recommended change touches no migration and no existing schema |
| Does any database already contain the `init.sql` version? | **None on this machine** (§11). Any dev/staging volume created from `docker-compose.yml` since `init.sql` was added would — and would already be unable to start |
| Databases with no `alembic_version`? | **Yes — 15 of 18** (§11), all disposable harness or empty databases, none application databases |
| Could a migration accidentally recreate an existing table? | **This is exactly what happens today** (`DuplicateTableError`). The recommended change removes the cause. No new migration is proposed |
| Could `alembic upgrade head` destroy data? | **No.** No proposed change adds a `DROP`. The existing risk is the opposite — §5 leaves a database *empty* by skipping migrations, without destroying anything |
| Could `alembic check` report expected differences? | Only the `missions` model gap Phase 10.16 will close. No difference arises from this change |
| Data migration required? | **No** |
| Schema migration required? | **No** for ownership. The four `init.sql`-exclusive triggers would normally need one to be adopted — **but they provably never fire** (§3), so nothing needs adopting |

---

## 11. Existing database states, classified [VERIFIED]

All 18 databases on `cortex-p99b-pg`:

| State | Count | Databases | `alembic_version` | `missions` | Shape |
|---|---|---|---|---|---|
| **Alembic-built** | 3 | `cortex_p99b`, `cortex_p1014_fresh`, `cortex_p1014_legacy` | `0023_retire_iam` | present | **`0001` shape**, 55 tables |
| **Durable-only harness** | 13 | `cortex_p102`…`cortex_p1014` | none | absent | `cp_*`/`cw_*` only, 21–25 tables |
| **Empty** | 2 | `cortex_p1014_headprobe`, `cortex_p1014_trap` | none | absent | 0 tables |
| **`init.sql`-shaped** | **0** | — | — | — | — |
| **Pre-stamped `'0008'`** | **0** | — | — | — | — |

Every state is classified, and **no database is in either broken state**. The
two disposable databases created to prove §2 and §5 were dropped after the
evidence was captured.

---

## 12. Task K — hidden assumptions [VERIFIED]

Searched across all Python, SQL, TypeScript, YAML and shell:

| Assumption | Found? |
|---|---|
| `status` type or length | **none** — no code compares, casts or truncates `missions.status` |
| Timestamp nullability | **none in code.** The ORM convention (`TimestampMixin`, `nullable=False`) agrees with `0001` |
| UUID generation | `uuid_generate_v4` appears **only in `init.sql`** (4 tables). No Python references either function |
| Constraint names | `ck_missions_status` / `missions_status_check` appear **only** in `0001` and `init.sql`. **No code depends on either** |
| Index ordering | `idx_missions_status` appears **only** in the two DDL sources |
| Direct SQL against `missions` | **none in production code** — only `tests/test_reflection_consolidation.py` (a fixture inserting a parent row to satisfy the FK) and operator SQL in two runbooks |
| Code expecting `missions` vs `missions_bc` | **cleanly separated.** `backend/mission/service.py` uses `MissionModel` → `missions_bc`; `mission_runtime_routes.py` uses `InMemoryMissionRepository` (no SQL); **nothing** uses `missions` |

**No hidden assumption blocks either option.** The `missions` table is
structurally inert: two FKs point at it and nothing else touches it.

---

## 13. Task L — unrelated debt, recorded and NOT mixed in

Phase 10.15 identified, and this phase does **not** touch:

`backend/memory/event_subscriber.py:116` passes an **execution id** as
`mission_id` into `store_reflection`, inside a `try` that swallows every
exception at `logger.debug`. Because nothing inserts into `missions`, such a
write would violate the FK and be **silently discarded**.

**[NOT VERIFIED]** — read from source, consistent with
`tests/test_reflection_consolidation.py`'s own comment, but no live event was
driven through the path. It is a potential **data-loss** defect, it is
independent of schema ownership, and it needs its own phase. It is recorded here
only so it is not lost.

---

## 14. Stop/go

| STOP if… | Finding |
|---|---|
| more than one production schema authority is still required | **No.** Every `init.sql` category is either duplicated by Alembic or has no consumer (§6) |
| ownership cannot be established | **It can** — Alembic, on seven independent lines of evidence (§8) |
| existing databases cannot be safely classified | **All 18 classified** (§11); none in a broken state |
| migration history would need rewriting | **No.** Nothing proposed touches any migration |
| baseline/stamping semantics are unclear | **They are now clear**: `init.sql`'s shape matches no revision, so **no honest stamp exists** — that state must be prevented, not stamped (§5). The existing pre-stamp is not unclear, it is wrong, and proven so by execution |
| `init.sql` contains application behaviour that cannot safely move | **No.** Its only exclusive behaviour is four triggers that **provably never fire**, and two tables with no consumer (§3) |
| changing ownership could silently alter existing data | **No.** `/docker-entrypoint-initdb.d` runs only on a fresh volume; no existing database is touched (§10) |
| production deployment behaviour cannot be proven | **Proven from configuration**, with a stated limit — see §15.1 |

**GO**, subject to two preconditions the implementation phase must be given
explicitly rather than infer:

- **P1 — the entrypoint pre-stamp is a separate, more urgent defect.** It should
  be removed (or corrected to test for *schema presence*, not an empty version
  table, and to use a real revision id) **before or alongside** the ownership
  change. Left in place while `init.sql` is unmounted, it becomes *more*
  dangerous: fresh databases would then be the normal case, and any deployment
  setting `DATABASE_URL` per the administrator guide gets a schema-less
  database that starts anyway in dev.
- **P2 — existing dev/staging volumes must be recreated, not repaired.** No
  honest stamp exists for them (§5). This is acceptable — they cannot start
  today — but it must be stated, not discovered.

---

## 15. Honest limitations

1. **No production or staging system was inspected.** §2's production and Helm
   rows are derived from `docker-compose.prod.yml`, `docker-compose.airgap.yml`,
   `helm/cortexprime` and the Dockerfile ENTRYPOINT — the configuration that
   *defines* those deployments — but no running deployment was observed. The
   claim "production is Alembic-only" rests on the absence of an `init.sql`
   mount in those files.
2. **The compose stacks were not brought up.** The decisive database steps were
   executed in isolation (§2.6); the surrounding orchestration was read.
3. **§13 remains [NOT VERIFIED]** and deliberately out of scope.
4. **The four `init.sql` triggers are proven never to fire *by static search***
   for `UPDATE` statements plus the ORM's `onupdate`. A dynamically constructed
   UPDATE would evade that search; none was found, but absence of a found path
   is weaker than execution.
5. **`'0008'` prefix-resolution was confirmed by observing which migration ran**
   (`0009` failed), not by reading Alembic's resolver. The observable outcome —
   `0001`–`0008` skipped, one table left — is what matters and is verified.
