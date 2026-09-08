# ADR-112 — ORM/Alembic drift: what the newly-working `alembic check` actually found

- **Status:** PROPOSED — discovery only. No code, no migration, no model, no
  configuration change.
- **Date:** 2026-09-08
- **Phase:** 10.17 (second use of the number — the first is ADR-109)
- **Parent:** `c95d370` — Phase 10.16 (ADR-111), which closed the metadata
  graph and let `alembic check` run for the first time
- **Evidence:** `docs/PHASE_10_17_DISCOVERY.md`

> **Numbering.** Next available is **112**. 107 is used twice; 108–111 once
> each. Nothing existing was overwritten. The brief's phase number collides
> with an existing phase; the document path does not.

## Context

Phase 10.16 added the `missions` ORM mapping, which made `Base.metadata`
sortable and let `alembic check` and `autogenerate` run for the first time in
this repository's history. They immediately reported drift, none of it about
`missions`, and Phase 10.16 stopped rather than make it green. This phase was
called to classify every discrepancy with evidence and choose a disposition
for each, without repairing anything.

## What was found

**39 tables, 135 upgrade operations, deterministic across two runs.** They
fall into three classes, and the interesting findings are in the first two.

**Class A — eleven tables the ORM declares that no migration has ever created.**
Ten are dead: the fleet (4), workflow-designer (3) and cost-intelligence (3)
models each have a real SQLAlchemy repository that is **constructed nowhere**;
the registered routes use in-memory dicts; the cost-intelligence router is not
registered at all; no test references any of them. The eleventh is
**`cp_approval`** — the governed approval store from Phase 10.3, defined on
`DURABLE_METADATA`, consumed by the production `SqlApprovalRepository` and the
product approval queue. **Its 24 sibling durable tables each have a migration
(`0010`–`0022`). It alone has none.**

That was proven, not inferred. The production readiness check, run against a
database built only by `alembic upgrade head`:

```
ready: false   schema_present: false   missing_tables: ["cp_approval"]
```

The production persistence builder refuses to create schema, by design (ADR-110
made that refusal the point). So **a production deployment migrated to head
cannot become ready for governed execution.** Every phase harness since 10.3
built its database with the development builder, which runs `create_all` —
which is why the platform's own fail-closed readiness check was never seen to
fail. The platform is right. The schema is not under migration control.

**Class B — one table the migrations own that the ORM does not register:
`cost_tracking`.** A model exists (`CostRecord`, `models/cost_tracking.py`) but
is not imported by `models/__init__.py`, so autogenerate proposes
**`drop_table('cost_tracking')`**. The table is live: `cost_engine` is
registered in the DI container and writes through that model from the mission
runtime, the mission library and five cost routes. And the model is wrong: it
maps its JSON column as `extra_data`, migration `0004` created it as `extra`.
The exact INSERT `cost_engine.record()` issues, run against a head database:

```
UndefinedColumn: column "extra_data" of relation "cost_tracking" does not exist
```

`record()` catches every exception and logs a warning. **Every cost record has
been silently discarded on every migrated database.** Both existing tests mock
the read methods; nothing exercises the write.

**Class C — 27 tables with index-only drift.** Every column agrees; the models'
`index=True` markers were never migrated and auto-name differently
(`ix_<table>_<col>`) from the migrations' hand-named `idx_*`. Three memory
tables carry pgvector and full-text expression indexes the ORM cannot declare,
which autogenerate would **drop**. No data is affected; one convention decision
covers all 27.

## Dispositions

| Disposition | Tables | Basis |
|---|---|---|
| **ADD_MIGRATION** | `cp_approval` | definition on `DURABLE_METADATA`; 24 migrated siblings; live governed consumer; readiness fails without it |
| **RETIRE_MODEL** | fleet ×4, workflow ×3, cost-intelligence ×3 | no constructor, no registered route, no test; routes use in-memory managers |
| **RECONCILE** | `cost_tracking` | Alembic owns the schema; the model must be registered and corrected to `0004`–`0006` |
| **RECONCILE** | 27 index-drift tables | one naming decision; expression indexes must be protected via `include_object` |

KEEP_MODEL 0 · KEEP_MIGRATION 0 · RETIRE_TABLE 0 · STOP_ARCHITECTURAL_DECISION 0.
None was chosen for convenience; each rests on a constructor search, a route
registration, a test search, a reflection, or an executed statement.

## Decision

**STOP.** Six of ten stop conditions fired — 1 (governed table), 3 (conflicting
definitions of a live table), 4 (missing migration, schema relied upon), 5 (two
tables for one concept: `cost_records` vs `cost_tracking`), 6 (autogenerate
would drop a live table and the vector indexes), 9 (the count is 39, not ~15).

Nothing in this discovery authorises implementation. The `cp_approval`
migration in particular touches the governed path and needs explicit sign-off,
even though its content is unambiguous — one `create_table` copied from the
existing `approval_table`, exactly as its siblings were done.

## Consequences

**Nothing changed.** Two disposable autogenerate revisions were generated,
copied to the scratchpad, deleted; the migrations directory was verified clean
after each. One disposable database was created and dropped.

**Two live defects are now on the record.** Production readiness fails on a
migrated database, and cost tracking silently loses every write. Neither is
caused by anything in Phases 10.14–10.16; both were invisible until
`alembic check` could run.

**The brief's premise was materially understated.** It was framed around ~15
V1 tables. The V1 tables are the least of it.

## Next, in dependency order

1. Authorise and add the `cp_approval` migration — governed, highest priority.
2. Reconcile `cost_tracking`: register and correct the model, add a write-path
   test.
3. Retire the ten dead models, after confirming the in-memory managers are the
   intended persistence.
4. Decide the index convention once, protect the expression indexes, apply
   across the 27.

After all four, `alembic check` is a working drift detector. Not before.
