# ADR-039 — Production execution lifecycle and recovery

**Status:** Accepted
**Date:** 2026-08-08
**Phase:** 3.3.4 — Production Execution Lifecycle, Dispatch, Recovery & Durability
**Extends:** ADR-038 (gateway), ADR-037 (adapter fabric), ADR-036 (worker contract), ADR-031 (durable execution core)

---

## 1. What this phase is

Phases 3.1–3.3.3 built the authority chain. Nothing yet **drove** it: no component
found ready work, acquired a lease, called the gateway, and decided what happens
when a process dies mid-flight.

This adds that, and adds nothing else. Recovery policy, retry policy,
compensation states and the aggregate's invariants already existed and are pure
(ADR-031); they are orchestrated here, never duplicated. The single largest
decision in the phase was **what not to write**.

## 2. The complete lifecycle

```
Execution → dispatchable_nodes → queue claim → lease → InvocationRequest
→ gateway admission → invoke once → result arrival classification
→ record → retry decision → recovery decision → compensation → completion
→ outbox → replay
```

Each arrow is a component that can refuse. None of them can substitute.

## 3. Dispatcher

`ExecutionDispatcher.cycle` does **one pass and returns**. It holds no authority
of its own: it cannot choose a capability, choose a worker, authorize, bind,
rebind, retry, compensate, or manufacture a tenant or principal. It carries
decisions between the components entitled to make them.

Verified by AST: **no loop of any kind** in the dispatcher, exactly one call to
the gateway, and no call to `rebind`, `reselect`, `resolve`, `renew` or
`compensate`.

`limit` bounds nodes dispatched per cycle so one wide workflow cannot monopolise a
pass; what was left is reported rather than silently dropped.

## 4. Ready-node calculation

`dispatchable_nodes` is pure and totally ordered — by node id, never by `dict`
insertion, `set` iteration, object identity or a wall-clock accident. Two
dispatchers reading one execution see the same list in the same order.

It does not restate the dependency rule; the aggregate's `ready_nodes` already
answers that from the graph. It adds what dispatch additionally needs: run state,
deadline, unresolved nodes, and the compensation distinction.

**Preserved from Phase 2:** sequence edges are dependencies, `on_failure` edges
are not, and **compensation nodes never dispatch on the success path** —
`COMPENSATION_NODE` refuses them in the ordinary sweep. Recovery dispatches them
explicitly or not at all.

`tenant_id` and `deadline_at` are required parameters, not `getattr` reads. The
aggregate has neither: tenancy travels on `ExecutionContext` (ADR-017), and
guessing with `getattr` would produce `None` and silently disable the check.

**A run holding an unresolved node dispatches nothing further.** Starting more
work beside an outcome nobody can state widens the blast radius of a situation
still unexplained.

## 5. Lease and concurrency

Ownership is established **twice**, deliberately:

1. `ExecutionQueue.claim` — atomic under its lock, hands the node to one caller.
   Prevents the wasted work.
2. `NodeRun.leased_to` — refuses a second holder inside the aggregate. Prevents
   the wrong outcome.

Neither alone suffices: the queue is a hint that can be lost, and the aggregate
check happens after work has already been prepared.

Added: `InMemoryExecutionRepository.compare_and_swap(expected_revision=…)` and
`revision_of`. A read-modify-write against a stale revision raises
`ConcurrentExecutionUpdate` rather than overwriting — a lost update here is a lost
*decision*, and the run would afterwards look consistent while being wrong.

Verified: four threads racing one revision produce **exactly one winner**.

The revision is a persistence concern and lives in the repository, not the
aggregate — no schema bump, no domain change.

## 6. Crash recovery

`RecoveryCoordinator` scans unfinished runs, asks `plan_recovery` (ADR-031,
unchanged and pure), records the decision as `ExecutionRecoveryPlanned`, and
returns. **It invokes nothing** — verified by AST: it imports no gateway, no
dispatcher and no worker runtime, and calls nothing that could execute.

Restart-safe by construction: it performs nothing, so running it twice cannot
create two attempts or two compensations. The same record produces the same
decision — verified.

`RESUME_FROM_CHECKPOINT` past an ambiguous node is **structurally
unrepresentable** — `RecoveryDecision.__post_init__` refuses to construct it.

**Recovery priority is stated, not accidental:**
`(urgency, deadline, execution_id)` where urgency is
`AMBIGUOUS_MUTATION(0) < COMPENSATION_OUTSTANDING(1) < EXPIRED_LEASE(2) <
DEADLINE_PASSED(3) < STALLED(4)`. Explicit integers because the ordering *is* the
contract. The execution id is a ULID, so the final tiebreak is creation order —
oldest unattended run first, which is also the fairness property.

## 7. Retry

Unchanged — `decide_retry` (ADR-031) already reads failure class, effect
semantics, idempotency and budget. The dispatcher **plans** a retry and does not
perform one: a component that both decided and performed would be free to
reinterpret its own decision.

**An ambiguous mutation without an idempotency key is not retried.** Verified,
along with its converse: an ambiguous write *with* a key may be. The key is the
only evidence this platform accepts that a repeat is safe.

The budget belongs to the approved workflow. Execution never raises it, and no
worker or adapter can.

*A real bug this caught:* the dispatcher initially passed
`profile_for(spec.side_effect)` instead of `profile_for(spec)`, which would have
classified every keyed write as unkeyed and refused retries that were fine.

## 8. Late and duplicate results

`classify_result_arrival` returns one of five verdicts, and **only `CURRENT` may
be applied**:

| Verdict | Meaning |
| --- | --- |
| `CURRENT` | the live lease holder answering its open attempt |
| `DUPLICATE` | the same attempt answering twice; first valid answer won |
| `SUPERSEDED_ATTEMPT` | an earlier attempt answering after a later one began |
| `LEASE_LOST` | the lease lapsed before the answer arrived |
| `EXECUTION_CLOSED` | the run completed, failed or was cancelled first |

Every non-`CURRENT` answer is recorded as `LateResultDiscarded` and **not
applied**. A dead worker cannot reopen a finished run — verified against the
aggregate, which refuses via `assert_held_by` and a closed attempt.

`EXECUTION_CLOSED` and `LEASE_LOST` are flagged `is_operationally_serious`: an
external effect may have landed after the run was declared over, and that is an
incident rather than noise.

## 9. Attempts and checkpoints

Attempts are append-only and contiguous — the aggregate already enforced both.
Verified: a retry appends attempt 2 while attempt 1 keeps its recorded outcome and
its id.

Checkpoints stay digest-bound to the workflow digest (ADR-031). Nothing here
checkpoints a belief: only recorded facts.

## 10. Compensation

`compensation_order` walks back **newest change first** — reverse completion
order, which is the only order that respects dependencies: undoing A before B
leaves B referring to something that no longer exists. Only mutating successes
are targets. Verified.

Compensation dispatch passes the **same governance chain** as forward work:
authorization, binding, worker selection, gateway, lease, result classification,
audit. There is no privileged compensation path, and compensation is often more
sensitive than the original.

`NodeCompensationConcluded` carries `change_remains`, defaulting to **`True`**.
Assuming a rollback worked is exactly the assumption that leaves a production
change standing while the record says it was undone. The event refuses to
construct with `outcome_known=False, change_remains=False` — not knowing is
precisely not knowing that.

`ExecutionPartiallyRecovered` exists because the state must be expressible:
calling it success hides a live change, calling it failure erases the rollbacks
that worked. It carries the original failure so a partial recovery is not a
record of half an incident. It is emitted only when genuinely true — something
compensated *and* something outstanding.

## 11. UNKNOWN

First-class throughout. A lapsed lease records `UNKNOWN`, not failure; the run
reports the node ambiguous; the run stops dispatching; recovery cannot resume past
it; the retry policy refuses an ambiguous mutation. Nothing anywhere converts
`UNKNOWN` to success or to a harmless failure.

## 12. Scheduler, shutdown, startup

`ExecutionScheduler` has `start` / `stop` / `recover` / `tick`. Four explicit
states: `STOPPED`, `RECOVERING`, `RUNNING`, `DRAINING`; only `RUNNING` accepts
dispatch.

**The loop lives here and nowhere else** — verified: none in the domain, none in
the dispatcher. It waits on a stop event rather than sleeping, so shutdown is
observed immediately.

`start` **always recovers first**. Dispatching before recovering would start new
work beside an outcome nobody had established. Only automatic decisions become
dispatch targets; unresolved outcomes and owed rollbacks wait for a person —
startup does not execute arbitrary work on the strength of having restarted.

`stop` stops *dispatch*. It does not cancel leases, conclude attempts, or mark
running work finished — verified. A process shutting down knows nothing about
what a worker did; the lease lapses on its own and recovery decides. **Shutdown
never produces success.**

`tick` is public and synchronous, so a cron, a queue consumer or a test drives the
same path the thread does. The thread is a mechanism; replacing it changes no
domain code, which is the point of the phase rather than the thread in it.

## 13. Outbox and event ordering

Added to the existing outbox — no second one:

- **`sequence`** — monotonic; ordering is derived from it, never from
  `recorded_at`. Two events in the same microsecond would tie on a timestamp, and
  a tie means two publishers can disagree about which fact came first.
- **`claim(publisher_id, …)`** — exclusive, time-bounded. Two publishers calling
  `pending` both hand the same event over; claiming makes one the owner. Bounded
  so a dead publisher does not strand the entry.
- **`event_id`** — the domain event's identity, lifted where a consumer can reach
  it. Delivery is **at-least-once**, not exactly-once. A consumer that
  deduplicates on this is correct; one that assumes single delivery is not.
- **`dead_lettered()`** — `ABANDONED` entries after 10 failed attempts. Kept,
  never deleted: an event that could not be published is precisely the one
  somebody needs to find.

Causal order is preserved by recording each stage as it happens rather than
batching. Events describe facts that already happened — `CompensationConcluded`
is emitted after the result exists, never to request one.

## 14. Events added — and the ones rejected

Five survived the test "does an existing event already state this?":

`RecoveryPlanned` · `CompensationStarted` · `CompensationConcluded` ·
`PartiallyRecovered` · `LateResultDiscarded`

**Rejected, with reasons:** `NodeReady` (derivable from graph + outcomes; per node
per cycle it would bury everything an operator reads during an incident);
`DispatchRefused` (the ordinary state of a healthy run is "most nodes are not
dispatchable yet" — that is a metric, and the metrics seam is where it went);
`RetryStarted` (`ExecutionRetried` and `ExecutionAssigned` already bracket it).

## 15. `WorkerSelected` reconciled

ADR-037 created it with no emission site; ADR-038 noted the loose end. **Resolved
here:** `SelectingRequestFactory` at the composition root is the authoritative
selection boundary — the selection it makes is the one the gateway re-checks — so
it is the only correct emission point. A selection made elsewhere would name a
worker that never ran.

It carries execution, node, worker id, worker digest, binding digest, selection
digest, policy version and correlation id. No dead event type remains.

## 16. Metrics seam

`ExecutionMetrics` Protocol, plus `Null`, `Safe` and `Recording` implementations.
21 named metrics. **No Prometheus, no OpenTelemetry, no exporter.** `SafeMetrics`
contains every exception for the same reason `SafeObserver` does: a monitoring
backend being down must never fail an execution, and a metrics call in an error
path is exactly where that would happen.

## 17. Persistence and consistency boundary — stated plainly

**What is real:** compare-and-set within one process; lease exclusivity in the
aggregate; outbox ordering and claim exclusivity within one process; tenant
isolation at the repository guard.

**What is not:** the repository and the outbox are **in-memory**. They do not
survive process death. `compare_and_swap` guarantees nothing across processes —
there is no shared store to compare against. That is a limitation of having no
database, not of the design; the same method against a real one becomes
`UPDATE … WHERE revision = ?`.

**Critical write pairs that are NOT atomic today**, each a real consistency
boundary:

| Pair | Risk if the process dies between |
| --- | --- |
| state transition + outbox entry | state advanced, event never published |
| result recorded + checkpoint | progress recorded, resume point stale |
| attempt concluded + lease released | node appears held after it finished |
| recovery decision + next action | decision recorded, action never taken |
| compensation + recovery state | rollback ran, run not marked recovered |

All five become atomic when the repository and outbox share one transaction. None
of them is claimed atomic now. **No claim of crash-safe, cross-process durable,
exactly-once or zero-loss is made anywhere in this phase.**

## 18. V1 strangler — fully reconciled

Phase 3.3.3 gated 3 of 10 and reported 7. Leaving a known privileged bypass
switched on is a documented hole rather than a boundary, so **all ten are now
gated** on `CORTEXPRIME_ENABLE_LEGACY_EXECUTION`, default off:

`/api/v2/mcp/execute` · `/api/agents/run` · `/api/agents/delegate` ·
`/api/v1/runtime/execute` · `/api/executions/run` · `/api/orchestrator/execute` ·
`/operator/execute` · `/api/computer/execute-workflow` ·
`/api/engineering/sandbox/{id}/execute` · `/api/engineering/execute`

`ungated_surfaces()` now returns empty and is kept as the assertion that nothing
was found and left open.

Two judgements worth stating: `/operator/execute` was admin-guarded, and admin is
not governed — `_ADMIN` proves who is asking, not that the action was authorized
against a capability, a binding and a worker. `/api/engineering/sandbox/…/execute`
was sandboxed, and a sandbox is a containment boundary, not an authorization one.

Nothing was deleted. Read-only V1 routes are untouched.

## 19. Architectural contradictions found

1. **`profile_for` misuse in the dispatcher** — passing `spec.side_effect` instead
   of `spec` would have classified every keyed write as unkeyed. Caught by the
   focused verification, fixed.
2. **The aggregate has no tenant and no deadline.** Correct per ADR-017 (tenancy
   is contextual), but it means dispatch cannot read either from the execution.
   Both are now required parameters; a `getattr` default would have silently
   disabled the environment and deadline checks.
3. **Outbox ordering was by timestamp.** Microsecond ties are real. Changed to a
   monotonic sequence.
4. **`replace()` had no concurrency control** — last write wins, silently. Now
   `compare_and_swap` alongside it.

## 20. Genuine remaining risks

- **No durable store.** Everything above about in-memory persistence. This is the
  single largest gap and it is infrastructural, not architectural.
- **No cross-process fairness or distributed scheduling.** One thread, one
  process. The seam is right; the implementation is minimal.
- **The five non-atomic write pairs** in §17.
- **The dispatcher's queue claim degrades to the aggregate check** when the queue
  is absent or has an older signature. Safe (the aggregate still refuses a second
  holder) but it means the wasted-work prevention is best-effort.
- **Compensation dispatch is wired but untravelled** — no concrete worker exists
  to compensate *with*, so the path is verified structurally rather than
  end-to-end.

## 21. Phase 4 boundary — not started

No concrete workers, no MCP/connector transports, no OAuth, no shell/Docker/
Kubernetes/browser workers, no credential implementation, no LLM in any execution
decision, no distributed scheduler, no telemetry platform, no
`POST /execute-anything`, and no force-success administrative path.

The execution engine is complete while the worker directory is empty, which was
the objective.
