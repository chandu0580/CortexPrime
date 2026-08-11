# ADR-037 — Worker / Connector / MCP adapter fabric

**Status:** Accepted
**Date:** 2026-08-08
**Phase:** 3.3.2 — Worker / Connector / MCP Adapter Fabric
**Extends:** ADR-036 (worker contract), ADR-035 (binding), ADR-032/033/034 (capability fabric), ADR-031 (durable execution), ADR-030 (`WorkerKindResolver`)

---

## 1. The rule the whole phase rests on

**A capability is an authority. A worker is a mechanism.**

Connectivity decides *what ability exists*, *whether it is trusted*, *whether
this principal may use it*, *which provider wins*, and *which version*. It
produces a `CapabilityBinding`. Execution consumes that binding and decides one
further thing: **which implementation performs it**.

A worker never decides whether it is allowed to run, which capability was
selected, which provider won, or whether authorization holds. It is handed the
result of all of that and asked to perform it. `WorkerExecutionRequest` carries
no registry, no resolver, no policy engine and no discovery service — a worker
cannot look those up because there is nothing in its hand to look them up with.

Nothing in this phase re-decides a Connectivity question. There is no second
capability registry, no second resolver, no second authorization system and no
second binding mechanism.

## 2. Worker identity is not capability identity

Capability identity answers *what ability exists*. Worker identity answers *what
implementation can perform it*. `WorkerImplementation` records the second and
can never assert the first: it names no capability into existence, grants itself
no operation, and is never consulted about a principal.

Its declared constraints are all **narrowing** and none has a wildcard:

| Field | Why |
| --- | --- |
| `worker_id`, `worker_kind`, `interface` | what it is |
| `implementation`, `implementation_version` | which build. `latest` is refused |
| `protocol_version` | the ADR-036 contract it speaks |
| `isolation` (`IsolationTier`, reused) | what containment it actually provides |
| `scope`, `tenant_id` | platform or one tenant |
| `supported_environments` | mandatory, non-empty |
| `supported_effects` | mandatory, non-empty |
| `supported_providers` | mandatory, non-empty |
| `supported_capability_refs` / `_operations` / `pinned_capability_digests` | optional further narrowing |
| `cancellation`, `supports_provider_idempotency` | what it can honestly promise |

Empty `supported_providers` is **refused**, not read as "any provider". The
difference between "declared fit for GitHub" and "declared fit for whatever turns
up" is the entire value of the object.

## 3. Lifecycle — registration is never enablement

`REGISTERED → VALIDATED → ENABLED ⇄ DISABLED`, with `REVOKED` terminal from
anywhere and reachable from nothing. Only `ENABLED` permits execution. A disabled
worker returns via `VALIDATED`, never straight to `ENABLED` — switching something
back on goes through the gate it went through the first time.

`REVOKED` has no transition out, and that absence *is* the security property. A
revoked implementation returns only as a new registration, which forces a new
digest and a new decision.

Deliberately narrower than `CapabilityStatus`, which also admits `DEPRECATED`. A
deprecated *ability* still has to run while callers migrate; there is no
equivalent for an implementation — superseding one means registering the
successor and disabling this.

`register()` lands a worker at `REGISTERED` / `UNVERIFIED` / `UNAVAILABLE`. Three
further deliberate acts stand between that and real work, and there is no
argument that skips them.

## 4. Worker trust ≠ capability trust

Two enums, deliberately not one shared type.

- Capability trust: *do we trust this declared ability?*
- Worker trust: *do we trust this implementation to perform it?*

A trusted capability reached through an unverified adapter is not a trusted
execution, and the reverse holds equally. **Both sides must be acceptable.** The
capability side is re-read through `BindingValidator` (ADR-036); the worker side
through the directory. Either one refuses.

`WorkerTrust` mirrors ADR-032's shape — `UNVERIFIED / VERIFIED / TRUSTED /
QUARANTINED / UNTRUSTED`, only the middle two permitting execution — because the
reasoning that produced it applies unchanged, not because they are the same fact.

## 5. Availability is a third axis

`AVAILABLE / UNAVAILABLE / UNHEALTHY / DRAINING`. Enabled-but-not-running is not
disabled and not untrusted; it calls for a different response. Collapsing the
three into `worker_not_found` is how an operator spends an incident looking for a
registration that was there all along.

`WorkerRefusal` has 28 distinct values for exactly this reason. No polling or
heartbeat infrastructure was introduced: availability is a recorded state that
something else sets, and `WorkerHealth` (ADR-029) remains what a worker reports
about *itself*.

## 6. Compatibility is deterministic field comparison

Every axis is an exact match against a declared value: kind, interface, protocol
version, provider, capability reference, operation, contract digest, effect
semantics, isolation sufficiency, environment, tenant.

**No fuzzy matching, no embeddings, no similarity, no LLM.** Selecting the
mechanism decides what credentials are used, what network is reachable and what
isolation applies — a selection that could be *persuaded* is a security boundary
that can be talked past. The execution fabric stays deterministic; a model may
propose an action elsewhere in CortexPrime and takes no part here.

`incompatibilities()` returns **every** reason, not the first. An operator who
fixes one and rediscovers the next has been told half the truth twice.

Isolation reuses `IsolationTier.minimum_for` rather than restating the table. The
platform already decided that arbitrary commands need `SEALED`; this does not get
a second opinion.

## 7. Environment — and the gap that made it explicit

`CapabilityBinding` carries no environment. It belongs to the resolution request,
and the Capability Fabric is frozen, so this phase did **not** add it there.

Instead: `ExecutionEnvironment` was promoted to `contracts/execution.py` — which
is precisely what `CapabilityEnvironment`'s own docstring prescribed for a third
consumer ("promote it to `contracts/` rather than making a third copy"). Values
are identical, so the composition root translates by value and a mistranslation
raises `ValueError` rather than silently selecting the wrong environment.

`BoundCapability` gained an optional `environment`, supplied explicitly to
`project_binding` by a caller that still has the Connectivity picture. It is
**optional in the type and mandatory in practice**: an absent environment yields
`ENVIRONMENT_UNKNOWN` and every candidate is refused.

Not defaulted, in either direction. Guessing `PRODUCTION` would authorize the
worst case; guessing `DEVELOPMENT` would let a development-only worker perform
production work. Refusing is the only safe third option.

## 8. `WorkerKindResolver` is unchanged

ADR-030's resolver remains the authoritative binding → kind mapping, reached
through the `WorkerKindPort` seam and adapted at the composition root exactly as
ADR-036 left it. No semantics were modified; inspection found no defect.

Three enum members were **added** to `WorkerKind` — `MCP`, `CONNECTOR`, `AGENT` —
because the resolver needs a value to resolve *to* before an adapter can declare
one. Added rather than repurposed: routing an MCP tool call through `HTTP`
because MCP often travels over HTTP would make the transport the identity, and a
worker offering `HTTP` would then be offered MCP work it cannot perform. `AGENT`
joins `is_inherently_stateful` (an actor that chose its own steps leaves partial
work nobody enumerated); `MCP` and `CONNECTOR` do not, being no more stateful
than the `HTTP` call they resemble.

## 9. Flow, and no fallback

```
CapabilityBinding → WorkerKindResolver → WorkerKind → WorkerDirectory
                  → candidates → deterministic selection → WorkerSelection
                  → authoritative re-read → ExecutionWorker → WorkerExecutionResult
```

- No worker kind → **refuse**
- Kind exists, no enabled worker implements it → **refuse**
- Multiple eligible → **explicit ambiguity refusal naming both**

There is no "worker A is down, worker B will do". A different implementation can
have different credentials, network reach, isolation and side effects — so
substituting one changes what the execution *means* while the binding, the
approval and the audit trail all still say the first thing.

Ambiguity is not resolved because first-registered, newest, local, faster and
cheaper are five different policies and none has been decided. Two eligible
workers is a question an operator can answer; a silent preference is not.

`candidates()` returns a stable order (platform before tenant, then id) so a
refusal reads the same way twice. That is an ordering **for reading**, never a
preference — selection refuses two eligible workers rather than taking the first.

## 10. `WorkerSelection` — immutable and digest-bound

Captures `worker_id`, `worker_kind`, `worker_version`, `worker_digest`,
`binding_id`, `binding_digest`, `capability_digest`, tenant, principal,
environment, interface, selection reasons, `policy_version`, and `expires_at`,
sealed under its own digest.

There is no `WorkerRebound`, no `WorkerSelectionUpdated`, and no mutation method.
A selection that could be changed would let the thing that runs differ from the
thing that was selected, with one selection id vouching for both. If the selected
worker becomes invalid, **execution refuses** and recovery begins a new governed
flow.

Selections are short-lived by design. A selection is not a grant; it is a note
about what was true a moment ago, and the re-read below is what actually decides.

## 11. TOCTOU — the cached selection is never trusted

Between selection and invocation a worker can be disabled, quarantined or
revoked. If the cached selection were trusted, disabling a compromised adapter
would not stop the invocation already on its way to it.

So `assert_invocable` re-reads the authoritative entry and calls
`selection.revalidate(entry)`, which checks expiry, existence, **implementation
digest**, lifecycle, trust, availability, and binding identity. Any mismatch
refuses. It never nominates a replacement.

The digest check catches the most dangerous shape: same id, different build — the
audit trail would name the worker that was chosen while different code performed
the work.

## 12. The implementation digest

Computed over stable implementation identity only. **Status, trust, availability
and every timestamp are excluded.**

The digest answers *which implementation was selected*, never *is it currently
enabled*. So disabling a worker does not change the digest an earlier selection
recorded, and an audit trail stays comparable across a state change — which is
exactly what makes the TOCTOU comparison meaningful.

## 13. `WorkerDirectory` evolved; `StaticWorkerDirectory` is gone

ADR-036 defined the directory as a single `adapter_for(kind)` lookup —
deliberately minimal, and insufficient once workers are real. It could not express
a worker being *disabled* rather than *absent*, could not confine a tenant's
registration to that tenant, and offered nothing to re-read between selecting a
worker and calling it.

The port is now three methods — `candidates`, `entry`, `adapter_for(worker_id)` —
and `adapter_for` takes a **worker id, never a kind**: a kind can have several
implementations, and picking one from a kind is exactly the substitution this
layer refuses.

`StaticWorkerDirectory` was **removed rather than kept alongside**. Two lookup
paths is how one of them stops being checked. It had no callers.

It remains not a capability registry: no definitions, no discovery, no
authorization, no resolution.

## 14. Tenancy — stated, never inferred

Platform workers are visible to every tenant and writable by none of them; tenant
workers to exactly one. A tenant **may not** register under an id a platform
worker holds — shadowing would let a tenant redirect platform work into an adapter
it controls, a privilege escalation that looks like a naming collision.

Cross-tenant reads **fail closed**: another tenant's worker returns `None`, the
same answer as one that does not exist. Distinguishing them would confirm its
existence to somebody not entitled to know.

Every governance call requires an `ExecutionContext` carrying a tenant. No ambient
`contextvars`, no global current tenant, no default, and no `TenantRef("system")`.
A platform-scoped worker may only be registered from a platform-internal context.

## 15. The adapter boundary

Every adapter implements the ADR-036 `ExecutionWorker` contract and receives a
`WorkerExecutionRequest`, returning a `WorkerExecutionResult`. It is given no
authorization engine, no discovery service, no capability registry and no
resolution service.

**An adapter may:** translate the request into a provider call, make it, capture
the result, map provider failure onto the Phase 3.1 taxonomy, and return.

**An adapter may not:** authorize, resolve, rebind, retry, mutate the execution
aggregate or the binding, touch registry state, or change tenant or principal.

`AdapterSeam.run` is the shared gate and is **not overridable**: request-type and
kind checks, transport presence, deadline sanity, exception classification,
effect-anomaly checks, and outcome translation happen identically for every
provider. Subclasses implement only `_perform`. A provider author who could
replace the gate would eventually replace the ambiguity rule with something more
convenient.

`_perform` returns a `ProviderOutcome` — facts in the provider's own terms.
Translation into outcome semantics, failure classes and ambiguity happens once,
under rules a transport author cannot accidentally reinterpret.

## 16. MCP seam — contract only

**Not implemented, deliberately:** no MCP client, no `tools/list`, no
`tools/call`, no OAuth, no token acquisition, no session manager, no websocket,
no SSE, no Streamable HTTP, no network of any kind.

`McpToolInvoker` is the port a future transport implements. One method — no
`connect`, no `authenticate`, no `list_tools`, no session handle — because each
of those would give an adapter a lifecycle, and a lifecycle is where credentials,
retries and cached tool listings end up living.

**An MCP server is not an MCP tool.** Preserved from ADR-033 and the most
important thing in the seam. The server is a provider boundary; the tool is the
capability:

```
MCP server (provider) → MCP tool (capability) → CapabilityBinding → MCP worker
```

So one server-level trust decision never authorizes everything that server
exposes. `McpToolTarget` carries both, derived from the binding's provider and
operation by **exact field copy** — no lookup table, because a table is a place
where a capability can be quietly pointed at a different tool.

A future implementation must not call `tools/list` and use the answer to decide
what to run. Discovery is BC-8's and it feeds the registry, not the invocation.

## 17. Connector seam — generic, permanently

No GitHub, Jira, Slack, Google, AWS, Azure, Kubernetes or Terraform, and none may
be added to `connector.py`. Providers attach behind `ConnectorInvoker`. The moment
one acquires a branch in the generic adapter, it stops being generic and every
later provider inherits the shape of the first.

`ConnectorRequest` carries `side_effect_class` and `effect_semantics` read-only so
a transport can refuse to exceed the binding — advisory only. **The binding
remains authoritative**, and a transport must not upgrade `UNKNOWN` to
`IDEMPOTENT_WRITE` because the provider usually behaves that way. Usually is not a
contract, and the retry rules read this.

## 18. Agent seam — required, and only a mechanism

Built because the architecture already treats agents as capabilities:
`CapabilityInterface` carries `AGENT` and `SKILL` (ADR-032), so a binding for one
can be resolved and authorized today. Without the seam it would reach execution
with nowhere to land, and the pressure would be to route it through an adapter
written for a deterministic call.

**No LLM call, no agent loop, no planner, no memory, no reasoning, no tool
selection, no orchestration.** All of that sits behind `AgentInvoker`, in a
concern that is not execution.

Recorded honestly: `CapabilityInterface.is_model_driven` already says an agent's
declared effect class is a statement about *intent*, not a bound on behaviour. The
binding stays authoritative and the effect check still runs, so an agent that
exceeds its authorization becomes an anomaly rather than a success. That is a
*detection*, not a prevention — which is why an agent capability wants stronger
isolation than a connector doing the same work.

## 19. Effect semantics — checked in both directions

`EffectSemantics` and `SideEffectClass` are reused from `contracts/execution.py`;
nothing was duplicated.

- **Over-claiming** (reports stronger than the binding declares) — a capability
  performing work it was not authorized for. Checked in the adapter *and* by
  `WorkerRuntime`.
- **Under-claiming** (reports `READ` for a mutating binding) — a write recorded as
  a read, and reads are retried freely. Checked in the adapter, where the
  provider's own account is still available.

Both become anomalies, and an anomaly is `UNKNOWN_OUTCOME` — the change may well
have landed, and calling it a failure would be the same mistake in a nicer tone.

## 20. Idempotency, timeout, cancellation

**Idempotency.** No adapter has a retry loop and none will: Execution owns retry,
attempt numbering and ambiguity handling (ADR-031). Adapters advertise
provider-native idempotency support via `supports_provider_idempotency` and pass
through the key Execution already derived. A second, incompatible key is never
generated — two keys for one operation is two operations as far as the provider is
concerned.

**Timeout.** Never `SUCCESS`. `timed_out` maps to `TIMEOUT`, `ambiguous` to
`UNKNOWN_OUTCOME`; both are unknown outcomes under Phase 3.1, which is what stops
an ambiguous mutation from being retried automatically. "The socket closed" is a
fact about this side.

**Cancellation.** `CancellationSupport` gates the claim. Only `GUARANTEED` yields
`CANCELLATION`; a cancel that was *requested* but not confirmed becomes
`UNKNOWN_OUTCOME`, and `cancel()` returns `False` by default. Returning `True` on
the strength of having sent a signal turns a still-running mutation into a node the
runtime believes is finished.

## 21. Credentials stay outside

`CredentialProvider` remains a seam with **no implementation and no caller**. No
credential system was invented.

No credential appears in `CapabilityBinding`, `BoundCapability`,
`WorkerExecutionRequest`, `WorkerExecutionResult`, the worker registry, any event,
or any audit record. `McpToolCall`, `ConnectorRequest` and `AgentInvocation` each
carry none, and each says so.

A capability binding carries authority to *act*; it must never carry the secret
that proves who is acting. When the credential architecture arrives, a scoped
handle is acquired at the execution boundary and passed to the transport
separately — never inside the object that gets serialized into a log line.

## 22. Input validation now fails closed

ADR-036 let an absent `InputValidator` pass payloads through unvalidated. **That
is fixed.** A request carrying a payload with no validator wired is refused
(`input_unvalidatable`). An empty payload has nothing to validate and proceeds.

The seam stays a seam — no second schema engine — and no worker validates its own
input: an adapter that did would be deciding what the capability's contract meant,
one provider at a time.

## 23. Output normalization

Every adapter returns the generic `WorkerExecutionResult`: outcome, classified
failure, result digest, safe provider metadata, observed effect, ambiguity, and
timing. Provider-specific result formats never reach Execution.

Output is **digested, never carried** — provider results are unbounded and can
contain anything, including the caller's own data coming back. `detail` carries
non-sensitive facts only (status codes, request ids); `to_dict()` on every request
object omits the payload, because those reach audit.

## 24. Events

Seven, namespaced `execution.worker.*`, mirroring ADR-032's capability set plus the
one genuinely new fact:

`registered` · `validated` · `enabled` · `disabled` · `revoked` ·
`trust_changed` · **`selected`**

All are tenant-attributable via `EventMetadata`, digest-aware (each carries the
implementation digest), and replay-safe. None carries a credential or a payload.

`set_availability` emits **no** event. An observation is not a decision;
availability changes as often as the network does, and an event for each would
bury the ones recording somebody deciding something.

Nothing was added merely because a method exists, and no existing execution event
was duplicated. The platform's audit contracts and event machinery are reused —
no second framework.

## 25. Replay stays structurally non-executable

`ExecutionReplayer` gained a `selections` projection so replay can reconstruct
which worker was selected, which digest, against which binding, and why it was
eligible — **folded from recorded events, never recomputed.** Re-running selection
would read today's directory and answer about a worker that may since have been
disabled, rebuilt or revoked.

Verified: the module's only import is `ContractViolation`. It holds no repository,
no directory, no worker, no adapter and no queue — so it cannot invoke, reconnect,
call, acquire, retry or rebind even if the code wanted to.

## 26. Composition root

`backend/api/capability_execution_composition.py` — the existing sanctioned root,
extended rather than replaced. It remains **the only module importing both
contexts**, verified by `BND-CONTEXT-ISOLATION`.

The adapter seams live in `backend/contexts/execution/infrastructure/adapters/`,
which preserves the boundary: an adapter is where a provider attaches, making it
infrastructure by definition, and nothing under it imports Connectivity.

`ADAPTER_SEAMS` maps kind → seam class and is exhaustive. Adding a provider does
**not** add an entry — providers attach behind an invoker.

## 27. V1 strangler targets

`backend/tools/tool_registry.py`, `backend/connectors/registry.py`,
`backend/agents/registry.py`, `backend/mcp/registry.py` and
`backend/runtime/agent_registry.py` are all mutable module-level singletons.

Nothing was migrated, nothing was deleted, and **the new fabric depends on none of
their state.** No module in this phase imports any of them. When one must be
bridged, it goes behind an invoker port at the composition root, explicitly marked
migration infrastructure — never imported into a context.

## 28. Fail-closed inventory

All verified:

| Condition | Result |
| --- | --- |
| worker missing / not registered | refuse |
| not validated / not enabled / disabled / revoked | refuse |
| unverified / quarantined / untrusted | refuse |
| unavailable / unhealthy / draining | refuse |
| kind / interface / protocol mismatch | refuse |
| provider / capability / operation / contract-digest mismatch | refuse |
| effect semantics unsupported | refuse |
| isolation insufficient for the side effect | refuse |
| environment unsupported | refuse |
| **environment unstated** | refuse |
| tenant mismatch / cross-tenant read | refuse |
| binding expired / invalid / capability revoked | refuse |
| worker digest changed since selection | refuse |
| selection expired or mismatched | refuse |
| **input validation unavailable with a payload** | refuse |
| adapter attached to an enabled worker missing | refuse |
| transport unavailable | definite failure, nothing sent |
| two eligible workers | explicit ambiguity refusal |

There is no branch that proceeds because something was unavailable.

The unwired-transport case is a **definite `FAILURE`**, not `UNKNOWN_OUTCOME`:
nothing left the process, so "it did not happen" is a claim that is true. Calling
it ambiguous would make an unwired seam look like a lost mutation and block retry
on a node that never left the building.

## 29. No public execute API

No worker execution API, no "execute worker", no "force worker", no "bypass
worker", no "select worker manually". Execution is still reached only through the
governed Mission Control path. No scheduler, no worker pool, no credential
implementation, and no concrete provider was built.

## 30. Verification

43 focused checks, all passing, over: adapter Protocol conformance; unwired-seam
behaviour; mandatory declarations; digest stability across lifecycle changes;
registration-is-not-enablement; every refusal in §28; TOCTOU on a worker disabled
mid-flight; ambiguity; tenant shadowing and cross-tenant visibility; terminal
revocation dropping the adapter; effect anomalies in both directions; and replay
inertness.

Architecture fitness functions: **16 passed, 0 failed** across 1026 modules,
including `BND-CONTEXT-ISOLATION`. Full regression is the hardening phase's.

## 31. Phase 3.3.3 boundary

Not built here, and each deliberately:

- MCP transport — client, OAuth, tokens, sessions, `tools/list`, `tools/call`
- Connector transports — GitHub, Jira, Slack, AWS, Kubernetes, Terraform, …
- Agent runtime behind `AgentInvoker`
- Shell / Docker / browser / Kubernetes workers
- The credential system behind `CredentialProvider`
- The input validator behind `InputValidator`
- Worker health polling and heartbeats
- Worker pool and scheduler
- An explicit selection policy, should ambiguity ever need resolving

Each has a port waiting for it, and until one is filled, the platform refuses —
which is the correct behaviour for a platform with no workers.
