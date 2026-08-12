# ADR-078 — Empirical Calibration & Reliability

Status: Accepted · Date: 2026-08-12 · Phase 8.7 · Follows ADR-073–077 and ADR-069 (Assurance) / ADR-062 (confidence)

## Context

Phase 8.5 captured the calibration substrate (prediction → outcome → evaluation → assurance in cw_reasoning/cw_verification) and Phase 8.6 enriched it with experience-use records. Phase 8.7 answers the central question empirically: *across the historical predictions of a class, how often did the predicted relationship actually hold, under what conditions, with what evidence quality, and how independently was it verified?* — derived from REAL outcomes, never from model-stated confidence. This fulfils the Phase 7.1 `ClaimConfidence`/`CalibrationState` contract, whose docstring reserved "a numeric confidence fitted from logged prediction-vs-outcome" for "a later phase". This is that phase. It reuses the existing ledgers and adds **no new table** and **no execution/governance/authority**.

## Decisions

**1. Empirical class reliability, not probability calibration.** CortexPrime deliberately emits **no model probability** anywhere in the epistemic path, so there is no probability-vs-frequency curve to fit and isotonic/Platt/logistic calibration are N/A (they calibrate a score that does not exist). The honest, correct quantity is the empirical reliability of a **prediction class**: the fraction of *decided* outcomes that held, with a Wilson interval around it. Distribution-shift (drift) and reliability (consistency under a task distribution) are tracked as distinct concepts.

**2. The calibration unit is a typed, minimal, version-tracked class.** `PredictionClass(subject_type, predicate, environment, model_identity, harness_version)` — a minimal useful stratification. `model_identity` and `harness_version` are always part of the class, so an estimate can never silently span incompatible runtime versions (Part L). `harness_version` is stamped into the prediction's reasoning `refs` at record time (additive; the record document and identity are unchanged).

**3. Deterministic eligibility; censored cases preserved.** Each prediction is classified ELIGIBLE / PENDING_OUTCOME / INSUFFICIENT_EVIDENCE / CONFLICTED / INELIGIBLE by joining prediction ↔ evaluation (via `refs.prediction_ref`) ↔ independent verification (by `(subject, predicate)` within the prediction's window — verification carries no execution_ref). Incomplete cases are preserved (censored), never discarded. Outcome labels keep SUPPORTED / UNSUPPORTED (decided) distinct from INSUFFICIENT_EVIDENCE / CONFLICTED / PENDING (censored): **UNKNOWN/STALE/CONFLICTED never become FALSE; missing observations never become failures** (Part E/K).

**4. Assurance quality is a visible population, not a filter that discards.** Each sample carries an `AssuranceTier` (ASSURED_OUTCOME / SUPPORTED_OUTCOME / UNASSURED_OUTCOME / INSUFFICIENT_OUTCOME); the estimate reports `assurance_coverage` and downgrades to CALIBRATED_WITH_LIMITATIONS below the policy floor rather than throwing lower-quality evidence away (Part F).

**5. Temporal-leakage defence via bitemporal reads.** `list_by_kind`/`list_for_subject` take an optional `known_at` cut (records with `recorded_at ≤ known_at`), giving an AS-KNOWN-AT-TIME view alongside the FINAL-EVALUATED view. A prediction made at 10:00 whose outcome was learned at 10:15 does not appear in a 10:05 dataset (Part G). Reuses the existing bitemporal semantics; no second temporal model.

**6. No fake precision; INSUFFICIENT_DATA is a first-class result.** Below `min_decided_samples`, the estimate is INSUFFICIENT_DATA with **no `support_rate`, no interval, and an UNCALIBRATED `ClaimConfidence`** (the contract forbids a rate on INSUFFICIENT_DATA). A calibrated result reports counts (supported/unsupported/insufficient/conflicted/pending/assured), a Wilson interval, and a `ClaimConfidence.calibrated(rate)` — the numeric confidence exists **only** when measured against real outcomes (Part I/J).

**7. Explicit fallback; versions never merged.** When a requested class is too sparse, the estimator broadens explicitly — dropping environment, then predicate — and records `fallback_applied`/`fallback_from`. It **never** wildcards `model_identity` or `harness_version`, so incompatible versions are never silently merged (Part K/L).

**8. Reproducibility by digest.** A dataset's `dataset_digest` is a pure function of tenant + policy + known_at + provider label + the (order-independent) samples; a result's digest is a pure function of the estimate. Same ledgers + same policy + same algorithm ⇒ identical digests (Part H/U). The digests are computed in the application layer (the contracts stay level-0 and hash-free).

**9. Drift by a documented policy, not a magic threshold.** `DriftDetector` compares two datasets of the same class: non-overlapping Wilson intervals ⇒ DRIFT_DETECTED; either side INSUFFICIENT_DATA ⇒ UNKNOWN_DRIFT_STATUS; otherwise NO_DRIFT. No invented threshold (Part V).

**10. Experience & human adjudication as distinct signals.** Each sample carries `uses_experience` (partitioning WITH/WITHOUT-experience reliability, measurable, no unearned claim — Part M) and `human_adjudicated` (a distinct signal; a HumanEvent lives on the cw_investigation log and never rewrites World/Assurance — Part P).

**11. Advisory only; fenced by the existing rules.** The calibration module lives in `backend.intelligence.application` and is auto-covered by `BND-INTELLIGENCE-CANNOT-EXECUTE` (no connector/execution/provider), `BND-MODEL-CANNOT-CREATE-FACT` (reads a verdict via a port, never mints a WorldVerification/Outcome), and `BND-INTELLIGENCE-CANNOT-BYPASS-WORLD` (consumes the ledgers only through composition-supplied read ports). So calibration **cannot** authorize an action, promote autonomy, bypass Assurance/Governance, or change World truth — no new fitness rule is required (Part R/Z; proven CURRENT=PASS, SYNTHETIC=FAIL). It produces a `ReliabilityEstimate`/`ClaimConfidence` as advisory evidence; Governance later decides whether it matters (Phase 8.8).

## Explicit non-goals

No probability calibration (no score exists), no confidence from the model, no authorization/autonomy/execution/World-write, no new ledger/table, no vector/embedding infrastructure, no exactly-once claim. Scripted-provider evidence is labelled `provider="scripted"` and never mixed with real-model evidence (Part Y).

## NOT built / deferred (recorded honestly)

- **Real-model calibration** — the real LLM leg is BLOCKED; all evidence is `provider="scripted"`, labelled as such (Part Y).
- **Environment stratification is present but unpopulated** — `PredictionClass.environment` exists as a dimension but defaults to "unknown" (no incident/environment source on a prediction today); populating it is future work.
- **Trajectory-feature calibration** (Part O) — the substrate exists (harness traces, step counts) but which fields are causally useful is a measured, later question; 8.7 does not feed trace fields into an estimator.
- **A materialized calibration artifact** — not built; calibration is computed-on-read from the ledgers (reproducible), so no `cw_calibration` table exists (Part Q).

## Consequences

The system can now state, from reality: "predictions of class X held Y% of the time (Wilson interval …), across N decided outcomes, M independently verified, at model/harness version V." That is empirical evidence about behaviour — not model opinion, not truth, not authorization, not autonomy — that Phase 8.8 may consume for a governed autonomy decision. The V1 learning/analytics stack remains quarantined. L1–L16, One Plane of Action, World immutability, independent Assurance, tenant isolation, the secret firewall, and the Phase 5.5 blocker are intact.
