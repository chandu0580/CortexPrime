# ADR-023 — ImplementationRecord Bounded Context

- **Status:** Accepted
- **Date:** 2026-08-05
- **Phase:** E1 (PR-E5)
- **Related:** ADR-017 (request context), ADR-018 (storage guard), ADR-019 (WorkOrder), ADR-020 (Engineering Runtime), ADR-021 (Verification), ADR-022 (ContextBundle)
- **Implements:** Engineering Constitution v1.0 §7; Engineering Artifact Specification v1.0 §4

## Context

ADR-021 shipped the Verification context and named a remaining risk plainly:
Verification received a **placeholder claim** from the runtime, because nothing
in the system carried what an implementer actually asserted. The composition root
seeded each request with one statement the runtime could make on its own
authority — that the WorkOrder had reached the phase through legal transitions.
True, and not what anyone wanted verified.

That is the gap this context closes. An ImplementationRecord is the artifact
Review and Verification consume: the files a round changed, the claims it makes,
the assumptions it checked, the risks it knows about, and the tests and builds it
ran.

## Decision

### Named `implementation_record`, not `implementation`

`implementation` is not one of the product's nine bounded contexts, so this is
not the BC-4 collision from ADR-021. But `backend/contexts/implementation/` would
read as "the implementation of contexts" at every import site. The artifact is a
*record*; the directory says so.

### Three rules the context exists to make unbreakable

**Immutable after completion.** Every mutation refuses once the record is
`COMPLETED` — enumerated in `test_domain.py` rather than spot-checked, with a
meta-test that fails if a mutation is added to the aggregate without a matching
entry. This is stricter than immutability elsewhere in the codebase and it earns
the strictness: a record that changed after Review and Verification read it would
make every finding they produced a statement about a document that no longer
exists.

**Every claim cites evidence.** Refused at `Claim.__post_init__`, not flagged by
policy. A claim with no reference gives a verifier nothing to attack; it can only
be taken on trust, which is the one thing verification exists not to do.

**Changed files stay inside the blast radius.** Checked when the file is
recorded — while the implementer still remembers why it touched it — *and* again
at completion, because a radius can be **narrowed** by re-approval after a file
was legally recorded. A recording-time check alone misses that path.

### The blast-radius matcher is duplicated, deliberately

ADR-022 made the opposite call: ContextBundle *records* a blast radius and does
not match against it, because a second copy of security-relevant matching logic
would drift from the first with nothing catching the drift.

Here the rule is different. Containment must be **enforced**, and enforcing it
requires a verdict. Accepting a pre-computed verdict from the caller would put
the check in the one place least able to be held to it — the caller is the party
the check exists to constrain.

So the matcher is duplicated, and the duplication is made safe the way PR-E2 made
the phase vocabulary safe: `tests/contexts/implementation_record/test_paths.py`
runs this matcher and the WorkOrder context's `BlastRadius` over a shared corpus
of pattern/path pairs and asserts they agree on every one, pair by pair, so a
failure names the pair that diverged. Duplication with a checked invariant beats
duplication without one, and both beat a check the caller performs on itself.

`ClaimType` is duplicated for the same reason and guarded the same way
(`test_claims.py`): S2 forbids importing another context's enum, and a
vocabulary that silently gained a sixth value on one side would let an
implementer make a claim the verifier has no rule for.

### Assumption outcomes are three-valued, and two of them block

`CONFIRMED`, `CONTRADICTED`, `UNVERIFIABLE`. Only the first permits completion.

`UNVERIFIABLE` blocking alongside `CONTRADICTED` is the non-obvious half:
proceeding on a belief nobody could check carries the same risk as proceeding on
one found false, minus the knowledge that it was. They are kept distinct anyway
because they call for different responses — a contradicted premise means reject
the WorkOrder (`PREMISE_FALSE`); an unverifiable one means go find out.

Every resolution must cite what was checked, **including `UNVERIFIABLE`**.
"I tried and could not determine" is itself a finding; recorded without saying
what was tried, it is indistinguishable from not having looked.

### Completion policy is separate from the aggregate, and reports everything

The aggregate enforces per-item invariants. `CompletionPolicy` (C0–C9) decides
whether the whole is submittable, which is a different question — a record where
every individual claim is well-formed can still be an inadequate submission.

`complete` runs the policy and refuses with **every** failure rather than the
first. A completion that refuses one reason at a time takes six attempts to land,
and the sixth is made by someone who has stopped reading the refusals. A
`GET /policy` endpoint runs the same evaluation without completing, so an
implementer can check before submitting.

Two rules are advisory rather than blocking: a declared-but-untouched radius
pattern (it weakens conflict detection for other WorkOrders, but is not a reason
to refuse this one), and an absence claim (settling it requires constructing the
violation, so the implementer should know what it is asking of the verifier).

### The digest is restored on load, never recomputed

`from_record` rebuilds the aggregate and restores the stored digest. Recomputing
it would make verification always pass — a check that cannot fail. This is the
one artifact where that check is the entire point: it is how a reviewer knows the
record under review is the one that was submitted.

`GOVERNED_FIELDS` excludes `status`, timestamps, and the digest itself.
Including `status` would invalidate the digest on the first legal transition, and
superseding a completed record is legal.

### Superseding is permitted on a completed record

The one exception to immutability, and it does not breach it: superseding does
not change what the record *says*, only whether it is current. The digest still
verifies afterwards, and a test asserts exactly that.

### Verification now draws real claims — and keeps the placeholder as a fallback

`ImplementationClaimSource` in the composition root reads the **completed**
record for a WorkOrder and hands Verification the implementer's claims plus the
revision they were made against, so `base_commit` is a real tree rather than
`"unrecorded"` and Verification's staleness check has something to compare.

Evidence travels across as `asserted_evidence` — the implementer's references,
untrusted by construction. Verification refuses to promote an
`AssertedEvidenceRef` into a `VerifiedEvidence`; there is no conversion (ADR-021).
Carrying the references gives a verifier somewhere to start, not a reason to
believe.

**The placeholder remains when no record is sealed.** A WorkOrder can reach
verification without an ImplementationRecord — an older run, or a lifecycle
driven directly through the runtime — and the domain refuses a verification with
no claims at all. Fabricating implementation claims nobody made would be worse
than an obviously thin one.

The wiring lives in `engineering_composition.py`, the only module that imports
more than one bounded context. Putting it inside either context would have been
an S2 violation in one direction or the other.

## Alternatives Considered

**Extend the WorkOrder aggregate with implementation fields.** Rejected: the
WorkOrder is what was *authorised*; the record is what was *done*. Merging them
means the authorisation mutates as work proceeds, and the digest that binds an
approved WorkOrder stops meaning anything.

**Let the caller pass a `within_blast_radius: bool`.** Rejected above — the
caller is the party the check exists to constrain.

**Import `ClaimType` and `BlastRadius` from their home contexts.** Rejected: S2.
Drift tests, not imports.

**Allow claims without evidence, flagged by policy.** Rejected: policy runs at
completion, so an evidence-free claim would exist in the store until then, and
anything reading a record mid-round could consume it.

**Recompute the digest on load so records always verify.** Rejected: a check that
cannot fail is not a check.

**Make `UNVERIFIABLE` advisory.** Rejected: it is the outcome most likely to be
selected under deadline pressure, and making it cheap makes it the default.

**One record per WorkOrder, overwritten each round.** Rejected: Review compares
rounds. Overwriting destroys the comparison and the audit trail with it.

## Consequences

- Verification receives what the implementer actually claimed, against a real
  revision. ADR-021's remaining risk 2 is closed.
- `backend/contexts/` holds five packages. None imports another.
- The composition root gained one reader (`ImplementationClaimSource`) and one
  optional constructor argument on `VerificationServiceAdapter` — the sanctioned
  change.
- The lifecycle still stalls at `implementation → review`, which needs the Review
  context. This PR does not move that.
- Two deliberate duplications now exist, each with a drift test naming the other
  side.

## Remaining Risks

1. **Evidence references are opaque and nothing resolves them.** The Evidence
   context does not exist. `EvidenceRef` records that an identifier was offered;
   it cannot say the identifier names anything. A resolver that answered "yes"
   would make the requirement unfalsifiable, so there is none. What the reference
   buys today is that a verifier knows which identifiers the implementer offered,
   and therefore which it may not reuse (ADR-021).

2. **The blast-radius matcher is duplicated.** Mitigated by `test_paths.py`, not
   eliminated. If someone changes one matcher and updates the test to match, the
   drift ships. The test makes drift loud, not impossible.

3. **Nothing verifies that the recorded change set matches the actual diff.** The
   record says what the implementer says it changed. Checking it against the
   repository needs a revision reader, which no context has. An implementer that
   omitted a file would pass every rule here.

4. **`content_digest` defaults to `unhashed:<path>` from the factory.** Real
   recording supplies the real hash; the placeholder exists so a caller need not
   hash a file to express intent. A record completed with placeholder digests
   still seals and still verifies — the digest covers what was recorded, and what
   was recorded is a placeholder. Visible in the payload rather than hidden.

5. **Storage is in-memory.** `STATE-NO-NEW-FILE-STORES` forbids a new JSON-backed
   store, and PostgreSQL is out of scope. Restarting loses every record, and with
   it the artifact Review and Verification consume. The Protocol is the seam.

6. **The API instantiates one module-level service.** Same shape as every other
   engineering route module. It shares process state across requests and is
   replaced wholesale in tests; a durable repository changes this.

7. **No round-to-round comparison exists yet.** Rounds coexist and supersede, but
   nothing computes what changed between them. Review needs that, and Review does
   not exist.

8. **The structured refusal bodies do not survive the running app.** The routes
   raise `HTTPException` with a body naming the offending path, the reason, and
   the allowed patterns — and the application's global handler
   (`backend/core/exception_handlers.py`, `http_exception_handler`) discards
   `exc.detail` and substitutes a canned message per status code. A client
   refused for a path outside the blast radius is told *"The request body failed
   validation"*, which is both wrong (the body was well-formed) and useless for
   choosing between "expand the radius through re-approval" and "the Architect
   ruled this out on purpose".

   Found by running the app, not by the tests: `TestClient` over a bare
   `FastAPI()` never installs those handlers, so the route-level tests assert a
   body the real deployment does not send. This is **pre-existing and
   app-wide** — PR-E1's and PR-E4's engineering routes lose their details
   identically, confirmed against the running server — so fixing it means
   changing a global handler, which is outside this PR's scope. Recorded here
   rather than papered over.

   The status codes themselves are correct and do survive (422/409/404 verified
   live), and `GET /policy` is unaffected because it reports findings in a `200`
   body rather than through an exception — which is where the detail matters
   most, since it is what an implementer reads before submitting.
