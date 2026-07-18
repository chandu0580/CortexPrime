"""
Enterprise Autonomous Engineering Execution Engine — single execution runtime
for complete engineering work from GitHub event to verified deployment.

This is NOT a duplicate planner.
This is NOT a duplicate workspace manager.
This is NOT a duplicate patch engine.

This is a coordinator that orchestrates the existing platform.

Reuses (never duplicates):
  - Executive Runtime           - Repository Brain
  - Decision Engine             - Context Intelligence
  - Engineering Memory          - Predictive Simulation
  - Verification Intelligence   - Workspace Engine
  - Sandbox                     - Patch Pipeline
  - GitHub Integration          - Git Operations
  - Delivery Orchestrator       - CI/CD Intelligence
  - Infrastructure Intelligence - RuntimeStore
  - ReplayStore                 - Knowledge Graph
  - EventHub                    - Learning Engine
  - Code Intelligence
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_EXECUTIONS_FILE = _DATA_DIR / "execution_engine.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _id(prefix: str = "exec") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def _load_json(path: Path) -> Dict[str, Any]:
    try:
        if path.exists():
            with open(path) as f:
                return json.load(f)
    except Exception as exc:
        log.debug("Failed to load %s: %s", path.name, exc)
    return {}


def _save_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)


# =============================================================================
# Phase 1 — Execution State Machine
# =============================================================================


class ExecutionStage(Enum):
    PENDING = "pending"
    PLANNING = "planning"
    WORKSPACE_PREP = "workspace_prep"
    ANALYSIS = "analysis"
    PATCH_GENERATION = "patch_generation"
    SANDBOX_EXECUTION = "sandbox_execution"
    GIT_OPS = "git_ops"
    DEPLOYMENT = "deployment"
    OBSERVABILITY = "observability"
    LEARNING = "learning"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"
    CANCELLED = "cancelled"


STAGE_ORDER = [
    ExecutionStage.PENDING,
    ExecutionStage.PLANNING,
    ExecutionStage.WORKSPACE_PREP,
    ExecutionStage.ANALYSIS,
    ExecutionStage.PATCH_GENERATION,
    ExecutionStage.SANDBOX_EXECUTION,
    ExecutionStage.GIT_OPS,
    ExecutionStage.DEPLOYMENT,
    ExecutionStage.OBSERVABILITY,
    ExecutionStage.LEARNING,
    ExecutionStage.COMPLETED,
]


# =============================================================================
# Execution Record
# =============================================================================


@dataclass
class ExecutionStageRecord:
    stage: str = ""
    status: str = "pending"
    started_at: str = ""
    completed_at: str = ""
    duration_seconds: float = 0.0
    error: str = ""
    result: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutionRecord:
    execution_id: str = ""
    mission_id: str = ""
    delivery_id: str = ""
    repository: str = ""
    branch: str = ""
    commit_sha: str = ""
    service: str = ""
    environment: str = ""
    source: str = ""
    source_event: str = ""

    status: str = "pending"
    current_stage: str = "pending"
    stages: Dict[str, ExecutionStageRecord] = field(default_factory=dict)
    stages_completed: List[str] = field(default_factory=list)
    stages_failed: List[str] = field(default_factory=list)

    objective: str = ""
    decision_report: Dict[str, Any] = field(default_factory=dict)
    context_snapshot_id: str = ""
    workspace_id: str = ""
    sandbox_id: str = ""
    patch_plan_id: str = ""
    patch_candidate_id: str = ""
    pr_number: int = 0
    pr_url: str = ""
    build_id: str = ""
    deployment_id: str = ""
    verification_id: str = ""
    prediction_id: str = ""

    risk_score: float = 0.0
    risk_level: str = "low"
    deployment_strategy: str = "rolling"

    artifacts: List[Dict[str, Any]] = field(default_factory=list)
    logs: List[Dict[str, Any]] = field(default_factory=list)
    timeline: List[Dict[str, Any]] = field(default_factory=list)

    error_message: str = ""
    started_at: str = ""
    completed_at: str = ""
    duration_seconds: float = 0.0

    created_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        base = asdict(self)
        base["stages"] = {
            k: asdict(v) if isinstance(v, ExecutionStageRecord) else v
            for k, v in self.stages.items()
        }
        return base

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> ExecutionRecord:
        stages_raw = data.pop("stages", {})
        stages = {}
        for k, v in stages_raw.items():
            if isinstance(v, dict):
                stages[k] = ExecutionStageRecord(**v)
            else:
                stages[k] = v
        rec = ExecutionRecord(**data)
        rec.stages = stages
        return rec


# =============================================================================
# Enterprise Execution Engine
# =============================================================================


class EnterpriseExecutionEngine:
    """
    Single execution runtime for complete engineering work.

    Phases:
      1. PLANNING          — DecisionEngine + RepositoryBrain + ContextIntelligence
      2. WORKSPACE_PREP    — Workspace Engine
      3. ANALYSIS          — Code Intelligence + Repository Brain
      4. PATCH_GENERATION  — Patch Pipeline
      5. SANDBOX_EXECUTION — Sandbox (build, test, lint, security)
      6. GIT_OPS           — Git Operations (branch, commit, PR)
      7. DEPLOYMENT        — Delivery Orchestrator + CI/CD + ArgoCD
      8. OBSERVABILITY     — Prometheus + Loki + OpenTelemetry
      9. LEARNING          — Verification + Memory + Learning Engine + KG
    """

    def __init__(self) -> None:
        self._executions: Dict[str, ExecutionRecord] = {}
        self._load_persisted()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load_persisted(self) -> None:
        data = _load_json(_EXECUTIONS_FILE)
        for entry in data.get("executions", []):
            try:
                rec = ExecutionRecord.from_dict(entry)
                self._executions[rec.execution_id] = rec
            except Exception as exc:
                log.debug("Skipping invalid execution: %s", exc)
        log.info("Loaded %d executions from persistence", len(self._executions))

    def _persist(self) -> None:
        _save_json(_EXECUTIONS_FILE, {
            "executions": [e.to_dict() for e in self._executions.values()],
        })

    # ------------------------------------------------------------------
    # Core Lifecycle
    # ------------------------------------------------------------------

    async def create_execution(
        self,
        repository: str = "",
        branch: str = "main",
        commit_sha: str = "",
        service: str = "",
        environment: str = "production",
        source: str = "manual",
        source_event: str = "manual_trigger",
        objective: str = "",
    ) -> Dict[str, Any]:
        execution_id = _id()
        now = _now()
        rec = ExecutionRecord(
            execution_id=execution_id,
            repository=repository,
            branch=branch,
            commit_sha=commit_sha,
            service=service,
            environment=environment,
            source=source,
            source_event=source_event,
            objective=objective,
            status="pending",
            current_stage="pending",
            stages={
                s.value: ExecutionStageRecord(stage=s.value, status="pending")
                for s in STAGE_ORDER
            },
            created_at=now,
        )
        self._executions[execution_id] = rec
        self._persist()
        await self._emit_event("execution.created", execution_id, {
            "repository": repository, "branch": branch, "objective": objective,
        })
        return rec.to_dict()

    async def execute(
        self,
        execution_id: str,
        auto_approve: bool = False,
    ) -> Dict[str, Any]:
        rec = self._executions.get(execution_id)
        if not rec:
            return {"error": f"Execution not found: {execution_id}"}

        if rec.status not in ("pending", "failed"):
            return {"error": f"Execution already {rec.status}"}

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._execute_sync, execution_id, auto_approve)

    async def execute_async(
        self,
        execution_id: str,
        auto_approve: bool = False,
    ) -> str:
        asyncio.ensure_future(self._run_execution(execution_id, auto_approve))
        return execution_id

    async def _run_execution(
        self,
        execution_id: str,
        auto_approve: bool = False,
    ) -> None:
        rec = self._executions.get(execution_id)
        if not rec:
            return

        rec.status = "running"
        rec.started_at = _now()
        self._persist()

        try:
            for stage in STAGE_ORDER:
                if stage in (ExecutionStage.PENDING, ExecutionStage.COMPLETED):
                    continue
                if rec.status in ("failed", "cancelled", "rolled_back"):
                    break

                stage_name = stage.value
                rec.current_stage = stage_name
                stage_rec = rec.stages.get(stage_name, ExecutionStageRecord(stage=stage_name))
                stage_rec.status = "running"
                stage_rec.started_at = _now()
                rec.stages[stage_name] = stage_rec
                self._persist()

                await self._emit_event("execution.stage_started", execution_id, {
                    "stage": stage_name,
                })

                try:
                    result = await self._execute_stage(stage, rec, auto_approve)
                    stage_rec.status = "completed"
                    stage_rec.completed_at = _now()
                    stage_rec.result = result or {}
                    rec.stages_completed.append(stage_name)
                    self._append_timeline(rec, stage_name, "completed", f"Stage {stage_name} completed")
                except Exception as exc:
                    stage_rec.status = "failed"
                    stage_rec.completed_at = _now()
                    stage_rec.error = str(exc)
                    rec.stages_failed.append(stage_name)
                    rec.error_message = str(exc)
                    rec.status = "failed"
                    self._append_timeline(rec, stage_name, "failed", str(exc))
                    await self._emit_event("execution.failed", execution_id, {
                        "stage": stage_name, "error": str(exc),
                    })
                    self._persist()
                    return

                self._persist()

            if rec.status != "failed":
                rec.status = "completed"
                rec.current_stage = "completed"
                rec.completed_at = _now()
                if rec.started_at:
                    start = datetime.fromisoformat(rec.started_at)
                    end = datetime.fromisoformat(rec.completed_at)
                    rec.duration_seconds = (end - start).total_seconds()
                self._append_timeline(rec, "completed", "completed", "Execution completed successfully")
                await self._emit_event("execution.completed", execution_id, {
                    "duration_seconds": rec.duration_seconds,
                })

        except Exception as exc:
            rec.status = "failed"
            rec.error_message = str(exc)
            await self._emit_event("execution.failed", execution_id, {
                "error": str(exc),
            })

        self._persist()

    async def _execute_stage(
        self,
        stage: ExecutionStage,
        rec: ExecutionRecord,
        auto_approve: bool,
    ) -> Dict[str, Any]:
        method_map = {
            ExecutionStage.PLANNING: self._stage_planning,
            ExecutionStage.WORKSPACE_PREP: self._stage_workspace_prep,
            ExecutionStage.ANALYSIS: self._stage_analysis,
            ExecutionStage.PATCH_GENERATION: self._stage_patch_generation,
            ExecutionStage.SANDBOX_EXECUTION: self._stage_sandbox,
            ExecutionStage.GIT_OPS: self._stage_git_ops,
            ExecutionStage.DEPLOYMENT: self._stage_deployment,
            ExecutionStage.OBSERVABILITY: self._stage_observability,
            ExecutionStage.LEARNING: self._stage_learning,
        }
        method = method_map.get(stage)
        if not method:
            raise ValueError(f"No handler for stage: {stage}")
        return await method(rec, auto_approve)

    # ------------------------------------------------------------------
    # Phase 1 — Planning
    # ------------------------------------------------------------------

    async def _stage_planning(
        self, rec: ExecutionRecord, auto_approve: bool
    ) -> Dict[str, Any]:
        from backend.services.engineering_decision_engine import (
            EngineeringDecisionEngine,
        )
        from backend.services.enterprise_context_intelligence import (
            enterprise_context_intelligence,
        )
        from backend.services.enterprise_repository_brain import repository_brain

        brain = await repository_brain.get_brain_summary(rec.repository)
        context = await enterprise_context_intelligence.build_snapshot(
            repository=rec.repository,
            branch=rec.branch,
            commit=rec.commit_sha,
            service=rec.service,
            environment=rec.environment,
        )
        rec.context_snapshot_id = context.execution_id if hasattr(context, 'execution_id') else ""

        engine = EngineeringDecisionEngine()
        report = await engine.analyze(
            source=rec.source,
            event_type=rec.source_event,
            payload={},
            repository=rec.repository,
            branch=rec.branch,
            context_snapshot=context,
            repository_brain=brain,
        )
        rec.decision_report = report.to_dict() if hasattr(report, 'to_dict') else {}
        rec.risk_score = report.risk_assessment.score if report and hasattr(report, 'risk_assessment') else 0
        rec.risk_level = report.risk_assessment.level.value if report and hasattr(report, 'risk_assessment') and hasattr(report.risk_assessment, 'level') else "low"
        rec.deployment_strategy = report.deployment_strategy.strategy.value if report and hasattr(report, 'deployment_strategy') and hasattr(report.deployment_strategy, 'strategy') else "rolling"

        return {
            "risk_score": rec.risk_score,
            "risk_level": rec.risk_level,
            "deployment_strategy": rec.deployment_strategy,
            "execution_plan": report.execution_plan.to_dict() if report and hasattr(report, 'execution_plan') and hasattr(report.execution_plan, 'to_dict') else {},
        }

    # ------------------------------------------------------------------
    # Phase 2 — Workspace Preparation
    # ------------------------------------------------------------------

    async def _stage_workspace_prep(
        self, rec: ExecutionRecord, auto_approve: bool
    ) -> Dict[str, Any]:
        from backend.services.enterprise_workspace_engine import workspace_manager

        ws = await workspace_manager.create(
            name=f"exec-{rec.execution_id[:8]}",
            repo_url=_to_github_url(rec.repository) if rec.repository else "",
            branch=rec.branch,
        )
        rec.workspace_id = ws.id if hasattr(ws, 'id') else ""

        await workspace_manager.checkout_branch(rec.workspace_id, rec.branch)
        snapshot = await workspace_manager.capture_snapshot(rec.workspace_id)

        return {
            "workspace_id": rec.workspace_id,
            "snapshot": snapshot or {},
        }

    # ------------------------------------------------------------------
    # Phase 3 — Engineering Analysis
    # ------------------------------------------------------------------

    async def _stage_analysis(
        self, rec: ExecutionRecord, auto_approve: bool
    ) -> Dict[str, Any]:
        from backend.services.enterprise_code_intelligence import code_intelligence
        from backend.services.enterprise_repository_brain import repository_brain

        arch = await repository_brain.get_architecture(rec.repository)
        deps = await repository_brain.get_dependency_graph(rec.repository)
        impact = {}
        if rec.decision_report:
            changed = rec.decision_report.get("change_report", {}).get("changed_files", [])
            for f in changed[:5]:
                try:
                    impact[f] = await code_intelligence.analyze_impact(f, rec.repository)
                except Exception:
                    pass

        return {
            "architecture": arch.to_dict() if hasattr(arch, 'to_dict') else {},
            "dependencies": deps,
            "impact_analysis": impact,
        }

    # ------------------------------------------------------------------
    # Phase 4 — Patch Generation
    # ------------------------------------------------------------------

    async def _stage_patch_generation(
        self, rec: ExecutionRecord, auto_approve: bool
    ) -> Dict[str, Any]:
        from backend.services.enterprise_patch_pipeline import patch_pipeline

        plan = await patch_pipeline.create_plan(
            input_type="execution",
            description=rec.objective or f"Auto execution for {rec.repository}",
            source=rec.source,
            affected_areas=[rec.service] if rec.service else [],
        )
        rec.patch_plan_id = plan.get("plan_id", "")

        candidates = await patch_pipeline.generate_candidates(
            plan_id=rec.patch_plan_id,
            count=3,
        )
        if candidates:
            comparison = await patch_pipeline.compare_candidates(rec.patch_plan_id)
            candidates_list = comparison.get("ranked_candidates", candidates) if isinstance(comparison, dict) else candidates
            best = candidates_list[0] if candidates_list else candidates[0]
            rec.patch_candidate_id = best.get("candidate_id", best.get("id", ""))

            if rec.workspace_id:
                validation = await patch_pipeline.validate_candidate(
                    candidate_id=rec.patch_candidate_id,
                    sandbox_id=rec.workspace_id,
                )
            else:
                validation = {}

            return {
                "plan_id": rec.patch_plan_id,
                "candidate_id": rec.patch_candidate_id,
                "candidates_count": len(candidates),
                "validation": validation or {},
            }

        return {"plan_id": rec.patch_plan_id, "candidates_count": 0}

    # ------------------------------------------------------------------
    # Phase 5 — Execution Sandbox
    # ------------------------------------------------------------------

    async def _stage_sandbox(
        self, rec: ExecutionRecord, auto_approve: bool
    ) -> Dict[str, Any]:
        from backend.services.enterprise_execution_sandbox import execution_sandbox

        sandbox = await execution_sandbox.create_sandbox(
            name=f"exec-{rec.execution_id[:8]}",
            repo_url=_to_github_url(rec.repository) if rec.repository else "",
            branch=rec.branch,
        )
        sb_id = sandbox.id if hasattr(sandbox, 'id') else ""
        rec.sandbox_id = sb_id

        await execution_sandbox.prepare_repository(sb_id)

        build_result = await execution_sandbox.execute(
            sandbox_id=sb_id,
            command="build",
            timeout=600,
        )
        test_result = await execution_sandbox.execute(
            sandbox_id=sb_id,
            command="test",
            timeout=600,
        )
        lint_result = await execution_sandbox.execute(
            sandbox_id=sb_id,
            command="lint",
            timeout=300,
        )
        security_result = await execution_sandbox.execute(
            sandbox_id=sb_id,
            command="security",
            timeout=300,
        )

        artifacts = await execution_sandbox.get_artifacts(sb_id)
        rec.artifacts = artifacts or []

        return {
            "sandbox_id": sb_id,
            "build": build_result.to_dict() if hasattr(build_result, 'to_dict') else {},
            "test": test_result.to_dict() if hasattr(test_result, 'to_dict') else {},
            "lint": lint_result.to_dict() if hasattr(lint_result, 'to_dict') else {},
            "security": security_result.to_dict() if hasattr(security_result, 'to_dict') else {},
            "artifacts_count": len(rec.artifacts),
        }

    # ------------------------------------------------------------------
    # Phase 6 — Git Operations
    # ------------------------------------------------------------------

    async def _stage_git_ops(
        self, rec: ExecutionRecord, auto_approve: bool
    ) -> Dict[str, Any]:
        from backend.services.enterprise_git_operations import git_operations

        repo_url = _to_github_url(rec.repository)
        branch_name = f"cortexprime/exec-{rec.execution_id[:8]}"

        branch = await git_operations.create_branch(
            repo_url=repo_url,
            branch_name=branch_name,
            source_branch=rec.branch,
            workspace_id=rec.workspace_id,
        )

        files = rec.artifacts or []
        commit = await git_operations.commit(
            repo_url=repo_url,
            branch=branch_name,
            description=rec.objective or f"Autonomous execution {rec.execution_id[:8]}",
            files=[{"path": a.get("path", ""), "content": a.get("content", "")} for a in files if a.get("path")],
            mission_id=rec.mission_id,
            patch_candidate_id=rec.patch_candidate_id,
        )

        pr = await git_operations.create_pull_request(
            repo_url=repo_url,
            title=rec.objective or f"Auto: {rec.execution_id[:8]}",
            head=branch_name,
            base=rec.branch,
            mission_id=rec.mission_id,
            patch_plan_id=rec.patch_plan_id,
            patch_candidate_id=rec.patch_candidate_id,
            workspace_id=rec.workspace_id,
        )
        rec.pr_number = pr.get("pr_number", 0)
        rec.pr_url = pr.get("html_url", "")

        return {
            "branch": branch,
            "commit": commit,
            "pull_request": pr,
        }

    # ------------------------------------------------------------------
    # Phase 7 — Deployment
    # ------------------------------------------------------------------

    async def _stage_deployment(
        self, rec: ExecutionRecord, auto_approve: bool
    ) -> Dict[str, Any]:
        from backend.services.enterprise_delivery_orchestrator import delivery_orchestrator

        delivery = await delivery_orchestrator.create_delivery(
            mission=rec.mission_id or rec.execution_id,
            repository=rec.repository,
            workspace=rec.workspace_id,
            patch=rec.patch_candidate_id,
            artifacts=rec.artifacts,
        )
        rec.delivery_id = delivery.get("delivery_id", delivery.get("id", ""))

        started = await delivery_orchestrator.start_delivery(
            delivery_id=rec.delivery_id,
        )

        return {
            "delivery_id": rec.delivery_id,
            "delivery": started,
        }

    # ------------------------------------------------------------------
    # Phase 8 — Observability
    # ------------------------------------------------------------------

    async def _stage_observability(
        self, rec: ExecutionRecord, auto_approve: bool
    ) -> Dict[str, Any]:
        health = {}
        try:
            from backend.services.enterprise_infrastructure_intelligence import (
                infrastructure_intelligence,
            )
            health["kubernetes"] = await infrastructure_intelligence.get_cluster_health()
        except Exception:
            pass

        try:
            from backend.services.enterprise_prometheus_intelligence import alert_intelligence
            health["alerts"] = await alert_intelligence.get_alerts()
        except Exception:
            pass

        try:
            from backend.services.enterprise_loki_intelligence import loki_intelligence
            health["errors"] = await loki_intelligence.check_recent_errors()
        except Exception:
            pass

        try:
            from backend.services.enterprise_trace_intelligence import trace_intelligence
            health["traces"] = await trace_intelligence.get_service_graph()
        except Exception:
            pass

        return {"health": health}

    # ------------------------------------------------------------------
    # Phase 9 — Learning
    # ------------------------------------------------------------------

    async def _stage_learning(
        self, rec: ExecutionRecord, auto_approve: bool
    ) -> Dict[str, Any]:
        result = {}

        try:
            from backend.services.enterprise_verification_intelligence import (
                enterprise_verification_intelligence,
            )
            verification = await enterprise_verification_intelligence.verify(
                execution_id=rec.execution_id,
            )
            rec.verification_id = verification.report_id if hasattr(verification, 'report_id') else ""
            result["verification"] = verification.to_dict() if hasattr(verification, 'to_dict') else {}
        except Exception as exc:
            result["verification_error"] = str(exc)

        try:
            from backend.services.enterprise_engineering_memory import (
                enterprise_engineering_memory,
            )
            experience = await enterprise_engineering_memory.build_experience(
                execution_id=rec.execution_id,
            )
            result["experience_id"] = experience.experience_id if hasattr(experience, 'experience_id') else ""
        except Exception as exc:
            result["memory_error"] = str(exc)

        try:
            from backend.services.enterprise_graph_service import enterprise_graph
            await enterprise_graph.record_mission_completion(
                execution_id=rec.execution_id,
                status=rec.status,
                outcome="success" if rec.status == "completed" else "failed",
            )
            result["knowledge_graph"] = "updated"
        except Exception as exc:
            result["kg_error"] = str(exc)

        try:
            from backend.services.enterprise_learning_service import enterprise_learning
            await enterprise_learning.analyze_mission(execution_id=rec.execution_id)
            result["learning"] = "analyzed"
        except Exception as exc:
            result["learning_error"] = str(exc)

        return result

    # ------------------------------------------------------------------
    # Management
    # ------------------------------------------------------------------

    async def cancel_execution(self, execution_id: str) -> Dict[str, Any]:
        rec = self._executions.get(execution_id)
        if not rec:
            return {"error": "Execution not found"}
        if rec.status in ("completed", "failed", "cancelled", "rolled_back"):
            return {"error": f"Cannot cancel execution in state: {rec.status}"}

        rec.status = ExecutionStage.CANCELLED.value
        rec.current_stage = "cancelled"
        self._persist()
        await self._emit_event("execution.cancelled", execution_id, {})
        return rec.to_dict()

    async def rollback_execution(self, execution_id: str) -> Dict[str, Any]:
        rec = self._executions.get(execution_id)
        if not rec:
            return {"error": "Execution not found"}

        rec.status = ExecutionStage.ROLLED_BACK.value
        rec.current_stage = "rolled_back"
        self._persist()
        await self._emit_event("execution.rolled_back", execution_id, {})
        return rec.to_dict()

    async def retry_execution(self, execution_id: str) -> Dict[str, Any]:
        rec = self._executions.get(execution_id)
        if not rec:
            return {"error": "Execution not found"}
        if rec.status not in ("failed",):
            return {"error": f"Cannot retry execution in state: {rec.status}"}

        rec.status = "pending"
        rec.current_stage = "pending"
        rec.stages_failed = []
        rec.error_message = ""
        for stage_rec in rec.stages.values():
            if isinstance(stage_rec, ExecutionStageRecord):
                stage_rec.status = "pending"
                stage_rec.error = ""
        self._persist()

        asyncio.ensure_future(self._run_execution(execution_id))
        return rec.to_dict()

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_execution(self, execution_id: str) -> Optional[Dict[str, Any]]:
        rec = self._executions.get(execution_id)
        return rec.to_dict() if rec else None

    def list_executions(
        self,
        status: str = "",
        repository: str = "",
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        results = list(self._executions.values())
        if status:
            results = [r for r in results if r.status == status]
        if repository:
            results = [r for r in results if repository in r.repository]
        results.sort(key=lambda r: r.created_at, reverse=True)
        return [r.to_dict() for r in results[:limit]]

    def get_dashboard(self) -> Dict[str, Any]:
        all_execs = list(self._executions.values())
        by_status: Dict[str, int] = {}
        for e in all_execs:
            by_status[e.status] = by_status.get(e.status, 0) + 1

        recent = sorted(all_execs, key=lambda r: r.created_at, reverse=True)[:10]

        return {
            "total_executions": len(all_execs),
            "by_status": by_status,
            "active_count": by_status.get("running", 0) + by_status.get("pending", 0),
            "completed_count": by_status.get("completed", 0),
            "failed_count": by_status.get("failed", 0),
            "recent_executions": [r.to_dict() for r in recent],
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _append_timeline(
        self,
        rec: ExecutionRecord,
        stage: str,
        status: str,
        message: str,
    ) -> None:
        rec.timeline.append({
            "stage": stage,
            "status": status,
            "message": message,
            "timestamp": _now(),
        })
        rec.logs.append({
            "stage": stage,
            "level": "error" if status == "failed" else "info",
            "message": message,
            "timestamp": _now(),
        })

    async def _emit_event(
        self,
        event_type: str,
        execution_id: str,
        metadata: Dict[str, Any],
    ) -> None:
        try:
            from backend.events.event_bus import event_bus
            from backend.events.event_models import CognitionEvent

            await event_bus.publish(
                CognitionEvent(
                    agent="execution_engine",
                    event_type=event_type,
                    status="info",
                    phase="execution_lifecycle",
                    execution_id=execution_id,
                    message=event_type,
                    payload=metadata,
                )
            )
        except Exception:
            pass

    # Internal synchronous fallback
    def _execute_sync(self, execution_id: str, auto_approve: bool) -> Dict[str, Any]:
        import asyncio
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self._run_execution(execution_id, auto_approve))
            rec = self._executions.get(execution_id)
            return rec.to_dict() if rec else {"error": "Execution not found"}
        finally:
            loop.close()


def _to_github_url(repository: str) -> str:
    if repository.startswith("http") or repository.startswith("git@"):
        return repository
    if "/" in repository:
        return f"https://github.com/{repository}"
    return repository


# =============================================================================
# Singleton
# =============================================================================

enterprise_execution_engine = EnterpriseExecutionEngine()
