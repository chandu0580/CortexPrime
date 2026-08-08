# ADR-024 — Review Bounded Context

- **Status:** Accepted
- **Date:** 2026-08-06
- **Phase:** E1 (PR-E6)
- **Related:** ADR-017 (request context), ADR-018 (storage guard), ADR-019 (WorkOrder), ADR-020 (Engineering Runtime), ADR-021 (Verification), ADR-022 (ContextBundle), ADR-023 (ImplementationRecord)
- **Implements:** Engineering Constitution v1.0 §3.2, §8; Engineering Artifact Specification v1.0 §5

## Context

ADR-020 defined `ReviewPort` and shipped the runtime against it, unimplemented.
Every PR since has recorded the same remaining gap: the lifecycle runs
`approved → assigned → spec_tests → implementation` and stops, because entering
`review` needs a collaborator that does not exist. ADR-023 closed the artifact
gap — Verification now receives real implementer claims — but left the lifecycle
stalled one transition earlier.

This context closes it. Review is the independent adversarial read of what an
implementer produced, and it is the last engineering capability between
implementation and verification.

## Decision

### Shaped by the port that already existed

`ReviewPort` was defined in PR-E2 and is **lens-based**: `required_lenses()`,
`request(work_id, round, lenses)`, `outcomes(work_id, round)`. That is not a
detail this PR was free to redesign — the runtime, its events, and its
`ReviewOutcome` value were all built against it.

So the aggregate is **one review per (work_id, round, lens)**, not one per round.
The runtime asks for every required lens and treats a lens that never reported as
a failure rather than a pass; that only works if a lens is a thing that can
independently report.

### Four required lenses, and one that is not

`CORRECTNESS`, `ARCHITECTURE`, `SECURITY`, `TESTING` are required.
`PERFORMANCE` exists and is not.

One reviewer reading for everything reads for whatever they noticed first. The
failure is not laziness — correctness and security are different reading
strategies, and a reader holding one is measurably worse at the other. Splitting
them means a security question is asked by someone who was asked nothing else,
and an unasked question is visible as a lens that never reported.

Performance is excluded from the required set for the opposite reason: a
performance review of a change with no performance-sensitive path produces a
review that says nothing, and a lens that is routinely empty teaches its
reviewers that approving without reading is the normal outcome. That habit does
not stay inside the lens it was learned in.

Each lens carries its `mandate` on the enum, so a reviewer is told what they were
asked rather than inferring it from the lens name.

### Three rules the context exists to make unbreakable

**Review never changes the implementation.** Structurally, not by convention.
This context imports nothing from `implementation_record`; it holds the
artifact's id and digest as opaque strings and has no path to the aggregate they
name. A reviewer that could edit what it reviews is not an independent read — it
is a second author, and the second author agreeing with the first tells you
nothing. `test_review_never_reaches_the_implementation_it_reviews` asserts the
import graph, so the property is checked rather than promised.

Holding the **digest** is what makes the read pin down: the review is a statement
about the artifact that hashed to this value.

**A finding points at something.** A location or an evidence reference, refused
at `ReviewFinding.__post_init__`. "The error handling is wrong" names no file, no
line, and no evidence; the round it triggers is spent guessing at what the
reviewer meant. And a **blocking** finding must additionally state its
`required_change` — stopping work without saying what would restart it is the
most expensive thing a reviewer can do.

**An approval cannot outrun the reading.** Two refusals, held in the aggregate
*and* in the policy:

- approving with an open blocking finding
- approving while any file in the change set is unexamined

The second is the rubber stamp, and it is the failure Review most needs to be
unable to commit: an approval that covered nine of ten files reports downstream
exactly like one that covered ten. Both live in the aggregate as well as the
policy because a record assembled from storage bypasses the service.

### Only one severity blocks

`BLOCKING`, `MAJOR`, `MINOR`, `NIT` — and only `BLOCKING` stops the round.

Three severities that all mean "must fix" carry no information; the reviewer is
choosing an adjective rather than making a decision. Blocking is an act with a
cost, and the cost is what makes it mean something. Everything below it travels
to the implementer as advice, and the implementer's judgement about advice is
itself part of what the next review reads.

### A blocking finding cannot be waived by the reviewer who raised it

`FIXED`, `WITHDRAWN`, `ACCEPTED_RISK` are the three resolutions, and
`ACCEPTED_RISK` is **refused** for a blocking finding.

Accepting a risk is legitimate, and it is not the reviewer's to make alone on
something they themselves called blocking. Waiving one converts "this must
change" into "this may ship" without anyone deciding so, which is the entire
distinction the severity exists to draw. The escape hatches are honest ones: a
blocker the reviewer no longer believes in is a `WITHDRAWN`, and one nobody
intends to fix is a rejection.

`ACCEPTED_RISK` on an advisory finding requires a justification, and the policy
reports every accepted risk as an advisory finding so the hazard travels forward.

### Three decisions, and an eighth event

The Artifact Specification names seven events, including `ReviewApproved` and
`ReviewRejected`. This context emits eight: **`ChangesRequested` is added.**

`review` has three doors out of it in `PHASE_TRANSITIONS` — verification, back to
implementation, and rejected. Folding "request changes" into "reject" would tell
the runtime to abandon a WorkOrder whose premise is sound and whose
implementation merely needs another pass. That is a materially different and far
more expensive answer, and no consumer of the event stream could distinguish the
two after the fact.

The addition is additive and changes no existing event. It is recorded here
rather than made quietly.

### Findings resolve inside the round, not across rounds

Resolution happens while the review is open: a reviewer raises something, the
implementer addresses it, the reviewer marks it. After the decision the review is
sealed. A finding that survives the round travels in the decision, and the next
round's review raises it against the next implementation.

The alternative — reopening a decided review to mark a finding fixed — would
break immutability for the one artifact whose immutability the runtime has
already acted on.

### The decision-to-verdict mapping lives in the adapter

The runtime reads `verdict == "pass"`; this context speaks in decisions. A
context that knew the orchestrator's verdict strings would be coupled to the
orchestrator, which S2 forbids. So `ReviewServiceAdapter` maps `APPROVED → "pass"`
and everything else to itself, and a drift test drives a real approval through the
real runtime and asserts `ReviewOutcome.passed`. Duplication with a checked
invariant, the same treatment ADR-023 gave the blast-radius matcher.

**`ReviewOutcome.blocking_findings` counts *open* blockers, not every blocker
raised.** Reporting all of them would make `passed` false for a review that
legitimately approved — punishing the reviewer who found something and got it
fixed.

### The digest is restored on load, never recomputed

Same rule as ADR-023, for the same reason: recomputing would make verification
always pass, and a check that cannot fail is not a check.

`GOVERNED_FIELDS` excludes `status`, timestamps, and the digest itself.
Superseding a **decided** review is legal and must not invalidate its digest —
superseding changes whether a review is current, not what it said. The aggregate
therefore permits a decision to persist through `SUPERSEDED`, which is the one
place the invariant is deliberately looser than "only a decided review carries a
decision".

## Alternatives Considered

**One review per round rather than per lens.** Rejected: `ReviewPort` reports one
outcome per lens and the runtime treats a missing lens as a failure. A single
review would make "which lens never reported" unanswerable.

**Let Review write to the ImplementationRecord (e.g. to mark findings fixed).**
Rejected: it makes the reviewer a second author. The record is immutable after
completion anyway (ADR-023), so this would have required loosening that too.

**Make every severity blocking.** Rejected: classification that never changes the
outcome is an adjective, not a decision.

**Allow a reviewer to accept a blocking risk.** Rejected above — it is the one
move that silently converts "must change" into "may ship".

**Emit `ReviewRejected` for changes-requested.** Rejected: three lifecycle doors,
three outcomes. Collapsing two loses the cheaper one.

**Refuse to open a review when no ImplementationRecord is sealed.** Rejected, and
this is the closest call in the PR — see remaining risk 1.

**Import `ClaimType`/`BlastRadius`-style vocabulary from other contexts.** Not
needed: Review's vocabulary (lenses, severities, categories, resolutions) is its
own and is duplicated nowhere.

## Consequences

- **`implementation → review → verification` is reachable.** The lifecycle no
  longer stalls, and `capability()` reports nothing missing for the first time.
- `backend/contexts/` holds six packages. None imports another.
- The composition root gained one adapter (`ReviewServiceAdapter`) and one reader
  (`ImplementationArtifactSource`) — the sanctioned change.
- Four tests that asserted "review is unbuilt" now pass `wire_review=False`, so
  each keeps testing exactly the rule it was written for rather than silently
  becoming a test that nothing is missing.
- The runtime's `ReviewCompleted` invariant ("cannot pass with blocking findings
  outstanding") is now enforced at three independent points: the runtime event,
  this context's aggregate, and this context's policy.

## Remaining Risks

1. **A review can be opened against no artifact.** When no ImplementationRecord
   is sealed, the adapter opens the reviews bound to `implementation_digest =
   "unrecorded"` with an empty change set. Refusing would make
   `implementation → review` unreachable for any lifecycle driven without an
   ImplementationRecord — the exact path this PR exists to open — and
   fabricating a digest would defeat the binding entirely. The placeholder is the
   visible middle: it appears on the record and in the API response, and a test
   pins it. **The cost is real:** with an empty change set the coverage rule is
   vacuously satisfied, so such a review *can* be approved without reading
   anything. It is identifiable as such rather than indistinguishable from a real
   approval, which is the most this PR can buy without a Mission Runtime that
   guarantees a sealed record before review.

2. **Nothing forces a reviewer to be a different agent from the implementer.**
   `reviewer` is a string this context records and does not authenticate.
   "Independent review" is structural here (Review cannot edit the
   implementation) but not yet adversarial by identity. That needs the Mission
   Runtime's agent assignment, which does not exist.

3. **`files_examined` is self-reported.** A reviewer can mark every file examined
   without reading one. The coverage rule raises the cost of a rubber stamp from
   *nothing* to *a deliberate false statement of record* — which is a real
   improvement and is not proof of reading. Checking it needs instrumentation no
   context has.

4. **Evidence references are opaque and nothing resolves them.** Identical to
   ADR-023 remaining risk 1: the Evidence context does not exist, and a resolver
   that answered "yes" would make the requirement unfalsifiable.

5. **Nothing gates the `review → verification` transition on lens coverage.**
   The runtime's `ReviewCompleted` event records `passed`, and
   `ReviewService.lens_coverage` reports which lenses are missing, but no policy
   check refuses the transition when a lens never reported. Adding one is a
   change to `engineering/policy.py` — the runtime's package, not this context's
   — and belongs with the Mission Runtime work that will drive these transitions
   automatically. **Today a WorkOrder can be advanced past review by an
   orchestrator that simply does not look at the outcomes.**

6. **Storage is in-memory.** `STATE-NO-NEW-FILE-STORES` forbids a new JSON-backed
   store, and PostgreSQL is out of scope. Restarting loses every review. The
   Protocol is the seam.

7. **The API instantiates one module-level service.** Same shape as every other
   engineering route module; it shares process state across requests and is
   replaced wholesale in tests.

8. **The structured refusal bodies do not survive the running app.** Identical
   and pre-existing: `backend/core/exception_handlers.py` discards `exc.detail`
   and substitutes a canned message per status code, so a reviewer refused for an
   unexamined change set is told *"The request body failed validation"*. The
   status codes survive, and `GET /policy` is unaffected because it reports
   findings in a `200` body — which is where the detail matters most, since it is
   what a reviewer reads before deciding. Fixing it means changing a global
   handler, which is outside this PR's scope. Recorded here rather than papered
   over, as in ADR-023.
