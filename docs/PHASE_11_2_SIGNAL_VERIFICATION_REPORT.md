# PHASE 11.2 — Verification Report: the real production signal fabric

- **Date:** 2026-09-10 · **Parent HEAD:** `e662688` (Phase 11.1) · **Branch:** `phase-1-foundation`
- **ADR:** `docs/adr/ADR-122-phase-11-2-signal-fabric.md` · **Map:** `docs/PHASE_11_2_SIGNAL_IMPLEMENTATION_MAP.md` · **Evidence:** `docs/phase112_signal_report.json`
- **Labels:** `[VERIFIED]` executed in this session with the output in hand · `[MEASURED]` observed and recorded verbatim, not designed · `[DEFERRED]` proven elsewhere and cited · `[FINDING]` a pre-existing property surfaced by this phase, not changed here

## 1. Executive verdict

A **real** production failure now becomes a durable, tenant-scoped, identity-deduplicated, provenance-carrying observation, a World fact, and a projected incident candidate handed to detection — with no new event bus, queue, worker framework, table, migration or dependency. The evidence is a CrashLoopBackOff created on the live k3d cluster and observed through the governed watch, and a Prometheus rule firing on a real down target delivered by a real Alertmanager through the Phase 11.1 boundary. Delivery is at-least-once and says so; loss across a stall is counted, never silent. The worker holds a read-only ServiceAccount token, composes no dispatcher, and can execute nothing. Cluster generations were unchanged across every run: **zero provider writes**. The governed plane was not modified and its harness chain re-run.

Two shapes of one loop were needed, and the reason is a measured property of the governed runtime, not a preference: the scheduler and audit-writer roles are per-store singletons and a runtime dispatches only what its own process started, so the signal loop runs **embedded** in `backend.main` beside the API (production) and **standalone** when no API runtime holds the roles (§4, F-1).

## 2. Evidence table

| Claim | Label | Evidence |
|---|---|---|
| Real end-to-end signal (Kubernetes) | `[VERIFIED]` | harness §3: `kubectl apply` of a `busybox` deployment that exits 1 → the cluster itself reports `CrashLoopBackOff` (ground truth read with the reader SA) → the watch event, enriched through the governed `pod.get`, is a `cw_observation` row with cluster/namespace/kind/name/**uid**/resourceVersion/eventType, provenance `signal:kubernetes-worker/1` + governed `execution_ref` → `cw_fact` derived → candidate `kubernetes.pod.backoff` for workload `p112-crashy` with `authority: none` → handoff counted |
| Real end-to-end signal (Alertmanager) | `[VERIFIED]` | harness §9: real Prometheus + Alertmanager containers, rule `VictimServiceDown` on a real scrape target taken down → webhook with `http_config.authorization` bearer → `POST /api/signals/alertmanager` through RateLimit ▸ AuthPerimeter ▸ TenantContext ▸ Guardrails ▸ governed ingest principal → durable tenant-A observation keyed by fingerprint + startsAt; the repeat notification deduplicated; the resolution a new lifecycle observation; the candidate appears while firing and clears when resolved |
| Harness | `[VERIFIED]` | `scripts/phase112_signal_fabric_harness.py`: **63/63 checks (7 negative cases, max provider_writes 0)**, verdict **VERIFIED**, 682.2 s — `docs/phase112_signal_report.json` |
| Permanent tests (new) | `[VERIFIED]` | `tests/signal/` — contract + correlation, worker supervision (incl. roles, status/backoff), ingress routes, driver enrichment, tenant-store fallback: **52 passed** |
| Adjacent suites | `[VERIFIED]` | `tests/signal tests/intelligence/test_kubernetes_watch.py tests/world tests/test_auth_perimeter.py tests/test_ingress_boundary.py` → **313 passed** |
| Architecture gate | `[VERIFIED]` | `pytest tests/architecture -q` → **155 passed** (791 s), identical to the 10.31 / 11.1 baseline |
| Governance chain 10.7 / 10.8 / 10.9 / 10.10 / 10.11 / 10.13 / 10.14 | `[VERIFIED]` | **155/155 · 118/118 · 107/107 · 107/107 · 68/68 · 60/60 · 53/53**, all VERIFIED, identical to the 10.31 / 11.1 baseline (10.9 on solo re-run, first attempt 100/105 — §8) (§8) |
| Regression suite | `[VERIFIED]` | **71 failed / 6935 passed / 36 skipped / 58 xfailed / 24 errors** (1159 s) — `FAILED` names identical to the 11.1 list: **0 new, 0 gone**; passed +52 (the new tests) (§9) |
| Provider writes | `[VERIFIED]` | standing deployments' generations before/after the harness identical: `{"billing-api": 1, "contained-worker": 134, "payments-api": 133}` → `{"billing-api": 1, "contained-worker": 134, "p112-crashy": 1, "payments-api": 133}`; (the extra `p112-crashy: 1` is the harness's own test deployment, created and deleted by `kubectl`, generation 1); the worker's ServiceAccount answers `no` to `can-i patch deployments`; the worker and API environments carry no restart credential (checked from the process environment) |
| Database integrity | `[VERIFIED]` | only `cw_*`, `cp_*` and `audit_logs` changed on the signal path; no schema change, no migration; the V1 application's own boot/background writes (`connector_activity`) measured separately (§10) |
| Redis | `[VERIFIED]` | the whole API/Alertmanager run had **no Redis** (`REDIS_URL` pointed at a closed port); nothing on the signal path needed it |

## 3. What was attacked and what failed honestly

Sections of the harness, in order. `[MEASURED]` numbers are in §6.

- **§1 Commissioning is an operator act.** The worker refuses to start when the three read capabilities are not commissioned (`CapabilityNotFound`) and without a tenant. Commissioning registers/validates/enables/trusts `platform.kubernetes.pods.list|pods.watch|pod.get` through the capability registry and admits the connector worker; two real tenants (`cp_tenant`) with one real member each (`cp_tenant_membership`).
- **§2 Boot.** The worker's environment carries the READ token and no restart credential; it establishes a real position from a governed LIST (`origin=list`, the cluster's own `resourceVersion`), holds `WORLD_WATCH` through the SQL leadership store, exports through the existing Prometheus registry.
- **§3 A real failure.** See §2 table row 1.
- **§4 Product API.** Tenant A reads its candidate and recent signals (native identity, provenance, `trust: untrusted_external`) through the real product app with real tokens; tenant B sees zero; no token → 401; **a token whose tenant claim names a tenant the subject is not a member of → 403** (the durable membership row decides, not the claim).
- **§5 Graceful restart.** CTRL_BREAK stops the worker and releases the role; the restarted worker resumes from the durable position (no relist, no invented position); re-delivered events collide on identity — zero duplicate identities in the ledger.
- **§6 Leadership.** A second instance for the same tenant is a follower; after a hard kill the follower takes over once the lease lapses and resumes the stream with no duplicate or fabricated observation.
- **§7 Kubernetes API outage** (container paused): failed cycles with backoff, nothing fabricated, the stream resumes after unpause; retries and provider errors counted.
- **§8 PostgreSQL outage** (container stopped): the worker survives and resumes once the database returns; no duplicate identities.
- **§9a Event storm** over the window cap (60 replicas): the over-cap window is refused by the normalizer, the worker stalls at one position, and after `max_stall_failures` performs an **explicit relist** whose checkpoint names the stall (`origin=list_after_stall`, `stallReason`) and whose loss is counted (`cortex_signal_events_dropped_total`); the stream is healthy afterwards.
- **§9 Alertmanager.** See §2 table row 2. The `tenant_hint` label Alertmanager was configured to send is **data**; tenancy came from the token.
- **§10 Attacks on the ingress:** no token 401 · garbage token 401 · tenant-less token 403 · wrong-secret token 401 · a tenant-B token lands in B never A · replay deduplicated · oversized 413 · malformed JSON 400 · schema violation 422 · authority-shaped labels and instruction text stay data under the token's tenant · >200 alerts refused whole (422), never partially accepted.
- **§11 Burst:** 100 distinct alerts recorded, none lost, none duplicated; the same 100 replayed → 100 deduplicated; the embedded loop still cycling afterwards (cycle count, not a stale file).
- **§12 Integrity:** generations unchanged; RBAC `no`; tables; no Redis; latencies and counters read from the registry; the signal modules import no V1 model/repository/service/connector/infrastructure module (static).

## 4. Findings (pre-existing or discovered; recorded, stated, not hidden)

- **F-1 One dispatching process per store.** `SCHEDULER`, `AUDIT_WRITER`, `OUTBOX_PUBLISHER` are singleton leadership roles taken by `runtime.start()`; `build_worker_directory()` returns an in-memory, per-process directory; the scheduler dispatches only executions its own process tracks. A governed read issued from a second process while the API holds the roles waits out its budget with `the node recorded no attempt`. Consequence: the signal loop is embedded in the API process (`start_embedded`) or standalone with the roles taken lazily; a standalone instance beside a running API is an honest hot-standby follower. Not changed; decision for the runtime's owner (§12).
- **F-2 A refused worker selection leaves the node `leased`.** With no admitted connector worker in the process, the dispatcher answers `invocation_request_unavailable` and the run stays `leased`; the reader waits its whole budget with no reason string. Found by the first harness run; the worker now admits the connector before reading. Governed plane untouched.
- **F-3 Transport and credential audit facts never persist.** `backend/platform/transport/broker.py` and `backend/platform/credentials/broker.py` call `self._audit.record(kind, **fields)`, but `AuditRuntime.record` takes a positional `scope`; every call raises `TypeError` and is swallowed as `recording a transport audit fact failed` (logged at ERROR on every governed connector call — 108 times in one worker log). Present since the Phase 5 baseline (`20f2f77`). The refusal/allow decisions are unaffected (audit failure never turns a refusal into an allow); the **evidence** is missing. Not fixed here: governed plane, and the fix changes what the governance chain counts. Decision requested (§12).
- **F-4 `backend.main` boot runs LLM-backed one-shot checks.** With the `.env` placeholder Azure endpoint, each router call waits the 60 s per-provider timeout (run 2 measured two 65 s calls before the harness gave up at 240 s). The harness unconfigures every LLM provider for the API process; boot then takes ~100 s (§6). V1 boot hazard, pre-existing.
- **F-5 The V1 application writes to its own tables while it lives.** Enterprise watchers poll connectors continuously and log to `connector_activity` (boot: 3 rows; during the run: more). Beside the signal path, not on it (static import check 12.3b). Measured, not hidden.
- **F-6 Embedded loop stall (once, not reproduced).** In one API-only iteration the embedded loop stopped cycling after 14 cycles, 79 s into boot, with no exception logged and the process healthy; a dedicated reproduction ran 64 cycles through and past boot without stalling, and the two following runs cycled throughout. The harness now runs the API under a periodic all-thread dump (`api-threads.txt`) and asserts liveness by cycle count, so a recurrence leaves a stack trace. Recorded as unresolved; a production deployment should alert on `cortex_signal_cycles_total` stalling while `cortex_signal_worker_leader` is 1 (§11).
- **F-7 Status file wrote backoff 0 for a failed cycle** (the loop slept correctly, the report was wrong). Found by harness 7.1; fixed in this phase with a test.

## 5. Delivery semantics, stated precisely

- **At-least-once** from Kubernetes (ADR-083) and from Alertmanager (it retries on non-2xx; the ingress answers 503 when the ledger write fails so nothing is acknowledged that is not durable).
- **Effectively-once per lifecycle state** through the World identity digest over (tenant, source, subject, predicate, observed_at, value) — a redelivery is `DEDUPED`, measured: repeat notification 0 new rows; 100 replayed alerts → 100 deduplicated; restart and takeover → 0 duplicate identities.
- **Loss is possible and counted** across a `410 Gone` recovery exhaustion or a stall relist; the checkpoint records `origin` and reason. Exactly-once is not claimed anywhere.
- **Ordering** is per source (resourceVersion within a stream; startsAt/endsAt per alert; `recorded_at` + ULID for what CortexPrime learned when). No global order.

## 6. Measurements `[MEASURED]`

| Measurement | Value |
|---|---|
| standalone worker: process start → first completed cycle (governed LIST, position durable) | `4.0` |
| kubectl apply → the cluster reports CrashLoopBackOff (ground truth) | `232.9` |
| cluster reports CrashLoopBackOff → enriched observation recorded in cw_observation | `1.1` |
| kubectl apply → observation recorded | `234.0` |
| graceful stop → restarted worker resumes from the durable position | `30.1` |
| observations for the crashing pod before/after the restart (no duplicates) | `{"before_restart": 14, "after": 14}` |
| hard kill of the leader → follower holds the role and resumes (lease 12 s) | `40.1` |
| Kubernetes API paused → unpaused → stream resumed | `17.2` |
| PostgreSQL stopped → started → worker recorded again | `20.5` |
| event storm over the window cap: seconds to the explicit relist, dropped counter, stall checkpoints | `{"seconds_to_relist": 30.2, "dropped_counter": 1.0, "stall_checkpoints": 1, "storm_pods_observed": 0, "received": 5.0, "persisted": 1.0}` |
| backend.main (uvicorn) start → /health 200, LLM providers unconfigured (F-4) | `97.0` |
| tables the V1 application changed while booting (not the signal path) | `{"audit_logs": [0, 4], "connector_activity": [0, 3], "cp_audit_record": [64, 77], "cp_binding": [83, 96], "cp_execution": [83, 96], "cp_leadership": [3, 4], "cp_outbox": [498, 655], "cw_observation": [65, 77]}` |
| Prometheus+Alertmanager started → first alert observation durable (rule `for: 10s`, group_wait) | `21.3` |
| Alertmanager startsAt → recorded_at | `5.0` |
| target back up → resolved observation durable | `12.2` |
| 100 distinct alert deliveries through the boundary | `{"seconds": 3.75, "per_second": 26.7, "codes": {"200": 100}, "rows": 100}` |
| embedded loop cycles at API-up vs end, and seconds alive | `{"at_api_up": 12, "at_end": 30, "seconds": 167.8}` |
| registry histograms (mean seconds) | `{"cortex_signal_cycle_seconds": {"count": 20.0, "mean_seconds": 3.929}, "cortex_signal_persist_seconds": {"count": 0.0, "mean_seconds": null}, "cortex_signal_event_lag_seconds": {"count": 1.0, "mean_seconds": 0.344}, "api_cortex_signal_ingest_seconds": {"count": 206.0, "mean_seconds": 0.013}, "api_cortex_signal_persist_seconds": {"count": 206.0, "mean_seconds": 0.0109}}` |
| standalone worker counters at hand-over to the API | `{"cortex_signal_events_received_total": 5.0, "cortex_signal_events_persisted_total": 1.0, "cortex_signal_events_deduplicated_total": 0.0, "cortex_signal_events_dropped_total": 2.0, "cortex_signal_retries_total": 10.0, "cortex_signal_reconnects_total": 2.0, "cortex_signal_provider_errors_total": 10.0, "cortex_signal_facts_derived_total": 1.0, "cortex_signal_handoffs_total": 4.0}` |
| embedded loop counters at the end | `{"cortex_signal_events_received_total": 252.0, "cortex_signal_events_persisted_total": 105.0, "cortex_signal_events_deduplicated_total": 102.0, "cortex_signal_cycles_total": 30.0, "cortex_signal_handoffs_total": 30.0}` |
| tables changed by the signal path: standalone phase / API phase | `{"cp_leadership": {"standalone": [0, 3], "api": [4, 4]}, "cw_observation": {"standalone": [0, 65], "api": [77, 199]}, "connector_activity": {"standalone": [0, 0], "api": [3, 5]}, "cp_binding": {"standalone": [0, 83], "api": [96, 115]}, "cp_outbox": {"standalone": [0, 498], "api": [655, 773]}, "cw_fact": {"standalone": [0, 15], "api": [15, 16]}, "cp_execution": {"standalone": [0, 83], "api": [96, 116]}, "cp_audit_record": {"standalone": [0, 64], "api": [77, 97]}, "audit_logs": {"standalone": [0, 0], "api": [4, 191]}, "cp_audit_chain": {"standalone": [0, 1], "api": [1, 1]}}` |
| V1 background writes during the API run (F-5) | `{"connector_activity": {"standalone": [0, 0], "api": [3, 5]}}` |

Reading the numbers honestly:

- **Detection latency is bounded by the watch window, not by CortexPrime's pipeline.** Once the cluster reported the failure, the enriched observation was durable 1.1 s later (`crashloop_kubectl_seen_to_recorded_seconds`); the 234 s from `kubectl apply` to that point is the cluster's own image pull + crash + back-off cycle (an earlier iteration measured 16 s for the same manifest with a warm image — cluster behaviour, not ours). The Alertmanager firing was durable 5.0 s after `startsAt` (the rule's `for: 10s` and `group_wait` are Alertmanager's).
- **Cycle mean 3.9 s** with a 5 s window: the mean includes fast failure cycles during the outages; a healthy cycle is window + enrichment reads (~5.7 s observed in the status files).
- **`cortex_signal_persist_seconds` is fed by the HTTP ingress only** (mean 10.9 ms per alert, 206 samples); the worker's persistence time is inside its cycle time. `cortex_signal_event_lag_seconds` on the Kubernetes source is observed once per enriched event (0.34 s).
- **Loss was counted, never silent:** `cortex_signal_events_dropped_total` = 2 on the standalone worker (one storm relist, one expiry/stall relist after the outages), each with a checkpoint that names the reason.
- **`cluster_generations_after` carries `p112-crashy: 1`** — the harness's own `kubectl apply` (deleted at cleanup). The three standing deployments are unchanged: that is the provider-write check.
- **The 7 negative cases** in the report's `negative_matrix` all recorded `provider_writes: 0`.
- **Burst:** 100 alerts in 3.75 s (26.7/s) through the whole boundary, all 200, all durable; the `ingest` bucket (300/min) was not reached. That ceiling is a stated limitation for an alert storm larger than ~5/s sustained (§12).

## 7. Tenant isolation

Tenancy is bound where the credential is: the worker's declared tenant (bound to the provider credential by `CORTEX_KUBERNETES_TENANT`; a mismatch refuses to start), the token's tenant at HTTP ingress (a tenant-less token is refused; the V1 fence does not apply because the ledger is tenant-scoped by row). Every read query is tenant-predicated. Attacked: tenant B sees nothing of A (product API, ingress), a claim without a durable membership is refused, a `tenant_id` label inside an alert is data.

## 8. Governance regression (10.7–10.14)

`[VERIFIED]` re-executed in this session against the real k3d cluster, real PostgreSQL (each harness's own `cortex_p10xx` database) and real Redis, by the same serial runner as Phase 11.1 (fresh ServiceAccount tokens passed through the environment, real kill on timeout):

| Harness | Result | Provider writes |
|---|---|---|
| 10.7 scoped authority / execution | **155/155 VERIFIED** (219 s) | `[0, 1]` — the one commissioned rollout restart the harness itself performs |
| 10.8 governed grant issuance | **118/118 VERIFIED** | 0 |
| 10.9 membership | **107/107 VERIFIED** (solo re-run, twice) | 0 |
| 10.10 tenant records | **107/107 VERIFIED** | 0 |
| 10.11 TenantManager retirement | **68/68 VERIFIED** | 0 |
| 10.13 V1 read retirement | **60/60 VERIFIED** | 0 |
| 10.14 IAM retirement | **53/53 VERIFIED** | 0 |

Counts are identical to the 10.31 and 11.1 baselines. Stated honestly: **10.9 failed its first attempt in the chain at 100/105** (J1, J3, K1, L1, L2 — admissions answering 500 after the threaded concurrency check, the run's stdout carrying the `Blacklist JTI check error … Event loop is closed` pattern of the shared async Redis client bound to a loop the TestClient closes, recorded in 11.1 §3-J) and once more solo; it then passed **107/107** twice with every change of this phase in place, and also passed at the parent commit `e662688` in a throw-away worktree and with `backend/auth/dependencies.py` reverted — so the failure does not track any change of this phase. Phase 11.1's first attempt of the same harness failed on exactly the same five checks before passing. 10.10, 10.13 and 10.14 printed their full VERIFIED reports and their processes lingered afterwards (as 10.13 did in 11.1); the runner released them after the verdict.

`git diff --stat HEAD -- backend/contexts backend/platform backend/assurance backend/intelligence` is empty; `backend/world` gained two read queries on the observation repository and nothing else.

## 9. Regression suite

`[VERIFIED]` `POSTGRES_HOST=0.0.0.0 REDIS_HOST=0.0.0.0 python -m pytest tests/ -q --tb=no -rf -p no:cacheprovider --timeout=900` → **71 failed / 6935 passed / 36 skipped / 58 xfailed / 24 errors** (1159 s). Baseline after 11.1: 71 / 6883 / 36 / 58 / 24. `FAILED` names diffed: **0 new, 0 gone**. Passed grew by 52 (the new `tests/signal` modules). No test was weakened or skipped.

## 10. Database and Redis integrity

Row counts of every table were taken at start, just before the API booted, just after it was up, and at the end. On the signal path only `cw_observation`, `cw_fact`, `cp_execution`, `cp_binding`, `cp_audit_record`, `cp_audit_chain`, `cp_leadership`, `cp_outbox` and `audit_logs` changed; no V1 table, no schema change, no migration. The V1 application's own writes (`connector_activity`) are reported under their own measurement. Redis was absent for the whole API run; the standalone worker has no `REDIS_URL` at all.

## 11. Known limitations

- Kubernetes source is pods in one namespace; Kubernetes `Event` and Deployment objects are not watched (further read capabilities, 11.6).
- Workload identity is inferred from the pod name and labelled as inferred (ownerReferences are not a declared watch field).
- One governed read per mutation for enrichment (≤ 64 per window); an over-cap window costs an explicit, counted relist.
- Candidate thresholds are projection defaults, not detection policy (Prompt 3).
- OpenTelemetry is not a governed source in this phase (ADR-122 D-8); the V1 OTLP receiver stays fenced.
- Embedded mode makes the API process the observer; two API replicas elect one observer per stream through `WORLD_WATCH`, but the API must be running for signals to be observed. Standalone mode is for stores no API dispatches against.
- F-6 is an open observation, not a closed defect.

## 12. Decisions requested

1. **F-3** — authorise the one-line audit fix in the two brokers (pass a `TenantScope` built from the request's tenant) and re-baseline the governance chain counts it will change, or leave the transport/credential audit facts unrecorded until the runtime's owner takes it.
2. **F-1** — whether multi-process dispatch (a durable worker directory, non-singleton scheduling) is a Phase 11.x item, or embedded-beside-the-API is the accepted GA shape.
3. Whether the `ingest` rate-limit bucket (300/min per identity) is the right ceiling for an Alertmanager principal under a real alert storm (100 alerts took 3.75 s).
