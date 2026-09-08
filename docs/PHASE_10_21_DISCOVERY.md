# Phase 10.21 — Dead ORM Model Retirement: Discovery
## DISCOVERY ONLY — no file deleted, no import altered, no migration, no schema change, no test changed

> **Issuance note.** This phase was executed and committed as `65951e5` (ADR-115),
> then re-issued with a stricter brief: an explicit twenty-question checklist, a
> fixed disposition vocabulary, a new stop condition 12 (governed
> infrastructure), explicit dynamic-reachability and public-contract sweeps, the
> `alembic check` baseline, the designer→engine→runtime trace, and the fleet
> state lifecycle. This document supersedes the first issue; every claim below
> rests on evidence captured in one of the two runs, both from the same clean
> tree. **Phase-number collision recorded:** 10.17 was used twice earlier
> (ADR-109, ADR-112), and 10.21 is now issued twice (this document is the second).

**STATUS:** discovery complete. **All twelve stop conditions PASS.** One finding
outside them outranks the question the phase was asked, and is the headline.

---

## 0. Headline — the candidates are not in the repository, and the registry that imports them is

**All ten candidates are gitignored.** `.gitignore:109-123`, under *"v2.0 Phase 1
components — not part of v1.0.0 GA"* (GA-preparation commit `9d15d77`), excludes
the three model files, the three SQL repositories, and the entire
`backend/cost_intelligence/` package. **The same commit made the tracked
`backend/database/models/__init__.py` import all three ignored model files.**

Proven on a clean git worktree of `HEAD` (created in the scratchpad, removed
afterwards):

```
absent  backend/database/models/{fleet,workflow,cost_intelligence}.py
absent  backend/fleet/repository.py   backend/workflow_designer/repository.py   backend/cost_intelligence/engine.py

python -c "import backend.database.models"     -> ModuleNotFoundError: No module named 'backend.database.models.cost_intelligence'
alembic current   (env.py:32 imports the models package)   -> same ModuleNotFoundError
python -c "import backend.database.engine, backend.database.models"       -> same
```

**The repository as committed cannot import its own models, run its own
migrations, or boot from a fresh clone.** Every verification in Phases
10.14–10.20 ran from this working tree, which carries the ignored files — which
is why nothing noticed. CI checks out with plain `actions/checkout@v4`; twenty
tracked test modules and three `tests/architecture` modules import the models
package, so their collection fails on a clean checkout by construction (CI
results not observed from here). `backend/governance/__init__.py:1` imports the
ignored `governance/policy_engine.py` — the same defect class, reaching only
`backend.agent_sdk`, not the boot path.

---

## 1. Persistence intent — established three ways, not inferred

| Source | Says |
|---|---|
| **Design** — `docs/CORTEXPRIME_V2_STRATEGIC_DESIGN.md:222-226, 648-650` | Fleet Manager: *PostgreSQL + Redis*. NL Workflow Designer: *PostgreSQL (persistence)*. Cost Intelligence: *PostgreSQL (timeseries)*. Fleet + Designer = v2.0 Phase 1; Cost Intelligence = v2.0 Phase 2 |
| **Repository** — `.gitignore:109-123` | the persistence layer (ORM models + SQL repositories) is excluded from v1.0 GA; the in-memory managers, dataclasses and routes ship |
| **Code** — `fleet/manager.py:21-23`, `workflow_designer/engine.py:17`, `cost_intelligence/engine.py:22-24`, `fleet/health.py:13` | `Dict`/`List` attributes on module singletons; no session, no repository, no persistence statement, no TODO |
| **Execution** — probe B, the shipped routers over HTTP with `require_user` overridden | `POST/GET /api/v2/fleets → 200, 1 listed`; `POST/GET /api/v2/workflows → 200, 1 listed`; state in the singleton dicts; a fresh `FleetManager()`/`WorkflowEngine()` sees **0**; routes and managers reference SQLAlchemy/session/repository: **False** |

**Classification: the planned v2.0 persistence layer, deliberately held out of
the v1.0 repository, with the in-memory managers as the shipped placeholder.**
Not dead design, and not "intentionally in-memory" as an end state — deferred
and unreleased. Persistence is intentionally *absent* today (stop 19: yes,
documented).

---

## 2. Twenty questions, answered per group

Common to all ten: on `Base.metadata` only (not `DURABLE_METADATA`, no other
collection); exported by `models/__init__.__all__`; imported by **no tracked
file** other than that registry; no migration; absent from both databases; no
test; no frontend, bundle, script, DI, scheduler, worker, plugin or CLI
reference; no `response_model`; the ORM `to_dict()` serializers are never
called because nothing imports the classes.

| # | Question | Fleet ×4 | Workflow-designer ×3 | Cost-intelligence ×3 |
|---|---|---|---|---|
| 1 | Genuinely unused? | **yes** | **yes** | **yes** (see §4 for `CostRecordModel`) |
| 2 | Intentionally in-memory? | the shipped *manager* is; the ORM is deferred persistence | same | same |
| 3 | Represents durable persistence? | designed to, in v2.0; not shipped | same | same |
| 4 | Migration creates its table? | **no** | **no** | **no** |
| 5 | Table exists in a real migrated DB? | **no** (fresh and existing) | **no** | **no** |
| 6 | In SQLAlchemy metadata? | `Base` — because the tracked registry imports the ignored file | same | same |
| 7 | Production code instantiates it? | **no** — only `fleet/repository.py`, gitignored, constructed nowhere | **no** | **no** |
| 8 | Production code queries it? | **no** | **no** | **no** |
| 9 | Repository uses it? | `FleetRepository` (gitignored) — **never constructed** | `WorkflowRepository` (gitignored) — never constructed; every `WorkflowRepository(` hit is `InMemoryWorkflowRepository` from `contexts/workflow` | `CostRepository` (gitignored) — never constructed, not even inside its package |
| 10 | Service/manager depends on it? | `FleetManager` → dicts; `FleetHealthMonitor` → `_snapshots` dict, on-demand, no loop | `WorkflowEngine` → dict; `WorkflowCompiler` → returns a `mission_def` dict to the HTTP caller | `CostIntelligenceEngine` → lists/dicts; imports only its dataclasses |
| 11 | API route depends on it? | `/api/v2/fleets` (tracked, registered `router_registry.py:1691` with health fallback) → manager, dataclass `to_dict` | `/api/v2/workflows` (registered `:1708`) → engine | `/api/v2/costs` — file gitignored, **mounted nowhere** |
| 12 | Background job / worker? | **none** — `fleet_health_monitor` has no loop and no start call | **none** | **none** |
| 13 | DI registers it? | **no** `container.register` | no | no |
| 14 | Test depends on it? | **no** | **no** — five hits are isolation guards that *forbid* importing `backend.workflow_designer` | **no** |
| 15 | Public import/API contract? | `__all__` export, **no importer**; route responses are dataclasses | same | same; no route at all |
| 16 | FK references its table? | `fleet_*→fleets.id` CASCADE ×3, **all internal** | `workflow_*→workflows.id` CASCADE ×2, internal | none |
| 17 | Removal changes Alembic ops? | exactly **18** | exactly **14** | exactly **11** — and nothing else (§6) |
| 18 | Removal changes runtime behaviour? | **no** — nothing imports the names | no | no |
| 19 | Persistence intentionally absent? | **yes** — §1 | yes | yes |
| 20 | Safe to classify for a later phase? | **yes** | **yes** | **yes** |

---

## 3. Special case — Fleet

**Subsystem:** purely in-memory. `FleetManager` (`fleet/manager.py:21-23`) holds
`_fleets`, `_agents`, `_deployments` dicts; `FleetHealthMonitor`
(`fleet/health.py:13`) holds `_snapshots` and exposes `compute_snapshot`,
`get_snapshot`, `get_fleet_health_status` — **on-demand computation, no
`while True`, no `create_task`, and no start call anywhere in tracked code**.
State lifecycle: created by `POST /api/v2/fleets`, lives for the process,
gone on restart (probe B). Not backed by any other durable model. Not using the
candidate models dynamically (§5). Intended to be persistent per the V2 design;
currently deliberately not.

**Runtime probe A** — `FleetRepository(session).list_fleets()` with a real
`AsyncSession` on a migration-built database → **`UndefinedTableError`**. The
repository cannot function anywhere Alembic builds the schema.

---

## 4. Special case — Workflow designer

**Trace:** designer route (`POST /api/v2/workflows`, `add_node`, `add_edge`) →
`Workflow`/`WorkflowNode`/`WorkflowEdge` **dataclasses** in
`workflow_designer/models.py` → `WorkflowEngine._workflows` dict →
`WorkflowCompiler.compile()` → a **plain `mission_def` dict** (`steps`,
`approval_gates`, `branches`) → **returned to the HTTP caller**. It is handed to
no runtime: `workflow_designer` never imports `contexts/workflow` or
`approval_center`, and neither imports it back (the `compile_workflow` hits in
`contexts/workflow/application/service.py:155` and `api/workflow_routes.py:397`
are the governed context's own method). The models are **unused ORM persistence
for a frontend-facing design structure** — neither persisted workflows nor
runtime workflow structures. `workflow.py:47-53` records a `String(64)`→UUID FK
fix "surfaced by the first real application boot against an Alembic-built
PostgreSQL (Phase 5.14)": evidence these models were once created by
`create_all` in a developer database, never by a migration.

**Runtime probe A** — `WorkflowRepository(session).list_workflows()` →
**`UndefinedTableError`**.

---

## 5. Special case — Cost intelligence, and `CostRecordModel → cost_records`

**The whole package is gitignored** (`__init__`, `engine`, `models`,
`repository`, `routes`). `routes.py` (`/api/v2/costs`) is mounted nowhere in
tracked code; `engine.py` imports only its own dataclasses; `CostRepository` is
constructed nowhere, not even inside the package.

**Why it exists:** v2.0 Phase 2 "Cost Optimization Intelligence"
(`V2_STRATEGIC_DESIGN.md §7.4`) — multi-provider rate cards
(`cost_provider_rates`), an org-scoped cost timeseries (`cost_records`), and
optimization recommendations.

**`CostRecordModel → cost_records` vs `CostRecord → cost_tracking`** — compared
column by column, not by name:

```
cost_records only  : agent_type, category, cost NUMERIC(12,6), input_tokens, org_id, output_tokens, timestamp
cost_tracking only : completion_tokens, cost_usd FLOAT, created_at, extra, prompt_tokens, report_date,
                     service, session_id, total_tokens, units, updated_at, user_id
shared names       : id, mission_id, model, provider
```

`cost_tracking` is the v1.0 per-call metering ledger, **live**, written by
`cost_engine` (repaired in Phase 10.20). `cost_records` is the v2.0 org-scoped,
category-typed, `Decimal` timeseries design. **An intentionally separate
concept — not an abandoned attempt at the same one, not an obsolete duplicate.**
Not part of any contract (no importer, no route, no schema, no frontend type),
not referenced dynamically (§6), expected by no runtime component. A fourth
class named `CostRecord` — a dataclass — lives in `cost_intelligence/models.py`.
The two concepts are **not merged** and remain clearly distinguishable
(stop 5 PASS).

**Runtime probe A** — `CostRepository(session).get_provider_rates()` →
**`UndefinedTableError`**.

---

## 6. Dynamic reachability — ruled out

Searched all of `backend/` for `importlib`, `__import__`, `import_module`,
`getattr(...models`, `globals()[`, `Base.registry`, `class_registry`,
`MODEL_MAP`/`model_map`/`MODEL_REGISTRY`/`TABLE_MAP`, and every candidate class
and table name as a **string literal**.

- Class-name strings occur **only** in `models/__init__.__all__`; table-name
  strings **only** in the model files' `__tablename__`.
- The single variable-target import in the backend is
  `application_runtime.py:310`, driven by `CORTEX_CONNECTOR_FACTORIES` — empty by
  default, explicit deployment configuration, and its factories must return
  connector/credential providers. It names no candidate; no config file names
  one.
- `backend/platform/architecture/boundary_rules.py:974-1012` **forbids**
  dynamic imports in governed code, and the gate is green.
- Every `__import__(...)` elsewhere is a constant stdlib/sqlalchemy name.

**Result: no dynamic path can reach any candidate.** Stop 8 PASS.

---

## 7. DATABASE

**Fresh Alembic database** — `cortex_p1021_fresh`, created empty,
`alembic upgrade head`: 24 migrations, `0024_approval_store`, **56 tables**.
**Existing migrated database** — `cortex_p1014_legacy`, `0024_approval_store`,
56 tables. Neither altered after evidence capture; the fresh one dropped.

| Table | Exists (fresh / existing) | Migration / revision | Rows | FK references | Indexes declared by model | Metadata | In current durable schema |
|---|---|---|---|---|---|---|---|
| `fleets` | no / no | **none** | n/a | none in | `idx_fleet_org`, `idx_fleet_org_name` (unique), `idx_fleet_status`, + `index=True` ×2 | `Base` | no |
| `fleet_agents` | no / no | none | n/a | → `fleets.id` CASCADE | `idx_fleet_agent_fleet`, `idx_fleet_agent_status`, + `index=True` | `Base` | no |
| `fleet_deployments` | no / no | none | n/a | → `fleets.id` CASCADE | `idx_fleet_dep_fleet`, `idx_fleet_dep_status`, + `index=True` | `Base` | no |
| `fleet_metrics_snapshots` | no / no | none | n/a | → `fleets.id` CASCADE | `idx_fleet_metrics_fleet`, `idx_fleet_metrics_time`, + `index=True` | `Base` | no |
| `workflows` | no / no | none | n/a | none in | `idx_workflow_org`, `idx_workflow_org_name` (unique), `idx_workflow_status`, + `index=True` ×2 | `Base` | no |
| `workflow_nodes` | no / no | none | n/a | → `workflows.id` CASCADE | `idx_wf_node_workflow`, + `index=True` | `Base` | no |
| `workflow_edges` | no / no | none | n/a | → `workflows.id` CASCADE | `idx_wf_edge_source`, `idx_wf_edge_target`, `idx_wf_edge_workflow`, + `index=True` | `Base` | no |
| `cost_records` | no / no | none | n/a | none | `idx_cost_record_{category,mission,org,time}`, + `index=True` ×2 | `Base` | no |
| `cost_provider_rates` | no / no | none | n/a | none | `idx_cost_rate_effective`, `idx_cost_rate_provider_model` | `Base` | no |
| `cost_optimization_recommendations` | no / no | none | n/a | none | none | `Base` | no |

FKs *into* any candidate from outside the group: **0** in both databases and in
every tracked model or durable table. No durable data exists anywhere for any
candidate (no migration creates the tables and production refuses `create_all`,
so a deployed database cannot have them either — disposable counts are not
generalised, the *mechanism* is).

---

## 8. RUNTIME — evidence per candidate

Identical for all ten unless stated:

- **Constructor evidence:** `git ls-files | xargs grep` over every tracked `.py`
  for `FleetRepository(`, `WorkflowRepository(`, `CostRepository(` — none; the
  only matches are `InMemoryWorkflowRepository(` (a different class). Inside
  the ignored packages: none.
- **Query evidence:** no `select(` over any candidate outside the gitignored
  repositories.
- **Repository evidence:** the three SQL repositories exist only as gitignored
  files and are never instantiated; **probe A** constructs each with a real
  session on a migration-built database → `UndefinedTableError` ×3.
- **Service evidence:** managers/engines are in-memory (§1); none imports an ORM
  candidate.
- **Route evidence:** `/api/v2/fleets`, `/api/v2/workflows` serve dataclasses;
  `/api/v2/costs` unmounted (§2, row 11).
- **DI evidence:** no `container.register` names any candidate or package.
- **Worker/background evidence:** no scheduler, worker, cron or `create_task`
  references any package; `fleet_health_monitor` has no loop.
- **Test evidence:** zero tests reference the ten classes, the three
  repositories, the ten tables, or the three route prefixes; the five
  `"backend.workflow_designer"` hits are forbidden-import lists.
- **Dynamic reachability:** ruled out (§6).

---

## 9. ALEMBIC

**Baseline** (files unchanged since Phase 10.20 — re-confirmed: a fresh
autogenerate is byte-identical to the 10.20 capture):

- `alembic check` against `cortex_p1014_legacy` @ `0024`: **exit non-zero**,
  130 `Detected` lines, **10 / 10 candidates reported as `added table`**.
- Autogenerate upgrade op lines: **129**.

**Candidate-specific operations** (`create_table` + `create_index`, nothing else):

| Table | ops | | Table | ops |
|---|---|---|---|---|
| `fleets` | 6 | | `workflows` | 6 |
| `fleet_agents` | 4 | | `workflow_nodes` | 3 |
| `fleet_deployments` | 4 | | `workflow_edges` | 5 |
| `fleet_metrics_snapshots` | 4 | | `cost_records` | 7 |
| | | | `cost_provider_rates` | 3 |
| | | | `cost_optimization_recommendations` | 1 |

**Simulated retirement impact:** **43 op lines disappear**, **86 remain** (the
27-table index drift ADR-112 classified), **no other op line touches a
candidate** — removing any one changes exactly its own lines. No `DROP TABLE`
arises, because no candidate table is in the migration lineage. Global
`alembic check` **is not clean and is not claimed to be.**

Registration contributes to autogenerate output: **yes** — the 43 lines exist
only because the tracked registry imports the gitignored files.

---

## 10. GOVERNANCE IMPACT

Searched every tracked file under `backend/auth`, `backend/contexts/**`,
`backend/database/durable`, `backend/platform/**`, `backend/api/product`,
`backend/world/**`, `backend/intelligence/**`, `backend/assurance/**`,
`backend/harness/**`, `backend/execution/**`, `backend/governance`,
`backend/identity/**`, `backend/connectors/**`, `backend/credentials/**` for the
ten class names, the three packages and the ten table names: **no reference.**
The only governed-side mention is `backend/platform/architecture/tenancy_rules.py:126-128`,
which grandfathers the names `CostRepository`, `FleetRepository`,
`WorkflowRepository` in the tenancy ratchet — an exemption list, not a
consumer (see Follow-up findings). Tenant, membership, authority, approval,
execution, worker, connector and assurance paths are **unaffected**.

**PROVIDER WRITES: 0.** Nothing in this phase touched a provider, a worker, a
credential or the k3d cluster.

---

## 11. STOP CONDITIONS

| # | Condition | Result |
|---|---|---|
| 1 | Live production consumer | **PASS** — probes A and B; no constructor, query, DI, worker or route touches an ORM candidate |
| 2 | Required by public API / external contract | **PASS** — routes serve dataclasses; `__all__` has no importer; no schema, CLI, frontend type, bundle or OpenAPI reference |
| 3 | Unresolved durable data | **PASS** — no table exists anywhere |
| 4 | Unresolved FK | **PASS** — five FKs, all internal to the group, all CASCADE |
| 5 | `CostRecordModel` vs `cost_tracking` indistinguishable | **PASS** — §5 |
| 6 | Persistence intent unestablished | **PASS** — §1, three sources plus execution |
| 7 | Retirement needs a schema decision outside this phase | **PASS** for deregistration (no table, no migration, no data). Shipping the v2.0 layer is a separate decision, not proposed |
| 8 | Dynamic reachability cannot be ruled out | **PASS** — §6 |
| 9 | Removal changes unrelated Alembic ops | **PASS** — exactly 43, no cross-reference |
| 10 | Provider write | **PASS** — 0 |
| 11 | Vacuous verification | **PASS** — clean-checkout probe, repository probe and HTTP probe all executed; the Alembic simulation was re-confirmed against a fresh autogenerate |
| 12 | Used by auth / tenant / membership / authority / approval / execution / governance / worker / connector / assurance | **PASS** — §10 |

**None fired.** The clean-clone breakage (§0) is outside the listed conditions
and is reported as the primary finding.

---

## 12. FOLLOW-UP FINDINGS — discovered, deliberately not changed

1. **The tracked registry imports gitignored files** (§0). Not one of the ten
   "models" — it is the shipped `models/__init__.py` — and it is why a clean
   clone cannot import, migrate or boot.
2. **`backend/governance/__init__.py:1` imports the ignored
   `governance/policy_engine.py`** — same defect class; reach limited to
   `backend.agent_sdk`.
3. **The tenancy ratchet grandfathers three repository names that do not exist
   in the repository** (`tenancy_rules.py:126-128`). From this tree the classes
   resolve; from a clean clone they are exemptions with nothing behind them —
   the pattern Phase 10.14 removed for the IAM repositories.
4. **`backend/workflow_designer/templates.py`** is also gitignored; no tracked
   file imports it. Not examined further.
5. **CI status was not observed**; its failure on a clean checkout is inferred
   from the workflow files and the import graph.
6. Four classes share the name `CostRecord`/`CostRecordModel` across
   `models/cost_tracking.py`, `models/cost_intelligence.py`,
   `cost_intelligence/models.py` — a text-search trap of the kind this phase
   family has been bitten by before.

---

## 13. RECOMMENDATION

**All ten are proven safe. Disposition: `RETIRE_MODEL` — registration only.**
The model files are not repository content; what the repository contains is
three import statements and ten `__all__` entries in
`backend/database/models/__init__.py` that point at gitignored files. Retiring
the *registration* is the smallest implementation phase:

1. Remove the three imports and ten `__all__` entries from the tracked
   registry. Touch no ignored file.
2. Decide `backend/governance/__init__.py`'s ignored import in the same phase
   (same defect class; one-line reach).
3. Remove the three stale tenancy-ratchet entries **only if** the ratchet test
   demands it, as Phase 10.14 did — do not edit the inventory pre-emptively.
4. **Prove on a clean checkout** that `import backend.database.models`,
   `alembic upgrade head` and boot succeed, and that autogenerate falls from
   129 to 86 with the other 86 byte-identical.
5. Re-run the architecture gate, the regression, and the 10.7–10.14 harnesses
   from *this* tree, and the clean-checkout probe from a worktree.

This does not decide whether to ship the v2.0 persistence layer; the ignored
files remain exactly where the GA-preparation commit left them.
