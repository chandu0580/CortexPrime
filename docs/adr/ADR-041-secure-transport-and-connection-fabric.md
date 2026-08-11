# ADR-041 — Secure transport and connection fabric

**Status:** Accepted
**Date:** 2026-08-08
**Phase:** 4.2 — Secure Transport + Connection Fabric
**Extends:** ADR-040 (credentials), ADR-038 (invocation gateway), ADR-033 (discovery endpoints)

---

## 1. The one question

    "How can this already-authorized invocation reach the selected provider?"

Transport never answers *"may this action happen?"*. The invocation gateway
answered that before a transport request existed, and a transport that could
re-answer it would be a second place the answer could differ.

A successful TLS handshake authenticates a channel. It authorizes nothing.

## 2. Ownership

`platform/transport/`, alongside the credential fabric and for the same reason:
Execution decides *when* a connection is needed, Connectivity describes *which
provider*, and those two may not import each other. Vocabulary that crosses the
boundary — `TransportKind`, `ConnectionRef`, `TransportFailure` — is in
`contracts/`; parsing needs `ipaddress` and `urllib`, which `DEP-CONTRACTS-LEAF`
does not permit there, so it lives in platform.

## 3. Protocol ≠ transport ≠ provider

| | |
| --- | --- |
| MCP | an application protocol |
| Streamable HTTP / SSE / stdio | transports MCP can be spoken over |
| GitHub | a provider, which is neither |

Collapsing any pair breaks the model somewhere. `MCP == HTTP` gives an
MCP-over-stdio server HTTP's rules and none of its own; `provider == transport`
gives every provider its own transport security and one of them will get it
wrong.

`TransportKind.is_network` is what routes stdio away from the address policy —
a local process is a different and worse problem, handled by a different boundary
rather than by pretending an IP rule applies.

## 4. Endpoint model

`TransportEndpoint` parses, **normalises**, and refuses. Normalisation is part of
the security boundary, not tidiness: an endpoint that compares unequal to itself
cannot be allow-listed, pooled safely, or audited coherently. Host lowercased,
root dot stripped, default port made explicit, path rooted.

Refused: `file:`, `data:`, `javascript:`, `ftp:`, `gopher:` and every other
scheme; embedded credentials; control characters (checked over the raw string
before parsing, since parsers silently drop them); over-long URLs, hosts and
labels; invalid ports.

**Query strings are carried and never logged.** `normalised` and `to_dict` omit
them; only `dial_target` reassembles. A query routinely carries a token or a
signature, which makes the full URL the one field that must not reach a log or a
metric label.

### Relationship to `DiscoveryEndpoint`

Kept separate, deliberately. `DiscoveryEndpoint` (ADR-033) *records* provenance
and permits `http` and `stdio` while recording `is_private` rather than refusing
it — correct there, because a platform-internal MCP server on `10.0.x.x` is
legitimate to discover. This one is **dialled**, so it refuses. Two types
because they give different answers to the same input on purpose; merging them
would force one to be wrong.

The checks they *agree* on — length, control characters, scheme presence,
embedded credentials, port validity — are one function, `parse_url_structure`.
Security-sensitive parsing written twice is parsing that gets fixed once.

## 5. SSRF model

The first layer that can connect, so the address policy lives here.

`classify_literal` is pure, total, and does no I/O. It handles:

loopback · private (RFC1918) · link-local · IPv6 unique-local (`fc00::/7`) ·
carrier-grade NAT (`100.64/10`) · multicast · unspecified · reserved ·
broadcast · **cloud metadata**

**Cloud metadata is refused unconditionally** — even when its class is listed in
`allowed_address_classes`. A deployment permitting private destinations is saying
"our providers live in the cluster"; it is not saying "the instance credential
service is a valid provider", and no configuration should be able to say the
second by accident.

### The bypass forms, and a real bug this caught

Numeric spellings are **not** pattern-matched — they are parsed, because a
pattern has to enumerate the forms and will miss the next one. Verified against
`127.1`, `127.0.1`, `0177.0.0.1`, `0x7f.0.0.1`, `0x7f000001`, `2130706433`,
`017700000001`, `::1`, `::ffff:127.0.0.1`.

Two of those initially failed. Python's `ipaddress` is deliberately strict — it
rejects leading zeros and abbreviated forms *because they are ambiguous* — so
`0177.0.0.1` and `127.1` fell through as hostnames and would have been handed to
DNS, where `getaddrinfo` resolves both to loopback. **That is a working SSRF
bypass**, and it was live in my first implementation.

The fix is to fall back to `socket.inet_aton`, which implements the same
permissive BSD parsing the resolver itself uses. Erring toward *more* strings
being treated as literals is the safe direction: a literal is judged by the
policy, while a string that falls through is judged on whatever DNS returns.

The existing `safety/guardrails_engine` regex — matching `127.`, `10.`,
`192.168.` as string prefixes — misses every form above plus `fe80::`,
`100.64/10`, and any hostname that merely resolves privately. It is not a
network primitive and is not relied on.

## 6. DNS and rebinding

    resolve → judge every answer → pin approved addresses → dial the pins

**Every** answer must pass, not one. A host resolving to a public address *and* a
loopback address will reach loopback on some fraction of connections; approving
it because one answer looked fine is how a round-robin rebind succeeds on the
second attempt. `pinned_addresses` is empty whenever anything was refused.

Literal addresses skip resolution — a lookup cannot change the answer.
Loopback aliases (`localhost`, `ip6-localhost`, …) are caught before resolution
so a resolver answering oddly cannot matter.

`require_dns_resolution=False` does **not** mean "trust the name". It refuses
every hostname and permits only literals, because a name that was not resolved
was not judged.

### The limit, stated

Pinning defends a caller that connects to the pins. **An adapter that re-resolves
the hostname is outside the defence**, and this fabric can only make the safe
path the obvious one and say so — which the `TransportAdapter` contract does, as
its first requirement. Phase 4.3 adapters must be reviewed against it.

## 7. Redirects

**Off by default.** A redirect changes host, scheme, port and network zone —
every property the endpoint check established. Following one means the
destination that was validated is not the destination that was reached.

When enabled, each hop is re-validated from scratch: full endpoint judgement,
full resolution, full address policy. A 302 to `http://169.254.169.254/` is
refused at the target, not merely at the origin.

**Credentials never cross an origin**, and that is not configurable —
`credentials_may_follow` is a `staticmethod` with no policy field behind it.
Forwarding an `Authorization` header to whatever host a provider names in a
`Location` is credential disclosure on request.

## 8. TLS

**There is no `verify=False`.** `verify_certificates` and `verify_hostname` are
not fields on `TlsPolicy`, so there is no value anybody can set. A boolean that
can be turned off gets turned off at 2am and stays off.

TLS 1.2 floor; 1.0/1.1/SSLv3 refused at construction. A provider declaring
anything about TLS changes nothing — metadata is not authority. Plaintext is a
per-policy exception and is **structurally impossible in production**:
`ConnectionPolicy` refuses to construct with it.

Private CAs are an explicit `ca_bundle_path` — a path, not certificate bytes, so
trust configuration stays in deployment configuration rather than in an object
that gets passed around.

## 9. mTLS seam

`client_certificate_ref` is an **opaque reference** to material the credential
fabric holds. The private key never enters transport state, and a cheap
constructor guard refuses a value containing `BEGIN` — the exact mistake the
field exists to prevent. Key material reaches a transport the same way a bearer
token does: at the moment of use, from `CredentialProvider`, and dropped after.

## 10. Proxy

**Off by default, and `trust_environment` is `False`.**

Two dangers, separately. A user-controlled proxy URL is an SSRF bypass no
endpoint check catches, since the proxy chooses the real destination. And an
*inherited* proxy is worse: **every httpx client in this repository uses
`trust_env=True` (the default) and therefore silently honours `HTTP_PROXY`,
`HTTPS_PROXY` and `ALL_PROXY`.** A variable set in a deployment changes the real
destination of every outbound request at once, and nothing opts out.

The fabric defaults it off and the adapter contract requires honouring that.
Proxy URLs with embedded credentials, and non-http proxy schemes, are refused.

## 11. Timeouts and cancellation

Six separate bounds — DNS, connect, TLS handshake, read, idle, total — because
the phases fail differently and one combined value means tuning at least one of
them wrongly. Every one is positive, ceilinged at 600s, and there is no way to
express infinity.

`bounded_by(authority_seconds)` clamps every phase to the remaining authority
window by taking the minimum. Work must not outlive the permission for it, and a
closed window refuses rather than clamping to zero.

Cancellation is part of the adapter contract and maps to `TransportFailure.
CANCELLED`, distinct from timeout and from failure. Nothing converts cancellation
into success or into a retry — Execution owns both decisions.

## 12. Connection lifecycle and pooling

`OPENING → OPEN → DRAINING → CLOSED | FAILED`. Only `OPEN` permits use.

**Pooling is not implemented, deliberately.** Correctness before performance
(§17 of the directive). A pool that reused an authenticated connection across
tenants, principals, credentials or environments would defeat every isolation
property above, and a pool key safe against all of them is a design decision that
deserves its own evidence rather than being assumed here.

What *is* implemented is `ConnectionSlots` — bounded concurrency keyed by tenant
and endpoint. It caps how much of the process one tenant's misbehaving provider
can occupy, which is a fairness property as well as an isolation one. It reuses
nothing authenticated.

## 13. Resource budgets

A **malicious provider is as dangerous as a malicious caller**, and rather more
likely to be overlooked. Bounded: response bytes, request bytes, header count,
header bytes, URL length, per-frame bytes, stream duration, concurrent
connections.

Per-frame is separate from the response total on purpose: a provider can stay
inside a total budget while sending one frame large enough to exhaust memory
being assembled. Truncation is reported (`truncated`), never silent — a truncated
body that looked complete would be parsed as complete.

## 14. Headers

Caller-supplied headers are **refused, never sanitised**. Silently stripping an
`Authorization` header means the caller believes it was sent and the request goes
out unauthenticated, failing in a way nobody can read.

Forbidden from callers: `Authorization`, `Proxy-Authorization`, `Cookie`,
`Content-Length`, `Transfer-Encoding`, `Connection`, `Upgrade`, `Host`, and the
`X-Forwarded-*` family. Authentication is the credential fabric's exclusively;
the framing pair is the classic request-smuggling vector; `Host` reaches a
different virtual host than the one the policy judged.

Names are lowercased before every check, so a forbidden-name rule cannot be
walked past by changing case. Control characters in names or values are refused —
a newline does not corrupt a header, it ends one and starts another.

## 15. Credential integration

Material arrives on `TransportRequest.credential` with `repr=False`,
`compare=False`, absent from `to_dict`, and unserialisable in itself — so a
request somebody tries to write down fails loudly rather than quietly emitting a
token. Verified.

Transport **never** fetches credentials, reads environment secrets, consults a
global store, or accepts a caller token. No fallback exists. Redaction reuses the
Phase 4.1 primitives (`safe_exception_text`); no second scrubber was written.

`_with_endpoint`, used to judge redirect targets, drops the credential — a copy
made purely to run the address policy has no reason to hold a secret.

## 16. Retries and idempotency

**No retry loop in the broker** — verified by AST, and it dials exactly once.

A network retry can duplicate a privileged action. Connection establishment
before any byte is written is safely retryable and is expressed as a bound on the
adapter contract; once a request may have been transmitted, control returns to
Execution.

`idempotency_key` is Execution's, passed through untouched. The transport never
mints one and never varies it per attempt — a new key per attempt would make
every retry a new operation to the provider, which is the opposite of the point.

## 17. Outcomes and unknown state

`DeliveryState` — `NOT_DELIVERED` / `DELIVERED` / `UNKNOWN` — is the field
Execution reads. `TransportFailure.is_definitely_not_delivered` is deliberately
conservative: only failures occurring before a byte is written. Everything else
is possibly-delivered, because the cost of being wrong in that direction is a
duplicated production change.

An adapter that raises mid-dial yields `UNKNOWN`, never a definite failure. An
adapter returning something uninterpretable yields `UNKNOWN` too. 31 distinct
failure codes, because collapsing them into `connection_failed` removes exactly
what recovery reads.

## 18. MCP preparation

Seams only. `MCP_STREAMABLE_HTTP` and `MCP_SSE` are `TransportKind` values that
inherit **the whole boundary** — TLS, endpoint validation, SSRF, redirects,
timeouts, budgets, credential controls. There is no privileged MCP path.

`MCP_STDIO` is a kind with no endpoint: `TransportEndpoint.parse` refuses it and
`ConnectionPolicy` refuses it, because a stdio target names a local process and
belongs to the worker sandbox boundary. **No subprocess, no shell, no command
execution** appears anywhere in this phase — verified by AST.

No tool discovery, no tool execution, no session management, no MCP
authorization semantics. Those are Phase 4.3 and later.

## 19. What is deliberately not built

**No transport.** No HTTP client, no socket connect, no TLS context — verified by
AST across five modules: none imports `httpx`, `requests`, `aiohttp`,
`urllib3`, `websockets`, `ssl` or `subprocess`.

With no adapter registered every dial refuses `transport_unavailable`. That is
correct for a platform with no transport, and the same shape the worker directory
took when it had no workers.

`DevelopmentTransport` exists so the paths *after* a successful approval can be
exercised. It sits **behind** the broker — every request it sees has already
passed endpoint policy, address judgement and pinning, and it cannot reach a
private address. It refuses production at construction and again at dial.

## 20. V1 reconciliation

Six outbound paths inventoried in `backend/api/legacy_network_inventory.py`, each
read rather than assumed. **Nothing was migrated**, stated rather than implied.

**The one hazard:** `backend/mcp/connectors/web.py` exposes `fetch_url` and
`http_get` taking a **caller-supplied URL** and caller headers, with
`follow_redirects=True`. That is a complete SSRF primitive whose only guard is
the prefix regex above. It is reachable solely through
`POST /api/v2/mcp/execute`, which is **gated off by default** (ADR-038), so it is
inert unless an operator sets the migration flag. Migrate or remove in Phase 4.3.

The ~18 provider connectors are lower risk — destinations are fixed at
construction rather than caller-chosen. Identity providers, model providers and
the health probe are outside the execution transport path and are recorded so the
exclusion is deliberate rather than accidental.

Two cross-cutting findings, recorded once: **no TLS bypass exists anywhere** in
the repository (searched for `verify=False`, `_create_unverified_context`,
`check_hostname`), and **every httpx client inherits environment proxies**.

## 21. Architectural contradictions found

1. **My own SSRF classifier had a working bypass.** `0177.0.0.1` and `127.1`
   fell through to DNS. Fixed with `inet_aton`; see §5.
2. **`contracts/` cannot parse.** `DEP-CONTRACTS-LEAF` permits neither
   `ipaddress` nor `urllib`, so vocabulary and parsing had to split across
   `contracts/` and `platform/` — the same constraint that shaped Phase 4.1.
3. **Time-dependent verification.** Two Phase 3.3.4 assertions mixed a frozen
   clock with real-time lease grants and began failing as the wall clock
   advanced. Fixed in the checks, not the code.

## 22. Carried-forward dependency: the Phase 4.1 delegation gap

Directive §29 asks that this not be silently ignored, so it is restated.

`AuthorityFacts` carries only `principal_id` (the actor). Delegation
(`on_behalf_of`) is preserved end-to-end and **must match the authenticated
context**, so it cannot be forged — but nothing confirms it against the
*authorization decision*, because there is no field to compare it to.
`CredentialRefusal.DELEGATION_NOT_AUTHORIZED` is declared and never raised.

Transport preserves the distinction (`TransportRequest.on_behalf_of`) and does
not deepen the gap. Closing it means adding a delegated-principal field to
`AuthorityFacts` and populating it at the composition root — an ADR-038 change,
which is why it is reported rather than made here.

## 23. Genuine remaining risks

- **No transport exists**, so the fabric is unexercised against a real network.
  Correct for the phase, and it means Phase 4.3's first adapter is where the
  contract gets tested.
- **DNS rebinding is bounded, not eliminated.** An adapter that re-resolves is
  outside the pinning defence; the contract forbids it and nothing yet enforces
  it mechanically.
- **`web.py` remains** — inert behind a gated route, but present.
- **Every V1 client still inherits environment proxies.**
- **No pooling** means a connection per request when a transport arrives; that is
  a performance cost accepted deliberately.
- **`SystemAddressResolver` sets the process-global default socket timeout**
  around `getaddrinfo`, which has no per-call timeout. Isolated in one small
  class, but it is process-global state for the duration.

## 24. Phase 4.3 boundary — not started

No provider implementation of any kind: no GitHub, Jira, Slack, Kubernetes, AWS,
Azure, GCP, browser, shell, Docker or Terraform. No MCP tool discovery,
execution, or session management. No OAuth flow. No LLM in any transport
decision.

Phase 4.3's first tasks, which the inventory already names: write the first
`TransportAdapter` against this contract, migrate or remove `web.py`, and begin
the connector migration behind the existing `ConnectorInvoker` seam.
