# PHASE 11.3 — Detection + Investigation Implementation Map

- **Date:** 2026-09-10 · **Parent HEAD:** `e4913b3` (Phase 11.2) · **Branch:** `phase-1-foundation`
- **ADR:** `docs/adr/ADR-123-phase-11-3-detection-investigation.md` · **Verification:** `docs/PHASE_11_3_DETECTION_INVESTIGATION_VERIFICATION_REPORT.md` · **Harness:** `scripts/phase113_detection_investigation_harness.py`

## 1. Repository research (what was true at `e4913b3`)

| Component | State found | Consequence |
|---|---|---|
| `InvestigationService` / `cw_investigation` | complete event-sourced state machine (`created → investigating → … → completed/failed/abandoned`), conclusion axis `resolved / unresolved / insufficient_evidence / conflicted / escalated / blocked / failed`, optimistic concurrency, secret firewall | reused verbatim; **no production caller of `create`** |
| `InvestigationEngine` (ADR-073/075) | OODA step: world evidence → deterministic context → model proposes → platform selects and validates a test → governed read → differential updated by **digest equality** → settle; budgets on steps/reads only; no time/token budget | extended with structured matching, a declared compatibility relation and two budget fields; everything else untouched |
| `GovernedModelBoundary` / `GovernedModelProposalPort` | strict schemas (`extra="forbid"`), scrubbed prompts, durable span **before** any proposal, provider stamped from the span; real `LLMServiceModelPort` never wired; every composition scripted | wired with a real port and a deterministic plan port; unchanged internally except the port's parameters |
| Phase 9.5 investigator (`incident_investigation.py`, `governed_evidence_acquisition.py`) | complete, harness-only: 5 seeded CrashLoop hypotheses, 5 tools (pod state, termination, deployment revision, memory, restarts), `ToolRegistry` refuses writes at construction, report assembler computes no verdict | reused: hypotheses, tool mechanism, report |
| Read capabilities | real-exposed: pods.list, pods.watch, pod.get, deployment.get; declared-only: pod.logs (`lineCount` only), events.list (`eventCount` only), deployments.list; Prometheus: 3 instant queries, harness-only | logs/events/replicasets real-exposed with declared record evidence; Prometheus + 3 operations incl. one bounded range query |
| Evidence model | World `Observation` (identity digest, provenance, source kind/ref), categorical authority/freshness/lineage/corroboration; **no numeric weight anywhere** | kept; confidence computed from those categories |
| `cw_reasoning` | kinds hypothesis / prediction / prediction_evaluation / experience_use | + `detection`, `assessment` (no migration: `kind` is text) |
| LLM stacks | `backend.llm_provider` (adapters, no retries, hand-rolled structured validator) and `backend.llm` (gateway/router); provider keys present in the git-ignored `backend/.env` (first missed, F-22); no Ollama running | Ollama adapter fixed for JSON mode/usage/timeout; a local Ollama container is the real provider |
| Cost | `cost_tracking` table + `CostEngine` (V1 mission path, currently unreachable per ADR-114); governed spend only in `cp_harness_trace` spans | cost read from spans; USD from the static table |
| Product API | read-only over investigations (`/investigations*`, evidence, timeline, assurance); no detection surface | + `/detections`, `/investigations/{ref}/assessment`, `/investigations/{ref}/cost` |
| Signal fabric (11.2) | candidates projected; `DetectionHandoff` default logs and opens nothing | implemented by `InvestigationHandoff` |
| V1 intelligence (`enterprise_root_cause_analysis`, alert correlators, connectors) | ungoverned, quarantined (ADR-071), file stores, caller-composed queries | not used |

## 2. Real-world research applied

- **RCA evaluation:** RCAEval / OpenRCA-style benchmarks report frontier agents recovering the exact root-cause set in about a fifth of cases and grounding a correct service in a causal path in about three fifths — so this phase measures evidence-citation correctness and false-causal rate per scenario rather than claiming a score, and treats INSUFFICIENT_EVIDENCE as a correct outcome.
- **Indirect prompt injection through logs/alerts** (LogJack, context-contamination studies): every mitigation has a ceiling, so containment here is structural — the model names tool keys only, the schema rejects authority fields, no write capability is composed, and injected text is retained as data.
- **Kubernetes:** events are short-lived (~1 h) and high-volume — read per object with a field selector and a limit; container logs via `previous=true`, `tailLines`; ReplicaSets carry the revision annotation and the pod template, which is where "what changed" actually lives.
- **Prometheus:** instant queries for state, one bounded `query_range` for onset; PromQL is a constant of each declared operation.
- **OpenTelemetry:** not adopted for the governed plane (11.2 D-8 stands).

## 3. Architecture, as implemented

```
signal worker (11.2) ── candidates ──▶ InvestigationHandoff.offer
                                         │ detect(): sustained? (DetectionPolicy)          backend/signal/detection.py
                                         │ cw_reasoning kind=detection (idempotent identity)
                                         │ one investigation per incident_ref (cw_investigation)
                                         ▼
                                 InvestigationRunner (one thread, bounded queue)        backend/api/investigation_runtime.py
                                         │ classify incident → seed differential (catalog)
                                         │ baseline reads: pod_state, events (governed)
                                         │ loop: engine.step
                                         │     context ▸ proposal (plan | model+plan) ▸ select ▸ validate ▸ governed read
                                         │     ▸ matching.matches(expectation, observed) ▸ SUPPORTED/REFUTED ▸ settle
                                         │ assessment (confidence.assess) → cw_reasoning kind=assessment
                                         ▼
product API: /detections, /investigations/{ref}/{assessment,cost,evidence,hypotheses,timeline}
```

Tools (`backend/api/investigation_catalog.py`), all governed READs, subject-kind checked, parameters platform-computed:

| key | operation | predicate | proposition |
|---|---|---|---|
| `k8s.pod_state` | kubernetes.pod.get | pod_state | phase, waiting reason |
| `k8s.pod_termination` | kubernetes.pod.get | last_termination | exit code, reason |
| `k8s.pod_logs` | kubernetes.pod.logs (`previous`, `tailLines=200`) | log_patterns | bounded patterns; configError / dependencyError / crashTrace |
| `k8s.pod_events` | kubernetes.events.list (`fieldSelector=involvedObject.name=`, `limit=64`) | events | backoff / probeFailure / imagePullFailure, first/last warning |
| `k8s.deployment_state` | kubernetes.deployment.get | deployment_state | replicas, ready, available, short |
| `k8s.deployment_revision` | kubernetes.deployment.get | deployed_revision | revision, image |
| `k8s.rollout_history` | kubernetes.replicasets.list | rollout_history | revisions, images, template digest, recentChange, containerSpecChanged |
| `metrics.pod_memory` | prometheus.pod_memory_ratio | memory_pressure | atOrAboveLimit, limited, peakRatio |
| `metrics.pod_restarts` | prometheus.pod_restarts | restart_count | corroboration (DERIVED) |
| `metrics.restart_timeline` | prometheus.pod_restarts_range (start/end computed from the window) | restart_onset | restartsIncreased |
| `metrics.deployment_unavailable` | prometheus.deployment_unavailable | replicas_unavailable | short |

Differentials: CrashLoop `h-startup-failure / h-configuration / h-dependency-connectivity / h-resource-exhaustion / h-deployment-regression`; workload-unavailable/alert `h-deployment-regression / h-probe-failure / h-image-pull-failure / h-configuration / h-resource-exhaustion`; unobservable subject `h-unobservable-subject`. The regression hypothesis names the Deployment subject; it is declared compatible with every mechanism hypothesis (composite explanation).

Test plan (structured expectations evaluated by `matching.matches`):

| hypothesis | supported when | contradicted when |
|---|---|---|
| resource exhaustion | termination exit 137 or OOMKilled; memory ratio ≥ 0.95 | other exit/reason; ratio < 0.95 with a limit |
| configuration | log carries a config-shaped error | log errors are dependency-shaped |
| dependency | log carries a connectivity-shaped error | log has errors, none connectivity-shaped |
| startup (internal) | crash trace, no config/dependency error | a config or dependency error explains it |
| regression | rollout in the change window AND container spec changed | no rollout in the window (metadata-only rollout stays OPEN) |
| probe failure | Unhealthy / probe-failed event | none, and back-off instead |
| image pull | waiting ErrImagePull/ImagePullBackOff; pull-failure event | other waiting reason; no such event |

Windows (`InvestigationWindow`): incident start = first recorded observation of the condition; change window = 30 min before it to 30 s after (skew tolerance); baseline 15 min; the range query is capped at 1 h. Assumptions are carried on every assessment.

Confidence (`confidence.assess`): categorical, from statuses + lineage origins + freshness + contradiction; correlated evidence counted once. Outcomes `ROOT_CAUSE_IDENTIFIED / LIKELY_CAUSE / INSUFFICIENT_EVIDENCE / CONFLICTED / BLOCKED`.

## 4. Model boundary

| Concern | Answer |
|---|---|
| Provider | `backend.llm_provider` `LLMService` through `LLMServiceModelPort` (existing); Ollama adapter fixed (JSON mode, usage, timeout, `num_ctx`). Record run: the operator's hosted `glm-5.2` through `OpenAICompatibleAdapter` over a plain-HTTP proxy (D-18). Also supported: local container `ollama/ollama` serving `llama3.2:3b` (no key, no egress). Hosted providers unconfigured (placeholder keys), not activated. |
| Configuration | `CORTEX_INVESTIGATION_MODEL_PROVIDER` (`ollama` / `openai-compatible` / unset), `CORTEX_INVESTIGATION_MODEL`, `CORTEX_INVESTIGATION_MODEL_TIMEOUT_SECONDS` (180), `CORTEX_INVESTIGATION_MAX_TOKENS` (24000), `OLLAMA_BASE_URL`, `OLLAMA_NUM_CTX` |
| Structured output | `InvestigationProposalSchema` (pydantic, `extra="forbid"`) validated in `GovernedModelBoundary`; invalid → `TEST_REJECTED` step, never used |
| Unavailable / timeout / budget | `PlanAugmentedModelPort` falls back to the deterministic plan; span config records `fallback_reason` |
| Without a model | `PlanModelPort` alone; every span `provider=deterministic` |
| Context | the assembled context only (incident, differential, world evidence, prior tests, tool keys); log evidence is bounded patterns, scrubbed; no credential, no raw payload |
| Output treatment | untrusted proposal; the platform selects the test, validates it, performs the read, matches the observed value; the model never sets a status, a conclusion, a confidence or an action |
| Trace | `cp_harness_trace` span per call: provider, model, tokens, latency, schema id, failure reason |

## 5. Files

### New
| File | Purpose |
|---|---|
| `backend/signal/detection.py` | deterministic sustained detection |
| `backend/api/investigation_catalog.py` | incident classes, differentials, tools, windows, test plan, plan / plan-augmented model ports |
| `backend/api/investigation_runtime.py` | handoff, runner, assessment/cost recording, composition, embedded start |
| `backend/intelligence/application/matching.py` | structured expectation matching |
| `backend/intelligence/application/confidence.py` | categorical confidence and assessment |
| `backend/api/product/assessment_routes.py` | `/detections`, `/investigations/{ref}/assessment`, `/investigations/{ref}/cost` |
| `scripts/phase113_detection_investigation_harness.py` | real-infrastructure scenarios, evaluation, integrity |
| `tests/signal/test_detection.py`, `tests/intelligence/test_matching.py`, `test_investigation_catalog.py`, `test_confidence.py`, `test_investigation_runtime.py` | permanent tests |
| `docs/adr/ADR-123-…`, this map, the verification report, `docs/phase113_detection_investigation_report.json` | record |

### Changed (additive)
| File | Change |
|---|---|
| `backend/contexts/execution/infrastructure/adapters/connectors/kubernetes.py` | `pod.logs` bounded params + pattern records + text decoder; `events.list` field selector + event records; `replicasets.list` (new); three more real-exposed reads |
| `backend/contexts/execution/infrastructure/adapters/connectors/prometheus.py` | `pod_memory_ratio` (per-pod aggregation, pod-cgroup limit, 30-minute scraped peak; D-14), `deployment_unavailable`, bounded `pod_restarts_range` + matrix normaliser |
| `backend/intelligence/application/engine.py` | `matches` in the differential update; `compatible` relation; `max_seconds` / `max_tokens` budget fields; `StepOutcome.EVIDENCE_ABSENT` (D-15) |
| `backend/intelligence/application/differential.py` | `settle(..., compatible=)` composite resolution |
| `backend/intelligence/application/proposal.py` | `EvidenceResult.absent` (D-15) |
| `backend/api/governed_evidence_acquisition.py` | a succeeded read that reports nothing for the subject answers `absent=True` (D-15); a tool may declare `absent_when`, and a failed read whose reason matches it answers `absent` too (D-19) |
| `backend/world/application/reasoning.py` | `ReasoningKind.DETECTION`, `.ASSESSMENT` |
| `backend/api/observability_evidence.py` | kubelet lineage origin (logs, cAdvisor); freshness horizons for the new predicates |
| `backend/harness/llm_boundary.py` | `LLMServiceModelPort(provider=, timeout_seconds=, max_tokens=)` |
| `backend/llm_provider/providers/ollama_adapter.py` | JSON format, usage, honoured timeout, HTTP error surfaced, `num_ctx`; refuses a prompt larger than its window before any call (D-17) |
| `backend/llm_provider/providers/openai_compatible_adapter.py` (new) | OpenAI-compatible provider configured by `LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL`; declares only `LLM_MODEL`; priority last; refuses plain HTTP to a non-loopback host unless `LLM_ALLOW_PLAINTEXT_HTTP=1` (D-18) |
| `backend/llm_provider/registry.py` | registers `OpenAICompatibleAdapter` beside the existing adapters (D-18) |
| `backend/intelligence/application/context.py` | `AssembledContext.prompt_view()`: included content, excluded sections named without content (D-17); `to_dict` unchanged |
| `backend/intelligence/application/model_boundary.py` | investigation and prediction prompts render `prompt_view()` instead of the full recorded context (D-17) |
| `backend/api/product/app.py` | engine fields `reasoning`, `traces`; assessment router |
| `backend/main.py` | lifespan starts the investigator and hands its handoff to the signal loop; stops it |
| `backend/observability/prometheus_metrics.py` | detection / investigation counters, histograms, gauge |
| `backend/api/capability_execution_composition.py` | `GovernedCapabilityReader`: a finished read leaves the dispatch set (`untrack` in `finally`); one governed read in flight per process through a fair re-entrant ticket lock (D-10) |
| `backend/platform/transport/httpx_adapter.py` | the policy's `total_seconds` is enforced on a streaming body read (D-11) |
| `backend/contexts/execution/application/dispatcher.py` | a platform-internal context is refused before the lease is taken, `invocation_refusal=tenant_unknown`, nothing leased (D-12) |
| `tests/intelligence/test_kubernetes_real_adapter.py`, `test_capability_bridge_k8s.py`, `test_kubernetes_watch.py`, `test_observability_corroboration.py` | pinned policy sets updated deliberately (real exposure, record evidence, range parameters) |

### Not changed
`backend/contexts/connectivity/*`, the execution context's domain layer and its gateway (`invocation_gateway.py` is untouched; D-12 changes only when the dispatcher takes a lease), `backend/assurance`, every migration, `requirements*.txt`, Helm, compose. No write capability declared, exposed or composed.

## 6. Environment

| Variable | Default | Meaning |
|---|---|---|
| `CORTEX_INVESTIGATION_ENABLED` | 1 | 0 disables the embedded investigator (signal loop still runs) |
| `CORTEX_INVESTIGATION_MODEL_PROVIDER` / `_MODEL` | unset | a real provider through `LLMService`; unset = deterministic plan |
| `CORTEX_INVESTIGATION_MODEL_TIMEOUT_SECONDS` | 180 | per model call |
| `LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL` / `LLM_ALLOW_PLAINTEXT_HTTP` | unset | the hosted OpenAI-compatible provider (D-18); values only in the git-ignored `backend/.env` |
| `CORTEX_INVESTIGATION_MODEL_MAX_OUTPUT_TOKENS` | 900 | answer tokens per model proposal; the hosted model pass sets 4096 (glm-5.2 reasons before answering) and a 150000-token investigation ceiling |
| `CORTEX_P113_MODEL_PROVIDER` | `ollama` | harness model-pass provider: `ollama` or `openai-compatible` |
| `CORTEX_INVESTIGATION_CONTEXT_TOKENS` | 4000 | the context assembler's size budget per proposal; the harness model pass sets 1500 for the local CPU model |
| `CORTEX_INVESTIGATION_MAX_STEPS` / `_MAX_READS` / `_MAX_SECONDS` / `_MAX_TOKENS` | 16 / 12 / 900 / 24000 | budgets (steps sized to the staged plan, D-16; the harness model pass raises seconds to 3600 and the model timeout to 600 for the local CPU provider) |
| `CORTEX_INVESTIGATION_RESUME` | 1 | resume active investigations at start |
| `CORTEX_PROMETHEUS_URL` / `_TOKEN` / `_NAMESPACE` / `_TENANT` + `prometheus_extension` in `CORTEX_CONNECTOR_FACTORIES` | unset | metrics tools appear only when composed |
| plus the 11.2 signal variables | | the investigator starts only where the signal loop is configured |

Harness: `CORTEX_P113_SCENARIOS` (subset), `CORTEX_P113_MODEL=1` (real model pass on S1/S5 + provider outage), `CORTEX_P113_SCRATCH`.
