# ADR-117 — Eight tracked models with live code and no migration: three decisions the repository cannot make for itself

- **Status:** PROPOSED — **STOPPED before implementation.** Discovery only.
  No migration, no code change, no schema change, no test changed.
- **Date:** 2026-09-08
- **Phase:** 10.23 (discovery) + 10.24 (implementation — **not entered**)
- **Parent:** `65d465c` — Phase 10.22 (ADR-116)
- **Evidence:** `docs/PHASE_10_23_DISCOVERY.md`,
  `docs/PHASE_10_23_VERIFICATION_REPORT.md`,
  `docs/PHASE_10_23_24_IMPLEMENTATION_MAP.md`

> **Numbering.** Highest used is 116; this is 117. Nothing overwritten.

## Problem

Phase 10.22 found seven tracked ORM models that no migration creates and the
registry does not import — invisible to autogenerate, present only in
databases that a development boot `create_all`'d. This phase was asked to
discover each one by execution, classify it, and implement only what discovery
proved safe, stopping at any architectural decision the brief did not
authorise.

## Evidence (all executed; detail in the discovery document)

**There are eight, not seven.** `mission_replay_events` is in the same state
and was missed because its only imports are inside functions — it reaches
`Base.metadata` only after the first replay write.

**None exists anywhere.** Not in a fresh `alembic upgrade head` database (24
migrations, 56 tables), not in the existing head database, not in any database
on the instance. No migration in the lineage has ever named any of them. There
is no durable data to protect or migrate.

**The V1 organisational directory** (`organizations`, `departments`,
`projects`) has three route modules, three repositories and full CRUD — mounted
at `/api/api/organizations` (etc.) since the day they were wired, because both
the router and the registry add `/api`. The one correctly-mounted endpoint,
`/api/organization/departments`, raises `UndefinedTableError` on every
migration-built database. The frontend's organizations page is mock data; its
wiring report lists departments and projects as "no backend endpoint yet".
With the tables present the code works and persists (`POST` → 201, one row).
The tracked persistence inventory says `KEEP` because *"IAM … identity depends
on them"* and *"these tables largely define tenancy"* — IAM was retired in
10.14, and ADR-103 rejected these tables as tenancy: *"a directory feature,
not an authorization boundary."* The reason the repository keeps them no
longer exists, and no document says what the directory is for.

**The enterprise-operations endpoints** (backup, health-center, maintenance,
operational-reports) are mounted the same doubled way, have no frontend
caller, and fail identically on a migration-built database — even flipping
the in-memory maintenance switch fails, because it logs an event row first.
With the tables present, three of the four write paths fail on their own
never-exercised bugs (naive/aware datetime in backup and report creation; a
non-dict response from the health snapshot); only maintenance persists.

**Mission replay is live in production and silently losing every event.**
`event_bus.publish()` schedules `replay_store.record()` for every V1 event;
the store appends to Redis (72 h TTL) and then inserts one
`mission_replay_events` row inside a `try/except` that logs at **DEBUG**. On
every migration-built database the insert fails with `UndefinedTableError`,
the failure is invisible at any production log level, and replay works for 72
hours and then returns nothing. Five route modules read it. The model, the
store's docstring and its code all say *permanent*. The tracked inventory
classifies the same file **`REPLACE`** — *"superseded in substance already"*
by the governed execution record and outbox, *"neither of which this table
feeds."*

**Governance is not involved.** No governed package imports these models or
publishes to the V1 event bus; ADR-103, `0021`/`0022` and `tenancy_rules.py`
already separate organizations from tenancy; the replay store carries V1
events only.

## Classifications

| Model | Classification |
|---|---|
| `organizations`, `departments`, `projects` | `STOP_ARCHITECTURAL_DECISION` |
| `backup_records`, `health_status_snapshots`, `maintenance_events`, `operational_reports` | `STOP_ARCHITECTURAL_DECISION` |
| `mission_replay_events` | `STOP_ARCHITECTURAL_DECISION` |

## Decisions required (smallest form)

1. **Does the V1 organisational directory ship in GA?** Yes → one migration
   for three tables, fix the doubled prefix, un-mock the panel. No → retire
   routes, repositories, models, the inventory entry and four ratchet names.
2. **Do the enterprise-operations endpoints ship in GA?** Yes → one migration
   for four tables plus the three code bugs and the prefix. No → retire. A
   split is legitimate; maintenance is the only one that works today.
3. **Mission replay's PostgreSQL layer: durable, or removed?** Durable → one
   migration from the model (no FKs, no data; mechanically ready) and raise
   the swallowed-write log level. Removed → delete `_db_append`/`_pg_fetch`
   and the model, making the 72 h Redis-only behaviour explicit until the
   governed replay the inventory promises exists.

## Rejected alternatives

- **`ADD_MIGRATION` for all eight as the "safe default."** A migration is a
  statement that the table is part of the product's schema. For the directory
  and operations tables that statement is not in the repository — the only
  document asserting it rests on retired reasons, and no client reaches the
  code. For replay it contradicts the inventory's `REPLACE`. Creating schema
  to make code stop failing is the thing ADR-109/116 forbid.
- **`RETIRE_MODEL` for all eight.** There is no registration to remove; the
  models are reached by their consumers directly. Retirement means deleting
  routes, repositories, services and models — live runtime code — and the
  brief forbids that without a `RETIRE_*` authorisation this ADR cannot grant
  itself.
- **`DEFERRED`.** Each of the eight carries a production defect (a 500 on
  every call, or silent data loss on every event). Deferring would leave the
  defects unowned; stopping names the owner.
- **Implementing replay alone** (the one mechanically ready migration) while
  stopping the other seven. Rejected on the brief's gate — *"ONLY enter Stage
  B if Stage A produces no architectural stop"* — and because the inventory's
  `REPLACE` makes even that a decision, not a repair.
- **Fixing the doubled prefix now.** It is not schema work, and it presupposes
  decision 1 or 2 is "yes".

## Schema ownership

Alembic is the canonical owner (ADR-109). For these eight the lineage owns
nothing and the models are the only definition. That does not make the models
authoritative: an unmigrated model is a *claim*, and for three of the eight
the repository's own inventory disputes the claim. Ownership is therefore
**undecided** per group until the questions above are answered — which is
precisely stop condition 9.

## Stop conditions that fired

1 (replay: live consumer, contested contract) · 5 (directory, operations:
intended persistence not establishable from repository evidence) · 9 (all:
boundary ownership) · 11 (any forced classification invents product scope).
2, 3, 4, 6, 7, 8, 10, 12 did not fire — evidence in the discovery document.

## Verification

Every claim was driven through the real route modules (mounted as the
registry mounts them), the real session/engine on a database built only by
`alembic upgrade head`, real tokens, and the real replay store against the
real Redis; then repeated after `create_all` for the eight tables only. See
the verification report for the verbatim results. Provider writes: 0. The
disposable database and Redis keys were removed. No tracked code changed, so
the gates were not re-run; Phase 10.22's results for this identical tree
stand.

## Known limitations

- The production consequence is executed on a production-*shaped* database
  (migration-built), not on a deployed instance; no deployed instance exists.
- Governed harnesses were not re-run: nothing changed. A re-run would verify
  nothing about this phase.
- The replay store's Redis layer means replay *appears* to work for 72 hours;
  the loss is only visible afterwards or by reading the DEBUG log.

## Follow-up work

- The three decisions above, each followed by one bounded phase (implementation
  map §"What each decision would authorise").
- Independent of any decision: the registry's doubled `/api` prefix on seven
  route modules, and the `log.info("… registered at /api/…")` lines that
  misreport it.
- The legacy persistence inventory's entries L110, L140, L176, L226 restate
  reasons the repository has retired; whichever way the decisions go, they
  need rewriting to the decided state.
- Still open from ADR-116: the index convention (86 operations) and the two
  stale ratchet entries.
