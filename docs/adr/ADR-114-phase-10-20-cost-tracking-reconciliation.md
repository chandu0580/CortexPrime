# ADR-114 — `cost_tracking`: the migration was right, the model was wrong, and every write was lost

- **Status:** ACCEPTED
- **Date:** 2026-09-08
- **Phase:** 10.20
- **Parent:** `3069a60` — Phase 10.19 (ADR-113)
- **Evidence:** `docs/PHASE_10_20_VERIFICATION_REPORT.md`,
  `docs/PHASE_10_20_IMPLEMENTATION_MAP.md`
- **Change:** `backend/database/models/cost_tracking.py` corrected;
  `backend/database/models/__init__.py` registers it;
  `tests/database/test_cost_tracking_write_path.py` added. **No migration.**

> **Numbering.** Next available is **114**. 107 is used twice; 108–113 once
> each. Nothing existing was overwritten.

## Context

ADR-112 found that `cost_tracking` — migrations `0004`–`0006`, live consumer
`cost_engine` — had an ORM model that was not registered and did not match its
table, and that the only writer, `cost_engine.record()`, failed on every
migrated database with `UndefinedColumn "extra_data"`, caught the exception,
logged a warning, and returned `None`. This phase was scoped to that table
alone: establish the authoritative contract, repair only what the evidence
requires.

## What discovery established

**The migration lineage is the contract, and it says `extra`.** `0004` created
`extra JSON`. `0005` and `0006` then changed the table *to match the model's
mixins* — their docstrings say so — and left `extra` alone both times. The
lineage had two deliberate opportunities to adopt the model's `extra_data` and
declined.

**`extra` and `extra_data` are one concept.** The model's own attribute is
`extra`; only its column-name override says `extra_data`. `record()`'s public
parameter is `extra`, and what callers pass is free-form per-call metadata —
an objective snippet, a confidence, a mission category. No reader projects the
column, no route returns it, no repository names it. And **no database on the
instance has ever had an `extra_data` column**; every one that has the table
has `extra`, and every one holds **0 rows**. The model and `0004` were born
disagreeing in the same GA commit, so the write has never once succeeded on a
migrated database. There was never any data to preserve.

**The defect, reproduced with nothing mocked** — the real `record()`, the real
`AsyncSessionLocal`, a database built only by `alembic upgrade head`:
`INSERT ... (... extra_data ...)`, `UndefinedColumnError`, `ROLLBACK`, caller
receives `None`, rows persisted 0.

**The error semantics are deliberate — and a data-integrity defect.** Every
method in `cost_engine` swallows exceptions and returns a fallback, and every
caller uses `asyncio.ensure_future`. Metering must not take the mission runtime
down; that is a coherent design. But it converts a persistence failure into
apparent success, and no caller can tell the difference. That is the defect
class the brief named, and it is now classified as such.

## Decision

**A — model correction.** The model is aligned to `0004`–`0006`: column
`extra`, type `JSON`, `String(255)` for `mission_id` and `user_id`, the four
`ix_cost_tracking_*` indexes declared by their migrated names, the six
unmigrated `index=True` markers removed. The mixins are kept, because `0005`
and `0006` were written to match them.

**Registered**, because it is a live persisted concept with a real writer.
Unregistered, autogenerate proposes `drop_table('cost_tracking')` — a data-loss
trap one careless apply away — `init_db()` never creates it, and drift on it can
never be detected. Every other live model is registered. The autogenerate diff
going quiet is the consequence of registration, not the reason for it.

**No migration**, because nothing in the evidence requires a database change.
The schema was right all along.

**Error semantics unchanged.** Changing them would be a behaviour change the
evidence does not ask for. Instead the cause is removed and a test now asserts
persistence directly and pins the semantics as they are, so silent loss cannot
recur undetected.

### Rejected

B — correcting the migration — would rename a column that no code or data
needs renamed, under a lineage that already chose not to, twice. C — a
reconciliation migration — has nothing to reconcile: zero rows. D — a
conceptual split — fails on the evidence: one concept, four ways. E — stop —
is unwarranted: the contract is established.

## Consequences

**Cost records persist.** The same real write path, after the correction:
`INSERT ... (... extra ...)`, `COMMIT`, one row, the payload round-tripping
through `extra` by plain SQL.

**The write path has a test that cannot pass vacuously.** It builds a fresh
database with Alembic, binds the real sessionmaker to it, drives the unmodified
`record()`, and reads back through an independent connection. 4/4 pass. With
the correction stashed, **3/4 fail** — the canary on `assert 0 == 0 + 1` — and
the one that passes is the failure-semantics test, which is correct: the
swallowing is the same either way.

**Alembic:** 134 → 129 operations. Exactly `cost_tracking`'s five
(`drop_table` + four `drop_index`) disappeared; the remaining 129 are
byte-identical to before. Global `alembic check` is still red on ADR-112's
other drift, and that was neither required nor claimed. Metadata closure holds
at 40 tables, 0 unresolved targets.

**Governance impact: none.** Provider writes: 0. The diff is two model files
and one test. Phase 10.19's readiness check re-run: `ready: true`.

**Prior phases intact:** 10.7 **155/155** · 10.8 **118/118** · 10.9 **107/107** · 10.10 **107/107** · 10.11 **68/68** · 10.13 **60/60** · 10.14 **53/53** — all VERIFIED, all `rc=0` (no shutdown hang this chain); 10.16 metadata probe holds; 10.19 readiness `ready: true`. Architecture gate **155 passed**; backend regression 75 failed / **6779 passed** / 24 errors — the Phase 10.18 baseline plus exactly the four new write-path tests, every other count byte-identical.

**What is now on the record and not repaired:** the swallowed-failure semantics
themselves, and the three `cost_intelligence.py` models that declare a *second*
"cost record" concept nothing writes and no migration creates — ADR-112's
retirement phase.

## Two things worth remembering

**A schema aligned to a model in two migrations, and a model that still did
not match it.** `0005` and `0006` each say "to match the mixin" — and neither
author noticed the column name one line above. The lineage was the truth
because it was what every database actually had; the model was the claim.

**Three of my own test bugs, each of which made the test *less* like
production, and each fix moved it closer:** a compiled-string type comparison
that would have failed on the migration's own `sa.Float()`; a module import
shadowed by the package `__init__`, a trap `conftest.py` already documents; and
three event loops sharing one pooled connection where production uses one.

## Next

Not started. ADR-112's dependency order continues: retire the ten dead models
(fleet ×4, workflow-designer ×3, cost-intelligence ×3) after confirming the
in-memory managers are the intended persistence; then decide the index
convention once and protect the expression indexes. After those,
`alembic check` is a working drift detector.
