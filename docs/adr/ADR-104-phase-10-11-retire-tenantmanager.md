# ADR-104 — Retire TenantManager

- **Status:** ACCEPTED
- **Date:** 2026-09-07
- **Phase:** 10.11
- **Completes:** the strangler begun in ADR-101 and continued by ADR-102 and
  ADR-103. Nothing is added here; the decision is what to delete.

## Context

Phases 10.8, 10.9 and 10.10 moved authority, membership and the tenant boundary
into PostgreSQL. Phase 10.10 closed by naming `TenantManager` as the remaining
runtime reason `data/tenants/tenants.json` and `data/tenants/tenant_users.json`
still existed, and both were still listed in `GRANDFATHERED_STORES` — a frozen
inventory that *may only shrink*.

A correction to the premise: **`data/users/users.json` does not exist.** The
two legacy stores are the ones above, and `tenant_users.json` is the file that
actually holds user rows.

### What discovery found

Every reference, classified by reachability rather than by whether a scan
called it unused:

| Consumer | Class |
|---|---|
| `auth_routes._tenant_claims` (login **and** refresh) | runtime production — minted the tenant claim on every session token from JSON |
| `dependencies.require_user` / `require_tenant` | runtime production, durable-first with a JSON fallback |
| `dependencies.get_current_tenant` | **dead** — defined, never imported, never referenced |
| `authority_routes` `members=get_tenant_manager()` | **dead argument** — `issue_grant` prefers `memberships=`, always supplied |
| `tenant_routes` create/deactivate bodies | **dead after a `raise`** (10.10) |
| `tenant_routes` list / get / list_users | runtime production reads |
| `tenant_routes` **add_user / update_user_role** | runtime production writes — see below |
| `TenantManager` mutators + `_save` | the only code writing either file |

### The finding: two live routes were a silent no-op trap

Phase 10.10 refused V1 *tenant* mutation and did not touch V1 **membership**
mutation. `POST /api/tenants/{id}/users` and `PATCH .../users/{id}` were still
live and still wrote `tenant_users.json` — a file that stopped being
authoritative in Phase 10.9.

So an operator added somebody through the V1 API, received **HTTP 201**, and
that person had **no governed membership at all**: no product access, no
authority, nothing. The call appeared to work and changed nothing that mattered.

That is the exact trap Phase 10.10 avoided for tenant mutation by refusing
rather than repointing, and left open for membership.

## Decision

**`TenantManager` becomes a read-only importer, and the inventory shrinks.**

`FileStateRule` flags a module that *writes* a state file and names it; reading
one is explicitly fine. `backend/auth/tenant.py` was the only module that wrote
either file. So every mutator — `create_tenant`, `add_user`,
`update_user_role`, `deactivate_tenant`, `grant_permission`,
`revoke_permission` — and the `_save` behind them are deleted, along with the
`mkdir` in its constructor: a reader creates nothing.

The read methods stay, for exactly one purpose: `migrate_json_tenants` and
`migrate_json_memberships` import these files once. After that they are inert.

**Then, and only then**, both filenames leave `GRANDFATHERED_STORES`. The
inventory shrinks because the writes are gone, not because the list was edited
— and the state-file rule is re-run to prove it, which is what makes the
removal honest rather than an edit that silenced a test.

### The other consumers

- **The login wire** now reads `cp_tenant_membership` and `cp_tenant`. This is
  a deliberate behaviour change in one direction: a login could previously mint
  a tenant claim from a JSON row the governed stores had never heard of,
  producing a token every governed path then refused. The claim now comes from
  the store that will judge it. The fail-closed contract is unchanged — no
  membership, an inactive one, an inactive tenant, or any store failure yields
  **no claims at all**.
- **The dependency fallbacks are gone.** A missing store is not permission to
  consult a file nobody governs; it refuses, like every other unreadable
  authority in this codebase.
- **V1 membership mutation is refused**, naming `POST /api/v1/tenants/members`.
- **V1 reads were repointed at the durable stores** rather than removed,
  because a client asking "who is in my tenant" deserves the real answer.
  `permissions` is projected as empty by construction: authority lives in
  `cp_authority_grant`, and a permission list beside a member is the thing
  Phase 10.5 spent a phase separating from membership.
- **Dead code deleted**: `get_current_tenant`, the `members=` argument, and the
  unreachable remainders of two refused routes.

### The two legacy test modules

`tests/test_tenant.py` and `tests/test_tenant_routes.py` tested the deleted
mutators. Those cases are gone — not correct tests bent to pass, but tests of a
mechanism that no longer exists. Both modules were rewritten to guard the
retirement instead: the read path the migrations depend on, the refusals, the
cross-tenant scoping, and **that the mutators stay gone**, because
reintroducing one would silently put a file store back into an inventory that
may only shrink.

## Consequences

**Nothing governed changed.** That is the whole claim, and it is proven by
mutating both files, deleting them, and running a child process in which
`backend.auth.tenant` cannot be imported at all — all three leave every
governed answer identical.

**The authenticated read path got faster.** Removing the JSON reads took the
p50 from ~355 ms (Phase 10.10) to ~75 ms. Phase 10.10 named the duplicate
tenant read as a cost and deliberately declined to optimise it in the phase
that added it; retiring the legacy reads addressed most of it without touching
a fail-closed check.

**The legacy files remain on disk**, read-only and inert, as bootstrap import
input. A fresh installation has none, and the importer treats that as the empty
import it is.

**Exactly-once is not claimed.** Tenant mutation semantics are unchanged from
Phase 10.10 and reported verbatim.

## Verification

`scripts/phase1011_retirement_harness.py` — **68/68 VERIFIED** against real
k3d, real PostgreSQL, real Redis and real process death. 20 negative cases,
**0 provider writes**. Phases 10.7, 10.8, 10.9 and 10.10 re-run in full;
results in `docs/PHASE_10_11_VERIFICATION_REPORT.md`.
