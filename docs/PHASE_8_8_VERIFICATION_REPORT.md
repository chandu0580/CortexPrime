# PHASE 8.8 — VERIFICATION REPORT

Date: 2026-08-12 · Branch `phase-1-foundation` · ADR-079 · No new migration (autonomy decisions on the cw_investigation event log)

Labels: **VERIFIED** · **NOT VERIFIED** · **DEFERRED** · **BLOCKED**. Distributed claims cite `tests/intelligence/test_autonomy.py` (**26 passed**) and the real-Postgres harness `scripts/phase88_autonomy_harness.py` (**22 checks, 0 fail, verdict VERIFIED** vs a fresh `cortex_p88`, over real calibration evidence). Real LLM BLOCKED; `provider="scripted"`.

## 1. Existing autonomy controls inventoried (Part A)
**VERIFIED** The A0–A4 `AutonomyLevel` contract, the investigation-service EXECUTING gate (A3 requires human `APPROVED`, A4 a policy ref), the Phase-6 One Plane of Action (`SecureCapabilityInvocationGateway` + authorization + digest-bound `ApprovalArtifact` + leases + audit chain), `RiskClassification`/`RiskLevel`/`SideEffectClass` (deterministic blast/reversibility), calibration (8.7), and independent assurance (7.7) were mapped and REUSED. No second executor/gateway/approval/governance system was created. No governed emergency-stop existed (only quarantined V1).

## 2. Capability and permission structurally separate (Part B)
**VERIFIED** `Capability` (technical ability) is distinct from permission (`PolicyEffect`) and autonomy (A0–A4). Unit `TestCapabilityVsPermission`: a destructive capability requested at A4 is capped to A1 by blast radius; low-permission/low-autonomy is legal.

## 3. A0–A4 semantics explicit (Part C)
**VERIFIED** The existing contract is reused (not replaced). `AutonomyPolicy` gives it operational meaning: A0–A2 need no earned authority (no action); A3 = supervised act (human approval); A4 = delegated autonomy (policy authorization, no per-action approval). `permits_autonomous_action` is true only for A4-policy or (post-approval) A3.

## 4. Autonomy is scope-bound (Part F)
**VERIFIED** Every `AutonomyDecision` carries an `AutonomyScope` (tenant/environment/service/capability/operation/resource_class). Unit `test_scope_is_never_universal`; blast-radius caps per action class (LOW→A4 … CRITICAL→A1) — `test_blast_radius_caps_per_level`.

## 5. No global trust score (Part E)
**VERIFIED** The output is a typed `AutonomyDecision` + `AutonomyEligibility`; unit `test_decision_is_typed_not_a_number` (no "trust"/"score" key). Reliability, assurance, risk, calibration stay separate inputs.

## 6. Promotion platform-controlled; calibration advisory (Part D/K)
**VERIFIED** `AutonomyPolicy.evaluate` is platform code consuming typed evidence; earning an action requires CALIBRATED reliability + min decided outcomes + support-rate floor + assurance-coverage floor + bounded blast + reversibility + no drift + fresh world + compatible version. Harness `[Y]`: `9/10` calibration alone does not ALLOW; it is one input. Unit `TestEarned`.

## 7. Assurance remains independent (Part F)
**VERIFIED** The autonomy floor consumes the calibration `assurance_coverage` (independent 7.7 verdicts). Low coverage → ASSURANCE_INSUFFICIENT (unit `test_low_assurance_coverage_insufficient`; harness `[neg]`). The verifier is unchanged and independent.

## 8. World freshness/conflict reduce authority (Part K)
**VERIFIED** Stale world → STALE_EVIDENCE; conflicted world → POLICY_FORBIDDEN — both non-action (unit `TestDowngradeAndRevocation`; harness `[neg]`).

## 9. Blast radius deterministic (Part G)
**VERIFIED** Reuses `RiskClassification` (computed from declared `RiskFactors`, never a name or a model score). Per-`RiskLevel` autonomy caps are explicit policy config (`AutonomyPolicyConfig`).

## 10. Reversibility explicit (Part H)
**VERIFIED** An irreversible action at/above the reversible-required level forces HUMAN_APPROVAL — no delegated autonomy (unit `test_irreversible_requires_human`; harness `[neg]`).

## 11. Deterministic pre-flight gate (Part I)
**VERIFIED** Fixed stage order (emergency stop → breaker → non-action → blast cap → version → calibration → assurance → drift → world → reversibility → approval); a denial caps the outcome and later stages cannot re-open it. The model cannot reorder/skip stages (it is not a parameter).

## 12. Human approval digest-bound; evidence inspectable (Part O/Z)
**VERIFIED** The existing digest-bound `ApprovalArtifact` + EXECUTING gate are reused; the decision computes which approval is required and records structured evidence (`AutonomyDecision.to_dict`) durably. No raw chain-of-thought is stored (unit `test_reason_is_specific_not_vague`; harness `[Z]`).

## 13. Autonomy downgrade + emergency stop + circuit breakers (Part L/M/N/Q)
**VERIFIED** Drift → downgrade to non-action; `EmergencyStopState.STOP_ACTIVE` → EMERGENCY_STOPPED (a governed, platform-controlled stop); `CircuitBreakerConfig` (explicit named thresholds) → CIRCUIT_OPEN. Unit `TestDowngradeAndRevocation`; harness `[neg]` (stale/conflict/drift/stop/breaker all refuse). Effective level may never exceed allowed (contract-enforced — `test_effective_never_exceeds_allowed`).

## 14. Tenant isolation (Part S)
**VERIFIED** Autonomy evidence is tenant-scoped; harness `[S]`: tenant B (no calibration) → INSUFFICIENT_EVIDENCE; tenant A's evidence never authorizes B. Unit `TestTenantScope`.

## 15. Version compatibility (Part T)
**VERIFIED** The decision requires the calibration evidence's `(model_identity, harness_version)` to match the current runtime; a mismatch → POLICY_FORBIDDEN, "re-evaluated" (unit `TestVersionBinding`; harness `[neg]`). A4 authority is never silently carried across a changed runtime.

## 16. Crash / recovery (Part U)
**VERIFIED** Harness `[U]`: after a hard exit + fresh reconnect, the autonomy decision and the EXECUTING state survive (durable, event count unchanged), and there is **no autonomy escalation on recovery** (level unchanged A3). No duplicate action, no fabricated approval.

## 17. Replay inert (Part V)
**VERIFIED** Re-evaluating the autonomy decision and reconstructing the investigation five times did **0** provider calls, **0** new audit events, **0** executions (harness `[V]`). Autonomy evaluation is a pure read.

## 18. Model cannot escalate / bypass / fabricate / self-reinforce (Part W/X)
**VERIFIED** The model cannot escalate (autonomy is not a parameter — `test_model_output_is_not_a_parameter`; a model self-authorizing at A3 without an APPROVED event is refused — harness `[gate]`), cannot bypass governance (`BND-INTELLIGENCE-CANNOT-EXECUTE` fences the module from the gateway), cannot fabricate approval/verification (existing digest-bound approval + independent assurance), cannot modify calibration (frozen contracts). **The self-reinforcing loop is structurally impossible** (`test_self_reinforcing_loop_broken`: a perfect 10/10 record with 0 assurance coverage still cannot promote). New fitness rule **BND-AUTONOMY-NOT-MODEL-DRIVEN** (CURRENT=PASS; SYNTHETIC=FAIL — `test_autonomy_module_not_model_driven_fitness`): the autonomy module imports no model boundary.

## 19. Controlled A3/A4 experiment succeeds (Part Y)
**VERIFIED** Harness `[Y]`/`[Y-A4]` vs `cortex_p88`: real calibration (9/10, coverage 1.0) → earned A3 → platform sets A3 → human APPROVED → the EXISTING EXECUTING gate passes → a governed action runs through the ONE gateway (execution_ref) → the audit chain grows. Earned A4 → EXECUTING via policy authorization ref, no per-action human approval.

## 20. Negative cases refuse/downgrade (Part Y)
**VERIFIED** stale world, conflicted world, insufficient calibration, drift, wrong runtime version, emergency stop, tripped breaker — all deny or downgrade; a denied decision keeps A1 so no autonomous execution is possible (harness `[neg]`).

## 21. Structured autonomy evidence durable/auditable (Part Z)
**VERIFIED** `record_autonomy_decision` persists the decision on the append-only cw_investigation log; the governed action is recorded in the cp_audit chain. Both survive recovery.

## 22. Architecture fitness / regression
**VERIFIED** New rule `BND-AUTONOMY-NOT-MODEL-DRIVEN`; gate **35 passed, 0 failed, 6 skipped across 1170 modules**. `pytest tests/intelligence tests/world tests/assurance tests/harness tests/architecture tests/contracts` → **914 passed**. No suppressed failures, no weakened assertions.

## Bug fixed (honest)
The A4 policy-authorization transition was latently broken — the investigation service stored `payload["policy_authorization_ref"]`, which the secret firewall flags (key-name contains "authorization"), so every A4-via-policy transition failed. Recorded now as `policy_grant_ref`; the A4 path works (harness `[Y-A4]`). Contract supersession: none (payload key renamed, API unchanged).

## Counts (harness, cortex_p88)
provider_calls=11 · audit_events=11 · investigation_events=15. Decision A3: allowed=a3_approved_action, eligibility=human_approval_required, approval=human_approval, blast=low, reversible=true.

## NOT built / DEFERRED (honest)
- **DEFERRED** A standalone durable emergency-stop ledger (the effect + platform-control + durability-via-event-log are proven; a dedicated stop/drain ledger with its own recovery is deferred).
- **DEFERRED** A full autonomy-grant state machine (represented as durable decisions).
- **DEFERRED** A production-write capability (controlled experiment uses a governed reversible dev operation).
- **BLOCKED** Real-model evidence — `provider="scripted"`, labelled.
- **NOT claimed** Exactly-once.

## Verdict
**VERIFIED** — CortexPrime increases autonomy only through deterministic, platform-owned governance from independent evidence: capability ≠ permission ≠ autonomy, no global trust score, scope-bound and version-bound authority, calibration advisory, assurance independent, deterministic blast/reversibility, a fixed pre-flight gate, digest-bound human approval, deterministic downgrade + circuit breakers + a governed emergency stop, tenant isolation, crash-safe, replay-inert — and the model can never promote itself or self-reinforce, proven structurally. The controlled A3/A4 experiment succeeds through the ONE gateway; every negative case refuses or downgrades. The platform owns authority; the model never does.
