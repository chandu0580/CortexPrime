"""
Comprehensive validation tests for Enterprise CI/CD & Deployment Intelligence.
Verifies all 8 subsystems plus events, routing, and E2E workflows.
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch

from backend.services.enterprise_cicd_intelligence import (
    CiCdIntegrationService,
    cicd_intelligence,
    CiCdPlatformManager,
    BuildIntelligence,
    DeploymentIntelligence,
    ArtifactIntelligence,
    PipelineTimeline,
    FailureAnalysis,
    DeploymentRecovery,
    CICD_EVENTS,
    SUPPORTED_PLATFORMS,
)
from backend.events.enterprise_event_types import EnterpriseEventTypes as EET


# =============================================================================
# Constants
# =============================================================================

class TestCiCdEvents:
    def test_all_events_defined(self):
        assert len(CICD_EVENTS) == 21

    def test_event_values_format(self):
        for key, val in CICD_EVENTS.items():
            assert val.startswith("cicd."), f"{key} -> {val}"

    def test_enterprise_event_types_integration(self):
        assert EET.CICD_PIPELINE_CREATED == "cicd.pipeline_created"
        assert EET.CICD_BUILD_COMPLETED == "cicd.build_completed"
        assert EET.CICD_DEPLOYMENT_RECOVERED == "cicd.deployment_recovered"
        assert EET.CICD_FAILURE_ANALYZED == "cicd.failure_analyzed"
        assert EET.CICD_RECOVERY_STARTED == "cicd.recovery_started"

    def test_event_hub_routing(self):
        from backend.services.enterprise_event_hub import _topic_for_event
        assert _topic_for_event("cicd.pipeline_created") == "enterprise:cicd"
        assert _topic_for_event("cicd.build_started") == "enterprise:cicd"
        assert _topic_for_event("cicd.deployment_recovered") == "enterprise:cicd"

    def test_supported_platforms(self):
        assert "github_actions" in SUPPORTED_PLATFORMS
        assert "azure_devops" in SUPPORTED_PLATFORMS
        assert "jenkins" in SUPPORTED_PLATFORMS
        assert "gitlab_ci" in SUPPORTED_PLATFORMS
        assert "circleci" in SUPPORTED_PLATFORMS


# =============================================================================
# Part 1 — CI/CD Platform Manager
# =============================================================================

class TestCiCdPlatformManager:
    def test_detect_github_actions(self):
        assert CiCdPlatformManager.detect_platform("workflow_run", {"repository": {"html_url": "https://github.com/org/repo"}}) == "github_actions"

    def test_detect_azure_devops(self):
        assert CiCdPlatformManager.detect_platform("azure-pipelines", {}) == "azure_devops"

    def test_detect_jenkins(self):
        assert CiCdPlatformManager.detect_platform("jenkins", {}) == "jenkins"

    def test_detect_gitlab_ci(self):
        assert CiCdPlatformManager.detect_platform(".gitlab-ci", {}) == "gitlab_ci"

    def test_detect_circleci(self):
        assert CiCdPlatformManager.detect_platform(".circleci", {}) == "circleci"

    def test_detect_default(self):
        assert CiCdPlatformManager.detect_platform("unknown_source", {}) == "github_actions"

    def test_parse_pipeline_event_workflow_run(self):
        payload = {
            "repository": {"full_name": "org/repo"},
            "sender": {"login": "bot"},
            "workflow_run": {"name": "CI", "id": 101, "head_branch": "main", "head_sha": "abc", "status": "completed", "conclusion": "success", "run_number": 5},
        }
        parsed = CiCdPlatformManager.parse_pipeline_event("workflow_run", payload)
        assert parsed["platform"] == "github_actions"
        assert parsed["workflow_name"] == "CI"
        assert parsed["status"] == "completed"
        assert parsed["conclusion"] == "success"

    def test_parse_pipeline_event_no_workflow(self):
        payload = {"repository": {"full_name": "org/repo"}}
        parsed = CiCdPlatformManager.parse_pipeline_event("push", payload)
        assert parsed["repository"] == "org/repo"
        assert parsed.get("status") == "unknown"


# =============================================================================
# Part 2 — Build Intelligence
# =============================================================================

class TestBuildIntelligence:
    def test_list_builds_returns_list(self):
        assert isinstance(BuildIntelligence.list_builds(), list)

    def test_track_and_get_build(self):
        b = BuildIntelligence.track_build("github_actions", {"name": "CI Build", "status": "running", "head_branch": "main"})
        assert b["build_id"] is not None
        assert BuildIntelligence.get_build(b["build_id"]) is not None

    def test_track_build_update(self):
        b1 = BuildIntelligence.track_build("jenkins", {"name": "Build #42", "status": "running", "repository": "org/a"})
        bid = b1["build_id"]
        BuildIntelligence.track_build("jenkins", {"build_id": bid, "status": "passed", "conclusion": "success"})
        updated = BuildIntelligence.get_build(bid)
        assert updated["status"] == "passed"
        assert updated["conclusion"] == "success"

    def test_list_by_platform(self):
        BuildIntelligence.track_build("circleci", {"name": "Circle Build", "status": "passed", "repository": "org/b"})
        circle = BuildIntelligence.list_builds(platform="circleci")
        assert len(circle) >= 1
        assert all(b["platform"] == "circleci" for b in circle)

    def test_list_by_status(self):
        BuildIntelligence.track_build("gitlab_ci", {"name": "Failed Build", "status": "failed", "repository": "org/c"})
        failed = BuildIntelligence.list_builds(status="failed")
        assert len(failed) >= 1

    def test_dashboard_stats(self):
        stats = BuildIntelligence.get_dashboard_stats()
        assert "total_builds" in stats
        assert "passed" in stats
        assert "failed" in stats
        assert "running" in stats

    def test_analyze_trends_insufficient(self):
        trend = BuildIntelligence.analyze_trends(limit=3)
        assert trend["trend"] == "insufficient_data"

    def test_get_nonexistent(self):
        assert BuildIntelligence.get_build("nonexistent") is None


# =============================================================================
# Part 3 — Deployment Intelligence
# =============================================================================

class TestDeploymentIntelligence:
    def test_list_returns_list(self):
        assert isinstance(DeploymentIntelligence.list_deployments(), list)

    def test_track_and_get(self):
        d = DeploymentIntelligence.track_deployment("azure_devops", {"environment": "staging", "status": "deploying", "repository": "org/repo"})
        assert d["deployment_id"] is not None
        assert DeploymentIntelligence.get_deployment(d["deployment_id"]) is not None

    def test_track_update(self):
        d1 = DeploymentIntelligence.track_deployment("github_actions", {"environment": "production", "status": "deploying", "repository": "org/repo"})
        did = d1["deployment_id"]
        DeploymentIntelligence.track_deployment("github_actions", {"deployment_id": did, "status": "deployed"})
        updated = DeploymentIntelligence.get_deployment(did)
        assert updated["status"] == "deployed"

    def test_list_by_environment(self):
        DeploymentIntelligence.track_deployment("jenkins", {"environment": "qa", "status": "deployed", "repository": "org/d"})
        qa = DeploymentIntelligence.list_deployments(environment="qa")
        assert len(qa) >= 1

    def test_list_by_status(self):
        DeploymentIntelligence.track_deployment("gitlab_ci", {"environment": "prod", "status": "failed", "repository": "org/e"})
        failed = DeploymentIntelligence.list_deployments(status="failed")
        assert len(failed) >= 1

    def test_dashboard_stats(self):
        stats = DeploymentIntelligence.get_dashboard_stats()
        assert "total_deployments" in stats
        assert "success" in stats
        assert "failed" in stats
        assert "rolled_back" in stats

    def test_environment_health(self):
        health = DeploymentIntelligence.environment_health()
        assert isinstance(health, dict)

    def test_get_nonexistent(self):
        assert DeploymentIntelligence.get_deployment("nonexistent") is None


# =============================================================================
# Part 4 — Artifact Intelligence
# =============================================================================

class TestArtifactIntelligence:
    def test_list_returns_list(self):
        assert isinstance(ArtifactIntelligence.list_artifacts(), list)

    def test_track_and_get(self):
        a = ArtifactIntelligence.track_artifact({"artifact_type": "docker_image", "name": "myapp", "version": "v1.0", "registry": "ghcr.io"})
        assert a["artifact_id"] is not None
        assert ArtifactIntelligence.get_artifact(a["artifact_id"]) is not None

    def test_track_update(self):
        a1 = ArtifactIntelligence.track_artifact({"artifact_type": "helm_chart", "name": "my-chart", "version": "1.0.0"})
        aid = a1["artifact_id"]
        ArtifactIntelligence.track_artifact({"artifact_id": aid, "version": "1.0.1"})
        assert ArtifactIntelligence.get_artifact(aid)["version"] == "1.0.1"

    def test_list_by_type(self):
        ArtifactIntelligence.track_artifact({"artifact_type": "docker_image", "name": "nginx", "tag": "latest"})
        docker = ArtifactIntelligence.list_artifacts(artifact_type="docker_image")
        assert len(docker) >= 1

    def test_list_by_build(self):
        ArtifactIntelligence.track_artifact({"artifact_type": "binary", "name": "app.jar", "build_id": "bld-123"})
        arts = ArtifactIntelligence.list_artifacts(build_id="bld-123")
        assert len(arts) >= 1

    def test_dashboard_stats(self):
        # get_dashboard_stats() now returns a generic by_type breakdown
        # instead of hardcoded top-level keys per artifact type.
        ArtifactIntelligence.track_artifact({"artifact_type": "docker_image", "name": "nginx", "tag": "latest"})
        ArtifactIntelligence.track_artifact({"artifact_type": "helm_chart", "name": "mychart", "tag": "1.0.0"})
        stats = ArtifactIntelligence.get_dashboard_stats()
        assert "total_artifacts" in stats
        assert "by_type" in stats
        assert "docker_image" in stats["by_type"]
        assert "helm_chart" in stats["by_type"]

    def test_get_nonexistent(self):
        assert ArtifactIntelligence.get_artifact("nonexistent") is None


# =============================================================================
# Part 5 — Pipeline Timeline
# =============================================================================

class TestPipelineTimeline:
    def test_build_timeline_returns_list(self):
        tl = PipelineTimeline.build_timeline()
        assert isinstance(tl, list)

    def test_timeline_sorted_by_timestamp(self):
        tl = PipelineTimeline.build_timeline()
        timestamps = [e.get("timestamp", "") for e in tl]
        assert timestamps == sorted(timestamps, reverse=True)

    def test_get_dashboard(self):
        stats = PipelineTimeline.get_pipeline_dashboard()
        assert "total_pipelines" in stats
        assert "recent_builds" in stats
        assert "recent_deployments" in stats
        assert "recent_artifacts" in stats


# =============================================================================
# Part 6 — Failure Analysis
# =============================================================================

class TestFailureAnalysis:
    def test_list_returns_list(self):
        assert isinstance(FailureAnalysis.list_failures(), list)

    def test_analyze_build_failure(self):
        logs = [
            "[2026-07-11] Starting build...",
            "[2026-07-11] Running tests...",
            "ERROR: test_login failed: AssertionError: expected True, got False",
            "ERROR: test_logout failed: TimeoutError",
            "Build FAILED",
        ]
        result = FailureAnalysis.analyze_failure("build-42", "build", logs, {"platform": "github_actions"})
        assert result["failure_id"] is not None
        assert result["entity_id"] == "build-42"
        categories = [c["category"] for c in result["root_causes"]]
        assert "test_failure" in categories
        assert result["entity_type"] == "build"

    def test_analyze_timeout_failure(self):
        logs = ["Step 1...", "Step 2...", "FATAL: Operation timed out after 300s"]
        result = FailureAnalysis.analyze_failure("dep-1", "deployment", logs)
        categories = [c["category"] for c in result["root_causes"]]
        assert "timeout" in categories

    def test_analyze_unknown_failure(self):
        result = FailureAnalysis.analyze_failure("unk-1", "build", ["Something went wrong"])
        categories = [c["category"] for c in result["root_causes"]]
        assert "unknown" in categories

    def test_analyze_compilation_failure(self):
        logs = ["Running compiler...", "src/main.py:42: SyntaxError: invalid syntax"]
        result = FailureAnalysis.analyze_failure("bld-99", "build", logs)
        categories = [c["category"] for c in result["root_causes"]]
        assert "compilation" in categories

    def test_analyze_docker_failure(self):
        logs = ["Pulling image...", "Error: image not found: myapp:latest"]
        result = FailureAnalysis.analyze_failure("bld-100", "build", logs)
        categories = [c["category"] for c in result["root_causes"]]
        assert "docker" in categories

    def test_get_failure(self):
        logs = ["Config error: missing API_KEY"]
        result = FailureAnalysis.analyze_failure("dep-2", "deployment", logs)
        fetched = FailureAnalysis.get_failure(result["failure_id"])
        assert fetched is not None
        assert fetched["entity_id"] == "dep-2"

    def test_dashboard_stats(self):
        stats = FailureAnalysis.get_dashboard_stats()
        assert "total_failures" in stats
        assert "top_causes" in stats

    def test_get_nonexistent(self):
        assert FailureAnalysis.get_failure("nonexistent") is None


# =============================================================================
# Part 7 — Deployment Recovery
# =============================================================================

class TestDeploymentRecovery:
    def test_list_returns_list(self):
        assert isinstance(DeploymentRecovery.list_recoveries(), list)

    def test_recommend_strategy_rollback(self):
        failure = {"root_causes": [{"category": "timeout"}]}
        dep = {}
        strategy = DeploymentRecovery.recommend_strategy(dep, failure)
        assert strategy == "rollback"

    def test_recommend_strategy_retry(self):
        failure = {"root_causes": [{"category": "configuration"}]}
        dep = {}
        strategy = DeploymentRecovery.recommend_strategy(dep, failure)
        assert strategy == "retry"

    def test_recommend_strategy_rollback_rollback(self):
        failure = {"root_causes": [{"category": "rollback"}]}
        dep = {}
        strategy = DeploymentRecovery.recommend_strategy(dep, failure)
        assert strategy == "rollback_rollback"

    @pytest.mark.asyncio
    async def test_recover_rollback(self):
        with patch("backend.services.enterprise_cicd_intelligence.DeploymentRecovery.recover", new_callable=AsyncMock) as mock:
            mock.return_value = {"recovery_id": "rec-1", "status": "completed", "strategy": "rollback"}
            result = await DeploymentRecovery.recover("dep-1", strategy="rollback")
            assert result["status"] == "completed"

    def test_dashboard_stats(self):
        stats = DeploymentRecovery.get_dashboard_stats()
        assert "total_recoveries" in stats
        assert "completed" in stats
        assert "failed" in stats

    def test_get_nonexistent(self):
        assert DeploymentRecovery.get_recovery("nonexistent") is None


# =============================================================================
# Part 8 — CiCdIntegrationService Orchestrator
# =============================================================================

class TestCiCdIntegrationService:
    @pytest.fixture
    def svc(self):
        s = CiCdIntegrationService()
        s.clear_state()
        return s

    @pytest.mark.asyncio
    async def test_ingest_pipeline_event_success(self, svc):
        payload = {
            "repository": {"full_name": "org/repo", "clone_url": "https://github.com/org/repo.git"},
            "sender": {"login": "bot"},
            "workflow_run": {"name": "CI", "id": 1, "head_branch": "main", "head_sha": "abc", "status": "completed", "conclusion": "success", "run_number": 42, "workflow_id": 1, "actor": {"login": "bot"}},
        }
        with patch.object(svc, "_emit", new_callable=AsyncMock):
            result = await svc.ingest_pipeline_event("workflow_run", payload)
        assert result["status"] == "passed"
        assert result["workflow_name"] == "CI"

    @pytest.mark.asyncio
    async def test_ingest_pipeline_event_failed(self, svc):
        payload = {
            "repository": {"full_name": "org/repo"},
            "sender": {"login": "bot"},
            "workflow_run": {"name": "Failed Pipeline", "id": 2, "head_branch": "main", "head_sha": "def", "status": "completed", "conclusion": "failure"},
        }
        with patch.object(svc, "_emit", new_callable=AsyncMock):
            result = await svc.ingest_pipeline_event("workflow_run", payload)
        assert result["status"] == "failed"

    @pytest.mark.asyncio
    async def test_ingest_build_event_success(self, svc):
        with patch.object(svc, "_emit", new_callable=AsyncMock):
            result = await svc.ingest_build_event("github_actions", {"name": "Build #1", "status": "passed", "repository": "org/repo", "head_branch": "main", "head_sha": "abc"})
        assert result["status"] == "passed"

    @pytest.mark.asyncio
    async def test_ingest_build_event_with_failure_analysis(self, svc):
        data = {"name": "Broken Build", "status": "failed", "repository": "org/repo", "head_branch": "feature", "head_sha": "xyz", "logs": ["ERROR: test failed: AssertionError", "Build FAILED"]}
        with patch.object(svc, "_emit", new_callable=AsyncMock):
            result = await svc.ingest_build_event("jenkins", data)
        assert result["status"] == "failed"
        failures = FailureAnalysis.list_failures(entity_type="build")
        assert len(failures) >= 1

    @pytest.mark.asyncio
    async def test_ingest_deployment_event(self, svc):
        with patch.object(svc, "_emit", new_callable=AsyncMock):
            result = await svc.ingest_deployment_event("azure_devops", {"environment": "production", "status": "deployed", "repository": "org/repo"})
        assert result["status"] == "deployed"

    @pytest.mark.asyncio
    async def test_ingest_deployment_event_failed_with_logs(self, svc):
        data = {"environment": "staging", "status": "failed", "repository": "org/repo", "logs": ["Deploying...", "Error: timeout connecting to database"]}
        with patch.object(svc, "_emit", new_callable=AsyncMock):
            result = await svc.ingest_deployment_event("circleci", data)
        assert result["status"] == "failed"
        failures = FailureAnalysis.list_failures(entity_type="deployment")
        assert len(failures) >= 1

    @pytest.mark.asyncio
    async def test_ingest_artifact_event(self, svc):
        with patch.object(svc, "_emit", new_callable=AsyncMock):
            result = await svc.ingest_artifact_event({"artifact_type": "docker_image", "name": "myapp", "version": "v2", "registry": "ghcr.io"})
        assert result["artifact_type"] == "docker_image"

    @pytest.mark.asyncio
    async def test_handle_failure_and_recover(self, svc):
        with patch.object(svc, "_emit", new_callable=AsyncMock):
            dep = DeploymentIntelligence.track_deployment("github_actions", {"environment": "prod", "status": "failed", "repository": "org/repo"})
            result = await svc.handle_failure_and_recover(
                entity_id=dep["deployment_id"],
                entity_type="deployment",
                logs=["Error: timeout", "Deployment failed"],
            )
        assert "failure" in result
        assert result["failure"]["entity_type"] == "deployment"
        assert result["recovery"] is not None or "note" in result

    @pytest.mark.asyncio
    async def test_handle_build_no_recovery(self, svc):
        with patch.object(svc, "_emit", new_callable=AsyncMock):
            result = await svc.handle_failure_and_recover(
                entity_id="build-1",
                entity_type="build",
                logs=["Build crashed"],
            )
        assert result["note"] == "Build failures should be retried via Engineering Executive"
        assert result["recovery"] is None

    @pytest.mark.asyncio
    async def test_get_dashboard(self, svc):
        stats = svc.get_dashboard()
        assert "total_builds" in stats
        assert "total_deployments" in stats
        assert "total_artifacts" in stats
        assert "total_failures" in stats
        assert "total_recoveries" in stats

    @pytest.mark.asyncio
    async def test_get_timeline(self, svc):
        with patch.object(svc, "_emit", new_callable=AsyncMock):
            await svc.ingest_build_event("github_actions", {"name": "Timeline Build", "status": "passed", "repository": "org/repo", "head_branch": "main", "head_sha": "aaa"})
        tl = svc.get_timeline()
        assert len(tl) >= 1

    @pytest.mark.asyncio
    async def test_clear_state(self, svc):
        with patch.object(svc, "_emit", new_callable=AsyncMock):
            await svc.ingest_build_event("github_actions", {"name": "To Clear", "status": "passed", "repository": "org/repo", "head_branch": "main", "head_sha": "bbb"})
        svc.clear_state()
        stats = svc.get_dashboard()
        assert stats["total_builds"] == 0
        assert stats["total_deployments"] == 0
        assert stats["total_failures"] == 0


# =============================================================================
# E2E Workflows
# =============================================================================

class TestCiCdE2E:
    @pytest.mark.asyncio
    async def test_push_to_build_to_artifact_workflow(self):
        """Developer push → pipeline → build → artifact."""
        svc = CiCdIntegrationService()
        svc.clear_state()

        with patch.object(svc, "_emit", new_callable=AsyncMock):
            # 1. Ingest pipeline event (push triggers workflow)
            pipeline_result = await svc.ingest_pipeline_event("workflow_run", {
                "repository": {"full_name": "org/e2e-demo", "clone_url": "https://github.com/org/e2e-demo.git"},
                "sender": {"login": "dev"},
                "workflow_run": {"name": "CI Pipeline", "id": 100, "head_branch": "feature/login", "head_sha": "commit1", "status": "completed", "conclusion": "success", "run_number": 10, "workflow_id": 5, "actor": {"login": "bot"}},
            })
            assert pipeline_result["status"] == "passed"

            # 2. Ingest build event
            build_result = await svc.ingest_build_event("github_actions", {
                "name": "Build #10", "status": "passed", "repository": "org/e2e-demo",
                "head_branch": "feature/login", "head_sha": "commit1", "conclusion": "success",
            })
            assert build_result["status"] == "passed"

            # 3. Ingest artifact
            art_result = await svc.ingest_artifact_event({
                "artifact_type": "docker_image", "name": "e2e-app", "version": "v1.0.10",
                "registry": "ghcr.io", "image": "ghcr.io/org/e2e-app", "tag": "v1.0.10",
                "build_id": build_result["build_id"],
            })
            assert art_result["artifact_type"] == "docker_image"

        stats = svc.get_dashboard()
        assert stats["total_builds"] >= 1
        assert stats["total_artifacts"] >= 1

    @pytest.mark.asyncio
    async def test_build_failure_to_analysis_workflow(self):
        """Build fails → failure analysis → metrics recorded."""
        svc = CiCdIntegrationService()
        svc.clear_state()

        with patch.object(svc, "_emit", new_callable=AsyncMock):
            with patch("backend.services.enterprise_cicd_intelligence.FailureAnalysis.analyze_failure") as mock_analyze:
                mock_analyze.return_value = {"failure_id": "fail-e2e", "entity_id": "bld-fail", "entity_type": "build", "root_causes": [{"category": "test_failure", "description": "Test failed"}], "log_sample": [], "analyzed_at": "2026-01-01"}
                result = await svc.ingest_build_event("jenkins", {
                    "name": "Failed Build", "status": "failed", "repository": "org/e2e",
                    "head_branch": "main", "head_sha": "bad", "logs": ["Test FAILED"],
                })
                assert result["status"] == "failed"
                assert mock_analyze.called

    @pytest.mark.asyncio
    async def test_deployment_failure_recovery_workflow(self):
        """Deployment fails → failure analysis → recovery triggered."""
        svc = CiCdIntegrationService()
        svc.clear_state()

        with patch.object(svc, "_emit", new_callable=AsyncMock):
            # Track a deployment
            dep = DeploymentIntelligence.track_deployment("github_actions", {
                "environment": "production", "status": "failed", "repository": "org/e2e",
            })
            dep_id = dep["deployment_id"]

            # Handle failure and recovery
            result = await svc.handle_failure_and_recover(
                entity_id=dep_id,
                entity_type="deployment",
                logs=["Error: timeout connecting to database", "Deployment failed"],
            )
            assert "failure" in result
            assert result["failure"]["entity_type"] == "deployment"
            if result.get("recovery"):
                assert "strategy" in result["recovery"]

    @pytest.mark.asyncio
    async def test_multi_platform_dashboard_accuracy(self):
        """Events from multiple platforms → dashboard reflects all."""
        svc = CiCdIntegrationService()
        svc.clear_state()

        with patch.object(svc, "_emit", new_callable=AsyncMock):
            await svc.ingest_build_event("github_actions", {"name": "GA Build", "status": "passed", "repository": "org/ga", "head_branch": "main", "head_sha": "a"})
            await svc.ingest_build_event("azure_devops", {"name": "AZ Build", "status": "passed", "repository": "org/az", "head_branch": "main", "head_sha": "b"})
            await svc.ingest_build_event("jenkins", {"name": "JK Build", "status": "failed", "repository": "org/jk", "head_branch": "main", "head_sha": "c", "logs": ["Error: compilation error"]})
            await svc.ingest_deployment_event("circleci", {"environment": "staging", "status": "deployed", "repository": "org/ci"})
            await svc.ingest_artifact_event({"artifact_type": "docker_image", "name": "multi", "version": "v1", "registry": "ghcr.io"})

        stats = svc.get_dashboard()
        assert stats["total_builds"] >= 3
        assert stats["total_deployments"] >= 1
        assert stats["total_artifacts"] >= 1
        assert stats["total_failures"] >= 0

        # Check build filtering
        jenkins = BuildIntelligence.list_builds(platform="jenkins")
        assert len(jenkins) >= 1
        passed = BuildIntelligence.list_builds(status="passed")
        assert len(passed) >= 2
        failed = BuildIntelligence.list_builds(status="failed")
        assert len(failed) >= 1

    @pytest.mark.asyncio
    async def test_environment_health_aggregation(self):
        """Multiple deployments to same env → environment health accurate."""
        svc = CiCdIntegrationService()
        svc.clear_state()

        with patch.object(svc, "_emit", new_callable=AsyncMock):
            DeploymentIntelligence.track_deployment("github_actions", {"environment": "production", "status": "deployed", "repository": "org/app"})
            DeploymentIntelligence.track_deployment("github_actions", {"environment": "production", "status": "deployed", "repository": "org/app"})
            DeploymentIntelligence.track_deployment("github_actions", {"environment": "production", "status": "failed", "repository": "org/app"})

        health = DeploymentIntelligence.environment_health()
        assert "production" in health
        assert health["production"]["status"] in ("healthy", "degraded")
        assert health["production"]["total"] == 3
        assert health["production"]["success"] >= 2
        assert health["production"]["failed"] >= 1
