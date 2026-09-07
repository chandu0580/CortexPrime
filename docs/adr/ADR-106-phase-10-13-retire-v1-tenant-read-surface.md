# ADR-106 — Retire the V1 tenant read surface; keep the dead IAM module

- **Status:** ACCEPTED
- **Date:** 2026-09-07
- **Phase:** 10.13
- **Implements:** ADR-105's first recommendation. **Declines its third**, for a
  reason ADR-105 could not have known.

## Context

Phase 10.12 proved the three V1 tenant read routes had no consumer anywhere —
not in the backend, and not in a 334 MB compiled browser bundle whose control
path matched — and that their shape actively misled: three fields with no
authoritative source, four real provenance columns dropped, `permissions` empty
by construction, and `user_id` silently carrying a membership id while keeping
its name.

It recommended a bounded deletion: three routes, two response models, the dead
IAM module and its tables, and one dead sidebar link.

## Decision

**Delete the three reads. Keep almost everything else, for stated reasons.**

### Deleted

- `GET /api/tenants`, `GET /api/tenants/{id}`, `GET /api/tenants/{id}/users`;
- `_durable()`, `_record_to_response()`, `_membership_to_response()` — helpers
  that existed solely for them, and the `backend.api.product.app` import only
  `_durable()` needed;
- the `CortexSidebar` link to `/settings/tenants`.

### Kept, and why each

**The two response models.** ADR-105 assumed they existed only for the reads.
They do not: `TenantResponse` is declared by `create_tenant` and
`deactivate_tenant`, and `TenantUserResponse` by `add_user_to_tenant` and
`update_user_role` — all four preserved refusals. The brief authorises removing
schemas that exist *solely* for the reads, and these do not qualify. Stripping
`response_model` from a route that always raises would change its OpenAPI
contract for no behavioural gain.

**The four refusals.** Each names where its governed operation moved. Deleting
them would turn an informative 403 into a 404 that tells an operator following
an old runbook nothing.

**`repositories/iam.py` and the three IAM tables — the condition is not met.**

The brief permits removal *only if* discovery confirms no runtime consumer.
There is one, and Phase 10.12 missed it. 10.12 asked whether `.user_repo` was
ever called (no) and whether `identity/authentication/providers.py` was imported
outside `backend/identity/` (no). Both answers were right; neither question
catches the coupling.

`backend/identity/authentication/__init__.py` **re-exports** `providers`, so
importing any submodule of that package executes it — and `backend/main.py:134`
imports `register_identity_services` from `backend.identity.di`, which imports
`PasswordVerifier` from exactly that package.

Proven by execution rather than by reading:

```
import backend.identity.di
→ backend.database.repositories.iam imported at V1 boot: True
→ iam tables on Base.metadata: ['iam_api_keys', 'iam_roles', 'iam_users']
```

And `backend/database/engine.py:210` runs `Base.metadata.create_all` inside
`init_db()`, so a live path creates those tables, not only alembic.

There is also a **third table the brief did not name**: `iam_api_keys`, whose
`user_id` is a foreign key to `iam_users`. The two named tables cannot be
dropped without it.

**No migration was written.** The lineage was investigated as required: the
chain is unbroken and single-headed, `0001 → … → 0022_tenant_record`, and
`0007_add_bounded_context_tables` — which creates all three IAM tables — **is
in the current HEAD lineage**. So the brief's escape hatch ("if they belong only
to an obsolete lineage, do not create a fake drop migration") does not apply.
But its precondition — *proven dead* — is not met either, because a live boot
path registers them and `create_all` would recreate whatever a migration
dropped. Writing one anyway would be the unexplained migration the Definition
of Done forbids.

Retiring them properly means deleting `identity/authentication/providers.py`,
rewriting that package's `__init__`, and editing `repositories/__init__.py`,
`factory.py` and `models/__init__.py` — a deletion inside the authentication
subtree this brief preserves and whose continued function it requires. Forcing
it to make the phase look complete is precisely what the brief warns against.

**The JSON files and the read-only importer**, unchanged from Phase 10.11.

## Consequences

**Nothing governed moved.** Proven by execution: the three routes answer 404 or
405 with no tenant data; product access, membership, authority resolution,
issuance, revocation and the approval queue all still work; the four refusals
still refuse with the database unchanged; poisoning both JSON files moves no
answer; and the bootstrap import still runs and still creates no authority.

**405 rather than 404 on two of the three.** `GET /api/tenants` and
`GET /api/tenants/{id}/users` share their paths with surviving POST routes, so
FastAPI reports Method Not Allowed. That is a stronger signal than 404, not a
weaker one: the method is gone while the documented refusal remains reachable.

**Two harnesses were updated**, not to make them pass but because they asserted
against a mechanism being removed. Phase 10.9's cross-tenant check required
`[404, 404, 404]` from two writes and one read; it now checks the two surviving
writes and accepts 404/405 for the retired read. Phase 10.11's I3/I4 asserted
the listings read the durable store; they now assert the routes are gone.

**The deletion is smaller than ADR-105 anticipated.** That is a finding, not a
shortfall, and the evidence is above.

## An unrelated observation, recorded not acted on

All three links in the sidebar's Admin section point at pages that do not
exist: `/settings/autonomy`, `/settings/retention` and `/settings/tenants`.
Only the last was authorised for removal and only the last was removed. The
other two are dead navigation and are reported rather than quietly fixed.

## Verification

`scripts/phase1013_retire_v1_reads_harness.py` — **59/59 VERIFIED** against
real k3d, real PostgreSQL and real Redis. 16 negative cases, **0 provider
writes**. Phases 10.7, 10.8, 10.9, 10.10 and 10.11 re-run in full; results in
`docs/PHASE_10_13_VERIFICATION_REPORT.md`.
