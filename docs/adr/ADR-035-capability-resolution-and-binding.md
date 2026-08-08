# ADR-035 — Capability resolution and binding

**Status:** Accepted
**Date:** 2026-08-08
**Phase:** 3.2.4 — Capability Resolution + Binding
**Extends:** ADR-032 (registry), ADR-033 (discovery), ADR-034 (authorization)
**Related:** ADR-030 (WorkerKindResolver), ADR-031 (durable execution)

---

## 1. Resolution is not authorization, and neither is execution

```
discovery → registry → authorization → resolution → binding → execution
```

Authorization: *may this principal use capability X?*
Resolution:   *which eligible implementation of X should serve this request?*

Resolution **consumes** an authorization decision and grants nothing. It
re-verifies rather than trusting that one was obtained, refusing on five
separate grounds: denied, requires-approval, expired, does not recompute to its
own digest, or was made about a different capability/operation/tenant/principal.
Each is a different way an unauthorized call can look authorized.

## 2. Filter, then rank — structurally

Ineligible candidates are removed **before** ranking, never scored badly and
hoped about. A ranker that can see a revoked capability is one that can be
written wrongly; one that never sees it cannot. The order is enforced by the
shape of the code, not by a rule inside the ranker.

Rejections: revoked · quarantined · not-enabled · trust-insufficient ·
tenant-mismatch · version-mismatch · digest-mismatch · authorization-mismatch ·
environment-mismatch · effect-undeclared · effect-too-strong · contract-mismatch ·
missing-contract-information · provider-not-permitted.

**Unknown is never an advantage.** A candidate whose effect semantics are
undeclared is *ineligible for execution*, not merely low-ranked. A scoring model
treating absence as neutral will eventually rank an undeclared destructive tool
above a declared safe one.

## 3. The ranking model, and what is deliberately absent from it

Four dimensions, all backed by data the registry actually holds:

`exact_version` → `trust_rank` → `tenant_local` → `effect_declared`

No latency, cost, or availability estimates — the platform cannot measure them,
and inventing numbers to produce a winner is how ranking stops being reviewable.

**Version number is not a ranking dimension.** This was a defect in the first
implementation. Because provider is a property of a `(capability_id, version)`
record, preferring the higher version would have silently chosen between
*providers* — precisely the hidden selection this phase exists to remove.

Tie-breaker: `(provider, capability_digest)` — stable identifiers meaning the
same thing in every process. Registration order, dictionary order and object
identity are not used; they would make the same request resolve differently on a
different machine.

## 4. Security precedence

```
eligibility → authorization compatibility → contract compatibility
            → operational preference → deterministic tie-breaker
```

No score can promote a revoked, untrusted, cross-tenant or environment-incompatible
candidate, because none of them reach the ranker.

## 5. Version handling

Execution requires `VersionSelection.EXACT` — enforced, not advised. A request
for `invoke` without a pinned version is refused with
`VERSION_SELECTION_NOT_PERMITTED`, because resolving without one would let the
platform choose which contract runs. `latest` does not exist as a target
(refused at parse time since ADR-032). No silent upgrade, no silent downgrade:
the authorization pins a digest, and a candidate whose digest differs is
rejected.

## 6. Ambiguity — kept, and honestly unreachable today

When candidates tie on every dimension, resolution returns
`AMBIGUOUS_RESOLUTION` naming the contenders, rather than picking one.

**It is currently unreachable, and that is stated rather than hidden.** An
`AuthorizationDecision` pins one exact capability digest (ADR-034) and
`(capability_id, version)` is unique in the registry, so the eligibility filter
narrows to at most one candidate before ranking runs. The directive's motivating
case — three providers of the same capability — is therefore decided at
*authorization*, not here.

The branch is retained because unreachability is a property of the current
authorization model, not of resolution. If a later policy issues
capability-scoped authorization without a digest, this refuses instead of
silently selecting a provider — behaviour that must not have to be remembered
and re-added at that point.

## 7. Provider selection

Provider is an implementation detail; `CapabilityId` is the identity, and it
survives provider replacement. The selected provider is recorded on the binding.

`pinned_provider` **narrows only**. It filters the eligible set and can never
widen it, so naming a provider cannot conjure one that trust, tenancy or
lifecycle would otherwise exclude. A caller cannot route themselves to a
malicious provider by asking for it.

No second provider-trust registry was created. The capability record remains
authoritative.

## 8. Effect, environment, contract compatibility

- **Effect** — `max_effect` refuses anything stronger than the caller accepted.
  A request for a read never binds to a write. `UNKNOWN` ranks above every
  declared value in strength, so it fails any bound.
- **Environment** — a candidate with no declared environments is
  `MISSING_CONTRACT_INFORMATION`, not a wildcard. A staging provider never
  serves a production run, and environment comes from explicit context, never
  from a hostname.
- **Contract** — compared by **schema digest**, never by parsing untrusted
  schemas during ranking.

## 9. The binding

Immutable, digest-bound, expiring. It records tenant, principal, capability ref,
capability digest, provider, operation, both policy versions, the authorization
digest, the mission/workflow/execution it is for, and the machine-readable
reasons the candidate was selected and the others rejected.

**There is no `update`, no `rebind`, and no `change_provider`** — not
discouraged, absent. A binding whose provider could change would let the thing
that runs differ from the thing authorized, with one binding id vouching for
both. A different provider means a new resolution, a new authorization if the
digest differs, and a new binding. The repository refuses to overwrite an
existing binding id.

Expiry is `min(binding TTL, authorization expiry)` — a binding never outlives the
authorization behind it, and expiry is never extended.

## 10. TOCTOU

A binding proves **identity continuity**, not standing authority.
`validate_binding` re-reads the authoritative registry at the execution boundary
and reports every invalidation: expired · authorization-expired ·
capability-revoked · not-enabled · trust-downgraded · digest-changed ·
provider-changed · binding-mismatch · tampered.

Verified: revoking a capability after binding yields
`('capability_revoked', 'trust_downgraded')`, and **the binding does not silently
re-resolve**. Absence of a current record is itself an invalidation — a
capability that can no longer be read is not one to run.

## 11. Replay

The binding key includes the execution it was made for. Presented against a
different execution it fails `matches_execution` and is refused with
`BINDING_MISMATCH`, audited as `REPLAY_ATTEMPT_DETECTED`. A binding is not a
bearer token that happens to name an execution; it is a record that matches only
one.

A tampered binding fails its own digest — verified.

## 12. Provenance and policy versioning

Every binding records why: `exact_version`, `trusted`/`verified`, `tenant_local`,
`effect_declared`, plus each rejected candidate with its reason. Machine-readable
facts only — no narrative, no reasoning traces.

`RESOLUTION_POLICY_VERSION` is recorded on every binding alongside the
authorization policy version, so a historical choice can be explained by the
rules that actually made it. Ranking changes bump the version; old bindings are
never mutated.

## 13. Information disclosure

`ResolutionResult.redacted()` is what the API returns. Rejections marked
`is_security_relevant` — tenant-mismatch, trust-insufficient, quarantined,
revoked — are withheld, leaving only a count. Telling a caller a candidate was
rejected for tenancy confirms it exists. The resolver must never become a
provider inventory leak.

## 14. Deliberately not built

**No fallback rebinding.** If the selected provider later fails, whether a retry
is *safe* is a runtime decision Phase 3.1 already owns — not a licence for this
service to quietly pick somebody else.

**No cache.** A stale entry could select a revoked capability, an old digest, or
a withdrawn provider. Correctness outranks the lookup cost at this boundary.

**No LLM, no embeddings, no semantic search.** V1's only capability selection is
an LLM tool-selector prompt (`ConnectorRegistry.get_capabilities_prompt`); that
is what this phase supersedes for security decisions and it remains a strangler
target. Selection here is deterministic and inspectable. A model may later
suggest candidates; it must never control the binding.

**No credentials, no execution, no worker, no connector, no MCP transport.**

## 15. Composition root and the Phase 3.3 seam

`capability_resolution_composition.py` assembles the service. Connectivity does
not import Execution and Execution does not import Connectivity — verified in
both directions. `WorkerKindResolver` (ADR-030) is **untouched** and remains the
only execution attachment seam.

Phase 3.3 will consume:

```
CapabilityBinding → composition-root adapter → WorkerKindResolver → worker
```

The binding is self-contained — digest, provider, contract, authorization
reference — so a worker adapter never needs to re-ask how the choice was made.

## 16. Compliance

- **S2** — imports only `contracts/` and `platform/`; verified against all five
  other contexts.
- **ADR-017 / BC-9** — explicit `ExecutionContext` throughout; another tenant's
  binding is absent, not forbidden.
- **ADR-018** — no new authoritative file store.
- Reused: platform canonical hashing, ULID identity, `DomainEvent`/
  `EventMetadata`, `AuditEventKind`, `RepositoryGuard`, `EffectSemantics`,
  `PrincipalRef`. No second registry, policy engine, hashing or ranking
  framework.

## 17. Known limitations

Binding persistence is **in-memory and not durable** — a restart loses every
binding. Bindings expire in minutes and a lost one means re-resolving, so this is
survivable, but it is not durability.

`AMBIGUOUS_RESOLUTION` is unreachable under the current authorization model
(§6). It is retained deliberately and is the one branch in this phase without
live coverage.
