"""
Enterprise CI/CD & Deployment Intelligence — REST API.

Ingestion endpoints + CRUD for all 7 CI/CD subsystems.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from backend.services.enterprise_cicd_intelligence import (
    CICD_EVENTS,
    SUPPORTED_PLATFORMS,
    ArtifactIntelligence,
    BuildIntelligence,
    DeploymentIntelligence,
    DeploymentRecovery,
    FailureAnalysis,
    cicd_intelligence,
)

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/cicd", tags=["Enterprise CI/CD Intelligence"])


# ---- Request schemas ----

class IngestPipelineRequest(BaseModel):
    event_type: str
    payload: Dict[str, Any]


class IngestBuildRequest(BaseModel):
    platform: str = "github_actions"
    build_data: Dict[str, Any]


class IngestDeploymentRequest(BaseModel):
    platform: str = "github_actions"
    deploy_data: Dict[str, Any]


class IngestArtifactRequest(BaseModel):
    artifact_data: Dict[str, Any]


class FailRecoverRequest(BaseModel):
    entity_id: str
    entity_type: str
    logs: List[str] = []
    strategy: str = ""


# ---- Ingestion ----

@router.post("/ingest/pipeline")
async def ingest_pipeline(body: IngestPipelineRequest):
    try:
        result = await cicd_intelligence.ingest_pipeline_event(body.event_type, body.payload)
        return result
    except Exception as exc:
        raise HTTPException(502, f"Pipeline ingestion failed: {exc}")


@router.post("/ingest/build")
async def ingest_build(body: IngestBuildRequest):
    try:
        result = await cicd_intelligence.ingest_build_event(body.platform, body.build_data)
        return result
    except Exception as exc:
        raise HTTPException(502, f"Build ingestion failed: {exc}")


@router.post("/ingest/deployment")
async def ingest_deployment(body: IngestDeploymentRequest):
    try:
        result = await cicd_intelligence.ingest_deployment_event(body.platform, body.deploy_data)
        return result
    except Exception as exc:
        raise HTTPException(502, f"Deployment ingestion failed: {exc}")


@router.post("/ingest/artifact")
async def ingest_artifact(body: IngestArtifactRequest):
    try:
        result = await cicd_intelligence.ingest_artifact_event(body.artifact_data)
        return result
    except Exception as exc:
        raise HTTPException(502, f"Artifact ingestion failed: {exc}")


@router.post("/failure-recover")
async def failure_and_recover(body: FailRecoverRequest):
    try:
        result = await cicd_intelligence.handle_failure_and_recover(
            entity_id=body.entity_id,
            entity_type=body.entity_type,
            logs=body.logs,
            strategy=body.strategy,
        )
        return result
    except Exception as exc:
        raise HTTPException(502, f"Failure handling failed: {exc}")


# ---- Dashboard ----

@router.get("/dashboard")
async def dashboard():
    try:
        return cicd_intelligence.get_dashboard()
    except Exception as exc:
        raise HTTPException(502, str(exc))


@router.get("/timeline")
async def timeline(limit: int = Query(50, ge=1, le=200)):
    try:
        return {"timeline": cicd_intelligence.get_timeline(limit)}
    except Exception as exc:
        raise HTTPException(502, str(exc))


# ---- Builds ----

@router.get("/builds")
async def list_builds(
    platform: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
):
    try:
        builds = BuildIntelligence.list_builds(platform=platform or "", status=status or "", limit=limit)
        return {"builds": builds}
    except Exception as exc:
        raise HTTPException(502, str(exc))


@router.get("/builds/{build_id}")
async def get_build(build_id: str):
    build = BuildIntelligence.get_build(build_id)
    if build is None:
        raise HTTPException(404, "Build not found")
    return build


@router.get("/builds/stats/trends")
async def build_trends():
    try:
        return BuildIntelligence.analyze_trends()
    except Exception as exc:
        raise HTTPException(502, str(exc))


# ---- Deployments ----

@router.get("/deployments")
async def list_deployments(
    environment: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
):
    try:
        deps = DeploymentIntelligence.list_deployments(environment=environment or "", status=status or "", limit=limit)
        return {"deployments": deps}
    except Exception as exc:
        raise HTTPException(502, str(exc))


@router.get("/deployments/{deployment_id}")
async def get_deployment(deployment_id: str):
    dep = DeploymentIntelligence.get_deployment(deployment_id)
    if dep is None:
        raise HTTPException(404, "Deployment not found")
    return dep


@router.get("/deployments/environments/health")
async def environment_health():
    try:
        return {"environments": DeploymentIntelligence.environment_health()}
    except Exception as exc:
        raise HTTPException(502, str(exc))


# ---- Artifacts ----

@router.get("/artifacts")
async def list_artifacts(
    artifact_type: Optional[str] = Query(None),
    build_id: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
):
    try:
        arts = ArtifactIntelligence.list_artifacts(artifact_type=artifact_type or "", build_id=build_id or "", limit=limit)
        return {"artifacts": arts}
    except Exception as exc:
        raise HTTPException(502, str(exc))


@router.get("/artifacts/{artifact_id}")
async def get_artifact(artifact_id: str):
    art = ArtifactIntelligence.get_artifact(artifact_id)
    if art is None:
        raise HTTPException(404, "Artifact not found")
    return art


# ---- Failures ----

@router.get("/failures")
async def list_failures(
    entity_type: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
):
    try:
        failures = FailureAnalysis.list_failures(entity_type=entity_type or "", limit=limit)
        return {"failures": failures}
    except Exception as exc:
        raise HTTPException(502, str(exc))


@router.get("/failures/{failure_id}")
async def get_failure(failure_id: str):
    f = FailureAnalysis.get_failure(failure_id)
    if f is None:
        raise HTTPException(404, "Failure analysis not found")
    return f


# ---- Recoveries ----

@router.get("/recoveries")
async def list_recoveries(limit: int = Query(100, ge=1, le=500)):
    try:
        return {"recoveries": DeploymentRecovery.list_recoveries(limit)}
    except Exception as exc:
        raise HTTPException(502, str(exc))


@router.get("/recoveries/{recovery_id}")
async def get_recovery(recovery_id: str):
    r = DeploymentRecovery.get_recovery(recovery_id)
    if r is None:
        raise HTTPException(404, "Recovery not found")
    return r


@router.post("/recoveries")
async def create_recovery(body: FailRecoverRequest):
    try:
        result = await DeploymentRecovery.recover(
            deployment_id=body.entity_id,
            strategy=body.strategy,
            initiated_by="api",
        )
        return result
    except Exception as exc:
        raise HTTPException(502, str(exc))


# ---- Platforms ----

@router.get("/platforms")
async def list_platforms():
    return {"platforms": SUPPORTED_PLATFORMS}


# ---- Build Intelligence (Phase 8) ----

@router.get("/builds/flaky")
async def flaky_builds(min_runs: int = Query(5, ge=2), threshold: float = Query(0.3, ge=0.0, le=1.0)):
    try:
        return {"flaky_builds": BuildIntelligence.get_flaky_builds(min_runs, threshold)}
    except Exception as exc:
        raise HTTPException(502, str(exc))


@router.get("/builds/ownership")
async def build_ownership():
    try:
        return BuildIntelligence.get_build_ownership()
    except Exception as exc:
        raise HTTPException(502, str(exc))


@router.get("/builds/repository-stats")
async def repository_stats():
    try:
        return {"repositories": BuildIntelligence.get_repository_stats()}
    except Exception as exc:
        raise HTTPException(502, str(exc))


@router.get("/builds/average-duration")
async def average_duration(limit: int = Query(100, ge=1, le=1000)):
    try:
        return BuildIntelligence.get_average_duration(limit)
    except Exception as exc:
        raise HTTPException(502, str(exc))


# ---- Artifact Intelligence (Phase 7) ----

@router.get("/artifacts/lineage/{artifact_name}")
async def artifact_lineage(artifact_name: str):
    try:
        return {"lineage": ArtifactIntelligence.get_version_lineage(artifact_name)}
    except Exception as exc:
        raise HTTPException(502, str(exc))


@router.get("/artifacts/{artifact_id}/dependencies")
async def artifact_dependencies(artifact_id: str):
    try:
        return {"dependencies": ArtifactIntelligence.get_artifact_dependencies(artifact_id)}
    except Exception as exc:
        raise HTTPException(502, str(exc))


@router.post("/artifacts/{artifact_id}/promote")
async def promote_artifact(artifact_id: str, target_environment: str = Query(...)):
    try:
        result = ArtifactIntelligence.promote_artifact(artifact_id, target_environment)
        if result is None:
            raise HTTPException(404, "Artifact not found")
        return result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(502, str(exc))


@router.get("/artifacts/environments/{environment}")
async def artifacts_by_environment(environment: str):
    try:
        return {"artifacts": ArtifactIntelligence.list_artifacts_by_environment(environment)}
    except Exception as exc:
        raise HTTPException(502, str(exc))


# ---- GitHub Actions (Phase 2) ----

@router.get("/github/actions/runs")
async def github_actions_runs(owner: str = Query(...), repo: str = Query(...)):
    try:
        runs = await cicd_intelligence.fetch_github_actions_runs(owner, repo)
        return {"workflow_runs": runs}
    except Exception as exc:
        raise HTTPException(502, str(exc))


@router.get("/github/actions/runs/{run_id}/jobs")
async def github_actions_jobs(owner: str = Query(...), repo: str = Query(...), run_id: int = 0):
    if run_id <= 0:
        raise HTTPException(400, "Invalid run_id")
    try:
        jobs = await cicd_intelligence.fetch_github_actions_jobs(owner, repo, run_id)
        return {"jobs": jobs}
    except Exception as exc:
        raise HTTPException(502, str(exc))


@router.post("/github/actions/runs/{run_id}/rerun")
async def github_rerun_workflow(owner: str = Query(...), repo: str = Query(...), run_id: int = 0):
    if run_id <= 0:
        raise HTTPException(400, "Invalid run_id")
    try:
        ok = await cicd_intelligence.rerun_github_workflow(owner, repo, run_id)
        return {"rerun": ok}
    except Exception as exc:
        raise HTTPException(502, str(exc))


@router.post("/github/actions/runs/{run_id}/cancel")
async def github_cancel_workflow(owner: str = Query(...), repo: str = Query(...), run_id: int = 0):
    if run_id <= 0:
        raise HTTPException(400, "Invalid run_id")
    try:
        ok = await cicd_intelligence.cancel_github_workflow(owner, repo, run_id)
        return {"cancel": ok}
    except Exception as exc:
        raise HTTPException(502, str(exc))


# ---- Jenkins (Phase 3) ----

@router.get("/jenkins/jobs")
async def jenkins_jobs(folder: str = Query("")):
    try:
        jobs = await cicd_intelligence.fetch_jenkins_jobs(folder)
        return {"jobs": jobs}
    except Exception as exc:
        raise HTTPException(502, str(exc))


@router.get("/jenkins/jobs/{job_name}/builds")
async def jenkins_builds(job_name: str, limit: int = Query(50, ge=1, le=200)):
    try:
        builds = await cicd_intelligence.fetch_jenkins_builds(job_name, limit)
        return {"builds": builds}
    except Exception as exc:
        raise HTTPException(502, str(exc))


@router.post("/jenkins/jobs/{job_name}/build")
async def jenkins_build_job(job_name: str, parameters: Optional[Dict[str, str]] = None):
    try:
        number = await cicd_intelligence.build_jenkins_job(job_name, parameters)
        return {"build_number": number}
    except Exception as exc:
        raise HTTPException(502, str(exc))


# ---- Azure Pipelines (Phase 4) ----

@router.get("/azure/pipelines")
async def azure_pipelines():
    try:
        pipelines = await cicd_intelligence.fetch_azure_pipelines()
        return {"pipelines": pipelines}
    except Exception as exc:
        raise HTTPException(502, str(exc))


@router.post("/azure/pipelines/{pipeline_id}/run")
async def azure_queue_pipeline(pipeline_id: int):
    try:
        result = await cicd_intelligence.queue_azure_pipeline(pipeline_id)
        if result is None:
            raise HTTPException(502, "Azure DevOps connector unavailable")
        return result
    except Exception as exc:
        raise HTTPException(502, str(exc))


# ---- GitLab CI (Phase 5) ----

@router.get("/gitlab/projects/{project_id}/pipelines")
async def gitlab_pipelines(project_id: int):
    try:
        pipelines = await cicd_intelligence.fetch_gitlab_pipelines(project_id)
        return {"pipelines": pipelines}
    except Exception as exc:
        raise HTTPException(502, str(exc))


@router.get("/gitlab/projects/{project_id}/pipelines/{pipeline_id}/jobs")
async def gitlab_jobs(project_id: int, pipeline_id: int):
    try:
        jobs = await cicd_intelligence.fetch_gitlab_jobs(project_id, pipeline_id)
        return {"jobs": jobs}
    except Exception as exc:
        raise HTTPException(502, str(exc))


# ---- CircleCI (Phase 6) ----

@router.get("/circleci/projects/{project_slug}/pipelines")
async def circleci_pipelines(project_slug: str):
    try:
        pipelines = await cicd_intelligence.fetch_circleci_pipelines(project_slug)
        return {"pipelines": pipelines}
    except Exception as exc:
        raise HTTPException(502, str(exc))


@router.get("/circleci/pipelines/{pipeline_id}/workflows")
async def circleci_workflows(pipeline_id: str):
    try:
        workflows = await cicd_intelligence.fetch_circleci_workflows(pipeline_id)
        return {"workflows": workflows}
    except Exception as exc:
        raise HTTPException(502, str(exc))


# ---- Canonical Execution Model (Phase 3) ----

@router.get("/executions")
async def list_executions(
    status: str = Query(""),
    platform: str = Query(""),
    repository: str = Query(""),
    limit: int = Query(100, ge=1, le=500),
):
    try:
        from backend.services.enterprise_runtime_store import runtime_store
        executions = runtime_store.list_executions(status=status, platform=platform, repository=repository, limit=limit)
        return {"executions": [e.to_dict() for e in executions]}
    except Exception as exc:
        raise HTTPException(502, str(exc))


@router.get("/executions/{execution_id}")
async def get_execution(execution_id: str):
    try:
        from backend.services.enterprise_runtime_store import runtime_store
        execution = runtime_store.get_execution(execution_id)
        if execution is None:
            raise HTTPException(404, "Execution not found")
        return execution.to_dict()
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(502, str(exc))


@router.get("/executions/dashboard")
async def execution_dashboard():
    try:
        from backend.services.enterprise_runtime_store import runtime_store
        return runtime_store.get_dashboard()
    except Exception as exc:
        raise HTTPException(502, str(exc))


# ---- Events ----

@router.get("/events")
async def list_events():
    return {"events": CICD_EVENTS}
