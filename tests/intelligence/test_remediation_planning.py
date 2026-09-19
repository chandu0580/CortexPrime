"""Remediation planning (ADR-124): the model proposes, the platform decides.

Every refusal is asserted to produce NO plan -- a decision with its reasons --
and every plan is asserted to bind exactly the resource the incident names, at
a revision the Deployment itself still owns, with a platform-computed risk.
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from backend.api.remediation_planning import (
    ACTION_ROLLBACK, CapabilityFacts, DiagnosisFacts, PlanningScope, RemediationPlanner, WorldSnapshot,
    classify_action, classify_action_risk, workload_of,
)
from backend.contracts.errors import ContractViolation
from backend.contracts.execution import SideEffectClass
from backend.contracts.policy import RiskLevel
from backend.contracts.remediation import PlanAuthority, RemediationPlan, RemediationStage, ReversibilityClass
from backend.intelligence.application.remediation_proposal import ProposedRemediation

NOW = datetime(2026, 9, 11, 12, 0, tzinfo=timezone.utc)
UID = "11111111-2222-3333-4444-555555555555"
NS, NAME = "cortex-p99b", "p114-shop"
INCIDENT = f"kubernetes:pod:{NS}/{NAME}-7d9c8f6b5d-abcde"
GOOD, BAD, OLDER = "a" * 64, "b" * 64, "c" * 64


def _assessment(**overrides):
    document = {
        "incident_ref": INCIDENT, "outcome": "ROOT_CAUSE_IDENTIFIED", "confidence": "high",
        "root_cause": "a recent deployment revision introduced the failure -- specifically: startup panic",
        "root_cause_hypothesis": "h-startup-failure",
        "supporting_evidence": ["wobs_rollout", "wobs_logs"],
        "weights": [{"observation_ref": "wobs_rollout", "hypothesis_ref": "h-deployment-regression",
                     "role": "supports"},
                    {"observation_ref": "wobs_logs", "hypothesis_ref": "h-startup-failure", "role": "supports"}],
        "recommended_action_candidate": "roll the deployment back to the previous revision (requires approval)",
    }
    document.update(overrides)
    return document


def _proposal(**overrides):
    fields = dict(action=ACTION_ROLLBACK, target_kind="Deployment", target_namespace=NS, target_name=NAME,
                  target_revision=None, hypothesis_ref="h-deployment-regression", evidence_refs=("wobs_rollout",),
                  expected_outcome="healthy", rollback_strategy="roll back again", rationale="regression",
                  source="model", model_identity="openai-compatible:glm-5.2", digest="d" * 64)
    fields.update(overrides)
    return ProposedRemediation(**fields)


def _world(**overrides):
    deployment = {"name": NAME, "namespace": NS, "uid": UID, "generation": 7, "revision": "3",
                  "templateDigest": BAD, "replicas": 1, "revisionHistoryLimit": 10, "persistentVolumeClaims": 0,
                  "paused": False}
    deployment.update(overrides.pop("deployment", {}))
    replicasets = overrides.pop("replicasets", [
        {"name": f"{NAME}-older", "revision": "1", "ownerUid": UID, "podTemplateDigest": OLDER},
        {"name": f"{NAME}-good", "revision": "2", "ownerUid": UID, "podTemplateDigest": GOOD},
        {"name": f"{NAME}-bad", "revision": "3", "ownerUid": UID, "podTemplateDigest": BAD},
    ])
    return WorldSnapshot(deployment=deployment, replicasets=replicasets, observation_refs=("wobs_target",),
                         healthy_revisions=overrides.pop("healthy", {"2": ("wobs_pod_healthy",)}), read_at=NOW)


def _decision(permits: bool):
    return SimpleNamespace(permits_autonomous_action=permits, reason="stub autonomy",
                           approval_requirement=SimpleNamespace(value="policy_authorization" if permits
                                                                else "human_approval"),
                           decision_id="autdec_1", eligibility=SimpleNamespace(value="eligible"))


def _planner(*, permits=False, production=False, compensation=True, seen=None):
    def autonomy(*, capability, risk, requested, now):
        if seen is not None:
            seen.append((capability, risk, requested))
        return _decision(permits)
    return RemediationPlanner(
        scope=PlanningScope(tenant_id="tenant-a", cluster_ref="k3d", namespace=NS, environment="development",
                            production=production, principal_id="remediation-runtime",
                            policy_version="phase114-autonomy/1+phase114-remediation/1+compensable=1"),
        capability=CapabilityFacts(capability_ref="platform.kubernetes.deployment.rollback@1",
                                   capability_digest="capdigest", operation="kubernetes.deployment.rollback",
                                   risk_floor=RiskLevel.HIGH, side_effect_class=SideEffectClass.IRREVERSIBLE_WRITE,
                                   compensation_declared=compensation),
        approval_digest=lambda payload: "approval:" + "|".join(f"{k}={payload[k]}" for k in sorted(payload)),
        autonomy=autonomy)


def _plan(planner=None, *, proposal=None, assessment=None, world=None, diagnosed=BAD):
    return (planner or _planner()).plan(
        incident_ref=INCIDENT, investigation_ref="winv_1", proposal=proposal or _proposal(),
        diagnosis=DiagnosisFacts(assessment=assessment or _assessment(), assessment_ref="wreason_a",
                                 diagnosed_template_digest=diagnosed, rollout_observation_ref="wobs_rollout"),
        world=world or _world(), now=NOW)


class TestTheToolRegistry:
    @pytest.mark.parametrize("action", ["deployment.delete", "shell.exec", "kubectl delete deploy payments-api",
                                        "cluster-admin", "credential.read", "http.request", "pod.delete",
                                        "namespace.delete", "kubectl.exec", "secret.read"])
    def test_prohibited_actions_are_prohibited(self, action):
        assert classify_action(action)[0] == "prohibited"

    def test_an_unknown_capability_is_unknown(self):
        assert classify_action("deployment.frobnicate")[0] == "unknown"

    @pytest.mark.parametrize("action, stage", [("deployment.delete", RemediationStage.PROHIBITED),
                                               ("shell.exec", RemediationStage.PROHIBITED),
                                               ("deployment.frobnicate", RemediationStage.PROPOSAL_REJECTED),
                                               ("no_action", RemediationStage.RECOMMENDATION_ONLY)])
    def test_a_non_admitted_action_never_becomes_a_plan(self, action, stage):
        result = _plan(proposal=_proposal(action=action))
        assert result.plan is None and result.decision.stage is stage and result.decision.reasons


class TestTheDiagnosisMustSupportTheAction:
    def test_a_configuration_failure_is_not_rolled_back(self):
        assessment = _assessment(root_cause_hypothesis="h-configuration",
                                 weights=[{"observation_ref": "wobs_logs", "hypothesis_ref": "h-configuration",
                                           "role": "supports"}])
        result = _plan(assessment=assessment)
        assert result.plan is None and "does not support a rollback" in result.decision.reasons[0]
        assert result.decision.recommendation

    def test_insufficient_evidence_is_not_rolled_back(self):
        result = _plan(assessment=_assessment(outcome="INSUFFICIENT_EVIDENCE", confidence="none"))
        assert result.plan is None

    def test_a_rollback_justified_by_another_hypothesis_is_rejected(self):
        result = _plan(proposal=_proposal(hypothesis_ref="h-resource-exhaustion"))
        assert result.plan is None and "rests on h-deployment-regression" in result.decision.reasons[0]

    def test_foreign_evidence_cannot_establish_authority(self):
        result = _plan(proposal=_proposal(evidence_refs=("wobs_from_tenant_b",)))
        assert result.plan is None and "missing evidence" in result.decision.reasons[0]

    def test_a_stale_diagnosis_is_rejected(self):
        result = _plan(diagnosed=OLDER)
        assert result.plan is None and "stale" in result.decision.reasons[0]


class TestTargetBinding:
    @pytest.mark.parametrize("namespace, name", [(NS, "billing-api"), ("tenant-b-namespace", NAME),
                                                 ("kube-system", "coredns")])
    def test_a_confused_deputy_target_is_rejected(self, namespace, name):
        result = _plan(proposal=_proposal(target_namespace=namespace, target_name=name))
        assert result.plan is None and "outside this incident" in result.decision.reasons[0]

    def test_the_target_is_resolved_to_a_uid_generation_and_digest(self):
        plan = _plan().plan
        assert (plan.target.uid, plan.target.generation, plan.target.current_revision,
                plan.target.current_template_digest) == (UID, 7, 3, BAD)

    def test_the_newest_prior_revision_with_a_different_template_is_chosen(self):
        assert _plan().plan.parameters["target_revision"] == 2

    def test_an_explicit_revision_is_honoured_only_if_the_deployment_owns_it(self):
        assert _plan(proposal=_proposal(target_revision=1)).plan.parameters["target_revision"] == 1
        for bad_revision in (3, 9):
            result = _plan(proposal=_proposal(target_revision=bad_revision))
            assert result.plan is None and "no substitute" in result.decision.reasons[0]

    def test_a_revision_owned_by_another_object_is_not_available(self):
        world = _world(replicasets=[{"name": "x", "revision": "2", "ownerUid": "other", "podTemplateDigest": GOOD},
                                    {"name": f"{NAME}-bad", "revision": "3", "ownerUid": UID, "podTemplateDigest": BAD}])
        assert _plan(world=world).plan is None

    def test_a_paused_deployment_is_not_planned(self):
        assert _plan(world=_world(deployment={"paused": True})).plan is None


class TestRiskAndAuthority:
    def test_a_compensable_healthy_non_production_single_rollback_is_medium(self):
        plan = _plan().plan
        assert plan.risk.level is RiskLevel.MEDIUM and plan.reversibility is ReversibilityClass.COMPENSABLE

    def test_unknown_target_health_keeps_the_capability_floor(self):
        assert _plan(world=_world(healthy={})).plan.risk.level is RiskLevel.HIGH

    def test_production_is_at_least_high(self):
        assert _plan(_planner(production=True)).plan.risk.level is RiskLevel.HIGH

    def test_no_compensation_is_irreversible_and_high(self):
        plan = _plan(_planner(compensation=False)).plan
        assert plan.reversibility is ReversibilityClass.IRREVERSIBLE and plan.risk.level is RiskLevel.HIGH

    def test_many_replicas_is_high(self):
        assert _plan(world=_world(deployment={"replicas": 40})).plan.risk.level is RiskLevel.HIGH

    def test_destructive_is_always_critical(self):
        risk = classify_action_risk(floor=RiskLevel.CRITICAL, side_effect_class=SideEffectClass.DESTRUCTIVE,
                                    environment="development", production=False, resource_count=1, replicas=1,
                                    persistent_volumes=False, compensation_available=True, target_health_known=True)
        assert risk.level is RiskLevel.CRITICAL

    def test_the_policy_decides_autonomy_from_a_compensable_capability(self):
        seen = []
        plan = _plan(_planner(permits=True, seen=seen)).plan
        assert plan.authority is PlanAuthority.AUTONOMOUS
        capability, risk, requested = seen[0]
        assert capability.compensable is True and capability.reversible is False
        assert requested.value == "a4_autonomous"

    def test_without_the_policys_permission_a_human_approves(self):
        assert _plan(_planner(permits=False)).plan.authority is PlanAuthority.HUMAN_APPROVAL

    def test_a_deterministic_proposal_is_a_recommendation_even_if_policy_would_permit(self):
        plan = _plan(_planner(permits=True), proposal=_proposal(source="deterministic",
                                                                model_identity="deterministic")).plan
        assert plan.authority is PlanAuthority.RECOMMENDATION_ONLY

    def test_an_irreversible_plan_is_never_autonomous(self):
        plan = _plan(_planner(permits=True, compensation=False)).plan
        assert plan.authority is PlanAuthority.HUMAN_APPROVAL


class TestTheDigestBindsTheAction:
    def test_parameters_bind_target_revision_plan_and_policy(self):
        plan = _plan().plan
        p = plan.parameters
        assert set(p) == {"namespace", "name", "uid", "expected_generation", "expected_revision",
                          "expected_template_digest", "target_revision", "target_template_digest",
                          "plan_id", "policy_version"}
        assert p["plan_id"] == plan.plan_id and p["policy_version"] == plan.policy_version
        assert plan.action_digest.startswith("approval:") and f"uid={UID}" in plan.action_digest

    def test_a_different_policy_version_is_a_different_plan_and_digest(self):
        first = _plan().plan
        other = RemediationPlanner(
            scope=PlanningScope(tenant_id="tenant-a", cluster_ref="k3d", namespace=NS, environment="development",
                                production=False, principal_id="remediation-runtime", policy_version="phase114-autonomy/2"),
            capability=_planner()._capability, approval_digest=_planner()._approval_digest,
            autonomy=lambda **kw: _decision(False))
        second = _plan(other).plan
        assert first.plan_id != second.plan_id and first.action_digest != second.action_digest

    def test_the_plan_round_trips_through_its_contract(self):
        plan = _plan().plan
        again = RemediationPlan.from_dict(plan.to_dict())
        assert again.plan_id == plan.plan_id and dict(again.parameters) == dict(plan.parameters)
        assert again.risk.level is plan.risk.level and again.authority is plan.authority

    def test_the_contract_refuses_an_autonomous_irreversible_plan(self):
        import dataclasses
        plan = _plan().plan
        with pytest.raises(ContractViolation):
            dataclasses.replace(plan, authority=PlanAuthority.AUTONOMOUS,
                                reversibility=ReversibilityClass.IRREVERSIBLE)


def test_workload_of_reduces_a_pod_to_its_deployment():
    assert workload_of(INCIDENT) == (NS, NAME)
    assert workload_of(f"kubernetes:deployment:{NS}/{NAME}") == (NS, NAME)
    assert workload_of("rollback production") is None
