# PHASE 8.4 — VERIFICATION REPORT

Date: 2026-08-12 · Branch `phase-1-foundation` · ADR-075 · No new migration (reuses 0019 + World ledgers)

Labels: **VERIFIED** (evidence this phase) · **NOT VERIFIED** · **DEFERRED** · **BLOCKED**. Distributed claims cite `tests/intelligence/test_differential_diagnosis.py` (**21 passed**), `tests/intelligence/test_intelligence_fitness.py` (fitness, incl. 4 new), and the real-Postgres harness `scripts/phase84_differential_harness.py` (**23 checks, 0 fail, verdict VERIFIED** vs a fresh `cortex_p84`). Real LLM BLOCKED; `provider="scripted"` throughout.

## 1. Discovery — reuse, no duplication (Part A)
**VERIFIED** Consumed, not rebuilt: `WorldQuery` (freshness + authority overlays), `FreshnessPolicy`/`AuthorityPolicy`, `BeliefFormation`/`CorroborationLevel`, the governed read path (Phase 7), the governed model boundary (8.3), the 8.1 `DifferentialHypothesis`/state machine, `EvidenceSelectionPolicy` (extended by classification, not replaced). No second executor/gateway/tracer/world-store/RAG/memory/scheduler. New code is one module (`differential.py`), an additive schema field, and engine wiring.

## 2. Differential diagnosis model (Part B)
**VERIFIED** Multiple competing hypotheses are independently represented; none collapse into one model answer. Each keeps evidence_for/against, missing_evidence, contradiction_refs, lineage_origins, temporal_fit, epistemic status. **No numeric confidence, no LLM score, no invented probability** (`DifferentialHypothesis.__post_init__` forbids a numeric status; unit `TestGaps`/harness `[P]` show 4 hypotheses tracked independently).

## 3. Evidence-gap analysis (Part C)
**VERIFIED** `analyze_gaps` deterministically computes, per live hypothesis: known, unknown, would-support, would-contradict, which competitors it bears against, and an explicit *unresolved reason*. The platform states "H1 remains unresolved because no discriminating observation of `deployment/payments` has been acquired yet" — never "H1 is most likely" (unit `TestGaps`; harness `[C]`).

## 4. Discriminating test selection (Part D)
**VERIFIED** A test names target hypothesis, tool, subject/predicate references, structured supports/contradicts expectations, and residual uncertainty (`ProposedTest` + `InvestigationTest`). The platform selects the most discriminating admissible candidate (`select_test`) — vague "gather more info" is impossible because a test without a structured expectation classifies NON_DISCRIMINATING and is dropped (unit `TestSelection`/`TestQualityClassification`).

## 5. Test quality scoring (Part E)
**VERIFIED / STOP-GATE HONOURED** `TestQuality` is categorical — DISCRIMINATING / PARTIALLY_DISCRIMINATING / NON_DISCRIMINATING / REDUNDANT / UNAVAILABLE / FORBIDDEN — **not** a numeric epistemic confidence. A test never becomes authoritative for scoring high (selection only orders admissible candidates, tie-broken on identity). **No numeric scoring mechanism was introduced**, so Part E's stop-and-document gate required no new architecture (unit `TestQualityClassification`).

## 6. Evidence reuse (Part F)
**VERIFIED** Before a governed read the engine consults the World read port; concrete + AFFIRMED + FRESH evidence is reused (no second read). Harness `[F]`: two hypotheses on one subject (`cache/redis`) resolve with **exactly one new governed read** (`delta == 1`), the second reusing the existing fresh World fact. Redundant identical tests are refused by identity before that (policy + `classify_test` REDUNDANT).

## 7. Authority / freshness / lineage (Part G)
**VERIFIED** The investigator consumes `WorldQuery` verdicts (`effective_value`, `effective_status`, `fresh.state`, `why.tier`) and never reclassifies them. Harness `[G]`: **STALE world evidence is NOT reused** (freshness ≠ truth) and **CONFLICTED is NOT reused** (conflict preserved, never overwritten); the world dict carries the `authority_tier` consumed from WorldQuery. Newer-low-authority-beats-older-authoritative and same-source-independence are the World Plane's decisions (Phase 7.4/7.5, unchanged), which the investigator honours by consuming `effective_value`. **UNKNOWN/STALE/CONFLICTED never become FALSE** (H1 stays OPEN; `settle` never emits FALSE — there is no FALSE state).

## 8. Hypothesis update (Part H)
**VERIFIED** After every read/reuse the differential updates from the OBSERVED/effective value vs the test's structured expectation — SUPPORTED / REFUTED, or OPEN when inconclusive. A model saying "H1 supported" never marks H1 supported (unit `TestAdversarial.test_favoured_hypothesis_not_supported_without_evidence`: the world contradicts the claim → REFUTED, not SUPPORTED; harness `[O]`).

## 9. Hypothesis state machine (Part I)
**VERIFIED / STOP-GATE HONOURED** The ratified World `HypothesisStatus` (OPEN/SUPPORTED/REFUTED/UNRESOLVED) is reused; **no FALSE, no VERIFIED** (verification belongs to Assurance). REFUTED = eliminated. The model cannot mutate status — the platform derives it from evidence. **No new state/transition was introduced** (Part I's stop-and-document gate required no change; richer WEAKENED/ELIMINATED distinctions are a derived view, documented in ADR-075, not persisted vocabulary).

## 10. Temporal diagnosis (Part J)
**VERIFIED** Observations carry `observed_at` (world time) and `recorded_at` (knowledge time) via the Phase 7 bitemporal ledger; the H1 test compares the deployment window against the incident window — deploy at 09:58 vs incident 10:03 (a 300s window) is temporally consistent but inconclusive → H1 stays OPEN. The three temporal facts (event / validity / knowledge) are never mixed (World Plane bitemporal, unchanged).

## 11. Evidence provenance (Part K)
**VERIFIED** Every used evidence item is traceable: governed reads produce real Observations/Facts (`obs=5, facts=5` in the harness) linked into the investigation via `evidence_refs`; the World read carries source_ref, authority tier, and observation ids. The differential is reconstructable from durable references, not free-text model memory (harness reconstruction preserves `test_refs`/`evidence_refs`).

## 12. Model responsibility (Part L)
**VERIFIED** The model proposes hypotheses / tests / interpretations only. It cannot create Fact/Belief/Verification/Outcome, change hypothesis status, choose authority/freshness/tenant/provider, execute, promote autonomy, or declare resolution — enforced by the 8.1/8.3 firewalls (extra="forbid"), the ports, and `BND-INTELLIGENCE-CANNOT-EXECUTE`/`-CREATE-FACT`. The platform evaluates every proposal.

## 13. Evidence selection policy (Part M)
**VERIFIED** `EvidenceSelectionPolicy.validate` + `classify_test` together enforce: tied to a real hypothesis, falsifiable, discriminating, structured expectation, tool declared + read-only, tenant-scoped, non-redundant, no arbitrary URL, no shell/code, no execution. Freshness/availability drive reuse vs read. **No provider call occurs before all checks pass** — FORBIDDEN/UNAVAILABLE tests reach zero reads (unit `TestAdversarial.test_shell_test_is_refused`/`test_unavailable_tool_causes_no_read`: `ev.calls == 0`).

## 14. Investigation prioritization (Part N)
**VERIFIED** The platform selects the next test (`select_test`) favouring DISCRIMINATING over PARTIALLY, deterministic tie-break — **not** "highest LLM confidence wins" and **not** model-dictated order (unit `TestSelection.test_prefers_discriminating_over_partial`, `test_selection_is_deterministic`). The engine owns the loop.

## 15. Adversarial (Part O)
**VERIFIED** A favoured hypothesis with no evidence is not promoted; "H1 is proven" is ignored; a shell/URL test is FORBIDDEN (zero reads); an unavailable tool causes zero reads; a redundant test is dropped; a test targeting an eliminated hypothesis is REDUNDANT; cross-tenant evidence is empty. Every attempt is reduced to an untrusted proposal (unit `TestAdversarial`; harness `[O]`/`[R]`).

## 16. DevOps vertical scenario (Part P)
**VERIFIED** Harness `[P]` vs `cortex_p84`: "Production API latency increased at 10:03", H1–H4. Result: **H2 REFUTED** (database normal), **H3 REFUTED** (network normal), **H4 SUPPORTED** (dependency elevated), **H1 OPEN** (deploy 09:58 temporally consistent but inconclusive — not FALSE). Conclusion **RESOLVED** with H4 leading, residual uncertainty naming the un-eliminated H1 and "not Assurance-verified"; `verification_refs` empty. "Supported, but not verified" is explicit — the core honesty capability.

## 17. Crash / replay (Part Q)
**VERIFIED** Real `os._exit(9)` mid-scenario: the successor reconstructs INVESTIGATING (**not fabricated**), pre-crash tests survive, and reconstruction does not repeat completed tests. **Replay inert**: five reconstructions did **0** new investigation events, **0** governed reads, **0** world mutations (harness `[Q]`). No provider reads / model calls / audit writes / transitions on replay.

## 18. Tenant isolation (Part R)
**VERIFIED** Cross-tenant reconstruct fails closed (`InvestigationNotFound`); cross-tenant World evidence is empty and non-affirmed (no leak of tenant A facts) — harness `[R]`.

## 19. Performance (Part S)
**NOT MEASURED / DEFERRED** No latency numbers were gathered and — per the instruction not to optimize before measuring — no speculative indexes were added. The harness records step/read counts (events=50, obs=5, facts=5, provider_calls=5) but not timings. **DEFERRED** to a measured pass.

## 20. Architecture fitness (Part T)
**VERIFIED** New rule **BND-INTELLIGENCE-CANNOT-BYPASS-WORLD**: `backend.intelligence` may not import `backend.world.infrastructure` (the World's SQL repos) — evidence only through the World application layer. CURRENT = **PASS** (the tree imports none); SYNTHETIC = **FAIL** (proven in `test_intelligence_fitness.py`, 4 cases: two rogue imports fail, WorldQuery/BeliefFormation allowed, own investigation ledger allowed). Gate: **33 passed, 0 failed, 6 skipped across 1163 modules**.

## 21. Regression (Part U)
**VERIFIED** `pytest tests/intelligence tests/world tests/assurance tests/harness tests/architecture tests/contracts/world` → **577 passed** (2 collection warnings: `TestQuality`/`TestRejected` are a domain enum/exception, not test classes). Nothing in Phases 5–8.3 regressed; no test weakened or suppressed. No ADR supersession needed (ADR-075 is additive).

## NOT built / DEFERRED (honest)
- **DEFERRED** Assurance-gated RESOLVED (Phase 8.7); `verified` always False here.
- **DEFERRED** Performance measurement (Part S).
- **DEFERRED** Richer persisted hypothesis states (kept the ratified four).
- **DEFERRED** Exhaustive process-kill boundary matrix.
- **BLOCKED** Real LLM leg (placeholder credentials, Phase 5.5 untouched) — `provider="scripted"`.
- **NOT claimed** Exactly-once.

## Counts (harness, cortex_p84)
investigation_events=50 · observations=5 · facts=5 · provider_calls=5 · governed_reads=5.
Differential: h1=open · h2=refuted · h3=refuted · h4=supported → RESOLVED (leading h4, residual: h1 not eliminated, not Assurance-verified).

## Verdict
**VERIFIED** — the smallest real differential-diagnosis engine: model proposes → platform tests the test → World provides evidence → hypotheses change → the next test is selected deterministically → uncertainty shrinks honestly. The system says "supported, but not verified", "conflicting evidence", "this evidence is stale", and "I don't know" — against real Postgres, with the real LLM BLOCKED, no new execution authority, no second RAG/memory, no numeric confidence, and no exactly-once claim.
