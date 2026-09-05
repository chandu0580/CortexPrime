# ADR-091 — The first-write lifecycle, closed and independently verified

**Status:** Accepted
**Date:** 2026-09-05
**Extends:** ADR-088 (execution trust model), ADR-089 (CONTAINED worker), ADR-090 (approval binds to the action)
**Implementation map:** `docs/PHASE_9_10_IMPLEMENTATION_MAP.md`
**Verification:** `docs/PHASE_9_10_VERIFICATION_REPORT.md`

## Context

9.9C performed CortexPrime's first real irreversible write and explicitly
deferred four things: an Assurance verdict, replay of a *completed* execution,
autonomy re-evaluation, and fencing/crash coverage. This phase closes exactly
those.

## Decision 1 — Add no mechanism; every one already existed

Discovery found that all four deferrals were served by code already built:

| Deferral | Served by | Built new? |
|---|---|---|
| Assurance verdict | `AssuranceVerifier` already returns SUPPORTED / UNSUPPORTED / INSUFFICIENT_EVIDENCE and already refuses self-verification. `deployed_revision` already exists with a 3600s freshness horizon. | **No** |
| Replay of a completed execution | `ExecutionReplayer` — *"Holds no repository, no worker pool, and no queue — by construction, not by discipline. There is nothing here to call."* | **No** |
| Autonomy | `AutonomyPolicy.evaluate`, ten gates, unchanged since 9.6 | **No** |
| Fencing / crash | `ExecutionLease`, the existing queue claim, and the 9.6 child-process pattern | **No** |

**No production mechanism was added in this phase.** No provider, executor,
gateway, approval system, verifier, lease, election or predicate. The World Plane
was not redesigned. The only production change is a harness-adjacent
parameterization of an existing helper.

## Decision 2 — Assurance reuses the existing predicate

The restart advances the Deployment's revision, which is exactly what
`deployed_revision` already records — the predicate 9.5 declared and 9.6 seeded.
The verification procedure is `COMPARE_WORLD_STATE` over that predicate, with the
expected value taken from a **governed read of the cluster**, never from the
worker's response.

Verified: matching evidence → `SUPPORTED` (citing 2 observations); contradictory
→ `UNSUPPORTED`; missing, wrong-workload, stale and undeclared-predicate → not
SUPPORTED; and the verifier refuses when asked to verify its own reasoning path
(Constitution P5).

## Decision 3 — Measure Kubernetes mutations, not envelope POSTs

The negative matrix initially reported a failure that was a **measurement error,
not a safety failure**. A cross-namespace approval was granted that was genuinely
valid *for that action*, so authorization and the gateway correctly allowed it —
and the CONTAINED worker's own namespace binding refused it before contacting the
API server. The harness counted the envelope POST as a provider write.

They are not the same thing. A POST to the worker is not a mutation of
Kubernetes, and conflating them hides **which layer actually stopped an attack**.
The matrix now measures the cluster's own generation as ground truth and records
`stopped_by=governance` or `stopped_by=worker` for every refusal.

This is worth stating plainly: for the cross-namespace case, the last line of
defence is the one that held. That is the layered design working, and the report
says so rather than implying governance caught it.

## Decision 4 — Assert what the record establishes, not what was expected

Two harness assertions were written against assumptions rather than properties
and were corrected rather than forced green:

- The replay projection's `final_state` is `pending`, not `succeeded`. Asserting
  `succeeded` was an assumption about the execution-level event stream. What the
  replay genuinely establishes — 6/6 frames folded, zero causal gaps, zero
  provider writes, cluster generation unchanged — is what is now asserted.
- The projection reports `execution_id: unknown`, because the events returned by
  `executions.history` carry no `execution_id` in the payload the replayer reads.
  **Recorded as a deferred finding rather than asserted away.** It does not
  affect inertness, but a projection that cannot name its own execution is worth
  knowing about.

## Decision 5 — No new fitness rule

Part M says to add nothing unless an actual bypass is found. None was. The
invariants in question are enforced by Gate 1, Gate 2, the approval action-digest
comparison (ADR-090), `BND-DIRECT-HTTP`, `BND-PROCESS-SPAWN` and the
`ProviderAuthority` requirement. A rule restating them would be cosmetic.

## Consequences

The first-write lifecycle is closed end to end: approval → authorization →
autonomy → gateway → CONTAINED worker → real Kubernetes write → independent
observation → Fact → Assurance `SUPPORTED`, with replay inert, every
cross-binding negative refused at zero mutations, and no credential in durable
state.

**The 9.9C security baseline is intact.** The `approval_required` fix and its two
regression guards remain green, and the cross-workload and unbound approvals are
re-proven refused here against the real cluster.

### Honestly not closed

- **Exactly-once is not claimed.** At-least-once remains the contract: a *new*
  governed request for the same action is a new execution and writes again,
  correctly. What is proven is that replaying the *recorded* execution cannot.
- **Crash coverage is partial by design.** Four of the ten named boundaries sit
  after the irreversible act and prove record durability rather than write
  safety. What is proven is the property they exist to protect: an interrupted
  provider request is `UNKNOWN`, and a real killed process produced no fabricated
  success.
- **A live two-holder fencing race** was not staged. The lease, its refusal path
  and the queue claim are re-proven wired; the live race was proven in 9.3 and no
  lease, leadership or recovery code changed since.
- Process-count and egress limits remain `NOT VERIFIED` (ADR-089), unchanged.
