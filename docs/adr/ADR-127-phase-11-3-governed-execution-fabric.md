# ADR-127 — The governed execution fabric: making governed execution a durable, product-reachable platform service rather than a function call owned by one process

- **Status:** ACCEPTED
- **Date:** 2026-09-20
- **Phase:** 11.3 — Governed Execution Fabric
- **Parents:** ADR-125 (the connector architecture), ADR-126 (the GitHub connector, whose F-3 opened this), ADR-122 (the signal fabric, whose **D-4 this amends**), ADR-089/090 (contained workers, canonical approval digest), ADR-031 (retry), ADR-038 (invocation request)
- **Amends:** **ADR-122 D-4**, which codified single-process dispatch as the production shape and built `backend/signal/worker.py`'s leader/follower behaviour on it.

> **On the number.** This is 11.3 of the *connector/platform* program. An earlier
> 11.3 — detection + investigation, ADR-123 — is a different phase under the
> earlier roadmap numbering. The same limitation is called **F-3 in ADR-126**
> (the GitHub connector) and **F-1 in the signal-fabric verification report**.
> Both names refer to what this ADR fixes.

## Context

ADR-126 recorded F-3: *a governed execution is dispatched only by the process
holding the scheduler role, and that process drives only executions it tracked
itself.* Phase 11.2 could not fix it without pretending; this phase fixes it.

Tracing the real path (not the intended one) found the limitation is one line —
`ExecutionScheduler.tick` iterates `self._targets`, an in-RAM `list` fed only by
`track()` — and that **the machinery built to close it exists and is inert**:

| Built | State found |
|---|---|
| `SqlExecutionRepository.find_by_state` — the bounded, tenant-narrowed "what is mid-flight" query | no caller |
| `SqlExecutionRepository.compare_and_swap` — revision-checked write | only caller is `DurableExecutionStore` |
| `DurableExecutionStore.claim_node` — lease + CAS + outbox in one transaction | **zero production callers** |
| `cp_node_lease` — PK-exclusive, carries a `fence` | **never written** |
| `cp_queue` / `SqlExecutionQueue` | never enqueued; claim is a no-op (see F-2) |
| `DurableLeaseRecovery` | no importer |

## The finding that set the order of work

**F-3 was load-bearing.** It was not merely a limitation; it was the only thing
preventing duplicate execution.

`ExecutionService.assign` did `_load` → `execution.assign(...)` →
`repository.replace(...)`, and `replace` is by its own docstring *"the unguarded
write… correct only where the caller genuinely owns the row."* The aggregate's
"refuses a second holder" check ran against the copy **that caller** loaded. The
caller genuinely owned the row only because one process dispatched.

Reproduced against real PostgreSQL, two services on separate connections racing
one node:

```
caller A: SUCCEEDED as worker-A
caller B: SUCCEEDED as worker-B
callers that believe they own the node: 2      (expected 1)
durable row's lease holder: worker-B           (A's lease silently erased)
```

Both would have dispatched to the provider. Therefore: **fence first, admit
callers second.** Shipping the callers before the fence would have converted a
documented limitation into a live duplicate-execution hole.

## Decisions

### D-1 The node lease is revision-checked, and that lands before any new dispatcher

`ExecutionService.assign` now writes through `compare_and_swap`, so the compare
and the swap are one statement. The loser is refused with
`ConcurrentExecutionUpdate`, which the dispatcher already classifies as
`NODE_LEASED`. Same race, after the change: **1 winner, not 2.**

This is deliberately the smallest change that closes the hole, and it is correct
on its own — it needs no new component, no new table and no new dependency, and
it improves the single-process product too.

### D-2 The dispatch context is *reconstructed from the sealed binding*, never invented

The gateway requires a context that is not platform-internal, whose tenant
matches the request and the binding, and whose principal matches the request's
(`_check_identity`, `_check_tenancy`). A background dispatcher therefore cannot
run as the platform — and `_platform_context()` is exactly what the scheduler
loop uses today, which is why the background loop dispatches nothing at all.

The dispatcher does **not** fabricate a tenant context. It rebuilds one from the
durable, content-addressed `cp_binding` row, which was sealed at resolve time
with the original caller's tenant and principal after identity, tenancy and
authorization were already decided and persisted.

The context therefore **confers nothing**. It carries a decision already made.
Every gateway stage still runs against durable records — binding agreement,
authorization, approval, action digest, worker, input, lease, rate, credential —
and both sides of every check derive from the same sealed binding, so a
dispatcher cannot widen what was granted.

This is also the answer to the precedent in ADR-123 F-9 (*"the runtime's platform
loop leased tenant reads it could never invoke"*): the fix there was to refuse
platform-internal context **before** taking a lease. That refusal stays. This
decision does not relax it; it removes the need to hit it, by never dispatching
under a platform context in the first place.

### D-3 Discovery is durable; authority is not derived from discovery

Dispatchable work is found with `find_by_state` under the platform context,
which reads across tenants — discovery only. Nothing about being *found* grants
anything: the row is then dispatched under D-2's reconstructed tenant context
and re-authorized in full.

### D-4 Discovery adds to the tracked set; it never replaces it

A caller driving its own execution through `tick` still gets it dispatched on
the tick it asked for, rather than waiting to be rediscovered. A discovery
failure degrades to the tracked set and is metered, because losing the query
should cost the executions nobody is holding, not the ones somebody is waiting
on.

### D-6 Discovery is a background sweep, never a per-tick operation

A caller ticking for its own execution does the caller's work, not the store's.
The background loop sweeps, on an interval rather than at its tick rate. See
F-9: the alternative makes every caller pay for every orphan in the database,
and orphans accumulate because governed reads do not finalise their aggregate.

### D-5 The revision must be read with the aggregate, in one statement

See F-7. This is a decision and not merely a fix: any future write on this path
takes `find_with_revision`, because the alternative is a guard that reports
success it never obtained.

## Findings

| # | Finding | Severity | Status |
|---|---|---|---|
| F-1 | **The node lease was not fenced across processes.** `assign` wrote through the unguarded `replace`; two callers on separate connections both leased the same node and both believed they owned it. Masked only by single-process dispatch. Reproduced against real PostgreSQL. | **Critical** (latent) | **Fixed** (D-1), reproduction re-run shows 1 winner. |
| F-2 | **The dispatcher's queue-claim layer is dead and fails open.** `_claim` calls `queue.claim(context, worker_id=…, limit=1)`; no implementation has that signature, so it raises `TypeError`, which is caught and **returns `True` (proceed)**. Even with the right signature, `.enqueue(` has **zero callers** in `backend/`, so `cp_queue` is always empty and the empty result also returns `True`. The docstring's "ownership is the queue's, then the lease's" describes a layer that does not run. | High | **Fixed**: the port's own signature; the `TypeError` swallow removed; an outage is logged and metered (`execution.queue.unavailable`). |
| F-3 | **The background scheduler thread dispatches nothing.** It ticks under `_platform_context()`, and the dispatcher refuses to lease for a platform-internal context (ADR-123 D-12). Every real dispatch happens synchronously on the *caller's* thread inside `_drive`, serialised process-wide by a fair lock. "Governed execution" is mechanically a synchronous in-process function call. | High | **Fixed** (D-2): the dispatcher rebuilds the binding's tenant context, and the scheduler's targets come from the durable store. A process that never saw an execution now dispatches it. |
| F-4 | **Worker identity is process-local.** `ExecutionService._workers` is an in-memory dict and `build_worker_directory()` returns a per-process in-memory directory, while the lease holder is the string `dispatcher:{execution_id}` registered into it by the calling process. A durable target set alone is therefore insufficient — another process could not name the holder. | High | **Fixed**: the dispatching process registers its own lease-holder capacity; the pool answers capacity, never authority. |
| F-5 | **There is no periodic reconciliation.** `RecoveryCoordinator` runs once at process start and reads the durable store, but hands its plans to `_targets`. `DurableLeaseRecovery` (which reads `cp_node_lease`) has no importer, and `cp_node_lease` is never written. | Medium | Open. |
| F-7 | **The revision check was defeated by reading the revision separately from the aggregate.** `assign` did `find` then `revision_of`: a writer landing between the two leaves a stale aggregate (node still free) beside a fresh revision, so `compare_and_swap` *matches* and overwrites the winner's lease — the defect the check exists to close, reintroduced one statement away from it. Passed 295 deterministic tests; **found only by four real processes racing twelve nodes, which produced twelve double-leases.** | **Critical** | **Fixed**: `find_with_revision` reads both in one statement; re-run is 12/12 leased exactly once, 0 duplicates. |
| F-8 | **Hypothesis: a lost update between a holder's success and a late reclaim.** Fencing the claim leaves one holder but not one writer, so a reclaim landing after a success would erase it — the node would read `UNKNOWN` and recovery would be entitled to repeat the provider action. | — | **REFUTED by test.** The aggregate evaluates the lease against the clock **at write time**, not against the copy the caller loaded, so holder and reclaimer are mutually exclusive at every instant (`LeaseExpired` vs "the lease has not expired"). Recorded because the hypothesis was plausible and the refutation is the useful artefact. The outcome transitions were made revision-checked anyway, as defence in depth on a path that now has more than one process on it — **not** as a fix for a live hole. |
| F-9 | **Durable discovery made the tick loop pathological.** Discovery ran on *every* tick, including the tight caller-driven loop a governed read uses while waiting for its own node. Governed reads never finalise their aggregate, so a live database held **1382 runs in `RUNNING`**; one read then cycled up to 100 unrelated runs on each of up to 450 ticks — tens of thousands of dispatch cycles for a single read — and the real end-to-end run wedged. Introduced by this phase's own fix; **caught only by the real GitHub regression, not by 299 deterministic tests.** | High | **Fixed**: discovery is a background sweep — skipped on caller-driven ticks and rate-limited to an interval on the background loop. |
| F-6 | No `FOR UPDATE`, `SKIP LOCKED`, advisory lock or `LISTEN/NOTIFY` exists anywhere in `backend/`. All exclusivity is conditional-`UPDATE`-plus-rowcount or PK collision. Recorded because it bounds which dispatch designs are available without new mechanism. | Informational | Recorded. |

## Consequences

- **F-3 is closed as recorded.** "A governed execution is dispatched only by the
  process holding the scheduler role, and that process drives only executions it
  tracked itself" is no longer true. Proven with four real OS processes and a
  real store; the GitHub connector regression passes 81/81 unchanged, including
  a real governed write.
- **The mandate's wider gate is not met**, and this ADR does not claim it: no
  asynchronous API execution contract, no MCP integration, multi-replica not
  deployed (the chart is still `replicas: 1`), crash cases B/C/D unexercised, no
  red team, no latency baseline. See the verification report §26.
- **Three defects were found on this path and two were introduced by this
  phase's own fixes** (F-2, F-7, F-9), and none was reachable by deterministic
  testing. The transferable rule: a change to a concurrency path is unproven
  until real concurrency *and* real data volume have run against it.
- **ADR-122 D-4 is amended.** It codified "a runtime dispatches only the
  executions its own process started" as the production shape, and
  `backend/signal/worker.py` implements an honest hot-standby follower on that
  basis. Once dispatch is durable, that constraint no longer holds.
- Exactly-once is **not** claimed. See the verification report.
