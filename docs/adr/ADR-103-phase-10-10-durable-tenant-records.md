# ADR-103 — Durable, governed tenant records

- **Status:** ACCEPTED
- **Date:** 2026-09-06
- **Phase:** 10.10
- **Completes:** the chain begun in ADR-098 and continued by ADR-101 and
  ADR-102. Tenant → membership → grant → approval → execution is now durable
  end to end.

## Context

Phase 10.8 moved authority grants into PostgreSQL. Phase 10.9 moved membership.
Both still rested on `data/tenants/tenants.json`: `require_tenant` read that
gitignored file on every request and refused when `is_active` was false, so an
edit to it disabled governance for an entire tenant.

Discovery **called** the tenant paths, and found three things source review
would have missed — two immediately, and one only because the harness ran.

### Finding 1 — every tenant in the system disclosed to any admin [VERIFIED]

```
GET /api/tenants  → 200   ['p1010a', 'p1010b', 'p1010c']
```

Phase 10.9 guarded five V1 routes that name a tenant in their path. This one
has no tenant in the path, so the guard never applied. It returned the full
system-wide tenant list — id, slug, domain, plan, state — to any token carrying
`role == "admin"`. That is the map an attacker uses to pick the next target.

### Finding 2 — any admin could create a tenant [VERIFIED]

```
POST /api/tenants → 201
```

An unscoped V1 admin operation with no relationship to the governed authority
model.

### Finding 3 — a third JSON authorization source, found by the harness

`require_user` — the **base authentication dependency**, older than
`require_tenant` and running before it — carried its own tenant check reading
the JSON file. My discovery pass missed it. The harness caught it because a
tenant that existed only in the durable store was refused as "does not exist",
and because flipping the file still refused a request the durable store
permitted. Leaving it would have meant JSON and PostgreSQL were **both**
authoritative — a stop condition — while every other check said otherwise.

## Decision

**The tenant boundary becomes durable, and stays a boundary.**

`cp_tenant` (migration 0022) holds `tenant_id`, a UNIQUE `slug`, `name`,
`status`, `source`, and who created and last changed it. `require_user`,
`require_tenant`, `product_context`, `resolve_approver_authority` and
`resolve_scoped_authority` all read it.

### `organizations` was evaluated and rejected

Part B required proving semantic equivalence before reuse. It fails:
`OrganizationModel` has **no `tenant_id`**, no membership, and no link to any
authority, approval or execution record. It is an org-chart entity with
departments, served by `organization_routes`. The names look alike and the
concepts are not, so they stay separate — and the harness asserts the absence
of a tenant reference rather than trusting this paragraph.

### A tenant confers nothing

A tenant row means an authoritative organizational boundary exists. It does not
admit anybody — membership is `cp_tenant_membership` — and it grants no
approval, execution or issuance authority: those remain Phase 10.8's explicit
scoped grants. Provisioning a tenant produces a boundary **nobody can access**,
which the harness proves rather than asserts.

What it *is* load-bearing for is the other direction: an inactive tenant makes
product access, approval, execution, grant issuance, grant revocation and
membership admission all fail closed.

### Tenant administration stays out-of-band

The authority grammar is capability + environment scoped. A tenant is neither,
so there is no way to express "may create a tenant" without inventing a new
authority action — which Part M forbids, and which would be the second
authority system this phase is told not to build. Phase 10.8 already
established that no role confers authority, so the V1 `role=admin` claim is not
an answer either.

So there is **no product route** for tenant mutation. `bootstrap_tenant` and
`set_tenant_status` are the provisioning path, the same shape as
`bootstrap_grant` (10.8) and out-of-band membership seeding (10.9).

The V1 mutation routes are **refused** rather than repointed at the durable
store: repointing would hand tenant-state authority to an unscoped admin claim
over a now-authoritative store, which is worse than the hole they had, and
leaving them writing the JSON would be worse still — they would appear to work
and change nothing. `GET /api/tenants` now returns only the caller's own tenant.

### No digest, and tenant state stays out of the existing digests

Two decisions, both deliberate. Tenant state is *intentionally* mutable, so a
hash over it would be recomputed by every legitimate change and prove nothing —
the same reasoning Phase 10.9 applied to membership, and the reason Phase 10.8's
grant digest works. And tenant state must **not** enter the capability, approval
or grant digests: those are historical bindings, and folding mutable state into
them would mean deactivating a tenant silently invalidated every approval and
grant ever bound in it. That is rewriting history, a stop condition. The
harness asserts every live grant still matches its own digest after a
deactivation cycle.

### Slug

`slug` has no mutation path and none is added; `tenant_id` is the
authority-bearing identity every other table already keys on. The slug is
UNIQUE and display/lookup only, so the historical-ambiguity problem a rename
would create does not arise.

## Consequences

**The JSON file is no longer authoritative.** It is bootstrap input:
`migrate_json_tenants` imports it deterministically, is safe to re-run, and
creates **no** membership, grant, approval or execution right — measured as a
before/after count. Editing it afterwards changes nothing the platform reads,
and a product request succeeds while the file says the tenant is off.

**An inactive tenant fails closed on every path**, on a token minted while it
was active, and **nothing is deleted**: memberships, grants, approvals and the
tenant row all survive so the history stays attributable.

**Reactivation restores authority.** Measured, not designed: memberships and
grants survive deactivation and become effective again, because neither was
revoked. Removing access permanently means revoking the grant or the
membership, not only switching the tenant off. Reported as a trap.

**Exactly-once is not claimed.** Tenant state is last-write-wins under a
conditional `UPDATE`; re-provisioning a slug is refused by the UNIQUE
constraint (`ConstraintConflict`), reported verbatim.

**Direct database deactivation is honoured.** Per Part U this is recorded as
*the store being the authority*, not as a security bypass — the honest
distinction between legitimate mutation and tampering.

## Verification

`scripts/phase1010_tenant_record_harness.py` — **107/107 VERIFIED** against
real k3d, real PostgreSQL, real Redis and real OS process death. 34 negative
cases, **0 provider writes**, four stopping layers. Phases 10.7, 10.8 and 10.9
re-run on the new substrate; results in
`docs/PHASE_10_10_VERIFICATION_REPORT.md`.
