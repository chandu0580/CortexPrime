# Phase 10.25 + 10.26 — Verification Report: mission replay durable persistence

- **Parent:** `3adf9bc` — Phase 10.23 (ADR-117)
- **Discovery:** `docs/PHASE_10_25_DISCOVERY.md` · **Map:** `docs/PHASE_10_26_IMPLEMENTATION_MAP.md` · **ADR:** ADR-118
- **Date:** 2026-09-09

Labels: `[VERIFIED]` executed and observed · `[NOT VERIFIED]` inferred ·
`[DEFERRED]` environment prevented it · `[STOP]`.

## 1. Summary

| Claim | Result |
|---|---|
| Fresh DB: `alembic upgrade head` builds the table | `[VERIFIED]` 25 migrations, 57 tables, `\d` matches the model (§2) |
| Guard: a DB that already has the table from `create_all` upgrades cleanly | `[VERIFIED]` 1 migration, table and every other table's fingerprint unchanged, 0 errors |
| Existing head DB: only 0025 runs; rows and other tables untouched | `[VERIFIED]` `cortex_p1014_legacy`: other-table fingerprint `1762a12b…` and row-count fingerprint `b7d7af57…` identical before/after; 56 → 57 tables |
| Migration == model | `[VERIFIED]` one fingerprint `e1df0fde9218fa9a68a5c8aeeef69f3e` for the `create_all`-only table, the fresh migration-built table, the guard-path table and the existing-DB table |
| Reversible; one head | `[VERIFIED]` downgrade → `0024`, table gone, 56 tables; re-upgrade → identical fingerprint; `heads` = `0025_mission_replay_events` only |
| Alembic before / after | `[VERIFIED]` before (DB at 0024, model registered): **92** = 86 + `add_table mission_replay_events` + 5 `add_index`; after (fresh head): **86**, byte-identical to the 10.22 inventory, 0 replay mentions; `alembic check` still red on exactly the 86 (21 remove_index / 62 add_index / 2 add_constraint / 1 remove_constraint) — **global cleanliness not claimed** |
| `create_all` census | `[VERIFIED]` registry metadata 31 tables, 0 unmigrated; with the eight route modules imported: exactly the seven unresolved tables remain unmigrated (unchanged); `mission_replay_events` in both sets |
| Real replay write → PostgreSQL | `[VERIFIED]` §3 |
| Real replay read from PostgreSQL after Redis removal | `[VERIFIED]` §3 |
| Failure path explicit and non-fatal | `[VERIFIED]` §3 |
| Tests non-vacuous | `[VERIFIED]` two canaries, §4 |
| Architecture / regression / harnesses | `[VERIFIED]` architecture **155 passed**; regression **75 failed / 6782 passed / 36 skipped / 58 xfailed / 24 errors** — zero new failures against the 10.22 baseline (76 / 6778): the three new tests pass and the baseline's one non-reproducible failure (`test_invoke_reaches_the_provider_exactly_once…`) passed this time; harnesses 10.7 **155/155** · 10.8 **118/118** · 10.9 **107/107** · 10.10 **107/107** · 10.11 **68/68** (solo re-run; §5) · 10.13 **60/60** · 10.14 **53/53** — all VERIFIED; 10.19 readiness `ready: true` on the fresh and the existing DB; 10.20 write-path + 10.26 replay tests 7 passed |
| Frontend | not run — no frontend file changed; no frontend test exercises replay (`git ls-files frontend | grep -i replay | grep -i test` → none) |
| Governance | `[VERIFIED]` by re-execution of the governed harnesses above — scoped authority (10.7), grant issuance (10.8), membership (10.9), tenant records (10.10), legacy retirement (10.11), V1-read retirement (10.13), IAM retirement (10.14) — all at full counts; no governed package imports the replay model or publishes to the V1 bus (grep), and no governed table changed (fingerprints) |
| Provider writes | **0** — no Kubernetes/GitHub/cloud call by this phase's code or probes; harness-reported writes [0,1] on 10.7 only — the one commissioned rollout restart that harness has always performed (identical to 10.20/10.22 runs); 0 on every other harness; the `provider_writes: 1` in the contended 10.11 chain run was that harness's own convention of scoring an unexpected HTTP status as a write, not a cluster measurement — its solo run records 0 on all 20 cases |
| Clean-up | `[VERIFIED]` §6 |

## 2. Schema — fresh migration-built table (`\d mission_replay_events`)

```
 id           | uuid                     | not null | gen_random_uuid()
 execution_id | character varying(255)   | not null |
 sequence     | integer                  | not null |
 event_type   | character varying(64)    | not null |
 agent        | character varying(128)   | not null |
 status       | character varying(32)    | not null |
 message      | text                     | not null |
 event_ts     | character varying(64)    |          |
 latency_ms   | double precision         |          |
 payload      | jsonb                    |          |
 created_at   | timestamp with time zone | not null | now()
 updated_at   | timestamp with time zone | not null | now()
Indexes: mission_replay_events_pkey (id); idx_replay_exec_agent (execution_id, agent);
         idx_replay_exec_seq (execution_id, sequence); idx_replay_exec_type (execution_id, event_type);
         ix_mission_replay_events_agent (agent); ix_mission_replay_events_execution_id (execution_id)
```

No FK, no unique constraint — exactly the model.

## 3. Real path — `tests/database/test_mission_replay_persistence.py` (3 passed, 32 s) and `p1025_probe.py` on the migrated DB

`test_real_event_persists_and_survives_redis_loss` — real `event_bus.publish`
and `publish_event`, real store, real Redis (isolated DB index 15), the real
`AsyncSessionLocal` on an Alembic-built database:

1. three real events → **three rows by independent psycopg2 SQL**, sequences
   `[1,2,3]`, types `{mission_started, tool_called, mission_completed}`,
   `payload` and `latency_ms` round-trip, `event_ts` == each event's
   `timestamp`;
2. Redis list of 3, **same sequence per event as PostgreSQL**, carrying the
   published `event_id`s;
3. `DEL` events/seq/meta keys → list length 0;
4. PostgreSQL rows identical to before;
5. `replay_store.get_events` → ordered by sequence, payloads equal,
   `timestamp == event_ts` on every event; `get_summary` found/3/first_ts/
   duration/complete; `get_timeline` offsets `0.0, …`, none `None`;
6. `/api/mission-replay/{id}` 200 with sequences `[1,2,3]`, payloads,
   timestamps, `summary.duration_ms`; `/graph` 200 `total_steps 3`;
   `/api/enterprise-replay/events/{id}` 200 with 3; `/api/mission-replay/`
   lists the execution **from PostgreSQL** (empty Redis window).

`test_db_write_failure_is_explicit_and_leaves_the_event_path_intact` — the
session factory bound to a database with no table: `publish()` returns, no
background task raised, the subscriber received the event, Redis holds it,
and the log carries `replay_store DB write skipped for execution <id> seq 1:
…` at **WARNING**.

`test_migration_table_matches_the_model` — reflected columns, nullability,
server defaults (`gen_random_uuid`, `now()`; none on `sequence`/`status`),
indexes and PK equal the ORM table; no FKs.

Probe on the migration-built head DB (`cortex_p1025_fresh @ 0025`): Phase 1
(no `create_all`) — three events, no skip lines, Redis 3; after Redis
deletion every route returns the three events from PostgreSQL with
timestamps/offsets/duration present and the listing containing the
execution; `event_id` `None` (not a column — documented limitation).

## 4. Non-vacuity — canaries

| Canary | Result |
|---|---|
| migration file removed (head = 0024), tests re-run | **2 failed, 1 passed** — `UndefinedTable: relation "mission_replay_events"`; the passing one is the failure-path test, correct: without the table the swallow-with-WARNING is exactly what it asserts |
| store + route repairs stashed (migration present) | **2 failed, 1 passed** — the durability test fails on `timestamp`/listing, the failure-path test on the WARNING level; the schema-equality test passes, correct: the migration is unchanged |
| all three restored | 3 passed |

## 5. Gates

| Gate | Result |
|---|---|
| Architecture (`tests/architecture`) | **155 passed** (457 s) |
| Regression, first full run | 77 failed / 6780 passed — the two *new* replay tests failed **in-suite only**: the Redis wrapper singleton captures its URL at construction (`connection.py:95`), which in a full run happens in an earlier module with no `REDIS_URL`, and `event_bus._background_tasks` still held pending tasks from other modules' closed loops, which `gather` refused (`ValueError: The future belongs to a different loop`). Both are test-isolation defects in my test, not product defects; fixed by pointing the singleton at the isolated test index for the scenario (restored on close) and awaiting only the current loop's bus tasks. Reproduced deterministically with `tests/benchmarks/test_resilience.py tests/benchmarks/test_mission_performance.py` before the module (16 failed / 5 passed → 14 / 7 after the fix, the 14 being baseline benchmark failures) |
| Regression, re-run after the fix | **75 failed / 6782 passed / 36 skipped / 58 xfailed / 24 errors** (2162 s); `FAILED` list vs 10.22: **0 new**, 1 no longer failing (the known non-reproducible one) |
| Harness chain (serial) | 10.7 155/155 · 10.8 118/118 · 10.9 107/107 · 10.10 107/107 · **10.11 66/68 rc=1** · 10.13 60/60 · 10.14 53/53 |
| 10.11 isolated | The two failures were N1/N2 "product read → HTTP 500 (expected 200)" with the harness tail `RuntimeError: This portal is not running` — the recurring TestClient anyio-portal death under contention, and the contention was mine: my reproduction pytest runs overlapped the chain. **Re-run alone: 68/68 VERIFIED, rc=0, provider writes 0 on all 20 negative cases.** Classified environmental on that evidence |
| 10.19 readiness | `ready: true`, `missing_tables: []` on `cortex_p1026_fresh` and `cortex_p1014_legacy` |
| 10.20 write-path + 10.26 replay | 7 passed |
| Frontend | not run — nothing under `frontend/` changed and no frontend test exercises replay |

## 6. Clean-up `[VERIFIED]`

Temporary autogenerate revisions: 0 left in `versions/` (moved to the
scratchpad during comparison). Disposable databases `cortex_p1025_fresh`,
`cortex_p1026_fresh`, `cortex_p1026_at24`, `cortex_p1026_createall`,
`cortex_p1026_before` and the tests' `cortex_test_replay_*` dropped; the
phase databases `cortex_p1014_legacy` and `cortex_p10*` kept at head `0025`
for the next phase. Redis: probe keys `cx:replay:*p1025*` and the test index
15 namespace deleted. Ignored files unchanged (`git status --ignored` shows
only the pre-existing `.phase99b.env` token refresh, which is gitignored and
never staged).

## 7. Known limitations

- `event_id`, `phase`, `confidence_score`, `token_usage`, `original_type` are
  not columns of the model and are therefore not durable; a PostgreSQL-served
  replay returns them `None`. Adding columns would change the model's contract
  and was out of scope.
- `sequence` is assigned by a Redis counter with a 72 h TTL and no uniqueness
  constraint; a late event after the counter expires reuses `1`. Pre-existing;
  documented, not fixed.
- Under a burst, background-task scheduling can assign sequences out of
  publish order, and the Redis-served order is append-completion order.
  Pre-existing; the contract is store sequence.
- The swallow remains: a persistently failing database still loses the
  durable copy — now at WARNING per event, with no retry. The repository
  establishes no retry policy and none was invented.
