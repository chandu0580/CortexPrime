# ADR-038 — Secure Capability Invocation Gateway

**Status:** Accepted
**Date:** 2026-08-08
**Phase:** 3.3.3 — Secure Capability Invocation Gateway
**Extends:** ADR-037 (adapter fabric), ADR-036 (worker contract), ADR-035 (binding), ADR-034 (authorization), ADR-031 (durable execution)

---

## 1. Purpose

Four components each recorded a fact at a different moment: the capability was
registered and trusted (ADR-032), the principal was authorized (ADR-034), a
binding was made (ADR-035), a worker was selected (ADR-037).

**Nothing checked that they still agree with each other** at the instant
something is about to happen to a production system. That gap is where a
revoked capability, a withdrawn grant, an expired approval or a rebuilt worker
lands between "we decided" and "we acted".

This is that check. It is not a new authorization system, not a new registry,
not a new resolver, not a second policy engine and not a second audit framework.
It asks the existing authorities whether what they said is still true, *together,
now*, and refuses if any one disagrees.

## 2. The authority chain

```
identity → tenancy → binding → authorization → approval → worker
→ input → action digest → obligations → freshness → lease → rate → credentials
→ invoke once → result integrity → record → audit
```

**The order is itself a security property.** Identity first, because everything
downstream is scoped by it. Input validation before the action digest, because
digesting first would bind whatever arrived rather than what was checked.
Credentials **last**, after every authorization check has passed, so a request
that was going to be refused never causes a secret to be minted — verified.

Refusal ordering is fixed, so a request wrong in three ways always names the
same one first. A reason that varied by evaluation order would make two
identical requests look like two different problems.

## 3. `InvocationRequest`

Immutable, references only. Carries ids and digests, never upstream aggregates:
a request that embedded a binding would let a caller present one of its own
construction; one carrying `binding_digest` can only *name* a binding, and naming
one that does not match is a refusal.

There is no `set_capability`, no `change_worker`, no `rebind`, no `change_tenant`
and no `change_operation` — absent, not discouraged.

**Deviation from the directive, stated:** `capability_id` and
`capability_version` are carried as the single rendered `capability_ref`
(`namespace.provider.capability@version`) rather than as two fields. ADR-036
established that Execution never parses that string; splitting it here would
require exactly the parsing that decision forbade. Comparing the whole token
enforces both clauses at once and **cannot drift between them** — there is no
state where the id matches and the version does not. Parsing happens once, at the
composition root, which is the translation layer by definition.

## 4. Identity and principal binding

The authenticated principal is the only one that was proved. A principal
supplied alongside the request is never trusted:
`request.principal == context.identity.principal`, or refuse.

Delegation is preserved, not flattened. `principal` (the actor) and
`on_behalf_of` (the original requester) stay distinct and both must match the
authenticated chain — collapsing them loses which of the two a decision was made
about.

## 5. Tenant binding

One tenant across context, request, binding and authorization, or refuse. No
`TenantRef("system")`, no ambient `contextvars`, no global current tenant, no
inference from capability owner, provider, worker, body or route.

A **platform-internal context is refused outright** for tenant capabilities: it
has no tenant of its own to match against, so it must never become a way to reach
one.

## 6. Authorization revalidation

A binding being valid says the *target* is still the one chosen. It does not say
the principal may still invoke it. Between binding and invocation a grant can be
withdrawn, a policy can change, an approval can expire — and every one of those
must be able to stop work already in flight.

So `CapabilityAuthority` re-asks `CapabilityAuthorizationService.authorize` at
invocation time. The same service, the same policy, asked again at the moment it
matters. Not a cache read, and not a second engine.

| Answer | Result |
| --- | --- |
| `DENY` | refuse |
| `REQUIRE_APPROVAL` without valid approval | refuse |
| `ALLOW` | continue |
| decision missing (`None`) | refuse — **never allow** |
| authority raises | refuse — unverifiable is unusable |
| no authority wired | refuse |
| expired | refuse |
| any other effect value | refuse |

Tenant, principal, operation, capability digest and environment on the decision
must all match the request. A `policy_version` differing from the one the binding
was authorized under refuses with `POLICY_VERSION_CHANGED`: the rules changed
under a live binding, and proceeding silently would execute under rules nobody
applied to it.

## 7. Approval binding

"There is some approval" is never sufficient. The approval must be bound to the
**action digest** — which covers capability, operation, validated input, tenant,
principal, environment and binding.

That single comparison is what makes both directive cases structural rather than
aspirational: an approval for `github.delete_repository` cannot authorize
`github.create_repository` (different operation → different digest), and an
approval for repository A cannot authorize repository B (different input →
different digest). An unbound approval refuses, because it would authorize
anything the capability can do. An expired approval is not a weaker approval; it
is none.

## 8. The canonical action digest

One digest, computed with platform hashing over `canonical_bytes`, which sorts
keys — so **Python dict ordering cannot determine what was authorized**. Verified:
two semantically identical payloads produce one digest.

Covers: capability ref, capability digest, operation, tenant, principal,
environment, binding digest, policy version, validated input.

Excludes: timestamps, worker health, availability, and **the attempt number**. A
digest that changed between an approval and the execution of the thing approved
would make approval unenforceable; one including the attempt number would make
each retry a different action, which is exactly backwards.

Computed **after** validation, over the validated payload. `action_digest()`
takes the payload as a parameter rather than reading it from the request, so
digesting the unvalidated input requires deliberately passing it.

## 9. No payload rewrite

After validation and digest, the payload is frozen. The adapter receives exactly
what was digested, so what was authorized and what executes are the same bytes.
A declared digest that disagrees with the computed one refuses with
`PAYLOAD_DIGEST_MISMATCH` — that is how a payload swapped between approval and
invocation is caught.

## 10. Input validation

The gateway is the **authority boundary** for validation. It has its own
validator port, separate from the runtime's, and both run: sharing one instance
would mean a single wiring mistake removes both, which is what defence in depth
is supposed to survive.

Absence fails closed. A request carrying a payload with no validator refuses. A
validator that raises refuses. There is no "best effort validate", and the worker
never becomes the primary validator — its own checks are defence in depth.

*Observed ordering note:* the directive places worker selection before input
validation, and the runtime performs its own validation inside the worker check.
So when only the runtime's validator is wired, the refusal surfaces at the worker
stage as `INPUT_VALIDATION_UNAVAILABLE`. Both layers fail closed; only the
attributed stage differs. Verified in both configurations.

## 11. Effect semantics

Reused, never duplicated. `EffectSemantics.UNKNOWN` **fails closed at the
gateway** — an undeclared repeat is what turns one production change into two, and
no worker's opinion upgrades it. The Phase 3.1 effect-anomaly behaviour (a worker
reporting a stronger or weaker effect than bound) remains authoritative and
unchanged.

## 12. Risk and obligations

Reuses `RiskLevel`, `PolicyEffect`, `Obligation`, `ApprovalOutcome`. No second
risk model. Risk defaults to `CRITICAL` when nobody said.

Obligations the gateway cannot discharge **refuse**. A policy that said "allow,
provided X" and then ran without X did not produce the decision anybody made.
This is enforced independently of any UI: a UI confirmation is not authorization.

## 13. Environment

Explicit on the request, the binding and the authorization; all three must agree.
Missing is not a wildcard — `ENVIRONMENT_UNKNOWN` refuses. A development-authorized
binding cannot execute against production, and no adapter choice can change that.

## 14. Freshness — one clock, earliest expiry

`AuthorityWindow` takes `min(binding, authorization, approval, deadline)`. The
minimum is the only combination that cannot be widened by adding another
authority. Remaining seconds are **floored**, never rounded up: rounding up hands
a worker a deadline outliving the authority that permitted it.

Zero or negative remaining refuses **before** invoking. No renewal, no extension —
`AuthorityWindow` is frozen, so extension is structurally impossible, not merely
forbidden.

**One clock.** A `Clock` port supplies the single `now` for every expiry check,
and it is threaded into the Phase 3.3.2 runtime rather than letting it read its
own. Two readings would let a binding be simultaneously live and expired across
one admission — which is exactly the defect the first verification run caught.

## 15. Worker and capability TOCTOU

Both delegated, not reimplemented.

- **Worker** — `WorkerRuntime.assert_invocable` re-reads the authoritative entry
  and compares lifecycle, trust, availability, compatibility, environment, tenant
  scope and **implementation digest** (ADR-037 §11). The gateway then additionally
  requires that the selected worker id and digest equal the ones the request
  names: same id + different build would put the chosen worker's name in the
  audit trail while different code did the work.
- **Capability** — `BindingValidator` re-reads lifecycle, trust and capability
  digest from Connectivity (ADR-036).

The runtime's gate runs **again** immediately before the adapter call, with the
admission's selection passed in. That is deliberate: it is the final pre-action
checkpoint, and the second read is what closes the window the first one opened.

Nothing is repaired. No re-resolution, no rebinding, no reselection, no expiry
extension — verified by AST: the gateway calls no `rebind`, `reselect`, `resolve`,
`retry` or `renew`.

## 16. Lease

A live lease is required, held by the selected worker, for the named attempt.
Missing, expired, foreign or unverifiable all refuse. The gateway **never grants,
renews or reclaims** — reclaiming would take a node from a worker that may still
be writing to production, and that is recovery's decision with the facts in front
of it.

## 17. One invocation, no retry

`admit → invoke once → classify → record`. Verified by AST: **the gateway body
contains no loop of any kind**, and exactly one call to `self._workers.invoke`.

No retry, no fallback worker, no automatic rebinding. Failures are classified and
handed to Execution's recovery policy (ADR-031).

## 18. Ambiguity and result integrity

Phase 3.1 semantics preserved. Timeout, connection drop, worker crash and unknown
provider response remain `UNKNOWN_OUTCOME` — never success.

Every result is checked before Execution records it: correct binding, correct
attempt, classified failure. A result naming another binding or attempt belongs
to another run — possibly another tenant's — and becomes `UNKNOWN_OUTCOME`, never
a failure and never a success. The work may well have happened; what is missing is
a trustworthy account of it, and recording an untrustworthy account as success is
how a half-applied change is marked done.

Result digests reuse the existing model and carry no secrets.

## 19. Idempotency

Reuses `derive_key` (ADR-031) unchanged. The key is passed through, never minted
here — a second key for one logical operation is a second operation as far as the
provider is concerned. Attempt number is not part of the logical operation
identity, in the key or in the action digest.

## 20. Credentials

`CredentialProvider` remains a Protocol with **no implementation**. No credential
store, no OAuth, no tokens.

Acquisition happens **last**, after every authorization check. Verified: a refused
request never mints a credential. The handle is deliberately *not* retained on the
admission — an admission is audited, and a credential on an audited object is a
credential in the audit log one refactor later. When the credential architecture
lands, the handle travels directly to the transport.

A wired provider returning nothing refuses. Nothing reaches audit, events,
bindings, selections, checkpoints or replay.

## 21. Audit

Uses `AuditRuntime.record_in_context` — the existing infrastructure. No second
framework. Every attempt, admitted or refused, produces attribution: tenant,
principal, execution, attempt, capability ref and digest, binding digest, worker
id and digest, operation, environment, action digest, policy version,
authorization outcome, approval reference, invocation outcome, failure class,
correlation and trace.

**Audit failure can never turn a denial into an allow.** The decision is already
made by the time anything is written; a raise there would propagate out of a
refusal path and could be caught as something other than a refusal, so it is
contained and logged. Verified with a deliberately exploding audit sink.

## 22. Denials are first-class

47 refusal codes, each machine-readable and safe to return. Every one carries a
code, a safe message, the correlation id, safe digests, a **retryability**
classification and a **security-relevance** flag.

Retryability is deliberately narrow: mismatches between authority artifacts will
not resolve by being asked again, and marking one retryable turns a security
refusal into a retry loop against a boundary that keeps saying no. Tenant,
principal, capability, binding, approval and worker-digest mismatches are all
non-retryable; transient unavailability is. **The gateway reports; recovery
decides.**

Security relevance separates "somebody presented another tenant's authority" from
"a worker was briefly unavailable". Recording both at the same weight is how the
first gets lost among the second.

No refusal leaks a credential, an internal URL, a provider hostname or a
traceback.

## 23. Events and outbox

Five, namespaced `capability.invocation.*`: `admitted`, `started`, `completed`,
`ambiguous`, `refused`. Aggregate is the **execution**, not a new one — an
invocation happens *to* a run, and a separate aggregate would split one run's
history across two streams.

`admitted` and `started` are distinct because credential acquisition sits between
them: a run stuck between the two is a run whose credential broker hung.
`completed` and `ambiguous` are distinct because that is the whole of Phase 3.1.

No `CapabilityRebound`, `WorkerRebound` or `BindingUpdated` — bindings and
selections are immutable, so those would describe something that cannot happen.

Published through the **existing Execution outbox**. No second outbox. Ordering is
preserved by recording each stage as it happens rather than batching, and the
in-memory outbox's lack of cross-process durability is stated, not claimed away.
Publication failure never changes a decision.

**ADR-037's un-emitted `WorkerSelected`:** the gateway is the authoritative
admission boundary, so selection facts are now emitted here — carried on
`InvocationAdmitted`, which binds the selection to the action it was made for
rather than announcing it in isolation. That closes the loose end recorded at the
end of Phase 3.3.2.

## 24. Observability

Reuses `ExecutionObserver` / `SafeObserver` (ADR-031). Observers cannot authorize,
deny, mutate execution, alter a result, or change a worker or binding — they are
handed facts after decisions are made, and `SafeObserver` contains their
exceptions. Verified with a deliberately exploding observer.

## 25. Replay

Replay reconstructs the invocation decision from recorded events: request
attribution, worker selection, action digest, admission, outcome, refusal reason.

Replay **cannot execute**. Verified structurally: `replay.py` imports only
`ContractViolation` and stdlib, and holds no repository, directory, worker,
adapter or queue. There is nothing there to call.

Historical replay ("what happened?") stays separate from current-policy
simulation ("would this be allowed today?"). The second is a different operation
and is not built here — conflating them would let a replay reauthorize against
live mutable state and report it as history.

## 26. API boundary

**No generic `POST /execute` was created.** No `force`, `bypass`, `ignore_policy`,
`skip_validation`, `skip_approval` or `use_worker` parameter exists anywhere in
this phase. Execution originates from the governed Mission Control path.

Concrete adapters remain unreachable from the network: they are constructible only
through the composition root, and the gateway is the only caller.

## 27. V1 strangler — what was found

The inspection found **ten** pre-existing HTTP surfaces that can cause real
external effects without a binding, an authorization decision, a worker selection
or tenant-attributable audit. They are inventoried in
`backend/api/legacy_execution_boundary.py`, with `gated` recorded honestly per
entry.

Three are gated (default **off**, `CORTEXPRIME_ENABLE_LEGACY_EXECUTION`):

| Route | Why it is the sharpest |
| --- | --- |
| `POST /api/v2/mcp/execute` | arbitrary tool name and params, **no tenant anywhere in the request** — there is nothing to check one against |
| `POST /api/agents/run` | `tenant_id` read from the **request body** — a tenant the caller chose |
| `POST /api/agents/delegate` | same body-supplied tenancy |

Seven are **reported but not enforced** — `runtime_api`, `execution.routes`,
`orchestrator`, `operator`, `computer`, `sandbox`, `enterprise_engineering`. Each
is an orchestration layer whose migration is its own piece of work, and switching
them off from here would be a change nobody reviewed. `ungated_surfaces()` makes
the gap queryable rather than only readable.

Nothing was deleted. Default-off **is a deliberate behaviour change** and is
recorded as one: the alternative was leaving a documented bypass switched on,
which is a longer way of saying the gate is optional. Read-only V1 routes are
untouched.

## 28. Composition root

`backend/api/capability_execution_composition.py`, extended. Still the only module
importing both contexts — `BND-CONTEXT-ISOLATION` passes. The gateway itself
imports only `contracts/`, `platform/` and its own context; verified by AST.

Three new adapters: `AuthorizationAuthorityAdapter` (over
`CapabilityAuthorizationService`), `ExecutionLeaseAdapter` and
`ExecutionResultRecorder` (both over `ExecutionService`). Everything crosses as
primitives.

## 29. Security invariants

All 25 enforced; I1–I25 verified by 92 focused checks. Fail-closed in every case,
including: no authority wired, authority raising, decision missing, validator
missing or raising, lease authority missing or raising, credential provider
returning nothing, and rate limiter raising.

The one deliberate exception is stated: an **absent** rate limiter is treated as
"no quota configured" rather than a refusal, because a rate limit is a resource
control and not an authority control. An **unavailable** one refuses. No limiter
is built in this phase; the Protocol seam is all that exists.

## 30. Phase 3.3.4 boundary

Not built, each deliberately: MCP/connector/agent transports, concrete providers,
the credential system, the input validator implementation, rate limiting,
scheduler, worker pool, compensation dispatch, current-policy simulation, and
migration of the seven ungated V1 surfaces.

Every one has a port or an inventory entry waiting for it. Until filled, the
platform refuses — which remains the correct behaviour.
