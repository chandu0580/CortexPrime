# Phase 10.11 — Retire TenantManager
## Implementation Map (written BEFORE any code)

A retirement phase. Nothing is added; the question is what can be **deleted**
without changing the semantics Phases 10.7–10.10 proved.

---

## 0. A correction to the brief's premise [VERIFIED]

The brief names `data/users/users.json`. **That file does not exist.** The two
legacy stores are:

```
data/tenants/tenants.json
data/tenants/tenant_users.json
```

Both are listed in `GRANDFATHERED_STORES`. Part F's questions are answered
against `tenant_users.json`, which is the file that actually holds user rows.

## 1. Consumer inventory — every reference, classified

Classified by **reachability**, not by whether a scan calls it unused.

| # | Consumer | Class | Replacement |
|---|---|---|---|
| 1 | `auth_routes._tenant_claims` (login **and** refresh) | **runtime production** | `cp_tenant_membership` + `cp_tenant` |
| 2 | `dependencies.require_user` tenant check | runtime production — durable-first since 10.10, with a JSON fallback | remove the fallback |
| 3 | `dependencies.require_tenant` | same | remove the fallback |
| 4 | `dependencies.get_current_tenant` | **dead code** — defined, never imported, never referenced anywhere | delete |
| 5 | `authority_routes` `members=get_tenant_manager()` | **dead argument** — `issue_grant` prefers `memberships=`, which is always supplied | delete |
| 6 | `tenant_routes.create_tenant` / `deactivate_tenant` bodies | **dead code after a `raise`** (10.10 refused both) | delete the unreachable remainder |
| 7 | `tenant_routes.list_tenants` / `get_tenant` / `list_tenant_users` | runtime production **reads** | durable reads |
| 8 | `tenant_routes.add_user_to_tenant` / `update_user_role` | **runtime production writes — see §2** | refuse, naming the governed route |
| 9 | `backend/auth/tenant.py` mutators + `_save` | the only code that **writes** either JSON file | delete — see §3 |
| 10 | `TenantManager` read methods | **bootstrap/migration only** | keep, explicitly isolated |
| 11 | `scripts/phase10*.py` `tm.create_tenant` / `tm.add_user` | test fixture | durable provisioning (already available) |
| 12 | `tests/test_tenant.py`, `tests/test_tenant_routes.py` | tests **of the deleted mechanism** | see §5 |

## 2. A finding: two live V1 routes are a silent no-op trap [VERIFIED]

Phase 10.10 refused V1 *tenant* mutation. It did not touch V1 **membership**
mutation, and those two routes are still live:

- `POST /api/tenants/{id}/users` → writes a member into `tenant_users.json`
- `PATCH /api/tenants/{id}/users/{id}` → writes a role into the same file

Neither file is authoritative any more. So an operator adds somebody through
the V1 API, receives **HTTP 201**, and that person has **no governed
membership at all** — no product access, no authority, nothing. The call
appears to work and changes nothing that matters.

This is not an authorization hole; it is the exact trap Phase 10.10 avoided for
tenant mutation by refusing rather than repointing, and left open for
membership. Same treatment: **refuse**, naming
`POST /api/v1/tenants/members` as the governed route.

## 3. TenantManager becomes read-only — and that is what shrinks the inventory

`FileStateRule` flags a module that **writes** a state file and names it;
reading one is explicitly fine (*"reading a JSON file is fine, and most modules
mentioning one only read it"*). So an entry may leave `GRANDFATHERED_STORES`
only when nothing writes that filename.

`backend/auth/tenant.py` is the **only** module that writes either file, via
`_save()`. Therefore:

- delete `_save`, `create_tenant`, `add_user`, `update_user_role`,
  `deactivate_tenant`, `grant_permission`, `revoke_permission`;
- keep `get_tenant`, `get_tenant_by_slug`, `list_tenants`, `get_users`,
  `get_user_by_email` and `_load` — the migrations read through them;
- rename nothing, so no import in the tree breaks silently.

The class becomes a **read-only importer**. That is the retirement: its
authority went in 10.9/10.10, and its write path goes here.

**Then, and only then**, both entries leave the frozen inventory — the first
time that list has shrunk. It shrinks because the writes are gone, not because
the list was edited.

## 4. What replaces the login wire

`_tenant_claims(user_id)` is the Phase 10.2 wire that puts `tenant_id`,
`tenant_slug` and `user_role` into every login **and refresh** token. It reads
`get_user_by_email` + `get_tenant` from JSON.

Replacement reads `cp_tenant_membership` for the subject's live membership and
`cp_tenant` for the boundary, preserving the existing fail-closed contract
exactly: no membership, an inactive membership, an inactive tenant, or any
store failure → **no claims at all**.

This is a genuine behaviour change in one direction and it is deliberate:
a login today can mint a tenant claim from a JSON row that the governed stores
do not have, producing a token that every governed path then refuses. After
this phase the claim comes from the same store that will judge it.

## 5. The two legacy test modules

`tests/test_tenant.py` (209 lines) and `tests/test_tenant_routes.py` (190) test
`create_tenant`, `add_user`, `update_user_role` and `deactivate_tenant` — the
methods being deleted.

Part T forbids rewriting **correct** tests to make them pass. These are not
correct tests being bent to fit: they describe a mechanism that no longer
exists. The honest treatment is to delete the cases for deleted methods and
**keep** the ones that still describe live behaviour (the dataclasses, the read
methods, and the route refusals). Anything kept must still assert something
true; anything deleted is recorded in the report by name and count.

## 6. Proof strategy — Parts A, C, M

Source scans are **not** the evidence. Phase 10.10 proved why: a store-level
assertion passed while a third JSON reader was still live, and only a real
request exposed it.

So the harness will, in order:

1. run the governed paths normally;
2. **mutate** both JSON files and re-run every authorization test — expect no
   change;
3. **make the files unavailable** (point the loader at an empty directory) and
   re-run — expect no change;
4. **make `TenantManager` unimportable** in a separate process and issue real
   product requests — expect them to work.

(4) is the strongest available evidence and is done in a child process against
a temporary copy, so the repository is never corrupted.

## 7. What will NOT be built

No frontend, no notification, no capability, no role, no approval type, no
autonomy, no identity provider, no group, no hierarchy, no exactly-once, no new
table, no new migration, no new authority, and no replacement invented for a
consumer that has none.

## 8. Risks accepted

1. Deleting the mutators breaks any out-of-tree caller. In-tree callers are
   enumerated in §1 and all are updated.
2. The login wire changes which store decides a token's tenant claim (§4).
3. Bootstrap still needs the JSON to exist for a *first* migration; after that
   it is inert. If it is absent, the migration imports nothing and the durable
   stores stay as they are — which is correct, not a failure.
