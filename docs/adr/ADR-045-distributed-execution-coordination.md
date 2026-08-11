# ADR-045 — Distributed execution coordination

**Status:** Accepted
**Date:** 2026-08-08
**Phase:** 5.2 — Distributed execution coordination
**Extends:** ADR-044 (durable state), ADR-043 (production connectivity), ADR-039
(lifecycle and recovery), ADR-038 (invocation gateway), ADR-031 (durable
execution core)

---

## 1. The one question

    "Can several instances coordinate over durable state without two of them
     doing the same work, and without a restarted process still acting as the
     owner it used to be?"

Phase 5.1 made state survive. This makes *coordination* survive.

## 2. What was already there, and was not replaced

| Component | Classification | What happened |
| --- | --- | --- |
| `ExecutionScheduler` | AUTHORITATIVE, process-local | **Extended**, not replaced: two optional ports and two new states |
| `ExecutionQueue` Protocol | AUTHORITATIVE | Unchanged; `SqlExecutionQueue` implements it |
| `InMemoryExecutionQueue` | PROCESS_LOCAL | Kept, correct for development |
| `ExecutionDispatcher` | AUTHORITATIVE | Untouched — it owns retry planning |
| `RecoveryCoordinator` | AUTHORITATIVE | Untouched — it owns recovery policy |
| Durable outbox (5.1) | AUTHORITATIVE | Gained a publisher |
| `SqlDelegationRepository` (5.1) | seam | Gained an authority that reads it |
| V1 loops, registries, connectors | LEGACY / STRANGLER | Unchanged, still gated |

No second scheduler, no second queue abstraction, no second recovery policy, no
second authorization engine.

## 3. The durable work queue

`cp_queue`, one row per `(execution_id, node_id)`.

**It is not a second source of truth.** The execution aggregate remains
authoritative; a queue row is a *reference* — tenant, execution, node, kind, and
enough identity to find the real thing. Everything that decides whether work may
run is re-derived downstream from the aggregate, the binding and the
authorization. Losing the queue loses ordering and claims, not work:
`ready_nodes()` recomputes it.

Nothing on a row could be mistaken for authority. There is no capability, no
principal and no digest, deliberately.

### Claim

One conditional `UPDATE` over a bounded candidate set, then a read-back filtered
on `claimed_by`. Two instances cannot both take an item: the second's predicate
no longer matches. Reading back the *request* rather than the *result* is exactly
how two instances end up believing they own the same node, so the read-back
filters on the claimant.

There is no `SELECT` → Python `if` → `UPDATE` anywhere in the module.

Claims are leases and **expire**. An instance that dies between claiming and
leasing leaves an item that returns to the queue rather than one that vanished.

### Ordering, and the actual guarantee

    priority DESC, available_at ASC, sequence ASC

`sequence` is unique, so the order is **total** — no tie is left for dictionary
order, object identity, randomness or a wall clock to break.

**What that is not:** it is claiming order, not completion order. Several
instances each take the head of what they can see, so item 5 can finish before
item 3. Deterministic claiming; non-deterministic completion. Overclaiming here
would be the easiest thing in the phase to get wrong.

### Tenant fairness

**Not implemented, deliberately.** The platform has no tenant quota policy, and
§5 forbids inventing one. What exists is the seam: `tenant_depths()` produces the
deterministic, durable number a policy or an operator would need — and requires
platform-internal authority, because showing one tenant how much work another has
is a disclosure.

The limitation is therefore real: **one tenant with a large backlog can occupy
claim capacity.** Recorded rather than papered over.

## 4. Scheduler

Extended in place. `SchedulerState` gained `FAILED` — genuinely missing, and
distinct from `STOPPED` because "we stopped it" and "it broke" need different
responses. `STARTING` and `QUIESCING` are **aliases** of the existing
`RECOVERING` and `DRAINING`: the directive's vocabulary without a second pair of
states to keep in step.

Two optional ports, both fail-closed when present and both absent-means-unchanged:

* `ReadinessPort` — durable state usable? Checked **every tick**, not once at
  startup, because a database that went away after the process started is the
  case this exists for. Not ready ⇒ no dispatch.
* `LeadershipPort` — hold the scheduler role? Not leader ⇒ no dispatch, cheaply.

Startup recovery that raises leaves the scheduler `FAILED` and **not
dispatching**: starting work beside outcomes nobody established is what recovery
exists to prevent.

The scheduler still decides only *when to look*. Authorization, provider
selection, worker selection, retry policy, compensation and credentials all
remain where they were, and the path is unchanged:

    scheduler → durable queue → dispatcher → execution state → gateway → worker

## 5. Leader election — and where it is deliberately not used

Three roles: `RECOVERY_SWEEP`, `OUTBOX_PUBLISHER`, `SCHEDULER`. Each is there
because the work must happen **once**, not once per item.

**Ordinary dispatch is not one of them.** The queue's conditional claim already
makes exactly one instance the owner of each item, so electing a leader for
dispatch would take a system that scales horizontally and give it a bottleneck
and a failover gap. Leadership is for singleton coordination; it is not a
substitute for concurrency control.

Election is one conditional `UPDATE`. Two instances arriving together cannot both
match `status != held OR expires_at <= now`. A follower gets `None` — the
ordinary answer for nine instances in ten, and never an exception.

Leadership **expires**. `heartbeat` extends it by one bounded period and is
fenced, so a leader that is wedged stops heartbeating and lapses, and a leader
that is partitioned has its extension refused by the same fence that refuses its
writes. A dead leader becomes replaceable after one lease period with nobody
intervening.

### Losing leadership is not losing execution authority

A scheduler that loses the role stops **scheduling**. It does not kill workers,
rewrite execution state, conclude attempts or cancel anything — active work is
governed by its own execution lease. A scheduler that killed workers on losing an
election would turn a coordination hiccup into a production incident.

## 6. Instance fencing

The failure this closes:

    A acquires the role, token 41
    A stalls — GC pause, partition, suspended VM
    A's lease expires; B acquires, token 42
    A wakes believing it is still the leader and writes

A Python-side "am I still the leader?" cannot close this: A *was* the leader when
it checked, and the stall is between the check and the write.

So the token travels **into the durable mutation** and the database rejects it.
`SqlLeadershipStore.fenced_where` / `fenced_exists` compose the fence into the
caller's own statement. There is no check to be stale, because there is no
check — there is one conditional write.

The token is a **counter on a row that outlives every leader**, incremented in
place on acquisition. That is what makes it monotonic. A UUID has no order; a
timestamp has an order two machines disagree about, which is the same problem
wearing a number.

Re-acquiring advances the token, so an instance that restarted quickly fences out
its own previous incarnation. `release` does *not* advance it: releasing is a
leader saying it has finished, and its writes up to that point were legitimate.

**The one durable hazard**: dropping `cp_leadership` resets every token to zero.
The migration's downgrade says so explicitly.

## 7. Recovery

`DurableLeaseRecovery` connects the durable lease store to the **existing**
`RecoveryCoordinator`. It never calls `plan_recovery`, has no access to the retry
rules, and contains no branch that decides to retry, compensate or fail.

    durable lease state → this → RecoveryCoordinator.plan → the decision

Three gates before a reclaim, all of which must agree: the lease is finished; it
is not ambiguous; and the existing policy returns `RESUME_FROM_CHECKPOINT` or
`RETRY_ATTEMPT`. A `COMPENSATE` or `FAIL_EXECUTION` decision is not a reclaim,
and an unrecognised action is a refusal — an unrecognised action is not a
permission.

Reclaims are **fenced** and happen in one transaction: old ownership invalidated,
fence advanced, new lease established. Read → decide → write would leave a window
where the old holder's heartbeat revives a lease already given away.

### Ambiguity is preserved

An `AMBIGUOUS` lease — expired, but heartbeating moments ago — is **never
automatically reclaimed**. Reclaiming would run the node twice; refusing forever
would strand it. It becomes a decision a person resolves, exactly as an ambiguous
*outcome* does. Turning it into a timeout would throw the distinction away.

Attempts remain append-only. Retry classification, idempotency and effect
semantics are untouched.

## 8. Outbox publisher

Claim → deliver → acknowledge. The order is the design: claim before delivering,
so two publishers cannot hand over the same entry; acknowledge after delivering,
so a crash between the two leaves the entry pending rather than marked published.
Both are survivable and only one direction loses an event, which is why the risk
is taken on the side of duplication.

**At-least-once, and not upgraded.** `event_id` is a column, written once, never
regenerated — stable across initial publish, retry, reclaim and restart. A
consumer that deduplicates on it is correct; one that assumes single delivery is
not.

Four delivery outcomes are distinguished, and the third is the load-bearing one:

| | meaning | effect |
| --- | --- | --- |
| `DELIVERED` | the sink took it | acknowledged |
| `REJECTED` | the sink refused it | counts towards dead-lettering |
| `UNKNOWN` | the sink may or may not have it | **stays pending, same event id, not counted** |
| claim failed | nothing was taken | skipped |

An `UNKNOWN` counted towards dead-lettering would dead-letter an event that may
well have been delivered. Treated as delivered, it would be lost.

Ordering is **per-claim**, not global. A deployment needing total order runs one
publisher via the `OUTBOX_PUBLISHER` role — and even then the guarantee is "one
at a time", not "one ever", because a leader can lapse.

Dead-letter semantics from 5.1 are unchanged: threshold of ten, and the entry
keeps its `event_id`, `sequence`, attempt count, last error, timestamps and
tenant. Never deleted — it is what somebody looks for after an incident.

No retry loop and no sleep. `publish_batch` does one pass and returns; repeating
is the caller's business.

## 9. Delegation

`DurableDelegationAuthority` implements the port Phase 4.4 left unwired, reading
the Phase 5.1 seam. It is **not** a second authorization engine: it answers one
narrower question — is there a durable, live, scoped grant letting this actor
borrow that identity — and the gateway's `_check_delegation` does the comparing,
unchanged.

Ten refusals and no default-allow: no store, no grant, wrong tenant, wrong actor,
wrong delegated principal, expired, revoked, out-of-scope operation, digest
mismatch, lookup raised. `None` in an empty database keeps every on-behalf-of
invocation refused, which is the Phase 4.4 default and is meant to be reached.

The actor is the **authenticated** principal. A request body cannot introduce a
delegation, widen one, or name an actor.

Structural refusals at issue time: self-delegation, empty scope (which would read
as everything), scope entries with no operation, and an already-expired window.

`DelegationStatus` is **derived**, never a stored column: `revoked_at` and
`expires_at` determine it completely, and a second copy would eventually
authorize something the timestamps say is dead.

### Revocation is immediate

Nothing is cached. Every check reads the durable row, so a revoked grant stops
authorizing the *next* invocation rather than the next cache expiry. That costs
one query per delegated invocation and the trade is deliberate: a cache would
need authoritative cross-instance invalidation to be correct.

Already-running work keeps its authority window. Retroactively rewriting what was
authorized would falsify historical evidence.

**No issuing surface exists.** There is no route and no command that grants a
delegation; `issue` exists so the model is exercisable. Building the approval
workflow is Phase 5.3.

## 10. PostgreSQL verification — **not run, and why**

The directive requires a real attempt. It was made:

    localhost:5432   ConnectionRefusedError
    127.0.0.1:5432   ConnectionRefusedError
    postgres:5432    name does not resolve
    db:5432          name does not resolve
    docker           daemon not running (npipe not found)
    POSTGRES_URL     not set

**SQLite was not substituted.** `validate_52_postgres.py` connects to a real
PostgreSQL, runs the scenarios, and — when it cannot — prints exactly why and
exits `2`, which means *not verified* rather than *verified*.

**Therefore: no PostgreSQL production-durability claim is made, in this ADR or
anywhere else.** Specifically unverified:

* serialization failures under `SERIALIZABLE` / `REPEATABLE READ`, and 40001
  classification
* deadlock detection and 40P01 classification
* `BIGSERIAL` allocation for `cp_outbox`
* connection-pool exhaustion and acquisition timeout
* connection loss mid-`COMMIT` and the `UnknownCommitOutcome` path
* tuple-`IN` behaviour in the queue claim

What *was* verified: the DDL for both new tables compiles against the PostgreSQL
dialect, and every write path is portable Core SQL with the one dialect branch
(`_supports_tuple_in`) written to be identical in meaning on both.

The suite is ready. `POSTGRES_URL=... python validate_52_postgres.py` runs it.

## 11. Connection pool

Explicit and bounded, unchanged from 5.1 and asserted by the PostgreSQL suite:
`pool_size`, `max_overflow`, bounded `pool_timeout` (an unbounded wait for a
connection is an unbounded hold on whatever asked for it), `pool_recycle`,
`pool_pre_ping`. No global session; the engine is a pool, which is a resource,
not a transaction. Disposal is verified by checking `checkedout() == 0`.

## 12. Readiness and shutdown

Four separate answers: process liveness, database health, `durable_state`,
`durable_scheduling`. A process can be alive while the store is not, and
conflating them takes a healthy instance out of rotation for a database problem —
or, worse, leaves a useless one in.

`durable_scheduling` now reports true where 5.1 reported false. What is **still**
not claimed is a worker: the execution directory is deliberately empty and the
platform refuses execution until one is registered and enabled.

Shutdown order, per §30: stop scheduling → stop claiming → leave active leases
alone → release leadership last (so a successor cannot start coordinating while
this one finishes a cycle) → dispose. Idempotent, including after a failure.
Releasing is best-effort and never raises: a shutdown blocked on an unreachable
database would leave a process alive holding a role it is not using.

## 13. Atomicity

| Pair | Atomic? |
| --- | --- |
| queue claim + read-back of what is held | yes, one transaction |
| leader acquisition + fencing-token advance | yes, one `UPDATE` |
| fenced write + leadership check | yes, the fence is *in* the write |
| recovery reclaim + new lease | yes, one transaction |
| outbox claim | yes |
| delegation issue + digest | yes |
| execution state + outbox event (5.1) | yes |
| **outbox publish + sink delivery** | **no, and cannot be** |
| **queue claim + execution lease** | atomic only when written in one unit |

The eighth is the honest limit and the reason delivery is at-least-once. The
ninth is atomic when the caller passes a `UnitOfWork` — `DurableExecutionStore`
does; a caller that claims and then leases separately gets two transactions, and
a crash between them leaves a claimed item whose claim lapses. Survivable, and
recorded.

## 14. V1 persistence decision

`backend/api/legacy_persistence_inventory.py` classifies every V1 SQLAlchemy
model — KEEP / REPLACE / STRANGLER / REMOVE_LATER / SECURITY_HAZARD — with owner,
callers, tenant model, transaction behaviour and migration risk. **Nothing was
migrated.**

The dominant finding: **almost none of these tables carries a tenant.** They
predate `ExecutionContext` and the storage guard. That is inherited state, not a
regression, and it is why none is on the Phase 4 authority path — every route
reaching them is read-only reporting or already gated.

One hazard: `backend/database/engine.py`. `init_db()` runs
`Base.metadata.create_all`, building schema **outside the Alembic history** —
exactly what 5.1's production config refuses for the durable store — and the
module-level engine is constructed at import from environment variables with a
password-less localhost default. Neither is on the authority path (the durable
store has its own engine, built explicitly and verified). **Gate `init_db` in
production; do not delete it** — development and tests rely on it.

`backend/database/repositories/*` commit inside the repository, so a caller
cannot compose two writes into one transaction — the defect `UnitOfWork` exists
to prevent. Not a hazard where they sit; not a pattern to copy.

## 15. Defects found by the tests

1. **The delegation digest could not round-trip.** `issue` digested
   `work.now.isoformat()` (offset-aware); verification re-derived it from a value
   SQLite returns naive, producing a different string. Every stored grant would
   have failed its own digest check — and it would have looked like tamper
   detection working. Fixed with **one shared `delegation_digest_payload`** used
   at both ends, normalising timestamps.
2. A Phase 5.1 assertion that "durable scheduling is not claimed" and a
   table-count assertion both went stale when 5.2 made them false. Updated to
   assert what 5.1 still guarantees rather than deleted.
3. Two intermittently-failing checks exposed a behaviour worth stating rather
   than a bug: **leadership is acquired on the first tick, not at ``start``.**
   That is deliberate — ``start`` runs recovery first, and taking the role
   before recovery has established what the last process left behind would be
   coordinating over an unknown state. A scheduler that starts and stops
   immediately therefore never held the role and correctly releases nothing.

## 16. Security

Tenant isolation, principal identity, capability digest, binding digest,
authorization digest, worker digest, execution identity and node identity are all
preserved. The queue is tenant-scoped in SQL; a per-tenant breakdown requires
platform-internal authority.

**Authority is never reconstructed from queue metadata.** A queue row is a hint
that an execution is worth loading. Every check runs again from the aggregate.

One injected clock throughout. No `datetime.now()` in an authority decision;
leader expiry, queue availability, lease expiry and delegation validity all read
`UnitOfWork.now`. All durable timestamps UTC, no `server_default NOW()`.

No credential, password or secret is logged. No fake tenant was introduced.

## 17. Verification

**121 new Phase 5.2 checks, 0 failures**, plus 244 earlier checks still passing
(365 total). Architecture fitness: 0 FAIL.

Genuinely separate processes (`ProcessPoolExecutor`, spawn) with file barriers so
both parties reach the contended operation before either proceeds — without that,
most concurrency tests pass without a race ever happening.

Covered: queue persistence/dedup/ordering/future-availability, cross-process
queue claim, concurrent enqueue, queue tenant isolation, leader election
single-winner, concurrent election across processes, heartbeat authority, stale
fence rejection at the write, monotonic tokens across takeover and re-acquisition,
release-does-not-advance, scheduler lifecycle/leadership/readiness gating/failed
startup/idempotent stop, ambiguous-lease preservation, policy-gated reclaim,
fence advance on reclaim, outbox publish/unknown/rejection/dead-letter/reclaim
with stable ids, delegation valid/expired/revoked/wrong-tenant/wrong-actor/
wrong-principal/out-of-scope/digest-tamper/missing, structural issue-time
refusals, V1 gates unchanged, no fake tenant, no concrete worker, migration
additivity and schema agreement.

## 18. Limitations

* **PostgreSQL unverified** (§10). The largest one.
* **No tenant fairness policy** — one tenant can occupy claim capacity (§3).
* **Claim + lease is two transactions** unless a unit is threaded (§13).
* **Per-claim ordering only**, for both queue and outbox.
* **No delegation issuing surface** — the model exists, the workflow does not.
* **No worker.** The platform still refuses execution.
* Queue sequence allocation is `MAX + 1` under the transaction with a unique
  constraint behind it, rather than a database sequence — portable, at the cost
  of a conflict under concurrent enqueue that the caller reads as "already
  queued".

## 19. Phase 5.3 boundary

In scope for 5.3, and explicitly **not** built here:

* the delegation approval workflow — issuing, approval, an administrative
  surface, and the policy governing who may grant one
* concrete workers, and the execution of real provider operations end to end
* MCP SSE and a sandboxed stdio transport
* connector configuration migration and a governed replacement for the V1 UI
* gating `init_db` in production and the V1 model migrations this phase decided
* a tenant fairness policy, if the platform decides it needs one
* PostgreSQL operational work: isolation-level selection, retry policy for
  serialization failures, pool sizing under load

Not in scope for 5.3 and not implied by anything here: an LLM participating in
tool selection, provider selection, capability ranking or authorization
reasoning; or any relaxation of the V1 strangler gates.
