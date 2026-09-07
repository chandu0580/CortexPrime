# Phase 10.16 — Restore the missing `missions` ORM mapping
## Verification Report

**STATUS: STOPPED** at implementation rule 5 / stop condition 1 —
*migration `0001` and `init.sql` disagree.*

No production code was written. No migration was created. No schema changed.

Every claim is labelled and every one is evidenced by a source read, a
reflection of a real PostgreSQL database, or a command that was actually run.

---

## 1. Section results

| § | Area | Result |
|---|---|---|
| 2 | Rule 3 — `0001` vs `init.sql` | **DISAGREE, six ways** [VERIFIED] |
| 3 | Rule 4 — reflection of a migrated database | matches `0001` on all six [VERIFIED] |
| 4 | Both shapes are really produced by this project | [VERIFIED] by execution |
| 5 | A database `init.sql` built cannot be migrated | [VERIFIED] by execution |
| 6 | Mandatory verification A–I | **NOT REACHED** — nothing to verify |
| 7 | Stop conditions | **1 fired** |

---

## 2. Rule 3 — the two sources disagree [VERIFIED]

`backend/database/migrations/versions/0001_initial_schema.py:31-49` against
`infra/postgres/init.sql:79-98`.

| # | Aspect | migration `0001` | `init.sql` | Material? |
|---|---|---|---|---|
| 1 | `id` default | `gen_random_uuid()` | `uuid_generate_v4()` | different function, different extension (`pgcrypto`/built-in vs `uuid-ossp`) |
| 2 | `status` type | `VARCHAR(32)` | `TEXT` | **yes — a length constraint exists in one and not the other** |
| 3 | `created_at` nullable | **NOT NULL** | **NULL** | **yes** |
| 4 | `updated_at` nullable | **NOT NULL** | **NULL** | **yes** |
| 5 | check constraint name | `ck_missions_status` | `missions_status_check` | yes — a migration referring to one by name fails on the other |
| 6 | index ordering | `(status, created_at)` | `(status, created_at DESC)` | yes — different index definition |

These are not cosmetic. Two are nullability differences and one is a type
difference; an ORM model can only be correct for one of them.

**Rule 5:** *"If migration 0001 and init.sql disagree: STOP. Do not choose one
silently. Report the discrepancy."* — **this is that report.**

---

## 3. Rule 4 — reflection of a real migrated database [VERIFIED]

`cortex_p99b` and `cortex_p1014_fresh`, both at `alembic_version =
0023_retire_iam`. Identical results from both:

```
 column_name  |        data_type         | len | is_nullable |        column_default
--------------+--------------------------+-----+-------------+------------------------------
 id           | uuid                     |     | NO          | gen_random_uuid()
 title        | text                     |     | NO          |
 objective    | text                     |     | NO          |
 status       | character varying        |  32 | NO          | 'pending'::character varying
 priority     | integer                  |     | YES         | 5
 result       | text                     |     | YES         |
 metadata     | jsonb                    |     | YES         | '{}'::jsonb
 started_at   | timestamp with time zone |     | YES         |
 completed_at | timestamp with time zone |     | YES         |
 created_at   | timestamp with time zone |     | NO          | now()
 updated_at   | timestamp with time zone |     | NO          | now()
```

Constraints: `missions_pkey` (PK), **`ck_missions_status`**.
Indexes: `missions_pkey`, `idx_missions_status ... btree (status, created_at)` — **ascending**.

**Every one of the six disagreements resolves in favour of migration `0001`.**
Foreign keys unchanged and correct:

```
reflection_history   mission_id  ->  missions     SET NULL
runtime_analytics    mission_id  ->  missions     SET NULL
mission_steps        mission_id  ->  missions_bc  CASCADE
executions           mission_id  ->  missions_bc  SET NULL
```

**On the evidence, `0001` is what every migratable database contains.** That
makes the *repair* unambiguous. It does **not** make the *discrepancy* resolved,
for the reason in §4.

---

## 4. `init.sql` is not a dead file — it builds a different table, in this
   project's own deployment path [VERIFIED]

This is why the stop is real rather than bookkeeping.

`infra/postgres/init.sql` is mounted into PostgreSQL's initialisation directory
by **both** compose files:

```
docker-compose.yml:251          ./infra/postgres/init.sql:/docker-entrypoint-initdb.d/01_init.sql:ro
docker-compose.staging.yml:185  ./infra/postgres/init.sql:/docker-entrypoint-initdb.d/01_init.sql:ro
```

Anything in `/docker-entrypoint-initdb.d` is executed by the official Postgres
image on first initialisation of a fresh data volume. **So a developer or a
staging deployment bringing this project up with its own compose file gets the
`init.sql` shape of `missions`, not the `0001` shape.**

Proven, not inferred. A disposable database `cortex_p1016_initsql` was created
and `init.sql` run against it. Reflection:

```
 column_name  |        data_type         | len | is_nullable |   column_default
--------------+--------------------------+-----+-------------+--------------------
 id           | uuid                     |     | NO          | uuid_generate_v4()
 status       | text                     |     | NO          | 'pending'::text
 created_at   | timestamp with time zone |     | YES         | now()
 updated_at   | timestamp with time zone |     | YES         | now()
```

Constraints: `missions_pkey`, **`missions_status_check`**.
Index: `idx_missions_status ... btree (status, created_at DESC)` — **descending**.

**Both shapes exist in reality, and this project produces both.** An ORM model
copied from `0001` would be correct on a migrated database and **wrong on a
compose-bootstrapped one**, where `alembic check` — the capability this repair
exists to restore — would report drift on `status`, on two nullability flags, on
the constraint name and on the index.

`init.sql` also writes **no `alembic_version` row** (grepped: no `alembic`
reference anywhere in the file).

---

## 5. A second defect, found while establishing the first: an `init.sql`
   database can never be migrated [VERIFIED by execution]

`0001.upgrade()` calls `op.create_table("missions", ...)` unconditionally —
there is no `IF NOT EXISTS` guard — and `backend/database/migrator.py` contains
no `stamp`, baseline or `DuplicateTable` handling (grepped).

Run against the `init.sql`-bootstrapped database:

```
$ POSTGRES_URL=...cortex_p1016_initsql  python -m alembic ... upgrade head

asyncpg.exceptions.DuplicateTableError: relation "missions" already exists
sqlalchemy.exc.ProgrammingError: ... DuplicateTableError: relation "missions" already exists

$ SELECT version_num FROM alembic_version;
ERROR:  relation "alembic_version" does not exist
```

**A database created by this project's own `docker-compose` cannot be migrated
at all.** It fails on the very first revision and never acquires an
`alembic_version` row, so it can never join the lineage.

This is outside Phase 10.16's scope and is **reported, not repaired**. It is
recorded here because it is the reason the discrepancy cannot be waved through:
the two schema sources are not merely inconsistent on paper, they are mutually
exclusive in practice, and nobody has decided which one owns the schema.

---

## 6. Mandatory verification A–I — NOT REACHED

The brief's sections A–I verify a change. **No change was made, so none of them
was run.** They are listed here as not-run rather than omitted, so the record
cannot be mistaken for a pass.

| § | Check | Status |
|---|---|---|
| A | metadata completeness before/after | **NOT RUN** — "before" state re-confirmed in Phase 10.15 (§6 of that report): exactly one unmapped FK target, `missions`, referenced by two columns |
| B | `Base.metadata.sorted_tables` succeeds | **NOT RUN** — still raises `NoReferencedTableError`, unchanged |
| C | fresh database initialization | **NOT RUN** |
| D | existing migrated database | **NOT RUN** |
| E | reflection equality | **PARTIALLY RUN as stop evidence** — §3 and §4 reflect the real tables; no ORM model exists to compare them against |
| F | both FKs remain with `SET NULL` | **VERIFIED as stop evidence** (§3) — and trivially so, since nothing was changed |
| G | `alembic check` / `--autogenerate` | **NOT RUN.** `alembic check` still fails inside `sorted_tables`, exactly as Phase 10.15 recorded. No temporary revision was generated, so none needed deleting |
| H | live FK `ON DELETE SET NULL` behaviour test | **NOT RUN** — deliberately. It would have required inserting disposable rows into `missions` and `reflection_history`; with the phase stopped there is no hypothesis to test, and writing rows to prove a constraint nobody is changing would be noise |
| I | regression, architecture, harnesses 10.7–10.14 | **NOT RUN** — no production code changed, so there is nothing that could have regressed. The working tree contains only new documentation |

**Working tree at the stop:** three new files under `docs/`. Zero modifications
to `backend/`, `tests/`, `scripts/` or `infra/`.

---

## 7. Stop conditions

| # | Condition | Result |
|---|---|---|
| 1 | **migration `0001` and `init.sql` disagree** | **FIRED — §2, six differences, §4 proves both are real** |
| 2 | reflected schema differs from the proposed model | Not reached. Reflection matches `0001` exactly (§3), so the proposed model would have been correct *for migrated databases* |
| 3 | adding the model causes Alembic to detect unrelated drift | Not reached |
| 4 | the model would require changing existing tables | **No** — §3; the table already matches `0001` |
| 5 | FK behaviour differs from existing database behaviour | **No** — both FKs present with `SET NULL` (§3) |
| 6 | Mission Runtime becomes coupled to the V1 `missions` table | **No** — nothing was written |
| 7 | governance/tenant/authority semantics change | **No** — nothing was written; `DURABLE_METADATA` untouched |
| 8 | a migration appears necessary | **Not for the mapping.** But see §5 — a migration or a change to `init.sql` may be necessary for the *separate* defect, which is a decision, not a workaround |

Condition 1 fired. Per the brief — *"DO NOT workaround it. Report the exact
evidence."* — no workaround was attempted and no source was silently chosen.

---

## 8. What the decision needs to be

Not made here. Stated so the next phase has the options rather than re-deriving
them.

The mapping repair is blocked on one question: **which artefact owns the
`missions` schema?**

- **If migration `0001` owns it** — which the evidence favours, since it is the
  only source in the alembic lineage and matches every migratable database —
  then `init.sql` is a divergent legacy bootstrap that also **breaks
  migrations** (§5), and the correct action is to stop mounting it, or reduce it
  to the extensions and roles that Alembic does not create. That is a change to
  deployment configuration, which this brief's rule 9 does not authorise and
  which deserves its own evidence.
- **If `init.sql` owns it**, then migration `0001` has been producing the wrong
  schema since the beginning and the ORM model must be copied from `init.sql`
  instead — in which case every existing migrated database is also wrong.

Only the first is consistent with the evidence, but **choosing it is exactly
what rule 5 forbids me from doing silently**, and it carries a consequence
(unmounting or rewriting a file used by two compose stacks) well beyond "add one
ORM model".

**Recommended sequence:** settle the `init.sql` question first, in its own
phase; then Phase 10.16 becomes a small, unambiguous change that the map in
`docs/PHASE_10_16_IMPLEMENTATION_MAP.md` §6 already specifies in full.

---

## 9. Honest limitations

1. **No production or staging database was inspected.** §4's claim that a
   compose-bootstrapped environment has the `init.sql` shape is proven for a
   database built by running that file, and by reading the two compose mounts —
   **not** by inspecting a deployed environment, because none was available.
2. **§5 proves migration fails on a database built *only* by `init.sql`.** A
   real deployment might differ if some other step stamps or pre-creates
   `alembic_version`; no such step was found in `backend/database/migrator.py`,
   but absence of a found mechanism is weaker than proof that none exists.
3. **The disposable database `cortex_p1016_initsql` was left in place** on
   `cortex-p99b-pg` as the evidence for §4 and §5. It holds no real data and can
   be dropped at any time.
4. **No claim is made that the proposed model is correct**, because it was never
   written or executed. §3 establishes only that it would match the reflected
   schema of migrated databases.
