# ADR-050 — Distributed Scheduler Crash Recovery and Coordination Hardening

**Status:** Accepted
**Date:** 2026-08-09
**Phase:** 5.7
**Relates to:** ADR-045 (coordination), ADR-049 (the loop)
**Does not complete:** Phase 5.5, which remains blocked on `credential_unavailable`.

---

## Why this phase exists

ADR-049 proved the durable execution loop as one governed lifecycle, and said
plainly what it had **not** proved:

* scheduler-controlled crash recovery;
* true multi-process scheduler competition — 5.6's two-scheduler test ran in one
  process.

Phase 5.4 had verified the underlying primitives (four-way election, lease
recovery, outbox reclaim) across real OS processes, but never with the scheduler
lifecycle on top. Phase 5.7 closes exactly those two gaps and nothing else.

## What was verified, and how

Every concurrency test runs in **genuinely separate OS processes** — spawn, own
interpreter, own connection pool, own scheduler instance — against real
PostgreSQL 16.14 at Alembic `0012`. Threads are not used as a substitute
anywhere. A file barrier makes the contended operations actually overlap.

### Multi-process election

Four processes stood for the scheduler role simultaneously. **Exactly one won**,
its identity is durable in `cp_leadership`, and the four were distinct instances
rather than one instance re-acquiring.

### Competition does not dispatch twice

Three full scheduler processes raced one execution. **Exactly one dispatched.**
Every loser made **zero provider calls and minted zero credentials**, and was
refused for the stated reason (`not_leader`) rather than by accident. One
execution record, one attempt.

The claim is narrow and stays narrow: *scheduler competition does not itself
create duplicate execution.* Exactly-once is not claimed anywhere.

### Fencing, and the stale leader

Leader A acquired token *N*; after a legitimate lapse, B acquired *N+1*. A then
attempted a leadership-controlled durable write carrying its stale token.

**The write matched no row** (`rowcount == 0`) and durable state was unchanged.
The current leader's identical write matched exactly one row.

This is the load-bearing property: `fenced_where` composes the token check into
the caller's own `UPDATE`, so no Python check runs and therefore no Python check
can be stale. `assert_current` exists and is used, but it is labelled advisory in
the source and is not the authority.

### Scheduler crashes — real kills

`os._exit(9)`: no finalisers, no rollback, no cleanup.

| Scenario | Durable outcome |
|---|---|
| dies before acquiring | holds nothing; role remains free |
| dies holding the role | claim survives; **a successor cannot take a live lease** |
| — after the lease lapses | successor acquires, with a newer token |
| dies after dispatch/claim | execution record survives; state is a real state, never fabricated |
| dies holding a node lease | lease survives, still naming the dead process |

### Lease recovery

Recovery reads durable lease state and **acts on nothing**. Verified structurally
that `DurableLeaseRecovery` never calls `scoped_credential`, `adapter.run`,
`broker.dial`, `gateway.invoke` or `resolve(`, and that an **ambiguous lease is
never automatically reclaimed**. No recovery policy was added or duplicated.

### Regressions inside this phase

Replay remained observationally inert (all counters zero). Outbox event ids
stayed stable across publication with no dead-lettering. The five identities —
queue claim, leadership, execution lease, WorkerDirectory, WorkerPool — remain
unmerged, verified from their own documentation.

## Two defects found

Both were in the Phase 5.7 harness, and both were exposed by the platform rather
than hidden by it.

**1. A default argument pinned the database.** `dsn(database: str = DB)` binds
`DB` when the module is imported, so reassigning `loop56.DB` in a child process
had no effect and every child silently talked to the Phase 5.6 database. The
symptom looked like leadership and durability failures; the cause was a default
argument. Now resolved at call time.

**2. `WorkerPool` capacity does not travel between processes.** A scheduler in
another process starts with an empty pool and fails at claim time with
`UnknownWorker` until it registers its own dispatcher capacity. This is the
documented semantics — *"how much can this process take right now"* — working
correctly, and the fix belongs in the caller, not the pool.

## Guarantees

**Guaranteed.** Exactly one leader per role at a time, durable. Fencing tokens
monotonic across handover. A stale leader cannot mutate leadership state. A dead
leader's lease is respected until it lapses. Queue claims and execution leases
remain exclusive across processes. Scheduler competition creates no duplicate
execution. Replay is inert. At-least-once outbox delivery with stable event ids.

**Not guaranteed, and deliberately not claimed.** Exactly-once execution.
Exactly-once provider delivery. That a provider side effect performed before a
crash did not happen — that remains `UNKNOWN` and is reconciled by durable
identity, never guessed.

## Non-goals

No rate limiter, tenant fairness, approver entitlement, MCP SSE, sandboxed
stdio, new retry or compensation policy, new isolation tier, new credential
provider or transport. No second scheduler, leadership mechanism, queue or
recovery system. No GitHub contact and no inspection or modification of
`GITHUB_TOKEN`.

## Relationship to ADR-045 and ADR-049

ADR-045 built fenced leadership and proved it at the primitive level. ADR-049
put the scheduler in the loop in a single process. This ADR joins the two: the
scheduler lifecycle under real multi-process competition and real crashes.

## What remains unverified

* **Real provider execution** — Phase 5.5, `credential_unavailable`.
* **Audit sink** — still unwired (`gateway._audit is None`). **DEFERRED**, not
  implemented here.
* **Long-running leadership churn** — repeated handovers under sustained load
  were not exercised; each scenario was a discrete event.
* **Scheduler background thread** — `tick()` was driven directly, as the
  scheduler's own docstring intends for tests. `start()`/`stop()` lifecycle under
  crash was not exercised.
