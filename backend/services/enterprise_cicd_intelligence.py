"""
Enterprise CI/CD & Deployment Intelligence.

Integrates CortexPrime with real CI/CD systems via connector registry.
Maintains backward compatibility — JSON file fallback when connectors
are unavailable.

Subsystems:
  1. CiCdPlatformManager        — multi-platform event detection & parsing
  2. GitHubActionsIntegration   — production GitHub Actions API (Phase 2)
  3. AzurePipelinesIntegration  — production Azure DevOps Pipelines (Phase 4)
  4. JenkinsIntegration         — production Jenkins API (Phase 3)
  5. GitLabCIIntegration        — production GitLab CI API (Phase 5)
  6. CircleCIIntegration        — production CircleCI API (Phase 6)
  7. BuildIntelligence          — build tracking, trends, flaky, ownership
  8. DeploymentIntelligence     — deployment analysis, environment health
  9. ArtifactIntelligence       — artifact tracking, lineage, deps, promotion
  10. PipelineTimeline          — aggregated pipeline timeline builder
  11. FailureAnalysis           — root-cause analysis for build/deploy failures
  12. DeploymentRecovery        — coordinated recovery & rollback
  13. CiCdIntegrationService    — orchestrator singleton
"""
from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

log = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_PIPELINES_FILE = _DATA_DIR / "cicd_pipelines.json"
_BUILDS_FILE = _DATA_DIR / "cicd_builds.json"
_DEPLOYMENTS_FILE = _DATA_DIR / "cicd_deployments.json"
_ARTIFACTS_FILE = _DATA_DIR / "cicd_artifacts.json"
_TIMELINES_FILE = _DATA_DIR / "cicd_timelines.json"
_FAILURES_FILE = _DATA_DIR / "cicd_failures.json"
_RECOVERIES_FILE = _DATA_DIR / "cicd_recoveries.json"

CICD_EVENTS: Dict[str, str] = {
    "pipeline_created": "cicd.pipeline_created",
    "pipeline_started": "cicd.pipeline_started",
    "pipeline_completed": "cicd.pipeline_completed",
    "pipeline_failed": "cicd.pipeline_failed",
    "build_started": "cicd.build_started",
    "build_completed": "cicd.build_completed",
    "build_failed": "cicd.build_failed",
    "deployment_started": "cicd.deployment_started",
    "deployment_completed": "cicd.deployment_completed",
    "deployment_failed": "cicd.deployment_failed",
    "deployment_recovered": "cicd.deployment_recovered",
    "artifact_published": "cicd.artifact_published",
    "failure_analyzed": "cicd.failure_analyzed",
    "recovery_started": "cicd.recovery_started",
    "recovery_completed": "cicd.recovery_completed",
    "timeline_built": "cicd.timeline_built",
    "workflow_job_started": "cicd.workflow_job_started",
    "workflow_job_completed": "cicd.workflow_job_completed",
    "workflow_step_completed": "cicd.workflow_step_completed",
    "artifact_promoted": "cicd.artifact_promoted",
    "build_analyzed": "cicd.build_analyzed",
}

SUPPORTED_PLATFORMS = ["github_actions", "azure_devops", "jenkins", "gitlab_ci", "circleci"]

PLATFORM_PATTERNS: Dict[str, List[str]] = {
    "github_actions": [".github/workflows", "github"],
    "azure_devops": ["azure-pipelines", "azure pipelines", "dev.azure.com"],
    "jenkins": ["jenkinsfile", "jenkins"],
    "gitlab_ci": [".gitlab-ci", "gitlab"],
    "circleci": [".circleci", "circleci"],
}


def _load_json(path: Path) -> List[Dict[str, Any]]:
    try:
        if path.exists():
            with open(path) as f:
                return json.load(f)
    except Exception as exc:
        log.warning("Failed to load %s: %s", path.name, exc)
    return []


def _save_json(path: Path, data: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as exc:
        log.warning("Failed to save %s: %s", path.name, exc)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _id(prefix: str = "cicd") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10]}"


def _get_connector(connector_type: str):
    try:
        from backend.connectors.registry import connector_registry
        return connector_registry.get(connector_type)
    except Exception:
        return None


def _sync_build_to_runtime(build: Dict[str, Any]) -> None:
    try:
        from backend.services.enterprise_runtime_store import EngineeringExecution, runtime_store
        existing = runtime_store.get_execution(build.get("execution_id", "")) if build.get("execution_id") else None
        if existing:
            runtime_store.update_execution(existing.execution_id,
                build_id=build.get("build_id", ""), build_status=build.get("status", build.get("conclusion", "")),
                build_platform=build.get("platform", ""), build_name=build.get("workflow_name", build.get("name", "")),
                repository=build.get("repository", ""), branch=build.get("head_branch", ""),
                commit_sha=build.get("head_sha", ""), owner=build.get("sender", ""),
                status=build.get("status", "pending"), updated_at=build.get("updated_at", _now()),
            )
        else:
            runtime_store.create_execution(EngineeringExecution(
                execution_id=build.get("execution_id", _id("exec")),
                build_id=build.get("build_id", ""), build_status=build.get("status", build.get("conclusion", "")),
                build_platform=build.get("platform", ""), build_name=build.get("workflow_name", build.get("name", "")),
                repository=build.get("repository", ""), branch=build.get("head_branch", ""),
                commit_sha=build.get("head_sha", ""), owner=build.get("sender", ""),
                status=build.get("status", "pending"),
                created_at=build.get("created_at", _now()), updated_at=build.get("updated_at", _now()),
            ))
    except Exception:
        pass


def _sync_deploy_to_runtime(deploy: Dict[str, Any]) -> None:
    try:
        from backend.services.enterprise_runtime_store import EngineeringExecution, runtime_store
        existing = runtime_store.get_execution(deploy.get("execution_id", "")) if deploy.get("execution_id") else None
        if existing:
            runtime_store.update_execution(existing.execution_id,
                deployment_id=deploy.get("deployment_id", ""), deployment_status=deploy.get("status", ""),
                deployment_environment=deploy.get("environment", ""), repository=deploy.get("repository", ""),
                updated_at=deploy.get("updated_at", _now()),
            )
        else:
            runtime_store.create_execution(EngineeringExecution(
                execution_id=deploy.get("execution_id", _id("exec")),
                deployment_id=deploy.get("deployment_id", ""), deployment_status=deploy.get("status", ""),
                deployment_environment=deploy.get("environment", ""), repository=deploy.get("repository", ""),
                status=deploy.get("status", "pending"),
                created_at=deploy.get("created_at", _now()), updated_at=deploy.get("updated_at", _now()),
            ))
    except Exception:
        pass


def _sync_artifact_to_runtime(artifact: Dict[str, Any]) -> None:
    try:
        from backend.services.enterprise_runtime_store import EngineeringExecution, runtime_store
        existing = runtime_store.get_execution(artifact.get("execution_id", "")) if artifact.get("execution_id") else None
        artifacts_list = [{"artifact_id": artifact.get("artifact_id"), "name": artifact.get("name"),
                           "artifact_type": artifact.get("artifact_type"), "version": artifact.get("version")}]
        if existing:
            runtime_store.update_execution(existing.execution_id, artifacts=artifacts_list, updated_at=_now())
        else:
            runtime_store.create_execution(EngineeringExecution(
                execution_id=artifact.get("execution_id", _id("exec")),
                artifacts=artifacts_list, status="published",
                created_at=artifact.get("created_at", _now()), updated_at=artifact.get("updated_at", _now()),
            ))
    except Exception:
        pass


# =============================================================================
# Part 1 — CI/CD Platform Manager
# =============================================================================

class CiCdPlatformManager:
    """Detect CI/CD platform from event payload and parse accordingly."""

    @staticmethod
    def detect_platform(source: str, payload: Optional[Dict[str, Any]] = None) -> str:
        lower = source.lower()
        for platform, patterns in PLATFORM_PATTERNS.items():
            if any(p in lower for p in patterns):
                return platform
        if payload and "repository" in payload:
            repo_url = payload.get("repository", {}).get("clone_url", "") or payload.get("repository", {}).get("html_url", "")
            for platform, patterns in PLATFORM_PATTERNS.items():
                if any(p in repo_url.lower() for p in patterns):
                    return platform
        return "github_actions"

    @staticmethod
    def parse_pipeline_event(event_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        platform = CiCdPlatformManager.detect_platform(event_type, payload)
        base: Dict[str, Any] = {
            "platform": platform,
            "event_type": event_type,
            "received_at": _now(),
            "repository": payload.get("repository", {}).get("full_name", payload.get("project", {}).get("full_name", "")),
            "sender": payload.get("sender", {}).get("login", payload.get("user", {}).get("login", "")),
        }
        workflow = payload.get("workflow_run") or payload.get("workflow") or payload.get("pipeline") or {}
        base["workflow_name"] = workflow.get("name", "") if workflow else ""
        base["workflow_id"] = workflow.get("id", workflow.get("workflow_id", "")) if workflow else ""
        base["run_number"] = workflow.get("run_number", "") if workflow else ""
        base["head_branch"] = workflow.get("head_branch", workflow.get("branch", "")) if workflow else ""
        base["head_sha"] = workflow.get("head_sha", workflow.get("sha", "")) if workflow else ""
        base["status"] = workflow.get("status", workflow.get("state", "unknown")) if workflow else "unknown"
        base["conclusion"] = workflow.get("conclusion", "") if workflow else ""
        return base


# =============================================================================
# Part 2 — GitHub Actions Integration (Phase 2)
# =============================================================================

class GitHubActionsIntegration:
    """Production GitHub Actions API integration via the GitHub connector."""

    @staticmethod
    def _connector():
        return _get_connector("github")

    @classmethod
    async def list_workflow_runs(cls, owner: str, repo: str, **kwargs) -> List[Dict[str, Any]]:
        conn = cls._connector()
        if conn and conn._available:
            try:
                return await conn.list_workflow_runs(owner, repo, params=kwargs)
            except Exception as e:
                log.warning("GitHub Actions API error: %s", e)
        return []

    @classmethod
    async def get_workflow_run(cls, owner: str, repo: str, run_id: int) -> Optional[Dict[str, Any]]:
        conn = cls._connector()
        if conn and conn._available:
            try:
                return await conn.get_workflow_run(owner, repo, run_id)
            except Exception as e:
                log.warning("GitHub Actions API error: %s", e)
        return None

    @classmethod
    async def list_workflow_jobs(cls, owner: str, repo: str, run_id: int) -> List[Dict[str, Any]]:
        conn = cls._connector()
        if conn and conn._available:
            try:
                check_data = await conn.list_check_runs(owner, repo, str(run_id))
                if isinstance(check_data, dict):
                    return check_data.get("check_runs", [])
            except Exception:
                pass
        return []

    @classmethod
    async def rerun_workflow(cls, owner: str, repo: str, run_id: int) -> bool:
        conn = cls._connector()
        if conn and conn._available:
            try:
                return await conn.rerun_workflow(owner, repo, run_id)
            except Exception as e:
                log.warning("GitHub Actions rerun failed: %s", e)
        return False

    @classmethod
    async def cancel_workflow_run(cls, owner: str, repo: str, run_id: int) -> bool:
        conn = cls._connector()
        if conn and conn._available:
            try:
                return await conn.cancel_workflow_run(owner, repo, run_id)
            except Exception as e:
                log.warning("GitHub Actions cancel failed: %s", e)
        return False

    @classmethod
    async def get_workflow_logs(cls, owner: str, repo: str, run_id: int) -> Optional[str]:
        conn = cls._connector()
        if conn and conn._available:
            try:
                run = await conn.get_workflow_run(owner, repo, run_id)
                if run and isinstance(run, dict) and "logs_url" in run:
                    # Phase 11.1: ``logs_url`` is provider-supplied text that
                    # reached us through a webhook or an API response, so it is
                    # fetched through the outbound guard -- host allow-listed
                    # to GitHub, every redirect hop (GitHub redirects logs to a
                    # signed blob URL) re-judged, connected by pinned address.
                    from backend.safety.outbound_guard import guarded_get
                    resp = await guarded_get(
                        str(run["logs_url"]),
                        allowed_hosts=None,
                        timeout_seconds=30.0,
                    )
                    if resp.status_code == 200:
                        return resp.text
            except Exception as e:
                log.warning("GitHub Actions logs failed: %s", e)
        return None

    @classmethod
    async def list_workflow_artifacts(cls, owner: str, repo: str, run_id: int) -> List[Dict[str, Any]]:
        conn = cls._connector()
        if conn and conn._available:
            try:
                result = await conn._request("GET", f"/repos/{owner}/{repo}/actions/runs/{run_id}/artifacts")
                if isinstance(result, dict):
                    return result.get("artifacts", [])
            except Exception:
                pass
        return []


# =============================================================================
# Part 3 — Jenkins Integration (Phase 3)
# =============================================================================

class JenkinsIntegration:
    """Production Jenkins API integration via the Jenkins connector."""

    @staticmethod
    def _connector():
        return _get_connector("jenkins")

    @classmethod
    async def list_jobs(cls, folder: str = "") -> List[Dict[str, Any]]:
        conn = cls._connector()
        if conn and conn._available:
            try:
                return await conn.list_jobs(folder)
            except Exception as e:
                log.warning("Jenkins API error: %s", e)
        return []

    @classmethod
    async def get_job(cls, job_name: str) -> Optional[Dict[str, Any]]:
        conn = cls._connector()
        if conn and conn._available:
            try:
                return await conn.get_job(job_name)
            except Exception as e:
                log.warning("Jenkins API error: %s", e)
        return None

    @classmethod
    async def list_builds(cls, job_name: str, limit: int = 50) -> List[Dict[str, Any]]:
        conn = cls._connector()
        if conn and conn._available:
            try:
                return await conn.list_builds(job_name, limit)
            except Exception as e:
                log.warning("Jenkins API error: %s", e)
        return []

    @classmethod
    async def get_build(cls, job_name: str, build_number: int) -> Optional[Dict[str, Any]]:
        conn = cls._connector()
        if conn and conn._available:
            try:
                return await conn.get_build(job_name, build_number)
            except Exception as e:
                log.warning("Jenkins API error: %s", e)
        return None

    @classmethod
    async def get_build_log(cls, job_name: str, build_number: int) -> Optional[str]:
        conn = cls._connector()
        if conn and conn._available:
            try:
                return await conn.get_build_log(job_name, build_number)
            except Exception as e:
                log.warning("Jenkins API error: %s", e)
        return None

    @classmethod
    async def get_build_stages(cls, job_name: str, build_number: int) -> List[Dict[str, Any]]:
        conn = cls._connector()
        if conn and conn._available:
            try:
                return await conn.get_build_stages(job_name, build_number)
            except Exception as e:
                log.warning("Jenkins API error: %s", e)
        return []

    @classmethod
    async def build_job(cls, job_name: str, parameters: Optional[Dict[str, str]] = None) -> int:
        conn = cls._connector()
        if conn and conn._available:
            try:
                return await conn.build_job(job_name, parameters)
            except Exception as e:
                log.warning("Jenkins API error: %s", e)
        return 0

    @classmethod
    async def stop_build(cls, job_name: str, build_number: int) -> bool:
        conn = cls._connector()
        if conn and conn._available:
            try:
                return await conn.stop_build(job_name, build_number)
            except Exception as e:
                log.warning("Jenkins API error: %s", e)
        return False

    @classmethod
    async def get_queue(cls) -> List[Dict[str, Any]]:
        conn = cls._connector()
        if conn and conn._available:
            try:
                return await conn.get_queue()
            except Exception as e:
                log.warning("Jenkins API error: %s", e)
        return []

    @classmethod
    async def list_agents(cls) -> List[Dict[str, Any]]:
        conn = cls._connector()
        if conn and conn._available:
            try:
                return await conn.list_agents()
            except Exception as e:
                log.warning("Jenkins API error: %s", e)
        return []

    @classmethod
    async def get_health(cls) -> Dict[str, Any]:
        conn = cls._connector()
        if conn and conn._available:
            try:
                return await conn.get_health()
            except Exception as e:
                log.warning("Jenkins API error: %s", e)
        return {"status": "unknown"}


# =============================================================================
# Part 4 — Azure Pipelines Integration (Phase 4)
# =============================================================================

class AzurePipelinesIntegration:
    """Production Azure DevOps Pipelines API integration."""

    @staticmethod
    def _connector():
        return _get_connector("azure_devops")

    @classmethod
    async def list_pipelines(cls) -> List[Dict[str, Any]]:
        conn = cls._connector()
        if conn and conn._available:
            try:
                return await conn.list_pipelines()
            except Exception as e:
                log.warning("Azure DevOps API error: %s", e)
        return []

    @classmethod
    async def queue_pipeline(cls, pipeline_id: int, **kwargs) -> Optional[Dict[str, Any]]:
        conn = cls._connector()
        if conn and conn._available:
            try:
                return await conn.queue_pipeline(pipeline_id, **kwargs)
            except Exception as e:
                log.warning("Azure DevOps API error: %s", e)
        return None

    @classmethod
    async def get_pipeline_run(cls, pipeline_id: int, run_id: int) -> Optional[Dict[str, Any]]:
        conn = cls._connector()
        if conn and conn._available:
            try:
                return await conn.get_pipeline_run(pipeline_id, run_id)
            except Exception as e:
                log.warning("Azure DevOps API error: %s", e)
        return None

    @classmethod
    async def cancel_pipeline(cls, pipeline_id: int, run_id: int) -> bool:
        conn = cls._connector()
        if conn and conn._available:
            try:
                await conn.cancel_pipeline(pipeline_id, run_id)
                return True
            except Exception as e:
                log.warning("Azure DevOps API error: %s", e)
        return False

    @classmethod
    async def list_repositories(cls) -> List[Dict[str, Any]]:
        conn = cls._connector()
        if conn and conn._available:
            try:
                return await conn.list_repositories()
            except Exception as e:
                log.warning("Azure DevOps API error: %s", e)
        return []


# =============================================================================
# Part 5 — GitLab CI Integration (Phase 5)
# =============================================================================

class GitLabCIIntegration:
    """Production GitLab CI API integration."""

    @staticmethod
    def _connector():
        return _get_connector("gitlab_ci")

    @classmethod
    async def list_projects(cls) -> List[Dict[str, Any]]:
        conn = cls._connector()
        if conn and conn._available:
            try:
                return await conn.list_projects()
            except Exception as e:
                log.warning("GitLab CI API error: %s", e)
        return []

    @classmethod
    async def list_pipelines(cls, project_id: int) -> List[Dict[str, Any]]:
        conn = cls._connector()
        if conn and conn._available:
            try:
                return await conn.list_pipelines(project_id)
            except Exception as e:
                log.warning("GitLab CI API error: %s", e)
        return []

    @classmethod
    async def get_pipeline(cls, project_id: int, pipeline_id: int) -> Optional[Dict[str, Any]]:
        conn = cls._connector()
        if conn and conn._available:
            try:
                return await conn.get_pipeline(project_id, pipeline_id)
            except Exception as e:
                log.warning("GitLab CI API error: %s", e)
        return None

    @classmethod
    async def list_jobs(cls, project_id: int, pipeline_id: int) -> List[Dict[str, Any]]:
        conn = cls._connector()
        if conn and conn._available:
            try:
                return await conn.list_jobs(project_id, pipeline_id)
            except Exception as e:
                log.warning("GitLab CI API error: %s", e)
        return []

    @classmethod
    async def get_job_log(cls, project_id: int, job_id: int) -> Optional[str]:
        conn = cls._connector()
        if conn and conn._available:
            try:
                return await conn.get_job_log(project_id, job_id)
            except Exception as e:
                log.warning("GitLab CI API error: %s", e)
        return None

    @classmethod
    async def retry_pipeline(cls, project_id: int, pipeline_id: int) -> bool:
        conn = cls._connector()
        if conn and conn._available:
            try:
                await conn.retry_pipeline(project_id, pipeline_id)
                return True
            except Exception as e:
                log.warning("GitLab CI API error: %s", e)
        return False

    @classmethod
    async def cancel_pipeline(cls, project_id: int, pipeline_id: int) -> bool:
        conn = cls._connector()
        if conn and conn._available:
            try:
                await conn.cancel_pipeline(project_id, pipeline_id)
                return True
            except Exception as e:
                log.warning("GitLab CI API error: %s", e)
        return False

    @classmethod
    async def list_runners(cls) -> List[Dict[str, Any]]:
        conn = cls._connector()
        if conn and conn._available:
            try:
                return await conn.list_runners()
            except Exception as e:
                log.warning("GitLab CI API error: %s", e)
        return []


# =============================================================================
# Part 6 — CircleCI Integration (Phase 6)
# =============================================================================

class CircleCIIntegration:
    """Production CircleCI API integration."""

    @staticmethod
    def _connector():
        return _get_connector("circleci")

    @classmethod
    async def list_projects(cls) -> List[Dict[str, Any]]:
        conn = cls._connector()
        if conn and conn._available:
            try:
                return await conn.list_projects()
            except Exception as e:
                log.warning("CircleCI API error: %s", e)
        return []

    @classmethod
    async def list_pipelines(cls, project_slug: str) -> List[Dict[str, Any]]:
        conn = cls._connector()
        if conn and conn._available:
            try:
                return await conn.list_pipelines(project_slug)
            except Exception as e:
                log.warning("CircleCI API error: %s", e)
        return []

    @classmethod
    async def get_pipeline(cls, pipeline_id: str) -> Optional[Dict[str, Any]]:
        conn = cls._connector()
        if conn and conn._available:
            try:
                return await conn.get_pipeline(pipeline_id)
            except Exception as e:
                log.warning("CircleCI API error: %s", e)
        return None

    @classmethod
    async def list_workflows(cls, pipeline_id: str) -> List[Dict[str, Any]]:
        conn = cls._connector()
        if conn and conn._available:
            try:
                return await conn.list_workflows(pipeline_id)
            except Exception as e:
                log.warning("CircleCI API error: %s", e)
        return []

    @classmethod
    async def get_workflow(cls, workflow_id: str) -> Optional[Dict[str, Any]]:
        conn = cls._connector()
        if conn and conn._available:
            try:
                return await conn.get_workflow(workflow_id)
            except Exception as e:
                log.warning("CircleCI API error: %s", e)
        return None

    @classmethod
    async def get_job_artifacts(cls, job_number: int, project_slug: str) -> List[Dict[str, Any]]:
        conn = cls._connector()
        if conn and conn._available:
            try:
                return await conn.get_job_artifacts(job_number, project_slug)
            except Exception as e:
                log.warning("CircleCI API error: %s", e)
        return []

    @classmethod
    async def get_project_insights(cls, project_slug: str) -> Dict[str, Any]:
        conn = cls._connector()
        if conn and conn._available:
            try:
                return await conn.get_project_insights(project_slug)
            except Exception as e:
                log.warning("CircleCI API error: %s", e)
        return {}


# =============================================================================
# Part 7 — Build Intelligence (Phase 8)
# =============================================================================

class BuildIntelligence:
    """Multi-platform build tracking, trend analysis, flaky detection, ownership."""

    @staticmethod
    def list_builds(platform: str = "", status: str = "", limit: int = 100) -> List[Dict[str, Any]]:
        builds = _load_json(_BUILDS_FILE)
        result = builds
        if platform:
            result = [b for b in result if b.get("platform") == platform]
        if status:
            result = [b for b in result if b.get("status") == status]
        return result[:limit]

    @staticmethod
    def get_build(build_id: str) -> Optional[Dict[str, Any]]:
        for b in _load_json(_BUILDS_FILE):
            if b.get("build_id") == build_id:
                return b
        return None

    @staticmethod
    def track_build(platform: str, build_data: Dict[str, Any]) -> Dict[str, Any]:
        builds = _load_json(_BUILDS_FILE)
        build_id = build_data.get("build_id", _id("bld"))
        for i, b in enumerate(builds):
            if b.get("build_id") == build_id:
                builds[i].update(build_data)
                builds[i]["updated_at"] = _now()
                break
        else:
            build_data["build_id"] = build_id
            build_data["platform"] = platform
            build_data["created_at"] = _now()
            build_data["updated_at"] = _now()
            builds.insert(0, build_data)
        _save_json(_BUILDS_FILE, builds)
        _sync_build_to_runtime(build_data)
        build_data["build_id"] = build_id
        return build_data

    @staticmethod
    def get_dashboard_stats() -> Dict[str, Any]:
        builds = _load_json(_BUILDS_FILE)
        total = len(builds)
        passed = sum(1 for b in builds if b.get("status") == "passed" or b.get("conclusion") == "success")
        failed = sum(1 for b in builds if b.get("status") == "failed" or b.get("conclusion") == "failure")
        running = sum(1 for b in builds if b.get("status") in ("running", "in_progress"))
        return {"total_builds": total, "passed": passed, "failed": failed, "running": running}

    @staticmethod
    def analyze_trends(limit: int = 50) -> Dict[str, Any]:
        builds = _load_json(_BUILDS_FILE)[:limit]
        if len(builds) < 5:
            return {"trend": "insufficient_data", "pass_rate": 0.0, "sample_size": len(builds)}
        passed = sum(1 for b in builds if b.get("status") == "passed" or b.get("conclusion") == "success")
        rate = passed / max(len(builds), 1)
        mid = len(builds) // 2
        first_half = builds[:mid]
        second_half = builds[mid:]
        fh_rate = sum(1 for b in first_half if b.get("status") == "passed" or b.get("conclusion") == "success") / max(len(first_half), 1)
        sh_rate = sum(1 for b in second_half if b.get("status") == "passed" or b.get("conclusion") == "success") / max(len(second_half), 1)
        if sh_rate > fh_rate + 0.05:
            trend = "improving"
        elif sh_rate < fh_rate - 0.05:
            trend = "declining"
        else:
            trend = "stable"
        return {"trend": trend, "pass_rate": round(rate, 3), "sample_size": len(builds)}

    @staticmethod
    def get_flaky_builds(min_runs: int = 5, threshold: float = 0.3) -> List[Dict[str, Any]]:
        builds = _load_json(_BUILDS_FILE)
        by_name: Dict[str, List[Dict[str, Any]]] = {}
        for b in builds:
            name = b.get("workflow_name", b.get("name", "unknown"))
            by_name.setdefault(name, []).append(b)
        flaky: List[Dict[str, Any]] = []
        for name, runs in by_name.items():
            if len(runs) < min_runs:
                continue
            outcomes = [1 for r in runs if r.get("status") == "passed" or r.get("conclusion") == "success"]
            flakiness = 1.0 - (len(outcomes) / len(runs))
            if flakiness >= threshold:
                flaky.append({
                    "name": name,
                    "total_runs": len(runs),
                    "pass_count": len(outcomes),
                    "fail_count": len(runs) - len(outcomes),
                    "flakiness": round(flakiness, 3),
                })
        flaky.sort(key=lambda x: -x["flakiness"])
        return flaky

    @staticmethod
    def get_build_ownership() -> Dict[str, Any]:
        builds = _load_json(_BUILDS_FILE)
        by_sender: Dict[str, int] = {}
        by_platform: Dict[str, int] = {}
        for b in builds:
            sender = b.get("sender", "unknown")
            by_sender[sender] = by_sender.get(sender, 0) + 1
            platform = b.get("platform", "unknown")
            by_platform[platform] = by_platform.get(platform, 0) + 1
        top_senders = sorted(by_sender.items(), key=lambda x: -x[1])[:10]
        return {
            "total_senders": len(by_sender),
            "top_senders": [{"sender": s, "count": c} for s, c in top_senders],
            "by_platform": by_platform,
        }

    @staticmethod
    def get_repository_stats() -> Dict[str, Any]:
        builds = _load_json(_BUILDS_FILE)
        by_repo: Dict[str, Dict[str, Any]] = {}
        for b in builds:
            repo = b.get("repository", "unknown")
            if repo not in by_repo:
                by_repo[repo] = {"total": 0, "passed": 0, "failed": 0, "running": 0}
            by_repo[repo]["total"] += 1
            status = b.get("status", b.get("conclusion", ""))
            if status in ("passed", "success"):
                by_repo[repo]["passed"] += 1
            elif status in ("failed", "failure"):
                by_repo[repo]["failed"] += 1
            else:
                by_repo[repo]["running"] += 1
        return by_repo

    @staticmethod
    def get_average_duration(limit: int = 100) -> Dict[str, Any]:
        builds = _load_json(_BUILDS_FILE)[:limit]
        durations = [b.get("duration", 0) or b.get("duration_ms", 0) for b in builds if b.get("duration") or b.get("duration_ms")]
        if not durations:
            return {"average_duration_ms": 0, "total_sampled": 0}
        return {
            "average_duration_ms": round(sum(durations) / len(durations), 1),
            "min_duration_ms": min(durations),
            "max_duration_ms": max(durations),
            "total_sampled": len(durations),
        }


# =============================================================================
# Part 8 — Deployment Intelligence
# =============================================================================

class DeploymentIntelligence:
    """Deployment analysis across environments using existing DeploymentEngine."""

    @staticmethod
    def list_deployments(environment: str = "", status: str = "", limit: int = 100) -> List[Dict[str, Any]]:
        deps = _load_json(_DEPLOYMENTS_FILE)
        result = deps
        if environment:
            result = [d for d in result if d.get("environment") == environment]
        if status:
            result = [d for d in result if d.get("status") == status]
        return result[:limit]

    @staticmethod
    def get_deployment(deployment_id: str) -> Optional[Dict[str, Any]]:
        for d in _load_json(_DEPLOYMENTS_FILE):
            if d.get("deployment_id") == deployment_id:
                return d
        return None

    @staticmethod
    def track_deployment(platform: str, deploy_data: Dict[str, Any]) -> Dict[str, Any]:
        deployments = _load_json(_DEPLOYMENTS_FILE)
        dep_id = deploy_data.get("deployment_id", _id("dep"))
        for i, d in enumerate(deployments):
            if d.get("deployment_id") == dep_id:
                deployments[i].update(deploy_data)
                deployments[i]["updated_at"] = _now()
                break
        else:
            deploy_data["deployment_id"] = dep_id
            deploy_data["platform"] = platform
            deploy_data["created_at"] = _now()
            deploy_data["updated_at"] = _now()
            deployments.insert(0, deploy_data)
        _save_json(_DEPLOYMENTS_FILE, deployments)
        _sync_deploy_to_runtime(deploy_data)
        deploy_data["deployment_id"] = dep_id
        return deploy_data

    @staticmethod
    def get_dashboard_stats() -> Dict[str, Any]:
        deps = _load_json(_DEPLOYMENTS_FILE)
        total = len(deps)
        success = sum(1 for d in deps if d.get("status") in ("deployed", "success"))
        failed = sum(1 for d in deps if d.get("status") in ("failed", "failure"))
        rolled_back = sum(1 for d in deps if d.get("status") == "rolled_back")
        return {"total_deployments": total, "success": success, "failed": failed, "rolled_back": rolled_back}

    @staticmethod
    def environment_health() -> Dict[str, Any]:
        deps = _load_json(_DEPLOYMENTS_FILE)
        envs: Dict[str, List[Dict[str, Any]]] = {}
        for d in deps:
            env = d.get("environment", "unknown")
            if env not in envs:
                envs[env] = []
            envs[env].append(d)
        result: Dict[str, Any] = {}
        for env, deployments in envs.items():
            latest = deployments[0] if deployments else {}
            status = "unknown"
            if latest.get("status") in ("deployed", "success"):
                status = "healthy"
            elif latest.get("status") in ("failed", "failure"):
                status = "degraded"
            elif latest.get("status") == "rolled_back":
                status = "recovering"
            result[env] = {
                "status": status,
                "last_deployment_id": latest.get("deployment_id", ""),
                "last_updated": latest.get("updated_at", ""),
                "total": len(deployments),
                "success": sum(1 for d in deployments if d.get("status") in ("deployed", "success")),
                "failed": sum(1 for d in deployments if d.get("status") in ("failed", "failure")),
            }
        return result


# =============================================================================
# Part 9 — Artifact Intelligence (Phase 7)
# =============================================================================

class ArtifactIntelligence:
    """Track build artifacts: Docker, Helm, ZIP, JAR, NPM, wheels, NuGet, OCI.
    Supports version lineage, artifact dependencies, and promotion."""

    ARTIFACT_TYPES = ["docker_image", "helm_chart", "zip", "jar", "npm_package", "python_wheel", "nuget_package", "oci_artifact"]

    @staticmethod
    def list_artifacts(artifact_type: str = "", build_id: str = "", limit: int = 100) -> List[Dict[str, Any]]:
        artifacts = _load_json(_ARTIFACTS_FILE)
        result = artifacts
        if artifact_type:
            result = [a for a in result if a.get("artifact_type") == artifact_type]
        if build_id:
            result = [a for a in result if a.get("build_id") == build_id]
        return result[:limit]

    @staticmethod
    def get_artifact(artifact_id: str) -> Optional[Dict[str, Any]]:
        for a in _load_json(_ARTIFACTS_FILE):
            if a.get("artifact_id") == artifact_id:
                return a
        return None

    @staticmethod
    def track_artifact(artifact_data: Dict[str, Any]) -> Dict[str, Any]:
        artifacts = _load_json(_ARTIFACTS_FILE)
        art_id = artifact_data.get("artifact_id", _id("art"))
        for i, a in enumerate(artifacts):
            if a.get("artifact_id") == art_id:
                artifacts[i].update(artifact_data)
                artifacts[i]["updated_at"] = _now()
                break
        else:
            artifact_data["artifact_id"] = art_id
            artifact_data["created_at"] = _now()
            artifact_data["updated_at"] = _now()
            artifacts.insert(0, artifact_data)
        _save_json(_ARTIFACTS_FILE, artifacts)
        _sync_artifact_to_runtime(artifact_data)
        artifact_data["artifact_id"] = art_id
        return artifact_data

    @staticmethod
    def get_dashboard_stats() -> Dict[str, Any]:
        arts = _load_json(_ARTIFACTS_FILE)
        by_type: Dict[str, int] = {}
        for a in arts:
            at = a.get("artifact_type", "generic")
            by_type[at] = by_type.get(at, 0) + 1
        return {
            "total_artifacts": len(arts),
            "by_type": by_type,
        }

    @staticmethod
    def get_version_lineage(artifact_name: str) -> List[Dict[str, Any]]:
        arts = _load_json(_ARTIFACTS_FILE)
        lineage = [a for a in arts if a.get("name") == artifact_name or a.get("package_name") == artifact_name]
        lineage.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        versions = []
        for a in lineage:
            versions.append({
                "version": a.get("version", "unknown"),
                "artifact_id": a.get("artifact_id", ""),
                "created_at": a.get("created_at", ""),
                "promoted": a.get("promoted", False),
                "environment": a.get("environment", ""),
            })
        return versions

    @staticmethod
    def get_artifact_dependencies(artifact_id: str) -> List[Dict[str, Any]]:
        art = ArtifactIntelligence.get_artifact(artifact_id)
        if not art:
            return []
        return art.get("dependencies", [])

    @staticmethod
    def promote_artifact(artifact_id: str, target_environment: str) -> Optional[Dict[str, Any]]:
        artifacts = _load_json(_ARTIFACTS_FILE)
        for a in artifacts:
            if a.get("artifact_id") == artifact_id:
                a["promoted"] = True
                a["environment"] = target_environment
                a["promoted_at"] = _now()
                a["updated_at"] = _now()
                _save_json(_ARTIFACTS_FILE, artifacts)
                _sync_artifact_to_runtime(a)
                return a
        return None

    @staticmethod
    def list_artifacts_by_environment(environment: str) -> List[Dict[str, Any]]:
        arts = _load_json(_ARTIFACTS_FILE)
        return [a for a in arts if a.get("environment") == environment]


# =============================================================================
# Part 10 — Pipeline Timeline
# =============================================================================

class PipelineTimeline:
    """Build aggregated timelines from pipeline runs, builds, deployments."""

    @staticmethod
    def build_timeline(pipeline_id: str = "", limit: int = 50) -> List[Dict[str, Any]]:
        entries: List[Dict[str, Any]] = []
        for build in _load_json(_BUILDS_FILE)[:10]:
            entries.append({
                "source": "build", "entity_id": build.get("build_id", ""),
                "platform": build.get("platform", ""), "name": build.get("workflow_name", build.get("name", "Build")),
                "status": build.get("status", build.get("conclusion", "")),
                "timestamp": build.get("updated_at", build.get("created_at", "")),
                "repository": build.get("repository", ""), "branch": build.get("head_branch", ""),
            })
        for dep in _load_json(_DEPLOYMENTS_FILE)[:10]:
            entries.append({
                "source": "deployment", "entity_id": dep.get("deployment_id", ""),
                "platform": dep.get("platform", ""), "name": f"Deploy to {dep.get('environment', '?')}",
                "status": dep.get("status", ""),
                "timestamp": dep.get("updated_at", dep.get("created_at", "")),
                "repository": dep.get("repository", ""),
            })
        for art in _load_json(_ARTIFACTS_FILE)[:10]:
            entries.append({
                "source": "artifact", "entity_id": art.get("artifact_id", ""),
                "platform": art.get("platform", ""), "name": art.get("name", art.get("artifact_type", "Artifact")),
                "status": "published",
                "timestamp": art.get("updated_at", art.get("created_at", "")),
                "repository": art.get("repository", ""),
            })
        entries.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        return entries[:limit]

    @staticmethod
    def get_pipeline_dashboard() -> Dict[str, Any]:
        builds = _load_json(_BUILDS_FILE)
        deps = _load_json(_DEPLOYMENTS_FILE)
        arts = _load_json(_ARTIFACTS_FILE)
        return {
            "total_pipelines": len(builds) + len(deps),
            "recent_builds": len(builds[:10]),
            "recent_deployments": len(deps[:10]),
            "recent_artifacts": len(arts[:10]),
        }


# =============================================================================
# Part 11 — Failure Analysis
# =============================================================================

class FailureAnalysis:
    """Analyze failed builds/deployments for root causes."""

    COMMON_FAILURE_PATTERNS = [
        (r"(?i)(timeout|timed.?out)", "timeout", "Build or deployment exceeded time limit"),
        (r"(?i)(out of memory|oom|memory limit)", "oom", "Out of memory error"),
        (r"(?i)(compil|syntax error|build error)", "compilation", "Compilation or syntax error"),
        (r"(?i)(test fail|test.*failed|failing test)", "test_failure", "One or more tests failed"),
        (r"(?i)(docker|container.*error|image.*not found)", "docker", "Docker or container error"),
        (r"(?i)(dependency|package.*not found|could not resolve)", "dependency", "Missing or unresolved dependency"),
        (r"(?i)(permission|access denied|unauthorized|forbidden)", "permission", "Permission or access denied"),
        (r"(?i)(network|connection refused|dns|host.*unreachable)", "network", "Network connectivity error"),
        (r"(?i)(config|misconfig|invalid.*config)", "configuration", "Configuration error"),
        (r"(?i)(disk full|no space)", "disk_space", "Insufficient disk space"),
        (r"(?i)(lint|format|style)", "lint", "Linting or formatting issue"),
        (r"(?i)(rollback|revert)", "rollback", "Rollback was triggered"),
    ]

    @staticmethod
    def list_failures(entity_type: str = "", limit: int = 100) -> List[Dict[str, Any]]:
        failures = _load_json(_FAILURES_FILE)
        if entity_type:
            return [f for f in failures if f.get("entity_type") == entity_type][:limit]
        return failures[:limit]

    @staticmethod
    def get_failure(failure_id: str) -> Optional[Dict[str, Any]]:
        for f in _load_json(_FAILURES_FILE):
            if f.get("failure_id") == failure_id:
                return f
        return None

    @staticmethod
    def analyze_failure(entity_id: str, entity_type: str, logs: List[str], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        combined = " ".join(logs)
        matched: List[Dict[str, Any]] = []
        for pattern, category, description in FailureAnalysis.COMMON_FAILURE_PATTERNS:
            if re.search(pattern, combined):
                matched.append({"category": category, "description": description})
        if not matched:
            matched.append({"category": "unknown", "description": "Could not determine root cause"})
        failure: Dict[str, Any] = {
            "failure_id": _id("fail"),
            "entity_id": entity_id,
            "entity_type": entity_type,
            "root_causes": matched,
            "log_sample": logs[:20],
            "analyzed_at": _now(),
        }
        if context:
            failure["context"] = context
        failures = _load_json(_FAILURES_FILE)
        failures.insert(0, failure)
        _save_json(_FAILURES_FILE, failures)

        try:
            from backend.services.enterprise_analytics_service import analytics_service
            for cause in matched:
                analytics_service.record_metric(
                    metric_type="failure",
                    metric_name=f"failure.{cause['category']}",
                    value=1,
                    labels={"entity_type": entity_type, "category": cause["category"]},
                )
        except Exception:
            pass

        return failure

    @staticmethod
    def get_dashboard_stats() -> Dict[str, Any]:
        failures = _load_json(_FAILURES_FILE)
        total = len(failures)
        by_category: Dict[str, int] = {}
        for f in failures:
            for rc in f.get("root_causes", []):
                cat = rc.get("category", "unknown")
                by_category[cat] = by_category.get(cat, 0) + 1
        top_causes = sorted(by_category.items(), key=lambda x: -x[1])[:5]
        return {"total_failures": total, "top_causes": [{"category": c, "count": n} for c, n in top_causes]}


# =============================================================================
# Part 12 — Deployment Recovery
# =============================================================================

class DeploymentRecovery:
    """Coordinated recovery and rollback for failed deployments."""

    RECOVERY_STRATEGIES = ["rollback", "retry", "rollback_rollback"]

    @staticmethod
    def list_recoveries(limit: int = 100) -> List[Dict[str, Any]]:
        return _load_json(_RECOVERIES_FILE)[:limit]

    @staticmethod
    def get_recovery(recovery_id: str) -> Optional[Dict[str, Any]]:
        for r in _load_json(_RECOVERIES_FILE):
            if r.get("recovery_id") == recovery_id:
                return r
        return None

    @staticmethod
    def recommend_strategy(failed_deployment: Dict[str, Any], failure: Dict[str, Any]) -> str:
        root_causes = [c.get("category", "") for c in failure.get("root_causes", [])]
        if "configuration" in root_causes or "dependency" in root_causes:
            return "retry"
        if "rollback" in root_causes:
            return "rollback_rollback"
        return "rollback"

    @staticmethod
    async def recover(
        deployment_id: str,
        strategy: str = "",
        initiated_by: str = "system",
    ) -> Dict[str, Any]:
        recovery_id = _id("rec")
        recovery: Dict[str, Any] = {
            "recovery_id": recovery_id,
            "deployment_id": deployment_id,
            "strategy": strategy,
            "status": "started",
            "initiated_by": initiated_by,
            "started_at": _now(),
        }

        try:
            from backend.services.enterprise_deployment_engine import deployment_engine

            if strategy == "rollback":
                result = await deployment_engine.rollback_deployment(deployment_id)
                recovery["status"] = "completed" if result else "failed"
                recovery["result"] = result
                recovery["message"] = "Rollback executed via DeploymentEngine"
            elif strategy == "retry":
                result = await deployment_engine.rollback_deployment(deployment_id)
                recovery["status"] = "completed" if result else "failed"
                recovery["result"] = result
                recovery["message"] = "Rolled back for retry"
            elif strategy == "rollback_rollback":
                recovery["status"] = "completed"
                recovery["message"] = "Original deployment was already a rollback; no further action needed"
            else:
                recovery["status"] = "skipped"
                recovery["message"] = f"No recognized recovery strategy: {strategy}"
        except Exception as exc:
            recovery["status"] = "failed"
            recovery["error"] = str(exc)
            log.warning("Recovery failed for %s: %s", deployment_id, exc)

        recovery["completed_at"] = _now()

        recoveries = _load_json(_RECOVERIES_FILE)
        recoveries.insert(0, recovery)
        _save_json(_RECOVERIES_FILE, recoveries)

        return recovery

    @staticmethod
    def get_dashboard_stats() -> Dict[str, Any]:
        recoveries = _load_json(_RECOVERIES_FILE)
        total = len(recoveries)
        completed = sum(1 for r in recoveries if r.get("status") == "completed")
        failed = sum(1 for r in recoveries if r.get("status") == "failed")
        return {"total_recoveries": total, "completed": completed, "failed": failed}


# =============================================================================
# Part 13 — CiCdIntegrationService Orchestrator (Phase 9 — Event Stream)
# =============================================================================

class CiCdIntegrationService:
    """Orchestrator coordinating all CI/CD intelligence subsystems with real connectors."""

    def __init__(self) -> None:
        pass

    # ---- webhook ingestion ----

    async def ingest_pipeline_event(self, event_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        parsed = CiCdPlatformManager.parse_pipeline_event(event_type, payload)
        platform = parsed["platform"]
        status = parsed.get("status", "unknown")
        conclusion = parsed.get("conclusion", "")

        pipeline_entry: Dict[str, Any] = {
            "pipeline_id": _id("pipe"),
            "platform": platform,
            "event_type": event_type,
            "workflow_name": parsed.get("workflow_name", "Unnamed Pipeline"),
            "repository": parsed.get("repository", ""),
            "sender": parsed.get("sender", ""),
            "head_branch": parsed.get("head_branch", ""),
            "head_sha": parsed.get("head_sha", ""),
            "status": status,
            "conclusion": conclusion,
            "run_number": parsed.get("run_number", ""),
        }

        is_failure = conclusion in ("failure", "error", "cancelled", "timed_out")
        if status in ("completed", "success") and not is_failure:
            pipeline_entry["status"] = "passed"
            await self._emit(CICD_EVENTS["pipeline_completed"], pipeline_entry["pipeline_id"], pipeline_entry)
        elif status in ("completed", "failed", "failure", "error", "cancelled", "timed_out") or is_failure:
            pipeline_entry["status"] = "failed"
            await self._emit(CICD_EVENTS["pipeline_failed"], pipeline_entry["pipeline_id"], pipeline_entry)
        elif status in ("running", "in_progress", "queued", "pending"):
            pipeline_entry["status"] = "running"
            await self._emit(CICD_EVENTS["pipeline_started"], pipeline_entry["pipeline_id"], pipeline_entry)
        else:
            await self._emit(CICD_EVENTS["pipeline_created"], pipeline_entry["pipeline_id"], pipeline_entry)

        build_result = BuildIntelligence.track_build(platform, {
            **pipeline_entry,
            "name": pipeline_entry["workflow_name"],
        })
        pipeline_entry["build_id"] = build_result.get("build_id", "")

        return pipeline_entry

    async def ingest_build_event(self, platform: str, build_data: Dict[str, Any]) -> Dict[str, Any]:
        result = BuildIntelligence.track_build(platform, build_data)
        status = build_data.get("status", build_data.get("conclusion", ""))
        if status in ("passed", "success", "completed"):
            await self._emit(CICD_EVENTS["build_completed"], result.get("build_id", ""), result)
        elif status in ("failed", "failure", "error"):
            await self._emit(CICD_EVENTS["build_failed"], result.get("build_id", ""), result)
            logs = build_data.get("logs", [])
            if logs:
                analysis = FailureAnalysis.analyze_failure(
                    entity_id=result.get("build_id", ""),
                    entity_type="build",
                    logs=logs if isinstance(logs, list) else [str(logs)],
                    context={"platform": platform, "repository": build_data.get("repository", "")},
                )
                await self._emit(CICD_EVENTS["failure_analyzed"], analysis["failure_id"], analysis)
        else:
            await self._emit(CICD_EVENTS["build_started"], result.get("build_id", ""), result)
        return result

    async def ingest_deployment_event(self, platform: str, deploy_data: Dict[str, Any]) -> Dict[str, Any]:
        result = DeploymentIntelligence.track_deployment(platform, deploy_data)
        status = deploy_data.get("status", "")
        if status in ("deployed", "success", "completed"):
            await self._emit(CICD_EVENTS["deployment_completed"], result.get("deployment_id", ""), result)
        elif status in ("failed", "failure", "error"):
            await self._emit(CICD_EVENTS["deployment_failed"], result.get("deployment_id", ""), result)
            logs = deploy_data.get("logs", [])
            if logs:
                analysis = FailureAnalysis.analyze_failure(
                    entity_id=result.get("deployment_id", ""),
                    entity_type="deployment",
                    logs=logs if isinstance(logs, list) else [str(logs)],
                    context={"platform": platform, "environment": deploy_data.get("environment", "")},
                )
                await self._emit(CICD_EVENTS["failure_analyzed"], analysis["failure_id"], analysis)
        else:
            await self._emit(CICD_EVENTS["deployment_started"], result.get("deployment_id", ""), result)
        return result

    async def ingest_artifact_event(self, artifact_data: Dict[str, Any]) -> Dict[str, Any]:
        result = ArtifactIntelligence.track_artifact(artifact_data)
        await self._emit(CICD_EVENTS["artifact_published"], result.get("artifact_id", ""), result)
        return result

    async def handle_failure_and_recover(self, entity_id: str, entity_type: str, logs: List[str], strategy: str = "") -> Dict[str, Any]:
        failure = FailureAnalysis.analyze_failure(entity_id, entity_type, logs)
        await self._emit(CICD_EVENTS["failure_analyzed"], failure["failure_id"], failure)

        if entity_type == "build":
            return {"failure": failure, "recovery": None, "note": "Build failures should be retried via Engineering Executive"}

        dep = DeploymentIntelligence.get_deployment(entity_id)
        if not dep:
            return {"failure": failure, "recovery": None, "note": "No deployment found for recovery"}

        if not strategy:
            strategy = DeploymentRecovery.recommend_strategy(dep, failure)
        await self._emit(CICD_EVENTS["recovery_started"], entity_id, {"strategy": strategy})
        recovery = await DeploymentRecovery.recover(entity_id, strategy=strategy)
        await self._emit(CICD_EVENTS["recovery_completed"], recovery.get("recovery_id", ""), recovery)
        if recovery.get("status") == "completed":
            await self._emit(CICD_EVENTS["deployment_recovered"], entity_id, recovery)

        return {"failure": failure, "recovery": recovery}

    # ---- Connector-based methods ----

    async def fetch_github_actions_runs(self, owner: str, repo: str, **kwargs) -> List[Dict[str, Any]]:
        return await GitHubActionsIntegration.list_workflow_runs(owner, repo, **kwargs)

    async def fetch_github_actions_jobs(self, owner: str, repo: str, run_id: int) -> List[Dict[str, Any]]:
        return await GitHubActionsIntegration.list_workflow_jobs(owner, repo, run_id)

    async def rerun_github_workflow(self, owner: str, repo: str, run_id: int) -> bool:
        return await GitHubActionsIntegration.rerun_workflow(owner, repo, run_id)

    async def cancel_github_workflow(self, owner: str, repo: str, run_id: int) -> bool:
        return await GitHubActionsIntegration.cancel_workflow_run(owner, repo, run_id)

    async def fetch_jenkins_jobs(self, folder: str = "") -> List[Dict[str, Any]]:
        return await JenkinsIntegration.list_jobs(folder)

    async def fetch_jenkins_builds(self, job_name: str, limit: int = 50) -> List[Dict[str, Any]]:
        return await JenkinsIntegration.list_builds(job_name, limit)

    async def build_jenkins_job(self, job_name: str, parameters: Optional[Dict[str, str]] = None) -> int:
        return await JenkinsIntegration.build_job(job_name, parameters)

    async def fetch_azure_pipelines(self) -> List[Dict[str, Any]]:
        return await AzurePipelinesIntegration.list_pipelines()

    async def queue_azure_pipeline(self, pipeline_id: int, **kwargs) -> Optional[Dict[str, Any]]:
        return await AzurePipelinesIntegration.queue_pipeline(pipeline_id, **kwargs)

    async def fetch_gitlab_pipelines(self, project_id: int) -> List[Dict[str, Any]]:
        return await GitLabCIIntegration.list_pipelines(project_id)

    async def fetch_gitlab_jobs(self, project_id: int, pipeline_id: int) -> List[Dict[str, Any]]:
        return await GitLabCIIntegration.list_jobs(project_id, pipeline_id)

    async def fetch_circleci_pipelines(self, project_slug: str) -> List[Dict[str, Any]]:
        return await CircleCIIntegration.list_pipelines(project_slug)

    async def fetch_circleci_workflows(self, pipeline_id: str) -> List[Dict[str, Any]]:
        return await CircleCIIntegration.list_workflows(pipeline_id)

    # ---- dashboard ----

    def get_dashboard(self) -> Dict[str, Any]:
        return {
            **BuildIntelligence.get_dashboard_stats(),
            **DeploymentIntelligence.get_dashboard_stats(),
            **ArtifactIntelligence.get_dashboard_stats(),
            **FailureAnalysis.get_dashboard_stats(),
            **DeploymentRecovery.get_dashboard_stats(),
            **PipelineTimeline.get_pipeline_dashboard(),
        }

    def get_timeline(self, limit: int = 50) -> List[Dict[str, Any]]:
        return PipelineTimeline.build_timeline(limit=limit)

    # ---- event emission (Phase 9) ----

    async def _emit(self, event_type: str, entity_id: str, data: Dict[str, Any]) -> None:
        try:
            from backend.services.enterprise_event_hub import enterprise_hub
            await enterprise_hub.emit(event_type=event_type, agent="cicd_intelligence", data=data)
        except Exception as exc:
            log.debug("Emit skipped for %s: %s", event_type, exc)

    async def _emit_to_all(self, event_type: str, data: Dict[str, Any]) -> None:
        try:
            from backend.services.enterprise_event_hub import enterprise_hub
            enriched = {**data, "emitted_at": _now()}
            await enterprise_hub.emit(event_type=event_type, agent="cicd_intelligence", data=enriched)
        except Exception as exc:
            log.debug("Multi-emit skipped: %s", exc)

    # ---- state management ----

    def clear_state(self) -> None:
        for path in [_PIPELINES_FILE, _BUILDS_FILE, _DEPLOYMENTS_FILE, _ARTIFACTS_FILE, _TIMELINES_FILE, _FAILURES_FILE, _RECOVERIES_FILE]:
            _save_json(path, [])


cicd_intelligence = CiCdIntegrationService()
