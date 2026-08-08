# ADR-030 — The Workflow → Execution handoff

**Status:** Accepted
**Date:** 2026-08-08
**Phase:** 2 — Mission Control Plane (reconciliation)
**Supersedes:** nothing
**Related:** ADR-028 (Workflow Runtime), ADR-029 (Execution Runtime),
ADR-025 (Mission Runtime), ADR-017 (request context), ADR-016 (fitness functions)

---

## Context

Phase 2 built five bounded contexts — Mission, Intent, Planner, Workflow,
Execution — each correct in isolation and each, by Constitution S2, forbidden
from importing the others. Every downstream context therefore accepts its
upstream artifact's identity and digest as **plain strings**: `intent_id` +
`intent_digest` on a plan, `plan_id` + `plan_digest` on a workflow,
`workflow_id` + `workflow_digest` on a run.

That is the right shape for the contexts. It leaves one thing unbuilt: nothing
checked that those strings referred to anything real.

Concretely, before this ADR, `StartExecution` was only ever constructed by the
execution route from a caller-supplied `workflow_id`, a caller-supplied
`workflow_digest`, and a caller-supplied list of nodes. A run could be started:

- from a workflow that was never approved,
- from a workflow that does not exist,
- with a digest that binds the run to nothing,
- over a node set the caller invented rather than the graph that was approved.

The digest whose entire purpose is to bind a run to the exact graph it executes
was whatever the caller typed.

## Decision

Add a composition root — `backend/api/mission_control_composition.py` — as the
**only** module that imports both the Workflow and Execution contexts, following
the pattern already established by `engineering_composition.py`. A fitness test
asserts it stays the only one.

`WorkflowExecutionLauncher` is the only sanctioned way to turn a workflow into a
run. It:

1. **Loads the workflow** by id, or finds the mission's approved one via the
   existing `executable_for` query.
2. **Requires approval.** `WorkflowStatus.is_executable` is `APPROVED` and
   nothing else. This reuses the existing approval semantics; no new approval
   system was introduced.
3. **Verifies the digest** against the workflow's own canonical payload, so the
   artifact being run is the one that was approved rather than one edited since.
4. **Derives the node set** from the compiled graph. The caller does not get to
   say what the run contains — that is the whole point of binding it to a digest.
5. **Hands Execution the workflow's own digest**, never a caller-supplied string.

### Dependencies come from sequence edges only

An `on_failure` edge is a route taken when something went wrong, not a
dependency to wait on. Projecting one as a dependency would leave a node waiting
for a failure that a healthy run never produces.

### Compensation nodes are not projected

Execution requires every node it was given to finish before a run may complete.
A compensation node is reachable only when something failed, so projecting one
would leave every **successful** run permanently outstanding — unable to
complete and unable to fail. That is a stranded state, and it is the exact class
of defect this reconciliation pass was asked to find.

Execution walks back a change by calling `compensate` on the mutated node
itself. Dispatching the compensating *action* needs a worker, so it is deferred
with the rest of capability routing.

### Worker kind arrives through a port, and is never defaulted

Workflow describes *how* work should execute. It does not name a runtime
capability, and pushing `worker_kind` into `WorkflowNode` would move an
execution concern backwards into the planning plane (Phase 2 boundary rule).

So the worker kind comes from `WorkerKindResolver` — a Protocol, with no
implementation behind it beyond `ExplicitWorkerKinds`, which only knows what it
was told. A node with no resolved kind is **refused**, not defaulted. Defaulting
would hand real work to whatever happened to be first in an enum.

This is the seam where Phase 3's capability routing plugs in. When the capability
registry exists it implements this interface and nothing else in the module
changes.

### API semantics

`POST /api/v1/mission-control/executions` — `409` when the workflow is not
approved or the mission has none (a conflict about the state of the artifact,
not a malformed request); `400` when a node's worker kind was not resolved.

## Consequences

**Good.** Approval is now a precondition of running rather than a note on a
record. A run can name the exact graph it executed and prove it. The coupling
between the two contexts is one greppable file. Successful runs can actually
complete.

**Costs.** The caller must state worker kinds until Phase 3 exists. The launcher
reads the process-wide service instances the route modules hold, which is the
same in-memory persistence story the rest of Phase 2 has and no worse.

**Deferred to Phase 3.** Capability registry, worker fleet, tool routing,
connector fabric, compensation dispatch, and any real worker implementation.

## Compliance

- **S2** — neither context imports the other; test-enforced in both directions.
- **P2** — reversibility: compensation semantics are preserved at the workflow
  level and not silently dropped, only deliberately not projected.
- **P9** — the approved graph, not a caller's node list, decides blast radius.
- **ADR-017 / BC-9** — the `ExecutionContext` is threaded through both services;
  no tenant identity is manufactured at the seam.
- **ADR-016** — architecture gate passes with zero blocking violations.

## What this ADR does not claim

There is no automatic planning, no LLM-based intent extraction, no autonomous
execution, no root-cause analysis, and no connector execution anywhere in
Phase 2. The control plane decides *what* should happen and proves it was
approved. Performing it against a real system is Phase 3.
