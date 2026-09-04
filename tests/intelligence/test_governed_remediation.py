"""Phase 9.6 (ADR-086): the first governed Kubernetes write — unit evidence.

What these prove without a cluster:

- The rollout restart is declared **IRREVERSIBLE**, and that is not pessimism:
  the contract defines REVERSIBLE_WRITE as having an inverse that *fully restores
  the prior state*, and a restart stamps the pod template and creates a revision
  nothing removes.
- Because it is declared honestly, the existing autonomy policy refuses to
  delegate it: A4 requested becomes A3 with HUMAN_APPROVAL_REQUIRED, through gate
  9, with no rule added and no policy weakened.
- Blast radius is a property of the types: `RemediationTarget` cannot express a
  selector, a list or a wildcard, and the operation declares two path parameters
  and nothing else.
- The body builder produces exactly one document, keyed on the platform's action
  identity rather than a clock, and refuses without one.
- Every approval mismatch — tenant, operation, digest, expiry, denial — refuses.
- Execution result and world outcome are separate fields, and rollback is
  classified unavailable with its reason.

The real cluster and the real write live in
``scripts/phase96_reversible_remediation_harness.py``.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from backend.contracts.errors import ContractViolation
from backend.contracts.execution import EffectSemantics, SideEffectClass
from backend.contracts.intelligence.investigation import AutonomyLevel
from backend.contexts.execution.infrastructure.adapters.connectors.kubernetes import (
    KUBERNETES_REAL_READ_OPERATIONS,
    RESTART_ANNOTATION,
    ROLLOUT_RESTART_OPERATION,
    KubernetesReadNormalizer,
    KubernetesRestartBodyBuilder,
    kubernetes_read_catalog,
    kubernetes_write_catalog,
    kubernetes_write_profiles,
)
from backend.api.remediation import (
    RemediationOutcome, RemediationResult, RemediationTarget,
)

NS = "cortex-p96"


def _spec():
    return kubernetes_write_catalog().require(ROLLOUT_RESTART_OPERATION)


def _profile():
    return kubernetes_write_profiles()[ROLLOUT_RESTART_OPERATION]


# ---------------------------------------------------------------------------
# The declaration
# ---------------------------------------------------------------------------

class TestTheWriteIsDeclaredHonestly:
    def test_there_is_exactly_one_kubernetes_write(self):
        catalog = kubernetes_write_catalog()
        mutating = [op for op in catalog.operations
                    if catalog.require(op).side_effect_class.mutates]
        assert mutating == [ROLLOUT_RESTART_OPERATION]

    def test_it_is_irreversible_not_reversible(self):
        # The contract's own words: REVERSIBLE_WRITE means "a declared inverse
        # fully restores the prior state". A restart stamps the pod template and
        # creates a revision; nothing removes either.
        assert _spec().side_effect_class is SideEffectClass.IRREVERSIBLE_WRITE
        assert _profile().reversible is False
        assert not SideEffectClass.IRREVERSIBLE_WRITE.requires_inverse

    def test_it_is_declared_non_idempotent(self):
        assert _spec().effect_semantics is EffectSemantics.NON_IDEMPOTENT_WRITE
        assert not _spec().effect_semantics.is_repeatable

    def test_a_mutating_capability_cannot_declare_no_verification(self):
        import dataclasses
        from backend.contracts.intelligence.capability_profile import (
            VerificationRequirement,
        )
        with pytest.raises(ContractViolation, match="independent verification"):
            dataclasses.replace(_profile(),
                                verification_requirement=VerificationRequirement.NONE)

    def test_its_autonomy_ceiling_is_a3_never_a4(self):
        assert _profile().autonomy_ceiling is AutonomyLevel.A3_APPROVED_ACTION
        assert _profile().autonomy_ceiling.rank < AutonomyLevel.A4_AUTONOMOUS.rank

    def test_it_is_a_patch_with_a_strategic_merge_content_type(self):
        spec = _spec()
        assert spec.method == "PATCH"
        assert spec.static_headers["content-type"] == (
            "application/strategic-merge-patch+json")

    def test_exactly_one_write_is_declared_and_none_is_exposed(self):
        """Declared is not exposed, and after ADR-086 that gap is deliberate.

        The write exists as a contract. It is absent from the real read exposure
        because an IRREVERSIBLE_WRITE may not be performed by the CONTAINED
        in-process worker that serves that exposure, and offering an operation a
        worker must refuse is worse than not offering it.
        """
        write_catalog = kubernetes_write_catalog()
        declared_writes = [op for op in write_catalog.operations
                           if write_catalog.require(op).side_effect_class.mutates]
        assert declared_writes == [ROLLOUT_RESTART_OPERATION]

        read_catalog = kubernetes_read_catalog()
        assert not any(read_catalog.require(op).side_effect_class.mutates
                       for op in read_catalog.operations)
        assert ROLLOUT_RESTART_OPERATION not in KUBERNETES_REAL_READ_OPERATIONS


class TestBlastRadiusIsInTheTypes:
    def test_the_operation_declares_only_namespace_and_name(self):
        assert {p.name for p in _spec().parameters} == {"namespace", "name"}

    def test_there_is_no_selector_list_or_wildcard_parameter(self):
        names = {p.name.lower() for p in _spec().parameters}
        assert not (names & {"selector", "labelselector", "all", "names", "targets"})

    def test_a_wildcard_target_is_refused(self):
        for namespace, workload in ((NS, "*"), ("*", "app"), (NS, "a,b"),
                                    (NS, "a b"), (NS, "ns/app")):
            with pytest.raises(ContractViolation):
                RemediationTarget(namespace=namespace, workload=workload)

    def test_only_a_deployment_can_be_targeted(self):
        with pytest.raises(ContractViolation, match="only deployments"):
            RemediationTarget(namespace=NS, workload="app", kind="daemonset")

    def test_a_target_names_exactly_one_workload(self):
        target = RemediationTarget(namespace=NS, workload="payments-api")
        assert target.subject_ref == f"kubernetes:deployment:{NS}/payments-api"


# ---------------------------------------------------------------------------
# The body builder
# ---------------------------------------------------------------------------

class TestRestartBodyBuilder:
    def test_it_builds_exactly_one_document(self):
        body = KubernetesRestartBodyBuilder().build(
            _spec(), {"namespace": NS, "name": "app"}, idempotency_key="act_1")
        assert body == {"spec": {"template": {"metadata": {"annotations": {
            RESTART_ANNOTATION: "act_1"}}}}}

    def test_it_stamps_the_platforms_action_identity_not_a_clock(self):
        build = KubernetesRestartBodyBuilder().build
        first = build(_spec(), {}, idempotency_key="act_1")
        second = build(_spec(), {}, idempotency_key="act_1")
        # Same authority, same request — which is what makes an approval binding
        # and a replay inert. A timestamp would differ every call.
        assert first == second
        assert build(_spec(), {}, idempotency_key="act_2") != first

    def test_it_refuses_without_an_action_identity(self):
        for key in (None, "", "   "):
            with pytest.raises(ValueError, match="action identity"):
                KubernetesRestartBodyBuilder().build(_spec(), {}, idempotency_key=key)

    def test_it_builds_nothing_for_any_other_operation(self):
        # The builder is attached to the whole adapter; every read keeps the flat
        # body its spec declares.
        for op in ("kubernetes.pods.list", "kubernetes.deployment.get"):
            spec = kubernetes_write_catalog().require(op)
            assert KubernetesRestartBodyBuilder().build(
                spec, {}, idempotency_key="act_1") is None

    def test_the_annotation_is_cortexprimes_own_not_kubectls(self):
        # Writing kubectl's annotation would make a platform action
        # indistinguishable from a human running kubectl.
        assert RESTART_ANNOTATION.startswith("cortexprime.io/")
        assert "kubectl" not in RESTART_ANNOTATION

    def test_the_normalizer_lifts_the_stamp_back_for_read_back(self):
        out = KubernetesReadNormalizer().normalize(
            kubernetes_read_catalog().require("kubernetes.deployment.get"),
            {"kind": "Deployment",
             "metadata": {"name": "app", "namespace": NS, "resourceVersion": "9",
                          "annotations": {"deployment.kubernetes.io/revision": "3"}},
             "spec": {"replicas": 1, "template": {
                 "metadata": {"annotations": {RESTART_ANNOTATION: "act_1"}},
                 "spec": {"containers": [{"image": "busybox:1.36"}]}}},
             "status": {"readyReplicas": 1}})
        assert out["restartedByAction"] == "act_1"


# ---------------------------------------------------------------------------
# The autonomy consequence of telling the truth
# ---------------------------------------------------------------------------

def _autonomy_inputs(**overrides):
    """The platform-side inputs to an autonomy decision.

    Every one of these comes from the platform: the stop state, the breaker, the
    calibration evidence, the drift verdict and the world's freshness. None of
    them is anything a model produced, which is the property the decision below
    depends on.
    """
    from datetime import datetime as _dt, timezone as _tz
    from backend.contracts.intelligence.autonomy import (
        AutonomyPolicyConfig, AutonomyScope, EmergencyStopState,
    )
    from backend.contracts.intelligence.calibration import (
        CalibrationStatus, DriftStatus, PredictionClass, ReliabilityEstimate,
    )
    from backend.contracts.intelligence.investigation import AutonomyLevel
    from backend.contracts.tenant import TenantRef

    pc = PredictionClass(subject_type="deployment", predicate="workload_health",
                         environment="development", model_identity="scripted",
                         harness_version="h/1")
    base = {
        "scope": AutonomyScope(
            tenant=TenantRef(tenant_id="dev"), environment="development",
            service="payments", capability_ref="platform." + ROLLOUT_RESTART_OPERATION,
            operation=ROLLOUT_RESTART_OPERATION, resource_class="deployment"),
        # The DEPLOYMENT's explicit, versioned autonomy policy.
        #
        # The shipped default caps HIGH-risk actions at A2 — no autonomous action
        # at all, even with a human approving. That default is deliberate and the
        # harness proves it still holds. This deployment raises HIGH to A3, which
        # is not a weakening: A3 means every single execution needs a fresh,
        # digest-bound human approval, and gate 9 independently forces an
        # irreversible action to A3 anyway, so A4 stays unreachable either way.
        # What changes is only whether a human is ALLOWED to approve it at all.
        #
        # Changing a threshold changes policy_version, which is the whole point
        # of these being configuration rather than constants.
        "config": AutonomyPolicyConfig(
            policy_version="phase96-autonomy/1",
            max_level_high=AutonomyLevel.A3_APPROVED_ACTION),
        "stop_state": EmergencyStopState.RUNNING,
        "breaker": None,
        "reliability": ReliabilityEstimate(
            prediction_class=pc, status=CalibrationStatus.CALIBRATED,
            sample_count=20, decided_count=20, supported_count=19,
            unsupported_count=1, insufficient_count=0, conflicted_count=0,
            pending_count=0, assured_count=19, dataset_digest="d" * 64,
            policy_digest="p" * 64, confidence=None,
            generated_at=_dt.now(_tz.utc), support_rate=0.95,
            assurance_coverage=0.95),
        "drift": DriftStatus.NO_DRIFT,
        "world_fresh": True,
        "world_conflicted": False,
        "versions": {"model_identity": "scripted", "harness_version": "h/1"},
        "now": _dt.now(_tz.utc),
    }
    base.update(overrides)
    return base


def _decide(level=AutonomyLevel.A4_AUTONOMOUS, **overrides):
    from backend.intelligence.application.autonomy import AutonomyPolicy
    profile = _profile()
    return AutonomyPolicy().evaluate(
        requested_level=level, capability=profile.to_capability(),
        risk=profile.risk, **_autonomy_inputs(**overrides))


class TestAutonomyRefusesToDelegateAnIrreversibleAction:
    def test_the_SHIPPED_DEFAULT_refuses_this_action_entirely(self):
        """The strongest safety result in this phase, and it needs stating.

        `IRREVERSIBLE_WRITE` implies `RiskLevel.HIGH` by the platform's own
        deterministic rule, and the shipped `AutonomyPolicyConfig` caps HIGH at
        A2 — no autonomous action at all, *even with a human approving*. Out of
        the box, CortexPrime will not perform this action. A deployment has to
        state, in a versioned policy, that a human may approve it.
        """
        from backend.contracts.intelligence.autonomy import (
            AutonomyEligibility, AutonomyPolicyConfig,
        )
        from backend.contracts.policy import RiskLevel

        shipped = AutonomyPolicyConfig(policy_version="shipped-default")
        assert shipped.cap_for_risk(RiskLevel.HIGH) is AutonomyLevel.A2_RECOMMEND
        decision = _decide(config=shipped)
        assert decision.eligibility is AutonomyEligibility.POLICY_FORBIDDEN
        assert not decision.effective_level.permits_action()

    def test_the_risk_level_is_derived_by_the_platform_not_chosen(self):
        # IRREVERSIBLE_WRITE -> HIGH is the platform's own rule; the profile
        # agrees with it rather than asserting a level of its own choosing.
        from backend.contexts.connectivity.domain.authorization import (
            AuthorizationSnapshot,
        )
        from backend.contracts.policy import RiskLevel
        assert _profile().risk.level is RiskLevel.HIGH

    def test_a4_requested_is_never_a4_effective(self):
        from backend.contracts.intelligence.autonomy import (
            ApprovalRequirement, AutonomyEligibility,
        )
        decision = _decide()
        assert decision.requested_level is AutonomyLevel.A4_AUTONOMOUS
        assert decision.effective_level is not AutonomyLevel.A4_AUTONOMOUS
        assert decision.eligibility is AutonomyEligibility.HUMAN_APPROVAL_REQUIRED
        assert decision.approval_requirement is ApprovalRequirement.HUMAN_APPROVAL
        assert "irreversible" in decision.reason.lower()

    def test_effective_never_exceeds_allowed_never_exceeds_requested(self):
        for level in (AutonomyLevel.A2_RECOMMEND, AutonomyLevel.A3_APPROVED_ACTION,
                      AutonomyLevel.A4_AUTONOMOUS):
            decision = _decide(level)
            assert decision.effective_level.rank <= decision.allowed_level.rank
            assert decision.allowed_level.rank <= level.rank

    def test_emergency_stop_forbids_action(self):
        from backend.contracts.intelligence.autonomy import (
            AutonomyEligibility, EmergencyStopState,
        )
        decision = _decide(stop_state=EmergencyStopState.STOP_ACTIVE)
        assert decision.eligibility is AutonomyEligibility.EMERGENCY_STOPPED
        assert not decision.effective_level.permits_action()

    def test_a_tripped_breaker_forbids_action(self):
        from backend.contracts.intelligence.autonomy import (
            AutonomyEligibility, BreakerTrip,
        )
        decision = _decide(breaker=BreakerTrip(
            trigger="verification_failure", count=5, threshold=3,
            reason="five verification failures crossed the configured threshold"))
        assert decision.eligibility is AutonomyEligibility.CIRCUIT_OPEN
        assert not decision.effective_level.permits_action()

    def test_stale_or_conflicted_world_forbids_action(self):
        assert not _decide(world_fresh=False).effective_level.permits_action()
        assert not _decide(world_conflicted=True).effective_level.permits_action()

    def test_insufficient_calibration_forbids_action(self):
        from backend.contracts.intelligence.calibration import (
            CalibrationStatus, PredictionClass, ReliabilityEstimate,
        )
        pc = PredictionClass(subject_type="deployment", predicate="workload_health",
                             environment="development", model_identity="scripted",
                             harness_version="h/1")
        thin = ReliabilityEstimate(
            prediction_class=pc, status=CalibrationStatus.INSUFFICIENT_DATA,
            sample_count=1, decided_count=0, supported_count=0, unsupported_count=0,
            insufficient_count=1, conflicted_count=0, pending_count=1,
            assured_count=0, dataset_digest="d" * 64, policy_digest="p" * 64,
            confidence=None, generated_at=datetime.now(timezone.utc),
            support_rate=None, assurance_coverage=None)
        assert not _decide(reliability=thin).effective_level.permits_action()
        assert not _decide(reliability=None).effective_level.permits_action()

    def test_no_model_input_appears_anywhere_in_the_decision(self):
        blob = json.dumps(_decide().to_dict(), default=str).lower()
        assert "model_said" not in blob and "confidence" not in blob


# ---------------------------------------------------------------------------
# Approval binding
# ---------------------------------------------------------------------------

def _facts(**overrides):
    from backend.contracts.approval import ApprovalOutcome
    from backend.contexts.connectivity.application.authorization import ApprovalFacts
    base = dict(artifact_id="appr-1", outcome=ApprovalOutcome.GRANTED,
                bound_digest="d" * 64, scope_tenant_id="dev",
                operation=ROLLOUT_RESTART_OPERATION, expires_at=None)
    base.update(overrides)
    return ApprovalFacts(**base)


class TestApprovalBinding:
    def _valid(self, facts, **overrides):
        base = dict(tenant_id="dev", capability_digest="d" * 64,
                    operation=ROLLOUT_RESTART_OPERATION,
                    moment=datetime.now(timezone.utc))
        base.update(overrides)
        return facts.is_valid_for(**base)

    def test_a_matching_approval_is_valid(self):
        assert self._valid(_facts())

    def test_a_denied_approval_authorizes_nothing(self):
        from backend.contracts.approval import ApprovalOutcome
        assert not self._valid(_facts(outcome=ApprovalOutcome.DENIED))

    def test_an_expired_approval_authorizes_nothing(self):
        assert not self._valid(_facts(
            expires_at=datetime.now(timezone.utc) - timedelta(seconds=1)))

    def test_an_approval_for_another_tenant_authorizes_nothing(self):
        assert not self._valid(_facts(scope_tenant_id="other"))

    def test_an_approval_for_another_operation_authorizes_nothing(self):
        assert not self._valid(_facts(operation="kubernetes.pods.list"))

    def test_an_approval_bound_to_another_digest_authorizes_nothing(self):
        assert not self._valid(_facts(), capability_digest="e" * 64)

    def test_a_bare_name_is_not_an_authority(self):
        from backend.contracts.intelligence.investigation import (
            HumanEvent, HumanEventKind,
        )
        with pytest.raises(ContractViolation, match="never a bare name"):
            HumanEvent(kind=HumanEventKind.APPROVED, actor_ref="admin",
                       reason="looks fine")
        HumanEvent(kind=HumanEventKind.APPROVED, actor_ref="principal:sre-oncall",
                   reason="reviewed the differential and the blast radius")


# ---------------------------------------------------------------------------
# The result record
# ---------------------------------------------------------------------------

def _result(**overrides):
    base = dict(
        remediation_ref="wrem_1", investigation_ref="winv_1", tenant_id="dev",
        target=RemediationTarget(namespace=NS, workload="app"),
        capability_ref="platform." + ROLLOUT_RESTART_OPERATION,
        capability_version=1, input_digest="d" * 64, action_ref="ex_1",
        diagnosis="stale configuration", diagnosis_supported_by=("wobs_1",),
        pre_action_gate=None, autonomy_decision=None, approval_ref="appr-1",
        executed=True, execution_state="succeeded",
        rollback_available=False,
        rollback_reason="a rollout restart has no inverse",
    )
    base.update(overrides)
    return RemediationResult(**base)


class TestRemediationRecord:
    def test_execution_result_and_world_outcome_are_separate(self):
        # The whole point: the action succeeding is not the world recovering.
        document = _result(executed=True,
                           world_outcome=RemediationOutcome.NOT_RECOVERED).to_dict()
        assert document["executed"] is True
        assert document["world_outcome"] == "not_recovered"

    def test_the_four_axes_stay_distinct(self):
        document = _result(
            world_outcome=RemediationOutcome.RECOVERED,
            prediction_evaluation="falsified",
            post_assurance_verdict="insufficient_evidence").to_dict()
        assert document["diagnosis"] is not None
        assert document["prediction"]["evaluation"] == "falsified"
        assert document["world_outcome"] == "recovered"
        assert document["post_assurance_verdict"] == "insufficient_evidence"

    def test_rollback_is_classified_unavailable_with_a_reason(self):
        document = _result().to_dict()
        assert document["rollback"]["available"] is False
        assert "no inverse" in document["rollback"]["reason"]

    def test_a_refusal_states_that_the_provider_was_not_contacted(self):
        rendered = _result(executed=False, refused_at="approval",
                           refusal_reason="no approval presented").render()
        assert "REFUSED AT" in rendered
        assert "the provider was not contacted" in rendered

    def test_the_record_carries_no_numeric_confidence(self):
        blob = json.dumps(_result().to_dict(), default=str).lower()
        assert "confidence" not in blob and "%" not in blob

    def test_the_record_names_the_approval_and_the_digest_it_was_bound_to(self):
        document = _result().to_dict()
        assert document["approval_ref"] == "appr-1"
        assert document["capability"]["input_digest"] == "d" * 64


# ---------------------------------------------------------------------------
# The Intelligence Plane still cannot write
# ---------------------------------------------------------------------------

class TestIntelligenceCannotWrite:
    def test_no_intelligence_module_imports_a_connector_or_writer(self):
        import os
        import backend.intelligence as intel
        offenders = []
        for root, _dirs, files in os.walk(os.path.dirname(intel.__file__)):
            for name in files:
                if not name.endswith(".py"):
                    continue
                text = open(os.path.join(root, name), encoding="utf-8").read()
                if ("adapters.connectors" in text or "import httpx" in text
                        or "GovernedCapabilityWriter" in text
                        or "backend.connectors" in text):
                    offenders.append(name)
        assert offenders == []

    def test_the_evidence_request_still_has_no_write_field(self):
        import dataclasses
        from backend.intelligence.application.proposal import EvidenceRequest
        fields = {f.name for f in dataclasses.fields(EvidenceRequest)}
        assert fields == {"tool", "subject_ref", "predicate", "read_only"}

    def test_the_investigator_tool_registry_still_refuses_a_write(self):
        from backend.api.governed_evidence_acquisition import (
            InvestigationTool, ToolRegistry,
        )
        # The catalog handed in DOES declare the write, so the refusal cannot
        # come from the operation being absent. It has to come from the side
        # effect, which is the property this test exists to pin.
        with pytest.raises(ContractViolation, match="does not act"):
            ToolRegistry(tools=(InvestigationTool(
                key="k8s.restart", operation=ROLLOUT_RESTART_OPERATION,
                subject_kind="kubernetes:deployment:", predicate="restarted",
                describes="a write an investigation must never hold",
                project=lambda e: {}, source_ref="connector:kubernetes",
                payload_from_subject=lambda s: {}),),
                catalogs={"kubernetes": kubernetes_write_catalog()})


class TestTheTwoDoorsAreTyped:
    """A read and a write are different entrances, and each rejects the other.

    The refusal has to happen BEFORE the governed chain starts, because the
    point of the two doors is that an approval is attached to a mutation and to
    nothing else. These cases execute the refusal itself rather than reading the
    source for it — an unimported exception name is still a green source check.
    """

    @staticmethod
    def _doors():
        from backend.api.capability_execution_composition import (
            GovernedCapabilityReader, GovernedCapabilityWriter,
        )
        from backend.contexts.execution.infrastructure.adapters.connectors.kubernetes import (
            kubernetes_write_catalog, ROLLOUT_RESTART_OPERATION,
        )

        class _Def:
            def __init__(self, spec):
                self.contract = spec

        catalog = kubernetes_write_catalog()
        specs = {op: _Def(catalog.require(op)) for op in catalog.operations}
        read_op = next(o for o, d in specs.items()
                       if not d.contract.side_effect_class.mutates)
        kwargs = dict(runtime=object(), capability_definitions=specs,
                      principal=object())
        return (GovernedCapabilityReader(**kwargs), GovernedCapabilityWriter(**kwargs),
                read_op, ROLLOUT_RESTART_OPERATION)

    def test_the_read_door_refuses_the_mutation(self):
        reader, _, _, write_op = self._doors()
        with pytest.raises(ContractViolation) as excinfo:
            reader.read(object(), operation=write_op, payload={})
        assert "cannot be performed through the read path" in str(excinfo.value)

    def test_the_write_door_refuses_a_read(self):
        _, writer, read_op, _ = self._doors()
        with pytest.raises(ContractViolation) as excinfo:
            writer.write(object(), operation=read_op, payload={},
                         approval_artifact_id="approval-1")
        assert "would attach an approval to an action that changes nothing" in str(
            excinfo.value)

    def test_neither_door_runs_an_undeclared_operation(self):
        reader, writer, _, _ = self._doors()
        for door in (lambda: reader.read(object(), operation="k.nope", payload={}),
                     lambda: writer.write(object(), operation="k.nope", payload={},
                                          approval_artifact_id="approval-1")):
            with pytest.raises(ContractViolation):
                door()
