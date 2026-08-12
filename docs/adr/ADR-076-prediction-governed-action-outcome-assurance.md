# ADR-076 — Prediction → Governed Action → Outcome → Assurance

Status: Accepted · Date: 2026-08-12 · Phase 8.5 · Follows ADR-073/074/075 and ADR-065–072 (Phase 7)

## Context

Phase 8.4 gave the Investigation Engine a settled differential with a supported hypothesis. Phase 8.5 closes the epistemic loop through the Intelligence Plane: a supported diagnosis becomes a falsifiable **prediction**, a **governed action**, a real **outcome from reality**, a deterministic **evaluation**, and an **independent Assurance verification** — with durable, calibration-ready evidence for Phase 8.7. This is a reuse phase: Phase 7.6 built the Prediction/Outcome contracts and `evaluate_prediction`, 7.7 built the `AssuranceVerifier`, 7.8 proved the full World-plane lifecycle, and the reasoning ledger (cw_reasoning) already persists predictions and evaluations. Phase 8.5 exposes that lifecycle through the intelligence plane, with the model proposing the prediction via the governed boundary — and **adds no executor, gateway, verifier, ledger, or table**.

## Decisions

**1. A prediction is a falsifiable forward claim, never a confidence.** The model proposes a `PredictionProposalSchema` (`extra="forbid"`): a hypothesis ref, subject/predicate references, a structured `expected` observation, a plain-language condition, and an evaluation window. Any self-declaring field — `outcome`, `verified`, `success`, `confidence`, `autonomy`, `provider`, `url`, `command`, `fact`, `belief`, `prediction=true` — is an extra field and is rejected. `PredictionPolicy` then validates the structure: tied to a **known** hypothesis in the differential, a structured falsifiable expectation, safe references (no URL/shell), a bounded window. No numeric confidence exists anywhere.

**2. The prediction goes through the ONE governed model boundary.** `GovernedModelProposalPort.propose_prediction` reuses `harness.GovernedModelBoundary` with the prediction schema — schema-validated, trace-recorded, provider stamped from the span, never the model's JSON. No second model gateway or tracer.

**3. The action runs only through the existing One Plane of Action.** The orchestrator (`PredictionLifecycle`) requests a governed action through a `GovernedOutcomePort`; the port's composition adapter drives the existing harness → governance → authorization → lease → scheduler → dispatcher → gateway → provider path and returns the real `execution_ref`. The intelligence plane imports no connector, provider, gateway, transport, or credential (enforced by `BND-INTELLIGENCE-CANNOT-EXECUTE`).

**4. The Outcome comes from reality, and intelligence cannot mint it.** The `Outcome` is constructed **outside** the intelligence plane, from the real `execution_ref` plus the *independently observed* world value (`WorldQuery.effective_value`) — never model text, never a bare provider 200. This is enforced structurally: `BND-MODEL-CANNOT-CREATE-FACT` already lists `Outcome` (and `Fact`/`Belief`/`WorldVerification`) among the grounded constructors `backend.intelligence` may not import. So Part U's proposed `BND-INTELLIGENCE-CANNOT-CREATE-OUTCOME` is **already enforced** — no new rule is added (CURRENT=PASS, and a synthetic intelligence module importing `Outcome` FAILS, both tested). The orchestrator receives the Outcome through a port and only hands it to the evaluator.

**5. Prediction evaluation is deterministic; the model never declares the result.** `evaluate_prediction` (reused) compares the prediction's `expected` against the Outcome's `observed` by canonical digest, with a horizon check. The orchestrator maps it to `PredictionSupport` — SUPPORTED (match within horizon), UNSUPPORTED (mismatch), INSUFFICIENT_EVIDENCE (no observation in the window, or out-of-horizon). Silence is never a failure; a late outcome is never silently accepted; nothing becomes FALSE.

**6. Assurance verifies independently.** After the outcome, the orchestrator requests an independent verification through an `AssuranceVerificationPort`, backed by the reused `AssuranceVerifier`, which **re-queries the World itself** (a `COMPARE_PREDICTION_OUTCOME` procedure) and applies failure-first semantics — UNKNOWN/CONFLICTED/STALE evidence can never return SUPPORTED. The verifier's reasoning path must differ from the producer's; a verifier sharing the model's path is **refused** (`is_independent_of`, Constitution P5). The minted `WorldVerification` lands in cw_verification.

**7. Three judgements stay distinct.** The result keeps *diagnostic support* (the differential's hypothesis status), *prediction support* (the platform's deterministic evaluation), and *independent verification* (the Assurance verdict) as separate fields. "Supported diagnosis", "supported prediction", and "independently verified" are three different claims, and the system never collapses them.

**8. Durable, reconstructable calibration evidence — no new table.** The prediction and the evaluation are recorded in cw_reasoning; the verdict in cw_verification; the prediction/verification refs on the cw_investigation aggregate. The calibration bundle (prediction, times, hypothesis, expected/observed, evaluation, verdict, evidence refs, model/provider identity, harness version, temporal window) is fully **reconstructable** by joining those existing ledgers — so no `cw_prediction`/`cw_outcome`/`cw_calibration` table is added (Part Q). No calibration score is produced (that is Phase 8.7).

## Explicit non-goals

No autonomous production remediation (the scenario is a governed READ; a write would need existing governance to authorize it — none was invented), no live LLM (scripted provider, BLOCKED real leg), no numeric confidence/calibration, no new executor/gateway/verifier/ledger/table, no RAG, no memory. Exactly-once is not claimed — a crash after a provider side effect is at-least-once, and re-running re-reads (same-value observations dedupe).

## NOT built / deferred (recorded honestly)

- **Numeric calibration** — 8.5 only *captures* the calibration substrate; the statistical phase is 8.7.
- **Production write remediation** — deliberately not introduced; documented as a future governed capability, not invented here (Part M).
- **Threshold-predicate evaluation** — `evaluate_prediction` is exact-match, so numeric-threshold predictions are modelled as categorical observations (the world classifies; the platform compares exactly); a richer predicate evaluator is deferred.
- **The exhaustive 9-point crash matrix** — the load-bearing boundary (crash after the provider side effect, before outcome/verification; durable side effect survives, outcome not fabricated, no second action) is proven; a full per-point sweep is deferred.

## Consequences

CortexPrime can now say: "I predicted X. Reality produced Y. These observations support/contradict the prediction. An independent verifier checked the relationship. Here is the evidence." — with no model claim ever becoming a result. The V1 intelligence stack remains quarantined. L1–L16, One Plane of Action, World immutability, independent Assurance, tenant isolation, the secret firewall, and the Phase 5.5 blocker are intact.
