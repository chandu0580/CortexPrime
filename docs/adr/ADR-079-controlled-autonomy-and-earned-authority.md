# ADR-079 — Controlled Autonomy & Earned Authority

Status: Accepted · Date: 2026-08-12 · Phase 8.8 · Follows ADR-072–078 and ADR-062 (One Plane of Action) / the Phase-6 governance ADRs

## Context

Phase 8.7 produced empirical reliability from real outcomes. Phase 8.8 answers the capstone question: *under exactly which conditions has CortexPrime earned the right to act without another human approval, and what deterministic mechanism takes that right away the moment the evidence no longer supports it?* Autonomy is **delegated authority, not a capability**, and the model must never appear on the authority side of the boundary. This reuses the existing A0–A4 contract, the investigation-service EXECUTING gate, the Phase-6 One Plane of Action (`SecureCapabilityInvocationGateway`, authorization, digest-bound approval, leases, audit), the deterministic risk/blast-radius contracts (`RiskClassification`), calibration (8.7), and independent assurance (7.7). It adds a deterministic autonomy **decision** layer that emits a value consumed *before* the gateway — and **no second executor, gateway, approval system, or governance system**.

## Decisions

**1. Capability ≠ permission ≠ autonomy (Part B).** Three separate typed concepts: `Capability` (what the system technically can do — operation/resource/side-effect/reversibility), permission (the existing `PolicyEffect` over a capability), and autonomy (the A0–A4 level). A system may legally be high-capability, low-permission, low-autonomy — enforced because blast-radius caps and policy denials apply regardless of capability.

**2. Autonomy is decided by a deterministic, platform-owned pre-flight gate (Part I).** `AutonomyPolicy.evaluate` is a pure function of typed evidence with a fixed stage order: emergency stop → circuit breaker → non-action gate → blast-radius cap → version compatibility → calibration evidence → assurance coverage → drift → fresh/non-conflicted world → reversibility → approval. A denial at any stage caps the outcome; later stages cannot re-open it. Same evidence + same config ⇒ same `AutonomyDecision`.

**3. The model is never an input (Part W/X).** `evaluate` has no model/prompt/proposal parameter; it consumes calibration (`ReliabilityEstimate`), assurance coverage, deterministic `RiskClassification`, world freshness/conflict, and runtime versions. The new fitness rule `BND-AUTONOMY-NOT-MODEL-DRIVEN` forbids the autonomy module from importing the governed model boundary or any model-proposal seam; `BND-INTELLIGENCE-CANNOT-EXECUTE` already stops it reaching the gateway. So the decision is outside the model's mutation surface — the **self-reinforcing loop is structurally impossible**: promotion evidence comes from *independently* evaluated outcomes (the outcome is grounded in real execution + independent world observation, the verdict in independent assurance, 8.5/7.7), and the decision + the human/policy approval are platform-owned.

**4. No global trust score (Part E).** The output is a typed `AutonomyDecision` — requested vs allowed vs effective level, a typed `AutonomyEligibility` (ELIGIBLE / INSUFFICIENT_EVIDENCE / STALE_EVIDENCE / DRIFT_DETECTED / POLICY_FORBIDDEN / ASSURANCE_INSUFFICIENT / HUMAN_APPROVAL_REQUIRED / EMERGENCY_STOPPED / CIRCUIT_OPEN), an approval requirement, the evidence references, and a specific reason. Reliability, assurance, risk, and calibration stay separate; none collapses into a number.

**5. Autonomy is scoped, never universal (Part F).** Every decision carries an `AutonomyScope` (tenant, environment, service, capability, operation, resource_class). The grant is "A4 is permitted for THIS capability under THESE conditions", never "the agent is A4". Blast radius (the reused `RiskLevel`, computed from declared properties, never from a name or a model score) deterministically caps autonomy per action class: LOW→A4, MEDIUM→A3, HIGH→A2, CRITICAL→A1 (explicit policy config, Part G).

**6. Calibration is advisory evidence, required but not sufficient (Part K).** Earning an action requires CALIBRATED reliability with enough decided outcomes, a support-rate floor, AND an independent-assurance-coverage floor AND bounded blast radius AND (for autonomous writes) reversibility AND no drift AND fresh, non-conflicted world AND a compatible runtime version. `24/27 supported` never means ALLOW by itself.

**7. Authority is revoked deterministically as evidence deteriorates (Part L/M/N/Q).** Drift downgrades to non-action; a world conflict or stale state forbids action; a tripped `CircuitBreakerConfig` (explicit named thresholds — action/verification failures, consecutive refusals, drift, conflict) opens; an `EmergencyStopState` blocks all new autonomous actions (a governed, platform-controlled stop — none existed governed; the only prior one was quarantined V1). Downgrade is deterministic and the model cannot argue against it.

**8. Reversibility gates delegated authority (Part H).** An irreversible action at or above the reversible-required level forces HUMAN_APPROVAL — no delegated autonomy for an action with no complete inverse.

**9. Human approval stays digest-bound; the platform never authorizes itself.** The existing EXECUTING gate is reused: A3 requires a human `APPROVED` event, A4 requires a policy authorization reference. The autonomy decision computes *which* is required; the existing Phase-6 digest-bound `ApprovalArtifact`/gateway binding enforces it at the action. A3 without an approval is refused — proven — so the model can never self-authorize.

**10. Decisions are durable, auditable structured evidence (Part Z).** `InvestigationService.record_autonomy_decision` appends the decision to the append-only cw_investigation event log (tenant-scoped, secret-firewalled). It is inspectable without any raw model chain-of-thought — which is never stored.

## Explicit non-goals

No second executor/gateway/approval/governance system; no production A4 by default (the experiment is development + reversible + low-blast); no numeric trust score; no model influence on authority. Exactly-once is not claimed. The autonomy decision emits a value; the ONE gateway remains the only execution authority.

## NOT built / deferred (recorded honestly)

- **A standalone durable emergency-stop ledger** — the stop STATE is consumed by the policy and its EFFECT (block new actions) is proven; a dedicated durable stop/drain ledger with its own recovery is deferred (the effect + platform-control + durability-via-event-log are established).
- **A full autonomy-grant state machine** (PROPOSED→…→REVOKED) — represented as a sequence of durable decisions rather than a new persisted state machine, to avoid duplicating the investigation status semantics.
- **A production write action** — the controlled experiment uses a governed reversible operation in development; a production-write capability is deliberately not introduced.
- **Real-model evidence** — BLOCKED; all calibration/decisions are `provider="scripted"`, labelled.

## Bug fixed

The A4 policy-authorization transition was latently broken: the investigation service stored the ref under key `policy_authorization_ref`, which the field-aware secret firewall flags as credential-shaped (the key-name contains "authorization"). Recorded now as `policy_grant_ref` (a reference, never a secret); the A4-via-policy path works.

## Consequences

CortexPrime can act without a per-action human approval only when it has earned, scoped, version-bound, independently-evidenced authority — and loses it deterministically the instant drift, conflict, staleness, a tripped breaker, or an emergency stop appears. The model never owns authority; the platform does. L1–L16, One Plane of Action, World immutability, independent Assurance, tenant isolation, the secret firewall, and the Phase 5.5 blocker are intact.
