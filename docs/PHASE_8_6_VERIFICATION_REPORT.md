# PHASE 8.6 — VERIFICATION REPORT

Date: 2026-08-12 · Branch `phase-1-foundation` · ADR-077 · **No new migration/table** (episode is a projection over cw_investigation + cw_reasoning + cw_verification)

Labels: **VERIFIED** · **NOT VERIFIED** · **DEFERRED** · **BLOCKED**. Distributed claims cite `tests/intelligence/test_investigation_experience.py` (**26 passed**), `tests/intelligence/test_intelligence_fitness.py` (fitness, incl. 4 new), and the real-Postgres harness `scripts/phase86_experience_harness.py` (**21 checks, 0 fail, verdict VERIFIED** vs a fresh `cortex_p86`). Real LLM BLOCKED; `provider="scripted"`.

## 1. Discovery — reuse, no duplication (Part A)
**VERIFIED** No episode/incident/experience contract existed (net-new); `incident_ref` is opaque (facets derived); the durable ledgers already hold everything an episode needs. **No vector DB / embeddings / Neo4j built** — structured facet retrieval satisfies the first useful capability. Reused: the `Investigation` aggregate (projection source), the `ReasoningLedger`/cw_reasoning (calibration sink), `ContextAssembler`, the `SqlInvestigationRepository`.

## 2. Incident/Investigation episode typed (Part B)
**VERIFIED** `InvestigationEpisode` (contract) references incident/investigation/tenant, facets, hypotheses (reference summaries), tests/observations/predictions/verifications (refs), disposition, residual, timestamps, harness version, model identity, assurance status. It holds **references, never copies** of World objects (unit `TestEpisodeContract`).

## 3. Completed investigation reconstructable (Part D)
**VERIFIED** `EpisodeProjection.project` reconstructs an episode from the terminal investigation snapshot; only TERMINAL investigations project (`test_non_terminal_is_not_reusable`). RESOLVED means "that investigation reached this disposition on the evidence available then" — carried with resolution, evidence refs, assurance status, residual.

## 4. Experience ≠ World truth (Part C) — the load-bearing invariant
**VERIFIED** `InvestigationEpisode` has **no `to_fact` / `to_belief` / `to_outcome` / `to_verification` method** (unit `test_episode_has_no_truth_minting_methods`). It exposes only status STRINGS + refs. Harness `[P]`: E123 found H4 (dependency) supported, but E456's current world REFUTES H4 — `E123.h4=supported` while `E456.h4=refuted`; history did not become current truth.

## 5. Cannot create Fact/Belief/Outcome/Verification (Part C/I/U#11)
**VERIFIED** Structurally: the episode contract omits any mint method, and `BND-MODEL-CANNOT-CREATE-FACT` forbids `backend.intelligence` from importing the World grounded constructors (Phase 8.5, still PASS). An adversarial model output ("fact: database saturation is causing latency") remains an untrusted proposal — the platform still requires a fresh governed test (harness `[P]`).

## 6. Retrieval is tenant-scoped (Part J)
**VERIFIED** `list_terminal` is tenant-scoped in SQL (stronger than app filtering). Unit `test_tenant_isolation`: ACME sees none of OTHER's episodes. Harness `[J]`: cross-tenant retrieval returns no episodes; cross-tenant reconstruct fails closed.

## 7. Retrieval is temporally safe (Part K / U#8)
**VERIFIED** `reconstruct_as_known` filters events to `recorded_at ≤ known_at`: unit `test_evidence_learned_after_t2_absent_in_as_known_view` (wobs-late linked at 10:15 is absent from the as-known-10:12 view). Harness `[K]`: the as-known-10:02 view of E123 has no terminal conclusion (no future leak); retrieval excludes an episode completed after the as-known cutoff (unit `test_temporal_safety_future_episode_excluded`).

## 8. Historical evidence carries provenance (Part K/L)
**VERIFIED** Each `ExperienceMatch`/episode carries episode_ref, match reasons, assurance status, quality, residual, episode_time, model identity, harness version, and reference lists — the diagnostic explanation is reconstructable from references.

## 9. Assurance status preserved (Part L/M)
**VERIFIED** `AssuranceStatus` (ASSURED/UNASSURED/INSUFFICIENT_EVIDENCE/CONFLICTED) and `ExperienceQuality` (categorical, **no numeric confidence**) map onto existing Verdict/Conclusion/HypothesisStatus. DIRECTLY_ASSURED requires a `Verdict.SUPPORTED` (unit `test_directly_assured_requires_supported_verdict`); a verification without support is not assured (`test_verification_without_support_is_not_assured`). Harness `[E]`: E123 is UNASSURED — "historically supported, NOT independently verified".

## 10. Context Assembly labels experience (Part H)
**VERIFIED** A `HISTORICAL_INVESTIGATION_EXPERIENCE` section (in `SECTION_ORDER`, folded into `context_digest`) carries the episodes with provenance="experience-memory", an explicit caveat "not current world truth", episode_ref, match reason, timestamp, assurance status, residual. Harness `[P]`: the section is present and labelled HISTORICAL; no `world_evidence`/authoritative section carries the episode.

## 11. Model cannot promote history to truth (Part I/U)
**VERIFIED** The model receives experience as labelled history and proposes tests/hypotheses (existing 8.4/8.5 firewalls). Harness `[P]`: despite E123 saying "dependency", the platform ran a FRESH governed read and H4 was REFUTED — no model claim promoted history to current truth.

## 12. Historical test ideas reusable; authorization is not (Part Q)
**VERIFIED** E456's model reused the dependency-latency test IDEA; the platform re-validated and re-governed it through the current One Plane of Action, producing a **fresh governed read** (harness `[P]`: provider call incremented). The episode carries no credentials and no live authorization — historical authorization/credentials/provider are never reused.

## 13. V1 memory cannot contaminate World truth (Part O/W)
**VERIFIED** New rule **BND-WORLD-CANNOT-IMPORT-V1-MEMORY**: no `backend.world`/`backend.assurance` module may import `backend.memory`/`backend.cognitive_memory`/`backend.cortex_memory`/`memory_context_service` (the "KNOWN FACTS" anti-pattern). CURRENT = **PASS**; SYNTHETIC = **FAIL** (unit `TestWorldCannotImportV1Memory`: world/assurance importing V1 memory fails; the reasoning ledger is allowed). No dual-write, no silent migration. Gate: **34 passed, 0 failed, 6 skipped across 1166 modules**.

## 14. Crash recovery (Part R)
**VERIFIED (load-bearing)** Real `os._exit(9)` mid experience-assisted investigation: harness `[R]` — the historical episode E123 is **byte-for-byte immutable** across the crash (`to_dict()` identical before/after), the crashed investigation reconstructs (not fabricated), and no historical mutation / duplicate episode occurs. **DEFERRED**: the exhaustive 7-point crash matrix.

## 15. Replay inert (Part S)
**VERIFIED** Five reconstructions + retrievals did **0** provider calls, **0** world mutations, **0** new reasoning records (harness `[S]`). Reading historical episodes and reconstructing context is a read-only reconstruction, never converted to live execution.

## 16. Calibration-ready experience evidence (Part T)
**VERIFIED** `ReasoningKind.EXPERIENCE_USE` records (in cw_reasoning, **no new table**) that episode E123 was retrieved into E456, with match reasons, categorical assurance/quality, and a current-outcome hint — references only, **no confidence/score** (harness `[T]`). Whether experience helped or misled is computed later (Phase 8.7), never asserted here.

## 17. Performance (Part V)
**VERIFIED (measured)** Actual numbers (harness `[V]`, `cortex_p86`): episode retrieval ≈ **11 ms**, context-assembly overhead ≈ **2.6 ms**, total E456 investigation ≈ **1.66 s** (dominated by the governed reads). No speculative indexes/infrastructure added.

## 18. Adversarial contamination (Part U)
**VERIFIED** (1) historically supported ≠ current fact (E123.h4 supported, E456.h4 refuted); (2) historical assurance ≠ current verification (categorical status, not a WorldVerification); (3–7) episode holds refs not objects, no authorization/provider/tenant carried; (8) evidence after T2 absent from as-known T2 view; (9–10) stale/conflicted stay categorical, never certainty (`test_conflicted_stays_conflicted_not_certain`); (11) model cannot promote experience to Fact (no mint method + fitness); (12) episode is immutable (frozen dataclass — `test_episode_is_immutable`). Every case fails closed.

## 19. Architecture fitness / regression (Part W/X)
**VERIFIED** Gate **34/0/6**. `pytest tests/intelligence tests/world tests/assurance tests/harness tests/architecture tests/contracts` → **853 passed** (2 collection warnings: domain enum/exception). No suppressed failures, no weakened assertions. Contract change (additive `ReasoningKind.EXPERIENCE_USE`, additive `historical_experience` assembler param, additive episode contract) — no supersession of existing behaviour.

## Counts (harness, cortex_p86)
investigation_events=40 · reasoning_records=1 (the EXPERIENCE_USE record) · provider_calls=4. E456 differential: h1=supported (deployment), h2/h3/h4=refuted — a DIFFERENT current cause than E123 (dependency), proving experience is relevant but not truth.

## NOT built / DEFERRED (honest)
- **DEFERRED** Semantic similarity / embeddings / vector store / Neo4j — structured facet retrieval suffices; no calibrated basis for a score.
- **DEFERRED** A first-class incident contract with facets (derived from incident_ref today).
- **DEFERRED** Numeric calibration (Phase 8.7); exhaustive 7-point crash matrix.
- **BLOCKED** Real LLM leg (Phase 5.5 untouched) — `provider="scripted"`.
- **NOT claimed** Exactly-once.

## Verdict
**VERIFIED** — CortexPrime retains the experience of completed investigations and reuses it safely: experience is a reference-only projection (no new table), retrieval is deterministic/explainable/tenant-scoped/temporally-safe, historical experience is explicitly labelled and can never mint World truth, test ideas are re-governed (never historical authorization), the calibration substrate is captured, and the World Plane is newly fenced from V1 memory — against real Postgres, real LLM BLOCKED, no second memory architecture, no vector/graph infrastructure, no numeric confidence, no exactly-once claim.
