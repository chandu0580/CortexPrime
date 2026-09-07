# Phase 10.12 — V1 Tenant Read Surface + Legacy Auth Artifacts
## Discovery (no production code changed)

**Deliverables:** this document and `docs/adr/ADR-105-…`. No production code,
no migration, no frontend change, no database change, nothing deleted.

Every claim is labelled. Where evidence is a source scan rather than an
execution, the method is stated so it can be discounted appropriately — Phase
10.10 established why that distinction matters.

---

## Part A — every V1 tenant route

`backend/api/tenant_routes.py`, prefix `/api/tenants`, registered in the V1 app
(`router_registry.py:91`). Seven routes: **three reads, four refused writes.**

| # | Method | Path | Auth | Tenant source | Store | Status |
|---|---|---|---|---|---|---|
| 1 | GET | `/api/tenants` | `require_admin` | **token claim** | `cp_tenant` | read |
| 2 | GET | `/api/tenants/{tenant_id}` | `require_admin` | path, **checked against the claim** | `cp_tenant` | read |
| 3 | GET | `/api/tenants/{tenant_id}/users` | `require_admin` | path, checked | `cp_tenant_membership` | read |
| 4 | POST | `/api/tenants` | `require_admin` | — | — | **403 refused** |
| 5 | POST | `/api/tenants/{id}/users` | `require_admin` | path, checked | — | **403 refused** |
| 6 | PATCH | `/api/tenants/{id}/users/{user_id}` | `require_admin` | path, checked | — | **403 refused** |
| 7 | POST | `/api/tenants/{id}/deactivate` | `require_admin` | path, checked | — | **403 refused** |

`require_admin` is a JWT `role == "admin"` claim; tenant scoping is the separate
`_same_tenant_or_refuse` guard added in Phase 10.9.

## Part B — real consumers [VERIFIED]

Repository-wide search for `api/tenants`, classified:

| Consumer | Class | Count |
|---|---|---|
| `backend/api/tenant_routes.py` (the router itself) | definition | 1 |
| `docs/**` — five prior phase reports and ADRs | documentation | 21 |
| `scripts/phase109_*`, `scripts/phase1011_*` | **test fixture** | 9 |
| Anything under `frontend/` | — | **0** |
| Any other backend module | — | **0** |

**No production consumer exists — frontend or backend.** The only callers are
the two harnesses that exist to *prove these routes refuse*, which is the
opposite of a dependency.

## Part C — the browser [VERIFIED, and stronger than source]

The brief warns against inferring this from imports, so the evidence is the
**compiled bundle** the browser actually loads:

```
grep -rl "api/tenants"            .next   →  (no match)
grep -rl "api/v1/investigations"  .next   →  .next/dev/server/app/approvals/page.js
                                             .next/dev/static/chunks/app/approvals/page.js
```

334 MB, 3 998 JavaScript files. The control path matches, so the search reaches
the bundle; the V1 tenant path appears **nowhere in it**.

Every governed product surface goes through `/product-api` (a same-origin Next
rewrite) to `/api/v1/{investigations,approvals,authority,tenants/members,…}`.

**A separate finding, unrelated to retirement:** `CortexSidebar.tsx:68` links to
`/settings/tenants`, and **no such page directory exists** — a dead navigation
link that would 404. It is not a consumer of these routes; it is recorded
because it was found while looking. [VERIFIED — `app/settings/tenants` absent]

**[NOT VERIFIED]** A live browser session was not driven. The bundle grep is
stronger than source inspection but is still static; a running-browser network
capture would be stronger still.

## Part D — response semantics [VERIFIED by calling]

### `TenantResponse` — 8 fields

| Field | Classification | Value observed |
|---|---|---|
| `tenant_id` | **authoritative** (`cp_tenant.tenant_id`) | real |
| `slug` | **authoritative** | `p1012a` |
| `name` | **authoritative** | real |
| `is_active` | **derived** from `cp_tenant.status` | `true` |
| `created_at` | **authoritative** | real |
| `domain` | **no authoritative source** | `null` |
| `plan` | **no authoritative source** | `""` |
| `settings` | **no authoritative source** | `{}` |

The last three are **empty, not fabricated** — the durable record does not carry
them (Phase 10.10, Part C: no unnecessary metadata), and Phase 10.11 chose to
report absence rather than invent a value.

**Four durable columns are dropped by the V1 shape:** `created_by`, `source`,
`updated_by`, `updated_at` — precisely the provenance Phases 10.9–10.11 added.
So the legacy shape is simultaneously *wider* (three empty fields) and
*narrower* (four real ones) than the truth.

### `TenantUserResponse` — 7 fields

| Field | Classification | Value observed |
|---|---|---|
| `tenant_id`, `email`, `role`, `is_active`, `created_at` | authoritative / derived | real |
| `permissions` | **empty by construction** | `[]` |
| `user_id` | **semantically changed** | `mbr-…` |

Two things worth naming:

- `permissions` is deliberately `[]`. Authority lives in `cp_authority_grant`,
  and a permission list beside a member is what Phase 10.5 spent a phase
  separating from membership. A client reading this field would conclude the
  member holds nothing — which is *not* what the field used to mean.
- **`user_id` now carries a membership id**, not a user id. The V1 contract's
  identifier changed meaning in Phase 10.11 without changing its name. Any
  client that stored a `user_id` from before holds a value that no longer
  resolves.

## Part E — authority leak [VERIFIED]

Database snapshot before and after three full rounds of all three reads —
tenant/membership/grant counts, every membership `(subject, status, role)`,
every grant digest, and tenant status:

```
E_state_unchanged      = True
E_grant_digests before/after = (1, 1)
```

The reads grant nothing, revoke nothing, and alter no membership, tenant state,
approval or execution record.

## Part F — tenant isolation [VERIFIED]

| Probe | Result |
|---|---|
| own tenant, `GET /{id}` | **200** |
| foreign tenant, `GET /{B}` | **404** |
| nonexistent tenant | **404** |
| foreign tenant's users | **404** |
| `GET /api/tenants` | 1 row, **own tenant only** |
| forged `?tenant_id=B` | 200, returns **A** — inert |
| forged `X-Tenant-Id: B` header | 200, returns **A** — inert |
| token with no tenant claim | **403** |
| anonymous | **401** |

404 rather than 403 for a foreign tenant is deliberate (Phase 10.9): a tenant
may not learn another exists. **No leak found.**

## Part G — authentication and legacy dependency [VERIFIED at runtime]

A child process installs an import guard that raises on `backend.auth.tenant`
**before anything can import it**, then calls all three reads:

```
LIST 200 · GET 200 · USERS 200
```

The V1 reads have **zero runtime dependency** on `TenantManager`,
`tenants.json` or `tenant_users.json`.

**Authentication itself:** `verify_credentials` (`jwt_handler.py:189`) checks
`CORTEX_USER` against `CORTEX_PASSWORD_HASH` / `CORTEX_PASSWORD` from the
environment. One configured user, exactly as the brief states. Neither
`TenantManager` nor `iam_users` participates; `TenantManager` supplied the
tenant *claim*, never the credential, and Phase 10.11 moved even that to
`cp_tenant_membership` + `cp_tenant`.

## Part H — `iam_users` [VERIFIED dead]

The reachability chain, each link checked:

1. `iam_users` / `iam_roles` are created by migration `0007` only.
2. `UserModel` is used solely by `UserRepository` (`repositories/iam.py`).
3. `UserRepository` is instantiated in exactly one place —
   `RepositoryFactory.user_repo`.
4. **`.user_repo` is never called anywhere** (grep excluding the definition and
   `providers.py`'s own `self._user_repo` attribute: no hits).
5. The only class that would query it,
   `identity/authentication/providers.py`, takes a `UserRepository` as a
   constructor argument and **is imported by nothing outside
   `backend/identity/`**.
6. `backend/main.py:134` does wire `register_identity_services()`, and that
   function registers **nine** services — key store, access/refresh token
   providers, password verifier, session runtime, audit hooks, RBAC provider,
   ABAC evaluator, permission evaluator, health. **None is a
   `UserRepository` or any database authentication provider.**
7. **The table does not exist in any governed database.** Across all 12
   databases on the instance, `iam_users`/`iam_roles`/`organizations` appear in
   exactly one — `cortex_p99b`, which holds `iam_users` and `iam_roles` from a
   different migration lineage the governed phase databases never ran.

**`iam_users` is authoritative for nothing.** The Part H stop condition does
not fire.

## Part I — the legacy JSON files [VERIFIED]

`data/tenants/tenants.json` and `data/tenants/tenant_users.json`. Phase 10.11
proved they are inert for governed authorization (poisoned, then deleted, with
every governed answer unchanged).

Their one remaining purpose: **read-only bootstrap input** for
`migrate_json_tenants` and `migrate_json_memberships`. `TenantManager` is a
read-only importer with no mutator, no `_save` and no `mkdir`.

They are also used as **test fixtures** by the 10.9/10.10/10.11 harnesses, which
poison and restore them on disk to prove they do not matter.

**`data/users/users.json` does not exist** — a correction first recorded in
Phase 10.11 and re-confirmed here.

## Part J — `GRANDFATHERED_STORES` [VERIFIED]

- **74 entries** remain (down from 76; Phase 10.11 removed both tenant files —
  the first time the inventory shrank).
- **No tenant- or user-related entry remains.**
- `APPROVED_STORES` holds 3: `approval_decisions.json`,
  `integrity_audit.jsonl`, `pending_approval_actions.json`.

The 74 remaining entries were **not** individually classified as runtime,
bootstrap-only or dead. That is a large inventory belonging to the V1 surface
this phase family has not touched, and guessing would be worse than saying so.
**[NOT VERIFIED — deliberately out of scope]**

## Part K — V1 write routes [VERIFIED]

All four called with a valid tenant-A admin token, with a full database
snapshot before and after:

| Route | Status | Detail |
|---|---|---|
| `POST /api/tenants` | **403** | "tenant administration is out-of-band…" |
| `POST /{id}/users` | **403** | "membership administration moved to the governed product API…" |
| `PATCH /{id}/users/{u}` | **403** | same |
| `POST /{id}/deactivate` | **403** | "tenant administration is out-of-band…" |

```
K_state_unchanged_after_writes = True
```

Classification: **all four are refusals.** None is a real mutation, a governed
mutation, or a no-op that appears to succeed. The two silent no-ops Phase 10.11
found are closed, and no new dangerous legacy surface remains here.

## Part L — retirement safety [VERIFIED]

Retiring the three reads would affect:

| System | Dependency |
|---|---|
| Authentication | **none** — env-configured user; the tenant claim comes from the durable stores |
| Membership | **none** — the governed route is `/api/v1/tenants/members` |
| Authority | **none** — `/api/v1/authority/grants` |
| Approvals | **none** — no approval path reads these routes |
| Execution | **none** |
| Workspace / approval queue | **none** — the compiled bundle contains no reference |

Nothing was modified to establish this.

## Part M — performance baseline [VERIFIED, measured]

| Path | p50 | p95 |
|---|---|---|
| `GET /api/tenants` (V1 list) | 27.2 ms | 49.8 ms |
| `GET /api/tenants/{id}` (V1 get) | 23.6 ms | 27.4 ms |
| `GET /api/tenants/{id}/users` (V1 users) | 37.2 ms | 51.4 ms |
| `GET /api/v1/tenants/members` (governed) | 56.5 ms | 78.4 ms |
| `cp_tenant` repository lookup | 11.6 ms | 16.8 ms |

**These are not comparable as a like-for-like.** The V1 list returns one tenant
row; the governed member listing returns every membership in the tenant and
carries the authority note. The numbers are recorded because the brief asks for
a baseline, not because the V1 route is "faster at the same job". No
optimisation, no SLA, no index.

## Part N — architecture boundary [VERIFIED]

Every import in `backend/api/tenant_routes.py`, by AST:

```
__future__ · backend.api.product.app · backend.auth.dependencies
fastapi · pydantic · typing
```

No gateway, worker, provider, credential, execution, world, assurance,
autonomy or capability-execution import. The module **cannot** execute a
provider, invoke a worker, reveal a credential, create an observation, a fact,
an approval or authority, or grant autonomy — there is nothing in scope to call.

## Part O — stop conditions

| # | Condition | Result |
|---|---|---|
| 1 | Production frontend depends on V1 tenant reads | **No** — absent from the compiled bundle |
| 2 | A backend governed path depends on them | **No** |
| 3 | `iam_users` authoritative for identity or authorization | **No** — chain broken at step 4; table absent from every governed DB |
| 4 | JSON authoritative anywhere in the governed path | **No** — Phase 10.11, re-confirmed at runtime here |
| 5 | Removing a read changes approval semantics | **No** |
| 6 | Removing a read changes execution semantics | **No** |
| 7 | A V1 read leaks cross-tenant information | **No** — Part F |
| 8 | A V1 route secretly mutates state | **No** — Parts E and K |

**No stop condition fired.**

---

## Definition of done — the fifteen answers

1. **Every V1 tenant read route** — three (Part A).
2. **Every real consumer** — none in production; docs and two harnesses only.
3. **Production-reachable?** The routes are registered and reachable, but
   **nothing reaches them**.
4. **Does the browser use them?** No — absent from a 334 MB compiled bundle
   whose control path matches.
5. **Response semantics** — three fields with no authoritative source, four
   durable columns dropped, `permissions` empty by construction, and `user_id`
   silently changed meaning to a membership id.
6. **Isolation** — correct: own 200, foreign 404, forged inputs inert.
7. **Authentication dependency** — none; proven with the legacy module
   unimportable.
8. **Is `iam_users` dead?** Yes, on seven independent checks.
9. **Do the JSON files have a purpose?** Yes, one: read-only bootstrap import.
10. **Remaining `GRANDFATHERED_STORES`** — 74, no tenant/user entries; the rest
    deliberately unclassified.
11. **Remaining V1 tenant writes** — four, all refusals, no state change.
12. **Is retirement safe?** Yes, for the three reads (Part L).
13. **What must be preserved** — the read-only importer and both JSON files
    until an operator decides no installation will import again; the governed
    routes; the four refusals, which are load-bearing documentation of what
    moved where.
14. **What can be deleted** — the three read routes and their two response
    models; `repositories/iam.py` plus `iam_users`/`iam_roles`; the dead
    `/settings/tenants` sidebar link.
15. **What the next phase should be** — see the ADR.
