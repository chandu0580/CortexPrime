# Phase 10.16 — Restore the missing `missions` ORM mapping
## Verification Report

**STATUS: STOPPED at stop condition 3** — `alembic check` reports legitimate
schema drift.

**The model was created and is proven correct.** A, B, C, D, G, H, I, J and K
all pass. **E and F do not, and cannot, for reasons that have nothing to do with
`missions`:** repairing metadata closure let `alembic check` run for the first
time, and it immediately exposed **pre-existing ORM-vs-migration drift across
~15 other tables**. Fixing that is forbidden here (rules 5, 6; stop conditions
4, 11) and is a decision, not a workaround.

Every claim was produced by running something.

---

## 1. Section results

| § | Verification | Result |
|---|---|---|
| A | Metadata closure | **PASS** |
| B | Reflected database comparison | **PASS** — every column, PK, index, constraint |
| C | Fresh database | **PASS** |
| D | Existing migrated database | **PASS** |
| E | `alembic check` | **STOPPED** — drift, none of it `missions` |
| F | Autogenerate empty | **STOPPED** — same cause; artifact deleted |
| G | `create_all` | **PASS** on the stated failure; **one caveat** (§8) |
| H | FK `ON DELETE SET NULL` | **PASS** — real rows, real delete |
| I | Cross-concept safety | **PASS** |
| J | Regression | **PASS** — identical to the 10.18 baseline |
| K | Governance safety | **PASS** |

**Files changed: 4.** `backend/database/models/mission.py` (new),
`backend/database/models/__init__.py` (one import + one `__all__` entry),
`scripts/phase1014_retire_iam_harness.py` (one superseded check inverted, §10),
`docs/PHASE_10_16_IMPLEMENTATION_MAP.md` (corrected, §2).

**No migration. No schema change. No `missions_bc`, Mission Runtime, governance,
tenant, authority, approval, execution, worker, connector or credential change.**

---

## 2. Corrections to the implementation map

The map is the specified source for the model, and two things in it needed
correcting before it could be followed exactly:

1. **§6 wrote the primary key as `sa.Uuid()`.** Migration `0001` uses
   `sa.UUID(as_uuid=True)`. Rule 7 forbids reinterpreting a column, so the
   shipped model uses `0001`'s form. Both render as `UUID` on PostgreSQL; the
   correction is fidelity to the source of truth, not behaviour.
2. **The header still described the phase as STOPPED**, which was true of the
   first attempt (ADR-108) and false after Phase 10.18 removed the competing
   authority. Updated, with the original stop preserved in §3-5 rather than
   rewritten.

Everything else was implemented exactly as §6 specified, including the decision
**not to use `UUIDPrimaryKeyMixin` or `TimestampMixin`**: both add Python-side
semantics `0001` does not specify (`default=uuid.uuid4`, `onupdate=_utcnow`), and
a mixin here would be a reinterpretation.

### The `metadata` column — proven, not assumed

Rule 4 requires the column named `metadata` to keep that name. It does. The
Python **attribute** cannot, and this was verified rather than asserted:

```
ATTRIBUTE 'metadata' REFUSED: InvalidRequestError
   Attribute name 'metadata' is reserved when using the Declarative API.
COLUMN NAME via mapped_column('metadata', ...) = ['id', 'metadata']
```

So the model uses `meta` as the attribute and `"metadata"` as the column —
exactly what `reflection_history` already does. The database column name is
unchanged and is not renamed to any application concept.

---

## 3. § A — metadata closure [PASS]

```
TABLES_ON_BASE_METADATA 39                     (was 38)
UNRESOLVED_FK_TARGETS 0 {}                     (was 1: 'missions')
SORTED_TABLES OK 39                            (was NoReferencedTableError)
FK reflection_history.mission_id -> missions.id  ondelete='SET NULL'  resolves_to_table='missions'
FK runtime_analytics.mission_id  -> missions.id  ondelete='SET NULL'  resolves_to_table='missions'
MISSIONS_MAPPED True
```

The assertion is that the unresolved-target **set is empty**, not merely that
`missions` is present — so it cannot pass while some other target is missing.

---

## 4. § B — reflected database comparison [PASS]

Against a database built by `alembic upgrade head`, with migration `0001` as the
authority. Reflected columns compared to the ORM model:

| column | ORM type | DB type | null ORM/DB | default | match |
|---|---|---|---|---|---|
| `id` | UUID | UUID | False/False | `gen_random_uuid()` | OK |
| `title` | TEXT | TEXT | False/False | — | OK |
| `objective` | TEXT | TEXT | False/False | — | OK |
| `status` | VARCHAR(32) | VARCHAR(32) | False/False | `pending` | OK |
| `priority` | INTEGER | INTEGER | True/True | `5` | OK |
| `result` | TEXT | TEXT | True/True | — | OK |
| `metadata` | JSONB | JSONB | True/True | `{}` | OK |
| `started_at` | TIMESTAMPTZ | TIMESTAMPTZ | True/True | — | OK |
| `completed_at` | TIMESTAMPTZ | TIMESTAMPTZ | True/True | — | OK |
| `created_at` | TIMESTAMPTZ | TIMESTAMPTZ | False/False | `NOW()` | OK |
| `updated_at` | TIMESTAMPTZ | TIMESTAMPTZ | False/False | `NOW()` | OK |

```
column order/name identical : True
ORM pk ['id']               DB pk ['id']
DB indexes  [('idx_missions_status', ['status', 'created_at'])]
ORM indexes [('idx_missions_status', ['status', 'created_at'])]
DB check    ['ck_missions_status']    ORM check ['ck_missions_status']
RESULT: ALL COLUMNS MATCH
```

Name, type, nullability, primary key, index (name **and** columns) and the
**named** check constraint all match. **Stop condition 1 does not fire.**

---

## 5. § C — fresh database [PASS]

```
upgrade EXIT=0   migrations run: 23
revision=0023_retire_iam   tables=55   missions_present=1
```

`missions` matches `0001` (§4). **No additional migration is generated merely
because the model was registered** — the disposable autogenerate in §7 contains
**zero** operations naming `missions`.

---

## 6. § D — existing migrated database [PASS]

Against a database already at head, carrying real rows:

```
BEFORE: md5=48b30be333e3a532be3430e98732ec97 tables=55 rev=0023_retire_iam rh_rows=1 ra_rows=1 missions_rows=0
upgrade EXIT=0  migrations run: 0
AFTER : md5=48b30be333e3a532be3430e98732ec97 tables=55 rev=0023_retire_iam rh_rows=1 ra_rows=1 missions_rows=0
```

No migration required, no table altered, no row changed, revision unchanged.

---

## 7. § E and § F — the stop [STOPPED — condition 3]

`alembic check` now **runs** (it previously died inside `sorted_tables` before
comparing anything). It exits non-zero with a long list of pending operations.

**None of them concerns `missions`.** Tables appearing in the diff:

```
cost_optimization_recommendations, cost_provider_rates, cost_records,
cost_tracking, cp_approval, fleets, fleet_agents, fleet_deployments,
fleet_metrics_snapshots, workflows, workflow_nodes, workflow_edges
```

plus ~20 removed-index operations across `agent_configs`, `connector_activity`,
`episodic_memory`, `semantic_memory`, `reflection_history`, `executions` and
others. A search for `'missions'` in the entire diff returns **nothing**.

**This is pre-existing drift, and that was proven rather than argued.** In a
database migrated to head:

```
cost_optimization_recommendations = 0    (referenced in 0 migration files)
fleets                            = 0    (referenced in 0 migration files)
workflows                         = 0    (referenced in 0 migration files)
missions                          = 1
```

Those models are imported by `models/__init__.py` and declare tables that **no
migration has ever created**. That divergence has existed for as long as the
models have; it was simply **invisible**, because `alembic check` could not get
past the unresolved `missions` foreign key to report it.

**§ F — autogenerate.** Run into a disposable revision:

```
generated: 736d79be8db6_p1016_disposable_probe.py
operations naming 'missions': NONE
total ops: 268
```

Not empty — for the same reason — and **zero** of the 268 operations touch
`missions`. The artifact was **deleted**; the migration count is back to 23 and
`git diff --quiet -- backend/database/migrations/` reports the directory
unchanged.

### Why this is a stop and not something to fix here

The brief is explicit: *"Do NOT make `alembic check` green by suppressing the
difference"* and *"Do NOT add an Alembic migration just because the ORM model is
new."* Making E pass would require writing migrations for ~15 unrelated tables —
forbidden by rule 6 and stop conditions 4 and 11, and far outside this phase.

The model itself is not the problem, and §4 is why that can be said with
confidence: it was compared against the real database **before** anything was
changed to satisfy `alembic check`, exactly as the brief's IMPORTANT section
requires.

---

## 8. § G — `create_all` [PASS, with one caveat]

| Target | Result |
|---|---|
| Fresh database | **error=NONE**, 39 tables created, `missions` present |
| Already-migrated database | **error=NONE**, `missions` untouched, **0 tables removed**, **10 tables added** |

**The failure this phase exists to remove is gone**: no `sorted_tables` failure,
no `NoReferencedTableError`. That is the stated requirement and it passes.

**The caveat, reported not hidden:** on an already-correct schema `create_all`
added 10 tables — `cost_optimization_recommendations`, `cost_provider_rates`,
`cost_records`, `fleets`, `fleet_agents`, `fleet_deployments`,
`fleet_metrics_snapshots`, `workflows`, `workflow_nodes`, `workflow_edges`.

These are exactly the drifted tables from §7: models with no migration behind
them. `create_all` creates what the models declare, so it creates them.
**`missions` was not among them, and nothing was altered or dropped.** This is
the same pre-existing divergence wearing a different hat, and it is the second
reason the drift needs its own phase.

---

## 9. § H — the foreign-key contract [PASS]

Real rows in a real migrated database, not a source assertion:

```
BEFORE reflection_history.mission_id = 11111111-1111-1111-1111-111111111111
BEFORE runtime_analytics.mission_id  = 11111111-1111-1111-1111-111111111111

DELETE 1   (the mission row)

AFTER  reflection_history.mission_id = NULL   row_still_exists=yes
AFTER  runtime_analytics.mission_id  = NULL   row_still_exists=yes
missions_rows_remaining = 0
```

And the rule as the database declares it:

```
reflection_history.mission_id -> missions.id  SET NULL
runtime_analytics.mission_id  -> missions.id  SET NULL
```

Both children survived with `mission_id` nulled. **Neither foreign key lost
`ON DELETE SET NULL`** — stop condition 6 does not fire.

---

## 10. § I — cross-concept safety [PASS]

```
I1 distinct tables          : missions vs missions_bc -> True
I3 imports (AST, not prose) : ['__future__', 'backend.database.base', 'datetime',
                               'sqlalchemy', 'sqlalchemy.dialects.postgresql',
                               'sqlalchemy.orm', 'typing', 'uuid']
I4 forbidden imports        : NONE
I5 classes / module funcs   : ['MissionRecord'] []  -> exactly one class, no functions
I6 runtime consumers        : (see below)
I7 Mission Runtime repo     : InMemoryMissionRepository
```

Imports were read from the **AST**, not from prose: the module imports nothing
from `repositories.missions`, `contexts.mission`, `backend.mission`, or any
auth/approval/authority/tenant/execution/worker/connector/credential module. It
declares one class and no functions — no repository, no authority, no second
mission system.

### A name collision, found and neutralised

`I6` flagged `backend/services/enterprise_executive_runtime.py`. Inspection
showed a **name collision, not a reference**: that file defines its own
`@dataclass(frozen=True) class MissionRecord` at line 90, held in an in-memory
dict, and never imports this one.

The name is kept — it follows the sibling convention
(`ReflectionHistoryRecord`, `RuntimeAnalyticsRecord`) — but the collision is
recorded in the model's docstring, because a future text search for
`MissionRecord` will find both and this phase family has already been bitten
once by exactly this (`MissionRepository` Protocol vs the SQLAlchemy class).

**Mission Runtime is unchanged**: its routes still use
`InMemoryMissionRepository`, and `missions_bc` is untouched.

---

## 11. § J — regression [PASS]

| Gate | Result |
|---|---|
| `tests/architecture` | **155 passed** |
| Phase 10.7 harness | **155/155 VERIFIED** |
| Phase 10.8 harness | **118/118 VERIFIED** |
| Phase 10.9 harness | **107/107 VERIFIED** |
| Phase 10.10 harness | **107/107 VERIFIED** |
| Phase 10.11 harness | **68/68 VERIFIED** |
| Phase 10.13 harness | **60/60 VERIFIED** |
| Phase 10.14 harness | **53/53 VERIFIED** (was 52; §12) |
| Full backend regression | 75 failed, 6775 passed, 36 skipped, 58 xfailed, 24 errors |

**The regression is identical to the baseline Phase 10.18 established** on a
tree without this model — same failed, passed, skipped, xfailed and error
counts. Those 75 failures and 24 errors are pre-existing and were proven so in
Phase 10.18 by reverting the tree; nothing here changes them.

**Two harness results were investigated, not accepted:**

- **10.13 and 10.14 first produced no counts**, crashing on `.json()` of an
  empty HTTP body. Both had run **in parallel with the full regression suite**.
  Re-run alone: 10.13 **60/60**, and 10.14 ran all 52 checks. **Contention,
  proven by isolation** — not a regression.
- **10.7 reports `provider_writes` of `0` and `1`.** The `1` is that harness's
  own single commissioned governed write (D6, mutating exactly one deployment),
  exactly as in every prior phase. Its negative matrix is 0. **This phase causes
  no provider write.**

---

## 12. A superseded assertion in the 10.14 harness, inverted not deleted

Re-running 10.14 alone gave **51/52**, with one failure:

> `D3. create_all itself fails on a PRE-EXISTING defect unrelated to IAM —
> reflection_history -> missions, a table no model declares — and the failure
> names missions, not iam`

**That check asserted the exact defect this phase was commissioned to repair.**
Phase 10.14 found it, proved it unrelated to IAM, and deliberately left it. Rule
11 of this brief permits repairing `init_db()` "beyond what becomes naturally
fixed by registering this model" — and this is precisely what registering the
model naturally fixes.

Following the precedent this family set when Phase 10.14 invalidated 10.13's
section H, the check was **inverted, not deleted** — deleting it would erase the
evidence that the gap was real; inverted, it now fails if the mapping ever
disappears again:

- `D3` now asserts `create_all` **no longer** raises `NoReferencedTableError`
  and that no failure names `missions`.
- `D4`, previously a `deferred()` entry reading *"init_db() on a fresh database:
  PRE-EXISTING and out of scope"*, became a **real check** that the repair did
  not resurrect IAM (`IAM_IN_METADATA []` and `IAM_AFTER []`).

That is why the total rose **52 → 53**: a deferral was discharged, not a check
removed. Re-run: **53/53 VERIFIED.**

*(`create_all` in that probe now fails further along, on `type "vector" does not
exist`, because the probe database has no pgvector extension. That is the
probe's environment, not a mapping defect — §8 shows `create_all` completing
cleanly where the extension exists.)*

---

## 13. § K — governance safety [PASS]

| Requirement | Evidence |
|---|---|
| Provider writes = 0 | This phase touches no execution path. The only write in any harness is 10.7's own commissioned one (§11) |
| No credential access | AST imports (§10) include no credential module |
| No authority / approval / tenant / execution changes | `git status`: `backend/auth`, `backend/api`, `backend/contexts`, `backend/platform`, `backend/governance` **untouched** |
| No migration history change | `git diff --quiet -- backend/database/migrations/` → unchanged; 23 revisions; head still `0023_retire_iam` |
| `missions_bc` / Mission Runtime unchanged | `git diff --quiet` over `repositories/missions.py`, `backend/mission/`, `backend/contexts/mission/`, `mission_runtime_routes.py` → unchanged |
| `init.sql` unchanged | `git diff --quiet -- infra/postgres/init.sql` → unchanged |
| Governed harnesses unchanged | 10.7–10.14 all VERIFIED at full counts (§11) |

---

## 14. Stop conditions

| # | Condition | Result |
|---|---|---|
| 1 | Reflected `missions` does not match `0001` | **No** — §4, exact match |
| 2 | Model would need to reinterpret a column | **No** — copied from `0001`; no mixins |
| 3 | **`alembic check` reports legitimate schema drift** | **FIRED — §7.** Drift is real, and **none of it is `missions`** |
| 4 | Autogenerate proposes a non-empty migration | Non-empty, **same cause as 3**; zero `missions` operations; artifact deleted |
| 5 | `create_all` proposes destructive/unexpected changes | **Not destructive** — 0 removed, 0 altered. 10 tables added, same cause as 3 (§8) |
| 6 | Either FK loses `ON DELETE SET NULL` | **No** — §9, proven with real rows |
| 7 | `missions_bc` coupled to this model | **No** — §10 |
| 8 | Mission Runtime behaviour changes | **No** — §10 |
| 9 | Governance behaviour changes | **No** — §13 |
| 10 | Prior phase regression | **No** — §11; the one 10.14 failure was a superseded assertion, §12 |
| 11 | A migration required to make the model correct | **No** — §4 and §5 |
| 12 | A second mission authority introduced | **No** — §10; nothing reads or writes this table |
| 13 | Verification depends on a vacuous assertion | **No** — §3 asserts the unresolved-target set is *empty*; §9 uses real rows and a real delete; §11 re-ran suspicious results in isolation rather than accepting them |

**Condition 3 fired**, and 4 and 5 are the same finding seen from two other
angles. Nothing was suppressed to avoid it.

---

## 15. Known limitations

1. **`alembic check` and autogenerate are still not clean** (§7). The model is
   not the cause; ~15 other tables are. Until that drift is resolved, neither
   command is usable as a drift detector — the capability is *unblocked* but not
   yet *useful*.
2. **`create_all` on a migrated database now creates 10 unrelated tables** (§8).
   It previously created none because it raised first. This is newly-visible
   behaviour, not new behaviour.
3. **The 75 regression failures and 24 errors remain**, pre-existing and
   untriaged.
4. **No application was started.** §D verified "no migration required" by
   running `alembic upgrade head` and comparing fingerprints, not by booting the
   app. `init_db()` was exercised through `create_all` (§8), which is the part
   the model affects.
5. **`missions` still has no reader or writer.** This phase adds a mapping, not
   a use. That remains the honest description of the table.
6. **The `MissionRecord` name is shared** with an unrelated dataclass (§10).
   Documented rather than renamed.
