# ADR-118 — Mission replay's PostgreSQL layer is durable, owned by migration 0025, and a lost write is loud

- **Status:** ACCEPTED
- **Date:** 2026-09-09
- **Phase:** 10.25 (discovery) + 10.26 (implementation)
- **Parent:** `3adf9bc` — Phase 10.23 (ADR-117, decision 3)
- **Evidence:** `docs/PHASE_10_25_DISCOVERY.md`,
  `docs/PHASE_10_26_IMPLEMENTATION_MAP.md`,
  `docs/PHASE_10_26_VERIFICATION_REPORT.md`
- **Change:** `versions/0025_mission_replay_events.py` (new);
  `models/__init__.py` registers `MissionReplayEvent`;
  `services/mission_replay_store.py` (`_db_append` failure at WARNING,
  `_pg_fetch` serves `timestamp`); `api/mission_replay_routes.py`
  (`list_replays` consults PostgreSQL on an empty window);
  `tests/database/test_mission_replay_persistence.py` (new).

> **Numbering.** Highest used is 117; this is 118. Nothing overwritten.

## Problem

`event_bus.publish()` writes every V1 mission event to the replay store, whose
docstring promises a Redis hot window (72 h) backed by a "cold / permanent"
PostgreSQL layer. No migration ever created that layer's table; the model was
imported only inside the store's functions, so neither Alembic nor a dev
boot's `create_all` saw it; and the failing insert was swallowed at DEBUG. On
every production-shaped database every mission's durable replay copy has been
silently discarded since the GA commit, and replay returned 404 once the
Redis window expired. The tracked persistence inventory classifies the file
`REPLACE`; ADR-117 stopped rather than choose between "make it durable" and
"remove the layer".

## Evidence

**Durability is intended.** The model calls itself a persistent log with an
emitted-time column distinct from write time; the store documents PostgreSQL
as the permanent layer and reads it as the fallback beyond the window; the
listing route documents a PostgreSQL fallback for history; the GA readiness
audit records "dual-layer replay"; eight `/api/enterprise-replay` endpoints,
`/api/mission-replay`, the governance centre's stage timeline and the context
intelligence service all read it, and the frontend replay pages consume those
routes. The inventory's `REPLACE` names a governed replay that does not serve
any of this — the governed packages do not even publish to the V1 bus. It is
a direction, not a replacement; it does not make the shipped product's replay
disposable.

**Redis is the window; PostgreSQL is the history.** Written in that order on
every event, both unconditionally. Redis: TTL 72 h, LTRIM 2000, and the
sequence counter. PostgreSQL: unbounded, nothing prunes it, the only place a
replay exists after 72 h.

**The swallow is design.** "Silently no-ops if DB is down", lazy imports so
startup survives an absent database, in-memory fallbacks for Redis, and a
background-task write from `publish()`. ADR-114 kept the same semantics in
`cost_engine`. What violates the durable contract is only that the loss was
invisible.

**Executed, not inferred.** Real events through `event_bus.publish`; rows
read by independent SQL; Redis and PostgreSQL agreeing on each event's
sequence; Redis keys deleted; the real routes serving the replay from
PostgreSQL; the failure path leaving the bus, subscribers and Redis intact.
Two canaries: with the migration removed the tests fail on `UndefinedTable`;
with the store/route repairs stashed they fail on the timeline and the log
level.

## Decision

1. **`mission_replay_events` is owned by migration `0025`**, hand-written from
   the model's compiled DDL with the 0023/0024 existence guard, reversible.
   The `create_all`-only table, the migration-built table, the guard-path
   table and the existing-DB table share one fingerprint.
2. **The model is registered** so Alembic and `create_all` see it without a
   replay write.
3. **The failure semantics stay fire-and-forget and swallowed; the loss
   becomes explicit** — `_db_append` logs the skipped write at WARNING with
   execution and sequence. No retry, no transaction coupling, no propagation:
   the repository establishes none, and the brief forbids inventing one.
4. **A PostgreSQL-served replay keeps its timeline**: `_pg_fetch` serves the
   emitted time under both its column name and the name every reader uses.
5. **The listing consults PostgreSQL when the window is empty**, as its
   docstring always claimed and as it already did when Redis was down.

## Rejected

- **Remove the PostgreSQL layer** (ADR-117's other branch). It would make the
  72-hour loss permanent by design for a product whose replay pages are
  shipped, on the authority of an inventory note about a replacement that
  does not exist yet.
- **Propagate or retry the failed write.** New reliability semantics without
  repository evidence; would also make the bus block on persistence, which
  every part of the store's design refuses.
- **Add `event_id` (and phase, confidence, token usage) columns** so the two
  layers serve identical shapes. A schema change beyond the model's contract;
  no reader keys on them.
- **A unique constraint on `(execution_id, sequence)`.** Invented semantics;
  the counter's documented restart case would turn into write failures.
- **Autogenerate the migration.** Its output is contaminated by the 86
  open index operations; the model's DDL is the authority.

## Schema ownership

Alembic (ADR-109). The model was the only definition and is now mirrored by
`0025`; drift on this table is detectable from here on (`alembic check` no
longer mentions it; the other 86 operations are unchanged and unclaimed).

## Consequences

Every mission event now has a durable copy on every migrated database;
replay survives the Redis window; the listing shows history; a lost copy is
a WARNING naming the execution. Existing databases gain one empty table and
nothing else changes (fingerprints identical). Gates: architecture **155**; regression **75 failed / 6782 passed / 24 errors** with zero new failures against the 10.22 baseline; harnesses 10.7–10.14 at full counts (10.11 re-run alone after a contention-induced portal death: 68/68); readiness `ready: true` on fresh and existing databases. Provider writes: 0 from this phase (the 10.7 harness's one standing rollout restart, as in every prior run).

## Stop conditions

None of the twelve fired; the table in the discovery document records each.

## Known limitations

`event_id`/`phase`/`confidence_score`/`token_usage`/`original_type` are not
durable (not columns). `sequence` can repeat after the Redis counter expires
and can be assigned out of publish order under a burst; the Redis-served
order is append-completion order. A persistently failing database still
loses copies — loudly now, one WARNING per event.

## Follow-up

- Rewrite `legacy_persistence_inventory.py:110-121` (`REPLACE`) to this
  decision when the inventory is next revised.
- ADR-117 decisions 1 and 2 (directory, enterprise operations) remain open.
- The 86 index operations (ADR-116) remain open.
