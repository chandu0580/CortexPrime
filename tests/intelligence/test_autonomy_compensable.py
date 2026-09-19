"""L10's compensable class in the autonomy policy (ADR-124).

The rule is additive and OFF by default: every capability that existed before
keeps exactly the behaviour it had, a compensable capability is still forced to
a human unless an explicit versioned policy says otherwise, and nothing
DESTRUCTIVE is ever compensable. Every other gate still applies first.
"""

from __future__ import annotations

import dataclasses

import pytest

from backend.contracts.errors import ContractViolation
from backend.contracts.execution import EffectSemantics, SideEffectClass
from backend.contracts.intelligence import (
    ApprovalRequirement, AutonomyEligibility, AutonomyLevel, AutonomyPolicyConfig, Capability,
    CalibrationStatus, CircuitBreakerConfig, DriftStatus,
)
from backend.contracts.policy import RiskLevel
from tests.intelligence.test_autonomy import CFG, _go, _rel, _risk

ROLLBACK = dict(capability_ref="platform.kubernetes.deployment.rollback", operation="rollback",
                resource_class="deployment", side_effect_class=SideEffectClass.IRREVERSIBLE_WRITE, reversible=False)
ENABLED = AutonomyPolicyConfig(policy_version="phase114-autonomy/1", compensable_autonomy=True,
                               max_level_medium=AutonomyLevel.A4_AUTONOMOUS)
MEDIUM = _risk(level=RiskLevel.MEDIUM, reversible=False, sec=SideEffectClass.IRREVERSIBLE_WRITE)


def _cap(compensable: bool) -> Capability:
    return Capability(**ROLLBACK, compensable=compensable)


class TestTheDefaultIsUnchanged:
    def test_the_default_config_does_not_enable_the_compensable_class(self):
        assert AutonomyPolicyConfig(policy_version="x").compensable_autonomy is False
        assert Capability(**ROLLBACK).compensable is False

    def test_a_compensable_capability_under_the_default_policy_still_needs_a_human(self):
        config = dataclasses.replace(CFG, max_level_medium=AutonomyLevel.A4_AUTONOMOUS)
        decision = _go(AutonomyLevel.A4_AUTONOMOUS, cap=_cap(True), risk=MEDIUM, config=config)
        assert decision.eligibility is AutonomyEligibility.HUMAN_APPROVAL_REQUIRED
        assert decision.approval_requirement is ApprovalRequirement.HUMAN_APPROVAL
        assert not decision.permits_autonomous_action
        assert "compensable" in decision.reason

    def test_an_irreversible_capability_under_the_enabled_policy_still_needs_a_human(self):
        decision = _go(AutonomyLevel.A4_AUTONOMOUS, cap=_cap(False), risk=MEDIUM, config=ENABLED)
        assert decision.eligibility is AutonomyEligibility.HUMAN_APPROVAL_REQUIRED
        assert "irreversible action" in decision.reason


class TestTheEnabledCompensableClassEarnsAutonomy:
    def test_a_verified_compensable_action_with_earned_reliability_is_policy_authorized(self):
        decision = _go(AutonomyLevel.A4_AUTONOMOUS, cap=_cap(True), risk=MEDIUM, config=ENABLED)
        assert decision.effective_level is AutonomyLevel.A4_AUTONOMOUS
        assert decision.approval_requirement is ApprovalRequirement.POLICY_AUTHORIZATION
        assert decision.permits_autonomous_action
        assert "compensable" in decision.reason

    @pytest.mark.parametrize("gate, kwargs, eligibility", [
        ("no calibration", {"reliability": _rel(status=CalibrationStatus.INSUFFICIENT_DATA, decided=3, supported=3)},
         AutonomyEligibility.INSUFFICIENT_EVIDENCE),
        ("low reliability", {"reliability": _rel(decided=10, supported=5)}, AutonomyEligibility.INELIGIBLE),
        ("thin assurance", {"reliability": _rel(coverage=0.2)}, AutonomyEligibility.ASSURANCE_INSUFFICIENT),
        ("drift", {"drift": DriftStatus.DRIFT_DETECTED}, AutonomyEligibility.DRIFT_DETECTED),
        ("breaker", {"breaker": CircuitBreakerConfig().evaluate(verification_failures=1)},
         AutonomyEligibility.CIRCUIT_OPEN),
        ("stale world", {"fresh": False}, AutonomyEligibility.STALE_EVIDENCE),
    ])
    def test_every_earlier_gate_still_refuses_first(self, gate, kwargs, eligibility):
        decision = _go(AutonomyLevel.A4_AUTONOMOUS, cap=_cap(True), risk=MEDIUM, config=ENABLED, **kwargs)
        assert decision.eligibility is eligibility, gate
        assert not decision.permits_autonomous_action

    def test_high_action_risk_caps_at_human_approval(self):
        high = _risk(level=RiskLevel.HIGH, reversible=False, sec=SideEffectClass.IRREVERSIBLE_WRITE)
        config = dataclasses.replace(ENABLED, max_level_high=AutonomyLevel.A3_APPROVED_ACTION)
        decision = _go(AutonomyLevel.A4_AUTONOMOUS, cap=_cap(True), risk=high, config=config)
        assert decision.effective_level is AutonomyLevel.A3_APPROVED_ACTION
        assert decision.approval_requirement is ApprovalRequirement.HUMAN_APPROVAL

    def test_critical_action_risk_permits_no_action_at_all(self):
        critical = _risk(level=RiskLevel.CRITICAL, reversible=False, sec=SideEffectClass.IRREVERSIBLE_WRITE)
        decision = _go(AutonomyLevel.A4_AUTONOMOUS, cap=_cap(True), risk=critical, config=ENABLED)
        assert decision.eligibility is AutonomyEligibility.POLICY_FORBIDDEN
        assert not decision.effective_level.permits_action()


class TestDestructiveIsNeverCompensable:
    def test_the_capability_contract_refuses_a_compensable_destructive_action(self):
        with pytest.raises(ContractViolation):
            Capability(capability_ref="x", operation="delete", resource_class="deployment",
                       side_effect_class=SideEffectClass.DESTRUCTIVE, reversible=False, compensable=True)

    def test_a_profile_cannot_bridge_a_destructive_compensation(self):
        from backend.contracts.intelligence.capability_profile import CapabilityProfile, VerificationRequirement
        profile = CapabilityProfile(
            capability_ref="x", provider="p", operation="delete", side_effect_class=SideEffectClass.DESTRUCTIVE,
            effect_semantics=EffectSemantics.NON_IDEMPOTENT_WRITE,
            risk=_risk(level=RiskLevel.CRITICAL, reversible=False, sec=SideEffectClass.DESTRUCTIVE),
            autonomy_ceiling=AutonomyLevel.A1_INVESTIGATE,
            verification_requirement=VerificationRequirement.INDEPENDENT_READBACK,
            resource_scope="deployment", reversible=False, timeout_seconds=10, policy_version="v",
            compensation="y")
        assert profile.to_capability(compensation_verified=True).compensable is False


class TestTheRollbackProfile:
    def test_the_rollback_is_irreversible_but_declares_its_compensation(self):
        from backend.contexts.execution.infrastructure.adapters.connectors.kubernetes import (
            DEPLOYMENT_ROLLBACK_OPERATION, ROLLOUT_RESTART_OPERATION, kubernetes_write_profiles,
        )
        profiles = kubernetes_write_profiles()
        rollback = profiles[DEPLOYMENT_ROLLBACK_OPERATION]
        assert rollback.side_effect_class is SideEffectClass.IRREVERSIBLE_WRITE and rollback.reversible is False
        assert rollback.compensation == f"platform.{DEPLOYMENT_ROLLBACK_OPERATION}"
        assert rollback.to_capability().compensable is False, "unverified compensation is not compensable"
        assert rollback.to_capability(compensation_verified=True).compensable is True
        restart = profiles[ROLLOUT_RESTART_OPERATION]
        assert restart.compensation is None and restart.to_capability(compensation_verified=True).compensable is False

    def test_a_read_profile_may_not_declare_a_compensation(self):
        from backend.contexts.execution.infrastructure.adapters.connectors.kubernetes import kubernetes_read_profiles
        profile = next(iter(kubernetes_read_profiles().values()))
        with pytest.raises(ContractViolation):
            dataclasses.replace(profile, compensation="anything")
