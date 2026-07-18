"""
Enterprise Engineering Routes — REST API for the Engineering Department.

Endpoints:
  POST /api/engineering/execute         — Execute a full engineering task
  GET  /api/engineering/agents          — List available engineering agents
  GET  /api/engineering/ecosystems      — List supported build ecosystems
  POST /api/engineering/analyze-repo    — Run repository analysis only
  POST /api/engineering/build-plan      — Generate build plan for ecosystem
  POST /api/engineering/investigate     — Run bug investigation
  POST /api/engineering/plan            — Generate engineering plan
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.services.enterprise_build_engine import BuildEngine
from backend.services.enterprise_deployment_engine import DeploymentEngine
from backend.services.enterprise_engineering_service import engineering_executive

log = logging.getLogger(__name__)

build_engine = BuildEngine()
deployment_engine = DeploymentEngine()

router = APIRouter(prefix="/api/engineering", tags=["Enterprise Engineering"])


class ExecuteRequest(BaseModel):
    objective: str
    repo_url: str = ""
    branch: str = "main"
    ecosystem: str = "python"
    execution_id: str = ""
    build_diagnostics: Optional[List[Dict[str, Any]]] = None


# ── Build Models ────────────────────────────────────────────────────────

class CreateBuildRequest(BaseModel):
    workspace_id: str
    branch: str = "main"
    commit_hash: str = ""
    steps: Optional[List[str]] = None
    environment: Optional[Dict[str, str]] = None
    trigger: str = "manual"
    patches: Optional[List[str]] = None


class AddArtifactRequest(BaseModel):
    name: str
    path: str
    size_bytes: int = 0
    artifact_type: str = "binary"
    metadata: Optional[Dict[str, Any]] = None


# ── Deployment Models ───────────────────────────────────────────────────

class CreateEnvironmentRequest(BaseModel):
    name: str
    env_type: str = "development"
    url: str = ""
    region: str = "us-east-1"
    config: Optional[Dict[str, Any]] = None


class CreateDeploymentRequest(BaseModel):
    workspace_id: str
    environment_id: str
    artifact_id: str = ""
    build_id: str = ""
    version: str = "1.0.0"
    strategy: str = "rolling"
    config_override: Optional[Dict[str, Any]] = None
    approvals_required: int = 0


class ApproveDeploymentRequest(BaseModel):
    approver: str


# ═════════════════════════════════════════════════════════════════════════
# BUILD ENDPOINTS
# ═════════════════════════════════════════════════════════════════════════

@router.post("/builds")
async def create_build(body: CreateBuildRequest):
    return await build_engine.create_build(**body.model_dump())


@router.get("/builds")
async def list_builds(workspace_id: str = "", status: str = "", limit: int = 50):
    return {"builds": await build_engine.list_builds(workspace_id, status, limit)}


@router.get("/builds/{build_id}")
async def get_build(build_id: str):
    build = await build_engine.get_build(build_id)
    if not build:
        raise HTTPException(status_code=404, detail="Build not found")
    return build


@router.post("/builds/{build_id}/execute")
async def execute_build(build_id: str):
    return await build_engine.execute_build(build_id)


@router.post("/builds/{build_id}/cancel")
async def cancel_build(build_id: str):
    build = await build_engine.cancel_build(build_id)
    if not build:
        raise HTTPException(status_code=404, detail="Build not found")
    return build


@router.post("/builds/{build_id}/artifacts")
async def add_build_artifact(build_id: str, body: AddArtifactRequest):
    result = await build_engine.add_artifact(build_id, **body.model_dump())
    if not result:
        raise HTTPException(status_code=404, detail="Build not found")
    return result


@router.post("/builds/{build_id}/log")
async def add_build_log(build_id: str, body: dict):
    result = await build_engine.add_build_log(build_id, body.get("message", ""))
    if not result:
        raise HTTPException(status_code=404, detail="Build not found")
    return result


# ═════════════════════════════════════════════════════════════════════════
# DEPLOYMENT ENDPOINTS
# ═════════════════════════════════════════════════════════════════════════

@router.post("/environments")
async def create_environment(body: CreateEnvironmentRequest):
    return await deployment_engine.create_environment(**body.model_dump())


@router.get("/environments")
async def list_environments():
    return {"environments": await deployment_engine.list_environments()}


@router.get("/environments/{env_id}")
async def get_environment(env_id: str):
    env = await deployment_engine.get_environment(env_id)
    if not env:
        raise HTTPException(status_code=404, detail="Environment not found")
    return env


@router.delete("/environments/{env_id}")
async def delete_environment(env_id: str):
    if not await deployment_engine.delete_environment(env_id):
        raise HTTPException(status_code=404, detail="Environment not found")
    return {"ok": True}


@router.post("/deployments")
async def create_deployment(body: CreateDeploymentRequest):
    return await deployment_engine.create_deployment(**body.model_dump())


@router.get("/deployments")
async def list_deployments(workspace_id: str = "", environment_id: str = "", status: str = "", limit: int = 50):
    return {"deployments": await deployment_engine.list_deployments(workspace_id, environment_id, status, limit)}


@router.get("/deployments/{deploy_id}")
async def get_deployment(deploy_id: str):
    deploy = await deployment_engine.get_deployment(deploy_id)
    if not deploy:
        raise HTTPException(status_code=404, detail="Deployment not found")
    return deploy


@router.post("/deployments/{deploy_id}/execute")
async def execute_deployment(deploy_id: str):
    return await deployment_engine.execute_deployment(deploy_id)


@router.post("/deployments/{deploy_id}/rollback")
async def rollback_deployment(deploy_id: str):
    result = await deployment_engine.rollback_deployment(deploy_id)
    if not result:
        raise HTTPException(status_code=404, detail="Deployment not found")
    return result


@router.post("/deployments/{deploy_id}/approve")
async def approve_deployment(deploy_id: str, body: ApproveDeploymentRequest):
    result = await deployment_engine.approve_deployment(deploy_id, body.approver)
    if not result:
        raise HTTPException(status_code=404, detail="Deployment not found")
    return result


# ═════════════════════════════════════════════════════════════════════════
# ORIGINAL ENGINEERING ENDPOINTS
# ═════════════════════════════════════════════════════════════════════════

@router.post("/execute")
async def execute_engineering_task(body: ExecuteRequest):
    """Execute a full engineering department workflow."""
    result = await engineering_executive.execute_engineering_task(
        objective=body.objective,
        repo_url=body.repo_url,
        branch=body.branch,
        ecosystem=body.ecosystem,
        execution_id=body.execution_id,
        build_diagnostics=body.build_diagnostics,
    )
    return result


@router.get("/agents")
async def list_agents():
    """List all available engineering agents in the department."""
    return {
        "agents": [
            {"name": "engineering_executive", "title": "Engineering Executive", "responsibility": "Orchestrates all engineering agents"},
            {"name": "repository_analyst", "title": "Repository Analyst", "responsibility": "Analyzes commits, branches, PRs, changed files"},
            {"name": "build_engineer", "title": "Build Engineer", "responsibility": "Runs build, lint, static analysis"},
            {"name": "qa_engineer", "title": "QA Engineer", "responsibility": "Runs tests and validates quality gates"},
            {"name": "security_engineer", "title": "Security Engineer", "responsibility": "Scans for vulnerabilities and secrets"},
            {"name": "software_architect", "title": "Software Architect", "responsibility": "Assesses architecture impact and dependencies"},
            {"name": "bug_investigator", "title": "Bug Investigator", "responsibility": "Correlates failures for root-cause analysis"},
            {"name": "engineering_planner", "title": "Engineering Planner", "responsibility": "Generates implementation plans"},
            {"name": "code_generator", "title": "Code Generator", "responsibility": "Prepares code change sets"},
            {"name": "code_reviewer", "title": "Code Reviewer", "responsibility": "Reviews proposed changes"},
            {"name": "test_validator", "title": "Test Validator", "responsibility": "Validates test coverage and results"},
            {"name": "devops_engineer", "title": "DevOps Engineer", "responsibility": "Pipeline, deployment, infrastructure"},
            {"name": "sre_engineer", "title": "SRE Engineer", "responsibility": "Reliability, monitoring, observability"},
        ],
        "total": 13,
    }


@router.get("/ecosystems")
async def list_ecosystems():
    """List supported build ecosystems."""
    return {
        "ecosystems": [
            {"id": "python", "name": "Python", "build": "pip install && python -m build", "lint": "ruff", "typecheck": "mypy"},
            {"id": "node", "name": "Node.js", "build": "npm ci && npm run build", "lint": "eslint", "typecheck": "tsc"},
            {"id": "java", "name": "Java", "build": "mvn compile", "lint": "checkstyle", "test": "mvn test"},
            {"id": "dotnet", "name": ".NET", "build": "dotnet build", "lint": "dotnet format", "test": "dotnet test"},
            {"id": "go", "name": "Go", "build": "go build ./...", "lint": "golangci-lint", "test": "go test ./..."},
            {"id": "rust", "name": "Rust", "build": "cargo build", "lint": "clippy", "test": "cargo test"},
        ],
        "total": 6,
    }


class RepoAnalysisRequest(BaseModel):
    repo_url: str
    branch: str = "main"
    execution_id: str = ""


@router.post("/analyze-repo")
async def analyze_repository(body: RepoAnalysisRequest):
    """Run repository analysis only."""
    result = await engineering_executive.repository_analyst.analyze(
        repo_url=body.repo_url,
        branch=body.branch,
        execution_id=body.execution_id or f"analyze_{body.repo_url.split('/')[-1][:12]}",
    )
    return result


class BuildPlanRequest(BaseModel):
    ecosystem: str = "python"
    execution_id: str = ""


@router.post("/build-plan")
async def build_plan(body: BuildPlanRequest):
    """Generate build plan for a given ecosystem."""
    result = await engineering_executive.build_engineer.build(
        ecosystem=body.ecosystem,
        execution_id=body.execution_id or f"build_{body.ecosystem}_{uuid4().hex[:8]}",
    )
    return result


class InvestigateRequest(BaseModel):
    execution_id: str
    build_diagnostics: Optional[List[Dict[str, Any]]] = None


@router.post("/investigate")
async def investigate(body: InvestigateRequest):
    """Run bug investigation."""
    result = await engineering_executive.bug_investigator.investigate(
        execution_id=body.execution_id,
        build_diagnostics=body.build_diagnostics,
    )
    return result


class PlanRequest(BaseModel):
    objective: str
    repo_analysis: Optional[Dict[str, Any]] = None
    architecture_review: Optional[Dict[str, Any]] = None
    execution_id: str = ""


@router.post("/plan")
async def generate_plan(body: PlanRequest):
    """Generate engineering plan."""
    result = await engineering_executive.engineering_planner.plan(
        repo_analysis=body.repo_analysis,
        architecture_review=body.architecture_review,
        objective=body.objective,
        execution_id=body.execution_id or f"plan_{uuid4().hex[:12]}",
    )
    return result


def uuid4() -> Any:
    import uuid
    return uuid.uuid4()


# =====================================================================
# Workspace & Repository Routes
# =====================================================================

from backend.services.enterprise_workspace_engine import workspace_manager


class CreateWorkspaceRequest(BaseModel):
    name: str
    repo_url: str = ""
    branch: str = "main"


@router.get("/repositories")
async def list_repositories():
    """List all known repositories from active workspaces."""
    workspaces = workspace_manager.list()
    repos = []
    seen: set = set()
    for ws in workspaces:
        url = ws.get("repo_url", "")
        if url and url not in seen:
            seen.add(url)
            repos.append({
                "url": url,
                "name": ws.get("repository", {}).get("name", url.split("/")[-1]) if ws.get("repository") else url.split("/")[-1],
                "workspaces": [ws.get("id")],
                "languages": ws.get("repository", {}).get("languages", {}) if ws.get("repository") else {},
                "analyzed_at": ws.get("repository", {}).get("analyzed_at", "") if ws.get("repository") else "",
            })
    return {"repositories": repos, "total": len(repos)}


@router.get("/repositories/{repo_url:path}")
async def get_repository_intelligence(repo_url: str, branch: str = "main"):
    """Get repository intelligence for a given URL."""
    intelligence = await workspace_manager.analyze_repository(repo_url, branch)
    return intelligence


@router.post("/workspaces")
async def create_workspace(body: CreateWorkspaceRequest):
    """Create a new engineering workspace."""
    ws = await workspace_manager.create(
        name=body.name,
        repo_url=body.repo_url,
        branch=body.branch,
    )
    return ws.to_dict()


@router.get("/workspaces")
async def list_workspaces(status: Optional[str] = None):
    """List all workspaces with optional status filter."""
    return {"workspaces": workspace_manager.list(status=status), "total": len(workspace_manager.list(status=status))}


@router.get("/workspaces/{ws_id}")
async def get_workspace(ws_id: str):
    """Get workspace details."""
    ws = workspace_manager.get(ws_id)
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return ws.to_dict()


@router.delete("/workspaces/{ws_id}")
async def destroy_workspace(ws_id: str):
    """Destroy a workspace."""
    ok = await workspace_manager.destroy(ws_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return {"status": "destroyed", "id": ws_id}


@router.post("/workspaces/{ws_id}/checkout")
async def checkout_branch(ws_id: str, branch: str = "main"):
    """Checkout a branch in the workspace."""
    result = await workspace_manager.checkout_branch(ws_id, branch)
    if not result:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return result


@router.get("/workspaces/{ws_id}/status")
async def workspace_status(ws_id: str):
    """Get workspace status summary."""
    status = workspace_manager.get_status(ws_id)
    if not status:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return status


@router.get("/workspaces/{ws_id}/artifacts")
async def workspace_artifacts(ws_id: str):
    """List workspace artifacts."""
    ws = workspace_manager.get(ws_id)
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return {"artifacts": workspace_manager.list_artifacts(ws_id), "total": len(ws.artifacts)}


@router.get("/workspaces/{ws_id}/snapshot")
async def workspace_snapshot(ws_id: str):
    """Get workspace snapshot."""
    snapshot = workspace_manager.get_snapshot(ws_id)
    if not snapshot:
        raise HTTPException(status_code=404, detail="No snapshot found for this workspace")
    return snapshot


# =====================================================================
# Patch Routes
# =====================================================================

from backend.services.enterprise_patch_engine import patch_manager


class CreatePatchRequest(BaseModel):
    workspace_id: str
    title: str
    description: str = ""
    engineer: str = "system"
    branch: str = "main"
    repository_url: str = ""
    mission_execution_id: str = ""
    files_changed: Optional[List[Dict[str, Any]]] = None
    categories: Optional[List[str]] = None


class UpdatePatchRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    files_changed: Optional[List[Dict[str, Any]]] = None


@router.get("/patches")
async def list_patches(workspace_id: Optional[str] = None, status: Optional[str] = None):
    """List patches with optional workspace/status filters."""
    return {"patches": patch_manager.list(workspace_id=workspace_id, status=status), "total": len(patch_manager.list(workspace_id=workspace_id, status=status))}


@router.post("/patches")
async def create_patch(body: CreatePatchRequest):
    """Create a new patch."""
    patch = await patch_manager.create(
        workspace_id=body.workspace_id,
        title=body.title,
        description=body.description,
        engineer=body.engineer,
        branch=body.branch,
        repository_url=body.repository_url,
        mission_execution_id=body.mission_execution_id,
        files_changed=body.files_changed,
        categories=body.categories,
    )
    return patch.to_dict()


@router.get("/patches/{patch_id}")
async def get_patch(patch_id: str):
    """Get patch details."""
    patch = patch_manager.get(patch_id)
    if not patch:
        raise HTTPException(status_code=404, detail="Patch not found")
    return patch.to_dict()


@router.post("/patches/{patch_id}/validate")
async def validate_patch(patch_id: str):
    """Validate a patch."""
    results = await patch_manager.validate_patch(patch_id)
    if not results:
        raise HTTPException(status_code=404, detail="Patch not found")
    return results


@router.post("/patches/{patch_id}/rollback")
async def rollback_patch(patch_id: str):
    """Create an automatic rollback patch."""
    rollback = await patch_manager.create_rollback(patch_id)
    if not rollback:
        raise HTTPException(status_code=404, detail="Patch not found")
    return rollback.to_dict()


@router.get("/patches/{patch_id}/diff")
async def patch_diff(patch_id: str):
    """Get patch diff."""
    diff = patch_manager.get_diff(patch_id)
    if not diff:
        diff = await patch_manager.generate_diff(patch_id)
    if not diff:
        raise HTTPException(status_code=404, detail="Patch not found")
    return diff
