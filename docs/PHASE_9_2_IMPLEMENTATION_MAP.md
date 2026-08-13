# PHASE 9.2 — Implementation Map

What was added/changed, and where it plugs in. **No second gateway, executor, scheduler, credential system, transport, or World ingestion path was created.** The real adapter is a composition of parts that already existed.

## Changed files (all additive)

| File | Change | Why |
|---|---|---|
| `backend/contexts/execution/infrastructure/adapters/connector.py` | New narrow port `ProviderBodyNormalizer` (mirrors the translator port) + optional `normalizer=` on `ConnectorAdapter`, applied in `_normalise` only after the translator classifies success; a normalizer failure is MALFORMED_RESPONSE (ambiguous), never an invention. | K8s nests its continuity token (`metadata.resourceVersion`); the governed evidence extractor reads top-level scalars by design. Provider dialect stays in the provider's module — the generic adapter stays generic. |
| `backend/contexts/execution/infrastructure/adapters/connectors/kubernetes.py` | + `KUBERNETES_PROVIDER` ref, `KUBERNETES_REAL_READ_OPERATIONS` (= `("kubernetes.pods.list",)`), `kubernetes_real_read_catalog()` (1-op subset, same spec digests), `KubernetesReadNormalizer` (the exact lift 9.1's docstring promised: `metadata.resourceVersion` → top-level, opaque, never fabricated; list counts; pod/deployment identity+status scalars), `KubernetesResponseTranslator` (bounded K8s `Status.message`), `build_kubernetes_channel` (HTTPS-only, no default URL), static headers on catalog specs. | The provider's whole dialect in the provider's one module — grafana.py's shape exactly. |
| `backend/api/capability_execution_composition.py` | + `build_kubernetes_connector` (mirrors `build_grafana_connector`; `ConnectorAdapter` + real catalog + channel + translator + normalizer, `IsolationTier.CONTAINED` with the stated ADR-059 gap); `build_adapter` gains a pass-through `normalizer=` kwarg (connector seam only). | The `(entry, adapter, catalog)` builder contract every provider uses. |
| `backend/api/kubernetes_provider_factory.py` | + `kubernetes_real_extension` — gated on `CORTEX_KUBERNETES_URL` + `CORTEX_KUBERNETES_TOKEN` (composition-root only; the connector never reads env), contributes a connector **builder** (constructed later with the composition's own broker/policy) + `DevelopmentCredentialProvider` (refuses production). **Raises if the scripted extension is also enabled** — one provider id, one path, never a fallback (Part U). | Same seam and trust shape as `grafana_extension`. |
| `backend/api/application_runtime.py` | `ProductionConnectivityConfig(ca_bundle_path=os.getenv("CORTEX_TLS_CA_BUNDLE") or None)` | The one TLS gap: `TlsPolicy.ca_bundle_path` existed and is enforced (`verify=<path>`, no `verify=False` anywhere) but had no deployment wire. A CA path is transport policy, not a credential. |
| `backend/contexts/execution/application/worker_runtime.py` | `to_execution_result` lifts exactly one key — `provider_evidence` (bounded, secret-free declared scalars) — onto the published `ExecutionResult.detail`. | Closes 9.1's honest limitation: evidence is now READ from the aggregate, not reconstructed. |

## New files

| File | What it is |
|---|---|
| `tests/intelligence/test_kubernetes_real_adapter.py` | 20 unit tests: exact/opaque resourceVersion lift, never-fabricate (+ the raw envelope failing the shape check without the normalizer — the lift is load-bearing), counts + CrashLoopBackOff signal, real-`ConnectorAdapter` normalization seam (success/missing-rv/ununderstood/401/403/404/undeclared-2xx), one-op exposure with unchanged spec digests, plaintext refusal, factory gating + dual-path refusal, provider_evidence surfacing (one key, absent stays absent, non-mapping not lifted). |
| `scripts/phase92_kubernetes_real_harness.py` | The real-cluster + real-Postgres harness (below). |

## The one action path, now with a real provider at the end

```
intelligence/harness → capability (kubernetes_real_read_catalog: pods.list ONLY)
                     → authorization (existing chain; wrong tenant/digest/ref refused, no dial)
                     → lease → governed execution (ExecutionService + scheduler.tick)
                     → gateway (SecureCapabilityInvocationGateway: credential minted
                       per action digest by the broker)
                     → ConnectorAdapter (validates input against the declared spec)
                     → ProviderChannel → TransportBroker (approve/resolve/judge/pin)
                     → HttpxTransportAdapter (the ONE place the credential is read;
                       verify=cluster CA; no verify=False exists)
                     → REAL Kubernetes API server (disposable k3d, RBAC-scoped SA)
                     → KubernetesResponseTranslator (cluster's own bounded message on failure)
                     → KubernetesReadNormalizer (metadata.resourceVersion → top-level, exact)
                     → spec.response_problems / spec.evidence (declared scalars only)
                     → provider_evidence on the aggregate (the one-key lift)
                     → Phase 7.2 ObservationIngestion → cw_observation (resourceVersion intact)
                     → Fact derivation → WorldQuery (provider-neutral; contacts no provider)
```

## Test environment (Part D, disposable)

k3d `cortex-p92` — k3s **v1.35.5** (Kubernetes 1.35), one server node, no LB. Namespace `cortex-p92`; ServiceAccount `cortex-reader`; Role `pod-reader` (get/list pods, that namespace only — `kubectl auth can-i` proves delete=no, other-namespace=no); deployment `nginx-test` (2 replicas) as the read subject. Endpoint `https://127.0.0.1:55290` (literal loopback; in the cert SANs), cluster CA extracted from kubeconfig → `CORTEX_TLS_CA_BUNDLE`. Token: `kubectl create token cortex-reader -n cortex-p92 --duration=8h`. Cleanup: `k3d cluster delete cortex-p92`.

## Operational truths the harness surfaced (recorded, not hidden)

1. **A gateway-refused node returns to READY by design** (dispatcher: "refused before anything ran, so the node goes back") — so a permanently-invalid payload (e.g. path-traversal namespace) cycles until cancelled. The harness proves no-dial + never-succeeds, then cancels. A production janitor for permanently-refused nodes is future work.
2. **The scheduler role is a durable 30s leadership lease.** A process that dies holding it (the crash children — deliberately) leaves every later scheduler a follower until expiry. The harness sizes drive budgets past one TTL and releases the role (`scheduler.stop()`) in cleanly-exiting children.

## Harness legs (scripts/phase92_kubernetes_real_harness.py)

Real read (1 dial, evidence from the aggregate, podCount corroborated out-of-band by kubectl) → Observation (rv intact) → Fact → WorldQuery (0 further dials) · authorization negatives (wrong tenant / drifted digest / missing capability / unknown+write op / malformed ref / no-authority / invalid scope — all with **zero dials**) · real provider failures (RBAC 403 with the cluster's own message; 401 bad token; TLS unverifiable; server unavailable — all FAILED/refused, **zero observations**) · replay inert · crash at 4 points (`os._exit(9)`: after start / after real read / after observation / after fact) with recovery from fresh handles (B: evidence durable, observation completed **without re-contacting the provider**) · tenant isolation on the durable path · secret firewall (the SA token string absent from **every row of every durable table**) · latency p50/p95 over 12 real reads.
