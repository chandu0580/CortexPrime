"""The governed remediation runtime (ADR-124), end to end over in-memory ports.

The ports are fakes; the planner, the autonomy policy, the calibration builder,
the verifier's classification and the recovery decisions are the real code.
The real-cluster harness re-proves every behaviour here against k3d, PostgreSQL
and the contained worker. What these tests pin is the ORDER: nothing executes
before a granted approval and a fresh stale check; nothing is reported resolved
that independent verification did not establish; nothing is retried.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from backend.api.remediation_planning import CapabilityFacts
from backend.api.remediation_runtime import RemediationPorts, RemediationRuntime, RemediationRuntimeConfig
from backend.contracts.approval import ApprovalOutcome
from backend.contracts.execution import SideEffectClass
from backend.contracts.policy import RiskLevel
from backend.contracts.remediation import PlanAuthority
from backend.intelligence.application.proposal import ModelProviderUnavailable, ModelSchemaRejected
from backend.intelligence.application.remediation_proposal import ProposedRemediation
from backend.world.application.reasoning import ReasoningKind, ReasoningRecord

TENANT, NS, NAME = "tenant-a", "cortex-p99b", "p114-shop"
UID = "11111111-2222-3333-4444-555555555555"
GOOD, BAD = "a" * 64, "b" * 64
INCIDENT = f"kubernetes:pod:{NS}/{NAME}-7d9c8f6b5d-abcde"
INVESTIGATION = "winv_1"


class Clock:
    def __init__(self):
        self.now = datetime(2026, 9, 11, 12, 0, tzinfo=timezone.utc)

    def __call__(self):
        self.now += timedelta(seconds=1)
        return self.now


class FakeReasoning:
    def __init__(self):
        self.rows = []

    def record(self, *, reasoning_id, identity_digest, tenant_id, kind, subject_ref, predicate, record, refs,
               recorded_at):
        if any(identity == identity_digest for identity, _ in self.rows):
            return False
        self.rows.append((identity_digest, ReasoningRecord(
            reasoning_id=reasoning_id, tenant_id=tenant_id, kind=ReasoningKind(kind), subject_ref=subject_ref,
            predicate=predicate, record=json.loads(json.dumps(record, default=str)), refs=dict(refs),
            recorded_at=recorded_at)))
        return True

    def list_for_subject(self, *, tenant_id, subject_ref):
        return tuple(r for _, r in self.rows if r.tenant_id == tenant_id and r.subject_ref == subject_ref)

    def list_by_kind(self, *, tenant_id, kind, known_at=None):
        return tuple(r for _, r in self.rows if r.tenant_id == tenant_id and r.kind.value == kind
                     and (known_at is None or r.recorded_at <= known_at))

    def stages(self, plan_id):
        return [r.record.get("stage") for _, r in self.rows
                if r.subject_ref == plan_id and r.kind is ReasoningKind.REMEDIATION_EVENT]


class World:
    """The cluster, as the reader sees it. Only the writer's effect changes it."""

    def __init__(self):
        self.template = BAD
        self.generation = 7
        self.revision = "3"
        self.crash_looping = True
        self.available = False

    def roll_back(self, *, still_crashing=False):
        self.template = GOOD
        self.generation += 1
        self.revision = "4"
        self.crash_looping = still_crashing
        self.available = not still_crashing

    def deployment(self):
        return {"name": NAME, "namespace": NS, "uid": UID, "generation": self.generation,
                "observedGeneration": self.generation, "revision": self.revision, "templateDigest": self.template,
                "replicas": 1, "updatedReplicas": 1, "availableReplicas": 1 if self.available else 0,
                "unavailableReplicas": 0 if self.available else 1,
                "availableCondition": "True" if self.available else "False",
                "revisionHistoryLimit": 10, "persistentVolumeClaims": 0, "paused": False}

    def replicasets(self):
        return [{"name": f"{NAME}-good", "revision": "2" if self.revision == "3" else "4", "ownerUid": UID,
                 "podTemplateDigest": GOOD},
                {"name": f"{NAME}-bad", "revision": "3", "ownerUid": UID, "podTemplateDigest": BAD}]

    def pods(self):
        return [{"name": f"{NAME}-bad-x1", "waitingReason": "CrashLoopBackOff" if self.crash_looping else None}]


class FakeReader:
    def __init__(self, world):
        self.world = world
        self._definitions = {"kubernetes.deployment.get": 1, "kubernetes.replicasets.list": 1,
                             "kubernetes.pods.list": 1}

    def read(self, context, *, operation, payload):
        evidence = {"kubernetes.deployment.get": self.world.deployment,
                    "kubernetes.replicasets.list": lambda: {"replicaSets": self.world.replicasets()},
                    "kubernetes.pods.list": lambda: {"pods": self.world.pods()}}[operation]()
        return SimpleNamespace(operation=operation, succeeded=True, evidence=evidence, failure_reason=None,
                               execution_id="exec-read", node_state="succeeded", status=200)


class FakeWriter:
    def __init__(self, world, mode="apply"):
        self.world = world
        self.mode = mode
        self.calls = []

    def write(self, context, *, operation, payload, approval_artifact_id=None):
        self.calls.append((operation, dict(payload), approval_artifact_id))
        if self.mode == "refuse":
            return SimpleNamespace(succeeded=False, execution_id="", node_state=None, evidence={},
                                   failure_reason="authorization refused: approval_required")
        if self.mode in ("apply", "fail_but_apply", "apply_still_crashing"):
            self.world.roll_back(still_crashing=self.mode == "apply_still_crashing")
        if self.mode in ("apply", "lie", "apply_still_crashing"):
            return SimpleNamespace(succeeded=True, execution_id=f"exec-{len(self.calls)}", node_state="succeeded",
                                   evidence={"generation": self.world.generation}, failure_reason=None)
        state = "unknown" if self.mode == "fail_but_apply" else "failed"
        reason = "the envelope did not complete" if state == "unknown" else "target_revision_unavailable: gone"
        return SimpleNamespace(succeeded=False, execution_id=f"exec-{len(self.calls)}", node_state=state,
                               evidence={}, failure_reason=reason)


class ApprovalRecord(SimpleNamespace):
    def is_expired_at(self, moment):
        return self.expires_at is not None and moment >= self.expires_at


class FakeApprovals:
    def __init__(self):
        self.rows = {}

    def request(self, *, approval_id, identity_digest, tenant_id, capability_ref, capability_digest, operation,
                authorization_operation, environment, principal_id, payload, approval_digest, requested_by,
                expires_at, requested_at, investigation_ref=None, justification=None):
        if any(r.identity_digest == identity_digest for r in self.rows.values()):
            return False
        self.rows[approval_id] = ApprovalRecord(
            approval_id=approval_id, identity_digest=identity_digest, tenant_id=tenant_id,
            capability_digest=capability_digest, operation=operation, authorization_operation=authorization_operation,
            payload=dict(payload), approval_digest=approval_digest, requested_by=requested_by, decided_by=None,
            justification=justification, outcome="pending", expires_at=expires_at, consumed_by_execution=None)
        return True

    def decide(self, *, approval_id, tenant_id, outcome, decided_by, decided_at, justification=None):
        row = self.rows.get(approval_id)
        if row is None or row.tenant_id != tenant_id or row.outcome != "pending":
            return False
        row.outcome, row.decided_by, row.justification = outcome.value, decided_by, justification
        return True

    def get(self, *, tenant_id, approval_id):
        row = self.rows.get(approval_id)
        return row if row is not None and row.tenant_id == tenant_id else None

    def get_by_identity(self, *, tenant_id, identity_digest):
        return next((r for r in self.rows.values() if r.identity_digest == identity_digest), None)

    def find(self, context, artifact_id):
        from backend.contexts.connectivity.application.authorization import ApprovalFacts

        row = self.rows.get(artifact_id)
        if row is None or row.outcome == "pending":
            return None
        return ApprovalFacts(artifact_id=row.approval_id, outcome=ApprovalOutcome(row.outcome),
                             bound_digest=row.capability_digest, scope_tenant_id=row.tenant_id,
                             bound_action_digest=row.approval_digest, operation=row.authorization_operation,
                             expires_at=row.expires_at, decided_by=row.decided_by)

    def mark_consumed(self, *, approval_id, tenant_id, execution_ref):
        row = self.rows.get(approval_id)
        if row is not None and row.consumed_by_execution is None:
            row.consumed_by_execution = execution_ref

    def only(self):
        assert len(self.rows) == 1
        return next(iter(self.rows.values()))


class FakeObserver:
    def __init__(self):
        self.last = {}
        self.count = 0

    def observe(self, *, tenant, outcome, legs, now=None, trace_ref=None):
        out = []
        for leg in legs:
            self.count += 1
            self.last[leg.predicate] = dict(leg.value)
            out.append((SimpleNamespace(record_id=f"wobs_{self.count}", subject_ref=leg.subject_ref,
                                        predicate=leg.predicate, value=dict(leg.value)), True))
        return tuple(out)


class FakeAssurance:
    def __init__(self, observer):
        self.observer = observer
        self.calls = 0

    def verify(self, *, tenant, procedure, producer_reasoning_path, verified_at):
        self.calls += 1
        observed = self.observer.last.get(procedure.predicate)
        if observed is None:
            verdict = "insufficient_evidence"
        else:
            verdict = "supported" if observed == dict(procedure.expected) else "unsupported"
        return SimpleNamespace(verdict=SimpleNamespace(value=verdict),
                               verification=SimpleNamespace(record_id=f"wverif_{self.calls}",
                                                            evidence_refs=("wobs_x",)),
                               rationale=f"stub assurance: {verdict}")


class FakeIdempotency:
    class IdempotencyConflict(Exception):
        pass

    def __init__(self):
        self.keys = {}

    def claim(self, context, *, key, execution_id, node_id=None, action_digest=None):
        if key not in self.keys:
            self.keys[key] = execution_id
            return True
        if self.keys[key] == execution_id:
            return False
        raise FakeIdempotency.IdempotencyConflict(key)

    def record_outcome(self, context, *, key, outcome):
        return None


class FakeObservations:
    def list_recent(self, *, tenant_id, since=None, subject_prefix=None, source_ref=None, limit=200):
        return (SimpleNamespace(record_id="wobs_healthy", subject_ref=f"kubernetes:pod:{NS}/{NAME}-good-p1",
                                value={"phase": "Running", "waitingReason": None}),)

    def get_observation(self, *, tenant_id, observation_id):
        return SimpleNamespace(predicate="rollout_history", value={"currentPodTemplateDigest": BAD})


class ModelPort:
    def __init__(self, *, fail=None, **overrides):
        self.fail = fail
        self.overrides = overrides
        self.calls = 0

    def propose(self, *, document, mission_id, now):
        self.calls += 1
        if self.fail == "provider":
            raise ModelProviderUnavailable("ConnectError")
        if self.fail == "schema":
            raise ModelSchemaRejected("1 validation error: evidence_refs")
        fields = dict(action="deployment.rollback", target_kind="Deployment", target_namespace=NS,
                      target_name=NAME, target_revision=None, hypothesis_ref="h-deployment-regression",
                      evidence_refs=("wobs_rollout",), expected_outcome="healthy", rollback_strategy="roll back",
                      rationale="regression", source="model", model_identity="openai-compatible:glm-5.2",
                      digest="d" * 64, prompt_tokens=1200, completion_tokens=900)
        fields.update(self.overrides)
        return ProposedRemediation(**fields)


def _assessment():
    return {"incident_ref": INCIDENT, "outcome": "ROOT_CAUSE_IDENTIFIED", "confidence": "high",
            "root_cause": "a recent deployment revision introduced the failure",
            "root_cause_hypothesis": "h-startup-failure", "supporting_evidence": ["wobs_rollout"],
            "weights": [{"observation_ref": "wobs_rollout", "hypothesis_ref": "h-deployment-regression",
                         "role": "supports"}],
            "recommended_action_candidate": "roll the deployment back"}


def _runtime(*, writer_mode="apply", model=None, compensable=False, calibrated=False, **config_overrides):
    clock = Clock()
    world = World()
    reasoning = FakeReasoning()
    reasoning.record(reasoning_id="wreason_assess", identity_digest="assess", tenant_id=TENANT, kind="assessment",
                     subject_ref=INVESTIGATION, predicate="assessment", record=_assessment(), refs={},
                     recorded_at=clock())
    observer = FakeObserver()
    settings = dict(tenant_id=TENANT, namespace=NS, cluster_ref="k3d", verification_window_seconds=1,
                    verification_poll_seconds=0.02, approval_ttl_seconds=600, compensable_autonomy=compensable,
                    model_provider="openai-compatible", model_name="glm-5.2", metric_operation=None)
    settings.update(config_overrides)
    config = RemediationRuntimeConfig(**settings)
    ports = RemediationPorts(
        tenant=SimpleNamespace(tenant_id=TENANT), reader=FakeReader(world), writer=FakeWriter(world, writer_mode),
        approvals=FakeApprovals(), reasoning=reasoning, observations=FakeObservations(), observer=observer,
        derivation=SimpleNamespace(derive=lambda **kw: None), assurance=FakeAssurance(observer),
        verifications=SimpleNamespace(list_for_subject=lambda **kw: ()), idempotency=FakeIdempotency(),
        investigations=SimpleNamespace(reconstruct=lambda **kw: SimpleNamespace(evidence_refs=("wobs_rollout",))),
        context_factory=lambda: SimpleNamespace(tenant_id=TENANT),
        approval_digest=lambda payload: "approval:" + json.dumps(dict(payload), sort_keys=True),
        capability=CapabilityFacts(capability_ref="platform.kubernetes.deployment.rollback@1",
                                   capability_digest="capdigest", operation="kubernetes.deployment.rollback",
                                   risk_floor=RiskLevel.HIGH, side_effect_class=SideEffectClass.IRREVERSIBLE_WRITE,
                                   compensation_declared=True),
        authorization_operation="invoke", proposal_port=model or ModelPort(),
        audit=SimpleNamespace(events=[], record_in_context=lambda kind, ctx, **kw: None))

    class Runtime(RemediationRuntime):
        def _reliability(self, now):
            if not calibrated:
                return super()._reliability(now)
            from tests.intelligence.test_autonomy import _rel
            return _rel(decided=10, supported=10, coverage=1.0, model=config.model_identity,
                        harness=config.harness_version)

    runtime = Runtime(config=config, ports=ports, clock=clock, sleep=lambda s: time.sleep(0.02))
    return SimpleNamespace(runtime=runtime, world=world, ports=ports, reasoning=reasoning, config=config)


def _plan_and_approve(rt, *, decision="granted", decider="human:approver"):
    result = rt.runtime.handle_investigation(INVESTIGATION)
    assert result["result"] == "awaiting_approval", result
    approval = rt.ports.approvals.only()
    assert approval.requested_by == "platform:remediation-runtime" and rt.ports.writer.calls == []
    rt.ports.approvals.decide(approval_id=approval.approval_id, tenant_id=TENANT,
                              outcome=ApprovalOutcome(decision), decided_by=decider, decided_at=rt.runtime._clock())
    return result, approval


class TestHumanApprovedRemediation:
    def test_nothing_executes_before_a_human_approves(self):
        rt = _runtime()
        result = rt.runtime.handle_investigation(INVESTIGATION)
        assert result["result"] == "awaiting_approval"
        assert rt.ports.writer.calls == [] and rt.runtime.process_pending() == []

    def test_an_approved_rollback_executes_once_and_is_independently_verified(self):
        rt = _runtime()
        result, approval = _plan_and_approve(rt)
        handled = rt.runtime.process_pending()
        assert handled[0]["result"] == "resolved"
        assert len(rt.ports.writer.calls) == 1
        operation, payload, approval_id = rt.ports.writer.calls[0]
        assert approval_id == approval.approval_id and payload == approval.payload
        assert rt.reasoning.stages(result["plan_id"]) == [
            "planned", "autonomy_decided", "approval_requested", "approval_granted", "executing", "executed",
            "verified", "learned", "closed"]
        assert approval.consumed_by_execution == "exec-1"
        predictions = rt.reasoning.list_by_kind(tenant_id=TENANT, kind="prediction")
        evaluations = rt.reasoning.list_by_kind(tenant_id=TENANT, kind="prediction_evaluation")
        assert len(predictions) == 1 and len(evaluations) == 1 and evaluations[0].record["matched"] is True

    def test_the_approval_preview_names_what_why_target_risk_blast_evidence_expected_rollback_verification_digest(self):
        rt = _runtime()
        rt.runtime.handle_investigation(INVESTIGATION)
        preview = rt.ports.approvals.only().justification
        for heading in ("WHAT:", "WHY:", "TARGET:", "RISK:", "BLAST RADIUS:", "EVIDENCE:", "EXPECTED:",
                        "ROLLBACK:", "VERIFICATION:", "ACTION DIGEST:"):
            assert heading in preview

    def test_a_human_rejection_executes_nothing_and_is_recorded_as_rejection(self):
        rt = _runtime()
        result, _ = _plan_and_approve(rt, decision="denied")
        rt.runtime.process_pending()
        assert rt.ports.writer.calls == []
        stages = rt.reasoning.stages(result["plan_id"])
        assert "approval_denied" in stages and stages[-1] == "closed"
        learned = [r.record for _, r in rt.reasoning.rows if r.record.get("stage") == "learned"]
        assert "human_rejection" in learned[-1]["category"] and learned[-1]["outcome"] == "not_executed"

    def test_an_unanswered_approval_expires_and_executes_nothing(self):
        rt = _runtime(approval_ttl_seconds=1)
        result = rt.runtime.handle_investigation(INVESTIGATION)
        rt.runtime._clock.now += timedelta(seconds=30)
        rt.runtime.process_pending()
        assert rt.ports.writer.calls == [] and "approval_expired" in rt.reasoning.stages(result["plan_id"])


class TestStalePlansAreNeverExecuted:
    def test_target_drift_after_approval_is_refused(self):
        rt = _runtime()
        result, _ = _plan_and_approve(rt)
        rt.world.generation += 1          # an operator edited the Deployment
        handled = rt.runtime.process_pending()
        assert handled[0]["result"] == "stale" and rt.ports.writer.calls == []
        assert any("target drift" in r for r in handled[0]["reasons"])

    def test_a_policy_change_after_approval_forces_a_new_plan(self):
        rt = _runtime()
        result, _ = _plan_and_approve(rt)
        rt.runtime._config = RemediationRuntimeConfig(**{**rt.config.__dict__, "autonomy_policy_version": "phase114-autonomy/2"})
        handled = rt.runtime.process_pending()
        assert handled[0]["result"] == "stale" and rt.ports.writer.calls == []
        assert any("policy changed" in r for r in handled[0]["reasons"])

    def test_a_withdrawn_approval_makes_the_plan_stale(self):
        rt = _runtime()
        result, approval = _plan_and_approve(rt)
        plan = rt.runtime._pending[result["plan_id"]][0]
        approval.outcome = "withdrawn"
        outcome = rt.runtime.execute_plan(plan, approval_id=approval.approval_id, authority_kind="human_approved")
        assert outcome["result"] == "stale" and rt.ports.writer.calls == []


class TestDuplicatesAndConcurrencyAreFenced:
    def test_the_same_plan_executed_twice_mutates_once(self):
        rt = _runtime()
        result, approval = _plan_and_approve(rt)
        plan = rt.runtime._pending[result["plan_id"]][0]
        first = rt.runtime.execute_plan(plan, approval_id=approval.approval_id, authority_kind="human_approved")
        second = rt.runtime.execute_plan(plan, approval_id=approval.approval_id, authority_kind="human_approved")
        assert first["result"] == "resolved" and second["result"] == "duplicate_suppressed"
        assert len(rt.ports.writer.calls) == 1

    def test_a_second_plan_for_the_same_target_generation_is_fenced(self):
        rt = _runtime()
        result, approval = _plan_and_approve(rt)
        plan = rt.runtime._pending[result["plan_id"]][0]
        import dataclasses
        rival = dataclasses.replace(plan, plan_id="rplan_rival")
        target_key_holder = rt.runtime.execute_plan(rival, approval_id=approval.approval_id,
                                                    authority_kind="human_approved")
        assert target_key_holder["result"] == "stale" or len(rt.ports.writer.calls) <= 1
        rt2 = _runtime(writer_mode="lie")
        result2, approval2 = _plan_and_approve(rt2)
        plan2 = rt2.runtime._pending[result2["plan_id"]][0]
        rival2 = dataclasses.replace(plan2, plan_id="rplan_rival")
        rt2.runtime.execute_plan(plan2, approval_id=approval2.approval_id, authority_kind="human_approved")
        fenced = rt2.runtime.execute_plan(rival2, approval_id=approval2.approval_id, authority_kind="human_approved")
        assert fenced["result"] == "fenced" and len(rt2.ports.writer.calls) == 1


class TestTheExecutorIsNotBelieved:
    def test_a_false_success_is_caught_by_the_verifier(self):
        rt = _runtime(writer_mode="lie")
        result, _ = _plan_and_approve(rt)
        handled = rt.runtime.process_pending()
        assert handled[0]["result"] == "verification_failed"
        stages = rt.reasoning.stages(result["plan_id"])
        assert "verification_failed" in stages and "discrepancy" in stages and "escalated" in stages
        assert "resolved" not in json.dumps(handled[0]["verification"]["classification"]).lower()
        discrepancy = next(r.record for _, r in rt.reasoning.rows if r.record.get("stage") == "discrepancy")
        assert discrepancy["discrepancy"].startswith("false success")

    def test_a_false_failure_is_verified_independently(self):
        rt = _runtime(writer_mode="fail_but_apply")
        result, _ = _plan_and_approve(rt)
        handled = rt.runtime.process_pending()
        assert handled[0]["result"] == "resolved"
        discrepancy = next(r.record for _, r in rt.reasoning.rows if r.record.get("stage") == "discrepancy")
        assert discrepancy["discrepancy"].startswith("false failure")

    def test_a_remediation_that_runs_but_does_not_resolve_is_escalated_not_retried(self):
        rt = _runtime(writer_mode="apply_still_crashing")
        result, _ = _plan_and_approve(rt)
        handled = rt.runtime.process_pending()
        assert handled[0]["result"] == "verification_failed" and handled[0]["recovery"] == "wait_for_human"
        assert len(rt.ports.writer.calls) == 1
        learned = [r.record for _, r in rt.reasoning.rows if r.record.get("stage") == "learned"][-1]
        assert "false_diagnosis" in learned["category"]

    def test_an_honest_failure_is_reported_as_execution_failed(self):
        rt = _runtime(writer_mode="fail")
        result, _ = _plan_and_approve(rt)
        handled = rt.runtime.process_pending()
        assert handled[0]["result"] == "execution_failed" and len(rt.ports.writer.calls) == 1
        stages = rt.reasoning.stages(result["plan_id"])
        # The verifier CONFIRMED the failure (the world did not change); that is
        # not a verification failure of a remediation that ran, and it must not
        # count toward the verification breaker.
        assert "no_effect_confirmed" in stages and "verification_failed" not in stages
        assert rt.runtime._breaker(rt.runtime._clock()) is None

    def test_a_governed_refusal_is_not_verified_and_not_retried(self):
        rt = _runtime(writer_mode="refuse")
        result, _ = _plan_and_approve(rt)
        handled = rt.runtime.process_pending()
        assert handled[0]["result"] == "refused" and rt.ports.assurance.calls == 0

    def test_the_incident_action_budget_stops_repeat_attempts(self):
        rt = _runtime(max_executions_per_incident=0)
        result, _ = _plan_and_approve(rt)
        handled = rt.runtime.process_pending()
        assert handled[0]["result"] == "escalated_budget" and rt.ports.writer.calls == []


class TestTheModelHasNoAuthority:
    def test_an_unavailable_model_yields_a_recommendation_and_no_approval_request(self):
        rt = _runtime(model=ModelPort(fail="provider"))
        result = rt.runtime.handle_investigation(INVESTIGATION)
        assert result["result"] == "recommendation_only"
        assert rt.ports.approvals.rows == {} and rt.ports.writer.calls == []

    def test_malformed_model_output_is_a_rejected_proposal(self):
        rt = _runtime(model=ModelPort(fail="schema"))
        result = rt.runtime.handle_investigation(INVESTIGATION)
        assert result["result"] == "proposal_rejected" and rt.ports.approvals.rows == {}

    @pytest.mark.parametrize("action", ["deployment.delete", "shell.exec", "cluster-admin", "http.request"])
    def test_a_model_requesting_a_dangerous_tool_is_prohibited(self, action):
        rt = _runtime(model=ModelPort(action=action))
        result = rt.runtime.handle_investigation(INVESTIGATION)
        assert result["result"] == "prohibited" and rt.ports.approvals.rows == {} and rt.ports.writer.calls == []

    def test_a_model_naming_another_workload_is_rejected(self):
        rt = _runtime(model=ModelPort(target_name="billing-api"))
        result = rt.runtime.handle_investigation(INVESTIGATION)
        assert result["result"] == "proposal_rejected" and rt.ports.writer.calls == []


class TestEarnedAutonomy:
    def test_without_calibration_even_the_compensable_policy_asks_a_human(self):
        rt = _runtime(compensable=True, calibrated=False)
        result = rt.runtime.handle_investigation(INVESTIGATION)
        assert result["result"] == "awaiting_approval" and rt.ports.writer.calls == []

    def test_with_earned_reliability_the_compensable_rollback_is_delegated_and_verified(self):
        rt = _runtime(compensable=True, calibrated=True)
        result = rt.runtime.handle_investigation(INVESTIGATION)
        assert result["result"] == "resolved", result
        approval = rt.ports.approvals.only()
        assert approval.outcome == "granted" and approval.decided_by.startswith("policy:autonomy/")
        assert len(rt.ports.writer.calls) == 1
        plan = [r for _, r in rt.reasoning.rows if r.kind is ReasoningKind.REMEDIATION_PLAN][0].record
        assert plan["authority"] == PlanAuthority.AUTONOMOUS.value and plan["reversibility"] == "compensable"

    def test_a_verification_failure_trips_the_breaker_and_autonomy_falls_back_to_a_human(self):
        rt = _runtime(compensable=True, calibrated=True, writer_mode="lie")
        first = rt.runtime.handle_investigation(INVESTIGATION)
        assert first["result"] == "verification_failed"
        rt.world.template, rt.world.generation = BAD, rt.world.generation + 1
        rt.reasoning.record(reasoning_id="wreason_assess2", identity_digest="assess2", tenant_id=TENANT,
                            kind="assessment", subject_ref="winv_2", predicate="assessment",
                            record=_assessment(), refs={}, recorded_at=rt.runtime._clock())
        second = rt.runtime.handle_investigation("winv_2")
        assert second["result"] == "awaiting_approval"


class TestCrashReconciliation:
    def test_a_plan_left_executing_is_reconciled_by_verification_never_re_executed(self):
        rt = _runtime()
        result, approval = _plan_and_approve(rt)
        plan = rt.runtime._pending.pop(result["plan_id"])[0]
        rt.runtime._event(plan.plan_id, __import__("backend.contracts.remediation", fromlist=["x"]).RemediationStage.EXECUTING,
                          investigation_ref=plan.investigation_ref, incident_ref=plan.incident_ref)
        rt.world.roll_back()               # the write landed before the crash
        rt.runtime.resume()
        stages = rt.reasoning.stages(plan.plan_id)
        assert "execution_unknown" in stages and "verified" in stages and stages[-1] == "closed"
        assert rt.ports.writer.calls == []
