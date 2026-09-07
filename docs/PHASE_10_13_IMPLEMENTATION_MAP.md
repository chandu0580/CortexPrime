# Phase 10.13 — Retire the V1 Tenant Read Surface + Dead IAM
## Implementation Map (written BEFORE any code)

A deletion phase. The goal is not to delete as much as possible; it is to
remove only what Phase 10.12 proved obsolete, preserve everything still
intentional, and prove the governed path survives.

---

## 1. What will be deleted

| # | Item | Justification |
|---|---|---|
| 1 | `GET /api/tenants` | 10.12: no production consumer, absent from the compiled bundle |
| 2 | `GET /api/tenants/{tenant_id}` | same |
| 3 | `GET /api/tenants/{tenant_id}/users` | same |
| 4 | `_durable()`, `_record_to_response()`, `_membership_to_response()` | helpers used **solely** by those three routes |
| 5 | The `backend.api.product.app` import in `tenant_routes` | only `_durable()` needed it |
| 6 | `CortexSidebar.tsx` link to `/settings/tenants` | 10.12: the page directory does not exist — a 404 in the product nav |

## 2. What will NOT be deleted, and why

### 2.1 The two response models — they are not "solely for the reads"

The brief authorises removing only schemas that exist **solely** for the three
reads. They do not:

| Model | Also declared by |
|---|---|
| `TenantResponse` | `create_tenant` (403), `deactivate_tenant` (403) |
| `TenantUserResponse` | `add_user_to_tenant` (403), `update_user_role` (403) |

All four are preserved refusal routes. Stripping `response_model` from a route
that always raises would change its OpenAPI contract for no behavioural gain,
so **both models stay.**

### 2.2 `repositories/iam.py` and the three IAM tables — the condition is not met

The brief is explicit: remove it **only if** discovery confirms it has no
runtime consumer. **It has one, and Phase 10.12 missed it.**

10.12 asked two questions and answered both correctly:
- is `.user_repo` ever *called*? No.
- is `identity/authentication/providers.py` imported outside
  `backend/identity/`? No.

Neither question catches the real coupling. `backend/identity/authentication/
__init__.py` **re-exports** `providers`, so importing any submodule of that
package executes it — and `backend/main.py:134` imports
`register_identity_services` from `backend.identity.di`, which imports
`PasswordVerifier` from that very package.

Proven by execution, not by reading:

```
import backend.identity.di
→ backend.database.repositories.iam imported at V1 boot: True
→ iam tables registered on Base.metadata: ['iam_api_keys','iam_roles','iam_users']
```

And `backend/database/engine.py:210` runs `Base.metadata.create_all` inside
`init_db()`, so those three tables are **created by a live path**, not only by
alembic.

There is also a **third** table the brief did not name: `iam_api_keys`, whose
`user_id` is a foreign key to `iam_users`. Dropping the two named tables
without it would fail.

**Decision: `repositories/iam.py` stays, and no IAM migration is written.**
Removing it properly means deleting `identity/authentication/providers.py`,
rewriting that package's `__init__`, and editing `repositories/__init__.py`,
`factory.py` and `models/__init__.py` — a deletion inside the authentication
subtree that this brief does not authorise and that the test list requires to
keep working. Forcing it to make the phase look complete is exactly what the
brief warns against.

### 2.3 Migration lineage — investigated, and the answer is "not yet"

The chain is **unbroken and single-headed**: `0001 → … → 0022_tenant_record`,
with no branches. `0007_add_bounded_context_tables`, which creates all three
IAM tables, **is in the current HEAD lineage** — so `alembic upgrade head`
does create them. They are absent from the governed phase databases only
because those are built by `DURABLE_METADATA.create_all`, which knows nothing
of the V1 ORM.

So the brief's condition — *"if they belong only to an obsolete/non-governed
lineage, do not create a fake drop migration"* — does **not** apply: they are
in the live lineage. But its other condition — *"if and only if the tables are
proven dead"* — is not met either, because a live boot path registers them and
`init_db()` creates them.

**No migration is written.** Dropping tables that `create_all` immediately
recreates would be incoherent, and writing one anyway would be the "unexplained
migration" the Definition of Done forbids.

### 2.4 Preserved outright

`tenants.json`, `tenant_users.json`, the read-only bootstrap importer, the four
V1 write refusal routes, `cp_tenant`, `cp_tenant_membership`,
`cp_authority_grant`, `cp_approval`, and every approval, execution, autonomy,
Kubernetes, worker, credential, World, Assurance and Investigation path.

## 3. Consequences for existing harnesses

Two harnesses assert against routes that will no longer exist. Both must be
updated — not to make them pass, but because they describe a mechanism being
removed:

- **10.9** `_v1_cross_tenant_refused` requires `[404, 404, 404]` from
  `POST /{B}/users`, `GET /{B}/users`, `POST /{B}/deactivate`. With the GET
  removed, FastAPI answers **405 Method Not Allowed** (the path still has a
  POST). The assertion becomes: the two surviving writes still 404 for a
  foreign tenant, and the retired read is gone.
- **10.11** `run_v1_routes` checks that the member listing reads the durable
  store (I3) and the tenant listing returns own-tenant-only (I4). Both routes
  are being deleted, so those two checks are replaced by assertions that the
  routes no longer exist.

Nothing else in 10.7, 10.8, 10.10 or 10.12 touches these routes.

## 4. What this phase creates

Nothing. **0 authorities, 0 roles, 0 permissions, 0 execution paths, 0
governance paths, 0 credential paths, 0 truth stores, 0 tables, 0 migrations,
0 fitness rules** unless a genuine new bypass appears.

## 5. Proof strategy

Source assertions are corroboration only. The harness will:

1. call all three retired routes and require **404 / 405**, not a body;
2. exercise the governed path end to end — product access, membership,
   authority, approval queue, approval decision, tenant isolation;
3. re-run the four V1 write refusals and confirm they still refuse with the
   database unchanged;
4. poison the legacy JSON and prove no governed answer moves;
5. invoke the bootstrap import explicitly and prove it still works;
6. run a negative matrix at **0 provider writes**;
7. re-run the 10.7, 10.8, 10.9, 10.10 and 10.11 harnesses in full.

## 6. Risks accepted

1. Deleting a registered route is visible to any out-of-tree client. 10.12
   established there is none, including in the compiled browser bundle.
2. The IAM module stays, so the phase's deletion is smaller than the brief
   anticipated. That is a finding, not a shortfall, and §2.2 is the evidence.
