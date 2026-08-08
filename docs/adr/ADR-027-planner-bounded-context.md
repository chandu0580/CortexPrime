# ADR-027 — Planner Bounded Context

- **Status:** Accepted
- **Date:** 2026-08-07
- **Phase:** M3 (PR-M3)
- **Related:** ADR-002 (BC-1), ADR-005 (BC-5 execution vocabulary), ADR-010 (contract vocabulary), ADR-023 (checked duplication), ADR-025 (Mission Runtime), ADR-026 (Intent)
- **Implements:** Constitution S4 (task graph, cycles); P2 (reversibility precedes action); P9 (blast radius declared)
- **Supersedes:** nothing. `contracts/mission.py` and `contracts/execution.py` are unchanged.

## Context

Mission Runtime owns *when* work happens. Intent owns *what* is wanted. Neither
knows *how*. A plan is the missing term, and it is the artifact execution acts
on — which makes it the last place an under-specified mandate can be caught
cheaply.

Two published contracts already carried most of the vocabulary, and one of them
contained an explicit instruction for this PR.

## Decision

### The cycle check lives here because the contract said so

`TaskRef` in `contracts/mission.py` enforces what it can locally and delegates
the rest in as many words:

> Cycles are forbidden by Constitution S4; detecting them requires the whole
> graph, so that check belongs to BC-1. What is enforced here is local: a task
> cannot depend on itself.

This context holds the whole graph, so `DependencyGraph` implements the check —
and reuses `TaskRef`/`TaskState` rather than inventing a second task vocabulary.
That reuse is what makes the delegation coherent rather than coincidental.

**A cycle stalls rather than fails**, which is why it is refused at construction.
No task inside one can ever become ready, so an executor waits forever, and
stalling is worse than failing because it looks like slowness — somebody notices
hours after a failure would have paged them.

The refusal names the cycle path (`a -> b -> c -> a`), not just its existence.
In a ninety-task plan that difference is the entire value of the check. Detection
is iterative rather than recursive: a plan is allowed to be deep, and a recursion
limit is a silly reason to refuse a legitimate one. A 3000-deep chain is tested.

### Constitution P2 is enforced at both levels

`contracts/execution.py` already enforces *reversibility precedes action* for a
fully-specified action: `ExecutionContract` refuses to construct a
`REVERSIBLE_WRITE` with no inverse.

This context applies the same rule one stage earlier, where the answer is
cheapest to change:

- **Task level** — a task whose `SideEffectClass` mutates must declare a reversal
  *or* name who accepted that it cannot be reversed. "There is no way back" is a
  decision somebody makes, not a property something has.
- **Plan level** — a plan containing mutating tasks cannot claim
  `NONE_REQUIRED` rollback.
- **Event level** — `PlanApproved` refuses to construct with mutating tasks and
  no rollback.

A read-only plan declares no rollback, deliberately. Demanding an elaborate one
for a plan that changes nothing trains people to write a rollback strategy that
says nothing, and one nobody means is worse than none — it reads as though
somebody thought about it.

### Risk has a floor computed from the plan's own tasks

The declared level is refused below what the tasks imply:

| plan contains | floor |
|---|---|
| any `DESTRUCTIVE` task | `SEVERE` |
| any `IRREVERSIBLE_WRITE` task | `ELEVATED` |
| any mutation with no declared way back | `ELEVATED` |
| reversible changes only | `MODERATE` |
| nothing that mutates | `LOW` |

So talking the risk down requires also understating what the tasks *do*, which is
a different and much more visible lie. Risk that can be argued down without
changing anything else is a mood, not an assessment.

**The floor is never a ceiling.** A plan of pure reads may be declared `SEVERE` —
reading the wrong production database at the wrong moment is a real risk, and
nothing here knows enough to argue.

### Four checks need the whole plan

Value objects enforce what is locally visible. These need everything:

1. **The graph is acyclic and complete** (above).
2. **Every task serves a goal.** Work tracing to nothing asked for still spends
   the blast radius and the time.
3. **Every success criterion is covered by a goal.** Otherwise the plan can
   complete every task and still not achieve what was asked for — the failure a
   plan exists to make impossible.
4. **The declared risk is not below the floor.**

Goals are the middle term that makes 2 and 3 answerable at all: criteria come
from Intent, goals decompose them, tasks hang off goals.

### Bound to the mandate, by digest

A plan carries `intent_id` **and** the intent's approval digest, and the digest is
governed. A plan built against a revised mandate cannot verify against the old
one. Same binding Review uses for the implementation it reads (ADR-024).

Criteria are *references*, not copies: `SuccessCriterionRef` holds the intent's
criterion id plus a restatement. The id exists because paraphrases drift; the
restatement exists because a plan has to be readable on its own. Nothing resolves
the id — S2 forbids importing Intent, and a resolver answering "yes, that exists"
would make the reference unfalsifiable.

### Revision creates a version; it never reopens

An approved plan is what execution acts on. Reopening it would mean work was
authorised against something nobody approved. `revise()` opens version *n+1*
carrying the content forward and naming what it supersedes, and the original is
superseded — so both stay on record, which is also what makes "what changed
between v2 and v3" answerable.

Editing a *validated* plan returns it to `DRAFT`, for the reason ADR-026 gives:
`VALIDATED` describes a particular graph, and adding a task makes it a statement
about a graph that no longer exists.

### Task ids are readable strings, not ULIDs

Dependencies name tasks by id. A graph reading `01KZD7… depends on 01KZD8…` is
unreadable by the person approving it. `TaskRef` takes a plain string for the same
reason. Uniqueness is enforced by the plan, which is where the whole set is
visible; surrounding whitespace is refused because two ids differing only by
spacing look identical in a dependency list.

### Planner never executes, and the import graph says so

No results, no outcomes, no task states, no attempts. `PlanTask.as_task_ref`
projects onto the published vocabulary with every task `PENDING`, because a
planner that could emit `SUCCEEDED` would be reporting execution it did not do.

`test_planner_never_executes_and_never_invokes_tools` asserts no import path to
`backend.execution`, `orchestrator`, `llm`, `ai`, `agents`, `connectors`,
`knowledge`, `services`, `tools`, `mcp` or `database`.

`backend.contracts.execution` **is** permitted and is not an exception — that
module says of itself: *"These are declarations, not invocations. Nothing here
performs work."* Declaring that a task would be destructive is what lets the plan
be risk-assessed before anything runs.

## Alternatives Considered

**Invent a Planner task vocabulary instead of reusing `TaskRef`.** Rejected: the
published contract explicitly delegates the graph check to whoever holds the
graph, and a second vocabulary would make that delegation meaningless.

**Store the graph rather than rebuild it.** Rejected: rebuilding on every
construction means a stored plan edited into a cycle refuses to *load*, instead
of loading and stalling an executor later. A test pins exactly that.

**Let policy report cycles instead of the aggregate refusing them.** Rejected as
the only mechanism — but policy *also* reports them, so a plan with a cycle *and*
an orphan task *and* an understated risk is refused with all three at once.
Fixing them one round-trip at a time is how planning becomes the slow part.

**Have the planner schedule.** Rejected: `layers()` reports what the graph
*permits*, which is a property of the graph. Choosing what actually runs, when,
and against what contention is Execution's, and a planner that scheduled would be
an executor with extra steps.

**ULID task ids.** Rejected above.

**Let risk be declared freely.** Rejected: an assessment that can be argued down
without changing anything else is an adjective.

## Consequences

- `backend/contexts/` holds nine packages. None imports another.
- `TaskRef`'s delegated cycle check is now implemented, and
  `contracts/execution.py`'s `SideEffectClass` has a second consumer — which is
  what a published contract is for.
- Execution, when it exists, reads `PlannerService.executable_for(mission_id)`
  and nothing else from here.
- Constitution P2 is now enforced at four independent points across two contexts:
  `ExecutionContract`, `PlanTask`, `Plan`, and `PlanApproved`.

## Remaining Risks

1. **Nothing produces a plan automatically.** This context provides the target
   structure and every rule about what makes it sound; the decomposition itself
   is done by whoever calls the API. There is no LLM, no heuristic, no template
   library — deliberately, for ADR-026's reason: a planner that invented tasks
   would invent the constraints they violate too. **Automated decomposition, when
   built, must produce a draft a human validates and approves.**

2. **`execution_key` and `ActionRef` parameters are unresolved.** A task can name
   an execution key that no connector implements, and Planner cannot tell.
   Resolving it needs BC-8, which this context must not reach.

3. **Nothing links an approved plan back to its mission.** `executable_for` is
   the seam; the composition-root adapter that would hand a plan to Mission
   Runtime is not built, because wiring it exceeds the "minimal" this PR allows.

4. **The criterion references are opaque.** A plan can claim to cover `CR-7` when
   the intent has no such criterion. Checking it needs Intent, which S2 forbids —
   the honest fix is a composition-root reconciler, not an import.

5. **`BLAST_OUTLIER_RATIO` and the risk floor table are judgements.** Both are
   named constants so they can be argued with rather than magic numbers in
   conditionals, but nothing validates them against real plans.

6. **Estimates are absent.** No duration, no cost, no resource contention. A plan
   says what and in what order, never how long. Adding estimates without a model
   of the executor would produce numbers that look authoritative and are not.

7. **Storage is in-memory.** `STATE-NO-NEW-FILE-STORES` forbids a new
   JSON-backed store. Restarting loses every plan, including approved ones.

8. **The structured refusal bodies do not survive the running app.** Identical
   and pre-existing: `backend/core/exception_handlers.py` discards `exc.detail`,
   so the cycle path a client would need is replaced by a canned message. Status
   codes survive, and `GET /policy` and `GET /graph` are unaffected because they
   report in `200` bodies — which is where the detail matters most.
