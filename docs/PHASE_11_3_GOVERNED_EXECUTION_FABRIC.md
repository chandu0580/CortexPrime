# Phase 11.3 — The governed execution fabric: verification report

Decision record: `docs/adr/ADR-127-phase-11-3-governed-execution-fabric.md`.
Machine-readable evidence: `docs/phase113_execution_fabric_report.json`.
Harness: `scripts/phase113_execution_fabric_harness.py`.
GitHub regression evidence: `docs/phase113_github_regression_report.json`
(kept separate from Phase 11.2's own record run, which it must not overwrite).

> **On the number.** This is 11.3 of the *connector/platform* program. An earlier
> 11.3 — detection + investigation, ADR-123 — is a different phase under the
> earlier roadmap numbering. The limitation fixed here is called **F-3 in
> ADR-126** (the GitHub connector) and **F-1 in the signal-fabric verification
> report**; both names refer to the same thing.

Every claim is marked **FACT** (observed this phase, evidence named),
**INFERENCE** (reasoned from facts) or **UNKNOWN** (not established here).

---

## 1. Current architecture (as found, not as intended)

**FACT.** The deployed governed product is **one pod, one replica, one OS
process** (`replicas: 1`, `strategy: Recreate`) running uvicorn, the scheduler
thread, the outbox pump, the remediator, the investigator, the signal worker and
connector health together.

**FACT.** The governed chain has exactly one door from application code
(`GovernedCapabilityReader._perform`, with `GovernedCapabilityWriter` as its
mutating subclass), and the gateway is called from exactly one place in
non-test code: the dispatcher.

**FACT.** The deployed product exposes exactly **one** route that can cause a
provider-side mutation: `POST /approvals/{id}/execute`. `/api/v1/executions` and
mission-control are mounted only by the V1 monolith's `router_registry`, which
the governed product app does not import, so they cannot create orphan rows in
the product.

---

## 2. F-3 root cause

**FACT.** Three compounding facts, each traced in code:

1. `ExecutionScheduler.tick` iterates `self._targets` — a plain in-RAM `list`
   written only by `track()`. It never queried the durable store. A run started
   by any other process was invisible **forever**; only a restart could rescue
   it, and only if recovery classified it automatically resumable.
2. The background scheduler thread **dispatched nothing**. It ticks under
   `_platform_context()`, and the dispatcher refuses to lease for a
   platform-internal context (ADR-123 D-12). Every real dispatch happened
   synchronously on the *caller's* thread inside `_drive`, serialised
   process-wide by a fair lock.
3. So "governed execution" was mechanically **a synchronous in-process function
   call wearing a scheduler's clothes.**

**FACT.** The machinery built to close this existed and was inert: `find_by_state`
had no caller; `compare_and_swap`'s only caller was `DurableExecutionStore`,
which itself had **zero production callers**; `cp_node_lease` (PK-exclusive,
carrying a `fence`) was never written; `cp_queue` was never enqueued;
`DurableLeaseRecovery` had no importer.

---

## 3. The finding that set the order of the work

**FACT. F-3 was load-bearing.** It was not only a limitation — it was the only
thing preventing duplicate execution.

`ExecutionService.assign` wrote through `replace`, which its own docstring calls
*"the unguarded write… correct only where the caller genuinely owns the row."*
The aggregate's "refuses a second holder" check ran against the copy **that
caller** loaded. The caller owned the row only because one process dispatched.

Reproduced against real PostgreSQL, two services on separate connections:

```
caller A: SUCCEEDED as worker-A
caller B: SUCCEEDED as worker-B
callers that believe they own the node: 2      (expected 1)
durable row's lease holder: worker-B           (A's lease silently erased)
```

**INFERENCE.** Lifting F-3 without fencing first would have converted a
documented limitation into a live duplicate-execution hole. Hence the order:
**fence, then admit callers.**

---

## 4. Architectural decision

**FACT (ratified by the operator, 2026-09-20).** The dispatcher does not
fabricate a tenant context and does not run as the platform. It **rebuilds the
context from the node's sealed `cp_binding` row**, which was written at resolve
time carrying the tenant and principal the work was authorized for, after
identity, tenancy and authorization had already been decided.

The context **confers nothing**. Every gateway stage re-runs against durable
records, and both the request and the context derive from the same binding, so a
dispatcher cannot name a tenant, principal or capability other than the one
already admitted.

**FACT.** This refines rather than relaxes ADR-123 F-9. That rule was never
"platform contexts are refused"; it was *never lease under a context the gateway
will certainly refuse*. The rebuilt context is the one context the gateway will
**not** refuse on tenancy. Where no such context can be built, the refusal
stands and nothing is leased — proven by test.

**FACT.** `BoundCapability` cannot be constructed without a non-blank tenant and
principal ("an uncheckable binding is not authority"), so the sealed binding
always names both — a stronger guarantee than the dispatcher's own check.

---

## 5–7. Durable state, dispatch and claiming

**FACT.** No new table, no new migration, no new dependency, no new identity and
no new locking system were added. What changed:

| Change | Why |
|---|---|
| `assign` writes through `compare_and_swap` | the fence (§3) |
| `find_with_revision` — aggregate and revision in **one** statement | §8 |
| `ExecutionService.dispatchable` — bounded, tenant-narrowed durable discovery | the scheduler had no durable source |
| scheduler `discovery` port, unioned with the tracked set | F-3 |
| dispatcher rebuilds the tenant context from the binding | §4 |
| dispatcher registers its own lease-holder capacity | another process could not name the holder |
| queue claim uses the port's real signature | §9 |

**FACT.** `cp_queue` remains unenqueued: it is a hint about *where* work is, not
the authority on *who owns it*, and an absent item proceeds to the lease. The
revision-checked lease is what refuses a second holder.

---

## 8. Three defects that only real execution exposed

**FACT.** Every defect this phase found on the dispatch path was a concurrency
or scale property, and **none was reachable by the cheaper evidence**:

| Defect | What passed while it was present | What caught it |
|---|---|---|
| F-2 — queue claim reported claims it never made | months of green suites | running it, not reading it |
| F-7 — the revision check defeated by a split read | 295 deterministic tests | 4 real OS processes racing 12 nodes |
| F-9 — discovery made the tick loop pathological | 299 tests **and** a 15/15 multi-process harness | the real cluster, with real accumulated data |

**INFERENCE.** F-7 and F-9 were introduced by this phase's own fixes. A change to
a concurrency path should be assumed wrong until real concurrency and real data
volume have run against it.

### 8.1 The defect the multi-process test found in the fix

**FACT.** The first fence was wrong, and **295 deterministic tests did not
catch it.** `assign` read the aggregate and its revision in two statements. A
writer landing between them leaves a stale aggregate (node still free) beside a
fresh revision — so `compare_and_swap` *matches* and overwrites the winner's
lease. The guard reported success it had never obtained, one statement away from
the check it exists to be.

Four real processes racing twelve nodes:

```
before: nodes leased by MORE than one process : 12   (0 of 12 leased exactly once)
after : nodes leased by MORE than one process : 0    (12 of 12 leased exactly once)
```

**INFERENCE.** Unit tests were right about the code and wrong about the world.
Concurrency defects of this shape are not reachable without real concurrency.

---

### 8.2 The defect the real cluster found in the fix (F-9)

**FACT.** Discovery ran on *every* tick, including the tight caller-driven loop a
governed read uses while waiting for its own node. Governed reads never finalise
their aggregate, so a live database held **1382 runs in `RUNNING`**. One read
then cycled up to 100 unrelated runs on each of up to 450 ticks — tens of
thousands of dispatch cycles for a single read — and the real end-to-end run
wedged for over seven minutes before being stopped.

**FACT.** The design error was categorical, not numerical: discovery is a
**background sweep**, and it had been made a per-tick operation. Fixed by two
guards — a caller-driven tick never sweeps (it does the caller's work), and the
background loop sweeps on an interval rather than at tick rate.

## 9. F-2: a security layer that was never running

**FACT.** The dispatcher's queue claim called
`queue.claim(context, worker_id=…, limit=1)`. **No implementation of the port
accepts that signature** — it is `(context, worker_id, kinds, seconds)` — so
every call raised `TypeError` into an `except TypeError: return True`. A claim
was reported as obtained, on every dispatch, and never made. Proven by
execution, not by reading:

```
InMemoryExecutionQueue.claim(context, worker_id=..., limit=1) -> TypeError
  queue raises TypeError (the real case) -> _claim returns True  (PROCEED)
  queue is empty (nothing ever enqueued) -> _claim returns True  (PROCEED)
callers of .enqueue( under backend/: 0
```

Both failure modes fail **open**. Fixed: the port's own signature, the
`TypeError` swallow removed, and an outage now logged at error and metered
(`execution.queue.unavailable`) rather than passing silently.

---

## 10–13. API, MCP, agent and scheduler execution

**UNKNOWN / NOT DONE.** This phase established the platform property that makes
these possible — dispatch is now a property of the run rather than of the
process that created it — but the caller-facing work is **not** done:

- **API-initiated execution** (§8 of the mandate): not implemented. The existing
  `POST /approvals/{id}/execute` still drives its own execution inside the API
  process via `_drive`. It now *would* be dispatched by another process if the
  caller vanished, but the asynchronous contract (return an execution id and a
  status, do not tie the operation to the HTTP request lifetime) is not built.
- **MCP** (§9): the MCP surface (`backend/mcp/`) is V1/legacy and gated off
  behind `guard_legacy_execution`. It does not reach the governed path, and no
  integration was built this phase.
- **Agent-initiated** (§10): already the case before this phase — a model emits
  a schema-validated proposal and deterministic code owns validation,
  authorization, approval, execution and verification. Unchanged here.
- **Scheduler as one producer among many** (§11): partially. The scheduler no
  longer holds the authoritative target set; it reads it. But it is still the
  only component that ticks.

---

## 14–15. State machine and action digest

**FACT.** No state was added. The lifecycle is unchanged
(`PENDING/RUNNING/PAUSED/…`, `WAITING/READY/LEASED/SUCCEEDED/FAILED/UNKNOWN/…`),
and the transition tables in `domain/state.py` remain the single authority.

**FACT.** The action digest and approval binding are untouched by this phase.
The security stage re-proves that what changed is *who may carry* a decision,
not *what was decided*.

---

## 16–17. Tenancy and credentials

**FACT (harness SECURITY stage).**

- another tenant's discovery does not return this tenant's run (0 rows);
- another tenant cannot lease this tenant's node — refused `ExecutionNotFound`,
  i.e. reported as **absent rather than as a conflict**, which is the correct
  non-disclosing behaviour;
- a binding naming no tenant produces **no** dispatch context (refused, not
  defaulted);
- the rebuilt context carries the binding's own tenant and principal and is not
  platform-internal;
- the dispatcher cannot choose a tenant: it is read, never supplied.

**FACT.** One of these checks first passed for the wrong reason — a dropped
port-forward surfaced as `OperationalError` and was counted as a tenancy
refusal. The check now requires a named tenancy refusal and the harness records
why. **A false pass on a security property is worse than a failure.**

**UNKNOWN.** Credential lifecycle under multi-process dispatch (expiry, renewal,
refusal) was not exercised this phase.

---

## 18–19. Audit and observability

**UNKNOWN.** Not re-verified this phase beyond the untouched existing paths. One
metric was added to the documented vocabulary (`execution.queue.unavailable`).

---

## 20–22. Failure scenarios and multi-replica behaviour

**FACT (harness, 15/15 VERIFIED).**

| Stage | What it established |
|---|---|
| FENCE | 4 real OS processes, 12 nodes: **0 held by two**, **0 orphans**, every loser refused with a named conflict (`ConcurrentExecutionUpdate` / `NodeAlreadyLeased`), not a crash |
| DURABLE | a process that never saw a run finds it dispatchable and its scheduler cycles it **with an empty tracked set** |
| SECURITY | §16 |
| RECOVERY | a run outlives the process holding its lease; a lapsed lease becomes reclaimable; **a live lease does not** (a slow worker is not a dead one) |

**FACT (crash matrix, partial).** Case A/E (dispatcher dies, run recoverable by
another process) are proven. **UNKNOWN:** Case B (death *during* the provider
call), Case C (death after the call, before recording) and Case D (verifier
dies) were not exercised end-to-end this phase.

**FACT (F-8, refuted).** A hypothesised lost update — a late reclaim erasing a
recorded success, yielding a duplicate provider action — is **not reachable**.
The aggregate evaluates the lease against the clock at write time, not against
the loaded copy, so holder and reclaimer are mutually exclusive at every
instant. Recorded as refuted because the hypothesis was plausible; the outcome
transitions were made revision-checked anyway as defence in depth, **not** as a
fix for a live hole.

---

## 23–24. Kubernetes and GitHub regression

**FACT.** Deterministic: **3361 passed, 1 failed** across
`connector_fabric, connectors, contexts, architecture, platform, contracts,
deployment, signal`. The single failure is pre-existing and unrelated
(`credentials/inspection.py` imports `base64`, absent from a guard's
allow-list; both files byte-identical to `HEAD` since Phase 7.2) and was
already failing before this phase.

**FACT.** A runtime image carrying these changes (`1.0.0-b16`) was built and
deployed to the live k3d cluster through the ordinary Helm path.

**FACT (real end-to-end regression).** The full Phase 11.2 GitHub harness was
re-run against the rebuilt image on the live k3d cluster: **81/81 checks passed,
verdict VERIFIED** — unchanged from the result before this phase. That includes
every shipped read against the real repository, **a real governed write**
(comment `5749916554` on issue #22, independently verified byte-for-byte),
approval and approval-replay refusal, all sixteen negative cases at **0 GitHub
writes**, and all seven behavioural evaluations PASS.

**INFERENCE.** The execution fabric changed underneath the connector without the
connector noticing, which is what "the same governance, the same verification"
has to mean in practice.

**UNKNOWN.** The Kubernetes connector's own harness (11.1-K) was **not** re-run
this phase; the Kubernetes evidence here is the deterministic suites plus the
fact that both connectors share the one dispatch path the GitHub run exercised.

---

## 25. Performance

**FACT.** Fence stage: 4 processes over 12 nodes in ~5 s wall clock. Whole
harness: ~26 s.

**UNKNOWN.** The mandate's latency baseline (request → durable execution →
claim → provider call → verification) was **not** measured. No optimisation was
attempted and none is claimed.

---

## 26. Known limitations

Stated, not implied.

1. **The caller-facing half of the mandate is not built** (§10–13): no
   asynchronous API execution contract, no MCP integration, no second ticking
   component.
2. **Multi-replica is not deployed.** The chart still runs `replicas: 1` with
   `strategy: Recreate`. The *platform* property was proven with real processes
   against a real store; running two replicas in the cluster was not done.
3. **Crash matrix B/C/D not exercised** (§20).
4. **`cp_queue` remains unenqueued** and `cp_node_lease` remains unwritten; the
   fence is the execution row's revision, not the lease table's fence token.
5. **Exactly-once is not claimed.** CortexPrime provides durable at-least-once
   dispatch with a revision-checked claim, idempotency where the provider
   supports it, and independent verification.
6. **Red team not run** (§21's 18 cases); only the subset in the SECURITY stage.
7. **ADR-122 D-4 is amended but its dependents are not revisited.**
   `backend/signal/worker.py` still implements hot-standby follower behaviour
   built on the assumption this phase removed.
8. Audit/observability/credential-lifecycle not re-verified under multi-process.

---

## 27. Completion decision

### F-3: COMPLETE as a platform property — the phase as mandated: NOT COMPLETE

**What is genuinely done and proven.** Governed execution is no longer owned by
one process's memory. A process that never saw a run discovers it durably and
dispatches it; four real OS processes racing twelve nodes produce exactly one
holder each, zero orphans; a run outlives the process holding its lease; the
authority path is unchanged, re-proven, and the dispatcher cannot name a tenant
the sealed binding did not. The full GitHub connector regression — including a
real governed write — passes 81/81 against the rebuilt image.

**Three defects were found and fixed on this path, two of them introduced by
this phase's own fixes**, and none was reachable by deterministic testing (§8).
That is the phase's most transferable result.

**What is not done, and is not claimed.** The caller-facing half of the mandate:
no asynchronous API execution contract, no MCP integration, multi-replica proven
with real processes but **not deployed** (the chart is still `replicas: 1`), the
crash matrix cases B/C/D unexercised, the 18-case red team not run, and no
latency baseline. Exactly-once is not claimed anywhere.

**Therefore F-3 is closed as the limitation ADR-126 recorded** — "a governed
execution is dispatched only by the process holding the scheduler role, and that
process drives only executions it tracked itself" is no longer true — **but the
mandate's completion gate is not met**, and the remaining items in §26 are the
honest list of what stands between this and that.
