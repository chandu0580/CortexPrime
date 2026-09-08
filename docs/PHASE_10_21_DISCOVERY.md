# Phase 10.21 — Dead ORM Model Retirement: Discovery
## DISCOVERY ONLY — no file deleted, no import altered, no migration, no schema change

**STATUS:** discovery complete. **None of the eleven stop conditions fired.** One
finding outside them outranks the question the phase was asked, and is the
headline.

**The ten candidates are not in the repository.** All three model files, all
three SQL repositories, and the entire `backend/cost_intelligence/` package are
listed in `.gitignore` under *"v2.0 Phase 1 components — not part of v1.0.0
GA"*, added by the GA-preparation commit `9d15d77`. **The same commit made the
tracked `backend/database/models/__init__.py` import all three ignored model
files.** Proven on a clean checkout of `HEAD`: `import backend.database.models`,
`alembic current`, and the boot dependency chain all fail with
`ModuleNotFoundError: backend.database.models.cost_intelligence`.

**The repository as committed cannot import its own models, run its own
migrations, or boot from a fresh clone.** Every verification in Phases
10.14–10.20 ran from this working tree, which carries the ignored files. That is
why nothing noticed.

Every claim below was produced by running something or reading a specific,
cited file.

---

## 1. Numbers

| | |
|---|---|
| Candidates | **10** — fleet ×4, workflow-designer ×3, cost-intelligence ×3 |
| Tracked by git | **0 of 10** (all three model files gitignored, `9d15d77`) |
| Tracked SQL repositories | **0 of 3** (`fleet/repository.py`, `workflow_designer/repository.py`, `cost_intelligence/repository.py` — all gitignored) |
| Constructed anywhere (tracked or ignored) | **0 of 3** |
| Migrations creating any candidate table | **0** |
| Candidate tables in a fresh head DB / existing head DB | **0 / 0** of 10 |
| FKs into a candidate from outside the group | **0** (five FKs, all internal: `fleet_*`→`fleets`, `workflow_*`→`workflows`) |
| Tracked importers of the ten class names (besides the registry) | **0** |
| Tests referencing the ten models, three repositories, or v2 routes | **0** (five hits are isolation guards that *forbid* importing `backend.workflow_designer`) |
| Frontend / built bundle callers of `/api/v2/{fleets,workflows,costs}` | **0** |
| Alembic baseline (post-10.20, re-confirmed byte-identical) | **129** op lines |
| Simulated removal impact | **43** op lines disappear (fleet 18, workflow 14, cost-intelligence 11); **86** remain; no other op touches a candidate |
| Provider writes | **0** |

---

## 2. The headline — proven on a clean checkout

A git worktree of `HEAD` was created in the scratchpad (and removed afterwards):

```
absent  backend/database/models/fleet.py
absent  backend/database/models/workflow.py
absent  backend/database/models/cost_intelligence.py
absent  backend/fleet/repository.py
absent  backend/workflow_designer/repository.py
absent  backend/cost_intelligence/engine.py

PROBE 1  python -c "import backend.database.models"
         ModuleNotFoundError: No module named 'backend.database.models.cost_intelligence'
PROBE 2  alembic current            (env.py:32 does `import backend.database.models`)
         ModuleNotFoundError: No module named 'backend.database.models.cost_intelligence'
PROBE 3  python -c "import backend.database.engine, backend.database.models"
         ModuleNotFoundError: No module named 'backend.database.models.cost_intelligence'
```

`.gitignore:109-123`:

```
# v2.0 Phase 1 components — not part of v1.0.0 GA
backend/cost_intelligence/
backend/executive_analytics/
backend/policy_simulation/
backend/governance/policy_engine.py
backend/fleet/repository.py
backend/workflow_designer/repository.py
backend/workflow_designer/templates.py
backend/mcp/connectors/
backend/database/models/cost_intelligence.py
backend/database/models/fleet.py
backend/database/models/workflow.py
cortexprime-agent-sdk/
frontend/lib/agent-sdk/
```

`git show 9d15d77:backend/database/models/__init__.py` already contained the
three imports. **The ignore rules and the imports that break under them were
authored in the same commit.**

**Tracked files importing an ignored module** (`git ls-files | xargs grep`):

| Tracked file | Ignored module | Reach |
|---|---|---|
| `backend/database/models/__init__.py` | `models.fleet`, `models.workflow`, `models.cost_intelligence` | **boot, `alembic env.py`, `init_db()`, 20 tracked test modules, 3 architecture tests** |
| `backend/governance/__init__.py:1` | `governance.policy_engine` | `backend.agent_sdk` only — not on the boot path or `router_registry` |

(`backend/api/enterprise_analytics_routes.py` matched the search on a local
variable named `executive_analytics`; it imports nothing ignored.)

**CI exposure [NOT VERIFIED — inferred from the workflows]:** both
`architecture.yml` and `test.yml` use plain `actions/checkout@v4`, which does not
carry ignored files. Twenty tracked test modules and three `tests/architecture`
modules import `backend.database.models` or its dependents. On a clean checkout
those collections cannot import. CI results were not observable from here; the
mechanism is.

---

## 3. Persistence intent — established three ways, not inferred

**The design says persist.** `docs/CORTEXPRIME_V2_STRATEGIC_DESIGN.md:222-226`:

| Component | Storage |
|---|---|
| Fleet Manager | PostgreSQL + Redis |
| NL Workflow Designer | PostgreSQL (persistence) + WebSocket |
| Cost Intelligence | PostgreSQL (timeseries) + Redis |

Roadmap (`:648-650`): Fleet + Workflow Designer are *v2.0 Phase 1*; Cost
Intelligence is *v2.0 Phase 2*.

**The repository says "not yet."** The `.gitignore` block excludes exactly the
persistence layer — the ORM models and the SQL repositories — while the
in-memory managers, dataclasses and routes ship.

**The code says in-memory, today.** `fleet/manager.py:21-23`
(`self._fleets: Dict[str, Fleet] = {}` …), `workflow_designer/engine.py:17`,
`cost_intelligence/engine.py:22-24` — dict/list attributes, no session, no
repository, no persistence statement, no TODO. `cost_intelligence/engine.py`
imports only its own dataclasses.

**Proven by execution (probe B)** — the shipped routers, over HTTP, with
`require_user` overridden:

```
POST /api/v2/fleets    -> 200        GET /api/v2/fleets    -> 200  fleets listed: 1
POST /api/v2/workflows -> 200        GET /api/v2/workflows -> 200  workflows listed: 1
state lives in the module singleton dicts: 1 fleet(s), 1 workflow(s)
a FRESH FleetManager()/WorkflowEngine() sees: 0 fleet(s), 0 workflow(s)  -> process-local
routes/managers reference SQLAlchemy/session/repository: False
```

**Classification: deliberately deferred v2.0 persistence, unreleased.** Not
dead design — the design document plans it — and not "intentionally in-memory"
as an end state. The ORM models are an unshipped future layer whose only
current effect is to be imported by a shipped registry.

---

## 4. Per-candidate evidence

Common to all ten unless stated: on `Base.metadata` only (not
`DURABLE_METADATA`, no other collection); exported in `models/__init__.__all__`;
imported by **no** tracked file other than the registry; no migration; absent
from both databases; no test; no frontend, bundle, script or DI reference.

### 4.1 Fleet — `FleetModel`, `FleetAgentModel`, `FleetDeploymentModel`, `FleetMetricsSnapshotModel`

| | |
|---|---|
| File | `backend/database/models/fleet.py` — **gitignored** |
| Tables | `fleets`, `fleet_agents`, `fleet_deployments`, `fleet_metrics_snapshots`; three FKs → `fleets.id` (CASCADE), all internal |
| Repository | `backend/fleet/repository.py` `FleetRepository` — **gitignored**; `FleetRepository(` constructed **nowhere** |
| Runtime | `backend/fleet/routes.py` (tracked, `/api/v2/fleets`, registered in `router_registry.py:1691` with a health fallback) → `fleet_manager`, in-memory |
| Probe A | `FleetRepository(session).list_fleets()` on a migrated DB → `UndefinedTableError` |
| Alembic | 6 op lines (`create_table` + 5 `create_index`) |
| Public contract | route family exists and serves dataclasses; the ORM model is not in any response |

### 4.2 Workflow designer — `WorkflowModel`, `WorkflowNodeModel`, `WorkflowEdgeModel`

| | |
|---|---|
| File | `backend/database/models/workflow.py` — **gitignored** |
| Tables | `workflows`, `workflow_nodes`, `workflow_edges`; two FKs → `workflows.id` (CASCADE), internal |
| Repository | `backend/workflow_designer/repository.py` `WorkflowRepository` — **gitignored**; constructed **nowhere** (every `WorkflowRepository(` hit is `InMemoryWorkflowRepository` from `contexts/workflow`, a different class) |
| Runtime | `backend/workflow_designer/routes.py` (tracked, `/api/v2/workflows`, registered `:1708`) → `workflow_engine`, in-memory |
| Probe A | `list_workflows()` → `UndefinedTableError` |
| Alembic | 6 + 3 + 5 = **14** op lines |
| Note | `workflow.py:47-53` records a `String(64)`→UUID FK fix "surfaced by the first real application boot against an Alembic-built PostgreSQL (Phase 5.14)" — evidence these models were once created by `create_all` in a developer database, never by a migration |
| Tests | `"backend.workflow_designer"` appears in five bounded-context tests **as a forbidden import** — a prohibition on the package name, unaffected by model removal |

### 4.3 Cost intelligence — `ProviderRateModel`, `CostRecordModel`, `OptimizationRecommendationModel` (special case)

| | |
|---|---|
| File | `backend/database/models/cost_intelligence.py` — **gitignored**, as is the **entire** `backend/cost_intelligence/` package (5 files: `__init__`, `engine`, `models`, `repository`, `routes`) |
| Tables | `cost_provider_rates`, `cost_records`, `cost_optimization_recommendations`; no FKs |
| Repository | `CostRepository` — constructed **nowhere**; `cost_intelligence/engine.py` imports only its dataclasses |
| Runtime | `cost_intelligence/routes.py` (`/api/v2/costs`) is **not mounted anywhere in tracked code**; only `legacy_persistence_inventory.py` and the registry mention the package |
| Probe A | `get_provider_rates()` → `UndefinedTableError` |
| Alembic | 3 + 7 + 1 = **11** op lines |
| Why it exists | v2.0 Phase 2 "Cost Optimization Intelligence" (`V2_STRATEGIC_DESIGN.md §7.4`): multi-provider rate cards, org-scoped cost timeseries, optimization recommendations |

**`CostRecordModel → cost_records` vs `CostRecord → cost_tracking` — clearly
distinct (stop condition 5 clear):**

```
cost_records only  : agent_type, category, cost NUMERIC(12,6), input_tokens, org_id, output_tokens, timestamp
cost_tracking only : completion_tokens, cost_usd FLOAT, created_at, extra, prompt_tokens, report_date,
                     service, session_id, total_tokens, units, updated_at, user_id
shared names       : id, mission_id, model, provider
```

`cost_tracking` is the v1.0 per-call metering ledger, live, written by
`cost_engine` (Phase 10.20). `cost_records` is the v2.0 org-scoped,
category-typed, `Decimal` timeseries design — a different concept with a
different owner, not a duplicate of the same one. **Nothing consumes it today;
it is not dead — it is unreleased.** Deleting the file would erase a designed
v2.0 contract; but the file is not in the repository to delete.

---

## 5. Alembic — simulated, files unchanged

```
BASELINE (post-10.20) upgrade op lines: 129
  fleets 6 · fleet_agents 4 · fleet_deployments 4 · fleet_metrics_snapshots 4
  workflows 6 · workflow_nodes 3 · workflow_edges 5
  cost_records 7 · cost_provider_rates 3 · cost_optimization_recommendations 1
SIMULATED REMOVAL IMPACT: 43 would disappear; 86 would remain (the 27 index-drift tables)
other op lines touching candidates: none
after (no files changed): 129 op lines; identical to baseline: True
```

Removing any candidate changes exactly its own `create_table` and
`create_index` lines and nothing else — stop condition 9 clear. The disposable
revision was captured and deleted; the migrations directory is clean.

---

## 6. Database

| | fresh (`alembic upgrade head`, 24 migrations, 56 tables) | existing (`cortex_p1014_legacy`, `0024`) |
|---|---|---|
| candidate tables present | 0 of 10 | 0 of 10 |
| FKs referencing a candidate | 0 | 0 |
| rows | n/a — no table | n/a — no table |

No durable data exists anywhere for any candidate; there is nothing whose
ownership could be unresolved. (Disposable counts are not generalised: a
deployed database *cannot* have these tables either, since no migration creates
them and the production builder refuses `create_all`.)

---

## 7. Classification

| Model | Runtime consumer | Migration | DB table | Metadata | Public contract | Disposition |
|---|---|---|---|---|---|---|
| `FleetModel` | none — routes use in-memory `fleet_manager` | none | absent | `Base` (file gitignored) | `__all__` export only; no importer | **DEREGISTER** (RETIRE_MODEL from the tracked registry; file untouched — it is not repository content) |
| `FleetAgentModel` | none | none | absent | `Base` | same | DEREGISTER |
| `FleetDeploymentModel` | none | none | absent | `Base` | same | DEREGISTER |
| `FleetMetricsSnapshotModel` | none | none | absent | `Base` | same | DEREGISTER |
| `WorkflowModel` | none — routes use in-memory `workflow_engine` | none | absent | `Base` | same | DEREGISTER |
| `WorkflowNodeModel` | none | none | absent | `Base` | same | DEREGISTER |
| `WorkflowEdgeModel` | none | none | absent | `Base` | same | DEREGISTER |
| `ProviderRateModel` | none — package unmounted, engine in-memory | none | absent | `Base` | same | DEREGISTER |
| `CostRecordModel` | none — distinct from live `cost_tracking` | none | absent | `Base` | same | DEREGISTER |
| `OptimizationRecommendationModel` | none | none | absent | `Base` | same | DEREGISTER |

**"DEREGISTER" is precise where "RETIRE_MODEL" would mislead.** The files are
already outside the repository by deliberate decision; there is nothing to
retire *from* it. The defect is that the tracked registry imports and exports
them. Removing the three import statements and the ten `__all__` entries from
`backend/database/models/__init__.py` makes the shipped repository
self-consistent, restores clean-clone import, migration and boot, removes
exactly 43 Alembic operations, and changes no shipped behaviour — nothing
imports the names.

**The alternative is a v2.0 decision, not a cleanup:** un-ignore the persistence
layer and ship it, which requires migrations for ten tables and belongs to the
v2.0 Phase 1/2 work the design document schedules. Deregistering now does not
foreclose it; the ignored files are unaffected.

---

## 8. Stop conditions

| # | Condition | Result |
|---|---|---|
| 1 | Live production consumer | **No** — probe A: the repositories cannot run; probe B: routes are in-memory |
| 2 | Required by a public API contract | **No** — the v2 routes serve dataclasses; the ORM models appear in no response; `__all__` has no importer |
| 3 | Durable data with unresolved ownership | **No** — no table exists anywhere |
| 4 | Unclassified FK | **No** — five FKs, all internal to the group |
| 5 | `CostRecordModel` vs `cost_tracking` indistinguishable | **No** — §4.3 |
| 6 | Persistence intent unestablished | **No** — design doc, `.gitignore`, code, probe B |
| 7 | Removal needs a schema decision outside this phase | **No** for deregistration; **yes** for shipping them — which is not proposed |
| 8 | Dynamic use defeating static analysis | **No** — probes executed; no DI, scheduler, worker or plugin reference |
| 9 | Removing one changes unrelated Alembic ops | **No** — exactly 43, no cross-references |
| 10 | Provider write | **No** — 0 |
| 11 | Vacuous verification | **No** — clean-checkout probe, repository probe, HTTP probe all executed |

**None fired.** The clean-clone breakage (§2) is outside the listed conditions
and is reported as the primary finding.

---

## 9. Known limitations

1. **CI status was not observed.** §2's CI exposure is derived from the
   workflow files and the import graph, not from a CI run.
2. **No production or staging database was inspected**; none can hold these
   tables by construction (no migration; production refuses `create_all`).
3. **The `governance/policy_engine.py` ignored import** is the same defect class
   and is outside this phase's ten models. Reported, not classified further.
4. **The V2 design document is the only statement of persistence intent for the
   future**; it schedules the work, it does not commit to the current model
   shapes. Deregistration preserves the files for that decision.
5. **`backend/workflow_designer/templates.py`** is also gitignored and was not
   examined beyond noting it; no tracked file imports it.
6. Disposable databases and the clean worktree were removed after evidence
   capture.

---

## 10. Next

Not started. **Deregister the ten models from the tracked registry** — three
import lines and ten `__all__` entries in `backend/database/models/__init__.py`
— then prove on a clean checkout that `import backend.database.models`,
`alembic upgrade head` and boot succeed; autogenerate drops from 129 to 86;
the `governance/__init__.py` ignored import is the same defect and should be
decided alongside. The ignored files themselves are not touched; whether to
ship them is the v2.0 Phase 1/2 decision the design document already owns.
