# Phase 9.9C — Implementation Map (discovery output)

**Written before any production code changed.** Required by the phase brief.

Phase 9.9B ended with the CONTAINED worker verified and the write refused with
`invocation_refusal=approval_required`. This phase traces exactly where the
approval reference is created and where it is lost, and repairs the data-flow
without inventing a second approval system.

---

## 1. The approval lifecycle, traced from source

| Stage | Where | Carries the approval? |
|---|---|---|
| Caller supplies it | `GovernedCapabilityWriter.write(approval_artifact_id=…)` | **yes** |
| First authorization | `_perform` → `AuthorizationRequest(approval_artifact_id=…)` (`capability_execution_composition.py`) | **yes** — *"Carried, never invented."* |
| Lookup + validation | `CapabilityAuthorizationService` → `ApprovalLookup.find(...)` → `ApprovalFacts.is_valid_for(...)` | **yes** |
| Decision | `AuthorizationDecision.approval_artifact_id`, and the artifact id is inside the decision's own **digest payload** | **yes** |
| Resolution | `ResolutionRequest(authorization=decision, …)` — the whole decision is handed over | **yes** |
| Binding seal | `CapabilityBinding.create(authorization_digest=request.authorization.digest, …)` | **LOST HERE** — only the digest is copied |
| Projection | `project_binding` → `BoundCapability` | no field exists |
| Dispatch | `InvocationRequest` | no field exists |
| **Gateway re-authorization** | `facts_for` builds a fresh `AuthorizationRequest` | **LOST HERE** — no `approval_artifact_id` |
| Gateway check | `_check_approval` | refuses |

### The two precise loss points

**Loss 1 — `facts_for` builds its `AuthorizationRequest` without
`approval_artifact_id`.** The re-authorization therefore looks up nothing,
`approval_valid` is always `False`, and `REQUIRE_APPROVAL` always refuses.

**Loss 2 — `facts_for` builds `AuthorityFacts` without four approval fields.**
`approval_present`, `approval_valid`, `approval_bound_digest` and
`approval_expires_at` are never set and default to `False`/`None`. Even a valid
decision would not survive the translation.

---

## 2. The semantic collision underneath the missing field

This is the part that is **not** a simple missing field, and the brief asked for
it to be surfaced rather than papered over.

One value, `ApprovalFacts.bound_digest`, is compared against two different things:

| Consumer | Compares `bound_digest` against | Source |
|---|---|---|
| `ApprovalFacts.is_valid_for` | the **capability contract digest** | *"An approval for version 1 must not authorize version 2 (digest)"* |
| `InvocationGateway._check_approval` | the **ADR-038 action digest** | *"The action digest the approval was granted against… an approval for repository A must not authorize repository B"* |

These are different digests. A single `bound_digest` cannot equal both, so under
today's code an approval either fails `is_valid_for` or fails the gateway. The
gateway additionally refuses outright when `approval_bound_digest is None`:

> *"the approval is not bound to a specific action; an unbound approval would
> authorize anything this capability can do"*

**The design is right and complete; the carrier is not.** The gateway already
demands action-level binding, which is exactly the property that stops
approval-for-A being replayed as approval-for-B. It simply has no field that can
supply it.

`AuthorizationRequest.approval_digest` exists but is **not** that carrier: it is
undocumented, read only by the delegation path (`delegation.py`), and never
consulted by `is_valid_for`.

---

## 3. The repair — additive, fail-closed, no new authority

1. **`ApprovalFacts.bound_action_digest`** *(new, optional)* — the ADR-038 action
   digest the approval was granted for. `bound_digest` keeps its existing meaning
   (capability digest) and its existing check. `AuthorizationSnapshot.approval_bound_digest`
   is populated from the new field instead of the old one. **This is the
   governance change, and it is documented in ADR-090 rather than hidden.**
2. **`CapabilityBinding.approval_artifact_id`** — sealed at
   `CapabilityBinding.create(...)` from `request.authorization.approval_artifact_id`,
   in the same place `authorization_digest` is already copied. Round-trips
   through `persistence.py`.
3. **`BoundCapability.approval_artifact_id`** — carried by `project_binding`.
4. **`facts_for`** — passes `binding.approval_artifact_id` into its
   `AuthorizationRequest`, and copies `approval_present`, `approval_valid`,
   `approval_bound_digest` and `approval_expires_at` from the decision onto
   `AuthorityFacts`.

### Why this cannot weaken anything

Today `approval_bound_digest` is always `None`, so the gateway refuses **every**
approval-requiring dispatch. The repair moves behaviour from *"always refuse"* to
*"refuse unless the approval is bound to this exact action"*. Nothing that
refuses today can start passing except an approval explicitly granted against
that action digest. There is no path where this makes the platform more
permissive than the design already intended.

### Why the model can never supply it

The artifact id reaches the binding from the **decision**, not from any payload.
The decision only carries it because a caller presented it to the first
authorization, where `is_valid_for` checked tenant, governance operation, expiry
and capability digest. The decision's own digest payload includes the artifact
id, and `authorization_digest` — which is in the binding's digest payload —
covers that decision. So the approval is already transitively sealed into the
binding, and a swapped id would not survive the gateway's action-digest
comparison in any case.

The worker receives `approval_ref` as an opaque, non-empty string. It has no
lookup, no validator and no authority over it; it refuses when the field is
absent and can do nothing else with it.

### Revocation is preserved

The lookup happens **at the gateway**, at dispatch, not at authorization time. An
approval revoked between authorization and dispatch returns `DENIED`/absent from
`ApprovalLookup.find`, and dispatch refuses. Nothing caches approval validity.

---

## 4. What is NOT being built

- No `ApprovalServiceV2`, `ApprovalGateway`, `WorkerApproval`,
  `WorkerAuthorization`, second approval database or second approval token.
- No second executor, gateway, scheduler, credential authority or audit path.
- `REQUIRE_APPROVAL`, isolation, `CodeTrust`, `SideEffectClass`, autonomy,
  assurance and gateway authorization are untouched.
- The CONTAINED worker from 9.9B is **not rebuilt**; it is reused as-is.

---

## 5. Fitness rules

None planned. The candidate concern — an approval reference supplied by a model —
is structurally impossible after this repair, because the field is read from the
sealed binding and never from a payload. A rule restating that would be cosmetic.
A rule will be added only if implementation reveals a genuine gap, with
`CURRENT = PASS` and `SYNTHETIC = FAIL` demonstrated.

---

## 6. Stop rule

The write happens only after the full negative matrix passes. If approval binding
is ambiguous, model-controllable, cross-tenant, or survives revocation, the phase
stops before the write and says which property failed — as 9.6, 9.7 and 9.9B did.
