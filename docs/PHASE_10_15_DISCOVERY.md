# Phase 10.15 — Repair the Broken Database Initialization Path
## Discovery Report (DISCOVERY ONLY — no production code, no migration, no schema change)

**Status: GO**, for a repair narrower than the phase title implies, and for a
reason the title does not name.

Every claim below is labelled. Evidence is a source read, a git query, a probe
run in a child process, or a query against a real PostgreSQL database.

---

## 0. Summary

`Base.metadata` contains two tables whose foreign keys point at `missions`, and
**no SQLAlchemy model has ever mapped `missions`**. The table is real — created
by migration `0001` and by `infra/postgres/init.sql` — but it exists only as raw
DDL. SQLAlchemy therefore cannot resolve the foreign key when it sorts tables,
and `Base.metadata.sorted_tables` raises.

That single unresolved reference breaks two things, not one:

| Affected | Severity |
|---|---|
| `init_db()` → `Base.metadata.create_all` | low — already gated, refused by default, non-fatal at boot |
| `alembic check` and `alembic revision --autogenerate` | **high — a developer-facing capability that is entirely unusable** |

`alembic upgrade head` is **not** affected and never was.

The defect is **not** a regression, **not** stale, and **not** caused by Phase
10.14.

---

## 1. Task 1 — the complete definition of `reflection_history` [VERIFIED]

`backend/database/models/reflection_history.py:37` —
`class ReflectionHistoryRecord(UUIDPrimaryKeyMixin, TimestampMixin, Base)`.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | from `UUIDPrimaryKeyMixin` |
| `mission_id` | UUID, nullable, indexed | **`ForeignKey("missions.id", ondelete="SET NULL")`** |
| `agent` | `String(128)`, not null, indexed | |
| `reflection` | `Text`, not null | |
| `embedding` | `Vector(1536)`, nullable | pgvector |
| `score` | `Float`, nullable | |
| `meta` | `JSONB`, nullable, column named `metadata` | |
| `created_at` / `updated_at` | from `TimestampMixin` | |

Indexes: `idx_refl_agent_created`, `idx_refl_mission_created`.

**Exact referenced table/column: `missions.id`, `ON DELETE SET NULL`.**

The model's own docstring says `mission_id : optional FK to missions table
(nullable — global reflections)`.

### The second referencing model [VERIFIED]

The brief names one FK. There are **two**:

- `reflection_history.mission_id` → `missions.id`
- `runtime_analytics.mission_id` → `missions.id`
  (`backend/database/models/runtime_analytics.py:43`, identical declaration)

Any repair must address both. A repair that fixed only the one named in the
error message would fail again on the next table SQLAlchemy reached.

---

## 2. Task 2 — every consumer of `reflection_history`, classified [VERIFIED]

| Consumer | Class |
|---|---|
| `backend/memory/stores/reflection_store.py` — raw SQL insert/select | **production runtime** (write path) |
| `backend/database/repositories/reflection_repository.py` — ORM + vector search | **production runtime** (read path) |
| `backend/api/vector_search_routes.py` | **production runtime** |
| `backend/api/memory_explorer_routes.py` — counts, group-by | **production runtime** |
| `backend/api/executive_routes.py` — table count | **production runtime** |
| `backend/database/models/__init__.py` | registration |
| `0001_initial_schema.py`, `0003_consolidate_reflection_tables.py` | **migration-only** |
| `infra/postgres/init.sql` | **migration-only** (raw bootstrap DDL) |
| `tests/test_reflection_consolidation.py` | **test-only** |
| `backend/api/legacy_persistence_inventory.py` | documentation record |
| `backend/agents/.../reflection_agent.py`, `backend/orchestrator/reflection_engine.py` | **unrelated** — a Python list attribute that happens to share the name, not the table |

`reflection_history` is **live production state**. It is not a candidate for
retirement in this phase.

---

## 3. Task 3 — every reference to `missions` [VERIFIED]

**Was a `missions` SQLAlchemy model ever present? No.**

```
git log --oneline --all -S'__tablename__ = "missions"' -- backend/   →  (no commits)
```

It was never removed and never renamed. **The model was never written.** The
table has only ever existed as raw DDL.

### Where the table is created

- `backend/database/migrations/versions/0001_initial_schema.py:31` —
  `op.create_table("missions", ...)`, under the comment
  *"missions (referenced by reflection_history + runtime_analytics)"*. The
  author knew about both references.
- `infra/postgres/init.sql:79` — `CREATE TABLE IF NOT EXISTS missions (...)`,
  where `cognition_events.mission_id` gives it a third reference.

Columns per `0001`: `id`, `title`, `objective`, `status`, `priority`, `result`,
`metadata`, `started_at`, `completed_at`, `created_at`, `updated_at`, plus
`ck_missions_status` and `idx_missions_status`.

### Is there another current table representing missions? Yes — a different one.

**Three distinct "mission" notions exist, and they are not the same thing.**

| # | Name | Defined by | ORM model | Production consumer |
|---|---|---|---|---|
| 1 | `missions` | migration `0001`, `init.sql` | **none, ever** | **none** |
| 2 | `missions_bc` | migration `0007` | `MissionModel` in `repositories/missions.py` | `backend/mission/service.py`, registered at boot |
| 3 | in-memory Mission | `backend/contexts/mission/` | none — no SQL | `mission_runtime_routes.py` |

`missions_bc` is deliberately suffixed to avoid colliding with the existing
`missions`. `mission_steps.mission_id` and `executions.mission_id` reference
`missions_bc`, not `missions`.

### Nothing reads or writes the `missions` table [VERIFIED]

A sweep for `FROM|INTO|UPDATE|JOIN|DELETE FROM missions` across the repository
returns, in production code, **nothing**. The only hits are:

- `tests/test_reflection_consolidation.py:95,101` — a fixture that INSERTs a row
  **solely so the FK is satisfiable**, then deletes it;
- `docs/TROUBLESHOOTING_GUIDE.md`, `docs/DISASTER_RECOVERY_RUNBOOK.md` —
  operator SQL in prose;
- the DDL that creates it.

`scripts/run-retention-policy.py`'s `purge_missions()` was checked and touches
**filesystem stores only** — `data/episodic`, `data/events`, `data/replay`
(`backend/core/data_retention.py:119-125`). It is not a SQL consumer.

**Conclusion: `missions` is an orphaned FK parent. Zero production readers, zero
production writers. Its only function today is to make two foreign keys legal.**

### Is the FK stale, or is the missing model the defect?

**Neither is "stale".** The FK is live and correct in every migrated database
(§5). The defect is the **absent ORM mapping** — an ORM-side gap, not a schema
gap.

---

## 4. Task 4 — migration lineage `0001 → HEAD` [VERIFIED]

Single unbroken head, `0001 → 0023_retire_iam`, 23 revisions.

| Question | Answer |
|---|---|
| When was `reflection_history` created? | `0001_initial_schema.py:139`, with the `missions.id` FK inline at line 141 |
| Was `missions` ever created? | Yes — `0001:31`, and independently by `infra/postgres/init.sql:79` |
| Did a migration drop or rename it? | **No.** `op.drop_table("missions")` appears only inside `0001`'s own `downgrade()` (line 225) |
| Was `reflection_log` involved? | `0003` consolidated `reflection_log` **into** `reflection_history` and re-declares the same `REFERENCES missions (id) ON DELETE SET NULL` at line 77 — the FK was reaffirmed, not inherited by accident |
| Does the FK exist in real PostgreSQL? | **Yes** — §5 |
| Do migrations and ORM metadata disagree? | **On the schema, no. On mapping, yes** — the ORM maps the children but not the parent |

---

## 5. Task 7 — the real databases [VERIFIED]

19 databases on `cortex-p99b-pg` (127.0.0.1:55437). Two have been migrated to
head; the rest were built by `DURABLE_METADATA.create_all` for governance phases
and contain none of these tables.

| DB | `alembic_version` | `missions` | `missions_bc` | `reflection_history` | `runtime_analytics` | `mission_steps` |
|---|---|---|---|---|---|---|
| `cortex_p99b` | `0023_retire_iam` | YES | YES | YES | YES | YES |
| `cortex_p1014_fresh` | `0023_retire_iam` | YES | YES | YES | YES | YES |
| `cortex_p102/103/107/109/1010/1013/1014` … | *(no `alembic_version`)* | no | no | no | no | no |

**Foreign keys actually present**, identical on both migrated databases:

```
child                col           parent        delete_rule
reflection_history   mission_id    missions      SET NULL
runtime_analytics    mission_id    missions      SET NULL
mission_steps        mission_id    missions_bc   CASCADE
executions           mission_id    missions_bc   SET NULL
```

**The runtime schema and the ORM declarations agree exactly.** There is no
divergence to reconcile — the FK is where the model says it is, with the delete
rule the model says.

**Row counts, both migrated databases:**
`missions=0  missions_bc=0  reflection_history=0  runtime_analytics=0  mission_steps=0`.

**[NOT VERIFIED]** No production or long-lived development database was
available to this discovery. Every database here is disposable phase
infrastructure. **The claim "these tables are empty" is true of what exists on
this machine and must not be generalised to a deployed environment.** A repair
that assumed empty tables would be assuming something this discovery cannot
establish — one reason the recommended repair does not touch data at all.

---

## 6. Task 5 — metadata registration [VERIFIED]

`init_db()` calls `_ensure_bc_models()` (`engine.py:202-203`) and then
`Base.metadata.create_all` (line 210). `_ensure_bc_models()`
(`models/__init__.py:39`) imports ten bounded-context repository modules for
their registration side effect — **including
`backend.database.repositories.missions`**, which registers `missions_bc` and
`mission_steps`, not `missions`.

A probe in a child process, mirroring exactly what `init_db()` does:

```
TABLES_ON_BASE_METADATA 38
UNMAPPED_FK_TARGETS 1
  MISSING TABLE 'missions' <- referenced by
      ['reflection_history.mission_id', 'runtime_analytics.mission_id']
MISSION_LIKE_TABLES ['mission_steps', 'missions_bc']
SORTED_TABLES_ERROR NoReferencedTableError Foreign key associated with column
  'reflection_history.mission_id' could not find table 'missions' with which to
  generate a foreign key to target column 'id'
```

Three things this establishes:

1. **`missions` is the only unmapped FK target on the whole of `Base.metadata`.**
   The problem is bounded: one missing table, two referencing columns.
2. **It is not an import-order problem.** `_ensure_bc_models()` ran and every
   registration module was imported; the table is unmapped because no model
   anywhere declares it.
3. **It is `sorted_tables` that fails, not `create_all` specifically.** Anything
   that topologically sorts `Base.metadata` hits it.

`reflection_history` is registered because `models/__init__.py:11` imports it
eagerly. `missions` is not registered because no module defines it.

`DURABLE_METADATA` — the governed Phase 5.1+ store — sorts cleanly at **25
tables**. It shares no metadata with `Base` and is entirely unaffected.

---

## 7. The blast radius is larger than `init_db()` [VERIFIED]

`backend/database/migrations/env.py:63` sets
`target_metadata = [Base.metadata, DURABLE_METADATA]`. Autogenerate must sort
that metadata, so it hits the same failure:

```
$ python -m alembic -c backend/database/migrations/alembic.ini check
...
sqlalchemy.exc.NoReferencedTableError: Foreign key associated with column
'reflection_history.mission_id' could not find table 'missions'
```

**`alembic check` and `alembic revision --autogenerate` are completely
unusable.** Nobody on this project can autogenerate a migration, or ask whether
the models and the database have drifted apart. Every migration from `0001` to
`0023` was necessarily hand-written.

`alembic upgrade head` is unaffected — it replays revision scripts and never
sorts `target_metadata`. Verified by `0023` applying cleanly to two databases
during Phase 10.14, both now reporting head.

**This is the finding that justifies the phase.** Repairing `init_db()` alone
would be low value; repairing autogenerate restores a real capability.

---

## 8. Task 8 — what `init_db()` is actually for [VERIFIED]

**Answer: C — development/test initialization — and it is already deliberately
gated as such.**

`backend/database/engine.py:159-196`:

- It raises `SchemaBootstrapRefused` unless the caller passes
  `allow_non_production=True` **and** `_is_production()` is false.
- `_is_production()` treats an **unset** environment as production, on the
  stated reasoning that *"an environment nobody configured is more likely to be
  a container somebody deployed than a laptop, and the failure modes are not
  symmetric."*
- Its docstring records why the gate exists: `init_db()` used to be the
  **fallback when migrations failed**, producing *"a database that no migration
  ever produced"*.
- It states plainly that this path **can never produce a complete schema
  anyway**, because the durable tables live on `DURABLE_METADATA` and are
  invisible to it.

`backend/main.py:814-832` catches `SchemaBootstrapRefused` and continues when
migrations succeeded. Any other exception — which is what the `missions` failure
produces — is logged as *"Development schema bootstrap incomplete"* and is fatal
**only if migrations had already failed**.

**So the current failure is non-fatal at boot, by design.**

`backend/api/legacy_persistence_inventory.py:245-256` already classifies this
module `SECURITY_HAZARD` and prescribes the disposition: *"`init_db` should not
be reachable in production. **Gate it; do not delete it**, because development
and tests rely on it."* That gate has since been built.

**No test calls `init_db()`.** The only two tests that call `create_all`
(`tests/architecture/probes.py:156`,
`tests/database/test_tenant_scoped_repository.py:111`) declare their **own local
`Base`** and run against in-memory SQLite. The "tests rely on it" clause of the
inventory note is, today, **not true** — worth recording, because it removes one
argument for keeping the path.

---

## 9. Task 6 — Mission Runtime [VERIFIED]

The brief warns not to assume a class named `Mission` maps to SQL `missions`.
It does not.

- **`backend/api/mission_runtime_routes.py:68`** —
  `_service = MissionService(repository=InMemoryMissionRepository())`.
  The mission runtime routes use an **in-memory repository. No SQL at all.**
- **`backend/mission/service.py:13`** imports `MissionModel` from
  `repositories/missions.py` → **`missions_bc`**. This service is registered at
  boot (`backend/main.py:200` → `register_mission_services()`), so it is live —
  and it uses the bounded-context table, not the V1 one.
- **`backend/contexts/mission/infrastructure/repository.py`** defines a
  `MissionRepository` *Protocol* and `InMemoryMissionRepository`. That is a
  different class from the SQLAlchemy `MissionRepository` in
  `repositories/missions.py`; the shared name is a trap for text search.

**Mission Runtime touches `missions` in none of its three forms.** No repair
proposed here can affect it.

---

## 10. A latent consequence found on the way [NOT VERIFIED]

Because **nothing ever inserts into `missions`**, any non-null `mission_id`
written to `reflection_history` or `runtime_analytics` must violate the foreign
key. Two paths appear to do exactly that:

1. `backend/memory/event_subscriber.py:116` calls
   `store_reflection(..., mission_id=getattr(event, "execution_id", None))` —
   an **execution id used as a mission id**. The enclosing `try` swallows
   everything at `logger.debug` (lines 120-121), so such a write would be
   **silently discarded**.
2. `backend/api/vector_search_routes.py:308-318` takes `mission_id` from the
   **request body** and writes it to `runtime_analytics`; a client-supplied UUID
   with no matching `missions` row would raise on insert.

`tests/test_reflection_consolidation.py` documents the mechanism in its own
words: *"reflection_history.mission_id has a real FK constraint against it, so a
random UUID with no matching row fails with ForeignKeyViolationError as soon as
the write path actually runs"* — and works around it by inserting a `missions`
row first.

**Labelled [NOT VERIFIED] deliberately.** It is read from source and is
consistent with the test's own comment, but no live event was driven through
either path in this discovery, and neither is proven to fire in practice. It is
recorded because it bears directly on candidate C below: **removing the FK would
silence a constraint a test relies on, and which may be discarding data today.**
Proving or disproving it is proposed as its own work, not as part of a metadata
repair.

---

## 11. Tasks 9 & 10 — repair candidates

### A. Declare a `missions` model matching migration `0001` exactly — **RECOMMENDED**

Add one ORM model mapping the existing table, column for column as `0001`
defines it, and register it in `models/__init__.py`.

| | |
|---|---|
| Invariant restored | `Base.metadata` is closed under foreign keys, so it can be sorted. `create_all`, `drop_all`, `alembic check` and `--autogenerate` all work |
| Could break | An inaccurate model makes `autogenerate` propose spurious drift — the exact failure Phase 10.14 produced in a `downgrade()`. It must be copied from `0001`, not reinterpreted |
| Migration required | **No** — the table already exists in every migrated database, with these columns |
| Data affected | **No** — nothing created, altered or deleted; `create_all` is `checkfirst=True` |
| Mission Runtime affected | **No** — §9; nothing consumes this table |
| Governance affected | **No** — `DURABLE_METADATA` is separate and already sorts (§6) |

Additive, reversible by deletion, and it changes no behaviour that exists today.
It also makes the two FKs *mean* what the database already enforces.

### B. Point both FKs at `missions_bc` instead

| | |
|---|---|
| Invariant restored | Metadata closes, and mission references would point at a table something actually writes |
| Could break | **This changes semantics.** A schema change requiring a migration to drop and recreate two constraints, and it silently redefines what a `mission_id` in reflection/analytics *means*. The two tables have different columns and different lifecycles |
| Migration required | **Yes** |
| Data affected | **Yes, potentially** — existing `mission_id` values must resolve against a different parent, or be nulled |
| Verdict | **Rejected for this phase.** It answers a design question — "which mission concept do reflections belong to?" — that discovery has not settled and nobody has asked |

### C. Drop the two foreign keys

| | |
|---|---|
| Invariant restored | Metadata closes |
| Could break | Removes a real database constraint. `tests/test_reflection_consolidation.py` explicitly relies on it, and §10 suggests it may be the only thing currently preventing orphaned mission references |
| Migration required | **Yes** |
| Data affected | No rows change, but referential integrity is permanently weakened |
| Verdict | **Rejected.** This is the "delete the FK to make `create_all` pass" shortcut the brief names in Task 11 |

### D. Retire `reflection_history`

Rejected outright: it is **live production state** with five runtime consumers
(§2). Not a candidate.

### E. Retire the `missions` table

Superficially attractive — it has no reader or writer (§3). But `0001` created
it, two live FKs depend on it, and `init.sql` gives `cognition_events` a third
reference. Retiring it means dropping three constraints and a table — candidate
C plus more. **Rejected for this phase**; recorded as possible future work once
§10 is settled.

### F. Repair import registration

**Not applicable.** §6 proves this is not an import-order problem — no module
defines the table at all, so no import can register it.

### G. Replace `create_all` with migration-only initialization

Arguably the correct long-term answer, and partly already done (the gate, and
`main.py`'s removal of the fallback). But it does **not** fix `alembic check`
(§7), which is the larger half of the defect — autogenerate needs sortable
metadata regardless of whether `create_all` is ever called again.
**Complementary, not a substitute.** Recorded as future work.

---

## 12. Task 11 — unsafe shortcuts, named

1. **Dropping the FK to make `create_all` pass.** Candidate C. It removes a
   constraint a test depends on and, per §10, possibly the only guard against
   orphaned mission references.
2. **Creating a fake or "minimal" `missions` model that does not match `0001`.**
   A model with invented or omitted columns would make `alembic --autogenerate`
   — the very capability this phase restores — immediately propose a spurious
   migration. Phase 10.14 made exactly this mistake in a `downgrade()` while its
   docstring claimed otherwise. The model must be **copied from `0001`, column
   for column, defaults included, and checked against it**.
3. **Changing migration history.** `0001` is the root of a live lineage and the
   table it creates is present in every migrated database. Nothing about this
   repair requires touching it.
4. **Repointing the FKs at `missions_bc` because that table "looks more alive".**
   Candidate B. A semantic decision, not a metadata fix.
5. **Suppressing the error** — a `try/except` around `create_all`, or an
   `extend_existing` stub — leaving the metadata still inconsistent and the
   autogenerate path still wrong.
6. **Deleting `init_db()` outright.** The existing inventory says *"Gate it; do
   not delete it"*; the gate exists. Deletion is a larger decision than this
   defect warrants, and would not fix autogenerate either.
7. **Assuming the tables are empty.** True of every database on this machine
   (§5), and **not established** for any deployed environment.

---

## 13. Task 12 — stop/go

Against the brief's stop criteria:

| Stop if… | Finding |
|---|---|
| the intended relationship is unclear | **Clear.** `reflection_history.mission_id → missions.id ON DELETE SET NULL`, declared identically in the model, in `0001`, re-affirmed in `0003`, and present in real PostgreSQL |
| `missions` has an unknown production consumer | **None found.** Zero readers, zero writers; one test fixture and DDL only (§3) |
| removing the FK could alter live semantics | It could — **so the recommendation does not remove it** |
| migration history and runtime schema disagree unexplainedly | **They agree exactly** (§5) |
| fixing `init_db()` requires redesigning Mission Runtime | **It does not.** Mission Runtime is in-memory or on `missions_bc` (§9) |

Against the go criteria: ownership is proven (V1 raw DDL, no ORM owner); the
relationship is understood; the repair is one additive model file plus one
import; data and behaviour impact is nil because nothing is created, altered or
deleted; and a verification strategy exists (§14).

**GO.**

---

## 14. Proposed verification strategy for the implementation phase

Not executed here — this is discovery. Recorded so the next phase inherits it.

1. **Fresh database:** create, `alembic upgrade head`, assert the table set is
   identical to a database migrated before the change. The repair must add
   **zero** tables.
2. **Existing database:** on a database already at `0023`, assert `alembic check`
   reports **no drift**. This is the check that catches an inaccurate model, and
   it is the whole point of the repair.
3. **The metadata invariant:** in a child process, run `_ensure_bc_models()` then
   assert `Base.metadata.sorted_tables` succeeds **and** that the
   unmapped-FK-target set is **empty** — not merely that `missions` is present.
4. **`create_all` on a fresh database** now completes, and the resulting table
   set is a **subset** of what `alembic upgrade head` produces (it must be — the
   durable tables live on the other metadata).
5. **`create_all` on a migrated database** creates nothing (`checkfirst`).
6. **Column-for-column equality with `0001`:** compare the *reflected* columns of
   `missions` on a real migrated database against the model's, rather than
   trusting the model file.
7. **Negative:** assert the two FKs still exist in PostgreSQL with
   `delete_rule = SET NULL` afterwards — proving the repair did not quietly
   become candidate C.
8. **Regression and architecture gates**, plus the Phase 10.7–10.14 harnesses, to
   prove the governed chain is untouched.

---

## 15. Honest limitations of this discovery

1. **No production database was inspected** (§5). All row counts come from
   disposable phase infrastructure.
2. **§10 is [NOT VERIFIED]** — the FK-violation write paths are read from source
   and consistent with a test's own comment, but were not driven live.
3. **Whether `missions` *should* exist at all is not settled here.** This
   discovery establishes only that it does exist, that two live FKs need it, and
   that mapping it is the smallest correct repair. Retiring it is a larger
   question (candidate E).
4. **`alembic --autogenerate` was not run after a hypothetical repair**, because
   that would require writing the model. The claim that the repair fixes
   autogenerate follows from `alembic check` failing inside `sorted_tables`
   today; it must be proven by execution in the implementation phase.
