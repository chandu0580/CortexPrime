# ADR-098 — Phase 10.5: approver authority

**Status:** Accepted (implemented)
**Date:** 2026-09-06
**Extends:** ADR-097 (approval queue), ADR-096 (human approval and remediation), ADR-090 (approval binds to the action)
**Map:** `docs/PHASE_10_5_IMPLEMENTATION_MAP.md`
**Verification:** `docs/PHASE_10_5_VERIFICATION_REPORT.md`
**Harness:** `scripts/phase105_approver_authority_harness.py` — 131/131

Labels: `[FACT]` verified from this repository or a live run, `[DECISION]`,
`[CONSEQUENCE]`.

## Context

CortexPrime treated tenant membership as sufficient authority to approve an
irreversible action. That was survivable while approvals were reachable only
from the investigation that raised them. Phase 10.4 put every pending decision
in one queue, which hands every member of a tenant a list of every irreversible
action awaiting authorization — so `tenant member != approver` had to become
structural.

## Decision 1 — An explicit grant on the membership, not a role `[DECISION]`

`[FACT]` `TenantUser.permissions` already existed, was already tenant-scoped,
was already durable — and was consulted by nothing. Approver authority is the
single grant `approve:remediation` stored there.

Not a role: `TenantUser.role` is a single field, so making approval a role would
force an owner who needs to approve to stop being an owner.

`[DECISION]` The grant means only *may decide an existing approval request in
this tenant*. It confers no execution. `[FACT]` No new table, no migration, no
new route — the product's non-GET routes are still exactly the three from
Phase 10.3.

## Decision 2 — No wildcard may confer approval `[DECISION]`

`[FACT]` The existing `PERMISSIONS` table gives `owner` `["*"]` for read, write
and admin. A permission reachable through one of those would be the blanket
approval authority the approval system exists to prevent.

`[FACT]` No role carries an `approve` action, and
`check_permission(role, "approve", …)` is False for every role × resource pair —
asserted by the harness rather than assumed. **A tenant owner is not an
approver**, which is the point: an owner is a membership, and membership is
exactly what stopped being sufficient.

## Decision 3 — Authority is read from the store, never from the token `[DECISION]`

`[FACT]` Phase 10.2 mints the tenant membership role into the JWT. A check
against that claim would keep honouring a revoked grant until the token expired.

`[DECISION]` The token establishes *who is calling* and *which tenant*; the
authoritative store establishes *what they may do*, on every request.

`[FACT]` Proven with a token minted **before** the revocation: the same token is
refused 403 with zero provider writes, and the queue immediately reports no
authority for it. `[FACT]` A token whose `user_role` claim says `owner` changes
nothing — a plain member holding one is still refused.

`[CONSEQUENCE]` One store read per decision and per queue projection. The
alternative is a window in which a removed approver can still authorize an
irreversible write.

## Decision 4 — The check runs before the decision and adds nothing after `[DECISION]`

```
authenticate → tenant from the token → APPROVER authority from the store
  → resolve the approval under that tenant → still actionable → the existing
    approval authority decides
```

`[FACT]` Asserted from the authority module's **parsed imports and calls** — not
its prose — that it cannot execute, dispatch, mint an approval, compute risk or
autonomy, or reach a provider or credential. An earlier version of that check
scanned raw text and failed on the module's own docstring, which names the
things it does not do; the AST check is strictly stronger and does not punish
the file for documenting its boundaries.

## Decision 5 — The queue projects authority; it stores none `[DECISION]`

`can_approve` is the approval's state **and** the caller's authority, resolved
server-side per request. `[DECISION]` It is kept **separate from `actionable`**:
collapsing them would make "you may not decide this" and "nobody may decide
this" indistinguishable, and a responder who cannot tell them apart cannot tell
whether to find a colleague or let it expire.

`[DECISION]` Rows are **not hidden** from a non-approver. Hiding them would leave
a member unable to see what is waiting and unable to distinguish a permission
boundary from a tenant one. The screen says plainly that they hold no authority
and offers no decision form at all.

## Decision 6 — Self-approval is reported, not changed `[DECISION]`

`[FACT]` Separation of duties exists and **is enforced** — for a different pair:
a capability owner may not be the one who makes it live, with a dedicated
`DenialReason.SEPARATION_OF_DUTIES`. `[FACT]` No rule requires a remediation
requester to differ from its approver; `cp_approval` stores both, so the
distinction is representable but unenforced.

`[DECISION]` **SUPPORTED-BY-CURRENT-POLICY**, tested in both directions and
recorded. Adding the constraint silently would be inventing governance; removing
it silently would be weakening it. Both are stop conditions. Recommended as its
own phase.

## Decision 7 — One fitness rule, after measuring the bypass `[DECISION]`

`[FACT]` Injecting `from backend.platform.transport import broker` into
`backend/auth/approver.py` left the gate **PASS**: no existing rule names
`backend/auth`. That is a measured gap, not a hypothetical one.

`BND-AUTH-CANNOT-EXECUTE` forbids the auth plane importing a gateway,
dispatcher, connector, adapter, transport, credential broker or scheduler.
`[FACT]` Sensitivity-tested in both directions. `backend.infrastructure.redis`
is deliberately allowed — the token blacklist needs it, and reading a revocation
list is not executing.

## What this ADR does NOT decide

- It does not narrow **execution** authority: triggering the execute route still
  requires tenant membership plus a granted approval. It can run only the exact
  digest-bound action an approver approved, and the gateway re-checks
  everything — but the gap is named rather than implied to be covered.
- It does not add finer scope. An approver may decide any approval in their
  tenant; per-capability, per-environment and per-risk scope do not exist in the
  primitives today, and Part D says to document that rather than pretend to
  granularity the system cannot enforce.
- No new capability was commissioned. No RAG. No model-driven authorization. No
  exactly-once claim.

## Status of the invariants

`[FACT]` 131/131. 39 negative cases, **0 provider writes**, refusals attributed
across six layers. One real provider write on the positive path, the
already-commissioned `kubernetes.workload.rollout_restart`. Both digests
unchanged by a decision. Architecture gate PASS (37 passed, 0 failed, 6 skipped,
1194 modules). Frontend 106/106. No new table, no migration, no new authority,
no new role.
