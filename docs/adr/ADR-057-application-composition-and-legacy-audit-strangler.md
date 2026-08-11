# ADR-057 — Application Composition and Legacy Audit Strangler

**Status:** Accepted
**Date:** 2026-08-10
**Phase:** 5.14
**Relates to:** ADR-056 (the production audit authority this puts in the running app), ADR-055 (fenced storage), ADR-054 (ownership), ADR-050 (leadership), ADR-015/052/053 (audit lineage)
**Does not complete:** Phase 5.5, independently blocked on `credential_unavailable`.

---

## The old startup architecture, as found

`backend/main.py` is a ~1,700-line FastAPI lifespan that registers roughly
forty V1 subsystems, almost every one wrapped in `try/except` +
`log.warning` — a **fail-open** startup in which a subsystem that cannot
start becomes a log line. It contained **zero references** to any 5.x
composition: no `DurablePersistence`, no governed gateway, no fenced audit,
no durable scheduler. The V1 execution/mission runtimes run their own
in-process world.

The legacy approval audit (`enterprise_integrity_audit`) was already an
adapter over the platform `AuditRuntime` (PR-06), but with three defects: it
resolved a **private JSONL chain** as its default sink at import time, it fell
back **silently to an in-memory store** on any store error (an approval trail
that quietly stops surviving restarts), and nothing could rebind it to the
durable authority. Its one production caller is the approval action
dispatcher (five call sites: four refusal records, one verified dispatch).

## The 5.x composition in the real application

`backend/api/application_runtime.py` — the missing composition, and nothing
else. It assembles only existing parts: `build_durable_persistence` (which
owns the fenced audit authority, ADR-056), `build_production_connectivity`
(audit required), `build_execution_lifecycle`, `ExecutionScheduler` +
`SchedulerLeadership`, `OutboxPublisher` under the existing
`OUTBOX_PUBLISHER` role, and an `EventBusSink` that delivers outbox entries
onto the application's existing EventBus (unacknowledged deliveries are
UNKNOWN, never DELIVERED-on-hope). Providers beyond GitHub arrive through
the `connectors` seam via `CORTEX_CONNECTOR_FACTORIES` — explicit
configuration, fatal if unloadable.

**Enablement is explicit; failure is fail-closed.** The governed runtime
exists iff `CORTEX_DURABLE_URL` is set. Unset: the runtime is *absent* — not
degraded, absent — and V1 behaves exactly as before. Set: every failure
aborts startup. The lifespan wiring in `main.py` is deliberately **not**
wrapped in the fail-open pattern that surrounds it, and says so in a comment
that names the reason.

### Startup order (the components' own contracts)

configuration → `build_durable_persistence` (verifies reachability,
transactions, Alembic schema; refuses otherwise; owns the audit) → services →
governed connectivity (audit required) → dispatcher + recovery → scheduler
(its own `start()` runs recovery before dispatching, ADR-050) → outbox pump →
legacy facade rebind → application serves.

### Shutdown order

`scheduler.stop()` first (drains the active cycle, leaves live leases to
recovery, releases its role **last**) → outbox pump stopped and joined, its
role released → audit writer role released → engine disposed. No role is
released while the work it coordinates may still be mid-cycle. Verified: no
live leadership claim survives the process, and the chain verifies after
shutdown.

### Production fail-closed rules, each exercised through the real entrypoint

PostgreSQL unreachable; schema behind head (0012); audit tables missing from
an otherwise-current schema; invalid production configuration (SQLite as a
production store); wrong credentials. All five: the real application refused
to start, created nothing, repaired nothing. No `create_all` for the durable
schema, no JSONL fallback, no in-memory fallback, no unaudited gateway.

## The strangler decision: Option B, completed

The facade **stays** — its typed interface (`record_refusal`,
`record_verified_dispatch`) *is* the approval-dispatch semantics — and its
sink becomes injectable:

* `rebind(runtime)` — the composition root points the facade at
  `persistence.audit`. In a durable-enabled application, approval-dispatch
  observations join **the** fenced PostgreSQL chain. One authority; no dual
  write (the facade holds exactly one runtime reference).
* The default sink is **lazy**: constructing the facade opens nothing, so a
  process that rebinds before first use never touches the legacy JSONL file.
* The silent in-memory fallback is **gone from production**: with
  `ENVIRONMENT=production` and a broken store, recording raises. The
  fallback survives only outside production, explicitly, loudly.
* The boundary is machine-checkable: **BND-LEGACY-AUDIT** (ERROR severity,
  in the default rule set) quarantines the module to exactly two importers —
  the approval dispatcher (records through it) and the rebinding composition
  root (records nothing through it). The rule caught its own author's first
  draft, which is what a fitness rule is for.

### Approval evidence vs. audit observation

Kept distinct, deliberately. The digest-bound pending action and the signed
approval decision are **evidence** and stay in their own stores; what joins
the audit chain is the **observation** — that a verified dispatch happened,
or that a refusal fired (including replay of a consumed approval). Nothing
was force-fitted into `AuditRuntime`, and no approval evidence was discarded
or replaced by an audit record.

## Evidence from the real application

Booted through `backend.main`'s actual lifespan against `cortex_p514`
(blank → Alembic 0013), controlled provider only (`enable_github` off, all
external credentials excluded from the process environment): governed
execution dispatched **by the application's own scheduler thread** through
authorization → binding → lease → gateway → provider (exactly one call) →
durable result → outbox (published onto the EventBus) → fenced audit chain
(verifies). Five refusal classes correctly classified and audited. Replay:
zero provider/credential/audit/outbox/leadership effects. Multi-process:
two whole application processes — exactly one live holder per role, one
dispatch per queue item, follower holds nothing. Crash (`os._exit(9)`)
while holding scheduler + audit writer: claims survive, a successor
application waits out the leases, takes over with the existing recovery
sweep, completes a governed execution, and the chain verifies across every
crash. A follower crash disturbs nothing.

## Defects found by booting the real thing

* `WorkflowNodeModel.workflow_id` / `WorkflowEdgeModel.workflow_id` were
  `String(64)` foreign keys onto a UUID primary key — model/schema drift
  PostgreSQL rejects outright. Invisible until the first real boot against
  an Alembic-built database (the developer DB predates the UUID mixin;
  SQLite doesn't enforce FK type agreement). Fixed to UUID.
* The first `EventBusSink` draft called `EventBus.publish` with a keyword
  contract the bus does not have, then read a `payload` attribute
  `OutboxEntry` does not carry. Every delivery failed, was honestly
  reported UNKNOWN, and every entry stayed pending — the outcome semantics
  worked exactly as designed while the sink itself was wrong, and the
  validation caught it as `0/6 published`. Fixed to construct a real
  `CognitionEvent` from `OutboxEntry.event`; the warning now names its
  cause, because an operator staring at a stuck outbox needs the reason,
  not just the outcome.
* `DeepResearchEngine` constructs a module-level singleton at import that
  **raises without `TAVILY_API_KEY`** — the entire application cannot boot
  without a Tavily credential. Worked around in the harness with a dummy
  value; the singleton-at-import pattern is recorded as a 5.15 strangler
  candidate, not fixed here.
* The V1 startup contacts real providers whose credentials exist in `.env`
  (the GitHub connector initialized and made read-only calls during the
  first two harness boots, before the harness excluded credentials from the
  process environment). This is standing V1 behaviour, now documented: a
  governed deployment must control provider credentials deliberately, not
  inherit whatever `.env` contains.

## Retention

Untouched, as required: PLAN-ONLY (ADR-056). Verified the new composition
neither bypasses nor mutates it — `KeepForever` retires nothing, no
delete/update/truncate surface appeared on the store.

## Guarantees

Everything ADR-056 guarantees, now composed and running in the real
application when durable is enabled: one audit authority; fail-closed
startup; ordered shutdown; governed execution audited end to end; approval
observations on the same chain; replay inert; single-writer /
single-scheduler across processes; crash recovery by existing semantics.

**Not guaranteed.** The V1 subsystems' own fail-open startup behaviour
(unchanged, out of scope); the V1 execution/mission runtimes still run
beside the governed path (the next strangler target, not a second
*authority* — they never touch cp_* state, the governed gateway, or the
audit chain); durability when `CORTEX_DURABLE_URL` is unset (explicitly
absent); exactly-once anything.

## Phase 5.15 boundary

Candidates: strangling the V1 execution/mission runtimes' callers onto the
governed path; import-time singletons that block boot (`DeepResearchEngine`
and kin); credential hygiene for V1 connectors (deliberate configuration
instead of ambient `.env`); an HTTP surface for the governed runtime; and the
standing Phase 5.5 blocker, untouched by this phase.
