# ADR-028 — Workflow Bounded Context

- **Status:** Accepted
- **Date:** 2026-08-07
- **Phase:** M4 (PR-M4)
- **Related:** ADR-005 (BC-5 execution vocabulary), ADR-025 (Mission Runtime), ADR-026 (Intent), ADR-027 (Planner)
- **Implements:** Constitution S4 (compensation is a first-class path); P2 (reversibility precedes action)
- **Supersedes:** nothing. `contracts/mission.py` and `contracts/execution.py` are unchanged.

## Context

Planner produces a DAG of *data dependencies*: resize waits for audit because it
needs what audit found. That answers **what** and **in what order it must
happen**.

It does not answer **when, under what conditions, and what happens when it goes
wrong**. Branches on outcomes, fan-outs with concurrency limits, retries with
backoff, compensations, timeouts, cancellation, resume — none of that is a fact
about the work, and all of it has to be decided before an executor can run
anything.

## Decision

### Two DAGs, and they are not the same DAG

A plan dependency is a *fact about the work*. A workflow edge is a *decision
about orchestration*. Keeping them separate is what lets orchestration be revised
— parallelised, retried differently, given a new deadline — without reopening the
plan, and what stops a planner deciding concurrency limits it has no basis for.

### Four gates, because compilation is not validation

`DRAFT → VALIDATED → COMPILED → APPROVED`.

`VALIDATED` says the graph is well-formed. `COMPILED` freezes what is *derived*
from it — execution order, compensation order — and binds the digest. `APPROVED`
says somebody accepted it.

Separating the middle two earns its keep: **recomputing an execution order at run
time lets two executors disagree about a graph both consider valid.** Freezing it
means they cannot. The derived orders are deliberately *not* governed by the
digest — they are recomputable from what is, so hashing them would be redundant.

### Seven checks need the whole graph

1. **Acyclic.** There is no loop construct, deliberately. A cycle never
   completes, so an executor spins or waits forever.
2. **Connected.** *Not* reachability from entry points — that check passes on
   exactly the mistake it should catch, because an unwired node has no
   predecessors and therefore looks like a legitimate entry point. Weak
   connectivity is the honest test, and it catches the orphan and the
   disconnected cluster.
3. **Every plan task covered, and no node invents work.** Orchestration may
   reorder what was approved; it may not add to it or drop it.
4. **Every condition reads an upstream node.** Branching on an outcome that does
   not exist yet is a null the executor must invent a meaning for.
5. **Parallel members are genuinely independent**, checked against the graph's
   transitive closure. Declaring independence does not create it; if one member
   waits for another, concurrency is a deadlock or a race.
6. **Compensations target real, mutating nodes.**
7. **The deadline is meetable.** The workflow's timeout must not be shorter than
   its longest *forward* path, including retry waits. A deadline nothing can meet
   always fires and always looks like a slow dependency.

Failure and compensating edges are traversed for 1 and 2 — a cycle through a
failure path is still a cycle — and excluded from 7, because budgeting the
deadline for the failure path would make every workflow's timeout absurd.

### Constitution P2 gets a retry corollary

`ExecutionContract` enforces reversibility for an action. Planner enforces it for
a task. This context adds the case neither covers:

**A node that mutates and is not idempotent may not be retried.** A retry after
an *ambiguous* failure — a timeout, a dropped connection — cannot know whether the
first attempt applied. Retrying anyway is how a thing happens twice, and the
second time is the one nobody planned. Reads are exempt.

Two related rules follow the same logic: a retry with no backoff and no delay is
refused (against a system failing because it is overloaded, immediate re-attempt
is the worst possible response), and an un-waited-for member of an `ANY` or
`QUORUM` group may not mutate (it can still be applying changes after the
workflow moved on, so the record of what happened is wrong).

### Branches require an explicit default

Arbitrary conditions cannot be proved exhaustive, so exhaustiveness is not
inferred — it is required as a declared catch-all arm. Without one, an input
matching no arm leaves the workflow with nowhere to go and *no error to report*,
which is the failure mode that looks like slowness.

### A compensation needs no compensation

Excluded from the "every mutation is walked back" rule, and the exclusion is the
point rather than an oversight: a compensation *is* the walk-back. Demanding one
for it is infinite regress, and the honest answer to "what if the walk-back
fails" is an operator, not another node.

**Found by running the policy, not by review** — the first end-to-end run refused
a perfectly good workflow for exactly this.

### Compensation order is derived, never declared

Reverse execution order. Walking back in the order things were done would undo
the earliest change first while later ones still depend on it. Reverse is the
only correct order, so it is computed — a declared one can be wrong.

## Alternatives Considered

**Extend Planner's graph instead of a second context.** Rejected: it would make
Planner decide concurrency limits and retry policies, which are properties of the
executor and the environment rather than of the work.

**Reachability from entry points for check 2.** Rejected after it silently passed
on an orphan node — see above. This is the second graph algorithm in two PRs
where the obvious formulation was wrong in the case that mattered.

**Support loops.** Rejected: a loop in an orchestration graph is not iteration,
it is a path that may never complete. Repetition belongs in a node's retry
policy, which is bounded by construction.

**Let the executor compute the order.** Rejected above.

**Infer branch exhaustiveness.** Rejected: it requires evaluating conditions this
context deliberately cannot evaluate.

**Store the graph rather than rebuild it.** Rejected, as in ADR-027: rebuilding
on every construction means a stored workflow edited into a cycle refuses to
*load* rather than stalling an executor later.

## Consequences

- `backend/contexts/` holds ten packages. None imports another.
- Constitution P2 is now enforced at six independent points across three
  contexts: `ExecutionContract`, `PlanTask`, `Plan`, `PlanApproved`,
  `WorkflowNode` (retry corollary), and `WorkflowApproved`.
- Execution, when it exists, reads `WorkflowService.executable_for(mission_id)`
  and nothing else from here.
- The chain `Intent → Plan → Workflow` is now digest-bound end to end: each
  artifact carries its predecessor's digest as a governed field.

## Remaining Risks

1. **Nothing compiles a workflow from a plan automatically.** The context
   provides the target structure and every rule; the compilation is done by
   whoever calls the API. Same deliberate choice as PR-M2 and PR-M3 — and here
   the honest note is that `plan_task_ids` is *supplied by the caller*, so a
   caller that passes an incomplete list gets a coverage check that passes
   vacuously. The composition-root reconciler that would read the real plan is
   not built.

2. **Timeouts are declared, not measured.** The critical-path budget uses the
   declared per-node timeouts. If those are optimistic, the workflow's deadline
   is optimistic in exactly the same proportion, and nothing here knows better.

3. **Conditions are opaque beyond their source node.** `on_output` carries an
   expression this context does not parse or evaluate. It can prove the *source*
   is upstream — worth proving — and nothing about whether the expression is
   satisfiable, well-typed, or refers to fields that exist.

4. **Cancellation is declared, not implemented.** `cancellable` and the timeout
   responses say what *should* happen; whether an executor can actually interrupt
   a node mid-write is a property of the connector, which this context must not
   reach.

5. **Resume points are structural, not semantic.** The rule is that a resume
   point may not sit inside a fan-out. It cannot check that the state at that
   point is genuinely restorable — that needs to know what the nodes did.

6. **`SPOF_RATIO` and `LONG_WORKFLOW_NODES` are judgements**, named as constants
   so they can be argued with rather than buried in conditionals.

7. **Storage is in-memory.** `STATE-NO-NEW-FILE-STORES` forbids a new JSON-backed
   store. Restarting loses every workflow, including approved ones.

8. **The structured refusal bodies do not survive the running app.** Identical
   and pre-existing: `backend/core/exception_handlers.py` discards `exc.detail`,
   so the cycle path and the unmeetable-deadline numbers a client would need are
   replaced by a canned message. `GET /policy` and `GET /graph` are unaffected
   because they report in `200` bodies.
