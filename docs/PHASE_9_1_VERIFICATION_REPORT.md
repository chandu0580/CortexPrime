# PHASE 9.1 — Verification Report

**Governed Capability Bridge & Kubernetes READ Contract.** Every claim is labeled
`[FACT]` (declared in code, cite file), `[VERIFIED]` (a test/harness run proved it),
`[NOT VERIFIED]`, `[BLOCKED]`, `[DEFERRED]`, or `[INFERENCE]`.

## Honesty header (the load-bearing labels)

- `[BLOCKED]` **No real Kubernetes cluster or credential was exercised.** No live API
  server was contacted. This is the Phase 5.5 credential class (no real credential
  authenticates); the real HTTPS-to-API-server adapter is `[DEFERRED]` to 9.2. This
  report does **not** claim Kubernetes production integration.
- `[FACT]` The Phase 5.5 credential blocker was **not touched**: no credential was
  inspected, manufactured, added to a fallback, extracted from a K8s secret, placed
  in the World, or placed in a trace. The scripted provider's dev token is a
  caller-supplied `DevelopmentCredentialProvider` secret (refuses production), never
  read from the environment.
- `[VERIFIED]` What *was* proven end-to-end against **real Postgres**: the governed
  Kubernetes READ capability path, read-only-by-construction, resourceVersion
  preservation into a durable Observation, Observation→Fact→WorldQuery, authorization
  + tenant isolation + fail-closed + replay + crash recovery + secret firewall — with
  a **scripted** provider composing the **real** catalog. Labeled as such throughout.

## Part-by-part

### B — Capability bridge (reuse, not duplication)
- `[FACT]` `CapabilityProfile` binds a governed operation to `RiskClassification`
  (reused from `contracts.policy`), `AutonomyLevel` (reused from
  `contracts.intelligence.investigation`), `EffectSemantics`/`SideEffectClass`
  (reused from `contracts.execution`), plus a `VerificationRequirement`, resource
  scope, reversibility, timeout, policy_version.
  `backend/contracts/intelligence/capability_profile.py`.
- `[FACT]` `.to_capability()` returns the exact Phase-8 `Capability` that
  `AutonomyPolicy` (8.8) already consumes — the bridge, not a parallel model.
- `[VERIFIED]` `test_profile_bridges_to_phase8_capability`,
  `test_reuses_existing_risk_and_autonomy_types` pass. Four concepts stay distinct
  (capability ≠ permission ≠ authorization ≠ autonomy); no numeric "score" field
  (`test_capability_not_a_number`).

### C/E — Smallest Kubernetes READ set as governed specs
- `[FACT]` `kubernetes_read_catalog()` declares 6 `ProviderOperationSpec`s:
  `pods.list`, `pod.get`, `pod.logs`, `deployments.list`, `deployment.get`,
  `events.list` — the smallest set for the CrashLoopBackOff / deployment-failure
  vertical (Phase 9.0 §8).
  `backend/contexts/execution/infrastructure/adapters/connectors/kubernetes.py`.
- `[VERIFIED]` `test_catalog_declares_the_smallest_read_set` (6 ops).

### D — Read-only guarantee (construction-time invariant + fail-closed)
- `[FACT]` `CapabilityProfile.__post_init__`: a READ profile must have
  `autonomy_ceiling ≤ A1` and `verification = NONE` and `reversible = True`; a
  mutating profile must have `verification ≠ NONE`.
- `[FACT]` Every catalog spec is `side_effect_class=READ`,
  `effect_semantics=READ_ONLY`, `method="GET"` (hardcoded in `_read()`).
- `[VERIFIED]` READ + action-ceiling rejected, READ + verification rejected,
  mutating + no-verification rejected (`TestReadOnlyGuarantee`, 5 tests);
  `test_catalog_is_read_only_by_construction`, `test_no_write_operation_present`.
- `[VERIFIED]` **Unknown/write op fails closed**: the harness asserts an unknown
  operation and a write-shaped operation are refused by `catalog.require(...)` with
  **no provider call** (harness `_governed_k8s_read` negative legs).

### F — resourceVersion preservation (data contract for future WATCH)
- `[FACT]` Every LIST/GET spec keeps `resourceVersion` in `response_evidence_fields`
  **and** `response_required_fields`; `pod.logs` legitimately omits it (text body, no
  envelope). The adapter normalizes `metadata.resourceVersion` → top-level
  `resourceVersion` because the governed `evidence()` keeps only top-level scalars
  (ADR-042).
- `[VERIFIED]` `test_resourceversion_preserved_in_evidence`.
- `[VERIFIED]` A governed `deployment.get` read's `resourceVersion` (**`100244`** in
  the scenario) survives into the durable `cw_observation`, and a second scenario's
  `resourceVersion=999999` survives a simulated crash (harness).
- `[FACT]` **WATCH is NOT implemented** — only the LIST/GET resourceVersion data
  contract that a future WATCH needs.

### G — Observation ingestion via Phase 7.2
- `[FACT]` The governed read result becomes a `ReadObservation` → `ObservationIngestion`
  → `cw_observation` (the World Plane owns ingestion; the adapter never inserts).
- `[VERIFIED]` Harness: `observations=2` written through the Phase 7.2 path;
  resourceVersion carried in observation evidence.

### H — Provider-neutral WorldQuery
- `[FACT]` No Kubernetes-specific world table / fact type / query was added; the read
  flows through the existing Fact derivation + `WorldQuery`.
- `[VERIFIED]` Harness: `facts=1`; a provider-neutral `WorldQuery` answers
  `readyReplicas=0` for the failed deployment.

### I — Authorization, tenant isolation, failure semantics, idempotency/replay
- `[VERIFIED]` Wrong-tenant read **refused** with no provider call; tenant isolation
  (a second tenant cannot see the first's observation) holds; replay of a completed
  governed read is **inert** (no duplicate provider call, no duplicate observation);
  crash mid-flight recovers deterministically. All in the phase91 harness.
- `[FACT]` One provider call per governed read (`provider_calls=1`).

### J — Fitness rules (only if genuinely new)
- `[FACT]` **No new fitness rule** (Part N): the read-only invariant is enforced by
  the contract + effect gate + catalog unit test; no-SDK / no-httpx / no-ambient-cred
  by the existing `BND-PROVIDER-SDK` / `BND-DIRECT-HTTP` / `BND-AMBIENT-CREDENTIALS`.
- `[VERIFIED]` `test_module_imports_no_sdk_httpx_or_v1_connector` (AST import check:
  no `kubernetes` SDK, no `httpx`/`requests`/`os`, no `backend.connectors`);
  `test_existing_fitness_rules_fence_the_governed_plane` (ProviderSdk + DirectHttp
  rules pass over the built module graph).

### K/O — Provider adapter through the governed transport only; honest labeling
- `[FACT]` `kubernetes_scripted_extension` composes the **real** catalog with a
  `TestProviderAdapter`; provider I/O happens only when the governed transport invokes
  it. Refuses production; `CORTEX_KUBERNETES_SCRIPTED`-gated.
  `backend/api/kubernetes_provider_factory.py`.
- `[DEFERRED]` The real HTTPS-to-API-server adapter (9.2) — no cluster/credential
  available (`[BLOCKED]`, Phase 5.5 class).

## Test & gate evidence (commands run)

- `[VERIFIED]` `pytest tests/intelligence/test_capability_bridge_k8s.py` → **16 passed**.
- `[VERIFIED]` `python scripts/phase91_kubernetes_read_harness.py` (fresh `cortex_p91`,
  real Postgres) → **VERIFIED, 22/22 checks, 0 fail** (observations=2, facts=1,
  provider_calls=1).
- `[VERIFIED]` Architecture gate → **PASS: 35 passed, 0 failed, 6 skipped over 1173
  modules** (the governed K8s module imports nothing forbidden).
- `[VERIFIED]` Regression `pytest tests/intelligence tests/world tests/architecture
  tests/contracts` → **848 passed, 2 warnings**.

## Known limitation (labeled, not hidden)

- `[FACT]` The execution aggregate's run `detail` does not surface `provider_evidence`
  to `runtime.executions.get(...)` (phase72 hit the same limitation). The harness
  reconstructs the governed evidence deterministically via
  `kubernetes_read_catalog().require(op).evidence(<real scripted response>)` — the
  exact bounded facts the governed pipeline extracts. The governed read (authorize →
  gateway → provider → succeeded, one provider call) is real; only the evidence
  *read-back surface* is reconstructed. Surfacing `provider_evidence` on the aggregate
  is a small follow-on for 9.2. `[NOT VERIFIED]` end-to-end evidence surfacing through
  the aggregate — deliberately deferred, not claimed.

## Constraints honored (checklist)

`[FACT]` One Plane of Action preserved — no second capability model, gateway,
executor, scheduler, credential system, or provider path. `[FACT]` World immutability,
independent Assurance, tenant isolation, secret firewall intact. `[FACT]` No WATCH,
no write capability, no real-credential inspection/manufacture/fallback, no K8s secret
extraction, no credential in World or traces. `[FACT]` Phase 5.5 blocker untouched.
