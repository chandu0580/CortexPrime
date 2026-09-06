# Phase 10.5 — Verification Report

**Phase:** Approver authority / governed RBAC
**Date:** 2026-09-06
**Branch:** `phase-1-foundation`
**ADR:** ADR-098
**Map:** `docs/PHASE_10_5_IMPLEMENTATION_MAP.md`
**Harness:** `scripts/phase105_approver_authority_harness.py`

Labels: `[VERIFIED]`, `[NOT VERIFIED]`, `[DEFERRED]`, `[BLOCKED]`.

---

## Result: **VERIFIED**

| | Result |
|---|---|
| Product harness | **131/131, exit 0, VERIFIED** |
| Negative matrix | **39 cases, 0 provider writes** |
| Positive path | **1 real provider write**, the already-commissioned capability |
| Architecture gate | **PASS** — 37 passed, 0 failed, 6 skipped, 1194 modules |
| Backend regression | see §15 |
| Frontend tests | **106/106** |
| Migrations / new tables | **0 / 0** |
| New authorities | **none** — one approval, one execution, one governance authority |
| New roles | **none** — an explicit **grant**, not a role |

---

## 1. Part A — the eleven discovery questions `[VERIFIED]`

| # | Question | Answer |
|---|---|---|
| 1 | What RBAC exists? | `backend/auth/rbac.py`, 52 lines: a `PERMISSIONS` dict, `check_permission`, `require_permission` |
| 2 | Roles? | `member` / `admin` / `owner`, plus a separate top-level JWT `role` claim login hardcodes to `"operator"` |
| 3 | Storage? | `TenantUser.role` in `TenantManager`, file-backed, round-tripped through `_save`/`_load` |
| 4 | Tenant-scoped roles? | **Yes** |
| 5 | Tenant-scoped permissions? | `TenantUser.permissions` exists per membership and **is durable** |
| 6 | Permission vocabulary? | `action × resource` |
| 7 | Does "approve" exist? | **No** `[GAP]` |
| 8 | Approval scope? | **No** `[GAP]` |
| 9 | Authoritative or V1 UI state? | **Authoritative** — it is what `require_tenant` consults and what 10.2 wired into login |
| 10 | New table needed? | **No** |
| 11 | Reusable safely? | **Partly — two hazards** |

### The two hazards `[FACT]`

1. **The existing RBAC reads the wrong claim.** `require_permission` checks
   `user["role"]` — the top-level claim, `"operator"` — not `user_role`, where
   the tenant membership role lives. `"operator"` is not a key in `PERMISSIONS`,
   so the helper denies everything, and it is used in exactly **one** place in
   the backend. It was inert for the tokens this platform issues.
2. **`owner` holds wildcards** — `read`, `write` and `admin` are all `["*"]`.

`[VERIFIED]` **A3: no wildcard confers approval.** Asserted directly:
`check_permission(role, "approve", resource)` is False for every combination of
`member`/`admin`/`owner` × `remediation`/`*`/`anything`. **A2:** no role carries
an `approve` action at all.

---

## 2. The model — a grant, not a role `[VERIFIED]`

`[DECISION]` Approver authority is the explicit grant `approve:remediation` on
the **tenant membership**, stored in `TenantUser.permissions` — a field that
already existed, was already durable and tenant-scoped, and **was consulted by
nothing**. This gives it the one meaning it should have had.

Not a role, because `TenantUser.role` is a single field: making approval a role
would force an owner who needs to approve to stop being an owner.

`[VERIFIED]` It means **only** "may decide an existing approval request in this
tenant". It confers no execution: the execute route, the gateway and the worker
are untouched, and `A5` asserts from the module's **parsed imports and calls**
(not its prose) that the authority module cannot execute, dispatch, mint an
approval, compute risk or autonomy, or reach a provider or credential.

`[VERIFIED]` **A4: no new table.** 22 durable tables, unchanged since 10.3.
`[VERIFIED]` **A1: no new route.** The product's non-GET routes are still
exactly the three from Phase 10.3.

---

## 3. The distinction the phase exists to make `[VERIFIED]`

| | Who | Result |
|---|---|---|
| B1 | The approver | **permitted** |
| B2 | A plain tenant member | **denied** — `no_approver_authority` |
| B3 | A tenant **owner** | **denied** — an owner is a membership, and membership is exactly what stopped being sufficient |
| B4 | An approver in **another tenant** | **denied** — `membership_in_another_tenant` |

`[VERIFIED]` Confirmed live over HTTP: approver, plain member and tenant owner
all see the **same three rows**, and only the approver has
`viewer_can_approve: true`.

---

## 4. Role assignment `[VERIFIED]`

`[VERIFIED]` **B5: the grant is durable** — a fresh `TenantManager` over the
same store still sees it. **B6: granting is idempotent** — a repeated
administrative action does not produce a duplicate nobody can revoke.
**B7: a malformed permission is refused** — there is no bare `"godmode"` to
grant; a grant must be a namespaced `action:resource`.

`[VERIFIED]` **R39: there is no HTTP route that grants a role.** `/api/v1/roles`,
`/api/v1/permissions` and `/api/v1/approvals/grant-role` do not exist. A user
cannot select their own role, a frontend cannot claim one, and no admin backdoor
was created.

---

## 5. Revocation — the check that a token-based design would fail by accident `[VERIFIED]`

`[DECISION]` Authority is resolved **live from the store on every request**. The
token establishes *who* and *which tenant*; the store establishes *what they may
do*.

| | Check | Result |
|---|---|---|
| E1 | Before revocation | may decide |
| E2 | Grant revoked in the store | yes |
| E3 | **The same token, minted before the revocation** | **403, 0 provider writes** |
| E4 | The queue, same token | `can_approve: false`, `no_approver_authority` |
| E5 | Window | **one request** — there is no cached-claim window, because no claim is consulted |
| E6 | The approval | **still pending** — a refused decision decides nothing |

`[VERIFIED]` **R6/R7 make the same point from the other side:** a token whose
`user_role` claim says `owner` changes nothing. For a genuine approver the
decision succeeds because the *identity* is an approver; for a plain member
holding a token claiming `role=admin, user_role=owner` it is **refused 403**. A
role claim is not authority.

---

## 6. Authority is evaluated at decision time `[VERIFIED]`

| | Check | Result |
|---|---|---|
| F1 | Not an approver → decide | **403**, 0 writes |
| F2 | Grant, then the **same person on the same approval** | **200, granted** |
| F3 | Revoke, then decide again | **403** |

---

## 7. Requester vs approver — Part G/P, reported not invented

`[FACT]` **Separation of duties exists and IS enforced — for a different pair.**
`policy.py:199` denies `grants_availability` when `principal_is_owner`: a
capability owner may not be the one who makes it live, with a dedicated
`DenialReason.SEPARATION_OF_DUTIES`.

`[FACT]` **No rule anywhere requires a remediation requester to differ from its
approver.** `cp_approval` stores `requested_by` and `decided_by` separately, so
the distinction is *representable*; nothing enforces it.

**Result: `requester == approver` is SUPPORTED-BY-CURRENT-POLICY.**

- `[VERIFIED]` **G1:** self-approval succeeds (HTTP 200).
- `[VERIFIED]` **G2:** requester ≠ approver also succeeds — the distinction is
  not a gate in either direction.
- `[VERIFIED]` **G3:** the precedent exists and is enforced elsewhere.
- `[DEFERRED]` Enforcing it. Part G is explicit that a policy the contracts do
  not require must not be added silently, and doing so *or* forbidding it
  silently is a declared stop condition. **Recommended as its own phase.**

---

## 8. The positive path `[VERIFIED]`

| | Check | Result |
|---|---|---|
| C1/C2 | An approver approves / rejects | 200, `granted` / `denied` |
| C3 | Approver identity | `human:approver-a@p105.example` — namespaced, **never `"admin"`** |
| C4 | **The authority used is recorded** | `authority=approver_authority_granted` on the decision |
| C5 | Tenant on the record | the authenticated one |
| C6 | Execution | **exactly one deployment mutated** — the only commissioned capability |
| C7 | The canonical approval digest | **unchanged** by the decision and the execution |
| C8 | Consumption | recorded |

`[VERIFIED]` **No new capability was commissioned.**
`kubernetes.workload.rollout_restart` remains the only one.

---

## 9. The queue projects authority; it invents no state `[VERIFIED]`

| | Check | Result |
|---|---|---|
| D1 | Approver | `can_approve: true` |
| D2 | Plain member, same approval | `can_approve: false` |
| D3 | Tenant owner | `can_approve: false` |
| D4 | **`actionable` and `can_approve` are two fields** | `actionable: true`, `can_approve: false` |
| D5 | The reason is attributed | `no_approver_authority`, not generic |
| D6 | A non-approver's queue | rows visible, **`viewer_can_approve: false`** |
| D8 | The projection stores nothing | derived on every read |

`[VERIFIED]` **D4 is the one that matters.** Collapsing the two would make
"you may not decide this" and "nobody may decide this" indistinguishable, and a
responder who cannot tell them apart cannot tell whether to find a colleague or
let it expire.

`[VERIFIED]` Rows are **not hidden** from a non-approver. Hiding them would leave
a member unable to see what is waiting and unable to distinguish a permission
boundary from a tenant one.

---

## 10. Concurrency `[VERIFIED]`

| | Case | Result |
|---|---|---|
| H1 | Two approvers, approve / approve | **`[200, 409]`** |
| H2 | Two approvers, approve / reject | **`[200, 409]`** |
| H1/H2 | Stored | one outcome, one decider |
| H3 | Mechanism | the existing conditional `UPDATE … WHERE outcome = 'pending'` |

`[VERIFIED]` **No distributed lock introduced.** No double execution.

---

## 11. Negative matrix `[VERIFIED]`

`[VERIFIED]` **39 cases, 0 provider writes**, measured by cluster generation.
Refusals attributed rather than collapsed:

| Stopped by | Cases |
|---|---|
| role authorization | 27 |
| approval state | 7 |
| authentication | 2 |
| membership | 1 |
| governance | 1 |
| role authorization (claim ignored) | 1 |

**The headline case is a real one:** R1 is a genuine tenant member, with a valid
session, on a real pending approval **in their own tenant**. The only thing
missing is authority — so the refusal cannot be explained by anything else. It
is 403 and the response names `no_approver_authority`.

Also covered: a tenant owner; an approver from the wrong tenant (404 — not
theirs to see); anonymous; a token with no tenant claim; a member holding a
token claiming `role=admin, user_role=owner`; **22 authority fields smuggled in
a decision body** (approver, role, tenant, tenant_id, actor, actor_ref,
can_approve, authority_reason, permissions, capability, provider, namespace,
workload, both digests, risk, blast radius, autonomy, code trust, isolation
tier, secret injection, extra authority field) — **all 422, rejected rather than
ignored**; tenant and role in **query parameters**; tenant, role and approver in
**headers**; already-approved, already-rejected, consumed, expired and revoked
approvals; wrong and malformed approval ids; and direct worker / provider /
credential / role-grant routes, none of which exist.

---

## 12. Frontend `[VERIFIED]`

`[VERIFIED]` `can_approve` is **presentation only**. The component renders the
server's verdict and computes nothing; the decision route re-resolves the same
authority from the same store and enforces it. R1 proves the API refuses a
non-approver whatever the browser believes.

`[VERIFIED]` A caller without authority is told **plainly** — *"You do not have
approval authority in this tenant"* — with the server's reason code, on both the
queue and the detail screen, and offered **no decision form at all** (the
buttons are absent, not disabled). The queue banner states that authority "is
not implied by membership" and that nothing on the page can grant it.

`[VERIFIED]` No control anywhere could grant, elevate, override or request
authority — asserted by role-based queries for buttons and links, not by
matching the word (the banner legitimately explains that authority *is granted
by an administrator*).

`[VERIFIED]` No `Admin`, `Superuser` or `Override` shortcut exists.

---

## 13. Audit `[VERIFIED]`

| | Check | Result |
|---|---|---|
| K1 | Actor, tenant, capability, both digests, decision, time | all present |
| K2 | **The authority used** | `authority=…` recorded on every decision |
| K3 | Secrets | none — no token, DSN, password, or even the raw grant string |
| K4 | `"admin"` | no decision is attributed to it |

`[VERIFIED]` K2 is the point: an audit trail that says *who* decided but not
*what entitled them to* cannot answer the question it exists for.

---

## 14. Restart `[VERIFIED]`

`[VERIFIED]` **J1:** a fresh tenant manager still sees the approver grant.
**J2:** and still sees that the revoked member does **not** — revocation
survived. **J3:** authority resolves identically after the restart. **J4:** the
decision survives. **J5:** an approval that was only ever *refused* is **still
pending** — no approval becomes granted because of a restart.

---

## 15. Gates

- `[VERIFIED]` **Architecture gate PASS** — 37 passed, 0 failed, 6 skipped,
  1194 modules.
- **Backend regression** — see the final report line.
- `[VERIFIED]` **Frontend 106/106.**

### One fitness rule added, because a real bypass was measured (Part R)

`[VERIFIED]` **`BND-AUTH-CANNOT-EXECUTE`.** Before adding it, the bypass was
**measured, not assumed**: injecting
`from backend.platform.transport import broker` into
`backend/auth/approver.py` left the gate **PASS**.
`BND-PRODUCT-CANNOT-BYPASS-EXECUTION` scopes to `backend/api/product`;
`BND-DIRECT-HTTP` to the bounded contexts; the `*-CANNOT-EXECUTE` rules each to
their own plane. **None names `backend/auth`.**

That matters more than it looks: authorization code runs before every governed
decision, holds the caller's identity, and is where a reviewer least expects a
side effect. A module answering "may this person approve?" that could also reach
a gateway would decide and act in one breath.

`[VERIFIED]` **Sensitivity-tested**: with the import injected the gate FAILs
naming `backend.auth.approver:1`; removed, it returns PASS.
`backend.infrastructure.redis` is deliberately **not** forbidden — the token
blacklist needs it, and reading a revocation list is not executing.

---

## 16. Performance `[MEASURED]`, no SLA

| | p50 | p95 |
|---|---|---|
| Queue list, with authority | **268.5 ms** | **350.7 ms** |
| Queue detail, with authority | **36.0 ms** | **47.8 ms** |
| Filtered queue | **292.0 ms** | **424.3 ms** |
| Approve decision | **36.1 ms** | 43.2 ms |
| Reject decision | **40.0 ms** | 46.5 ms |

`[MEASURED]` Authority resolution adds one tenant-store read per request. Queue
list is within noise of Phase 10.4's 230.6 ms on the same hardware; the cost is
dominated by the per-row investigation replay recorded there, not by this check.
**No index was added.**

`[DEFERRED]` Decision p95 is from 6 samples — each decision consumes a pending
approval, so a larger sample would measure seeding as much as deciding.

---

## 17. Accessibility `[VERIFIED structurally]`, `[NOT VERIFIED]` with assistive technology

`[VERIFIED]` The authority state is **text**, not colour: "You do not have
approval authority in this tenant", plus a machine reason code, in a
`role="note"` region. The row marker reads "you cannot approve". Controls are
labelled; the confirmation input keeps its `aria-describedby`; filters remain a
labelled group with `aria-pressed`; timestamps are explicit UTC. A caller
without authority sees **no disabled button to puzzle over** — the form is
absent, with a sentence saying why.

`[NOT VERIFIED]` Not tested with a screen reader or keyboard-only pass. **No
certification claimed.**

---

## 18. Stop-condition audit — **PASS**

Tenant membership is no longer sufficient. The frontend cannot grant itself
authority (there is no control, and the API refuses regardless). Role never
comes from client input. A stale token cannot approve after revocation — the
window is one request, because no claim is consulted. The queue creates no
second approval authority. The role check runs **before** the existing approval
validation and replaces none of it. The action cannot be edited; both digests
are unchanged. The grant confers no execution. No model influences
authorization. No direct provider or worker access. No secrets in the frontend
or in durable RBAC state. Self-approval semantics were **reported, not silently
changed**. Exactly-once is not claimed.

---

## 19. Known limitations

- `[DEFERRED]` **Self-approval is permitted** (§7). Reported, not changed. The
  single most valuable next constraint.
- `[NOT VERIFIED]` **Execution authority was not narrowed.** Triggering the
  execute route still requires only tenant membership plus a granted approval.
  Defensible — it can run only the exact digest-bound action an authorized
  approver approved, and the gateway re-checks everything — but it is a real
  gap and is named here rather than implied to be covered.
- `[NOT VERIFIED]` **Scope is tenant-wide.** An approver may decide **any**
  approval in their tenant. Finer scope (per capability, environment, risk or
  side-effect class) does not exist in the primitives today; Part D says
  document the limitation rather than pretend to granularity the system cannot
  enforce. With one commissioned capability this is currently a distinction
  without a difference — that stops being true the moment the catalogue grows.
- `[NOT VERIFIED]` **Accessibility with assistive technology.**
- `[UNCHANGED]` Authentication is still a single env-configured user; identities
  are memberships in a file-backed store. A real identity provider is not here.
- `[UNCHANGED]` The queue costs one investigation replay per returned row.
- `[UNCHANGED]` 5 pre-existing TypeScript errors and 1 pre-existing
  vitest/Playwright glob collision, in files this phase did not touch.
