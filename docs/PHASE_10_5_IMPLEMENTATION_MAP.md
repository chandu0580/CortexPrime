# Phase 10.5 — Implementation Map

**Written before implementation.** Part A requires the existing RBAC substrate be
inspected first; this records what was found, what will be reused, and the one
thing that must not be invented.

Labels: `[FACT]` read from this repository, `[DECISION]`, `[GAP]`.

---

## 1. Part A — the eleven discovery questions, answered from the code

| # | Question | Answer |
|---|---|---|
| 1 | What RBAC already exists? | `backend/auth/rbac.py` — 52 lines: a `PERMISSIONS` dict, `check_permission(role, action, resource)`, and a `require_permission` dependency `[FACT]` |
| 2 | What roles exist? | Tenant roles `member` / `admin` / `owner` in `PERMISSIONS`; separately a top-level JWT `role` claim that login hardcodes to `"operator"` `[FACT]` |
| 3 | How is role membership stored? | `TenantUser.role` in `TenantManager`, file-backed under `data/tenants`, round-tripped through `_save` / `_load` `[FACT]` |
| 4 | Are roles tenant-scoped? | **Yes.** A `TenantUser` belongs to exactly one tenant `[FACT]` |
| 5 | Are permissions tenant-scoped? | `TenantUser.permissions` is a per-user, per-tenant list — and it **round-trips durably** `[FACT]` |
| 6 | Is there a reusable permission vocabulary? | Yes: `action × resource` (`read`/`write`/`admin` × `projects`/`missions`/…) `[FACT]` |
| 7 | Does "approve" exist as a permission? | **No.** `[GAP]` |
| 8 | Does approval scope exist? | **No.** `[GAP]` |
| 9 | Is role assignment authoritative or V1 UI state? | **Authoritative.** `TenantManager` is what `require_tenant` consults and what Phase 10.2 wired into login; `update_user_role` already exists `[FACT]` |
| 10 | Does approver authority need a new table? | **No.** `[DECISION]` `TenantUser.permissions` is the substrate |
| 11 | Can the existing model be reused safely? | **Partly — with two hazards, below** |

---

## 2. Two hazards in the existing RBAC `[FACT]`

**Hazard 1 — it reads the wrong claim.** `require_permission` checks
`user.get("role")`, which is the top-level JWT claim (`"operator"`), not
`user_role`, which is where Phase 10.2 puts the tenant membership role.
`"operator"` is not a key in `PERMISSIONS`, so `check_permission` returns
`False` for it — the existing RBAC helper is effectively inert for the tokens
this platform issues, and is used in exactly **one** place in the whole backend.

**Hazard 2 — `owner` holds wildcards.** `read`, `write` and `admin` are all
`["*"]` for `owner` `[FACT]`. A permission granted through a wildcard is exactly
the "generic permission that effectively bypasses the approval system" Part C
forbids.

`[DECISION]` Approve authority is therefore **not** derived from a role
wildcard. `PERMISSIONS[role].get("approve", [])` returns `[]` for every existing
role, so no wildcard in another action can leak into it — and the harness
asserts that, rather than assuming it.

---

## 3. The role model `[DECISION]`

`[DECISION]` **Approver authority is an explicit permission grant on the tenant
membership**, not a role swap.

- `TenantUser.role` is a **single** field. Making approval a role would force an
  owner who needs to approve to stop being an owner. `[CONSEQUENCE]` avoided.
- `TenantUser.permissions` already exists, is already tenant-scoped, and is
  already durable — and is currently **dead state consulted by nothing**
  `[FACT]`. This gives it the one meaning it should have had.

The grant is the single string `approve:remediation`. It means exactly:

> may make a decision on an existing approval request in this tenant

`[DECISION]` It does **not** mean "may execute". Execution stays behind the
existing execute route, the existing gateway and the existing worker; nothing in
this phase touches them. No `SUPER_ADMIN`, no `ADMIN_OVERRIDE`, no wildcard.

`[DECISION]` **A tenant owner is not automatically an approver.** That is the
point: the phase exists because tenant membership was sufficient, and an owner
is a tenant membership.

---

## 4. Revocation is why authority is read from the store, not the token `[DECISION]`

`[FACT]` Phase 10.2 mints the tenant membership role into the JWT as
`user_role`. A check against that claim would keep honouring a revoked grant
until the token expired — a real revocation window.

`[DECISION]` **Approver authority is resolved live from `TenantManager` at
decision time.** The token establishes *who* and *which tenant*; the store
establishes *what they may do*. Revocation therefore takes effect on the next
request, and the harness proves it with a token minted **before** the revocation.

`[CONSEQUENCE]` One store read per decision and per queue projection. Accepted:
the alternative is a documented window during which a removed approver can still
authorize an irreversible write.

---

## 5. Separation of duties — Part G, answered from the code `[FACT]`

Separation of duties **exists and is enforced**, for a different pair:
`policy.py:199` denies `grants_availability` when `principal_is_owner` —
"whoever proposes a capability must not be the one who makes it live" — with a
dedicated `DenialReason.SEPARATION_OF_DUTIES`.

`[FACT]` There is **no rule anywhere that a remediation requester must not be
its approver.** `cp_approval` stores `requested_by` and `decided_by` as distinct
columns, so the distinction is *representable*, but nothing enforces it.

`[DECISION]` **This phase does not invent one.** Part G is explicit: if the
contracts do not require separation, do not add a policy silently. Both cases
are tested and the result is reported as
**SUPPORTED-BY-CURRENT-POLICY (self-approval permitted)**, recorded as a named
limitation with the existing precedent, and recommended as its own phase.
Enabling *or* disabling it silently is a declared stop condition.

---

## 6. What is added

### Backend

```
backend/auth/approver.py            (new: resolve approver authority, live, fail-closed)
backend/auth/rbac.py                (modified: the approve action joins the one vocabulary)
backend/auth/tenant.py              (modified: grant_permission / revoke_permission)
backend/api/product/context.py      (modified: authority on the product context)
backend/api/product/approval_routes.py (modified: the check, before the decision)
backend/api/product/approval_queue.py  (modified: can_approve projection)
backend/api/product/schemas.py      (modified: can_approve / authority fields)
```

`[DECISION]` **No new route.** The decision still goes to
`POST /api/v1/approvals/{approval_id}/decision`. The product's non-GET routes
stay exactly the three from Phase 10.3, and the harness asserts it.

### Frontend

```
frontend/components/investigator/ApprovalQueue.tsx (modified: render the server's verdict)
frontend/lib/investigator/types.ts                 (modified)
frontend/tests/investigator/queue.test.tsx         (modified)
```

`[DECISION]` `can_approve` is **presentation only**. The frontend never decides
it, and the harness proves the API refuses a non-approver whatever the browser
believes.

### Harness

```
scripts/phase105_approver_authority_harness.py
```

---

## 7. Order of checks, and it is fail-closed at every step

```
authenticate (existing)
  → tenant from the verified token (existing)
  → membership + APPROVER authority, read LIVE from the store   ← new
  → resolve the approval under the authenticated tenant (existing)
  → still actionable / not expired / not revoked (existing)
  → the existing approval authority decides (existing)
```

`[DECISION]` The new step is inserted **before** the decision and adds nothing
after it. It cannot execute, mint an approval, alter a digest, compute risk or
autonomy, bind a capability, reach a provider or touch a credential.

---

## 8. Invariants this phase must not break

1. One approval authority, one execution authority, one governance authority.
2. Approver identity and tenant come only from the verified session.
3. Authority is read from the authoritative store, never from a client claim.
4. Revocation is fail-closed and takes effect on the next request.
5. No wildcard grants approval.
6. The queue projects authority; it stores none.
7. Provider writes stay at 0 for every negative case.
8. No new capability is commissioned; `rollout_restart` remains the only one.
