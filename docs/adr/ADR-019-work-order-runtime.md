# ADR-019 — WorkOrder Runtime

- **Status:** Accepted
- **Date:** 2026-08-05
- **Phase:** E1 (PR-E1)
- **Related:** ADR-010 (contracts), ADR-011 (hashing), ADR-012 (events), ADR-016 (fitness functions), ADR-017 (request context), ADR-018 (storage boundary)
- **Implements:** Engineering Constitution v1.0 §2, §3, §4, §5; Engineering Artifact Specification v1.0 §2, §7

## Context

The Engineering Constitution and Artifact Specification define the WorkOrder on
paper. Paper does not refuse an invalid transition.

This ADR records the decisions made turning that specification into a bounded
context — specifically the ones where the specification was silent, ambiguous, or
in tension with the Architecture Constitution.

## Decision

### Placement: `backend/contexts/workorder/`, and the bounded-context list is unchanged

`BOUNDED_CONTEXTS` in `platform/architecture/boundary_rules.py` names the
product's nine domains: mission, evidence, reasoning, verification, execution,
governance, knowledge, connectivity, tenancy. WorkOrder is none of them — it is
an *engineering-process* concept, not a product one.

Adding `"workorder"` to that tuple would have activated `BND-CONTEXT-ISOLATION`
and `BND-PERSISTENCE` for this code, which is tempting. It would also have been
a change to a specification the brief froze, and it would have made the
Architecture Constitution assert that CortexPrime has a tenth bounded context
concerned with pull requests. It does not.

So the context lives under `backend/contexts/` and is governed by `DEP-LAYERS`,
which keys on the `backend.contexts` prefix rather than on the nine names. The
two isolation rules continue to report **skipped**.

*Consequence, stated plainly:* this context has layer enforcement but not
boundary enforcement. With one context there is nothing to isolate *from*, so
the gap costs nothing today. It costs something the moment a second engineering
context exists, and that is when the list should be revisited — as a deliberate
decision, not a side effect.

### `SpecTests` precedes `Implementation`

The brief's example ordering had implementation first. The state machine
inverts it.

Tests written after reading an implementation test what the code *does*, not
what it *should do*. The local proof is PR-02: a test asserted `prefixed_id` was
strictly time-sortable because that matched the mental model of the code just
written. It was wrong, and catching it meant returning to the ULID
specification.

`(Implementation, SpecTests)` is in `FORBIDDEN` with that reason attached, so an
attempt to reorder is refused with the argument rather than with "not permitted".

### Two transition tables, not one

`ALLOWED` says what may happen. `FORBIDDEN` says what may not, **with the reason**.

A transition in neither is refused generically. A transition in `FORBIDDEN` is
refused with the specific reason it was ruled out, because those are the ones
people attempt in good faith. `Implementation → SpecTests` looks like harmless
reordering; refusing it with "not allowed" teaches nothing.

### The digest excludes `state`, `priority`, and assumption resolutions

Each exclusion has a failure it prevents:

- **`state`** — including it would invalidate the digest on the first legal transition.
- **`priority`** — re-ordering a queue must not require re-approving work.
- **assumption `resolution`** — written after approval, by the receiver. Including it would mean the act of checking an assumption broke the approval that demanded the check.

`CANONICAL_FORM_VERSION` is an input to the digest. The day the serialisation
rules change silently is the day every stored approval becomes unverifiable with
no error to announce it.

### Identity is `(work_id, version)`, and only a blast-radius expansion increments it

Every other change produces a new WorkOrder. Predicting a blast radius correctly
first time is genuinely hard, and forcing a new `work_id` for an expansion would
sever the causal chain back to the original intent — losing the ability to ask
*"what did we think this would touch, and how wrong were we?"*, which is one of
the few direct quality signals about the Architect stance.

Narrowing is refused: a radius that shrinks after approval may already have
authorised work that becomes retroactively out of scope.

### Assumptions and rejection grounds are inseparable at authoring

`AssumptionSpec` carries both, and the factory emits the pair. V3 requires every
assumption to have a rejection ground; a factory that let you declare a belief
and forget its refusal path would recreate the exact gap the rule closes.

The incident behind it: a brief once required promoting an invariant to ENFORCED
when no model carried the column that enforcement needed. The belief that it was
possible was never written down, so nothing forced anyone to check it.

### Validation declares its own decidability

Not every rule is mechanically decidable, and a validator that claims to check
"criteria are decidable without the implementation" while actually checking
nothing gives false assurance — worse than none.

So each rule declares itself `STRUCTURAL`, `RESOLVED`, or `HEURISTIC`, and
heuristics produce **advisory** findings. A heuristic that blocks a merge gets
worked around within a week, and the workaround outlives the rule.

### References resolve through an injected resolver, and unknown means absent

S2 forbids this context from importing the contexts that own ADRs, evidence, and
architecture rules. So resolution is injected.

`StaticReferenceResolver` has **no permissive mode**. A resolver that answered
"yes" by default would make V4, V5 and V9 unfalsifiable, and an unfalsifiable
check is indistinguishable from no check.

The practical consequence today: no Evidence context exists, so any WorkOrder
citing evidence **cannot be approved**. That is fail-closed (EP-6) and it is the
honest state of the system rather than a bug.

`FilesystemReferenceResolver` resolves ADRs from `docs/adr/` and constraints from
the live architecture suite — so a constraint stops being enforceable the moment
its rule is deleted, which is precisely when a WorkOrder citing it should start
failing V9.

### The repository takes an `ExecutionContext` on every method

`TENANT-REPOSITORY-CONTEXT` (ADR-018) blocks the merge for any repository method
without one. This repository is the first written after that rule and is
deliberately **not** grandfathered — that list may only shrink.

Tenancy is enforced through the platform's storage guard rather than by hand, so
this repository gets the same refusals as every other guarded store.

**The rule caught a real violation here.** `clear()` originally took no context.
It is the most destructive operation the repository offers, and it was the one
method that lacked one. It now authorises a `DELETE` and clears only within
scope. That is a better argument for the rule than any test of the rule itself.

### In-memory storage only

`STATE-NO-NEW-FILE-STORES` forbids a forty-fourth JSON store. A durable
implementation belongs with the schema work rather than smuggled in here.

Restarting the process loses WorkOrders. That is a stated limitation, not a
hidden one, and the `WorkOrderRepository` Protocol exists so the durable
implementation can be dropped in without touching the domain.

### Events are returned, never published

This context owns no bus. `CommandResult` carries the new aggregate and its
events; the orchestrator publishes. Reaching for an event bus here would couple
the context to infrastructure it has no business knowing about.

`StateChanged` is emitted **alongside** the specific event, not instead of it. A
consumer tracking the machine wants one uniform event; a consumer reacting to
approval wants the specific one. Making the general event a substitute forces
every consumer to branch on a string, which is how a new state goes unhandled.

## Alternatives Considered

**Add `"workorder"` to `BOUNDED_CONTEXTS`.** Would have bought isolation
enforcement for one line. Rejected: it is a specification change the brief
froze, and it asserts something untrue about the product's domain model.

**Put the engineering runtime in a new top-level `backend/engineering/`.**
Cleaner conceptually — it is not a product domain. Rejected because that prefix
appears in no layer rule, so the code would have had *no* dependency enforcement
at all. Layer enforcement without boundary enforcement beats neither.

**Mutable aggregate with in-place transitions.** Shorter. Rejected: every other
domain layer in this codebase is immutable, and a mutable aggregate lets two
concurrent operations observe each other's half-applied state.

**Let `TenantScopedRepository` back the WorkOrder store.** It is the guarded
SQLAlchemy base from ADR-018. Rejected for now: it requires a real table and a
tenant column, which is the schema work this PR is not doing. The guard itself is
reused directly instead, so the refusals are identical.

**Validate on read from storage, or trust the record.** Chose to validate. A
record read back is untrusted input, and "it was valid when written" assumes the
store was never edited by anything but this code — the assumption the product's
own audit chain exists because nobody should make.

## Consequences

- The Engineering Constitution's state machine is executable. An invalid
  transition raises, with the reason it was ruled out.
- Approval binds to content: a governed field changed after approval fails digest
  verification at the next transition.
- `backend/contexts/` exists for the first time. `DEP-LAYERS` now has something
  at layer 2 to enforce.
- A false premise has a typed path out. The PR-10 scenario runs end to end in
  `test_service.py::test_a_contradicted_assumption_leads_to_premise_false`.
- Blast-radius conflict detection is conservative: it serialises work it cannot
  prove disjoint. A false conflict costs latency; a false non-conflict costs a
  corrupted merge.

## Remaining Risks

1. **Storage is in-memory.** Restarting loses everything. The Protocol is the
   seam for a durable implementation; nothing else changes.

2. **No WorkOrder can be approved while citing evidence.** The Evidence context
   does not exist, so V4 fails closed. Correct behaviour, and it means this
   runtime cannot yet govern a real PR end to end.

3. **`BND-CONTEXT-ISOLATION` and `BND-PERSISTENCE` still skip.** They key on the
   nine product contexts and this is not one. No isolation is enforced between
   engineering contexts, and there is currently nothing to isolate.

4. **Rejection is unreachable from `Assigned` and `Blocked`.** The Constitution's
   table permits it from Draft, SpecTests, Implementation, Review and
   Verification only. A WorkOrder blocked forever on a dependency that was itself
   rejected has no exit. Implemented as specified; flagged as a gap in the
   Constitution rather than patched here, because the specification is frozen.

5. **V1 and V2 are heuristics.** They detect the mechanical signature of a
   violation — a semicolon, a function call in a criterion — not the semantic
   question. They will miss a two-outcome intent written as one clean sentence.

6. **The static rule matches parameter names.** It cannot tell a real
   `ExecutionContext` from a dictionary named `context`. The runtime guard
   catches the impostor; static analysis only confirms the parameter is there to
   be checked.

7. **The API composes one service at import time.** Fine for a single-process
   deployment and wrong for anything else. It is not wired into request-scoped
   dependency injection, and the execution context is manufactured per request
   rather than propagated from the caller — so an authenticated user's identity
   does not yet reach a WorkOrder.
