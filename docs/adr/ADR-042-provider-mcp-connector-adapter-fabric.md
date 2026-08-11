# ADR-042 — Provider, MCP and connector adapter fabric

**Status:** Accepted
**Date:** 2026-08-08
**Phase:** 4.3 — Provider / MCP / Connector adapters
**Extends:** ADR-041 (transport), ADR-040 (credentials), ADR-039 (lifecycle and
recovery), ADR-038 (invocation gateway), ADR-037 (adapter seams), ADR-036 (worker
contract), ADR-035 (binding), ADR-034 (authorization), ADR-033 (discovery),
ADR-032 (capability identity), ADR-031 (durable execution)

---

## 1. The one question

    "How does this already-authorized operation become one provider protocol
     exchange, and what actually happened?"

An adapter answers that, and nothing else. It is **not** an authorization
mechanism, **not** a capability registry, **not** a credential store, and **not**
a transport. It consumes authority four other components established and returns
facts.

The chain, and every arrow is a separate decision by a separate component:

    capability → binding → authorization → worker selection → invocation
    → credential acquisition → secure transport → provider adapter
    → external operation → normalised result

No provider-specific implementation may bypass any arrow. That is the whole
phase.

## 2. Ownership

`backend/contexts/execution/infrastructure/adapters/` — infrastructure by
definition, because an adapter is where a provider attaches. It imports
`platform.transport` and `platform.credentials`, imports no bounded context, and
is imported by nothing except the composition root.

The vocabulary that crosses boundaries — `ProviderRef`, `AdapterRef`,
`ProviderFailure`, `ProviderDelivery` — lives in `contracts/provider.py`, for the
same reason `CredentialRef` and `ConnectionRef` do: Execution names a provider,
Connectivity describes one, audit records both, and none may import the others.

## 3. Six identities, and none of them collapse

| Identity | Answers | Owner |
| --- | --- | --- |
| `CapabilityRef` | **what** may be done | BC-8 (ADR-032) |
| `WorkerRef` | **which** implementation runs | Execution (ADR-036) |
| `ProviderRef` | **who** is being addressed | here |
| `AdapterRef` | **how** we translate for them | here |
| `ConnectionRef` | **how** bytes move | transport (ADR-041) |
| `CredentialRef` | **what** authenticates | credentials (ADR-040) |

Every pair that gets merged takes a security decision with it.
`provider == capability` makes trusting GitHub authorize every GitHub operation.
`adapter == worker` makes one trust decision cover code written later.
`provider == connection` makes reachability into permission.

`ProviderRef` is deliberately **not** tenant-qualified — see §14.

## 4. The authority chain is structural, not procedural

`ProviderAuthority` is what an adapter consumes. Every adapter refuses without
one, and there is no other entry point: `AdapterSeam.run` returns a definite
refusal when `authority is None`.

It cannot be manufactured. Every field is required; the digests are opaque
strings Execution cannot compute; the binding is a `BoundCapability` projection
with no constructor path from nothing; and the credential is material minted by
the fabric *against this action's digest*. A route or a service that built one
would hold nothing any downstream check accepts — the provider would reject a
credential it could not produce, and the seam would reject a grant whose
`action_digest` did not match.

It is built in exactly one place: `InvocationAdmission.provider_authority()`,
which is a projection. Nothing there is computed and nothing is defaulted.

**`WorkerRuntime.invoke(authority=None)` is permitted and is not a bypass.** A
caller reaching the runtime directly gets a refusal from the adapter rather than
a provider call.

## 5. No re-authorization, and no second engine

Adapters perform provider-specific protocol checks. They do not decide who may
act. A provider's refusal — `AUTHENTICATION_FAILURE`, `AUTHORIZATION_FAILURE` —
is returned as a **fact about what the provider said**, never silently
transformed into a success and never fed back into whether CortexPrime
authorized the action.

The reverse also holds: a provider saying *yes* does not revisit authorization
either.

## 6. One adapter contract, three specialisations

MCP, connectors and agents share `AdapterSeam`: the same authority check, the
same TOCTOU re-read, the same effect comparison, the same failure taxonomy, the
same ambiguity rule. They differ only in how one authorized operation becomes one
protocol exchange.

Three separate execution frameworks would be three places the ambiguity rule
could be got wrong, and the first one to get it wrong reports a timeout as a
failure and duplicates a mutation on retry.

## 7. The operation model — why there is no `request(url, method, body)`

An execution API shaped like that is an authenticated HTTP proxy with a
capability check bolted to the front. Every operation it can perform is
"whatever the caller typed", so the capability that authorized it describes
nothing, the approval that covered it covered nothing, and the audit record says
a caller was allowed to make requests.

So operations are **declared**. `ProviderOperationSpec` names a method, a path
*template*, a parameter list, an effect class, and what a valid answer looks
like. `OperationCatalog` holds them, is constructed whole, is owned by the
composition root, and **has no `register`** — a mutable catalog is a place an
operation can appear without anybody declaring it.

Arbitrary-destination execution is impossible for two independent reasons:

1. There is no code path that builds a request from anything except a catalog
   entry.
2. `ProviderChannel` takes its scheme, host and port from deployment
   configuration. A plan contributes a path built from a declared template and
   validated segments; a path containing an authority is refused.

Path parameters must be `RESOURCE_SEGMENT`, which refuses `/`, `\`, `..`, `?`,
`#`, `%` and whitespace. A `STRING` in a path is how `../` gets into one, so the
spec refuses that declaration at construction.

### Determinism

Same binding + same validated input + same environment ⇒ the same provider
request. No attempt number in the path, no clock, no counter, no random routing.
The body is `canonical_bytes`, so key order, float formatting and escaping are
fixed. MCP JSON-RPC ids are constants (`1` for initialize, `2` for the call) for
the same reason.

## 8. Input validation, wired at last

`InputValidator` has been a port with nothing behind it since ADR-038, and the
gateway has refused every payload-carrying invocation ever since — correctly.
`OperationInputValidator` implements it over the same catalogs the adapters build
requests from. One declaration, used for both, so "what is checked" and "what may
be sent" cannot diverge.

It fails closed in four directions: no catalog for the provider, no entry for the
operation, a declaration that no longer matches the bound contract, or input that
does not satisfy the declaration.

Unknown fields are **refused, not dropped**. A dropped field is an operation the
caller did not perform and believes they did — and it is also not the operation
the action digest covered.

Validation runs before the digest and before the credential, which is the
ordering the gateway already had. Malformed input therefore never becomes an
action digest, never mints a secret, and never reaches a provider.

It runs **twice** by design: at the gateway (the authority boundary) and inside
the adapter (defence in depth). A single wiring mistake should not remove both.

## 9. Capability contract, and drift

`ProviderOperationSpec.contract_refusals(binding)` refuses three disagreements:

* the operation is not the bound one;
* `pinned_capability_digests` is non-empty and the bound contract digest is not
  among them — the capability was republished and the adapter was written for
  the previous shape;
* the catalog declares a **stronger** effect than the binding authorizes, or
  declares non-idempotent where the binding claims repeatable.

A *weaker* catalog effect is permitted: a read performed under a write
authorization is within what was allowed, and refusing it would make the binding
a floor as well as a ceiling.

A provider's runtime schema is **never** consulted. The authorized contract is
the one the binding names.

## 10. MCP

**A server is not a tool.** An MCP server is a provider boundary; an MCP tool is
a capability (ADR-033). `McpToolTarget.from_binding` derives both by exact field
copy — the provider *is* the server, the operation *is* the tool name. No mapping
table, no similarity, no inference.

**No `tools/list` at call time**, and no code path that could add one. Discovery
is BC-8's and it feeds the registry, not the invocation. An adapter that listed a
server's tools and chose one would be choosing a capability.

A payload may carry `_mcp_tool` / `_mcp_server` / `_mcp_endpoint`. Any of them
disagreeing with the binding is **refused** rather than ignored: a caller who
passed one believes it did something.

### Session lifecycle

    CONNECTING → INITIALIZING → READY → CLOSING → CLOSED
                      ↓            ↓        ↓
                    FAILED       FAILED   FAILED

Only `READY` permits a tool call, and only while inside the authority window that
opened the session. No transition leaves a terminal state: a session that ended
comes back as a new session, which forces a new key, a new credential and a new
initialization.

`McpSessionKey` is (tenant, provider, environment, principal, credential
fingerprint). Every component changes the authority the session speaks with, so
dropping any one of them merges two authorities into one channel.

**Sessions are per-invocation.** One invocation opens one, initializes it, calls
one tool, and lets it go. No pooling, no reuse, no cache — which costs a round
trip and buys the property that matters: there is no authenticated MCP client
outliving the authority that created it, and therefore no channel one tenant's
credential could answer another tenant's call on. There is no global session and
no global authenticated client anywhere in this fabric.

### Initialization is negotiation, never authorization

The adapter validates the protocol version against an explicit list (a dated
revision string has no ordering anybody should infer, so `>=` is not used),
validates the server identity fields, and validates the session id as printable
ASCII within bounds *because it is echoed into a header*.

`McpInitialization` holds the server's declaration as **data**. Its only query,
`declares()`, deliberately answers a question about the server rather than about
permission. A server saying "I support `dangerous_tool`" has advertised
something and granted nothing. The declaration is digested and recorded so a
server quietly changing it is visible after the fact — and is *not* acted on at
call time, because acting on it would make the server's self-description
load-bearing.

The client advertises **no capabilities**. Claiming sampling or roots would
invite a server to ask CortexPrime to do work nobody authorized.

### Result normalisation

MCP has two error channels and they mean different things:

| | meaning | outcome |
| --- | --- | --- |
| JSON-RPC `error` | the protocol refused; the tool did not run | definite |
| `result.isError` | the tool ran and failed | definite provider failure |
| lost/timed-out | nobody can say | `UNKNOWN_OUTCOME` |

Collapsing the first two would make "the server does not know that method" and
"the deployment failed" the same outcome.

Content is bounded (`_MAX_CONTENT_ITEMS`) and the transport budget already
bounds the response; a truncated body is refused before parsing, because half a
JSON document sometimes parses and a partial answer that parses cleanly is
exactly the shape a provider could use to make an incomplete result look whole.

## 11. Connectors

`ConnectorAdapter` is generic and stays generic. There is no GitHub, Jira, Slack,
AWS or Kubernetes branch in it, and none may be added. What varies is expressed
as data (`OperationCatalog`) and as one narrow port
(`ProviderResponseTranslator`), both supplied at composition.

The moment a provider acquires a branch in the generic adapter, it stops being
generic and every later provider inherits the shape of the first.

## 12. First connector: GitHub

Chosen against §45's preference order from repository evidence, not popularity:

* **Existing working client.** `backend/connectors/github.py` is the largest and
  most exercised V1 connector. Its endpoints, status codes and error shapes are
  known from code that has run.
* **Documented, single-mechanism authentication.** One bearer token in one
  header — so the credential fabric can own the secret and the transport can
  inject the header, which is the arrangement 4.1 and 4.2 were built for.
* **A conventional REST API**, so the generic adapter carries almost all of it.
* **Capability coverage that matters**: reading a repository, an issue or a pull
  request, and opening an issue or a comment is the minimum vocabulary
  CortexPrime needs to explain a problem and propose the fix.
* **Bounded security ambiguity**: resources are named explicitly by
  `owner`/`repo`, which is what makes §14 expressible.

Five operations are declared: `repository.get_repository`, `.get_issue`,
`.get_pull_request`, `.create_issue`, `.create_issue_comment`. Small on purpose —
each entry is a capability somebody has to register, a contract somebody has to
approve and a scope somebody has to grant.

`backend/connectors/github.py` is **untouched** and still serves every V1 caller.
What was migrated is the *declaration*, not the code.

Two GitHub-specific translator rules, and only two: a rate limit answered as 403
(classified as `AUTHORIZATION_FAILURE` it would send an operator to check scopes
on a token that is fine), and the bounded extraction of GitHub's `message` and
`errors` fields. GitHub's deliberate 404-for-private-resources is **not**
"corrected" into a permissions error — guessing would be inventing a fact.

### The isolation finding, stated rather than worked around

`create_issue` is `IRREVERSIBLE_WRITE` (closing an issue is not deleting it, and
Constitution P2 says an action with no complete inverse is classified
irreversibly). `IsolationTier.AMBIENT` — which is what an in-process HTTPS
adapter genuinely is — is sufficient only for `READ`.

So **worker selection refuses the two mutating GitHub operations with
`isolation_insufficient`** until a deployment runs this adapter somewhere that
provides more and says so in its registration.

That refusal is the fabric working. Declaring `SEALED` to make the write
selectable would claim hardware isolation this process does not have, and the
gate would then be waved through for every later capability that needs it.

## 13. Agents

`AgentAdapter` is a mechanism seam. No LLM call, no loop, no planner, no memory,
no tool selection, no orchestration.

**§31's refusal is implemented.** An agent's declared effect class is a statement
about intent, not a bound on behaviour, so the effect check catches an over-reach
only *after* the write. For a read-only capability that is tolerable. For a
mutating one it is not — so a mutating agent binding requires an invoker that
declares `confines_effects`, and without one the invocation is refused having
done nothing.

An agent that reports success without declaring what it did is
`UNKNOWN_OUTCOME`, not success: the effect comparison is the whole safety story
and a missing effect makes it vacuous.

No credential travels to an agent runtime. An agent that needs a provider reaches
it through its own governed capability with its own binding.

## 14. Tenancy, and provider resource ownership

Every invocation carries tenant, principal, execution and node, all from the
authority. There is no `TenantRef("system")`, no ambient tenant, no default, and
no inference from a provider account, an environment variable, a URL or a
credential.

**A provider account is not a tenant.** Two CortexPrime tenants may reach GitHub
through the same installation and nothing in the token distinguishes them. What
distinguishes them is that `owner` and `repo` are required path parameters: they
are part of the validated input, therefore part of the action digest, therefore
part of what authorization decided, and the credential grant carries that same
digest. Tenant A's repository cannot become tenant B's, because neither the
capability nor the credential nor the digest would match.

There is deliberately **no operation that lists what the token can see**. "Show
me every repository this credential reaches" is exactly the shape that turns a
shared installation into a cross-tenant read.

## 15. Credentials

Phase 4.1, exclusively. Adapters never read `os.environ`, a global store, a V1
singleton, or an inbound `Authorization` header — and there is no code in the
fabric that could: material arrives on the authority and is handed to
`TransportRequest.credential`.

`REQUIRES_CREDENTIAL` defaults to `True` and is overridden only where a provider
genuinely needs none (the agent seam). Defaulting the other way would make a
wiring mistake look like an anonymous provider call that happens to fail.

Nothing caches material. The seam checks, immediately before sending, that the
grant is live *and* that its `action_digest` matches the one about to run.

## 16. Transport

Phase 4.2, exclusively. `ProviderChannel` holds a `TransportBroker` and no HTTP
client, no socket, no TLS context — there is no import in that module that could
open a connection. Address policy, SSRF judgement, DNS pinning, redirect rules
and resource budgets all happen inside the broker.

An operation may **narrow** the response budget and may not widen it: the
deployment's number is the one somebody sized the process against.

### Two additive changes to Phase 4.2

`TransportOutcome` gained `body` and `response_headers`. An adapter cannot
normalise or validate an answer it cannot see, and §26 requires a response to be
validated before it counts as a success; transport is the only thing that reads
bytes, so there is no other channel.

Both are `repr=False`, `compare=False`, and absent from `to_dict`, exactly as
`TransportRequest.credential` is. Credential-bearing response header names
(`set-cookie`, `authorization`, `proxy-authenticate`, `www-authenticate`) are
**refused at construction** rather than filtered later, so there is no code path
where one exists as a reportable fact. Adapters read a short allow-list on top of
that.

This is recorded as an extension rather than a redesign: no existing behaviour
changed, and the fields default to absent.

## 17. Headers

Adapters never inject `Authorization` or `Proxy-Authorization` — transport owns
credential header injection. Adapter-contributed headers go through the Phase 4.2
`validate_caller_headers`, which refuses the credential-bearing, framing and
forwarding names by the same list the transport enforces. One list, checked
twice, no second opinion about what is forbidden.

Provider-specific headers are permitted only when non-secret, explicitly declared
in the operation spec, and validated.

## 18. Action digest and idempotency

The adapter **receives** the ADR-038 digest. It never recomputes it, never
derives a provider-specific one, and never includes the attempt number.

Execution's idempotency key is passed through untouched, and only where the
operation declares the provider reads one. **GitHub has none**, and the catalog
says so: a key sent to a provider that ignores it is protection that is not
there, and Execution's retry rules need to know which kind of provider they are
dealing with. `supports_provider_idempotency=False` on the registration says the
same thing at the selection layer.

## 19. Retry, cancellation, timeout

**No adapter-level retry loop, anywhere.** One `dial`, one answer. Provider errors
are classified `is_ambiguous` / `is_definitely_not_applied` / neither, and
Execution owns the decision.

**Rate limits are facts.** `retry_after_seconds` is returned; nothing sleeps on
it. The V1 GitHub connector's `asyncio.sleep` on a 403 is exactly what this
replaces.

**Cancellation** is a one-way `CancellationToken` created per admission,
observed before sending and propagated into transport. A cancel that could not be
confirmed produces `UNKNOWN_OUTCOME`, never `CANCELLATION` — a stop requested
after transmission stops nothing anybody can vouch for. `CancelledError` is never
swallowed into a success.

**Timeout** is `min(provider limit, transport limit, remaining authority)`,
applied through `TransportRequest.authority_seconds_remaining`, which the broker
already clamps every phase to. There is no second timeout regime.

## 20. Error classification and response integrity

`ProviderFailure` is provider-neutral and deliberately granular — flattening it
into `provider_failed` would take away what recovery reads. Raw provider
exceptions never escape: the seam catches everything and classifies it through
`safe_exception_text`, because an HTTP client's exception routinely carries the
request it was making, headers included.

A response is validated before it counts as a success: delivery settled, body
decoded, status classified, **and** the declared shape present. A malformed,
truncated or wrong-shaped answer is `MALFORMED_RESPONSE` — which is *ambiguous*,
not failed: the operation may well have been applied, and only the account of it
is untrustworthy.

**`SUCCESS` is never manufactured.** It requires valid request authority, valid
credential authority, a valid transport outcome, a valid adapter, valid input, a
valid response, and an effect within the contract.

## 21. Effect integrity

Checked in both directions, at the adapter (where the provider's own account is
available) and again at the runtime.

* Reported effect **stronger** than the binding ⇒ anomaly ⇒ `UNKNOWN_OUTCOME`.
* Reported `READ` for a **mutating** binding ⇒ anomaly ⇒ `UNKNOWN_OUTCOME`.
  Recording a mutation as a read would make it freely repeatable.

The observed effect comes from the **catalog's** declaration, not from the
provider's claim: a provider-supplied effect would make the comparison circular.

## 22. Evidence

Bounded and structured: provider, operation, action digest, response digest, a
safe provider request id, the classification, and the operation's declared
`response_evidence_fields` (an id, a number, a URL — clamped to 256 characters
each).

Never: credential material, `Authorization`, private keys, cookies, or raw
provider payloads. Raw retention, if it is ever needed, is a separately governed
evidence mechanism and not an execution event.

## 23. Adapter lifecycle and trust

**No new lifecycle model.** `WorkerLifecycle` (REGISTERED → VALIDATED → ENABLED
→ DISABLED → REVOKED, terminal) and `WorkerTrust` are reused, because an adapter
*is* a worker implementation and a second model would be a second place the
answer could differ.

Capability trust and adapter trust stay separate records, both read at the
execution boundary, either able to refuse. A trusted capability reached through
an unverified adapter is not a trusted execution.

`AdapterRef` is nonetheless distinct from `WorkerRef` (§3): today one object
carries both, and "we vouch for this adapter" and "we vouch for this worker" must
remain two sentences.

`build_github_connector` returns a `WorkerEntry` at
REGISTERED/UNVERIFIED/UNAVAILABLE. Four separate deliberate acts stand between
construction and real work, and none happens as a side effect of the others.

## 24. TOCTOU

Immediately before external communication, `AdapterSeam` re-checks: cancellation,
binding expiry, authority window, remaining time, provider match, operation
support, credential liveness, and credential–action agreement. All of them are
answerable without asking anybody, so none can fail because a collaborator was
unavailable.

`AdapterPreflight` — implemented by `DirectoryAdapterPreflight` at the
composition root — re-reads the authoritative worker entry: lifecycle, trust,
availability, and implementation digest. It fails closed on a missing directory,
a missing context, a raising lookup, a missing entry or a changed digest.

**No re-resolution and no substitution.** A stale authority is a refusal.

## 25. No fallback, no hidden side effects

If provider A fails, nothing calls provider B. If adapter A fails, nothing calls
adapter B. Recovery decides.

Adapter construction is side-effect-free: it creates no resource, mutates no
provider state, writes no repository, registers no capability, enables nothing,
and fires **no health probe** (§59 — a provider being reachable is not
authorization, and a probe per invocation multiplies provider traffic by the
fleet size).

## 26. Audit, events and replay

The existing audit is reused — `InvocationAdmission.audit_detail()` and
`ProviderAuthority.audit_detail()` carry capability, operation, provider,
adapter, worker, connection, execution, node, tenant, principal, action digest
and outcome, all built from identifiers and digests with no branch that could
emit a secret.

**No new events.** The Phase 3.3.3 invocation events already represent the
meaningful transitions; `ProviderCalled` and `AdapterMethodEntered` would be
events because methods exist, which is not a reason.

**Replay remains inert.** It invokes no worker, calls no connector, contacts no
provider, reacquires no credential and reconnects no transport — there is no
repository, no directory and no adapter in that module to do it with.

## 27. Observability

`ADAPTER_METRICS` enumerates the full observable surface in one reviewable place.
Labels carry tenant, provider, adapter and environment — never an operation
payload, never a credential reference, never a URL, and never a capability
reference (high-cardinality, and as a metric dimension it would turn a dashboard
into an inventory of what each tenant can do).

## 28. Failure behaviour

Every missing dependency fails closed: missing credential, missing transport,
missing binding, invalid binding, revoked capability, disabled adapter, untrusted
adapter, provider mismatch, tenant mismatch, environment mismatch, malformed
input, malformed response, expired authority, cancelled execution.

No fallback provider. No default credential. No default tenant. No default
adapter.

## 29. V1 migration

`backend/api/legacy_provider_inventory.py` classifies fifteen mechanisms as
SAFE_TO_REUSE / ADAPTER_TARGET / STRANGLER_TARGET / SECURITY_HAZARD /
REMOVE_LATER, with `chooses_operation` as the column that matters most: seven
V1 mechanisms decide *what* is performed, which is the defect this fabric exists
to remove.

Nothing is deleted. The Phase 3.3.3 strangler gate already refuses every V1
execution route by default (ADR-039), so the legacy path cannot become a second
production execution path.

**One genuine hazard**, carried forward from the Phase 4.2 network inventory:
`backend/mcp/connectors/web.py` exposes `fetch_url` and `http_get` taking a
caller-supplied URL with redirects followed — a complete SSRF primitive, inert
only because its route is gated off. It has **no migration path as written**: a
capability whose operation is "fetch a URL the caller names" cannot be expressed
in the operation model, which is the point of the operation model. Remove the two
tools or replace them with declared, host-pinned operations. Not changed here
because deleting a tool somebody may use is a decision with an owner.

## 30. Test adapter

`TestProviderAdapter` — named so nobody mistakes it. Requires
`allow_non_production=True`, refuses PRODUCTION at construction, refuses a
registration declaring PRODUCTION, and refuses again at every invocation.

It runs the whole gate: authority, staleness, credential, catalog, contract
drift, input validation, response shape, effect comparison. A double that skipped
those would be testing a different adapter than production runs.

**It proves the authority chain, not the transport.** It performs no dial, so it
demonstrates nothing about TLS, address policy, DNS pinning or budgets — for
those, wire a real `ProviderChannel` to Phase 4.2's `DevelopmentTransport`, which
sits behind the broker and therefore goes through all of them. Saying that
plainly matters more than the code: a double described as "proving the adapter
works" is how a deployment believes a path was checked that never was.

## 31. Consequences

**Positive.** One governed adapter lifecycle instead of three. Arbitrary-URL and
arbitrary-tool execution are structurally impossible rather than checked against.
The `InputValidator` seam is no longer empty. Provider errors reach recovery in
one vocabulary whether they came from the provider or from this side. Contract
drift is detected. Ambiguity survives every translation.

**Negative, and accepted.** Adding a provider now requires writing a catalog
rather than calling a client — deliberately, since that is what makes the
capability, the approval and the audit record describe the same thing. MCP costs
an extra round trip per invocation because sessions are not pooled. The two
mutating GitHub operations are unreachable until a deployment provides real
isolation.

**Unresolved.** No transport adapter and no credential adapter exist, so the
fabric refuses end-to-end in every deployment today. That is Phase 4.4.

## 32. Phase 4.4 boundary

In scope for 4.4, and explicitly **not** built here:

* a production HTTP/streaming `TransportAdapter` registered on the broker;
* a production `CredentialAdapter` (the Vault client is the inventoried
  candidate);
* connection reuse and pooling policy, if any, with the tenant-isolation
  argument made explicitly;
* the second and subsequent connector catalogs;
* a decision on `backend/mcp/connectors/web.py`;
* an agent runtime that can declare `confines_effects`;
* a governed raw-evidence retention mechanism, if raw provider responses are
  ever needed.

Not in scope for 4.4 and not implied by anything here: an LLM participating in
tool selection, provider selection, capability ranking or authorization
reasoning. That remains impossible by construction at this layer.
