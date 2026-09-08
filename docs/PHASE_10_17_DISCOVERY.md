# Phase 10.17 (second use of the number) — ORM / Alembic Drift Discovery
## DISCOVERY ONLY — no repair, no migration, no model change, no configuration change

> **Phase numbering.** This brief is labelled 10.17, but 10.17 already exists
> (schema-ownership discovery, `183a34c`, ADR-109,
> `docs/PHASE_10_17_SCHEMA_OWNERSHIP_DISCOVERY.md`). This document is created at
> the path the brief specified; the filename does not collide, but the phase
> number does. Nothing was renamed on my own initiative.

**STATUS: STOPPED** — stop conditions **1, 3, 4, 5, 6 and 9** fired. The
inventory is complete; the stop governs what happens *next*, not whether the
discovery was finished.

**The headline is not the ~15 V1 tables.** It is that a production database
built by `alembic upgrade head` **has no `cp_approval` table** and **cannot
become ready for governed execution** — proven by running the production
readiness check against exactly such a database. A second live defect was
found on the way: **every `cost_engine.record()` call fails** on a column-name
mismatch and is swallowed at `warning`.

Every claim below was produced by running something or reading a specific file.

---

## 0. Numbers

| | |
|---|---|
| `alembic check` | **DISCREPANCIES FOUND** (exit non-zero) |
| Autogenerate upgrade operations | **135**, across **39 tables** (274 op lines including downgrade) |
| Autogenerate determinism | two runs **byte-identical** apart from the message string I passed |
| Tables ORM-declared but absent at head | **11** |
| Tables at head but not ORM-declared | **2** — `alembic_version` (Alembic's own) and **`cost_tracking`** |
| Tables with index-only drift | **27** |
| Fresh head DB vs existing head DB | **identical** table sets (55 = 55) |
| The brief's "~15 tables" | **materially wrong — it is 39** (stop condition 9) |

---

## 1. Method

- **Fresh head database**: `cortex_drift_fresh`, created empty,
  `alembic upgrade head` → 23 migrations, `0023_retire_iam`, **55 tables**.
- **Existing head database**: `cortex_p1014_legacy`, at `0023_retire_iam`,
  **55 tables**, inspected read-only. `diff` of the two table sets: **identical**.
- **ORM metadata**: `Base.metadata` after `_ensure_bc_models()` → **39 tables**;
  `DURABLE_METADATA` → **25 tables**; no table on both.
- **`alembic check`** and **two `revision --autogenerate` runs** into disposable
  revisions, both copied to the scratchpad and **deleted**;
  `git status backend/database/migrations/` clean after each; versions count
  24 files before and after.
- **Runtime consumers** found by searching imports, constructors, route
  registration and tests — not by the existence of a model or a migration.
- **Readiness** proven by calling `verify_durability(create_schema=False)`
  against the fresh head database.
- Disposable database dropped after the evidence was captured.

---

## 2. The three classes of drift

```
Base.metadata (39)                        alembic head (55)
 ├─ 11 declared, NEVER migrated  ──────►  absent           [class A: add_table]
 ├─ 27 present, index names differ ─────►  present          [class C: index-only]
 └─ 1  declared elsewhere, unregistered   cost_tracking     [class B: drop_table]
DURABLE_METADATA (25)
 ├─ 24 migrated (0010–0022) ────────────►  present
 └─ 1  NEVER migrated: cp_approval ─────►  absent           [class A, GOVERNED]
```

---

## 3. Class A — declared by ORM, created by no migration (11 tables)

### 3.1 `cp_approval` — GOVERNED. Stop conditions 1 and 4.

| | |
|---|---|
| **ORM** | `approval_table`, `backend/database/durable/tables.py:879`, on **`DURABLE_METADATA`**, 21 columns, 2 indexes. Phase 10.3, ADR-096 |
| **Migration lineage** | **None.** Mentioned only in `0020`'s docstring, as a reason *not* to reuse it. Every other durable table has one: `0010`(9), `0011`(2), `0012`(2), `0013`(2), `0014`, `0015`–`0019`(5), `0020`, `0021`, `0022` — **24 of 25** |
| **Fresh head DB** | **absent** |
| **Existing head DB** | **absent** |
| **Runtime consumers** | `backend/contexts/connectivity/infrastructure/sql_approval.py:90` — **`SqlApprovalRepository`**, the production `ApprovalLookup` over `cp_approval`; `backend/api/product/approval_queue.py` — the product approval queue, a read model over it; the 10.3–10.10 product approval/execution routes |
| **How it exists anywhere** | Only via `DURABLE_METADATA.create_all`: `build_development_store` (`durable/config.py:285`) and `verify_durability(create_schema=True)` (`:321`). Both are **development-only**; `build_development_persistence` **raises `DurabilityMisconfigured`** if asked to serve production (`durability_composition.py:411-419`). Production boots via `build_durable_persistence` (`application_runtime.py:373`), which never creates schema |
| **Concept** | Real, live, persisted, governed — the approval store the entire remediation path depends on |

**Proven by execution** — production-style readiness against the fresh head
database, `create_schema=False`:

```json
{ "ready": false, "schema_present": false, "schema_version_ok": false,
  "missing_tables": ["cp_approval"], "detail": "missing tables: cp_approval" }
```

**A production deployment migrated with `alembic upgrade head` cannot become
ready for governed execution.** Every phase harness since 10.3 built its
database with `build_development_store`, which is why none of them noticed.
`verify_durability` fails closed correctly — the platform is right — but the
schema is simply not under migration control.

**Disposition: `ADD_MIGRATION`** — the evidence is unambiguous (the definition
is on `DURABLE_METADATA`, its 24 siblings are migrated, its consumer is live).
**Flagged GOVERNED: the phase stops here rather than proceed to implementation
without explicit authorisation.**

### 3.2 Fleet — 4 tables: `fleets`, `fleet_agents`, `fleet_deployments`, `fleet_metrics_snapshots`

| | |
|---|---|
| **ORM** | `FleetModel`, `FleetAgentModel`, `FleetDeploymentModel`, `FleetMetricsSnapshotModel` — `backend/database/models/fleet.py`, eager-imported by `models/__init__.py:10` |
| **Migration lineage** | **None**, ever |
| **Head DB** | absent (fresh and existing) |
| **Repository** | `backend/fleet/repository.py:20` `FleetRepository` — real SQLAlchemy SELECT/INSERT code |
| **Runtime consumers** | **`FleetRepository(` is constructed nowhere.** `router_registry.py:1691` registers `backend.fleet.routes`, which uses `fleet_manager` — `backend/fleet/manager.py:21-23`, **in-memory dicts** (`self._fleets: Dict[str, Fleet] = {}`). Only `repository.py` itself mentions the repository |
| **Tests** | **none** reference `FleetRepository` or `backend.fleet.repository` |
| **Concept** | Runtime-only (in-memory); the SQL models are an **accidental/aspirational** persistence layer that was never wired |

**Disposition: `RETIRE_MODEL`** (all four). Nothing can lose data that was never
written.

### 3.3 Workflow designer — 3 tables: `workflows`, `workflow_nodes`, `workflow_edges`

| | |
|---|---|
| **ORM** | `WorkflowModel`, `WorkflowNodeModel`, `WorkflowEdgeModel` — `models/workflow.py`, eager-imported (`__init__.py:15`) |
| **Migration lineage** | **None**, ever |
| **Head DB** | absent |
| **Repository** | `backend/workflow_designer/repository.py:14` `WorkflowRepository` — real SQLAlchemy code |
| **Runtime consumers** | **constructed nowhere.** `router_registry.py:1708` registers `backend.workflow_designer.routes`, which uses `workflow_engine` — `engine.py:17` `self._workflows: Dict[str, Workflow] = {}`, **in-memory**. `backend/api/workflow_routes.py:77` uses `InMemoryWorkflowRepository` from `contexts/workflow` — a *different* class sharing the `WorkflowRepository` name (a Protocol), the same trap as `MissionRepository` |
| **Tests** | **none** |
| **Concept** | Runtime-only; accidental SQL layer |

**Disposition: `RETIRE_MODEL`** (all three).

### 3.4 Cost intelligence — 3 tables: `cost_records`, `cost_provider_rates`, `cost_optimization_recommendations`. Stop condition 5.

| | |
|---|---|
| **ORM** | `CostRecordModel`, `ProviderRateModel`, `OptimizationRecommendationModel` — `models/cost_intelligence.py`, eager-imported (`__init__.py:3-7`) |
| **Migration lineage** | **None**, ever |
| **Head DB** | absent |
| **Repository** | `backend/cost_intelligence/repository.py:20` `CostRepository` — imports these models, real SQLAlchemy code |
| **Runtime consumers** | **`CostRepository(` is constructed nowhere** — not outside the package, not inside it. The `cost_intelligence` router is **not registered** in `router_registry.py` under any spelling. `routes.py`/`engine.py` in that package do not reference the repository |
| **Tests** | **none** |
| **Concept** | **A second "cost record" concept colliding with the live one.** `CostRecordModel` → `cost_records` (dead) vs `CostRecord` → `cost_tracking` (live, §4). Same word, different table, one of them real |

**Disposition: `RETIRE_MODEL`** (all three) — evidenced, but **stop condition 5
fired**: two tables claim one concept, and retiring the dead one is a decision
that should be taken knowing the live one is broken (§4).

---

## 4. Class B — migrated, unregistered, LIVE, and broken: `cost_tracking`. Stop conditions 3 and 6.

| | |
|---|---|
| **Migration lineage** | `0004_add_cost_tracking` (create), `0005` (add `updated_at`), `0006` (fix id type), `0007` (mention). **Owned by Alembic** |
| **Head DB** | **present** — 16 columns, 2 composite indexes (`ix_cost_tracking_mission_date`, `ix_cost_tracking_user_date`) |
| **ORM** | A model **exists**: `CostRecord`, `backend/database/models/cost_tracking.py:19`, `__tablename__ = "cost_tracking"` — but it is **not imported by `models/__init__.py`**, so it is **off `Base.metadata`**. That is why autogenerate proposes **`drop_table('cost_tracking')`** |
| **Runtime consumers** | **LIVE.** `backend/analytics/cost_engine.py` imports `CostRecord` lazily at six sites and **writes** through it (`record()`, line 138-162). `cost_engine` is registered in the DI container at `backend/main.py:448-450`; called by `backend/api/cost_routes.py` (5 endpoints), `backend/services/mission_runtime.py:326,1285`, `backend/mission_library/executor.py:220,278`, `enterprise_cost_anomaly_monitor.py:219`, `enterprise_recommendation_engine.py:590`. `core/data_retention.py:35` names it |
| **Model vs table** | **They disagree.** Reflected against the head DB: `mission_id` model `VARCHAR(36)` vs DB `VARCHAR(255)`; `user_id` `VARCHAR(128)` vs `VARCHAR(255)`; and the JSON column is **`extra_data` in the model** (`mapped_column("extra_data", JSONB)`, line 37) vs **`extra` in migration `0004:41`** (`sa.JSON`) |
| **Tests** | `test_cost_engine_provider_alias.py` and `test_cost_anomaly_monitor.py` — both **mock** `cost_engine`'s read methods; **nothing exercises the write path against a database** |

**Proven by execution** — the exact INSERT `cost_engine.record()` issues, against
the fresh head database, rolled back:

```
INSERT FAILED: ProgrammingError - (psycopg2.errors.UndefinedColumn)
  column "extra_data" of relation "cost_tracking" does not exist
rows in cost_tracking afterwards: 0
```

`cost_engine.record()` wraps this in `try/except Exception` and logs
`log.warning("cost_engine.record failed: %s", exc)` (line 173-174). **Every cost
record written by the mission runtime, the mission library and the cost routes
has been silently discarded on every migrated database.** Not this phase's to
repair; recorded as a live defect.

**Two hazards in one table:**
1. **Data-loss trap** (stop 6): applying the autogenerate output as-is would
   `DROP TABLE cost_tracking`.
2. **Conflicting definitions of a live table** (stop 3): the model and the
   migration disagree on names and lengths, and the model is the one that is
   wrong *and* the one that is used.

**Disposition: `RECONCILE`** — register the model and align it to migrations
`0004`–`0006` (Alembic owns the schema; the model must be corrected to match,
exactly as `MissionRecord` was in Phase 10.16). No migration is required for the
schema; the table is right. The model is not.

---

## 5. Class C — index-only drift (27 tables)

The ORM and the migrations agree on every column of these 27 tables and
disagree only on indexes. Two mechanisms, characterised programmatically
against the fresh head database:

| Mechanism | Tables | What autogenerate proposes |
|---|---|---|
| **Pure rename** — migration created `idx_<short>`; the model's `index=True` auto-names `ix_<table>_<column>` | 8 | drop one, create the other, same columns |
| **`index=True` never migrated** — the model marks single columns for indexing; migrations created composite or different indexes, or none | 19 | create the missing single-column `ix_*` indexes |
| **Expression indexes the ORM cannot declare** — IVFFlat (`embedding vector_cosine_ops`) and GIN full-text on `episodic_memory`, `semantic_memory`, `reflection_history` (the models say so in comments: *"not expressible in DDL here"*) | 3 (within the 19) | **`drop_index`** on the vector/FTS indexes |

The 27: `agent_configs`, `agent_states`, `billing_invoices`,
`billing_usage_records`, `connector_activity`, `connector_configs`,
`digital_twin_metrics`, `digital_twin_models`, `digital_twin_relationships`,
`embedding_cache` (plus its `embedding_cache_text_hash_key` unique constraint),
`episodic_memory`, `execution_events`, `executions`,
`governance_approval_requests`, `governance_compliance_rules`,
`governance_policies`, `knowledge_entries`, `knowledge_relationships`,
`learning_patterns`, `learning_sessions`, `mission_steps`, `missions_bc`,
`platform_feature_flags`, `platform_settings`, `reflection_history`,
`runtime_analytics`, `semantic_memory`.

**No data is affected by any of it.** But applying the output blindly would
**drop the pgvector and full-text indexes** on the three memory tables — a
performance regression on every similarity search, invisible to any test.

**Disposition: `RECONCILE`** (all 27) — **one convention decision**, not 27
decisions: either migrate the model's `index=True` intent (adding the `ix_*`
indexes and dropping duplicates), or align the models to the migration-created
names. In either case the expression indexes must be **protected** from
autogenerate via `include_object` in `env.py` — a configuration change this
brief forbids, correctly, since it belongs with the decision.

*(`governance_approval_requests`, `governance_compliance_rules` and
`governance_policies` are V1 `repositories/governance.py` tables, not durable
`cp_*` tables. They carry no authority — Phases 10.5–10.8 established that the
governed authority path never reads them. Index-only; not a governed-table
discrepancy.)*

---

## 6. Complete inventory

| ORM table | Model | Migration lineage | Exists at head | Runtime consumers | Owner | Disposition | Evidence |
|---|---|---|---|---|---|---|---|
| **`cp_approval`** | `approval_table` (DURABLE) | **none** | **no** | **`SqlApprovalRepository`, product approval queue — LIVE, GOVERNED** | Alembic (by ADR-109) | **ADD_MIGRATION** ⚠ STOP 1/4 | §3.1, readiness `ready:false` |
| `fleets` | `FleetModel` | none | no | none — routes use in-memory `fleet_manager` | — | RETIRE_MODEL | §3.2 |
| `fleet_agents` | `FleetAgentModel` | none | no | none | — | RETIRE_MODEL | §3.2 |
| `fleet_deployments` | `FleetDeploymentModel` | none | no | none | — | RETIRE_MODEL | §3.2 |
| `fleet_metrics_snapshots` | `FleetMetricsSnapshotModel` | none | no | none | — | RETIRE_MODEL | §3.2 |
| `workflows` | `WorkflowModel` | none | no | none — routes use in-memory `workflow_engine` | — | RETIRE_MODEL | §3.3 |
| `workflow_nodes` | `WorkflowNodeModel` | none | no | none | — | RETIRE_MODEL | §3.3 |
| `workflow_edges` | `WorkflowEdgeModel` | none | no | none | — | RETIRE_MODEL | §3.3 |
| `cost_records` | `CostRecordModel` | none | no | none — `CostRepository` never built, router unregistered | — | RETIRE_MODEL ⚠ STOP 5 | §3.4 |
| `cost_provider_rates` | `ProviderRateModel` | none | no | none | — | RETIRE_MODEL | §3.4 |
| `cost_optimization_recommendations` | `OptimizationRecommendationModel` | none | no | none | — | RETIRE_MODEL | §3.4 |
| **`cost_tracking`** | `CostRecord` (**unregistered, mismatched**) | `0004`, `0005`, `0006` | **yes** | **`cost_engine` — LIVE, write path BROKEN** | Alembic | **RECONCILE** ⚠ STOP 3/6 | §4, `UndefinedColumn` |
| 27 index-drift tables (§5) | various | `0001`–`0009` | yes | various V1 | Alembic | RECONCILE (one decision) | §5 |

**Tally:** ADD_MIGRATION **1** · RETIRE_MODEL **10** · RECONCILE **28** ·
KEEP_MODEL 0 · KEEP_MIGRATION 0 · RETIRE_TABLE 0 · STOP_ARCHITECTURAL_DECISION 0
— **39 tables**.

---

## 7. Architecture check — governed tables

| Governed area | Touched? |
|---|---|
| tenant (`cp_tenant`), membership (`cp_tenant_membership`) | **no** — migrated `0022`, `0021`; no drift |
| authority (`cp_authority_grant`) | **no** — `0020`; no drift |
| **approval (`cp_approval`)** | **YES — absent from every migrated database. Stop condition 1.** |
| execution (`cp_execution`, `cp_queue`, `cp_idempotency`, `cp_outbox`) | **no** — `0010`/`0011` |
| autonomy | no table; not touched |
| worker (`cp_worker`, `cp_binding`) | **no** — `0010` |
| credentials | no durable table; not touched |
| provider connectors (`cp_connector_config`) | **no** — `0012` |

Exactly one governed table is affected, and it is the one that authorises every
irreversible action.

---

## 8. Stop conditions

| # | Condition | Result |
|---|---|---|
| 1 | A discrepancy affects a governed table | **FIRED — `cp_approval`** (§3.1) |
| 2 | Intended owner cannot be established | No — Alembic, per ADR-109, for every table; the *question* is whether each table should exist |
| 3 | A table has conflicting production concepts | **FIRED — `cost_tracking`**: model and migration disagree on a live table (§4) |
| 4 | A migration appears missing but the schema is relied upon | **FIRED — `cp_approval`**: readiness `ready:false`, consumer live (§3.1) |
| 5 | A model represents a different table with the same concept | **FIRED — `CostRecordModel`→`cost_records` vs `CostRecord`→`cost_tracking`** (§3.4) |
| 6 | Resolving incorrectly could cause data loss | **FIRED — autogenerate proposes `drop_table('cost_tracking')`** (§4), and would drop the pgvector/FTS indexes (§5) |
| 7 | Fresh and existing database disagree unexpectedly | No — identical (§1) |
| 8 | Autogenerate not deterministically reproducible | No — two runs identical apart from the message string (§0) |
| 9 | The ~15-table count is materially wrong | **FIRED — 39 tables, 135 upgrade operations** |
| 10 | A supposed dead model has an actual runtime consumer | No — every model classified dead (fleet, workflow, cost_intelligence) was proven to have no constructor, no registered route and no test |

**Six of ten fired. No implementation may proceed on this discovery alone.**

---

## 9. Two live defects found, neither repaired

1. **Production cannot become ready** — `cp_approval` is not created by any
   migration, and the production persistence builder refuses to create schema.
   Proven by `verify_durability` (§3.1). Every harness since Phase 10.3 used the
   development builder, which is why the platform's own fail-closed readiness
   check was never seen to fail.
2. **Cost tracking silently discards every write** — `UndefinedColumn
   "extra_data"`, caught and logged at `warning` (§4). No test covers the write
   path; both existing tests mock the read methods.

---

## 10. Known limitations

1. **No production or staging database was inspected**; readiness was proven
   against a database built by this repository's own migrations, which is what
   production is defined to be by ADR-109/110.
2. **Runtime-consumer conclusions rest on static search** — constructors,
   imports, route registration, tests. A dynamically-constructed
   `FleetRepository` would evade it. The three dead groups also have no
   registered route and no test, which is stronger than any single signal.
3. **The 19 "index=True never migrated" tables were classified
   programmatically**; individual index intent was not reviewed. It is
   index-only drift by construction — every column matched.
4. **`cost_tracking`'s `extra` column is `sa.JSON` in `0004` and `JSONB` in the
   model** — a type difference beyond the name mismatch, noted for the
   reconciliation.
5. **The disposable database was dropped after capture.** All evidence files
   (`drift_*.py`, `drift_*.json`, both autogenerate revisions, the check log)
   remain in the session scratchpad.
6. **`ApprovalRequestRepository` / `governance_approval_requests`** (V1) shares a
   word with `cp_approval` and was checked: it is index-only drift and carries
   no authority.

---

## 11. Next

Not started. In dependency order:

1. **Authorise and add the `cp_approval` migration** — one `create_table`
   copied from `approval_table` on `DURABLE_METADATA`, exactly as its 24
   siblings were done. Governed; needs explicit sign-off. Highest priority: it
   is the difference between production being ready and not.
2. **Reconcile `cost_tracking`** — register `CostRecord`, correct it to
   `0004`–`0006` (`extra`, lengths, JSON), and add a write-path test. Repairs
   the silent data loss.
3. **Retire the ten dead models** (fleet 4, workflow 3, cost_intelligence 3) —
   after confirming, with the product owner, that the in-memory managers are the
   intended persistence.
4. **Decide the index convention** once, protect the expression indexes via
   `include_object`, and apply it across the 27 tables.

After 1–4, `alembic check` becomes a working drift detector. Before them it is
unblocked but not yet useful, exactly as ADR-111 said.
