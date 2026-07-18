"""
Enterprise Engineering Runtime Store — SINGLE SOURCE OF TRUTH.

Consolidates all engineering execution state into ONE canonical store.
Replaces builds.json, cicd_builds.json, deployments.json, cicd_deployments.json,
cicd_artifacts.json, cicd_pipelines.json, cicd_timelines.json, cicd_failures.json,
cicd_recoveries.json, and the legacy in-memory RuntimeState and Redis
RuntimeStateStore.

Architecture:
  EngineeringExecution — canonical dataclass for EVERY engineering execution.
  RuntimeStore — singleton that persists all executions to runtime_store.json
                 and emits events on every write.

Every subsystem (BuildEngine, DeploymentEngine, DeliveryOrchestrator,
CICDIntelligence, Analytics, RuntimeState, RuntimeStateStore) reads and
writes the SAME execution record.  RuntimeStateStore becomes a read-through
cache; RuntimeState becomes a read-only projection.
"""
from __future__ import annotations

import json
import logging
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

log = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_RUNTIME_STORE_FILE = _DATA_DIR / "runtime_store.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _id(prefix: str = "exec") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


# =============================================================================
# Canonical Execution Model
# =============================================================================

@dataclass
class EngineeringExecution:
    """Canonical execution record used by ALL engineering subsystems.

    Every engineering activity (build, deploy, pipeline, mission, sandbox,
    terraform, patch, rollback, approval, delivery, CI/CD event) is represented
    as an EngineeringExecution.  Subsystems may populate only the fields relevant
    to their domain; the store treats missing fields as empty defaults.
    """
    # ---- Identity ----
    execution_id: str = ""
    mission_id: str = ""
    pipeline_id: str = ""
    delivery_id: str = ""

    # ---- Objective / Goal ----
    objective: str = ""

    # ---- Repository ----
    repository: str = ""
    branch: str = ""
    commit_sha: str = ""

    # ---- Build ----
    build_id: str = ""
    build_status: str = ""
    build_conclusion: str = ""
    build_platform: str = ""
    build_name: str = ""
    build_duration_ms: int = 0
    build_log: List[Dict[str, Any]] = field(default_factory=list)
    build_steps: List[Dict[str, Any]] = field(default_factory=list)

    # ---- Deployment ----
    deployment_id: str = ""
    deployment_status: str = ""
    deployment_environment: str = ""
    deployment_version: str = ""
    deployment_strategy: str = ""
    deployment_log: List[Dict[str, Any]] = field(default_factory=list)

    # ---- Artifacts ----
    artifacts: List[Dict[str, Any]] = field(default_factory=list)

    # ---- Pipeline / Delivery ----
    platform: str = ""
    workflow_name: str = ""
    run_number: str = ""
    sender: str = ""
    current_stage: str = ""
    current_stage_index: int = 0
    stages_completed: List[str] = field(default_factory=list)
    stages_failed: List[str] = field(default_factory=list)
    timeline: List[Dict[str, Any]] = field(default_factory=list)

    # ---- Verification & Approvals ----
    approvals: List[Dict[str, Any]] = field(default_factory=list)
    verification: Dict[str, Any] = field(default_factory=dict)
    qa_results: Dict[str, Any] = field(default_factory=dict)
    security_report: Dict[str, Any] = field(default_factory=dict)
    monitoring_metrics: Dict[str, Any] = field(default_factory=dict)

    # ---- Metrics ----
    owner: str = ""
    started_at: str = ""
    completed_at: str = ""
    duration_seconds: float = 0.0

    # ---- Failure & Recovery ----
    failure: Optional[Dict[str, Any]] = None
    recovery: Optional[Dict[str, Any]] = None

    # ---- Event / webhook source ----
    event_type: str = ""
    event_id: str = ""

    # ---- Session / User ----
    user_id: str = ""
    session_id: str = ""

    # ---- Priority & Step tracking ----
    priority: int = 5
    current_step: str = ""

    # ---- Mission-specific ----
    mission_type: str = ""
    mission_status: str = ""

    # ---- Sandbox ----
    sandbox_id: str = ""
    sandbox_status: str = ""

    # ---- Infrastructure / Terraform ----
    terraform_workspace: str = ""
    terraform_status: str = ""
    infra_action: str = ""

    # ---- Patch ----
    patch_id: str = ""
    patch_status: str = ""

    # ---- Rollback ----
    rollback_target: str = ""
    rollback_status: str = ""

    # ---- Approval workflow ----
    approval_status: str = ""
    approval_required: bool = False
    approval_decision: str = ""
    approved_by: str = ""

    # ---- Result ----
    final_response: str = ""
    failure_reason: str = ""
    result_summary: str = ""

    # ---- System ----
    created_at: str = ""
    updated_at: str = ""
    status: str = "pending"

    def __post_init__(self) -> None:
        if not self.execution_id:
            self.execution_id = _id("exec")
        if not self.created_at:
            self.created_at = _now()
        if not self.updated_at:
            self.updated_at = _now()

    def update(self, **kwargs: Any) -> None:
        for k, v in kwargs.items():
            if hasattr(self, k):
                setattr(self, k, v)
        self.updated_at = _now()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> EngineeringExecution:
        data = {k: v for k, v in data.items() if k in EngineeringExecution.__dataclass_fields__}
        return EngineeringExecution(**data)


# =============================================================================
# Runtime Store — persists ALL executions to ONE JSON file (Phase 3)
# =============================================================================

class RuntimeStore:
    """Single source of truth for all engineering execution state.

    Replaces builds.json, cicd_builds.json, deployments.json, cicd_deployments.json,
    cicd_artifacts.json, cicd_pipelines.json, cicd_timelines.json, cicd_failures.json,
    cicd_recoveries.json, and the legacy in-memory RuntimeState and Redis
    RuntimeStateStore with one runtime_store.json.

    Subsystems access executions by ID.  Every write emits a standardized event
    so that caches (Redis RuntimeStateStore), WebSocket broadcasters, and
    dashboards can react without polling.
    """

    _event_callbacks: List[Callable[[str, str, Optional[Dict[str, Any]]], None]] = []

    @classmethod
    def on_event(cls, callback: Callable[[str, str, Optional[Dict[str, Any]]], None]) -> None:
        """Register a callback fired on every CRUD event.

        Callback signature:  ``callback(event_type: str, execution_id: str, data: dict | None)``
        """
        cls._event_callbacks.append(callback)

    def _emit(self, event_type: str, execution_id: str, data: Optional[Dict[str, Any]] = None) -> None:
        for cb in self._event_callbacks:
            try:
                cb(event_type, execution_id, data)
            except Exception as exc:
                log.debug("RuntimeStore event callback failed: %s", exc)

    def __init__(self) -> None:
        self._executions: Dict[str, EngineeringExecution] = {}
        self._loaded: bool = False

    # ---- Persistence ----

    def _load(self) -> None:
        if self._loaded:
            return
        try:
            if _RUNTIME_STORE_FILE.exists():
                with open(_RUNTIME_STORE_FILE) as f:
                    raw = json.load(f)
                if isinstance(raw, list):
                    for item in raw:
                        if isinstance(item, dict) and "execution_id" in item:
                            exec_id = item["execution_id"]
                            self._executions[exec_id] = EngineeringExecution.from_dict(item)
                elif isinstance(raw, dict):
                    for exec_id, item in raw.items():
                        if isinstance(item, dict):
                            self._executions[exec_id] = EngineeringExecution.from_dict(item)
        except Exception as exc:
            log.warning("Failed to load runtime store: %s", exc)
        self._loaded = True

    def _save(self) -> None:
        _RUNTIME_STORE_FILE.parent.mkdir(parents=True, exist_ok=True)
        try:
            data = [execution.to_dict() for execution in self._executions.values()]
            data.sort(key=lambda x: x.get("created_at", ""), reverse=True)
            with open(_RUNTIME_STORE_FILE, "w") as f:
                json.dump(data, f, indent=2, default=str)
        except Exception as exc:
            log.warning("Failed to save runtime store: %s", exc)

    # ---- CRUD ----

    def create_execution(self, execution: EngineeringExecution) -> EngineeringExecution:
        self._load()
        if execution.execution_id in self._executions:
            log.warning("Execution %s already exists — overwriting", execution.execution_id)
        self._executions[execution.execution_id] = execution
        self._save()
        self._emit("created", execution.execution_id, execution.to_dict())
        return execution

    def get_execution(self, execution_id: str) -> Optional[EngineeringExecution]:
        self._load()
        return self._executions.get(execution_id)

    def update_execution(self, execution_id: str, **kwargs: Any) -> Optional[EngineeringExecution]:
        self._load()
        execution = self._executions.get(execution_id)
        if not execution:
            return None
        execution.update(**kwargs)
        self._save()
        self._emit("updated", execution_id, execution.to_dict())
        return execution

    def list_executions(
        self,
        status: str = "",
        platform: str = "",
        repository: str = "",
        build_id: str = "",
        deployment_id: str = "",
        limit: int = 100,
    ) -> List[EngineeringExecution]:
        self._load()
        result = list(self._executions.values())
        if status:
            result = [e for e in result if e.status == status]
        if platform:
            result = [e for e in result if e.platform == platform]
        if repository:
            result = [e for e in result if e.repository == repository]
        if build_id:
            result = [e for e in result if e.build_id == build_id]
        if deployment_id:
            result = [e for e in result if e.deployment_id == deployment_id]
        result.sort(key=lambda x: x.created_at, reverse=True)
        return result[:limit]

    def delete_execution(self, execution_id: str) -> bool:
        self._load()
        if execution_id in self._executions:
            del self._executions[execution_id]
            self._save()
            self._emit("deleted", execution_id, None)
            return True
        return False

    def count(self) -> int:
        self._load()
        return len(self._executions)

    # ---- Migration helper (import from legacy stores) ----

    def import_legacy_build(self, build_data: Dict[str, Any]) -> str:
        execution = EngineeringExecution(
            build_id=build_data.get("id", _id("bld")),
            build_status=build_data.get("status", "unknown"),
            build_name=build_data.get("name", ""),
            repository=build_data.get("repository", ""),
            branch=build_data.get("branch", ""),
            owner=build_data.get("sender", build_data.get("actor", "")),
            status=build_data.get("status", "pending"),
            created_at=build_data.get("created_at", _now()),
            updated_at=build_data.get("updated_at", _now()),
            build_log=build_data.get("log", []),
            artifacts=[{"id": a.get("id"), "name": a.get("name")} for a in build_data.get("artifacts", [])],
            execution_id=build_data.get("execution_id", _id("exec")),
        )
        return self.create_execution(execution).execution_id

    def import_legacy_deployment(self, dep_data: Dict[str, Any]) -> str:
        execution = EngineeringExecution(
            deployment_id=dep_data.get("id", dep_data.get("deployment_id", _id("dep"))),
            deployment_status=dep_data.get("status", "unknown"),
            deployment_environment=dep_data.get("environment", dep_data.get("environment_name", "")),
            deployment_version=dep_data.get("version", ""),
            deployment_strategy=dep_data.get("strategy", ""),
            repository=dep_data.get("repository", ""),
            status=dep_data.get("status", "pending"),
            created_at=dep_data.get("created_at", _now()),
            updated_at=dep_data.get("updated_at", _now()),
            deployment_log=dep_data.get("log", []),
            execution_id=dep_data.get("execution_id", _id("exec")),
        )
        return self.create_execution(execution).execution_id

    def clear(self) -> None:
        self._executions.clear()
        self._save()

    # ---- Dashboard ----

    def get_dashboard(self) -> Dict[str, Any]:
        self._load()
        all_execs = list(self._executions.values())
        builds = [e for e in all_execs if e.build_id]
        deployments = [e for e in all_execs if e.deployment_id]
        return {
            "total_executions": len(all_execs),
            "total_builds": len(builds),
            "builds_passed": sum(1 for b in builds if b.build_status in ("passed", "success")),
            "builds_failed": sum(1 for b in builds if b.build_status in ("failed", "failure")),
            "builds_running": sum(1 for b in builds if b.build_status in ("running", "in_progress")),
            "total_deployments": len(deployments),
            "deployments_success": sum(1 for d in deployments if d.deployment_status in ("deployed", "success")),
            "deployments_failed": sum(1 for d in deployments if d.deployment_status in ("failed", "failure")),
            "deployments_rolled_back": sum(1 for d in deployments if d.deployment_status == "rolled_back"),
            "total_artifacts": sum(len(e.artifacts) for e in all_execs),
        }


runtime_store = RuntimeStore()
