# ADR-090 — An approval binds to the action, and reaches the gateway

**Status:** Accepted
**Date:** 2026-09-05
**Extends:** ADR-088 (the execution trust model), ADR-089 (the CONTAINED worker)
**Implementation map:** `docs/PHASE_9_9C_IMPLEMENTATION_MAP.md`
**Verification:** `docs/PHASE_9_9C_VERIFICATION_REPORT.md`

## Context

Phase 9.9B ended with the CONTAINED worker verified and the write refused with
`invocation_refusal=approval_required`. The stated cause was a missing field.
Tracing it turned up three defects, not one, and the second and third are the
reason this is an ADR rather than a bug fix.

## Decision 1 — Carry the approval reference on the sealed binding

`facts_for` built the gateway's re-authorization request with no
`approval_artifact_id`, so the `ApprovalLookup` was never given anything to look
up. It also dropped four approval fields when translating the decision into
`AuthorityFacts`.

The reference now travels: authorization decision → `CapabilityBinding` (sealed
at `create()`, beside `authorization_digest`) → `project_binding` →
`BoundCapability` → `facts_for` → `AuthorizationRequest`.

It is read **from the sealed binding and from nothing a caller supplies**, so no
model output can reach it. The decision's own digest already covers
`approval_artifact_id`, and `authorization_digest` is in the binding's digest
payload, so the approval is transitively sealed into the binding without a new
digest field.

The lookup happens **at the gateway, at dispatch** — not cached from
authorization time. A revoked approval is refused at dispatch. Verified.

## Decision 2 — An approvable digest, distinct from the action digest

`ApprovalFacts.bound_digest` was compared against two different things: the
**capability** digest by `is_valid_for`, and the **action** digest by the
gateway. One field cannot be both, so an approval necessarily failed one of them.

Worse, the action digest includes `binding_digest`, and the binding is created by
resolution *inside* the execution the approval authorizes. **No human could ever
compute it at approval time.** The gateway's action-level check was therefore
unsatisfiable in principle, not merely unfed.

Added: `ApprovalFacts.bound_action_digest`, and `canonical_approval_digest(...)`
— the same facts as the action digest minus `binding_digest` and
`policy_version`:

> capability_ref, capability_digest, operation, tenant_id, principal_id,
> environment, **payload**

That is exactly what an approver can be shown and asked about. Both excluded
fields are execution-internal: which binding resolution produced, and which
policy revision evaluated it, are not things a human approved and do not change
what is about to be done. Authorization re-evaluates the policy at dispatch
independently, so dropping the policy version removes no check.

The payload stays inside the digest, which is the whole point: an approval
granted to restart workload A cannot authorize workload B.

`bound_digest` keeps its existing meaning and its existing check. This is
additive.

## Decision 3 — `approval_required` means the action required approval

This is the one the harness caught, and it was a live security hole rather than
a missing field.

When a presented approval passed the policy's capability-level test,
`CapabilityAuthorizationService` downgraded `REQUIRE_APPROVAL` to `ALLOW`.
`facts_for` computed `approval_required` from that downgraded effect, so it was
`False`, and the gateway's `_check_approval` returned on its first line —
**before the action-digest comparison.** The gateway's strongest approval check
was dead code whenever authorization succeeded.

Measured, on a real cluster, before the fix:

- an approval granted for `billing-api` **successfully restarted
  `payments-api`**;
- an approval bound to no action at all **succeeded**;
- four real writes occurred inside a negative matrix that was supposed to prove
  zero.

`approval_required` now means *"an approval was relied upon for this action"*:

```python
approval_required = (
    decision.effect is PolicyEffect.REQUIRE_APPROVAL
    or bool(decision.approval_artifact_id)
)
```

If an approval was used to allow the action, the gateway must show it covers
*this* action. `AuthorizationDecision` now carries `approval_bound_digest` on
every `allow()` path, not only the one that began as `REQUIRE_APPROVAL`.

After the fix, all sixteen negatives refuse with **zero provider writes**.

## Decision 4 — Attribution by action digest, not idempotency key

The contained worker stamped the restart annotation with an idempotency key. But
a rollout restart is honestly `NON_IDEMPOTENT_WRITE` — a repeat creates another
revision rather than collapsing — so the platform derives no idempotency key for
it, and demanding one would have forced a false `IDEMPOTENT_WRITE` declaration
to make the write possible.

The worker now stamps the **action digest**, which identifies the action just as
well, is what the approval was granted against, and requires no lie about
repeat-safety. `supports_provider_idempotency` stays `False`, honestly.

## Security impact

**Strictly more restrictive than the state before this ADR**, on every axis that
changed:

| | Before | After |
|---|---|---|
| Approval reaches the gateway | never | yes, from the sealed binding |
| Action-level approval check | dead code | runs whenever an approval was relied upon |
| Approval for another workload | **succeeded** | refused |
| Unbound approval | **succeeded** | refused |
| Revoked approval | (unreachable) | refused at dispatch |

Nothing that refused before now passes, except an approval explicitly granted
against that exact action digest.

## Migration impact

- `ApprovalFacts.bound_action_digest` is optional; an approval without one is
  not dispatchable, which is the pre-existing behaviour rather than a new
  refusal.
- `CapabilityBinding.approval_artifact_id` and
  `BoundCapability.approval_artifact_id` are optional and round-trip through
  persistence. Binding digests are unchanged.
- No migration is required: no column was added, and the binding record is JSON.

## What was not done

No `ApprovalServiceV2`, `ApprovalGateway`, `WorkerApproval`,
`WorkerAuthorization`, second approval database or second approval token. No
second executor, gateway, scheduler, credential authority or audit path. The
CONTAINED worker from ADR-089 is reused unchanged apart from Decision 4.
`REQUIRE_APPROVAL`, isolation, `CodeTrust`, `SideEffectClass`, autonomy,
assurance and gateway authorization are untouched. ADR-088 remains authoritative.

## Consequences

CortexPrime performed its **first real irreversible write to a real external
system**: one governed `kubernetes.workload.rollout_restart` against a
disposable k3d Deployment, through approval → authorization → gateway →
CONTAINED worker → Kubernetes, with the outcome established by an independent
read rather than by the worker's answer.

The obstacle has moved four times across 9.6–9.9C — hardware, taxonomy, a
missing field, and finally a dead-code check — and every one of them was found
by running the real chain against real infrastructure. The last was the most
dangerous, and it was found by a negative test that was expected to pass and
did not.
