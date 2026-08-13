# PHASE 9.2 — Verification Report

**Real Governed Kubernetes READ Adapter.** Every claim is labeled `[FACT]` (declared
in code, cite file), `[VERIFIED]` (a test/harness run proved it), `[NOT VERIFIED]`,
`[BLOCKED]`, `[DEFERRED]`, or `[INFERENCE]`.

## Honesty header

- `[VERIFIED]` **A real Kubernetes API server was contacted** — a disposable local
  k3d cluster (k3s v1.35.5), NOT a mock, NOT a script, and NOT a production cluster.
  Every contact went through the one governed path; provider dials were counted by a
  pure pass-through wrapper on the channel's `send`.
- `[FACT]` **Phase 5.5 remains blocked and untouched.** No GitHub/production
  credential was inspected, manufactured, or modified. The Kubernetes credential is
  a short-lived (8h), RBAC-scoped ServiceAccount token for the disposable cluster,
  entering once at the composition root (`CORTEX_KUBERNETES_TOKEN`, the exact
  `CORTEX_GRAFANA_TOKEN` trust shape) into `DevelopmentCredentialProvider`, which
  refuses production four ways. The connector never reads the environment.
- `[FACT]` **WATCH is NOT implemented** (Part V): no watch(), no 410 recovery, no
  bookmarks, no streaming, no reconnect. Only the LIST resourceVersion data
  contract a future WATCH needs — now proven with a real cluster's value.

## REAL KUBERNETES EVIDENCE

| Item | Value |
|---|---|
| Cluster type | k3d (k3s in docker), disposable, created by the harness runner |
| Cluster | `k3d-cortex-p92`, single server node, no LB |
| Kubernetes version | k3s **v1.35.5** (Kubernetes 1.35), server verified via kubectl |
| API endpoint | `https://127.0.0.1:55290` (literal loopback; in the cert SANs; cluster CA as `CORTEX_TLS_CA_BUNDLE`) |
| Auth mechanism | ServiceAccount bearer token, `kubectl create token cortex-reader -n cortex-p92 --duration=8h` |
| RBAC | Role `pod-reader`: get/list pods, namespace `cortex-p92` ONLY (`kubectl auth can-i`: list=yes, delete=no, other-namespace=no) |
| TLS mode | HTTPS, verified against the cluster CA (`verify=<path>`; `verify=False` does not exist in the transport) |
| Test resources | deployment `nginx-test`, 2 replicas, namespace `cortex-p92` |
| Capability | `platform.kubernetes.pods.list` (the ONLY real-exposed operation) |
| Provider call count (main read) | **1** (counted at the channel) |
| resourceVersion | **`4954`** (opaque string, exact as returned; changes run to run — a live cluster) |
| Observation | `wobs_01KZX6VRDE822S84W9G7B4318H` (execution `01KZX6VR41YTT6F0CK7YT8QFJR`) |
| Fact | 1 fact derived; WorldQuery answers podCount + resourceVersion |
| Tenant | `dev` (cross-tenant reads fail closed) |
| Corroboration | governed `podCount=2` == out-of-band `kubectl get pods` count=2 |
| Audit | audit chain verifies at end of run |
| Cleanup | `k3d cluster delete cortex-p92` |

## Part-by-part

### A — Discovery (source, not reports)
- `[FACT]` Two 9.1 claims were prose, not code, and are now real code: the
  `metadata.resourceVersion` normalization (nothing performed the lift anywhere; the
  scripted responder pre-baked flat bodies) and evidence read-back (the projection
  dropped `provider_evidence`). Both were found by re-reading source before coding.

### B — Real transport through the existing architecture
- `[FACT]` The adapter is the generic `ConnectorAdapter` + `ProviderChannel` +
  `TransportBroker` + `HttpxTransportAdapter` — the ONE HTTP client of the governed
  plane (ADR-041). No Kubernetes SDK (BND-PROVIDER-SDK), no httpx outside
  `backend.platform.transport` (BND-DIRECT-HTTP), no second transport/retry loop.
- `[FACT]` The model chooses nothing: operation from the binding, path template and
  method (GET) from the declared catalog, destination from the channel's configured
  endpoint (`CORTEX_KUBERNETES_URL`, deployment config, deliberately **no default**),
  credential minted by the broker. `build_kubernetes_channel` refuses plaintext.
- `[VERIFIED]` A governed `kubernetes.pods.list` SUCCEEDED against the real API
  server with exactly **one** dial; 12 further reads → exactly 12 further dials.

### C — Credential boundary
- `[FACT]` No `os.getenv("KUBECONFIG")`/`KUBE_TOKEN` anywhere; the connector module
  imports no `os`. Only the composition-root factory reads
  `CORTEX_KUBERNETES_URL/TOKEN/TENANT` (the Grafana pattern, `grafana_provider_factory.py`).
- `[VERIFIED]` The factory refuses the scripted/real dual path (RuntimeError when
  both are configured) — unit `test_factory_refuses_the_dual_path`.
- `[VERIFIED]` The httpx adapter is the only credential read; the token appears in
  **no durable row of any table** (full-database scan, Part R below).

### D — Disposable cluster
- `[VERIFIED]` Environment as in the evidence table. No production cluster, no
  developer production credentials, full cleanup command documented.

### E — One real capability
- `[FACT]` `kubernetes_real_read_catalog()` exposes exactly `kubernetes.pods.list`
  — same declared spec (same digest) as the 9.1 contract
  (`test_real_specs_are_the_declared_contract`). The other five operations remain
  declared but NOT real-exposed.
- `[VERIFIED]` Runtime catalog contains exactly one operation (harness check 1).

### F — Real API request, evidence recorded
- `[VERIFIED]` provider/operation/endpoint/method/namespace/correlation/status/
  resourceVersion/observed_at all present across the aggregate detail, the
  Observation, and provenance. No bearer token, no Authorization header, no key
  material stored (Part R scan).
- `[VERIFIED]` Out-of-band corroboration: governed `podCount` == kubectl's count.

### G — resourceVersion
- `[FACT]` `KubernetesReadNormalizer` lifts `metadata.resourceVersion` → top-level
  **exactly as returned**: opaque string, never coerced to int, never hashed,
  never substituted, never fabricated (`kubernetes.py`).
- `[VERIFIED]` Opaque shapes survive byte-for-byte (`"00123"`, `"9a8b7c"`); the raw
  envelope FAILS the shape check without the normalizer (the lift is load-bearing,
  nothing can skip it); a real cluster's value survived into `cw_observation` and
  across a crash.

### H — Provider evidence on the aggregate
- `[FACT]` `WorkerRuntime.to_execution_result` lifts exactly one key —
  `provider_evidence` — onto the published result (`worker_runtime.py`). Failure-path
  detail is untouched (failures carry `FailureRecord`).
- `[VERIFIED]` The harness reads evidence **from the aggregate**
  (`executions.get → run_for → attempts[-1].result.detail`) — the 9.1 reconstruction
  is gone. Unit: one key lifted, absent stays absent, non-mapping not lifted.

### I/J — Observation and WorldQuery
- `[VERIFIED]` Real read → Phase 7.2 `ObservationIngestion` → `cw_observation` with
  tenant/provider/subject/observed_at/recorded_at/provenance/execution_ref/identity
  digest; resourceVersion intact. The adapter never inserts into cw_observation.
- `[VERIFIED]` Fact derived; provider-neutral WorldQuery answers WHAT (podCount),
  WHEN (observed/recorded), WHICH resourceVersion, WHOSE tenant — with **zero**
  provider dials during ingestion/derivation/query (the hard invariant).

### K — Authorization negatives (all with zero dials)
- `[VERIFIED]` wrong tenant refused · drifted digest refused · missing capability
  (a write) not registered — fail closed · unknown/write op refused by the catalog ·
  malformed capability ref does not authorize · real adapter with NO authority
  refuses · invalid resource scope (path-traversal namespace) never succeeds and
  never dials — refused at the gateway's input validation.
- `[VERIFIED]` (existing suite) expired binding refused, never extended —
  `tests/contexts/execution/test_invocation_gateway_matrix.py::test_an_expired_binding_is_refused_never_extended`;
  `_authority_stale` (expiry + credential-for-this-digest) runs inside every real
  adapter invocation (`adapters/base.py`).

### L — Kubernetes authorization ≠ CortexPrime authorization
- `[VERIFIED]` CortexPrime authorized a read of namespace `default`; the cluster's
  RBAC refused it: real **403**, classified `AUTHORIZATION_FAILURE`, carrying the
  cluster's own message ("pods is forbidden: User \"system:serviceaccount:...\""),
  execution FAILED, **no observation, no fact, no success, no UNKNOWN-as-truth**.

### M/N — Failure matrix
- `[VERIFIED]` Real 401 (bogus token) → FAILED (`Unauthorized`), no observation.
- `[VERIFIED]` Real TLS verification failure (a valid CA bundle that did not sign
  the server cert) → refused/unknown, no observation, never success. Verification
  is never disabled.
- `[VERIFIED]` API server unavailable (closed port) → FAILED, no observation.
- `[VERIFIED]` Missing resourceVersion → MALFORMED_RESPONSE (ambiguous), no
  fabrication (unit, Part N choice: **reject the observation**). Malformed envelope
  → refused. Undeclared 2xx → not a success. 404 classification (unit).
- `[NOT VERIFIED]` A real connect-*timeout* leg (unroutable address) was not
  exercised — the closed-port (fast refusal) leg was; the timeout path is the same
  transport classification. `[INFERENCE]` No fabricated observation is possible for
  it: ingestion is a separate explicit act on success evidence only.

### O — Replay
- `[VERIFIED]` Replay of the completed real read: **zero** new observations,
  **zero** provider dials (replay is a pure event-history reconstruction —
  `service.py: "Executes nothing"`). At-least-once remains the claim; exactly-once
  is not claimed.

### P — Crash / recovery (real os._exit(9), four points)
- `[VERIFIED]` A: died after start, before provider contact — no dial, no
  fabricated anything. B: died after the real read, before observation — the
  provider evidence (with the real resourceVersion) was durable on the aggregate; a
  fresh process completed the observation **without re-contacting the provider**.
  C: died after observation — reconstructs from a fresh handle, identity matches,
  cross-tenant fails closed. D: died after fact — fact durable, re-derivation inert
  (deterministic dedupe).

### Q — Tenant isolation
- `[VERIFIED]` Cross-tenant `get_observation` → None; cross-tenant WorldQuery →
  nothing; wrong-tenant authorization refused with no dial; exercised on the
  durable path (fresh repository handles), not only in-process filters.

### R — Secret firewall
- `[VERIFIED]` The SA token string is absent from **every row of every table** in
  the durable database (full scan). The Observation contains no `Bearer`, no token.
  ADR-041 structure: bodies/headers are excluded before `ProviderExchange` exists;
  the credential is read exactly once, in the httpx adapter.

### S — Fitness rules
- `[FACT]` **No new rule.** BND-DIRECT-HTTP (httpx only in `backend.platform.transport`),
  BND-PROVIDER-SDK (no kubernetes SDK anywhere in backend), BND-AMBIENT-CREDENTIALS
  already fence the real adapter; `CORTEX_KUBERNETES_TOKEN` follows the same
  composition-root pattern the rule deliberately allows for `CORTEX_GRAFANA_TOKEN`.
  The AST import test (`test_module_imports_no_sdk_httpx_or_v1_connector`, 9.1)
  still passes over the changed module.
- `[VERIFIED]` Architecture gate: **155 passed** over the full module graph.

### T — Performance (12 real governed reads, p50/p95 ms)
- `[VERIFIED]` authorize ≈ 41/44 · execute (start→terminal, includes the real HTTPS
  roundtrip + scheduler ticks at 100ms) ≈ 278/518 · evidence read ≈ 5/7 ·
  ingestion ≈ 9/11 · WorldQuery ≈ 6/7. No index was added (none indicated by these
  numbers at this scale).

### U — V1 strangler
- `[VERIFIED]` `backend.connectors` (V1) is never imported in the real-adapter
  process (checked against `sys.modules` after composition + reads). No dual
  execution, no fallback: the real and scripted factories refuse to coexist.

## Operational truths surfaced (recorded, not hidden)

- `[FACT]` A gateway-refused node returns to READY by design ("refused before
  anything ran, so the node goes back" — `dispatcher.py`), so a permanently-invalid
  payload cycles until cancelled; the harness cancels it. A janitor for
  permanently-refused nodes is future work (noted in ADR-082).
- `[FACT]` The scheduler role is a durable **30s leadership lease**
  (`SchedulerLeadership`); a process that dies holding it leaves later schedulers
  followers until expiry. Harness children release it (`scheduler.stop()`) or
  outwait one TTL. This is correct one-coordinator behavior, not a bug.

## Test & gate evidence (commands run)

- `[VERIFIED]` `pytest tests/intelligence/test_kubernetes_real_adapter.py` → **20 passed**.
- `[VERIFIED]` `pytest tests/intelligence/test_capability_bridge_k8s.py` → **16 passed** (9.1 contract intact).
- `[VERIFIED]` `python -m scripts.phase92_kubernetes_real_harness` (fresh `cortex_p92`,
  real Postgres, real k3d cluster) → **VERIFIED, 49/49 checks, 0 fail**.
- `[VERIFIED]` Architecture gate `pytest tests/architecture` → **155 passed**.
- `[VERIFIED]` Regression `pytest tests/intelligence tests/world tests/contracts
  tests/contexts/execution` → **915 passed**.
- `[FACT]` One pre-existing test adjusted (`test_the_worker_port_is_a_protocol_...`):
  its text marker `"kubernetes."` false-positived on the 9.1 catalog's declared
  operation *names* (`kubernetes.pods.list`) — latent since 9.1, surfaced by 9.2's
  wider regression scope. The marker is now import-shaped; the underlying invariant
  (no SDK in the execution context) is enforced by BND-PROVIDER-SDK's AST pass
  regardless, which passes.

## Definition of done — the 28 points

1–3 real server contacted, only via governed execution, one real READ `[VERIFIED]` ·
4 capability declared `[FACT]` · 5 model cannot modify provider/path/method `[FACT]`
(catalog-only construction) · 6–7 no connector credentials, no production
credentials `[FACT]` · 8–9 resourceVersion exact, missing→fail-closed `[VERIFIED]` ·
10 evidence durable via existing structures `[VERIFIED]` · 11 Phase-7 ingestion
`[VERIFIED]` · 12 WorldQuery provider-neutral `[VERIFIED]` · 13 provider failure ≠
truth `[VERIFIED]` · 14 authorization precedes contact `[VERIFIED]` · 15 K8s auth
separate `[VERIFIED]` · 16 tenant isolation `[VERIFIED]` · 17 secret firewall
`[VERIFIED]` · 18 replay `[VERIFIED]` · 19 crash/recovery `[VERIFIED]` · 20 V1
fallback impossible `[VERIFIED]` · 21 architecture gate `[VERIFIED]` · 22 real
Postgres `[VERIFIED]` · 23 real Kubernetes `[VERIFIED]` · 24 WATCH not implemented
`[FACT]` · 25 no write capability `[FACT]` · 26 no second authority `[FACT]` ·
27 Phase 5.5 untouched `[FACT]` · 28 L1–L16 intact `[FACT]`.
