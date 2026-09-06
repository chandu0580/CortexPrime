# Phase 10.3 — Verification Report

**Phase:** Human approval and governed remediation through the product path
**Date:** 2026-09-06
**Branch:** `phase-1-foundation`
**ADR:** ADR-096
**Map:** `docs/PHASE_10_3_IMPLEMENTATION_MAP.md`
**Harness:** `scripts/phase103_approval_remediation_harness.py`

Labels: `[VERIFIED]`, `[NOT VERIFIED]`, `[DEFERRED]`, `[BLOCKED]`.

---

## Result: **VERIFIED**

| | Result |
|---|---|
| Product harness | **121/121, exit 0, VERIFIED** |
| Negative matrix | **38 cases, 0 cluster mutations** |
| Positive path | **exactly 1 real provider write** |
| Architecture gate | **PASS** — 36 passed, 0 failed, 6 skipped, 1192 modules |
| Backend regression | **2974 passed, 0 failed** |
| Frontend workspace tests | **79/79** |
| Revocation | **VERIFIED** against real Redis, fail-closed |
| New authorities | **none** |
| Migrations / new tables | 0 migrations, **1 new table** (`cp_approval`) |

---

## 1. The blocking discovery — [VERIFIED] as fixed

`[GAP]` **There was no durable approval store, and there never had been.**

- `ApprovalLookup` is a port. Its only implementations in the repository were
  `NoApprovals` (fail-closed) and `_Approvals` — **an in-memory dict defined
  inside the Phase 9.9B harness** `[FACT]`.
- `DURABLE_TABLES` contained no approval table `[FACT]`.
- Phase 9.9C had to reach into a private attribute
  (`approvals._facts[id] = dataclasses.replace(..., bound_action_digest=...)`)
  because `grant()` had no way to bind an action digest at all `[FACT]`.

So CortexPrime's first governed write was authorized by an approval that existed
only in one process's memory. Fine for a harness; impossible for a product,
where a human approves in one request and the execution reads it back in
another.

`[VERIFIED]` `cp_approval` + `SqlApprovalRepository` implement the **existing**
port. They store and retrieve; they decide nothing. `ApprovalFacts.is_valid_for`
and the gateway's action-digest comparison are untouched. `request()` takes the
approval digest as a **required argument**, so nothing reaches into a private
field again.

`[VERIFIED]` It is installed through the **declared seam** —
`build_authorization(approvals=…)`, reached by a new
`build_governed_runtime(approvals_factory=…)` parameter that defaults to `None`
(unchanged, fail-closed, for every existing caller). Check A3 asserts the
runtime's lookup is the SQL repository and not a privately-assigned attribute.

---

## 2. Revocation — [VERIFIED], not BLOCKED

Phase 10.2 recorded revocation as NOT VERIFIED because Redis was absent. Part B
required it be settled before approval authority reached a UI.

`[VERIFIED]` A disposable Redis was provisioned and the **existing**
`token_blacklist` was used — no second revocation mechanism —
with `REVOCATION_FAIL_OPEN=false`:

| | Check | Result |
|---|---|---|
| B0 | Real Redis, **fail-closed** | `redis_connected=True, fail_open=False` |
| B1 | Valid token | decodes, carries the store-assigned tenant |
| B2 | Expired token (re-signed with the **real** key, so only the expiry is wrong) | rejected |
| B3 | Malformed token | rejected |
| B4 | Forged token (wrong signing key) | rejected |
| B5 | **Revoked token** | `before=False → after=True` |
| B5a | Revoking one token does not revoke the user's others | per-token, not a blanket lockout |
| N2 | A revoked token requesting an approval, through HTTP | **401** |
| B8/B9 | Membership re-resolved from the store at mint | server-side only |

### A real operational hazard found while proving this

`[VERIFIED]` The async Redis client is a module singleton **bound to the event
loop that created it**. A second `asyncio.run` gets a client whose loop is dead,
every call raises, and `is_jti_revoked` — correctly, in fail-closed mode —
answers "revoked" for *every* token. The first run of this harness took
authentication down completely that way.

That is the blacklist behaving as designed, and it is worth recording: **under
`REVOCATION_FAIL_OPEN=false`, a Redis client bound to a dead loop is a total
authentication outage.** The harness now uses one loop and resets the client
between them; a deployment should never switch loops under a live client.

---

## 3. Proposal and preview — derived, never invented `[VERIFIED]`

| | Check | Result |
|---|---|---|
| C2 | Capability, provider and operation | from the **commissioned** capability; a client cannot name one |
| C3 | Target | parsed from the investigation's own `incident_ref` |
| C4 | Classification | `irreversible_write` / `fixed` / `contained`, read from the contract |
| C5 | Reversibility | **False**, read from the contract, not inferred from the operation's name |
| C6/C7 | Approval digest | present, and **recomputed in the harness with the platform's own `canonical_approval_digest` and asserted equal** |
| C9 | A different workload | yields a **different** digest |

`[VERIFIED]` The preview carries capability + version + digest, provider, tenant,
environment, parameters, side-effect class, effect semantics, code trust,
isolation tier, reversibility, blast radius, autonomy ceiling, approval
requirement, both digests and evidence references. **The UI computes none of
them.**

---

## 4. The 9.9C negative matrix, re-run through the product path — [VERIFIED]

`[VERIFIED]` **38 cases. 0 cluster mutations.** Measured by **deployment
generation** read with the platform's *read* credential — never by a return
value, which was Phase 9.10's lesson.

Refusals are attributed rather than collapsed into "blocked":

| Stopped by | Cases |
|---|---|
| authentication | 3 |
| authorization | 5 |
| governance | 30 |

Covered: unauthenticated; revoked token; no tenant claim; wrong tenant;
cross-tenant read / decision / execution; execution of an unapproved action;
**18 authority fields smuggled in a body** (tenant, capability, provider,
namespace, workload, parameters, action digest, approval digest, risk,
side-effect class, code trust, isolation tier, blast radius, autonomy, forged
actor, `"admin"`, execution identity, secret injection); malformed request;
approval bound to a **different workload**, a wrong namespace digest, a tampered
digest, **no digest at all**, a different capability version, another tenant, a
different authorization operation; expired; withdrawn; denied; and direct
worker / connector / provider access.

`[VERIFIED]` Every mutation attempt at a governance route hits a route that
**does not exist**. Every provider-shaped path answers 404.

### The check that mattered most

`[VERIFIED]` **N28a: an approval bound to `billing-api`'s digest cannot restart
`payments-api`.** This is the exact hole 9.9C found, re-tested from a new
caller. It refused, with zero mutations.

### A defect this matrix found in my own endpoint

`[VERIFIED as fixed]` On the first full run, N28a reported **HTTP 200** with zero
cluster writes. Governance had refused correctly — but the writer returns a
refusal as an *outcome* (`succeeded=False`), not an exception, and the execute
endpoint returned 200 regardless. A refused action was indistinguishable from a
performed one to any client trusting the status code — precisely the "green tick
that means only HTTP 200" this phase forbids. The endpoint now inspects
`succeeded` and answers 409 with the refusal reason.

---

## 5. Action-digest security (Part P) — [VERIFIED]

`[VERIFIED]` Mutating **tenant**, **capability version**, **namespace**,
**workload**, **parameters** or the **digest itself** each invalidated the
approval and the chain refused. The payload is inside
`canonical_approval_digest`, so an approval for one target cannot authorize
another — asserted both by recomputation (C7/C9) and by execution (N28a–N28g).

---

## 6. One real provider write (Part L) — [VERIFIED]

`[VERIFIED]` A human requested, confirmed and approved one action through the
product API, and it ran through the existing chain:

| | Check | Result |
|---|---|---|
| G2 | Approver identity | `human:responder@p103.example`, from the **verified session** |
| G3 | Expiry | present; approvals cannot be granted without one |
| G4 | Wrong workload confirmation | **409** — checked against what the server stored |
| G5/G6 | Approval | granted, attributed to the authenticated human |
| G7 | A **second** decision on the same approval | **409** — one action, one judgement |
| G10 | Cluster | **exactly one deployment changed generation** |
| G11 | Target | the approved one; the bystander untouched |
| G12 | Identity, image, replica count | **unchanged** — a restart, not a redeploy |
| G13 | Pod | a **new pod identity** appeared |
| G19 | Approval | records which execution consumed it |

`[VERIFIED]` **`provider_writes = 1`.** A POST to the product API, to the
approval API or to the worker is not counted — only a mutation of Kubernetes.

---

## 7. Outcome and Assurance — [VERIFIED]

`[VERIFIED]` G9: the execute response **does not claim the world changed**. It
carries an execution reference and a note saying so explicitly. World status and
Assurance verdicts are absent from it by construction.

`[VERIFIED]` The outcome endpoint reads World state through an **independent**
World query and Assurance through the verification repository. Nothing is
derived from the worker's own reply. No percentage, no "guaranteed", no
fabricated verdict; an empty verdict list means Assurance has not ruled, and
says so.

---

## 8. Replay (Part Q) — [VERIFIED], and honestly variable

`[MEASURED]` **Two runs of this harness produced two different replay outcomes:**

- one run: replaying the same approval produced a **second cluster mutation**
  (`replay_provider_writes = 1`);
- another: the chain refused it (`HTTP 409`, `replay_provider_writes = 0`).

Both are recorded. **This is exactly why exactly-once is never claimed.** The
platform contract is **at-least-once**; `consumed_by_execution` records which
execution used an approval so a second use is *visible to an auditor*, and it is
deliberately **not** a guard — a store inventing exactly-once would be this
module overriding a platform contract it does not own.

`[VERIFIED]` H2: the approval still names the **first** execution that consumed
it; a later use does not overwrite that record.

---

## 9. Audit (Part S) — [VERIFIED]

`[VERIFIED]` I1: the approval is durably recorded with the human principal, the
tenant, the capability, **both digests**, and a decision timestamp.

`[VERIFIED]` I2: **no secret, token, credential or DSN** appears in any value of
the approval row.

`[VERIFIED]` I3/I4: the audit ledger recorded activity, carrying more than one
event kind — `execution_refused`, `execution_failed`, `execution_succeeded`.

### A false negative in my own leak check, and a silent deferral

- The leak check first scanned the row **including its keys**, so the column name
  `authorization_operation` matched a search for `authorization` and looked like
  a leaked header. Fixed to scan values only — the tempting "fix" would have
  been to delete the check.
- The audit assertion first queried `audit_record`; the real tables are
  `cp_audit_record` / `cp_audit_chain`. It therefore fell into its exception
  branch and reported **DEFERRED**. A check that silently defers because it was
  pointed at the wrong table proves nothing. It is now a real assertion.

---

## 10. Crash boundaries (Part R) — 2 VERIFIED, 10 DEFERRED

- `[VERIFIED]` **J1, before approval persistence:** a request that never reached
  the store leaves no approval, and `find` consults only the store.
- `[VERIFIED]` **J2, after approval persistence:** a PENDING row is not a grant.
  `"pending"` is not an `ApprovalOutcome` value, so `find` returns `None` and
  authorization fails closed — by construction, not by a check.
- `[DEFERRED]` **J3–J12** (before/after authorization, worker dispatch, provider
  write, World observation, Assurance). These were proven in Phase 9.10 against
  a real killed OS process. Re-manufacturing them here would corrupt the state
  this phase's audit assertions read. **Deferred, not claimed.**

---

## 11. Autonomy (Part J) — [VERIFIED]

`[VERIFIED]` No route, request model, hook or component can set, promote or
unlock an autonomy level. A frontend fitness test scans every workspace file for
`set*Autonomy`, `promote*Autonomy`, an autonomy literal assignment and
`unlock a3/a4`, and the approval screen has no `<select>` and no autonomy input.
Autonomy is rendered as a platform-set ceiling read from the proposal.

`[VERIFIED]` An unapproved action is refused (N8, 409) — an approval is an input
to the existing governance path, never an autonomy override.

---

## 12. Frontend security (Part T) — [VERIFIED]

`[VERIFIED]` The client **throws before sending** for any of 15 forbidden body
keys — tenant, capability, namespace, workload, digests, risk, side-effect
class, code trust, isolation tier, blast radius, autonomy, actor, `"admin"`,
execution reference. `fetch` is never called. It is not "ignored server-side"; it
cannot be expressed.

`[VERIFIED]` POST is restricted to an **enumerated allow-list of three paths**;
anything else throws. Server-side, every request model sets `extra="forbid"`, so
a hand-crafted request carrying an authority field is **rejected 422** rather
than accepted-and-ignored — an attempt to smuggle authority is visible in a log
instead of invisible in a success.

`[VERIFIED]` The session token remains an HttpOnly cookie the workspace cannot
read.

---

## 13. UI safety (Part U) — [VERIFIED]

`[VERIFIED]` The lifecycle has its own vocabulary — PROPOSED, AWAITING APPROVAL,
APPROVED, REJECTED, WITHDRAWN, EXPIRED, EXECUTING, OUTCOME ESTABLISHED,
VERIFIED, INSUFFICIENT EVIDENCE, REFUSED, FAILED — with **no success member at
all**. Tests assert:

- APPROVED explicitly is **not** executed;
- EXECUTING says the world state is **not yet established**;
- OUTCOME ESTABLISHED credits an **independent** observation, not the worker;
- VERIFIED is a separate stage from OUTCOME ESTABLISHED;
- REFUSED is "a decision, not a malfunction" and does not share FAILED's tone;
- FAILED says what reached the world is **UNKNOWN until observed**, and does not
  claim nothing happened;
- EXPIRED is distinct from REJECTED — "nobody changed their mind";
- **no stage emits a percentage, a confidence, "guaranteed" or "success".**

**No green tick means HTTP 200.** The execute response renders as EXECUTING with
the server's own note that the world change is established elsewhere.

---

## 14. Accessibility (Part V) — [VERIFIED structurally], [NOT VERIFIED] with assistive technology

`[VERIFIED]` Every stage name renders as **text**, so security meaning never
depends on colour. Inputs have labels; the confirmation input has
`aria-describedby`; the approve button is `disabled` until the typed workload
matches; failures use `role="alert"` and loading `role="status"` with
`aria-live`. Timestamps are explicit UTC with a named clock.

`[NOT VERIFIED]` **Not tested with an actual screen reader or a keyboard-only
pass.** The markup is semantic and the states are textual, but that is a
structural argument, not a measurement. **No accessibility certification is
claimed.**

---

## 15. Architecture (Part X) — one rule added, sensitivity-tested

`[VERIFIED]` **`BND-PRODUCT-CANNOT-BYPASS-EXECUTION` was added**, after
establishing the bypass is genuinely uncovered: `BND-DIRECT-HTTP` scopes to
bounded contexts and the credential fabric; `BND-PROVIDER-SDK` to connector
modules; the three `*-CANNOT-EXECUTE` rules each to their own plane. **None
names `backend/api/product`**, which did not exist when they were written. A
product module could have imported the gateway, dispatcher, an adapter, the
transport broker or the credential broker and dispatched around authorization
while every existing rule passed.

`[VERIFIED]` **Sensitivity-tested:** injecting
`from backend.platform.transport import broker` into a product route turned the
gate **FAIL** with a precise violation; removing it returned it to PASS.

### An existing rule caught this phase's own code

`[VERIFIED]` The regression failed on
`test_the_composition_root_is_the_only_module_importing_two_contexts`:
`remediation.py` imported both the `connectivity` and `execution` contexts.
That is a real violation and it was **fixed, not allow-listed** — the
authorization verb is now supplied by composition, and the module imports one
context.

---

## 16. Performance (Part W) — [MEASURED], no SLA

| | p50 | p95 |
|---|---|---|
| Remediation proposal | 693.2 ms | 2409.0 ms |
| Approval list | 131.6 ms | 511.8 ms |
| Approval detail | 254.7 ms | 998.1 ms |
| Complete governed execution | **7552.8 ms** (single sample) | — |

`[MEASURED]` These are from a **cold** host — every container had just been
restarted. An earlier warm run of the same harness measured proposal p50
**17.6 ms** / p95 21.8 ms, approval list p50 **18.1 ms**, approval detail p50
**17.0 ms**, execution **500.9 ms**. Both are reported because the spread is
real and averaging them would hide it.

**Measured / target / unknown:** *measured* — the above; *target* — **none, no
SLA is proposed**; *unknown* — behaviour under concurrency, over a network, and
approval-validation / Assurance latency as separate figures (they occur inside
one governed dispatch and are not separately instrumented).

---

## 17. Stop-condition audit — **PASS**

The frontend is not an approval authority (it posts a decision word; the store
and the gateway decide). The client controls no tenant and no digest. The
approval is digest-bound, not capability-only. Authorization does not bypass
approval — the gateway re-checks. Autonomy cannot be promoted by UI or model. No
second executor, no second approval authority, no direct provider access. No
secret reaches the frontend or durable product state. The outcome does not come
from the worker response. Assurance is displayed, never fabricated. Replay is
reported as at-least-once with both observed behaviours. **Every negative
produced zero cluster mutation.**

---

## 18. Known limitations

- `[MEASURED, not a defect]` **Replay behaviour varies between runs** (§8). The
  contract is at-least-once and this is what at-least-once looks like.
- `[DEFERRED]` **10 of 12 crash boundaries** (§10) — proven in 9.10, not
  re-proven here.
- `[NOT VERIFIED]` **Accessibility with assistive technology** (§14).
- `[NOT VERIFIED]` **Latency under concurrency or over a network.**
- `[UNCHANGED]` Authentication is still a single env-configured user; tenant
  membership comes from the file-backed `TenantManager`. Real multi-user
  identity and RBAC remain Phase 10.9.
- `[UNCHANGED]` Exactly one commissioned write capability exists
  (`kubernetes.workload.rollout_restart`), so the product proposes a remediation
  only for Kubernetes deployment subjects and says so rather than offering
  something that would be refused.
- `[UNCHANGED]` 5 pre-existing TypeScript errors and 1 pre-existing
  vitest/Playwright glob collision, in files this phase did not touch.
- `[ENVIRONMENTAL]` A host restart invalidated the disposable environment three
  ways: expired ServiceAccount tokens, a stopped PostgreSQL/Redis, and — the
  interesting one — **the k3d node IP moved from `172.29.0.3` to `172.29.0.2`
  while the worker's egress NetworkPolicy still allowed only the old address**,
  so the worker's own API-server call failed and it honestly reported
  `URLError`. The policy was doing its job; the allow-list was re-pointed as an
  operator action. Worth recording: the 9.11 egress allow-list is tied to a node
  address that a container restart can change.
