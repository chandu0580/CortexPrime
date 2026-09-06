# Phase 10.6 — Verification Report

**Phase:** Separation of duties — requester ≠ approver
**Date:** 2026-09-06
**Branch:** `phase-1-foundation`
**ADR:** ADR-099
**Map:** `docs/PHASE_10_6_IMPLEMENTATION_MAP.md`
**Harness:** `scripts/phase106_separation_of_duties_harness.py`

Labels: `[VERIFIED]`, `[NOT VERIFIED]`, `[DEFERRED]`, `[BLOCKED]`.

---

## Result: **VERIFIED**

| | Result |
|---|---|
| Product harness | **123/123, exit 0, VERIFIED** (first run) |
| Negative matrix | **37 cases, 0 provider writes** |
| Positive path | **1 real provider write**, the already-commissioned capability |
| Architecture gate | **PASS** — 37 passed, 0 failed, 6 skipped, 1194 modules |
| Backend regression | see §14 |
| Frontend tests | **113/113** |
| Migrations / new tables | **0 / 0** |
| New authorities / roles | **none** |
| New fitness rules | **none** — the existing one already covers it |

---

## 1. Part A — the twelve discovery questions `[VERIFIED]`

The load-bearing answers:

- `[FACT]` **Requester identity is already authoritative.** `cp_approval.requested_by`
  is written server-side as `f"human:{ctx.principal.principal_id}"` from the
  verified token, by the **same helper** that later writes `decided_by`. The two
  are therefore directly comparable.
- `[FACT]` **No caller can supply it.** `POST …/approval-request` accepts a
  justification and nothing else; `extra="forbid"` rejects the rest.
- `[FACT]` **Requester and proposer are the same person** in this model — there
  is no separate proposer role.
- `[FACT]` **The requester is already inside `canonical_approval_digest`** (as
  `principal_id`). Asserted in the harness (A4) by recomputing the digest for two
  different principals and showing they differ.
- `[FACT]` **No migration needed** — both identities were already stored.

`[VERIFIED]` **Part H is clean — no STOP was required.** The identity data-flow
was already correct; nothing had to be patched around.

---

## 2. Reuse, not a second SoD system `[VERIFIED]`

`[FACT]` The existing check is
`operation.grants_availability and snapshot.principal_is_owner` — it reasons
about a capability lifecycle operation and an owner, has no approval and no
deciding actor, and so cannot be called for this question. Extending it to take
them would have changed its semantics rather than preserved them, which Part I
forbids.

`[VERIFIED]` **A3: what is reused is the primitive that matters** — the outcome
vocabulary. `separation_denial_reason()` returns the platform's own
`DenialReason.SEPARATION_OF_DUTIES`, imported lazily and asserted equal to
`"separation_of_duties"`, so a refusal here and a refusal in the capability
policy are the **same named thing**. The predicate itself is one identity
comparison; there is no policy engine duplicated.

---

## 3. The requester cannot decide — in either direction `[VERIFIED]`

`[VERIFIED]` **B0 is what makes the rest meaningful: the refused caller is a
fully authorized approver.** They hold `approve:remediation`, in the right
tenant, on a live pending approval. The only thing wrong is that they asked for
it — so no refusal below can be explained by a missing grant.

| | Check | Result |
|---|---|---|
| B1 | Requester **approves** their own remediation | **403**, `separation_of_duties` |
| B2 | Requester **rejects** their own remediation | **403**, `separation_of_duties` |
| B3 | Cluster | **0 writes** |
| B4/B5 | After each refusal | **still PENDING**, no decider, no decision time |

`[VERIFIED]` **B2 closes the loophole Part D names.** A rule that stopped
approval but allowed rejection would leave the requester able to bury their own
request — the same authority wearing a different hat.

---

## 4. An independent approver still can `[VERIFIED]`

| | Check | Result |
|---|---|---|
| C1 | An independent approver approves **the very approval the requester was refused** | 200, `granted` |
| C2 | And rejects the other one | 200, `denied` |
| C3 | Both identities survive | `human:requester-a…` → `human:approver-b…` |
| C4 | They are different people | yes — the point |
| C5 | Execution through the **existing gateway** | **exactly one deployment mutated** |

`[VERIFIED]` E1–E4: refusal then independent decision works in both directions —
requester refused → still pending → independent approver approves; and the same
for reject.

---

## 5. No digest changes `[VERIFIED]`

| | Check | Result |
|---|---|---|
| D1 | After an independent **approve** | approval digest, capability digest and payload **byte-identical** |
| D2 | After an independent **reject** | **byte-identical** |
| D3 | After a **refused** self-decision | **byte-identical** |

`[VERIFIED]` The policy answers ALLOWED or REFUSED and rewrites nothing. The
requester is *inside* the digest; the check reads that identity and never
touches it.

---

## 6. Precedence — inherited, not invented `[VERIFIED]`

`[FACT]` `CapabilityPolicy.evaluate` orders its checks: **(1)** principal not
authorized, **(2)** separation of duties, **(3)** effect/state. This phase places
its check in the same position — after approver authority, before expiry.

| | Case | Reason returned |
|---|---|---|
| I1 | An **independent** approver on an expired approval | **EXPIRED** (409) |
| I2 | The **requester** on that same expired approval | **SEPARATION_OF_DUTIES** (403) |

`[VERIFIED]` That is exactly Part N's worked example, reached by inheriting the
existing order rather than choosing one.

`[VERIFIED]` **I3/I4:** a revoked approval refuses **both** the requester and an
independent approver, with zero cluster mutations.

`[VERIFIED]` **F4:** the queue applies the same precedence — a member with no
authority is told about the *authority*, not about separation, because that is
what is actually stopping them.

---

## 7. Concurrency — the requester must not win `[VERIFIED]`

| | Case | Result |
|---|---|---|
| G1 | Two independent approvers, approve/approve | **`[200, 409]`** |
| G2 | approve/reject | **`[200, 409]`** |
| G3 | **Requester races an approver** | requester **403 `separation_of_duties`**, approver **200** |
| G4 | The single stored decision | the **approver's**, never the requester's |
| G5 | Cluster | 0 writes |
| G6 | Mechanism | the existing conditional `UPDATE … WHERE outcome = 'pending'` |

`[VERIFIED]` **G3 is the one that matters.** A race cannot be used to slip past
the policy: the requester's request is refused on its own merits before it ever
reaches the conditional update, so there is no window in which it could win.
**No distributed lock was introduced.**

---

## 8. Revocation still fail-closed `[VERIFIED]`

| | Check | Result |
|---|---|---|
| H1 | B's authority revoked, token minted before | **403 `no_approver_authority`** |
| H2 | The requester on the same approval | **403 `separation_of_duties`** — the *other* reason |
| H3 | A newly-authorized independent approver | **200** |

---

## 9. The queue says why, without computing it `[VERIFIED]`

| | Viewer | `actionable` | `can_approve` | `authority_reason` |
|---|---|---|---|---|
| F1/F2 | The requester | **true** | **false** | `separation_of_duties`, `viewer_is_requester: true` |
| F3 | An independent approver | true | **true** | `approver_authority_granted` |
| F4 | A member with no authority | true | false | `no_approver_authority` |

`[VERIFIED]` **F5: the row is NOT hidden from the requester.** They can see what
they asked for and that somebody else must decide it. Hiding it would leave them
unable to distinguish "somebody must act" from "nothing is there".

`[VERIFIED]` **F6:** the flag is computed **server-side** from the stored
requester. The component renders it; a frontend test asserts the component
contains no `requested_by ===` comparison and no `currentUser` — a client-side
comparison would put the security control in the one place that cannot be
trusted.

`[VERIFIED]` Confirmed live over HTTP: requester `can_approve=false /
separation_of_duties`, approver `true / approver_authority_granted`, plain
member `false / no_approver_authority` — and the real decision returns **403**
for the requester and **200** for the approver.

---

## 10. Negative matrix `[VERIFIED]`

`[VERIFIED]` **37 cases, 0 provider writes**, measured by cluster generation.
Refusals attributed across six layers:

| Stopped by | Cases |
|---|---|
| governance | 24 |
| separation_of_duties | 4 |
| approval_state | 4 |
| approver_authority | 2 |
| authentication | 2 |
| membership | 1 |

Covered: requester approves and rejects; a non-approver approves and rejects; an
approver from the wrong tenant (404); anonymous; a token with no tenant claim;
**22 identity- and authority-forgery fields in the body** — including
`requester`, `requested_by`, `approver`, `actor`, `actor_ref`,
`viewer_is_requester`, `can_approve`, both digests, capability, workload,
namespace, risk, blast radius, autonomy, code trust, isolation and a secret —
**all 422, rejected rather than ignored**; tenant and actor in **query
parameters**; tenant, actor, requester, role and `can_approve` in **headers**
(both still `separation_of_duties`); expired, revoked, already-approved and
already-rejected approvals; an approval whose stored digest was tampered with
directly in the database, refused by the gateway; and direct worker / provider /
credential / `self-approve` routes, none of which exist.

`[VERIFIED]` **J-FINAL-b: the approval every one of those 37 cases targeted is
still PENDING.**

---

## 11. Restart `[VERIFIED]`

`[VERIFIED]` **K1:** both identities survive. **K2:** an approval the requester
was refused on is **still pending** after a restart — no restart converts a
refusal into an approval. **K3:** the policy reaches the same verdict on the
reloaded record, in both directions. **K4:** a decision taken before the restart
survives it.

---

## 12. Audit `[VERIFIED]`

`[VERIFIED]` **L1/L2:** the approved and rejected records name **both humans** —
who asked and who allowed — with the outcome and the decision time.

`[VERIFIED]` **L3:** the approval the requester attempted carries **no decider,
no decision time and outcome `pending`**. Nothing in the record claims they
approved anything.

`[VERIFIED]` **L4: no new audit event kind was invented.** Part P is explicit
about not inventing one for convenience; a refusal leaves the row untouched,
which is the existing semantics.

`[VERIFIED]` **L5:** no token, credential or DSN in any record.

---

## 13. Frontend `[VERIFIED]`

`[VERIFIED]` The screen now distinguishes **four** reasons a decision is
unavailable, as four distinct sentences and never one "forbidden":

- *decided / expired / revoked* — nobody may decide this any more;
- *no approver authority* — you may not, and neither may most people here;
- **separation of duties** — you may in general, and not this one: you asked for it;
- *actionable* — you may decide it.

`[VERIFIED]` Telling the requester "you lack authority" would be **false** —
they have it. The screen says *"You requested this remediation and cannot decide
it"*, explains that the rule covers rejection too, and shows the server's reason
code. It offers **no decision control at all** — the buttons are absent, not
disabled. The row marker reads "you requested this", distinct from "you cannot
approve".

`[VERIFIED]` The tenant-wide banner is suppressed for a requester who does hold
authority, so the page never contradicts itself.

---

## 14. Gates

- `[VERIFIED]` **Architecture gate PASS** — 37 passed, 0 failed, 6 skipped,
  1194 modules.
- **Backend regression** — see the final report line.
- `[VERIFIED]` **Frontend 113/113.**
- `[VERIFIED]` **No new fitness rule (Part V).** The policy lives in
  `backend/auth/approver.py`, which `BND-AUTH-CANNOT-EXECUTE` (Phase 10.5)
  already covers — **proven by sensitivity test**: injecting
  `from backend.contexts.execution.domain import invocation` into that module
  turned the gate **FAIL** naming it; removing it returned PASS. A second rule
  would be cosmetic.

---

## 15. Performance `[MEASURED]`, no SLA

| | p50 | p95 |
|---|---|---|
| Queue list | **54.0 ms** | **74.4 ms** |
| Queue detail | **28.3 ms** | **56.1 ms** |
| **Requester refusal** | **14.4 ms** | **18.9 ms** |
| Independent approval | **42.6 ms** | 69.0 ms |
| Independent rejection | **36.5 ms** | 59.6 ms |

`[MEASURED]` The separation check is one string comparison on a record already
loaded — no query, no index, and it is the cheapest path on the board: a refused
self-decision is *faster* than an accepted one, because it stops before the
state checks and the write. **No index was added.**

`[DEFERRED]` Decision p95 is from 6 samples — each consumes a pending approval.

---

## 16. Accessibility `[VERIFIED structurally]`, `[NOT VERIFIED]` with assistive technology

`[VERIFIED]` The refusal is **text** in a `role="note"` region with a machine
reason code; approval state and risk are words, not colour; controls are
labelled; the confirmation keeps its `aria-describedby`; timestamps are explicit
UTC. **There is no misleading disabled control** — a requester sees no decision
form at all, with a sentence saying why.

`[NOT VERIFIED]` Not tested with a screen reader or keyboard-only pass. **No
certification claimed.**

---

## 17. Stop-condition audit — **PASS**

The requester can no longer approve **or** reject. Requester, approver and
tenant identities all come from the verified session and none is client
controlled. Self-approval cannot be bypassed through another endpoint (the three
POST routes are unchanged and enumerated), through direct worker access (no such
route), through replay (a refused decision changes nothing to replay), or
through concurrency (G3). Neither digest changes. Revocation stays fail-closed.
The frontend cannot authorize itself. No model influences the policy. No new
approval or execution authority. No secrets in durable records. **No new
capability was commissioned.** Exactly-once is not claimed.

---

## 18. Known limitations

- `[NOT VERIFIED]` **Requester and proposer are the same person in this model.**
  There is no separate proposer role, so "the proposer may not approve" is not a
  distinct constraint here — it is the same constraint. If a proposer role is
  ever introduced, this policy must be revisited rather than assumed to cover it.
- `[DEFERRED]` **The identity reference is not tenant-qualified.** It is
  `human:<subject>`, not `human:<tenant>:<subject>`. Safe today because
  `_load_approval` is tenant-scoped, so an identity in tenant A is never
  compared against one in tenant B — the approval is not visible across the
  boundary. Changing the format would change what existing stored references
  mean, so it is recorded rather than done.
- `[NOT VERIFIED]` **Execution authority is still not narrowed** (carried from
  Phase 10.5): triggering the execute route needs tenant membership plus a
  granted approval. **Note the interaction:** a requester who cannot approve
  their own action *can* still execute one an independent approver approved.
  That is arguably correct — the human judgement was independent — but it is
  named here rather than implied to be covered.
- `[NOT VERIFIED]` **Approver scope is still tenant-wide** (carried from 10.5).
- `[NOT VERIFIED]` **Accessibility with assistive technology.**
- `[UNCHANGED]` One commissioned write capability; authentication is a single
  env-configured user over a file-backed membership store; 5 pre-existing
  TypeScript errors and 1 pre-existing vitest/Playwright glob collision, in
  files this phase did not touch.
