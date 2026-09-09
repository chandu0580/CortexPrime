# ADR-120 — Index ownership: the migration lineage owns every index; the ORM mirrors it by the migrated names; PostgreSQL-specific indexes are mirrored exactly

- **Status:** ACCEPTED
- **Date:** 2026-09-09
- **Phase:** 10.30 (discovery) + 10.31 (implementation)
- **Parents:** `37b4608` — Phase 10.29 (ADR-119); ADR-116 (the 86 operations first inventoried and STOPPED); ADR-114 (the `cost_tracking` precedent); ADR-109 (Alembic is the canonical schema owner)
- **Evidence:** `docs/PHASE_10_30_INDEX_DISCOVERY.md`, `docs/PHASE_10_31_IMPLEMENTATION_MAP.md`, `docs/PHASE_10_31_VERIFICATION_REPORT.md`
- **Change:** 16 ORM model modules under `backend/database/{models,repositories}/`. **No migration. No database change. No Alembic configuration change.**

> **Numbering.** Highest used is 119; this is 120. Nothing overwritten.

## Context

After Phases 10.16–10.29 every table-level drift between ORM metadata and the
migration lineage had been resolved and `alembic check` still reported 86
operations, all index-only, across 27 tables. Phase 10.22 had stopped on them:
the repository had no index naming convention, and the brief forbade inventing
one. This phase rediscovered the 86 from the real database as structured
comparison objects, traced each in both directions, classified each, and
established ownership from evidence before touching anything.

## What discovery established

**The database is exactly the migrations.** A fresh `alembic upgrade head`
database and the existing head database carry identical index inventories on
all 27 tables (212 indexes in `public`). There is no historical artefact.

**The 86 are the ORM disagreeing with that reality, in four shapes.**

- 62 `add_index` are `index=True` column markers, auto-named `ix_<table>_<col>`,
  never declared in any migration and never present on any database: 31 of them
  describe an index the migrations created under a hand-written `idx_*` name
  (11 of those UNIQUE on both sides), 31 describe an index that has never
  existed anywhere.
- 21 `remove_index` are migration-built indexes the ORM did not declare: 15
  are the partners of the pairs above; 5 are the ivfflat and GIN indexes from
  `0001`, which the model files said in comments were created via Alembic and
  "not expressible in DDL here"; 1 (`connector_configs.idx_connector_status`,
  0008) the model simply never mentioned.
- 3 constraint operations: a UNIQUE *index* the ORM expressed as a
  *constraint* (`billing_invoices.invoice_number`); a table where `0001` created
  both a UNIQUE constraint and a UNIQUE index and Alembic's de-duplication left
  the constraint unmatched (`embedding_cache.text_hash`); and one uniqueness
  claim that exists only in the ORM (`missions_bc.execution_id`).

**No naming convention exists.** No `MetaData(naming_convention=…)`, nothing in
`script.py.mako`, no ADR; models and migrations both mix `idx_*` and `ix_*`.

**Every specialized index has a real consumer** (`<=>` in the episodic,
semantic and reflection repositories; `to_tsvector … @@ plainto_tsquery` in the
episodic repository) and exactly one owner (`0001`).

## Decision

1. **The migration lineage owns every index.** This is ADR-109 applied to
   indexes: what `alembic upgrade head` builds is the schema. The database
   agrees with it on every instance; only the ORM did not.
2. **ORM metadata mirrors the owner, by the migrated names.** The ADR-114
   pattern becomes the rule: a migrated index is declared explicitly under the
   name the migration gave it; an `index=True` marker that no migration ever
   realized is removed, and nothing is created because a model wished it.
   Where the ORM already declared the migrated name, the redundant marker is
   simply removed. No index is renamed; the mixed `idx_*`/`ix_*` history is
   preserved as-is.
3. **No naming convention is adopted.** The names are the migrations' names,
   table by table. Future migrations remain free to name indexes; the ORM
   follows.
4. **PostgreSQL-specific indexes are migration-owned and mirrored exactly in
   the ORM.** ivfflat indexes as column indexes with
   `postgresql_using="ivfflat"`, `postgresql_ops={"embedding": "vector_cosine_ops"}`
   and `postgresql_with={"lists": N}`; GIN expression indexes with the
   expression text SQLAlchemy reflects. Alembic 1.14 compares these equal
   (verified empirically before and after). This is the only permitted way to
   "protect the expression indexes" (ADR-114's stated next step), because
   suppression is forbidden. The model comments claiming inexpressibility were
   wrong and are corrected.
5. **Uniqueness is mirrored structure-for-structure.** UNIQUE indexes are
   declared as unique `Index()`s (not constraints); the `embedding_cache`
   constraint is declared by its migrated name alongside the unique index;
   nothing is created or dropped. `missions_bc.execution_id` follows its owner
   (0007: not unique) — no repository queries that column, no row exists on
   any database, and the table is inventoried `REPLACE`; the ORM claim is
   removed and no database uniqueness is touched.

## Rejected alternatives

- **Generate the 86 as a migration.** It would rename 31 indexes for
  aesthetics, create 31 indexes nobody proved canonical, drop the vector and
  full-text indexes, and drop a unique constraint — autogenerate output taken
  as authority, which ADR-109/ADR-116 forbid.
- **Invent a naming convention and rename to it.** Forbidden by the brief and
  unnecessary: the drift was never about names in the database, only about the
  ORM not saying them.
- **`include_object` / comparison suppression.** Hides drift instead of ending
  it; forbidden.
- **Leave the specialized indexes undeclared.** Keeps `alembic check`
  permanently red with five `drop_index` proposals — a standing hazard that a
  future autogenerate apply would destroy vector retrieval.
- **Migrate a unique constraint for `missions_bc.execution_id`.** Speculative:
  the owner never declared it and nothing depends on it.

## Consequences

- `alembic check` returns **"No new upgrade operations detected."** on a fresh
  database and on the existing head database — the first time since the GA
  commit — and it is clean because every declaration mirrors a migration, not
  because anything was hidden (98 ORM indexes compile to their
  `pg_get_indexdef`).
- `create_all` (development) and `alembic upgrade head` (production) now
  produce the same 56 application tables and the same 211 application indexes
  by name and definition. Drift on any of the 27 tables is detectable from
  here on.
- No database changed: fresh and head schema fingerprints identical before and
  after; no rows touched; query plans unchanged by construction.

## Verification

Recorded in the verification report: fresh DB (25 migrations, 57 tables, 212
indexes, fingerprint identical to pre-edit), existing head DB (0 migrations,
three fingerprints identical), `create_all` vs migrations index-by-index,
`alembic check` clean on both databases, per-index DDL proof, executed pgvector
and FTS repository paths with the GIN index in the plan, architecture gate,
targeted tests, regression at the 10.22 scope, harnesses 10.7–10.14,
readiness, provider writes 0.

## Limitations and deferred

- `knowledge_entries.embedding` has no vector index on either side (sequential
  `cosine_distance`); not drift, not added.
- The five governed `cw_*` unique constraints are named `uq_cw_*` by the
  migrations and `<table>_<col>_key` by `create_all`; Alembic matches them by
  columns and is silent. Governed tables are outside this phase; recorded.
- `embedding_cache.text_hash` is doubly enforced (constraint + unique index)
  since `0001`; mirrored, not simplified.

## Follow-up

None required for schema integrity. If a future model needs an index, it is
declared explicitly with the name the accompanying migration creates.
