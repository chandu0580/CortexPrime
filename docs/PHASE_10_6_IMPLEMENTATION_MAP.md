# Phase 10.6 — Implementation Map

**Written before implementation.** Part A requires the tree be inspected first.

Labels: `[FACT]` read from this repository, `[DECISION]`, `[GAP]`.

---

## 1. Part A — the twelve discovery questions

| # | Question | Answer |
|---|---|---|
| 1 | Where is requester identity stored? | `cp_approval.requested_by`, written as `f"human:{ctx.principal.principal_id}"` `[FACT]` |
| 2 | Is requester distinct from proposer? | **No — they are the same person in this model.** The human who asks for the remediation is the `principal_id` on the proposal and the `requested_by` on the approval. There is no separate proposer role `[FACT]` |
| 3 | Where is approver identity stored? | `cp_approval.decided_by`, written by the **same** `_principal_ref` helper at decision time `[FACT]` |
| 4 | Is capability owner already separated from enabler? | **Yes** — `policy.py:199` denies `grants_availability` when `principal_is_owner` `[FACT]` |
| 5 | Is there a reusable SoD primitive? | **Partly.** The *denial reason* is reusable; the *predicate* is capability-specific |
| 6 | Does `DenialReason.SEPARATION_OF_DUTIES` exist? | **Yes**, `domain/authorization.py:162` `[FACT]` |
| 7 | Can the existing policy be reused directly? | **No** — `CapabilityPolicy.evaluate` takes an `AuthorizationSnapshot` about a capability operation. It has no approval and no deciding actor |
| 8 | Does requester identity participate in a digest? | **Yes.** `canonical_approval_digest` includes `principal_id`, which is the requester `[FACT]` |
| 9 | Migration required? | **No.** Both identities are already stored |
| 10 | Does the frontend have enough to render the refusal? | Not yet — it needs a server-computed flag `[GAP]` |
| 11 | Is requester identity authoritative and namespaced? | **Yes** — `human:<subject>`, from the verified token `[FACT]` |
| 12 | Is any requester identity accepted from client input? | **No.** `POST …/approval-request` accepts a justification and nothing else; `extra="forbid"` rejects the rest `[FACT]` |

`[VERIFIED]` **Part H is clean — no STOP.** The requester identity data-flow is
already authoritative: it is minted server-side from the verified session by the
same helper that later mints the approver identity, so the two are directly
comparable and neither can be supplied by a caller.

---

## 2. Reusing the SoD primitive without a second implementation `[DECISION]`

Part I: prefer the existing primitive plus the two identities, not a second SoD
system.

`[FACT]` The existing check is
`operation.grants_availability and snapshot.principal_is_owner` — it reasons
about a capability lifecycle operation and an owner. It has no approval, no
decision and no deciding actor, so it cannot be called for this question, and
extending it to take them would change its semantics rather than preserve them.

`[DECISION]` What **is** reused is the primitive that matters: the outcome
vocabulary. The new check emits the existing
`DenialReason.SEPARATION_OF_DUTIES`, so a refusal here and a refusal in the
capability policy are the same named thing, and a reviewer grepping for that
reason finds both. The predicate itself is one identity comparison — there is no
policy engine to duplicate.

`[DECISION]` It lives in `backend/auth/approver.py`, beside the authority
question it sits next to in the request path. That module is already covered by
`BND-AUTH-CANNOT-EXECUTE`, so it structurally cannot execute, dispatch, reach a
provider or touch a credential — which is exactly the constraint Part V asks for
and it is already enforced.

---

## 3. Where the check goes, and why there `[DECISION]`

```
authenticate                                (existing)
  → tenant from the verified token          (existing)
  → approver authority, live from the store (Phase 10.5)
  → load the approval under that tenant     (existing, tenant-scoped)
  → SEPARATION OF DUTIES                    ← new
  → expiry / state                          (existing)
  → the existing approval authority decides (existing)
```

### Precedence is inherited, not invented `[DECISION]`

Part N forbids inventing a precedence rule. `[FACT]` The established order in
`CapabilityPolicy.evaluate` is: **(1)** principal not authorized → DENY,
**(2)** separation of duties → DENY, **(3)** effect/state concerns. This phase
places its check in the same position: after authorization, before state.

`[CONSEQUENCE]` For an approval that is **both expired and self-decided**, the
answer is `SEPARATION_OF_DUTIES` — which is what Part N's own worked example
expects. An independent approver on the same expired approval gets `EXPIRED`.

---

## 4. Identity comparison `[DECISION]`

Both sides are produced by the **same** helper from the verified session, so the
comparison is between two canonical `human:<subject>` references and never
between display names, browser-supplied usernames or free text.

`[DECISION]` The reference is **not** re-formatted to add a tenant segment.
Changing the identity format would change what existing stored references mean.
It is not needed: `_load_approval` is tenant-scoped, so a `human:x` in tenant A
is never compared against a `human:x` in tenant B — the approval is not visible
across the boundary in the first place. This is recorded as a limitation rather
than papered over.

`[DECISION]` Comparison is exact on the stored reference, after stripping
surrounding whitespace and case-folding — because the same person must not
become two people through a capitalisation difference.

---

## 5. Digest safety `[DECISION]`

The check returns ALLOWED or REFUSED and touches nothing else. `[FACT]` The
requester is *inside* `canonical_approval_digest` already; the policy reads it
and never rewrites it. The harness asserts both digests are byte-identical
before and after a decision, on both the approve and the reject path.

---

## 6. What is added

### Backend

```
backend/auth/approver.py               (modified: the SoD check, reusing the existing denial reason)
backend/api/product/approval_routes.py (modified: the check, in the inherited position)
backend/api/product/approval_queue.py  (modified: viewer_is_requester projection)
backend/api/product/schemas.py         (modified)
```

`[DECISION]` **No new table, no migration, no new route, no new authority, no
new role, no new capability.** The product's non-GET routes stay exactly the
three from Phase 10.3.

### Frontend

```
frontend/components/investigator/ApprovalQueue.tsx (modified)
frontend/lib/investigator/types.ts                 (modified)
frontend/tests/investigator/queue.test.tsx         (modified)
```

`[DECISION]` The frontend renders a **server-computed** flag. It never compares
the requester to the current user — a client-side comparison would be the
security control living in the one place that cannot be trusted.

### Harness

```
scripts/phase106_separation_of_duties_harness.py
```

---

## 7. Invariants this phase must not break

1. Requester and approver identities both come from the verified session.
2. A refused self-decision leaves the approval **pending** — it decides nothing.
3. Separation applies to **both** decisions: no loophole where the requester
   cannot approve but can reject.
4. Neither digest changes.
5. Revocation and expiration stay fail-closed.
6. Concurrency stays deterministic, with no lock: if the requester races an
   approver, the **requester must not win**.
7. Provider writes stay at 0 for every negative case.
8. No new capability is commissioned.
