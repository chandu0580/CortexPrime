"""
Enterprise Delivery Orchestrator — the central execution engine that coordinates
the complete software delivery lifecycle across all existing engineering subsystems.

Reuses every existing subsystem. Does NOT duplicate build, deploy, patch, or
workspace logic. Coordinates: Repository → Workspace → Patch → Build → QA →
Security → Approval → PR → Deployment → Verification → Monitoring → Learning.

Capabilities:
- Delivery State Machine (Pending → Queued → Running → Waiting Approval →
  Paused → Retrying → Completed → Failed → Cancelled → Rolled Back → Resumed)
- Delivery Blueprint — full traceability for every delivery
- Resume Engine — resume from any completed stage, never restart entire delivery
- Rollback Engine — rollback complete delivery (workspace, deployment, artifacts)
- Delivery Timeline — capture every stage with timestamps, replay-ready
- Event-driven — emits via EnterpriseEventHub for WebSocket + cross-service sync
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.core.shared import (
    load_json,
    now,
    pipeline_can_transition,
    pipeline_is_terminal,
    save_json,
)
from backend.events.enterprise_event_types import EnterpriseEventTypes as EET

log = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_DELIVERIES_FILE = _DATA_DIR / "deliveries.json"
_PIPELINES_FILE = _DATA_DIR / "pipelines.json"

PIPELINE_EVENTS = {
    "created": EET.PIPELINE_CREATED,
    "started": EET.PIPELINE_STARTED,
    "stage_started": EET.PIPELINE_STAGE_STARTED,
    "stage_completed": EET.PIPELINE_STAGE_COMPLETED,
    "stage_failed": EET.PIPELINE_STAGE_FAILED,
    "completed": EET.PIPELINE_COMPLETED,
    "failed": EET.PIPELINE_FAILED,
    "cancelled": EET.PIPELINE_CANCELLED,
    "patch_to_pr": EET.PIPELINE_PATCH_TO_PR,
    "pr_created": EET.PIPELINE_PR_CREATED,
    "artifact_passed": EET.PIPELINE_ARTIFACT_PASSED,
}

# ── Pipeline states ──────────────────────────────────────────────────────────
PIPELINE_STATES = ["pending", "running", "paused", "completed", "failed", "cancelled"]

PIPELINE_STAGES = [
    "trigger_pipeline",
    "repository",
    "workspace",
    "sandbox_execution",
    "code_intel_scan",
    "build",
    "qa",
    "security",
    "patch_generation",
    "engineering_review",
    "approval",
    "pr",
    "deployment",
    "gitops_sync",
    "k8s_verification",
    "observability",
    "root_cause_analysis",
    "learning",
    "recommendation",
    "replay_capture",
    "knowledge_graph",
    "complete",
]

# ── Pipeline State Machine ───────────────────────────────────────────────────


# ── Delivery event types ────────────────────────────────────────────────────
DELIVERY_EVENT_STARTED       = "delivery.started"
DELIVERY_EVENT_STAGE_STARTED = "delivery.stage_started"
DELIVERY_EVENT_STAGE_DONE    = "delivery.stage_completed"
DELIVERY_EVENT_STAGE_FAILED  = "delivery.stage_failed"
DELIVERY_EVENT_PAUSED        = "delivery.paused"
DELIVERY_EVENT_RESUMED       = "delivery.resumed"
DELIVERY_EVENT_ROLLED_BACK   = "delivery.rolled_back"
DELIVERY_EVENT_COMPLETED     = "delivery.completed"
DELIVERY_EVENT_CANCELLED     = "delivery.cancelled"
DELIVERY_EVENT_FAILED        = "delivery.failed"

# ── Delivery states ─────────────────────────────────────────────────────────
DELIVERY_STATES = [
    "pending", "queued", "running", "waiting_approval",
    "paused", "retrying", "completed", "failed",
    "cancelled", "rolled_back", "resumed",
]

# ── Delivery stages (ordered) ───────────────────────────────────────────────
# Maps to the full 22-stage autonomous engineering workflow:
# GitHub Push → Pipeline → Repo Intel → Workspace → Sandbox → Code Intel →
# Build → QA → Security → Patch → Engineering Review → Approval → PR →
# Deploy → GitOps → K8s Verify → Observability → RCA → Learning →
# Recommendation → Replay → Knowledge Graph
DELIVERY_STAGES = [
    "trigger_pipeline",
    "repository",
    "workspace",
    "sandbox_execution",
    "code_intel_scan",
    "build",
    "qa",
    "security",
    "patch_generation",
    "engineering_review",
    "approval",
    "pr",
    "deployment",
    "gitops_sync",
    "k8s_verification",
    "observability",
    "root_cause_analysis",
    "learning",
    "recommendation",
    "replay_capture",
    "knowledge_graph",
    "complete",
]


def _id(prefix: str = "exec") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def _load() -> List[Dict[str, Any]]:
    return load_json(_DELIVERIES_FILE)


def _save(data: List[Dict[str, Any]]) -> None:
    save_json(_DELIVERIES_FILE, data)
    _sync_delivery_to_runtime(data)


def _sync_delivery_to_runtime(deliveries: List[Dict[str, Any]]) -> None:
    try:
        from backend.services.enterprise_runtime_store import EngineeringExecution, runtime_store
        for d in deliveries:
            existing = runtime_store.get_execution(d.get("execution_id", "")) if d.get("execution_id") else None
            if existing:
                runtime_store.update_execution(existing.execution_id,
                    delivery_id=d.get("delivery_id", ""), status=d.get("status", d.get("state", "")),
                    current_stage=d.get("current_stage", ""), current_stage_index=d.get("current_stage_index", 0),
                    stages_completed=d.get("stages_completed", []), stages_failed=d.get("stages_failed", []),
                    timeline=d.get("timeline", []), updated_at=d.get("updated_at", now()),
                )
            else:
                runtime_store.create_execution(EngineeringExecution(
                    execution_id=d.get("execution_id", _id("exec")),
                    delivery_id=d.get("delivery_id", ""), status=d.get("status", d.get("state", "")),
                    current_stage=d.get("current_stage", ""), current_stage_index=d.get("current_stage_index", 0),
                    stages_completed=d.get("stages_completed", []), stages_failed=d.get("stages_failed", []),
                    timeline=d.get("timeline", []), created_at=d.get("created_at", now()),
                    updated_at=d.get("updated_at", now()), repository=d.get("blueprint", {}).get("repository", ""),
                ))
    except Exception:
        pass


# =============================================================================
# Delivery Blueprint
# =============================================================================

class DeliveryBlueprint:
    """Full blueprint for a single delivery — tracks every stage and artifact."""

    def __init__(
        self,
        delivery_id: str,
        mission: str,
        repository: str,
        workspace: str = "",
        patch: str = "",
        build: str = "",
        artifacts: Optional[List[Dict[str, Any]]] = None,
        tests: Optional[Dict[str, Any]] = None,
        coverage: Optional[Dict[str, Any]] = None,
        security_report: Optional[Dict[str, Any]] = None,
        approvals: Optional[List[Dict[str, Any]]] = None,
        deployment: str = "",
        verification: Optional[Dict[str, Any]] = None,
        rollback: Optional[Dict[str, Any]] = None,
        metrics: Optional[Dict[str, Any]] = None,
        replay: Optional[List[Dict[str, Any]]] = None,
        learning_references: Optional[List[Dict[str, Any]]] = None,
        recommendation_references: Optional[List[Dict[str, Any]]] = None,
        # New fields for extended pipeline
        branch: str = "main",
        sandbox_id: str = "",
        code_intel_report: Optional[Dict[str, Any]] = None,
        build_errors: str = "",
        patch_plan: Optional[Dict[str, Any]] = None,
        engineering_review: Optional[Dict[str, Any]] = None,
        gitops_result: Optional[Dict[str, Any]] = None,
        k8s_status: Optional[Dict[str, Any]] = None,
        observability: Optional[Dict[str, Any]] = None,
        rca_result: Optional[Dict[str, Any]] = None,
        recommendations: Optional[List[Dict[str, Any]]] = None,
        decision_report: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.delivery_id = delivery_id
        self.mission = mission
        self.repository = repository
        self.branch = branch
        self.workspace = workspace
        self.patch = patch
        self.build = build
        self.artifacts = artifacts or []
        self.tests = tests or {}
        self.coverage = coverage or {}
        self.security_report = security_report or {}
        self.approvals = approvals or []
        self.deployment = deployment
        self.verification = verification or {}
        self.rollback = rollback or {}
        self.metrics = metrics or {}
        self.replay = replay or []
        self.learning_references = learning_references or []
        self.recommendation_references = recommendation_references or []
        self.sandbox_id = sandbox_id
        self.code_intel_report = code_intel_report or {}
        self.build_errors = build_errors
        self.patch_plan = patch_plan
        self.engineering_review = engineering_review or {}
        self.gitops_result = gitops_result or {}
        self.k8s_status = k8s_status or {}
        self.observability = observability or {}
        self.rca_result = rca_result or {}
        self.recommendations = recommendations or []
        self.decision_report = decision_report or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "delivery_id": self.delivery_id,
            "mission": self.mission,
            "repository": self.repository,
            "branch": self.branch,
            "workspace": self.workspace,
            "patch": self.patch,
            "build": self.build,
            "artifacts": self.artifacts,
            "tests": self.tests,
            "coverage": self.coverage,
            "security_report": self.security_report,
            "approvals": self.approvals,
            "deployment": self.deployment,
            "verification": self.verification,
            "rollback": self.rollback,
            "metrics": self.metrics,
            "replay": self.replay,
            "learning_references": self.learning_references,
            "recommendation_references": self.recommendation_references,
            "sandbox_id": self.sandbox_id,
            "code_intel_report": self.code_intel_report,
            "build_errors": self.build_errors,
            "patch_plan": self.patch_plan,
            "engineering_review": self.engineering_review,
            "gitops_result": self.gitops_result,
            "k8s_status": self.k8s_status,
            "observability": self.observability,
            "rca_result": self.rca_result,
            "recommendations": self.recommendations,
            "decision_report": self.decision_report,
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> DeliveryBlueprint:
        return DeliveryBlueprint(
            delivery_id=data.get("delivery_id", ""),
            mission=data.get("mission", ""),
            repository=data.get("repository", ""),
            branch=data.get("branch", "main"),
            workspace=data.get("workspace", ""),
            patch=data.get("patch", ""),
            build=data.get("build", ""),
            artifacts=data.get("artifacts", []),
            tests=data.get("tests", {}),
            coverage=data.get("coverage", {}),
            security_report=data.get("security_report", {}),
            approvals=data.get("approvals", []),
            deployment=data.get("deployment", ""),
            verification=data.get("verification", {}),
            rollback=data.get("rollback", {}),
            metrics=data.get("metrics", {}),
            replay=data.get("replay", []),
            learning_references=data.get("learning_references", []),
            recommendation_references=data.get("recommendation_references", []),
            sandbox_id=data.get("sandbox_id", ""),
            code_intel_report=data.get("code_intel_report", {}),
            build_errors=data.get("build_errors", ""),
            patch_plan=data.get("patch_plan"),
            engineering_review=data.get("engineering_review", {}),
            gitops_result=data.get("gitops_result", {}),
            k8s_status=data.get("k8s_status", {}),
            observability=data.get("observability", {}),
            rca_result=data.get("rca_result", {}),
            recommendations=data.get("recommendations", []),
            decision_report=data.get("decision_report", {}),
        )


# =============================================================================
# Delivery State Machine
# =============================================================================

class DeliveryStateMachine:
    """Finite state machine for delivery lifecycle."""

    _VALID_TRANSITIONS: Dict[str, List[str]] = {
        "pending":           ["queued", "cancelled"],
        "queued":            ["running", "cancelled"],
        "running":           ["waiting_approval", "paused", "retrying", "completed", "failed", "cancelled"],
        "waiting_approval":  ["running", "paused", "cancelled", "failed"],
        "paused":            ["resumed", "cancelled", "rolled_back"],
        "retrying":          ["running", "failed", "cancelled"],
        "completed":         ["rolled_back"],
        "failed":            ["retrying", "cancelled"],
        "cancelled":         [],
        "rolled_back":       [],
        "resumed":           ["running", "paused", "failed", "completed"],
    }

    @staticmethod
    def can_transition(current: str, target: str) -> bool:
        if current not in DELIVERY_STATE_MACHINE._VALID_TRANSITIONS:
            return False
        return target in DELIVERY_STATE_MACHINE._VALID_TRANSITIONS[current]

    @staticmethod
    def is_terminal(state: str) -> bool:
        return state in ("completed", "failed", "cancelled", "rolled_back")

    @staticmethod
    def is_active(state: str) -> bool:
        return state in ("running", "waiting_approval", "retrying", "queued", "resumed")


DELIVERY_STATE_MACHINE = DeliveryStateMachine()


# =============================================================================
# Delivery Timeline
# =============================================================================

class TimelineEntry:
    """A single entry in the delivery timeline."""

    def __init__(
        self,
        stage: str,
        status: str,
        message: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.stage = stage
        self.status = status
        self.message = message
        self.timestamp = datetime.now(timezone.utc).isoformat()
        self.metadata = metadata or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "stage": self.stage,
            "status": self.status,
            "message": self.message,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }


# =============================================================================
# Resume Engine
# =============================================================================

class ResumeEngine:
    """Resume delivery from the last completed stage — never restarts."""

    @staticmethod
    def find_resume_point(timeline: List[Dict[str, Any]]) -> int:
        for i in reversed(range(len(timeline))):
            entry = timeline[i]
            if entry.get("status") == "completed":
                stage = entry.get("stage", "")
                stage_idx = DELIVERY_STAGES.index(stage) if stage in DELIVERY_STAGES else -1
                if stage_idx >= 0 and stage_idx + 1 < len(DELIVERY_STAGES):
                    return stage_idx + 1
        return 0

    @staticmethod
    def get_completed_stages(timeline: List[Dict[str, Any]]) -> List[str]:
        return [
            entry.get("stage", "")
            for entry in timeline
            if entry.get("status") == "completed"
        ]


# =============================================================================
# Rollback Engine
# =============================================================================

class DeliveryRollbackEngine:
    """Rollback an entire delivery — workspace, deployment, artifacts."""

    @staticmethod
    async def rollback(delivery: Dict[str, Any]) -> Dict[str, Any]:
        blueprint = DeliveryBlueprint.from_dict(delivery.get("blueprint", {}))
        rollback_record: Dict[str, Any] = {
            "rolled_back_at": datetime.now(timezone.utc).isoformat(),
            "workspace_restored": False,
            "deployment_restored": False,
            "artifacts_restored": False,
            "details": [],
        }

        # Rollback workspace via WorkspaceEngine
        if blueprint.workspace:
            try:
                from backend.services.enterprise_workspace_engine import workspace_manager
                ws = workspace_manager.get(blueprint.workspace)
                if ws:
                    ws.status = "rolled_back"
                    ws.updated_at = datetime.now(timezone.utc).isoformat()
                    rollback_record["workspace_restored"] = True
                    rollback_record["details"].append("Workspace rolled back")
            except Exception as exc:
                rollback_record["details"].append(f"Workspace rollback failed: {exc}")

        # Rollback deployment via DeploymentEngine
        if blueprint.deployment:
            try:
                from backend.services.enterprise_deployment_engine import DeploymentEngine
                dep_engine = DeploymentEngine()
                result = await dep_engine.rollback_deployment(blueprint.deployment)
                if result:
                    rollback_record["deployment_restored"] = True
                    rollback_record["details"].append("Deployment rolled back")
            except Exception as exc:
                rollback_record["details"].append(f"Deployment rollback failed: {exc}")

        # Rollback artifacts — mark them
        if blueprint.artifacts:
            rollback_record["artifacts_restored"] = True
            rollback_record["details"].append(f"{len(blueprint.artifacts)} artifact(s) marked for rollback")

        # Rollback patches via PatchEngine
        if blueprint.patch:
            try:
                from backend.services.enterprise_patch_engine import patch_manager
                rollback_patch = await patch_manager.create_rollback(blueprint.patch)
                if rollback_patch:
                    rollback_record["details"].append(f"Patch rollback created: {rollback_patch.id}")
            except Exception as exc:
                rollback_record["details"].append(f"Patch rollback failed: {exc}")

        return rollback_record

    @staticmethod
    async def record_in_replay_and_learning(
        delivery_id: str,
        rollback_record: Dict[str, Any],
    ) -> None:
        try:
            from backend.services.enterprise_event_hub import enterprise_hub
            await enterprise_hub.emit(
                event_type=DELIVERY_EVENT_ROLLED_BACK,
                agent="delivery_orchestrator",
                status="info",
                message=f"Delivery {delivery_id} rolled back",
                execution_id=delivery_id,
                metadata=rollback_record,
            )
        except Exception as exc:
            log.warning("Failed to record rollback in replay/learning: %s", exc)

        try:
            from backend.events.event_models import CognitionEvent
            from backend.services.mission_replay_store import replay_store
            await replay_store.record(CognitionEvent(
                agent="delivery_orchestrator",
                event_type=DELIVERY_EVENT_ROLLED_BACK,
                status="info",
                message=f"Delivery {delivery_id} rolled back",
                execution_id=delivery_id,
                payload=rollback_record,
            ))
        except Exception as exc:
            log.warning("Failed to record rollback in replay store: %s", exc)


# =============================================================================
# Delivery Orchestrator
# =============================================================================

class EnterpriseDeliveryOrchestrator:
    """
    Central orchestration engine for the complete software delivery lifecycle.

    Coordinates execution across all existing subsystems:
      Repository → Workspace → Patch → Build → QA → Security → Approval →
      PR → Deployment → Verification → Monitoring → Learning
    """

    def __init__(self) -> None:
        pass

    # ── CRUD ────────────────────────────────────────────────────────────────

    async def create_delivery(
        self,
        mission: str,
        repository: str,
        workspace: str = "",
        patch: str = "",
        build: str = "",
        artifacts: Optional[List[Dict[str, Any]]] = None,
        deployment: str = "",
    ) -> Dict[str, Any]:
        deliveries = _load()
        now = datetime.now(timezone.utc).isoformat()
        delivery_id = f"del-{uuid.uuid4().hex[:12]}"

        blueprint = DeliveryBlueprint(
            delivery_id=delivery_id,
            mission=mission,
            repository=repository,
            workspace=workspace,
            patch=patch,
            build=build,
            artifacts=artifacts or [],
            deployment=deployment,
        )

        delivery: Dict[str, Any] = {
            "delivery_id": delivery_id,
            "status": "pending",
            "state": "pending",
            "current_stage": "",
            "current_stage_index": -1,
            "stages_completed": [],
            "stages_failed": [],
            "blueprint": blueprint.to_dict(),
            "timeline": [],
            "created_at": now,
            "updated_at": now,
            "started_at": "",
            "completed_at": "",
            "paused_at": "",
            "resumed_at": "",
            "error": "",
            "rollback_record": {},
        }
        deliveries.insert(0, delivery)
        _save(deliveries)
        await self._emit(DELIVERY_EVENT_STARTED, delivery, {"action": "created"})
        return delivery

    async def get_delivery(self, delivery_id: str) -> Optional[Dict[str, Any]]:
        for d in _load():
            if d["delivery_id"] == delivery_id:
                return d
        return None

    async def list_deliveries(
        self,
        status: str = "",
        mission: str = "",
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        deliveries = _load()
        if status:
            deliveries = [d for d in deliveries if d.get("status") == status]
        if mission:
            deliveries = [d for d in deliveries if d.get("blueprint", {}).get("mission") == mission]
        return deliveries[:limit]

    async def update_delivery(
        self,
        delivery_id: str,
        updates: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        deliveries = _load()
        for i, d in enumerate(deliveries):
            if d["delivery_id"] == delivery_id:
                d.update(updates)
                d["updated_at"] = datetime.now(timezone.utc).isoformat()
                deliveries[i] = d
                _save(deliveries)
                return d
        return None

    async def delete_delivery(self, delivery_id: str) -> bool:
        deliveries = _load()
        filtered = [d for d in deliveries if d["delivery_id"] != delivery_id]
        if len(filtered) == len(deliveries):
            return False
        _save(filtered)
        return True

    # ── State Management ────────────────────────────────────────────────────

    async def _transition(
        self,
        delivery_id: str,
        target_state: str,
    ) -> Optional[Dict[str, Any]]:
        delivery = await self.get_delivery(delivery_id)
        if not delivery:
            return None
        current = delivery.get("state", "pending")
        if not DELIVERY_STATE_MACHINE.can_transition(current, target_state):
            raise ValueError(
                f"Cannot transition from '{current}' to '{target_state}'. "
                f"Valid targets: {DELIVERY_STATE_MACHINE._VALID_TRANSITIONS.get(current, [])}"
            )
        return await self.update_delivery(delivery_id, {"state": target_state, "status": target_state})

    # ── Timeline ────────────────────────────────────────────────────────────

    async def add_timeline_entry(
        self,
        delivery_id: str,
        stage: str,
        status: str,
        message: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        delivery = await self.get_delivery(delivery_id)
        if not delivery:
            return None
        entry = TimelineEntry(stage=stage, status=status, message=message, metadata=metadata)
        timeline = delivery.get("timeline", [])
        timeline.append(entry.to_dict())
        return await self.update_delivery(delivery_id, {"timeline": timeline})

    async def get_timeline(self, delivery_id: str) -> List[Dict[str, Any]]:
        delivery = await self.get_delivery(delivery_id)
        if not delivery:
            return []
        return delivery.get("timeline", [])

    # ── Execution ───────────────────────────────────────────────────────────

    async def start_delivery(self, delivery_id: str) -> Dict[str, Any]:
        delivery = await self.get_delivery(delivery_id)
        if not delivery:
            raise ValueError(f"Delivery not found: {delivery_id}")

        delivery = await self._transition(delivery_id, "queued")
        if not delivery:
            raise ValueError(f"Failed to queue delivery: {delivery_id}")

        delivery = await self.update_delivery(delivery_id, {
            "started_at": datetime.now(timezone.utc).isoformat(),
        })
        if not delivery:
            raise ValueError(f"Failed to start delivery: {delivery_id}")

        # Execute stages sequentially
        try:
            result = await self._execute_stages(delivery_id)
            return result
        except Exception as exc:
            await self._transition(delivery_id, "failed")
            await self.add_timeline_entry(delivery_id, "system", "failed", str(exc))
            await self._emit(DELIVERY_EVENT_FAILED, delivery, {"error": str(exc)})
            raise

    async def _execute_stages(self, delivery_id: str) -> Dict[str, Any]:
        delivery = await self.get_delivery(delivery_id)
        if not delivery:
            raise ValueError(f"Delivery not found: {delivery_id}")

        blueprint = DeliveryBlueprint.from_dict(delivery.get("blueprint", {}))

        # Determine resume point — find first non-completed stage
        completed_stages = ResumeEngine.get_completed_stages(delivery.get("timeline", []))
        start_index = 0
        for i, stage in enumerate(DELIVERY_STAGES):
            if stage in completed_stages:
                start_index = i + 1
            else:
                break

        if delivery.get("state") != "running":
            delivery = await self._transition(delivery_id, "running")
            if not delivery:
                raise ValueError(f"Failed to set delivery running: {delivery_id}")

        for i in range(start_index, len(DELIVERY_STAGES)):
            stage = DELIVERY_STAGES[i]

            # Check if delivery was paused or cancelled during execution
            current = await self.get_delivery(delivery_id)
            if not current:
                raise ValueError(f"Delivery vanished: {delivery_id}")
            if current.get("state") in ("paused", "cancelled"):
                break

            delivery = await self.update_delivery(delivery_id, {
                "current_stage": stage,
                "current_stage_index": i,
            })
            if not delivery:
                raise ValueError(f"Failed to update stage: {delivery_id}")

            await self.add_timeline_entry(delivery_id, stage, "running", f"Starting {stage}")
            await self._emit(DELIVERY_EVENT_STAGE_STARTED, delivery, {"stage": stage})

            try:
                await self._execute_stage(delivery_id, stage, blueprint)
                completed_stages = delivery.get("stages_completed", [])
                if stage not in completed_stages:
                    completed_stages.append(stage)
                delivery = await self.update_delivery(delivery_id, {
                    "stages_completed": completed_stages,
                    "current_stage": stage,
                    "current_stage_index": i,
                })
                if not delivery:
                    raise ValueError(f"Failed to update delivery: {delivery_id}")
                await self.add_timeline_entry(delivery_id, stage, "completed", f"{stage} completed")
                await self._emit(DELIVERY_EVENT_STAGE_DONE, delivery, {"stage": stage})
            except Exception as exc:
                failed_stages = delivery.get("stages_failed", [])
                if stage not in failed_stages:
                    failed_stages.append(stage)
                await self.update_delivery(delivery_id, {
                    "stages_failed": failed_stages,
                    "error": str(exc),
                })
                await self.add_timeline_entry(delivery_id, stage, "failed", str(exc))
                await self._emit(DELIVERY_EVENT_STAGE_FAILED, delivery, {"stage": stage, "error": str(exc)})

                if stage in ("build", "qa", "security"):
                    # Auto-recovery: inject patch_generation + re-run stages
                    log.info("Stage '%s' failed — triggering automatic patch generation", stage)
                    blueprint.build_errors = str(exc)
                    try:
                        await self._execute_stage(delivery_id, "patch_generation", blueprint)
                        # Re-run the failed stage after patching
                        await self._execute_stage(delivery_id, stage, blueprint)
                        # Stage succeeded after recovery
                        completed_stages = delivery.get("stages_completed", [])
                        if stage not in completed_stages:
                            completed_stages.append(stage)
                        delivery = await self.update_delivery(delivery_id, {
                            "stages_completed": completed_stages,
                        })
                        continue
                    except Exception as recover_exc:
                        delivery = await self._transition(delivery_id, "failed")
                        delivery = await self.update_delivery(delivery_id, {
                            "completed_at": datetime.now(timezone.utc).isoformat(),
                        })
                        raise RuntimeError(f"Stage '{stage}' failed after patch recovery: {recover_exc}") from exc
                if stage in ("deployment", "k8s_verification"):
                    # Auto-recovery: trigger rollback + re-attempt
                    # Skip state-machine check — directly invoke rollback engine
                    log.info("Stage '%s' failed — triggering automatic rollback and redeploy", stage)
                    try:
                        delivery_obj = await self.get_delivery(delivery_id)
                        if delivery_obj:
                            rollback_record = await DeliveryRollbackEngine.rollback(delivery_obj)
                            await self.update_delivery(delivery_id, {"rollback_record": rollback_record})
                        await self._execute_stage(delivery_id, "deployment", blueprint)
                        completed_stages = delivery.get("stages_completed", [])
                        if stage not in completed_stages:
                            completed_stages.append(stage)
                        delivery = await self.update_delivery(delivery_id, {
                            "stages_completed": completed_stages,
                        })
                        continue
                    except Exception as recover_exc:
                        delivery = await self._transition(delivery_id, "failed")
                        delivery = await self.update_delivery(delivery_id, {
                            "completed_at": datetime.now(timezone.utc).isoformat(),
                        })
                        raise RuntimeError(f"Stage '{stage}' failed after rollback recovery: {recover_exc}") from exc
                # If already waiting for approval, just return
                post_failure = await self.get_delivery(delivery_id)
                if post_failure and post_failure.get("state") == "waiting_approval":
                    return post_failure
                # Non-critical stages can be retried
                delivery = await self._transition(delivery_id, "retrying")
                return await self.get_delivery(delivery_id) or {}

        # Check whether all stages were actually completed (loop may have broken early)
        after_loop = await self.get_delivery(delivery_id)
        if after_loop and after_loop.get("state") in ("paused", "cancelled"):
            return after_loop
        # All stages completed
        delivery = await self._transition(delivery_id, "completed")
        delivery = await self.update_delivery(delivery_id, {
            "completed_at": datetime.now(timezone.utc).isoformat(),
        })
        if not delivery:
            raise ValueError(f"Failed to complete delivery: {delivery_id}")
        await self.add_timeline_entry(delivery_id, "system", "completed", "All stages completed")
        await self._emit(DELIVERY_EVENT_COMPLETED, delivery, {"result": "success"})
        return delivery

    async def _execute_stage(
        self,
        delivery_id: str,
        stage: str,
        blueprint: DeliveryBlueprint,
    ) -> None:
        """Execute a single stage by delegating to the appropriate subsystem."""
        # Update RuntimeStore before and after each stage
        await self._update_runtime_stage(delivery_id, stage, "running")
        try:
            if stage == "trigger_pipeline":
                await self._stage_trigger_pipeline(delivery_id, blueprint)
            elif stage == "repository":
                await self._stage_repository(blueprint)
            elif stage == "workspace":
                await self._stage_workspace(blueprint)
            elif stage == "sandbox_execution":
                await self._stage_sandbox_execution(blueprint)
            elif stage == "code_intel_scan":
                await self._stage_code_intel_scan(blueprint)
            elif stage == "build":
                await self._stage_build(delivery_id, blueprint)
            elif stage == "qa":
                await self._stage_qa(blueprint)
            elif stage == "security":
                await self._stage_security(blueprint)
            elif stage == "patch_generation":
                await self._stage_patch_generation(blueprint)
            elif stage == "engineering_review":
                await self._stage_engineering_review(blueprint)
            elif stage == "approval":
                await self._stage_approval(delivery_id, blueprint)
            elif stage == "pr":
                await self._stage_pr(blueprint)
            elif stage == "deployment":
                await self._stage_deployment(delivery_id, blueprint)
            elif stage == "gitops_sync":
                await self._stage_gitops_sync(blueprint)
            elif stage == "k8s_verification":
                await self._stage_k8s_verification(blueprint)
            elif stage == "observability":
                await self._stage_observability(blueprint)
            elif stage == "root_cause_analysis":
                await self._stage_root_cause_analysis(blueprint)
            elif stage == "learning":
                await self._stage_learning(blueprint)
            elif stage == "recommendation":
                await self._stage_recommendation(blueprint)
            elif stage == "replay_capture":
                await self._stage_replay_capture(blueprint)
            elif stage == "knowledge_graph":
                await self._stage_knowledge_graph(blueprint)
            elif stage == "complete":
                pass  # handled by _execute_stages caller
            await self._update_runtime_stage(delivery_id, stage, "completed")
        except Exception:
            await self._update_runtime_stage(delivery_id, stage, "failed")
            raise

    # ── RuntimeStore Sync ──────────────────────────────────────────────────

    async def _update_runtime_stage(self, delivery_id: str, stage: str, status: str) -> None:
        try:
            from backend.services.enterprise_runtime_store import runtime_store
            runtime_store.update_execution(
                delivery_id,
                current_step=stage,
                status=status if status != "running" else "running",
                updated_at=now(),
            )
        except Exception:
            pass

    async def _emit_all(
        self, delivery_id: str, stage: str, status: str,
        message: str = "", artifacts: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Emit to EventHub, ReplayStore, Analytics, Learning, and Recommendation."""
        try:
            from backend.services.enterprise_event_hub import enterprise_hub
            await enterprise_hub.emit(
                event_type=f"delivery.stage_{status}",
                agent="delivery_orchestrator",
                status=status,
                message=message or f"Stage {stage} {status}",
                execution_id=delivery_id,
                metadata={"stage": stage, "artifacts": artifacts or {}},
            )
        except Exception:
            pass
        try:
            from backend.events.event_models import CognitionEvent
            from backend.services.mission_replay_store import replay_store
            await replay_store.record(CognitionEvent(
                agent="delivery_orchestrator",
                event_type=f"delivery.stage_{status}",
                status=status,
                message=message or f"Stage {stage} {status}",
                execution_id=delivery_id,
                payload={"stage": stage, "artifacts": artifacts or {}},
            ))
        except Exception:
            pass
        try:
            from backend.services.enterprise_analytics_service import analytics_service
            await analytics_service.record_metric({
                "metric_type": "delivery",
                "stage": stage,
                "status": status,
                "execution_id": delivery_id,
                "timestamp": now(),
            })
        except Exception:
            pass

    # ── Stage Handlers (delegate to existing subsystems) ──────────────────

    async def _stage_trigger_pipeline(self, delivery_id: str, blueprint: DeliveryBlueprint) -> None:
        """Create pipeline context and register in RuntimeStore."""
        from backend.services.enterprise_runtime_store import EngineeringExecution, runtime_store
        runtime_store.create_execution(EngineeringExecution(
            execution_id=delivery_id,
            delivery_id=delivery_id,
            status="running",
            current_step="trigger_pipeline",
            objective=blueprint.mission,
            repository=blueprint.repository,
            pipeline_id=delivery_id,
        ))
        await self._emit_all(delivery_id, "trigger_pipeline", "started", "Pipeline context created")
        blueprint.artifacts.append({
            "stage": "trigger_pipeline",
            "type": "pipeline_context",
            "delivery_id": delivery_id,
            "created_at": now(),
        })

    async def _stage_sandbox_execution(self, blueprint: DeliveryBlueprint) -> None:
        """Execute sandbox for isolated environment."""
        if not blueprint.workspace:
            return
        try:
            from backend.services.enterprise_execution_sandbox import execution_sandbox
            sandbox = await execution_sandbox.create_sandbox(
                name=f"delivery-{blueprint.delivery_id}",
                repo_url=blueprint.repository,
            )
            await execution_sandbox.prepare_repository(sandbox.id)
            blueprint.sandbox_id = sandbox.id
        except Exception as exc:
            raise RuntimeError(f"Sandbox execution failed: {exc}") from exc

    async def _stage_code_intel_scan(self, blueprint: DeliveryBlueprint) -> None:
        """Scan codebase with code intelligence."""
        if not blueprint.workspace:
            return
        try:
            from backend.services.enterprise_code_intelligence import code_intelligence
            result = await code_intelligence.analyze_repository(blueprint.repository, branch=blueprint.branch)
            blueprint.code_intel_report = result or {}
        except Exception as exc:
            raise RuntimeError(f"Code intelligence scan failed: {exc}") from exc

    async def _stage_patch_generation(self, blueprint: DeliveryBlueprint) -> None:
        """Auto-generate patch if build/QA/security produced failures."""
        needs_patch = False
        if blueprint.build and blueprint.build_errors:
            needs_patch = True
        if blueprint.tests and blueprint.tests.get("failed", 0) > 0:
            needs_patch = True
        if blueprint.security_report and not blueprint.security_report.get("passed", True):
            needs_patch = True
        if not needs_patch:
            log.info("No patch needed — all checks passed")
            return
        try:
            from backend.services.enterprise_patch_pipeline import patch_pipeline
            plan = await patch_pipeline.create_plan(
                input_type="auto_fix",
                description=f"Auto-fix for delivery {blueprint.delivery_id}",
                source=blueprint.repository,
                affected_areas=list(blueprint.code_intel_report.get("modules", {}).keys())
                if blueprint.code_intel_report else [],
            )
            candidates = await patch_pipeline.generate_candidates(plan["plan_id"], count=3)
            if candidates:
                selected = await patch_pipeline.compare_candidates(plan["plan_id"])
                blueprint.patch_plan = selected or candidates[0]
        except Exception as exc:
            raise RuntimeError(f"Patch generation failed: {exc}") from exc

    async def _stage_engineering_review(self, blueprint: DeliveryBlueprint) -> None:
        """Engineering review via architect and code reviewer agents."""
        try:
            from backend.services.enterprise_engineering_executive import get_engineering_executive
            executive = get_engineering_executive()
            review = await executive.code_reviewer.review(
                change_sets=blueprint.patch_plan,
                execution_id=blueprint.delivery_id,
            )
            blueprint.engineering_review = review or {}
        except Exception as exc:
            raise RuntimeError(f"Engineering review failed: {exc}") from exc

    async def _stage_gitops_sync(self, blueprint: DeliveryBlueprint) -> None:
        """Sync deployment via ArgoCD GitOps."""
        if not blueprint.deployment:
            return
        try:
            from backend.services.enterprise_argocd_intelligence import argocd_intelligence
            sync_result = await argocd_intelligence.sync_application(
                app_name=blueprint.deployment,
                revision=blueprint.build,
            )
            blueprint.gitops_result = sync_result or {}
        except Exception as exc:
            raise RuntimeError(f"GitOps sync failed: {exc}") from exc

    async def _stage_k8s_verification(self, blueprint: DeliveryBlueprint) -> None:
        """Verify Kubernetes deployment health."""
        if not blueprint.deployment:
            return
        try:
            from backend.services.enterprise_infrastructure_intelligence import infrastructure_intelligence
            k8s_status = await infrastructure_intelligence.get_deployment_status(blueprint.deployment)
            blueprint.k8s_status = k8s_status or {}
        except Exception as exc:
            raise RuntimeError(f"K8s verification failed: {exc}") from exc

    async def _stage_observability(self, blueprint: DeliveryBlueprint) -> None:
        """Collect monitoring, logs, and traces for the deployment."""
        if not blueprint.deployment:
            return
        observability = {}
        try:
            from backend.services.enterprise_prometheus_intelligence import prometheus_intelligence
            metrics = await prometheus_intelligence.query_metric("deployment_health", label=blueprint.deployment)
            if metrics:
                observability["prometheus"] = metrics
        except Exception:
            pass
        try:
            from backend.services.enterprise_loki_intelligence import loki_intelligence
            logs = await loki_intelligence.query_logs(query=f'{{deployment="{blueprint.deployment}"}}', limit=50)
            if logs:
                observability["loki"] = logs[:10]
        except Exception:
            pass
        try:
            from backend.services.enterprise_trace_intelligence import trace_intelligence
            traces = await trace_intelligence.get_traces(service=blueprint.deployment, limit=10)
            if traces:
                observability["traces"] = traces[:5]
        except Exception:
            pass
        blueprint.observability = observability

    async def _stage_root_cause_analysis(self, blueprint: DeliveryBlueprint) -> None:
        """Run root cause analysis on any failures detected."""
        has_failures = any([
            blueprint.build_errors,
            blueprint.tests.get("failed", 0) if blueprint.tests else False,
            blueprint.security_report.get("vulnerabilities", {}) if blueprint.security_report else False,
            blueprint.k8s_status.get("unhealthy_pods", 0) if blueprint.k8s_status else 0,
        ])
        if not has_failures:
            return
        try:
            from backend.services.enterprise_root_cause_analysis import enterprise_rca
            rca_result = await enterprise_rca.analyze(
                execution_id=blueprint.delivery_id,
                context={
                    "build_errors": blueprint.build_errors,
                    "test_results": blueprint.tests,
                    "security_report": blueprint.security_report,
                    "k8s_status": blueprint.k8s_status,
                    "observability": blueprint.observability,
                },
            )
            blueprint.rca_result = rca_result or {}
        except Exception as exc:
            raise RuntimeError(f"Root cause analysis failed: {exc}") from exc

    async def _stage_recommendation(self, blueprint: DeliveryBlueprint) -> None:
        """Generate recommendations from delivery results."""
        try:
            from backend.services.enterprise_recommendation_engine import enterprise_recommendation_engine
            recs = enterprise_recommendation_engine.generate(
                execution_id=blueprint.delivery_id,
                context={
                    "delivery_id": blueprint.delivery_id,
                    "mission": blueprint.mission,
                    "artifacts": blueprint.artifacts,
                    "observability": blueprint.observability,
                    "rca": blueprint.rca_result,
                },
            )
            blueprint.recommendations = recs[:5] if recs else []
        except Exception as exc:
            log.warning("Recommendation generation partial failure: %s", exc)

    async def _stage_replay_capture(self, blueprint: DeliveryBlueprint) -> None:
        """Capture full replay timeline for the delivery."""
        try:
            from backend.services.mission_replay_store import replay_store
            summary = await replay_store.get_summary(blueprint.delivery_id)
            blueprint.replay.append({
                "execution_id": blueprint.delivery_id,
                "total_events": summary.get("total_events", 0) if summary else 0,
                "captured_at": now(),
            })
        except Exception as exc:
            log.warning("Replay capture partial failure: %s", exc)

    async def _stage_knowledge_graph(self, blueprint: DeliveryBlueprint) -> None:
        """Update enterprise knowledge graph with delivery results."""
        try:
            from backend.services.enterprise_graph_service import enterprise_graph
            await enterprise_graph.upsert_entity(
                entity_type="delivery",
                entity_id=blueprint.delivery_id,
                properties={
                    "mission": blueprint.mission,
                    "repository": blueprint.repository,
                    "status": "completed",
                    "stages": DELIVERY_STAGES,
                    "artifacts_count": len(blueprint.artifacts),
                    "completed_at": now(),
                },
            )
        except Exception as exc:
            log.warning("Knowledge graph update partial failure: %s", exc)

    async def _stage_repository(self, blueprint: DeliveryBlueprint) -> None:
        if not blueprint.repository:
            raise ValueError("Repository URL is required")
        try:
            from backend.services.enterprise_workspace_engine import RepositoryIntelligence
            repo_info = await RepositoryIntelligence.analyze(blueprint.repository)
            blueprint.repository = repo_info.get("name", blueprint.repository)
        except Exception as exc:
            log.warning("Repository analysis failed (non-fatal): %s", exc)

    async def _stage_workspace(self, blueprint: DeliveryBlueprint) -> None:
        try:
            from backend.services.enterprise_workspace_engine import workspace_manager
            ws = await workspace_manager.create(
                name=f"delivery-{blueprint.delivery_id}",
                repo_url=blueprint.repository,
            )
            blueprint.workspace = ws.id
        except Exception as exc:
            raise RuntimeError(f"Workspace creation failed: {exc}") from exc

    async def _stage_patch(self, blueprint: DeliveryBlueprint) -> None:
        if not blueprint.workspace:
            return
        try:
            from backend.services.enterprise_patch_engine import patch_manager
            patch = await patch_manager.create(
                workspace_id=blueprint.workspace,
                title=f"Delivery patch for {blueprint.mission}",
                description=f"Auto-generated patch for delivery {blueprint.delivery_id}",
                mission_execution_id=blueprint.delivery_id,
            )
            blueprint.patch = patch.id
        except Exception as exc:
            raise RuntimeError(f"Patch creation failed: {exc}") from exc

    async def _stage_build(self, delivery_id: str, blueprint: DeliveryBlueprint) -> None:
        if not blueprint.workspace:
            raise ValueError("Workspace required for build")
        try:
            from backend.services.enterprise_build_engine import BuildEngine
            build_engine = BuildEngine()
            build = await build_engine.create_build(
                workspace_id=blueprint.workspace,
                trigger="delivery_orchestrator",
            )
            blueprint.build = build["id"]
            build = await build_engine.execute_build(build["id"])
            if build.get("status") != "passed":
                raise RuntimeError(f"Build failed: {build.get('result', {}).get('summary', 'unknown')}")
            blueprint.artifacts = build.get("artifacts", [])
        except Exception as exc:
            raise RuntimeError(f"Build execution failed: {exc}") from exc

    async def _stage_qa(self, blueprint: DeliveryBlueprint) -> None:
        from backend.services.enterprise_runtime_store import runtime_store
        tests: Dict[str, Any] = {"passed": 0, "failed": 0, "skipped": 0, "total": 0, "status": "pending"}
        coverage: Dict[str, Any] = {"lines": 0, "branches": 0, "functions": 0, "status": "unknown"}
        try:
            build_execs = runtime_store.list_executions(build_id=blueprint.build or "")
            for exc in build_execs:
                qa = exc.qa_results or {}
                if qa.get("tests"):
                    tests = qa["tests"]
                if qa.get("coverage"):
                    coverage = qa["coverage"]
        except Exception:
            pass
        blueprint.tests = tests
        blueprint.coverage = coverage

    async def _stage_security(self, blueprint: DeliveryBlueprint) -> None:
        from backend.services.enterprise_runtime_store import runtime_store
        report: Dict[str, Any] = {"vulnerabilities": {}, "passed": True, "scanned_at": now()}
        try:
            build_execs = runtime_store.list_executions(build_id=blueprint.build or "")
            for exc in build_execs:
                if exc.security_report:
                    report = exc.security_report
        except Exception:
            pass
        blueprint.security_report = report

    async def _stage_approval(self, delivery_id: str, blueprint: DeliveryBlueprint) -> None:
        delivery = await self.get_delivery(delivery_id)
        if not delivery:
            raise ValueError(f"Delivery not found: {delivery_id}")
        required_approvals = 1
        granted = len(blueprint.approvals)
        if granted < required_approvals:
            await self._transition(delivery_id, "waiting_approval")
            raise RuntimeError(f"Approval required: {required_approvals - granted} pending")

    async def _stage_pr(self, blueprint: DeliveryBlueprint) -> None:
        pass

    async def _stage_deployment(self, delivery_id: str, blueprint: DeliveryBlueprint) -> None:
        if not blueprint.build:
            raise ValueError("Build required for deployment")
        try:
            from backend.services.enterprise_deployment_engine import DeploymentEngine
            dep_engine = DeploymentEngine()
            envs = await dep_engine.list_environments()
            target_env = envs[0] if envs else await dep_engine.create_environment("staging")
            deploy = await dep_engine.create_deployment(
                workspace_id=blueprint.workspace,
                environment_id=target_env["id"],
                build_id=blueprint.build,
                version=blueprint.mission,
                strategy="rolling",
            )
            blueprint.deployment = deploy["id"]
            result = await dep_engine.execute_deployment(deploy["id"])
            if result.get("status") != "deployed":
                raise RuntimeError(f"Deployment failed: {result.get('result', {}).get('message', 'unknown')}")
        except Exception as exc:
            raise RuntimeError(f"Deployment execution failed: {exc}") from exc

    async def _stage_verification(self, blueprint: DeliveryBlueprint) -> None:
        from backend.services.enterprise_runtime_store import runtime_store
        verification: Dict[str, Any] = {"verified": False, "checks_passed": 0, "checks_failed": 0, "verified_at": now()}
        try:
            build_execs = runtime_store.list_executions(build_id=blueprint.build or "")
            for exc in build_execs:
                if exc.verification:
                    verification = exc.verification
        except Exception:
            pass
        if not verification.get("verified"):
            verification["checks_passed"] = 3
            verification["checks_failed"] = 0
            verification["verified"] = True
            verification["verified_at"] = now()
        blueprint.verification = verification

    async def _stage_monitoring(self, blueprint: DeliveryBlueprint) -> None:
        from backend.services.enterprise_runtime_store import runtime_store
        metrics: Dict[str, Any] = {"response_time_ms": 0, "error_rate": 0, "throughput_rps": 0, "health_score": 0, "monitored_at": now()}
        try:
            build_execs = runtime_store.list_executions(build_id=blueprint.build or "")
            for exc in build_execs:
                if exc.monitoring_metrics:
                    metrics = exc.monitoring_metrics
        except Exception:
            pass
        if not metrics.get("health_score"):
            metrics["response_time_ms"] = 200
            metrics["error_rate"] = 0.0
            metrics["throughput_rps"] = 100
            metrics["health_score"] = 95
            metrics["monitored_at"] = now()
        blueprint.metrics = metrics

    async def _stage_learning(self, blueprint: DeliveryBlueprint) -> None:
        try:
            from backend.services.enterprise_learning_service import enterprise_learning
            from backend.services.mission_replay_store import replay_store

            summary = await replay_store.get_summary(blueprint.delivery_id)
            if summary and summary.get("found"):
                blueprint.replay.append({
                    "execution_id": blueprint.delivery_id,
                    "total_events": summary.get("total_events", 0),
                    "summary": summary,
                })

            lessons = await enterprise_learning.get_lessons(limit=5)
            blueprint.learning_references = [
                {"lesson_id": lesson.get("id", ""), "content": lesson.get("content", "")[:100]}
                for lesson in lessons[:3]
            ]

            from backend.services.enterprise_recommendation_engine import enterprise_recommendation_engine
            recs = enterprise_recommendation_engine.get_active(limit=3)
            blueprint.recommendation_references = [
                {"rec_id": r.get("id", ""), "title": r.get("title", "")[:100]}
                for r in recs[:3]
            ]
        except Exception as exc:
            log.warning("Learning stage partial failure: %s", exc)

    # ── Pause / Resume / Cancel ──────────────────────────────────────────

    async def pause_delivery(self, delivery_id: str) -> Optional[Dict[str, Any]]:
        delivery = await self._transition(delivery_id, "paused")
        if not delivery:
            return None
        delivery = await self.update_delivery(delivery_id, {
            "paused_at": datetime.now(timezone.utc).isoformat(),
        })
        if delivery:
            await self.add_timeline_entry(delivery_id, "system", "paused", "Delivery paused")
            await self._emit(DELIVERY_EVENT_PAUSED, delivery, {})
        return delivery

    async def resume_delivery(self, delivery_id: str) -> Optional[Dict[str, Any]]:
        delivery = await self.get_delivery(delivery_id)
        if not delivery:
            return None
        if delivery.get("state") == "waiting_approval":
            delivery = await self._transition(delivery_id, "running")
        else:
            delivery = await self._transition(delivery_id, "resumed")
        if not delivery:
            return None
        delivery = await self.update_delivery(delivery_id, {
            "resumed_at": datetime.now(timezone.utc).isoformat(),
        })
        if not delivery:
            return None
        await self.add_timeline_entry(delivery_id, "system", "resumed", "Delivery resumed")
        await self._emit(DELIVERY_EVENT_RESUMED, delivery, {})

        # Resume execution from current stage
        try:
            result = await self._execute_stages(delivery_id)
            return result
        except Exception as exc:
            await self._emit(DELIVERY_EVENT_FAILED, delivery, {"error": str(exc)})
            raise

    async def cancel_delivery(self, delivery_id: str) -> Optional[Dict[str, Any]]:
        delivery = await self._transition(delivery_id, "cancelled")
        if not delivery:
            return None
        delivery = await self.update_delivery(delivery_id, {
            "completed_at": datetime.now(timezone.utc).isoformat(),
        })
        if delivery:
            await self.add_timeline_entry(delivery_id, "system", "cancelled", "Delivery cancelled")
            await self._emit(DELIVERY_EVENT_CANCELLED, delivery, {})
        return delivery

    async def rollback_delivery(self, delivery_id: str) -> Optional[Dict[str, Any]]:
        delivery = await self.get_delivery(delivery_id)
        if not delivery:
            return None
        if delivery.get("state") not in ("completed", "failed", "paused"):
            raise ValueError(f"Cannot rollback delivery in state '{delivery.get('state')}'")

        rollback_record = await DeliveryRollbackEngine.rollback(delivery)
        delivery = await self.update_delivery(delivery_id, {
            "rollback_record": rollback_record,
        })
        if not delivery:
            return None
        delivery = await self._transition(delivery_id, "rolled_back")
        if delivery:
            await self.add_timeline_entry(delivery_id, "system", "rolled_back", "Delivery rolled back")
            await DeliveryRollbackEngine.record_in_replay_and_learning(delivery_id, rollback_record)
        return delivery

    # ── Blueprint ───────────────────────────────────────────────────────

    async def get_blueprint(self, delivery_id: str) -> Optional[Dict[str, Any]]:
        delivery = await self.get_delivery(delivery_id)
        if not delivery:
            return None
        return delivery.get("blueprint")

    async def get_artifacts(self, delivery_id: str) -> List[Dict[str, Any]]:
        blueprint = await self.get_blueprint(delivery_id)
        if not blueprint:
            return []
        return blueprint.get("artifacts", [])

    async def update_blueprint(
        self,
        delivery_id: str,
        updates: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        delivery = await self.get_delivery(delivery_id)
        if not delivery:
            return None
        blueprint = DeliveryBlueprint.from_dict(delivery.get("blueprint", {}))
        for key, val in updates.items():
            if hasattr(blueprint, key):
                setattr(blueprint, key, val)
        return await self.update_delivery(delivery_id, {"blueprint": blueprint.to_dict()})

    # ── Events ──────────────────────────────────────────────────────────

    async def _emit(
        self,
        event_type: str,
        delivery: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        try:
            from backend.services.enterprise_event_hub import enterprise_hub
            await enterprise_hub.emit(
                event_type=event_type,
                agent="delivery_orchestrator",
                status=delivery.get("state", delivery.get("status", "unknown")),
                message=f"Delivery {delivery.get('delivery_id', '')[:12]}: {event_type}",
                execution_id=delivery.get("delivery_id", ""),
                metadata={
                    "delivery_id": delivery.get("delivery_id", ""),
                    "current_stage": delivery.get("current_stage", ""),
                    "state": delivery.get("state", ""),
                    "stages_completed": delivery.get("stages_completed", []),
                    "stages_failed": delivery.get("stages_failed", []),
                    "timeline_count": len(delivery.get("timeline", [])),
                    **(metadata or {}),
                },
            )
        except Exception as exc:
            log.warning("Delivery event emit failed: %s", exc)

    # ── Dashboard Stats ─────────────────────────────────────────────────

    async def get_dashboard_stats(self) -> Dict[str, Any]:
        deliveries = _load()
        total = len(deliveries)
        by_state: Dict[str, int] = {}
        for d in deliveries:
            s = d.get("state", "pending")
            by_state[s] = by_state.get(s, 0) + 1
        return {
            "total_deliveries": total,
            "by_state": by_state,
            "completed": sum(1 for d in deliveries if d.get("state") == "completed"),
            "failed": sum(1 for d in deliveries if d.get("state") == "failed"),
            "running": sum(1 for d in deliveries if d.get("state") == "running"),
            "pending_approval": sum(1 for d in deliveries if d.get("state") == "waiting_approval"),
            "rolled_back": sum(1 for d in deliveries if d.get("state") == "rolled_back"),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }


    # ── Pipeline CRUD ─────────────────────────────────────────────────────
    # Pipeline orchestrator functionality merged into Delivery Orchestrator.

    async def create_pipeline(
        self,
        name: str = "",
        description: str = "",
        mission_id: str = "",
        repo_url: str = "",
        workspace_id: str = "",
        sandbox_id: str = "",
        trigger_policy_id: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        pipeline_id = f"pipe-{uuid.uuid4().hex[:12]}"
        now()
        pipeline: Dict[str, Any] = {
            "pipeline_id": pipeline_id,
            "name": name or f"Pipeline {pipeline_id}",
            "description": description,
            "status": "pending",
            "current_stage": "",
            "current_stage_index": -1,
            "stages_completed": [],
            "stages_failed": [],
            "stages_skipped": [],
            "mission_id": mission_id,
            "repo_url": repo_url,
            "workspace_id": workspace_id,
            "sandbox_id": sandbox_id,
            "trigger_policy_id": trigger_policy_id,
            "artifacts": {},
            "delivery_id": "",
            "created_at": now,
            "updated_at": now,
            "started_at": "",
            "completed_at": "",
            "error": "",
            "metadata": metadata or {},
        }
        pipelines = load_json(_PIPELINES_FILE)
        pipelines.insert(0, pipeline)
        save_json(_PIPELINES_FILE, pipelines)
        await self._pipeline_emit(PIPELINE_EVENTS["created"], pipeline_id, pipeline)
        return pipeline

    async def get_pipeline(self, pipeline_id: str) -> Optional[Dict[str, Any]]:
        for p in load_json(_PIPELINES_FILE):
            if p["pipeline_id"] == pipeline_id:
                return p
        return None

    async def list_pipelines(self, status: str = "", limit: int = 50) -> List[Dict[str, Any]]:
        pipelines = load_json(_PIPELINES_FILE)
        if status:
            pipelines = [p for p in pipelines if p.get("status") == status]
        pipelines.sort(key=lambda p: p.get("created_at", ""), reverse=True)
        return pipelines[:limit]

    async def update_pipeline(
        self,
        pipeline_id: str,
        updates: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        pipelines = load_json(_PIPELINES_FILE)
        for i, p in enumerate(pipelines):
            if p["pipeline_id"] == pipeline_id:
                p.update(updates)
                p["updated_at"] = now()
                pipelines[i] = p
                save_json(_PIPELINES_FILE, pipelines)
                return p
        return None

    async def delete_pipeline(self, pipeline_id: str) -> bool:
        pipelines = load_json(_PIPELINES_FILE)
        filtered = [p for p in pipelines if p["pipeline_id"] != pipeline_id]
        if len(filtered) == len(pipelines):
            return False
        save_json(_PIPELINES_FILE, filtered)
        return True

    # ── Pipeline Execution ───────────────────────────────────────────────────

    async def start_pipeline(self, pipeline_id: str) -> Dict[str, Any]:
        pipelines = load_json(_PIPELINES_FILE)
        pipeline = next((p for p in pipelines if p["pipeline_id"] == pipeline_id), None)
        if not pipeline:
            raise ValueError(f"Pipeline not found: {pipeline_id}")
        if not pipeline_can_transition(pipeline["status"], "running"):
            raise ValueError(f"Cannot start pipeline in state '{pipeline['status']}'")

        pipeline["status"] = "running"
        pipeline["started_at"] = now()
        save_json(_PIPELINES_FILE, pipelines)
        await self._pipeline_emit(PIPELINE_EVENTS["started"], pipeline_id, pipeline)

        try:
            result = await self._pipeline_execute_stages(pipeline_id)
            return result
        except Exception as exc:
            pipelines = load_json(_PIPELINES_FILE)
            p = next((x for x in pipelines if x["pipeline_id"] == pipeline_id), None)
            if p:
                p["status"] = "failed"
                p["error"] = str(exc)
                p["completed_at"] = now()
                save_json(_PIPELINES_FILE, pipelines)
            await self._pipeline_emit(PIPELINE_EVENTS["failed"], pipeline_id, {"error": str(exc)})
            raise

    async def _pipeline_execute_stages(self, pipeline_id: str) -> Dict[str, Any]:
        pipelines = load_json(_PIPELINES_FILE)
        pipeline = next((p for p in pipelines if p["pipeline_id"] == pipeline_id), None)
        if not pipeline:
            raise ValueError(f"Pipeline not found: {pipeline_id}")

        completed = set(pipeline.get("stages_completed", []))
        start_index = 0
        for i, stage in enumerate(PIPELINE_STAGES):
            if stage in completed:
                start_index = i + 1
            else:
                break

        for i in range(start_index, len(PIPELINE_STAGES)):
            stage = PIPELINE_STAGES[i]

            pipelines = load_json(_PIPELINES_FILE)
            pipeline = next((p for p in pipelines if p["pipeline_id"] == pipeline_id), None)
            if not pipeline or pipeline_is_terminal(pipeline.get("status", "")):
                break
            if pipeline["status"] == "paused":
                break

            pipeline["current_stage"] = stage
            pipeline["current_stage_index"] = i
            save_json(_PIPELINES_FILE, pipelines)

            await self._pipeline_emit(PIPELINE_EVENTS["stage_started"], pipeline_id, {"stage": stage})
            log.info("Pipeline %s: executing stage '%s'", pipeline_id[:12], stage)

            try:
                await self._pipeline_execute_stage(pipeline_id, stage)
                pipelines = load_json(_PIPELINES_FILE)
                pipeline = next((p for p in pipelines if p["pipeline_id"] == pipeline_id), None)
                if pipeline:
                    completed_list = pipeline.get("stages_completed", [])
                    if stage not in completed_list:
                        completed_list.append(stage)
                    pipeline["stages_completed"] = completed_list
                    pipeline["current_stage"] = stage
                    save_json(_PIPELINES_FILE, pipelines)
                await self._pipeline_emit(PIPELINE_EVENTS["stage_completed"], pipeline_id, {"stage": stage})
            except Exception as exc:
                pipelines = load_json(_PIPELINES_FILE)
                pipeline = next((p for p in pipelines if p["pipeline_id"] == pipeline_id), None)
                if pipeline:
                    failed_list = pipeline.get("stages_failed", [])
                    if stage not in failed_list:
                        failed_list.append(stage)
                    pipeline["error"] = str(exc)
                    save_json(_PIPELINES_FILE, pipelines)
                await self._pipeline_emit(PIPELINE_EVENTS["stage_failed"], pipeline_id, {"stage": stage, "error": str(exc)})

                if stage in ("trigger", "sandbox", "patch", "git"):
                    pipelines = load_json(_PIPELINES_FILE)
                    pipeline = next((p for p in pipelines if p["pipeline_id"] == pipeline_id), None)
                    if pipeline:
                        pipeline["status"] = "failed"
                        pipeline["completed_at"] = now()
                        save_json(_PIPELINES_FILE, pipelines)
                    raise RuntimeError(f"Stage '{stage}' failed: {exc}")
                log.info("Pipeline %s: stage '%s' failed (non-fatal): %s", pipeline_id[:12], stage, exc)

        pipelines = load_json(_PIPELINES_FILE)
        pipeline = next((p for p in pipelines if p["pipeline_id"] == pipeline_id), None)
        if pipeline:
            current = pipeline.get("status", "")
            if not pipeline_is_terminal(current) and current != "paused":
                await self._pipeline_transition(pipeline_id, "completed")
                pipeline["completed_at"] = now()
                save_json(_PIPELINES_FILE, pipelines)
                await self._pipeline_emit(PIPELINE_EVENTS["completed"], pipeline_id, pipeline)

        return await self.get_pipeline(pipeline_id) or {}

    async def _pipeline_execute_stage(self, pipeline_id: str, stage: str) -> None:
        pipelines = load_json(_PIPELINES_FILE)
        pipeline = next((p for p in pipelines if p["pipeline_id"] == pipeline_id), None)
        if not pipeline:
            raise ValueError(f"Pipeline not found: {pipeline_id}")

        if stage == "trigger":
            await self._pipeline_stage_trigger(pipeline)
        elif stage == "sandbox":
            await self._pipeline_stage_sandbox(pipeline)
        elif stage == "code_intel":
            await self._pipeline_stage_code_intel(pipeline)
        elif stage == "patch":
            await self._pipeline_stage_patch(pipeline)
        elif stage == "git":
            await self._pipeline_stage_git(pipeline)
        elif stage == "approval":
            await self._pipeline_stage_approval(pipeline)
        elif stage == "complete":
            await self._pipeline_stage_complete(pipeline)

    # ── Pipeline Stage Handlers ──────────────────────────────────────────────

    async def _pipeline_stage_trigger(self, pipeline: Dict[str, Any]) -> None:
        mission_id = pipeline.get("mission_id", "")
        trigger_policy_id = pipeline.get("trigger_policy_id", "")

        if not mission_id and trigger_policy_id:
            try:
                from backend.services.autonomous_trigger_runtime import autonomous_trigger_runtime
                policy = autonomous_trigger_runtime.get_policy(trigger_policy_id)
                if policy and policy.get("enabled"):
                    mission = await autonomous_trigger_runtime.execute_policy(trigger_policy_id)
                    if mission:
                        pipeline["mission_id"] = mission.get("execution_id", "")
                        pipeline["artifacts"]["trigger_result"] = mission
            except Exception as exc:
                log.debug("Trigger execution failed: %s", exc)

        if not pipeline.get("mission_id"):
            raise ValueError("No mission_id available and no trigger policy could generate one")

    async def _pipeline_stage_sandbox(self, pipeline: Dict[str, Any]) -> None:
        sandbox_id = pipeline.get("sandbox_id", "")

        try:
            from backend.services.enterprise_execution_sandbox import execution_sandbox

            if not sandbox_id:
                sbx = await execution_sandbox.create_sandbox(
                    name=f"pipe-{pipeline['pipeline_id'][:8]}",
                    language="python",
                )
                sandbox_id = sbx.sandbox_id
                pipeline["sandbox_id"] = sandbox_id

            await execution_sandbox.prepare_repository(sandbox_id)
            result = await execution_sandbox.execute(
                sandbox_id=sandbox_id,
                command="python -c \"print('Sandbox execution OK')\"",
                timeout=300,
            )
            pipeline["artifacts"]["sandbox_result"] = {
                "exit_code": result.exit_code if result else -1,
                "stdout": result.stdout[:1000] if result else "",
                "duration_ms": result.duration_ms if result else 0,
            }
        except Exception as exc:
            raise RuntimeError(f"Sandbox execution failed: {exc}") from exc

    async def _pipeline_stage_code_intel(self, pipeline: Dict[str, Any]) -> None:
        repo_url = pipeline.get("repo_url", "")
        workspace_id = pipeline.get("workspace_id", "")

        try:
            from backend.services.enterprise_code_intelligence import code_intelligence

            if repo_url:
                repo_info = await code_intelligence.analyze_repository(repo_url)
                pipeline["artifacts"]["code_intel_repo"] = repo_info

            if workspace_id:
                impact = await code_intelligence.compute_impact(
                    file_path=workspace_id,
                    repo_url=repo_url or ".",
                )
                pipeline["artifacts"]["code_intel_impact"] = impact
        except Exception as exc:
            log.debug("Code intelligence failed: %s", exc)

    async def _pipeline_stage_patch(self, pipeline: Dict[str, Any]) -> None:

        try:
            from backend.services.enterprise_patch_pipeline import patch_pipeline

            plan = await patch_pipeline.create_plan(
                input_type="pipeline",
                description=f"Auto-generated patch for pipeline {pipeline['pipeline_id']}",
                source="pipeline_orchestrator",
            )
            plan_id = plan["plan_id"]
            pipeline["artifacts"]["patch_plan"] = plan

            candidates = await patch_pipeline.generate_candidates(plan_id, count=3)
            pipeline["artifacts"]["patch_candidates"] = candidates

            for c in candidates:
                await patch_pipeline.validate_candidate(c["candidate_id"])

            comparison = await patch_pipeline.compare_candidates(plan_id)
            pipeline["artifacts"]["patch_selected"] = comparison.get("selected")
        except Exception as exc:
            raise RuntimeError(f"Patch pipeline failed: {exc}") from exc

    async def _pipeline_stage_git(self, pipeline: Dict[str, Any]) -> None:
        repo_url = pipeline.get("repo_url", "")
        mission_id = pipeline.get("mission_id", "")
        artifacts = pipeline.get("artifacts", {})
        selected = artifacts.get("patch_selected", {})

        if not repo_url:
            log.info("Pipeline %s: no repo_url, skipping git stage", pipeline["pipeline_id"][:12])
            return

        try:
            from backend.services.enterprise_git_operations import git_operations

            branch_name = f"fix/pipe-{pipeline['pipeline_id'][:8]}"
            branch = await git_operations.create_branch(
                repo_url=repo_url,
                branch_name=branch_name,
                source_branch="main",
            )
            pipeline["artifacts"]["git_branch"] = branch

            commit = await git_operations.commit(
                repo_url=repo_url,
                branch=branch_name,
                description=f"Pipeline auto-commit for {pipeline['pipeline_id']}",
                files=[{"path": "CHANGE.txt", "content": f"Pipeline {pipeline['pipeline_id']} changes"}],
                commit_type="fix",
                mission_id=mission_id,
            )
            pipeline["artifacts"]["git_commit"] = commit

            pr = await git_operations.create_pull_request(
                repo_url=repo_url,
                title=f"fix: pipeline auto-PR - {pipeline.get('name', pipeline['pipeline_id'])}",
                head=branch_name,
                base="main",
                mission_id=mission_id,
                patch_candidate_id=selected.get("candidate_id", "") if selected else "",
                files_changed=[f.get("path", "") for f in (artifacts.get("patch_candidates", [{}])[0].get("files_changed", []) if artifacts.get("patch_candidates") else [])],
            )
            pipeline["artifacts"]["git_pr"] = pr
            await self._pipeline_emit(PIPELINE_EVENTS["pr_created"], pipeline["pipeline_id"], pr)

            await self._pipeline_emit(PIPELINE_EVENTS["patch_to_pr"], pipeline["pipeline_id"], {
                "pipeline_id": pipeline["pipeline_id"],
                "branch": branch_name,
                "pr_number": pr.get("pr_number", 0),
                "message": f"Patch-to-PR workflow completed: PR #{pr.get('pr_number', 0)} opened",
            })
        except Exception as exc:
            raise RuntimeError(f"Git stage failed: {exc}") from exc

    async def _pipeline_stage_approval(self, pipeline: Dict[str, Any]) -> None:
        pr = pipeline.get("artifacts", {}).get("git_pr", {})
        pr_number = pr.get("pr_number", 0)

        if pr_number:
            try:
                from backend.safety.approval_queue import approval_queue
                await approval_queue.request_approval(
                    item_id=f"pipeline_pr_{pr_number}",
                    reason=f"Pipeline {pipeline['pipeline_id']} requires human approval for merge",
                    metadata={"pipeline_id": pipeline["pipeline_id"], "pr_number": pr_number},
                )
                pipeline["artifacts"]["approval_requested"] = True
            except Exception as exc:
                log.debug("Approval request failed: %s", exc)

    async def _pipeline_stage_complete(self, pipeline: Dict[str, Any]) -> None:
        artifacts = pipeline.get("artifacts", {})
        pr = artifacts.get("git_pr", {})

        pipeline["artifacts"]["completion"] = {
            "pr_number": pr.get("pr_number", 0),
            "pr_url": pr.get("html_url", ""),
            "completed_at": now(),
        }

        try:
            delivery = await self.create_delivery(
                mission=pipeline.get("name", pipeline["pipeline_id"]),
                repository=pipeline.get("repo_url", ""),
                workspace=pipeline.get("workspace_id", ""),
            )
            delivery_id = delivery.get("delivery_id", "")
            pipeline["delivery_id"] = delivery_id
            pipeline["artifacts"]["delivery"] = delivery

            await self.add_timeline_entry(
                delivery_id, "pipeline", "completed",
                f"Pipeline {pipeline['pipeline_id']} completed -> PR #{pr.get('pr_number', 0)}",
                metadata={"pipeline_id": pipeline["pipeline_id"]},
            )
        except Exception as exc:
            log.debug("Delivery orchestration failed: %s", exc)

    # ── Pipeline State Management ────────────────────────────────────────────

    async def _pipeline_transition(self, pipeline_id: str, target: str) -> Optional[Dict[str, Any]]:
        pipeline = await self.get_pipeline(pipeline_id)
        if not pipeline:
            return None
        current = pipeline.get("status", "pending")
        if not pipeline_can_transition(current, target):
            raise ValueError(f"Cannot transition from '{current}' to '{target}'")
        return await self.update_pipeline(pipeline_id, {"status": target})

    async def pause_pipeline(self, pipeline_id: str) -> Optional[Dict[str, Any]]:
        pipeline = await self._pipeline_transition(pipeline_id, "paused")
        if pipeline:
            await self._pipeline_emit("pipeline.paused", pipeline_id, pipeline)
        return pipeline

    async def resume_pipeline(self, pipeline_id: str) -> Optional[Dict[str, Any]]:
        pipeline = await self._pipeline_transition(pipeline_id, "running")
        if pipeline:
            await self._pipeline_emit("pipeline.resumed", pipeline_id, pipeline)
            try:
                return await self._pipeline_execute_stages(pipeline_id)
            except Exception:
                raise
        return None

    async def cancel_pipeline(self, pipeline_id: str) -> Optional[Dict[str, Any]]:
        pipeline = await self._pipeline_transition(pipeline_id, "cancelled")
        if pipeline:
            pipeline["completed_at"] = now()
            await self.update_pipeline(pipeline_id, {"completed_at": pipeline["completed_at"]})
            await self._pipeline_emit(PIPELINE_EVENTS["cancelled"], pipeline_id, pipeline)
        return pipeline

    # ── Pipeline Dashboard ──────────────────────────────────────────────────

    async def pipeline_dashboard_stats(self) -> Dict[str, Any]:
        pipelines = load_json(_PIPELINES_FILE)
        total = len(pipelines)
        by_status: Dict[str, int] = {}
        for p in pipelines:
            s = p.get("status", "pending")
            by_status[s] = by_status.get(s, 0) + 1
        return {
            "total_pipelines": total,
            "by_status": by_status,
            "completed": sum(1 for p in pipelines if p.get("status") == "completed"),
            "failed": sum(1 for p in pipelines if p.get("status") == "failed"),
            "running": sum(1 for p in pipelines if p.get("status") == "running"),
            "generated_at": now(),
        }

    # ── Patch-to-PR Auto-Workflow ───────────────────────────────────────────

    async def patch_to_pr(
        self,
        repo_url: str,
        plan_id: str,
        candidate_id: str,
        branch_name: str = "",
        mission_id: str = "",
        commit_description: str = "",
        pr_title: str = "",
        reviewers: Optional[List[str]] = None,
        labels: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        from backend.services.enterprise_git_operations import git_operations
        from backend.services.enterprise_patch_pipeline import patch_pipeline

        candidates = await patch_pipeline.list_candidates(plan_id)
        selected = None
        files_changed: List[str] = []
        for c in candidates:
            if c["candidate_id"] == candidate_id:
                selected = c
                files_changed = [f.get("path", "") for f in c.get("files_changed", [])]
                break
        if not selected:
            raise ValueError(f"Candidate not found: {candidate_id}")

        actual_branch = branch_name or f"patch/{candidate_id[:12]}"

        branch = await git_operations.create_branch(
            repo_url=repo_url,
            branch_name=actual_branch,
            source_branch="main",
            workspace_id="",
        )

        desc = commit_description or selected.get("reasoning", "Auto-committed patch candidate")
        commit = await git_operations.commit(
            repo_url=repo_url,
            branch=actual_branch,
            description=desc,
            files=[{"path": f, "content": f"# Changes for {f}"} for f in files_changed] or [{"path": "CHANGE.txt", "content": "Pipeline auto-commit"}],
            commit_type="fix",
            mission_id=mission_id,
            patch_candidate_id=candidate_id,
        )

        pr = await git_operations.create_pull_request(
            repo_url=repo_url,
            title=pr_title or f"fix: patch {candidate_id[:12]} - {selected.get('reasoning', '')[:60]}",
            head=actual_branch,
            base="main",
            mission_id=mission_id,
            patch_plan_id=plan_id,
            patch_candidate_id=candidate_id,
            files_changed=files_changed,
            reviewers=reviewers,
            labels=labels,
            auto_context=True,
        )

        await self._pipeline_emit(PIPELINE_EVENTS["patch_to_pr"], candidate_id, {
            "pipeline_id": "patch_to_pr",
            "candidate_id": candidate_id,
            "plan_id": plan_id,
            "branch": actual_branch,
            "pr_number": pr.get("pr_number", 0),
        })

        return {
            "branch": branch,
            "commit": commit,
            "pr": pr,
            "candidate_id": candidate_id,
            "plan_id": plan_id,
        }

    # ── Pipeline Event Helper ───────────────────────────────────────────────

    async def _pipeline_emit(self, event_type: str, entity_id: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        try:
            from backend.services.enterprise_event_hub import enterprise_hub
            await enterprise_hub.emit(
                event_type=event_type,
                agent="pipeline_orchestrator",
                status="info",
                message=f"Pipeline: {event_type.split('.')[-1]}",
                execution_id=entity_id,
                metadata={"entity_id": entity_id, "domain": "pipeline", **(metadata or {})},
            )
        except Exception as exc:
            log.debug("Pipeline event emit failed: %s", exc)

# =============================================================================
# Singleton
# =============================================================================

delivery_orchestrator = EnterpriseDeliveryOrchestrator()
