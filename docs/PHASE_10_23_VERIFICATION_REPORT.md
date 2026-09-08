# Phase 10.23 + 10.24 — Verification Report

- **Parent:** `65d465c` — Phase 10.22 (ADR-116)
- **Discovery:** `docs/PHASE_10_23_DISCOVERY.md` · **ADR:** ADR-117
- **Date:** 2026-09-08
- **Outcome:** **STOPPED after Stage A.** No implementation, so the Stage B
  verification matrix (A–J in the brief) has nothing to verify; what follows
  verifies the *discovery* claims, each by execution, and records the
  unchanged state of everything Stage B would have had to protect.

Labels: `[VERIFIED]` executed and observed · `[NOT VERIFIED]` inferred ·
`[DEFERRED]` · `[STOP]`.

## 1. Summary

| Claim | Result |
|---|---|
| Eight tracked models (not seven) are unregistered and unmigrated | `[VERIFIED]` census over every tracked model file: `organizations`, `departments`, `projects`, `backup_records`, `health_status_snapshots`, `maintenance_events`, `operational_reports`, **`mission_replay_events`**; registry-only-unmigrated set is empty |
| None exists in any migration-built or existing database; no data anywhere | `[VERIFIED]` fresh DB 24/56/0; `cortex_p1014_legacy` 0 of 8; every database on the instance 0 of 8 |
| `create_all` would create exactly the seven, plus the eighth after the first replay write | `[VERIFIED]` metadata census; `mission_replay_events` absent from metadata until `replay_store.record()` runs |
| Directory/operations routes are mounted at `/api/api/…` since `1413159f` | `[VERIFIED]` boot log paths + `git blame`; `GET /api/organizations` → 404, `GET /api/api/organizations` → 401 without a token |
| Every DB-backed endpoint of the seven fails on a migration-built DB | `[VERIFIED]` 12 calls → `UndefinedTableError`, including the correctly-mounted `/api/organization/departments` and the admin write `maintenance/enable` |
| With the tables present the code persists (where it is not itself broken) | `[VERIFIED]` `POST organizations` → 201, 1 row; `maintenance/enable` → 200, 1 row; `backup/create` → 500 (`DataError` naive/aware datetime, row lost, file written); `health-center/snapshot` → `ResponseValidationError`; `reports/generate` → `TypeError` |
| `mission_replay_events` is written on every V1 bus event and silently lost | `[VERIFIED]` table absent: `record()` returns normally, DEBUG `replay_store DB write skipped: … UndefinedTableError`, Redis has the event; table present: 1 row |
| No frontend consumer of the seven; replay endpoints documented | `[VERIFIED]` grep over `frontend/` (1,881 tracked files): the organizations panel is mock data; wiring report lists departments/projects as "no backend endpoint yet"; developer portal documents `/api/mission-replay/…` |
| Governance untouched | `[VERIFIED]` no governed package imports the models or the V1 event bus; nothing changed, so no governed request was re-run — `[NOT VERIFIED]` as a re-execution, deliberately, because there is no change to verify against |
| Provider writes | **0** — no Kubernetes, GitHub or cloud call; the probe wrote to a disposable database and to the local Redis (keys deleted) |
| Stage B entered | **No** `[STOP]` — three architectural decisions recorded in ADR-117 |

## 2. Stage A probes — method

All probes ran from this tree (`65d465c`, ignored files present but
irrelevant: none of the eight, their routes or services is gitignored).

- `cortex_p1023_fresh`: created empty, `alembic upgrade head` → exit 0, 24
  `Running upgrade` lines, 56 tables.
- `p1023_meta.py`: `import backend.database.models` (registry + bounded
  contexts) → `Base.metadata` vs the 56; then import the eight route modules →
  diff.
- `p1023_probe.py`: a `FastAPI()` with the eight routers included **exactly as
  `router_registry.py:1440-1527` includes them** (`prefix="/api"` for seven,
  none for `organization_department_routes`); the real
  `backend.database.session.get_session` → `AsyncSessionLocal` → engine on
  `POSTGRES_URL=…/cortex_p1023_fresh`; bearer tokens minted by the real
  `create_access_token` (no `tenant_id`, so `require_user` takes the V1 path
  and does not consult the tenant store); `TestClient(raise_server_exceptions=True)`
  so the real exception is recorded. Phase 1 on the migration-built DB; Phase
  2 after `Base.metadata.create_all(tables=[the eight])` — the dev-boot path,
  restricted so no other table is touched.
- `p1023_probe2.py`: `POST …/backup/create` with a supported entity.
- `p1023_probe3.py`: `replay_store.record()` with the store's logger at DEBUG,
  single event loop; table present, then `DROP TABLE`, then again.

Known probe artefact: in Phase 2 the first `GET /api/api/organizations` hit
the anyio "attached to a different loop" error because the async engine had
already been used from the outer `asyncio.run` loop before the `TestClient`
portal — the pooled-asyncpg-across-loops trap the memory notes record. The
immediately following calls on the same router (POST 201, GET departments 200,
GET projects 200) show the route itself works; the artefact is the probe's,
not the code's.

## 3. Results — verbatim

```
PHASE 1 — migration-built DB; present: all eight False
  GET  /api/organizations                         -> 404
  GET  /api/api/organizations                     -> UndefinedTableError: relation "organizations" does not exist
  GET  /api/api/organizations (no token)          -> 401 Authentication required
  POST /api/api/organizations                     -> UndefinedTableError: "organizations"
  GET  /api/organization/departments              -> UndefinedTableError: "departments"
  GET  /api/api/departments                       -> UndefinedTableError: "departments"
  GET  /api/api/projects                          -> UndefinedTableError: "projects"
  GET  /api/api/operations/backup/list            -> 200 {"backups":[],"total":0}        (filesystem, not DB)
  GET  /api/api/operations/health-center/history  -> UndefinedTableError: "health_status_snapshots"
  GET  /api/api/operations/health-center/snapshot -> UndefinedTableError: "health_status_snapshots"
  GET  /api/api/operations/maintenance/events     -> UndefinedTableError: "maintenance_events"
  POST /api/api/operations/maintenance/enable     -> UndefinedTableError: "maintenance_events"
  GET  /api/api/operations/reports/list           -> UndefinedTableError: "operational_reports"
  POST /api/api/operations/reports/generate       -> UndefinedTableError: "operational_reports"
  replay_store.record(): returned normally; DEBUG "replay_store DB write skipped: … UndefinedTableError";
                         get_events -> 1 (Redis); table present=False

PHASE 2 — after create_all for the eight; present: all True
  POST /api/api/organizations                     -> 201 {"organization":{"id":"91397989-…","name":"Probe Org",…
  GET  /api/organization/departments              -> 200 {"departments":[],"total":0,…}
  GET  /api/api/departments                       -> 200 · GET /api/api/projects -> 200
  POST /api/api/operations/backup/create          -> 500  asyncpg DataError: invalid input for query argument $5 …
                                                          (can't subtract offset-naive and offset-aware datetimes)
                                                          backup file written; backup_records rows = 0
  GET  /api/api/operations/health-center/history  -> 200 · snapshot -> ResponseValidationError (non-dict response)
  GET  /api/api/operations/maintenance/events     -> 200 · POST enable (admin) -> 200, maintenance_events rows = 1
  GET  /api/api/operations/reports/list           -> 200 · POST generate -> TypeError naive/aware datetimes
  replay_store.record(): 1 row in mission_replay_events; after DROP TABLE: silent skip again
ROWS: organizations 1, maintenance_events 1, mission_replay_events 1 (probe3), all others 0
```

## 4. Unchanged state (what Stage B would have had to protect)

| Item | State after this phase |
|---|---|
| Working tree | only the four documents added; `git diff --stat` on code: empty |
| Migration history | `versions/` untouched; single head `0024_approval_store` |
| The 86 index-only operations | untouched; no autogenerate run into `versions/`; no suppression added |
| Existing head DB `cortex_p1014_legacy` | not migrated, not written; fingerprint `264072c9…` |
| Governed tables `cp_*`/`cw_*` | not referenced by any probe |
| Provider writes | 0 |
| Disposable state | `cortex_p1023_fresh` dropped; Redis keys `cx:replay:*p1023*` deleted (0 remain); backup temp dirs are OS temp files |

## 5. Gates

Not re-run: no tracked code changed, so the Phase 10.22 results for this tree
stand — architecture 155, regression 76F/6778P/36S/58X/24E (one
non-reproducible failure under external load), harnesses 10.7–10.14 as
recorded in `PHASE_10_22_VERIFICATION_REPORT.md` §4.8. Re-running them against
an identical tree would verify nothing about this phase.
