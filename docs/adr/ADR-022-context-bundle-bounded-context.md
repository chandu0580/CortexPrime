# ADR-022 — ContextBundle Bounded Context

- **Status:** Accepted
- **Date:** 2026-08-05
- **Phase:** E1 (PR-E4)
- **Related:** ADR-017 (request context), ADR-019 (WorkOrder), ADR-020 (Engineering Runtime), ADR-021 (Verification)
- **Implements:** Engineering Constitution v1.0 §6; Engineering Artifact Specification v1.0 §3

## Context

The engineering lifecycle stalled at `assigned`. PR-E3's brief claimed
Verification was the blocker; it was not — `spec_tests` and `implementation` both
require the `context` port. This PR is the one that unblocks it.

A context bundle is what an agent *sees*. That makes its failure mode unusual: a
bundle that widened by accident would give an agent access nobody approved, and
the only trace would be work that turned out better informed than it should have
been. Nothing would look wrong.

## Decision

### Named `context_bundle`, not `context`

`backend/platform/context/` already holds `ExecutionContext` (ADR-017), which
appears as a parameter in nearly every method in this codebase. Two things called
"context" one layer apart would be genuinely confusing, and the confusion would
land in exactly the code where getting it wrong matters.

`context` is not one of the product's nine bounded contexts, so this is not the
BC-4 collision from ADR-021 — it is a collision with a platform concept. Same
conclusion, different reason.

### Layers carry access modes, not labels

Five tiers, each with a fixed access mode. Fixed rather than configurable: a
layer whose access could be raised per bundle would let a caller turn a read-only
dependency into a writable one and call it configuration.

**L2 carries interfaces, never implementations.** An agent working on Execution
needs to know what an approval *is*, not how the dispatcher stores one. Supplying
the implementation invites reasoning about it, and reasoning about another
context's internals is how a boundary erodes one convenient shortcut at a time.
`DependencyContract` records `implementation_paths` and deliberately does not
include them, so the omission is visible to a reviewer rather than merely absent.

**L4 is search-only.** Search answers *"does this exist, and where?"*; retrieval
answers *"what does it say?"*. The first is what makes a false premise
discoverable — a repository-wide search returning nothing is exactly how an
unverifiable assumption falls, and it is how PR-10's premise fell. The second is
an expansion, and treating it as a search would be implicit expansion wearing a
query's clothes.

### Expansion is three steps, not one

`request` → `decide` → `apply`. Collapsing them would make the common failure — a
grant whose assembly then fails — indistinguishable from a denial. Keeping them
apart means a granted-but-unapplied request is a visible state: the bundle knows
it owes someone a path.

`apply_expansion` is the **only** path by which a bundle grows, and it refuses
anything outside the granted root and anything targeting the writable layer.
Widening the writable set is a blast-radius change — the Architect's decision,
producing a new WorkOrder version — not an expansion.

### Auto-grant is deterministic, and still an expansion

ADRs, the contracts vocabulary, and a declared dependency's interface are granted
without escalation. Each is already conceptually inside the bundle: an agent
given ADR-018's identifier in its index and refused its text is being told about
a decision it may not read.

Auto-granting is **recorded exactly like any other expansion**. The difference is
who decided, not whether it happened. A category merely "allowed" rather than
granted-and-recorded would be implicit expansion with extra steps, and the log
would understate what agents actually saw.

Auto-grant beats an explicit denial, because denying an ADR the bundle's own
index names would produce a bundle inconsistent with itself.

### Denials are kept, and the expansion log is the point

Repeated requests for the same out-of-scope path across independent WorkOrders
mean the architectural boundary is drawn in the wrong place. That is a finding no
code review surfaces, because each individual request looked reasonable to
whoever made it.

`boundary_signals()` aggregates them. Grants count as strongly as denials —
arguably more, since a boundary routinely worked around is worse than one merely
tested.

### The blast radius is recorded, not matched

`BlastRadiusSpec` holds the declared patterns and does **no path matching**. The
WorkOrder context already owns a `BlastRadius` with a glob engine, forbidden-wins
subtraction, and conservative conflict detection. A second copy of
security-relevant matching logic would drift from the first.

So resolution happens at the composition root, which may legally hold both. This
context knows *what scope was authorised*; it does not decide *which paths that
means*. Stated plainly because it is a real seam: a caller that resolves the
radius wrongly produces a bundle this context will accept.

### The manifest digest makes "what the agent saw" verifiable

Every retrievable reference records a content digest, and the bundle records a
digest over the whole manifest. Without it a bundle records that a path was
included; with it, it records *what was there*.

Persistence restores the digest rather than recomputing it. Recomputing would
make it always match — a check that cannot fail.

## Alternatives Considered

**Import the WorkOrder context's `BlastRadius`.** Would remove the duplication
question entirely. Rejected: it is a context-to-context import, which S2 forbids
and which every engineering context so far has avoided.

**Reimplement glob matching here.** Rejected: two copies of security-relevant
matching logic, guaranteed to drift, with no test that could catch the drift
short of duplicating the test suite too.

**One `expand()` call.** Simpler API. Rejected — see above; it destroys the
distinction between "denied" and "granted but assembly failed".

**Let auto-granted paths bypass the expansion record.** Faster and quieter.
Rejected: the log would understate what agents saw, and the log is the entire
value of the expansion machinery.

**Take `backend/contexts/context/`.** Rejected for the naming collision with
`platform/context`.

## Consequences

- `assigned → spec_tests → implementation` is now reachable. The lifecycle stalls
  at `implementation → review`, which needs the Review context.
- `backend/contexts/` holds four packages. None imports another.
- The composition root gained one adapter — the sanctioned change.
- A bundle cannot grow without a recorded request, and cannot be resolved if it
  is superseded, invalidated, or stale.

## Remaining Risks

1. **The assembled bundle is structurally complete and materially thin.** The
   adapter reads the WorkOrder snapshot's declared blast radius and constraints,
   and resolves no file contents. The right scope, no contents. Filling it needs
   a repository reader — neither this PR nor this context. A bundle that *looked*
   full would be worse, which is why the emptiness is visible rather than papered
   over.

2. **`base_commit` is `"unrecorded"` when assembled by the runtime.** The runtime
   does not know the merge base. Every staleness check therefore passes
   vacuously through that path, which is the same failure shape flagged in
   ADR-021 §6. It resolves when something in the chain reliably knows the commit.

3. **PR-E2 requires the context port for `spec_tests` but never calls it there.**
   `_begin_phase` only assembles on entering `implementation`, so a WorkOrder in
   spec-tests has a port available and no bundle. The Spec-Test Author arguably
   needs one. Not patched here — the brief forbids changing the runtime beyond
   wiring — and pinned by
   `test_the_adapter_assembles_from_the_declared_blast_radius`.

4. **Storage is in-memory.** Restarting loses every bundle, and with it the
   expansion log — which is the artifact this context exists to produce.

5. **Nothing verifies that an agent actually respected the bundle.** The context
   records what was granted; it cannot observe what was read. Enforcement would
   need the agent runtime to route file access through the bundle, which nothing
   currently does.

6. **`boundary_signals` counts paths, not intent.** Three WorkOrders legitimately
   needing the same interface look identical to three working around a badly
   drawn boundary. The signal says "look here", not "this is wrong".
