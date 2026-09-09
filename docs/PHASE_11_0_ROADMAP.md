# PHASE 11.0 — Dependency-aware Roadmap (Phase 11+)

Companion to `docs/PHASE_11_0_ENTERPRISE_AUTONOMY_AUDIT.md` and `docs/PHASE_11_0_GAP_REGISTER.md` (HEAD `2c9452b`, 2026-09-09). Nothing here is implemented; every phase follows the repository's own discipline (discovery → implementation → verification → ADR; stop on ambiguity). Framework candidates are named only where a gap would otherwise tempt custom infrastructure; **no dependency is added or proposed for installation by this audit** — each candidate is a question for its phase's discovery.

## Decisions that gate the roadmap (owner decisions, not made here)

| ID | Decision | Gates |
|---|---|---|
| D1 | V1 surface tenancy: scope / fence (single-tenant only) / retire per feature | 11.1, every multi-tenant claim |
| D2 | How a real credential (model, Vault) enters production | 11.5, 11.6 |
| D3 | First governed ingress standard (Alertmanager webhook, Kubernetes events, CloudEvents) | 11.3 |
| D4 | One knowledge/vector store (pgvector vs Chroma vs Neo4j) | 11.12 |
| D5 | Production autonomy ceiling and earned-authority evidence | 11.11 |

## Phases

### 11.1 — Fence the V1 surface and expose the product surface (P0/P1)
- **Objective:** make the deployable product safe and visible: authenticate or disable the 38 unauthenticated V1 ingest/webhook routes (G-06), fence the SSRF-primitive route (G-07), retire or fence `approval_center_routes` (G-24), add sidebar navigation to `/investigator` and `/approvals` (G-05), and record the D1 decision.
- **Why:** these are the first things a real customer would hit (audit §8).
- **Dependencies:** D1.
- **Expected evidence:** unauthenticated request to each fenced route → 401/404; negative matrix at 0 provider writes; sidebar renders the two links; 10.4–10.14 harnesses unchanged.
- **Acceptance:** zero V1 ingress reachable without auth; product pages navigable; ADR.
- **Risks:** breaking a V1 dashboard that silently depended on unauthenticated push.
- **Framework candidates:** none needed (FastAPI dependencies, existing `require_user`).
- **Complexity:** low. **Architecture:** no. **Schema:** no. **Providers:** no. **Governance:** no (fences only).

### 11.2 — Production runner for the governed WATCH driver (P0)
- **Objective:** run `backend/api/kubernetes_watch_driver.py` as a supervised, lease-fenced process so World observations arrive without a script (G-02).
- **Why:** the engine has no ingress; the driver already exists and is crash-safe (ADR-083).
- **Dependencies:** none beyond a KUBECONFIG credential path (already proven).
- **Expected evidence:** observations accumulating in `cw_observation` from a real cluster with the app booted normally; kill/restart resumes from the recorded position; two instances → one leader.
- **Acceptance:** at-least-once observation stream from boot; no new authority; architecture gate 155.
- **Risks:** process supervision on the deployment side (Helm worker template is stale, G-19).
- **Framework candidates:** the existing lease/fencing (`cp_node_lease`) — no scheduler library needed; if a job runner is later wanted, evaluate APScheduler vs a Kubernetes CronJob/Deployment (already the Helm model).
- **Complexity:** low–medium. **Architecture:** no (existing component). **Schema:** no. **Providers:** read-only. **Governance:** no.

### 11.3 — First governed external ingress (P0)
- **Objective:** one authenticated, tenant-bound webhook that turns an external signal into a World observation (G-02, D3).
- **Why:** without it, only Kubernetes-watchable facts exist.
- **Dependencies:** D3; 11.1 (auth pattern).
- **Expected evidence:** a real Alertmanager (or chosen source) delivery recorded as an observation with source lineage and tenant; replay of the same delivery deduplicated by identity; negative matrix (wrong tenant, unsigned, replayed, malformed) at 0 side effects.
- **Acceptance:** ADR naming the ingress contract; at-least-once with identity; no bypass of World ingestion.
- **Risks:** inventing a second event model; the answer must be an Observation, not a new table.
- **Framework candidates:** CloudEvents envelope (spec, not a dependency); Alertmanager's webhook schema (documented format).
- **Complexity:** medium. **Architecture:** yes (ingress boundary). **Schema:** probably no (observations). **Providers:** none. **Governance:** yes (tenant binding at ingress).

### 11.4 — Governed detection: rules that open investigations (P0)
- **Objective:** a detector over World facts that opens `cw_investigation` for the CrashLoop rule (already harness code) and records why (G-03).
- **Dependencies:** 11.2 or 11.3.
- **Expected evidence:** a real CrashLoop on k3d → an investigation appears in the product API with evidence refs, without any script; duplicate facts do not open duplicate investigations (identity).
- **Acceptance:** first autonomous DETECT; A0 autonomy only (no action).
- **Risks:** detector thresholds are policy — keep them in governed policy objects, not code constants.
- **Framework candidates:** none (rule evaluation over facts); revisit CEP libraries only if rule count grows.
- **Complexity:** medium. **Architecture:** yes (new production caller of the engine). **Schema:** no. **Providers:** no. **Governance:** yes (who may open investigations).

### 11.5 — A real model behind the boundary, with defences (P0/P1)
- **Objective:** wire one real model provider through `GovernedModelProposalPort` using the credential broker (D2, G-04, G-13), with untrusted-content handling before evidence reaches the model (G-08), and per-call latency/token/cost recorded (G-11/G-12).
- **Dependencies:** D2; 11.4 (something to investigate).
- **Expected evidence:** trace-evidence contract still enforced (`llm_boundary`); injection corpus (evidence containing instructions) does not alter proposals' authority; cost/latency rows per investigation; a killed model call yields INSUFFICIENT_EVIDENCE, not a fabricated hypothesis.
- **Acceptance:** model-produced hypotheses pass the same calibration harness the scripted ones did.
- **Risks:** the single largest safety change in the roadmap; must land behind A0/A1 only.
- **Framework candidates:** the existing `llm_provider` package (already supports OpenAI/Azure/Anthropic env keys) for transport; for evaluation, the existing harness pattern first; consider promptfoo/inspect-style scenario runners only if the harness cannot express model-quality assertions.
- **Complexity:** high. **Architecture:** yes (model boundary goes live). **Schema:** maybe (cost per investigation). **Providers:** model provider. **Governance:** yes.

### 11.6 — Second and third governed capabilities (P1)
- **Objective:** read capabilities that give causal reasoning its sources — Kubernetes events, deployment history/rollout status, pod logs tail — through the existing profile/registration path (G-09).
- **Dependencies:** none for Kubernetes; D2 for anything else.
- **Expected evidence:** each capability registered with risk/reversibility/verification; real reads on k3d; digests in the capability catalog; no new gateway.
- **Acceptance:** investigations cite the new sources; zero writes.
- **Complexity:** medium. **Architecture:** no. **Schema:** no. **Providers:** Kubernetes read. **Governance:** yes (capability registration).

### 11.7 — Plan object with rollback and blast radius (P1)
- **Objective:** a governed plan artefact (prerequisites, expected effect, risk, blast radius computed from World facts, rollback capability ref, verification criteria) between investigation and approval (G-10).
- **Dependencies:** 11.6 (facts to compute blast radius).
- **Expected evidence:** approval digest binds to the plan; rollback executes through the same gateway with its own verification; negative matrix.
- **Complexity:** medium–high. **Architecture:** yes. **Schema:** likely (plan contract). **Providers:** no. **Governance:** yes.

### 11.8 — Governed observability and cost (P1)
- **Objective:** export the governed plane's counters (reads, writes, refusals by reason, verdict distribution, approval wait, queue wait) and per-investigation latency/cost; define MTTD/MTTR from `cw_investigation`/`cw_verification` timestamps (G-11, G-12, G-23).
- **Dependencies:** 11.5 for cost.
- **Expected evidence:** a scrape of `/metrics` showing governed counters; a per-investigation cost row; an MTTR figure computed from real records.
- **Framework candidates:** `prometheus_client` (already present for V1), OpenTelemetry (`backend/core/tracing.py` exists) — reuse, no new dependency.
- **Complexity:** medium. **Architecture:** no. **Schema:** maybe. **Providers:** no. **Governance:** no.

### 11.9 — Test-suite truth (P1)
- **Objective:** classify the 75 baseline failures; fix tests whose expectation predates a decision (the four `/execute` 401→guard-503 cases), quarantine benchmark tests that mock non-existent attributes, and grow real-PostgreSQL coverage of the governed loop (G-14).
- **Expected evidence:** a green-or-explained baseline; no assertion weakened.
- **Complexity:** medium. **Architecture:** no. **Schema:** no. **Providers:** no. **Governance:** no.

### 11.10 — Learning fed back (P2)
- **Objective:** production path from verification outcomes to calibration and experience memory, and from experience memory into investigation context (G-15).
- **Dependencies:** 11.4, 11.5, 11.8.
- **Expected evidence:** a second investigation of the same rule cites the first's outcome; calibration table updated from real outcomes.
- **Complexity:** medium. **Architecture:** no (components exist). **Schema:** no. **Governance:** no.

### 11.11 — Autonomy above A1 (P2)
- **Objective:** exercise ADR-079's ladder in production for one capability under earned authority (D5, G-16).
- **Dependencies:** 11.7, 11.10, D5.
- **Expected evidence:** an action executed without a per-action human approval only after the evidence threshold, with the same independent verification; downgrade on drift.
- **Complexity:** high. **Architecture:** yes. **Governance:** yes.

### 11.12 — Data ownership: stores and V1 fabric (P2/P3)
- **Objective:** one knowledge store (D4, G-17); durable, tenant-scoped replacement or retirement of JSON/in-memory V1 stores (G-18); replay `sequence` durability under Redis loss (G-22).
- **Complexity:** medium. **Schema:** yes.

### 11.13 — Deployability and documentation truth (P3)
- **Objective:** reconcile Helm with the real worker (G-19), render and deploy the chart in CI, fix the `/api/api` prefix and path vocabularies (G-20), and a documentation truth pass (G-21).
- **Complexity:** low–medium. **Architecture:** no.

### 11.14+ — Future (P4)
GitHub/cloud write capabilities behind D2; multi-provider capability fabric; org federation (V2 design).

## Sequencing summary

```
D1 ──▶ 11.1 (fence + navigate)
        11.2 (watch runner) ──┐
D3 ──▶  11.3 (governed ingress) ─┴──▶ 11.4 (detector) ──▶ 11.5 (model + defences; D2, 11.9 in parallel)
                                        │                     │
                                        ▼                     ▼
                                     11.6 (read caps) ──▶ 11.7 (plan/rollback) ──▶ 11.8 (observability/cost) ──▶ 11.10 (learning) ──▶ 11.11 (autonomy; D5)
                                                                                     11.12 (stores; D4)   11.13 (deploy/docs)
```

The first four phases (11.1–11.4) require no new dependency, no new provider, and no new schema beyond observations — they connect components that already exist and are verified.
