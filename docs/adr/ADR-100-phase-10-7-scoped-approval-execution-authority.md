# ADR-100 — Scoped approver authority and narrow execution authority

- **Status:** ACCEPTED
- **Date:** 2026-09-06
- **Phase:** 10.7
- **Supersedes:** nothing. **Amends:** ADR-098 (approver authority), in the
  narrow sense described under *Consequences*.

## Context

After Phase 10.5 a person either held approver authority in a tenant or did
not. After Phase 10.6 the requester of an action could not also approve it.
Both are real controls, and together they still left two surfaces wider than
the governed chain they guard:

1. **Approver authority was tenant-wide.** A grant that let someone approve a
   log-level change also let them approve a production rollout restart of any
   workload, because the grant named no capability, no environment and no risk
   ceiling. The one write CortexPrime has commissioned is irreversible.

2. **Execution required no authority at all.** `POST .../execute` checked
   tenant membership and that a valid approval existed. Any member of the
   tenant — including one holding no grant of any kind — could run any granted
   approval. The approval was doing double duty: it authorized *the action*,
   and it was being read as authorizing *whoever happened to call the route*.

Phase 9's chain already refuses an unauthorized action. Neither of these is a
hole in that chain; both are holes in **who may hand an action to it**.

## Decision

**Grants carry scope, and executing is a third act.**

A grant is parsed from the existing `permissions` field on tenant membership —
the same dead field Phase 10.5 brought to life — as
`action:resource:capability_ref:environment[:max_risk]`. `action` is `approve`
or `execute`. `capability_ref` is the **versioned** reference
(`platform.kubernetes.workload.rollout_restart@1`), so a grant does not silently
follow a capability across a version bump.

`resolve_scoped_authority()` in `backend/auth/approver.py` compares a grant
against the capability, environment and risk **of the stored approval row** —
never against anything in the request. Risk is derived by the platform's own
`implied_risk_for()`, the same function authorization uses, so a ceiling is
compared against the same classification the engine would apply. An undeclared
effect is CRITICAL, not LOW.

Both the decision route and the execute route resolve it. The execute route's
check is deliberately **not** a separation rule: the requester may execute, the
approver may execute, a third party may execute — each only if they hold
execution scope. Phase 10.6's invariant is `requester != approver` and nothing
more; turning it into `requester != executor` here would be inventing
governance nobody ratified.

### What was deliberately not built

- **No second authority.** No new engine, no new policy object, no new
  decision point. The scope check sits *inside* the existing authorization
  step, before separation of duties, in `CapabilityPolicy.evaluate`'s
  inherited precedence.
- **No new table, no migration.** Scope lives in the existing `permissions`
  field. The durable schema is unchanged at 22 tables.
- **No new capability.** Phase 9's single commissioned write is still the only
  write.
- **No numeric trust.** No `approver_confidence`, `trust_level` or
  `approval_score`. Authority is categorical and every refusal names the
  dimension that failed.
- **No self-granting.** There is no route through which an approver can widen
  their own scope; grants are issued through `grant_permission` outside the
  product API.
- **No client-side security.** React renders `can_approve` / `can_execute` /
  the reason codes. It computes none of them, and both routes re-resolve
  scope independently of what any projection said.

### Environment scoping is real, not invented

`CapabilityContract.supported_environments` and the approval row's
`environment` column already existed. Part L of the brief permitted a DEFERRED
here; it was not needed.

## Consequences

**A bare `approve:remediation` grant no longer confers authority.** This is a
deliberate, fail-closed breaking change: an unscoped grant resolves to
`grant_is_not_scoped` and the UI says so in those words, so the holder is told
to have it re-issued rather than being told they are not an approver. Phase
10.5's gate still asks "are you an approver at all?"; Phase 10.7 asks "for THIS
action?" — the two layer, and 10.5's exact-string match became a parse so
scoped grants satisfy it.

**Approving and executing can be held separately, and usually should be.** The
product now distinguishes APPROVED — YOU MAY EXECUTE from APPROVED — NO
EXECUTION AUTHORITY rather than offering a button because an approval exists.

**Exactly-once is still not claimed.** Two concurrent executions of one
approval were observed as `[200, 200]` with **1** cluster mutation. That is
reported verbatim. The contract remains at-least-once; no idempotency was
invented for this phase.

## Verification

`scripts/phase107_scoped_authority_harness.py` — **155/155 VERIFIED** against a
real k3d cluster, real PostgreSQL, real Redis and the real tenant store. Ten
personas, each holding a **real** grant for something that is not this action.
47 negative cases, **0 provider writes**, refusals attributed to seven distinct
stopping layers rather than collapsed into "blocked": governance 28,
executor_authority 6, approver_authority 4, approval_state 4, membership 2,
authentication 2, separation_of_duties 1. One real provider write on the
positive path.
