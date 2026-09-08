# Phase 10.23 — Discovery: the live, unmigrated tracked models

- **Parent:** `65d465c` — Phase 10.22 (ADR-116)
- **ADR:** `docs/adr/ADR-117-phase-10-23-unmigrated-live-models.md`
- **Date:** 2026-09-08
- **Outcome:** **STOPPED before Stage B.** Every one of the eight models is
  `STOP_ARCHITECTURAL_DECISION`; three distinct product/architecture questions
  are recorded in the ADR. Nothing implemented. No migration. No code change.

Labels: `[VERIFIED]` executed and observed · `[NOT VERIFIED]` inferred from
reading · `[DEFERRED]` deliberately not done · `[STOP]` a stop condition fired.

---

## 0. Scope correction: eight models, not seven

The brief names seven. A census of every tracked model file
(`git ls-files backend/database/models`, each `__tablename__` checked against
the registry, the migration lineage and its importers) finds **one more** in
the same state — no registry import, no migration ever, tracked consumers:

| Table | Model file | Registered | Migration | Tracked importers |
|---|---|---|---|---|
| `organizations` | `organization.py` | no | none | `api/organization_routes.py`, `repositories/organization_repository.py`, `models/department.py` |
| `departments` | `department.py` | no | none | `api/department_routes.py`, `api/organization_department_routes.py` (via repo), `repositories/department_repository.py`, `models/organization.py` |
| `projects` | `project.py` | no | none | `api/project_routes.py`, `repositories/project_repository.py` |
| `backup_records` | `backup_record.py` | no | none | `services/backup_service.py` |
| `health_status_snapshots` | `health_status.py` | no | none | `services/health_center_service.py` |
| `maintenance_events` | `maintenance_event.py` | no | none | `services/maintenance_service.py` |
| `operational_reports` | `operational_report.py` | no | none | `services/operational_reports_service.py` |
| **`mission_replay_events`** | `mission_replay.py` | no | none | `services/mission_replay_store.py` (lazy, inside functions), `api/mission_replay_routes.py` (lazy) |

`mission_replay_events` did not appear in Phase 10.22's boot-created set
because its only imports are *inside functions*: the model reaches
`Base.metadata` — and therefore `create_all` — only after the first replay
write. It is the most consequential of the eight (§4).

All eight were added in the same commit, `5c800bc` (2026-07-18, "Commit all
unstaged work — v1.0 remediation, all v2.0 Phase 1 components"); their routes
were wired in `1413159f` the same day. No migration has ever named any of the
eight tables (`grep` over every `versions/*.py`; `git log -S` over the
migrations directory finds only prose mentions in `0021`/`0022`, quoted in §2).
`infra/postgres/init.sql` never created them either.

---

## 1. Database evidence `[VERIFIED]`

| Check | Result |
|---|---|
| Fresh DB, `alembic upgrade head` (this tree): `cortex_p1023_fresh` | 24 migrations, 56 tables, **0 of the eight present** |
| Existing head DB `cortex_p1014_legacy` (`0024`) | **none of the eight present** |
| Every database on the instance (`pg_database`, all non-template) | **no database has any of the eight tables** — there is no durable data anywhere on this machine; no stopped container or volume holds a CortexPrime database either |
| Which migration creates / references / FKs to any of them | none / none (prose only) / none |
| `create_all` set: `Base.metadata` after importing the eight route modules, minus the 56 migration tables | exactly the seven; `mission_replay_events` joins only after `replay_store.record()` runs |
| Registry-only tables not migrated | `[]` — the registry itself is clean |

---

## 2. Per-model findings

### 2.1 `organizations` / `departments` / `projects` — the V1 organisational directory

**Definition.** UUID PK (`gen_random_uuid()`), `TimestampMixin`, JSONB
`metadata`; `departments.organization_id → organizations.id ON DELETE CASCADE`;
`projects.organization_id → organizations.id CASCADE`,
`projects.department_id → departments.id SET NULL`; uniques on
`organizations.domain`, `projects.key`, `(projects.organization_id, name)`;
explicit `idx_*` indexes plus `index=True` markers. Repositories extend
`BaseRepository` over the real `AsyncSession`.

**Runtime consumers.**
- Route modules `organization_routes`, `department_routes`, `project_routes`
  (5 endpoints each, `require_user`) and `organization_department_routes` (1
  endpoint) — all registered by `router_registry.py:1449-1527`.
- **Mounted at the wrong path since inception `[VERIFIED]`.** Each router
  declares `prefix="/api/organizations"` (etc.) *and* the registry includes it
  with `prefix="/api"`, so the effective paths are `/api/api/organizations`,
  `/api/api/departments`, `/api/api/projects` — the 10.22 boot log lists them
  exactly so, while the registry's own log line says "registered at
  /api/organization". `git blame`: `1413159f`, 2026-07-18. The one router
  without the doubled prefix, `organization_department_routes`, mounts
  correctly at `/api/organization/departments`.
- **Frontend `[VERIFIED]`.** `frontend/app/operations-center/organizations/page.tsx`
  and `organizations-panel.tsx` exist — and the panel is **mock data**
  (`// ─── MOCK DATA`, `const ORGANIZATIONS: Organization[] = [...]`, no API
  call). `frontend/REALTIME_DATA_WIRING_REPORT.md:213-214` lists *Departments
  → `/api/organization/departments`* and *Projects → `/api/projects`* under
  "Data Categories Still Needing Backend APIs — wired to return empty arrays
  since no backend endpoints exist yet." No frontend file calls any of these
  endpoints. The security page's `/api/security/organizations` is a
  different, in-memory thing (`security_center/identity.py`, a dict).
- Tests: `tests/test_api_endpoints.py` asserts the route *files exist* and use
  an auth dependency; nothing drives them.

**Executed `[VERIFIED]`** (real routers mounted exactly as the registry does,
real `get_session` → `AsyncSessionLocal` on `cortex_p1023_fresh`, real token
from `create_access_token`):

| Call | Migration-built DB | After `create_all` (dev path) |
|---|---|---|
| `GET /api/organizations` | 404 | 404 (the doubled prefix, not the DB) |
| `GET /api/api/organizations` (no token) | 401 | 401 |
| `POST /api/api/organizations` | `UndefinedTableError: relation "organizations"` | **201**, one row persisted |
| `GET /api/organization/departments` (correct mount) | `UndefinedTableError: "departments"` | 200 `{"departments":[]}` |
| `GET /api/api/departments`, `GET /api/api/projects` | `UndefinedTableError` | 200 |

So the code is functional and durable when the tables exist, and every one of
these endpoints fails on every migration-built — i.e. every production —
database.

**Persistence intent.** `legacy_persistence_inventory.py:140-150` says `KEEP`,
owner *"IAM / org structure"*, callers *"IAM routes and services"*, tenant
model *"these tables largely define tenancy"*, risk *"identity depends on
them"*. Every one of those reasons is now false: IAM was retired in Phase 10.14
(`0023_retire_iam`, ADR-107); ADR-103 (Phase 10.10) evaluated `organizations`
for tenancy and **rejected** it — *"an org-chart entity with departments,
served by organization_routes … a directory feature, not an authorization
boundary"*; migrations `0021`/`0022` say in their docstrings that
`organizations` *"is live, but an organization is not a tenant and carries no
tenant_id"*; and `tenancy_rules.py:65` deliberately omits `organization_id`
from tenant parameters. The inventory's `KEEP` therefore rests on a
justification the repository has since retired, and nothing else in the
repository states what the directory is *for*.

**Governance.** No governed package (`auth`, `contexts`, `platform`,
`contracts`, `assurance`, `world`) imports these models; `contracts/tenant.py`'s
`organization_id` is an `OrganizationContext` string, not a reference to this
table. Tenant, membership, authority, approval, execution, worker, connector,
credential and audit are untouched by any outcome. `[VERIFIED]` by grep;
governed harnesses were not re-run because nothing was changed.

**Dynamic reachability.** No string reference to the table names outside the
models, the routes' response keys and the inventory; no `Table()` reflection,
no `importlib` target, no plugin loading names them.

### 2.2 `backup_records` / `health_status_snapshots` / `maintenance_events` / `operational_reports` — "enterprise operations"

**Definition.** UUID PK + timestamps (health snapshots: `captured_at`
`server_default NOW()` instead of `TimestampMixin`), string status/type
columns, JSONB detail columns, `idx_*` indexes; no FKs in or out.

**Runtime consumers.** `backup_routes` (6), `health_center_routes` (4),
`maintenance_routes` (5, writes need `require_admin`), `operational_reports_routes`
(3) — registered at `router_registry.py:1440-1491`, **all with the same doubled
prefix**: `/api/api/operations/backup/…`, `…/health-center/…`,
`…/maintenance/…`, `…/reports/…` (boot log `[VERIFIED]`). The four services are
module singletons used only by their route module (and by
`tests/test_enterprise_operations.py`, which passes an `AsyncMock` session).
No scheduler, worker or startup hook calls `record_snapshot`, backup creation
or report generation. **No frontend file references any of these paths.**

**Executed `[VERIFIED]`:**

| Call | Migration-built DB | After `create_all` |
|---|---|---|
| `GET …/backup/list` | 200 (reads the filesystem) | 200 |
| `POST …/backup/create` (supported entity) | not reached | **500** — `asyncpg DataError … can't subtract offset-naive and offset-aware datetimes` while inserting the `BackupRecord`; the backup *file* was written first, so the list then shows a backup the table never recorded |
| `GET …/health-center/history` | `UndefinedTableError` | 200 `{"snapshots":[]}` |
| `GET …/health-center/snapshot` | `UndefinedTableError` | **`ResponseValidationError`** — the service returns a non-dict |
| `GET …/maintenance/events` | `UndefinedTableError` | 200 |
| `POST …/maintenance/enable` (admin) | `UndefinedTableError` — even the in-memory maintenance switch cannot be flipped, because it logs an event row first | **200**, one `maintenance_events` row persisted |
| `GET …/reports/list` | `UndefinedTableError` | 200 |
| `POST …/reports/generate` | `UndefinedTableError` | **`TypeError: can't subtract offset-naive and offset-aware datetimes`** |

Three of the four write paths carry bugs that any single real invocation would
have surfaced — evidence that none has ever been exercised against a
database, in any environment. Only `maintenance_events` works end to end.

**Persistence intent.** Inventory: `backup_record` = `STRANGLER` (*"kept until
the backup subsystem is revisited; nothing in the execution fabric reads
it"*); `health_status`/`maintenance_event`/`operational_report` = `KEEP`,
*"Observability. Explicitly not a system of record for anything the platform
decides."* None of the entries notes that nothing creates the tables.

**Governance.** None. No governed importer; no FK; `maintenance_service`'s
"block new missions" flag is an in-memory `MaintenanceState` that nothing in
the governed execution path reads (`grep` over `backend/contexts`,
`backend/auth`: 0 hits).

### 2.3 `mission_replay_events` — the V1 replay store's "permanent" layer

**Definition.** UUID PK + timestamps; `execution_id String(255) index`,
`sequence int`, `event_type String(64)`, `agent String(128) index`, `status`,
`message Text`, `event_ts String(64)`, `latency_ms Float`, `payload JSONB`;
three composite `idx_replay_exec_*` indexes; **no foreign keys** (`execution_id`
is a free string).

**Runtime consumers — this one is live in production `[VERIFIED]`.**
- **Writer:** `backend/events/event_bus.py:99` — `publish()` schedules
  `replay_store.record(event)` for **every** event on the V1 bus. `record()`
  filters by event type, appends to Redis (`cx:replay:{execution_id}`, 72 h
  TTL), then calls `_db_append()` — one `MissionReplayEvent` row — which
  **swallows every failure at `log.debug`** (`"replay_store DB write skipped"`).
  `engineering_decision_engine.py:989` also calls `record()` directly.
- **Readers:** `mission_replay_routes` (`/api/mission-replay/{execution_id}`,
  `/graph`, `/timeline` — mounted correctly), `enterprise_replay_routes`
  (`/api/enterprise-replay/*`, eight endpoints), `governance_center_routes:675`,
  `enterprise_knowledge_routes:192`, `enterprise_context_intelligence:672`.
  `get_events()` reads Redis first and falls back to `_pg_fetch()` — the
  PostgreSQL layer is what is supposed to answer once the 72 h TTL has expired.
  The developer portal documents `curl …/api/mission-replay/exec-123`.

**Executed `[VERIFIED]`** (real `replay_store`, real Redis, `cortex_p1023_fresh`,
`DEBUG` captured on the store's logger):

| State | `record()` | Log | `get_events()` | Table |
|---|---|---|---|---|
| table absent (every migration-built DB) | returns normally | `replay_store DB write skipped: … UndefinedTableError: relation "mission_replay_events"` — at DEBUG, invisible at any production log level | 1 event, from Redis | — |
| table present (`create_all`) | returns normally | nothing | 1 event | **1 row persisted** |

So in production every mission event's durable copy has been silently
discarded since `5c800bc`; replay works for 72 hours and then returns
nothing. This is the ADR-114 `cost_tracking` defect class — a persistence
failure converted into apparent success — on the busiest write path in the V1
runtime.

**Persistence intent — and the collision.** The model, the store's docstring
("Layer 2 — PostgreSQL (cold / permanent) … long-term audit trail") and the
code all say *durable*. But the tracked
`legacy_persistence_inventory.py:110-121` classifies `mission_replay.py` as
**`REPLACE`**: *"Replay in the governed fabric reconstructs facts from the
execution record and the outbox, both of which are durable as of Phase 5.1 and
neither of which this table feeds. Superseded in substance already."* The
repository therefore holds two contradictory positions: a live writer that
promises permanence, and an architectural decision that the table is
superseded and should not be the thing made durable.

**Governance.** The governed packages do not import or publish to
`backend.events.event_bus` (`grep` over `auth`, `contexts`, `platform`,
`assurance`, `world`, `intelligence`: 0 importers), so the replay store carries
**V1** mission events only; the governed audit trail is the fenced audit
storage (`0013`) and the `cw_*` substrate, neither of which this table feeds.
A migration would not change governance semantics — but it would make durable
a V1 audit trail the inventory says is superseded, which *is* an architectural
choice (stop condition 9), and "audit" is in the brief's governance list.

---

## 3. Classification

| Model | Classification | Why not the others |
|---|---|---|
| `organizations`, `departments`, `projects` | **`STOP_ARCHITECTURAL_DECISION`** | `ADD_MIGRATION` would create schema for a feature no client reaches (doubled prefix since inception, UI is mock data, wiring report says "no backend endpoint yet") on the strength of an inventory entry whose every stated reason was retired by 10.10/10.14; `RETIRE_MODEL` has no registration to remove — retiring means deleting routes, repositories and models, which is live runtime code the brief forbids deleting without a decision; not `DEFERRED`, because the production state (500 on every call, including the correctly-mounted `/api/organization/departments`) is a defect that needs an owner |
| `backup_records`, `health_status_snapshots`, `maintenance_events`, `operational_reports` | **`STOP_ARCHITECTURAL_DECISION`** | same shape: unreachable paths, no UI, three of four write paths carry never-exercised bugs; the inventory's `KEEP`/`STRANGLER` does not say whether these endpoints ship in GA |
| `mission_replay_events` | **`STOP_ARCHITECTURAL_DECISION`** | live writer + readers, clear durable contract, clean schema, no FKs, no data — `ADD_MIGRATION` is *mechanically* ready; but the tracked inventory says `REPLACE`/"superseded", so making it durable or removing its PostgreSQL layer is a decision about which replay is the product's replay, not a migration |

No model is `RETIRE_TABLE` (no table exists anywhere), `RECONCILE` (no
migration to reconcile against) or `DEFERRED` (each has a production defect
attached).

## 4. Stop conditions — which fired, with evidence

| # | Condition | Fired? | Evidence |
|---|---|---|---|
| 1 | live consumer, unclear persistence contract | **yes** (replay) | writer + readers live; inventory says the table should not exist |
| 2 | existing durable data | no | no database on the instance has any of the eight |
| 3 | FK ambiguity | no | directory FKs are internal to the trio; others have none |
| 4 | model/migration disagree materially | no | there is no migration |
| 5 | intended persistence not establishable from repository evidence | **yes** (directory, operations) | inventory reasons retired; no UI, no reachable path, no ADR states the feature's GA status |
| 6 | API contract with unclear source of truth | no | contracts are the models' `to_dict()` |
| 7 | tenant/governance semantics would change | no | proven separate (ADR-103, 0021/0022, tenancy_rules) |
| 8 | provider/execution path would change | no | — |
| 9 | architectural boundary ownership unclear | **yes** (all eight) | directory vs governed tenancy: ADR-103 separated them, decided nothing about the directory; V1 replay vs governed replay: inventory `REPLACE` vs live writer |
| 10 | unrelated autogenerate ops not isolable | n/a | no migration attempted; the 86 untouched |
| 11 | classification would invent semantics | **yes** if forced | deciding "ships in GA" or "which replay is canonical" is not derivable from code |
| 12 | vacuous verification | no | every claim above was driven through the real route/store against a real database (§1, §2) |

## 5. The three decisions (smallest form)

1. **The V1 organisational directory** (`organizations`/`departments`/`projects`,
   3 route modules + `organization_department_routes`, 3 repositories, 3
   models, inventory entry L140): **ships in GA — yes or no?**
   *Yes* → one migration for three tables (schema fully specified by the
   models; fresh + existing DB verified), fix the doubled prefix, and the UI
   panel stops being mock data. *No* → retire routes, repositories, models and
   the inventory entry; nothing else references them.
2. **The enterprise-operations endpoints** (backup / health-center /
   maintenance / operational-reports; 4 route modules, 4 services, 4 models,
   inventory entries L176 and L226): **ship in GA — yes or no?**
   *Yes* → one migration for four tables plus the three code bugs found in
   §2.2 and the doubled prefix. *No* → retire. (A split — e.g. keep
   maintenance, drop the rest — is also a valid answer; it is the only one of
   the four that works.)
3. **Mission replay's PostgreSQL layer**: **make it durable, or remove it?**
   *Durable* → one migration for `mission_replay_events` (ready: model is the
   only source, no FKs, no data, writer/readers unchanged) and raise the
   swallowed-write log level. *Remove* → delete `_db_append`/`_pg_fetch` and
   the model, and accept that replay is Redis-only for 72 h until the governed
   replay the inventory promises exists.

Until these are answered, Stage B is not entered — by the brief's own gate.

## 6. Evidence files

Session scratchpad: `p1023_meta.py` (metadata census), `p1023_upgrade.log`,
`p1023_probe.py` / `p1023_probe.out` (routes + replay, both phases),
`p1023_probe2.py` (backup create), `p1023_probe3.py` (replay with DEBUG).
Disposable database `cortex_p1023_fresh` dropped; probe Redis keys deleted.
