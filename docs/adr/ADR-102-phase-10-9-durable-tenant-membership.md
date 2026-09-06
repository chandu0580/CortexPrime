# ADR-102 — Durable, governed tenant membership

- **Status:** ACCEPTED
- **Date:** 2026-09-06
- **Phase:** 10.9
- **Amends:** ADR-098, ADR-100 and ADR-101, by moving the membership those
  authorities resolve against into a durable, attributed store.

## Context

Phase 10.8 gave authority grants a durable home with an issuer, a digest, a
revocation path and an audit trail. Every one of those grants points at a
*subject*, and who that subject was — whether they belonged to the tenant,
whether they were still active — was answered by
`data/tenants/tenant_users.json`.

Discovery **called** the membership paths rather than reading them, and two
findings would have been missed by source review alone.

### Finding 1 — cross-tenant membership mutation over a live route

`backend/api/tenant_routes.py` is registered in the V1 app. It takes
`tenant_id` from the **path** and guards with `require_admin`, which checks a
JWT `role == "admin"` claim and **no tenant at all**. With an admin token
scoped to tenant A:

| Against tenant **B** | Result |
|---|---|
| `POST /api/tenants/{B}/users` | **201** — a member was planted |
| `PATCH /api/tenants/{B}/users/{id}` | **200** — role changed to `owner` |
| `GET /api/tenants/{B}/users` | **200** — full member disclosure |
| `POST /api/tenants/{B}/deactivate` | **200** — tenant B deactivated |

Severity, stated precisely: membership alone grants nothing after Phase 10.8,
so this is not privilege escalation into another tenant's *actions*. It **is** a
cross-tenant **denial of governance** — deactivating tenant B makes every
authority there answer `tenant_inactive` — plus disclosure of another tenant's
membership list.

### Finding 2 — product access never checked membership

`product_context` verified signature, revocation, tenant claim and that the
*tenant* was active. It never asked whether the subject belonged to it. A
subject with **no membership at all**, and an **inactive** member, both got
**HTTP 200** on the product API — including the authority-grant listing, which
is precisely the reconnaissance an attacker wants.

## Decision

**Membership becomes a durable, attributed primitive — and stays a primitive.**

`cp_tenant_membership` (migration 0021) stores the relation and its state:
tenant, subject, `status`, an informational `role`, `source`
(`migrated` / `admitted`), and who created and last changed it. It is
deliberately **not a user table**: no credential, no display name, no profile,
so it cannot grow into a second identity system.

### Membership ≠ authority

A membership says one thing: *this subject belongs to this tenant.* It does not
confer approval, execution, issuance or autonomy — those remain Phase 10.8's
explicit scoped grants, and no column here maps to any of them. `role` is
carried and **never read by a decision**, preserving Phase 10.5's rule that a
tenant owner is not an approver. The membership listing states this in its own
payload rather than leaving a reader to infer it from a role column.

What membership *is* load-bearing for is the other direction: an inactive
membership makes every authority fail, because a grant must never resurrect a
membership somebody took away.

### Who may administer it

Holding at least one live `issue` grant in the tenant — a **presence** check
against Phase 10.8's store, not a scoped match, because membership names no
capability and forcing one in would invent a dimension.

This reuses the existing authority rather than adding a fourth action. An
issuer already holds the strictly more dangerous power of creating approval and
execution authority, and a member-admin who could not issue grants could still
create the principals grants attach to. **No new authority, no new action, no
new escalation surface** — which Part AB requires.

The limitation is real and stated: **admission and issuance are not separable
today.**

### No digest, deliberately

Membership is *intentionally* mutable — activating, deactivating and relabelling
are legitimate operations. A hash over those fields would be recomputed by every
legitimate change and prove nothing. That is exactly why Phase 10.8's grant
digest works: a grant's authority-bearing fields are immutable once issued.
Integrity here comes from the audit trail, not from hashing a field designed to
change. Part Q's warning — *do not confuse database mutability with security
failure* — is the reason.

### The routes carry no tenant

`POST /api/v1/tenants/members` and its siblings take the tenant from the
verified session. There is no path, query, header or body parameter through
which a caller could name another tenant, so cross-tenant administration is
**unrepresentable rather than refused**. The V1 routes were repaired separately:
the path tenant must equal the caller's own, and a mismatch is a 404, because a
tenant may not learn that another tenant exists.

## Consequences

**The JSON file is no longer authoritative.** It remains bootstrap/import input:
`migrate_json_memberships` imports it deterministically, is safe to re-run, and
creates **no** grant, approval or execution right — a migration that handed out
authority while moving membership would be the quietest possible privilege
escalation. Editing the file afterwards changes nothing the platform reads.

**Deactivation fails closed on every path** — product access, approval,
execution, grant issuance and grant revocation — on a token minted while the
member was active, because membership is resolved live.

**Reactivation restores existing grants.** This is the **measured** behaviour,
recorded rather than designed: grants are revoked separately and were not
revoked by the deactivation. An operator removing authority permanently must
revoke the grant, not only the membership. Reported as a limitation, not
presented as a feature.

**Tenant records themselves remain in the JSON file.** Only membership moved.
The cross-tenant deactivation path is closed regardless, because that was an
authorization defect rather than a storage one — but tenant existence and
activity are still file-backed, and this is named as the remaining gap.

**Exactly-once is not claimed.** Membership mutation is last-write-wins under a
conditional `UPDATE`; concurrency is reported verbatim.

## A defect this phase found in the existing audit model

`AuditWriterLeadership` renews its 30-second lease **only when something is
audited**. A process that governs nothing for half a minute therefore loses
writer status *silently* and never regains it, and every later mutation commits
unaudited. Phase 10.8's grant audit had the same exposure and its harness
passed only because the section ran inside the window.

Fixed: a lapsed lease is re-acquired once and the append retried — deliberately
once, so that a process does not fight a legitimate holder for the pen. An
audit gap that appears only after a system has been quiet is exactly the gap
nobody notices.

## Verification

`scripts/phase109_membership_harness.py` — against real k3d, real PostgreSQL,
real Redis, the real tenant store and real OS process death. Results, stopping
layers and limitations are in `docs/PHASE_10_9_VERIFICATION_REPORT.md`.
