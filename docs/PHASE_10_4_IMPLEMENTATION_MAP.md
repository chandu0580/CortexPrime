# Phase 10.4 — Implementation Map

**Written before implementation.** Part A requires discovery first; this records
what already exists, what is genuinely missing, and what must not be built.

Labels: `[FACT]` read from this repository, `[DECISION]`, `[GAP]`.

---

## 1. Part A — the eight discovery questions, answered from the code

| # | Question | Answer |
|---|---|---|
| 1 | How are pending approvals persisted? | `cp_approval`, one row per request. `outcome` holds `pending` until decided `[FACT]` |
| 2 | How is approval status derived? | From `outcome`, plus `expires_at` and `consumed_by_execution`. `"pending"` is deliberately **not** an `ApprovalOutcome` member, so `find()` returns `None` for it and authorization fails closed `[FACT]` |
| 3 | Does expiration already exist? | **Yes.** `expires_at` is `nullable=False`; `ApprovalFacts.is_valid_for` refuses `moment >= expires_at`; the decision route refuses an expired request `[FACT]` |
| 4 | Is consumption represented? | **Yes.** `consumed_by_execution` records which execution used the approval `[FACT]` |
| 5 | Is tenant scope persisted? | **Yes.** `tenant_id`, and every read is tenant-scoped in SQL `[FACT]` |
| 6 | Is approver identity persisted? | **Yes.** `requested_by` and `decided_by`, both namespaced identity references the repository refuses to write without `[FACT]` |
| 7 | Can an approval be addressed independently of its investigation? | **Yes, already.** `GET /api/v1/approvals` and `GET /api/v1/approvals/{approval_id}` exist and are tenant-scoped; `investigation_ref` is an optional *filter*, not a requirement `[FACT]` |
| 8 | Is a new schema/table necessary? | **No.** `[DECISION]` Everything the queue needs is already a column or is derivable from the capability contract |

`[DECISION]` **No new table. No migration. No queue state store.** Part I's
preference is the one the data already supports: the queue is a projection of
`cp_approval`, reconstructed on every read. A separate `queue_state` would be a
second place the truth lives, and the first place they disagreed would be a
governance incident.

---

## 2. What is genuinely missing

| # | Gap | Needed for |
|---|---|---|
| 1 | **The projection is thin.** `ApprovalView` carries ids, target, digest, state and times — but no side-effect class, code trust, isolation tier, reversibility, risk, blast radius, autonomy or assurance | Part C, Part N |
| 2 | **No derived state.** `state` is the raw outcome string with a separate `expired` boolean; EXPIRED and CONSUMED are not first-class | Part H |
| 3 | **No server-side filters and no deterministic ordering.** The list orders by `requested_at DESC` and filters only by investigation | Parts E, L |
| 4 | **No `/approvals` route in the product.** Approvals are reachable only from inside the investigation that raised them | Parts K, M |

---

## 3. The two things this phase must NOT compute

`[DECISION]` **Autonomy is not evaluated here.** `AutonomyPolicy.evaluate`
requires reliability estimates, drift status, world freshness, emergency-stop
state, breaker state and a policy config `[FACT]`. Running it from a queue
projection would be the queue *making an autonomy decision* — a declared stop
condition. The queue reports the platform-set **ceiling** already carried by the
remediation proposal, and reports a requested/allowed pair **only when an
`AutonomyDecision` was actually recorded**. Where none was, it says so rather
than computing one.

`[GAP]` **The ADR-038 action digest cannot exist for a pending approval.** It
includes `binding_digest`, and the binding is created by resolution *inside* the
execution the approval is meant to authorize `[FACT]` — which is the whole
reason ADR-090 introduced `canonical_approval_digest`. Part C lists both. The
queue therefore projects the canonical approval digest, which is real, and
reports the action digest as **not yet in existence**, with the reason. It does
not invent one.

---

## 4. Risk — reuse, do not invent

`[FACT]` The platform already has a deterministic risk derivation:
`AuthorizationSnapshot.implied_risk` maps the declared effect to a `RiskLevel`,
and an **undeclared** effect is CRITICAL, not LOW — "the field most often
missing is the one that says how much damage the thing can do."

`[DECISION]` That rule is **extracted into a module-level function in the same
module** and `implied_risk` delegates to it, so there remains exactly **one**
implementation and the queue calls it rather than copying it. Part L's rule —
do not invent a risk priority conflicting with the existing taxonomy — is met by
using the taxonomy itself.

`[DECISION]` Ordering is deterministic and policy-backed:
**actionable first, then risk descending, then oldest first.** "Actionable"
means genuinely decidable now — pending, not expired. No LLM, no embedding, no
score (Part X).

---

## 5. What is added

### Backend

```
backend/contexts/connectivity/domain/authorization.py   (modified: extract implied_risk_for)
backend/contexts/connectivity/infrastructure/sql_approval.py (modified: server-side filters + ordering)
backend/api/product/approval_queue.py                   (new: the projection, no authority)
backend/api/product/schemas.py                          (modified: ApprovalQueueItem / ApprovalQueue)
backend/api/product/approval_routes.py                  (modified: filters on the existing GET)
```

`[DECISION]` **No new route is added for the decision.** `POST
/api/v1/approvals/{approval_id}/decision` already exists, already resolves the
approval by id, already takes the approver from the session and already applies
a conditional `outcome = 'pending'` update. The queue submits to it. The set of
non-GET routes therefore stays exactly the three Phase 10.3 enumerated, and the
harness assertion that they are exactly those three is unchanged.

### Frontend — all new except one route link

```
frontend/app/approvals/page.tsx              the inbox
frontend/components/investigator/ApprovalQueue.tsx
frontend/lib/investigator/types.ts           (modified: queue types)
frontend/hooks/queries/useInvestigator.ts    (modified: useApprovalQueue)
frontend/tests/investigator/queue.test.tsx   rendering + safety rules
```

### Harness

```
scripts/phase104_approval_queue_harness.py   real PostgreSQL, real cluster, real Redis
```

---

## 6. Concurrency (Part Q)

`[FACT]` `decide()` already issues a single conditional UPDATE
(`WHERE approval_id = … AND tenant_id = … AND outcome = 'pending'`) and returns
`rowcount`. Two responders deciding at once therefore produce **one** update and
one `rowcount = 0`, which the route turns into 409.

`[DECISION]` **No distributed lock is added.** The existing optimistic
concurrency is sufficient and inventing a lock would be a second coordination
authority. The harness proves it with two real concurrent decisions —
approve/approve and approve/reject — and asserts exactly one wins and no double
execution follows.

---

## 7. Invariants this phase must not break

1. The queue **reads**; the approval service **decides**. One approval authority.
2. Tenant from the verified session only; filters are applied **after** tenant
   scope, never instead of it.
3. No editing of an action, ever. A different remediation means rejecting and
   proposing again.
4. An expired or revoked approval is never actionable and never executes.
5. Concurrent decisions resolve to exactly one, with no double execution.
6. Every negative case: `provider_writes = 0`, with the stopping layer named.
7. At-least-once remains the contract; exactly-once is not claimed.
