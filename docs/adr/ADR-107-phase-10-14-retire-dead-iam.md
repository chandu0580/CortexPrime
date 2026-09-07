# ADR-107 — Retire the dead IAM subsystem

- **Status:** ACCEPTED
- **Date:** 2026-09-07
- **Phase:** 10.14
- **Completes:** what ADR-106 refused to do, once the condition it named was
  actually met.

## Context

Phase 10.13 was authorised to delete `repositories/iam.py` *only if* it had no
runtime consumer. It had one, so the phase declined and said why: the package
`__init__` of `identity/authentication` re-exported `providers`, so
`backend/main.py → identity.di` imported the dead IAM repository at V1 boot,
its three models landed on `Base.metadata`, and `init_db()`'s `create_all`
would have recreated whatever a migration dropped.

This phase cuts that dependency and then removes the schema.

## What discovery added

Phase 10.13 found one edge. There are **three**, and cutting only the known one
would have left the subsystem alive:

```
backend/main.py → backend.identity.di
  ├─ → identity.authentication.password_verifier
  │      └─ (package __init__ re-exports providers) → repositories.iam   [1]
  ├─ → backend.database.repositories.factory        → repositories.iam   [2]
  └─ (separately) backend/database/models/__init__  → repositories.iam   [3]
```

Edge 2 is a direct import for three `RepositoryFactory` accessors —
`user_repo`, `role_repo`, `api_key_repo` — **none of which is ever called**.
Edge 3 is a side-effect import whose only purpose is registering the models.

`DefaultAuthenticationProvider`, `DefaultTokenProvider` and
`DefaultIdentityProvider` have no production consumer at all:
`register_identity_services()` wires nine services and none is one of them.
Their only reference outside the package was one test module.

## Decision

**Cut all three edges, then drop the schema.**

Removed: `identity/authentication/providers.py`, the providers re-export from
that package's `__init__`, `backend/database/repositories/iam.py`, the IAM
import and three accessors in `repositories/factory.py`, the three names in
`repositories/__init__.py`, and the side-effect import in
`models/__init__.py`.

Preserved: `PasswordVerifier` (registered, used, never coupled to IAM), every
other repository in the factory, and every interface file.

`tests/test_identity_auth.py` keeps `TestPasswordVerifier` and loses the three
provider classes — tests of deleted code, not behaviour being weakened.

### The migration

Migration `0023_retire_iam` drops `iam_api_keys` → `iam_roles` → `iam_users`,
in that order because `iam_api_keys.user_id` is a foreign key to `iam_users`.
`0007` is part of the current unbroken lineage, so **history is not rewritten**:
a forward migration drops what it created.

Each drop is guarded by an existence check, because most databases here were
built by `DURABLE_METADATA.create_all` and never had these tables — a fresh
database must migrate to head without tripping over one that was never created.

`downgrade()` recreates all three **exactly as `0007` defined them**. The first
draft did not: it used `UUID(as_uuid=True)` instead of `sa.Uuid()`, dropped the
`gen_random_uuid()` and `NOW()` defaults, and invented `scopes` and
`last_used_at` on `iam_api_keys` while omitting the real `last_prefix` and
`is_active`. Checking it against the original caught that. A downgrade that
produces a *different* schema is worse than none.

### Data safety, established before anything was deleted

Across every database on the instance, exactly one had the three tables and all
three were **empty** — 0 users, 0 roles, 0 api keys. No authoritative product
state, nothing to migrate, no reason to invent a data migration.

## A pre-existing defect this phase found and did not repair

Part K required running the application's normal initialisation and proving the
IAM tables stay absent. Running it surfaced something older and unrelated:
**`init_db()` cannot complete on any database.**

`Base.metadata.create_all` raises `NoReferencedTableError` on
`reflection_history.mission_id → missions`. No model anywhere declares
`__tablename__ = "missions"` — the table is created by migration `0001` and
never mapped — so SQLAlchemy cannot resolve the key while sorting tables.

This is not caused by the retirement: the deleted module defined exactly
`iam_users`, `iam_roles` and `iam_api_keys`, so removing it cannot be why
`missions` is absent. The harness asserts both halves — the IAM tables stay
absent, **and** the failure names `missions` rather than anything IAM — so the
trap is answered rather than excused.

It is **reported, not repaired**: fixing it means mapping or removing a V1
table, which this brief does not authorise and which deserves its own evidence.

## An existing gate finished the job

The first architecture run failed on
`test_the_ratchet_has_no_stale_entries`. `UserRepository`, `RoleRepository` and
`ApiKeyRepository` were **grandfathered exemptions from the tenancy guard**,
and deleting the repositories left three exemptions with nothing behind them —
which the test's own docstring calls out: *"a future repository reusing the
name inherits a pass it never earned."*

They were removed, and `GRANDFATHERED_REPOSITORIES` went from 42 to 39. That is
the second frozen inventory in this phase family to shrink for a proven reason,
and unlike the first it was **the gate that noticed**, not the author. Nothing
was edited to make a test pass; the exemptions went because the code they
exempted is gone.

## Consequences

**The authoritative path did not move.** Authentication is still
`verify_credentials` against the environment; the tenant claim still comes from
`cp_tenant_membership` and `cp_tenant`; tenant, membership, authority,
issuance, revocation, the approval queue and tenant isolation all verified by
real request after the removal.

**Both database scenarios converge.** A fresh database migrated to head and a
database seeded to `0022` (which genuinely had all three tables) end at the
same 55-table schema with no `iam_*`.

**The V1 surface is untouched** — still exactly four routes, all refusals, no
GET, and no IAM route of any kind.

## What the re-runs cost, and what they were worth

Two of the six prior harnesses did not pass on the first re-run, and neither
was a regression.

**Phase 10.7 reported 150/155**, every failure on the governed execution leg.
Because Part Q stop condition 8 is *"removing IAM changes execution
semantics"*, it was investigated as a possible stop rather than dismissed.

The cause was an **expired TLS certificate on the contained worker** —
`notAfter` 2026-09-07 15:05:31 IST, minted `-days 2` by the disposable
phase-9.9B provisioning. The last passing run of that harness finished at
15:06:58, before the expiry; the failing run began at 16:10. `curl -k` reported
the worker healthy, which is exactly why it looked fine; with verification on,
the answer was `CERTIFICATE_VERIFY_FAILED`.

Two things are worth recording:

- **The platform was right, and said so precisely.** It refused to send a
  credential over a connection it could not verify, and reported the outcome as
  `ambiguous=True` / `succeeded=False` — *"whether the worker performed the
  restart is unknown from here"*. An expired certificate is the exact case
  where reporting "the write failed" would be a lie. UNKNOWN is not FALSE, and
  the code held that line without being asked to.
- **The harness's diagnostics were the weak link.** Three checks printed
  `HTTP 409` and nothing else, which is why placing the cause took four runs.
  Their detail strings now carry the response body; the assertions are
  byte-identical. The fix was to regenerate the certificate — verification was
  never disabled — after which the harness returned **155/155**, identical to
  its pre-retirement result.

**Phase 10.13 reported 55/59**, and all four failures were assertions this
phase was authorised to invalidate: that `repositories/iam.py` *is* imported at
boot, that its models *are* on `Base.metadata`, that the `iam_api_keys` FK
*exists* — which were 10.13's stated reason for declining the deletion — plus a
check pinning the lineage at 22 migrations.

They were **inverted, not deleted**. Deleting them would erase the evidence
that the coupling was real; inverted, they now fail if IAM ever comes back. The
migration check was making a claim about its own phase's delivery expressed as
a ceiling on the whole lineage, and now asserts what it meant. A `deferred()`
entry reading *"dropping the IAM tables: not done"* became a real check that
the drop is a forward migration with `0007` intact — which is why the total
rose from 59 to 60. Re-run: **60/60**.

## Verification

`scripts/phase1014_retire_iam_harness.py` — **52/52 VERIFIED** against real
k3d, real PostgreSQL, real Redis, real child processes and real databases.
11 negative cases, **0 provider writes**.

`tests/architecture` **155 passed**; backend regression **2852 passed**.
Phases 10.7 (**155/155**), 10.8 (**118/118**), 10.9 (**107/107**), 10.10
(**107/107**), 10.11 (**68/68**) and 10.13 (**60/60**) re-run in full. Details
in `docs/PHASE_10_14_VERIFICATION_REPORT.md`.
