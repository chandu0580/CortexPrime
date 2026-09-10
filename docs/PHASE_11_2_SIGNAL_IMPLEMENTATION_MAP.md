# PHASE 11.2 — Signal Implementation Map: the real production signal fabric

- **Date:** 2026-09-10 · **Parent HEAD:** `e662688` (Phase 11.1) · **Branch:** `phase-1-foundation`
- **ADR:** `docs/adr/ADR-122-phase-11-2-signal-fabric.md` · **Verification:** `docs/PHASE_11_2_SIGNAL_VERIFICATION_REPORT.md` · **Harness:** `scripts/phase112_signal_fabric_harness.py`

## 1. Repository research (what the signal path actually was at `e662688`)

| Component | State found | Consequence for this phase |
|---|---|---|
| `backend/api/kubernetes_watch_driver.py` | complete, crash-safe, position-checkpointing (positions are observations), 410 recovery bounded, leadership via `SqlLeadershipStore` role `WORLD_WATCH`, **no runner** | supervise it; do not rewrite it |
| Kubernetes connector watch operation | declared record fields `type, kind, namespace, name, uid, resourceVersion`; cap 64 events/window (`WATCH_MAX_EVENTS`); a window over the cap is **refused, not trimmed**; `pod.get` lifts phase/restartCount/waitingReason/lastExitCode/lastTerminationReason | enrich through `pod.get`; handle the over-cap window as a stall |
| World Plane (`cw_observation` 0015, `cw_fact` 0016) | append-only, tenant-scoped, identity digest over (tenant, source, subject, predicate, observed_at, value) with a unique constraint; facts derive from observations; secret-bearing values refused; `retrieved_at < observed_at` refused | the canonical durable event; nothing new to store |
| `GovernedReadObserver` / `GovernedCapabilityReader` | the 9.2/9.3 composition: governed read → `ReadObservation` → ingestion | reused verbatim |
| Leadership store | closed role list incl. `WORLD_WATCH`; heartbeat is a fenced conditional UPDATE | the only fencing |
| Runtime roles | `SCHEDULER`, `AUDIT_WRITER`, `OUTBOX_PUBLISHER` are per-store singletons taken by `runtime.start()`; the worker directory is process-local; the dispatcher does not pick up executions another process started | the signal loop must run INSIDE the dispatching process beside the API (embedded), or alone (standalone) |
| `build_governed_runtime` | composes persistence, connectivity, capabilities, dispatcher, scheduler, publisher; `start()` runs the scheduler and outbox pump | the worker composes but never starts it |
| Product engine (`compose_engine`) | separate process (ADR-094); `backend.main` never sets it, so `require_user` refused every tenant-bearing token there | tenant store fallback to the governed runtime's store (same table) |
| V1 event bus / enterprise hub / replay | in-memory ring, replay store; V1 alert correlator writes a JSON file | not used for governed signals; untouched |
| Alertmanager | **no integration anywhere**; `infra/prometheus/alertmanager.yml` is a Slack template; V1 polls Prometheus alerts into a JSON store | build the governed webhook ingress |
| OpenTelemetry | SDK/exporters installed; `infra/opentelemetry/otel-collector-config.yaml`; V1 `/otel/v1/traces` receiver (fenced in 11.1) | deferred for the governed plane (ADR-122 D-8) |
| Metrics | `backend/observability/prometheus_metrics.py` (`prometheus_client`, `/metrics`); governed plane has only a null recorder | signal counters added to the existing registry |
| Redis | rate-limit windows, revocation, V1 caches/replay | not on the signal path |
| Helm worker template | Celery-stale (G-19) | not touched; the worker is `python -m backend.signal.worker` |
| Incident model | `cw_investigation` opened by `InvestigationService.create(tenant, incident_ref, …)` (harness-only callers); V1 correlator is a file | candidates carry an `incident_ref` for Prompt 3; no incident is created here |

## 2. Real-world research applied

- **Kubernetes watch:** bounded windows with `timeoutSeconds`, `allowWatchBookmarks`, opaque `resourceVersion` copied exactly, `410 Gone` → relist, events-before-position ordering, RBAC list/watch/get on pods in one namespace, single leader per stream, graceful release. Implemented in the driver (ADR-083) and the supervisor (this phase).
- **Alertmanager:** webhook v4 payload (`groupKey`, `status`, `alerts[]` with `fingerprint`, `startsAt`, `endsAt`, `generatorURL`), retries on non-2xx, `repeat_interval` re-notification, `send_resolved`, `http_config.authorization` bearer. Consumed; grouping and dedupe not rebuilt.
- **OpenTelemetry:** collector patterns evaluated (DaemonSet/Deployment collectors, k8s attributes, kubelet, filelog, cluster metrics, k8s events). Deferred; the V1 receiver remains fenced.

## 3. Architecture, as implemented

```
KUBERNETES API ──governed LIST/WATCH (pods, ns)──▶ KubernetesWatchDriver ──▶ GovernedReadObserver ──▶ ObservationIngestion ──▶ cw_observation
        ▲                                              │ enricher: governed pod.get                     (identity digest, tenant row)
        │ cortex-reader SA (list/watch/get only)       ▼
   SUPERVISED WORKER: embedded in backend.main (start_embedded) or standalone (python -m backend.signal.worker)
        │ WORLD_WATCH lease (SqlLeadershipStore); standalone also takes AUDIT_WRITER lazily ── FactDerivation ──▶ cw_fact
        │ metrics :9102 (existing registry)            ── project_candidates ──▶ DetectionHandoff (Prompt 3)
        │ status file (optional)                       ── no scheduler, no dispatcher, no restart credential

PROMETHEUS ──rule──▶ ALERTMANAGER ──webhook + bearer token──▶ backend.main
                                                         RateLimit ▶ AuthPerimeter ▶ TenantContext ▶ Guardrails
                                                         ▶ POST /api/signals/alertmanager (require_governed_ingest_principal: token tenant, body bound)
                                                         ▶ AlertmanagerPayload (v4 schema) ▶ normalise ▶ ObservationIngestion ▶ cw_observation
                                                         ▶ audit ingress.accepted/rejected (no payload) ▶ 503 on persistence failure

PRODUCT API (separate process) ── GET /api/v1/signals/recent, /api/v1/signals/candidates (product_context tenant) ── read-only
```

## 4. Canonical event contract (see `backend/signal/contract.py`)

| Field | Kubernetes pod signal | Alertmanager alert signal |
|---|---|---|
| global id | `Observation.record_id` (ULID) + identity digest | same |
| source / instance | `connector` / `connector:kubernetes` | `probe` / `webhook:alertmanager` |
| subject | `kubernetes:pod:<ns>/<name>` | `alertmanager:alert:<fingerprint>` |
| predicate | `state` (same as 9.2 read and 9.3 watch) | `alert` |
| event type | `eventType` ADDED/MODIFIED/DELETED | `status` firing/resolved |
| event time / observed time | window moment (`observed_at`) | `startsAt` (clamped to receipt on skew) |
| tenant | worker config (token-equivalent: the deployment's declared tenant) | the token's tenant |
| integration | `enrichment: pod.get` + `enrichmentExecution` | `groupKey`, `receiver` |
| resource identity | cluster, namespace, kind, name, uid | fingerprint, labels |
| resource version | `resourceVersion` (opaque) | `startsAt`/`endsAt` |
| correlation | namespace, workload (inferred), phase, waitingReason, restartCount, lastTerminationReason, lastExitCode | alertname, severity, service/job, namespace, pod, instance, generatorURL |
| payload digest / provenance | identity digest; produced_by `signal:kubernetes-worker/1`; execution_ref of the governed read | identity digest; produced_by `signal:alertmanager-ingress/1`; trace_ref = request id |
| trust | `untrusted_external` | `untrusted_external` |
| delivery | at-least-once | at-least-once; effectively-once per lifecycle state |
| order | resourceVersion within a stream; `recorded_at` + ULID | `startsAt`/`endsAt`; `recorded_at` + ULID |

## 5. Files

### New
| File | Purpose |
|---|---|
| `backend/signal/__init__.py`, `contract.py`, `alertmanager.py`, `correlation.py`, `worker.py` | the signal fabric: contract view, Alertmanager normalisation, correlation + candidates, supervised worker |
| `backend/api/signal_ingress_routes.py` | `POST /api/signals/alertmanager` behind the 11.1 boundary |
| `backend/api/product/signal_routes.py` | `GET /api/v1/signals/recent`, `GET /api/v1/signals/candidates` |
| `scripts/phase112_signal_fabric_harness.py` | real-infrastructure end-to-end, failure, attack, storm and integrity harness |
| `tests/signal/*` (5 modules, 52 tests) | permanent tests: contract + correlation, worker supervision (roles, backoff, stall, status), ingress routes, driver enrichment, tenant-store fallback |
| `docs/adr/ADR-122-…`, this map, the verification report, `docs/phase112_signal_report.json` | record |

### Changed (additive, surgical)
| File | Change |
|---|---|
| `backend/api/kubernetes_watch_driver.py` | optional `enricher` hook merged into mutation legs; `relist(context, reason)` with `origin=list_after_stall` + `stallReason`; `_establish` carries the stall reason |
| `backend/world/infrastructure/sql_observation.py` | `list_recent(...)`, `latest_by_subject_prefix(...)` (DISTINCT ON) — existing indexes |
| `backend/safety/ingress_boundary.py` | `require_governed_ingest_principal` (tenant required, fence not applied) |
| `backend/safety/auth_perimeter.py` | `/api/signals` fence-exempt (governed, tenant-scoped ledger) |
| `backend/safety/rate_limiter.py` | `/signals/` classified into the `ingest` bucket |
| `backend/auth/dependencies.py` | `_tenant_store()` — product engine's tenants, else the governed runtime's store (same `cp_tenant`) |
| `backend/api/router_registry.py` | registers the signal ingress unconditionally |
| `backend/api/product/app.py` | includes the signal read routes |
| `backend/main.py` | lifespan starts `start_embedded(governed_runtime)` after the runtime, stops it before the runtime |
| `backend/observability/prometheus_metrics.py` | signal counters/gauges/histograms |

### Not changed
`backend/contexts/*`, `backend/world/application/*`, `backend/assurance`, `backend/intelligence`, `backend/platform/*`, every migration, `requirements*.txt`, Helm, compose.

## 6. Environment variables (worker)

| Variable | Default | Meaning |
|---|---|---|
| `CORTEX_SIGNAL_TENANT_ID` | required | the tenant whose stream this worker holds |
| `CORTEX_SIGNAL_NAMESPACE` | required | the namespace watched |
| `CORTEX_SIGNAL_CLUSTER_REF` | host of `CORTEX_KUBERNETES_URL` | cluster label on every observation |
| `CORTEX_SIGNAL_WINDOW_SECONDS` / `_LEASE_SECONDS` | 20 / 60 | watch window and stream lease (lease must outlive a window) |
| `CORTEX_SIGNAL_METRICS_PORT` | 9102 | Prometheus endpoint (0 disables) |
| `CORTEX_SIGNAL_MAX_STALL_FAILURES` | 5 | consecutive failures at one position before an explicit relist |
| `CORTEX_SIGNAL_BACKOFF_MIN/MAX_SECONDS` | 1 / 60 | failure backoff |
| `CORTEX_SIGNAL_FOLLOWER_SLEEP_SECONDS` | 5 | follower poll |
| `CORTEX_SIGNAL_STATUS_FILE` | unset | optional JSON status (last cycle, candidates) |
| plus `CORTEX_DURABLE_URL`, `CORTEX_KUBERNETES_URL/TOKEN`, `CORTEX_TLS_CA_BUNDLE`, `CORTEX_CONNECTOR_FACTORIES` | as for the API | the reader credential only |
| `CORTEX_KUBERNETES_TENANT` | as for the API | the tenant the provider credential is bound to; the worker refuses to start if it differs from `CORTEX_SIGNAL_TENANT_ID` |

**Embedded mode** (`backend.main`): set `CORTEX_SIGNAL_TENANT_ID` + `CORTEX_SIGNAL_NAMESPACE` (and the variables above) on the API process; the lifespan starts the loop after the governed runtime and stops it before. Metrics are on the API's `/metrics`. Unset = the pre-11.2 behaviour (nothing observed). **Standalone mode** must not run beside an API that holds the runtime roles for the same store: it becomes an honest hot-standby follower (ADR-122 D-4).

**Harness modes:** `CORTEX_P112_API_ONLY=1` reruns commissioning + worker boot + the API/Alertmanager sections only (iteration; report to scratch); the full run is the phase record (`docs/phase112_signal_report.json`). `CORTEX_P112_SCRATCH` keeps logs, status files, generated Prometheus/Alertmanager configs and the API thread dumps.

Alertmanager: `webhook_configs[].url = https://<cortexprime>/api/signals/alertmanager`, `http_config.authorization.credentials = <access token minted for the tenant's signal principal>`, `send_resolved: true`.

## 7. Operational limits (measured in the verification report)

Window cap 64 mutations per window (over-cap → refused → stall → relist with counted loss); one governed read per mutation for enrichment; Alertmanager payload ≤ 200 alerts, labels ≤ 64, annotations ≤ 32, text ≤ 2048 chars, body ≤ 1 MiB; rate-limit bucket `ingest` 300/min per identity.
