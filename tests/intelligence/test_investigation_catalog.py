"""Phase 11.3 (ADR-123): the investigation catalog -- incident classes, tools,
projections, the deterministic plan, and the plan-augmented model port."""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone

import pytest

from backend.api.investigation_catalog import (
    H_CONFIG, H_DEPENDENCY, H_REGRESSION, H_RESOURCE, H_STARTUP, H_UNMAPPED,
    IncidentClass, InvestigationWindow, PlanAugmentedModelPort, PlanModelPort, ToolComposition,
    classify_incident, deployment_subject, investigation_tools, planned_tests, seed_hypotheses,
    window_for, workload_of_subject,
)
from backend.api.investigation_catalog import (
    _events, _log_patterns, _memory_ratio, _restart_onset, _rollout_history,
)
from backend.harness.llm_boundary import ModelInvocation
from backend.intelligence.application.matching import matches

NOW = datetime(2026, 9, 10, 12, 0, tzinfo=timezone.utc)
POD = "kubernetes:pod:prod/api-7d9f8b6c5-abcde"


class TestClassesAndSubjects:
    def test_workload_and_deployment_are_inferred_and_labelled_as_such(self):
        assert workload_of_subject(POD) == "api"
        assert deployment_subject(POD) == "kubernetes:deployment:prod/api"
        assert workload_of_subject("alertmanager:alert:x") is None

    def test_classification_is_deterministic(self):
        assert classify_incident(detection_kind="kubernetes.pod.crashloop", subject_ref=POD) == IncidentClass.CRASHLOOP
        assert classify_incident(detection_kind="alertmanager.alert.firing",
                                 subject_ref="kubernetes:deployment:prod/api") == IncidentClass.ALERT
        assert classify_incident(detection_kind="alertmanager.alert.firing",
                                 subject_ref="alertmanager:alert:abc") == IncidentClass.UNMAPPED

    def test_seeded_hypotheses_are_open_with_gaps_and_the_regression_names_the_deployment(self):
        seeds = seed_hypotheses(incident_class=IncidentClass.CRASHLOOP, subject_ref=POD)
        assert {h.hypothesis_ref for h in seeds} == {H_STARTUP, H_CONFIG, H_DEPENDENCY, H_RESOURCE, H_REGRESSION}
        assert all(h.status.value == "open" and h.missing_evidence for h in seeds)
        regression = next(h for h in seeds if h.hypothesis_ref == H_REGRESSION)
        assert regression.subject_ref == "kubernetes:deployment:prod/api"
        unmapped = seed_hypotheses(incident_class=IncidentClass.UNMAPPED, subject_ref="alertmanager:alert:x")
        assert [h.hypothesis_ref for h in unmapped] == [H_UNMAPPED]


class TestWindow:
    def test_windows_are_explicit_and_stated(self):
        window = window_for(first_observed_at=NOW - timedelta(minutes=10), now=NOW)
        assert window.change_start < window.incident_start < window.change_end
        document = window.to_dict()
        assert document["assumptions"] and document["change_window"]

    def test_a_future_first_observation_is_clamped(self):
        window = window_for(first_observed_at=NOW + timedelta(minutes=10), now=NOW)
        assert window.incident_start == NOW


class TestProjections:
    def test_log_patterns_classify_and_keep_bounded_text(self):
        value = _log_patterns({"lineCount": 12, "errorLineCount": 3, "patterns": [
            {"pattern": "FATAL missing env DATABASE_URL", "count": 3, "level": "error"},
            {"pattern": "starting v#", "count": 1, "level": "info"}]})
        assert value["configError"] is True and value["dependencyError"] is False
        assert value["lineCount"] == 12 and len(value["topPatterns"]) == 2

    def test_the_plan_reads_a_kernel_kill_against_the_application_exit_hypotheses(self):
        """A below-limit sample refutes nothing (a burst between samples is
        invisible); a kernel OOM kill refutes 'it failed at startup on X'; an
        ordinary exit supports none of them (S3 stays open)."""
        plan = planned_tests(incident_class=IncidentClass.CRASHLOOP,
                             available_tools=("k8s.pod_termination", "metrics.pod_memory", "k8s.pod_logs",
                                              "k8s.pod_logs_previous", "k8s.rollout_history"))
        memory = [t for t in plan if t.tool == "metrics.pod_memory"]
        assert memory and all(t.contradicts_value is None for t in memory)
        kills = {t.hypothesis: t for t in plan if t.tool == "k8s.pod_termination" and t.supports_value is None}
        assert set(kills) == {H_STARTUP, H_CONFIG, H_DEPENDENCY}
        oom = {"exitCode": 137, "reason": "OOMKilled"}
        plain = {"exitCode": 3, "reason": "Error"}
        assert all(matches(t.contradicts_value, oom) for t in kills.values())
        assert not any(matches(t.contradicts_value, plain) for t in kills.values())

    def test_a_runtime_panic_is_a_crash_not_a_configuration_error(self):
        """A Go nil-pointer panic says 'invalid memory address'. Measured on the
        live cluster: that 'invalid' made the S2 bad revision a configuration
        error. Runtime-fault vocabulary is a crash signature, never a setting."""
        value = _log_patterns({"lineCount": 3, "errorLineCount": 1, "patterns": [
            {"pattern": "panic: runtime error: invalid memory address or nil pointer dereference",
             "count": 1, "level": "error"},
            {"pattern": "goroutine # [running]: main.main() /app/main.go:#", "count": 1, "level": "info"}]})
        assert value["crashTrace"] is True and value["configError"] is False
        # a genuine configuration message still classifies as one
        value = _log_patterns({"lineCount": 1, "errorLineCount": 1, "patterns": [
            {"pattern": "fatal: invalid configuration: DATABASE_URL is not a url", "count": 1, "level": "error"}]})
        assert value["configError"] is True and value["crashTrace"] is True

    def test_empty_logs_are_a_value_with_nothing_classified(self):
        value = _log_patterns({"lineCount": 0, "errorLineCount": 0, "patterns": []})
        assert value == {"available": True, "lineCount": 0, "errorLineCount": 0, "truncated": False,
                         "configError": False, "dependencyError": False, "crashTrace": False, "topPatterns": []}
        assert _log_patterns({}) is None

    def test_an_unavailable_log_is_declared_unavailable_and_decides_nothing(self):
        value = _log_patterns({"lineCount": 0, "errorLineCount": 0, "logUnavailable": True, "patterns": []})
        assert value["available"] is False
        assert not matches({"available": True, "configError": False, "dependencyError": True}, value)
        assert not matches({"available": True, "configError": True}, value)

    def test_events_classify_backoff_probe_and_image(self):
        value = _events({"eventCount": 3, "events": [
            {"reason": "BackOff", "type": "Warning", "message": "Back-off restarting failed container",
             "count": 5, "firstTimestamp": "2026-09-10T11:50:00Z", "lastTimestamp": "2026-09-10T11:59:00Z"},
            {"reason": "Unhealthy", "type": "Warning", "message": "Readiness probe failed: 503", "count": 2,
             "firstTimestamp": "2026-09-10T11:55:00Z"},
            {"reason": "Pulled", "type": "Normal", "message": "Container image pulled"}]})
        assert value["backoff"] and value["probeFailure"] and not value["imagePullFailure"]
        assert value["firstWarningAt"] == "2026-09-10T11:50:00Z"

    def test_rollout_history_places_the_change_in_the_window(self):
        window = InvestigationWindow(incident_start=NOW - timedelta(minutes=5), now=NOW)
        project = _rollout_history("api", window)
        value = project({"replicaSets": [
            {"name": "api-1", "revision": "1", "image": "app:v1", "ownerName": "api",
             "templateDigest": "aaaa", "creationTimestamp": (NOW - timedelta(hours=3)).isoformat()},
            {"name": "api-2", "revision": "2", "image": "app:v2", "ownerName": "api",
             "templateDigest": "bbbb", "creationTimestamp": (NOW - timedelta(minutes=8)).isoformat()},
            {"name": "other-1", "revision": "1", "image": "x", "ownerName": "other",
             "creationTimestamp": (NOW - timedelta(minutes=1)).isoformat()}]})
        assert value["currentRevision"] == "2" and value["imageChanged"] and value["recentChange"]
        assert value["previousImage"] == "app:v1" and value["revisionCount"] == 2
        assert value["containerSpecChanged"] is True
        assert matches({"recentChange": True, "containerSpecChanged": True}, value)

    def test_a_metadata_only_rollout_is_recent_but_changed_nothing_the_process_runs(self):
        window = InvestigationWindow(incident_start=NOW - timedelta(minutes=5), now=NOW)
        value = _rollout_history("api", window)({"replicaSets": [
            {"name": "api-1", "revision": "1", "image": "app:v1", "ownerName": "api",
             "templateDigest": "same", "creationTimestamp": (NOW - timedelta(hours=3)).isoformat()},
            {"name": "api-2", "revision": "2", "image": "app:v1", "ownerName": "api",
             "templateDigest": "same", "creationTimestamp": (NOW - timedelta(minutes=8)).isoformat()}]})
        assert value["recentChange"] and not value["containerSpecChanged"] and not value["imageChanged"]
        assert not matches({"recentChange": True, "containerSpecChanged": True}, value)
        assert not matches({"recentChange": False}, value)   # neither supported nor refuted: stays OPEN

    def test_a_rollout_after_the_incident_cannot_be_recent(self):
        window = InvestigationWindow(incident_start=NOW - timedelta(minutes=30), now=NOW)
        value = _rollout_history("api", window)({"replicaSets": [
            {"name": "api-2", "revision": "2", "image": "app:v2", "ownerName": "api",
             "creationTimestamp": (NOW - timedelta(minutes=1)).isoformat()}]})
        assert value["recentChange"] is False and value["changeAfterIncident"] is True

    def test_memory_ratio_reads_an_unlimited_container_honestly(self):
        assert _memory_ratio({"series": [{"value": "0.97"}]}) == {"limited": True, "peakRatio": 0.97, "atOrAboveLimit": True}
        # the operation is namespace-wide; the projection keeps ONLY the subject's series
        namespace_wide = {"series": [{"pod": "payments-api-1", "value": "0.97"}, {"pod": "p113-oom-1", "value": "0.09"}]}
        assert _memory_ratio(namespace_wide, pod="p113-oom-1")["peakRatio"] == 0.09
        assert _memory_ratio(namespace_wide, pod="absent-pod") is None
        onset = {"series": [{"pod": "a", "first": "0", "last": "5", "firstTimestamp": 1.0},
                            {"pod": "b", "first": "2", "last": "2", "firstTimestamp": 2.0}]}
        assert _restart_onset(onset, pod="b") == {"restartsIncreased": False, "firstCount": 2, "lastCount": 2,
                                                  "windowStartedAt": 2.0}
        assert _restart_onset(onset, pod="a")["restartsIncreased"] is True
        assert _memory_ratio({"series": [{"value": "+Inf"}]}) == {"limited": False, "peakRatio": None, "atOrAboveLimit": False}
        assert _memory_ratio({"series": []}) is None


class TestToolsAndPlan:
    def test_tools_are_bound_to_the_composition_and_carry_platform_computed_parameters(self):
        window = InvestigationWindow(incident_start=NOW - timedelta(minutes=5), now=NOW)
        tools = investigation_tools(ToolComposition(subject_ref=POD, window=window, restart_count=3, prometheus=True))
        keys = {t.key for t in tools}
        assert {"k8s.pod_logs", "k8s.pod_logs_previous", "k8s.pod_events", "k8s.rollout_history",
                "metrics.pod_memory", "metrics.restart_timeline"} <= keys
        logs = next(t for t in tools if t.key == "k8s.pod_logs")
        assert logs.payload_from_subject(POD) == {"namespace": "prod", "name": "api-7d9f8b6c5-abcde",
                                                  "tailLines": 200, "previous": False}
        previous = next(t for t in tools if t.key == "k8s.pod_logs_previous")
        assert previous.payload_from_subject(POD)["previous"] is True
        events = next(t for t in tools if t.key == "k8s.pod_events")
        assert events.payload_from_subject(POD)["fieldSelector"] == "involvedObject.name=api-7d9f8b6c5-abcde"
        timeline = next(t for t in tools if t.key == "metrics.restart_timeline")
        payload = timeline.payload_from_subject(POD)
        assert payload["end"] == int(NOW.timestamp()) and payload["end"] - payload["start"] <= 3600

    def test_without_prometheus_no_metrics_tool_is_offered(self):
        window = InvestigationWindow(incident_start=NOW, now=NOW)
        tools = investigation_tools(ToolComposition(subject_ref=POD, window=window))
        assert not any(t.key.startswith("metrics.") for t in tools)

    def test_the_plan_only_names_exposed_tools_and_class_hypotheses(self):
        plan = planned_tests(incident_class=IncidentClass.CRASHLOOP,
                         available_tools=("k8s.pod_logs", "k8s.pod_termination"))
        assert {t.tool for t in plan} == {"k8s.pod_logs", "k8s.pod_termination"}
        assert all(t.supports_value.get("available") is True for t in plan if t.tool == "k8s.pod_logs")
        assert all(t.supports_value is not None or t.contradicts_value is not None for t in plan)

    def test_the_plan_port_emits_schema_shaped_tests_and_skips_refuted_and_run(self):
        port = PlanModelPort(incident_class=IncidentClass.CRASHLOOP, subject_ref=POD,
                             available_tools=("k8s.pod_logs", "k8s.pod_termination", "k8s.rollout_history"))
        prompt = json.dumps({"sections": [
            {"section_type": "hypotheses", "included": True,
             "content": [{"hypothesis_ref": H_RESOURCE, "status": "refuted"}]},
            {"section_type": "prior_tests", "included": True, "content": []}]})
        document = port.proposal_document(prompt)
        tests = document["tests"]
        assert tests and all(t["discriminates"] != H_RESOURCE for t in tests)
        regression = next(t for t in tests if t["discriminates"] == H_REGRESSION)
        assert regression["subject_ref"] == "kubernetes:deployment:prod/api"
        invocation = asyncio.run(port.generate(system_prompt="s", prompt=prompt))
        assert invocation.provider == "deterministic" and json.loads(invocation.content)["tests"]


    def test_the_plan_port_offers_the_decisive_stage_first(self):
        """Every hypothesis's primary discriminator before any secondary test.
        Measured: without this the silent scenario spent its whole step budget
        on previous-instance logs and kernel-kill checks and never read the
        termination that eliminates resource exhaustion."""
        from backend.intelligence.application.proposal import test_identity
        tools = ("k8s.pod_logs", "k8s.pod_logs_previous", "k8s.pod_termination", "k8s.rollout_history",
                 "metrics.pod_memory")
        port = PlanModelPort(incident_class=IncidentClass.CRASHLOOP, subject_ref=POD, available_tools=tools)
        empty = json.dumps({"sections": [{"section_type": "prior_tests", "included": True, "content": []}]})
        first = port.proposal_document(empty)["tests"]
        assert {t["discriminates"] for t in first} == {H_STARTUP, H_CONFIG, H_DEPENDENCY, H_RESOURCE, H_REGRESSION}
        assert {t["tool"] for t in first} == {"k8s.pod_logs", "k8s.pod_termination", "k8s.rollout_history"}
        ran = [f"wtest-{test_identity(discriminates=t['discriminates'], tool=t['tool'], subject_ref=t['subject_ref'], predicate=t['predicate'])}"
               for t in first]
        after = json.dumps({"sections": [{"section_type": "prior_tests", "included": True, "content": ran}]})
        second = port.proposal_document(after)["tests"]
        assert second and {t["tool"] for t in second} == {"k8s.pod_logs_previous", "metrics.pod_memory"}
        assert not any(t["tool"] == "k8s.pod_termination" and t["supports_value"] is None for t in second), \
            "kernel-kill contradictions are a later stage"


    def test_the_plan_port_remembers_what_ran_when_the_prompt_dropped_the_section(self):
        """Measured: the assembler excluded ``prior_tests`` ("context token
        budget exceeded") on a real context, and the port then offered stage 0
        forever. The runner now tells the port what the ledger holds."""
        from backend.intelligence.application.proposal import test_identity
        tools = ("k8s.pod_logs", "k8s.pod_logs_previous", "k8s.pod_termination", "k8s.rollout_history")
        port = PlanModelPort(incident_class=IncidentClass.CRASHLOOP, subject_ref=POD, available_tools=tools)
        dropped = json.dumps({"sections": [{"section_type": "prior_tests", "included": False, "content": [],
                                            "exclusion_reason": "context token budget exceeded"}]})
        first = port.proposal_document(dropped)["tests"]
        assert {t["tool"] for t in first} == {"k8s.pod_logs", "k8s.pod_termination", "k8s.rollout_history"}
        port.note_prior_tests([f"wtest-{test_identity(discriminates=t['discriminates'], tool=t['tool'], subject_ref=t['subject_ref'], predicate=t['predicate'])}"
                               for t in first])
        second = port.proposal_document(dropped)["tests"]
        assert second and {t["tool"] for t in second} == {"k8s.pod_logs_previous"}


class _Model:
    def __init__(self, content=None, error=None, delay=0.0):
        self.content, self.error, self.delay = content, error, delay
        self.calls = 0

    async def generate(self, *, system_prompt, prompt):
        self.calls += 1
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.error:
            raise self.error
        return ModelInvocation(content=self.content, provider="ollama", model="llama3.2", latency_ms=5.0,
                               usage=None)


class TestPlanAugmentedPort:
    def _plan(self):
        return PlanModelPort(incident_class=IncidentClass.CRASHLOOP, subject_ref=POD,
                             available_tools=("k8s.pod_logs", "k8s.pod_termination"))

    def test_model_output_is_merged_with_the_plan_and_the_provider_is_the_models(self):
        model = _Model(content=json.dumps({"interpretation": "looks like config",
                                           "hypotheses": [{"ref": "h-x", "proposition": "p", "subject_ref": POD}],
                                           "tests": [{"discriminates": "h-x", "tool": "kubectl", "subject_ref": POD,
                                                      "predicate": "p", "evidence_expected": "e",
                                                      "supports_if": "s", "contradicts_if": "c",
                                                      "residual_uncertainty": "r", "supports_value": 1}]}))
        port = PlanAugmentedModelPort(model_port=model, plan=self._plan(), timeout_seconds=5)
        invocation = asyncio.run(port.generate(system_prompt="s", prompt="{}"))
        document = json.loads(invocation.content)
        assert invocation.provider == "ollama" and invocation.config["plan_augmented"] is True
        assert document["interpretation"] == "looks like config"
        assert any(t["tool"] == "kubectl" for t in document["tests"])       # the model's (platform will refuse it later)
        assert any(t["tool"] == "k8s.pod_logs" for t in document["tests"])  # the plan's
        assert "success" not in document and "verified" not in document

    def test_a_model_failure_falls_back_to_the_plan_and_says_so(self):
        port = PlanAugmentedModelPort(model_port=_Model(error=RuntimeError("provider down")), plan=self._plan())
        invocation = asyncio.run(port.generate(system_prompt="s", prompt="{}"))
        assert invocation.provider == "deterministic" and "model unavailable" in invocation.config["fallback_reason"]
        assert port.model_failures and json.loads(invocation.content)["tests"]

    def test_a_model_timeout_falls_back_to_the_plan(self):
        port = PlanAugmentedModelPort(model_port=_Model(content="{}", delay=0.5), plan=self._plan(),
                                      timeout_seconds=0.05)
        invocation = asyncio.run(port.generate(system_prompt="s", prompt="{}"))
        assert invocation.config["fallback_reason"] == "model timeout"

    def test_unparseable_model_output_keeps_the_plan_and_records_the_problem(self):
        port = PlanAugmentedModelPort(model_port=_Model(content="I think it is the deployment"), plan=self._plan())
        invocation = asyncio.run(port.generate(system_prompt="s", prompt="{}"))
        assert invocation.config["model_output_used"] is False
        assert "not JSON" in invocation.config["model_output_problem"]

    def test_the_token_budget_stops_calling_the_model(self):
        model = _Model(content="{}")
        port = PlanAugmentedModelPort(model_port=model, plan=self._plan(), max_tokens=0)
        invocation = asyncio.run(port.generate(system_prompt="s", prompt="{}"))
        assert model.calls == 0 and invocation.config["fallback_reason"] == "token budget exhausted"


class TestLogNormalizer:
    def test_the_kubelet_saying_it_has_no_log_is_not_an_application_error(self):
        from backend.contexts.execution.infrastructure.adapters.connectors.kubernetes import (
            KubernetesReadNormalizer,
        )
        value = KubernetesReadNormalizer._normalize_log(
            {"log": "unable to retrieve container logs for containerd://abc123def456\n"})
        assert value["logUnavailable"] is True and value["lineCount"] == 0
        assert value["errorLineCount"] == 0 and value["patterns"] == []
        value = KubernetesReadNormalizer._normalize_log({"log": "FATAL: DATABASE_URL is not set\n"})
        assert value["logUnavailable"] is False and value["errorLineCount"] == 1
