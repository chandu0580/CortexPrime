# PHASE 7.0 — WORLD PLANE DISCOVERY REPORT

**Discovery and architecture only. No code was written, no contract modified, no store migrated. This document is a design and a set of decisions to ratify before Phase 7.1 begins.**

Date: 2026-08-11 · Basis: a read-only repository world-state audit (Part A), a deep read of the dead epistemic contracts (Part B), and a fresh 2024–2026 literature sweep (Part V), synthesized against the ratified Zero Phase ontology (CONSTITUTION §4–6) and the Phase 6 harness architecture.

**Classification of every statement:** **[FACT]** — verifiable from the repository. **[SOURCE]** — from cited external research. **[INFERENCE]** — reasoning over facts/sources. **[PROPOSAL]** — a design choice proposed, not established.

Constitutional constraint honored throughout: **L1–L16 preserved; the World Plane informs action and never executes it.** `WORLD → INTELLIGENCE → HARNESS → GOVERNANCE → EXECUTION`, never `WORLD → EXECUTION`.

---

## 1. Executive summary

**[INFERENCE]** CortexPrime can now safely *act* (Phases 6.1–6.3: one plane of action, hardened harness, integration gate passed). It cannot yet coherently say what it *knows*. Phase 7.0's audit found that the repository's current answer to "what is true about the external world" is a scatter of ~19 destructively-overwritten JSON snapshots, a repository "brain" with no staleness, cached connector reads with no TTL, and a cross-tenant, LLM-writable memory subsystem — none of which records *when a fact was true* versus *when we learned it*, *where it came from*, or *what contradicts it*.

**[FACT]** The three conditions Part Z names as stop-worthy are all true **of the existing V1 substrate**: model output is written into `semantic_memory` with `confidence=1.0` and no ingestion boundary; the memory and JSON stores are cross-tenant; and infrastructure/brain state is destructively overwritten, erasing history. **[INFERENCE]** These are not a reason to halt Phase 7.0 and not a conflict with the Phase 6 architecture. They are the *migration boundary and the empirical case for the World Plane*: the existing stores are strangler targets (as the 76 JSON stores already were in the Zero Phase), must be quarantined from ever feeding the World Plane, and must never be extended into it. Section 26 reports them formally as the Part Z outcome.

**[INFERENCE + SOURCE]** The design that follows is a **bitemporal, provenanced, tenant-scoped epistemic substrate** with a hard **ingestion boundary** — only provenanced observations from instruments become facts; the model proposes hypotheses and beliefs, never facts. The external research is unusually aligned: bitemporal world state (Zep/Graphiti, XTDB), graph-linked provenance (PROV-AGENT), the STALE benchmark (agents act on stale beliefs even after retrieving fresh evidence — 55.2%), memory-poisoning attacks (MINJA >90%, AgentPoison ≥80% at <0.1% poison), and the consensus that verbalized LLM confidence is systematically overconfident (ECE up to 0.30+) each independently point at the same shape. The whitespace is not any single primitive — all are built by someone — but the **composition** into one governed substrate, plus the ingestion boundary and first-class CONFLICTED/UNKNOWN/STALE states, which are the least-productized and most evidence-backed.

**[PROPOSAL]** Phase 7 is sequenced ontology-and-boundary first (7.1), observation ingestion and tenant scoping second (7.2), bitemporal state third (7.3) — because the security-critical invariants (no model-authored facts, tenant isolation, provenance) are the differentiators and the existing violations are live. Full roadmap in §25.

---

## 2. Phase 6 exit verification

**[FACT]** Phase 6 is complete and its guarantees hold, verified this session: 6.1 (one plane of action + harness spine, ADR-059), 6.2 (hardening + assurance boundary, ADR-060, storage-context fail-open fixed), 6.3 (final integration gate, ADR-061 — full plane driven as one system through the scheduler, leadership reclaim across real `os._exit(9)`, replay matrix inert, 25 architecture rules PASS, 2912 core tests green). **[FACT]** No Phase 6 architecture is modified by this discovery; nothing in the audit contradicts it. **[INFERENCE]** The World Plane attaches *above* the Phase 6 substrate as a new read-authority plane; it consumes execution outcomes and audit/trace evidence but adds no execution path, satisfying the Part Z condition "no second execution authority."

---

## 3. Existing world-state inventory (Part A)

**[FACT]** Full matrix in the audit (SOURCE→OWNER→SCHEMA→PROVENANCE→TIMESTAMP→FRESHNESS→TENANT→AUTHORITY→MUTABILITY→CONSUMERS→CAN-CONTRADICT). Classified summary:

| Class | Sources (file evidence) | World-Plane disposition |
|---|---|---|
| **TRUE-WORLD-STATE** | `data/infrastructure/*.json` (19 files, k8s/docker/prometheus/grafana/loki snapshots, `enterprise_infrastructure_intelligence.py:24-39`); `repository_brain.json` (`enterprise_repository_brain.py:43`); `github_*.json` cached reads; `enterprise_graph_service` KG + `knowledge/*` docs; domain `*_history.json`; live connector reads (transient, `connectors/base.py`, `effects.py`) | **REPLACE** — strangler targets. None has observed-vs-recorded time, provenance-system id, freshness, or tenant. The live connector reads are the *actual* truth and are transient by design; the World Plane's job is to ingest them with provenance rather than snapshot them destructively. |
| **CONVERSATION-MEMORY** | `semantic_memory`, `episodic_memory`, reflection tables, Redis context, Neo4j cognition graph, `cognitive_memory/*`, Chroma, `MemoryOrchestrator` | **KEEP as memory, QUARANTINE from world** — Constitution I7 "propose, never authorize." This is Part Q's distinction: memory is not world truth. Cross-tenant + LLM-written (STOP-1/2) — must be walled off from World Plane ingestion. |
| **EXECUTION-OUTCOME** | `cp_execution` (V2 authoritative), `runtime_store.json` (V1 parallel), `EngineeringExperience` (derived), cicd/build/sandbox JSON | **REUSE `cp_execution`; REPLACE V1** — an execution outcome is *"the call completed,"* not *"the world changed"* (Part R). It is provenance-for a later fact, not a fact. |
| **AUDIT-TRACE** | `cp_audit_record`+`cp_audit_chain` (hash-chained, fenced), `cp_harness_trace`, `integrity_audit.jsonl`, V1 `audit_log`, `connector_activity` | **KEEP, REUSE as provenance anchors** — the World Plane links beliefs to these by `correlation_id`, never copies them. |
| **CONFIG** | `monitoring_rules.json`, `trigger_policies.json`, `cp_capability`/`cp_connector_config` | **KEEP** — not world state. |

**[FACT]** The one correct template already in the repo is the Phase 5.1 `cp_*` durable fabric (`backend/database/durable/tables.py`): tenant-scoped (`tenant_id NOT NULL`), digest-provenanced, expiry-bearing, append-only, migration-backed. **[PROPOSAL]** The World Plane's storage follows this template exactly (Postgres under Alembic, `cw_*` tables), not the JSON-store pattern.

---

## 4. Dead-contract analysis (Part B)

**[FACT]** Re-verified post-6.3: `backend.contracts.knowledge` and `backend.contracts.evidence` have **zero live importers** (only the package re-export and one I7 invariant-test probe). The live `AssembledContext` is the Pydantic `backend/memory/models.py:69` (no authority, no confidence), a name collision with the dead `contracts/knowledge.py:134` contract.

**[FACT + PROPOSAL]** Verdicts (from the deep read), adopted:

| Contract element | Verdict | Reason |
|---|---|---|
| `knowledge.py` `KnowledgeKind` + `KnowledgeAuthority` + I7 (`may_be_authoritative`, "experiential may propose, never authorize") | **EXTEND (salvage)** | The only typed epistemic-*authority* axis in the repo. Becomes the World Plane's "how much may I lean on this" dimension. |
| `knowledge.py` `KnowledgeItem` record shape | **REPLACE** | No bitemporal, no tenant, no structured provenance/evidence link, no supersession; `recorded_at` conflates event and ingest time. |
| `knowledge.py` `AssembledContext` | **DEPRECATE** | Dead; collides with the live memory type. Resolve to one. |
| `evidence.py` `SourceStatus` (RETURNED_DATA/RETURNED_EMPTY/UNAVAILABLE/NOT_CONFIGURED) + `Citation` (observed_at vs retrieved_at, re-executable query, `staleness_at`) | **KEEP / EXTEND — the best seed in the repo** | The only place separating event time from ingest time; the empty≠unavailable tri-state is exactly "STALE ≠ FALSE / I-don't-know" done right. Extend with tenant, valid-time interval, correction axis, forward links. |
| `evidence.py` `EvidenceSet`/`EvidenceItem`/`SourceOutcome` | **EXTEND** | Sound P1/P6 discipline (unavailability is a value; cite don't copy); lacks trust-on-evidence, tenant, set-level staleness. |
| `engineering_verification/domain/evidence.py` `TrustLevel` (DETERMINISTIC>ENVIRONMENTAL>OBSERVED>ASSERTED) + asserted-vs-verified unconvertible-types split | **KEEP the discipline (not the record shape)** | The epistemic-*strength* axis, orthogonal to authority. Its record is gate-shaped (commit-bound), not world-shaped. |
| `contracts/execution.py` `EffectSemantics` / `SideEffectClass` / `ExecutionEnvironment` | **REUSE** | Orthogonal consequence/repeatability/environment axes; an observation is READ/READ_ONLY. |
| `contracts/audit.py` `TenantScope`, `correlation_id`/`causation_id`, `PayloadDigest` chaining | **REUSE as pattern** | Supplies the tenant + causal-linkage + tamper-evidence fields the epistemic contracts lack. |
| `contracts/_contract.py` `Contract` base | **REUSE (foundation)** | Envelope, versioning (additive-only), canonical serialization; World Plane primitives subclass it; digest external. |

**[FACT]** The load-bearing cross-cutting gap: **authority (knowledge) and trust (verification) are two distinct epistemic axes living in disconnected modules with no shared primitive**, and *no* existing model carries both plus bitemporal time, tenant scope, and provenance links. That combination is what the World Plane must mint. **[FACT]** No bitemporal or valid-time modeling exists anywhere in the repo (`valid_from`/`valid_to`/`bitemporal`/`transaction_time` = zero hits); the World Plane would be the first — no prior art to conflict with, and `Citation.observed_at`-vs-`retrieved_at` + `VerificationRecord.superseded_by` are the seeds to generalize.

---

## 5. Epistemic ontology (Part C)

**[SOURCE]** The research is explicit against reifying six words as six tables — prefer a small number of ledger families with typed records. **[PROPOSAL]** Four ledgers, one shared bitemporal+provenance+tenant spine (subclassing `Contract`), reconciling the Zero Phase epistemic family with the research:

1. **Observation Ledger** — append-only, immutable, never model-written. Raw provenanced instrument outputs. Carries `SourceStatus` (salvaged from `evidence.py`), `observed_at` vs `retrieved_at`, source-system id, tenant, the re-executable query. This is Part D's OBSERVATION.
2. **Claim Ledger** (facts + beliefs) — bitemporal, append-only with supersession (invalidation-not-deletion). A **FACT** is a claim with observational backing at admissible trust; a **BELIEF** is a claim held below observational backing, confidence-bearing. Same table, distinguished by an epistemic-status field, never silently promoted (Part C's core rule).
3. **Hypothesis Ledger** — on-trial explanations with discriminating-evidence links and a lifecycle (open → supported/refuted/unresolved); promotion to belief/fact only through the assurance rules (Part L).
4. **Prediction/Outcome Ledger** — sealed predictions paired with observed outcomes; never collapsed (Part M); the seed of future prediction-error learning.

**[PROPOSAL]** For each type, the required columns (semantics · creator · allowed sources · provenance · temporal model · confidence · contradiction rule · promotion rule · consumers · action authority):

| Type | Creator | Allowed source | Temporal | Confidence | Contradiction rule | Promotion rule | Action authority |
|---|---|---|---|---|---|---|---|
| OBSERVATION | ingestion boundary (deterministic) | instrument/connector read ONLY, never model | observed_at + retrieved_at, immutable | none (raw) | records disagreements, resolves nothing | — | **none** (evidence only) |
| FACT | derivation engine (deterministic rules over observations) | ≥1 observation at admissible trust | valid_from/valid_to + recorded_at, superseded not deleted | calibrated or UNCALIBRATED | CONFLICTED is a first-class state, never auto-resolved | observation(s) → fact by rule; **model cannot** | informs the epistemic gate; never authorizes |
| BELIEF | inference (may be model-proposed) | inference over facts, or accepted hypotheses | same bitemporal | calibrated or UNCALIBRATED | supersession + CONFLICTED | belief→fact only via assurance-verified observation | informs proposals only |
| HYPOTHESIS | model or algorithmic RCA | freely proposed | recorded_at + status timeline | discriminating-evidence weighted | plural allowed and encouraged | hypothesis→belief needs the discriminating evidence | never directly |
| PREDICTION | planner/simulation (may be model) | sealed pre-action | recorded_at + deadline | calibrated where history exists | — | resolved against outcome, never becomes it | approval evidence / verification target |
| OUTCOME | execution + observation | worker result + fresh observation | recorded_at | — | — | — | is what it is |
| VERIFICATION | assurance plane (Phase 8) | executed checks only | recorded_at | — | — | — | gates completion |

**[PROPOSAL]** The five non-collapses are enforced structurally (unconvertible types, following the live `AssertedEvidenceRef`/`VerifiedEvidence` pattern): a BELIEF never silently becomes a FACT; a HYPOTHESIS never silently becomes a BELIEF; a PREDICTION never silently becomes an OUTCOME; a MODEL VERDICT never becomes a VERIFICATION. Each promotion is a distinct, recorded, rule-gated act.

---

## 6. Observation vs fact (Part D)

**[PROPOSAL + SOURCE]** Yes — the split is mandatory and is the ingestion boundary's whole point. A provider returning `"replicas = 3"` is an **OBSERVATION** (raw, immutable, provenanced, with `observed_at` distinct from `retrieved_at`). The derived, normalized, bitemporal statement `"deployment X had 3 replicas, valid from T"` is a **FACT**, minted by a deterministic derivation rule, never by the model. **[FACT]** The existing infra JSON collapses exactly this — a connector read is destructively upserted into `pods.json` with a single `_now()` write time (`enterprise_infrastructure_intelligence.py:141-142`), losing observed-vs-ingest and prior history. **[PROPOSAL]** Normalization (raw provider JSON → canonical entity/field), source authority, observation time, ingestion time, validity interval, supersession, and provenance are all properties of the *fact*, derived from the *observation*, never conflated. Raw evidence (observation) and derived world state (fact) are separate ledgers.

---

## 7. Temporal model (Part E)

**[SOURCE]** Bitemporality (Snodgrass/SQL:2011, XTDB, Datomic) is settled theory; Graphiti operationalizes it for agents with four timestamps and invalidation-not-deletion. **[PROPOSAL]** The World Plane needs three times, two axes: **valid time** (`valid_from`/`valid_to` — when the fact was true in the world) and **transaction/knowledge time** (`recorded_at`/`superseded_at` — when we learned/revised it), with **observation time** (`observed_at` on the source observation) as the input that seeds valid time. Facts are never deleted; a contradicting observation writes a new fact and sets the prior's `valid_to`/`superseded_at`.

**[PROPOSAL]** The Part E test, answered deterministically. Deployment changed 10:00 (valid); observed 10:04, recorded 10:05. At 10:10 source B says it was already changed at 09:58.

- **09:59** — no observation yet ingested; the World Plane holds the *prior* fact (or UNKNOWN if none). It does not know about the 10:00 change.
- **10:02** — still no observation (first is at 10:04); same as 09:59. The world moved but the World Plane has not learned it — and it *says so* (the prior fact's freshness is aging), it does not hallucinate the change.
- **10:06** — the 10:04 observation (recorded 10:05) is ingested: fact `valid_from=10:00, recorded_at=10:05`. As-of-now query returns the changed state; as-of-09:59 query still returns the prior fact.
- **10:11** — source B's observation (valid_from=09:58) arrives, recorded 10:10. This *corrects the valid-time* of the same change: a new fact version `valid_from=09:58` supersedes `valid_from=10:00`, the earlier version retained with its `superseded_at=10:10`. A query "what did CortexPrime believe about the change's start at 10:06?" returns 10:00; "what does it believe now?" returns 09:58; "when did it learn 09:58?" returns 10:10. Both source observations and both fact versions are retained. **[INFERENCE]** This is exactly the bitemporal correction case, and only a bitemporal model answers it without losing history.

---

## 8. Provenance model (Part F)

**[SOURCE]** W3C PROV-DM/PROV-O + PROV-AGENT (Oak Ridge, IEEE e-Science 2025) unify entity/activity/agent and agent-specific prompt/tool-call/model-invocation metadata into one provenance graph. **[SOURCE + PROPOSAL]** Provenance is **graph-linked by reference**, never embedded — the anti-pattern (copying raw evidence into the belief) duplicates secrets and bloats state. Every epistemic record links to a provenance node answering: what produced it (agent/instrument), from which source-system, when, under which tenant, from which observation id, which tool-call, which execution id, which trace/`correlation_id`, under which harness version. **[FACT]** The repo already has the anchors: `cp_harness_trace` (harness version, correlation), `cp_audit_record` (fenced, correlation/causation), `cp_execution` (execution id) — the World Plane references these by id, reusing the `audit.py` correlation pattern. **[PROPOSAL]** Hard rule: provenance carries **no secret material** — it stores `credential_ref` style references (as `cp_connector_config` already does), content hashes, and ids, never tokens, headers, or payloads. The Phase 6 firewall (`find_secrets`) is the tripwire on the ingestion path.

---

## 9. Source authority (Part G)

**[SOURCE + PROPOSAL]** Three distinct, non-interchangeable quantities, stored separately (the research names this as underserved):

- **SOURCE AUTHORITY** — how much a *source system* is trusted, derived (not a naive `0.95` field) from: source identity, observation method, historical accuracy, corroboration history, and a provenance *tier* (the reliability-conditional-updating result: trust = `min(provenance_ceiling, content)` — content can only *lower* trust within a channel's ceiling, never raise it; low-trust channels achieved 0% poisoning ASR vs 100% naive).
- **CLAIM CONFIDENCE** — how strongly a *specific claim* is held, from corroboration across sources, freshness, temporal consistency, and (later) outcome calibration.
- **MODEL CONFIDENCE** — what the model *said*; stored as metadata, **never** a control input.

**[SOURCE]** These must not be collapsed: the truth-discovery literature estimates source reliability and claim truth *jointly* but keeps them distinct; conflating any two is a known failure. **[PROPOSAL]** Phase 7 establishes the schema and the source-authority *tier* mechanism (deterministic, provenance-derived); it does not build a full statistical truth-discovery engine yet.

---

## 10. Freshness (Part H)

**[SOURCE]** STALE ≠ FALSE is articulated in the epistemic-integrity literature; "when nothing fails when the cache disagrees with the source of truth, stale entries become confident-sounding falsehood." **[PROPOSAL]** Freshness is a first-class, *derived* epistemic state, not a boolean: each fact class has a **validity window / refresh interval** (a Kubernetes replica count ages fast; a repository's language ages slowly). A fact past its window is **STALE** (needs re-observation) — a distinct state from **INVALIDATED** (known false, superseded) and **CONFLICTED** (contradicted). **[SOURCE + INFERENCE]** This ties to the runtime-discovery-beats-learned-models finding: staleness triggers re-discovery (re-observation), not a guess. **[PROPOSAL]** The epistemic gate (Zero Phase §6.4) enforces freshness *at use*: a consequential action whose justifying fact is STALE is refused with "observe first," not served the stale fact — the structural answer to STALE's finding that agents act on stale beliefs even after retrieving fresh evidence. A stale belief is not automatically false; it is automatically *not admissible for a consequential action* until refreshed.

---

## 11. Contradiction model (Part I)

**[SOURCE]** The conflict-detection literature detects conflicts but resolves by picking a winner (Graphiti invalidates the loser; RAG concatenates/votes). For a governed system this is REJECT: silently choosing is how false certainty causes action. **[PROPOSAL]** Contradiction is a first-class, non-collapsing record. Source A `replicas=3`, source B `replicas=5` produces a **CONTRADICTION record** linking the competing claims, their source authorities, freshness, and temporal overlap — and the derived fact enters state **CONFLICTED**, not a coin-flip winner. Resolution paths: supersede (one is staler/lower-authority by rule), corroborate (a third observation), or **escalate to a human** (both load-bearing, irreconcilable). **[PROPOSAL]** The World Plane must be able to represent, as valuable states: *"I don't know"* (UNKNOWN — no observation), *"I have conflicting evidence"* (CONFLICTED), *"this belief is stale"* (STALE), *"this hypothesis is unresolved"* (open). **[FACT]** The `evidence.py` `SourceStatus` tri-state (empty≠unavailable≠not-configured) is exactly the "record the absence honestly" discipline this needs, salvaged.

---

## 12. Belief revision (Part J)

**[SOURCE]** AGM belief revision (minimal change, non-destructive) is the formal discipline; the 2026 diagnostics work (Semantic Belief Propagation) shows the winning pattern is *separating LLM reasoning from deterministic belief-store control*. STALE proves the in-context "just retrieve" approach fails (55.2%). **[PROPOSAL]** Belief change is: BELIEF → new observation → contradiction → revision → new confidence → **history preserved**. Never destructive overwrite (directly countering the existing infra/brain STOP-3 behavior). Because the store is bitemporal and append-only-with-supersession, the World Plane answers deterministically: *"what did CortexPrime believe yesterday?"* (as-of query on recorded_at), *"what changed it?"* (the superseding observation's provenance), *"which evidence caused the change?"* (the provenance link). **[PROPOSAL]** The revision *control* is deterministic (rules over the store); the model may *propose* a revised belief but cannot commit a fact — the ingestion boundary again.

---

## 13. Confidence / calibration (Part K)

**[SOURCE]** Strong consensus: verbalized LLM confidence is systematically overconfident (ECE up to 0.30+, clustered 80–100%), prompt-sensitive, mechanistically ingrained, RLHF-induced. As a truth source: **REJECT**. **[PROPOSAL]** Four distinct quantities, schema established now, statistics deferred:

- **confidence** — the calibrated hit-rate of this claim class/source/method, or the explicit state **UNCALIBRATED** (never a default 0.5, never the memory system's current default 1.0).
- **calibration** — the mapping from stated to actual, fit later from logged prediction↔outcome (Platt/isotonic, measured by ECE/Brier).
- **accuracy** — realized correctness over time.
- **source reliability** — §9's source authority.

**[SOURCE + PROPOSAL]** "I am 95% confident" from a model must **not** produce `confidence = 0.95`. Phase 7 establishes: (a) a `confidence` field that is UNCALIBRATED until enough outcome history exists, (b) the schema that *makes future calibration possible* — every consequential prediction and its observed outcome are logged (Prediction/Outcome ledger, §15) so isotonic/Platt can be fit per claim class later. **[PROPOSAL]** No full statistical calibration engine is built in Phase 7 — the repo contains none to reuse — only the schema and the UNCALIBRATED semantics.

---

## 14. Hypothesis lifecycle (Part L)

**[PROPOSAL]** HYPOTHESIS → INVESTIGATION → EVIDENCE → SUPPORTED / REFUTED / UNRESOLVED → (only then, via assurance) VERIFIED or REJECTED. **[FACT]** The repo already types the critical non-collapse: the live `VerificationStatus` distinguishes INCOMPLETE (the verifier could not tell) from FAILED (the work is wrong), and `Verdict` distinguishes INSUFFICIENT_EVIDENCE from UNSUPPORTED — the "we don't know ≠ it's wrong" axis, reused. **[PROPOSAL]** "Supported" is **not** "verified": a hypothesis with supporting discriminating evidence remains a hypothesis (or is promoted to belief) until independent, executed assurance passes — it never becomes a FACT on the strength of its own supporting evidence. Promotion rule: hypothesis→belief requires the named discriminating evidence to resolve; belief→fact requires an admissible-trust *observation* (not a model verdict). A hypothesis stays type-distinct from a fact until it crosses the assurance boundary (Phase 8).

---

## 15. Prediction / outcome separation (Part M)

**[PROPOSAL]** PREDICTION → ACTION → OBSERVED OUTCOME → COMPARISON, with prediction and outcome in the same ledger but **never** collapsed. A prediction does not become an outcome because an action executed. The Part M example — prediction "rollback restores replicas to 3," observation "replicas became 2" — preserves both records; their diff is the prediction error. **[SOURCE + INFERENCE]** This is the foundation the calibration (§13) and future prediction-error learning (Zero Phase §10) build on, and it is the one differentiator (outcome-calibrated confidence) the research found genuinely underserved. **[FACT]** This is distinct from execution success (Part R): the execution outcome "the call completed" is *provenance for* a later world-state observation, not the observation itself.

---

## 16. Memory vs world model (Part Q)

**[SOURCE]** No surveyed agent-memory framework (Letta/MemGPT, Mem0, A-MEM) separates "what I remember/was told" from "what is true about the external world" — all let model-generated content become stored memory on the write path, which is the MINJA/AgentPoison vulnerability. **[FACT]** CortexPrime's existing memory subsystem is exactly this: `MemoryOrchestrator.consolidate_session` writes an LLM summary into `semantic_memory` with `confidence=1.0`, cross-tenant (STOP-1/2). **[PROPOSAL]** Explicit separation, both retained:

- **MEMORY** answers *"what happened in previous interactions / what did the agent do?"* — episodic + semantic + procedural, advisory (I7), may be model-written, quarantined from world truth.
- **WORLD** answers *"what is believed true about the external system?"* — the World Plane, facts from observations only.

**[PROPOSAL]** The interface: memory may *provide provenance for* a world update (an episodic record "agent ran `kubectl get pods` at T" is provenance for the observation it produced) but is **never** itself world truth. A memory of a fact is not a fact. The World Plane ingests the *observation* the memory references, with its provenance, not the memory's content.

---

## 17. World query boundary (Part N) + 18. World → Harness interface (Part P)

**[PROPOSAL]** Different consumers get different **views**, none gets the whole database (directly countering the existing pattern where the entire memory bag is dumped into a prompt):

| Consumer | View | Rationale |
|---|---|---|
| **Governance** | fresh, authoritative FACTS only (admissible trust, within freshness window) | authority decisions need truth, not beliefs |
| **Intelligence (model)** | beliefs + hypotheses + contradictions + facts, each *labeled* with epistemic status, confidence, freshness, provenance | reasoning needs the full epistemic picture, honestly typed |
| **Assurance** | raw observations + full provenance | verification checks the evidence, not the conclusion |
| **Execution** | only explicitly authorized world state | least privilege |

**[SOURCE + PROPOSAL]** The World→Harness interface (Part P) is a **typed World Query → Context Assembly → Model** path, designed now, **not implemented** (the full Context Assembly Engine is a later phase). Query semantics: typed retrieval (by entity/claim-type), freshness constraints (refuse or mark stale), tenant scope (mandatory), provenance inclusion, contradiction inclusion, confidence/calibration inclusion, token budget. The model receives *"here are the relevant claims and why we believe them"* (claim + epistemic status + provenance + confidence + freshness), never *"here is the entire database."* This is the World-Plane input to the Phase 6.0 Context Assembly Engine design — the CAE consumes World Plane views.

---

## 19. World → Governance boundary (Part O) — critical

**[PROPOSAL + FACT]** The most important boundary. World Plane information may *inform* authorization, capability selection, planning, tool exposure, and execution **only as evidence/context** — it may **never** silently become authority. World says *"production is unhealthy"* → that does **not** authorize *"restart production."* Authorization remains independent (the Phase 5 capability fabric); the World Plane provides the evidence the epistemic gate (Zero Phase §6.4) reads to decide whether a justification is *fresh and factual enough* to proceed — but the *grant* is governance's, unchanged. **[INFERENCE]** Concretely: a plan may cite a World Plane fact as justification; the epistemic gate checks that fact is a FACT (not a belief), fresh, uncontradicted, provenanced — and if so *permits the plan to be considered*; the capability authorization then decides, separately, whether the principal may perform the action. Two independent gates. This satisfies L1 (one plane of action), L4 (cognition cannot grant authority), and the Part Z condition "world state must not bypass governance." **[PROPOSAL]** Fitness rule `BND-WORLD-CANNOT-EXECUTE` (§24) enforces structurally that no World Plane module imports a connector, the gateway, or the execution plane.

---

## 20. Tenant isolation (Part S)

**[FACT]** Every existing memory/world store except the `cp_*` fabric is cross-tenant (STOP-2): `semantic_memory`/`episodic_memory`/reflection have no `tenant_id`; every JSON store is process-global. **[PROPOSAL]** Every World Plane record — observation, fact, belief, hypothesis, prediction, provenance node, contradiction — carries a mandatory `tenant_id` (following the `cp_*` template and the Phase 6 `RepositoryGuard`), and **world queries fail closed on tenant ambiguity** (the storage guard's `is_repository_context` fail-closed fix from Phase 6.2 is the pattern). Threats to close: cross-tenant reads, provenance leakage, contradiction leakage, source-metadata leakage, cached-retrieval leakage. **[PROPOSAL]** Fitness rule `BND-TENANT-SCOPED-WORLD` (§24). No shared cache spans tenants.

---

## 21. Security threat model (Part U)

**[SOURCE + PROPOSAL]** Threat model and the boundary that answers each:

| Threat | Evidence | Defense |
|---|---|---|
| **Model-generated facts** | MINJA >90%, AgentPoison ≥80% at <0.1% poison [SOURCE] | **The ingestion boundary — the payoff of the whole design.** Only provenanced observations from instruments write facts; the model proposes hypotheses/beliefs (typed, quarantined, UNCALIBRATED), never facts. `BND-MODEL-CANNOT-CREATE-FACT`. |
| **Prompt injection / poisoned observations** | reliability-conditional paper [SOURCE] | provenance-tier trust cap (`min(ceiling, content)`); low-trust channels cannot raise trust; taint-tracking noted as the laundering defense (Phase 7.x, not 7.1). |
| **Malicious tools / false provider responses** | — | observations carry source authority; a low-authority source cannot mint a high-trust fact; contradiction with corroborating sources surfaces it. |
| **Stale data** | STALE 55.2% [SOURCE] | freshness-at-use gate (§10). |
| **Cross-tenant claims** | existing STOP-2 [FACT] | mandatory tenant scope, fail-closed queries (§20). |
| **Forged provenance** | — | provenance references immutable Phase 5 anchors (audit chain, execution ids) by id; a forged reference dangles and is detectable. |
| **Replayed observations** | — | observations carry `observed_at` + source id + idempotency; a replay is a duplicate observation, deduped, not a new fact. |
| **Conflicting sources** | truth-discovery [SOURCE] | CONFLICTED first-class (§11), never auto-resolved. |

**[PROPOSAL]** The overriding invariant: **MODEL OUTPUT MUST NOT BECOME WORLD FACT without the defined ingestion boundary.** This is the single most evidence-backed, least-productized differentiator (§23).

---

## 22. Existing architecture KEEP / REPLACE / DELETE

**[PROPOSAL]** (Consolidating §3–4.)
- **KEEP:** `cp_*` durable fabric (template + provenance anchors), `cp_audit_record`/`cp_harness_trace` (provenance references), `contracts/_contract.py` base, `contracts/execution.py` enums (reuse), the live `TrustLevel` + `VerificationStatus` discipline, conversation memory (as memory, quarantined).
- **EXTEND (salvage into World Plane primitives):** `evidence.py` `SourceStatus` + `Citation` (best seed), `evidence.py` `EvidenceSet` discipline, `knowledge.py` `KnowledgeKind`/`KnowledgeAuthority` + I7.
- **REPLACE (strangler targets):** `data/infrastructure/*.json` (19 files), `repository_brain.json`, `github_*.json` caches, `runtime_store.json` (V1 execution) → World Plane facts + `cp_execution`, `enterprise_engineering_memory` derived views.
- **DEPRECATE:** `knowledge.py` `AssembledContext` (dead + collision); the dead `contracts.knowledge`/`contracts.evidence` record shapes once replaced.
- **DELETE:** confirmed 0-byte `services/graph_service.py`; the destructive-upsert `track_*` paths once the ingestion boundary exists.
- **QUARANTINE (must never feed the World Plane):** LLM-written `semantic_memory` consolidation; all cross-tenant stores.

---

## 23. Competitive / whitespace analysis (Part W)

**[SOURCE]** Honest assessment — every primitive is built by someone; do not claim "nobody has built this":
- **Commodity (adopt):** bitemporal storage (Snodgrass/SQL:2011, XTDB, Datomic); provenance vocabulary (W3C PROV-O, PROV-AGENT); post-hoc calibration math (Platt/isotonic/ECE); truth-discovery algorithms.
- **Done by someone (credit):** bitemporal *agent memory* — **Zep/Graphiti** (4-timestamp edges, invalidation-not-deletion, provenance, as-of queries) — but targets conversational memory, not external-system operational state, and its validity decisions are LLM-driven. Provenance-tiered anti-poisoning — the reliability-conditional paper (leaves taint-tracking unimplemented). Live-system discovery + confidence-ranked RCA — **Cleric** (read-only, layered confidence), **Traversal** (multiple confidence-ranked root causes, causal ML), **Datadog Bits AI**, **Resolve.ai**.
- **[INFERENCE] Genuinely underserved / the real differentiator:** (1) the **composition** of bitemporal world state + graph-linked provenance + contradiction-as-first-class + outcome-calibrated confidence + memory/world separation + ingestion boundary into one *governed* substrate — no surveyed system composes all six; (2) the **ingestion boundary** keeping model output out of world facts (the most evidence-backed, least-productized property — Cleric's read-only stance is about *actions*, not an epistemic write-boundary on *beliefs*); (3) **CONFLICTED/UNKNOWN/STALE as first-class action-gating states**; (4) **confidence calibrated from logged action→outcome**, not verbalized (no public evidence Traversal's confidence is outcome-calibrated). **[INFERENCE]** Strategic anchor: the two enterprise world-model papers (WoW "dynamics blindness"; CascadeBench runtime-discovery-beats-learned) prove agents cannot self-simulate side effects and that runtime discovery into a structured store beats learned simulation under drift — the empirical reason a queryable World Plane that *informs but never executes* should exist.

---

## 24. Fitness rule proposals (Part Y)

**[PROPOSAL]** Proposed, not yet implemented (7.0 is discovery; each lands in the 7.x that builds the corresponding code, with CURRENT=PASS / SYNTHETIC=FAIL sensitivity tests, per the Phase 6 discipline). Each protects a real, discovered risk:

| Rule | Invariant | Synthetic violation that must FAIL |
|---|---|---|
| `BND-MODEL-CANNOT-CREATE-FACT` | no intelligence/model-plane module writes the Fact/Observation ledgers; only the deterministic ingestion boundary does | a harness/agent module importing the fact-writer |
| `BND-WORLD-CANNOT-EXECUTE` | no World Plane module imports a connector, the invocation gateway, an adapter, or the execution plane | a world module importing `backend.connectors` or the gateway |
| `BND-TENANT-SCOPED-WORLD` | every World Plane record type has a `tenant_id`; every query goes through the tenant guard | a world table/record without `tenant_id`; a query bypassing the guard |
| `BND-PROVENANCE-REQUIRED` | no fact/belief is constructed without a provenance link | a fact-writer path that admits an empty provenance |
| `BND-TEMPORAL-INTEGRITY` | World Plane records are append-only-with-supersession; no destructive UPDATE/overwrite of a fact's history | a world module issuing an UPDATE that overwrites `valid_from`/history |
| `BND-CONTRADICTION-NOT-SILENTLY-DROPPED` | conflicting claims produce a CONTRADICTION record; no code path picks a winner silently | an ingestion path that overwrites a claim with a conflicting one and discards the prior |
| `BND-NO-SECRET-IN-PROVENANCE` | provenance nodes carry references/hashes, never secret material (firewall on the write path) | a provenance writer admitting a value that `find_secrets` flags |

**[INFERENCE]** These are not cosmetic — each maps directly to a STOP-condition violation found in the *existing* substrate, so each has a demonstrable real-world violation shape.

---

## 25. Phase 7.1–7.x roadmap (Part X)

**[PROPOSAL]** Reordered from the suggested sequence, because discovery shows the security-critical, differentiating invariants (no model-authored facts, tenant scope, provenance, ingestion boundary) are the highest-value and the existing violations are live — they go first, not last.

- **7.1 — Ontology + contracts + the ingestion boundary.** Mint the World Plane primitives by salvaging `evidence.py` (`SourceStatus`, `Citation`) and `knowledge.py` (`KnowledgeKind`/`KnowledgeAuthority`/I7), subclassing `Contract`; add tenant, bitemporal fields, provenance links, epistemic-status + trust + authority axes. Define the Observation and Claim ledger contracts (no persistence yet). Establish `BND-MODEL-CANNOT-CREATE-FACT` and `BND-WORLD-CANNOT-EXECUTE` as the founding invariants. Resolve the `AssembledContext` collision. **Exit: the type discipline exists and the model-cannot-create-fact boundary is a fitness rule.**
- **7.2 — Observation ingestion + tenant scoping.** The deterministic ingestion boundary: connector reads → provenanced observations (append-only, `cw_observation` under Alembic), tenant-scoped, fail-closed. Strangle the first destructive JSON path (infra snapshots). `BND-TENANT-SCOPED-WORLD`, `BND-PROVENANCE-REQUIRED`, `BND-NO-SECRET-IN-PROVENANCE`. **Exit: one real connector read becomes a provenanced, tenant-scoped observation; no model can write one.**
- **7.3 — Bitemporal fact derivation.** Deterministic rules: observations → facts with valid-time + transaction-time; supersession-not-deletion; as-of queries. `BND-TEMPORAL-INTEGRITY`. **Exit: the Part E temporal test answers deterministically against real Postgres.**
- **7.4 — Provenance graph** (PROV-O shaped, referencing Phase 5 anchors).
- **7.5 — Contradiction handling** (CONFLICTED first-class; `BND-CONTRADICTION-NOT-SILENTLY-DROPPED`).
- **7.6 — Freshness** (validity windows; freshness-at-use gate).
- **7.7 — Belief revision** (append-only history; as-of "what did we believe" queries).
- **7.8 — Hypothesis lifecycle** (open→supported/refuted; promotion rules; reuse `VerificationStatus`).
- **7.9 — Prediction/outcome ledger** (sealed predictions; the calibration substrate).
- **7.10 — World query interface + views** (typed, per-consumer, tenant-scoped; feeds the CAE).
- **7.11 — Harness/CAE integration** (World views → Context Assembly → model).
- **7.12 — Security hardening + full tenant-isolation verification** (poisoning, taint-tracking, replay).
- **7.13 — Full World-Plane verification** (real-Postgres, real-process, the Part E/I/J tests as committed evidence).

**[INFERENCE]** Source-authority statistics (§9) and outcome-calibration statistics (§13) are deliberately *deferred within* 7.9+/7.12 — schema first, statistics once outcome history exists, exactly as the research (calibrate from your own logs) prescribes.

---

## 26. Explicit contradictions (Part Z)

**[FACT]** The Part Z scan found three flagged conditions **TRUE of the existing V1 substrate**, with file evidence:
- **Model output → world store with no ingestion boundary:** `MemoryOrchestrator.consolidate_session` writes an LLM summary into `semantic_memory` at `confidence=1.0` (`memory_orchestrator.py:240-268`, `compression_engine.py:75-86`, `semantic_store.py:74-102`).
- **Cross-tenant world/memory stores:** `semantic_memory`/`episodic_memory`/reflection have no `tenant_id` (`semantic_memory.py:36-48`); all JSON stores are process-global (`legacy_persistence_inventory.py:162-174`).
- **Destructive temporal overwrite:** infra `track_*` upserts in place and rewrites the file (`enterprise_infrastructure_intelligence.py:160-183`); `repository_brain` overwrites wholesale (`enterprise_repository_brain.py:368-369`).

**[INFERENCE] These do not halt Phase 7.0 and do not contradict the Phase 6 architecture.** They are properties of the *existing dead/V1 world-state substrate* — the very thing the World Plane replaces — not of the proposed design. Per Part Q, the memory subsystem is a *separate concern* (memory, not world) that coexists with the World Plane; it does not "conflict fundamentally," it is *walled off*. The proposed World Plane design *inverts* all three (ingestion boundary, mandatory tenant scope, append-only-with-supersession). **[PROPOSAL] The hard constraint they impose:** the World Plane must be a new clean substrate (`cw_*` under Alembic, the `cp_*` template), must **never** be layered on or fed by these stores, and the existing stores are strangler/quarantine targets — exactly as the 76 JSON stores were named in the Zero Phase. **[FACT]** No Part Z condition about the *proposed World Plane* is violated: it has no execution path, no model-authored facts, mandatory tenant scope, non-destructive history, reconstructable provenance, freshness-as-state, contradiction-as-record, and it sits behind governance. **No architectural contradiction requiring a redesign was found.**

---

## 27. ADR-062 proposal

**[PROPOSAL]** *ADR-062 — The World Plane: a governed epistemic substrate.* Records: (1) the World Plane is a new read-authority plane that informs but never executes (`WORLD → INTELLIGENCE → HARNESS → GOVERNANCE → EXECUTION`); (2) four ledger families (Observation, Claim=fact+belief, Hypothesis, Prediction/Outcome) over one bitemporal + provenance + tenant spine subclassing `Contract`; (3) the ingestion boundary — only provenanced observations become facts, the model proposes hypotheses/beliefs never facts (`BND-MODEL-CANNOT-CREATE-FACT`); (4) salvage `evidence.py`/`knowledge.py` epistemic vocabulary, replace their record shapes, deprecate the dead `AssembledContext`; (5) the existing V1 world-state stores are strangler/quarantine targets, never World Plane inputs; (6) authority (knowledge) and trust (verification) unified as orthogonal axes on the Claim primitive, with confidence UNCALIBRATED until outcome history exists; (7) the seven founding fitness rules (§24). To be written and ratified at the start of Phase 7.1.

---

## 28. Definition of Done for Phase 7.1

**[PROPOSAL]** Phase 7.1 (ontology + contracts + ingestion boundary) is complete only when:
1. This discovery report and its §22 KEEP/REPLACE/DELETE/DEPRECATE/QUARANTINE dispositions are ratified.
2. ADR-062 is written and its seven decisions ratified or amended.
3. The World Plane primitive contracts exist (Observation, Claim with epistemic-status + authority + trust axes, provenance link, bitemporal + tenant fields), subclassing `Contract`, salvaging `SourceStatus`/`Citation`/`KnowledgeAuthority`/I7 — **as contracts only, no persistence, no execution path.**
4. `BND-MODEL-CANNOT-CREATE-FACT` and `BND-WORLD-CANNOT-EXECUTE` are implemented as un-grandfathered fitness rules, each CURRENT=PASS / SYNTHETIC=FAIL.
5. The `AssembledContext` name collision is resolved (one type).
6. The five non-collapses (fact≠belief≠hypothesis≠prediction≠outcome≠verification) are enforced as unconvertible types with tests.
7. Every claim in the phase is labeled [FACT]/[SOURCE]/[INFERENCE]/[PROPOSAL]; no inference is silently converted to fact.
8. **No persistence, no ingestion, no world query is built** — 7.1 is types and boundaries only. No World Plane store, no `cw_*` table, no execution influence exists yet.
9. Phase 5.5 credential blocker untouched; L1–L16 intact; no second execution/governance/coordination authority introduced.

*Then* Phase 7.2 (observation ingestion) begins.

---

*Compiled from three read-only discovery sweeps (repository world-state audit with file:line evidence; deep read of the dead epistemic contracts; 2024–2026 literature with inline citations) synthesized against the ratified Zero Phase ontology and the Phase 6 harness architecture. No source code, contracts, migrations, or stores were modified. Every statement labeled [FACT]/[SOURCE]/[INFERENCE]/[PROPOSAL] per the research standard.*
