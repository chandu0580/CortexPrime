# ADR-107 (10.15) — The `missions` mapping gap: discovery and decision to repair

> **Numbering collision, flagged not silently resolved.** The brief specified
> this filename, and `ADR-107-phase-10-14-retire-dead-iam.md` already holds
> number 107. The file is created at the path requested rather than renamed on
> my own initiative. **Recommendation: renumber this to ADR-108** before it is
> cited anywhere, so the index has one 107.

- **Status:** PROPOSED — discovery only. No production code, no migration, no
  schema change, no test modified.
- **Date:** 2026-09-07
- **Phase:** 10.15 (discovery)
- **Evidence:** `docs/PHASE_10_15_DISCOVERY.md`
- **Follows:** ADR-107 (Phase 10.14), which found this defect, proved it
  unrelated to the IAM retirement, and deliberately left it alone.

## Context

Phase 10.14 reported that `init_db()` cannot complete on any database:
`Base.metadata.create_all` raises `NoReferencedTableError` on
`reflection_history.mission_id → missions`. It repaired nothing, because
repairing it meant touching a V1 table mapping that brief did not authorise.

This phase was asked to establish ownership and lifecycle before any repair.

## What discovery found

**The model was never written.** `git log -S'__tablename__ = "missions"'` across
all history returns no commit. `missions` was not removed and not renamed — it
has only ever existed as raw DDL, created by migration `0001` and independently
by `infra/postgres/init.sql`. The absent ORM mapping is the original condition,
not a regression.

**The database is not wrong.** On every migrated database the two foreign keys
exist exactly as the models declare them, `ON DELETE SET NULL`. Migration
lineage and runtime schema agree completely. Nothing is stale; the gap is
entirely ORM-side.

**The brief named one FK; there are two.** `runtime_analytics.mission_id`
carries an identical declaration. A repair addressing only the one in the error
message would fail again on the next table SQLAlchemy sorted.

**Three different things are called "mission", and only one is this table.**
`missions` (V1 DDL, no model, **no production reader or writer at all**);
`missions_bc` (migration `0007`, `MissionModel`, used by
`backend/mission/service.py` which is registered at boot); and the in-memory
mission in `backend/contexts/mission/`, which `mission_runtime_routes.py` uses
and which touches no SQL. **Mission Runtime cannot be affected by any repair
proposed here.**

**The interesting finding is one the phase title does not mention.**
`backend/database/migrations/env.py` sets
`target_metadata = [Base.metadata, DURABLE_METADATA]`, so the same unresolved
reference breaks `alembic check` and `alembic revision --autogenerate`
outright — verified by running it. Every migration `0001` through `0023` was
necessarily hand-written. `alembic upgrade head` is unaffected and always was.

Meanwhile `init_db()` itself matters far less than it appears: it is already
gated by `SchemaBootstrapRefused`, refused unless explicitly permitted in a
declared non-production environment, treats an *unset* environment as
production, is caught and downgraded to a warning at boot, and — by its own
docstring — could never produce a complete schema anyway, since the durable
tables live on a separate metadata. No test calls it; the two tests that call
`create_all` use their own local `Base` on in-memory SQLite.

**So the low-severity half is the half the brief named, and the high-severity
half was found on the way.**

## Decision

**GO**, for candidate A only: **declare a `missions` ORM model that matches
migration `0001` column for column, and register it.**

Nothing else. No migration, no schema change, no data migration, no FK
modification.

This restores the invariant that `Base.metadata` is closed under its own foreign
keys, which is what `sorted_tables` requires — and therefore what `create_all`,
`drop_all`, `alembic check` and `--autogenerate` all require.

### What was rejected, and why

- **Repointing both FKs at `missions_bc`** — it *looks* like the live table, and
  that is exactly the trap. It would change what a `mission_id` means in
  reflection and analytics rows, needs a migration, and may need data handling.
  That is a design decision nobody has asked for, and discovery has not settled
  it.
- **Dropping the two foreign keys** — the shortcut this brief names explicitly.
  `tests/test_reflection_consolidation.py` relies on the constraint and says so
  in its own comment. Removing it to make an error message go away would trade a
  real database guarantee for a green run.
- **Retiring `reflection_history`** — it is live production state with five
  runtime consumers.
- **Retiring `missions`** — defensible on the evidence that nothing reads or
  writes it, but it is candidate C plus more, and it depends on an open question
  (below). Deferred, not dismissed.
- **Repairing import registration** — not applicable. `_ensure_bc_models()` runs
  and imports every registration module; the table is unmapped because no module
  declares it, so no import can fix it.
- **Replacing `create_all` with migration-only initialization** — probably right
  eventually, and already half-done, but it does not fix autogenerate.
  Complementary, not a substitute.

### The constraint the repair must satisfy

The model must be **copied from `0001`, not reinterpreted** — every column,
every server default, the check constraint and the index. An inaccurate model
would make `alembic --autogenerate` propose a spurious migration, which is the
capability this repair exists to restore. Phase 10.14 made precisely this
mistake in a `downgrade()` whose docstring claimed it had copied the original;
that is why verification step 6 compares the model against the **reflected**
columns of a real migrated database rather than against the model file.

## A latent consequence, reported and NOT repaired

Nothing inserts into `missions`, so any non-null `mission_id` written to
`reflection_history` or `runtime_analytics` must violate the foreign key.
`backend/memory/event_subscriber.py` passes an **execution id** as
`mission_id` into `store_reflection`, inside a `try` that swallows everything at
`logger.debug` — so such reflections would be **silently dropped**. The
analytics ingest route takes `mission_id` from the request body, with the same
exposure.

This is marked **[NOT VERIFIED]**: it is read from source and matches the test's
own comment, but no live event was driven through either path. It is recorded
because it is the strongest argument against dropping the FK, and because if it
is real it is a data-loss bug that has nothing to do with metadata. **Proving it
belongs in its own phase**, with its own evidence.

## Consequences

**Governance is untouched.** `DURABLE_METADATA` — the 25 governed tables — is a
separate metadata that already sorts cleanly. Tenant, membership, authority,
approval and execution semantics are not reachable from this change.

**Nothing is created, altered or deleted.** The repair is additive and reversible
by deleting the file. `create_all` uses `checkfirst`, so on a migrated database
it creates nothing.

**Two capabilities come back:** `alembic check` (drift detection) and
`alembic revision --autogenerate`. That is the real return on this phase.

**One question stays open on purpose:** whether `missions` should exist at all,
or whether reflection and analytics should reference `missions_bc`. Discovery
establishes only that the table exists, that two live FKs need it, and that
mapping it is the smallest correct repair. Answering the larger question needs a
consumer to be identified, and there is not one today.

## Verification strategy for the implementation phase

Fresh database migrated to head must produce an identical table set (the repair
adds **zero** tables); `alembic check` must report **no drift** on a database
already at `0023`; a child process must show the unmapped-FK-target set is
**empty**, not merely that `missions` is present; `create_all` must complete on
a fresh database and create nothing on a migrated one; the model must be
compared against the reflected columns of a real database; and both foreign keys
must still exist afterwards with `delete_rule = SET NULL`, proving the repair did
not quietly become the rejected candidate. Regression, architecture and the
10.7–10.14 harnesses re-run.
