# PHASE 10.28 — ENTERPRISE OPERATIONS DEPENDENCY GATE

- **Date:** 2026-09-09
- **Nature:** discovery only — one dependency census before the ADR-117
  decision-2 retirement/keep choice. Nothing modified, retired, fixed or
  committed except this report.
- **Method:** `git grep` over the complete tracked repository (backend,
  frontend, scripts, helm, infra, docker-compose, `.github`, docs, tests) for
  each model class and module, each service module and singleton, every
  service method, `block_new_missions` / `should_block_new_mission` /
  `is_maintenance_active` / `MaintenanceState`, each table name as a string,
  and every HTTP path form the routers, the registry log lines and the docs
  use; plus `git log -S` for history. Phase 10.23's executed route evidence is
  cited where it bears on function.

Classification vocabulary (exactly one per reference): `LIVE_PRODUCTION_CONSUMER`,
`OPERATIONAL_DOCUMENTATION_CONSUMER`, `TEST_ONLY`, `DEAD_SCAFFOLD`,
`MOCK_ONLY`, `HISTORICAL_REFERENCE`. Excluded by the brief: the models' own
definitions, the route modules that only expose the endpoints, tests that only
test the endpoint, mock frontend data that does not call the API. A model's
own service is not a consumer.

## Repository State

| | |
|---|---|
| HEAD | `e464c22` (Phase 10.27 report) ← `8de3060` (10.25+10.26) ← `3adf9bc` (ADR-117) |
| Branch | `phase-1-foundation` |
| Working tree | clean at start; clean at end except this report |

## Common findings (all four)

- **F1 — one importer each, and it is the model's own service.**
  `backup_record` ← `services/backup_service.py:13`; `health_status` ←
  `services/health_center_service.py:11`; `maintenance_event` ←
  `services/maintenance_service.py:10`; `operational_report` ←
  `services/operational_reports_service.py:9`. No other tracked file imports
  any of the four classes or modules (the only other hits are
  `tests/test_enterprise_operations.py:378-391`, which assert `__tablename__`
  strings, and phase documents).
- **F2 — each service is imported by exactly one route module and by the test
  module.** `backup_routes.py:12`, `health_center_routes.py:11`,
  `maintenance_routes.py:12`, `operational_reports_routes.py:12`;
  `tests/test_enterprise_operations.py` (mock `AsyncMock` sessions, temp
  `BACKUP_DIR`). No worker, scheduler, recovery, monitoring, execution,
  mission-runtime, context, platform, event or startup module references any
  of them (`git grep` over `backend/workers`, `worker*`, `scheduler*`,
  `runtime`, `monitoring`, `recovery`, `observability`, `execution`,
  `mission`, `contexts`, `platform`, `core`, `events`,
  `services/mission_runtime.py`, `main.py`: **0 hits**). No scheduler
  library exists in the backend at all (`apscheduler|aiocron|croniter|
  BackgroundScheduler|AsyncIOScheduler`: 0).
- **F3 — no deployment, CI or operational script references them.** `helm/`,
  `infra/`, `scripts/`, `docker-compose*.yml`, `.github/`, `Dockerfile*`,
  `Makefile`: **0 hits** for any model, service, route module, table name or
  `/api/operations` path.
- **F4 — no runbook or guide invokes them.** `OPERATIONS_RUNBOOK.md`,
  `DISASTER_RECOVERY_RUNBOOK.md`, `TROUBLESHOOTING_GUIDE.md`,
  `ADMINISTRATOR_GUIDE.md`, `SECURITY_GUIDE.md`, `USER_GUIDE.md`: **0 hits**
  for "maintenance mode", "health center", "operational report",
  `/api/operations`, "backup API", "restore API".
- **F5 — no frontend client.** `frontend/services/**`, `hooks/**`, `lib/**`,
  `store/**`: no fetch of any of these paths; the only Operations Center
  reference is the mock `backup-panel.tsx` and a nav link to a non-existent
  `/operations/backup` (10.27 §2.7–2.9).
- **F6 — the endpoints are served at `/api/api/operations/…`** (doubled
  prefix, `router_registry.py:1441-1486`), while the API reference
  (`docs/api.md` §34–38, lines 3648-3800) documents them at
  `/api/operations/…` and the registry's own log lines claim `/api/backup`,
  `/api/health-center`, `/api/maintenance`, `/api/operational-reports`
  (`router_registry.py:1442,1470,1479,1488`). No document or client uses the
  path that is actually served.
- **F7 — two documents describe the subsystems:** `docs/api.md` §34–38 (request/
  response reference) and `docs/architecture.md` §11 Health Center, §12
  Backup & Restore, §13 Maintenance Mode, §14 Operational Reports (lines
  642-930), both from the same commit as the code (`9d15d77`/`5c800bc`,
  2026-07-18) and untouched since. They describe endpoints and intended
  behaviour; neither is an operator procedure, and neither is referenced by
  any runbook.
- **F8 — history.** All four services and route modules have exactly one
  commit, `5c800bc` (2026-07-18). `git log -S"should_block_new_mission"` finds
  only `5c800bc` and the 10.27 report; `git log -S"maintenance_service"` over
  `services/mission_runtime.py`, `mission/`, `execution/`, `runtime/`: none —
  **no caller was ever wired and later removed**.

## backup_records

- **Live consumers:** none. `BackupRecord` is written by
  `backup_service.create_backup` (`:39-46`) and read by `_get_record` (`:246-251`);
  both are reached only from `backup_routes.py` (`:45-93`). Executed (10.23):
  `create` fails inserting the record (`asyncpg DataError`, naive/aware
  datetime) after the JSON file is written; `restore`/`rollback` call
  `_restore_entity`, which only logs (`backup_service.py`, one `log.info`
  line) and then report `status: completed`.
- **Operational consumers:** none. `docs/architecture.md` §12 and `docs/api.md`
  §35 describe the API (`OPERATIONAL_DOCUMENTATION_CONSUMER`, descriptive
  only — no runbook or script invokes it). `diagnostics_service.py:108-116`
  lists the environment-variable *name* `BACKUP_DIR` in its configuration
  report — an env-name read, no import of the model/service, no table access
  (`DEAD_SCAFFOLD` coupling by name only; diagnostics is outside this scope).
- **Classification of references:** service methods → own service (not a
  consumer); `backup_routes.py` → endpoint exposure (excluded);
  `tests/test_enterprise_operations.py:67-146` → `TEST_ONLY` (temp dir, no
  DB); `backup-panel.tsx` → `MOCK_ONLY`; `docs/api.md` §35,
  `docs/architecture.md` §12 → `OPERATIONAL_DOCUMENTATION_CONSUMER`
  (descriptive); `legacy_persistence_inventory.py:225-234` (`STRANGLER`,
  "nothing in the execution fabric reads it") → `HISTORICAL_REFERENCE`.
- **Retirement impact:** no code path that works today is lost; the JSON
  export files under `data/backups` (default) are not consumed by anything.
  Documentation §12/§35 and the inventory entry would describe a removed
  feature.

## health_status_snapshots

- **Live consumers:** none. Written by `health_center_service.save_snapshot`
  (`:180-191`), read by `get_snapshot_history` (`:197-201`); reached only
  from `health_center_routes.py:31,39`. Nothing schedules a snapshot (F2).
  Executed (10.23): `snapshot` → `ResponseValidationError` (non-dict);
  `history` works with the table. `get_health_dashboard`/`get_cached_status`
  are in-process probes with no DB and are not part of this table's
  dependency set.
- **Operational consumers:** none. `docs/architecture.md` §11 (line 740:
  "Snapshots are written to the `health_status_snapshots` table … for
  historical analysis") and `docs/api.md` §34 → `OPERATIONAL_DOCUMENTATION_CONSUMER`
  (descriptive). No monitoring stack (Prometheus/Grafana assets, `helm/`,
  `infra/`) references the table or the endpoints (F3).
- **Classification:** tests `:26-64` → `TEST_ONLY` (mock session); docs →
  descriptive; inventory L175-186 (`KEEP`, "Observability … not a system of
  record") → `HISTORICAL_REFERENCE`.
- **Retirement impact:** no consumer of history exists; the dashboard probe
  endpoints, if retained, do not need the table.

## maintenance_events

- **Live consumers:** none. Written by `maintenance_service.enable`/`disable`
  (`:57-64`, `:83-89`), read by `get_event_history` (`:112-113`); reached
  only from `maintenance_routes.py:40,56,79`.
- **`block_new_missions` consumers — SPECIAL CHECK:**
  - **Who calls it:** `MaintenanceState.block_new_missions` is set in
    `maintenance_service.enable` and read by
    `maintenance_service.should_block_new_mission()`; that method is called
    by **nobody in production code**. Whole-repository hits for
    `should_block_new_mission|is_maintenance_active|MaintenanceState|
    block_new_missions|allow_existing_missions|maintenance_active|
    get_maintenance_state|maintenance_mode`: the service, its routes,
    `tests/test_enterprise_operations.py:149-215`, `docs/api.md:3767-3768`,
    `docs/architecture.md:820-849`, and the 10.27 report. **Zero
    `LIVE_PRODUCTION_CONSUMER` references.**
  - **When:** only on an admin `POST …/maintenance/enable` (never issued by
    any client, F5).
  - **Mission admission:** **unchanged by maintenance state.** The mission
    runtime, admission, approval, execution and orchestration paths never
    import or query the service (F2, F8). `MissionType.MAINTENANCE`
    (`backend/mission/models.py:38`) and the auto-approve category
    `"maintenance"` (`backend/mission/approval.py:57`) are a mission
    *category*, unrelated to maintenance mode.
  - **Workers / execution / recovery / monitoring / scheduler:** none
    observe it (F2, F3).
  - **Frontend:** nothing invokes enable/disable/banner/status (F5); there is
    no maintenance-banner component.
  - **Operator workflow:** no runbook or script (F3, F4).
  - **Documentation conflict, stated explicitly:** `docs/architecture.md:849`
    says `should_block_new_mission()` is *"Called by Mission Runtime before
    starting missions"*. **That call does not exist and never has** (F8).
    The document promises a behaviour the runtime does not implement; it is
    not evidence of a hidden dependency — it is evidence that the documented
    integration was never built.
- **Classification:** tests → `TEST_ONLY`; `docs/api.md` §36,
  `docs/architecture.md` §13 → `OPERATIONAL_DOCUMENTATION_CONSUMER`
  (descriptive, and in one line inaccurate); inventory L175-186 →
  `HISTORICAL_REFERENCE`; `should_block_new_mission()` itself →
  `DEAD_SCAFFOLD` (a hook with no caller).
- **Retirement impact:** no mission admission, execution, worker or recovery
  behaviour changes, because none depends on it today. The only functional
  loss is an admin-only in-memory switch that nothing reads and an audit
  table nothing queries.

## operational_reports

- **Live consumers:** none. Written by `generate_report` (`:121-129`), read
  by `list_reports`/`get_report` (`:93-106`); reached only from
  `operational_reports_routes.py:39,52,65`. `generate_daily/weekly/monthly_report`
  have no caller outside the service and tests (the other `generate_report`
  symbols in `enterprise_analytics_*`, `enterprise_engineering_*`,
  `enterprise_memory_*` are unrelated services). Executed (10.23):
  `generate` → `TypeError` (naive/aware datetime); `list`/`get` work with
  the table.
- **Operational consumers:** none. `docs/architecture.md` §14 documents a
  "Report Schedule" (daily/weekly/monthly windows) — **no scheduler exists**
  (F2) — and "Reports are stored in the `operational_reports` table"
  (`:926`); `docs/api.md` §38. Both → `OPERATIONAL_DOCUMENTATION_CONSUMER`
  (descriptive; the schedule is unimplemented).
- **Classification:** tests `:269-340` → `TEST_ONLY`; docs → descriptive;
  inventory L175-186 → `HISTORICAL_REFERENCE`.
- **Retirement impact:** none at runtime; §14/§38 would describe a removed
  feature.

## GA Backup/DR Separation

| | Enterprise Operations backup API (A) | GA database backup/DR (B) |
|---|---|---|
| Code | `backend/services/backup_service.py`, `backend/api/backup_routes.py`, model `backup_records` | `scripts/backup-database.sh` (`pg_dump` at `:46`, retention `find … -delete` at `:72`); `helm/cortexprime/templates/backup-cronjob.yaml` (`pgvector/pgvector:pg16` image running `pg_dump`, `:21-26`) |
| What it produces | JSON exports of application entities (six named entities; `replay_history` exports `{"available": true}`) under the service's `BACKUP_DIR` (default `data/backups`, `backup_service.py:17`) | PostgreSQL dumps (`cortexprime_*.dump`) under the script's own `BACKUP_DIR` variable (default `./backup`, `backup-database.sh:26`) with S3 upload/rotation |
| References to `backup_records` / the service / the routes | — | **none** in either file (grep: `pg_dump`, `psql`, `find` only; no `python`, `curl`, `api`, `backup_records`) |
| Documented by | `docs/api.md` §35, `docs/architecture.md` §12 | `ADMINISTRATOR_GUIDE.md` §11 (`:1225-1268`), `DISASTER_RECOVERY_RUNBOOK.md` §2 (`:70-72`), GA Readiness Audit (`:427-428,440-441,489` "Backup automation ✅ PASS") |
| Depends on the other | no | no |

The two `BACKUP_DIR` names are a coincidence of naming with different
defaults and different producers; there is no shared code or data path.
**B is independent of `backup_records` and of the API; it is not part of any
retirement.**

## Final Dependency Result

**B. ZERO LIVE DEPENDENCIES — RETIREMENT DECISION SAFE**

Stated per the brief's hard-stop list: no genuine production consumer
exists; no operator workflow depends on these APIs (F3, F4); maintenance
state does **not** affect mission admission (no caller, never had one);
the backup API does **not** participate in GA DR (separate `pg_dump`
mechanism); no hidden worker/scheduler dependency exists (F2, and no
scheduler library in the backend); documentation does not reveal a
contractual dependency invisible in code — it reveals the reverse, a
documented integration (`architecture.md:849`) and a documented schedule
(`:905-910`) that were never implemented; and retirement, if chosen, needs
no further architectural decision. What retirement would carry, for the
record and not as a recommendation: four models, four services, four route
modules, `tests/test_enterprise_operations.py`, inventory entries L175-186
and L225-234, registry includes `:1440-1491` and their log lines,
`docs/api.md` §34–38, `docs/architecture.md` §11–14, the mock `backup-panel.tsx`
and nav link `shared.tsx:139`. Whether to retire remains the product
decision recorded in the 10.27 report; this gate establishes only that
nothing in production would notice.
