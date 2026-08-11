# ADR-040 — Credential and secret management fabric

**Status:** Accepted
**Date:** 2026-08-08
**Phase:** 4.1 — Credential + Secret Management Fabric
**Extends:** ADR-038 (invocation gateway), ADR-039 (execution lifecycle), ADR-034 (authorization), ADR-035 (binding)

---

## 1. The one rule

**A reference may be written down. Material may not.**

| Type | Holds | May be persisted |
| --- | --- | --- |
| `CredentialRef` | an opaque, tenant-qualified handle | yes — records, events, audit, replay |
| `CredentialGrant` | scope, expiry, type, state, fingerprint | yes |
| `CredentialMaterial` | **the secret** | never — unserialisable by construction |

Everything else in this phase follows from keeping those apart.

## 2. Possession is not authority

Holding a credential proves you can authenticate to a provider. It does **not**
mean CortexPrime authorized the action — the invocation gateway already decided
that (ADR-038), and obtaining a credential does not revisit it.

That separation is the security property worth having: a leaked credential still
fails at the gate. The fabric is a mechanism for authenticating outward, never a
second route to permission.

## 3. Ownership

`platform/credentials/`, not a new bounded context. Execution decides *when* a
credential is needed; Connectivity describes *which provider* is reached; those
two may not import each other, so the fabric lives beneath both. Phase 4.1's stop
condition names a new bounded context as a reason to report rather than build,
and the fabric owns no business decision — only a mechanism.

`CredentialRef`, `CredentialScope`, `CredentialType` and `CredentialState` are in
`contracts/` because they cross the context boundary and get persisted.
`CredentialMaterial` is deliberately *not* there: contracts describe things that
get written down.

## 4. `CredentialRef`

`cred://<tenant>/<opaque-id>`. Tenant-qualified **in the identity itself** rather
than alongside it — a reference whose tenant could be changed by editing a
neighbouring field is one that eventually will be.

Never derived from the secret (that would leak by construction) and length-bounded
as a cheap guard against a token being passed where a reference belongs. Its
`to_dict` has exactly three keys and none can hold a value.

## 5. `CredentialMaterial` — leakage prevented, not discouraged

A rule saying "do not log credentials" holds until somebody adds a debug line. So
each escape route does the safe thing on its own:

| Route | Behaviour |
| --- | --- |
| `repr` / `str` / `__format__` | `<CredentialMaterial …redacted>` |
| `__getstate__` / `__reduce__` | **raise** — blocks pickle, copy, deepcopy, `dataclasses.asdict`, and every serialiser built on them |
| `to_dict` | **raises** — the codebase's universal "write this down" method, and the one an audit path reaches for by habit |
| `__eq__` | **raises** — ordinary equality leaks by timing; `matches()` is constant-time |
| `__hash__` | `None` — cannot become a dict key or set member |

Not a `@dataclass`, deliberately: a generated `__repr__` prints every field.

The secret has **one exit**: `reveal(purpose=...)`, keyword-only and requiring a
non-blank purpose. `grep -rn "\.reveal("` is the complete audit of what touches
secret material in this codebase.

All verified, including that `json.dumps` fails rather than leaking.

## 6. The provider port

The **existing** `CredentialProvider` seam (ADR-036) is authoritative. No second
abstraction was created.

It was **widened**: it previously took `(context, binding)`, which cannot prevent
a confused deputy — a binding says which capability was chosen, not which *action*
was authorized, so a provider given only that could return a credential for a
different resource within the same capability. It now takes a `CredentialRequest`
carrying the full authority. Nothing implemented the old shape, so no caller broke.

`CredentialAdapter` is provider-neutral with three verbs — `acquire`, `validate`,
`revoke` — and only where the mechanism supports them. **No vendor name appears
anywhere in the fabric**, verified by AST across four modules: no `hvac`, `boto3`,
`azure.keyvault`, `google.cloud`, `requests` or `httpx`.

## 7. Authority binding

```
Identity → Tenant → CapabilityBinding → AuthorizationDecision
→ Approval (if required) → CredentialRequest → Credential
```

Every field of `CredentialRequest` is required. Nothing is inferred: no ambient
tenant, no current principal, no default environment. A subsystem that could fill
a blank would eventually fill the wrong one, and the blank most likely to be
filled wrongly is the tenant.

**The action digest is reused, never recomputed.** It is ADR-038's — capability,
operation, validated input, tenant, principal, environment, binding, policy
version, under one hash. That is what makes the confused deputy structural: a
credential issued for "create an issue in repository A" carries the digest of
*that* action, and the grant is refused if it names a different one.

## 8. Scope

Explicit and provider-neutral. The fabric does not enumerate provider scopes — it
would need changing for every provider and be wrong about the first one it guessed.

What it enforces is the relationship:

- **Broader than requested → refuse** (`SCOPE_BROADENED`). A credential stronger
  than the authority that asked for it is a privilege escalation delivered by the
  component meant to prevent one.
- **Narrower than requested → refuse** (`INSUFFICIENT_SCOPE`), unless the caller
  explicitly set `allow_partial_scope`. Silently accepting half a credential fails
  in the middle of an operation somebody approved.
- **Different resource → refuse** (`RESOURCE_MISMATCH`). `covers()` is
  resource-aware, so a scope for repository A never covers repository B however
  many verbs it holds.

## 9. Just-in-time lifetime

```
effective_expiry = min(
    now + requested_lifetime (ceiling 900s),
    authorization_expires_at,
    approval_expires_at,
    execution deadline,
)
```

The minimum is the only combination that cannot be widened by adding another
authority. Seconds are **floored**, never rounded up past an expiry.

`MAX_CREDENTIAL_LIFETIME_SECONDS = 900` is a ceiling no call site can raise —
`CredentialRequest` refuses to construct above it, because the call site is
exactly where it would be raised for convenience.

A provider issuing something longer-lived than the authority is **refused**
(`LIFETIME_UNSUPPORTED`), not truncated: truncating would leave the provider
holding something valid we merely decided to stop using. A long-lived secret is
not a JIT credential, and the fabric says so rather than pretending.

## 10. Fail-closed inventory

23 refusal codes. All verified:

| Condition | Result |
| --- | --- |
| no adapter registered | refuse — **no default, no fallback** |
| authorization expired | refuse |
| approval required and absent / expired | refuse |
| authority window closed | refuse |
| authority changed since admission (TOCTOU) | refuse |
| authority unverifiable | refuse |
| provider raises / returns `None` / returns garbage | refuse |
| credential expired / revoked / **state unknown** | refuse |
| tenant, action, binding, provider, environment mismatch | refuse |
| scope broadened / insufficient / wrong resource | refuse |
| credential outlives its authority | refuse |
| another tenant's credential | refuse |

`UNKNOWN` fails closed everywhere. "Not known to be invalid" is not "known valid"
— treating it otherwise is how a revoked token keeps working during the incident
it was revoked for.

**No fallback of any kind**: no default provider, no system credential, no other
tenant's credential, no cached unrelated token, no environment variable, no
forwarded caller `Authorization` header (searched; none found).

## 11. Post-issuance verification

The most important code in the broker runs *after* the adapter answers. An adapter
is infrastructure somebody else may have written, and it can return a credential
that is broader, for the wrong tenant, for the wrong resource, or already expired.
Each is refused; the tenant check runs first and unconditionally.

Verified against eight deliberately misbehaving adapters.

## 12. TOCTOU

`AuthorityRevalidator` re-reads the authority chain immediately before minting.
Between the gateway admitting an invocation and the credential being issued, a
capability can be revoked or a binding invalidated — and unlike a refused
invocation, a *minted* credential exists at the provider whether or not we use it.

Implemented at the composition root over ADR-035's `validate_binding`, so it is a
re-read rather than a second opinion. Raising, or no service wired, both refuse.

## 13. Tenant and principal isolation

Tenancy is checked three times: the request's own fields, the caller's
authenticated context (`BrokerCredentialProvider`), and the returned grant's
reference. Cross-tenant `validate` returns `UNKNOWN` — the same answer as a
nonexistent credential, because confirming another tenant's credential exists is
itself a disclosure. Cross-tenant `revoke` returns `False`.

Delegation is preserved, not flattened: `principal` (actor) and `on_behalf_of`
(original requester) stay distinct, and `effective_principal_id` derives which
authority the credential represents so no call site has to remember.

## 14. Gateway integration

ADR-038's ordering is **unchanged** and verified by parsing `admit`:

```
identity → tenancy → binding → authorization → approval → worker
→ input → action digest → obligations → freshness → lease → rate → credentials
```

Credentials stay **last**. A request that was going to be refused never causes a
secret to be minted — verified: a denied authorization mints nothing.

The material rides on `InvocationAdmission.credential` with `repr=False` and
`compare=False`, and is **never** in `audit_detail` — only the grant's reference,
type, scope, expiry and fingerprint are. A second guard comes free:
`IssuedCredential.__getstate__` raises, so `dataclasses.asdict` on an admission
fails loudly rather than quietly emitting a secret.

## 15. Retry, recovery, compensation

Credentials are **not reusable authority**. Nothing stores one in an
`ExecutionAttempt`, a checkpoint, an event, or the outbox — structurally
impossible, since none of those can hold an unserialisable object.

A retry is a new attempt through the gateway, so it re-runs the whole chain and
acquires fresh material. Compensation is a new governed invocation (ADR-039 §10)
with its own binding, authority, lease and credential — never the original's,
merely because it targets the same provider.

Material is acquired at admission and dropped after invocation. It does not
survive queue delays, retry backoff, recovery waits or compensation planning.

## 16. Redaction

Two mechanisms, deliberately different:

- **`redact_mapping`** works by *key* — reliable, since keys are ours and
  enumerable. Separators are normalised, so `X-Api-Key`, `api_key` and `apiKey`
  all match. *(That normalisation was a real bug caught in verification: `X-Api-Key`
  slipped past `api_key` and would have reached a log beside a redacted field.)*
- **`scrub_text`** works by *pattern* over free text where there is no key —
  exception messages, provider error bodies. **Best-effort and documented as
  such**; pattern matching over text somebody else wrote cannot be complete.

`NON_SENSITIVE_KEYS` is an explicit allow-list so `authorization_digest` and
`authorization_effect` — the substance of an audit record — are not redacted by
the "authorization" fragment. An explicit list, not a pattern: every entry is a
reviewable claim that one named field is safe.

`safe_exception_text` replaces bare `str(exc)` on credential paths: an HTTP
client's exception routinely carries the request it was making, headers included.

## 17. Audit, events, metrics

Audit reuses `AuditRuntime` — no second framework. It answers who, which tenant,
which execution, node, capability, operation, provider, reference, scope,
decision, expiry and outcome. Refusals are audited as first-class facts. Audit
failure **cannot turn a refusal into an allow** (the decision is already made;
a raise there could be caught as something else).

**No credential events were added.** `InvocationAdmitted` already carries the
grant metadata at the only moment it matters, and ADR-039 established that an
event pair with nothing between them is duplication. A separate `CredentialIssued`
would restate a fact `InvocationAdmitted` already states, at the same instant.

Metrics carry tenant, provider and environment. **Never a reference** — not
secret, but high-cardinality and per-credential, which would turn a dashboard into
a credential inventory.

## 18. No credential API

**None was added.** No listing, no `GET /credentials/{id}/value`, no reveal, no
raw retrieval. The only pre-existing secret-adjacent endpoint
(`security_center /secrets`) returns metadata pointers with no value field —
verified by reading the model, not assumed.

## 19. Development provider

`DevelopmentCredentialProvider` — named so nobody mistakes it. Not
`InMemoryProvider`, not `DefaultProvider`; a harmless-sounding name ends up in a
production composition root and the reviewer moves on.

Refuses production **four ways**: `PRODUCTION` in its environments at
construction; missing `allow_non_production=True`; a production request at
acquisition (construction checks are bypassable by a mutated attribute); and
`build_development_broker` refusing it too — a differently-named function rather
than a flag a config file can set by accident.

It ships **no hard-coded secrets**. Every value is supplied by its constructor, so
there is no key in that file to leak or copy into a fixture. Verified by AST.

## 20. Persistence and durability — stated plainly

**Nothing about credential storage is durable, and nothing claims to be.**

| Concern | Status |
| --- | --- |
| Secret material | never persisted anywhere by CortexPrime — structurally impossible |
| Grant metadata | returned to the caller; **no store was built** |
| Runtime retrieval | the adapter's, and no production adapter exists |

No credential cache was built. The directive permits one with a defined scope,
TTL, eviction and revocation behaviour; none of those is needed while every
credential is acquired for one invocation and dropped, and a cache is the thing
most likely to become an invisible global credential store.

## 21. V1 reconciliation — six surfaces inventoried, one hazard

Inventoried in `backend/api/legacy_credential_inventory.py`, each read rather than
assumed. **Nothing was migrated**, and that is stated rather than implied.

**The hazard:** `backend/auth/credential_store.py :: CredentialStore` decrypts
*every* stored credential into a process-wide dictionary at construction, keyed by
a bare id with no tenant anywhere in the type, exposed as a module singleton. It
is the global credential dictionary and the ambient-tenant lookup this phase
forbids, in one object. **It is currently unreferenced** — no module imports it,
verified by grep — so it is a loaded weapon in a drawer rather than one in use.
Not deleted here: deleting a credential store is a decision with data attached.
It should be removed or gated before Phase 4.2.

**Ten V1 connectors** read a process-wide env var for their token — one token per
provider for every tenant, which cannot express per-tenant credentials at all.
Strangler targets behind the Phase 3.3.2 `ConnectorInvoker` seam; every V1 route
reaching them is already gated (ADR-039).

**`VaultClient`** is a working client with no tenant scoping — and **the natural
first production adapter**. Wrapping it in a `CredentialAdapter` gives it tenant
scoping, action binding, scope checking and lifetime bounding without a rewrite.
Phase 4.2.

None of these bypasses the *invocation gateway*. They bypass the *credential
fabric*: a leaked V1 secret authenticates to a provider; it does not authorize a
CortexPrime action.

## 22. Rotation vs revocation

Rotation is infrastructure lifecycle and changes nothing about capability
identity, version, digest, workflow digest or execution identity — a rotated
secret produces a new `CredentialRef` and nothing else moves. **No capability
rebinding is forced by a provider rotating a secret.**

Credential revocation and capability revocation stay distinct states with distinct
causes. Both block invocation; merging them would make "rotate the token" and
"withdraw the ability" the same operation.

## 23. Architectural contradictions found

1. **Two clocks in the fabric.** The development adapter read `datetime.now()`
   while the broker used its injected clock, so a request could be inside its
   window per one and outside per the other. The adapter contract now takes `now`
   from the broker — the same defect ADR-038 closed by threading its clock into
   the worker runtime.
2. **Refusal ordering hid the specific cause.** The aggregate window is the
   minimum of every expiry, so an expired authorization also closed it and
   reported `AUTHORITY_WINDOW_CLOSED` — leaving an operator to work out which of
   four clocks ran out. Specific reasons now precede the aggregate.
3. **Separator-blind key matching.** `X-Api-Key` did not match `api_key`.
4. **`contracts/` may not import `re`.** `DEP-CONTRACTS-LEAF` curates a short
   stdlib allow-list. Scope validation was rewritten with plain string
   operations rather than widening that list to fit one validator.

## 24. Genuine remaining risks

- **No production adapter exists.** The fabric refuses everything until one is
  written. Correct, and it means the fabric is unexercised against a real
  provider.
- **`CredentialStore` remains on disk**, unreferenced but present, holding
  whatever a previous deployment wrote.
- **Ten connectors still read env vars.** Inert behind gated routes, but the
  secrets are in the process environment where any code can read them.
- **`scrub_text` is best-effort.** A token with no recognisable prefix in a field
  with no recognisable name passes through. It is the last line, not the defence.
- **No credential metadata store**, so a grant's history is not queryable after
  the invocation that used it.
- **In-process only.** Nothing here survives a restart, consistent with ADR-039's
  persistence boundary.

## 25. Phase 4.2 boundary — not started

No MCP transport, no OAuth remote flow, no GitHub/Jira/Slack connectors, no
browser/shell/Docker/Kubernetes workers, no cloud integration, and no vendor
adapter of any kind. No LLM participates in any credential decision.

The first Phase 4.2 tasks the inventory already names: wrap `VaultClient` as a
`CredentialAdapter`, and decide the fate of `CredentialStore`.
