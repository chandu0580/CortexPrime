# ADR-029 — Execution Runtime as a bounded context

**Status:** Accepted
**Date:** 2026-08-08
**Phase:** 2 — Mission Runtime
**PR:** PR-M5
**Supersedes:** nothing
**Related:** ADR-025 (Mission Runtime), ADR-027 (Planner), ADR-028 (Workflow Runtime),
ADR-018 (storage boundary and tenant guard), ADR-016 (architecture fitness functions)

---

## Context

Workflow Runtime (ADR-028) produces a compiled, approved graph and then stops —
deliberately, because "what should happen" and "what did happen" are different
questions and the second one is the only one that can hurt production.

Nothing in the platform answered the second question. There was no owner for
runtime state, no record of which worker held which node, no way to say a node's
outcome was *unknown* rather than failed, and no artifact that could later be
shown to somebody asking what actually ran.

`execution` is one of the Constitution's nine bounded contexts, so unlike the
last four contexts this one is actively policed by `BND-CONTEXT-ISOLATION`
rather than by its own compliance tests alone.

## Decision

Build `backend/contexts/execution/` as the runtime owner: it executes a compiled
workflow graph, owns node state, leases work to workers, checkpoints, resumes,
retries, cancels, and seals a digest-bound record of the outcome.

### Execution never plans

No estimation, no risk levels, no critical path, no graph compilation. The node
set arrives as a projection of an already-approved workflow, carrying the
`workflow_digest` that binds the run to the exact graph it executes. A run that
cannot name its graph is a run of whatever somebody later decides it was running,
so the digest is mandatory. A compliance test greps the whole context for
planning vocabulary.

### Workers are interfaces only

`ExecutionWorker` is a `Protocol`. There is no shell, Docker, Kubernetes,
Terraform, or browser implementation in this PR, and a test asserts the context
contains no `subprocess.`, `docker.`, `kubernetes.`, or `playwright` reference.
Putting an executor inside the context that decides what may execute is how the
decision and the action stop being separable.

The service never calls a worker. `ready_nodes` says what *could* be dispatched;
`assign` leases one node to one worker; the caller runs it and reports back.

### There is no dispatch loop

No `run()` that drives a workflow to completion. Deciding how fast to go, how
many workers to use, and when to stop is a deployment decision, and a service
that owned the loop would own the concurrency policy with it.

### Two state machines, not one

`ExecutionState` (pending → running → paused → completed/failed/cancelled/
timed_out) governs the run. `NodeState` governs each node. They are separate
because a run can be healthy while a node is not, and collapsing them would force
a failed node to mean a failed run.

### UNKNOWN is a first-class node outcome

`NodeState.UNKNOWN` is terminal but **not finished**. It is what a node becomes
when its lease lapses with no result: the attempt is over, but nobody may treat
its outcome as settled. This is the single most important decision in the
context. A runtime that calls a lapsed lease "failed" will retry a destructive
action that already succeeded.

An unknown node blocks completion (policy X2) until somebody resolves it
deliberately — retry it, skip it with a reason, or compensate it.

The published `ExecutionStatus` contract has no word for "we do not know", so
`published_status_of` degrades `UNKNOWN` to `FAILED`. That is a real loss of
information in the safe direction, and it is pinned by a test so it is never
mistaken for an accident.

### Leases, not assignments

A node is *leased* to a worker for a bounded time. Every result is checked
against the lease: wrong worker → `LeaseNotHeld`; expired lease → `LeaseExpired`;
nobody holds it → `NodeNotRunning`. A live lease cannot be reclaimed out from
under a worker that is still entitled to it.

The check lives in the aggregate, not the service. A guard in the service is a
guard a second caller can go around, and the worker pool is the only mutable
shared resource in the product layer.

### Retry is refused when it would be ambiguous

`NodeSpec.assert_retryable_after` raises `AmbiguousRetry` when a mutating,
non-idempotent node is retried after an `UNKNOWN` outcome. Re-running a
`destructive` action that may already have run is the failure mode this whole
context exists to prevent (Constitution P2 — reversibility precedes action).

### Readiness is derived, never signalled

`ready_nodes()` is computed from the graph: a node becomes ready when all its
dependencies are satisfied. Only `SUCCEEDED` and a deliberate `SKIPPED` satisfy a
dependent — a failure does not. Asking each finishing node to work out who to
wake is how one of them gets it wrong.

### The policy reports every failure at once

X0 (run open, move legal), X1 (all nodes finished), X2 (ambiguity resolved),
X3 (cancellation declares what it changed), X4 (no node blocked forever),
X5 (stale leases), X6 (stateful work that went unknown), X7 (resumability).
X3 and X5–X7 are advisory: they inform without refusing, because refusing a pause
because a lease is stale leaves the operator no move at all.

**"Already finished" is not a policy question.** A terminal run is guarded before
the policy runs, so a caller who lost a race gets `409 Conflict` rather than
`422 Unprocessable` — the same distinction ADR-024 needed for closed reviews.

### The digest is restored, never recomputed

Loading a stored run restores the recorded digest rather than recomputing it.
Recomputing would make the check always pass — a check that cannot fail — and
this record is the account of what happened to production, so this is the place
that check matters most in the codebase.

Every invariant is re-checked on load, including completion. A stored run edited
to claim completion with an outstanding node refuses to load.

### The queue is infrastructure

`ready_nodes()` is the domain answer to *what could run*. A queue is the
operational answer to *what should a worker pick up next* — which depends on pool
size and fairness, things the domain has no view of. The in-memory queue **claims
rather than deletes**: a worker that dies between claiming and leasing leaves an
item that returns to the queue rather than one that vanished. Same reasoning as
the lease itself, one level up.

## Consequences

**Good.** The runtime can be interrupted and resumed without losing track of what
already happened. Ambiguity is representable, so it can be handled instead of
guessed at. No executor code exists inside the context that authorises execution.
The outcome record is tamper-evident.

**Costs.** The worker pool is in-memory and per-process; a durable pool needs the
storage story the repository has, and inventing a second one here would be worse
than admitting there is one. There is no dispatcher, so a caller must drive the
loop. `UNKNOWN` flattens to `FAILED` at the published boundary.

**Deferred.** Real worker implementations, a durable queue, heartbeat-driven
lease renewal, and the Mission Runtime ↔ Execution wiring that turns an approved
plan into a started run.

## Compliance

- **S2** — imports only `backend.contracts` and `backend.platform`; test-enforced.
- **S4** — no state is exited without recording why; every terminal state carries
  an outcome note; compensation is a first-class path, not an error branch.
- **P2** — reversibility precedes action: retry is refused where it would be
  ambiguous, and mutating nodes are tracked separately.
- **P9** — the run declares what it changed, and cancellation says so out loud.
- **BC-9 / ADR-017** — every repository method takes an `ExecutionContext`;
  a run saved under one tenant is invisible to another.
- **ADR-018** — the repository is `RepositoryGuard`-backed; no new file store.

The spec named the worker's execution context `ExecutionContext`. That name is
already taken by `backend.platform.context.ExecutionContext`, the tenancy and
identity context threaded through every repository in the codebase (ADR-017).
Different concept, same name. Shadowing it would be reckless, so the worker-facing
one is `RunContext`. A naming decision, not a semantic fork.
