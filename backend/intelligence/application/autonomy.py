"""The autonomy decision engine — earned, scoped, revocable authority (Phase 8.8).

A deterministic, platform-owned pre-flight gate that answers, per scope: under
exactly which conditions has CortexPrime earned the right to act without another
human approval, and what deterministic mechanism removes that right the moment the
evidence no longer supports it. The MODEL is never an input:

  * autonomy is decided from INDEPENDENT typed evidence — calibration (empirical
    reliability from real outcomes, 8.7), independent assurance coverage (7.7),
    deterministic risk/blast-radius (policy contracts), fresh world state, and
    runtime versions — never from model output;
  * the ordered pre-flight (emergency stop → circuit breaker → non-action gate →
    blast-radius cap → version compatibility → calibration → assurance → drift →
    fresh/conflict world → reversibility → approval) is fixed; a denial at any
    stage caps the outcome and the later stages cannot re-open it;
  * the result is an explainable ``AutonomyDecision`` (requested vs allowed vs
    effective level, the reason, the evidence references) — never a global trust
    score, never a vague 'safety policy prevented action'.

Capability ≠ permission ≠ autonomy. Reliability ≠ authorization. Calibration ≠
permission. Assurance ≠ autonomy. This module imports contracts + the calibration
result type only; it imports NO execution gateway, NO model boundary, NO connector —
it emits a value the governed EXECUTING gate consumes.
"""

from __future__ import annotations

from typing import Optional

from backend.platform.identity.generators import prefixed_id
from backend.contracts.policy import RiskClassification, RiskLevel
from backend.contracts.intelligence.investigation import AutonomyLevel
from backend.contracts.intelligence.calibration import (
    CalibrationStatus, DriftStatus, ReliabilityEstimate,
)
from backend.contracts.intelligence.autonomy import (
    ApprovalRequirement, AutonomyDecision, AutonomyEligibility, AutonomyPolicyConfig,
    AutonomyScope, BreakerTrip, Capability, EmergencyStopState,
)

__all__ = ["AutonomyPolicy"]

_A0, _A1, _A2, _A3, _A4 = (
    AutonomyLevel.A0_OBSERVE, AutonomyLevel.A1_INVESTIGATE, AutonomyLevel.A2_RECOMMEND,
    AutonomyLevel.A3_APPROVED_ACTION, AutonomyLevel.A4_AUTONOMOUS)
_BY_RANK = {level.rank: level for level in AutonomyLevel}


def _level(rank: int) -> AutonomyLevel:
    return _BY_RANK[max(0, min(4, rank))]


def _no_action_cap(requested: AutonomyLevel) -> AutonomyLevel:
    """The highest NON-action level (<= A2) not exceeding the request — the safe
    floor when an autonomous action is refused (observe/recommend still allowed)."""
    return _level(min(requested.rank, _A2.rank))


def _approval_for(level: AutonomyLevel) -> ApprovalRequirement:
    if level is _A3:
        return ApprovalRequirement.HUMAN_APPROVAL
    if level is _A4:
        return ApprovalRequirement.POLICY_AUTHORIZATION
    return ApprovalRequirement.NOT_PERMITTED


class AutonomyPolicy:
    """Deterministic autonomy evaluation. Pure function of typed evidence — same
    evidence + same config ⇒ same decision. The model is not a parameter."""

    def evaluate(
        self, *, requested_level: AutonomyLevel, scope: AutonomyScope, capability: Capability,
        risk: RiskClassification, reliability: Optional[ReliabilityEstimate],
        drift: DriftStatus, world_fresh: bool, world_conflicted: bool,
        versions: dict, stop_state: EmergencyStopState, breaker: Optional[BreakerTrip],
        config: AutonomyPolicyConfig, now, assurance_ref: Optional[str] = None,
        world_evidence_ref: Optional[str] = None,
    ) -> AutonomyDecision:
        model_id = str(versions.get("model_identity", "unknown"))
        harness_v = str(versions.get("harness_version", "unknown"))
        rel_ref = None
        cal_digest = None
        if reliability is not None:
            rel_ref = f"{reliability.status.value}:{reliability.support_rate}"
            cal_digest = reliability.dataset_digest

        def mk(allowed, effective, elig, approval, reason, *, downgraded_from=None, brk=None):
            return AutonomyDecision(
                decision_id=prefixed_id("autdec"), scope=scope, requested_level=requested_level,
                allowed_level=allowed, effective_level=effective, eligibility=elig,
                approval_requirement=approval, risk=risk, reason=reason, decided_at=now,
                policy_version=config.policy_version, model_identity=model_id, harness_version=harness_v,
                reliability_ref=rel_ref, assurance_ref=assurance_ref,
                world_evidence_ref=world_evidence_ref, calibration_dataset_digest=cal_digest,
                downgraded_from=downgraded_from, breaker=brk)

        floor = _no_action_cap(requested_level)

        # 1. EMERGENCY STOP — no new autonomous actions (Part M). Observe/recommend only.
        if stop_state.blocks_new_actions:
            return mk(floor, floor, AutonomyEligibility.EMERGENCY_STOPPED,
                      ApprovalRequirement.NOT_PERMITTED,
                      f"emergency stop {stop_state.value}: no new autonomous actions")

        # 2. CIRCUIT BREAKER — a tripped breaker halts autonomy (Part N).
        if breaker is not None:
            return mk(floor, floor, AutonomyEligibility.CIRCUIT_OPEN,
                      ApprovalRequirement.NOT_PERMITTED, f"circuit open: {breaker.reason}", brk=breaker)

        # An observe/recommend request (A0–A2) needs no earned authority.
        if not requested_level.permits_action():
            return mk(requested_level, requested_level, AutonomyEligibility.ELIGIBLE,
                      ApprovalRequirement.NOT_PERMITTED,
                      "observe/recommend level requested — no autonomous action")

        # 3. BLAST-RADIUS CAP — deterministic policy, never a model score (Part F/G).
        cap = config.cap_for_risk(risk.level)
        allowed = _level(min(requested_level.rank, cap.rank))
        if not allowed.permits_action():
            return mk(allowed, allowed, AutonomyEligibility.POLICY_FORBIDDEN,
                      ApprovalRequirement.NOT_PERMITTED,
                      f"blast radius {risk.level.value} caps autonomy at {cap.value}; "
                      "no autonomous action permitted for this action class")

        # 4. VERSION COMPATIBILITY — evidence must be for the CURRENT runtime (Part T).
        if reliability is not None:
            pc = reliability.prediction_class
            if pc.model_identity != model_id or pc.harness_version != harness_v:
                return mk(floor, floor, AutonomyEligibility.POLICY_FORBIDDEN,
                          ApprovalRequirement.NOT_PERMITTED,
                          f"calibration evidence is for model/harness "
                          f"{pc.model_identity}/{pc.harness_version}, not the current "
                          f"{model_id}/{harness_v}; autonomy must be re-evaluated")

        # 5. CALIBRATION EVIDENCE — advisory but REQUIRED to earn action (Part D/K).
        if reliability is None or reliability.status is CalibrationStatus.INSUFFICIENT_DATA:
            return mk(floor, floor, AutonomyEligibility.INSUFFICIENT_EVIDENCE,
                      ApprovalRequirement.NOT_PERMITTED,
                      "insufficient calibrated outcomes for this class; autonomy not eligible")
        if reliability.status in (CalibrationStatus.STALE, CalibrationStatus.INVALIDATED):
            return mk(floor, floor, AutonomyEligibility.STALE_EVIDENCE,
                      ApprovalRequirement.NOT_PERMITTED,
                      f"calibration is {reliability.status.value}; evidence no longer usable")
        if reliability.decided_count < config.min_decided_outcomes:
            return mk(floor, floor, AutonomyEligibility.INSUFFICIENT_EVIDENCE,
                      ApprovalRequirement.NOT_PERMITTED,
                      f"only {reliability.decided_count} decided outcomes "
                      f"(< {config.min_decided_outcomes} required)")
        rate = reliability.support_rate if reliability.support_rate is not None else 0.0
        if rate < config.min_support_rate:
            return mk(floor, floor, AutonomyEligibility.INELIGIBLE,
                      ApprovalRequirement.NOT_PERMITTED,
                      f"empirical reliability {rate:.2f} below the required {config.min_support_rate:.2f}")

        # 6. ASSURANCE COVERAGE — independent verification floor (Part F).
        coverage = reliability.assurance_coverage if reliability.assurance_coverage is not None else 0.0
        if coverage < config.min_assurance_coverage:
            return mk(floor, floor, AutonomyEligibility.ASSURANCE_INSUFFICIENT,
                      ApprovalRequirement.NOT_PERMITTED,
                      f"assurance coverage {coverage:.2f} below the required "
                      f"{config.min_assurance_coverage:.2f}")

        # 7. DRIFT — automatically reduces authority (Part L). One level down, no action.
        if config.require_no_drift and drift is DriftStatus.DRIFT_DETECTED:
            downgraded = _no_action_cap(allowed)
            return mk(allowed, downgraded, AutonomyEligibility.DRIFT_DETECTED,
                      ApprovalRequirement.NOT_PERMITTED,
                      "calibration drift detected; autonomy downgraded to non-action",
                      downgraded_from=allowed.value)

        # 8. FRESH / NON-CONFLICTED WORLD — stale/conflicted reduces authority (Part K).
        if config.deny_on_world_conflict and world_conflicted:
            return mk(allowed, _no_action_cap(allowed), AutonomyEligibility.POLICY_FORBIDDEN,
                      ApprovalRequirement.NOT_PERMITTED,
                      "conflicting authoritative world evidence; no autonomous action",
                      downgraded_from=allowed.value)
        if config.require_fresh_world and not world_fresh:
            return mk(allowed, _no_action_cap(allowed), AutonomyEligibility.STALE_EVIDENCE,
                      ApprovalRequirement.NOT_PERMITTED,
                      "current world state is stale; no autonomous action",
                      downgraded_from=allowed.value)

        # 9. REVERSIBILITY — an irreversible action at/above the floor needs a human (Part H).
        if (allowed.rank >= config.require_reversible_at_or_above.rank
                and capability.side_effect_class.mutates and not capability.reversible):
            forced = _level(min(allowed.rank, _A3.rank))
            return mk(allowed, forced, AutonomyEligibility.HUMAN_APPROVAL_REQUIRED,
                      ApprovalRequirement.HUMAN_APPROVAL,
                      "irreversible action: human approval required; no delegated autonomy",
                      downgraded_from=allowed.value if forced.rank < allowed.rank else None)

        # 10. APPROVAL — the earned level with its explicit approval requirement.
        approval = _approval_for(allowed)
        elig = (AutonomyEligibility.HUMAN_APPROVAL_REQUIRED if allowed is _A3
                else AutonomyEligibility.ELIGIBLE)
        reason = (f"earned {allowed.value}: reliability {rate:.2f} over "
                  f"{reliability.decided_count} independently-evaluated outcomes, assurance "
                  f"coverage {coverage:.2f}, blast {risk.level.value}, reversible="
                  f"{capability.reversible}")
        return mk(allowed, allowed, elig, approval, reason)
