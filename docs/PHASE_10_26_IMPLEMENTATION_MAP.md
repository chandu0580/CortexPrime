# Phase 10.26 — Implementation Map: mission replay durable persistence

- **Parent:** `3adf9bc` — Phase 10.23 (ADR-117)
- **Discovery:** `docs/PHASE_10_25_DISCOVERY.md` (GO) · **ADR:** ADR-118
- **Written before the code, from the discovery's evidence.**

## Discovery baseline

Tree `3adf9bc`, clean. Alembic head `0024_approval_store`, one lineage. Fresh
DB 24 migrations / 56 tables, `mission_replay_events` absent everywhere.
Autogenerate on a fresh head: 86 index-only operations (the 10.22 inventory);
with the model registered and no migration it would be 92. Architecture 155;
regression baseline from 10.22 (76F / 6778P / 36S / 58X / 24E, one failure
non-reproducible under external load). The new model is the only definition;
compiled DDL recorded in `p1025_ddl.py`.

## Changes — the minimum the discovery requires

| # | File | Change | Why (discovery §) |
|---|---|---|---|
| 1 | `backend/database/models/__init__.py` | import `MissionReplayEvent`; add to `__all__` | the table must reach Alembic metadata and a dev boot's `create_all` without waiting for the first replay write (§E) |
| 2 | `backend/database/migrations/versions/0025_mission_replay_events.py` (new) | `create_table` + five indexes, hand-written from the compiled model DDL, existence-guarded (0023/0024 convention), reversible `downgrade` | no migration ever created the table (§H) |
| 3 | `backend/services/mission_replay_store.py` `_db_append` | failure log DEBUG → WARNING, naming execution and sequence; swallow unchanged | a lost durable copy must be visible (§G) |
| 4 | `backend/services/mission_replay_store.py` `_pg_fetch` | each row dict also carries `timestamp` = `event_ts` | the store's own readers (`get_summary`, `get_timeline`) and every route read `timestamp`; a PostgreSQL-served replay lost its timeline (§C) |
| 5 | `backend/api/mission_replay_routes.py` `list_replays` | an empty Redis window falls back to PostgreSQL, as an unavailable Redis already did | the docstring promises "falls back to PostgreSQL for historical data"; the trigger was wrong (§C) |
| 6 | `tests/database/test_mission_replay_persistence.py` (new) | real bus → real store → independent SQL → Redis present → keys deleted → PostgreSQL-served readers and routes; explicit-failure path; migrated table == model | anti-vacuity (§F, §G) |

**Not changed:** Redis behaviour (keys, TTL, LTRIM, counter); the swallow;
`record()`'s filter and field mapping; every route's response shape (the
`timestamp` field already existed and was `None` when served from
PostgreSQL); the seven unresolved models; the 86 index operations; any
historical migration; the persistence inventory (its `REPLACE` entry is
recorded in ADR-118 as superseded by this decision, and left for the phase
that rewrites the inventory).

## Migration review (against the compiled DDL, not autogenerate)

| Model | Migration | Note |
|---|---|---|
| `id UUID PK server_default gen_random_uuid()` | same | mixin |
| `execution_id String(255) NOT NULL index=True` | column + `ix_mission_replay_events_execution_id` | SQLAlchemy's own name for the marker; the same way `0004` carried `ix_cost_tracking_*` |
| `sequence Integer NOT NULL default=0` | `NOT NULL`, no server default | Python-side default is the model's, not the schema's |
| `status`/`message` Python defaults | no server default | same |
| `event_ts String(64) NULL`, `latency_ms Float NULL`, `payload JSONB NULL` | same | `JSONB.with_variant(JSON, "sqlite")` as 0024 |
| `created_at`/`updated_at TIMESTAMPTZ NOT NULL server_default NOW()` | same | mixin |
| three `idx_replay_exec_*` composites + `agent index=True` | five indexes total | exactly the set `create_all` produces |
| no FK, no unique | none | the model has none; adding uniqueness would be invented semantics and would break the documented sequence-reuse case |

Verification of exactness: the table fingerprint (columns, types, lengths,
nullability, defaults, index definitions, constraints) of a `create_all`-only
table must equal the migration-built table's — that equality is the
"production schema and ORM metadata agree" proof.

## Verification plan

Fresh DB (25 migrations, 57 tables, `\d`), guard path (a DB that already has
the table from `create_all` upgrades without error and unchanged), existing
head DB (fingerprint of every other table and every row count identical),
downgrade/upgrade round-trip, single head; autogenerate before (92, six replay
ops) and after (86, byte-identical to the 10.22 inventory), `alembic check`
kinds; `create_all` census (the seven unchanged); the new tests; two canaries
(migration absent → tests fail; store/route repairs stashed → tests fail);
the Stage A probe re-run on a migration-built head DB; architecture,
regression, harnesses 10.7–10.14, 10.19 readiness, 10.20 write-path; provider
writes 0; clean-up of every disposable database, temporary revision and Redis
key.
