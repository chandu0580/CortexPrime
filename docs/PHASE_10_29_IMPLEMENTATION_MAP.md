# Phase 10.29 — Implementation Map: retire the organizational directory and the enterprise-operations surface

- **Parent:** `34b1892` — Phase 10.28 (dependency gate, result B) ← `e464c22` — Phase 10.27
- **ADR:** ADR-119 · **Verification:** `docs/PHASE_10_29_VERIFICATION_REPORT.md`
- **Decisions executed:** directory → RETIRE; enterprise operations → RETIRE; GA backup/DR → KEEP; mission replay untouched (ADR-118); the 86 index operations untouched (ADR-116).

## Preflight (verified, not assumed)

HEAD `34b1892`, parent `e464c22`, branch `phase-1-foundation`, working tree
clean, highest ADR 118, PostgreSQL/Redis/k3d containers up.

## Final implementation inventory (before any deletion)

A whole-repository `git grep` for every module, class, table name, path form
and panel name found **only** the references Phases 10.27/10.28 had listed,
plus three prose mentions that are not consumers and are not changed:
`backend/database/durable/tables.py:1086` (a comment inside governed
durable code), `versions/0022_tenant_record.py:16` (a historical migration
docstring), `docs/RELEASE_READINESS.md:59` (a historical readiness note).
`tests/test_enterprise_operations.py` was found to be **mixed** — it also
covers diagnostics, which is retained — so it is edited, not deleted.
`frontend/app/operations-center/{organizations,backup}/` each also held a
per-segment `error.tsx`/`loading.tsx`; they belong exclusively to the
retired segments and go with their pages.

## Database gate (real PostgreSQL, before deletion)

All 18 databases on the instance: none of the seven tables present. No FK
references them. No migration created them (`0021`/`0022` mention
`organizations` in prose). **No durable data; no migration required
(outcome 1).**

## Changes

| Group | Removed | Edited |
|---|---|---|
| Directory | `models/{organization,department,project}.py`; `repositories/{organization,department,project}_repository.py`; `api/{organization,department,project,organization_department}_routes.py`; `frontend/components/operations-center/organizations-panel.tsx`; `frontend/app/operations-center/organizations/{page,error,loading}.tsx` | `router_registry.py` (4 blocks); `tenancy_rules.py` (`DepartmentRepository`, `OrganizationRepository`, `ProjectRepository`); `legacy_persistence_inventory.py` (entry → retirement note); `tests/test_api_endpoints.py` (3 names × 3 lists + 3 prefix entries); `shared.tsx` (nav + `Building2` import); `ADMINISTRATOR_GUIDE.md` §6 |
| Enterprise operations | `models/{backup_record,health_status,maintenance_event,operational_report}.py`; `services/{backup,health_center,maintenance,operational_reports}_service.py`; `api/{backup,health_center,maintenance,operational_reports}_routes.py`; `frontend/components/operations-center/backup-panel.tsx`; `frontend/app/operations-center/backup/{page,error,loading}.tsx` | `router_registry.py` (4 blocks); `legacy_persistence_inventory.py` (backup entry → note; operations entry keeps `runtime_analytics.py` only); `tests/test_enterprise_operations.py` (diagnostics kept); `shared.tsx` (nav + `HardDrive` import); `docs/api.md` §34/35/36/38; `docs/architecture.md` §11–14; `docs/developer_guide.md` tree |
| Inventory reconciliation | — | mission-replay entry `REPLACE` → `KEEP` per ADR-118 (the brief's L110 item) |
| Verification script (found during the gates) | — | `scripts/phase1010_tenant_record_harness.py` check A5: read the retired model by path; now proves the property by execution when the file is absent (verification report §3) |

**Deliberately not changed:** `diagnostics_routes`/service/tests and `api.md`
§37; the doubled `/api` prefix on retained routers; `backend/services/diagnostics_service.py:108`
(lists the `BACKUP_DIR` env-var *name*); `security_center` organizations;
`MissionType.MAINTENANCE`; `scripts/backup-database.sh`;
`helm/cortexprime/templates/backup-cronjob.yaml`; every migration; the 86
index operations; the ten other mock Operations Center panels; the
`CostRepository`/`FleetRepository` ratchet names (ADR-116 finding, unrelated
to this retirement); the three prose mentions above.

## Verification plan

Whole-repository reference census; real registry mounting on a bare app;
`create_all` census; fresh DB (`alembic upgrade head`, PostgreSQL inspected);
existing head DB (0 migrations, schema/row fingerprints identical);
autogenerate vs the 86; targeted tests; frontend tsc + vitest; GA backup/DR
files byte-unchanged; architecture; regression (same scope as 10.22);
harnesses 10.7–10.14; 10.19 readiness; 10.20/10.26 tests; provider writes 0;
one commit; clean tree.
