# Phase 10.22 — GA Integrity + ORM/Alembic Drift Reconciliation
## Verification Report

- **Parent:** `4db52fb` — Phase 10.21 (ADR-115)
- **ADR:** `docs/adr/ADR-116-phase-10-22-ga-integrity.md`
- **Plan:** `docs/PHASE_10_22_IMPLEMENTATION_MAP.md` (written before code)
- **Date:** 2026-09-08
- **Outcome:** Workstream A **IMPLEMENTED and VERIFIED from a clean checkout**.
  Workstream B **discovery complete — STOPPED at an architectural decision**
  (index-only drift with no established convention). **No migration generated.
  No v2.0 file touched. Provider writes: 0.**

Labels: `[VERIFIED]` = executed and observed in this phase · `[NOT VERIFIED]`
= claimed by inspection only · `[DEFERRED]` = deliberately not done ·
`[BLOCKED]` = could not be done · `[STOP]` = the brief's stop rule applied.

---

## 1. Summary

| Item | Result |
|---|---|
| Registry coupling removed (`models/__init__.py`) | `[VERIFIED]` 3 imports + 10 `__all__` entries removed; 0 candidate names remain — §3 |
| `governance/__init__.py` import | `[VERIFIED]` proven accidental by all four of the brief's tests; removed — §3.2 |
| Clean checkout: import | `[VERIFIED]` `backend.database.models`, `governance.service`, `execution.service`, `mission.service` all import on a worktree with ignored files absent — §4.1 |
| Clean checkout: `alembic upgrade head` | `[VERIFIED]` 24 migrations, 56 tables, 0 candidate tables, table set identical to the existing head DB — §4.2 |
| Existing database unchanged | `[VERIFIED]` `cortex_p1014_legacy`: 0 migrations run, schema md5 `264072c9…` identical, rows preserved — §4.3 |
| Clean checkout: boot | `[VERIFIED]` `import backend.main`, lifespan startup, `GET /health` → 200, v2 fleet/workflow routes still mounted — §4.4 |
| Autogenerate | `[VERIFIED]` **129 → 86**; the 86 byte-identical to baseline minus exactly the 43 candidate lines; inventory persisted — §4.5 |
| Architecture gate, this tree | `[VERIFIED]` **155 passed** — §4.6 |
| Architecture gate, clean checkout | `[VERIFIED]` **154 passed / 1 failed** — `test_the_ratchet_has_no_stale_entries`, cause proven; **`[STOP]`** on the ratchet rule — §5 |
| Regression suite, this tree | `[VERIFIED]` **76 failed / 6778 passed / 36 skipped / 58 xfailed / 24 errors** vs baseline 75 / 6779 / 36 / 58 / 24 — exactly one test moved, `test_invocation_gateway_matrix.py::TestHappyPath::test_invoke_reaches_the_provider_exactly_once_after_the_credential`; passes 3/3 solo, 63/63 module, 238/238 directory; imports neither edited package — §4.7 |
| Historical harnesses + probes | `[VERIFIED]` 10.7 155/155 · 10.8 118/118 · 10.9 107/107 (solo; chain run lost its TestClient portal) · 10.10 107/107 · 10.11 68/68 checks `[OK]` (verdict block not emitted — shutdown hang, see §4.8) · 10.13 60/60 · 10.14 53/53 (solo; chain run lost its portal) — all `provider_writes` 0 except 10.7's one commissioned restart; 10.16 probe holds; 10.19 readiness `ready: true` ×2; 10.20 write-path 4/4 — §4.8 |
| Workstream B classification | `[VERIFIED]` all 86 operations classified: **index-only drift**, 27 tables, 5 mechanisms — §6 |
| Index convention | `[VERIFIED]` **none exists** — 5 migrations use `idx_*`, 8 use `ix_*`, ORM mixes all three forms, no ADR states one — §6.4 |
| Workstream B disposition | **`STOP_ARCHITECTURAL_DECISION`** — no migration generated, no convention invented — §6.6 |
| Migrations generated | **0** |
| v2.0 (gitignored) files modified | **0** |
| Provider writes | **0** |
| `alembic check` executed | `[VERIFIED]` from the clean worktree against a pure migration-built DB: non-zero exit, "New upgrade operations detected", 62 add_index / 21 remove_index / 2 add_constraint / 1 remove_constraint = **86** — §4.5 |
| Alembic clean? | **No.** Not claimed. |
| **New finding — seven unregistered, unmigrated tracked models** | `[VERIFIED]` `organizations`, `departments`, `projects`, `backup_records`, `health_status_snapshots`, `maintenance_events`, `operational_reports`: live consumers, no registry import, no migration, absent from every migration-built DB; invisible to autogenerate by construction — §6.7. Classification **`[DEFERRED]`** to a dedicated discovery |
| Post-commit re-verification on a worktree of the commit | `[VERIFIED]` on a worktree of the **staged tree** `2e326c8e` (built with `git write-tree` / `commit-tree` before the commit, ignored files absent): the four importers load; `alembic upgrade head` on an empty DB → 24 migrations, 56 tables, 0 candidate tables; autogenerate `upgrade()` → **86 operations, byte-identical** to `p1022_ops_after.txt`; no generated revision left behind. The commit's tree differs from the verified tree only by this row of this document (checked with `git diff-tree` after the commit) |

---

## 2. Baseline

The code tree was unchanged since Phase 10.20's gate run (10.21 was
documentation-only), so that run is the pre-modification baseline: architecture
**155 passed**; regression **75 failed / 6779 passed / 36 skipped / 58 xfailed /
24 errors**; autogenerate **129 operations** (re-confirmed byte-identical in
10.21); harnesses 10.7 155/155 · 10.8 118/118 · 10.9 107/107 · 10.10 107/107 ·
10.11 68/68 · 10.13 60/60 · 10.14 53/53.

**The baseline could not be reproduced from a clean checkout.** On a git
worktree of `HEAD` (ignored files absent), before any edit:

```
backend.database.models    -> ModuleNotFoundError: backend.database.models.cost_intelligence
backend.governance.service -> ModuleNotFoundError: backend.governance.policy_engine
backend.governance.models  -> ModuleNotFoundError: backend.governance.policy_engine
backend.execution.service  -> ModuleNotFoundError: backend.governance.policy_engine
backend.mission.service    -> ModuleNotFoundError: backend.governance.policy_engine
```

---

## 3. Workstream A — the change

### 3.1 `backend/database/models/__init__.py`

Removed: `from backend.database.models.cost_intelligence import (CostRecordModel,
OptimizationRecommendationModel, ProviderRateModel)`, `from
backend.database.models.fleet import FleetAgentModel, FleetDeploymentModel,
FleetMetricsSnapshotModel, FleetModel`, `from backend.database.models.workflow
import WorkflowEdgeModel, WorkflowModel, WorkflowNodeModel`, and the ten
matching `__all__` entries. Added a four-line comment naming the reason and
this ADR. Diff: 21 lines, 4 insertions / 17 deletions. `git ls-files --eol`:
`i/lf w/lf`. A search of the edited file for any of the ten names: 0.

### 3.2 `backend/governance/__init__.py` — the brief's four tests, executed

| Test | Evidence |
|---|---|
| Does production require `PolicyEngine`? | **No.** `git grep PolicyEngine` over tracked files finds it only in this `__init__` (and `docs/`). `governance/service.py` imports `events`, `models`, `pipeline` — not `policy_engine` |
| Is it part of the GA architecture? | **No.** `.gitignore:114` excludes it under *"v2.0 Phase 1 components — not part of v1.0.0 GA"* |
| Does the clean checkout fail because of it? | **Yes** — the four modules in §2, including the mission and execution services, whose module-level `from backend.governance.models import …` runs the package `__init__` first |
| Does removal change governed runtime behaviour? | **No.** Nothing tracked references the name. `backend/governance` is the V1 decision pipeline; the Phase 10.5–10.8 authority path (`backend/auth`, `contexts/connectivity`) does not import it |

Removed the one import and the one `__all__` entry; added a three-line comment.
Diff: 6 lines, 4 insertions / 2 deletions. `i/lf w/lf`. Executed after the
edit on the clean worktree: all four modules import.

### 3.3 Not changed

Any gitignored file · any migration · any table · `env.py` ·
`backend/platform/architecture/tenancy_rules.py` (see §5) · tenant, membership,
authority, approval, execution, worker, connector, credential or assurance code
· the frontend.

---

## 4. Workstream A — verification from a clean filesystem state

Method: `git worktree add --detach $SP/clean_after HEAD`; the two edited
tracked files copied in byte-for-byte; every probe run with `cwd=$W`,
`PYTHONPATH=$W`. A worktree carries no ignored files, so it is an exact
stand-in for the commit. The ten candidate table names and the six ignored
module paths were confirmed absent from the worktree before each probe.

### 4.1 Imports `[VERIFIED]`

`backend.database.models`, `backend.governance.service`,
`backend.governance.models`, `backend.execution.service`,
`backend.mission.service`, `backend.platform.architecture.tenancy_rules` — all
`OK` from the worktree. `Base.metadata` from the worktree contains none of the
ten candidate tables.

### 4.2 Fresh database, migrations only `[VERIFIED]`

`cortex_p1022_fresh` created empty; `alembic upgrade head` from the worktree
(`POSTGRES_URL` pointed at it): **24** `Running upgrade` lines,
`0023_retire_iam -> 0024_approval_store` last, exit 0. Reflected: **56 tables,
0 of the ten candidates**. The table set is identical (`diff` = empty) to the
existing head database's.

### 4.3 Existing head database `[VERIFIED]`

`cortex_p1014_legacy` (`0024_approval_store`): `alembic upgrade head` from the
worktree ran **0** migrations. Schema fingerprint (normalised
`information_schema.columns` + indexes + constraints, md5) before and after:
`264072c9896946f9f62ec0d9d2b24554` = `264072c9896946f9f62ec0d9d2b24554`.
Row counts identical for every table.

### 4.4 Application boot `[VERIFIED]`

From the worktree, bounded, against `cortex_p1022_fresh` and the real Redis:
`import backend.main` OK (144.6 s — the import-time side effects the memory
notes document); ASGI lifespan startup OK (96.4 s); `GET /health` → **200**
`{"status":"healthy","agents":7,"event_bus":"active","runtime":"operational",…}`;
`/api/v2/fleets` and `/api/v2/workflows` routes **still mounted** (`True True`
— the in-memory managers ship unchanged, as ADR-115 required); no candidate
table created; process exit 0.

**Side effect, discovered afterwards.** The probe booted in development mode,
so the lifespan's `init_db()` ran `Base.metadata.create_all`
(`allow_non_production=True`; production refuses it — `engine.py:188-198`) and
added **seven tables** to `cortex_p1022_fresh` that no migration creates:
`backup_records`, `departments`, `health_status_snapshots`,
`maintenance_events`, `operational_reports`, `organizations`, `projects`
(56 → 63). That database is therefore no longer purely migration-built after
§4.4; every autogenerate and `alembic check` figure below was taken on a pure
one (this database *before* the boot, and a second one, `cortex_p1022_check`,
built and dropped for §4.5). The seven tables are a finding in their own
right — §6.7.

### 4.5 Autogenerate — the exact inventory `[VERIFIED]`

From the worktree against the fresh migration-built database:
**86 operations** (`p1022_ops_after.txt`, persisted). Composition:
`create_index` 62 · `drop_index` 21 · `create_unique_constraint` 2 ·
`drop_constraint` 1 · **`create_table` 0 · `drop_table` 0 · column ops 0**.

Compared line-by-line with the 129-operation baseline (`p1020_autogen.py`
output, re-confirmed in 10.21): the 43 lines that disappeared are exactly the
ten candidates' `create_table` and `create_index` lines and nothing else; the
86 that remain are **byte-identical** to the baseline's non-candidate lines;
none of the 86 mentions any candidate name. This is the brief's "129 → 86" —
reported on the inventory, not the count.

**`alembic check` itself, executed.** From the clean worktree against a second
database built only by `alembic upgrade head` (`cortex_p1022_check`: 24
migrations, 56 tables): exit non-zero, `ERROR [alembic.util.messaging] New
upgrade operations detected: […]`, containing **62 `add_index` / 21
`remove_index` / 2 `add_constraint` / 1 `remove_constraint` = 86** and no
table or column operation. The same run against `cortex_p1022_fresh` *after*
the boot probe (§4.4) reports 86 **plus** 7 `remove_table` and 32
`remove_index` for the boot-created tables — which is how §6.7 was found.

### 4.6 Architecture gate `[VERIFIED]`

- This tree: `pytest tests/architecture -q` → **155 passed** (642.9 s).
- Clean worktree: **154 passed, 1 failed** —
  `tests/architecture/test_tenancy_guard.py::test_the_ratchet_has_no_stale_entries`.
  See §5. Every other architecture test — including the three that import the
  models package and could not be collected on a clean checkout before this
  phase — passes.

### 4.7 Regression suite, this tree

`python -m pytest tests/ -q --tb=no -rf -p no:cacheprovider` (74 min, run
while two unrelated `krixi` pytest processes competed for the CPU):
**76 failed / 6778 passed / 36 skipped / 58 xfailed / 24 errors**. Baseline:
75 / 6779 / 36 / 58 / 24. The `-rf` lists were diffed against the Phase 10.18
baseline file: **75 failures identical, one new**, none fixed —

`tests/contexts/execution/test_invocation_gateway_matrix.py::TestHappyPath::test_invoke_reaches_the_provider_exactly_once_after_the_credential`

Executed afterwards: the test alone **3/3 passed** (5.6–7.7 s each); its module
**63/63**; its directory `tests/contexts/execution` **238/238**. The test is an
in-memory `Fixture` with fixed clock constants and no database; the file
imports only `backend.contracts.*` — neither `backend.database.models` nor
`backend.governance`, the two packages this phase edited. The full run used
`--tb=no`, so the one-time failure's traceback was not captured; it is recorded
as **a single non-reproducible failure under external CPU contention, not
attributable to this change** — `[NOT VERIFIED]` as to its root cause, which
would need a captured traceback from a full run.

### 4.8 Historical harnesses and probes, this tree

Run serially after the regression, from this tree, with fresh 6-hour k3d
tokens, the real Redis and each harness's own database, exactly as Phase 10.20
ran them:

| Harness | Chain run | Solo re-run | Result |
|---|---|---|---|
| 10.7 scoped authority | **155/155** VERIFIED, rc=0, writes {0, 1} | — | `[VERIFIED]` (the 1 is 10.7's one commissioned `rollout_restart`, as in every run since 9.9C) |
| 10.8 grant issuance | **118/118** VERIFIED, rc=0, writes 0 | — | `[VERIFIED]` |
| 10.9 membership | 100/105, 5 `[FAIL]`, rc=1 — `RuntimeError: This portal is not running` at TestClient `wait_shutdown`; the five failures (K1 `[500, 500]`, L1, L2, J1, J3) are the requests that hit the dead portal | **107/107** VERIFIED, writes 0; rc=124 = the harness's known post-verdict shutdown hang, killed by `timeout` *after* the verdict printed | `[VERIFIED]` solo |
| 10.10 tenant record | **107/107** VERIFIED, rc=0, writes 0 | — | `[VERIFIED]` |
| 10.11 retirement | rc=124 (900 s timeout) after `[OK] M1`, log full of `Event loop is closed` / `attached to a different loop` — the same anyio hazard | solo #1: 66/68 — N1/N2 `HTTP 500 (expected 200)` because the TestClient portal died (`RuntimeError: This portal is not running` ×5 in the log); their `provider_writes: 1` is the harness's pass/fail flag for those two cases (`record_negative(…, 0 if status == expected else 1)`), not a cluster measurement — the cluster-generation delta is 0 for every case. solo #2, uncontended: **68/68 `[OK]`, 0 `[FAIL]`, 0 portal deaths, `negative_matrix_provider_writes = 0`, the check set identical to the 10.20 baseline's 68** — then the process hung after `[OK] M1`, before printing its `[REPORT]`/verdict block, and was killed by the 1200 s timeout (rc=124) | checks `[VERIFIED]` 68/68; harness verdict `[NOT VERIFIED]` — the JSON summary was never emitted in the passing run |
| 10.13 retire V1 reads | **60/60** VERIFIED, rc=0, writes 0 | — | `[VERIFIED]` |
| 10.14 retire IAM | rc=1 — `JSONDecodeError` on an empty body from `GET /api/v1/approvals` inside the negative matrix (dead portal again) | **53/53** VERIFIED, rc=0, writes 0 | `[VERIFIED]` solo |
| 10.16 metadata probe | `ATTRIBUTE 'metadata' REFUSED: InvalidRequestError`; column via `mapped_column('metadata', …)` = `['id', 'metadata']` | — | `[VERIFIED]` holds |
| 10.19 readiness (`verify_durability`, `create_schema=False`) | `cortex_p1022_fresh` → `ready: true, missing_tables: []`; `cortex_p1014_legacy` → `ready: true, missing_tables: []` | — | `[VERIFIED]` (note: `cortex_p1022_fresh` had by then also been dev-booted, §4.4; the check is on `cp_*` presence and is unaffected) |
| 10.20 write-path test | `tests/database/test_cost_tracking_write_path.py` **4 passed** in 30 s | — | `[VERIFIED]` |

The TestClient/anyio portal death under load is the hazard recorded in every
phase since 10.7; the remedy has always been a solo re-run, and it was applied
here unchanged. None of the three chain-run failures names either edited
package, and each harness's model-registry-dependent sections (every
database-backed check) passed in the same runs.

---

## 5. The tenancy ratchet — `[STOP]`, not edited

`stale_grandfather_entries(ModuleGraph.build("backend"))`, executed on both
trees:

| Tree | Stale entries |
|---|---|
| this tree (ignored files present) | `()` |
| clean worktree | `('CostRepository', 'FleetRepository')` |

`WorkflowRepository` is **not** stale on the clean worktree because a tracked
class of that name exists at
`backend/contexts/workflow/infrastructure/repository.py`, and it is the *only*
thing satisfying that entry there (on this tree the ignored
`backend/workflow_designer/repository.py` satisfies it too).

**The brief's rule:** *"If stale tenancy-ratchet exemptions fail ONLY because
they refer to repository code deleted in this phase, remove those exact stale
exemptions. Do not edit exemptions just to make the test pass."*

**No repository code was deleted in this phase.** `CostRepository` and
`FleetRepository` are gitignored since `9d15d77`; their entries have been stale
on every clean checkout since then, masked by working trees that carry the
ignored files — the same masking that hid the registry coupling. Their
staleness is not a consequence of this phase's edits: the graph scan reads
files, not imports, so the entries were stale on a clean checkout *before*
Workstream A too. The rule's condition is therefore not met, and removing them
now would be editing exemptions to make the test pass. **`tenancy_rules.py` is
not touched.** The clean-checkout gate is reported as 154/155 with this one
named failure, and the two-line removal is recorded as a follow-up for the
user's explicit authorisation.

**Side-finding (recorded, not acted on).** The `WorkflowRepository` entry was
written for the ignored v2.0 `workflow_designer` repository and now
grandfathers, by name collision, the governed `contexts/workflow` repository.
Executed: all four of that class's methods (`save`, `replace`, `find`, `all`)
take `context` and take no tenant parameter, so they satisfy the rule on their
own — the collision would downgrade a future violation from ERROR to WARNING
but currently hides nothing. Tenant scoping is outside this phase's boundary.

---

## 6. Workstream B — the remaining 86 operations

### 6.1 Discovery method

Each of the 86 operations was parsed (`re.findall` on the persisted inventory;
0 unparsed) and grouped by table (`p1022_ops_by_table.json`). For each of the
27 tables, the ORM `Table` object's indexes/unique markers were compared with
the reflected indexes/constraints of the migration-built database
(`p1022_B_indexes.py` → `p1022_B_indexes.json`), giving each table's
*mechanism* — why the two sides differ — rather than just Alembic's proposal.
Row counts, inbound/outbound FKs, mapping files and tests were read from the
existing head database and the tracked tree.

### 6.2 Classification `[VERIFIED]`

**Every one of the 86 operations is index-only.** Not one creates or drops a
table, adds, drops or alters a column, or touches a foreign key. Five
mechanisms, by table count (a table may show several):

| Mechanism | Tables | Meaning |
|---|---|---|
| `RENAME` | 17 | migration created `idx_<abbrev>` on a column; ORM declares `index=True`, whose auto-name is `ix_<table>_<col>` → Alembic proposes drop + create of an **equivalent** index |
| `INDEX_TRUE_NEVER_MIGRATED` | 17 | ORM `index=True` that no migration ever created |
| `UNIQUE_DECLARED_ONLY_IN_ORM` | 12 | ORM `unique=True`; the migration created a plain (or unique-index, not constraint) index instead |
| `EXPRESSION_INDEX_MIGRATION_ONLY` | 3 | GIN / ivfflat indexes on `to_tsvector(...)` / vector columns that the ORM cannot declare → **autogenerate proposes to DROP them** |
| `DB_ONLY_PLAIN` | 2 | plain index in the migration with no ORM counterpart |

Operation totals: `create_index` 62 · `drop_index` 21 ·
`create_unique_constraint` 2 · `drop_constraint` 1 = 86.

### 6.3 Per-table inventory

| Table | ops (create_idx / drop_idx / create_uq / drop_con) | Mechanisms | Detail |
|---|---|---|---|
| `agent_configs` | 2 / 1 / 0 / 0 | RENAME, UNIQUE_DECLARED_ONLY_IN_ORM | rename `idx_agent_configs_type`→`ix_agent_configs_agent_type`, `idx_agent_name`→`ix_agent_configs_name`; orm unique `name` |
| `agent_states` | 2 / 1 / 0 / 0 | RENAME, UNIQUE_DECLARED_ONLY_IN_ORM | rename `idx_agent_states_status`→`ix_agent_states_status`, `idx_agent_states_name`→`ix_agent_states_agent_name`; orm unique `agent_name` |
| `billing_invoices` | 2 / 1 / 0 / 0 | RENAME, INDEX_TRUE_NEVER_MIGRATED, DB_ONLY_PLAIN, UNIQUE_DECLARED_ONLY_IN_ORM | rename `idx_billing_invoices_status`→`ix_billing_invoices_status`; never-migrated `ix_billing_invoices_organization_id`; db-only `idx_billing_invoices_number`; orm unique `invoice_number` |
| `billing_usage_records` | 4 / 0 / 0 / 0 | RENAME, INDEX_TRUE_NEVER_MIGRATED | rename `idx_billing_usage_resource`→`ix_billing_usage_records_resource_type`; never-migrated `ix_billing_usage_records_mission_id`, `…_organization_id`, `…_user_id` |
| `connector_activity` | 7 / 3 / 0 / 0 | RENAME, INDEX_TRUE_NEVER_MIGRATED | rename `idx_ca_request_id`, `idx_ca_initiated_by`, `idx_ca_correlation_id`, `idx_ca_connector_name` → `ix_connector_activity_*`; never-migrated `ix_connector_activity_operation`, `…_connector_type`, `…_status` |
| `connector_configs` | 2 / 2 / 0 / 0 | RENAME, DB_ONLY_PLAIN, UNIQUE_DECLARED_ONLY_IN_ORM | rename `idx_connector_name`→`ix_connector_configs_name`, `idx_connector_configs_type`→`ix_connector_configs_connector_type`; db-only `idx_connector_status`; orm unique `name` |
| `digital_twin_metrics` | 1 / 0 / 0 / 0 | INDEX_TRUE_NEVER_MIGRATED | never-migrated `ix_digital_twin_metrics_resource_id` |
| `digital_twin_models` | 3 / 0 / 0 / 0 | INDEX_TRUE_NEVER_MIGRATED | never-migrated `ix_digital_twin_models_name`, `…_provider`, `…_resource_type` |
| `digital_twin_relationships` | 3 / 0 / 0 / 0 | INDEX_TRUE_NEVER_MIGRATED | never-migrated `ix_digital_twin_relationships_target_id`, `…_relationship_type`, `…_source_id` |
| `embedding_cache` | 1 / 0 / 0 / 1 | RENAME | drop constraint `embedding_cache_text_hash_key` → create `ix_embedding_cache_text_hash` (unique); orm unique `text_hash` |
| `episodic_memory` | 2 / 2 / 0 / 0 | INDEX_TRUE_NEVER_MIGRATED, **EXPRESSION** | never-migrated `ix_episodic_memory_agent`, `…_session_id`; **would DROP `idx_ep_content_fts` (GIN) and `idx_ep_embedding` (ivfflat, lists=100)** |
| `execution_events` | 1 / 0 / 0 / 0 | INDEX_TRUE_NEVER_MIGRATED | never-migrated `ix_execution_events_execution_id` |
| `executions` | 4 / 1 / 0 / 0 | RENAME, INDEX_TRUE_NEVER_MIGRATED, UNIQUE_DECLARED_ONLY_IN_ORM | rename `idx_exec_id`, `idx_exec_agent`, `idx_exec_mission` → `ix_executions_*`; never-migrated `ix_executions_status`; orm unique `execution_id` (DB: unique index `idx_exec_id`) |
| `governance_approval_requests` | 2 / 1 / 0 / 0 | RENAME, INDEX_TRUE_NEVER_MIGRATED, UNIQUE_DECLARED_ONLY_IN_ORM | rename `idx_gov_approval_rid`→`ix_governance_approval_requests_request_id`; never-migrated `…_status`; orm unique `request_id` |
| `governance_compliance_rules` | 2 / 0 / 0 / 0 | INDEX_TRUE_NEVER_MIGRATED | never-migrated `…_name`, `…_framework` |
| `governance_policies` | 2 / 1 / 0 / 0 | RENAME, UNIQUE_DECLARED_ONLY_IN_ORM | rename `idx_gov_policies_name`, `idx_gov_policies_category` → `ix_governance_policies_*`; orm unique `name` |
| `knowledge_entries` | 2 / 0 / 0 / 0 | RENAME, INDEX_TRUE_NEVER_MIGRATED | rename `idx_knowledge_category`→`ix_knowledge_entries_category`; never-migrated `ix_knowledge_entries_title` |
| `knowledge_relationships` | 3 / 0 / 0 / 0 | INDEX_TRUE_NEVER_MIGRATED | never-migrated `…_target_id`, `…_source_id`, `…_relationship_type` |
| `learning_patterns` | 2 / 1 / 0 / 0 | RENAME, UNIQUE_DECLARED_ONLY_IN_ORM | rename `idx_learn_patterns_name`, `idx_learn_patterns_category` → `ix_learning_patterns_*`; orm unique `name` |
| `learning_sessions` | 3 / 1 / 0 / 0 | RENAME, UNIQUE_DECLARED_ONLY_IN_ORM | rename `idx_learn_session_mission`, `idx_learn_session_status`, `idx_learn_session_sid` → `ix_learning_sessions_*`; orm unique `session_id` |
| `mission_steps` | 1 / 0 / 0 / 0 | INDEX_TRUE_NEVER_MIGRATED | never-migrated `ix_mission_steps_mission_id` |
| `missions_bc` | 3 / 0 / 0 / 0 | RENAME, INDEX_TRUE_NEVER_MIGRATED, UNIQUE_DECLARED_ONLY_IN_ORM | rename `idx_missions_bc_owner`, `idx_missions_bc_category` → `ix_missions_bc_*`; never-migrated `ix_missions_bc_status`; orm unique `execution_id` |
| `platform_feature_flags` | 1 / 1 / 0 / 0 | RENAME, UNIQUE_DECLARED_ONLY_IN_ORM | rename `idx_platform_ff_name`→`ix_platform_feature_flags_name`; orm unique `name` |
| `platform_settings` | 2 / 1 / 0 / 0 | RENAME, UNIQUE_DECLARED_ONLY_IN_ORM | rename `idx_platform_settings_key`, `idx_platform_settings_category` → `ix_platform_settings_*`; orm unique `key` |
| `reflection_history` | 2 / 1 / 0 / 0 | INDEX_TRUE_NEVER_MIGRATED, **EXPRESSION** | never-migrated `ix_reflection_history_agent`, `…_mission_id`; **would DROP `idx_refl_embedding` (ivfflat, lists=50)** |
| `runtime_analytics` | 3 / 1 / 0 / 0 | RENAME, INDEX_TRUE_NEVER_MIGRATED | rename `idx_analytics_session`→`ix_runtime_analytics_session_id`; never-migrated `…_mission_id`, `…_agent` |
| `semantic_memory` | 0 / 2 / 0 / 0 | **EXPRESSION** | **would DROP `idx_sem_concept_fts` (GIN) and `idx_sem_embedding` (ivfflat, lists=100)** |

Shared facts, executed on the existing head database and the tracked tree:
**every one of the 27 tables holds 0 rows**; every table is mapped by a tracked
model and a tracked repository; no table has an inbound FK from outside this
set (`missions_bc` has two, both from tables already migrated); tests exist for
`executions` (10), `episodic_memory` / `reflection_history` / `semantic_memory`
(2 each), `embedding_cache`, `agent_states`, `runtime_analytics` (1 each).
None of the 27 is a governed `cp_*` / `cw_*` table.

### 6.4 Is there an established index convention? `[VERIFIED]` — **No**

Census of `create_index` names in the migration lineage (regex over
`versions/*.py`):

| Migration | `idx_*` | `ix_*` |
|---|---|---|
| `0001_initial_schema` | 11 | 0 |
| `0002_add_audit_logs` | 1 | 6 |
| `0004_add_cost_tracking` | 0 | 4 |
| `0007_add_bounded_context_tables` | 61 | 0 |
| `0008_add_connector_status` | 1 | 0 |
| `0009_consolidate_connector_activity` | 10 | 0 |
| `0010_durable_state_foundation` | 0 | 4 |
| `0011_distributed_coordination` | 0 | 1 |
| `0013_fenced_audit_storage` | 0 | 1 |
| `0018_world_reasoning` | 0 | 3 |
| `0019_world_investigation` | 0 | 3 |
| `0022_tenant_record` | 0 | 1 |
| `0023_retire_iam` | 6 | 0 |

Five migrations use `idx_*` (90 indexes, mostly the V1 bounded-context
tables); eight use `ix_*` (23, mostly the governed durable tables — where
`ix_*` is SQLAlchemy's own auto-name). Even `0002` mixes both in one file. The
tracked ORM (`git ls-files backend/database/models`): 47 explicit
`Index("idx_…")`, 4 explicit `Index("ix_…")`, 32 bare `index=True` markers
(auto-named `ix_*`), 5 `unique=True`. `git grep` over `docs/` and
`backend/database/` for a stated convention finds only ADR-112 and the 10.17
discovery — both of which *report* the mixture; neither decides it. **There is
no single convention to apply.**

### 6.5 The three expression indexes

`0007` created `idx_ep_content_fts`, `idx_ep_embedding`, `idx_refl_embedding`,
`idx_sem_concept_fts`, `idx_sem_embedding` — GIN full-text and pgvector
ivfflat indexes on expressions the declarative ORM does not model. On these the
migration side is plainly canonical, and Alembic's proposal (`drop_index`, ×5)
is **wrong**, not merely differently-named: applying it would remove the
memory subsystem's semantic-search indexes. This is the concrete instance of
the brief's "Alembic output is evidence, not authority."

### 6.6 Disposition: `STOP_ARCHITECTURAL_DECISION`

Applying the brief's index-only special rule — *"If there is no established
convention: STOP and document the architectural decision. Do not invent one."*
— the whole 86-operation remainder is stopped, because every sub-mechanism
turns on the same undecided question: **which side names an index, and are
`index=True` markers in the ORM a promise the migrations must keep?**

- `RENAME` (17 tables) is *only* a naming decision — the indexes are
  equivalent; either side could be made canonical by a rename migration or by
  giving the ORM the migration's names (as Phase 10.20 did for `cost_tracking`).
- `INDEX_TRUE_NEVER_MIGRATED` (17) and `DB_ONLY_PLAIN` (2) depend on that
  answer to know which side is missing something.
- `UNIQUE_DECLARED_ONLY_IN_ORM` (12) is a constraint-vs-unique-index policy
  question on top of naming.
- `EXPRESSION_INDEX_MIGRATION_ONLY` (3) is decided on its own evidence
  (migration canonical, §6.5) but is protected only by *not* running an
  autogenerated migration — a durable protection needs the same convention
  decision (declare them in the ORM with `postgresql_using`, or exclude them in
  `env.py`'s `include_object`), which is outside this phase's authority.

No other disposition applies: nothing here is `RETIRE_*` (every table is live,
mapped and migrated), nothing is a plain `RECONCILE` (no column disagrees), and
`ADD_MIGRATION` would be generating a migration because autogenerate proposed
it. **Decision recorded in ADR-116; no migration written.**

### 6.7 New finding: seven tracked models Alembic cannot see `[VERIFIED]` — classification `[DEFERRED]`

Found because the dev-mode boot (§4.4) created them and `alembic check` then
proposed dropping them. Facts, executed on the tracked tree and the databases:

| Table | Model (tracked) | Registered in `models/__init__.py` | Any migration names it | In `cortex_p1014_legacy` (head) | Tracked consumers |
|---|---|---|---|---|---|
| `organizations` | `organization.py` | no | no | **absent** | `api/organization_routes.py`, `repositories/organization_repository.py`, `models/department.py` |
| `departments` | `department.py` | no | no | **absent** | `api/department_routes.py`, `repositories/department_repository.py`, `models/organization.py` |
| `projects` | `project.py` | no | no | **absent** | `api/project_routes.py`, `repositories/project_repository.py` |
| `backup_records` | `backup_record.py` | no | no | **absent** | `services/backup_service.py` |
| `health_status_snapshots` | `health_status.py` | no | no | **absent** | `services/health_center_service.py` |
| `maintenance_events` | `maintenance_event.py` | no | no | **absent** | `services/maintenance_service.py` |
| `operational_reports` | `operational_report.py` | no | no | **absent** | `services/operational_reports_service.py` |

These models reach `Base.metadata` only when their consumer modules import
them — which the application boot does and `alembic env.py` (importing the
registry package alone) does not. So autogenerate can never propose a
`create_table` for them, `alembic check` can never flag their absence, and no
migration has ever created them: they exist only in databases that a
development boot `create_all`'d. **In production, where `init_db()` refuses
`create_all`, the organization / department / project routes and the backup,
health-center, maintenance and operational-reports services address tables
that do not exist** — `[NOT VERIFIED]` by execution in this phase (the
mechanism is the same one Phase 10.21 executed for the v2.0 repositories:
`UndefinedTableError`), recorded here as an inference. The tracked
`legacy_persistence_inventory.py:176` classifies three of them
(`health_status`, `maintenance_event`, `operational_report`) as `KEEP` /
"observability" without noting that nothing creates their tables; the other
four are not in that inventory. ADR-112's "metadata closure: 40 tables, 0
unresolved" could not have seen them — closure was computed over the
registry's metadata, and these are outside it.

This is the `cp_approval` (ADR-113) / `cost_tracking` (ADR-114) defect class,
seven more times. It is **not** part of the 86 operations and it is **not
index drift**; each table needs the same per-table discovery those phases had
(consumers, rows, contract, `ADD_MIGRATION` vs `RETIRE_MODEL`) before any
disposition. Deferred, not stopped — no architectural question blocks it, only
scope: the brief bounded Workstream B to the remaining autogenerate operations.

---

## 7. Negative matrix

| Assertion | Evidence |
|---|---|
| `provider_writes = 0` | No Kubernetes, GitHub, cloud or external call made by this phase's probes; harness `provider_writes` fields — 10.7 {0, 1} (the commissioned restart), 10.8 0, 10.9 0, 10.10 0, 10.11 see §4.8 (its N1/N2 field is a pass/fail flag, the cluster-generation measurement is 0 for every case), 10.13 0, 10.14 0 |
| No gitignored (v2.0) file modified or deleted | `git status --short` shows exactly the two tracked edits + the new docs; the ignored model/repository files are untouched (never opened for write in this phase) |
| No migration created | `versions/` unchanged; head still `0024_approval_store` |
| Alembic not made green by suppression | `env.py` untouched; no `include_object` added; `alembic check` executed and still reports 86 (§4.5) |
| No migration generated from autogenerate | 0 migrations |
| No governed code touched | `git diff --stat`: only `backend/database/models/__init__.py`, `backend/governance/__init__.py` |
| Governed tables untouched | no `cp_*` / `cw_*` table appears in the 86 ops or in any edit |
| exactly-once | **not claimed** |
| `.phase99b.env` not staged | `git ls-files --error-unmatch .phase99b.env` → not tracked; `.gitignore:139` |

---

## 8. Clean-checkout requirement — status

| Requirement | Before this phase | After |
|---|---|---|
| import the models package | ✗ | ✓ |
| `alembic upgrade head` | ✗ (`env.py` imports models) | ✓ 24/24 |
| boot the application | ✗ | ✓ `/health` 200 |
| architecture gate | ✗ (3 tests uncollectable) + stale ratchet | 154/155 — the one failure is §5, `[STOP]` |
| `alembic check` clean | ✗ (129) | ✗ (86, executed) — **not claimed** |
| every tracked model has a migration | ✗ — and unknown, because 7 were invisible | ✗ — now known: §6.7 |

---

## 9. Evidence files (session scratchpad)

`p1022_autogen.py`, `p1022_ops_after.txt` (the 86), `p1022_ops_by_table.json`,
`p1022_B_indexes.py/.json`, `p1022_upgrade.log`, `p1022_tables_fresh.txt`,
`p1022_legacy_before.txt`, `p1022_boot.py/.out`, `p1022_arch.out`,
`p1022_reg.out`, `p1022_harness.out`, `p1022_stale.py`, `p1022_wr.py`,
`p1022_wr2.py`. Disposable database `cortex_p1022_fresh` and worktree
`clean_after` removed before the commit.
