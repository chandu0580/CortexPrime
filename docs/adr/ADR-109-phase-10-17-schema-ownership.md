# ADR-109 — Alembic is the canonical application-schema owner

- **Status:** PROPOSED — discovery only. No production code, no migration, no
  Docker change, no frontend change.
- **Date:** 2026-09-07
- **Phase:** 10.17 (discovery)
- **Evidence:** `docs/PHASE_10_17_SCHEMA_OWNERSHIP_DISCOVERY.md`
- **Unblocks:** Phase 10.16, which stopped because two schema authorities
  disagreed about `missions` (ADR-108)

> **Numbering.** The brief specified the filename `ADR-108-...`, but **108 is
> already taken by Phase 10.16** (`ADR-108-phase-10-16-missions-orm-mapping.md`).
> The brief's own IMPORTANT block takes precedence — *"Determine the next
> available ADR number... Do NOT overwrite an existing ADR"* — so this is
> **ADR-109**. For the record, the outstanding collision is that **ADR-107 is
> used twice**, by Phase 10.14 and Phase 10.15; 108 and 109 are each used once.

## Context

Phase 10.16 was to add one ORM model for the existing `missions` table. It
stopped at its own rule 5: migration `0001` and `infra/postgres/init.sql` define
**different** `missions` tables, and `init.sql` is live — mounted into
`/docker-entrypoint-initdb.d` by the dev and staging compose files. A model
copied from `0001` would be right on a migrated database and wrong on a
compose-bootstrapped one.

That is a schema-ownership question, and this phase was called to settle it.

## Decision

**Alembic migrations are the single canonical owner of the application schema.
`infra/postgres/init.sql` owns nothing that anything still needs.**

Not chosen for convenience. Seven independent lines of evidence:

1. It is the only mechanism present in **every** environment.
2. **Production, air-gapped and Helm deployments never mount `init.sql`** — they
   are already Alembic-only by configuration.
3. It is the only mechanism with a replayable lineage (`0001 → 0023`,
   single head, no branches).
4. It is the shape **every existing migrated database actually has** — reflected
   from two databases at head, matching `0001` on all six points of
   disagreement.
5. The ORM's own conventions already agree with it: `TimestampMixin` declares
   both timestamps `nullable=False` and `UUIDPrimaryKeyMixin` uses
   `gen_random_uuid()` — `init.sql` contradicts both.
6. `0001`'s `downgrade()` explicitly calls `init.sql` **legacy**, distinguishing
   tables *"bootstrapped by the legacy init.sql, not created by any upgrade()
   here"* from its own with a different drop style. The author knew.
7. Alembic creates all three extensions and the `set_updated_at()` function
   itself, so `init.sql` is not even required for infrastructure.

### `init.sql` can be removed, and this was tested rather than assumed

The brief warned against assuming it could disappear. Every category was checked:

| Category | Needed from `init.sql`? |
|---|---|
| Extensions (`vector`, `uuid-ossp`, `pg_trgm`) | No — `0001` creates all three |
| Users, roles, schemas | No — it creates none |
| Application tables | No — **6 of 8 duplicate `0001`**; the other 2 have **no consumer** |
| Seed data | No — it contains no `INSERT` |
| Functions | No — `set_updated_at()` is created by `0001` |
| Indexes, constraints | No |
| Triggers | No — 2 duplicate `0001`/`0002`; the **4 exclusive ones provably never fire** |
| GRANTs | No — the grantee is the database owner, and they run before Alembic creates anything |

The trigger claim is the one that could have blocked this, and it resolves
cleanly: the four `init.sql`-exclusive triggers cover `missions`,
`reflection_history`, `runtime_analytics` and `embedding_cache`, and **no code
anywhere issues an `UPDATE` against any of those four tables.** Every write is
an INSERT or goes through the ORM, which already maintains `updated_at` in
Python via `onupdate`. So no migration is needed to adopt them — there is no
behaviour to preserve.

**Rejected:** Option B (`init.sql` authoritative) would make every existing
database wrong and requires a stamp that cannot honestly exist. Option C
(parallel authorities) *is* the current state, and it is proven mutually
incompatible. Option D (a dedicated migration Job) has real merit and is
**deferred, not rejected** — it is orthogonal to ownership and should follow it.

## The finding that matters more than the one we were looking for

While establishing the above, `backend/entrypoint.sh` was found to contain a
pre-stamp block that writes `alembic_version = '0008'` into **any** database
where that table is empty — **including a brand-new empty one**. Its comment
says it is for a database *"restored from a pre-Alembic backup"*; its condition
does not test that.

Verified by execution against a fresh empty database:

```
INSERT 0 1                    -- stamped '0008'
$ alembic upgrade head
UndefinedObjectError: index "idx_connector_activity_status" does not exist
tables in public schema: 1
```

`'0008'` is not a revision id — the real one is `0008_add_connector_status` —
but Alembic resolves partial ids by unique prefix, so instead of erroring it
**silently skips migrations `0001` through `0008`** and dies inside `0009`. The
database is left with **one table and no application schema**.

Three defects in nine lines: it tests for an empty version table rather than for
an existing schema; it stamps a revision id that does not exist; and it creates
`alembic_version` as `VARCHAR(32)` when real revision ids reach **35**
characters and Alembic's own column is `VARCHAR(128)`.

It is gated on `DATABASE_URL`, which no compose file sets and no Python module
reads — **but `docs/ADMINISTRATOR_GUIDE.md:265` tells operators to set it.** An
operator following the administrator guide arms it. The same variable also gates
the advisory migration lock, which is therefore a silent no-op in every compose
deployment today.

**This is independent of `missions` and more dangerous than it.**

## Consequences

**Nothing changed.** Discovery only: two documents, no code, no migration, no
Docker change. Two disposable databases were created to obtain the evidence in
§2 and §5 of the discovery report and were dropped afterwards.

**Dev and staging are currently broken from a fresh volume**, and this explains
why: `init.sql` creates `missions`, then `alembic upgrade head` runs `0001`,
which creates `missions` with no `IF NOT EXISTS` guard, and fails with
`DuplicateTableError`. In dev, `BLOCK_ON_MIGRATION_FAILURE` is unset, so the
entrypoint logs *"continuing anyway"*. In staging it is `"true"`, so start-up
aborts. **No CI job runs the compose bootstrap and the migrations together** —
the compose smoke test starts Postgres, runs `pg_isready`, and tears down
without ever starting the backend. That is why this survived.

**Existing dev/staging volumes must be recreated, not repaired.** `init.sql`'s
schema is not an *earlier* point in the lineage, it is a *different shape*, so
there is no revision it could honestly be stamped at. That state is not
supportable and must be prevented rather than migrated. It is acceptable to
recreate them: they cannot start today.

**No existing data is at risk.** `/docker-entrypoint-initdb.d` runs only on the
first initialisation of a fresh volume, so unmounting it changes only future
initialisations. No proposed change adds a `DROP`, touches a migration, or
alters a live schema.

**Phase 10.16 is unblocked.** Once `init.sql` stops being a competing authority,
the model copied from `0001` — already fully specified in
`docs/PHASE_10_16_IMPLEMENTATION_MAP.md` §6 — is unambiguously correct, and its
`alembic check` verification becomes meaningful.

**Governance is untouched.** `DURABLE_METADATA` and the `cp_*`/`cw_*` tables are
created by migrations `0010`+ and were never part of either bootstrap.

## Preconditions for the implementation phase

Stated explicitly rather than left to inference:

- **P1.** The entrypoint pre-stamp must be removed, or corrected to test for
  schema presence and use a real revision id, **before or alongside** unmounting
  `init.sql`. Leaving it while fresh databases become the normal case makes it
  *more* likely to fire, not less.
- **P2.** Existing dev/staging volumes must be recreated. No honest stamp exists
  for them.

## Recorded, and deliberately not mixed in

`backend/memory/event_subscriber.py` passes an execution id as `mission_id` into
`store_reflection`, inside a `try` that swallows every exception at
`logger.debug` — a potential silent data-loss defect, **[NOT VERIFIED]**,
independent of schema ownership, needing its own phase.
