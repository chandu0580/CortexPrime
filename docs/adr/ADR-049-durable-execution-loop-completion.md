# ADR-049 — Durable Execution Loop Completion

**Status:** Accepted
**Date:** 2026-08-09
**Phase:** 5.6
**Relates to:** ADR-047 (which named "the full chain in one run")
**Does not supersede:** anything. **Does not complete:** Phase 5.5.

---

## Why this ADR exists while Phase 5.5 is still blocked

Phase 5.5 is blocked on `credential_unavailable`: no GitHub credential this
environment holds will authenticate. That blocker is untouched here and remains
open. **ADR-048 is deliberately not written** — it belongs to Phase 5.5 and
writing it now would imply a completion that has not happened.

What Phase 5.5's discovery found was that three components had passing unit
tests and had **never run in the loop**:

* `ExecutionScheduler` — nothing drove dispatch; `dispatcher.cycle()` was called
  by hand;
* `OutboxPublisher` — events were recorded and never published;
* the checkpoint write path and replay against a *completed* run.

None of those depend on a GitHub credential. Waiting for one would have left
verifiable machinery unverified for no reason.

## Decision

### The loop is driven by the scheduler, and by nothing else

`ExecutionScheduler.tick()` performs readiness, acquires fenced leadership, and
then drives the **existing** dispatcher. No `dispatcher.cycle()` call appears in
the Definition-of-Done execution. One scheduler, one dispatcher, one gateway,
one queue, one repository, one publisher, one leadership store.

The scheduler coordinates and does not authorize — verified structurally: its
source contains no `authorize(`, `scoped_credential`, `adapter.run`,
`broker.dial` or `resolve(`.

### Leadership is a narrow port, and the adapter already existed

`LeadershipPort` is three no-argument methods, so Execution never learns what a
fencing token or a role is. `SchedulerLeadership` (Phase 5.1) binds the role and
lease length at the composition root.

Passing the raw `SqlLeadershipStore` instead makes **every tick answer
`not_leader`** — the scheduler failing closed rather than guessing. That is the
correct behaviour and it is what happened on the first run here.

### The controlled provider proves the loop and nothing else

`TestProviderAdapter` keeps `REQUIRES_CREDENTIAL = True`. The credential broker,
the authority window and the gateway's credential gate are exercised exactly as
a real provider would exercise them — an exercise that skipped them would
exercise a shorter chain than production runs.

**It proves nothing about GitHub.** No external host was contacted; the adapter
imports no `httpx`, `requests`, `socket` or `urllib`, and refuses production.

### At-least-once, stated and unchanged

An unknown delivery outcome leaves the entry pending, its claim lapses, and it
is republished **with the same `event_id`**. Verified end to end: a publisher
delivered, returned `UNKNOWN`, was not dead-lettered, and a successor
republished the same ids after the claim lapsed. Exactly-once is not claimed.

## Evidence

One governed execution, scheduler-driven, against PostgreSQL 16.14 at Alembic
`0012` (single head), in throwaway database `cortex_p56`:

```
scheduler_tick        skipped=false dispatched=1
leadership            trace fence=8 held
tenant                phase56-test
execution_id          01KZJZZ95AYWP4C3A15BNN3QHW
governance_operation  invoke
provider_operation    document.fetch
capability            tenant.controlled.document@1   digest b34e8d9c2feaf396
binding_digest        42616e31e5eb5164
lease_holder          dispatcher:01KZJZZ95AYWP4C3A15BNN3QHW
worker                controlled-connector
payload               {"collection": "reports", "document_id": "annual-2026"}
node_state            succeeded
credential_acquisitions  1
provider_calls           1
outbox_events            6      published: claimed 16, delivered 16
secret_present_anywhere  false
```

**94 focused checks passed, 0 failed.**

Replay reconstructs the completed run with every counter at zero — credential,
provider, transport, publication — and does not mutate durable state. Proven by
call counters, not by reading the source.

## Two defects this phase found

**1. A shared instance id makes two schedulers look like one.** Both loops used
`instance_id="phase56"`, so the second scheduler's acquisition was read as the
same instance re-acquiring its own role — legitimately — and it dispatched. The
identity is now per-instance by default, and sharing must be opted into. Phase
5.2 had already written down why ("a shared identity would let one release the
other's claim"); this is the same hazard in a second costume.

**2. Path parameters must be `RESOURCE_SEGMENT`.** A `STRING` in a path slot is
refused, because only that kind is checked for the characters that let a value
escape the path an operation declared. The domain caught it at construction.

Neither required a code change to the platform; both were harness errors that
the platform's own guards exposed.

## Explicit non-goals

No rate limiter, no tenant fairness, no approver entitlement model, no MCP SSE,
no sandboxed stdio, no new credential provider, no new isolation tier, no new
retry or compensation policy, no exactly-once, no second scheduler, queue,
gateway or authorization path. The absence of a rate limiter remains *"a quota
nobody wrote is not a rule"* and was not quietly turned into a policy.

## What remains unverified

* **Real provider execution** — Phase 5.5, still `credential_unavailable`.
* **Crash recovery under the scheduler.** Phase 5.4 verified dispatcher, lease
  and outbox crash recovery with real process kills; this phase did not repeat
  them *under scheduler control*.
* **Multi-process schedulers.** The two-scheduler test ran two distinct
  claimants in one process. Phase 5.4 proved four-way election across real OS
  processes; that was not repeated here.
* **Audit sink** remains unwired (`gateway._audit is None`).

## Relationship to ADR-047

ADR-047 named three Phase 5.5 items. This phase completes the *loop* half of
item 2 — the chain as one governed execution — using a controlled provider.
Item 1 (real provider) and the real-provider half of item 2 remain open, as does
item 3 (queue-contention tick).
