# PHASE 6.1 — IMPLEMENTATION MAP (Architecture Discovery, Pre-Code)

Date: 2026-08-11 · Basis: three parallel read-only investigations of the working tree (HEAD `3bf0b11` + ~148 uncommitted/untracked paths). No code has been modified. Per the Phase 6.1 stop condition, this map precedes any implementation.

---

## 0. CONTRADICTIONS REQUIRING DECISIONS (STOP items)

Per the critical final instruction, these repository facts contradict or complicate the prompt and need explicit decisions before coding:

**C1 — DoD item 3 cannot use GitHub, and no other governed provider exists.**
The prompt requires one real governed action reaching a PROVIDER, and simultaneously (correctly) blocks GitHub credentials. The only real provider adapter in the governed plane is GitHub (`contexts/execution/infrastructure/adapters/connectors/github.py`) — its 2 write ops are *structurally refused* (`AMBIENT` isolation < `IRREVERSIBLE_WRITE`, `capability_execution_composition.py:472-484`) and its reads need the blocked credential. The only provider on this machine that can take a **real, observable, reversible write with zero third-party credentials** is the **local Docker daemon** (`docker.py:92` → `docker.from_env()`; docker-compose runs 10 containers here). → **Decision: build a governed Docker provider adapter (catalog: `list_containers`/`inspect_container` as READ, `restart_container` as a compensable write) and make `restart_container` on a dedicated scratch container the Phase 6.1 vertical slice.** Alternative: defer the real-provider leg of DoD#3 entirely (weakens the phase). GitHub is not an option.

**C2 — "Current repository state" is largely uncommitted.**
The entire Phase 5 governed plane is untracked/modified (148 paths: the gateway, `application_runtime.py`, migrations 0010–0013, `platform/credentials/`, `platform/transport/`, all Phase 5 ADRs). HEAD is the README rewrite. Building 6.1 on an uncommitted foundation makes every diff unreviewable and every rollback impossible. → **Decision: commit the existing working tree as a Phase 5 baseline commit (or commits) before any 6.1 change.** This is hygiene, not new work.

**C3 — "Existing Phase 5 guarantees remain green" has no committed test to stay green.**
Phase 5's evidence (ADR-047/057/058 verification tables) came from ad-hoc harnesses that were never committed. Grep proof: zero tests reference `invocation_gateway`, `ExecutionScheduler`, `RecoveryCoordinator`, `CredentialBroker`, `OutboxPublisher`, or the SQL durable repositories. DoD#12 can only honestly mean: the architecture gate stays green (19 rules, currently PASS) **plus the new tests 6.1 writes**. The report will state this; "remain green" will not be claimed over machinery that has no committed test.

**C4 — CI is partly vacuous.** `.github/workflows/ci.yml:42` runs pytest against `backend/tests/`, which does not exist — that job passes on nothing. `test.yml` is the real test job. The 6.1 evidence chain must not cite ci.yml.

**C5 — Pre-existing safety defects discovered during discovery** (fix in 6.1 scope, they are one-line class): `computer_agent.py:103` — the computer-use governance check (emergency stop + approval queue) **fails open** (`except Exception: return True`); `executive_routes.py:156` + `governance_center_routes.py:313` call nonexistent `emergency_stop.is_active()` so dashboards always report "not stopped"; `enterprise_docker_health_fix_executor.py:62` + `approval_center/policies.py:23` — LOW-risk actions **auto-approve** (`required_levels=0`), which is how a watcher can restart containers with only an env flag in the way.

**C6 — Quarantine-to-zero disables V1 product behaviors by default.**
Reaching UNGOVERNED = 0 means the ~60 mutating enterprise routes, the auto-fix executors, and the delivery pipeline's side-effecting stages go behind the existing default-off legacy flags. Watchers keep polling (read-only), dashboards keep working, but nothing writes to Jira/GitHub/ArgoCD/Terraform/Docker unless a flag is set. This is the stated desired end state ("UNGOVERNED SIDE EFFECTS = 0") — flagged here so the product consequence is explicit and accepted, not discovered later.

---

## 1. CURRENT EXECUTION ENTRY POINTS

| Entry | Cadence/Trigger | Gate | Evidence |
|---|---|---|---|
| ~60 mutating `enterprise_*` HTTP routes (git, cicd, infrastructure, delivery, pipeline, monitor `/check`) | on request — **unauthenticated** (`APIRouter` with no dependencies) | **none** | `enterprise_infrastructure_routes.py:87`, `enterprise_git_routes.py:24`, `enterprise_cicd_routes.py`, `enterprise_delivery_routes.py:28,92`, `enterprise_pipeline_routes.py:16` |
| Watcher manager (9 watchers) | 30–180 s | none (skips under pytest only) | `main.py:1108`; `enterprise_watchers.py:655,692` |
| Autonomous trigger runtime | 60 s scheduler + EventBus | `AUTONOMOUS_TRIGGERS_ENABLED` default **true** | `main.py:608`; `autonomous_trigger_runtime.py:271,498` |
| Continuous cognition runtime | 60/120/300 s | none | `main.py:733-742` |
| Startup one-shots (credential/vuln/branch-protection/cost checks) | boot | none | `main.py:1050-1075` |
| Docker event-stream listener | continuous | none | `enterprise_infrastructure_intelligence.py:1091` |
| 22 quarantined surfaces (12 exec routes, 6 connectivity, 2 internal, 2 process/exec) | on request | `CORTEXPRIME_ENABLE_LEGACY_EXECUTION` / `_CONNECTIVITY` / 2 others — default **off** | `legacy_execution_boundary.py:96-215`; `legacy_connectivity_boundary.py:100-162` |
| Governed scheduler → dispatcher → gateway | 0.5 s tick when running | `CORTEX_DURABLE_URL` — **unset**; plane absent by default | `application_runtime.py:63,335`; `main.py:119-127` |

## 2. EVERY KNOWN SIDE-EFFECT PATH (classified)

Desired end state: UNGOVERNED = 0. Current counts:

- **GOVERNED: 2 declared, 0 operational.** GitHub adapter ops; writes structurally refused; worker never commissioned (`commission_first_operation` at `first_governed_operation.py:225` is called by nothing); worker directory built empty (`capability_execution_composition.py:271-282`).
- **QUARANTINED: 22 surfaces** behind 4 default-off flags (above), incl. `subprocess.Popen` host launch (`computer_task_engine.py:37`) and in-process `exec()` (`execution/sandbox/interfaces.py:365`).
- **READ-ONLY: ~110 connector read methods** across 9 families + 8 watcher pollers (still ungoverned outbound calls with process-wide credentials — classified read-only at the provider).
- **UNGOVERNED: 13 chains (~90 write-capable connector methods reachable).** Headlines: **U1** `POST /api/infrastructure/terraform/{apply,destroy}` → `terraform apply -auto-approve` subprocess inheriting `os.environ` (`terraform.py:155,214,222`); **U2** ArgoCD sync `prune=True`/rollback (`enterprise_infrastructure_routes.py:740-758`); **U3** GitHub branch/commit/PR/merge (`enterprise_git_routes.py:98-184`); **U4** CI/CD rerun/build/queue (`enterprise_cicd_routes.py:367-429`); **U5** Docker restart/prune/remove — watcher-reachable every 30 s (`docker.py:298,505,517`); **U6** Jira `create_issue` from 6+ incident reporters (startup + watcher + unauthenticated `/check` routes); **U7–U9** auto-fix executors (GitHub PRs, branch protection, deploy rollback) gated only by env flags + an approval system whose LOW tier auto-approves; **U10** delivery pipeline (ArgoCD + sandbox subprocess + deployment); **U11** sandbox `/prepare` → `git clone` + `pip/npm install` ungated (`enterprise_sandbox_routes.py:92`); **U12** `os.environ` mutation from request bodies (`docker.py:76-86`); **U13** pipeline routes.
- **LATENT: 2.** `mission_skills/engine.py:189-196` (`getattr(connector, op)(**params)` — has approval queue, no legacy guard); `orchestrator/handlers.py:322-331` (blind first-capability execution, dead only because `"connector_service"` is never DI-registered).

## 3. V1 EXECUTION BYPASSES — see U1–U13 + L1–L2 above. Chokepoint analysis (§15) shows ~23 insertion points close all of them.

## 4. CURRENT AGENT/ORCHESTRATOR LOOPS

| Loop | Structure | Budget | Stop condition | State |
|---|---|---|---|---|
| `cognition_pipeline.py:468-497` | fixed 6-stage sequence | none | `should_retry()` gate **can never fire** (`retry_count` never incremented) | Redis, swallowed writes; restart loses stage outputs (`to_dict` doesn't serialize them) |
| `autonomous_reasoning_loop.py:409-525` | for-loop | `max_iterations` default 5; nothing else | "success" = `len(output.strip()) > 20` | in-memory dicts, unbounded, lost on restart |
| `orchestrator_agent.py:484` | retry-while | `max_retries=2` hardcoded | — | in-memory |
| `computer/task_completion_engine.py:161-399` | best of the lot | `MAX_ITERATIONS=30`, `MAX_FAILURES=5` | vision "complete" / failures / emergency stop / timeout | in-memory; memory write at end |
| `orchestrator/engine.py:260` | state-machine while | **no cap** | ARCHIVED state | — |
| `mission_runtime.py:1027-1180` | linear pipeline | one `timeout=300` | — | — |

No loop has a wall-clock, token, or cost budget. None uses the durable execution substrate.

## 5. CURRENT LLM INVOCATION BOUNDARIES

**Four independent paths to a model** (no single chokepoint): (1) `llm_provider.LLMService` (clean stack: 8 adapters, `LLMResponse` with raw `usage`+`latency_ms`); (2) `llm/llm_gateway.py` — **discards** usage/latency/request_id, falls back to raw SDK clients; (3) `llm/llm_router.py` — keyword routing, circuit breaker, direct SDK fallbacks; `RouterResult` has **no token fields**; (4) direct SDK: `providers/openai_provider.py` used by `mission_runtime.py:409` and `vision_reasoner.py:252`.

16 production call sites inventoried; **zero use Pydantic/jsonschema on model output**. The only "validation" is hand-rolled top-level checks in `llm_provider/structured.py:66-102` (greedy `\{[\s\S]*\}` regex fallback), reachable only from an HTTP route. Three call sites are **structurally broken and silently swallowed**: `llm_gateway.complete()` kwarg mismatch at `cognition_pipeline.py:234`, `task_decomposer.py:190`, `reflection_agent.py:174` — **LLM task decomposition has never actually run** (always falls back to a static template); `mission_runtime.py:330` reads nonexistent `RouterResult.prompt_tokens` (AttributeError on the success path).

## 6. CURRENT TOOL INVOCATION BOUNDARIES

V1: `ConnectorRegistry.get()` (`registry.py:32`, ~40 call sites) → per-connector methods, 15/20 connectors routing 100% of ops through `BaseConnector._execute()` (`base.py:217`) — the single best chokepoint (~76/90 writes). Bypasses: `argocd._post`, `terraform._run`, `github.graphql_request:133` (arbitrary GraphQL POST), 6 direct-constructed connector instances. V2: adapter seams (`ADAPTER_SEAMS`: Connector/MCP/Agent) behind the gateway with `AdapterSeam` TOCTOU re-checks; `TestProviderAdapter` for tests.

## 7. EXISTING SCHEDULER/RECOVERY PATH

Fully built, deliberately loopless components: `ExecutionScheduler` (`tick()` callable once in a test; leadership + readiness fail-closed ports), `ExecutionDispatcher` (one bounded `cycle()`), `RecoveryCoordinator` (performs nothing itself), `OutboxPublisher` (daemon-thread pump). Composed in `application_runtime.py:416-447`; start order rebinds audit → acquires writer role → recovery-then-dispatch → outbox pump; stop drains in reverse. Durable queue `cp_queue` + `cp_leadership` (migration 0011).

## 8. EXISTING GOVERNED GATEWAY

`SecureCapabilityInvocationGateway` — 13 ordered stages + delegation (`invocation_gateway.py:502-516`): identity → tenancy → binding → authorization → approval → worker → input → digest → obligations → freshness → lease → rate → credential; credentials minted last; `invoke()` has no loop/retry/fallback. Caller must supply: tenant `ExecutionContext` (platform-internal refused), `InvocationRequest` (via `SelectingRequestFactory.build`, `capability_execution_composition.py:923`), sealed `BoundCapability` projection, and ~9 wired collaborators. Worker path to operability: REGISTERED→VALIDATED→ENABLED + trust + availability (`WorkerCommissioning`; `first_governed_operation.py:225` — never called). **Zero committed tests.**

## 9. EXISTING AUDIT PATH

Platform audit runtime: hash-chained, single-writer-by-admission, `record_in_context()` pulls correlation/causation + `trace_id`/`span_id` from `ExecutionContext.audit_detail()` (`platform/audit/runtime.py:206-239`; `runtime.py:341-362`). Durable: `cp_audit_chain`/`cp_audit_record` (migration 0013, cross-process `next_sequence`, no update/delete path). Docstring explicitly **bans traces/metrics from the audit trail** (`runtime.py:26-28`) → the 6.1 trace store must be a separate store correlated by `correlation_id`. Two other V1 audit surfaces exist (`integrity_audit.jsonl`, `safety/audit_logger.py`) — unchained; not to be extended.

## 10. EXISTING TRACING/OBSERVABILITY

Reusable as-is: `platform/context/tracing.py` (W3C-shaped `TraceContext` + `CorrelationContext` with `child_span()`/`caused_by()` — fully built, correct); platform `ExecutionContext` (immutable, mandatory identity/tenancy/trace/correlation); `contexts/execution/application/instrumentation.py` `ExecutionObserver` — the **designed, unimplemented trace hook**; `observability/prometheus_metrics.py:340` `record_llm_call(provider, model, latency, tokens, cost, …)` — the full budget shape; `analytics/cost_engine.py` (correct cost table; the adapter-level one is 1000× off); `platform/credentials/redaction.py` — `scrub_text` + `redact_mapping`, dependency-free, exactly the trace/prompt redaction hook. Not reusable: `orchestration_tracer.py` (no trace_id, no parent/child, unbounded in-memory); OTel configured (`core/tracing.py`) but never called from any loop or LLM path; `telemetry_service.py` confirmed 0 bytes.

## 11. EXISTING CONTEXT ASSEMBLY

All f-strings/constants; char-count truncation (`mission_runtime.py:1140-1172`); memory injection via `retrieval_engine.py:44-90`; `PromptTemplate` with a `version` field exists (`llm_provider/prompt.py:24-33`) and **`register_template` is never called**. No secrets scrubbing on any prompt path; concrete leak surfaces: workspace RAG chunks, OCR text (up to 1500 chars raw), code diffs into RCA prompts, full desktop screenshots to Azure.

## 12. EXISTING SCHEMA VALIDATION

None at any LLM boundary (§5). The pattern to extend: contract-style `__post_init__` validation (`contracts/_contract.py`, `Execution.__post_init__`) — plus Pydantic already in the stack for API models.

## 13. EXISTING FITNESS RULES

19 rules + 10 invariants, `PASS` today (306 warnings, all interface-purity). Mechanics: AST import graph (`rules.py:174-224`), two AST-over-source rules, one heuristic; ERROR blocks merge; grandfather ratchets proven by sensitivity tests. **Adding a rule = 3 edits** (dataclass in `*_rules.py`, append to `default_boundary_rules()`, sensitivity test in `tests/architecture/`; precedent: `LegacyAuditQuarantineRule`, `boundary_rules.py:245-308`). **Known evasion surface for the L1 rule to handle:** `importlib.import_module` is invisible to the import graph (and is used at `application_runtime.py:310`); unparseable files are silently skipped (`rules.py:202-205`); symbol-level (`from pkg import X`) needs its own AST pass. `INV-I1` (L1's invariant) is NOT_ENFORCED with a stale tracking string; `legacy_execution_boundary.ungated_surfaces()` (`:297`) already computes the runtime inventory a probe can assert empty. CI: `architecture.yml` runs the gate + sensitivity tests; `ci.yml` is vacuous (C4).

## 14. EXISTING TESTS PROVING L1/L13/L14

Strong and committed: audit chain integrity incl. tamper/torn-line/concurrency (`tests/platform/test_audit_runtime.py`); approval digest binding fail-closed probes (`tests/architecture/probes.py:26-99`); storage tenant isolation with real SQLAlchemy (`probes.py:102-204`); lease/fencing domain semantics (`tests/contexts/execution/test_domain.py:136-206,333-422`). **Absent: any test of the gateway's 13 checks, dispatcher/scheduler/recovery, credential broker, transport broker, SQL durable repos, migrations 0010–0013, replay inertness (V2).** The pieces for an in-memory end-to-end governed fixture all exist (`InMemory*` repos, `TestProviderAdapter`, `scheduler.tick()`); the fixture does not. `tests/conftest.py` autouse fixtures assume live Postgres (fail-soft); no pytest markers exist; `scripts/postgres_durability_harness.py` is the only committed real-DB harness (not pytest).

## 15. MINIMUM SET OF FILES THAT MUST CHANGE

**A. Quarantine to UNGOVERNED = 0 (~23 insertion points, no connector/route rewrites):**
1. `backend/connectors/base.py` — effect gate as first statement of `_execute()` (covers ~76 writes/15 connectors)
2. `backend/connectors/argocd.py` (`_post`), `backend/connectors/terraform.py` (`_run`), `backend/connectors/github.py` (`graphql_request`) — same gate, 3 sibling edits
3. Router-level `Depends(guard_…)` on 5 modules: `enterprise_infrastructure_routes.py`, `enterprise_git_routes.py`, `enterprise_cicd_routes.py`, `enterprise_delivery_routes.py`, `enterprise_pipeline_routes.py`
4. `guard_legacy_internal(...)` in ~10 fix-executors/incident-reporters (U5–U9) + `mission_skills/engine.py` (L1)
5. Guarded spawn helper covering 3 subprocess sites (`terraform.py`, `enterprise_execution_sandbox.py`, `execution/sandbox/interfaces.py`)
6. `backend/api/legacy_execution_boundary.py` / `legacy_connectivity_boundary.py` — enroll the new surfaces in the registries
7. Defect fixes (C5): `computer/computer_agent.py:103` fail-closed; `emergency_stop.is_active` dashboard calls; note (not silently "fix") the LOW-auto-approve policy — enrollment behind flags supersedes it
8. `orchestrator/handlers.py` — guard or delete the latent blind-execution path

**B. Fitness + invariants:**
9. `backend/platform/architecture/boundary_rules.py` — new ERROR rules: `ConnectorEffectGateRule` (AST: no call path into connector write verbs outside the gate/gateway; symbol-level pass; flags `importlib` use in the acting plane), enrollment-completeness rule (every mutating route module carries a guard dependency)
10. `backend/platform/architecture/invariant_tests.py` — I1 probe via `ungated_surfaces()` == ∅ + gate-refusal probe; fix stale I5 tracking text
11. `tests/architecture/` — sensitivity tests for each new rule (violating synthetic trees must fail)

**C. Harness spine (new package `backend/harness/`, thin, no new frameworks):**
12. `backend/harness/version.py` — immutable `HARNESS_VERSION` + component policy versions (loop/schema/context/tool-exposure/budget), stamped into every trace + audit detail
13. `backend/harness/loop.py` — `HarnessLoop`: mission → iteration → proposal → validation → governance → execution → observation → verification-boundary → continue/stop; explicit budgets (max_iterations, max_tool_calls, wall-clock; token budget where `LLMResponse.usage` exists) and typed stop reasons (completed / budget_exhausted / refused / invalid_output / interrupted / failed / unknown); checkpoints via existing `ExecutionService.checkpoint` when durable runtime present
14. `backend/harness/llm_boundary.py` — the harness's single LLM chokepoint wrapping `llm_provider.LLMService` (the clean stack): Pydantic schema validation on every structured output (invalid ⇒ explicit harness failure, never regex-extract-execute), `scrub_text` on assembled prompts, normalized `TokenUsage`
15. `backend/harness/trace.py` — attribution-grade trace records (14 required fields incl. harness version, gate decisions, correlation_id to audit) with deterministic redaction on the write path; honest replay marking (recipe + refs; unreconstructable inputs explicitly marked)
16. `backend/llm_provider/models.py` — add normalized `TokenUsage` (prompt/completion/total, cost via `cost_engine`) to `LLMResponse` (additive)
17. Migration `0014_harness_trace` — `cp_harness_trace` (append-only, correlation-keyed, redacted-at-write); Alembic chain extension
18. `backend/api/application_runtime.py` — compose harness spine with governed runtime (no behavior change when `CORTEX_DURABLE_URL` unset)

**D. Vertical slice (pending C1 decision — Docker):**
19. `backend/contexts/execution/infrastructure/adapters/connectors/docker.py` — catalog + translator (declaration-only, per the GitHub adapter pattern): `list_containers`/`inspect_container` (READ), `restart_container` (write, compensable), worker at an isolation tier sufficient for the write; **no new adapter seam**
20. `backend/api/` — commissioning path invoked deliberately (the four acts: register → validate → enable → trust) as an explicit, audited setup step; `first_governed_operation.py` extended to drive the slice
21. `.env.example` — document `CORTEX_DURABLE_URL` + Phase 5/6 switches (currently absent entirely)

**E. Tests (Levels 1–5 + failure injection):** new `tests/harness/` (budgets, stop reasons, schema rejection, redaction, versioning); new `tests/contexts/execution/test_governed_end_to_end.py` — the in-memory fixture (scheduler.tick → dispatcher → gateway → TestProviderAdapter) unlocking gateway/refusal/negative-path tests; `tests/architecture/` sensitivity tests; real-Postgres slice evidence via extended `scripts/postgres_durability_harness.py` pattern; failure-injection suite (malformed output, schema mismatch, tool timeout, governance denial, budget exhaustion, crash mid-loop, missing trace write, stale state).

**Explicitly NOT in 6.1** (Part K honored): no World Model, no CAE (only prompt scrubbing + recipe capture), no reconciliation/prediction engines, no assurance plane (verification *boundary* documented per Part H: the existing self-report verification is quarantined as untrusted input, the harness records "unverified claim" — it does not mint VERIFIED), no learning, no self-evolution, no auto-attribution, no new orchestrator/gateway/scheduler/audit/approval/memory systems.

---

## 16. SMALLEST SAFE CHANGE SEQUENCE (Part L discipline per step)

0. **Baseline commit(s)** of the uncommitted Phase 5 tree (C2) → every later diff reviewable.
1. **Quarantine** (A above) + fitness rules + sensitivity tests → UNGOVERNED = 0 by construction; gate enforces it forward. Verify: architecture gate, negative HTTP tests on the 5 routers, watcher-cycle test proving reporter writes refuse.
2. **Harness spine** (C) with unit tests → no consumer yet; zero behavior change.
3. **Docker governed adapter + commissioning** (D) → gateway can perform a real, reversible write on a scratch container.
4. **Vertical slice**: `HarnessLoop` drives model proposal ("restart scratch container X") → schema validation → governance (authorize/admit; deny paths exercised) → gateway → Docker → observation (read-after-write `inspect_container`) → verification boundary record → audit + trace with harness version.
5. **Failure injection + real-Postgres evidence** (Levels 4–5), then the Phase 6.1 verification report with VERIFIED / NOT VERIFIED / DEFERRED / BLOCKED per claim.

Estimated blast radius: ~30 files touched, 2 new packages (`backend/harness/`, one adapter module), 1 migration, no deletions except the latent `handlers.py` path (guard-or-delete decision at implementation time).
