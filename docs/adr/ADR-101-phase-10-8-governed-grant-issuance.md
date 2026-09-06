# ADR-101 — Governed grant issuance

- **Status:** ACCEPTED
- **Date:** 2026-09-06
- **Phase:** 10.8
- **Amends:** ADR-098 (approver authority) and ADR-100 (scoped authority), by
  moving the grants they read into an attributed durable store.

## Context

Phases 10.5–10.7 made authority *enforcement* governed: an approver's grant is
scoped to a capability, an environment and a risk ceiling; executing requires
its own grant; the requester of an action may not approve it.

Every one of those decisions read a grant that anybody could create. Discovery
established this by **calling the real administrative API**, not by reading it:

| Property | State before this phase |
|---|---|
| Issuer | **No parameter existed.** Not a weak check — an absent concept |
| Validation | `":" in permission`, and nothing else |
| Storage | `data/tenants/tenant_users.json` — and `data/` is **gitignored** |
| Audit | None |
| Digest / version | None |
| Mutability | Editing the file silently replaced authority |
| Scope bound | `environment=production` accepted for a capability supporting only `development` |

Ten escalating strings — `godmode:everything`, `autonomy:A4`,
`approve:remediation:capability=*,environment=*`, comma-injection — were all
**accepted and stored**. None of them was *honoured*: matching is strict
equality and wildcards match nothing real. So the gap was never enforcement.
It was that **authority creation was an unvalidated, unattributed, unaudited
write to an untracked file.**

## Decision

**Creating authority is itself a governed act.**

A new durable table, `cp_authority_grant`, holds every grant with the
attribution it never had: `issued_by`, `issued_at`, `issue_reason`,
`revoked_at`, `revoked_by`, and a `digest` covering every authority-bearing
field. `backend/auth/grants.py` is the only thing that produces a matching
argument set for the repository's `issue`, whose `issued_by` and
`issue_reason` are required keywords with no defaults — routing around the
policy yields a `TypeError`, not an unattributed grant.

Issuance is exposed through two product routes so the issuer is an
**authenticated human** rather than whoever ran a script. That is the whole
reason the routes exist; a service callable only from a shell would have
reproduced the unattributed write this phase closes.

### One authority model, not two

The issuer's own entitlement is resolved by `resolve_scoped_authority` — the
*same* function that decides approval and execution authority — with
`action="issue"`, a third action in the same grammar read by the same parser.
Phase 10.7 added `execute` beside `approve` exactly this way.

This makes **non-escalation free**: "may this issuer issue a grant for
capability C in environment E at ceiling R" *is* "does this issuer hold
issue-authority scoped to C, E and R", answered by the existing strict-equality
matcher with no wildcards.

### What cannot be issued, structurally

`ISSUABLE_AUTHORITIES` is `("approve", "execute")`. **`issue` is not issuable**,
so holding issuance authority never confers the power to spread it — transitive
delegation is impossible rather than forbidden, and Part P's rule (authority to
*use* is not authority to *delegate*) holds without a separate check.

### Why not an existing table

- **`cp_delegation`** is structurally almost perfect and was refused **on
  security grounds**: `DurableDelegationAuthority.delegation_for()` reads it to
  permit **on-behalf-of invocation** at the execution gateway. An authority
  grant written there would silently become an identity-borrowing permission.
- **`cp_approval`** binds a capability *invocation* through
  `canonical_approval_digest`; a grant is not an invocation, and the digest
  would cover a fiction — the codebase's own reasoning for why `delegation.py`
  refuses to reuse `ApprovalArtifact`.
- **The audit ledger** records what happened; it is not a store of what is
  currently true. It carries the *events*, which is what it is for.

Per Part AB this was stopped on and documented in the implementation map
**before** any code was written.

### Does issuance require human approval? — decided explicitly

**No.** Grant issuance *is* an administrative authority change, so the question
is real. But the smallest existing approval mechanism binds an approval to a
capability invocation via `canonical_approval_digest`, and a grant is not an
invocation. Building a second approval workflow for grants is precisely the
"second approval engine" the stop conditions forbid.

Issuance is therefore governed by **issuer authority + separation of duties +
capability bounding + durable audit**. This is a stated policy, not an
inherited "admin can do anything".

### Audit

`AuditEventKind.IDENTITY_EVENT` already means "authentication, authorization,
or credential lifecycle" and is `is_security_relevant`, so it can never be
sampled or truncated away. **No new audit kind was invented.**

## Consequences

**The JSON `permissions` list no longer confers authority.** A deliberate,
fail-closed breaking change of the same kind Phase 10.7 made to bare grants. A
missing grant store answers `authority_store_unavailable` rather than "you hold
nothing" — those send an operator to two different places.

**Tampering is detected, not merely deplored.** `live_grants_for` recomputes
each row's digest and drops any that no longer matches, logging it as an
integrity finding and surfacing `intact: false` in the product projection.
This is detection, not prevention: a database administrator can also recompute
a digest. The honest claim is that **silent** mutation is what becomes
impossible.

**Revocation is deliberately not risk-bounded.** Revoking only ever removes
authority, so a ceiling comparison buys no safety and costs something real — an
issuer could otherwise create a grant and be unable to take it back. A
revocation harder than the issuance it undoes is not fail-closed; it is a
one-way door. This was found by the harness, as a bug, and fixed.

**Bootstrap is a real limitation, stated rather than hidden.** No system issues
its own root of trust. `bootstrap_grant` provisions the first grant out of
band; it is unreachable from any route, attributes itself to `bootstrap`, and
anything that can call it can already write to the database.

**Exactly-once is not claimed.** Two concurrent issuances of the same authority
were observed as `[201, 201]` producing **2** rows sharing **one** digest — two
legitimate attributed acts conferring identical power. No uniqueness was
invented. Two concurrent revocations gave `[200, 409]`.

## Verification

`scripts/phase108_governed_grant_issuance_harness.py` — **118/118 VERIFIED**
against real k3d, real PostgreSQL, real Redis, the real tenant store and real
OS process death. 43 negative cases, **0 provider writes**, refusals attributed
to five distinct layers: governance 21, grant_scope 11, issuer_authority 6,
authentication 3, grant_state 2.

Phase 10.7's harness was re-run on the new substrate: **155/155**, unchanged.
