# ADR-111 — The `missions` ORM mapping, and the drift it made visible

- **Status:** ACCEPTED for the mapping; **STOPPED** at stop condition 3 for the
  phase's `alembic check` criterion.
- **Date:** 2026-09-07
- **Phase:** 10.16 (resumed)
- **Parents:** `df4f046` (10.15 discovery) → `183a34c` (10.17) → `1e0f29a` (10.18)
- **Evidence:** `docs/PHASE_10_16_VERIFICATION_REPORT.md`,
  `docs/PHASE_10_16_IMPLEMENTATION_MAP.md`
- **Supersedes:** ADR-108, which recorded this phase's first attempt stopping

> **Numbering.** Next available is **111**. ADR-107 is used twice (Phases 10.14
> and 10.15); 108 is this phase's first attempt; 109 is 10.17; 110 is 10.18.
> Nothing existing was overwritten.

## Context

`reflection_history.mission_id` and `runtime_analytics.mission_id` have always
carried foreign keys to `missions.id`, and no SQLAlchemy model has ever mapped
`missions`. `Base.metadata` was therefore not closed under its own foreign keys,
`sorted_tables` raised, and `create_all`, `alembic check` and
`alembic revision --autogenerate` were all broken.

The first attempt at this phase stopped: migration `0001` and
`infra/postgres/init.sql` defined *different* `missions` tables and `init.sql`
was still mounted, so no model could be correct for both (ADR-108). Phase 10.18
removed that competing authority (ADR-110). This phase then implemented the
model.

## Decision

**Add one ORM model — `MissionRecord`, `__tablename__ = "missions"` — copied
from migration `0001` column for column, and register it through the existing
eager-import mechanism.** Nothing else: no migration, no repository, no route,
no authority, no schema change.

Two choices are worth recording because both were tempting to get wrong:

**No mixins.** Every sibling model uses `UUIDPrimaryKeyMixin` and
`TimestampMixin`, and using them here would have looked idiomatic. Both add
Python-side semantics `0001` does not specify — `default=uuid.uuid4` and
`onupdate=_utcnow`. A mixin here would be a reinterpretation of the source of
truth, so the columns are declared explicitly.

**The `metadata` column keeps its name; the attribute cannot have it.** Verified
rather than assumed: SQLAlchemy raises *"Attribute name 'metadata' is reserved
when using the Declarative API"*, while `mapped_column("metadata", ...)` yields a
column genuinely named `metadata`. The model uses `meta` as the attribute, which
is what `reflection_history` already does.

The model was validated against the **real database** before anything was
adjusted to satisfy any tool: every column name, type, nullability, the primary
key, the index (name and columns) and the **named** check constraint match a
database built by `alembic upgrade head`. The foreign-key contract was proven
with real rows — deleting a mission left both children in place with
`mission_id` set to `NULL`, and both constraints still declare `SET NULL`.

## The stop

**`alembic check` does not pass, and the phase stops on that.**

Repairing metadata closure let `alembic check` run for the first time. It
immediately reported a long list of pending operations — and **not one of them
concerns `missions`**. The diff names `cost_*`, `fleets`, `fleet_*`,
`workflows`, `workflow_*`, `cp_approval`, and around twenty removed indexes
across other V1 tables.

That drift is real and pre-existing, proven rather than argued: in a database
migrated to head, `cost_optimization_recommendations`, `fleets` and `workflows`
**do not exist**, and each is referenced by **zero** migration files. They are
declared by ORM models that no migration has ever backed. The divergence has
existed for as long as those models have — it was simply **invisible**, because
`alembic check` died inside `sorted_tables` before it could compare anything.

Autogenerate tells the same story: 268 operations, **zero** naming `missions`.
The disposable revision was deleted and the migrations directory verified
unchanged.

`create_all` shows it a third way. The failure this phase existed to remove is
gone — no `sorted_tables` error, on both a fresh and a migrated database. But on
an already-correct schema it now creates **ten** tables: the same drifted set.
It altered and dropped nothing, and did not touch `missions`.

**Making `alembic check` green would mean writing migrations for ~15 unrelated
tables** — forbidden by this brief's rules and, more importantly, a schema
decision nobody has taken. The brief's own instruction was explicit: *"Do NOT
make `alembic check` green by suppressing the difference"* and *"Do NOT add an
Alembic migration just because the ORM model is new."* So the phase reports and
stops.

**The capability is unblocked but not yet useful.** `alembic check` can now run;
it cannot yet serve as a drift detector until the pre-existing drift is
resolved. That is the honest description, and it is a smaller claim than the
phase set out to make.

## A superseded assertion, inverted rather than deleted

Phase 10.14's harness contained a check asserting that `create_all` **fails**
on `reflection_history -> missions`, *"a table no model declares"* — the defect
that phase found, proved unrelated to IAM, and deliberately left alone.

This phase repaired exactly that, so the check failed. Following the precedent
set when Phase 10.14 invalidated Phase 10.13's section H, it was **inverted, not
deleted**: it now asserts that `create_all` no longer raises
`NoReferencedTableError` and that no failure names `missions`, so it will fail
again if the mapping ever disappears. A neighbouring `deferred()` entry became a
real check that the repair did not resurrect IAM. The harness total rose 52 → 53
— a deferral discharged, not a check removed — and re-ran 53/53.

## Consequences

**Metadata is closed.** 38 → 39 tables, **zero** unresolved foreign-key targets
(asserted as an empty set, not merely as "`missions` is present"),
`sorted_tables` succeeds, and both foreign keys resolve to `missions.id` with
`SET NULL`.

**The database is untouched.** No migration, no schema change, no row change. A
database already at head was fingerprinted before and after: identical md5, zero
migrations run, revision unchanged.

**Nothing depends on the model.** It declares one class and no functions, imports
nothing from `missions_bc`, `contexts.mission`, `backend.mission`, or any
auth/approval/authority/tenant/execution/worker/connector/credential module —
read from the AST, not from prose. `missions` still has no reader or writer;
this phase adds a mapping, not a use.

**Governance is unchanged**: architecture gate 155 passed, and 10.7 155/155,
10.8 118/118, 10.9 107/107, 10.10 107/107, 10.11 68/68, 10.13 60/60, 10.14
53/53. The backend regression is byte-identical to the baseline Phase 10.18
established on a tree without this model.

**One naming hazard, documented not renamed.**
`backend/services/enterprise_executive_runtime.py:90` defines its own unrelated
`MissionRecord` dataclass. It never imports this one, but a text search finds
both — and this family has already been bitten by exactly this with
`MissionRepository`. The collision is recorded in the model's docstring.

## What the verification caught

Two harness results were investigated rather than accepted. 10.13 and 10.14
first produced **no counts at all**, crashing on `.json()` of an empty HTTP
body; both had run in parallel with the full regression suite, and re-running
them alone gave 60/60 and a complete 52-check run. **Contention, proven by
isolation.** A result with no totals is not a pass — the same lesson Phase 10.18
recorded, applied before it could mislead.

## Next

**Resolve the pre-existing ORM-vs-migration drift** — around fifteen tables
whose models no migration backs. That is what stands between this repair and a
working drift detector, and it needs its own discovery: for each table, whether
the model or the migration lineage is right, and whether the tables should exist
at all. It is a schema decision, not a cleanup.
