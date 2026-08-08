# ADR-026 — Intent Bounded Context

- **Status:** Accepted
- **Date:** 2026-08-07
- **Phase:** M2 (PR-M2)
- **Related:** ADR-002 (BC-1 ownership), ADR-010 (contract vocabulary), ADR-023 (checked duplication), ADR-025 (Mission Runtime)
- **Implements:** BC-1 "Intent & Mission"; BC-9 (security context); Constitution S6
- **Supersedes:** nothing. `backend/contracts/mission.py` is unchanged.

## Context

PR-M1 built Mission Runtime and stated plainly what it does not do: understand
what a person asked for. It executes structured missions. Something has to turn
"our AWS bill is out of control" into a mandate an automated system can act on
without guessing, and that is what this context is.

The stakes are asymmetric. An under-specified intent does not fail loudly — it
produces a plan that looks reasonable, executes something expensive, and reports
success against a goal nobody could have checked. Every refusal in this context
exists because of that failure mode.

## Decision

### It lives in `backend/contexts/intent/`, and that is BC-1's second package

`backend/contracts/mission.py` declares its owner as **"BC-1 Intent & Mission"**.
So Intent and Mission are the same bounded context in the Constitution's numbering
and separate packages in the tree — the same arrangement the engineering layer
already uses, where `workorder`, `review` and `implementation_record` are distinct
packages that do not import one another.

`intent` is not one of `BOUNDED_CONTEXTS`' nine names, so `BND-CONTEXT-ISOLATION`
does not iterate it. Isolation is enforced by this context's own compliance tests
instead, exactly as PR-E5 and PR-E6 did.

### The requester's words reuse the published contract

`MissionIntent` — `stated_goal`, `requested_by: SecurityContext`, `requested_at`
— already exists and is already what Mission Runtime holds. The aggregate embeds
it rather than duplicating it.

Two things fall out for free: the verbatim goal survives intact, and BC-9's
"every cross-context message carries a tenant-scoped security context" is
enforced by a contract this context did not write. Duplicating it would have
given the codebase two answers to *what did the requester actually say*.

### Three rules refused at construction, not flagged by policy

These are the ones where flagging is too late — an element this weak is consumed
by whatever reads the intent the moment it exists.

**A success criterion nobody can check is a wish.** Every `SuccessCriterion`
must name how it is measured. "The system should be faster" cannot be satisfied
or refuted: an executor cannot know when to stop and a verifier cannot know
whether it worked. The `measure` has no default, deliberately — defaulting it
would be the single most damaging convenience available here, because every
criterion would silently acquire a plausible-looking measure nobody chose.

**A quantitative constraint carries its limit.** Budget, deadline and rate
constraints are refused without one. "Keep costs down" states a concern, not a
boundary; nothing can be shown to have exceeded it. Qualitative kinds are not
held to that standard, because forcing a number onto "do not violate GDPR" would
produce a fake one.

**A scope that includes nothing authorises nothing** — and one that both includes
and excludes a target is a contradiction nobody downstream can resolve. The
natural reading of "no scope" is *everything*, which is the most expensive
possible default.

### Inviolable constraints cannot be soft

Compliance, safety, approval and data residency are refused at
`ConstraintEnforcement.SOFT`. A soft constraint is one a planner may trade off;
marking a regulation tradeable is how it gets traded, and the trade would be
reported as a legitimate optimisation.

### Expansion invalidates validation

`VALIDATED` is a statement about *a particular* set of constraints, scope and
criteria. Adding a constraint — or removing one — makes it a statement about a
document that no longer exists. So expansion returns a validated intent to
`DRAFT`, and `IntentExpanded` carries `returned_to_draft` so a consumer cannot
miss it.

This looks expensive and is cheap: the alternative is an intent marked validated
whose current content nobody checked, which is strictly worse than one honestly
marked draft.

### Approval seals the mandate

An approved intent binds a digest and accepts no further change. Planning acts on
it, so an intent that changed afterwards would mean the plan was built from
something nobody approved — and the approval would be evidence for a mandate that
no longer exists. Supersession is the one exception, and it does not change what
the intent *said*, only whether it is current.

### `IntentPriority` mirrors `MissionPriority`, and the mirror is checked

An approved intent becomes a mission. S2 forbids importing the other context, so
the enum is duplicated — and `test_elements.py` asserts the two agree on
**values, ranks, and urgency**, member for member. A priority that existed on one
side and not the other would silently downgrade in translation and nothing else
in the system would notice.

This is ADR-023's checked-duplication pattern, applied for the same reason.

### Intent never plans, and the import graph says so

No tasks, no steps, no ordering, no dependencies, no tool selection.
`test_the_aggregate_exposes_no_way_to_express_a_plan` asserts no planner-shaped
field exists, and `test_intent_never_plans_and_never_executes` asserts no import
path to `backend.execution`, `orchestrator`, `llm`, `ai`, `agents`, `connectors`,
`knowledge`, `services` or `database`.

The boundary matters because it is what lets a human approve *the goal* without
implicitly approving *the how*. The moment an intent could carry a plan, one
approval would silently become two.

### Risk appetite, not risk

Appetite is what the requester will accept before work starts; a discovered risk
is what the work found. Only the first can exist in an intent. `AVERSE` is
Constitution S6's *prefer blocked over wrong*, stated by the requester rather
than assumed on their behalf.

A `HIGH`-impact acknowledged risk must name who accepted it — one acknowledged
and not accepted is one nobody has decided about.

## Alternatives Considered

**Put Intent inside `backend/contexts/mission/`.** Rejected: PR-M2's constraint
is one bounded context and no Mission Runtime changes. It would also make the
mission package own two lifecycles with different vocabularies.

**Name the package `backend/contexts/bc1/` or fold it into the nine.** Rejected:
`intent` is not one of the nine names, and adding it would change a Constitution
constant to accommodate a package layout — the tail wagging the dog.

**Duplicate `MissionIntent` rather than embed it.** Rejected: two answers to what
the requester said, and BC-9 re-enforced in the copy.

**Let policy flag unmeasurable criteria instead of refusing them.** Rejected:
policy runs at validation, so the criterion would exist in the store until then
and anything reading a draft could consume it.

**Allow soft compliance constraints "for flexibility".** Rejected above.

**Make expansion preserve validation.** Rejected: it is the one change that
converts this context from a check into a rubber stamp.

**Model intent as free text plus tags.** Rejected: that is what already arrives.
The whole value added here is structure a planner can act on without guessing.

## Consequences

- `backend/contexts/` holds eight packages. None imports another.
- Planning has a canonical input that cannot be under-specified in the six ways
  that matter, and `IntentService.planable()` is the query a Planner will read.
- The published `MissionIntent` contract now has two users (Mission and Intent),
  which is what a published contract is for.
- Two deliberate duplications exist across the codebase's product layer, each
  with a drift test naming the other side: `ClaimType` (ADR-023) and
  `IntentPriority` (here).

## Remaining Risks

1. **Nothing turns an approved intent into a mission.** The join is a
   composition-root adapter that PR-M2 does not build, because wiring it would
   mean touching Mission Runtime beyond the "minimal" the PR allows. Today an
   approved intent is a well-formed mandate that nothing consumes. `planable()`
   is the seam.

2. **The `measure` is opaque and nothing resolves it.** This context does not
   know whether the named metric, query or signal exists. A resolver that
   answered "yes" would make the requirement unfalsifiable in a different way,
   and this context has no business reaching a metrics system. So a criterion can
   name a measure that does not exist, and only whoever tries to settle it will
   find out.

3. **Structure is entered, not inferred.** PR-M2 states that Intent "transforms
   natural-language enterprise goals into structured Mission Intents". What this
   context provides is the *target structure* and every rule about what makes it
   valid; the transformation itself is done by whoever calls the API. There is no
   parser, classifier, or LLM here — deliberately, since inferring a constraint
   the requester never stated is exactly the failure this context exists to
   prevent. **Automated extraction, if it is ever built, must produce a draft a
   human expands and approves — not an approved intent.**

4. **Scope targets are strings nobody resolves.** `ScopeTarget("prod-db-7")` is
   accepted whether or not that system exists. Resolving it needs an inventory,
   which means a connector, which this context must not have.

5. **`BROAD_SCOPE_THRESHOLD` is a judgement, not a measurement.** Ten targets is
   where a scope stops looking like a target and starts looking like an estate.
   It is a named constant so it can be argued with rather than a magic number in
   a conditional, but nothing validates it against real usage.

6. **Policy rule `I4` is unreachable through every path that exists.**
   `AcknowledgedRisk` refuses to construct a `HIGH`-impact risk with nobody
   accepting it, so the policy check behind it never fires today. It is kept as a
   second net for a record assembled by some future path that bypasses
   construction, and a test exercises it by bypassing construction deliberately —
   so it cannot quietly become dead code nobody has run. Found by writing the
   test, not by review.

7. **Storage is in-memory.** `STATE-NO-NEW-FILE-STORES` forbids a new JSON-backed
   store. Restarting loses every intent, including approved ones.

8. **The structured refusal bodies do not survive the running app.** Identical
   and pre-existing: `backend/core/exception_handlers.py` discards `exc.detail`,
   so a client refused for an unmeasurable criterion is told the body failed
   validation. Status codes survive, and `GET /policy` is unaffected because it
   reports in a `200` body — which is where the detail matters most, since it is
   what somebody reads before submitting.
