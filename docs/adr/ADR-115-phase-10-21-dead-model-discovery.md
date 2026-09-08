# ADR-115 — The ten "dead" models are not in the repository, and the registry that imports them is

- **Status:** PROPOSED — discovery only. No file deleted, no import altered, no
  migration, no schema change.
- **Date:** 2026-09-08
- **Phase:** 10.21
- **Parent:** `978a32c` — Phase 10.20 (ADR-114)
- **Evidence:** `docs/PHASE_10_21_DISCOVERY.md`

> **Numbering.** Next unused is **115**. 107 is used twice; 108–114 once each.
> Nothing existing was overwritten.

## Context

ADR-112 classified ten ORM models — fleet ×4, workflow-designer ×3,
cost-intelligence ×3 — as dead: real SQLAlchemy repositories constructed
nowhere, routes served from in-memory managers, no migration, no table, no
test. This phase was asked to prove that per model, both directions, with
runtime probes rather than grep, and to treat `CostRecordModel → cost_records`
and the in-memory managers as special cases.

## What discovery found

**The ten models are not in the repository.** `.gitignore:109-123`, under the
heading *"v2.0 Phase 1 components — not part of v1.0.0 GA"*, excludes all three
model files, all three SQL repositories, and the entire
`backend/cost_intelligence/` package. The rules were added by the
GA-preparation commit `9d15d77`.

**The same commit made the tracked registry import them.**
`git show 9d15d77:backend/database/models/__init__.py` already contained
`from backend.database.models.fleet import …`, `…workflow import …`, and
`…cost_intelligence import …`. The ignore rules and the imports that break
under them were authored together.

**Proven on a clean checkout of `HEAD`**, in a git worktree that was removed
afterwards: the six ignored files are absent, and `import
backend.database.models`, `alembic current` (because `env.py:32` imports the
models package), and the boot dependency chain all fail with
`ModuleNotFoundError: No module named 'backend.database.models.cost_intelligence'`.

**The repository as committed cannot import its own models, run its own
migrations, or boot from a fresh clone.** Every verification in Phases
10.14–10.20 ran from a working tree that carries the ignored files, which is
why the platform's own gates never saw it. CI checks out with plain
`actions/checkout@v4`; twenty tracked test modules and three architecture
tests import the models package. Their failure on a clean checkout follows by
construction, though no CI run was observed from here.

A second tracked file has the same defect: `backend/governance/__init__.py:1`
imports the ignored `governance/policy_engine.py`. Its reach is
`backend.agent_sdk` only, not the boot path.

**Persistence intent is established, not inferred.** The V2 strategic design
document assigns PostgreSQL to all three components — Fleet Manager
(PostgreSQL + Redis), NL Workflow Designer (PostgreSQL), Cost Intelligence
(PostgreSQL timeseries) — and schedules them as v2.0 Phase 1 and Phase 2. The
shipped code is in-memory: dict and list attributes on module singletons, no
session, no repository, no TODO. Driven over HTTP with `require_user`
overridden, the shipped `/api/v2/fleets` and `/api/v2/workflows` routers create
and list from those dicts, a fresh manager instance sees nothing, and neither
routes nor managers reference SQLAlchemy at all. **These models are the planned
v2.0 persistence layer, deliberately held out of the v1.0 repository, with the
in-memory managers as the shipped placeholder.** Neither dead nor
intentionally in-memory as an end state: deferred and unreleased.

**Every other question the brief asked has a clean answer.** No migration
creates any of the ten tables; none exists in a fresh or an existing head
database; the five foreign keys are all internal to the group; no tracked file
imports any of the ten names except the registry; no test, frontend, bundle,
script, DI registration, scheduler or worker references them; the three SQL
repositories, constructed for real against a migration-built database, fail
with `UndefinedTableError`; and `cost_records` is a different concept from the
live `cost_tracking` — org-scoped, category-typed, `Numeric` cost, sharing only
`id`, `mission_id`, `model` and `provider`. Alembic's baseline of 129
operations was re-confirmed byte-identical; removing the ten would remove
exactly 43 — their own `create_table` and `create_index` lines — and touch no
other.

## Decision

**Disposition for all ten: DEREGISTER** — remove the three import statements
and the ten `__all__` entries from the tracked
`backend/database/models/__init__.py`, and touch the ignored files not at all.

"Retire the model" would misdescribe it: the files are already outside the
repository by a deliberate release decision, and there is nothing to retire
*from* it. The defect is a shipped registry that imports unshipped files.
Deregistration makes the repository self-consistent, restores clean-clone
import, migration and boot, removes exactly 43 Alembic operations, and changes
no shipped behaviour, because nothing imports the names.

**It does not decide the v2.0 question.** Whether to un-ignore and ship the
persistence layer — which needs migrations for ten tables — belongs to the
v2.0 Phase 1/2 work the design document already schedules. Deregistering now
does not foreclose it; the ignored files are unaffected. `CostRecordModel` in
particular is not deleted: it is an unreleased design, distinct from
`cost_tracking`, and the brief's concern that deleting it could erase an
intended future contract is answered by not deleting it.

**No stop condition fired.** No live consumer, no public-API dependency, no
durable data, no unclassified FK, a clear distinction between the two cost
concepts, established intent, no schema decision required for deregistration,
no dynamic use, no unrelated Alembic change, no provider write, no vacuous
check. The clean-clone breakage is outside the listed conditions and is
reported as the primary finding rather than folded into one.

## Consequences

**Nothing changed.** Two documents. A disposable database and a clean worktree
were created for evidence and removed.

**The priority order changes.** ADR-112 scheduled this as "retire the dead
models after confirming in-memory persistence is intended." It is now: **make
the shipped repository importable from a clean clone**, which happens to be the
same three-line edit, and which has been blocking every fresh checkout, CI run
and deployment build from the repository since the GA-preparation commit.

**Two things this discovery corrects in earlier phases.** ADR-112 called these
models "dead"; they are unreleased. And every phase since 10.14 reported
"architecture gate passed" and "regression passed" from a working tree the
repository cannot reproduce. Those results were real for this tree and are not
withdrawn; the claim they cannot support — that a clean clone passes them — was
never made, and now cannot be assumed.

## Next

Not started. Deregister the ten from the tracked registry; decide
`governance/__init__.py`'s ignored import alongside it; then prove on a clean
checkout that import, `alembic upgrade head` and boot succeed and that
autogenerate falls from 129 to 86. The 27-table index drift remains after that,
and is the last item in ADR-112's order.
