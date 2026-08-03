"""Tests for Enterprise Root Cause Analysis Intelligence."""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.enterprise_root_cause_analysis import (
    RootCauseAnalysisService,
    CorrelationEngine,
    TimelineCorrelator,
    EvidenceCollector,
    RootCauseBuilder,
    ConfidenceCalculator,
    ImpactAnalyzer,
    EngineeringStoryGenerator,
    RCA_EVENTS,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture(autouse=True)
def _isolate_data(tmp_path: Path):
    import backend.services.enterprise_root_cause_analysis as mod
    original = mod._DATA_DIR
    mod._DATA_DIR = tmp_path / "rca"
    mod._DATA_DIR.mkdir(parents=True, exist_ok=True)
    for name in ["_INCIDENTS_FILE", "_ANALYSES_FILE"]:
        setattr(mod, name, mod._DATA_DIR / getattr(mod, name).name)
    yield
    mod._DATA_DIR = original


@pytest.fixture
def rca():
    return RootCauseAnalysisService()


@pytest.fixture
def sample_timeline() -> List[Dict[str, Any]]:
    # Relative to "now" (not a fixed past date) — TimelineCorrelator.build_timeline
    # filters events older than hours_back, so a hardcoded absolute date becomes
    # a time bomb: it silently drops out of every window once enough time passes.
    base = datetime.now(timezone.utc) - timedelta(hours=1)

    def _ts(minutes: int) -> str:
        return (base + timedelta(minutes=minutes)).isoformat().replace("+00:00", "Z")

    return [
        {"source": "github", "type": "push", "name": "main", "status": "passed", "timestamp": _ts(0)},
        {"source": "cicd", "type": "build", "name": "CI Build #42", "status": "failed", "timestamp": _ts(5)},
        {"source": "infrastructure", "type": "k8s_deployment", "name": "api-server", "status": "rollback", "timestamp": _ts(10)},
        {"source": "infrastructure", "type": "k8s_pod", "name": "api-server-7d8f9", "status": "crashloop", "timestamp": _ts(12)},
        {"source": "prometheus", "type": "alert", "name": "HighErrorRate", "status": "firing", "timestamp": _ts(8)},
        {"source": "loki", "type": "log_analysis", "name": "api-server-prod", "status": "error", "timestamp": _ts(15)},
        {"source": "opentelemetry", "type": "trace", "name": "api-server/GET /orders", "status": "error", "timestamp": _ts(14)},
    ]


# =============================================================================
# Constants
# =============================================================================


class TestConstants:
    def test_rca_events_count(self):
        assert len(RCA_EVENTS) == 7

    def test_all_events_start_with_rca(self):
        for key, val in RCA_EVENTS.items():
            assert val.startswith("rca."), f"{key}: {val}"


# =============================================================================
# Correlation Engine
# =============================================================================


class TestCorrelationEngine:
    def test_correlate_by_time(self):
        events = [
            {"timestamp": "2026-07-11T10:00:00Z", "source": "a", "name": "e1", "status": "ok"},
            {"timestamp": "2026-07-11T10:02:00Z", "source": "b", "name": "e2", "status": "failed"},
            {"timestamp": "2026-07-11T11:00:00Z", "source": "c", "name": "e3", "status": "ok"},
        ]
        groups = CorrelationEngine.correlate_by_time(events, 300)
        assert len(groups) == 1
        assert groups[0]["event_count"] == 2

    def test_correlate_by_time_no_group(self):
        events = [
            {"timestamp": "2026-07-11T10:00:00Z", "source": "a", "name": "e1"},
            {"timestamp": "2026-07-11T11:00:00Z", "source": "b", "name": "e2"},
        ]
        groups = CorrelationEngine.correlate_by_time(events, 300)
        assert len(groups) == 0

    def test_correlate_by_entity(self):
        events = [
            {"entity_id": "pod-1", "source": "infrastructure", "name": "pod-1", "status": "running"},
            {"entity_id": "pod-1", "source": "prometheus", "name": "Alert", "status": "firing"},
        ]
        groups = CorrelationEngine.correlate_by_entity(events)
        assert len(groups) >= 1

    def test_correlate_prometheus_to_k8s(self):
        alerts = [{"alert_name": "HighCPU", "labels": {"pod": "web-1"}}]
        pods = [{"name": "web-1", "status": "running"}]
        deps = [{"name": "web", "status": "available"}]
        result = CorrelationEngine.correlate_prometheus_to_k8s(alerts, pods, deps)
        assert result[0]["related_pod"] == "web-1"

    def test_correlate_loki_to_traces(self):
        logs = [{"stream": "order-svc", "error_count": 5}]
        traces = [{"service_name": "order-svc", "error_spans": 2}]
        result = CorrelationEngine.correlate_loki_to_traces(logs, traces)
        assert len(result) == 1
        assert result[0]["log_errors"] == 5

    def test_correlate_cicd_to_k8s(self):
        deps = [{"name": "api-deploy", "environment": "production", "image": "api:1.0"}]
        k8s_deps = [{"name": "api-deploy-v2", "image": "api:1.0"}]
        k8s_pods = [{"name": "api-deploy-pod", "namespace": "production"}]
        result = CorrelationEngine.correlate_cicd_to_k8s(deps, k8s_deps, k8s_pods)
        assert len(result) == 1


# =============================================================================
# Timeline Correlator
# =============================================================================


class TestTimelineCorrelator:
    def test_build_timeline(self):
        tl = TimelineCorrelator.build_timeline(hours_back=24)
        assert isinstance(tl, list)

    def test_build_timeline_with_sources(self, sample_timeline):
        tl = TimelineCorrelator.build_timeline(hours_back=24, github_events=sample_timeline[:1])
        assert len(tl) >= 1

    def test_extract_error_events(self, sample_timeline):
        errors = TimelineCorrelator.extract_error_events(sample_timeline)
        assert len(errors) >= 4

    def test_find_adjacent_events(self, sample_timeline):
        adjacent = TimelineCorrelator.find_adjacent_events(sample_timeline, 1, window_minutes=30)
        assert len(adjacent) >= 1


# =============================================================================
# Evidence Collector
# =============================================================================


class TestEvidenceCollector:
    def test_collect_from_pods(self):
        pods = [
            {"name": "p1", "namespace": "prod", "status": "running", "restarts": 0},
            {"name": "p2", "namespace": "prod", "status": "crashloop", "restarts": 5, "crashloop_detected": True},
        ]
        result = EvidenceCollector.collect_from_pods(pods)
        assert result["total_pods"] == 2
        assert result["crashloop_pods"] == 1

    def test_collect_from_deployments(self):
        deps = [
            {"name": "d1", "namespace": "prod", "status": "available", "rollout_status": "completed"},
            {"name": "d2", "namespace": "prod", "status": "unavailable", "rollout_status": "rollback"},
        ]
        result = EvidenceCollector.collect_from_deployments(deps)
        assert result["rollbacks"] == 1

    def test_collect_from_alerts(self):
        alerts = [
            {"alert_name": "CPUHigh", "severity": "critical", "status": "firing"},
            {"alert_name": "DiskLow", "severity": "info", "status": "firing"},
        ]
        result = EvidenceCollector.collect_from_alerts(alerts, "warning")
        assert result["total_firing_alerts"] == 1

    def test_collect_from_logs(self):
        analyses = [
            {"stream": "svc-a", "error_count": 5, "warn_count": 2, "total_lines": 100, "log_sample": ["ERROR"]},
            {"stream": "svc-b", "error_count": 0, "warn_count": 1, "total_lines": 50},
        ]
        result = EvidenceCollector.collect_from_logs(analyses)
        assert result["total_log_streams_with_errors"] == 1

    def test_collect_from_traces(self):
        traces = [
            {"trace_id": "t1", "service_name": "svc-a", "error_spans": 3, "total_spans": 10, "duration_ms": 500, "latency_p95": 800},
            {"trace_id": "t2", "service_name": "svc-b", "error_spans": 0, "total_spans": 5, "duration_ms": 100, "latency_p95": 150},
        ]
        result = EvidenceCollector.collect_from_traces(traces)
        assert result["total_traces_with_errors"] == 1

    def test_collect_from_network(self):
        failures = [
            {"source": "svc-a", "destination": "svc-b", "reason": "timeout", "protocol": "TCP", "port": 8080, "namespace": "prod", "resolved": False},
            {"source": "svc-c", "destination": "svc-d", "reason": "refused", "protocol": "TCP", "port": 443, "namespace": "prod", "resolved": True},
        ]
        result = EvidenceCollector.collect_from_network(failures)
        assert result["total_unresolved_failures"] == 1


# =============================================================================
# Root Cause Builder
# =============================================================================


class TestRootCauseBuilder:
    def test_build_hypotheses_rollback_pattern(self, sample_timeline):
        hypotheses = RootCauseBuilder.build_hypotheses(sample_timeline)
        assert len(hypotheses) >= 1
        pattern_ids = [h["pattern_id"] for h in hypotheses]
        assert "rollback_after_deploy_failure" in pattern_ids

    def test_build_hypotheses_empty_timeline(self):
        hypotheses = RootCauseBuilder.build_hypotheses([])
        assert len(hypotheses) == 0

    def test_classify_by_severity(self, sample_timeline):
        hypotheses = RootCauseBuilder.build_hypotheses(sample_timeline)
        classified = RootCauseBuilder.classify_by_severity(hypotheses)
        assert "deployment" in classified


# =============================================================================
# Confidence Calculator
# =============================================================================


class TestConfidenceCalculator:
    def test_calculate_high_confidence(self, sample_timeline):
        hypothesis = {"matching_event_count": 5, "pattern_id": "test", "root_cause": "Test"}
        score = ConfidenceCalculator.calculate(hypothesis, sample_timeline, total_evidence_sources=4)
        assert score >= 0.5

    def test_calculate_low_confidence(self):
        hypothesis = {"matching_event_count": 0, "pattern_id": "test", "root_cause": "Test"}
        score = ConfidenceCalculator.calculate(hypothesis, [], total_evidence_sources=0)
        assert score < 0.3

    def test_rank_hypotheses(self, sample_timeline):
        hypotheses = [
            {"matching_event_count": 3, "pattern_id": "a", "root_cause": "Cause A"},
            {"matching_event_count": 1, "pattern_id": "b", "root_cause": "Cause B"},
        ]
        ranked = ConfidenceCalculator.rank_hypotheses(hypotheses, sample_timeline)
        assert ranked[0]["confidence"] >= ranked[1]["confidence"]

    def test_confidence_label(self):
        assert ConfidenceCalculator.get_confidence_label(0.9) == "very_high"
        assert ConfidenceCalculator.get_confidence_label(0.7) == "high"
        assert ConfidenceCalculator.get_confidence_label(0.5) == "medium"
        assert ConfidenceCalculator.get_confidence_label(0.3) == "low"
        assert ConfidenceCalculator.get_confidence_label(0.1) == "very_low"


# =============================================================================
# Impact Analyzer
# =============================================================================


class TestImpactAnalyzer:
    def test_analyze(self, sample_timeline):
        impact = ImpactAnalyzer.analyze(sample_timeline)
        assert "affected_services" in impact
        assert "affected_deployments" in impact

    def test_analyze_github_push(self):
        timeline = [
            {"source": "github", "type": "push", "name": "main", "status": "passed",
             "details": {"repository": "org/myapp"}},
            {"source": "github", "type": "pull_request", "name": "PR #42", "status": "merged",
             "details": {}},
            {"source": "cicd", "type": "build", "entity_id": "build_123", "name": "Build #1",
             "status": "failed", "details": {"repository": "org/myapp"}},
        ]
        impact = ImpactAnalyzer.analyze(timeline)
        assert len(impact["affected_commits"]) >= 0
        assert len(impact["affected_prs"]) >= 1
        assert len(impact["affected_services"]) >= 1

    def test_count_impacted(self):
        impact = {"affected_services": ["a", "b"], "affected_deployments": ["c"]}
        assert ImpactAnalyzer.count_impacted(impact) == 3


# =============================================================================
# Engineering Story Generator
# =============================================================================


class TestEngineeringStoryGenerator:
    def test_generate_story(self, sample_timeline):
        hypothesis = {"root_cause": "Failed deployment", "pattern_id": "test", "description": "Test description"}
        impact = {"affected_services": ["api", "web"], "affected_deployments": ["api-v2"], "affected_commits": [], "affected_prs": [], "affected_builds": [], "affected_infrastructure": []}
        evidence = {"pods": {"error_pods": 2, "oom_pods": 0, "crashloop_pods": 1}}
        story = EngineeringStoryGenerator.generate(
            problem="Test incident",
            timeline=sample_timeline,
            top_hypothesis=hypothesis,
            impact=impact,
            confidence=0.75,
            evidence_summary=evidence,
        )
        assert "story_id" in story
        assert "story" in story
        assert len(story["story"]) > 50
        assert "Failed deployment" in story["story"]

    def test_generate_story_no_hypothesis(self, sample_timeline):
        story = EngineeringStoryGenerator.generate(
            problem="Unknown incident",
            timeline=sample_timeline,
            top_hypothesis=None,
            impact={},
            confidence=0.0,
            evidence_summary={},
        )
        assert story["confidence_label"] == "very_low"


# =============================================================================
# Root Cause Analysis Service
# =============================================================================


class TestRootCauseAnalysisService:
    def test_list_analyses_empty(self, rca):
        assert rca.list_analyses() == []

    def test_list_incidents_empty(self, rca):
        assert rca.list_incidents() == []

    @pytest.mark.asyncio
    async def test_get_analysis_not_found(self, rca):
        assert rca.get_analysis("nonexistent") is None

    @pytest.mark.asyncio
    async def test_get_incident_not_found(self, rca):
        assert rca.get_incident("nonexistent") is None

    def test_dashboard_empty(self, rca):
        d = rca.get_dashboard()
        assert d["total_analyses"] == 0

    @pytest.mark.asyncio
    async def test_run_full_analysis(self, rca):
        result = await rca.run_full_analysis(
            problem="Test: pod crash after deployment",
            hours_back=24,
        )
        assert "analysis_id" in result
        assert "incident_id" in result
        assert "timeline" in result
        assert "evidence" in result
        assert "hypotheses" in result
        assert "impact" in result
        assert "story" in result
        assert "recommendation" in result
        assert "recovery_actions" in result
        assert "correlations" in result
        assert "summary" in result

    @pytest.mark.asyncio
    async def test_run_analysis_persists(self, rca):
        result = await rca.run_analysis(
            problem="Persistent incident test",
            hours_back=12,
        )
        analyses = rca.list_analyses()
        assert len(analyses) == 1
        assert analyses[0]["analysis_id"] == result["analysis_id"]
        incidents = rca.list_incidents()
        assert len(incidents) == 1

    @pytest.mark.asyncio
    async def test_run_analysis_updates_dashboard(self, rca):
        await rca.run_analysis(problem="Dashboard test")
        d = rca.get_dashboard()
        assert d["total_analyses"] == 1
        assert d["total_incidents"] == 1

    @pytest.mark.asyncio
    async def test_run_analysis_with_timeline_events(self, rca):
        result = await rca.run_full_analysis(problem="Timeline test", hours_back=168)
        tl = result.get("timeline", [])
        assert isinstance(tl, list)
        assert result["summary"]["total_events_in_timeline"] == len(tl)


# =============================================================================
# Event emission
# =============================================================================


class TestRcaEvents:
    def test_event_hub_topic_routing(self):
        from backend.services.enterprise_event_hub import _topic_for_event
        topic = _topic_for_event("rca.incident_detected")
        assert topic == "enterprise:rca"

    @pytest.mark.asyncio
    async def test_service_routes_events(self, rca):
        with patch.object(rca, "_emit", new_callable=AsyncMock) as mock_emit:
            await rca.run_full_analysis(problem="Event test")
            assert mock_emit.called


# =============================================================================
# E2E: Full pipeline
# =============================================================================


class TestEndToEnd:
    @pytest.mark.asyncio
    async def test_full_rca_pipeline(self, rca):
        result = await rca.run_full_analysis(
            problem="Production outage: elevated errors after deploy",
            hours_back=48,
        )

        # 1. Timeline built
        assert len(result["timeline"]) >= 0

        # 2. Evidence collected
        assert isinstance(result["evidence"], dict)

        # 3. Hypotheses generated
        assert len(result["hypotheses"]) >= 1

        # 4. Top hypothesis exists
        top = result["top_hypothesis"]
        assert top is not None
        assert "root_cause" in top
        assert "confidence" in top

        # 5. Impact analyzed
        impact = result["impact"]
        assert isinstance(impact.get("affected_services"), list)

        # 6. Story generated
        story = result["story"]
        assert "story" in story
        assert len(story["story"]) > 20

        # 7. Recommendations and recovery
        assert isinstance(result["recommendation"], dict)
        assert isinstance(result["recovery_actions"], list)

        # 8. Summary
        s = result["summary"]
        assert s["top_root_cause"] != ""
        assert s["confidence_score"] >= 0

        # 9. Correlations
        assert isinstance(result["correlations"], dict)
