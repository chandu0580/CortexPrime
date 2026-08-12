# PHASE 8.7 — VERIFICATION REPORT

Date: 2026-08-12 · Branch `phase-1-foundation` · ADR-078 · **No new migration/table** (calibration is computed-on-read from cw_reasoning + cw_verification)

Labels: **VERIFIED** · **NOT VERIFIED** · **DEFERRED** · **BLOCKED**. Distributed claims cite `tests/intelligence/test_calibration.py` (**26 passed**) and the real-Postgres harness `scripts/phase87_calibration_harness.py` (**18 checks, 0 fail, verdict VERIFIED** vs a fresh `cortex_p87`, over 20 real prediction outcomes). Real LLM BLOCKED; `provider="scripted"`.

## 1. Existing calibration evidence inventoried (Part A)
**VERIFIED** No governed calibration/reliability/analytics implementation existed; V1 `backend.learning`/`backend.analytics` are quarantined (`backend.learning` is in the V1-import fitness list). The substrate exists in cw_reasoning (predictions + evaluations) and cw_verification (verdicts); `PredictionLifecycleResult.calibration` was a transient pre-joined bundle. Join keys confirmed: prediction↔evaluation via `refs.prediction_ref`; evaluation↔verification by `(subject, predicate)` (verification carries no execution_ref).

## 2. Calibration unit explicitly typed (Part C)
**VERIFIED** `PredictionClass(subject_type, predicate, environment, model_identity, harness_version)` — a minimal useful stratification, never one global number. `harness_version` is stamped into the prediction reasoning `refs` (additive; record identity unchanged).

## 3. Eligibility is deterministic; incomplete preserved (Part D)
**VERIFIED** `CalibrationDatasetBuilder` classifies each prediction ELIGIBLE / PENDING_OUTCOME / INSUFFICIENT_EVIDENCE deterministically (unit `TestEligibility`): no evaluation → PENDING_OUTCOME; out-of-horizon → INSUFFICIENT_EVIDENCE (not failure); verified → ELIGIBLE + ASSURED; unverified → ELIGIBLE + UNASSURED. Censored cases are preserved, never discarded.

## 4. Assurance quality represented (Part E/F)
**VERIFIED** `AssuranceTier` (ASSURED/SUPPORTED/UNASSURED/INSUFFICIENT_OUTCOME) keeps populations visible; `assurance_coverage` is reported and low coverage → CALIBRATED_WITH_LIMITATIONS (unit `test_low_assurance_coverage_is_limited`), never discarding lower-quality evidence. Harness `[C]`: coverage 1.0 (every decided outcome independently verified).

## 5. UNKNOWN/STALE/CONFLICTED never become FALSE (Part E/K)
**VERIFIED** `test_out_of_horizon_is_insufficient_not_failure`, `test_insufficient_verdict_is_censored_not_failure` — an INSUFFICIENT/late/conflicted outcome is labelled INSUFFICIENT_EVIDENCE, never UNSUPPORTED. Missing observations → PENDING, never failure.

## 6. Temporal leakage impossible (Part G)
**VERIFIED** `list_by_kind`/`list_for_subject` take a `known_at` cut (`recorded_at ≤ known_at`). Unit `test_known_at_excludes_future_records`: an as-known-10:05 view of predictions evaluated at 10:20 shows all PENDING; the final view shows all decided. Harness `[G]`: as-known-10:05 sees no outcomes — future evaluations did not leak backward.

## 7. Reproducible dataset + version/digest (Part H/U)
**VERIFIED** `dataset_digest` is a pure function of tenant+policy+known_at+provider+samples; `result_digest` of the estimate. Unit `TestReproducibility` (same → same digest; one flipped sample → different digest; result digest stable). Harness `[U]`: same ledgers+policy → same dataset digest; same dataset+algorithm → same result digest.

## 8. Calibration method justified by data (Part I)
**VERIFIED** Because CortexPrime emits no model probability, probability calibration (isotonic/Platt) is N/A; the justified method for binary outcomes with small samples is empirical binomial reliability with a **Wilson score interval** (stdlib `NormalDist`, no dependency). Documented in ADR-078.

## 9. INSUFFICIENT_DATA; no fake precision (Part J)
**VERIFIED** Below `min_decided_samples`, the estimate is INSUFFICIENT_DATA with **no `support_rate`, no interval, UNCALIBRATED ClaimConfidence** (unit `test_insufficient_data_no_fake_precision`; the contract forbids a rate on INSUFFICIENT_DATA — `test_insufficient_data_cannot_carry_rate`). Harness `[J]`: an unknown class returns INSUFFICIENT_DATA, no rate, uncalibrated. Calibrated results report full counts + interval, never a bare point estimate.

## 10. Stratification/fallback explicit (Part K)
**VERIFIED** `estimate` broadens explicitly (drop environment, then predicate) recording `fallback_applied`/`fallback_from` (unit `test_fallback_broadens_explicitly`); it never wildcards model/harness. Never silently uses unrelated data.

## 11. Model/harness versions tracked; never merged (Part L)
**VERIFIED** `PredictionClass` includes model_identity + harness_version; `_class_matches` never merges versions and `broaden` keeps them fixed. Unit `test_version_not_merged_by_fallback`; harness `[L]`: an `h/2` class sees none of `h/1`'s samples.

## 12. Drift policy explicit (Part V)
**VERIFIED** `DriftDetector` uses the documented non-overlapping-Wilson-interval policy: unit `TestDrift` (90%→10% → DRIFT_DETECTED; stable → NO_DRIFT; thin → UNKNOWN_DRIFT_STATUS). Harness `[V]`: batch A (9/10) vs batch B (1/10) → DRIFT_DETECTED; a 50-sample floor → UNKNOWN_DRIFT_STATUS. No magic threshold.

## 13. Experience interaction measurable (Part M)
**VERIFIED** Each sample carries `uses_experience`; `ReliabilityEstimator.compare_experience` returns WITH/WITHOUT estimates for measurement. No claim that experience helps without evidence.

## 14. Reliability vs calibration distinguished (Part N)
**VERIFIED** ADR-078 keeps them distinct: probability calibration is N/A (no score); the estimate is empirical class reliability with an interval; drift is a separate distribution-shift concept. Documented, not collapsed.

## 15. Agent trajectory evidence evaluable (Part O)
**DEFERRED (substrate present)** The harness traces / step counts exist and the sample references execution/investigation, but which trajectory fields are causally useful is a measured later question; 8.7 does not feed trace fields into an estimator. **DEFERRED**, honestly.

## 16. Human adjudication remains distinct (Part P)
**VERIFIED** `human_adjudicated` is a distinct per-sample signal (via an optional port); a `HumanEvent` lives on the cw_investigation event log and never rewrites World facts/observations/outcomes/verifications (structural — HumanEvent has no path into those ledgers).

## 17. Calibration cannot authorize / promote autonomy / write World (Part R/Z)
**VERIFIED / NO NEW RULE** The calibration module is auto-fenced by `BND-INTELLIGENCE-CANNOT-EXECUTE`, `BND-MODEL-CANNOT-CREATE-FACT`, and `BND-INTELLIGENCE-CANNOT-BYPASS-WORLD` (unit `TestCalibrationFenced`: a synthetic calibration module importing a connector FAILS; the current module passes all three). No cosmetic rule added (Part Z). It reads a verdict via a port, never mints a Verification/Outcome, and cannot reach execution/governance. Gate: **34 passed, 0 failed, 6 skipped across 1168 modules**.

## 18. Model cannot rewrite calibration (Part T#15)
**VERIFIED** All calibration contracts are frozen dataclasses (unit `test_estimate_is_immutable`); the model never sees a mutable calibration surface.

## 19. Replay inert; crash-safe (Part X)
**VERIFIED** Calibration performs **no writes** — it is computed-on-read. Harness `[X]`: five rebuild+estimate cycles created **0** reasoning/verification/world records and **0** provider calls, and reproduced the identical result digest. No partial calibration artifact can become authoritative (there is no durable artifact). Crash during construction leaves the ledgers untouched.

## 20. Tenant isolation fail-closed (Part T#8)
**VERIFIED** Reads are tenant-scoped in SQL; harness `[tenant]`: cross-tenant calibration sees no samples (empty dataset).

## 21. Adversarial (Part T)
**VERIFIED** model-stated confidence never enters (no confidence field on a sample — `test_sample_carries_no_confidence_field`; the estimate's ClaimConfidence is measured, not stated — `test_estimate_confidence_is_measured_not_stated`); future outcomes cannot leak (§6); replay creates no samples (§19); **duplicate outcomes cannot inflate** the count (deduped by `prediction_ref` — `test_duplicate_predictions_do_not_inflate`); UNKNOWN/STALE/CONFLICTED never failure (§5); tenant/version isolation (§11, §20); insufficient data → no fake precision (§9); calibration cannot authorize/promote/rewrite (§17, §18).

## 22. Reproducibility & drift proven (Part U/V)
**VERIFIED** §7 (reproducibility) and §12 (drift), both in unit tests and the real-Postgres harness.

## 23. Performance measured (Part W)
**VERIFIED (measured)** Harness `[W]`, `cortex_p87`: dataset construction ≈ **80 ms** (20 predictions, joining evaluations + verifications), estimation ≈ **1.3 ms**. No speculative indexes/infrastructure added (the existing `(tenant_id, kind)` index serves `list_by_kind`).

## 24. Real LLM honestly separated (Part Y)
**VERIFIED / BLOCKED** All evidence is `provider="scripted"`; the dataset carries a `provider_label` and never mixes scripted with real-model evidence. No credential was manufactured/inspected; the Phase 5.5 blocker is untouched.

## 25. Regression (Part X-regression)
**VERIFIED** `pytest tests/intelligence tests/world tests/assurance tests/harness tests/architecture tests/contracts` → **882 passed** (2 collection warnings). One additive change to Phase 8.5 recording (`record_prediction` stamps harness_version) — the 8.5 test stub was updated; no behaviour superseded. No weakened assertions.

## Counts (harness, cortex_p87)
predictions=20 · verifications=20 · provider_calls=~20. Calibration (class dependency/latency/scripted/h/1): **9/10 supported**, Wilson interval, assurance coverage 1.0, ClaimConfidence CALIBRATED at 0.9; drift DETECTED between a 9/10 and a 1/10 window.

## NOT built / DEFERRED (honest)
- **DEFERRED** Real-model calibration — BLOCKED, all evidence scripted (labelled).
- **DEFERRED** Environment stratification population; trajectory-feature calibration (Part O); a materialized calibration artifact (computed-on-read instead, Part Q).
- **NOT built** Probability calibration (isotonic/Platt) — N/A (no model score exists).
- **NOT claimed** Exactly-once.

## Verdict
**VERIFIED** — CortexPrime derives empirically grounded reliability from real prediction outcomes, never model confidence: a typed prediction class, deterministic eligibility with censored cases preserved, assurance-quality populations, temporal-leakage defence, reproducible digests, empirical Wilson-interval reliability with INSUFFICIENT_DATA when the sample is thin, explicit fallback that never merges versions, documented drift detection, and advisory-only output fenced from authorization/execution/World-writes — against real Postgres, real LLM BLOCKED, no new table, no vector/graph infrastructure, no fake precision, no exactly-once claim. This is evidence Phase 8.8 may consume for a governed autonomy decision.
