# ADR-043 — Production connectivity gateway

**Status:** Accepted
**Date:** 2026-08-08
**Phase:** 4.4 — Production connectivity gateway (final phase of Phase 4)
**Extends:** ADR-042 (adapters), ADR-041 (transport), ADR-040 (credentials),
ADR-039 (lifecycle and recovery), ADR-038 (invocation gateway), ADR-036 (worker
contract), ADR-031 (durable execution)
**Amends:** ADR-040 §DELEGATION — the refusal it declared is now raised

---

## 1. The one question

    "Is there exactly one path from an approved intention to an external side
     effect, and can it be traced?"

Phases 4.1–4.3 built the fabrics. This phase wires them into one path and closes
everything that could reach a provider without going through it.

## 2. The final authority chain

```
Mission → Intent → Planner → Workflow → Approved Workflow → Execution
  → CapabilityBinding → AuthorizationDecision → WorkerSelection
  → InvocationRequest
  → SecureCapabilityInvocationGateway
        identity · tenant · binding · authorization · delegation · approval
        · worker · input · action digest · obligations · freshness · lease
        · rate · credential
  → CredentialProvider → CredentialBroker → VaultCredentialAdapter
  → WorkerRuntime          (TOCTOU re-read: binding, worker, directory entry)
  → AdapterSeam            (TOCTOU re-read: authority, credential, cancellation)
  → ProviderChannel → TransportBroker → HttpxTransportAdapter
  → provider
  → ProviderOutcome → WorkerExecutionResult → Execution → Audit → Replay
```

Credentials stay last in the gateway's ordering. A request that was going to be
refused must never cause a secret to be minted, and moving acquisition earlier
for convenience would mean every refused invocation left a live credential at
some provider.

No network connection is established before the authority chain is complete, and
no provider is contacted to discover whether an operation is allowed.

## 3. One entry, and no second gateway

`SecureCapabilityInvocationGateway` remains authoritative and unchanged in role.
`ProductionConnectivity` is a **handle on an assembled graph**, not a gateway: its
`invoke` counts a metric, calls `gateway.invoke`, counts another, and returns.
It could be deleted without changing a single thing that is enforced.

There is deliberately no `ConnectivityGateway`, `ProviderGateway`, `MCPGateway`
or `ConnectorGateway` type in the new code. A second thing named "gateway" is how
a second place to authorize appears.

## 4. Delegation — the ADR-040 gap, closed

`CredentialRefusal.DELEGATION_NOT_AUTHORIZED` was declared in Phase 4.1 and
**nothing could raise it**. The delegated principal travelled the whole chain and
was compared only against the authenticated context — so "the actor is who they
say" was checked and "the actor may act for that principal" never was.

Two different questions, and both are now asked:

| stage | question |
| --- | --- |
| `_check_identity` | is this actor who they say, acting for whom they say? |
| `_check_delegation` | was this actor ever *allowed* to act for that principal? |

`AuthorityFacts` gained `delegation_permitted` (default `False`) and
`delegated_principal_id`. Three refusals, fail-closed:

* the request delegates and the decision does not sanction delegation;
* the decision sanctions delegation but names no principal, or a different one;
* the decision names a delegated principal and the request delegates to nobody.

The refusal is `is_security_relevant`. It is checked again at the credential
broker (`CredentialRequest.delegation_authorized`, default `False`) and a third
time in the Vault adapter — three checks for one mistake, because the consequence
of missing it is a live provider credential minted under a borrowed identity.

### The finding underneath it

`AuthorizationRequest` **has no delegation concept.** Connectivity answers "may
this principal invoke this capability" and has never been asked "may this
principal act for another". There is nothing in an `AuthorizationDecision` to
project into `delegated_principal_id`.

Inventing one at the composition root would have been building a second
authorization engine, which this phase must not do. So `DelegationAuthority` is
an explicit port and **its absence is a refusal**: with none wired,
`delegation_permitted` stays `False` and *every* on-behalf-of invocation is
refused.

That is stricter than before this phase, and it is the correct fail-closed answer
to a capability the platform does not yet have. Building the delegation model is
Phase 5 work.

## 5. Credentials

`CredentialProvider` is the only credential authority on the production path.
Searched and confirmed: no `os.environ` provider-secret read, no legacy
singleton, no request-body secret, no inbound `Authorization` reuse.

**One environment secret remains, deliberately**: `VAULT_TOKEN`, CortexPrime's
own credential to its secret store. It is the bootstrap root of trust and by
definition cannot come from the store it unlocks. It is read once at
construction, wrapped immediately in `CredentialMaterial`, and never read again.
ADR-040's prohibition is on *provider* credentials — which are per-tenant, and
one process variable cannot be.

## 6. Vault adapter — and why it does not wrap `VaultClient`

Phase 4.1 named `backend/infrastructure/vault/client.py` as the natural first
adapter. Reading it here said otherwise:

* it is **`hvac`-based**, not httpx as the Phase 4.2 network inventory recorded
  (corrected there) — so wrapping it would have added a second outbound path with
  its own TLS, its own proxy inheritance and no address policy;
* it is a module singleton holding one `VAULT_TOKEN` with no tenant in the type;
* `get_secret` returns `None` on **every** exception, so a missing secret, an
  unreachable Vault and a rejected token are one answer — fail-open shaped;
* `hvac` may not be installed.

So `VaultCredentialAdapter` speaks Vault's KV v2 HTTP API **through the transport
broker**: one `GET`, same address policy, same DNS pinning, same budgets as every
provider call. The V1 client is untouched.

The tenant is structural, not incidental:

    <mount>/data/<prefix>/<tenant>/<environment>/<provider>

Every segment is validated against a conservative character set, so a tenant id
containing `..` refuses rather than reading somebody else's path. The adapter
caches nothing, issues with the authority window as expiry, returns exactly the
requested scope, reports `UNKNOWN` from `validate` (a KV secret has no per-issuance
state to read) and `False` from `revoke` (a static secret does not stop working
because we asked).

## 7. Legacy credential store — quarantined

`backend/auth/credential_store.py` decrypts every stored credential into a
process-wide dictionary with no tenant in the type. Re-verified as **completely
unreferenced**.

Not deleted — deleting a credential store is a decision with somebody's encrypted
files and key attached. Quarantined: `CredentialStore` requires
`allow_non_production=True`, and `get_credential_store()` refuses outright,
taking the memoising module singleton with it. The point is not friction; it is
that wiring it into a production path is now something a reviewer cannot miss.

## 8. Production transport

`HttpxTransportAdapter`, registered on the broker for `HTTPS` and
`MCP_STREAMABLE_HTTP`.

| requirement | how |
| --- | --- |
| TLS verification | `verify` is only ever `ca_bundle_path or True`; `ConnectionPolicy` has no field that disables it |
| no `verify=False` | no parameter exists that produces one |
| no plaintext in production | refused by policy, by config, and again at dial |
| no ambient proxy | `trust_env=policy.proxy.trust_environment`, default `False` |
| bounded timeouts | `httpx.Timeout(connect=, read=, write=, pool=)` from `TimeoutPolicy`, already clamped to the authority window |
| no retry | `httpx.HTTPTransport(retries=0)` |
| redirects | `follow_redirects=False`; the broker judges each hop |
| bounded reads | streamed, stopped at `max_response_bytes`, `truncated` reported |
| connection limits | `max_keepalive_connections=0`, `keepalive_expiry=0` |

`trust_env=False` also disables `NETRC` and `SSL_CERT_FILE` inheritance — same
argument twice: credentials and trust anchors are configured, never ambient.

## 9. DNS safety and rebinding

The Phase 4.2 order is preserved exactly:

    parse → normalise → resolve → judge **every** answer → pin → connect to the pin

The adapter rewrites the request URL to the **pinned literal address** and
restores two things explicitly:

* `Host` — the original authority, so the provider routes correctly;
* the `sni_hostname` extension — passed by httpcore to
  `ssl_context.wrap_socket(server_hostname=...)`, so SNI *and* certificate
  hostname verification are performed against the real name.

Getting the second wrong is the subtle failure: verifying a certificate against
an IP fails on every legitimate provider, and the "fix" is to disable
verification.

**Verified against the real network.** A GET to `api.github.com` dialled at the
pinned address returned 200 with a valid certificate — which is itself the proof,
since GitHub's certificate does not cover that IP. Loopback, decimal-encoded
loopback (`2130706433`), RFC1918 and the cloud metadata address were all refused
with `ssrf_refused` before a socket existed.

## 10. Redirects

Disabled by default, at the policy and at the client. When a policy enables them
the broker re-runs the **whole** endpoint and address judgement on each hop, and
`ConnectionPolicy.credentials_may_follow` is a `staticmethod` returning
same-origin-only — not configurable, because forwarding an `Authorization` header
to whatever host a provider names in a `Location` is credential disclosure on
request.

Redirect behaviour is never influenced by caller input.

## 11. MCP production path

MCP reaches providers through `ProviderChannel` → `TransportBroker` →
`HttpxTransportAdapter`. There is no direct httpx, socket, websocket or
subprocess anywhere in the MCP adapter.

Unchanged from ADR-042 and re-confirmed: the server is pinned (configuration),
the tool is pinned (binding, by exact field copy), no `tools/list` at call time,
sessions are per-invocation and scoped by (tenant, provider, environment,
principal, credential fingerprint).

**Initialization is negotiation, not authorization.** Server capabilities, tool
descriptions, server metadata and protocol version grant nothing; the binding is
authoritative; a runtime mismatch refuses and nothing auto-registers or
auto-versions.

**`MCP_STDIO` remains refused**, in four places: `TransportEndpoint.parse`,
`ConnectionPolicy.judge_endpoint`, `PRODUCTION_TRANSPORT_KINDS`, and
`HttpxTransportAdapter.__init__`. Launching a local process needs a sandbox
boundary that does not exist, and an HTTP client cannot approximate one.

`MCP_SSE` is also refused by this adapter — an SSE stream needs idle-timeout and
per-frame accounting a request/response client does not provide, and carrying it
would bound a stream by its total timeout and nothing else.

## 12. Connector production path — GitHub

Wired through `build_production_connectivity`: catalog, translator, channel over
the broker, credential through the fabric, registered in the worker directory at
**REGISTERED / UNVERIFIED / UNAVAILABLE**.

The isolation refusal from ADR-042 §12 is **preserved and not downgraded**.
`create_issue` and `create_issue_comment` are `IRREVERSIBLE_WRITE`;
`IsolationTier.AMBIENT` — what an in-process HTTPS adapter genuinely is — covers
only `READ`. Worker selection therefore refuses them with
`isolation_insufficient` until a deployment provides real isolation and says so.

Declaring `SEALED` to make a demonstration work would claim hardware isolation
this process does not have, and would wave the gate through for every later
capability that needs it.

Resource ownership stays explicit: `owner` and `repo` are required
`RESOURCE_SEGMENT` path parameters, part of the validated input, therefore part
of the action digest, therefore part of what authorization decided and what the
credential grant is bound to. There is no arbitrary URL, host, path or method,
and no operation that lists what the token can see.

## 13. Input and response validation

`OperationInputValidator` is wired into both the gateway and the worker runtime,
built from the same catalogs the adapters construct requests from. Validation
runs **before** the action digest and **before** credential acquisition, so
malformed input never mints a secret or reaches a provider.

Unknown fields are refused, never dropped. Path traversal is refused at the
parameter level.

Responses are validated for delivery, decodability, status, declared shape and
size. A malformed or truncated answer is `MALFORMED_RESPONSE`, which is
**ambiguous** rather than failed — the operation may well have been applied and
only the account of it is untrustworthy. Malformed data can never become
`SUCCESS`.

## 14. Provider errors, effect, idempotency, retry, cancellation, timeout

Unchanged from ADR-042 and re-verified end to end in this phase:

* errors normalise to the provider-neutral `ProviderFailure` taxonomy; raw
  exceptions never escape (`safe_exception_text`);
* the **catalog** declares the effect, never the provider; over-reach is
  `UNKNOWN_OUTCOME`, never `SUCCESS`, and classification is never downgraded;
* GitHub has no idempotency mechanism and the catalog says so rather than
  pretending; Execution's key is passed through untouched and never regenerated;
* **no retry loop** at transport, adapter, provider or MCP level; `retry_after` is
  returned as a fact and nothing sleeps;
* cancellation propagates Execution → gateway → adapter → transport, and an
  unconfirmed stop is `UNKNOWN_OUTCOME`, never a cancelled-success;
* timeout is `min(authority remaining, provider limit, transport limit)`;
  authority is never extended and authorization is never renewed from inside
  connectivity.

## 15. TOCTOU

Three re-reads, at widening distance from the decision:

1. `WorkerRuntime.assert_invocable` — binding validity, worker kind, selection,
   the authoritative directory entry, the adapter.
2. `AdapterSeam.run` — cancellation, binding expiry, authority window, remaining
   time, provider match, operation support, credential liveness, and that the
   credential's `action_digest` is *this* action's.
3. `DirectoryAdapterPreflight` — lifecycle, trust, availability, implementation
   digest, read again immediately before a socket exists.

Any change refuses. No rebind, no reselect, no renew, no fallback, no downgrade,
no retry. Recovery decides what happens next.

## 16. Tenancy and disclosure

Tenant originates from the authenticated `ExecutionContext` and is compared
against the request, the binding, the authorization, the worker registration, the
credential grant and the connection. Cross-tenant fails closed everywhere, and
`WorkerDirectory.entry` answers `None` for another tenant's worker exactly as it
does for a nonexistent one — existence is not disclosed.

No production path reads tenant from a request body, a provider account, a URL, a
credential, an environment variable or a global.

## 17. V1 strangler migration — the fourth state, found and closed

ADR-038's boundary gates V1 **execution** routes. Phase 4.4's reconciliation found
a category it never covered, sitting in exactly the state the directive warns
about — *reachable but forgotten*:

| route | what it actually does |
| --- | --- |
| `POST /api/connectors/{type}/connect` | takes a **credential in the request body** and writes it into a process-wide connector singleton — one authenticated user sets a provider credential for every tenant |
| `POST /api/connectors/{type}/test` | same, plus an outbound authenticated call |
| `POST /api/connectors/{type}/disconnect` `.../refresh` | any authenticated user mutates every tenant's shared connector |
| `GET /api/connectors/{provider}/**` (~14) | authenticated outbound provider calls with a process-wide environment credential, no tenant, no capability, and `str(e)` returned on failure |
| `POST /api/v2/mcp/connectors/register` | inserts caller-named tools into the global MCP registry, whose `execute` is **first-match-wins by tool name** — a registration can shadow an existing tool process-wide |

All six are now gated by `legacy_connectivity_boundary` on
`CORTEXPRIME_ENABLE_LEGACY_CONNECTIVITY`, default off. A **separate** flag from
the execution one on purpose: an operator migrating a workflow must not
simultaneously reopen a route that writes provider credentials into a global.

`ungated_surfaces()` returns empty for both boundaries.

**The behaviour change, stated plainly:** this breaks the connector configuration
UI and the live connector dashboards until they move to the governed path. That
is the correct trade — the alternative is leaving a credential-writing endpoint
open because a page renders from it.

Authentication is not authorization. `require_user`, admin dependencies and API
keys prove who is asking; none of them authorizes an external operation.

## 18. Legacy web connector

`backend/mcp/connectors/web.py` takes a caller-supplied URL and follows
redirects — a complete SSRF primitive. Determined: **not registered anywhere, not
dynamically imported, not reachable through a route or an agent**; it is exported
from `backend/mcp/connectors/__init__.py` and constructed nowhere.

Quarantined: construction requires `allow_non_production=True`. Both routes that
could ever have reached it are gated (execute by ADR-038, register by this ADR).

**It is not migrated, and it cannot be.** The operation model declares a method, a
path template and typed parameters, and takes the destination from deployment
configuration. "Reach an address I will name later" is not an operation, and
migrating it would put the arbitrary-URL hole *inside* the governed fabric —
worse than leaving it outside one. Replacement means declared, host-pinned
operations.

## 19. Environment credentials

Re-scanned. Ten V1 connectors still read `os.getenv(PROVIDER_TOKEN_ENV)`; all are
inventoried, all are reachable only through gated routes, and none is on the
production path. The governed GitHub path takes its credential from the fabric,
so the same credential is **not** duplicated into two live mechanisms — the V1
client is simply unreachable without a flag.

## 20. API surface

No arbitrary-execute, arbitrary-provider, arbitrary-URL, arbitrary-tool,
force-success, bypass-auth, bypass-credential, bypass-transport or direct-adapter
endpoint exists on an ungated path. Administrative routes (`/operator/execute`)
are gated on the same execution flag as everything else: admin proves who, not
whether.

## 21. Configuration

`ProductionConnectivityConfig` splits security-critical, provider and operational
values, and **holds no secret field** — the Vault token never lands on it, so a
configuration that is logged or put in a bug report carries nothing to leak.

Production refuses at construction: plaintext transport, plaintext Vault,
plaintext provider endpoint, private destinations, environment proxy inheritance,
and missing `VAULT_ADDR`/`VAULT_TOKEN`. The last one matters most —
"credential acquisition refuses" and "credentials are not configured" look
identical at runtime, and only one of them is a bug somebody notices.

Development defaults cannot enable production behaviour:
`build_development_connectivity` is a separately named function that refuses
production, and every scripted component refuses it again independently.

## 22. Audit, observability, replay

Existing audit reused; no new telemetry framework. Every production operation
records tenant, principal, execution, node, capability, capability digest,
provider, adapter, worker, operation, environment, action digest, binding digest,
authorization digest, credential reference and fingerprint, connection reference,
outcome, provider request id where safe, response digest and timestamps. No
secret can reach any of it — `audit_detail()` is built from identifiers and
digests, and there is no branch that could emit material.

Audit failure never turns DENY into ALLOW or REFUSE into SUCCESS: every audit
call is wrapped and the decision is already made before anything is written.
`SafeObserver` remains enforced — an observer exception cannot abort an
operation or change an outcome.

`CONNECTIVITY_METRICS` adds five counters on top of the fabrics' own, labelled
with tenant and environment only.

**Replay is inert**, verified by search: it references no broker, no channel, no
adapter, no httpx, no gateway. An `UNKNOWN_OUTCOME` in history replays as
`UNKNOWN_OUTCOME`; history is never repaired.

## 23. Supply-chain and drift

`AdapterRef`, the worker implementation digest, the capability binding digest and
the action digest are all preserved and all compared. A rebuilt adapter changes
the worker digest, which the runtime's TOCTOU re-read and the adapter's preflight
both refuse — so a previously approved binding cannot silently execute new code.
There is no hot replacement path.

Provider contract drift refuses via `ProviderOperationSpec.contract_refusals`:
nothing auto-registers, auto-approves or auto-creates a version 2.

## 24. Durability — the boundary, stated

**Phase 4 does not solve durable distributed state, and nothing here claims
otherwise.** Execution state, the outbox, leases and the worker directory are
in-process. This phase claims **no** crash safety, **no** exactly-once, **no**
cross-process leases, **no** zero-loss outbox and **no** distributed ordering.

`ProductionConnectivity.readiness()` returns `durability_ready: False`
unconditionally, with the reason attached, so a deployment reading readiness
cannot mistake three ready axes for four.

## 25. Readiness — four separate answers

| axis | status |
| --- | --- |
| **Architecturally ready** | Yes. One entry, one chain, every seam filled or explicitly refusing. |
| **Operationally ready** | Conditional. Requires `VAULT_ADDR`/`VAULT_TOKEN` and secrets stored at the tenant path; refuses to assemble without them. |
| **Provider ready** | Partial. GitHub reads are ready end to end; GitHub writes are refused by isolation until a deployment provides more than `AMBIENT`. MCP is ready when a server is configured. |
| **Durability ready** | **No**, deliberately, and unconditionally reported as such. |

## 26. Remaining risks

* **Delegation is refused platform-wide.** Correct and fail-closed, but it means
  no on-behalf-of execution works until a delegation model exists.
* **The V1 connector UI is broken by default.** Deliberate; it needs migrating to
  governed capabilities, which is per-provider work.
* **Vault is the only credential adapter.** A deployment on AWS Secrets Manager
  or Azure Key Vault has no adapter yet.
* **No real credentialed provider operation has been executed.** The transport
  was verified against a live public HTTPS endpoint; the *authorized, credentialed
  write* path has been verified only against scripted providers. No production
  network claim is made.
* **`MCP_SSE` and `MCP_STDIO` are unimplemented**, so a provider needing either
  is unreachable.
* **In-process durability**, as above.
* **Seventeen V1 connectors remain unmigrated** behind gates.

## 27. Consequences

**Positive.** One traceable production path. The Phase 4.1 delegation gap is
closed and stricter than before. A real transport that cannot be configured
insecurely. A credential adapter that reaches its store through the same address
policy as everything else. Two credential authorities reduced to one. A whole
category of forgotten V1 surface found and gated.

**Negative, and accepted.** Connector configuration and dashboards break until
migrated. Delegation stops working entirely. GitHub writes stay unreachable
without real isolation. MCP costs a round trip per invocation.

## 28. Phase 5 boundary

In scope for Phase 5, and explicitly **not** built here:

* **durable distributed state** — persistent execution, cross-process leases, a
  durable outbox with ordering guarantees, crash recovery;
* **a delegation model** in Connectivity, so `DelegationAuthority` has something
  authoritative to answer from;
* additional credential adapters (AWS, Azure, OAuth brokers);
* additional connector catalogs, and a governed replacement for the connector
  configuration UI;
* an isolation tier that makes mutating provider operations selectable;
* SSE and a sandboxed stdio transport;
* a governed raw-evidence retention mechanism;
* a separate, non-authoritative provider health observation system.

Not in scope for Phase 5 and not implied by anything here: an LLM participating
in tool selection, provider selection, capability ranking or authorization
reasoning. That remains impossible by construction at this layer.
