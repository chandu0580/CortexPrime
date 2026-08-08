# ADR-020 — Engineering Runtime

- **Status:** Accepted
- **Date:** 2026-08-05
- **Phase:** E1 (PR-E2)
- **Related:** ADR-012 (events), ADR-016 (fitness functions), ADR-017 (request context), ADR-019 (WorkOrder runtime)
- **Implements:** Engineering Constitution v1.0 §3, §4, §9

## Context

PR-E1 built the WorkOrder as a bounded context: an aggregate that refuses illegal
transitions and binds approval to a digest. What it does not do is *drive* a
WorkOrder — decide when to move it, ask a reviewer to look, or record that a
phase boundary was crossed.

That is orchestration, and it needs collaborators the WorkOrder context must not
know about.

## Decision

### The runtime depends on ports, not on contexts

An orchestrator that imports the contexts it orchestrates couples them
permanently, and the coupling looks harmless at every individual call site. That
is the erosion Constitution S2 exists to prevent.

`BND-CONTEXT-ISOLATION` would not catch it — the rule iterates the nine product
contexts, and neither `workorder` nor `engineering` is one. ADR-019 recorded that
gap. This package is the first thing that could have widened it and does not.

So `backend/contexts/engineering/ports.py` defines four Protocols — `WorkOrderPort`,
`ReviewPort`, `VerificationPort`, `ContextPort` — and the runtime imports no
bounded context at all. Three tests assert this, including one that pins the
adapter to a single file.

The immediate payoff is not theoretical: **three of the four collaborators do not
exist.** Ports let the runtime be built, tested and reasoned about against
collaborators that are still hypothetical.

### Adapters live at the composition root

Something must join port to service. Putting the adapter inside the runtime makes
the runtime import the WorkOrder context; putting it inside the WorkOrder context
reverses the coupling and is no better.

Layer 3 may import layer 2, so `backend/api/engineering_composition.py` is the one
place where the join is both legal and correct — composition is what a composition
root is for. Keeping it in one small named module rather than scattered through
route handlers means the coupling is greppable:
`test_only_the_composition_root_imports_both` asserts exactly one file in the
repository imports both.

### The runtime keeps its own copy of the lifecycle

A port exchanging `WorkOrderState` would import the WorkOrder context.
`WorkOrderPhase` is the runtime's own vocabulary, with values identical to the
WorkOrder context's state strings.

Duplication is a real risk, so it is converted into a checked invariant:
`test_phase_vocabulary_matches_the_workorder_context` and
`test_transition_table_matches_the_workorder_context` compare the two copies
edge by edge. That is the one place importing the other context is correct,
because comparing them *is* the test.

Holding the table locally also lets the executor refuse an illegal move **before**
calling any collaborator. An orchestrator that discovers a move is illegal by
attempting it has already started it.

### Six new events, not eleven

The brief names eleven. Five already exist in the WorkOrder context:

| Requested | Already emitted |
|---|---|
| `WorkOrderCreated` | `engineering.work_order.drafted` |
| `WorkOrderAssigned` | `engineering.work_order.assigned` |
| `WorkOrderRejected` | `engineering.work_order.rejected` |
| `WorkOrderMerged` | `engineering.work_order.merged` |
| `WorkOrderSuperseded` | `engineering.work_order.superseded` |

Defining a second event for a fact that already has one is the mistake that looks
like completeness. Two event types meaning the same thing force every consumer to
subscribe to both and handle the case where only one arrives; the day they
disagree, nobody can say which is authoritative.

The mapping is exported as `WORK_ORDER_EVENT_ALIASES` so a consumer can resolve a
requested name to the real one rather than discovering it in a docstring.

The six genuinely new events mark orchestration facts no aggregate can know:
`ImplementationStarted`, `ImplementationCompleted`, `ReviewRequested`,
`ReviewCompleted`, `VerificationRequested`, `VerificationCompleted`.

### Events are recorded in the transaction and delivered outside it

The outbox pattern, and it is what makes "state changed" and "events emitted"
unable to disagree.

Persist-then-dispatch loses events when a subscriber raises.
Dispatch-then-persist emits events describing something that never happened. So
events are **recorded** inside the lock, in the same critical section as the state
change, and **delivered** afterwards from the log.

A subscriber that raises produces a `DeliveryFailure` and delays delivery; it
cannot lose an event, because the event is already durable. The cursor advances
past a failure deliberately — holding it back would redeliver every subsequent
event to every healthy subscriber to retry one broken pair, turning a single bad
handler into a storm.

Replay falls out for free: it is a delivery pass from sequence zero, and
`test_a_projection_rebuilt_by_replay_equals_the_live_one` asserts the two agree.

### Rollback covers from "collaborator asked" to "events recorded"

Steps that change nothing come first, so a refusal needs no rollback. The
protected window opens when a collaborator is told to start.

**Event construction is inside the protected region, not merely the append.** This
was a real bug caught by a test: an event whose invariants refuse construction —
a review request naming no lens — would otherwise have left the phase changed with
nothing recorded, which is exactly the disagreement the outbox exists to prevent.

### Concurrency: a lock *and* a precondition

A per-WorkOrder reentrant lock serialises read-modify-write. An optional
`expected_phase` gives optimistic concurrency for a caller that read the snapshot
before acquiring anything.

Both, because the lock alone does not help a caller working from a stale read. The
precondition is checked **before** legality: a stale caller's move may be perfectly
legal from the phase it believed the WorkOrder was in, and the useful answer is
"it moved", not "that is illegal".

### The architecture gate does not run on every transition

The requirement as literally stated is not implementable. The gate parses 782
modules and takes **eight minutes**; running it on each of the eight transitions a
WorkOrder makes would add over an hour per WorkOrder, and a gate nobody can afford
to run is a gate that gets switched off.

What runs instead:

* **Cheap constitutional checks on every transition** — the digest still binds,
  the WorkOrder is not superseded, assumptions are resolved before review. These
  are the rules a *transition* can actually violate.
* **`constraints-enforceable` at `VERIFICATION → READY`** — every cited constraint
  still resolves to a live rule. A constraint whose rule was deleted since
  approval is prose, and prose does not block a merge.
* **The full gate, opt-in, at the same transition.** Architecture cannot drift
  during a state change; it drifts when code changes, and the only transition
  after code changes is this one.

`default_policy(run_architecture_gate=True)` turns it on. It is a registered
policy like any other, so moving it is a one-line change.

### A phase whose collaborator is missing is refused

Not skipped. A phase that requires review and proceeds because nothing was
listening is worse than one that stops: the first produces an unreviewed merge
that *looks* reviewed, and no later inspection can tell the difference.

Consequence: a WorkOrder currently cannot be driven past `assigned`. That is the
honest state of the system, reported by `GET /capability` and asserted by
`test_review_is_unreachable_because_no_review_context_exists`.

## Alternatives Considered

**Import the WorkOrder context directly.** Far shorter — no ports, no adapter, no
composition root. Rejected: it permanently couples the orchestrator to one
context, and `BND-CONTEXT-ISOLATION` would not have caught it. A gap in
enforcement is not a licence.

**Put the adapter inside the engineering context, isolated to one module.**
Pragmatic and reviewable. Rejected because it still means the runtime imports
another context, and "isolated to one module" is a convention that erodes.

**A shared `EngineeringPhase` in `backend/contracts/`.** Would remove the
duplication properly. Rejected for this PR: moving the state vocabulary out of the
WorkOrder context is a change to PR-E1's frozen surface, and the drift test buys
the same safety without it. Worth revisiting when a third context needs the
vocabulary.

**Publish events synchronously inside the transition.** Simplest. Rejected: it
makes a subscriber able to fail a transition, which means an unrelated consumer's
bug can block engineering work.

**Let the runtime own review and verification directly.** Rejected — the brief
forbids it, and correctly. Those are separate stances with their own artifacts.

## Consequences

- The Engineering Constitution's lifecycle is executable end to end, with each
  forbidden transition refused by its own argument.
- The runtime is testable against collaborators that do not exist, which is the
  only way it could have been built at all.
- `backend/contexts/` now holds two packages that share nothing but a checked
  vocabulary.
- Rollback and replay are solved by one mechanism rather than two.
- Three of four ports are unwired, so the runtime is currently a gate that mostly
  says no. That is correct and temporary.

## Remaining Risks

1. **Storage is in-memory, including the event log.** Restarting loses the log,
   and with it every round and attempt number — which are derived from it. A
   durable log is the first thing PR-E3 should need.

2. **Rejection is unreachable from `Approved`, `Assigned` and `Blocked`.** The
   Constitution's table permits it from Draft, SpecTests, Implementation, Review
   and Verification only. A WorkOrder blocked on a dependency that was itself
   rejected is stranded with no exit. This has now surfaced three times — in
   PR-E1's tests, PR-E2's tests, and here. It is a gap in the frozen
   specification and needs an amendment, not a patch.

3. **`_attempt_reverse` is best-effort and usually cannot succeed.** The machine
   has few backward edges by design, so reversing a transition after a failed log
   append is normally itself illegal. When that happens the state and the log
   disagree, and the raised `TransitionRolledBack` is the only thing that says so.
   A durable log with a two-phase commit would close this; an in-memory one
   cannot.

4. **The lock table grows without bound.** One `RLock` per `work_id`, never
   evicted. Harmless at current scale and a leak at any real one.

5. **`ReviewCompleted.passed` is `False` when no lens reported.** Correct — a
   missing lens is not a passing lens — but it means a review context returning an
   empty outcome list silently produces a failing-looking review rather than an
   error. The distinction should be explicit once a real Review context exists.

6. **The composition root builds one runtime at import time.** Fine for a single
   process, wrong for anything else, and the execution context is manufactured
   per request rather than propagated from the authenticated caller.
