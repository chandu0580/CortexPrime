# PHASE 8.0 — INTELLIGENCE PLANE DISCOVERY REPORT

Date: 2026-08-12 · Discovery only — no code, no migrations, no new tables · Follows Phase 7 (COMPLETE)

Labels on every statement: **[FACT]** = directly verified in the repo this phase · **[SOURCE]** = cited from the source inventory (file:line) · **[INFERENCE]** = reasoning from evidence · **[PROPOSAL]** = design for later phases (not built here). Evidence and design are kept separate deliberately.

Governing constraint: Phase 7 is complete and is **not reopened**. Everything proposed here reuses the World Plane (7.2–7.6), the Assurance Plane (7.7), the reasoning ledger (7.8), the governed execution path (Phase 6), and the governed model boundary (`harness.GovernedModelBoundary`). L1–L16 remain ratification-pending and unweakened; the Phase 5.5 credential blocker is untouched.

---

## 1. Current intelligence inventory

**[FACT]** The repo contains ~230 Python modules of V1 "intelligence" across 22 packages: `agents` (27), `memory` (27), `llm_provider` (21), `orchestrator` (20), `ai` (17), `mission` (15), `mission_intel` (14), `computer` (12), `mcp` (9), `learning` (9), `knowledge` (9), `cognitive_memory` (8), `research` (7), `orchestration` (7), `agent_sdk` (7), plus `voice_v2`, `mission_skills`, `mission_library`, `voice`, `vision`, `llm`, `autonomy`.

**[FACT]** None of these are imported by the governed composition roots (`backend/api/application_runtime.py`, `backend/api/durability_composition.py`). **[SOURCE]** Only `backend/mission` is composition-wired (via `backend/api/mission_control_composition.py`) to delegate to a governed `ExecutionService`; every other package bypasses `backend/contexts/execution` and `backend/harness`. This is the "two disjoint planes" audit finding from the Zero Phase, at full scale.

Representative modules, by cluster (source-cited):
- **Provider/LLM.** [SOURCE] Governed runtime `backend/llm_provider/` (adapters hold keys — the legitimate key layer). V1 `backend/llm/llm_gateway.py` + `llm/llm_router.py` — dual-path: try governed runtime, then **fall back to direct SDK clients with their own `os.getenv(*_API_KEY)`** (`llm_gateway.py:46-62`, `llm_router.py:287,318,372`). Raw `backend/providers/openai_provider.py` (`AsyncAzureOpenAI` direct) used by `computer/vision_reasoner.py:227` — outside both.
- **Orchestration spine.** [SOURCE] `orchestration/cognition_pipeline.py` (central engine, runs agents inline `:148-152`, calls `llm_gateway.complete()` directly `:233-238`, side effects to Neo4j/Redis/RabbitMQ, memory-as-truth `:367-387`, self-declares `status="completed"`); `runtime/execution_manager.py` (API entrypoint, fire-and-forget `asyncio.create_task`); `orchestration/execution_context.py` (homegrown execution state in Redis, unrelated to `contexts/execution`).
- **Memory/RAG.** [SOURCE] `memory/vector_memory.py` (ChromaDB + `SentenceTransformer` MiniLM), `memory/embedding_pipeline.py` (OpenAI `text-embedding-3-small` → local fallback, Redis cache), `memory/stores/semantic_store.py` / `episodic_store.py` / `reflection_store.py` (pgvector cosine `ivfflat vector_cosine_ops`), `memory/graph/cognition_graph.py` + `infrastructure/neo4j/repositories/*` (Neo4j).
- **RCA/incident.** [SOURCE] `services/enterprise_root_cause_analysis.py` (deterministic rule-based, hardcoded hypothesis table, persists conclusions to `data/rca/*.json`); LLM reasoners `enterprise_deploy_root_cause_reasoner.py` / `_flaky_test_` / `_alert_incident_` (model hypotheses, explicitly labeled unverified, posted as ticket comments).
- **Execution surfaces.** [SOURCE] `api/legacy_execution_boundary.py` enumerates 15 privileged surfaces, all `gated=True` behind `CORTEXPRIME_ENABLE_LEGACY_EXECUTION` (default off): `mcp/gateway.py` (arbitrary tool+params), `computer/*` (`pyautogui`, `subprocess.Popen`), `tools/browser_agent.py` (Playwright), enterprise executors.
- **Autonomy.** [SOURCE] `autonomy/autonomous_runtime.py` — a start/stop runtime driving agents via a tool registry.

## 2. V1 intelligence weaknesses

**[SOURCE]** Ranked by severity:
1. **Model output becomes stored "truth."** `MemoryContextService` regex-extracts user statements at confidence **0.9** and LLM answer summaries at **0.85**, then re-injects them into planner/critic prompts labeled **"KNOWN FACTS"** (`services/memory_context_service.py:219,295,467`). `semantic_memory.confidence` DB default **1.0** (`migrations/0001:110`); `SemanticStore.store`, `MemoryOrchestrator.store_semantic_knowledge`, `WorldModelRepository.upsert_concept`, `cognitive_memory` reasoning steps all default confidence **1.0**. **[INFERENCE]** This is precisely the "model output → world fact" failure the World Plane exists to prevent.
2. **No tenant isolation.** V1 memory/knowledge/learning/research/graph are global (no `tenant_id`); `cognitive_memory` has a tenant field only in a volatile RAM dict; `/api/agents/run` reads tenant **from the request body** (caller-chosen = none); `/api/v2/mcp/execute` has no tenant at all (`api/legacy_execution_boundary.py`).
3. **Ungoverned execution + direct providers.** Inline agent execution, direct `llm_gateway`/`llm_router` SDK fallbacks holding their own keys, `computer/vision_reasoner.py` reaching a raw provider, `mcp` executing an arbitrary model-named tool.
4. **Self-declared success.** `success = len(output) > 20` (`orchestrator/autonomous_reasoning_loop.py:226`), hardcoded `"success": True` (`:537`), `success = bool(sources)` (`research/live_research_pipeline.py:186`), `DynamicAgent.execute` returns hardcoded `"completed"`.
5. **Fake retrieval / fake confidence.** `research` "semantic rerank" is positional (`1.0 - index*0.1`, `deep_research_engine.py:450`); `knowledge` "search" is SQL+Python filtering; `EvidenceEngine.overall_confidence` = mean of Tavily source scores (`evidence_engine.py`).
6. **Dead weight.** Several `backend/memory/*.py` are 0-byte stubs; `tools/browser_tool.py` and `tools/code_execution_tool.py` are empty.

**[INFERENCE]** Net: the V1 intelligence stack violates almost every Phase-7 invariant (model→truth, no tenant, ungoverned execution, invented confidence, hidden self-declared success). It is a **quarantine/replace surface**, not a foundation.

## 3. Intelligence boundary

**[PROPOSAL]** A new plane `backend/intelligence/` (application-only, fenced like `backend/world`/`backend/assurance`). It **MAY**: query World (`WorldQuery`), read evidence/beliefs, obtain schema-validated model proposals through `harness.GovernedModelBoundary`, generate hypotheses/investigation-plans/predictions (as *proposals*), rank investigation candidates by a deterministic policy, propose actions, summarize structured evidence, and request additional evidence. It **MUST NOT**: write World truth; construct `Fact`/`Belief`/`Outcome`/`Verification`; bypass governance; call provider APIs; acquire credentials or leadership; execute shell/browser/computer-use; mutate production. **[INFERENCE]** The Harness and the governed Execution plane remain the only actors; Intelligence is a *proposer and evidence-consumer*.

## 4. Investigation loop

**[PROPOSAL]** A deterministic state machine — **OBSERVE → ORIENT → HYPOTHESIZE → TEST → UPDATE → DECIDE** — where the model *proposes* inside a step and the platform *decides/acts/verifies* between steps. The loop invariant: **every step has a falsifiable purpose** — each proposed evidence query must name *which hypothesis it discriminates* and *what uncertainty it reduces*; a step that cannot state this is refused. No "look around" / "try random tools." **[INFERENCE]** This mirrors the Phase 6 harness loop (propose → validate → govern → act → record) applied to investigation, so it inherits replay, trace evidence, and crash recovery for free.

## 5. Differential diagnosis

**[PROPOSAL]** Maintain a *set* of candidate hypotheses (never immediately select one root cause). For each: `evidence_for`, `evidence_against`, `missing_evidence`, `contradictory_evidence`, `temporal_fit`, `authority`, `lineage`, `status`. **[INFERENCE]** These reuse existing contracts — `Hypothesis` (7.6, with `contradiction_refs`/`falsifier`), `EpistemicStatus`/`HypothesisStatus`, the 7.6 `SourceLineage`, and belief corroboration — with **no numeric confidence percentages**. A hypothesis is eliminated only by contradicting evidence (`falsifier`), and the differential stays CONFLICTED/UNKNOWN rather than forcing a pick when evidence is insufficient (UNKNOWN ≠ FALSE).

## 6. Active investigation

**[PROPOSAL]** The model may propose "query deployment history"; the platform decides whether it is allowed, maps it to an **exact governed READ capability** (no model-generated URL/API/shell), runs it under the incident's tenant through the existing gateway, and returns provenanced evidence. **[INFERENCE]** This is the Phase 6.3 tool-exposure discipline (model names a key into a frozen allowlist) applied to read-only investigation tools. Constraints honored: permissions, cost, latency, safety, freshness, tenant scope.

## 7. Context engine

**[PROPOSAL]** Reuse the Phase 6 Context Assembly Engine. Sections: World state, evidence, incident, active hypotheses, prior investigation steps, relevant predictions, governance constraints — **not** arbitrary conversation history, entire DB, or a vector index. Each section carries priority, freshness requirement, provenance requirement, and a token budget; contradictions are surfaced, not hidden. **[FACT]** Reproducibility already exists: `GovernedModelBoundary.propose` computes a deterministic `context_id` from `(mission_id, iteration, step_id, harness_version)` and records a trace span before returning (`harness/llm_boundary.py:244-289`). **[PROPOSAL]** Extend it so every model call is reproducible from context references + context version + harness version + model version + policy version.

## 8. World vs memory

**[PROPOSAL]** Keep three concepts **disjoint** (do not merge): **World** = the `cw_*` epistemic ledgers (authoritative, bitemporal, provenanced, tenant-scoped); **Memory** = what CortexPrime learned from prior investigations (advisory, never authoritative — Constitution I7: "experiential may propose, never authorize"); **Investigation state** = what it currently suspects and is testing. **[SOURCE]** The V1 memory system must NOT silently become World truth — and today it does (`MemoryContextService` "KNOWN FACTS"). **[INFERENCE]** A future governed memory (incident episodes) is a *derived, advisory, tenant-scoped, expiring* projection that feeds context but can never override an authoritative world observation.

## 9. RAG decision

**[PROPOSAL]** **No general RAG in the Intelligence Plane's truth path.** The rule: *retrieval is subordinate to epistemic authority — a retrieved document can never override an authoritative world observation.* `WorldQuery` is a structured, deterministic query and needs no RAG. **[INFERENCE]** Lexical/structured retrieval over runbooks or incident history *may* have a bounded, advisory role later (procedural knowledge), but semantic/vector/graph retrieval as a truth source is rejected. **[SOURCE]** The entire V1 vector/Chroma/pgvector/Neo4j stack (`memory/*`, `infrastructure/neo4j/*`, `api/vector_search_routes.py`, `api/graph_routes.py`) is a **quarantine** target, not to be wired into Intelligence. No pgvector/FAISS/Qdrant/Chroma is introduced by Phase 8.

## 10. Tool design

**[PROPOSAL]** The Intelligence tool interface is the Phase 6.3 tool-exposure model. A tool exposes: typed capability, operation, expected evidence, required permissions, side-effect class (read-only for investigation), freshness, cost, timeout, provenance. The model sees only tool identity, description, and schema — **never** raw credentials, provider URLs, shell paths, connection strings, or an unrestricted connector registry. **[FACT]** Tool selection is already deterministic at the harness boundary (`harness/tool_exposure.py`, `ToolProposal`), and `BND-HARNESS-NO-DYNAMIC-DISPATCH` forbids the model reaching a dynamic Python target. Investigation begins with **read-only** tools; any write goes through the full governed path.

## 11. Single-agent vs multi-agent decision

**[PROPOSAL]** **Single governed investigator + deterministic planner state machine + independent Assurance verifier.** **[INFERENCE]** A specialist/parallel/debate swarm adds coordination complexity, evidence duplication, attribution difficulty, and security surface for no measured benefit at this stage; the Constitution explicitly rejects "multi-agent decide/edit swarms." Independence that matters (producer ≠ verifier) is already provided by the Assurance Plane (7.7), not by a second reasoning agent. A planner/investigator split may be introduced later *only if* measured investigation quality justifies it — no multi-agent theater.

## 12. Investigation state

**[PROPOSAL]** Durable, append-only investigation state (a later phase, 8.2): `incident_ref`, `investigation_ref`, `active_hypotheses`, `evidence_refs`, `tested_hypotheses`, `pending_questions`, `predictions`, `governance_state`, `current_phase`, `last_durable_checkpoint`. It must survive crash, model restart, retry, and replay. **[INFERENCE]** Prefer a derived projection over the existing ledgers where possible (evidence, predictions, verifications already durable in `cw_*`); persist only the **loop checkpoint** (phase + active-hypothesis set + pending questions) that cannot be re-derived — the same "smallest append-only representation" discipline as Phase 7.8's `cw_reasoning`. No mutable truth, no latest-wins.

## 13. Failure attribution

**[PROPOSAL]** Preserve Phase 6's rejection of *trusted automatic* failure attribution (published accuracy 11–14%). Capture the evidence sufficient for later human/tooled adjudication: model input context, tool input, tool output, world evidence, policy, harness version, model version, decision, result. Attribution may *propose* a category (model / context / tool / world-state-gap / governance-refusal / execution / verification failure) but that proposal **never becomes truth** — it is evidence, adjudicated later.

## 14. Assurance integration

**[PROPOSAL]** Assurance is not a final checkbox; it enters at three points: (a) **hypothesis test** — a prediction that discriminates a hypothesis is independently verified against world evidence; (b) **remediation validation** — after a governed action, the claimed effect is independently verified; (c) **incident closure** — closure is **blocked** until the closing claim is independently SUPPORTED, or explicitly accepted as provisional by a human. **[INFERENCE]** UNKNOWN/STALE/CONFLICTED/INSUFFICIENT never close an incident as "resolved."

## 15. Autonomy ladder

**[PROPOSAL]** Explicit levels, model cannot self-promote: **A0 observe** (ingest signals) · **A1 investigate** (read-only evidence acquisition — the default) · **A2 recommend** (produce a differential + a proposed action, no execution) · **A3 execute approved** (each action human-approved through the existing Approval Center, governed execution) · **A4 policy-authorized autonomous remediation** (**default OFF**). Transition requirements: A2→A3 needs a governed approval; A3→A4 needs *measured* calibration (prediction/verification history), an explicit governance policy, and a scoped blast radius — never a model's request. **[SOURCE]** The V1 `autonomy/autonomous_runtime.py` is a quarantine target; A4 is not enabled.

## 16. HITL

**[PROPOSAL]** Humans enter where adjudication is meaningful: approve remediation, resolve conflicting evidence (CONFLICTED), confirm a high-impact hypothesis, override a provisional conclusion. **[FACT]** The governed approval surface already exists (Phase 5 Approval Center; `enterprise_deploy_rollback_executor.py` routes through it). **[PROPOSAL]** Human identity is a distinct `VerifierIdentity` (7.7) with a real person — never a fabricated approval string, never approval theater on every step.

## 17. Learning / calibration

**[PROPOSAL]** Learn from the durable signals already captured (predictions, outcomes, evaluations in `cw_reasoning`; verifications in `cw_verification`): prediction accuracy, hypothesis elimination rate, evidence usefulness, remediation success, verification success. **[INFERENCE]** Calibration is *measured from outcomes*, never from model-stated confidence, and is **deferred** to a dedicated phase — **no** automatic self-modification, online policy mutation, or autonomous harness evolution (the Constitution rejects these; they require the later evaluation infrastructure).

## 18. Incident memory

**[PROPOSAL]** A completed investigation becomes a structured **Incident Episode**: trigger, world-snapshot references, hypotheses, evidence refs, actions, outcomes, verification, lessons — **no raw chain-of-thought**, only structured reasoning artifacts (the same discipline as the reasoning ledger). It is tenant-specific, expiring, and **requires revalidation before reuse** (experiential/advisory, never authoritative — I7). **[INFERENCE]** This replaces the V1 `episodic_memory`/`semantic_memory` "KNOWN FACTS" path with a governed, advisory memory that can never overwrite world truth.

## 19. Observability

**[PROPOSAL]** Investigation telemetry is the Phase 6 harness trace (`cp_harness_trace`) plus the reasoning/verification ledgers — answering, from structured artifacts alone: what CortexPrime believed, why, what evidence it inspected, what it tested, what it rejected, what it predicted, what it did, what happened, who authorized it, who/what verified it. **[INFERENCE]** No hidden-reasoning requirement — structured evidence suffices, and private chain-of-thought is never persisted.

## 20. Competitive reality

**[INFERENCE, from training knowledge — not repo-verified]** 2026 incident-AI systems (AWS's DevOps/agentic assistants, Harness AI worker agents, Resolve AI, PagerDuty/Datadog/Cleric-style incident copilots) overwhelmingly share a shape: connect telemetry → retrieve context (RAG/graph) → LLM root-cause narrative → suggested actions, often with human approval. **[INFERENCE]** "Agents + RAG + incident response + automation + knowledge graph" is table-stakes, **not** a differentiator. The defensible differentiator for CortexPrime — *if* it is actually delivered — is the combination the industry generally does **not** do: **evidence-backed epistemic investigation** (bitemporal, provenanced, lineage-honest, model-output-can't-become-truth), **independent verification** (a verifier structurally distinct from the producer), **governed action** (one plane of action, authorization + lease + audit), **falsifiable predictions**, and **closed-loop outcome verification**. **[FACT]** Phase 7 delivered exactly these substrates against real Postgres. **[INFERENCE]** The bet holds *only* if Phase 8 wires investigation onto them rather than onto the V1 RAG/memory stack; if a future review shows the market has converged on independent-verification + governed-action too, the differentiator narrows to execution quality and calibration.

## 21. Architectural decisions

**[PROPOSAL]** (D1) A new `backend/intelligence/` application plane, fenced from execution and from World-writes. (D2) Reuse — do not rebuild — World Query, Assurance, the reasoning ledger, the governed model boundary, the governed execution path, and tool exposure. (D3) Model output is always a *schema-validated proposal*, never truth; grounding/verification stays with the platform. (D4) Differential diagnosis over a hypothesis set with epistemic states, no numeric confidence. (D5) Deterministic investigation state machine with falsifiable-purpose steps. (D6) Single investigator + independent Assurance; no swarm. (D7) No RAG in the truth path; retrieval is advisory and subordinate to authority. (D8) The entire V1 intelligence stack is quarantined behind `guard_legacy_internal`/`CORTEXPRIME_ENABLE_LEGACY_EXECUTION`, then strangled. (D9) Autonomy is an explicit A0–A4 ladder, default A1, model cannot self-promote, A4 off.

## 22. KEEP / REPLACE / QUARANTINE / DELETE

**[PROPOSAL]** (classification of the source inventory)

| Component | Verdict | Rationale |
|---|---|---|
| `backend/world`, `backend/assurance`, `backend/harness`, `backend/contexts/execution`, Phase-5 governance/approval, `backend/llm_provider` (governed adapters) | **KEEP** | The Phase 5–7 substrate; the Intelligence Plane composes on these. |
| `backend/harness.GovernedModelBoundary` + `tool_exposure` | **KEEP** | The sanctioned model-proposal + tool-selection seam. |
| `backend/mission` (governed-shaped: tenant, delegates to execution service, reads `SUCCEEDED`) | **MIGRATE** | Closest to governed; rebase onto the Intelligence Plane + governed execution. |
| `backend/ai` (mostly simulated/routing shell, partial tenant) | **MIGRATE/REPLACE** | Routing concept reusable; the simulation stubs replaced by governed investigation. |
| `services/enterprise_*_root_cause_reasoner` (LLM, honest-uncertainty, output = unverified ticket comment) | **MIGRATE** | Correct discipline (unverified proposal); rewire to emit `ModelHypothesisProposal` into governed grounding + Assurance. |
| `services/enterprise_root_cause_analysis.py` (deterministic rules, but stores conclusions as JSON "truth") | **REPLACE** | Deterministic pattern rules are reusable as hypothesis *seeds*; the "store conclusion as truth in JSON" path is replaced by the epistemic ledgers. |
| `backend/memory/*` (Chroma/pgvector/embeddings), `memory/stores/*`, `memory/graph`, `infrastructure/neo4j/*`, `MemoryContextService` "KNOWN FACTS", `cognitive_memory`, `knowledge` (confidence=1.0, no tenant) | **QUARANTINE → REPLACE** | Model-output-as-truth, no tenant, RAG-as-truth. Replace with governed advisory incident-episode memory. |
| `orchestration/cognition_pipeline`, `runtime/execution_manager`, `orchestration/execution_context`, `orchestrator/autonomous_reasoning_loop`, `runtime/dynamic_agent_factory`, `autonomy/autonomous_runtime` | **QUARANTINE → DELETE** | Ungoverned inline execution, self-declared success, homegrown execution state. Superseded by the governed loop. |
| `research/*` (Tavily direct, fake semantic rerank, synthesis→memory-truth) | **QUARANTINE** | Ungoverned outbound + model-as-truth. A governed read-only research tool may replace it later. |
| `computer/*`, `tools/browser_agent`, `mcp/gateway` (execution surfaces) | **KEEP-QUARANTINED** | Already behind `legacy_execution_boundary`; remain gated; only ever reached through governed execution, never by Intelligence directly. |
| `llm/llm_gateway`, `llm/llm_router` (direct-SDK fallback with own keys) | **REPLACE** | The direct-key fallback bypasses the governed provider runtime; Intelligence uses `GovernedModelBoundary` only. |
| 0-byte stubs (`memory/*.py` empties, `tools/browser_tool.py`, `tools/code_execution_tool.py`) | **DELETE** | Dead files. |
| `voice*`, `vision`, `voice_v2` | **DEFER** | Out of scope for incident investigation; classify in a later phase. |

## 23. Phase 8 roadmap

**[PROPOSAL]** (order chosen so each phase is provable against real Postgres before the next depends on it)
- **8.1 Intelligence contracts & boundary** — `backend/intelligence/`, the plane's ports, `Investigation`/`InvestigationStep`/`DifferentialDiagnosis` contracts, fitness rules (§24). No loop yet.
- **8.2 Investigation state** — durable append-only investigation checkpoint (crash/replay proven).
- **8.3 Context assembly for investigation** — governed, reproducible context recipe over World/evidence/hypotheses.
- **8.4 Investigation loop** — the OBSERVE→…→DECIDE state machine with falsifiable-purpose steps, read-only.
- **8.5 Differential diagnosis** — hypothesis-set maintenance, elimination by contradiction, no numeric confidence.
- **8.6 Evidence acquisition** — model-proposed → platform-mapped governed READ tools.
- **8.7 Prediction/evaluation/Assurance integration** — hypothesis test → prediction → independent verification (end-to-end, building on 7.8).
- **8.8 Incident memory** — governed advisory incident episodes (I7).
- **8.9 Calibration** — measured from accumulated prediction/outcome/verification history.
- **8.10 Autonomous remediation readiness** — A2/A3 wiring; A4 remains gated and off.

## 24. Fitness rules (proposed for 8.1)

**[PROPOSAL]** (each must ship with CURRENT=PASS / SYNTHETIC=FAIL; none cosmetic)
- `BND-INTELLIGENCE-CANNOT-EXECUTE` — `backend/intelligence` imports no connector/gateway/transport/credential-carrier/scheduler/computer/browser (mirrors `BND-ASSURANCE-CANNOT-EXECUTE`).
- `BND-INTELLIGENCE-CANNOT-WRITE-WORLD` — Intelligence does not import the World *write* constructors (`Fact`, `Belief`, `Observation`) or the ingestion/derivation writers — it may import read types and `ModelHypothesisProposal`/`Prediction`. (Extends `BND-MODEL-CANNOT-CREATE-FACT` to the new plane.)
- `BND-INTELLIGENCE-NO-DIRECT-PROVIDER` — Intelligence imports no `llm_provider`/`llm`/`providers` direct client — only `harness.GovernedModelBoundary`.
- `BND-NO-V1-INTELLIGENCE-IMPORT` — the governed planes do not import the quarantined V1 packages (a ratchet so the strangler zone only shrinks; mirrors `BND-NO-LEGACY`).
**[INFERENCE]** No new rule is needed for "model cannot create Verification/Outcome" (already covered by the extended `BND-MODEL-CANNOT-CREATE-FACT`) or "cannot execute the machine" (Phase 6 process-spawn/effect-gate/SDK/dynamic-dispatch rules).

## 25. Stop-condition results

**[FACT/INFERENCE]** Against the **target design**: none of the Part-V stop conditions is present — Intelligence cannot execute, cannot write world truth, belief is not model confidence, no numeric confidence is invented, evidence is not discarded, stale/unknown are not truth, contradictions are preserved, tenant isolation is structural, RAG cannot override authority, investigation state is append-only, the model selects no arbitrary connector/URL/shell, replay does not execute, human approval is an identity not a string, verification does not consume model self-report, and no multi-agent architecture is added. **[SOURCE]** Against the **existing V1 code**, almost every stop-condition hazard is present (model→truth, no tenant, ungoverned execution, invented confidence, RAG-as-truth) — which is exactly why the V1 stack is classified QUARANTINE/REPLACE/DELETE, not integrated. This is a discovery finding about legacy code, not a Phase-8-design contradiction.

## 26. Risks

**[INFERENCE]** (1) **Strangler scale** — ~230 V1 modules; the risk is that new code accidentally imports the quarantined stack (mitigated by `BND-NO-V1-INTELLIGENCE-IMPORT`). (2) **Model-proposal quality** — a governed investigator is only as useful as its proposals; the platform's job is to keep bad proposals harmless (read-only, verified), not to make them good. (3) **Governed provider still BLOCKED** — the real LLM leg remains blocked by placeholder credentials (Phase 5.5 class); investigation loops will be exercised with the controlled/scripted provider until real keys exist, and every scripted run stays labeled. (4) **Differentiator is a bet** (§20) — it holds only if Phase 8 wires onto the epistemic substrate. (5) **RAG temptation** — pressure to reuse the existing vector stack for "context" must be resisted; retrieval stays advisory and subordinate to authority.

## 27. NOT VERIFIED

**[FACT]** This is a discovery phase — no design claim here is executable-verified. The competitive analysis (§20) is from training knowledge, not repo evidence or a live 2026 market scan. The V1 inventory is source-cited but not exhaustively read module-by-module (the highest-signal ~50 modules were characterized). No performance, latency, or cost of any proposed loop is measured.

## 28. Deferred

**[PROPOSAL]** Numerical calibration (8.9); autonomous remediation A4 (8.10, gated/off); incident-episode memory (8.8); any semantic/lexical retrieval role (advisory only, later, bounded); `voice*`/`vision` classification; the governed Kubernetes watch stream (still Phase 7.9); a live 2026 competitive scan.

## 29. ADR-071

**[PROPOSAL]** `docs/adr/ADR-071-intelligence-plane-boundary.md` records the Intelligence Plane boundary, the reuse-not-rebuild stance, the V1 quarantine/strangler strategy, the no-RAG-in-the-truth-path decision, single-investigator + independent-assurance, and the A0–A4 ladder. (Written alongside this report.)

## 30. Phase 8.1 Definition of Done (proposed)

**[PROPOSAL]** Phase 8.1 is complete when: the `backend/intelligence/` plane exists with a defined boundary and typed `Investigation`/`InvestigationStep`/`DifferentialDiagnosis`/`InvestigationPlan` contracts; the four fitness rules (§24) pass with sensitivity tests (CURRENT=PASS, SYNTHETIC=FAIL); the plane imports World-read + `GovernedModelBoundary` + Assurance only (no execution, no world-write, no direct provider, no V1 import); a model proposal flows in through the governed boundary and produces a *typed proposal object* that cannot become Fact/Belief/Outcome/Verification; tenant is structural on every contract; no new table unless justified (contracts/derived-projection first); ADR-072 + a Phase 8.1 verification report exist; Phase 7.8 regression stays green; the developer DB is untouched; and L1–L16 + One Plane of Action + World immutability + independent Assurance + tenant isolation + the Phase 5.5 blocker remain intact.

---

**Discovery verdict [INFERENCE]:** Phase 7 gives CortexPrime a genuine, defensible substrate (evidence-backed, bitemporal, independently-verified, governed). The V1 "intelligence" is a large, ungoverned, model-output-as-truth stack that must be **quarantined and replaced**, not extended. Phase 8 should build a thin, governed Intelligence Plane that *proposes* investigations and *consumes* evidence, letting the World and Assurance planes remain the sole sources of truth and verification, and the governed Execution plane the sole actor.
