# ADR-116 — The repository can import, migrate and boot from a clean clone again; the index drift is an undecided convention, not a migration

- **Status:** ACCEPTED (Workstream A) · **STOPPED — architectural decision
  required** (Workstream B)
- **Date:** 2026-09-08
- **Phase:** 10.22 — GA Integrity + ORM/Alembic Drift Reconciliation
- **Parent:** `4db52fb` — Phase 10.21 (ADR-115)
- **Evidence:** `docs/PHASE_10_22_VERIFICATION_REPORT.md`,
  `docs/PHASE_10_22_IMPLEMENTATION_MAP.md`
- **Change:** `backend/database/models/__init__.py` and
  `backend/governance/__init__.py` no longer import gitignored v2.0 files.
  **No migration. No v2.0 file touched. No convention invented.**

> **Numbering.** Highest used is 115; this is 116. Nothing existing was
> overwritten.

## Context

ADR-115 found that the GA-preparation commit `9d15d77` gitignored the v2.0
persistence layer (fleet, workflow designer, cost intelligence) but left the
tracked model registry — and `backend/governance/__init__.py` — importing it.
A clean clone could not import its own models, run its own migrations
(`env.py` imports the registry) or boot; every gate since Phase 10.14 had run
from a working tree carrying the ignored files. Behind that, ADR-112's last
drift class remained: 86 autogenerate operations across 27 tables.

This phase was asked to remove *only* the tracked coupling, prove the result
from a clean checkout, persist the exact operation inventory, then classify —
not fix — the remainder, with a standing order that index-only drift with no
established convention is a **STOP**, and that Alembic's output is evidence,
not authority.

## Decision — Workstream A

**Deregister the ten v2.0 models and the `PolicyEngine` re-export from the
tracked package `__init__` files. Nothing else.**

The `governance/__init__.py` import was proven accidental by execution, not
inspection: nothing tracked references `PolicyEngine`; `.gitignore:114` puts
`policy_engine.py` outside the GA; the mission and execution services failed
to import on a clean checkout *because of it*; and the governed authority path
(`backend/auth`, `contexts/connectivity`) never imports `backend.governance`.

**Verified from a git worktree with the ignored files absent:** all importers
load; `alembic upgrade head` on an empty database runs 24 migrations to 56
tables, none of them a v2.0 table, identical to the existing head database's
table set; the existing database is byte-identical before and after (0
migrations, same fingerprint, rows preserved); the application imports, runs
its lifespan and answers `GET /health` 200 with the v2 in-memory fleet and
workflow routes still mounted. Autogenerate fell **129 → 86**, and the claim is
on the inventory: the 43 lines removed are exactly the ten candidates' own
`create_table` / `create_index` lines; the 86 that remain are byte-identical to
the baseline's other lines and name no candidate.

**The tenancy ratchet was not edited.** On the clean worktree
`stale_grandfather_entries` returns `('CostRepository', 'FleetRepository')`
and the gate is 154/155. The brief allows removing entries only when they
refer to *repository code deleted in this phase*, and forbids editing
exemptions to make the test pass. No repository code was deleted: those two
files have been gitignored since `9d15d77`, and the entries were already stale
on every clean checkout — the same masking that hid the registry coupling.
The condition is not met; the two-line removal is recorded as a follow-up for
explicit authorisation. (`WorkflowRepository` is not stale only because a
governed class of the same name in `contexts/workflow` now satisfies an
exemption written for the ignored `workflow_designer` file. Executed: that
class's four methods all take `context`, so the collision hides no violation
today. Recorded, not acted on — tenant scoping is outside this phase.)

## Decision — Workstream B: `STOP_ARCHITECTURAL_DECISION`

**All 86 remaining operations are index-only.** Not one is a table, column or
foreign-key change. By mechanism (27 tables; a table may show more than one):

| Mechanism | Tables | What it is |
|---|---|---|
| RENAME | 17 | migration made `idx_<abbrev>`; ORM `index=True` auto-names `ix_<table>_<col>` — equivalent indexes, different names |
| INDEX_TRUE_NEVER_MIGRATED | 17 | ORM markers no migration ever created |
| UNIQUE_DECLARED_ONLY_IN_ORM | 12 | ORM `unique=True` vs a plain or unique *index* in the migration |
| EXPRESSION_INDEX_MIGRATION_ONLY | 3 | GIN / ivfflat indexes (`0007`) the ORM cannot declare — **autogenerate would drop them** |
| DB_ONLY_PLAIN | 2 | migration indexes with no ORM counterpart |

**There is no established convention.** Of the thirteen migrations that create
indexes, five use `idx_*` (90 indexes) and eight use `ix_*` (23); `0002` mixes
both in one file. The tracked ORM declares 47 `Index("idx_…")`, 4
`Index("ix_…")` and 32 bare `index=True`. No ADR or document states a rule;
ADR-112 and the 10.17 discovery only report the mixture. Every mechanism above
reduces to one undecided question — *which side names an index, and are ORM
`index=True` markers a promise the migrations must keep?* — so, per the
brief's rule, the phase **stops here and invents nothing.** No migration was
generated; none of the `RETIRE_*`, `RECONCILE` or `ADD_MIGRATION` dispositions
applies (every table is live, mapped, migrated and column-consistent, and
"ADD_MIGRATION because autogenerate said so" is the thing the brief forbids).

**One finding stands on its own evidence regardless of the convention:** the
five expression indexes on `episodic_memory`, `reflection_history` and
`semantic_memory` are canonical on the migration side, and Alembic's five
`drop_index` proposals for them are wrong. They are protected today only by
nobody applying an autogenerated migration.

## The decision the user must make

Exactly one of, stated once and then applied uniformly:

1. **Migrations name indexes; the ORM follows.** Give the ORM the migration
   names (as Phase 10.20 did for `cost_tracking`), decide per table whether
   each never-migrated `index=True` is a wanted index (one migration) or a
   stray marker (remove it), declare the expression indexes in the ORM with
   `postgresql_using`/`postgresql_with` so autogenerate stops proposing to drop
   them, and decide unique-constraint-vs-unique-index once.
2. **The ORM names indexes; the lineage follows.** One rename migration for the
   17 RENAME tables, create the never-migrated ones, plus the same expression
   and unique decisions.
3. **Exclude indexes from drift detection** (`include_object` in `env.py`) —
   explicitly rejected as a candidate by this phase's brief ("do not make
   Alembic green by suppression") unless the user ratifies it as policy.

Until then `alembic check` is red by 86 operations — executed from the clean
worktree against a pure migration-built database: 62 `add_index`, 21
`remove_index`, 2 `add_constraint`, 1 `remove_constraint` — all of them known,
none of them a schema disagreement. **Alembic is not clean, and this ADR does
not say it is.**

## A second finding, which Alembic cannot see

The boot probe ran in development mode, so `init_db()`'s `create_all` — the
path production refuses — added seven tables to the fresh database that **no
migration creates and no migration-built database has**: `organizations`,
`departments`, `projects`, `backup_records`, `health_status_snapshots`,
`maintenance_events`, `operational_reports`. Their models are tracked, have
tracked routes, repositories and services, and are **not imported by the
model registry** — so `alembic env.py` never sees them, autogenerate can never
propose them, and `alembic check` is silent about their absence. The existing
head database does not contain them. In production the organization,
department and project routes and the backup, health-center, maintenance and
operational-reports services address tables that do not exist (inferred from
the mechanism; not executed in this phase).

This is ADR-113's `cp_approval` and ADR-114's `cost_tracking` defect, seven
more times, and it was invisible to every drift measurement so far because
those measured what the registry declares. It is **not** the index question
and is not stopped by it; it is deferred because it needs per-table discovery
(consumers, contract, `ADD_MIGRATION` vs `RETIRE_MODEL`) that this phase's
brief did not scope. Registering the seven would make autogenerate propose
seven `create_table`s — and the brief is explicit that a migration is not
created because autogenerate proposes it.

## Consequences

- **A clean clone imports, migrates and boots.** This has not been true since
  `9d15d77`. CI, fresh checkouts and deployment builds from the repository
  were failing at the models import; that is now fixed at its source.
- **Shipped behaviour unchanged.** The v2 routes serve the same in-memory
  managers; nothing imported the ten names; `PolicyEngine` had no tracked
  consumer.
- **The clean-checkout architecture gate is 154/155**, the one failure being
  the stale-ratchet test whose fix is authorised-but-not-taken by the brief's
  own condition. Reported as such.
- **Two gitignored v2.0 subsystems remain exactly where ADR-115 left them**:
  unreleased, deliberately held out, and now no longer blocking anything.
- **Gates:** architecture 155 (this tree) / 154+1 (clean checkout, §5 of the report); regression 76F/6778P/36S/58X/24E vs 75/6779/36/58/24 — one non-reproducible failure under external CPU load in a test that imports neither edited package (3/3, 63/63, 238/238 solo); harnesses 10.7 155/155 · 10.8 118/118 · 10.9 107/107 · 10.10 107/107 · 10.11 68/68 checks `[OK]` (verdict block not emitted — shutdown hang, see §4.8) · 10.13 60/60 · 10.14 53/53, three of them on solo re-run after the documented TestClient portal death; 10.16 / 10.19 / 10.20 probes hold. Provider writes: 0 beyond 10.7's one commissioned restart.

## Next

Not started. Two independent threads, in either order:

1. **The seven invisible models** — a discovery phase in the ADR-113/114
   mould, per table: who reads and writes it, what the contract is, whether
   the answer is a migration or a retirement. This is a GA-integrity defect
   (production routes over absent tables), so it outranks the index question.
2. **The index convention** — the user decides (above); one phase applies it,
   including the expression-index protection; *then* `alembic check` can be a
   working drift detector, which was ADR-112's stated end state.

Separately: authorise removing the two stale ratchet entries, and consider
renaming the governed `contexts/workflow` repository class or the exemption so
a v2.0 file's name no longer covers it.
