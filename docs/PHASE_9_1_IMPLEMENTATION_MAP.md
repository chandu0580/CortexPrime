# PHASE 9.1 — Implementation Map

What was added/changed, and where it plugs into the existing architecture. **No second executor, scheduler, gateway, approval, audit, world-store, assurance, or credential system was created.**

## New files

| File | What it is | Reuses |
|---|---|---|
| `backend/contracts/intelligence/capability_profile.py` | The **bridge contract** `CapabilityProfile` + `VerificationRequirement`. Binds a governed operation to its Phase-8 risk/reversibility/verification/autonomy_ceiling; `.to_capability()` → the Phase-8 `Capability`. Read-only guarantee in `__post_init__`. | `RiskClassification`/`RiskLevel` (contracts.policy), `AutonomyLevel` (investigation), `SideEffectClass`/`EffectSemantics` (execution), `Capability` (autonomy) |
| `backend/contexts/execution/infrastructure/adapters/connectors/kubernetes.py` | The governed **Kubernetes READ catalog** (`kubernetes_read_catalog()`, 6 `ProviderOperationSpec`s, all READ, resourceVersion in evidence) + **`kubernetes_read_profiles()`** (a `CapabilityProfile` per op, A1 ceiling). | `ProviderOperationSpec`/`OperationCatalog`/`ParameterSpec` (execution.domain), the bridge contract |
| `backend/api/kubernetes_provider_factory.py` | A **scripted** governed provider (`kubernetes_scripted_extension`) — composes the real catalog with `TestProviderAdapter` + a K8s responder (normalized bodies with resourceVersion). Honestly labeled; refuses production; `CORTEX_KUBERNETES_SCRIPTED`-gated. | `controlled_provider_factory` pattern, `TestProviderAdapter`, `DevelopmentCredentialProvider` |
| `tests/intelligence/test_capability_bridge_k8s.py` | 16 unit tests: bridge, read-only guarantee, catalog all-READ, resourceVersion preservation, profiles A1, no-direct-provider (AST imports + fitness). | — |
| `scripts/phase91_kubernetes_read_harness.py` | Real-Postgres harness: commission K8s capability → governed read (scripted) → Observation(resourceVersion) → Fact → WorldQuery + authorization/tenant/read-only/crash/replay/secret-firewall. | `phase62 _start_and_resolve/_drive`, `phase72 _store`, ObservationIngestion/FactDerivation/WorldQuery |

## Changed files (additive)

| File | Change |
|---|---|
| `backend/contracts/intelligence/__init__.py` | Export `CapabilityProfile`, `VerificationRequirement`. |

## The one action path (unchanged, reused)

```
intelligence/harness  →  capability (kubernetes_read_catalog)
                      →  authorization (existing chain)
                      →  lease (ExecutionLease)
                      →  governed execution (ExecutionService + scheduler.tick)
                      →  gateway (SecureCapabilityInvocationGateway)
                      →  provider (scripted TestProviderAdapter; real HTTPS adapter DEFERRED)
                      →  Observation (Phase 7.2 ObservationIngestion → cw_observation)
                      →  World (Fact derivation → WorldQuery, provider-neutral)
```

The governed K8s adapter performs provider I/O **only** when invoked by the governed execution transport. No `World → Kubernetes`, `Intelligence → Kubernetes`, `Harness → Kubernetes`, `registry → socket`, `model → Kubernetes`, or connector-owned HTTP transport exists (structurally fenced).

## The bridge, concretely

```
ProviderOperationSpec (governed: method, path, side_effect_class, evidence)
        +
CapabilityProfile (risk, autonomy_ceiling, verification_requirement, resource_scope)
        ↓ .to_capability()
Capability (Phase-8)  +  RiskClassification  →  AutonomyPolicy.evaluate(...)  (8.8)
```

A Kubernetes read profile: `side_effect_class=READ`, `RiskLevel.LOW`, `autonomy_ceiling=A1`, `verification=NONE`, `reversible=True` — so the `AutonomyPolicy` caps any Kubernetes read at observe/investigate; it is never an autonomous action.

## resourceVersion data contract (for future WATCH)

- The catalog keeps `resourceVersion` in every LIST/GET `response_evidence_fields` (and `response_required_fields`).
- The adapter normalizes `metadata.resourceVersion` → top-level `resourceVersion` (the governed `evidence()` keeps only top-level scalars, ADR-042).
- The harness proves a governed read's `resourceVersion` (e.g. `"100244"`) survives into the durable Observation and across a crash — the LIST→WATCH continuity substrate. **WATCH itself is NOT implemented.**

## Honest limitation (labeled)

The execution aggregate's run `detail` does not currently surface `provider_evidence` to `runtime.executions.get(...)` (phase72 hit the same and used a fallback). The harness therefore reconstructs the governed evidence deterministically as `ProviderOperationSpec.evidence(response)` — the exact bounded facts the pipeline extracts — from the real scripted provider response. The governed read itself (authorize → gateway → provider → succeeded, one provider call) is real; only the evidence *read-back surface* is reconstructed. Surfacing `provider_evidence` on the aggregate is a small follow-on for 9.2.
