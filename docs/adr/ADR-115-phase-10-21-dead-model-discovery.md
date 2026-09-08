# ADR-115 — The ten "dead" models are not in the repository; the registry that imports them is

- **Status:** PROPOSED — discovery only. No file deleted, no import altered, no
  migration, no schema change, no test changed.
- **Date:** 2026-09-08
- **Phase:** 10.21 — issued twice; this ADR covers both issues and supersedes
  its first text (`65951e5`)
- **Parent:** `978a32c` — Phase 10.20 (ADR-114)
- **Evidence:** `docs/PHASE_10_21_DISCOVERY.md`

> **Numbering.** Highest used is 115 — this ADR, created by this phase's first
> issue. Re-issuing the phase does not earn a second number: the ADR is updated
> in place, and no other phase's ADR is touched. Collisions on record: 107 is
> used by Phases 10.14 and 10.15; phase number 10.17 was used twice (ADR-109,
> ADR-112); phase number 10.21 is now used twice (this ADR, both times).

## Context

ADR-112 classified ten ORM models — fleet ×4, workflow-designer ×3,
cost-intelligence ×3 — as dead: real SQLAlchemy repositories constructed
nowhere, routes served from in-memory managers, no migration, no table, no
test. This phase was asked to prove that per model, in both directions, with
execution where grep is insufficient; to treat `CostRecordModel → cost_records`,
the fleet subsystem and the workflow designer as special cases; and to choose
from a fixed disposition vocabulary without forcing `RETIRE_MODEL`.

## What discovery found

**The ten models are not in the repository.** `.gitignore:109-123`, under
*"v2.0 Phase 1 components — not part of v1.0.0 GA"*, excludes all three model
files, all three SQL repositories, and the entire `backend/cost_intelligence/`
package. The rules were added by the GA-preparation commit `9d15d77`.

**The same commit made the tracked registry import them.**
`git show 9d15d77:backend/database/models/__init__.py` already contained the
three imports. Proven on a clean git worktree of `HEAD`: the six ignored files
are absent, and `import backend.database.models`, `alembic current` (because
`env.py:32` imports the models package) and the boot dependency chain all fail
with `ModuleNotFoundError: backend.database.models.cost_intelligence`.

**The repository as committed cannot import its own models, run its own
migrations, or boot from a fresh clone.** Every verification in Phases
10.14–10.20 ran from a working tree that carries the ignored files, which is
why the platform's own gates never saw it. CI checks out plain; twenty tracked
tests and three architecture tests import the models package, so their
collection fails on a clean checkout by construction — inferred from the
workflow files, not observed. `backend/governance/__init__.py:1` has the same
defect, reaching only `backend.agent_sdk`.

**Persistence intent is established from three independent sources and one
execution.** The V2 strategic design assigns PostgreSQL to all three
components and schedules them as v2.0 Phase 1 and 2. The `.gitignore` excludes
exactly the persistence layer while shipping the in-memory managers. The
managers are dict and list attributes on module singletons — no session, no
repository, no loop, no TODO; `FleetHealthMonitor` computes on demand and is
started by nothing. Driven over HTTP, the shipped `/api/v2/fleets` and
`/api/v2/workflows` routers create and list from those dicts, a fresh manager
instance sees nothing, and neither routes nor managers reference SQLAlchemy.
**These models are the planned v2.0 persistence layer, deliberately held out of
the v1.0 repository, with the in-memory managers as the shipped placeholder** —
neither dead nor intentionally in-memory as an end state; deferred and
unreleased.

**Every other question has a clean, executed answer.** No migration creates any
of the ten tables; none exists in a fresh (24 migrations, 56 tables) or an
existing head database; the five foreign keys are all internal to the group;
no tracked file imports any of the ten names except the registry; no test,
frontend, bundle, script, CLI, DI registration, scheduler, worker, plugin,
`response_model` or OpenAPI export references them; the three SQL
repositories, constructed for real against a migration-built database, fail
with `UndefinedTableError`; the workflow designer's compiler returns a plain
`mission_def` dict to its HTTP caller and hands it to no runtime; the only
variable-target import in the backend (`CORTEX_CONNECTOR_FACTORIES`) is empty
by default and names no candidate, and the architecture boundary rules forbid
dynamic imports in governed code; and `cost_records` is a different concept
from the live `cost_tracking` — org-scoped, category-typed, `Numeric` cost,
sharing only `id`, `mission_id`, `model` and `provider`. `alembic check` reports
all ten as added tables; autogenerate's baseline of 129 operations was
re-confirmed byte-identical; removing the ten would remove exactly 43 — their
own `create_table` and `create_index` lines — and touch no other. No governed
package references a candidate.

## Decision

**Disposition for all ten: `RETIRE_MODEL` — registration only.** What the
repository contains is three import statements and ten `__all__` entries in the
tracked `backend/database/models/__init__.py` that point at gitignored files.
Retiring that registration makes the shipped repository self-consistent,
restores clean-clone import, migration and boot, removes exactly 43 Alembic
operations, and changes no shipped behaviour, because nothing imports the
names. The ignored files are not repository content and are not touched.

This is not a forced classification. Each of the twelve stop conditions was
tested and passed: no live consumer, no public contract, no durable data, no
unresolved foreign key, a clear distinction between the two cost concepts,
established intent, no schema decision needed for deregistration, no dynamic
reachability, an exact and isolated Alembic delta, zero provider writes,
non-vacuous probes, and no governed-infrastructure use.

**It does not decide the v2.0 question.** Whether to un-ignore and ship the
persistence layer — which needs migrations for ten tables — belongs to the
v2.0 Phase 1/2 work the design document already schedules. Deregistering now
does not foreclose it. `CostRecordModel` in particular is not deleted: it is an
unreleased, separately designed concept, and the brief's concern that deleting
it could erase an intended contract is answered by not deleting it.

## Consequences

**Nothing changed.** Two documents. A disposable database and a clean worktree
were created for evidence and removed.

**The priority order changes.** ADR-112 scheduled this as "retire the dead
models after confirming in-memory persistence is intended." It is now: **make
the shipped repository importable from a clean clone** — the same three-line
edit, and one that has been blocking every fresh checkout, CI run and
deployment build from the repository since the GA-preparation commit.

**Two corrections to earlier phases.** ADR-112 called these models "dead"; they
are unreleased. And every phase since 10.14 reported gates passing from a
working tree the repository cannot reproduce. Those results were real for this
tree and are not withdrawn; the claim they cannot support — that a clean clone
passes them — was never made, and now cannot be assumed.

## Follow-up findings, not changed

The registry's imports of gitignored files; `governance/__init__.py`'s ignored
import; three tenancy-ratchet exemptions naming repositories that are not in
the repository; a gitignored `workflow_designer/templates.py`; CI status
unobserved; four classes sharing the name `CostRecord`/`CostRecordModel`.

## Next

Not started. Deregister the ten from the tracked registry; decide
`governance/__init__.py`'s ignored import alongside; remove the three stale
ratchet entries only if the ratchet test demands it; then **prove on a clean
checkout** that import, `alembic upgrade head` and boot succeed and that
autogenerate falls from 129 to 86 with the other 86 byte-identical. The
27-table index drift remains after that, last in ADR-112's order.
