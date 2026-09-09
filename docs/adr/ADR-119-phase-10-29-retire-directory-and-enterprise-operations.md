# ADR-119 — Retire the V1 organizational directory and the enterprise-operations API/model surface; keep GA backup/DR

- **Status:** ACCEPTED
- **Date:** 2026-09-09
- **Phase:** 10.29
- **Parents:** `34b1892` — Phase 10.28 dependency gate; `e464c22` — Phase 10.27 GA-surface discovery; ADR-117 (decisions 1 and 2), ADR-118 (decision 3, resolved separately)
- **Evidence:** `docs/PHASE_10_27_GA_SURFACE_DISCOVERY.md`, `docs/PHASE_10_28_ENTERPRISE_OPS_DEPENDENCY_GATE.md`, `docs/PHASE_10_23_DISCOVERY.md` (executed route/DB evidence), `docs/PHASE_10_29_IMPLEMENTATION_MAP.md`, `docs/PHASE_10_29_VERIFICATION_REPORT.md`

> **Numbering.** Highest used is 118; this is 119. Nothing overwritten.

## Context

Phase 10.22 found seven tracked ORM models that no migration created and the
registry did not import. Phase 10.23 established by execution that they were
reachable only through routes mounted at `/api/api/…` since their first
commit, failed with `UndefinedTableError` on every migration-built database,
and had no table on any database; it stopped rather than decide whether the
features they belonged to were part of GA. Phase 10.27 traced both
capability groups in both directions and found the repository's intent
ambiguous — an administrator guide documenting an API that never existed, an
inventory `KEEP` resting on retired reasons, a mock-data UI behind a dead
navigation base. Phase 10.28 ran the final dependency census for the
enterprise-operations group: zero live production consumers, zero operator
workflows, zero scheduler/worker/recovery/monitoring dependencies, mission
admission never gated by maintenance state, GA backup/DR a separate
`pg_dump` mechanism. The product decision was then made: both surfaces are
not part of the GA architecture.

## Evidence (summarised; the phase reports carry the citations)

**Organizational directory** (`organizations`, `departments`, `projects`):
three route modules plus `organization_department_routes`, three
repositories, three models. Mounted at `/api/api/organizations` etc. since
`1413159f`; the one correctly-mounted endpoint 500'd on every migrated
database. Frontend: `organizations-panel.tsx` was `MOCK DATA`, its nav link
pointed at a non-existent `/operations/*` base, no client called any
directory endpoint, and the wiring report listed departments/projects as "no
backend endpoint yet". `ADMINISTRATOR_GUIDE.md §6` documented
`/api/v1/admin/organizations…`, which never existed. ADR-103 had rejected
the tables as tenancy ("a directory feature, not an authorization
boundary"); IAM, the inventory's stated dependent, was retired in ADR-107.
No runtime, governance, tenant, test or CI dependency.

**Enterprise operations** (`backup_records`, `health_status_snapshots`,
`maintenance_events`, `operational_reports`): four services, four route
modules, four models, mounted at `/api/api/operations/…`. Three of four
write paths were broken or stubbed (backup create and report generate failed
on naive/aware datetimes; `_restore_entity` only logged and then reported
`completed`; health snapshot returned a non-dict). `should_block_new_mission()`
had no caller in any commit, so maintenance mode never gated admission;
`docs/architecture.md:849` documented a runtime call that was never built,
and §14 a report schedule with no scheduler. `backup-panel.tsx` was mock;
no client called any endpoint. The GA Readiness Audit's backup automation
is `scripts/backup-database.sh` + the Helm `backup-cronjob.yaml`, which
never referenced the API or the table.

**Schema (real PostgreSQL, Phase 10.29 gate):** none of the seven tables
existed in any of the 18 databases on the instance; no foreign key
referenced them; no migration ever created them (`0021`/`0022` mention
`organizations` in prose only). There was no data to lose.

## Decision

1. **V1 organizational directory → RETIRE.** Models, repositories, the four
   route modules, the registry entries, the mock panel and page, the dead
   navigation link, the inventory entry, the three grandfathered ratchet
   names, the administrator-guide section and the endpoint-list test entries.
2. **Enterprise-operations API/model surface → RETIRE.** Models, services,
   the four route modules, the registry entries, the mock panel and page,
   the dead navigation link, the inventory entries, the API-reference and
   architecture sections, and the tests that covered only that surface.
3. **GA backup/DR infrastructure → KEEP.** `scripts/backup-database.sh` and
   `helm/cortexprime/templates/backup-cronjob.yaml` are untouched, as are
   the Administrator Guide §11 and the Disaster Recovery Runbook §2 that
   document them.

## Rationale

CortexPrime's production surface is the governed loop — signal, detect,
investigate, understand, decide, govern, act, verify, learn. Every surface
that ships must have a real product purpose and a defensible contract. These
two groups had neither: they were unreachable at their documented paths from
the day they were wired, had no table on any database, no client, no
consumer, no operator procedure, and — for enterprise operations — did not
work even when their tables existed. Keeping them would have meant carrying
seven unmigrated models that a development boot creates and production
never has, an inventory whose justifications had been retired, and
documentation describing an API that does not exist. Retiring them removes
scaffold, not capability.

## Alternatives rejected

- **Keep and make durable** (migrate seven tables, fix the doubled mount,
  fix three code bugs and a restore stub, wire a maintenance consumer,
  un-mock two panels, re-point the guide). A feature build for features
  nobody has specified beyond a curl example; ADR-117 and 10.27 refused to
  make that product decision by technical default, and the product decision
  went the other way.
- **Defer** (leave as-is). Leaves seven production defects unowned — 500s on
  documented endpoints, a `create_all`/migration divergence, a documented
  runtime integration that does not exist — and keeps autogenerate blind to
  seven tables.
- **Build/fix them now.** Same as the first alternative with less
  justification.

## Scope

**Removed (30 tracked files):** `backend/database/models/{organization,
department,project,backup_record,health_status,maintenance_event,
operational_report}.py`; `backend/database/repositories/{organization,
department,project}_repository.py`; `backend/api/{organization,department,
project,organization_department,backup,health_center,maintenance,
operational_reports}_routes.py`; `backend/services/{backup,health_center,
maintenance,operational_reports}_service.py`;
`frontend/components/operations-center/{organizations,backup}-panel.tsx`;
`frontend/app/operations-center/{organizations,backup}/{page,error,loading}.tsx`.

**Edited (10 tracked files):** `backend/api/router_registry.py` (eight
include blocks removed; diagnostics untouched); `backend/platform/architecture/tenancy_rules.py`
(three grandfathered names of deleted repositories removed);
`backend/api/legacy_persistence_inventory.py` (directory and backup entries
replaced by retirement notes; the operations entry now names only
`runtime_analytics.py`; the mission-replay entry updated from `REPLACE` to
`KEEP` per ADR-118); `tests/test_api_endpoints.py` (the three retired route
files removed from its lists); `tests/test_enterprise_operations.py`
(diagnostics tests kept; the four retired service classes, their route-import
tests and the model-import tests removed); `frontend/components/operations-center/shared.tsx`
(two nav entries and their icon imports); `docs/api.md` §34, §35, §36, §38;
`docs/architecture.md` §11–14; `docs/ADMINISTRATOR_GUIDE.md` §6;
`docs/developer_guide.md` (four tree lines). Plus one verification script: `scripts/phase1010_tenant_record_harness.py` (check A5 read the retired model file by path; it now proves the same property by module resolution and a table-declaration search when the file is absent — found only when the harness chain ran, because the inventory grep matched names, not paths).

## Preservation

Diagnostics (`diagnostics_routes`, `diagnostics_service`, its tests, `api.md`
§37), the whole Operations Center apart from the two retired pages, mission
replay (ADR-118, migration 0025), the governed tenancy/membership/authority/
approval/execution/assurance/worker/connector/credential/audit surfaces, the
security centre's in-memory organizations, the mission `MAINTENANCE`
category, GA backup/DR, every historical phase report and migration, and the
86 open index operations (ADR-116). The doubled `/api` prefix on the
retained `diagnostics_routes` is deliberately not fixed here.

## Schema impact

None. No migration is added: the seven tables never belonged to the
canonical Alembic schema (no migration created them, none exists on any
database), so there is nothing to drop and no lineage to extend. Head remains
`0025_mission_replay_events`. Autogenerate on a fresh head is the same 86
index-only operations as the 10.22 inventory, byte-identical; `alembic check`
is still red on exactly those and is not claimed clean. The `create_all`
census — ORM metadata minus migration-built tables — is now empty: for the
first time development metadata and production schema agree table-for-table.

## Runtime impact

None observable. The retired routes answered 500 (or 404 at their documented
paths) on every production-shaped database; nothing in the runtime imported
the models or services; maintenance state was never consulted by mission
admission; no scheduler or worker existed. The `availability` dict returned
by `register_all_routers` loses eight keys that nothing read.

## Verification

Recorded in `docs/PHASE_10_29_VERIFICATION_REPORT.md`: whole-repository
reference census after removal (zero production references); real registry
on a bare app (retired paths absent, diagnostics/replay/approvals/security
present); fresh database 25 migrations / 57 tables with the seven absent;
existing head database 0 migrations, schema and row fingerprints identical
before and after, and identical to the fresh database; autogenerate 86 ==
10.22 inventory; `create_all` census empty; targeted tests (only the three
pre-existing baseline failures); frontend vitest 14/14 and a tsc error set
confined to four untouched files; GA backup/DR files byte-unchanged;
architecture, regression and governed harnesses as reported there.

## Future reconsideration

If organizational management or enterprise operations (backup UI, health
snapshots, maintenance mode, operational reports) becomes a real product
requirement, it returns as an explicit product/architecture phase — with a
specification, a migration, a mounted API, a client and tests — rather than
regrowing from scaffold. The governed tenancy model (ADR-102/103) is the
organizational boundary the platform enforces today.
