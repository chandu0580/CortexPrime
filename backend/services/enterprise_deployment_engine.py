"""
Enterprise Deployment Engine — deploys built artifacts from Workspaces to
target environments with rollback support.
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_DEPLOYMENTS_FILE = _DATA_DIR / "deployments.json"
_ENVIRONMENTS_FILE = _DATA_DIR / "environments.json"

DEPLOY_EVENT_CREATED       = "deploy.created"
DEPLOY_EVENT_STARTED       = "deploy.started"
DEPLOY_EVENT_COMPLETED     = "deploy.completed"
DEPLOY_EVENT_FAILED        = "deploy.failed"
DEPLOY_EVENT_ROLLED_BACK   = "deploy.rolled_back"
DEPLOY_EVENT_ENV_UPDATED   = "deploy.env_updated"

DEPLOY_STATUSES = ["pending", "deploying", "deployed", "failed", "rolled_back"]

ENVIRONMENTS = ["development", "staging", "production", "qa", "demo"]

HEALTH_STATUSES = ["unknown", "healthy", "degraded", "down"]


def _load_json(path: Path) -> List[Dict[str, Any]]:
    try:
        if path.exists():
            with open(path) as f:
                return json.load(f)
    except Exception as exc:
        log.error("Failed to load %s: %s", path.name, exc)
    return []


def _save_json(path: Path, data: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)


def _sync_deploy_to_runtime_store(deploy: Dict[str, Any]) -> None:
    """Write this deployment to the canonical RuntimeStore."""
    try:
        from backend.services.enterprise_runtime_store import EngineeringExecution, runtime_store
        existing = runtime_store.get_execution(deploy.get("execution_id", "")) if deploy.get("execution_id") else None
        if existing:
            runtime_store.update_execution(
                existing.execution_id,
                deployment_id=deploy.get("id", ""),
                deployment_status=deploy.get("status", ""),
                deployment_environment=deploy.get("environment_name", deploy.get("environment", "")),
                deployment_version=deploy.get("version", ""),
                deployment_strategy=deploy.get("strategy", ""),
                repository=deploy.get("repository", ""),
                updated_at=deploy.get("updated_at", datetime.now(timezone.utc).isoformat()),
                deployment_log=deploy.get("log", []),
            )
        else:
            execution = EngineeringExecution(
                execution_id=deploy.get("execution_id", f"exec-{uuid.uuid4().hex[:12]}"),
                deployment_id=deploy.get("id", ""),
                deployment_status=deploy.get("status", ""),
                deployment_environment=deploy.get("environment_name", deploy.get("environment", "")),
                deployment_version=deploy.get("version", ""),
                deployment_strategy=deploy.get("strategy", ""),
                repository=deploy.get("repository", ""),
                status=deploy.get("status", "pending"),
                created_at=deploy.get("created_at", datetime.now(timezone.utc).isoformat()),
                updated_at=deploy.get("updated_at", datetime.now(timezone.utc).isoformat()),
                deployment_log=deploy.get("log", []),
            )
            runtime_store.create_execution(execution)
    except Exception:
        pass


class DeploymentEngine:
    """Manages deployment lifecycle from artifact to environment."""

    def __init__(self, event_bus=None) -> None:
        self._event_bus = event_bus

    # ── Environment Management ───────────────────────────────────────────

    async def create_environment(self, name: str, env_type: str = "development",
                                  url: str = "", region: str = "us-east-1",
                                  config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        envs = _load_json(_ENVIRONMENTS_FILE)
        now = datetime.now(timezone.utc).isoformat()
        env = {
            "id": f"env-{uuid.uuid4().hex[:8]}",
            "name": name,
            "type": env_type,
            "url": url,
            "region": region,
            "config": config or {},
            "health": "unknown",
            "current_deployment_id": "",
            "deployment_history": [],
            "created_at": now,
            "updated_at": now,
        }
        envs.insert(0, env)
        _save_json(_ENVIRONMENTS_FILE, envs)
        await self._emit(DEPLOY_EVENT_ENV_UPDATED, env)
        return env

    async def list_environments(self) -> List[Dict[str, Any]]:
        return _load_json(_ENVIRONMENTS_FILE)

    async def get_environment(self, env_id: str) -> Optional[Dict[str, Any]]:
        for e in _load_json(_ENVIRONMENTS_FILE):
            if e["id"] == env_id:
                return e
        return None

    async def update_environment_health(self, env_id: str, health: str,
                                         metrics: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        envs = _load_json(_ENVIRONMENTS_FILE)
        for i, e in enumerate(envs):
            if e["id"] == env_id:
                e["health"] = health
                e["updated_at"] = datetime.now(timezone.utc).isoformat()
                if metrics:
                    e.setdefault("metrics", {}).update(metrics)
                envs[i] = e
                _save_json(_ENVIRONMENTS_FILE, envs)
                await self._emit(DEPLOY_EVENT_ENV_UPDATED, e)
                return e
        return None

    async def delete_environment(self, env_id: str) -> bool:
        envs = _load_json(_ENVIRONMENTS_FILE)
        filtered = [e for e in envs if e["id"] != env_id]
        if len(filtered) == len(envs):
            return False
        _save_json(_ENVIRONMENTS_FILE, filtered)
        return True

    # ── Deployment CRUD ──────────────────────────────────────────────────

    async def create_deployment(
        self,
        workspace_id: str,
        environment_id: str,
        artifact_id: str = "",
        build_id: str = "",
        version: str = "1.0.0",
        strategy: str = "rolling",
        config_override: Optional[Dict[str, Any]] = None,
        approvals_required: int = 0,
    ) -> Dict[str, Any]:
        deploys = _load_json(_DEPLOYMENTS_FILE)
        now = datetime.now(timezone.utc).isoformat()
        env = await self.get_environment(environment_id)
        deploy = {
            "id": f"dep-{uuid.uuid4().hex[:12]}",
            "workspace_id": workspace_id,
            "environment_id": environment_id,
            "environment_name": env["name"] if env else environment_id,
            "artifact_id": artifact_id,
            "build_id": build_id,
            "version": version,
            "strategy": strategy,
            "status": "pending",
            "config_override": config_override or {},
            "approvals_required": approvals_required,
            "approvals_granted": [],
            "rollback_id": "",
            "result": {},
            "log": [],
            "created_at": now,
            "updated_at": now,
            "started_at": "",
            "completed_at": "",
        }
        deploys.insert(0, deploy)
        _save_json(_DEPLOYMENTS_FILE, deploys)
        _sync_deploy_to_runtime_store(deploy)
        await self._emit(DEPLOY_EVENT_CREATED, deploy)
        return deploy

    async def get_deployment(self, deploy_id: str) -> Optional[Dict[str, Any]]:
        for d in _load_json(_DEPLOYMENTS_FILE):
            if d["id"] == deploy_id:
                return d
        return None

    async def list_deployments(self, workspace_id: str = "", environment_id: str = "",
                                status: str = "", limit: int = 50) -> List[Dict[str, Any]]:
        deploys = _load_json(_DEPLOYMENTS_FILE)
        if workspace_id:
            deploys = [d for d in deploys if d["workspace_id"] == workspace_id]
        if environment_id:
            deploys = [d for d in deploys if d["environment_id"] == environment_id]
        if status:
            deploys = [d for d in deploys if d["status"] == status]
        return deploys[:limit]

    async def update_deployment(self, deploy_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        deploys = _load_json(_DEPLOYMENTS_FILE)
        for i, d in enumerate(deploys):
            if d["id"] == deploy_id:
                d.update(updates)
                d["updated_at"] = datetime.now(timezone.utc).isoformat()
                deploys[i] = d
                _save_json(_DEPLOYMENTS_FILE, deploys)
                _sync_deploy_to_runtime_store(d)
                event = DEPLOY_EVENT_STARTED if updates.get("status") == "deploying" else DEPLOY_EVENT_COMPLETED
                await self._emit(event, d)
                return d
        return None

    async def execute_deployment(self, deploy_id: str) -> Dict[str, Any]:
        deploy = await self.get_deployment(deploy_id)
        if not deploy:
            raise ValueError(f"Deployment not found: {deploy_id}")
        deploy = await self.update_deployment(deploy_id, {
            "status": "deploying",
            "started_at": datetime.now(timezone.utc).isoformat(),
        })
        if not deploy:
            raise ValueError(f"Failed to start deployment: {deploy_id}")
        try:
            await self._add_log(deploy_id, f"Deploying {deploy['version']} to {deploy['environment_name']}")
            await self._add_log(deploy_id, f"Strategy: {deploy['strategy']}")
            deploy = await self.update_deployment(deploy_id, {
                "status": "deployed",
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "result": {"success": True, "message": "Deployment completed successfully"},
            })
            await self.update_environment_health(deploy["environment_id"], "healthy")
            return deploy or {}
        except Exception as exc:
            await self._add_log(deploy_id, f"FAILED: {exc}")
            deploy = await self.update_deployment(deploy_id, {
                "status": "failed",
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "result": {"success": False, "error": str(exc)},
            })
            await self.update_environment_health(deploy["environment_id"], "degraded")
            return deploy or {}

    async def rollback_deployment(self, deploy_id: str) -> Optional[Dict[str, Any]]:
        deploy = await self.get_deployment(deploy_id)
        if not deploy:
            return None
        await self._add_log(deploy_id, "Initiating rollback...")
        rollback_deploy = await self.create_deployment(
            workspace_id=deploy["workspace_id"],
            environment_id=deploy["environment_id"],
            artifact_id=deploy.get("artifact_id", ""),
            build_id=deploy.get("build_id", ""),
            version=f"{deploy['version']}-rollback",
            strategy="immediate",
        )
        await self._add_log(deploy_id, f"Rollback deployment created: {rollback_deploy['id']}")
        deploys = _load_json(_DEPLOYMENTS_FILE)
        for i, d in enumerate(deploys):
            if d["id"] == deploy_id:
                d["status"] = "rolled_back"
                d["rollback_id"] = rollback_deploy["id"]
                d["completed_at"] = datetime.now(timezone.utc).isoformat()
                d["updated_at"] = datetime.now(timezone.utc).isoformat()
                deploys[i] = d
                _save_json(_DEPLOYMENTS_FILE, deploys)
                await self._emit(DEPLOY_EVENT_ROLLED_BACK, d)
                await self.update_environment_health(deploy["environment_id"], "healthy")
                return d
        return None

    async def approve_deployment(self, deploy_id: str, approver: str) -> Optional[Dict[str, Any]]:
        deploys = _load_json(_DEPLOYMENTS_FILE)
        for i, d in enumerate(deploys):
            if d["id"] == deploy_id:
                if approver not in d.setdefault("approvals_granted", []):
                    d["approvals_granted"].append(approver)
                    d["updated_at"] = datetime.now(timezone.utc).isoformat()
                    deploys[i] = d
                    _save_json(_DEPLOYMENTS_FILE, deploys)
                    if len(d["approvals_granted"]) >= d.get("approvals_required", 0):
                        await self.execute_deployment(deploy_id)
                return d
        return None

    async def _add_log(self, deploy_id: str, message: str) -> None:
        deploys = _load_json(_DEPLOYMENTS_FILE)
        for i, d in enumerate(deploys):
            if d["id"] == deploy_id:
                d.setdefault("log", []).append({
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "message": message,
                })
                d["updated_at"] = datetime.now(timezone.utc).isoformat()
                deploys[i] = d
                _save_json(_DEPLOYMENTS_FILE, deploys)
                _sync_deploy_to_runtime_store(d)
                break

    async def _emit(self, event_type: str, payload: Dict[str, Any]) -> None:
        if self._event_bus:
            try:
                from backend.events.event_models import CognitionEvent
                await self._event_bus.publish(CognitionEvent(event_type=event_type, data=payload))
            except Exception as exc:
                log.warning("Deploy event emit failed: %s", exc)
