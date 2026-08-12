# ADR-077 — Incident Episodes & Investigation Experience Memory

Status: Accepted · Date: 2026-08-12 · Phase 8.6 · Follows ADR-073/074/075/076 and ADR-062–072

## Context

Phases 8.2–8.5 gave CortexPrime a durable investigation, a differential, and a prediction lifecycle. Phase 8.6 lets it retain the EXPERIENCE of completed investigations and reuse it — without letting experience become world truth. The central distinction is `WORLD TRUTH ≠ INVESTIGATION EXPERIENCE ≠ MODEL MEMORY`: the system can say "three prior incidents with these symptoms involved database saturation, under different conditions, and this one has not established that cause" — useful memory without epistemic contamination. Discovery confirmed no episode/incident contract exists, `incident_ref` is opaque (facets must be derived), and the durable ledgers (cw_investigation + cw_reasoning + cw_verification) already hold everything an episode needs. So an episode is a **projection**, not new state, and Phase 8.6 adds **no new table** and **no vector/embedding/graph infrastructure**.

## Decisions

**1. An episode is a reference-only projection, not a copy.** `InvestigationEpisode` (a new contract) summarises a completed investigation as references (episode/test/evidence/prediction/verification refs) and categorical summaries (facets, quality, assurance status, residual). It is reconstructed by `EpisodeProjection` from the `Investigation` aggregate (+ optional cw_verification verdicts). It **deliberately has no `to_fact` / `to_belief` / `to_outcome` / `to_verification` method** — that absence is the experience-is-not-truth firewall (Part C). Only TERMINAL investigations project (Part D); a resolved episode means "that investigation reached this disposition on the evidence available then", never "globally true".

**2. No new durable ledger (Part N).** Every episode field is reconstructable from cw_investigation (+ cw_reasoning for predictions/evaluations, cw_verification for verdicts). So no `cw_episode`/`cw_memory`/`cw_experience` table is created. The one genuinely non-derivable artifact — that a prior episode was *retrieved into* a current investigation (the calibration substrate, Part T) — reuses cw_reasoning via a new `ReasoningKind.EXPERIENCE_USE` (the `kind` column is already a free string; no migration). It is references-only and secret-firewalled like every reasoning record.

**3. Deterministic, explainable relevance before similarity (Part F).** `StructuredExperienceRetrieval` matches episodes on categorical facets — service / environment / symptom class / resource types — derived deterministically from the incident reference and the prior differential. A match carries its **reasons** ("service=payments-api matched; symptom=latency-spike matched; resource types overlap"), and ranking is a count of matched dimensions, tie-broken deterministically. There is **no embedding, no vector store, no similarity score** — the first useful capability is fully explainable.

**4. Tenant isolation at the storage boundary (Part J).** Retrieval reads terminal investigations through `SqlInvestigationRepository.list_terminal`, which is tenant-scoped in SQL (a stronger boundary than application filtering). Cross-tenant retrieval returns nothing; cross-tenant reconstruct fails closed.

**5. Temporal safety (Part K).** `latest_state_as_known` / `reconstruct_as_known` reconstruct "what the investigator knew at T2" by filtering events to `recorded_at ≤ known_at`, so evidence learned later cannot appear in a past-knowledge view. Retrieval excludes episodes that completed after an as-known cutoff. Incident time, investigation time, completion time, and retrieval time stay distinct — reusing the bitemporal World Plane, no second temporal model.

**6. Context Assembly labels experience as history (Part H).** A new `HISTORICAL_INVESTIGATION_EXPERIENCE` section (added to the fixed `SECTION_ORDER`, folded into the reproducible `context_digest`) carries each episode's ref, match reasons, relevant hypotheses/tests, assurance status, quality, residual, and episode time — with an explicit caveat "historical experience, not current world truth; acquire fresh evidence". It is never `world_evidence` and never authoritative state. The engine injects it via an optional `experience_port`; without one, behaviour is unchanged.

**7. Assurance status is preserved and categorical (Part L/M).** `ExperienceQuality` (DIRECTLY_ASSURED / SUPPORTED / PARTIALLY_SUPPORTED / UNRESOLVED / CONFLICTED / INSUFFICIENT_EVIDENCE) and `AssuranceStatus` (ASSURED / UNASSURED / INSUFFICIENT_EVIDENCE / CONFLICTED) map onto the existing `InvestigationConclusion` / `Verdict` / `HypothesisStatus` vocabularies — no new epistemic axis, **no numeric confidence**. DIRECTLY_ASSURED requires an actual `Verdict.SUPPORTED`; absent the verdict, an episode is conservatively UNASSURED. So the investigator can distinguish "historically supported" from "independently verified" from "current-world evidence".

**8. Test IDEAS are reusable; authorization is not (Part Q).** A current investigator may reuse the *semantic test pattern* of a historical episode (e.g. "check dependency latency"), but the test is re-validated and re-governed through the current One Plane of Action against current tenant scope and policy. Historical execution authorization, credentials, and provider details are never reused — an episode carries no credentials and no live authorization (it holds refs).

**9. Fitness: BND-WORLD-CANNOT-IMPORT-V1-MEMORY (Part O/W).** `BND-NO-V1-INTELLIGENCE-IMPORT` already fences `backend.intelligence` from the V1 memory stack, but the WORLD/ASSURANCE planes — including the durable reasoning ledger under `backend.world.application` — were **not** gated. The new rule forbids any `backend.world` / `backend.assurance` module from importing a V1 memory package (`backend.memory`'s MemoryOrchestrator/semantic "KNOWN FACTS", `backend.cognitive_memory`, the memory_context_service), preventing a dual-write of model memory into the World ledgers as truth. CURRENT = PASS; SYNTHETIC = FAIL (both tested). The "experience cannot mint World truth" invariant is otherwise already enforced by `BND-MODEL-CANNOT-CREATE-FACT` (the episode contract has no mint method, and intelligence cannot import the World grounded constructors), so no redundant rule was added there.

## Explicit non-goals

No vector database, no embeddings, no Neo4j, no second memory architecture, no new execution/governance/model gateway, no numeric confidence/calibration (only the substrate is captured), no dual-write or silent migration of V1 memory. Exactly-once is not claimed.

## NOT built / deferred (recorded honestly)

- **Semantic similarity retrieval** — deliberately deferred; structured facet retrieval satisfies the first useful capability, and no calibrated basis for a similarity score exists.
- **An incident contract with first-class facets** — none exists, so facets are derived from `incident_ref` + the differential (best-effort, explainable); a real incident model is future work.
- **The full 7-point crash matrix** — the load-bearing boundary (crash mid-experience-assisted investigation; history immutable, investigation resumes, no fabrication) is proven; an exhaustive sweep is deferred.
- **Numeric calibration** — Phase 8.7 consumes the EXPERIENCE_USE substrate; 8.6 computes no calibration and no confidence.

## Consequences

CortexPrime remembers experience without remembering it as truth: the World Plane answers "what is true", the Investigation Plane "what are we investigating", and the Experience layer "what happened when we investigated similar situations before" — the model may use all three, but only the World Plane establishes current state, only Assurance verifies, only Governance authorizes, only Execution acts. The V1 memory stack remains quarantined. L1–L16, One Plane of Action, World immutability, independent Assurance, tenant isolation, the secret firewall, and the Phase 5.5 blocker are intact.
