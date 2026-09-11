"""Phase 11.3 (ADR-123): detection → investigation in one process, against
fakes for the world and the governed reads. The engine, service, differential,
plan port, governed model boundary, matcher and confidence are all REAL; only
the provider-facing edges are scripted, and they are labelled so."""
from __future__ import annotations

from backend.contracts.errors import ContractViolation

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from backend.api.investigation_catalog import (
    H_CONFIG, H_DEPENDENCY, H_REGRESSION, H_RESOURCE, H_STARTUP, IncidentClass, PlanModelPort,
)
from backend.api.investigation_runtime import (
    InvestigationHandoff, InvestigationRunner, InvestigationRuntimeConfig, incident_ref_for,
)
from backend.api.observability_evidence import observability_lineage_policy
from backend.contracts.evidence import SourceStatus
from backend.contracts.tenant import TenantRef
from backend.contracts.world import ObservationSourceKind
from backend.harness.llm_boundary import GovernedModelBoundary
from backend.harness.trace import InMemoryTraceRecorder
from backend.harness.version import CURRENT_HARNESS_VERSION
from backend.intelligence.application.context import ContextAssembler
from backend.intelligence.application.investigation_service import InvestigationService
from backend.intelligence.application.model_boundary import GovernedModelProposalPort
from backend.intelligence.application.proposal import EvidenceResult, EvidenceSelectionPolicy
from backend.signal.correlation import project_candidates
from backend.signal.detection import CONDITION_CRASHLOOP, DetectionEvent
from backend.world.application import ObservationIngestion, ReadObservation

NOW = datetime(2026, 9, 10, 12, 0, tzinfo=timezone.utc)
TENANT = TenantRef(tenant_id="tenant-a")
POD = "kubernetes:pod:prod/api-7d9f8b6c5-abcde"
DEPLOY = "kubernetes:deployment:prod/api"


# -- fakes ---------------------------------------------------------------------

class MemRepo:
    def __init__(self):
        self.by_identity, self.events = {}, []

    def append(self, *, event_id, identity_digest, investigation_id, tenant_id, incident_ref, seq,
               event_kind, from_status, to_status, autonomy_level, state, payload, recorded_at):
        if identity_digest in self.by_identity:
            return False
        self.by_identity[identity_digest] = True
        self.events.append({"investigation_id": investigation_id, "tenant_id": tenant_id, "seq": seq,
                            "state": state, "event_kind": event_kind, "to_status": to_status,
                            "recorded_at": recorded_at})
        return True

    def latest_state(self, *, tenant_id, investigation_id):
        rows = [e for e in self.events if e["investigation_id"] == investigation_id and e["tenant_id"] == tenant_id]
        return max(rows, key=lambda e: e["seq"])["state"] if rows else None

    def list_active(self, *, tenant_id, limit=200):
        latest = {}
        for e in self.events:
            if e["tenant_id"] == tenant_id:
                latest[e["investigation_id"]] = e
        return tuple(e["state"] for e in latest.values()
                     if e["to_status"] not in ("completed", "failed", "abandoned"))

    def list_terminal(self, *, tenant_id, limit=200):
        latest = {}
        for e in self.events:
            if e["tenant_id"] == tenant_id:
                latest[e["investigation_id"]] = e
        return tuple(e["state"] for e in latest.values()
                     if e["to_status"] in ("completed", "failed", "abandoned"))

    def list_events(self, *, tenant_id, investigation_id, limit=200):
        return tuple(e for e in self.events if e["investigation_id"] == investigation_id)


class MemObservations:
    """The World observation ledger, in memory, with the read API the runtime uses."""

    def __init__(self):
        self.rows = {}
        self.by_id = {}

    def record(self, observation, *, identity_digest):
        if identity_digest in self.rows:
            return False
        self.rows[identity_digest] = observation
        self.by_id[observation.record_id] = observation
        return True

    def get_observation(self, *, tenant_id, observation_id):
        obs = self.by_id.get(observation_id)
        return obs if obs is not None and obs.tenant.tenant_id == tenant_id else None

    def list_recent(self, *, tenant_id, since=None, subject_prefix=None, source_ref=None, limit=200):
        return tuple(o for o in self.rows.values() if o.tenant.tenant_id == tenant_id)


class MemReasoning:
    def __init__(self):
        self.records = []
        self.identities = set()

    def record(self, *, reasoning_id, identity_digest, tenant_id, kind, subject_ref, predicate, record, refs, recorded_at):
        if identity_digest in self.identities:
            return False
        self.identities.add(identity_digest)
        self.records.append(SimpleNamespace(reasoning_id=reasoning_id, tenant_id=tenant_id, kind=kind,
                                            subject_ref=subject_ref, record=record, refs=refs,
                                            recorded_at=recorded_at))
        return True


class FakeQuery:
    def current(self, *, tenant, subject_ref, predicate, now):
        return SimpleNamespace(to_dict=lambda: {"fresh": {"state": "fresh"}})


class FakeWorldPort:
    def evidence_for(self, *, tenant, subject_ref, predicate, now):
        return {"value": None, "status": "unknown", "freshness": "unknown", "source_ref": None,
                "conflicted": False, "evidence": []}


ABSENT = object()  # the read succeeded; the instrument had no series for the subject


class ScriptedEvidence:
    """The governed read edge, scripted per (tool, predicate): records a REAL
    World observation through the real ingestion so lineage and confidence see
    a genuine ledger."""

    def __init__(self, observations, answers, source_refs):
        self._ingestion = ObservationIngestion(repository=observations)
        self._answers = answers
        self._sources = source_refs
        self.calls = []

    def acquire(self, *, tenant, request, now):
        assert request.read_only
        self.calls.append((request.tool, request.subject_ref, request.predicate))
        value = self._answers.get(request.tool)
        if value is ABSENT:
            return EvidenceResult(ok=False, absent=True, subject_ref=request.subject_ref,
                                  predicate=request.predicate,
                                  reason=f"{request.tool} succeeded but reported nothing for the subject")
        if value is None:
            return EvidenceResult(ok=False, subject_ref=request.subject_ref, predicate=request.predicate,
                                  reason=f"{request.tool} unavailable")
        obs, _ = self._ingestion.ingest(
            tenant=tenant, recorded_at=now,
            read=ReadObservation(source_kind=ObservationSourceKind.CONNECTOR,
                                 source_ref=self._sources[request.tool], subject_ref=request.subject_ref,
                                 predicate=request.predicate, value=value, status=SourceStatus.RETURNED_DATA,
                                 observed_at=now, retrieved_at=now, produced_by="test"))
        return EvidenceResult(ok=True, subject_ref=request.subject_ref, predicate=request.predicate,
                              observation_ref=obs.record_id, observed_value=value,
                              source_ref=self._sources[request.tool], execution_ref="exec-1")


class FakeRegistry:
    def __init__(self, keys):
        self._keys = tuple(sorted(keys))

    @property
    def keys(self):
        return self._keys

    def get(self, key):
        return SimpleNamespace(key=key) if key in self._keys else None


SOURCES = {"k8s.pod_state": "connector:kubernetes", "k8s.pod_termination": "connector:kubernetes",
           "k8s.pod_events": "connector:kubernetes", "k8s.pod_logs": "kubelet:container-logs",
           "k8s.rollout_history": "connector:kubernetes", "metrics.pod_memory": "prometheus:kubelet-cadvisor"}
TOOLS = tuple(SOURCES)


def _stack_factory(observations, answers, reasoning, traces):
    def compose(*, incident_class, subject_ref, window, restart_count):
        evidence = ScriptedEvidence(observations, answers, SOURCES)
        plan = PlanModelPort(incident_class=incident_class, subject_ref=subject_ref, available_tools=TOOLS)
        boundary = GovernedModelBoundary(model_port=plan, recorder=traces, harness_version=CURRENT_HARNESS_VERSION)
        return {"registry": FakeRegistry(TOOLS), "evidence_port": evidence, "observations": observations,
                "query": FakeQuery(), "beliefs": None, "lineage": observability_lineage_policy(),
                "assembler": ContextAssembler(), "policy": EvidenceSelectionPolicy(),
                "world_port": FakeWorldPort(),
                "proposal_port": GovernedModelProposalPort(boundary=boundary, provider_label="deterministic"),
                "plan": plan,
                "hybrid_port": None, "provider_label": "deterministic", "model_name": "",
                "traces": traces, "reasoning": reasoning}
    return compose


def _runtime(answers):
    repo = MemRepo()
    service = InvestigationService(repository=repo)
    observations = MemObservations()
    reasoning = MemReasoning()
    traces = InMemoryTraceRecorder()
    config = InvestigationRuntimeConfig(tenant_id="tenant-a", namespace="prod", resume_active=False)
    runner = InvestigationRunner(config=config, composer=_stack_factory(observations, answers, reasoning, traces),
                                 service=service, repository=repo, tenant=TENANT)
    runner.reasoning = reasoning
    handoff = InvestigationHandoff(config=config, observations=observations, reasoning=reasoning,
                                   service=service, repository=repo, runner=runner, tenant=TENANT)
    return SimpleNamespace(repo=repo, service=service, observations=observations, reasoning=reasoning,
                           traces=traces, runner=runner, handoff=handoff, config=config)


def _event(subject=POD, restarts=5):
    return DetectionEvent(detection_id="det_1", tenant_id="tenant-a", condition=CONDITION_CRASHLOOP,
                          subject_ref=subject, severity="high", signal="kubernetes.watch",
                          window_start=NOW - timedelta(minutes=5), window_end=NOW, evidence=("wobs-x",),
                          reason="test", correlation={"restartCount": restarts, "namespace": "prod"})


CONFIG_LOGS = {"available": True, "lineCount": 6, "errorLineCount": 3, "truncated": False, "configError": True,
               "dependencyError": False, "crashTrace": True,
               "topPatterns": [{"pattern": "FATAL missing env DATABASE_URL", "count": 3, "level": "error"}]}
EMPTY_LOGS = {"available": True, "lineCount": 0, "errorLineCount": 0, "truncated": False, "configError": False,
              "dependencyError": False, "crashTrace": False, "topPatterns": []}
NO_ROLLOUT = {"revisionCount": 1, "currentRevision": "1", "currentImage": "app:v1", "previousImage": None,
              "imageChanged": False, "latestRolloutAt": (NOW - timedelta(days=2)).isoformat(),
              "recentChange": False, "changeAfterIncident": False}


class TestRunOne:
    def test_a_config_failure_is_a_root_cause_from_two_independent_origins(self):
        rt = _runtime({
            "k8s.pod_state": {"phase": "Running", "waitingReason": "CrashLoopBackOff"},
            "k8s.pod_events": {"eventCount": 1, "reasons": {"BackOff": 5}, "probeFailure": False,
                               "imagePullFailure": False, "backoff": True, "firstWarningAt": None,
                               "lastWarningAt": None, "truncated": False},
            "k8s.pod_termination": {"exitCode": 1, "reason": "Error"},
            "k8s.pod_logs": CONFIG_LOGS,
            "k8s.rollout_history": NO_ROLLOUT,
            "metrics.pod_memory": {"limited": True, "peakRatio": 0.04, "atOrAboveLimit": False},
        })
        rt.handoff._handle(_event(), NOW)
        assert len(rt.handoff.opened) == 1
        ref, incident = rt.handoff.opened[0]
        outcome = rt.runner.run_one(ref, incident, _event())
        assert outcome.conclusion == "resolved"
        assert outcome.outcome == "ROOT_CAUSE_IDENTIFIED" and outcome.confidence == "high"
        assessment = outcome.assessment
        assert assessment["root_cause_hypothesis"] == H_CONFIG
        # the cause is NAMED by one origin (the kubelet's log); the alternatives are
        # ELIMINATED by another (the API server's termination, the ReplicaSet lineage)
        assert set(assessment["independent_origins"]) == {"kubelet"}
        assert any("independent of the supporting origin" in line for line in assessment["basis"])
        eliminated = {e["hypothesis_ref"] for e in assessment["eliminated"]}
        assert {H_RESOURCE, H_REGRESSION, H_DEPENDENCY, H_STARTUP} <= eliminated
        assert assessment["recommended_action_candidate"] and assessment["authority"] == "none"
        # every supporting/eliminating reference is a REAL observation in the ledger
        for ref_ in assessment["supporting_evidence"]:
            assert rt.observations.get_observation(tenant_id="tenant-a", observation_id=ref_) is not None
        # the assessment is durable and the cost is measured, not invented
        kinds = [r.kind for r in rt.reasoning.records]
        assert kinds.count("detection") == 1 and kinds.count("assessment") == 1
        assert assessment["cost"]["model_calls"] >= 1 and assessment["cost"]["estimated_usd"] == 0.0
        assert all(span.model_provider == "deterministic" for span in rt.traces.spans)
        assert outcome.provider == "deterministic"

    def test_silent_crash_with_no_change_is_insufficient_evidence_not_a_guess(self):
        rt = _runtime({
            "k8s.pod_state": {"phase": "Running", "waitingReason": "CrashLoopBackOff"},
            "k8s.pod_events": {"eventCount": 0, "reasons": {}, "probeFailure": False, "imagePullFailure": False,
                               "backoff": True, "firstWarningAt": None, "lastWarningAt": None, "truncated": False},
            "k8s.pod_termination": {"exitCode": 2, "reason": "Error"},
            "k8s.pod_logs": EMPTY_LOGS,
            "k8s.rollout_history": NO_ROLLOUT,
            "metrics.pod_memory": {"limited": True, "peakRatio": 0.03, "atOrAboveLimit": False},
        })
        rt.handoff._handle(_event(), NOW)
        ref, incident = rt.handoff.opened[0]
        outcome = rt.runner.run_one(ref, incident, _event())
        assert outcome.outcome == "INSUFFICIENT_EVIDENCE" and outcome.confidence == "none"
        assert outcome.assessment["root_cause"] is None
        assert set(outcome.assessment["alternatives_open"]) == {H_STARTUP, H_CONFIG, H_DEPENDENCY}
        assert outcome.assessment["next_step"]

    def test_an_instrument_with_nothing_for_the_subject_does_not_block_the_investigation(self):
        """Measured on the live cluster: a container that dies within a second
        has no cAdvisor series at all, and the memory read -- which succeeded --
        used to end the whole investigation as BLOCKED. Now the read is spent,
        the hypothesis keeps its gap, the step is labelled, and the rest of the
        evidence is still read: the silent scenario still ends INSUFFICIENT."""
        rt = _runtime({
            "k8s.pod_state": {"phase": "Running", "waitingReason": "CrashLoopBackOff"},
            "k8s.pod_events": {"eventCount": 0, "reasons": {}, "probeFailure": False, "imagePullFailure": False,
                               "backoff": True, "firstWarningAt": None, "lastWarningAt": None, "truncated": False},
            "k8s.pod_termination": {"exitCode": 3, "reason": "Error"},
            "k8s.pod_logs": EMPTY_LOGS,
            "k8s.rollout_history": ABSENT,   # the lineage read answered with nothing for this workload
            "metrics.pod_memory": {"limited": True, "peakRatio": 0.03, "atOrAboveLimit": False},
        })
        rt.handoff._handle(_event(), NOW)
        ref, incident = rt.handoff.opened[0]
        outcome = rt.runner.run_one(ref, incident, _event())
        assert outcome.outcome == "INSUFFICIENT_EVIDENCE", outcome.outcome
        assert "evidence_absent" in outcome.step_outcomes
        assert {e["hypothesis_ref"] for e in outcome.assessment["eliminated"]} == {H_RESOURCE}
        assert set(outcome.assessment["alternatives_open"]) == {H_STARTUP, H_CONFIG, H_DEPENDENCY, H_REGRESSION}

    def test_a_metadata_only_rollout_before_an_oom_is_not_blamed(self):
        rt = _runtime({
            "k8s.pod_state": {"phase": "Running", "waitingReason": "CrashLoopBackOff"},
            "k8s.pod_events": {"eventCount": 0, "reasons": {}, "probeFailure": False, "imagePullFailure": False,
                               "backoff": True, "firstWarningAt": None, "lastWarningAt": None, "truncated": False},
            "k8s.pod_termination": {"exitCode": 137, "reason": "OOMKilled"},
            "k8s.pod_logs": EMPTY_LOGS,
            "k8s.rollout_history": {**NO_ROLLOUT, "revisionCount": 2, "currentRevision": "2",
                                    "previousImage": "app:v1", "imageChanged": False,
                                    "latestRolloutAt": (NOW - timedelta(minutes=6)).isoformat(),
                                    "recentChange": True},
            "metrics.pod_memory": {"limited": True, "peakRatio": 0.99, "atOrAboveLimit": True},
        })
        rt.handoff._handle(_event(), NOW)
        ref, incident = rt.handoff.opened[0]
        outcome = rt.runner.run_one(ref, incident, _event())
        assert outcome.assessment["root_cause_hypothesis"] == H_RESOURCE
        assert H_REGRESSION in outcome.assessment["alternatives_open"]     # open, not blamed
        assert outcome.confidence in ("medium", "low") and outcome.outcome != "CONFLICTED"

    def test_an_oom_burst_the_metrics_missed_is_still_the_likely_cause_from_the_kubelet(self):
        """Measured on the live cluster: the kernel killed the container within a
        second; the scraped peak stayed under a tenth of the limit. The kubelet's
        termination is the direct evidence; the metric neither confirms nor
        refutes; the metadata-only rollout stays open; so: LIKELY_CAUSE, low,
        never the rollout, never CONFLICTED."""
        rt = _runtime({
            "k8s.pod_state": {"phase": "Running", "waitingReason": "CrashLoopBackOff"},
            "k8s.pod_events": {"eventCount": 0, "reasons": {}, "probeFailure": False, "imagePullFailure": False,
                               "backoff": True, "firstWarningAt": None, "lastWarningAt": None, "truncated": False},
            "k8s.pod_termination": {"exitCode": 137, "reason": "OOMKilled"},
            "k8s.pod_logs": EMPTY_LOGS,
            "k8s.rollout_history": {**NO_ROLLOUT, "revisionCount": 2, "currentRevision": "2",
                                    "previousImage": "app:v1", "imageChanged": False,
                                    "latestRolloutAt": (NOW - timedelta(minutes=6)).isoformat(),
                                    "recentChange": True},
            "metrics.pod_memory": {"limited": True, "peakRatio": 0.09, "atOrAboveLimit": False},
        })
        rt.handoff._handle(_event(), NOW)
        ref, incident = rt.handoff.opened[0]
        outcome = rt.runner.run_one(ref, incident, _event())
        a = outcome.assessment
        assert a["root_cause_hypothesis"] == H_RESOURCE and outcome.outcome == "LIKELY_CAUSE"
        assert outcome.confidence == "low"
        assert set(a["alternatives_open"]) == {H_REGRESSION}
        assert {e["hypothesis_ref"] for e in a["eliminated"]} == {H_STARTUP, H_CONFIG, H_DEPENDENCY}

    def test_a_bad_rollout_that_introduced_a_crash_is_one_composite_root_cause(self):
        rt = _runtime({
            "k8s.pod_state": {"phase": "Running", "waitingReason": "CrashLoopBackOff"},
            "k8s.pod_events": {"eventCount": 0, "reasons": {}, "probeFailure": False, "imagePullFailure": False,
                               "backoff": True, "firstWarningAt": None, "lastWarningAt": None, "truncated": False},
            "k8s.pod_termination": {"exitCode": 2, "reason": "Error"},
            "k8s.pod_logs": {**EMPTY_LOGS, "lineCount": 3, "errorLineCount": 1, "crashTrace": True,
                             "topPatterns": [{"pattern": "panic: runtime error: nil pointer", "count": 1, "level": "error"}]},
            "k8s.rollout_history": {**NO_ROLLOUT, "revisionCount": 2, "currentRevision": "2", "previousImage": "app:v1",
                                    "currentImage": "app:v2", "imageChanged": True, "containerSpecChanged": True,
                                    "latestRolloutAt": (NOW - timedelta(minutes=6)).isoformat(), "recentChange": True},
            "metrics.pod_memory": {"limited": True, "peakRatio": 0.05, "atOrAboveLimit": False},
        })
        rt.handoff._handle(_event(), NOW)
        ref, incident = rt.handoff.opened[0]
        outcome = rt.runner.run_one(ref, incident, _event())
        assert outcome.conclusion == "resolved" and outcome.outcome == "ROOT_CAUSE_IDENTIFIED"
        assessment = outcome.assessment
        assert assessment["root_cause_hypothesis"] == H_STARTUP
        assert "recent deployment revision" in assessment["root_cause"] and "specifically" in assessment["root_cause"]
        assert any("composite" in line for line in assessment["basis"])
        assert outcome.confidence in ("high", "medium")

    def test_a_blocked_read_is_blocked_never_a_fabricated_conclusion(self):
        rt = _runtime({"k8s.pod_state": {"phase": "Running", "waitingReason": "CrashLoopBackOff"}})
        rt.handoff._handle(_event(), NOW)
        ref, incident = rt.handoff.opened[0]
        outcome = rt.runner.run_one(ref, incident, _event())
        assert outcome.conclusion == "blocked" and outcome.outcome == "BLOCKED"
        assert outcome.assessment["root_cause"] is None


class TestHandoff:
    def test_one_investigation_per_incident_however_often_the_condition_is_offered(self):
        rt = _runtime({})
        rt.handoff._handle(_event(), NOW)
        rt.handoff._handle(_event(), NOW + timedelta(minutes=1))
        assert len(rt.handoff.opened) == 1
        assert len([r for r in rt.reasoning.records if r.kind == "detection"]) == 1

    def test_the_context_budget_is_configurable_and_unchanged_by_default(self, monkeypatch):
        monkeypatch.delenv("CORTEX_INVESTIGATION_CONTEXT_TOKENS", raising=False)
        assert InvestigationRuntimeConfig.from_env(tenant_id="tenant-a", namespace="prod").context_tokens == 4000
        monkeypatch.setenv("CORTEX_INVESTIGATION_CONTEXT_TOKENS", "1500")
        assert InvestigationRuntimeConfig.from_env(tenant_id="tenant-a", namespace="prod").context_tokens == 1500

    def test_the_model_answer_budget_is_configurable_and_unchanged_by_default(self, monkeypatch):
        from backend.api.investigation_runtime import model_port_from_config
        monkeypatch.delenv("CORTEX_INVESTIGATION_MODEL_MAX_OUTPUT_TOKENS", raising=False)
        config = InvestigationRuntimeConfig.from_env(tenant_id="tenant-a", namespace="prod")
        assert config.model_max_output_tokens == 900
        monkeypatch.setenv("CORTEX_INVESTIGATION_MODEL_MAX_OUTPUT_TOKENS", "4096")
        monkeypatch.setenv("CORTEX_INVESTIGATION_MODEL_PROVIDER", "openai-compatible")
        monkeypatch.setenv("CORTEX_INVESTIGATION_MODEL", "glm-5.2")
        config = InvestigationRuntimeConfig.from_env(tenant_id="tenant-a", namespace="prod")
        port = model_port_from_config(config)
        assert config.model_max_output_tokens == 4096 and port._max_tokens == 4096
        assert port._provider == "openai-compatible" and port._model == "glm-5.2"

    def _crash_runner(self, rt, *, investigating: bool):
        from backend.contracts.intelligence import InvestigationStatus

        rt.handoff._handle(_event(), NOW)
        ref, _incident = rt.handoff.opened[0]
        if investigating:
            inv = rt.service.reconstruct(tenant=TENANT, investigation_ref=ref)
            rt.service.transition(investigation=inv, to_status=InvestigationStatus.INVESTIGATING,
                                  cause="test", now=NOW)

        def crash(*_args, **_kwargs):
            raise ContractViolation("hypothesis_ref is required")

        rt.runner.run_one = crash
        rt.runner.start()
        import time
        deadline = time.time() + 10
        while not rt.runner.outcomes and time.time() < deadline:
            time.sleep(0.05)
        rt.runner.stop()
        assert rt.runner.outcomes and rt.runner.outcomes[0].outcome == "BLOCKED"
        return ref

    def test_a_crash_during_investigation_is_concluded_failed_in_the_ledger(self):
        """D-20: before this, a crash left the investigation ``investigating``
        forever; the product showed it running and the handoff refused to reopen it."""
        rt = _runtime({})
        ref = self._crash_runner(rt, investigating=True)
        state = rt.repo.latest_state(tenant_id="tenant-a", investigation_id=ref)
        assert state["status"] == "failed" and state["conclusion"] == "failed"
        assert rt.repo.list_active(tenant_id="tenant-a") == ()

    def test_a_crash_before_investigation_began_is_abandoned_in_the_ledger(self):
        rt = _runtime({})
        ref = self._crash_runner(rt, investigating=False)
        state = rt.repo.latest_state(tenant_id="tenant-a", investigation_id=ref)
        assert state["status"] == "abandoned"
        assert rt.repo.list_active(tenant_id="tenant-a") == ()

    def test_a_concluded_incident_is_not_reopened_inside_the_lookback(self):
        """The next detection window of the same CrashLoop is the same incident.
        Without this rule the S1 pod, still crash-looping, got a second
        investigation the moment its next detection window fired -- queued ahead
        of the incident that actually needed one (measured on the live cluster)."""
        rt = _runtime({})
        rt.handoff._handle(_event(), NOW)
        ref = rt.handoff.opened[0][0]
        outcome = rt.runner.run_one(ref, POD, _event())
        assert outcome.outcome in ("BLOCKED", "INSUFFICIENT_EVIDENCE")
        assert rt.repo.list_terminal(tenant_id="tenant-a")
        rt.runner._known.clear()  # the runner thread has let go of it
        concluded_at = datetime.now(timezone.utc)  # the runner concludes on the wall clock
        rt.handoff._handle(_event(restarts=9), concluded_at + timedelta(minutes=5))
        assert len(rt.handoff.opened) == 1, "reopened inside the lookback"
        rt.handoff._handle(_event(restarts=12), concluded_at + timedelta(seconds=rt.config.lookback_seconds + 60))
        assert len(rt.handoff.opened) == 2, "not reopened once the lookback has passed"

    def test_another_tenants_candidates_are_ignored(self):
        rt = _runtime({})
        rt.handoff.offer((), tenant_id="tenant-b", now=NOW)
        rt.handoff.offer((SimpleNamespace(tenant_id="tenant-b", subject_refs=(POD,), candidate_id="c",
                                          correlation={}),), tenant_id="tenant-b", now=NOW)
        assert rt.handoff.opened == [] and rt.reasoning.records == []

    def test_incident_reference_grammar(self):
        assert incident_ref_for(_event()) == POD
        alert = DetectionEvent(detection_id="d", tenant_id="t", condition="alertmanager.alert.firing",
                               subject_ref="alertmanager:alert:abc", severity="high", signal="am",
                               window_start=NOW, window_end=NOW, evidence=(), reason="r",
                               correlation={"namespace": "prod", "pod": "api-7d9f8b6c5-abcde"})
        assert incident_ref_for(alert) == POD
        alert2 = DetectionEvent(detection_id="d", tenant_id="t", condition="alertmanager.alert.firing",
                                subject_ref="alertmanager:alert:abc", severity="high", signal="am",
                                window_start=NOW, window_end=NOW, evidence=(), reason="r", correlation={})
        assert incident_ref_for(alert2) == "alertmanager:alert:abc"

    def test_an_unobservable_alert_subject_concludes_insufficient_evidence(self):
        rt = _runtime({})
        alert = DetectionEvent(detection_id="d", tenant_id="tenant-a", condition="alertmanager.alert.firing",
                               subject_ref="alertmanager:alert:abc", severity="high", signal="am",
                               window_start=NOW, window_end=NOW, evidence=(), reason="r", correlation={})
        rt.handoff._handle(alert, NOW)
        ref, incident = rt.handoff.opened[0]
        outcome = rt.runner.run_one(ref, incident, alert)
        assert outcome.incident_class == IncidentClass.UNMAPPED
        assert outcome.outcome == "INSUFFICIENT_EVIDENCE" and outcome.reads == 0

    def test_the_runner_thread_drains_the_queue_and_resumes_active_work(self):
        rt = _runtime({
            "k8s.pod_state": {"phase": "Running", "waitingReason": "CrashLoopBackOff"},
            "k8s.pod_termination": {"exitCode": 1, "reason": "Error"},
            "k8s.pod_logs": CONFIG_LOGS, "k8s.rollout_history": NO_ROLLOUT,
            "metrics.pod_memory": {"limited": True, "peakRatio": 0.04, "atOrAboveLimit": False},
            "k8s.pod_events": {"eventCount": 0, "reasons": {}, "probeFailure": False, "imagePullFailure": False,
                               "backoff": True, "firstWarningAt": None, "lastWarningAt": None, "truncated": False},
        })
        rt.handoff._handle(_event(), NOW)
        rt.runner.start()
        import time
        deadline = time.time() + 20
        while not rt.runner.outcomes and time.time() < deadline:
            time.sleep(0.05)
        rt.runner.stop()
        assert rt.runner.outcomes and rt.runner.outcomes[0].outcome == "ROOT_CAUSE_IDENTIFIED"
        assert rt.repo.list_active(tenant_id="tenant-a") == ()
