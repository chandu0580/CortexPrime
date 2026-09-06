# Phase 10.10 — Durable, Governed Tenant Records
## Implementation Map (written BEFORE any code)

Every answer was obtained by **calling** the real tenant paths. Two findings
would have been missed by source review, and both are routes Phase 10.9's fix
did not reach.

---

## 1. Discovery — where tenants live

| Question | Answer | Basis |
|---|---|---|
| Where are tenants stored | `data/tenants/tenants.json` — gitignored | [VERIFIED] |
| Is there a durable tenant table | **No.** 24 durable tables; the only match is `cp_tenant_membership` | [VERIFIED] probe |
| Is tenant state on the governed path | **Yes.** `require_tenant` reads the file and checks `is_active`; so do `resolve_approver_authority` and `resolve_scoped_authority` | [VERIFIED] |
| Who creates tenants | **Any V1 `role=admin` JWT**, via `POST /api/tenants` | [VERIFIED] §2 |
| Who deactivates tenants | Same admin claim, via `POST /api/tenants/{id}/deactivate` (tenant-scoped since 10.9) | [VERIFIED] |
| Who reads tenants | `require_tenant`, `auth_routes`, all V1 tenant routes, both authority resolvers | [VERIFIED] |
| Is tenant identity durable | **No** | [VERIFIED] |
| Is tenant identity immutable | `tenant_id` is never rewritten by any method | [VERIFIED] |
| Is slug mutable | **No mutation path exists** — `TenantManager` has no update method for it | [VERIFIED] probe §6 |
| Can a tenant be deleted | **No delete method exists** — deactivation only | [VERIFIED] probe §7 |
| Does membership depend on tenant existence | Yes — `require_tenant` gates every product request | [VERIFIED] |
| Do authority/approval/execution depend on it | Yes — both resolvers refuse `tenant_inactive` | [VERIFIED] |
| Is JSON the only tenant source | **Yes** | [VERIFIED] |

## 2. Two findings, both proven by calling

Phase 10.9 guarded five V1 routes that name a tenant in their path. **Two
routes have no tenant in the path, so the guard never applied.**

### Finding 1 — every tenant in the system is disclosed to any admin [VERIFIED]

```
GET /api/tenants  → HTTP 200
   ['p1010a', 'p1010b', 'p1010c']
```

An admin token scoped to tenant A receives the **full system-wide tenant list**
— id, slug, domain, plan, state. That is cross-tenant disclosure, and it is the
map an attacker uses to pick the next target.

### Finding 2 — any admin can create a tenant [VERIFIED]

```
POST /api/tenants  → HTTP 201   → tenants: [... 'planted-by-a']
```

Tenant creation is an unscoped V1 admin operation with no relationship to the
governed authority model at all.

## 3. Is `organizations` the tenant concept? — No [VERIFIED]

Part B requires proving semantic equivalence before reuse. It fails:

- `OrganizationModel` has **no `tenant_id`**, no membership, and no relationship
  to any authority, approval or execution record. [VERIFIED — grep of the model
  and `department.py` finds no tenant reference]
- It models an org-chart entity with departments, served by
  `organization_routes` — a directory feature, not an authorization boundary.

**They are different concepts and stay separate.** Renaming or overloading it
because the words look similar is exactly what Part B forbids.

`iam_users` was already dismissed in Phase 10.9: zero references, no tenant
column, dead code.

## 4. STOP — a new table is necessary (Part A / Part B)

No durable tenant representation exists; `organizations` is a different concept;
`cp_tenant_membership` stores the relation, not the boundary.

**Decision:** one new table, `cp_tenant`, migration `0022`.

## 5. Who may administer tenants (Parts M and N) — out-of-band, preserved

The existing authority grammar is **capability + environment** scoped. A tenant
is neither. There is therefore **no existing authority that can express "may
create a tenant"**, and Part M forbids inventing one:

> *Do NOT invent an authority action merely to make the product convenient.*

Phase 10.8 already established that no role confers authority, so the V1
`role=admin` claim is not an answer either.

**Decision: tenant creation, activation and deactivation remain
bootstrap/out-of-band**, exactly as Part N contemplates. There will be **no
product route** for them, and `bootstrap_tenant` is the provisioning path — the
same shape as `bootstrap_grant` (10.8) and out-of-band membership seeding
(10.9). No system creates its own root boundary.

### What happens to the V1 routes

Once the durable store is authoritative, a V1 route that writes the JSON would
silently do nothing — a trap worse than the hole. So:

- `POST /api/tenants` (create) and `POST /api/tenants/{id}/deactivate` become
  **refusals** naming where tenant administration actually happens. They are
  not repointed at the durable store, because that would hand tenant-state
  authority to an unscoped admin claim over a now-authoritative store — worse
  than today.
- `GET /api/tenants` returns **only the caller's own tenant**, closing
  Finding 1.

## 6. Tenant is not authority, and not membership (Parts F, G, H)

A tenant row means one thing: **an authoritative organizational boundary
exists.** It confers no approval, execution, issuance or autonomy — those stay
with Phase 10.8's explicit grants — and it creates **no membership**: Phase
10.9's store still answers who belongs. Creating a tenant will be proven to
produce a boundary that nobody can yet access.

## 7. No digest, and tenant state stays OUT of existing digests (Part T)

Two separate decisions, both deliberate:

1. **No tenant digest.** Tenant state is *intentionally* mutable
   (activate/deactivate). A hash over mutable fields is recomputed by every
   legitimate change and proves nothing — the same reasoning Phase 10.9 applied
   to membership, and the reason Phase 10.8's grant digest *does* work
   (a grant's authority-bearing fields are immutable once issued).

2. **Tenant state must NOT enter the capability, approval or grant digests.**
   Those digests are historical bindings. Folding mutable tenant state into
   them would mean deactivating a tenant silently invalidates every historical
   approval and grant digest — which is rewriting history, a stop condition.
   Historical records must stay attributable precisely *because* the tenant can
   change state.

Integrity comes from the audit trail, as in 10.9.

## 8. Slug (Part P)

`slug` has **no mutation path today** and is therefore effectively immutable.
`tenant_id` is the stable, authority-bearing identity and every membership,
grant, approval and audit record already keys on it. The slug will be stored
`UNIQUE` and treated as **display/lookup only**; no mutation route is being
added, so the historical-ambiguity question Part P raises does not arise.
Frontend URLs are not authoritative and none is being introduced.

## 9. Design

**`cp_tenant`** (migration 0022): `tenant_id` PK · `slug` UNIQUE · `name` ·
`status` (active/inactive, **never deleted**) · `source` (migrated/provisioned)
· `created_by`, `created_at`, `updated_by`, `updated_at` · `schema_version`.

**`backend/auth/tenants.py`** — resolution, activation/deactivation and the
JSON migration, in the module family already fenced by
`BND-AUTH-CANNOT-EXECUTE`.

**Enforcement:** `require_tenant`, `resolve_approver_authority` and
`resolve_scoped_authority` all read the durable tenant. `product_context`
already gates on membership; tenant state is checked before it.

**Migration (Part V):** deterministic, re-runnable import of every tenant in
`tenants.json`, preserving `tenant_id`, `slug` and active state, and creating
**no** membership, grant, approval or execution right. Afterwards the file is
bootstrap input only — proven by editing it and showing authorization does not
move.

## 10. `GRANDFATHERED_STORES` — an honest note

`backend/platform/architecture/state_rules.py` holds a frozen inventory of file
stores that *"may only shrink"*. `tenants.json` and `tenant_users.json` are
both listed.

Neither entry is removed by this phase, and that is the honest position:
`TenantManager` still *writes* both files (V1 routes, membership bootstrap), so
the stores still exist. What changes is that they stop being **authoritative**.
Removing the entries requires retiring `TenantManager` entirely, which reaches
well beyond this phase. Recorded as a limitation rather than claimed.

## 11. What will NOT be built

No second tenant store, no `TenantStore2`, no tenant-admin authority action, no
product route for tenant mutation, no slug mutation path, no tenant digest, no
tenant state in existing digests, no new capability, no claim of exactly-once.

## 12. Risks accepted

1. This is the third substrate move in three phases. All prior harnesses
   (10.7, 10.8, 10.9) will be re-run.
2. Tenant provisioning stays out-of-band; the bootstrap problem recurs a third
   time and is stated rather than solved.
3. `TenantManager` survives as a bootstrap reader and V1 shim, so both JSON
   files remain on disk — non-authoritative, but present.
