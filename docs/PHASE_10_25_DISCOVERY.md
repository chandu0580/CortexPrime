# Phase 10.25 — Discovery: mission replay persistence

- **Parent:** `3adf9bc` — Phase 10.23 (ADR-117)
- **ADR:** `docs/adr/ADR-118-phase-10-25-26-mission-replay-durable.md`
- **Date:** 2026-09-08 / 09
- **Outcome:** **GO for Stage B.** PostgreSQL is the intended durable layer;
  Redis is the hot window; Alembic owns the schema and the model is its only
  definition; the swallow is intentional design that must become explicit.
  No stop condition fired.

Labels: `[VERIFIED]` executed and observed · `[NOT VERIFIED]` inferred from
reading · `[DEFERRED]` · `[STOP]`.

---

## A. Model — `backend/database/models/mission_replay.py` `[VERIFIED]`

`MissionReplayEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base)`, table
`mission_replay_events`. Compiled by SQLAlchemy (`CreateTable`) the contract is:

| Column | Type | Null | Default | Semantics (from the model's own docstring/comments) |
|---|---|---|---|---|
| `id` | UUID | no | `gen_random_uuid()` (server) + `uuid4` (client) | row identity |
| `execution_id` | String(255) | no | — | *"primary grouping key — every event of the same mission run shares it"*; `index=True` |
| `sequence` | Integer | no | Python `0` (no server default) | *"monotonically increasing per execution, assigned by the store so playback can ORDER BY sequence"* |
| `event_type` | String(64) | no | — | canonical replay type |
| `agent` | String(128) | no | — | `index=True` |
| `status` | String(32) | no | Python `"info"` | |
| `message` | Text | no | Python `""` | |
| `event_ts` | String(64) | yes | — | *"wall-clock ISO timestamp when the event was emitted; `created_at` is when the row was written"* |
| `latency_ms` | Float | yes | — | |
| `payload` | JSONB | yes | Python `dict` | *"free JSONB column holding all extra context"* |
| `created_at`, `updated_at` | TIMESTAMPTZ | no | `NOW()` | row write time |

Primary key `id`. **No foreign keys** — `execution_id` is a free string.
**No unique constraints.** Indexes: `idx_replay_exec_seq (execution_id, sequence)`,
`idx_replay_exec_type (execution_id, event_type)`, `idx_replay_exec_agent
(execution_id, agent)` plus the two `index=True` markers (SQLAlchemy names them
`ix_mission_replay_events_execution_id`, `ix_mission_replay_events_agent`).
Ordering: by `sequence` within `execution_id`. Retention fields: none — the
model has no TTL/expiry; the docstring calls it a *"Persistent log"*.
Timestamp semantics: two clocks, emitted (`event_ts`) vs written (`created_at`).

**Model vs migrations:** no migration in `versions/` names the table
(`grep` all 24; `git log -S` finds nothing) — the model has been unmigrated
since `5c800bc`. **Model vs store:** `_db_append` writes exactly these columns;
`_pg_fetch` selects the model and returns `to_dict()`. **Model vs routes:**
`ReplayEventSchema` (all replay-specific fields `Optional`, `extra="allow"`)
accepts both shapes. **Model vs tests:** no test asserted a PostgreSQL row
before this phase. **Model vs docs/ADRs:** the GA readiness audit calls the
runtime *"dual-layer replay"*; no ADR mentions this table; the tracked
persistence inventory classifies the file `REPLACE` (§D).

## B. Writers `[VERIFIED]`

| Writer | Path | Frequency | Sync? | Failure |
|---|---|---|---|---|
| `backend/events/event_bus.py:99` | `publish()` → `asyncio.ensure_future(replay_store.record(event))` | **every** event published on the V1 bus (agents, orchestrator, `publish_event()` helper) | fire-and-forget background task; `publish()` returns before the write | `record()` never raises; the bus logs only if *scheduling* fails |
| `engineering_decision_engine.py:989` | direct `await replay_store.record(...)` | per engineering decision | awaited | same |

`record()` filters on `REPLAY_EVENT_TYPES`/`_CANONICAL` and requires
`execution_id`; assigns `sequence` via Redis `INCR` (in-memory counter if Redis
is down); `_redis_append` (RPUSH, LTRIM 2000, EXPIRE 72 h; in-memory list on
failure); then `_db_append` — one row, own session, `commit`; **any exception
swallowed, logged at DEBUG**: *"Silently no-ops if DB is down."*

Driven for real (`p1025_probe.py`, three events through `event_bus.publish` and
`publish_event`, real Redis, migration-built DB):

- **Table absent (every production DB before this phase):** `publish()`
  returns, subscribers receive all three, Redis holds three (`ttl 259199 s`,
  `seq 3`), three `DEBUG replay_store DB write skipped: … UndefinedTableError`
  lines, and after the Redis keys are deleted every route answers **404** —
  the replay is gone.
- **Table present:** three rows, `payload` and `latency_ms` intact,
  `event_ts` = the event's `timestamp`; Redis and PostgreSQL carry the same
  `sequence` per event.
- Redis and PostgreSQL are written **in that order, both unconditionally** —
  dual stores, not primary/backup.
- **Ordering:** `sequence` is assigned inside `record()`, which runs as a
  background task, so under a burst the sequence order can differ from publish
  order (observed: seq 1 = `tool_called`, seq 2 = `mission_started`). Redis
  list order is append-completion order and may differ again (observed
  `[1, 3, 2]` served from Redis). The contract is *order by store sequence*,
  and both layers agree on the sequence of each event.
- **Idempotency:** none. If the Redis `seq` counter is lost (TTL, flush,
  restart) a later event of the same execution reuses `1` (observed
  `[1, 1, 2, 3]` in PostgreSQL). The model declares no uniqueness; exactly-once
  is not claimed anywhere and is not introduced here.

## C. Readers `[VERIFIED]`

| Reader | Store call | Needs PostgreSQL for | Works from Redis? | Historical? | Missing vs failed distinguishable? | Ordering contractual? | Window/pagination | Tenant |
|---|---|---|---|---|---|---|---|---|
| `mission_replay_routes` `/api/mission-replay/{id}`, `/timeline`, `/graph` | `get_summary`, `get_timeline`, `get_graph` | anything older than 72 h | yes | yes — the page is linked from mission history | no: empty ⇒ 404 "No replay data" | yes: `sequence`; graph steps are cumulative per step | none (whole execution) | none — `require_user` only |
| `mission_replay_routes` `/api/mission-replay/` (list) | Redis `KEYS`, PG `DISTINCT execution_id` **only on exception** | listing executions after the window | yes | yes | no | — | `limit` | none |
| `enterprise_replay_routes` (8 endpoints, `/api/enterprise-replay/*`) | `get_timeline`, `get_summary` ×13 call sites | same | yes | yes (export, decisions, costs…) | no | yes | agent/type filters | none |
| `governance_center_routes:675` | `get_events` | execution stage timeline | yes | yes | no | yes | none | none; already reads `event_ts or timestamp` |
| `enterprise_knowledge_routes:192` | `get_summary("__recent__")` | — (sentinel id, always `found: False`) | — | — | — | — | — | — |
| `enterprise_context_intelligence:672` | `get_events(id, 0, 20)` | context of past executions | yes | yes | no | yes | slice 0–20 | none |
| frontend `app/replay/[execution_id]`, `enterprise-replay/*` pages, `services/replayService.ts`, `mission-control/missions.ts` | the routes above | *"animated by recorded timestamps"* | — | — | — | — | — | — |

Driven for real: all five route families return 200 from Redis; **after Redis
deletion with the table present** they return the same events from
PostgreSQL — but before this phase's repair with `timestamp`, `offset_ms`,
`first_ts`, `duration_ms` all `None` (the PG row is keyed `event_ts`), and the
listing empty (its fallback triggers only on a Redis *exception*, not an empty
window). `event_id`, `phase`, `confidence_score`, `token_usage`,
`original_type` are **not in the model** and cannot be served from PostgreSQL;
the schema marks them `Optional` and no reader keys on `event_id` (the
frontend uses it only as a React key with a fallback).

## D. Redis vs PostgreSQL responsibility `[VERIFIED]`

| | Redis | PostgreSQL |
|---|---|---|
| Role stated by the store | *"Layer 1 — Redis (hot) … TTL 72 h … sub-second reads, live playback"* | *"Layer 2 — PostgreSQL (cold / permanent) … long-term audit trail, graph queries, timeline reconstruction for any past execution"* |
| Retention | `REPLAY_REDIS_TTL_HOURS` (72) and `REPLAY_MAX_EVENTS_REDIS` (2000, LTRIM) | none; nothing prunes the table |
| Read order | first (`_redis_fetch`) | fallback (`_pg_fetch`, *"fallback / long-term storage"*) |
| Sequence authority | `INCR` counter (TTL 72 h) | stores the number it is given |
| Source of truth | for the live window | for history — the only place a replay exists after 72 h |
| Corroboration | GA readiness audit: *"dual-layer replay"*; `list_replays` docstring: *"Falls back to PostgreSQL for historical data"* | |

**Verdict: PostgreSQL durability is intended** — by the model, the store's
public docstring and code, the readers' fallbacks, the listing's fallback and
the audit. The **only** contrary text is the tracked
`legacy_persistence_inventory.py:110-121`: `REPLACE` — *"Replay in the
governed fabric reconstructs facts from the execution record and the outbox …
neither of which this table feeds. Superseded in substance already."* That is
a direction, not a shipped replacement: no governed component serves
`/api/mission-replay` or `/api/enterprise-replay`, the frontend pages consume
this store, and the governed packages do not publish to the V1 bus at all
(`grep` `backend/auth`, `contexts`, `platform`, `assurance`, `world`,
`intelligence`: 0 importers of `backend.events.event_bus`). The brief's
recommendation is therefore confirmed from the repository, not adopted from
the brief: **MISSION REPLAY POSTGRESQL = DURABLE.**

## E. Database evidence `[VERIFIED]`

- Fresh `alembic upgrade head` (`cortex_p1025_fresh`): 24 migrations, 56
  tables, `mission_replay_events` **absent**; no migration creates or
  references it; 0 FKs point at it; no indexes/constraints exist because no
  table exists.
- Existing head DB `cortex_p1014_legacy` (`0024`): absent.
- Every database on the instance: none has the table — **no existing replay
  data, so no ownership ambiguity** (stop condition 5 does not fire).
- Registry census: `import backend.database.models` + bounded contexts → 31
  tables, none unmigrated; the model joins metadata only via the store's lazy
  imports.

## F. Durability test (Stage A, on a `create_all`'d copy) `[VERIFIED]`

The brief's seven steps were run on the migration-built DB after
`create_all` for this one table (Stage B repeats them on the migrated table):
(1) three real events via `event_bus.publish`/`publish_event`; (2) three rows
by independent SQL, payload `{'k':'v3','nested':{'a':[1,2]}}` intact,
`latency_ms 12.5`; (3) Redis list length 3; (4) `DEL` of the events/seq/meta
keys → list length 0, seq `None`; (5) SQL rows byte-identical; (6)
`/api/mission-replay/{id}`, `/timeline`, `/graph`, `/api/enterprise-replay/events/{id}`
→ 200 with the three events; (7) ordering `[1,2,3]` by sequence, payload
round-trip `True`; identity = `(execution_id, sequence)` + row `id` —
`event_id` is not part of the durable contract (not a column).

## G. Failure semantics `[VERIFIED]`

The swallow is **design, not accident**: `_db_append`'s docstring, the lazy
imports *"so startup still works if DB is unavailable"*, the in-memory
fallbacks for Redis, and `publish()` scheduling the write as a background task
all say the same thing — the event path must never block on, or fail because
of, persistence. ADR-114 met the identical pattern in `cost_engine` and kept
the semantics while removing the cause and pinning both with a test. What is
**not** compatible with the durable contract is the *visibility*: a lost
durable copy at DEBUG is invisible at every production log level, so a
successful `publish()` falsely implies durability. The brief's own rule
applies — *"a successful event path must NOT falsely imply durable persistence
when the DB write failed"* — and the smallest repair among its list is
**record explicit persistence failure**: the same swallow, logged at WARNING
with execution and sequence. No retry, no transaction, no propagation: the
repository establishes no such policy and the brief forbids inventing one.

## H. Migration ownership `[VERIFIED]`

Alembic is canonical (ADR-109); no migration creates the table; the model is
the only definition and the store writes exactly it — the same situation
ADR-113 resolved for `cp_approval` by deriving the migration from the
metadata definition. Stage B may create the smallest forward migration.

## Stop conditions

| # | Condition | Fired? | Evidence |
|---|---|---|---|
| 1 | durability not intended | no | §D |
| 2 | authority not establishable | no | §D table |
| 3 | retention contradictory | no | layered: 72 h/2000 hot, unbounded cold |
| 4 | model/store disagree materially | no | store writes the model's columns exactly; the `event_ts`/`timestamp` key mismatch is a read-path defect inside the store, repaired by aliasing, not a schema disagreement |
| 5 | existing data with ambiguous ownership | no | no table anywhere |
| 6 | migration touches unrelated schema | no | one table, its own indexes |
| 7 | reliability policy undecided | no | fire-and-forget + swallow is established design; visibility is the repair (§G) |
| 8 | tenant/governance dependency | no | no tenant column, no governed reader/writer |
| 9 | provider/execution behaviour change | no | — |
| 10 | exactly-once needed | no | not claimed; duplicates documented, not fixed |
| 11 | vacuous test | no | real bus, real Redis, independent SQL, real routes, canaries (Stage B) |
| 12 | destructive operation | no | `downgrade` drops an empty/new table only when explicitly run |

## Evidence files

Scratchpad: `p1025_upgrade.log`, `p1025_probe.py` / `p1025_probe.out`,
`p1025_ddl.py` (compiled DDL). Databases and Redis keys disposable, removed in
Stage B's clean-up.
