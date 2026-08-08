# ADR-034 — Capability authorization and admission

**Status:** Accepted
**Date:** 2026-08-08
**Phase:** 3.2.3 — Capability Authorization + Admission
**Extends:** ADR-032 (identity and registry), ADR-033 (discovery and ingestion)
**Related:** ADR-005 (connector vocabulary), ADR-016, ADR-017, ADR-018

---

## 1. Authorization is not discovery, and admission is not authorization

Three separate questions, three separately observable boundaries:

```
discovery   → what exists?              (3.2.2, produces candidates)
registry    → what does it claim?       (3.2.1, produces definitions)
authorize   → is this principal permitted?
admit       → may this proceed right now?
resolve     → which one should we use?  (3.2.4, not built)
execute     → do it                     (not built)
```

`authorize()` and `admit()` are separate because **time passes between them**. A
decision made thirty seconds ago is evidence about thirty seconds ago; a
capability can be revoked or quarantined in the gap. Admission re-reads the
authoritative record rather than trusting the decision's account of the world.
Verified:

```
authorize → ALLOW
(capability revoked)
admit     → DENY  ('capability_revoked', 'admission_state_changed')
```

## 2. Three types, and why policy sees only one

`AuthorizationRequest` (what is asked) → `AuthorizationSnapshot` (the evidence,
assembled by the service from authoritative reads) → `AuthorizationDecision`
(the answer).

Policy is handed the **snapshot** and nothing else — no repository, no service,
no way to fetch. An evaluator that could look things up would have inputs nobody
can enumerate, and a review could not reconstruct why a decision went the way it
did. Everything a decision rests on is in the snapshot, which is why the snapshot
is what feeds the digest.

## 3. Default deny, structurally

`AuthorizationDecision` has **no default effect**. Every construction states one,
and every path that does not reach a successful policy evaluation constructs a
denial with a machine-readable reason. There is no code path returning "allowed"
by omission.

`GuardedPolicy` wraps every evaluator — including caller-supplied ones — so an
exception, a `None`, a malformed verdict, or an unexplained non-allow becomes
`DENY / POLICY_UNAVAILABLE`. There is no configuration that changes this. The
permissive branch is absent rather than optional. Verified: a policy engine that
raises denies; one that returns a string denies.

## 4. Pinning: version, digest, operation

- **Version** — `CapabilityRef` is pinned. `latest` is refused at parse time
  (ADR-032), so it cannot even be expressed as an authorization target.
- **Digest** — mandatory for `invoke`. A request that does not state which
  contract it believes it is authorizing is asking about whatever the version
  currently says. Mismatch and absence are both denials.
- **Operation** — authorization is per-operation, never per-capability.
  Authorizing a capability rather than an operation is how permission to read
  becomes permission to delete.

## 5. Principal, and the spoofing gap that was closed

The principal is the **subject**; the owner is a different concept and never an
authorization. There is no `owner == principal → allow` rule and no field that
would make one easy to write.

**A real gap found during implementation:** the request carries a principal while
grants are read from `IdentityContext`. If those may disagree, a caller can name
one principal and be evaluated with another's privileges. The service now
requires the request principal to be the authenticated principal, or one
explicitly linked by `on_behalf_of`. Verified: `mallory` cannot obtain a decision
about `alice`.

## 6. Two-axis admission, uncollapsed

Lifecycle and trust remain separate (ADR-032). `ENABLED + QUARANTINED` is a legal
state and is **refused** — verified. There is no `allow_disabled`, and no
administrative bypass on the ordinary execution path: a bypass on the ordinary
path becomes the path.

Facts are checked **before** policy — existence, tenancy, digest, lifecycle,
trust, environment. Not for speed: these are facts and policy is judgement. A
policy that could allow a revoked capability is a policy that could be written
wrongly; one that never sees revoked capabilities cannot be.

## 7. Tenant isolation and information disclosure

Cross-tenant requests receive `capability_not_found` — the same answer as genuine
absence. Verified: another tenant asking about `tenant.acme.deploy_rollback@1`
learns only `capability_not_found`, with no provider, owner, trust state or
version leaked. `DenialReason.is_disclosure_safe` marks the three reasons safe to
return across a boundary.

## 8. Policy: one seam, not a fifth engine

`CapabilityPolicy` is a two-member Protocol. CortexPrime's existing RBAC/ABAC/PBAC
code and any future OPA integration adapt to it at the composition root.

`GrantBackedPolicy` is the built-in default: it reads the grants the identity
already carries (`IdentityContext.capabilities`), applies separation of duties,
and escalates by risk. It exists so the platform is **governed now** rather than
open until an external engine is wired — a registry nobody can use is safe and
useless, and teams route around it.

**Deliberately not wired:** an adapter to `backend/identity/authorization` or
`backend/security_center/rbac_abac`. Mapping their role model onto capability
operations is a decision to make with the people who own those modules; guessing
it would quietly grant lifecycle powers nobody intended.

## 9. Risk escalation, and a defect found in its direction

High and critical work requires an approval behind it. **But only for operations
that increase exposure.**

The first implementation gated *every* high-risk operation, which meant revoking
or disabling a destructive capability required sign-off. That has the escalation
backwards at exactly the moment it matters: a destructive capability is the one
somebody needs to shut down at three in the morning. `reduces_exposure` now
exempts `DISABLE`, `REVOKE`, `QUARANTINE` and `DEPRECATE`. Verified.

An **undeclared effect** (`EffectSemantics.UNKNOWN`) is `CRITICAL` risk and yields
`REQUIRE_APPROVAL`, never a silent allow. Undeclared never becomes safe.

## 10. Approval integration — reused, not rebuilt

No new approval system, no new signing, no second integrity mechanism.
`ApprovalLookup` reads the existing one and returns `ApprovalFacts`; validity is
checked against **every** binding dimension. Verified that an approval fails to
authorize when it is for another version's digest, another operation, another
tenant, expired, or not granted.

`NoApprovals` is the default when nothing is wired: every lookup fails closed, so
a policy demanding approval refuses rather than waving through.

## 11. Decision binding, digest, expiry, replay

A decision records tenant, principal, capability ref, capability digest,
operation, binding key, policy version, reasons, risk, approval reference,
break-glass flag, decided-at and expires-at — digested with **platform canonical
hashing**, no new algorithm.

`binding_key` bounds replay: a decision is usable only for the exact
tenant/principal/capability/operation/execution/workflow/mission it was made for.
Presenting it for another execution is refused with `BINDING_MISMATCH` and
recorded as `REPLAY_ATTEMPT_DETECTED`. Verified.

Decisions expire (default 300s) and expiry is **never extended** — renewal is a
new evaluation. Verified that an expired decision is refused at admission.

There is no `authorization_token = "allowed"` anywhere.

## 12. Policy versioning

Every decision records the policy version that produced it, so "what authorized
this?" remains answerable after policy changes. Historical decisions are
immutable; a new evaluation produces a new decision. `admit()` returns the
original decision unchanged when it holds and a **fresh** denial when it does not
— never a mutated one, because rewriting a decision destroys the audit trail.

## 13. Break-glass

Reuses the existing `AuditEventKind.BREAK_GLASS_INVOKED`. Never a bypass: it does
not skip evaluation, audit, or binding. It requires an identity, a reason, and an
expiry, all enforced at construction — an emergency lever nobody has to sign for
is a back door.

## 14. Registration is no longer open

`OpenRegistration` (ADR-032) is replaced by `PolicyBackedRegistrationGuard`,
installed at startup in `router_registry`. Every lifecycle operation is
authorized **as itself**:

`register · validate · enable · disable · deprecate · revoke · trust · quarantine`

A principal holding `capability:register` is **not** thereby permitted to enable
or trust — verified. An unmapped lifecycle operation is refused rather than
waved through, so a new operation added later must be classified before it is
permitted.

**Separation of duties:** the owner of a capability cannot enable or trust it.
Verified. Combined with 3.2.2's rule that discovery lands everything
REGISTERED/UNVERIFIED, a self-declared capability cannot make itself available:
it does not arrive enabled, and the principal who declared it cannot be the one
who enables it.

Provenance remains an input, never a grant. `source == INTERNAL` authorizes
nothing.

## 15. Audit — denials are first-class

Reuses the durable audit runtime. No `authorization.log`, no new store. Allows
record as `POLICY_EVALUATED`; refusals as `EXECUTION_REFUSED`; approval
requirements as `APPROVAL_REQUESTED`; break-glass as `BREAK_GLASS_INVOKED`;
replay attempts as `REPLAY_ATTEMPT_DETECTED`. Each carries actor, payload digest,
reasons, policy version and binding key — and no secrets.

A security system recording only successful actions cannot explain why an attack
was stopped. Verified: denials appear in the audit store with their reason codes.

**Audit failure cannot change a decision.** It is logged and swallowed *after* the
decision exists, so it can neither turn a denial into an allow nor break an allow.
Verified both directions.

## 16. What was deliberately not built

No resolution, ranking, provider selection, version selection, or semantic search
(3.2.4). No execution of any kind. No credential system — if a rule needs
credentials, that is a Protocol seam and a later architecture. No new
authentication system. No LLM anywhere in the decision path: authorization is
deterministic and inspectable, and a model must never become the final gate. No
changes to Execution, Workflow, Mission, Intent, Planner, or `WorkerKindResolver`.

## 17. Compliance

- **S2** — imports only `contracts/` and `platform/`; verified it imports none of
  execution, mission, intent, planner, workflow.
- **I1** — a recorded policy decision is produced regardless of what grants a
  principal holds; grants are an input, never a substitute.
- **ADR-017 / BC-9** — explicit `ExecutionContext` throughout; no contextvars, no
  default tenant, no `TenantRef("system")`.
- **ADR-018** — no new authoritative file store.
- Reused: `PolicyEffect`, `RiskLevel`, `Obligation`, `ObligationKind`,
  `ApprovalOutcome`, `PayloadDigest`, `PrincipalRef`, `IdentityContext`,
  `AuditEventKind`, `AuditRuntime`, platform canonical hashing. No second policy
  engine, approval system, identity model, audit system, or hash implementation.

## 18. Known limitation, stated

`GrantBackedPolicy` is a coarse grant check, not an authorization model. It has no
roles, no rule language, and no inheritance. It is a floor that closes the open
door 3.2.2 left, and it is designed to be replaced by the existing engine through
the same Protocol. A deployment relying on it should understand it is running a
placeholder — a named one, which is the improvement over `OpenRegistration`.

Everything remains in-memory, unchanged from 3.2.1.

## 19. Phase 3.2.4 boundary

Resolution consumes decisions and never recomputes them. The resolver will ask
"which capability should serve this request?", select among candidates it is
already authorized for, and bind. It should never need to know how authorization
was computed — which is why the decision is a self-contained, digested, bound,
expiring record rather than a reference into this service's internals.
