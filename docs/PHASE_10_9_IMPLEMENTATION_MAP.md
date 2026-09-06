# Phase 10.9 — Durable, Governed Tenant Membership
## Implementation Map (written BEFORE any code)

Every answer below was obtained by **calling** the real membership paths, not
by reading them. Two of the findings would have been missed by source review.

---

## 1. Discovery — where membership lives

| Question | Answer | Basis |
|---|---|---|
| Where is membership stored | `data/tenants/tenant_users.json` — **gitignored**. **16 tenants, 35 users today** | [VERIFIED] probe |
| Is there any durable membership table | **No.** 23 durable tables, none naming user, member, tenant or identity | [VERIFIED] |
| Is membership durable | **No** | [VERIFIED] |
| Is membership tenant-scoped | Yes, by lookup | [VERIFIED] |
| Is membership authoritative | Yes — and it is a JSON file | [VERIFIED] |
| Is membership mutable | Yes, by anyone who can open the file | [VERIFIED] |
| Does membership have an identity | `user_id` (`user-<hex>`), but **authority resolves by email** | [VERIFIED] §3 |
| Active/inactive state | `is_active` exists | [VERIFIED] |
| Role | `member` / `admin` / `owner` | [VERIFIED] |
| Can membership be deleted | **No delete method exists** — only `add_user` and `update_user_role` | [VERIFIED] |
| Can membership be deactivated | **No method exists.** `is_active` can only be changed by editing the file | [VERIFIED] |
| Can membership be self-created | Not directly; see §2 | [VERIFIED] |
| Is membership embedded in tokens | The tenant is; membership is not re-checked for product access | [VERIFIED] §2 |

### Other membership representations — searched, and none is usable

- **`iam_users`** (migration 0007) — has email, status, roles. **`IamUserRepository`
  has zero references anywhere in the repository; it is dead code.** It also has
  **no tenant column**, so it is a *user* table, not a membership. [VERIFIED]
- **`organizations`** — live (organization/department routes), but an
  organization is not a tenant and it carries no membership. [VERIFIED]
- No join table between users and tenants exists anywhere. [VERIFIED]

## 2. Two blocking findings, both proven by calling

### Finding 1 — cross-tenant membership mutation over a live route [VERIFIED]

`backend/api/tenant_routes.py` is **registered** (`router_registry.py:91`). It
takes `tenant_id` from the **path** and guards with `require_admin`, which
checks only a JWT `role == "admin"` claim **with no tenant scoping**.

With an admin token scoped to tenant A:

| Action against tenant **B** | Result |
|---|---|
| `POST /api/tenants/{B}/users` | **HTTP 201** — a member was planted |
| `PATCH /api/tenants/{B}/users/{id}` | **HTTP 200** — role changed to `owner` |
| `GET /api/tenants/{B}/users` | **HTTP 200** — full member disclosure |
| `POST /api/tenants/{B}/deactivate` | **HTTP 200** — tenant B deactivated |

This fires two stop conditions: *cross-tenant membership mutation is possible*
and *client controls tenant*.

**Severity, stated precisely.** Membership alone grants nothing after Phase
10.8 — approval, execution and issuance each need an explicit scoped grant. So
this is not privilege escalation into another tenant's actions. It **is**:
- a **cross-tenant denial of governance** — deactivating tenant B makes
  `resolve_scoped_authority` answer `tenant_inactive` for everyone in B, so
  every approval and execution in B stops;
- **disclosure** of another tenant's membership list;
- creation of principals in another tenant that B's own issuer could later
  grant.

### Finding 2 — product access does not check membership [VERIFIED]

`product_context` verifies the token's signature, revocation, tenant claim and
that the **tenant** is active. It never asks whether the subject is a member.

| Caller | `GET /api/v1/approvals` |
|---|---|
| Subject with **no membership at all**, valid tenant claim | **HTTP 200** |
| **Inactive** member | **HTTP 200** |
| Inactive member, `GET /api/v1/authority/grants` | **HTTP 200** — every grant in the tenant disclosed |

Part G requires that a disabled membership authorize no product access. Today
it does. Authority operations still refuse (`resolve_scoped_authority` reads
`is_active` live), so this is a **read** exposure, not an action one — but the
grant listing is exactly the reconnaissance an attacker wants.

## 3. Identity — already fixed by existing data, and must not change

`resolve_scoped_authority` resolves membership with
`get_user_by_email(principal_id)`, where `principal_id` is the JWT `sub`. Phase
10.8's `cp_authority_grant` rows already store that same value in
`subject_principal_id` and `issued_by` (e.g. `p108-issuer@cortexprime.test`).
Approval attribution separately uses `human:<subject>` (Phase 10.6).

Part C prefers "the existing namespaced human identity". The honest finding is
that **there are two conventions already in the data**, and the one membership
and grants share is the bare subject. Changing it now would rewrite the
references in every existing grant — which is a stop condition
(*historical identity is rewritten*).

**Decision:** membership keys on `subject_principal_id`, the same value grants
already use. The `human:` prefix stays where it already is, in approval
attribution. This inconsistency is **inherited, documented, and not fixed in
this phase** rather than papered over.

## 4. Role semantics — informational, and staying that way [VERIFIED]

In the governed path `member.role` is only ever *carried* — `ApproverAuthority.
membership_role`, for reporting. It is never compared, and no decision reads
it. (`backend/auth/rbac.py` has a role→permission table, but Phase 10.5 found
it reads the wrong JWT claim and is inert.)

Phase 10.5 established that a tenant **owner is not an approver**. Part H
requires preserving that. **Role remains informational; no role maps to
approve, execute or issue.**

## 5. STOP — a new table is necessary (Part B)

No durable membership representation exists; `iam_users` is dead and
tenant-less; `organizations` is a different concept. Reuse is impossible, not
merely inconvenient.

**Decision:** one new table, `cp_tenant_membership`, migration `0021`.

**No duplicate user or tenant concept is created**: the table stores the
*relation* (subject ∈ tenant) plus its state, and nothing else. It defines no
user record, no credentials and no tenant record.

## 6. Who may administer membership (Part F)

Part F forbids assuming owner/admin/operator suffices — and Phase 10.5 already
proved an owner is not an approver.

The existing authority model is **capability-scoped** grants. Membership is not
capability-scoped, so strictly **the existing model cannot express membership
administration**. That is an honest gap.

**Decision, with its rationale:** membership administration requires **holding
at least one live `issue` grant in this tenant** — a presence check against the
Phase 10.8 store, not a scoped match against a capability (which would force an
arbitrary capability into a question that has none).

Why this and not a fourth action: an issuer already holds the strictly more
dangerous power — creating approval and execution authority. A member-admin who
could not issue grants could still create the principals that grants attach to.
Reusing `issue` adds **no new authority, no new action, and no new escalation
surface**, which Part AB requires.

**Limitation, stated:** admission and issuance are not separable today. A
deployment wanting a member-admin who cannot issue grants cannot express that.

## 7. Digest / version (Part P) — deliberately none

Part Q is explicit: *"Do not claim tamper detection if membership is
intentionally mutable"* and *"do not confuse database mutability with security
failure."*

Membership **is** intentionally mutable: activating, deactivating and changing
a role are legitimate operations. A digest over mutable state would be
recomputed by every legitimate change and would prove nothing. Phase 10.8's
grant digest works precisely because a grant's authority-bearing fields are
**immutable after issuance**.

**Decision: no membership digest.** Integrity comes from the audit trail (who
changed what, when) rather than from a hash of a field designed to change.
Concurrency uses conditional `UPDATE`s, as Phase 10.8's revoke does.

## 8. Design — what will be built

**`cp_tenant_membership`** (migration 0021):

| Column | Why |
|---|---|
| `membership_id` PK | stable identity, independent of the subject string |
| `tenant_id`, `subject_principal_id` | the relation; unique together |
| `status` | `active` / `inactive` — **never deleted**, so historical grants stay attributable (Part J) |
| `role` | informational only, preserved from the JSON model |
| `created_at`, `created_by` | attribution, as Phase 10.8 established |
| `updated_at`, `updated_by` | who last changed the state |
| `source` | `migrated` or `issued` — so a bootstrap-imported row is distinguishable from an admitted one |

**`backend/auth/membership.py`** — admission, activation, deactivation and role
change, in the module family already fenced by `BND-AUTH-CANNOT-EXECUTE`.

**Enforcement changes:**
- `resolve_approver_authority` and `resolve_scoped_authority` read membership
  from the durable store instead of the JSON file.
- `product_context` requires an **active membership**, closing Finding 2.

**V1 route repair (Finding 1):** `tenant_routes` membership mutation must stop
being a cross-tenant path. The tenant will be taken from the authenticated
token and the path tenant compared against it, refusing a mismatch.

**Migration (Part AA):** a deterministic import of all 35 memberships,
preserving subject, tenant, active state and role, and creating **no** grants,
approvals or execution rights. Afterwards the JSON file is bootstrap input
only — proven by editing it and showing authorization is unchanged.

## 9. What will NOT be built

No second membership store, no `MembershipAuthority`, no RBAC2, no invitation
engine, no role→authority mapping, no membership digest, no new capability, no
expiry invention, no claim of exactly-once.

## 10. Risks accepted

1. Moving membership under Phases 10.5–10.8 is as load-bearing as 10.8's move
   of authority. All prior harnesses will be re-run.
2. **Tenant records themselves remain in JSON.** Only membership moves.
   `require_tenant` still reads tenant existence and activity from the file.
   This is a real remaining gap and will be reported as a limitation — the
   cross-tenant *deactivation* path is closed regardless, since that was an
   authorization defect rather than a storage one.
3. The bootstrap problem recurs: the first membership in a new tenant is
   imported or provisioned out of band, as the first grant was in 10.8.
