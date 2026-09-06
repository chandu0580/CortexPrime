# Phase 10.4 — Verification Report

**Phase:** The governed approval queue
**Date:** 2026-09-06
**Branch:** `phase-1-foundation`
**ADR:** ADR-097
**Map:** `docs/PHASE_10_4_IMPLEMENTATION_MAP.md`
**Harness:** `scripts/phase104_approval_queue_harness.py`

Labels: `[VERIFIED]`, `[NOT VERIFIED]`, `[DEFERRED]`, `[BLOCKED]`.

---

## Result: **VERIFIED**

| | Result |
|---|---|
| Product harness | **135/135, exit 0, VERIFIED** |
| Negative matrix | **36 cases, 0 provider writes** |
| Architecture gate | **PASS** — 36 passed, 0 failed, 6 skipped, 1193 modules |
| Backend regression | see §14 |
| Frontend tests | **99/99** |
| New authorities | **none** |
| Migrations / new tables | **0 / 0** |

---

## 1. Part A — discovery found most of this already existed `[VERIFIED]`

| # | Question | Answer |
|---|---|---|
| 1 | How are pending approvals persisted? | `cp_approval`, `outcome = 'pending'` until decided |
| 2 | How is status derived? | From `outcome` + `expires_at` + `consumed_by_execution` |
| 3 | Does expiration exist? | **Yes** — `expires_at` is NOT NULL and already enforced |
| 4 | Is consumption represented? | **Yes** — `consumed_by_execution` |
| 5 | Is tenant scope persisted? | **Yes**, and every read is tenant-scoped in SQL |
| 6 | Is approver identity persisted? | **Yes** — `requested_by` / `decided_by`, namespaced |
| 7 | Addressable independently of its investigation? | **Yes, already.** `GET /api/v1/approvals` and `/{id}` existed from 10.3 |
| 8 | Is a new table necessary? | **No** |

`[VERIFIED]` **A2: no new table.** 22 durable tables, unchanged since Phase 10.3.
No migration, no `queue_state`, no stored queue status. The queue is
reconstructed from `cp_approval` on every read.

### A false positive in my own check

`[VERIFIED as fixed]` The first version of A2 searched table names for the
substring `"queue"` and failed — on `cp_queue`, the **execution** queue, which
long predates this phase. Corrected to assert the table count is unchanged and
that no approval-queue table exists. The tempting "fix" would have been to
delete the assertion.

---

## 2. The queue is a projection, not an authority `[VERIFIED]`

- `[VERIFIED]` **A1: the product's non-GET routes are still exactly the three
  from Phase 10.3.** The queue added no way to decide anything new; the decision
  goes to the same `POST /approvals/{id}/decision` — the same conditional update,
  the same one approval authority.
- `[VERIFIED]` **A3: the projection module contains no write.** Asserted by
  source inspection for `sa.insert`, `sa.update`, `sa.delete`, `.decide(`,
  `.request(`, `.grant(` and `commit()` — none present. It cannot become an
  authority by accident.

### Two things it deliberately refuses to compute

- `[VERIFIED]` **C8: no autonomy decision.** `AutonomyPolicy.evaluate` needs
  reliability, drift, world freshness, stop and breaker state and a policy
  config. Supplying plausible values for those would be *deciding* autonomy. The
  queue reports the platform-set ceiling and says so in the payload.
- `[VERIFIED]` **C7: the ADR-038 action digest is reported absent, with the
  reason.** It covers `binding_digest`, which resolution creates *inside* the
  execution the approval authorizes — the very reason ADR-090 exists. It is
  `null` plus a note, never a synthesised value that would look like a binding
  nobody made.

---

## 3. The projection carries authoritative facts `[VERIFIED]`

| | Check | Result |
|---|---|---|
| C1 | Capability, provider, operation | from the commissioned capability |
| C2 | Classification | `irreversible_write` / `fixed` / `contained` |
| C3 | Reversibility | **False**, read from the contract |
| C4 | **Risk** | **recomputed in the harness with the platform's own `implied_risk_for` and asserted equal** |
| C5 | An undeclared effect | **CRITICAL, never low** |
| C6 | Canonical approval digest | present |
| C10 | Target and blast radius | from the stored action |
| C11 | State | pending and actionable |
| C12 | Secrets | **none** in any row |
| C13 | List row vs detail | **identical projection** |

`[VERIFIED]` **Risk is reused, not invented.** `AuthorizationSnapshot.implied_risk`
was **extracted** into `implied_risk_for` and the property now delegates to it,
so there is exactly one implementation and the queue calls the platform's own
taxonomy rather than a copy of it.

`[VERIFIED]` **C13 matters more than it looks:** the list and the detail are the
same function. Two projections of one approval would be two chances to show
different actions for the same digest, and the row a responder triaged must be
the action they decide on.

---

## 4. Tenant isolation — non-vacuous `[VERIFIED]`

| | Check | Result |
|---|---|---|
| D1 | **Neither queue is empty** | A≥3, B≥1 — real approvals for both tenants |
| D2/D3 | Each tenant sees its own | yes |
| D4 | The two queues share **no** approval | yes |
| D5 | B's queue does not contain A's approval | yes |
| D6 | B reading A's approval by id | **404** |
| D7 | The refusal leaks nothing about it | id and namespace absent from the body |

`[VERIFIED]` Confirmed again over the **real browser path** (§13): tenant A's
queue returned 21 approvals from 21 investigations; tenant B's returned 1.

---

## 5. Filters narrow; they never escape tenant scope `[VERIFIED]`

`[VERIFIED]` The tenant predicate is the **first** clause in SQL and every
filter narrows that set. E7 is the one that matters: **tenant B filtering by
tenant A's investigation reference gets nothing.** E8: a forged `tenant_id`
query parameter is ignored.

Also verified: the actionable filter returns only actionable rows (E1); an
investigation filter narrows correctly (E2); the risk filter matches the
platform taxonomy (E3) and returns **nothing** for a risk these actions do not
have (E4) — so it is real, not decorative; unknown capability and week-old age
filters return nothing (E5, E6); an unrecognised status is **422**, not silently
widened to all (E9); an oversized limit is refused (E10).

`[VERIFIED]` **E11: ordering is deterministic** — two reads give the same order.
**E12:** actionable rows sort before decided ones.

---

## 6. The state machine `[VERIFIED]`

Every state is **derived** from the approval row; there is no second machine.

| | Transition | Result |
|---|---|---|
| F1 | pending → approve | 200, granted |
| F2 | pending → reject | 200, denied |
| F3–F6 | approved → approve / reject, rejected → approve / reject | **409 — one action, one judgement** |
| F7 | revoked → approve | **409** |
| F8 | a revoked approval projects | **REVOKED, not actionable** |
| F9/F10 | executing a rejected / revoked approval | **409** |
| G3 | an expired pending request | **EXPIRED, not actionable** |
| G6 | a **granted** approval past its expiry | **EXPIRED, not actionable** |

`[VERIFIED]` **G6 is the subtle one.** A grant that ran out of time authorizes
nothing, so the queue must not keep showing it as approved and offering it.
Equally, a *rejected* approval that later passes its expiry stays REJECTED —
relabelling it would lose who refused it and why.

`[VERIFIED]` An unrecognised outcome projects as **INVALID** and is never
actionable. Fail closed.

---

## 7. Expiration `[VERIFIED]`

| | Check | Result |
|---|---|---|
| G1 | Before expiry | pending, actionable |
| G2 | Every approval has an expiry | the column is NOT NULL — there is no "never expires" option |
| G3 | After expiry | **EXPIRED, not actionable** |
| G4 | It disappears from the actionable queue | yes |
| G5 | Approving an expired request | **409 — fail closed** |

---

## 8. Concurrency `[VERIFIED]`

Two authorized responders, two genuinely simultaneous decisions:

| | Case | Result |
|---|---|---|
| H1 | approve / approve | **status codes `[200, 409]` — exactly one won** |
| H2 | approve / reject | **`[200, 409]` — exactly one won** |
| H1/H2 | Stored outcome | a single decided value with **one** decider |
| H3 | Mechanism | the existing conditional `UPDATE … WHERE outcome = 'pending'` |

`[VERIFIED]` **No distributed lock was added.** The existing optimistic
concurrency is sufficient, and inventing a lock would have been a second
coordination authority. No double execution followed either case.

---

## 9. Negative matrix `[VERIFIED]`

`[VERIFIED]` **36 cases, 0 provider writes**, measured by cluster generation.
Refusals attributed rather than collapsed:

| Stopped by | Cases |
|---|---|
| authentication | 4 |
| authorization | 7 |
| governance | 20 |
| approval-state | 5 |

Covered: unauthenticated listing and detail; forged token; no tenant claim;
cross-tenant listing, detail, approval, rejection and execution;
**18 authority fields smuggled in a decision body** (forged actor, `"admin"`,
tenant, action digest, approval digest, capability, provider, namespace,
workload, parameters, risk, blast radius, code trust, isolation tier, autonomy,
state, secret injection, extra authority field) — **all 422, rejected rather
than ignored**; already-approved, already-rejected, revoked, expired and
granted-then-expired approvals; wrong and malformed approval ids; **an approval
whose stored digest was tampered with directly in the database**, refused by the
gateway; and direct worker / connector / provider / bulk-execute paths, none of
which exists.

---

## 10. Restart `[VERIFIED]`

`[VERIFIED]` **J1: a brand-new repository over a brand-new connection
reconstructs the same queue row** — the state a fresh process would see. The
queue holds nothing a restart could lose, because it holds nothing.

`[VERIFIED]` **J2/J3:** a decision taken before the restart survives it, in both
directions.

`[DEFERRED]` A process restart *mid-decision*: the decision is a single
conditional UPDATE inside one transaction, so there is no window between two
writes to interrupt and no partial state to manufacture.

---

## 11. Audit `[VERIFIED]`

`[VERIFIED]` **K1:** both decisions are durably recorded with actor, tenant,
capability, capability digest, approval digest and timestamp, and the actor is a
namespaced `human:` reference.

`[VERIFIED]` **K2:** no secret, token or DSN in any decision record.

`[DEFERRED]` **An auditable "approval viewed" event was NOT invented.** It is
not currently an auditable event, and adding a governance record for UI
analytics would put reads into the chain that establishes what was authorized.
Part T explicitly permits this; the decision remains auditable, which is what
matters.

---

## 12. Frontend `[VERIFIED]`

`[VERIFIED]` `/approvals` renders the inbox: state, risk, remediation, target,
blast radius, originating investigation, incident, requester, requested time,
expiry and assurance. Each row offers **Review** — never Run, never Execute.

`[VERIFIED]` **No bulk action.** No approve-all, no select-all, no checkbox, no
run-all — asserted by a test that distinguishes a bulk *action* from the "All"
status *filter*, and by a boundary test scanning the component source.

`[VERIFIED]` The detail screen shows the same authoritative preview and **cannot
edit the action**: exactly two inputs exist, a reason and a confirmation, and
their ids are asserted. Approve stays disabled until the operator types the
workload name, which the **server** re-checks.

`[VERIFIED]` A non-actionable approval shows **no decision form at all** — the
approve and reject buttons are absent, not merely disabled.

`[VERIFIED]` The screen states that a different remediation means rejecting and
raising a new proposal; the approved action is never edited.

`[VERIFIED]` Ordering is the **server's**, displayed as such — the component
does no client-side sort.

---

## 13. Real browser-path evidence `[VERIFIED]`

Both processes running, through the same-origin proxy:

| Request | Result |
|---|---|
| `GET /approvals` (the page) | **200** |
| `GET /product-api/api/v1/approvals` with **no cookie** | **401** |
| Tenant A's queue with a real cookie | **21 approvals from 21 different investigations** |
| Tenant B's queue with its own cookie | **1 approval** — its own |

`[VERIFIED]` That first figure is Part K's product goal, demonstrated live: a
responder finds every pending decision without knowing which investigation
raised it.

---

## 14. Gates

- `[VERIFIED]` **Architecture gate PASS** — 36 passed, 0 failed, 6 skipped,
  1193 modules.
- **Backend regression** — see the final report line.
- `[VERIFIED]` **Frontend 99/99.**
- `[VERIFIED]` **No new fitness rule (Part V).** The existing
  `BND-PRODUCT-CANNOT-BYPASS-EXECUTION` already covers the queue — **proven by
  sensitivity test**: injecting `from backend.platform.transport import broker`
  into `approval_queue.py` turned the gate FAIL naming that module; removing it
  returned PASS. Adding a second rule would have been cosmetic.

---

## 15. Performance `[MEASURED]`, no SLA

| | p50 | p95 |
|---|---|---|
| Queue list | **230.6 ms** | **305.2 ms** |
| Queue detail | **23.6 ms** | **28.4 ms** |
| Filtered queue | **182.0 ms** | **199.7 ms** |

`[MEASURED]` The list is dominated by reconstructing one investigation per row
for triage context — an event-sourced replay each. **No index was added**;
instead the algorithm was fixed: the list now projects candidates *without*
context, orders and truncates, and enriches only the rows it returns. That took
list p50 from **521.7 ms to 230.6 ms** on identical data. The remaining cost is
one replay per returned row, which is a real limitation and is recorded as one
rather than optimised speculatively.

**Measured / target / unknown:** *measured* — the above; *target* — **none**;
*unknown* — behaviour under concurrency, over a network, and with a queue of
thousands rather than tens.

---

## 16. Accessibility `[VERIFIED structurally]`, `[NOT VERIFIED]` with assistive technology

`[VERIFIED]` Filters are a labelled `role="group"` with `aria-pressed`; the risk
filter has a label; the queue is a real `<table>` with a caption and
`<th scope="col">`; the confirmation input has `aria-describedby`; state and
risk are rendered as **words**, so no security meaning depends on colour;
timestamps are explicit UTC with a named clock; failures use `role="alert"` and
loading `role="status"`.

`[NOT VERIFIED]` **Not tested with a screen reader or a keyboard-only pass.** No
certification is claimed.

---

## 17. Stop-condition audit — **PASS**

The queue is not an approval authority (no write path exists in it). The client
controls no tenant and no approval identity. The queue recalculates no
governance — risk is the platform's own function, autonomy is not computed, the
action digest is not invented. The action cannot be edited. Digest binding is
untouched. Expired and revoked approvals cannot execute. Concurrent approvals
cannot both execute. No second execution authority, no direct provider access,
no secrets in the frontend or in durable state. No notification became
authorization. No RAG. Exactly-once is not claimed.

---

## 18. Known limitations

- `[MEASURED]` **The list costs one investigation replay per returned row.**
  Halved by the two-pass fix; the remainder is inherent to reading triage
  context from an event-sourced aggregate. Not optimised speculatively.
- `[NOT VERIFIED]` **Accessibility with assistive technology.**
- `[NOT VERIFIED]` **Behaviour at queue scale** — tens of approvals, not
  thousands. No pagination cursor exists; the queue returns a bounded page and
  says so.
- `[DEFERRED]` **No "approval viewed" audit event** (§11), deliberately.
- `[DEFERRED]` **No notifications** — Part R's scope, unchanged.
- `[UNCHANGED]` One commissioned write capability, so every queue row today is
  the same operation on different targets. The projection is capability-generic;
  the catalogue is not yet.
- `[UNCHANGED]` Authentication is still a single env-configured user; approval
  *authority* is therefore tenant membership, not a distinct approver role.
  Real RBAC remains Phase 10.9.
- `[UNCHANGED]` 5 pre-existing TypeScript errors and 1 pre-existing
  vitest/Playwright glob collision, in files this phase did not touch.
