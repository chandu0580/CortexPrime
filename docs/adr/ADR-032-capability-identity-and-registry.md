# ADR-032 — Capability identity and the registry foundation

**Status:** Accepted
**Date:** 2026-08-08
**Phase:** 3.2.1 — Capability Identity + Registry Foundation
**Supersedes:** nothing
**Related:** ADR-005 (connector vocabulary), ADR-029/031 (Execution), ADR-030 (handoff),
ADR-016 (fitness functions), ADR-017 (request context), ADR-018 (storage boundary)

---

## 1. The placement decision, and why no amendment was needed

The Constitution names nine bounded contexts. One of them, **`connectivity`
(BC-8)**, had never been built — but it already owned this responsibility in
published form. `backend/contracts/connector.py` is headed *"Owner: BC-8
Connectivity"* and already declares `ToolDescriptor`, `ConnectorRef`,
`IsolationTier` and `ConnectorCapabilities`: *"Describes what a tool can do, so
that Governance can reason about a tool it has never seen."*

That is the Capability Fabric's job description, written before the fabric
existed.

So the registry is built at **`backend/contexts/connectivity/`**. No new bounded
context was created, `BOUNDED_CONTEXTS` was not touched, and no ADR amendment is
required. Because `connectivity` is one of the nine, `BND-CONTEXT-ISOLATION`
actively polices it — unlike the contexts outside the list, which rely on their
own compliance tests.

Existing registries were inspected and none of them owns this: `backend/tools/
tool_registry.py`, `backend/connectors/registry.py`, `backend/agents/registry.py`,
`backend/mcp/registry.py` and `backend/runtime/agent_registry.py` are V1
singletons holding mutable dicts, with no tenancy, versioning, digest, lifecycle
or trust. They remain strangler-migration targets and were not modified.

## 2. A capability is not a tool call

It is an authoritative declaration of an executable ability, and it is the object
an approval is *about*. That is why it has an identity that outlives its
implementation, a version that pins its contract, and a digest that makes
"is this what was approved?" answerable.

## 3. Identity

```
<namespace>.<provider>.<capability>[.<operation>]

platform.github.pull_request.create
platform.shell.execute
tenant.acme.deploy.rollback
```

Structured text, not a ULID — deliberately breaking this codebase's own
convention. Every other identifier here names *an occurrence* (this run, this
attempt) and nobody outside the platform needs to recognise it. A capability
names *an ability*: it appears in workflow definitions and audit records, and it
must survive its implementation being rewritten in another language. It is
therefore not a class name, module path, URL, or database key.

Segments are lowercase `[a-z][a-z0-9_]*`, so `GitHub` and `github` cannot become
two capabilities that read identically in a log.

`namespace` separates platform-supplied abilities from tenant-supplied ones, so a
tenant registration can never shadow a platform capability. A tenant-namespaced
capability may not be platform-owned; the invariant is enforced.

## 4. Version

An **integer**, not semver. Semver invites the judgement call this registry must
not permit — *"is this a minor change?"* A contract either is the one an approved
workflow bound to, or it is not.

**`latest` is refused explicitly**, with an error that says why: a run bound to a
moving target can have the capability change underneath it after approval.

Version is *not* part of identity. `CapabilityRef` pins the two together and
renders as `platform.github.pull_request.create@2`, so the pin is visible wherever
it is logged.

## 5. Contract and digest

`CapabilityContract` holds what running the capability promises: interface, side
effect class, effect semantics, isolation tier, execution mode, schema
references, required permissions, environments, and the execution properties
Phase 3.1 needs (idempotency, retryability, cancellability, compensation,
timeout).

The digest covers `capability_id + version + provider + owner + tenancy +
contract`. It deliberately **excludes** status, trust, timestamps and notes — a
digest that changed when a capability was disabled would make "is this the
contract that was approved?" unanswerable.

Platform canonical hashing is reused; no second implementation exists. The digest
is **restored, not recomputed** on load, so a stored definition edited after
registration is detectable rather than silently re-blessed.

Schemas are **referenced with their own digest, not embedded**. Embedding
arbitrary third-party JSON Schema would put unbounded untrusted structure inside
an object the platform hashes and shows widely.

## 6. Lifecycle and trust — two axes, never one

`CapabilityStatus`: DRAFT → REGISTERED → VALIDATED → ENABLED, plus DISABLED,
DEPRECATED, REVOKED.

`TrustState`: UNVERIFIED → VERIFIED → TRUSTED, plus QUARANTINED, UNTRUSTED.

**Existence is not trust.** If these were one field, "we know about this" and "we
vouch for this" would be the same statement, and every later resolver would be
entitled to assume anything it can find is safe. `is_executable` requires *both*
axes to permit it — a capability can legitimately be ENABLED and QUARANTINED at
once, meaning "meant to be available, and right now I do not trust it".

`enabled: bool` was rejected because it cannot express revocation. **REVOKED has
no transitions out at all** — that absence is the security property. Bringing
back a revoked capability means registering a new version, which forces a new
digest and a new decision. Revocation drops trust in the *same construction*, so
no halfway object exists that is withdrawn and vouched-for simultaneously.

DISABLED returns to VALIDATED, never straight to ENABLED: switching something
back on goes through the gate it went through the first time. Coming out of
QUARANTINE returns to UNVERIFIED, not to the prior trust — release means being
re-checked, not resuming a trust already in doubt.

Nothing arrives enabled or trusted. Something that describes itself and is
immediately usable is a self-signed certificate.

## 7. Effect semantics — and the one shared-vocabulary change

Capability declares both effect axes:

- `SideEffectClass` (published, BC-5) — how consequential.
- `EffectSemantics` — whether repeating is safe.

`EffectSemantics` previously lived inside the execution context, where BC-8
cannot reach it (S2). Duplicating it was not acceptable. It has been **promoted
to `backend/contracts/execution.py`** as shared vocabulary — *owner BC-5,
consumed BC-8* — following the precedent of `configuration.py`. The execution
context now imports it from there and re-exports it; behaviour is unchanged.
This is the only change made outside the new context.

Enforced at registration:

- `UNKNOWN` is **never** treated as safe, and a capability with unknown semantics
  **cannot declare itself retryable**.
- A mutating capability cannot claim read-only semantics.
- Claiming idempotent-write semantics requires actually supporting an
  idempotency key.
- BC-8's existing rule is reused unchanged: the isolation tier must be sufficient
  for the side-effect class, so a destructive capability cannot be registered as
  `AMBIENT`.

## 8. Duplicate registration — the registry's central security invariant

| offered | outcome |
|---|---|
| same identity + version + **same** digest | idempotent; the stored definition wins |
| same identity + version + **different** digest | **refused** (`ConflictingRegistration`) |

The stored definition winning matters: it may have been validated or trusted
since, and overwriting would silently undo those decisions.

The comparison and the write happen **under one lock**. Checking first and
writing after is the race in which two registrants each decide they are first and
the second silently redefines what something was approved against.

## 9. Ownership, tenancy, provenance

**Owner** is a `PrincipalRef` and is mandatory. `"system"` is explicitly refused
by the command — an unowned capability is an ability nobody answers for.

**Tenancy** is stated, never inferred: `PLATFORM` (no tenant, serves everyone),
`TENANT` (exactly one, named), `SHARED` (must name the tenants). A shared
capability with an empty share list is refused — *"shared with nobody in
particular is shared with everybody"*.

The repository enforces visibility rather than trusting callers, and **invisible
is indistinguishable from absent**: returning a "forbidden" would confirm that
another tenant's capability exists.

**Provenance** (`CapabilitySource`) is recorded now, before discovery exists, so
that a capability a machine found can later be told apart from one a human
declared — a distinction impossible to reconstruct afterwards.
`is_self_declared` marks MCP and agent sources, which are exactly the ones that
should not start out trusted.

## 10. Persistence — honestly in-memory

`CapabilityRepository` is a Protocol; the only implementation is in-memory.
**Nothing here is durable**: a restart loses every registration.

No file store was created — `STATE-NO-NEW-FILE-STORES` forbids `capabilities.json`
and none exists. There is no `update()`, no `set_status()`, and no generic
`save()`: a repository with a generic setter is one through which the lifecycle
can be bypassed, and the lifecycle is the security model.

## 11. Registration is privileged — and the guard is currently open

Registering a capability is how something becomes runnable at all, so it is at
least as sensitive as approving a workflow.

`RegistrationGuard` is the seam Phase 3.2.3 will occupy. Its only implementation
today is `OpenRegistration`, which **refuses nothing**. It is named rather than
absent so that "this registry has no authorization yet" is visible at the
composition root instead of being a gap somebody has to notice.

**This is a real exposure and is stated as one.** The API is not yet safe to
expose publicly.

## 12. WorkerKindResolver — preserved, not replaced

`WorkerKindResolver` (ADR-030) is **untouched**. It remains a Protocol in
`mission_control_composition.py` with one method, and that module still imports
no capability code.

The intended future integration, deliberately *not* built here: a
`RegistryBackedWorkerKindResolver` will live at the composition root, look up the
pinned `CapabilityRef` for a node, assert the capability is executable, and return
its worker kind. Execution will still never import Connectivity — the join stays
in the composition root, exactly as the Workflow → Execution join does.

## 13. Boundaries left for later phases

**3.2.2 Discovery** — `CapabilitySource.DISCOVERY` and `MCP` exist as provenance
values. No scanning, no remote inspection, no dynamic loading was built.

**3.2.3 Authorization** — `RegistrationGuard`. No policy engine, no RBAC, no
admission rules.

**3.2.4 Resolution/binding** — the registry answers *what exists*. It does not
answer *which one should serve this request*; that needs a request to resolve
against and would make the registry decide rather than record.

## 14. Compliance

- **S2** — imports only `contracts/` and `platform/`; verified in both
  directions, Execution and Connectivity know nothing of each other.
- **S6** — semantic allowlisting preserved: classification by declared capability,
  reusing BC-8's isolation-sufficiency rule.
- **P2/P9** — effect class and reversibility declared at registration.
- **BC-9 / ADR-017** — every repository method takes an `ExecutionContext`; no
  ambient context, no contextvars, no fake tenant.
- **ADR-018** — no new authoritative file store.
- Reused: platform hashing, `DomainEvent`/`EventMetadata`, `PrincipalRef`,
  `TenantScope`, `RepositoryGuard`, `SideEffectClass`, `IsolationTier`. No
  duplicate hashing, identity, event or tenancy implementation was created.

## 15. What this ADR does not claim

No discovery, no authorization, no resolution, no binding, no connector, no
worker, no MCP execution, and no durable persistence. The registry records what
exists and refuses what would be unsafe to record. Running any of it is a later
phase.
