# ADR-021 — Verification Bounded Context

- **Status:** Accepted
- **Date:** 2026-08-05
- **Phase:** E1 (PR-E3)
- **Related:** ADR-016 (fitness functions), ADR-018 (storage boundary), ADR-019 (WorkOrder runtime), ADR-020 (Engineering Runtime)
- **Implements:** Engineering Constitution v1.0 §7; Engineering Artifact Specification v1.0 §6, §8

## Context

PR-E2 built a runtime with a `VerificationPort` and no implementation behind it.
This is the implementation: the context that independently validates engineering
claims.

Its single rule, from Engineering Constitution EP-5: **verification never trusts
a summary.** Not an implementation summary, not a review summary, not a test
summary. It reproduces.

Stating that is easy. Making it structurally true is the work.

## Decision

### Named `engineering_verification`, not `verification`

`verification` is already one of the product's nine bounded contexts — BC-4,
*"did the fix actually work?"*. That is a different concept that happens to share
a word: BC-4 verifies that a deployed remediation succeeded; this verifies that
an engineering claim is true.

Taking `backend/contexts/verification/` would have activated
`BND-CONTEXT-ISOLATION` and `BND-PERSISTENCE` for this code, which is tempting.
It would also have left BC-4 nowhere to go, and asserted that the product's
Verification context is about pull requests.

Same precedent as ADR-019's decision not to add `workorder` to the bounded-context
list. `DEP-LAYERS` still applies; the two isolation rules continue to skip.

### The type system carries the central rule

An implementer's evidence arrives as `AssertedEvidenceRef` — an opaque
identifier. The verifier's own findings are `VerifiedEvidence`, which cannot be
constructed without stating what was collected and how strongly it is held.

`ClaimResult` requires `VerifiedEvidence`. **There is no conversion between the
two types**, so "verification" that re-points at the implementer's artifact does
not type-check. That is stronger than any runtime check, because it fails at the
call site rather than at the end of a run.

A runtime check backs it up anyway (`BorrowedEvidence`), because someone can
always wrap the implementer's identifier in fresh evidence and claim to have
collected it.

### Claim type determines what can settle it

The rule that makes this more than re-running the tests.

An `ABSENCE` claim — *"no cross-tenant read is possible"* — cannot be settled by
observing success. A green suite shows that nothing tried; it says nothing about
whether something *could*. Only `ADVERSARIAL_CONSTRUCTION` settles it, and the
aggregate refuses a `REPRODUCED` verdict reached any other way.

`COUNT` claims are flagged as needing independent measurement for the opposite
reason: they look trivially verifiable and are the ones most often wrong, because
the counting mechanism is itself untested. Every false status claim observed
during Phase 1 was a count.

Only `ABSENCE` has a *mandatory* method. Forcing one where several legitimately
work makes a rule feel arbitrary, and arbitrary rules get worked around.

### Four verdicts, and `UNREPRODUCIBLE` is not a soft `REPRODUCED`

A claim nobody could check carries the same risk as one checked and found false,
minus the knowledge that it was. So it blocks completion exactly as a
contradiction does.

`OUT_OF_SCOPE` exists so a verifier can say *"this is real but not mine"* without
either passing or failing it. Silence would be indistinguishable from having
missed it.

### `FAILED` and `INCOMPLETE` are separate outcomes

They mean different things to the reader. `FAILED` says the work is wrong.
`INCOMPLETE` says the verifier could not tell — a fact about the verification,
not the work, and merging on it is a different decision needing different
information.

Collapsing them into "not complete" removes exactly the distinction the reader
needs.

### The outcome is derived, never chosen

`close()` asks the policy what the record has earned and closes as that. A caller
cannot pass the outcome it would prefer.

The single exception is `invalidated`, which policy cannot see: it means an
approved premise turned out false, which is a fact about the WorkOrder rather
than about any claim. Even that requires naming the failed premise.

If a caller could close a verification as complete, "verification" would be a
field someone sets.

### `OBSERVED` evidence is second-class, deliberately

Live validation against a real external system produces exactly this, and it is
the most valuable evidence there is for whether something actually works. It also
cannot be re-established.

So it is admissible — it may support a claim — but it cannot be the *sole*
support for a gate. That is a compromise between two true things, not a
resolution of them.

`ASSERTED` exists in the enumeration so it can be named and refused rather than
passing silently as absence. `VerifiedEvidence` cannot be constructed at that
level at all.

### Storage re-validates on read

A record read back is untrusted input. "It was valid when written" assumes the
store was never edited by anything but this code.

In a context whose entire purpose is refusing to take things on trust, exempting
its own storage would be absurd.

## Alternatives Considered

**One `Evidence` type with a `produced_by` field.** Simpler. Rejected: it makes
the central rule a runtime check on a string, and a string field is exactly what
gets set to the convenient value under time pressure. Two types with no
conversion cannot be.

**Let the caller supply the outcome and have policy advise.** Rejected for the
reason above — it makes verification a field.

**Take `backend/contexts/verification/` and add BC-4 elsewhere later.** Rejected:
it moves the cost onto whoever builds BC-4, who will have less context and no
reason to expect the collision.

**Exclude `OBSERVED` evidence entirely.** Cleaner rule. Rejected: it would make
the project's most valuable validation practice — real Docker containers, real
Jira tickets, real databases — formally inadmissible, which would either be
ignored or would stop the practice.

**Reuse the runtime's `VerificationRequested` event.** Rejected: `CONTRACT_NAME`
is globally unique so it is not even possible, and the two are genuinely
different facts. The runtime's says *the orchestrator asked*; this one says *the
context accepted*. The gap between them is where a dropped request would hide.

## Consequences

- `review -> verification` and `verification -> ready` are now reachable. They
  were previously unreachable even with everything upstream in place.
- A verification cannot report success without producing its own evidence for
  every claim, at a trust level that can stand alone, against the tree being
  merged.
- `backend/contexts/` now holds three packages. None imports another.
- The composition root gained one adapter, which is the sanctioned change.

## Remaining Risks

1. **The stated premise of this PR was false, and the blocker remains.** The
   brief said the runtime stalls at `Assigned` because Verification is missing.
   It stalls because `spec_tests` requires the **context** port. Wiring
   Verification unblocks the last two transitions without unblocking the path to
   them. `test_the_path_to_verification_is_still_blocked` asserts this. The
   lifecycle needs ContextBundle and Review, both explicitly out of scope here.

2. **The runtime's verification request carries a placeholder claim.** The
   runtime knows a WorkOrder is ready to be verified; it does not know what was
   claimed, because no ImplementationRecord exists to carry the implementer's
   claims. The adapter seeds the one claim the runtime can state on its own
   authority — that the WorkOrder reached this phase legitimately. Honest, and
   nearly useless: real verification needs the artifact the Engineering Artifact
   Specification calls `ImplementationRecord`, which nothing builds yet.

3. **Storage is in-memory.** Restarting loses every verification.

4. **Nothing enforces that the verifier is a different agent from the
   implementer.** The context records `collected_by` and refuses borrowed
   evidence, but a single process could produce both. Independence is currently a
   deployment property, not an enforced one.

5. **`P4` compares trust levels, not evidence quality.** A `DETERMINISTIC`
   command that ran the wrong command passes every check here. The context can
   enforce that evidence was produced and how strongly it is held; it cannot
   enforce that it was the right evidence.

6. **Staleness is only checked when `current_commit` is supplied.** A caller that
   omits it gets no staleness check at all. Failing closed would mean refusing
   every verification whose caller does not know the current commit, which in
   practice would mean the check is disabled by omission rather than by choice —
   the same outcome, less visibly. Worth revisiting once a caller reliably knows
   the merge base.
