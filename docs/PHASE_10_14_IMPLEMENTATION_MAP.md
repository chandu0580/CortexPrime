# Phase 10.14 — Retire the Dead IAM Subsystem
## Implementation Map (written BEFORE any code)

The goal is not to delete IAM because it is old. It is to prove it is dead,
cut its runtime dependency, remove its schema safely, and prove the
authoritative product path is unchanged.

---

## Part A — the live dependency graph, mapped by execution

`backend/main.py:134` imports `register_identity_services` from
`backend.identity.di`. From there, **two independent edges** reach
`repositories.iam` — Phase 10.13 found the first and this phase found the
second:

```
backend/main.py
 └─ backend.identity.di
     ├─ backend.identity.authentication.password_verifier      [edge 1]
     │    └─ (package __init__ re-exports providers)
     │         └─ identity/authentication/providers.py
     │              └─ backend.database.repositories.iam
     └─ backend.database.repositories.factory                  [edge 2]
          └─ backend.database.repositories.iam
```

A third, independent registration edge:

```
backend/database/models/__init__.py:49
 └─ import backend.database.repositories.iam   (side-effect, registers models)
```

**Cutting `providers.py` alone would not have worked** — `factory.py` imports
`repositories.iam` directly for three accessors, and `models/__init__` imports
it for its side effect. All three edges must go.

### Every edge, classified

| Edge | Class | Disposition |
|---|---|---|
| `main.py → identity.di` | **runtime** | keep — `di` registers nine live services |
| `di → password_verifier` | **runtime** | keep — `PasswordVerifier` is registered |
| `authentication/__init__ → providers` | **dead re-export** | remove the re-export |
| `providers.py → repositories.iam` | **dead** | delete `providers.py` |
| `di → repositories.factory` | **runtime** | keep — `execution_repo` is live |
| `factory → repositories.iam` | **dead** (3 accessors, never called) | remove import + accessors |
| `repositories/__init__ → iam` | **dead re-export** | remove |
| `models/__init__ → iam` | **dead side-effect** | remove |
| `tests/test_identity_auth.py → providers` | **test-only** | see §D |

`DefaultAuthenticationProvider`, `DefaultTokenProvider` and
`DefaultIdentityProvider` have **no production consumer**: they are referenced
only by their own definition, the package re-export, and one test module.
`register_identity_services()` registers nine services and none of them is any
of these three, nor a `UserRepository`.

## Part B — the authoritative auth path

Authentication is `verify_credentials` (`jwt_handler.py:189`): `CORTEX_USER`
against `CORTEX_PASSWORD_HASH` / `CORTEX_PASSWORD` from the environment. The
tenant claim comes from `cp_tenant_membership` + `cp_tenant` (Phase 10.11).
Neither touches `iam_*`.

This will be **proven by real requests**, not by grep: login, refresh, and the
full governed path exercised after removal.

## Part F — data safety, checked before anything is deleted

Across all databases on the instance, exactly one — `cortex_p99b` — has the
three tables, and **all three are empty**:

```
cortex_p99b: tables=3  users=0  roles=0  api_keys=0
```

No authoritative product state, nothing to migrate, and no reason to invent a
data migration. The stop condition does not fire. `cortex_p99b` also gives
Part J its Scenario 2 for free: a real database that already contains the
legacy tables.

## What will be changed

| # | File | Change |
|---|---|---|
| 1 | `backend/identity/authentication/providers.py` | **delete** — three classes with no production consumer |
| 2 | `backend/identity/authentication/__init__.py` | stop re-exporting providers; keep `PasswordVerifier` and the interface re-exports |
| 3 | `backend/database/repositories/iam.py` | **delete** — three models, three repositories, none queried |
| 4 | `backend/database/repositories/factory.py` | remove the IAM import and the three accessors; **keep everything else** — `execution_repo` is live |
| 5 | `backend/database/repositories/__init__.py` | remove the three from the imports and `__all__` |
| 6 | `backend/database/models/__init__.py` | remove the side-effect import |
| 7 | `tests/test_identity_auth.py` | keep `TestPasswordVerifier`; remove the three provider test classes — they test a deleted mechanism |
| 8 | `backend/database/migrations/versions/0023_retire_iam.py` | **new** — drop `iam_api_keys` → `iam_roles` → `iam_users`, in FK order |

Nothing else is touched. `password_verifier.py` stays, `factory.py` keeps every
other repository, and no interface file is modified.

## Part E — the migration

The lineage is a single unbroken head `0001 → … → 0022_tenant_record`, and
`0007_add_bounded_context_tables` created the IAM tables. **History is not
rewritten**: `0007` stays exactly as it is, and a forward migration `0023`
drops what it created.

Drop order respects the foreign key: `iam_api_keys` (whose `user_id` references
`iam_users`) first, then `iam_roles`, then `iam_users`. `downgrade()` recreates
them in the reverse order, so the migration is reversible rather than a
one-way door.

## Part D and Part K — the load-bearing tests

These decide whether the phase succeeded:

- **D:** after the import chain is cut, `Base.metadata` must contain none of
  the three tables *before* `create_all` is ever called.
- **K (the create_all trap):** start from a database where the three tables
  have been dropped, run the application's normal initialisation, and prove
  they stay absent. **If `create_all` recreates them the phase fails**, and the
  fix is the model registration, never the test.

Both run in a **child process** so the parent's already-imported modules cannot
mask the result — a stale `sys.modules` entry would make a broken cut look
clean.

## Part J — two database scenarios

1. **Fresh:** empty database → migrate to head → initialise → schema has no
   `iam_*`.
2. **Existing:** a database that already contains the three tables → run the
   new migration → schema has no `iam_*`.

Both must converge, and the application must boot in both.

## What this phase will NOT do

No new authority, role, permission, credential path, execution path,
governance path or truth store. No fitness rule unless a genuine new bypass
appears. No change to `cp_tenant`, `cp_tenant_membership`,
`cp_authority_grant`, `cp_approval`, approvals, execution, autonomy,
Kubernetes, the worker, the World, Assurance or Investigation. The four V1
refusal routes stay refusals, and no IAM route of any kind is introduced.

## Risks accepted

1. `repositories/factory.py` is live; the edit must remove exactly three
   accessors and one import and leave twelve other repositories untouched.
2. `tests/test_identity_auth.py` loses three of its four test classes. They
   cover deleted code, not behaviour being weakened — the surviving
   `TestPasswordVerifier` covers the part that stays.
3. Migration `0023` drops tables that exist in only one database here. It must
   therefore be written to tolerate their absence, or the fresh-database
   scenario fails on a table that was never created.
