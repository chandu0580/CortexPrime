"""Phase 8.8 — controlled autonomy & earned authority.

Autonomy is delegated authority the PLATFORM grants from independent evidence
(calibration, assurance, risk, world, versions) — never a capability, never a model
claim, never a global trust score. Authority is earned, scoped, and revoked the
moment the evidence no longer supports it (drift/conflict/stale/breaker/stop). The
model can never promote itself. In-memory evaluation; the real-Postgres controlled
experiment (governed action + audit) is the phase88 harness.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from backend.contracts.tenant import TenantRef
from backend.contracts.execution import SideEffectClass
from backend.contracts.errors import ContractViolation
from backend.contracts.policy import RiskClassification, RiskFactors, RiskLevel
from backend.contracts.world import ClaimConfidence
from backend.contracts.intelligence import (
    ApprovalRequirement, AutonomyDecision, AutonomyEligibility, AutonomyLevel,
    AutonomyPolicyConfig, AutonomyScope, BreakerTrip, CalibrationStatus, Capability,
    CircuitBreakerConfig, DriftStatus, EmergencyStopState, PredictionClass,
    ReliabilityEstimate, ReliabilityInterval,
)
from backend.intelligence.application import AutonomyPolicy

ACME, OTHER = TenantRef(tenant_id="acme"), TenantRef(tenant_id="other")
CFG = AutonomyPolicyConfig(policy_version="autpol/1")
VERSIONS = {"model_identity": "scripted", "harness_version": "h/1"}


def _t(m):
    return datetime(2026, 8, 12, 10, m, tzinfo=timezone.utc)


def _scope(tenant=ACME, env="development"):
    return AutonomyScope(tenant=tenant, environment=env, service="widget-svc",
                         capability_ref="cap:widget.create", operation="create", resource_class="widget")


def _cap(sec=SideEffectClass.REVERSIBLE_WRITE, reversible=True):
    return Capability(capability_ref="cap:widget.create", operation="create",
                      resource_class="widget", side_effect_class=sec, reversible=reversible)


def _risk(level=RiskLevel.LOW, env="development", reversible=True,
          sec=SideEffectClass.REVERSIBLE_WRITE, count=1):
    factors = RiskFactors(side_effect_class=sec, environment=env, resource_count=count,
                          reversible=reversible)
    return RiskClassification(level=level, factors=factors, rationale=f"{level.value} risk")


def _rel(status=CalibrationStatus.CALIBRATED, decided=10, supported=9, coverage=1.0,
         model="scripted", harness="h/1"):
    pc = PredictionClass("widget", "create", "development", model, harness)
    rate = (supported / decided) if (decided and status is not CalibrationStatus.INSUFFICIENT_DATA) else None
    return ReliabilityEstimate(
        prediction_class=pc, status=status, sample_count=decided, decided_count=decided,
        supported_count=supported, unsupported_count=decided - supported, insufficient_count=0,
        conflicted_count=0, pending_count=0, assured_count=int(round(coverage * decided)),
        dataset_digest="dd", policy_digest="pp",
        confidence=ClaimConfidence.calibrated(rate) if rate is not None else ClaimConfidence.uncalibrated(),
        generated_at=_t(9), support_rate=rate,
        interval=ReliabilityInterval("wilson", 0.95, 0.5, 0.99) if rate is not None else None,
        assurance_coverage=coverage)


def _go(requested, reliability=None, *, risk=None, cap=None, drift=DriftStatus.NO_DRIFT,
        fresh=True, conflict=False, stop=EmergencyStopState.RUNNING, breaker=None,
        versions=None, scope=None, config=CFG):
    return AutonomyPolicy().evaluate(
        requested_level=requested, scope=scope or _scope(), capability=cap or _cap(),
        risk=risk or _risk(), reliability=reliability if reliability is not None else _rel(),
        drift=drift, world_fresh=fresh, world_conflicted=conflict, versions=versions or VERSIONS,
        stop_state=stop, breaker=breaker, config=config, now=_t(10))


# ======================================================================
# Capability != permission != autonomy (Part B)
# ======================================================================

class TestCapabilityVsPermission:
    def test_capability_is_not_a_grant(self):
        # a HIGH-capability action (destructive) but the model requests A4; blast
        # radius caps it — capability does not imply permission or autonomy.
        d = _go(AutonomyLevel.A4_AUTONOMOUS, risk=_risk(RiskLevel.CRITICAL))
        assert d.allowed_level is AutonomyLevel.A1_INVESTIGATE  # critical caps at A1
        assert not d.permits_autonomous_action

    def test_low_permission_low_autonomy_is_legal(self):
        d = _go(AutonomyLevel.A0_OBSERVE)
        assert d.allowed_level is AutonomyLevel.A0_OBSERVE and d.eligibility is AutonomyEligibility.ELIGIBLE


# ======================================================================
# Autonomy is earned (Part D) and scoped (Part F)
# ======================================================================

class TestEarned:
    def test_earned_a3_requires_human_approval(self):
        d = _go(AutonomyLevel.A3_APPROVED_ACTION)
        assert d.allowed_level is AutonomyLevel.A3_APPROVED_ACTION
        assert d.eligibility is AutonomyEligibility.HUMAN_APPROVAL_REQUIRED
        assert d.approval_requirement is ApprovalRequirement.HUMAN_APPROVAL
        assert not d.permits_autonomous_action  # A3 not autonomous until approved

    def test_earned_a4_low_blast_reversible(self):
        d = _go(AutonomyLevel.A4_AUTONOMOUS)  # LOW blast + reversible + good evidence
        assert d.allowed_level is AutonomyLevel.A4_AUTONOMOUS
        assert d.eligibility is AutonomyEligibility.ELIGIBLE
        assert d.approval_requirement is ApprovalRequirement.POLICY_AUTHORIZATION
        assert d.permits_autonomous_action

    def test_insufficient_calibration_not_eligible(self):
        d = _go(AutonomyLevel.A3_APPROVED_ACTION, _rel(CalibrationStatus.INSUFFICIENT_DATA, 3, 2))
        assert d.eligibility is AutonomyEligibility.INSUFFICIENT_EVIDENCE
        assert not d.permits_autonomous_action

    def test_low_reliability_ineligible(self):
        d = _go(AutonomyLevel.A4_AUTONOMOUS, _rel(decided=10, supported=5))  # 0.5 < 0.8
        assert d.eligibility is AutonomyEligibility.INELIGIBLE

    def test_low_assurance_coverage_insufficient(self):
        d = _go(AutonomyLevel.A4_AUTONOMOUS, _rel(coverage=0.3))
        assert d.eligibility is AutonomyEligibility.ASSURANCE_INSUFFICIENT

    def test_scope_is_never_universal(self):
        d = _go(AutonomyLevel.A4_AUTONOMOUS)
        assert d.scope.capability_ref == "cap:widget.create" and d.scope.environment == "development"

    def test_blast_radius_caps_per_level(self):
        # HIGH blast caps at A2 (no action); MEDIUM caps at A3.
        assert _go(AutonomyLevel.A4_AUTONOMOUS, risk=_risk(RiskLevel.HIGH)).allowed_level is AutonomyLevel.A2_RECOMMEND
        assert _go(AutonomyLevel.A4_AUTONOMOUS, risk=_risk(RiskLevel.MEDIUM)).allowed_level is AutonomyLevel.A3_APPROVED_ACTION


# ======================================================================
# Authority is revoked when evidence deteriorates (Part L/Q)
# ======================================================================

class TestDowngradeAndRevocation:
    def test_drift_downgrades_to_non_action(self):
        d = _go(AutonomyLevel.A4_AUTONOMOUS, drift=DriftStatus.DRIFT_DETECTED)
        assert d.eligibility is AutonomyEligibility.DRIFT_DETECTED
        assert d.effective_level.rank < d.allowed_level.rank and not d.permits_autonomous_action
        assert d.downgraded_from == AutonomyLevel.A4_AUTONOMOUS.value

    def test_world_conflict_forbids_action(self):
        d = _go(AutonomyLevel.A4_AUTONOMOUS, conflict=True)
        assert d.eligibility is AutonomyEligibility.POLICY_FORBIDDEN and not d.permits_autonomous_action

    def test_stale_world_reduces_authority(self):
        d = _go(AutonomyLevel.A4_AUTONOMOUS, fresh=False)
        assert d.eligibility is AutonomyEligibility.STALE_EVIDENCE and not d.permits_autonomous_action

    def test_emergency_stop_blocks_new_actions(self):
        d = _go(AutonomyLevel.A4_AUTONOMOUS, stop=EmergencyStopState.STOP_ACTIVE)
        assert d.eligibility is AutonomyEligibility.EMERGENCY_STOPPED and not d.permits_autonomous_action

    def test_circuit_breaker_halts(self):
        trip = CircuitBreakerConfig().evaluate(verification_failures=1)
        assert trip is not None and trip.trigger == "verification_failure"
        d = _go(AutonomyLevel.A4_AUTONOMOUS, breaker=trip)
        assert d.eligibility is AutonomyEligibility.CIRCUIT_OPEN and d.breaker is not None

    def test_irreversible_requires_human(self):
        d = _go(AutonomyLevel.A4_AUTONOMOUS,
                cap=_cap(sec=SideEffectClass.DESTRUCTIVE, reversible=False),
                risk=_risk(RiskLevel.LOW, sec=SideEffectClass.DESTRUCTIVE, reversible=False))
        assert d.eligibility is AutonomyEligibility.HUMAN_APPROVAL_REQUIRED
        assert d.approval_requirement is ApprovalRequirement.HUMAN_APPROVAL
        assert not d.permits_autonomous_action  # no delegated autonomy for irreversible


# ======================================================================
# Version compatibility (Part T)
# ======================================================================

class TestVersionBinding:
    def test_evidence_from_other_version_forbidden(self):
        d = _go(AutonomyLevel.A4_AUTONOMOUS, _rel(model="scripted", harness="h/2"))  # current is h/1
        assert d.eligibility is AutonomyEligibility.POLICY_FORBIDDEN
        assert "re-evaluated" in d.reason

    def test_matching_version_allowed(self):
        d = _go(AutonomyLevel.A4_AUTONOMOUS, _rel(harness="h/1"))
        assert d.permits_autonomous_action


# ======================================================================
# No global trust score; explainable (Part E/J)
# ======================================================================

class TestExplainable:
    def test_decision_is_typed_not_a_number(self):
        d = _go(AutonomyLevel.A4_AUTONOMOUS)
        dd = d.to_dict()
        assert "trust_score" not in dd and not any("trust" in k for k in dd)
        assert isinstance(d.eligibility, AutonomyEligibility)

    def test_reason_is_specific_not_vague(self):
        d = _go(AutonomyLevel.A4_AUTONOMOUS, conflict=True)
        assert d.reason and "safety policy prevented" not in d.reason.lower()
        assert "conflict" in d.reason.lower()

    def test_effective_never_exceeds_allowed(self):
        # the contract forbids a silent escalation
        with pytest.raises(ContractViolation):
            _base = _go(AutonomyLevel.A4_AUTONOMOUS)
            AutonomyDecision(**{**_base.__dict__, "effective_level": AutonomyLevel.A4_AUTONOMOUS,
                               "allowed_level": AutonomyLevel.A2_RECOMMEND})


# ======================================================================
# Model cannot promote / self-reinforce (Part W/X)
# ======================================================================

class TestModelCannotPromote:
    def test_model_output_is_not_a_parameter(self):
        # AutonomyPolicy.evaluate takes only typed evidence; there is no model/prompt
        # parameter through which model text could influence authority.
        import inspect
        params = set(inspect.signature(AutonomyPolicy.evaluate).parameters)
        assert not (params & {"model_output", "proposal", "prompt", "model", "context"})

    def test_decision_is_immutable(self):
        d = _go(AutonomyLevel.A4_AUTONOMOUS)
        with pytest.raises(Exception):
            d.allowed_level = AutonomyLevel.A4_AUTONOMOUS  # frozen

    def test_self_reinforcing_loop_broken(self):
        # even with a perfect (10/10) record, autonomy still needs INDEPENDENT
        # assurance coverage + reversible + bounded blast + no drift + fresh world;
        # a supported record ALONE (0 assurance) cannot promote.
        d = _go(AutonomyLevel.A4_AUTONOMOUS, _rel(decided=10, supported=10, coverage=0.0))
        assert not d.permits_autonomous_action
        assert d.eligibility is AutonomyEligibility.ASSURANCE_INSUFFICIENT

    def test_autonomy_module_not_model_driven_fitness(self, tmp_path):
        import textwrap
        from backend.platform.architecture.boundary_rules import AutonomyNotModelDrivenRule
        from backend.platform.architecture.rules import ModuleGraph
        root = tmp_path / "backend"
        (root / "intelligence" / "application").mkdir(parents=True)
        (root / "intelligence" / "application" / "autonomy.py").write_text(
            textwrap.dedent("from backend.harness.llm_boundary import GovernedModelBoundary\n"),
            encoding="utf-8")
        graph = ModuleGraph.build(root, package_root=root.name)
        assert not AutonomyNotModelDrivenRule().evaluate(graph).passed

    def test_current_autonomy_module_passes(self):
        from pathlib import Path
        from backend.platform.architecture.boundary_rules import (
            AutonomyNotModelDrivenRule, IntelligenceCannotExecuteRule)
        from backend.platform.architecture.rules import ModuleGraph
        graph = ModuleGraph.build(Path(__file__).resolve().parents[2] / "backend")
        assert AutonomyNotModelDrivenRule().evaluate(graph).passed       # not model-driven
        assert IntelligenceCannotExecuteRule().evaluate(graph).passed    # cannot reach the gateway


# ======================================================================
# Tenant isolation (Part S)
# ======================================================================

class TestTenantScope:
    def test_decision_carries_the_requesting_tenant(self):
        d = _go(AutonomyLevel.A4_AUTONOMOUS, scope=_scope(tenant=OTHER))
        assert d.scope.tenant.tenant_id == "other"
        # a scope for OTHER never mentions ACME
        assert "acme" not in d.scope.key
