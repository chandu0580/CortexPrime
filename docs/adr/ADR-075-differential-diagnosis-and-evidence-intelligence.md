# ADR-075 — Differential Diagnosis & Evidence Intelligence

Status: Accepted · Date: 2026-08-12 · Phase 8.4 · Follows ADR-073/074 and ADR-062–072

## Context

Phases 8.2/8.3 built the Investigation Engine and wired the live governed model boundary, but the platform's reasoning *about* the differential was thin: it took the model's single proposed test, ran it, and updated one hypothesis. Phase 8.4 makes CortexPrime a genuine evidence-driven investigator: it maintains competing hypotheses, computes evidence gaps deterministically, selects the most discriminating test itself, reuses existing World evidence, and settles honestly — a supported hypothesis is not a verified one, and an open alternative is never false. It reuses everything (the state machine, `WorldQuery` with freshness/authority, `BeliefFormation`, the governed read path, the governed model boundary) and adds no executor, gateway, RAG, memory, scheduler, or numeric confidence.

## Decisions

**1. The differential is first-class; no collapse to one answer.** Competing hypotheses each keep their own `evidence_for` / `evidence_against` / `missing_evidence` / `contradiction_refs` / `lineage_origins` / `temporal_fit` / epistemic `status` (the Phase 8.1 `DifferentialHypothesis`, unchanged). REFUTED is eliminated; OPEN/SUPPORTED/UNRESOLVED are "live". There is no numeric confidence and no model probability anywhere.

**2. Deterministic evidence-gap analysis** (`differential.analyze_gaps`). For each live hypothesis the platform computes what is known, what is missing, what would support vs contradict it, which other live hypotheses it bears against, and an explicit *unresolved reason* — "H1 remains unresolved because no discriminating observation of `deployment/payments` has been acquired yet". The platform can always explain a hypothesis's standing without a model verdict.

**3. Categorical test quality, never a truth score** (`TestQuality` + `classify_test`). A proposed test is DISCRIMINATING / PARTIALLY_DISCRIMINATING / NON_DISCRIMINATING / REDUNDANT / UNAVAILABLE / FORBIDDEN. These are engineering categories — a test never becomes more authoritative for being "higher". A test is DISCRIMINATING only when it targets a live hypothesis *and* two or more hypotheses are still live (so resolving the target narrows the competition); with one live hypothesis it is PARTIALLY (confirm/deny only). We deliberately introduced **no numeric epistemic score** (Part E's stop-and-document gate — none was required).

**4. The platform selects the next test, not the model** (`select_test`). The model may propose several candidate tests (`InvestigationProposalSchema.tests`, additive to the legacy single `test`); the platform picks the most discriminating admissible one, breaking ties on a deterministic test identity — never on model-verbalised preference. NON_DISCRIMINATING / REDUNDANT / UNAVAILABLE / FORBIDDEN candidates are dropped before any provider is reached.

**5. Evidence reuse before acquisition** (Part F). Before a governed read the engine consults the World read port for the test's subject/predicate; if the World already holds concrete, **AFFIRMED, FRESH** evidence (an observation backs it), it is reused and no second governed read is spent. STALE / CONFLICTED / UNKNOWN are never reused — freshness is not truth, a conflict is preserved not overwritten, and unknown is not evidence. The harness proves two hypotheses on one subject cost exactly one governed read.

**6. Authority / freshness / lineage are consumed, never reimplemented** (Part G). Freshness and authority come from `WorldQuery` (its `FreshnessPolicy` / `AuthorityPolicy`); corroboration/lineage from `BeliefFormation`. The engine reads the verdicts (`effective_value`, `effective_status`, `fresh.state`, `why.tier`) and acts on them. Newer low-authority evidence cannot beat older authoritative evidence, two same-source observations are not independent, and STALE/UNKNOWN/CONFLICTED never become FALSE — because the World Plane decides those, not the investigator.

**7. Hypothesis updates come from observed evidence; status is platform-controlled.** After a read (or a reuse) the engine compares the observed/effective value to the test's structured `supports_value` / `contradicts_value` and sets SUPPORTED / REFUTED, or leaves the hypothesis OPEN when the observation is inconclusive. A model's `suggested_conclusion` and interpretation carry no authority. We did **not** add new hypothesis states (Part I's stop-and-document gate): the ratified World `HypothesisStatus` (OPEN/SUPPORTED/REFUTED/UNRESOLVED — no VERIFIED, no FALSE) is sufficient; "eliminated" is REFUTED, and richer distinctions are a derived diagnostic view, not new persisted vocabulary.

**8. Honest settlement** (`settle`, Part P). When no admissible discriminating test remains, the platform settles deterministically: exactly one supported hypothesis → RESOLVED, naming its residual uncertainty (un-eliminated open alternatives and "not Assurance-verified"); two or more supported → CONFLICTED (not a coin-flip); none supported → UNRESOLVED / INSUFFICIENT_EVIDENCE. RESOLVED here means "one hypothesis is supported by admissible world evidence and no competitor is" — it does **not** claim the open alternatives are false, and it does **not** claim Assurance verified anything (that gate is Phase 8.7). The system can say "supported, but not verified", "conflicting evidence", "this hypothesis was weakened", "this evidence is stale", and "I don't know".

**9. New fitness rule: BND-INTELLIGENCE-CANNOT-BYPASS-WORLD.** `IntelligenceCannotExecuteRule` forbids *acting* but not reaching the World's storage. A reasoning plane importing `backend.world.infrastructure` (the World's SQL repositories) could read raw fact rows and re-derive freshness/authority/corroboration itself — the exact V1 hazard of a parallel truth. The new rule forbids any `backend.intelligence` module from importing `backend.world.infrastructure`: evidence is obtained only through the World application layer as a read port. CURRENT = PASS (the tree imports none); SYNTHETIC = FAIL (proven). Reading the durable investigation ledger and consuming `WorldQuery`/`BeliefFormation` remain allowed.

## Explicit non-goals

No remediation/action, no live LLM (scripted provider, BLOCKED real leg), no direct provider access, no numeric/probabilistic confidence, no RAG, no second executor/scheduler/gateway/memory/world-store. Exactly-once is not claimed.

## NOT built / deferred (recorded honestly)

- **Assurance-gated RESOLVED** — a RESOLVED conclusion rests on world evidence; wiring the independent Assurance verifier into termination remains Phase 8.7. `verified` is always False here.
- **Richer derived hypothesis states** (WEAKENED / ELIMINATED as distinct persisted states) — deliberately not added; the ratified four-state World vocabulary is used, with finer distinctions left as a derived view.
- **The full interruption matrix** — the load-bearing crash boundary (mid-loop, reconstruct without repeating tests) is proven; an exhaustive per-boundary process-kill sweep is deferred.

## Consequences

The Investigation Engine now shrinks uncertainty honestly: model proposes → platform tests the test → World provides evidence → hypotheses change → the next test is selected deterministically → the differential settles with its residual uncertainty named. The V1 intelligence stack remains quarantined. L1–L16, One Plane of Action, World immutability, independent Assurance, tenant isolation, the secret firewall, and the Phase 5.5 blocker are intact.
