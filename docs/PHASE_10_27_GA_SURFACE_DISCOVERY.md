# PHASE 10.27 — GA SURFACE DECISION DISCOVERY

- **Date:** 2026-09-09
- **Nature:** discovery only. No production code, migration, model, route,
  test, index, Alembic configuration or governance surface was modified.
- **Evidence classes:** **FACT** = observed in the repository or by execution
  in Phase 10.23 (cited); **INFERENCE** = drawn from facts, labelled;
  **UNKNOWN** = not establishable from the repository.

## Repository State

| | |
|---|---|
| HEAD | `8de3060` — Phase 10.25 + 10.26 (ADR-118), parent `3adf9bc` (ADR-117) |
| Branch | `phase-1-foundation` |
| Working tree | clean at start (`git status --short` → 0 entries); clean at end apart from this document |
| Latest relevant ADRs | ADR-103 (organizations rejected as tenancy), ADR-107 (IAM retired), ADR-116 (the seven found), ADR-117 (all seven `STOP_ARCHITECTURAL_DECISION`; decisions 1 and 2 open), ADR-118 (decision 3 resolved) |
| Relevant phase documents | `PHASE_10_23_DISCOVERY.md` (executed route/DB evidence for all seven), `PHASE_10_23_VERIFICATION_REPORT.md`, `PHASE_10_23_24_IMPLEMENTATION_MAP.md` |
| Out of scope, untouched | the 86 index-only Alembic operations (ADR-116) |

Both groups share four **FACT**s established by execution in 10.23 and
re-read here from the tracked sources:

- **F0.1 — doubled mount.** Each router declares its own `/api/…` prefix
  (`organization_routes.py` `prefix="/api/organizations"`,
  `backup_routes.py` `prefix="/api/operations/backup"`, etc.) *and*
  `router_registry.py:1441/1451/1469/1478/1487/1496/1505` includes it with
  `prefix="/api"`. The 10.22 boot log lists the effective paths as
  `/api/api/organizations`, `/api/api/operations/backup/…`, etc. Only
  `organization_department_routes` (registry `:1522`, included without a
  prefix) mounts at its declared `/api/organization/departments`.
  `git blame`: all of it from `1413159f` (2026-07-18), never changed since.
- **F0.2 — three path vocabularies that disagree.** The registry's own
  `log.info` lines claim `/api/organization`, `/api/departments`,
  `/api/projects`, `/api/backup`, `/api/health-center`, `/api/maintenance`,
  `/api/operational-reports` (`router_registry.py:1442,1452,1470,1479,1488,1497,1506`);
  the routers declare `/api/organizations`, `/api/operations/backup`, …; the
  Administrator Guide documents `/api/v1/admin/organizations…`
  (`docs/ADMINISTRATOR_GUIDE.md:568-640`), a path that **has never existed in
  the backend** (`git log -S"admin/organizations" -- backend` → nothing).
- **F0.3 — no gating, no flags.** No `if`/feature flag around any of the
  includes (`router_registry.py:1436-1530`); no `ORGANIZATION_*`, `BACKUP_*`,
  `MAINTENANCE_*`, `HEALTH_CENTER*`, `OPERATIONAL_REPORT*` setting in
  `backend/config`, any `.env*`, compose, Helm, infra or CI file.
- **F0.4 — no table, no data, no migration.** No migration names any of the
  seven tables; no database on the instance has any of them
  (10.23 §1). `create_all` from a dev boot is the only thing that has ever
  created them.

---

## Decision 1 — V1 Organizational Directory (`organizations`, `departments`, `projects`)

### Evidence

| # | Fact | Where | Direction |
|---|---|---|---|
| 1.1 | Models: UUID PK + timestamps + JSONB `metadata`; `departments.organization_id → organizations ON DELETE CASCADE`; `projects.organization_id → organizations CASCADE`, `projects.department_id → departments SET NULL`; uniques on `organizations.domain`, `projects.key`, `(projects.organization_id, name)` | `backend/database/models/organization.py:16-35`, `department.py:17-40`, `project.py:14-45` | model |
| 1.2 | Model importers (tracked): only the three route modules, the three repositories, and each other | `git grep "database.models.(organization\|department\|project)"` (10.23 §0 table) | model → consumers |
| 1.3 | Routes: 5 CRUD endpoints each behind `require_user`; `organization_department_routes` 1 read endpoint | `backend/api/organization_routes.py:45-179`, `department_routes.py:46-170`, `project_routes.py:55-280`, `organization_department_routes.py:23` | consumer → model |
| 1.4 | Registered, unconditionally, at the doubled paths (F0.1) | `router_registry.py:1449-1527` | mounting |
| 1.5 | Repositories extend `BaseRepository` over the real `AsyncSession`; `get_session` → `AsyncSessionLocal` → production engine | `backend/database/repositories/organization_repository.py:12-14`, `department_repository.py:13-15`, `project_repository.py:13-15`; `backend/database/session.py:28` | runtime |
| 1.6 | Executed (10.23): on a migration-built DB every DB-backed call → `UndefinedTableError`, including the correctly-mounted `/api/organization/departments`; `GET /api/organizations` → 404; with the tables present `POST /api/api/organizations` → 201 and one row | `PHASE_10_23_DISCOVERY.md` §2.1 table | runtime |
| 1.7 | Not registered in `backend/database/models/__init__.py`; absent from Alembic metadata; the ratchet grandfathers `DepartmentRepository`, `OrganizationRepository`, `ProjectRepository` | `models/__init__.py:5-27`; `backend/platform/architecture/tenancy_rules.py:101,111,113` | schema / architecture |

### Live Consumers

**FACT:** the only code that reads or writes these models is the four route
modules and three repositories (1.2, 1.3). No service, worker, scheduler,
event subscriber, DI registration, startup hook, script, CLI or CI workflow
references them (`git grep` over `backend`, `scripts`, `.github`, `helm`,
`infra`: only the files in 1.2).

**FACT:** no test drives them. `tests/test_api_endpoints.py:51-53,109-111`
asserts the route *files exist* and use an auth dependency
(`test_all_route_files_exist`, `test_route_file_uses_auth`); no test
imports the repositories or models (`git grep` over `tests`: none).
`tests/conftest.py` has no fixture for them.

### Frontend Evidence

| # | Fact | Where |
|---|---|---|
| 1.8 | The Operations Center nav lists **"Organizations"** at `href: "/operations/organizations"` | `frontend/components/operations-center/shared.tsx:129` |
| 1.9 | **No `frontend/app/operations/` directory exists** (0 tracked files); the page lives at `frontend/app/operations-center/organizations/page.tsx`; no rewrite, redirect or route group maps `/operations/*` to it (`next.config.ts:23-31` rewrites only `/product-api/*`; `proxy.ts` has no such rule; `git grep redirect(` in the app → none) | `git ls-files frontend/app` |
| 1.10 | The Operations Center landing page's own `navItems` (Dashboard, GitHub, Jira, Slack, Docker, Kubernetes, Prometheus, Grafana, Users, Roles, Connectors, Workers, Secrets, Audit) **do not include Organizations** | `frontend/app/operations-center/page.tsx:11-34` |
| 1.11 | `organizations-panel.tsx` is **mock data** — `// ─── MOCK DATA`, `const ORGANIZATIONS: Organization[] = […]`, local `useState`, **no API call** | `frontend/components/operations-center/organizations-panel.tsx:30-66` |
| 1.12 | **No frontend file calls** `/api/organizations`, `/api/departments`, `/api/projects`, `/api/organization/departments` or `/api/v1/admin/organizations` | `git grep` over `frontend/**` (excluding `developer-portal/content.ts`): none |
| 1.13 | The frontend's own wiring report lists *Departments → `/api/organization/departments`* and *Projects → `/api/projects`* under **"Data Categories Still Needing Backend APIs — wired to return empty arrays since no backend endpoints exist yet"** | `frontend/REALTIME_DATA_WIRING_REPORT.md:207-214` |
| 1.14 | The executive **Security** page's "Organizations" card reads `/api/security/organizations`, which is served by the in-memory `IdentityManager._organizations` dict — a different concept, not these tables | `frontend/app/executive-platform/security/page.tsx:18`, `frontend/services/enterprise/platformService.ts:220`, `backend/api/security_center_routes.py:171-180`, `backend/security_center/identity.py:42,297-311`, `security_center/models.py:166` (`@dataclass Organization`) |
| 1.15 | The only frontend test touching the Operations Center asserts it "renders … without crashing" | `frontend/tests/enterprise-platform.test.tsx:97-101` |

**INFERENCE (from 1.8–1.13):** there is no working production UI for the
directory; the one page that exists renders fixtures and is reachable only
by typing its URL.

### Runtime Dependencies

**FACT:** none. The mission runtime, agents, connectors, workers and
schedulers do not import these models (1.2). The governed `ProjectRef` and
`OrganizationContext` are pure string contracts with no model import
(`backend/contracts/tenant.py:59-70`, `backend/platform/context/tenancy.py:118-140`,
`runtime.py:214-232`), and nothing supplies their ids from these tables
(`git grep organization_id` over `platform/context`, `api/product`, `auth`:
only the contract fields themselves). The `resource.department` attribute in
the Administrator Guide's ABAC example is a user claim, not this table
(`docs/ADMINISTRATOR_GUIDE.md:439`). "Projects" in `architecture_routes`,
CI/CD and connector routes are provider/other concepts (`/api/architecture/projects`,
`/api/cicd/gitlab/projects/…`, `/api/connectors/jira/projects` in the boot
log), not `ProjectModel`.

### Governance / Tenancy Dependencies

| # | Fact | Where |
|---|---|---|
| 1.16 | ADR-103 evaluated `organizations` for tenancy and **rejected** it: *"no `tenant_id`, no membership, no link to any authority, approval or execution record … an org-chart entity with departments, served by `organization_routes` … the names look alike and the concepts are not"*; the 10.10 harness asserts the absence of a tenant reference | `docs/adr/ADR-103-phase-10-10-durable-tenant-records.md:59-66`; `docs/PHASE_10_10_IMPLEMENTATION_MAP.md:60-61` ("a directory feature, not an authorization boundary") |
| 1.17 | Migrations `0021`/`0022` state in their docstrings that `organizations` *"is live, but an organization is not a tenant and carries no tenant_id"* / *"has no tenant_id, no membership, and no relationship to…"* | `versions/0021_tenant_membership.py:17`, `0022_tenant_record.py:14` |
| 1.18 | `tenancy_rules.py` deliberately excludes `organization_id` from tenant parameters: *"an organization is not a tenant"* | `backend/platform/architecture/tenancy_rules.py:65-66` |
| 1.19 | No governed package (`auth`, `contexts`, `platform`, `contracts`, `assurance`, `world`) imports these models | `git grep` (10.23 §2.1) |
| 1.20 | **IAM** (`iam_users/roles/api_keys`) was retired in Phase 10.14, migration `0023_retire_iam`, ADR-107; ADR-107 does not mention organizations, departments or projects | `docs/adr/ADR-107*.md` (grep: none) |
| 1.21 | The tracked persistence inventory's entry for these three says `KEEP`, owner *"IAM / org structure"*, callers *"IAM routes and services"*, tenant model *"these tables largely define tenancy"*, risk *"identity depends on them"* | `backend/api/legacy_persistence_inventory.py:139-150` |

**FACT:** every justification in 1.21 is contradicted by later tracked
decisions — IAM is retired (1.20) and the tables were rejected as tenancy
(1.16–1.18). **FACT:** no ADR or phase document has *replaced* that
justification with another; ADR-103 says what the directory is *not*, and
nothing says what it is *for*.

### GA Evidence

| # | Fact | Where | Reads as |
|---|---|---|---|
| 1.22 | The Administrator Guide has a section **"6. Organization Management"** (Organizations, Departments, Projects: *"Projects group agents, knowledge bases, and connections within an organization"*) with `curl` examples against `/api/v1/admin/organizations…` | `docs/ADMINISTRATOR_GUIDE.md:12,568-640` | **documented as a product capability** — against an API that does not exist (F0.2) |
| 1.23 | The originating commit `5c800bc` is titled *"v1.0 remediation, all v2.0 Phase 1 components"* and lists *"All 4 phases of v1.0 GA remediation (Security, Operational, Quality, Enterprise)"*; the models, routes and the frontend panel all arrive in it, and the mount in `1413159f` the same day | `git log -1 5c800bc`; `git log --diff-filter=A` on each file | shipped in the GA-remediation commit |
| 1.24 | The GA Readiness Audit's remediation items and scoring do not mention organization management, departments or projects | `docs/CORTEXPRIME_V1_GA_READINESS_AUDIT.md` (grep) | not a tracked GA blocker/feature |
| 1.25 | `RELEASE_READINESS.md`, `PRODUCTION_WORKFLOW_READINESS.md`, `OPERATIONS_RUNBOOK.md`, `USER_GUIDE.md`, `README.md` do not mention the directory as a feature | grep | absent |
| 1.26 | The V2 strategic design has "Multi-Organization Collaboration" at priority P3 with *"Single-org isolation"* as the v1 state, and "Org Federation" as a v2 module; `CostAllocation (org_id, department, project)` as a v2 cost-intelligence field | `docs/CORTEXPRIME_V2_STRATEGIC_DESIGN.md:45,231,258` | organizations/departments/projects appear as **v2** concepts |
| 1.27 | No status word — GA, planned, deferred, experimental, placeholder — is attached to the directory anywhere in tracked documentation except the Administrator Guide's present-tense description | grep | **UNKNOWN by omission** |

**INFERENCE:** the repository holds two incompatible signals — an
administrator-facing document that presents the directory as a shipped,
managed capability (1.22, 1.23), and a codebase in which it has never been
reachable, never had a table, never had a UI, and whose only stated reason
for existing was retired (1.6, 1.9–1.13, 1.20–1.21). Neither signal is
strong enough to override the other on repository evidence alone.

### Retirement Impact

**FACT (what breaks):** nothing that currently works. Retiring the three
models, three repositories and four route modules removes endpoints that
answer 500 on every production database (1.6), a panel that renders fixtures
(1.11), and no runtime, governance, tenant, test or CI dependency (1.2, 1.15,
1.19). Follow-ups a retirement would carry: `legacy_persistence_inventory.py:139-150`
(entry), `tenancy_rules.py:101,111,113` (three grandfathered names — the
ratchet test reports stale entries, ADR-116), `tests/test_api_endpoints.py:51-53,109-111`
(file-existence lists), `router_registry.py:1449-1527` (includes),
`docs/ADMINISTRATOR_GUIDE.md §6` (documentation of a non-existent API),
`frontend/components/operations-center/shared.tsx:129` and the mock panel.

**UNKNOWN:** whether any *external* consumer (a customer script, a deployment
not in this repository) calls `/api/api/organizations` or
`/api/organization/departments`. The repository contains no such consumer,
and the endpoints have failed on every migrated database since inception,
which makes an external dependent improbable — but the repository cannot
prove a negative about the outside.

### Durability Requirements If Retained

**FACT (derivable):** one migration for three tables exactly as the models
declare (1.1), with the `index=True`/`unique=True` markers rendered under
SQLAlchemy's names — which touches the open index-convention question only
insofar as new tables add new `ix_*`/`idx_*` names (ADR-116 is not resolved
by it, nor violated). Registration in `models/__init__.py`. Then, to be a
*capability* rather than a table: the doubled prefix fixed (F0.1), the
registry log lines corrected (F0.2), the Administrator Guide re-pointed from
`/api/v1/admin/…` (1.22), the nav link fixed (1.9) and the panel un-mocked
(1.11), plus a decision on where "organizations" and the security centre's
in-memory organizations (1.14) meet. **INFERENCE:** that is a feature build,
not a durability repair.

### Classification

**AMBIGUOUS — ARCHITECTURAL DECISION REQUIRED.**

The technically clean outcome (retire: nothing works, nothing depends) is not
the same as the product outcome, and the repository documents the capability
for administrators (1.22) in the same commit that shipped it under the GA
remediation banner (1.23). Choosing "retire" would be resolving a product
decision by technical convenience; choosing "keep" would be building a
feature nobody has specified beyond a curl example. Hard-stop conditions
met: *repository evidence conflicts* (1.22 vs 1.6–1.13), *GA intent cannot be
established* (1.27), *retaining requires an unmade product decision* (the
directory's purpose after ADR-103/ADR-107).

---

## Decision 2 — Enterprise Operations (`backup_records`, `health_status_snapshots`, `maintenance_events`, `operational_reports`)

### Evidence

| # | Fact | Where | Direction |
|---|---|---|---|
| 2.1 | Models: UUID PK, string status/type, JSONB details, timestamps (`HealthStatusSnapshot` uses `captured_at NOW()`), `idx_*` indexes; **no FKs in or out** | `backend/database/models/backup_record.py:14-30`, `health_status.py:14-33`, `maintenance_event.py:13-24`, `operational_report.py:14-29` | model |
| 2.2 | Model importers: exactly one service each (`backup_service`, `health_center_service`, `maintenance_service`, `operational_reports_service`) plus `tests/test_enterprise_operations.py` | `git grep` (10.23 §0) | model → consumers |
| 2.3 | Each service is a module singleton imported only by its route module (and the test) | `backend/services/*_service.py` last lines; `git grep` over `backend`: only `backend/api/{backup,health_center,maintenance,operational_reports}_routes.py` | consumer → model |
| 2.4 | Routes: backup 6, health-center 4, maintenance 5 (`enable`/`disable` require `require_admin`), reports 3; all `require_user`; registered unconditionally at the doubled paths `/api/api/operations/…` | `backup_routes.py:32-98`, `health_center_routes.py:22-44`, `maintenance_routes.py:33-75`, `operational_reports_routes.py:27-61`; `router_registry.py:1440-1491` | mounting |
| 2.5 | No scheduler, worker, startup hook or other module calls snapshot capture, backup creation, report generation or the maintenance switch | `git grep record_snapshot\|maintenance_service\|is_maintenance_active\|should_block_new_mission` outside the service/route files: none | runtime |
| 2.6 | Executed (10.23): on a migration-built DB every DB-backed endpoint → `UndefinedTableError`, including admin `maintenance/enable` (it logs an event row before flipping the in-memory switch); `backup/list` → 200 (filesystem) | `PHASE_10_23_DISCOVERY.md` §2.2 table | runtime |

### Live Consumers

**FACT:** none outside the route modules (2.3, 2.5). The mission runtime does
**not** consult `MaintenanceState.block_new_missions` — the flag is set and
read only inside `maintenance_service.py` and its routes (2.5), so
"maintenance mode" cannot block anything today.

**FACT (tests):** `tests/test_enterprise_operations.py` unit-tests the
services with `AsyncMock` sessions and a temp `BACKUP_DIR`
(`:47-55`, `:69-135`, `:154-215`); no test drives the routes; no test
touches a database for these models; `test_api_endpoints.py` checks file
existence only.

### Frontend Evidence

| # | Fact | Where |
|---|---|---|
| 2.7 | The Operations Center nav lists **"Backup & Restore"** at `href: "/operations/backup"` — the same non-existent `/operations/*` base as 1.9 | `shared.tsx:139` |
| 2.8 | `backup-panel.tsx` is **mock data** (`// ─── MOCK DATA`) with **no API call** | `frontend/components/operations-center/backup-panel.tsx:43` |
| 2.9 | **No frontend file calls** `/api/operations/*`, `/api/api/operations/*`, `health-center`, `maintenance/banner` or `operations/reports`; no maintenance-banner component exists | `git grep` over `frontend/**`: none |
| 2.10 | `frontend/app/enterprise/operations/page.tsx` is the **connectors** grid (`useConnectors`, `ConnectorGrid`), unrelated | `:3-7` |
| 2.11 | `executive-platform/certification/{health,reports}` pages are certification views, unrelated to these services | path grep |

**INFERENCE:** no production UI reaches any of the four capabilities.

### Runtime Dependencies

**FACT:** none (2.5). **FACT:** the backup capability's *documented* GA
implementation is a different mechanism entirely — `scripts/backup-database.sh`
(`pg_dump` + S3 rotation) and `helm/cortexprime/templates/backup-cronjob.yaml`,
which the GA Readiness Audit scores and marks *"Backup automation ✅ PASS"*
(`docs/CORTEXPRIME_V1_GA_READINESS_AUDIT.md:427-428,440-441,489`), and which
the Administrator Guide §11 and the DR Runbook §2 describe
(`ADMINISTRATOR_GUIDE.md:1225-1268`, `DISASTER_RECOVERY_RUNBOOK.md:70-72`).
None of those documents references `backup_routes`, `backup_service`,
`/api/operations/backup` or `backup_records`.

### Governance / Tenancy Dependencies

**FACT:** none. No tenant column (2.1); no governed importer; the inventory
classifies health/maintenance/report as `KEEP` — *"Observability. Explicitly
not a system of record for anything the platform decides"* — and
`backup_record` as `STRANGLER` — *"Operational metadata. Kept until the
backup subsystem is revisited; nothing in the execution fabric reads it"*
(`legacy_persistence_inventory.py:175-186,225-234`).

### GA Evidence — which operations are functional

| Capability | Functional? | Evidence |
|---|---|---|
| Maintenance switch + event log | **works when the table exists** (10.23: `enable` → 200, one row); **inert** as a control — nothing reads the flag (2.5) | `maintenance_service.py:16-90` |
| Health dashboard (`GET …/health-center`) | probes components in-process, no DB (`get_health_dashboard`, `_probe_component`) — **not driven**; UNKNOWN | `health_center_service.py:56-120` |
| Health snapshot (`GET …/snapshot`) | **broken**: `ResponseValidationError` — the service returns a non-dict (10.23) | `health_center_routes.py:27-33` |
| Health history | works when the table exists (200, empty) | 10.23 |
| Backup create | **broken**: `asyncpg DataError … can't subtract offset-naive and offset-aware datetimes` while inserting `BackupRecord`; the JSON file is written first, so `list` shows a backup the table never recorded (10.23) | `backup_service.py:39-75` |
| Backup restore / rollback | **stub**: `_restore_entity` only logs *"Restore of %s initiated"* and writes nothing; `restore_backup` then reports `status: completed` with `restored_entities` | `backup_service.py:98-141`, `_restore_entity` (one `log.info` line) |
| Backup verify / list / entities | read the filesystem and a hash; `replay_history` entity exports `{"available": True}` only | `backup_service.py:145-165,214-221` |
| Operational report generate | **broken**: `TypeError: can't subtract offset-naive and offset-aware datetimes` (10.23) | `operational_reports_service.py:100-130` |
| Report list / get | work when the table exists (200, empty) | 10.23 |

**FACT:** the inventory calls these `KEEP`/`STRANGLER` (above); the
originating commit is the GA-remediation commit (1.23, "Operational"
phase); the GA Readiness Audit's operational/DR remediation is satisfied by
the pg_dump script and Helm CronJob, not by this API (Runtime Dependencies);
no document labels the API GA, planned, deferred or placeholder (grep over
`docs/`, `README.md`: only the developer guide's file-tree listing,
`developer_guide.md:33`). **UNKNOWN by omission.**

### Retirement Impact

**FACT (what breaks):** nothing that currently works. Removing the four
models, four services and four route modules removes endpoints that answer
500 on every production database (2.6), three of whose write paths are
broken or stubbed even with tables (table above), with no UI (2.7–2.9), no
runtime reader (2.5) and no non-mock test (Live Consumers). Follow-ups a
retirement would carry: `tests/test_enterprise_operations.py` (deleting a
test file is a change the brief forbids without a decision — it is listed,
not proposed), inventory entries L175-186 and L225-234, `router_registry.py:1440-1491`,
`test_api_endpoints.py` lists, `shared.tsx:139`, the mock backup panel.

**FACT (what is *not* affected):** GA backup/DR (`scripts/backup-database.sh`,
the Helm CronJob, the runbooks) — a different mechanism.

**UNKNOWN:** external callers of `/api/api/operations/*` — same reasoning as
Decision 1.

### Durability Requirements If Retained

**FACT (derivable):** one migration for four tables as the models declare
(2.1; no FKs), registration, and — to be a capability — the three code bugs
(backup create datetime, report generate datetime, health snapshot return
type), the restore stub, the doubled prefix, the registry log lines, a
consumer for `MaintenanceState.block_new_missions` if maintenance mode is to
mean anything, and a UI. **INFERENCE:** that is a feature build, and a split
is possible (maintenance is the only one that works end to end when its
table exists).

### Classification

**AMBIGUOUS — ARCHITECTURAL DECISION REQUIRED.**

The evidence is one-sided technically (nothing reaches it, most of it is
broken or stubbed, GA backup is something else) but the inventory says
`KEEP`/`STRANGLER` and the code shipped under the GA-remediation
"Operational" banner; no document declares the API deferred or placeholder.
Hard-stop conditions met: *GA intent cannot be established*, *retaining
requires an unmade product decision* (which of the four, and what
"maintenance mode" must actually block).

---

## Cross-Cutting Findings (relevant to both decisions only)

- **C1.** The doubled mount (F0.1) is common to both groups and to
  `diagnostics_routes` (`router_registry.py:1458-1464`, `/api/api/operations/diagnostics`
  in the boot log). Whichever way the decisions go, the registry's include
  convention for these seven routers is wrong and its log lines misreport
  it (F0.2). Not fixed here.
- **C2.** The Operations Center's `/operations/*` nav base (1.9, 2.7) has no
  pages behind it; ten of its panels are mock data (`audit`, `backup`,
  `licensing`, `models`, `organizations`, `roles`, `runtime`, `secrets`,
  `updates`, `users` — `frontend/components/operations-center/*-panel.tsx`).
  The "no UI" finding is therefore not specific to these two groups; it is
  the state of that whole surface. Relevant because a "keep" decision for
  either group implies deciding the Operations Center's status, which this
  phase was not asked to do.
- **C3.** The persistence inventory (`legacy_persistence_inventory.py`) is
  the only tracked artefact that assigns intent to these seven models, and
  its Decision-1 justification is retired (1.21). It is evidence of what was
  intended in July, not of what is decided now.
- **C4.** The Administrator Guide documents an admin API family
  (`/api/v1/admin/organizations…`) that never existed (F0.2). Any "keep"
  decision inherits a documentation-vs-implementation conflict; any
  "retire" decision leaves a guide section describing a removed feature.

## Architectural Decision Required

Two decisions, stated in their smallest form. Each is a product-scope
question the repository cannot answer:

1. **Is the V1 organizational directory — organizations / departments /
   projects, as an administrator-managed org chart distinct from governed
   tenancy (ADR-103) — a CortexPrime GA capability?**
   *Yes* → the durability-if-retained list under Decision 1 becomes a
   bounded implementation phase (migration + mount + docs + UI).
   *No* → a bounded retirement phase (models, repositories, four route
   modules, inventory entry, three ratchet names, the guide section, the nav
   link, the mock panel).

2. **Does the enterprise-operations API — backup/restore, health-center,
   maintenance mode, operational reports — ship in GA, in whole or in part?**
   *Whole* → migration for four tables + the three bugs + the restore stub +
   a real maintenance consumer + UI. *Part* (e.g. maintenance only) → the
   subset's migration and the rest retired. *None* → a bounded retirement
   phase (four models, four services, four route modules, one test module,
   two inventory entries, the nav link, the mock panel). GA backup/DR is
   unaffected either way.

## Scope Integrity

- no production code changed — `git status --short` shows only this document
- no migrations changed — `versions/` untouched, head `0025_mission_replay_events`
- no tests changed
- no indexes changed — the 86 operations untouched
- no Alembic behaviour changed — `env.py`, `alembic.ini` untouched
- no governance changed — no file under `backend/auth`, `contexts`, `platform`, `contracts`, `assurance`, `world` touched
- no database created, dropped or written; no Redis key written

## Final Status

**STOPPED — ARCHITECTURAL DECISION REQUIRED** (both decisions).
