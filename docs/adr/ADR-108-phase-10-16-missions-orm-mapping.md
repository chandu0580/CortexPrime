# ADR-108 — The `missions` ORM mapping, and the schema-ownership conflict that blocks it

- **Status:** **STOPPED** — Phase 10.16 halted at implementation rule 5 /
  stop condition 1. No production code, no migration, no schema change.
- **Date:** 2026-09-07
- **Phase:** 10.16
- **Parent:** `df4f046` — Phase 10.15 discovery (STATUS=GO)
- **Evidence:** `docs/PHASE_10_16_VERIFICATION_REPORT.md`,
  `docs/PHASE_10_16_IMPLEMENTATION_MAP.md`

> **Numbering.** Phase 10.15's ADR was created at the filename its brief
> specified, which reused 107. This ADR takes **108** as instructed, and
> `ADR-107-phase-10-14-retire-dead-iam.md` is untouched. The 107 collision
> between Phases 10.14 and 10.15 remains and is a documentation matter, not a
> code one.

## Context

Phase 10.15 proved that no SQLAlchemy model has ever mapped the `missions`
table, that two live ORM tables carry foreign keys to it, and that this single
unresolved reference makes `Base.metadata.sorted_tables` raise — breaking
`create_all` and, more importantly, `alembic check` and
`revision --autogenerate`. It returned GO for one additive model copied from
migration `0001`.

Phase 10.16 was to write that model. Its rule 5 required comparing migration
`0001` against `infra/postgres/init.sql` first, and stopping if they disagreed.

## The finding

**They disagree, in six ways, and three of them are material:**

| | migration `0001` | `init.sql` |
|---|---|---|
| `id` default | `gen_random_uuid()` | `uuid_generate_v4()` |
| `status` | `VARCHAR(32)` | `TEXT` |
| `created_at` | **NOT NULL** | **NULL** |
| `updated_at` | **NOT NULL** | **NULL** |
| check constraint | `ck_missions_status` | `missions_status_check` |
| index | `(status, created_at)` | `(status, created_at DESC)` |

A reflection of two real databases at head shows the schema matches **`0001` on
every one of the six**. On that evidence alone the repair would be
unambiguous — copy `0001` — and the phase could have continued.

**It did not, because `init.sql` is not a dead file.** It is mounted into
`/docker-entrypoint-initdb.d` by **both `docker-compose.yml` and
`docker-compose.staging.yml`**, so the official Postgres image executes it on
first initialisation. A developer or staging deployment bringing this project up
with its own compose file gets the `init.sql` shape.

That was proven rather than assumed: a disposable database was created,
`init.sql` run against it, and the result reflected — `status text`, both
timestamps nullable, `missions_status_check`, and a `DESC` index.

**Both shapes are real, and this project produces both.** A model copied from
`0001` would be correct on a migrated database and **wrong on a
compose-bootstrapped one**, where `alembic check` — the very capability this
repair exists to restore — would immediately report drift.

## A second defect, found while establishing the first

`0001.upgrade()` creates `missions` unconditionally, with no `IF NOT EXISTS`
guard, and the migrator has no stamp or baseline logic. Running
`alembic upgrade head` against the `init.sql`-bootstrapped database:

```
asyncpg.exceptions.DuplicateTableError: relation "missions" already exists
```

and no `alembic_version` row is ever written.

**A database created by this project's own `docker-compose` cannot be migrated
at all.** It fails on the first revision and can never join the lineage.

This is outside Phase 10.16's scope and is reported, not repaired. It is what
turns the discrepancy from an inconsistency into a conflict: the two schema
sources are not merely different, they are **mutually exclusive in practice**,
and nobody has decided which one owns the schema.

## Decision

**Stop. Do not write the model. Do not choose a source.**

Rule 5 and stop condition 1 both name this exact situation, and the brief's
instruction on firing a stop condition is *"DO NOT workaround it. Report the
exact evidence."*

The tempting move was available and was declined: the reflected schema matches
`0001`, so writing the `0001` model would have passed every check the brief
lists — sections A through I would have gone green on the migrated databases the
verification is run against. It would also have quietly ratified `0001` as the
schema owner, encoded that choice in an ORM model, and left every
compose-bootstrapped environment with a model that does not describe its
database. **Passing the tests is not the same as being right**, and the stop
condition exists precisely because the author anticipated that the evidence
available inside this phase would look conclusive.

## What was NOT decided

Which artefact owns the `missions` schema. The evidence favours migration
`0001` — it is the only source in the alembic lineage, and it matches every
database that has ever been migrated. But acting on that means `init.sql` is a
divergent bootstrap that also breaks migrations, and the consequence is to stop
mounting it or reduce it to what Alembic does not create. That is a change to
deployment configuration for two compose stacks, which rule 9 does not
authorise and which needs its own evidence and its own decision.

## Consequences

**Nothing changed.** No production code, no migration, no schema, no test. The
working tree contains three new documents and nothing else. The defect Phase
10.15 described is still present, unchanged: `sorted_tables` still raises,
`alembic check` still fails, `init_db()` still cannot complete — all of which
remain non-fatal at boot, exactly as before.

**The repair is fully specified and ready.**
`docs/PHASE_10_16_IMPLEMENTATION_MAP.md` §6 contains the complete model, the
registration mechanism, and two design notes (no mixins — they would
reinterpret the columns; `metadata` mapped as `meta`). Once ownership is
settled, the implementation is one new file and one import.

**Governance is untouched** and was never at risk: `DURABLE_METADATA` is a
separate metadata that already sorts cleanly at 25 tables.

## Next

A phase to settle schema ownership: decide whether `infra/postgres/init.sql`
should continue to bootstrap tables that Alembic also creates, given that doing
so makes the resulting database unmigratable. Phase 10.16 resumes unchanged
afterwards.
