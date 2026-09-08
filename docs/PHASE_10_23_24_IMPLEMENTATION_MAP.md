# Phase 10.23 + 10.24 — Implementation Map

- **Parent:** `65d465c` — Phase 10.22 (ADR-116)
- **Discovery:** `docs/PHASE_10_23_DISCOVERY.md`
- **ADR:** ADR-117 (highest used: 116)
- **Status:** **Stage B (10.24) NOT ENTERED.** The brief's gate — *"ONLY enter
  Stage B if Stage A produces no architectural stop"* — is closed: all eight
  models are `STOP_ARCHITECTURAL_DECISION`.

## Discovery baseline (recorded before any implementation would have started)

- Tree `65d465c`, clean. Alembic head `0024_approval_store`, single lineage.
- Fresh DB (`alembic upgrade head`): 24 migrations, 56 tables, none of the eight.
- Existing head DB `cortex_p1014_legacy`: none of the eight; schema fingerprint
  `264072c9896946f9f62ec0d9d2b24554` (unchanged since 10.22).
- Autogenerate: 86 index-only operations (10.22 inventory, untouched here).
- No database on the instance holds any of the eight tables.

## What was NOT done, and why

| Item | Reason |
|---|---|
| Any migration | Stage B gate closed; a migration for any of the eight would encode a product/architecture answer the repository does not contain |
| Any change to `router_registry.py` (the doubled `/api/api` prefix) | outside schema scope; and fixing it presupposes the directory/operations features ship |
| Any change to the 86 index operations | forbidden by the brief; untouched, re-confirmed by not running autogenerate into `versions/` |
| Any change to the legacy persistence inventory | its entries are the *evidence* of the collision; rewriting them is the decision itself |
| Retiring routes/repositories/models | live runtime code; the brief forbids deleting it without a `RETIRE_*` authorisation |

## What each decision would authorise (for the phase that follows)

**Decision 1 = yes (directory ships):**
`0025_org_directory` — `organizations`, `departments`, `projects` exactly as
the models declare (UUID PK `gen_random_uuid()`, timestamps `NOW()`, JSONB
`metadata`, the two CASCADE FKs and one SET NULL FK, uniques on `domain`,
`key`, `(organization_id, name)`, the `idx_*` indexes; the `index=True` markers
and `unique=True` markers are then subject to the open index-convention
decision, ADR-116) with the `0023`/`0024` existence guard; register the three
in `models/__init__.py`; fix the doubled prefix in the registry; replace the
mock panel with real calls. **Decision 1 = no:** delete the 3 route modules +
`organization_department_routes`, 3 repositories, 3 models, inventory L140,
and the four grandfathered ratchet names.

**Decision 2 = yes (operations ship):** `0026_enterprise_operations` for the
four tables; fix `backup_service` and `operational_reports_service` naive/aware
datetimes and `health_center_service.get_health_snapshot`'s return type; fix
the prefix. **No:** delete 4 route modules, 4 services, 4 models, inventory
L176/L226, `tests/test_enterprise_operations.py`.

**Decision 3 = durable:** `0025_mission_replay_events` from the model (no FKs,
three composite indexes), register the model, raise `_db_append`'s failure log
from DEBUG to WARNING (behaviour otherwise unchanged). **Decision 3 = remove:**
delete `_db_append`, `_pg_fetch` and the model; `get_events` becomes
Redis-only explicitly.

Each is one bounded phase with the 10.19/10.20 verification shape: fresh DB,
existing DB fingerprint, `create_all` census, `alembic check` before/after with
the 86 unchanged, real write-and-read-back, gates and harnesses.
