# PHASE 11.0 — CortexPrime Enterprise Autonomy & Production Readiness Audit

- **Date:** 2026-09-09 · **HEAD audited:** `2c9452b` (branch `phase-1-foundation`, clean) · **Nature:** VERIFY → DISCOVER → DECIDE. No code, schema, test, frontend, dependency or configuration change. No ADR (no new architectural decision is established here; the decisions the audit surfaces are listed for the owner in §14).
- **Companion artefacts:** `docs/PHASE_11_0_CAPABILITY_MATRIX.md`, `docs/PHASE_11_0_GAP_REGISTER.md`, `docs/PHASE_11_0_ROADMAP.md`.
- **Evidence labels:** **FACT** = observed in the repository, a migration, a database, or an executed harness whose report is committed; **INFERENCE** = drawn from facts; **RECOMMENDATION**; **UNKNOWN** = the repository does not settle it.
- **Method:** repository census (3,829 tracked files; 1,162 backend `.py`; 1,873 frontend files; 323 test modules; 110 ADRs; 268 docs), targeted `git grep` traces per dimension, the real head database (`cortex_p1014_legacy`, 57 tables at `0025`), and the committed verification reports of Phases 5–10 (each of which executed its claims against real PostgreSQL, real Redis and a real k3d cluster). Where this audit relies on a prior phase's executed result, it cites that phase's report/ADR rather than re-running it.

---

## 1. Executive summary

**FACT — CortexPrime is two products in one repository.**

1. **The governed engine** (`backend/contexts/*`, `backend/world`, `backend/assurance`, `backend/intelligence`, `backend/platform`, `backend/auth`, `backend/api/product`; 22 `cp_*`/`cw_*` tables, every one tenant-scoped). Built in Phases 5–10 and verified by 43 executed harness scripts against real PostgreSQL, Redis and a live k3d Kubernetes cluster. It can, today: read and watch a real cluster through one governed path (ADR-082/083); corroborate evidence from two sources (ADR-084); run a read-only CrashLoopBackOff investigation with five competing hypotheses and eliminate the misleading one by evidence (ADR-085); bind a human approval to a specific action digest with separation of duties and scoped authority (ADR-090/098/099/100); execute **one** commissioned irreversible write — `kubernetes.workload.rollout_restart` — in an out-of-process CONTAINED worker holding no platform credentials (ADR-089/091); verify the result by an **independent** read and record an Assurance verdict (ADR-091); replay the recorded execution inertly; and expose all of it through a tenant-scoped product API with an investigator workspace and an approval inbox (ADR-094–097). Its guarantees are explicit and honest: at-least-once, never exactly-once; INSUFFICIENT_EVIDENCE is a first-class verdict.

2. **The V1 platform** (`backend/agents` 13 agents, `backend/connectors` 25 modules, mission runtime, replay, memory/knowledge/learning, ~185 routers, 139 frontend pages). LLM-backed, feature-broad, tenant-unaware (35 of 57 tables have no `tenant_id`; 54 repositories are grandfathered out of the tenancy ratchet), with its execution paths **quarantined** behind `guard_legacy_execution` since Phase 9.11 and much of its surface mock-data or scaffold (Phases 10.21–10.29 retired 17 models/routes that were never reachable).

**FACT — The governed loop is real but has no production trigger.** `InvestigationEngine` is constructed only in `scripts/phase8*_harness.py`; the Kubernetes watch driver (`backend/api/kubernetes_watch_driver.py`) has no runner in `backend/main.py` or any worker; the intelligence model port is `provider='scripted'` (`backend/intelligence/application/model_boundary.py:16-18`) because no real model credential has ever authenticated (ADR-049, Phase 5.5 blocker, still open). No real external signal enters the governed plane in production. The product API reads investigations that only harnesses create.

**INFERENCE — Verdict.** CortexPrime today is a **verified governed-execution engine with a proven single vertical (Kubernetes CrashLoop → restart), wrapped in a large, mostly-unverified V1 platform**. It is not yet an autonomous operations platform, because the loop's front half (signal → detect → trigger) and its brain (a real model behind the boundary) are not connected in production, and because the V1 surface that a customer would actually touch is tenant-unaware. Deployed to a real enterprise tomorrow it would not "fail" at execution — it would fail at *ingress*: nothing would happen unless an engineer ran a script, and the V1 dashboards the customer sees would show data that is either theirs, everyone's, or synthetic (§9).

---

## 2. Current product truth (what exists, classified)

| Capability area | Classification | Evidence (FACT unless marked) |
|---|---|---|
| Governed Kubernetes READ (3 ops) + WATCH | **REAL_PRODUCTION_VERIFIED (harness-triggered)** | ADR-082 49/49 real HTTPS; ADR-083 84/84 real k3d watch with 410 recovery, crash-safety by `os._exit(9)`; operations `kubernetes.pods.list/pod.get/deployment.get` (`git grep operation="kubernetes.`) |
| Governed Kubernetes WRITE (1 op) with independent verification | **REAL_PRODUCTION_VERIFIED (harness + product API)** | ADR-091 95/95: generation 1→2, exactly one provider write, outcome from an independent read; ADR-096 121/121 through `POST /investigations/{ref}/remediation/…` and `/approvals/{id}/execute` |
| Human approval, separation of duties, scoped authority, grants, membership, tenant records | **REAL_INTERNAL_VERIFIED (governed plane)** | ADR-097–103; harnesses 10.4–10.10 at 135/121/118/107/107; re-run at full counts in 10.29 and 10.31 |
| Evidence-backed investigation (hypotheses, elimination, calibration, experience memory) | **REAL_INTERNAL_VERIFIED, scripted proposer** | ADR-073–078; `model_boundary.py:151-165` `GovernedModelProposalPort(provider_label="scripted")`; hypotheses come from scenario tables (e.g. `CRASHLOOP_HYPOTHESES`, ADR-085), not a model |
| World plane (bitemporal facts, belief, corroboration, lineage) | **REAL_INTERNAL_VERIFIED** | ADR-063–070; `cw_observation/fact/verification/reasoning/investigation` migrations 0015–0019 |
| Product API + investigator workspace + approval inbox | **REAL_INTERNAL_VERIFIED, not navigable** | `backend/api/product/*` (20 routes, all tenant-scoped); `frontend/app/{investigator,approvals}`; **no link from `CortexSidebar.tsx`** — only `components/investigator/Workspace.tsx:60` links to itself |
| Real-signal ingestion into the governed plane | **SCAFFOLD (production) / REAL (harness)** | watch driver exists, no runner (§3) |
| V1 signal ingestion (`/ingest/prometheus`, `/ingest/grafana`, `/ingest/loki`, webhooks for GitHub/GitLab) | **PARTIAL / SIMULATED persistence, UNAUTHENTICATED** | `enterprise_infrastructure_routes.py:232-250`; correlator persists incidents to a JSON file (`enterprise_alert_correlator.py:44,86-114`); no tenant; no auth dependency on any of the 38 routes across the three modules (§7) |
| V1 mission runtime, planner, 13 agents, tool selection | **REAL_INTERNAL (LLM-backed), execution QUARANTINED** | `backend/agents` (13 `*Agent` classes); LLM routers in 7 agent/service files; `guard_legacy_execution` on `/api/executions/run` and mission routes (`execution/routes.py:220`, `mission/routes.py:254`); Phase 9.11 "0 ungated surfaces" |
| V1 connectors (25) | **REAL CLIENT CODE, QUARANTINED; 2 spawn subprocesses** | `backend/connectors/*`; `terraform.py`, `effects.py` use `subprocess`; Phase 9.0: Kubernetes connector read-only, Terraform all-write; none reachable through governance |
| Mission replay (Redis 72 h + PostgreSQL) | **REAL_INTERNAL_VERIFIED** | ADR-118, migration 0025, real write/read/failure tests |
| V1 memory (episodic/semantic/reflection, pgvector ivfflat) | **REAL_INTERNAL (V1 agents)**; not tenant-scoped | migrations 0001; ADR-120 index proof; `episodic_repository.py:74-122` real `<=>`/FTS |
| Learning engine / pattern detector | **SCAFFOLD → UNKNOWN influence** | `backend/learning/detector.py` (`PatternDetector.detect_*`); no evidence any detected pattern changes a decision (§13) |
| Knowledge graph (Neo4j) | **OPTIONAL / UNKNOWN** | 32 files reference `neo4j`; driver not installed on the audit host ("neo4j driver not installed — cognitive graph disabled" at import); runtime index creation only there |
| Cost tracking | **PARTIAL** | `cost_tracking` per mission/user (ADR-114 repaired writes); no `tenant` in `cost_engine.py` (0 matches); governed loop has no cost (no model calls) |
| Enterprise operations API, org directory, IAM, TenantManager, v2 models | **DEAD → RETIRED** | ADR-104/106/107/115/116/119 |
| Observability of the platform itself | **PARTIAL** | `/metrics` route (`metrics_routes.py:30`); governed `platform/observability/metrics.py:3` — "No Prometheus, no OpenTelemetry, no StatsD, and no exporter"; harness counters only |
| Documentation | **OVERCLAIMED in places** | README:3 "An autonomous DevOps operating platform"; `architecture.md`, `api.md` corrected only where 10.29 retired sections (§27) |

---

## 3. Architecture map (as it is)

```
                 V1 PLATFORM (LLM-backed, tenant-unaware, execution quarantined)
  Prometheus/Grafana/Loki/GitHub/GitLab webhooks ─▶ enterprise_*_routes ─▶ alert correlator (JSON file)
  139 pages ─▶ 185 routers ─▶ mission runtime ─▶ 13 agents ─▶ llm_router ─▶ [tools/connectors GUARDED]
  event_bus (in-memory, 10k ring) ─▶ replay_store (Redis 72h + PG 0025) ─▶ replay routes
  V1 memory (pgvector) ◀─▶ agents        cost_engine ─▶ cost_tracking      learning/PatternDetector

                 GOVERNED ENGINE (tenant-scoped, fail-closed, harness-triggered)
  [no production ingress] ─▶ WATCH driver (harness) ─▶ World: cw_observation → cw_fact (bitemporal) → belief
        ─▶ Investigation (scripted proposer) → hypotheses/evidence/verdict (cw_investigation, cw_reasoning)
        ─▶ Product API (/investigations, /approvals, /authority, /world) ─▶ investigator + approvals UI
        ─▶ Approval (cp_approval, action digest, SoD, scoped grants) ─▶ Execution (cp_execution, outbox, lease, idempotency)
        ─▶ CONTAINED worker (own container, no platform creds) ─▶ Kubernetes (1 write op) ─▶ independent READ ─▶ Assurance (cw_verification)
```

**FACT** — the two planes share PostgreSQL and Redis but not tables, not tenancy, not events (V1 `event_bus` vs governed `cp_outbox`), not approvals (`approval_center_routes` vs `cp_approval`), not governance (`backend/governance` decision pipeline vs `backend/auth` authority), not memory (V1 pgvector tables vs Phase 8 experience memory), not incidents (JSON correlator vs `cw_investigation`). The architecture gate (`tests/architecture`, 155 rules) forbids the governed planes from reaching the V1 execution paths and vice-versa (BND-* rules, Phase 9.0 bypass scan).

---

## 4. Thirty-dimension scorecard

GREEN = production-credible · YELLOW = partial · RED = major gap · GRAY = insufficient evidence. Each score cites the evidence that fixes it.

| # | Dimension | Score | Evidence |
|---|---|---|---|
| 1 | Production signal ingestion | **RED** | Governed: no production ingress (§3). V1: `/ingest/*` endpoints exist but persist to a JSON file with no tenant and **no authentication** (§7). A real event cannot become an actionable governed event today. |
| 2 | Event fabric | **YELLOW** | Governed outbox with dead-letter, leases, idempotency (`cp_outbox/cp_node_lease/cp_idempotency`, migrations 0010/0011; `outbox_publisher.py`); watch at-least-once with crash-safety proven. V1 `event_bus` is an in-memory 10k ring (`event_bus.py:42`) — at-most-once, lost on restart, replay only via the store. |
| 3 | Detection | **RED** | No governed detection. V1 alert correlator groups by service into a file store. The only "detection" that led to a governed investigation is harness code reading a CrashLoop. |
| 4 | Investigation | **YELLOW** | Engine proven (ADR-073/075/085) with evidence traces and eliminations; proposer scripted; triggered only by scripts. |
| 5 | Root cause / causal reasoning | **YELLOW** | Real: competing hypotheses, evidence scoring, elimination of the misleading OOM hypothesis by an independent instrument (ADR-085), corroboration lineage (ADR-084). Missing: deployment/config/code-change correlation, topology; hypotheses are scenario tables, not derived. |
| 6 | Planning | **YELLOW** | Governed action carries risk class, reversibility, verification requirement, autonomy ceiling, resource scope (ADR-081/079). No general root-cause→plan generation; one capability; blast radius asserted by the harness, not computed. |
| 7 | Agent orchestration | **YELLOW/RED** | 13 V1 agents are LLM wrappers with no governed tool access (quarantined); governed plane has no agents — it has a scripted proposer. |
| 8 | Tool / connector execution | **YELLOW** | Governed: 4 Kubernetes ops (3 read, 1 write) through one gateway, fail-closed credentials, contained worker. V1: 25 connectors, real client code, none reachable through governance; Terraform/Docker/shell spawn subprocesses. |
| 9 | Autonomous remediation | **YELLOW** | The loop INCIDENT→PLAN→APPROVE→EXECUTE→VERIFY works for one vertical (ADR-091/096) — with a human approval and a script at the front. No trigger, no autonomy above A1 exercised in production (ADR-079 ladder exists). |
| 10 | World-state verification | **GREEN (governed)** | Independent read → `WorldVerification` verdict; a killed worker fabricated no success (ADR-091 "real killed process"). V1 execution declares success from responses — quarantined. |
| 11 | Governance | **GREEN (governed) / RED (V1)** | Centralized in `backend/auth` + `contexts/connectivity`; 10.5–10.14 at full counts, re-run 10.29/10.31. V1 routes: 89/96 modules never mention tenant (Phase 10.0 Part I). |
| 12 | Tenancy / isolation | **GREEN (governed) / RED (V1)** | 22 tenant-scoped tables vs 35 without; Redis replay keys `cx:replay:events:{execution_id}` carry no tenant; V1 memory/knowledge shared across tenants. |
| 13 | Memory | **YELLOW** | Real pgvector retrieval in V1 (`<=>`); Phase 8 experience memory proven in harness reuse (ADR-077). No tenant scope in V1 memory. |
| 14 | Knowledge | **YELLOW/GRAY** | `knowledge_entries` with pgvector but **no vector index** on either side (ADR-120 limitation); Neo4j optional and absent here; Chroma referenced in 4 files + Helm PVC — three vector/graph stores, no owner. |
| 15 | Learning | **RED** | Calibration/drift detection exist (ADR-078, `calibration.py:356 DriftDetector`); no production path feeds outcomes back; `learning/detector.py` patterns have no consumer that changes behaviour (§13). |
| 16 | AI observability | **RED** | No exporter for the governed plane; V1 `/metrics` exists; no LLM latency/token/cost per investigation (no LLM in governed loop); reasoning trail (`cw_reasoning`) is the one strong explainability asset. |
| 17 | AI evaluation | **YELLOW** | 43 scenario harnesses with negative matrices are a real, executed eval system for the governed engine; no model-quality evals (nothing to evaluate — scripted); V1 agents have none. |
| 18 | Failure recovery | **YELLOW** | Governed: outbox retry/dead-letter, fencing with two instance ids (ADR-092), crash markers. V1: in-memory bus loses events on restart; recovery engine V1 unverified. |
| 19 | Idempotency | **YELLOW (honest)** | At-least-once everywhere proven; `cp_idempotency`, approval `identity_digest`, effect `idempotency_key`; exactly-once never claimed. |
| 20 | Security | **YELLOW** | JWT + role checks + tenant role checks (`auth/dependencies.py:51-135`), rate limiter middleware (`main.py:1398`), guardrails engine; **`legacy_network_inventory.py:60` documents "a complete SSRF primitive"** in a V1 surface; no prompt-injection defence anywhere (governed plane has no LLM; V1 agents feed untrusted data to LLMs); 4 baseline-failing `test_auth_enforcement` cases on legacy `/execute`. |
| 21 | Operability | **YELLOW** | Backups (script + Helm CronJob, real); readiness `verify_durability`; entrypoint migrates; health routes. Helm `worker-deployment.yaml:52-54` configures **Celery**, which the backend does not contain (0 files) — stale. |
| 22 | UX | **RED** | 139 pages; 5 product pages exist but are not in the sidebar; Operations Center is ten mock panels behind a dead `/operations/*` nav base (10.27 C2). |
| 23 | API platform | **YELLOW** | Product API v1 consistent and tenant-scoped; V1 API mixes three path vocabularies, `/api/api/` double prefix (diagnostics), file-existence tests as contract tests. |
| 24 | Data architecture | **YELLOW** | Alembic canonical and clean (ADR-109/120); but JSON-file stores (`alert_incident_history.json`), in-memory identity (`security_center/identity.py`), Chroma/Neo4j/pgvector all present. |
| 25 | Cost | **RED** | Per-mission LLM cost only (V1), no tenant, nothing for the governed loop; "what did this incident cost" is unanswerable. |
| 26 | Customer value | **RED** | No MTTR/MTTD/automation-rate metric exists anywhere in the repository. |
| 27 | Deployment | **YELLOW** | Clean-clone import/migrate/boot proven (ADR-116); Docker/compose/Helm exist; Helm unrendered here (no `helm`), worker template stale; compose ships RabbitMQ used by 10 V1 files. |
| 28 | Testing | **YELLOW** | 6,919 tests, 75 baseline failures (17 benchmarks, sandbox, e2e, auth-enforcement); only 3 modules use a real migrated PostgreSQL; 110 modules mock-heavy; harness scripts are the real test of the engine. |
| 29 | Documentation | **RED** | 268 docs; README tagline overclaims; Phase reports honest; guides/architecture describe V1 as if shipped (§27). |
| 30 | Strategic differentiation | **YELLOW** | Genuinely real: governed execution with independent verification, evidence-based investigation with honest uncertainty, bitemporal world. Vision: everything upstream of the trigger and the model. |

---

## 5. Core loop matrix (mandatory)

| Stage | Current implementation | Evidence | Reality | Gap |
|---|---|---|---|---|
| Real signal | V1 ingest endpoints (Prometheus/Grafana/Loki, GitHub/GitLab webhooks); governed WATCH driver | `enterprise_infrastructure_routes.py:232-250`; `kubernetes_watch_driver.py`; ADR-083 | V1 path is real HTTP into a JSON file, tenant-less; governed watch is real but runs only from `scripts/phase93_*` | **No production ingress to the governed plane** |
| Detection | V1 alert correlator; harness reads CrashLoop state | `enterprise_alert_correlator.py`; ADR-085 | No governed detector; V1 detection unverified against real alerts | **No governed detection; no trigger** |
| Investigation | `InvestigationEngine` + `ContextAssembler` + scripted `ModelPort` | `backend/intelligence/*`; `scripts/phase82-85*` | Real engine, real evidence, scripted hypotheses | **No production caller; no model** |
| Root cause | Differential diagnosis, evidence scoring, elimination, calibration | ADR-075/078/085 | Real for the scenario table it is given | **No causal sources beyond K8s state + Prometheus corroboration; no deployment/config/code correlation** |
| Planning | Capability profile with risk/reversibility/verification/autonomy ceiling | ADR-081/079 | One capability, plan = "restart" | **No plan generation; no blast-radius computation** |
| Governance | Tenant, membership, scoped authority, grants | ADR-098–103 | Real, enforced, re-verified | V1 surface outside it |
| Approval | `cp_approval`, action digest, SoD, inbox UI | ADR-090/096/097/113 | Real, product-reachable | UI not navigable |
| Execution | Gateway → CONTAINED worker → Kubernetes | ADR-089/091 | Real, 1 op, 0 platform creds in worker | **1 write capability; credentials for anything else blocked (ADR-049)** |
| World-state verification | Independent read → Assurance verdict | ADR-091/096 | Real | — |
| Recovery | Outbox dead-letter, fencing, crash markers; replay inert | ADR-092/118 | Real for the governed path | No rollback plan object; V1 recovery unverified |
| Learning | Experience memory, calibration, drift detector | ADR-077/078 | Real in harness reuse | **Nothing in production feeds outcomes back or reads them** |

---

## 6. Five end-to-end scenario traces (architecture tracing only)

| # | Scenario | Signal | Detect | Investigate | Root cause | Plan | Approve | Execute | Verify | Resolve | Learn | **Stops at** |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | Deployment raises error rate | Prometheus alert → V1 `/ingest/prometheus` (file); governed: none | V1 correlator groups; governed: none | governed engine has Prometheus corroboration (ADR-084) but no deployment-correlation source | — | — | — | — | — | — | — | **DETECT** (governed) — no trigger; V1 stops at CORRELATE with no remediation |
| 2 | Database connectivity degradation | no connector or capability observes a customer database | — | — | — | — | — | — | — | — | — | **SIGNAL** |
| 3 | Kubernetes workload CrashLoop | governed WATCH (harness) | harness reads pod state | 5 hypotheses, OOM eliminated (ADR-085) | evidence-scored | rollout_restart with risk/verification (ADR-081) | human, SoD, scoped (ADR-096) | contained worker, 1 write (ADR-091) | independent read, SUPPORTED (ADR-091) | recorded, replay inert | experience memory in harness | **TRIGGER** (no production process starts it) and **LEARN** (not fed back in production) |
| 4 | Credential expiry breaks a service | no credential-health signal; broker refuses expired/absent creds fail-closed | — | — | — | — | — | — | — | — | — | **SIGNAL** |
| 5 | Runaway cost / resource | V1 `cost_engine` tracks V1 LLM spend only; no cloud-cost signal | — | — | — | — | — | — | — | — | — | **SIGNAL** |

**INFERENCE** — exactly one scenario reaches EXECUTE and VERIFY, and it does so only when a human runs a script. That is the honest boundary of "autonomous" today.

---

## 7. Red-team findings

| Question | Finding | Class |
|---|---|---|
| Can a fake signal trigger a mission? | Governed: no signal triggers anything. V1: **FACT** — `enterprise_infrastructure_routes.py` (15 ingest/prometheus/grafana/loki routes), `enterprise_github_routes.py` (13, incl. `POST /webhook` with no signature/HMAC check) and `enterprise_gitlab_routes.py` (10) declare **no auth dependency at router or route level**: anyone who can reach the API can inject alerts/incidents into the file-backed correlator and V1 dashboards. They do not reach execution (quarantined). | **P1** (unauthenticated V1 ingress), P0 for the governed ingress design |
| Can untrusted log content manipulate an agent? | Governed: no model in the loop; evidence is normalized and digested (`normalization.py:3-5,144`). V1: agents send fetched content to LLMs with **no injection defence** (grep: none); V1 execution is guarded, so the blast radius today is advice/UI, not action. | P1 (must be solved before a real model enters the governed boundary) |
| Can an agent call a privileged connector without approval? | Governed: no — gateway, authority, approval digest, worker binding all fail-closed (ADR-088–091; 15+38-case negative matrices at 0 mutations). V1: `guard_legacy_execution` on every execution route (Phase 9.11 "0 ungated surfaces"). **FACT** — the 4 baseline-failing `test_auth_enforcement[/execute]` cases receive **503 SERVICE_UNAVAILABLE** from the guard *before* authentication runs (test expects 401): the path is closed, not bypassed; the tests predate the quarantine and should be re-pointed at the guard's contract. | P3 (test expectation), no bypass |
| Can a tenant see another tenant's memory? | **Yes, in V1**: episodic/semantic/reflection, knowledge, replay have no tenant column or key namespace (35 tables; `cx:replay:events:{execution_id}`). Governed: no (`cw_*` scoped; World queries tenant-scoped, Phase 10.0 Part I). | **P0** for any multi-tenant deployment of the V1 surface |
| Can Redis loss destroy required state? | Replay hot window lost (PostgreSQL copy kept since ADR-118); replay `sequence` counter resets → duplicate sequences (ADR-118 limitation); V1 pub/sub, runtime, auth caches lost. Governed state is PostgreSQL-only. | P2 |
| Can PostgreSQL loss cause false success? | Governed: writes are refused, not faked (ADR-091: killed worker produced no success; ADR-114 class fixed). V1 `cost_engine` and replay swallow DB failures (now at WARNING). | P2 |
| Can a provider return 200 while the action failed? | Governed: success requires an independent read (ADR-091). V1 connectors: yes — response-as-success — quarantined. | P1 if any V1 connector is ever un-quarantined without adopting Assurance |
| Can duplicate events execute actions twice? | Governed: idempotency table + approval identity digest + action digest; at-least-once documented; duplicates refused at the approval/execution identity, not exactly-once. | P2 (document; prove per capability as capabilities grow) |
| Can stale knowledge cause an unsafe remediation? | Governed: freshness/staleness verdicts (ADR-066) make STALE a verdict; no capability acts on knowledge. V1: knowledge feeds LLM advice only. | P2 |
| Can an approval be bypassed? | No, in the governed plane (ADR-090 closed the REQUIRE_APPROVAL→ALLOW downgrade hole; SoD; scoped grants; 36+38-case matrices). V1 `approval_center_routes` is a separate, unenforced surface. | P1 (retire/fence V1 approval center) |
| Can a worker execute under the wrong tenant? | No: worker binds to an execution whose tenant is in the digest; 17 binding attacks refused (ADR-089). | — |
| Can an agent hallucinate a resource and mutate something else? | Governed: action digest names the resource; approval binds to it (ADR-090 — the billing-api/payments-api hole was found and closed). V1: agents cannot execute. | — |
| Can a failed execution be marked successful? | Governed: no (independent verification; UNKNOWN is a verdict). V1: yes by design; quarantined. | P1 (same as above) |
| Can the system lose the evidence behind a decision? | Governed: `cw_reasoning`/`cw_verification` are append-only ledgers (ADR-069/070). V1 mission replay: durable since ADR-118. | — |
| Can an operator understand why an autonomous action happened? | For the governed vertical: yes — evidence refs, hypotheses, verdicts, approval record, execution record, verification (product API `/timeline`, `/evidence`, `/assurance`). For anything V1: partially, via replay. | — |
| Untrusted V1 surface: SSRF | `legacy_network_inventory.py:60` — "This is a complete SSRF primitive" for a V1 route with only a prefix regex control. | **P1** |

---

## 8. Production blockers (P0) and the "deploy tomorrow" answer

**Where would it fail first?** At **ingress**: no production process observes anything, so the governed engine idles; the customer sees the V1 surface.
**What would the customer experience?** A large UI in which the Operations Center is mock data, investigator/approvals are unreachable without a URL, incidents come from a file store without tenancy, and any second tenant can read the first tenant's memory/replay/knowledge through V1 routes.
**Smallest sequence that eliminates those failures (RECOMMENDATION, ordered by dependency):**
1. Decide the V1 surface's fate per tenant safety (§14, D1) — fence or scope it before any multi-tenant deployment.
2. A production trigger: run the existing governed WATCH driver as a supervised worker (it already exists, is leased/fenced and crash-safe) and open one governed webhook ingress (Alertmanager-compatible) into World observations.
3. A governed detector that opens investigations from World facts (the CrashLoop rule already exists in harness form).
4. A real model behind `GovernedModelProposalPort` with credentials via the existing Vault adapter — with injection defences before it, because untrusted evidence will then reach a model.
5. Link the product pages into navigation.

---

## 9. Roadmap summary (detail in `PHASE_11_0_ROADMAP.md`)

- **P0 — blockers:** G-01 tenant-unsafe V1 surface (decision D1); G-02 no production ingress/trigger; G-03 no governed detection; G-04 no real model behind the boundary (credential blocker).
- **P1 — core product:** G-05 product pages not navigable; G-06 injection defences before a model; G-07 V1 approval centre and SSRF primitive fenced; G-08 second and third governed capabilities (read-mostly: deployment history, events, logs corroboration); G-09 rollback/compensation plan object; G-10 cost and latency per investigation; G-11 baseline test failures classified and either fixed or quarantined.
- **P2 — differentiation:** causal sources (deployment/config/code change correlation), autonomy ladder exercised (A2+) with earned authority, learning fed back in production, model-quality evals.
- **P3 — polish:** Helm worker template truth, `/api/api` prefix, three path vocabularies, doc overclaims, Chroma/Neo4j ownership.
- **P4 — future:** multi-provider capability fabric (GitHub writes, cloud), org federation.

---

## 10. Strategic opportunities (INFERENCE, grounded)

1. **The verification story is real and rare.** Independent world-state verification with honest INSUFFICIENT_EVIDENCE verdicts, a bitemporal world, and approval bound to an action digest — these exist, are tested by executed negative matrices, and are the product's defensible core.
2. **The engine is model-agnostic by construction.** The scripted proposer means the whole loop was proven without a model; putting a model behind the boundary changes the *quality* of hypotheses, not the safety of execution.
3. **One vertical is done end-to-end.** Kubernetes CrashLoop → restart is a credible first product story if it gets a trigger and a front door.

## 11. Known limitations of this audit

- Harness results are cited from committed reports, not re-executed in this phase (no implementation, no provider calls).
- Helm charts were not rendered (no `helm` on the host); CI workflows exist but their remote status is not visible here.
- Frontend behaviour was traced by code, not by driving a browser.
- "Real customer value" metrics: none exist; nothing to measure.

## 12. Explicit UNKNOWNs

U-1 *resolved →* FACT: V1 ingest/webhook routes have no auth dependency (§7). U-2 *resolved →* FACT: the guard refuses with 503 before auth (§7). U-3 Whether `VaultCredentialAdapter` has ever authenticated against a real Vault. U-4 Whether the Helm chart renders/deploys (worker template references Celery). U-5 Whether the GitHub governed capabilities described in ADR-080 are still registered (no `operation="github.*"` found by grep). U-6 Neo4j/Chroma: which, if either, is intended. U-7 Whether any V1 agent output has ever been validated against ground truth.

## 13. Learning: does storage influence behaviour? (dimension 13 detail)

**FACT** — Phase 8.4 reused prior investigation experience in harness (`phase84_differential_harness.py:345 reuse_engine`); ADR-078 calibrates confidence from outcomes; `DriftDetector` exists. **FACT** — no production code path constructs the engine, so no production decision has ever been influenced by stored experience. **FACT** — `backend/learning/detector.py` `PatternDetector` produces patterns; grep finds no consumer that alters routing, planning or execution. **Classification: SCAFFOLD in production, REAL in harness.**

## 14. Architecture decisions required (for the owner; not made here)

- **D1 — V1 surface tenancy:** scope it (add tenant to 35 tables and 54 repositories), fence it (single-tenant deployments only), or retire it feature by feature. This gates every multi-tenant claim.
- **D2 — Model boundary credentials:** how a real model credential enters production (Vault adapter path) — the Phase 5.5 blocker.
- **D3 — Governed ingress standard:** which external signal format is the first governed webhook (Alertmanager, CloudEvents, Kubernetes events).
- **D4 — Knowledge store:** pgvector vs Chroma vs Neo4j — one owner.
- **D5 — Autonomy ceiling in production:** whether any capability may run above A1 without a human, and under what earned-authority evidence (ADR-079 defines the ladder; nothing exercises it).

No ADR is written for these: each is a product/architecture choice the repository cannot make for itself.
