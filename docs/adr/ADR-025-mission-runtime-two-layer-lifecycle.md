# ADR-025 — Mission Runtime and the Two-Layer Mission Lifecycle

- **Status:** Accepted
- **Date:** 2026-08-06
- **Phase:** M1 (PR-M1) — first PR of Phase 2, the product runtime
- **Related:** ADR-002 (BC-1 ownership), ADR-010 (contract vocabulary), ADR-011 (canonical hashing), ADR-012 (domain events), ADR-017 (request context), ADR-018 (storage guard), ADR-020 (Engineering Runtime — the pattern this follows)
- **Implements:** Constitution S4 (mission lifecycle), BC-1, BC-9
- **Supersedes:** nothing. `backend/contracts/mission.py` is unchanged.

## Context

PR-M1 asked for a Mission Runtime with this lifecycle:

```
Draft → Planned → Ready → Running → Paused → Completed → Failed → Cancelled → Archived
```

`backend/contracts/mission.py` already publishes a *different* mission lifecycle,
encoding Constitution S4:

```
RECEIVED → INTERPRETED → GATHERING → REASONING → PLANNED →
AWAITING_DECISION → EXECUTING → VERIFYING → COMPENSATING → CONCLUDED
                              (+ BLOCKED, ABANDONED, FAILED)
```

Only `planned` and `failed` appear in both, and they mean different things in
each. More seriously, S4 enforces a rule the requested machine does not have:
**`EXECUTING` never reaches `CONCLUDED` directly — verification is mandatory.**
The requested `Running → Completed` is a direct edge.

Three options were possible: implement the requested machine and drop S4's rule;
implement S4 and not deliver the requested machine; or hold both. The third was
chosen deliberately, and this ADR records why.

## Decision

### Two lifecycles, owned by different layers

**`MissionStatus` — operational.** Owned by this context. Draft, planned, ready,
running, paused, completed, failed, cancelled, archived. It answers *is this
mission cleared to run, running, paused, or finished?*

**`contracts.mission.MissionState` — execution.** Owned by Constitution S4 and
already published. It answers *has this run been interpreted, gathered, reasoned,
executed, verified?* Mission Runtime records it and gates on it; Execution and
Verification advance it. **This ADR does not touch the published contract.**

They are genuinely different questions, and the clearest evidence is a continuous
mission. "Monitor Production Kubernetes Cluster" is `RUNNING` for months while
its execution state cycles through gathering, reasoning and verifying many times
over. One machine would have to be either the operational one — losing mandatory
verification — or the cognitive one, which cannot express *paused*.

### The gate that makes two machines safer than one

`RUNNING → COMPLETED` is refused unless the execution state is `CONCLUDED`.
Since S4 already forbids `EXECUTING → CONCLUDED`, verification cannot be skipped
from either side. Without that gate the operational machine would let a mission
report success over work nobody checked, which is precisely the failure S4 exists
to prevent.

The gate is enforced at **four** independent points, because it is the one rule
whose failure produces confident wrong answers:

1. `Mission.transition` refuses the move.
2. `Mission.__post_init__` refuses the *state* — so a mission assembled from
   storage cannot hold an unverified completion either.
3. `MissionExecution.__post_init__` refuses a `SUCCEEDED` outcome at any state
   but `CONCLUDED`.
4. `MissionCompleted.__post_init__` refuses to construct the event.

Policy rule `P5` reports it alongside every other reason rather than raising
first, so an operator sees the whole picture in one refusal.

### Mission Runtime performs no work, and that is checked

Every heavy noun is a *reference*: `PlanRef` holds a plan id, never a plan;
`MissionCheckpoint` holds a `payload_ref`, never a payload; `MissionExecution`
holds an `executor_ref`, never an executor.

`test_mission_runtime_performs_no_work` asserts the import graph contains no path
to `backend.execution`, `backend.orchestrator`, `backend.llm`, `backend.agents`,
`backend.connectors`, `backend.knowledge`, `backend.services`, or
`backend.database`. A runtime that *could* reach an executor would stop being an
orchestrator the first time someone found it convenient.

The cost is real and worth stating: Mission Runtime cannot tell you what a
checkpoint contains, only that it exists and that its record is intact.

### The timeline is the spine, not a log beside it

Every movement lands on an append-only, gapless timeline carrying its reason
(Constitution S4: *no state is exited without recording why*) and its actor.

The status is stored **and** derived by replaying the timeline, and
`timeline_agrees()` asserts they match. A mission whose history disagrees with
its state is therefore a test failure rather than a support ticket. A gap would
make replay unable to distinguish a lost entry from one that never existed, so
sequences are refused unless contiguous.

### Resuming restores the state the checkpoint captured

A checkpoint records the execution state it was taken at, and resuming opens a
new attempt *at that state*. Found during implementation: without it, resuming
opened a run at `RECEIVED` while the mission still reported `executing`, which
made checkpoints decorative and left the aggregate disagreeing with itself.

Resuming with no checkpoint restarts the run at `RECEIVED` — honest rather than
convenient, and visible in the timeline.

This state change is recorded on the timeline as an execution entry but is
**not** checked against the S4 table: S4 governs movement *within* a run, and
this is a new run beginning at a recorded position. Checking it would refuse
every legitimate resumption.

### One open execution at a time

Two concurrent runs of one objective produce two answers and nothing in the model
says which one the mission means. Pausing closes the run as `SUSPENDED`; resuming
opens a new attempt that records which checkpoint it came from — which is what
makes attempts countable and comparable.

### A mission that never ran cannot fail

`FAILED` is reachable only from `RUNNING` and `PAUSED`. A mission called off
before it ran was *cancelled*; recording it as a failure would corrupt every
failure-rate figure computed from this lifecycle. Cancellation is reachable from
every pre-outcome state, because a lifecycle that forced a mission to run in
order to stop it would be worse than one that permits calling it off.

### Acting missions need explicit authorisation

`REMEDIATE` and `OPTIMIZE` change live systems; the rest observe. Policy `P4`
refuses `READY` for an acting mission that has not declared and satisfied an
`authorisation.to-act` precondition. The cost of a wrong observation is a wrong
answer; the cost of a wrong action is an outage.

### Archival seals the record

The digest covers the whole timeline, and `ARCHIVED` is the only terminal status
— an outcome is not the end. Restored on load, never recomputed: recomputing
would make verification always pass.

## Alternatives Considered

**Replace `contracts/mission.py` with the requested machine.** Rejected: it edits
a published contract, requires superseding ADR-002/ADR-010's mission vocabulary,
breaks existing users, and drops mandatory verification. The last one alone is
disqualifying — it is the rule that stops CortexPrime reporting confident,
unverified answers.

**Implement only S4 and skip the requested states.** Rejected: `Draft`, `Ready`,
`Paused` and `Archived` are real operational needs with no S4 equivalent, and a
runtime that cannot express *paused* cannot run a long-lived mission.

**Map the requested states onto S4 as aliases.** Rejected: `Running` would have
to alias `EXECUTING`, making `Running → Completed` alias `EXECUTING → CONCLUDED`
— reintroducing the exact edge S4 forbids, but hidden behind a rename.

**Duplicate the S4 transition table inside this context.** Rejected: a second
copy would drift with nothing catching the drift. The contract is *used*, and its
refusal is re-raised with the mission named.

**One execution per mission.** Rejected: a continuous mission would need either a
new mission per cycle (losing the objective's history) or one S4 pass stretched
across months (making "verified" meaningless).

**Store the checkpoint payload here.** Rejected: it would make Mission Runtime a
knowledge store, and the boundary would be gone before anyone noticed it moved.

## Consequences

- `backend/contexts/` holds seven packages; `mission` is the first of the
  Constitution's nine product contexts to be built. None imports another.
- The published mission contract is now *enforced* rather than only defined —
  `MissionExecution.advance` routes every S4 move through `MissionTransition`.
- V1's mission code (`backend/services/mission_runtime.py`,
  `backend/mission*/`, `/api/enterprise/missions`) is untouched and coexists.
  The V2 runtime is mounted at `/api/v1/missions`; sharing a prefix would make
  which implementation answered a request depend on registration order.
- Every enterprise capability that wants governed execution now has a lifecycle
  to hang off, and no way to skip verification while doing so.

## Remaining Risks

1. **Nothing advances the execution state on its own.** The Execution and
   Verification contexts do not exist, so `advance_execution` is driven by
   whatever calls the API. Today a caller could walk a mission through
   `EXECUTING → VERIFYING → CONCLUDED` without anything having been verified —
   the *transitions* are enforced, the *work behind them* is not. The gate
   guarantees the sequence was walked, not that a verifier ran. Closing this
   needs BC-4 Verification, which is a later PR.

2. **`MissionStatus` and `MissionState` can be confused at a glance.** They are
   different types with two overlapping value strings (`planned`, `failed`).
   `test_the_operational_and_execution_vocabularies_are_distinct` pins the
   overlap so it cannot silently grow, but a reader skimming a payload still has
   to know which field they are looking at.

3. **Storage is in-memory.** `STATE-NO-NEW-FILE-STORES` forbids a new
   JSON-backed store and PostgreSQL is out of scope. Restarting loses every
   mission — including long-running ones, which is the kind this context exists
   for. The Protocol is the seam, and this is the most operationally significant
   gap in the PR.

4. **`files`/payload references are opaque and nothing resolves them.** A
   checkpoint can name a payload that no longer exists, and Mission Runtime
   cannot tell. Resuming would then restore a position whose data is gone.

5. **The API instantiates one module-level service.** Same shape as every other
   route module in this codebase; it shares process state across requests and is
   replaced wholesale in tests.

6. **The structured refusal bodies do not survive the running app.** Identical
   and pre-existing: `backend/core/exception_handlers.py` discards `exc.detail`.
   The status codes survive, and `GET /policy` is unaffected because it reports
   in a `200` body — which is where the detail matters most. Recorded rather than
   papered over, as in ADR-023 and ADR-024.

7. **Two mission implementations now exist.** V1's and this one. Until the
   strangler migration retires V1, "the mission runtime" is ambiguous in
   conversation even though it is unambiguous in code.
