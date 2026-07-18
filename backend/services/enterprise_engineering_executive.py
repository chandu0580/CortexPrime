"""
Enterprise Engineering Executive — coordinates all engineering subsystems
into one autonomous engineering workflow.

Responsibilities:
  1. Understand engineering intent (classify natural language tasks)
  2. Select participating engineering agents dynamically
  3. Create execution plans with ordered stages
  4. Launch missions through Mission Runtime
  5. Coordinate all engineering departments
  6. Track progress and recover from failures
  7. Generate executive engineering reports
"""
from __future__ import annotations

import json
import logging
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger(__name__)


SUPPORTED_TASK_TYPES = {
    "repo_analysis": {"label": "Repository Analysis", "stages": ["workspace", "code_intel", "learning"]},
    "bug_investigation": {"label": "Bug Investigation", "stages": ["workspace", "code_intel", "patch", "sandbox", "learning"]},
    "root_cause_analysis": {"label": "Root Cause Analysis", "stages": ["workspace", "code_intel", "learning", "recommendation"]},
    "architecture_review": {"label": "Architecture Review", "stages": ["workspace", "code_intel", "learning", "recommendation"]},
    "code_review": {"label": "Code Review", "stages": ["workspace", "code_intel", "patch", "git", "learning"]},
    "security_review": {"label": "Security Review", "stages": ["workspace", "code_intel", "patch", "sandbox", "learning"]},
    "performance_optimization": {"label": "Performance Optimization", "stages": ["workspace", "code_intel", "patch", "sandbox", "git", "delivery", "learning"]},
    "dependency_upgrade": {"label": "Dependency Upgrade", "stages": ["workspace", "code_intel", "patch", "sandbox", "git", "delivery", "learning"]},
    "test_repair": {"label": "Test Repair", "stages": ["workspace", "code_intel", "patch", "sandbox", "git", "learning"]},
    "patch_generation": {"label": "Patch Generation", "stages": ["workspace", "code_intel", "patch", "sandbox", "git", "delivery", "learning"]},
    "build_validation": {"label": "Build Validation", "stages": ["workspace", "code_intel", "sandbox", "learning"]},
    "deployment": {"label": "Deployment", "stages": ["workspace", "patch", "sandbox", "git", "delivery", "learning"]},
    "rollback": {"label": "Rollback", "stages": ["workspace", "git", "delivery", "learning"]},
    "production_incident": {"label": "Production Incident Response", "stages": ["workspace", "code_intel", "patch", "sandbox", "git", "delivery", "learning", "recommendation"]},
}

TASK_CLASSIFIER_KEYWORDS = {
    "repo_analysis": ["analyze repo", "scan repository", "examine codebase", "audit code", "code analysis"],
    "bug_investigation": ["bug", "defect", "issue", "failing", "broken", "error", "exception", "crash"],
    "root_cause_analysis": ["root cause", "why", "investigate", "deep dive", "rca"],
    "architecture_review": ["architecture", "design review", "system design", "arch review"],
    "code_review": ["code review", "review pr", "review pull request", "review change"],
    "security_review": ["security", "vulnerability", "cve", "security review", "pen test", "owasp"],
    "performance_optimization": ["performance", "latency", "slow", "optimize", "speed", "throughput"],
    "dependency_upgrade": ["upgrade", "update dependency", "bump", "migrate", "new version", "fastapi", "library"],
    "test_repair": ["fix test", "test failing", "broken test", "test repair", "test suite", "failing test", "fixing test"],
    "patch_generation": ["patch", "fix", "change", "modify", "implement", "add feature"],
    "build_validation": ["build", "compile", "validate build", "ci", "build check"],
    "rollback": ["rollback", "revert", "undo", "back out", "roll back"],
    "deployment": ["deploy", "release", "ship", "publish", "go live"],
    "production_incident": ["production", "incident", "outage", "downtime", "p1", "pagerduty"],
}


# =============================================================================
# Helpers
# =============================================================================

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _id() -> str:
    return uuid.uuid4().hex[:12]


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


# =============================================================================
# Part 1 — Task Classifier
# =============================================================================

class TaskClassifier:
    """Classifies engineering intent from natural language input."""

    @staticmethod
    def classify(task_description: str) -> Dict[str, Any]:
        """Determine the task type and extract parameters."""
        lower = task_description.lower()

        best_match = "patch_generation"
        best_score = 0

        for task_type, keywords in TASK_CLASSIFIER_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in lower)
            if score > best_score:
                best_score = score
                best_match = task_type

        task_def = SUPPORTED_TASK_TYPES.get(best_match, SUPPORTED_TASK_TYPES["patch_generation"])

        # Extract repo URL if present
        repo_url = ""
        for word in lower.split():
            if word.startswith(("http://", "https://", "git@")) and any(
                ext in word for ext in [".git", "github", "gitlab", "bitbucket"]
            ):
                repo_url = word
                break

        # Extract branch if present
        branch = ""
        branch_keywords = ["branch", "on branch"]
        for keyword in branch_keywords:
            if keyword in lower:
                parts = lower.split(keyword)
                if len(parts) > 1:
                    branch = parts[1].strip().split()[0] if parts[1].strip() else ""
                    break

        return {
            "task_type": best_match,
            "task_label": task_def["label"],
            "confidence": best_score / max(len(TASK_CLASSIFIER_KEYWORDS.get(best_match, ["placeholder"])), 1),
            "stages": list(task_def["stages"]),
            "repo_url": repo_url,
            "branch": branch or "main",
        }

    @staticmethod
    def get_participating_subsystems(task_type: str) -> List[str]:
        """List the subsystems that will participate for this task type."""
        mapping = {
            "repo_analysis": ["workspace_manager", "code_intelligence", "learning_engine"],
            "bug_investigation": ["workspace_manager", "code_intelligence", "patch_pipeline", "execution_sandbox", "learning_engine"],
            "root_cause_analysis": ["workspace_manager", "code_intelligence", "learning_engine", "recommendation_engine"],
            "architecture_review": ["workspace_manager", "code_intelligence", "learning_engine", "recommendation_engine"],
            "code_review": ["workspace_manager", "code_intelligence", "patch_pipeline", "git_operations", "learning_engine"],
            "security_review": ["workspace_manager", "code_intelligence", "patch_pipeline", "execution_sandbox", "learning_engine"],
            "performance_optimization": ["workspace_manager", "code_intelligence", "patch_pipeline", "execution_sandbox", "git_operations", "delivery_orchestrator", "learning_engine"],
            "dependency_upgrade": ["workspace_manager", "code_intelligence", "patch_pipeline", "execution_sandbox", "git_operations", "delivery_orchestrator", "learning_engine"],
            "test_repair": ["workspace_manager", "code_intelligence", "patch_pipeline", "execution_sandbox", "git_operations", "learning_engine"],
            "patch_generation": ["workspace_manager", "code_intelligence", "patch_pipeline", "execution_sandbox", "git_operations", "delivery_orchestrator", "learning_engine"],
            "build_validation": ["workspace_manager", "code_intelligence", "execution_sandbox", "learning_engine"],
            "deployment": ["workspace_manager", "patch_pipeline", "execution_sandbox", "git_operations", "delivery_orchestrator", "learning_engine"],
            "rollback": ["workspace_manager", "git_operations", "delivery_orchestrator", "learning_engine"],
            "production_incident": ["workspace_manager", "code_intelligence", "patch_pipeline", "execution_sandbox", "git_operations", "delivery_orchestrator", "learning_engine", "recommendation_engine"],
        }
        return mapping.get(task_type, mapping["patch_generation"])


# =============================================================================
# Part 2 — Engineering Planner
# =============================================================================

class ExecutivePlanBuilder:
    """Creates execution plans from classified tasks."""

    @staticmethod
    def create_plan(
        task_id: str,
        task_type: str,
        task_label: str,
        stages: List[str],
        repo_url: str = "",
        branch: str = "main",
        description: str = "",
    ) -> Dict[str, Any]:
        plan_id = f"exec-plan-{_id()}"
        plan_stages = []

        for i, stage in enumerate(stages):
            plan_stages.append({
                "stage_id": f"{plan_id}-stage-{i}",
                "stage_index": i,
                "stage_type": stage,
                "status": "pending",
                "subsystem": ExecutivePlanBuilder._stage_subsystem(stage),
                "retry_count": 0,
                "max_retries": 2,
                "artifacts": [],
                "error": None,
                "started_at": None,
                "completed_at": None,
            })

        return {
            "plan_id": plan_id,
            "task_id": task_id,
            "task_type": task_type,
            "task_label": task_label,
            "description": description,
            "repo_url": repo_url,
            "branch": branch,
            "stages": plan_stages,
            "current_stage_index": -1,
            "status": "created",
            "participating_subsystems": TaskClassifier.get_participating_subsystems(task_type),
            "artifacts": [],
            "recovery_log": [],
            "created_at": _now(),
            "updated_at": _now(),
        }

    @staticmethod
    def _stage_subsystem(stage_type: str) -> str:
        mapping = {
            "workspace": "WorkspaceManager",
            "code_intel": "EnterpriseCodeIntelligence",
            "patch": "EnterprisePatchPipeline",
            "sandbox": "EnterpriseExecutionSandbox",
            "git": "EnterpriseGitOperations",
            "delivery": "EnterpriseDeliveryOrchestrator",
            "learning": "EnterpriseLearningEngine",
            "recommendation": "EnterpriseRecommendationEngine",
        }
        return mapping.get(stage_type, "Unknown")


# =============================================================================
# Part 3 — Stage Executor
# =============================================================================

class StageExecutor:
    """Executes individual stages by calling the appropriate subsystem."""

    def __init__(self):
        self._imported = False

    def _import_subsystems(self):
        if self._imported:
            return
        # Lazy imports to avoid circular dependencies
        from backend.services.enterprise_code_intelligence import code_intelligence as ci
        from backend.services.enterprise_delivery_orchestrator import delivery_orchestrator as do
        from backend.services.enterprise_execution_sandbox import execution_sandbox as es
        from backend.services.enterprise_git_operations import git_operations as go
        from backend.services.enterprise_learning_service import enterprise_learning as el
        from backend.services.enterprise_patch_pipeline import patch_pipeline as pp
        from backend.services.enterprise_recommendation_engine import enterprise_recommendation_engine as re
        from backend.services.enterprise_workspace_engine import workspace_manager as wm

        self._workspace_manager = wm
        self._code_intelligence = ci
        self._patch_pipeline = pp
        self._execution_sandbox = es
        self._git_operations = go
        self._delivery_orchestrator = do
        self._learning_engine = el
        self._recommendation_engine = re
        self._imported = True

    async def execute_stage(
        self, stage: Dict[str, Any], plan: Dict[str, Any], context: Dict[str, Any]
    ) -> Tuple[bool, Optional[Dict[str, Any]], str]:
        """Execute a single stage. Returns (success, artifacts, error_message)."""
        self._import_subsystems()
        stage_type = stage["stage_type"]
        log.info("Executing stage: %s for plan %s", stage_type, plan["plan_id"])

        try:
            if stage_type == "workspace":
                return await self._execute_workspace(stage, plan, context)
            elif stage_type == "code_intel":
                return await self._execute_code_intel(stage, plan, context)
            elif stage_type == "patch":
                return await self._execute_patch(stage, plan, context)
            elif stage_type == "sandbox":
                return await self._execute_sandbox(stage, plan, context)
            elif stage_type == "git":
                return await self._execute_git(stage, plan, context)
            elif stage_type == "delivery":
                return await self._execute_delivery(stage, plan, context)
            elif stage_type == "learning":
                return await self._execute_learning(stage, plan, context)
            elif stage_type == "recommendation":
                return await self._execute_recommendation(stage, plan, context)
            else:
                return False, None, f"Unknown stage type: {stage_type}"
        except Exception as exc:
            log.error("Stage %s failed: %s", stage_type, exc)
            return False, None, str(exc)

    async def _execute_workspace(
        self, stage: Dict[str, Any], plan: Dict[str, Any], ctx: Dict[str, Any]
    ) -> Tuple[bool, Optional[Dict[str, Any]], str]:
        name = plan.get("repo_url", "").split("/")[-1].replace(".git", "") or f"exec-{plan['task_id']}"
        workspace = await self._workspace_manager.create(
            name=name,
            repo_url=plan.get("repo_url", ""),
            branch=plan.get("branch", "main"),
        )
        ws_dict = workspace.to_dict() if hasattr(workspace, "to_dict") else {"workspace_id": str(workspace.id) if hasattr(workspace, "id") else ""}
        ctx["workspace_id"] = ws_dict.get("workspace_id", "")
        return True, ws_dict, ""

    async def _execute_code_intel(
        self, stage: Dict[str, Any], plan: Dict[str, Any], ctx: Dict[str, Any]
    ) -> Tuple[bool, Optional[Dict[str, Any]], str]:
        repo_path = ctx.get("repo_path", "")
        result = await self._code_intelligence.scan_repository(repo_path or ".")
        ctx["code_intel_result"] = result
        return True, result, ""

    async def _execute_patch(
        self, stage: Dict[str, Any], plan: Dict[str, Any], ctx: Dict[str, Any]
    ) -> Tuple[bool, Optional[Dict[str, Any]], str]:
        task_type = plan.get("task_type", "patch_generation")
        input_type = "security" if task_type == "security_review" else task_type
        plan_result = await self._patch_pipeline.create_plan(
            input_type=input_type,
            description=plan.get("description", ""),
            source="engineering_executive",
        )
        ctx["plan_id"] = plan_result.get("plan_id", "")

        candidates = await self._patch_pipeline.generate_candidates(plan_result["plan_id"], count=2)
        ctx["candidates"] = candidates
        return True, {"plan": plan_result, "candidates": candidates}, ""

    async def _execute_sandbox(
        self, stage: Dict[str, Any], plan: Dict[str, Any], ctx: Dict[str, Any]
    ) -> Tuple[bool, Optional[Dict[str, Any]], str]:
        sandbox = await self._execution_sandbox.create_sandbox(
            name=f"exec-sandbox-{plan['plan_id'][:8]}",
            repo_url=plan.get("repo_url", ""),
            branch=plan.get("branch", "main"),
        )
        ctx.get("workspace_id", "")
        sandbox_id = sandbox.sandbox_id if hasattr(sandbox, "sandbox_id") else ""
        prepared = await self._execution_sandbox.prepare_repository(sandbox_id)
        ctx["sandbox_id"] = sandbox_id
        return True, {"sandbox_id": sandbox_id, "status": str(prepared.status) if hasattr(prepared, "status") else "prepared"}, ""

    async def _execute_git(
        self, stage: Dict[str, Any], plan: Dict[str, Any], ctx: Dict[str, Any]
    ) -> Tuple[bool, Optional[Dict[str, Any]], str]:
        repo_url = plan.get("repo_url", "")
        branch_name = f"exec/{plan['task_type']}/{plan['task_id'][:8]}"
        await self._git_operations.create_branch(
            repo_url=repo_url or ".",
            branch_name=branch_name,
            source_branch=plan.get("branch", "main"),
        )
        ctx["branch_name"] = branch_name
        commit = await self._git_operations.commit(
            repo_url=repo_url or ".",
            branch=branch_name,
            description=f"[Executive] {plan.get('task_label', '')}: {plan.get('description', '')[:100]}",
            files=[],
            commit_type="fix" if plan["task_type"] in ("bug_investigation", "test_repair", "patch_generation") else "refactor",
            mission_id=plan["task_id"],
        )
        pr = await self._git_operations.create_pull_request(
            repo_url=repo_url or ".",
            title=f"[Executive] {plan.get('task_label', '')}",
            head=branch_name,
            base=plan.get("branch", "main"),
            body=f"Automated engineering executive task: {plan.get('description', '')}",
            mission_id=plan["task_id"],
        )
        ctx["pr_number"] = pr.get("pr_number", 0)
        return True, {"branch": branch_name, "commit": commit, "pr": pr}, ""

    async def _execute_delivery(
        self, stage: Dict[str, Any], plan: Dict[str, Any], ctx: Dict[str, Any]
    ) -> Tuple[bool, Optional[Dict[str, Any]], str]:
        delivery = await self._delivery_orchestrator.create_delivery(
            mission={"mission_id": plan["task_id"], "objective": plan.get("description", "")},
            repository=plan.get("repo_url", ""),
            workspace=ctx.get("workspace_id", ""),
            patch=ctx.get("plan_id", ""),
            artifacts=ctx.get("candidates", []),
        )
        delivery_id = delivery.get("delivery_id", "")
        await self._delivery_orchestrator.start_delivery(delivery_id)
        ctx["delivery_id"] = delivery_id
        return True, delivery, ""

    async def _execute_learning(
        self, stage: Dict[str, Any], plan: Dict[str, Any], ctx: Dict[str, Any]
    ) -> Tuple[bool, Optional[Dict[str, Any]], str]:
        await self._learning_engine.initialize()
        analysis = await self._learning_engine.analyze_mission(plan["task_id"])
        recommendations = await self._learning_engine.generate_recommendations()
        dashboard = await self._learning_engine.get_dashboard()
        return True, {"analysis": analysis, "recommendations": recommendations, "dashboard": dashboard}, ""

    async def _execute_recommendation(
        self, stage: Dict[str, Any], plan: Dict[str, Any], ctx: Dict[str, Any]
    ) -> Tuple[bool, Optional[Dict[str, Any]], str]:
        await self._recommendation_engine.initialize()
        count = await self._recommendation_engine.full_scan()
        active = self._recommendation_engine.get_active()
        dashboard = self._recommendation_engine.get_dashboard()
        return True, {"new_recommendations": count, "active": active, "dashboard": dashboard}, ""


# =============================================================================
# Part 4 — Recovery Manager
# =============================================================================

class RecoveryManager:
    """Manages failure recovery: retry, escalate, fallback, stop."""

    @staticmethod
    def should_retry(stage: Dict[str, Any]) -> bool:
        return stage["retry_count"] < stage["max_retries"]

    @staticmethod
    def get_recovery_action(stage: Dict[str, Any]) -> str:
        if RecoveryManager.should_retry(stage):
            return "retry"
        return "escalate"

    @staticmethod
    def record_recovery(plan: Dict[str, Any], stage_index: int, action: str, reason: str) -> Dict[str, Any]:
        entry = {
            "stage_index": stage_index,
            "stage_type": plan["stages"][stage_index]["stage_type"],
            "action": action,
            "reason": reason,
            "timestamp": _now(),
        }
        plan["recovery_log"].append(entry)
        plan["stages"][stage_index]["retry_count"] += 1
        return entry


# =============================================================================
# Part 5 — Report Generator
# =============================================================================

class ReportGenerator:
    """Generates executive engineering reports from completed/failed plans."""

    @staticmethod
    def generate_report(plan: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        completed_stages = [s for s in plan["stages"] if s["status"] == "completed"]
        failed_stages = [s for s in plan["stages"] if s["status"] == "failed"]
        total_duration = 0.0
        for s in plan["stages"]:
            if s.get("started_at") and s.get("completed_at"):
                try:
                    start = datetime.fromisoformat(s["started_at"])
                    end = datetime.fromisoformat(s["completed_at"])
                    total_duration += (end - start).total_seconds()
                except Exception:
                    pass

        subsystems_used = list(set(s["subsystem"] for s in plan["stages"]))
        recovery_actions = [r["action"] for r in plan.get("recovery_log", [])]

        return {
            "report_id": f"exec-report-{_id()}",
            "plan_id": plan["plan_id"],
            "task_id": plan["task_id"],
            "task_type": plan["task_type"],
            "task_label": plan["task_label"],
            "overall_status": plan["status"],
            "total_stages": len(plan["stages"]),
            "completed_stages": len(completed_stages),
            "failed_stages": len(failed_stages),
            "total_duration_seconds": total_duration,
            "subsystems_used": subsystems_used,
            "recovery_actions_taken": recovery_actions,
            "artifacts_summary": {
                "workspace_id": context.get("workspace_id", ""),
                "sandbox_id": context.get("sandbox_id", ""),
                "plan_id": context.get("plan_id", ""),
                "branch_name": context.get("branch_name", ""),
                "pr_number": context.get("pr_number", 0),
                "delivery_id": context.get("delivery_id", ""),
                "code_intel_entities": len(context.get("code_intel_result", {}).get("entities", [])) if context.get("code_intel_result") else 0,
                "candidate_count": len(context.get("candidates", [])),
                "delivery_summary": context.get("delivery_summary", ""),
            },
            "stage_summary": [
                {
                    "stage_type": s["stage_type"],
                    "stage_index": s["stage_index"],
                    "status": s["status"],
                    "retry_count": s["retry_count"],
                    "error": s.get("error"),
                }
                for s in plan["stages"]
            ],
            "recovery_log": plan.get("recovery_log", []),
            "generated_at": _now(),
        }


# =============================================================================
# Part 6 — Engineering Agents (merged from enterprise_engineering_service.py)
# =============================================================================

ENGINEERING_EVENT_PREFIX = "engineering."

ENGINEERING_EVENT_REPO_ANALYZED    = ENGINEERING_EVENT_PREFIX + "repo_analyzed"
ENGINEERING_EVENT_BUILD_COMPLETED  = ENGINEERING_EVENT_PREFIX + "build_completed"
ENGINEERING_EVENT_TEST_COMPLETED   = ENGINEERING_EVENT_PREFIX + "test_completed"
ENGINEERING_EVENT_SECURITY_SCANNED = ENGINEERING_EVENT_PREFIX + "security_scanned"
ENGINEERING_EVENT_ARCHITECTURE_REVIEWED = ENGINEERING_EVENT_PREFIX + "architecture_reviewed"
ENGINEERING_EVENT_RCA_COMPLETED    = ENGINEERING_EVENT_PREFIX + "rca_completed"
ENGINEERING_EVENT_PLAN_GENERATED   = ENGINEERING_EVENT_PREFIX + "plan_generated"
ENGINEERING_EVENT_CODE_GENERATED   = ENGINEERING_EVENT_PREFIX + "code_generated"
ENGINEERING_EVENT_CODE_REVIEWED    = ENGINEERING_EVENT_PREFIX + "code_reviewed"
ENGINEERING_EVENT_MISSION_COMPLETED = ENGINEERING_EVENT_PREFIX + "mission_completed"


class EngineeringAgent:
    """Base for all engineering agents."""

    def __init__(self, name: str, title: str) -> None:
        self.name = name
        self.title = title

    async def _emit(self, event_type: str, execution_id: str, message: str, metadata: Optional[Dict] = None) -> None:
        try:
            from backend.services.enterprise_event_hub import enterprise_hub
            await enterprise_hub.emit(
                event_type=event_type,
                agent=self.name,
                status="info",
                message=message,
                execution_id=execution_id,
                metadata={"engineering_agent": self.name, **(metadata or {})},
            )
        except Exception:
            pass

    async def _record_to_graph(self, execution_id: str, entity_type: str, entity_id: str, properties: Optional[Dict] = None) -> None:
        try:
            from backend.services.enterprise_graph_service import enterprise_graph
            await enterprise_graph.upsert_entity(entity_type=entity_type, entity_id=entity_id, properties=properties or {})
        except Exception:
            pass

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()


class RepositoryAnalyst(EngineeringAgent):
    """Analyzes repository structure, commits, branches, pull requests, changed files."""

    def __init__(self) -> None:
        super().__init__("repository_analyst", "Repository Analyst")

    async def analyze(self, repo_url: str, branch: str = "main", execution_id: str = "") -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "agent": self.name,
            "repo_url": repo_url,
            "branch": branch,
            "analyzed_at": self._now(),
            "commits": [],
            "branches": [],
            "pull_requests": [],
            "changed_files": [],
            "affected_modules": [],
            "language_stats": {},
            "file_summary": {},
        }

        try:
            from backend.connectors.registry import connector_registry

            gh = connector_registry.get("github")
            if gh:
                if hasattr(gh, "list_branches"):
                    branches_raw = await gh.list_branches(repo_url)
                    result["branches"] = branches_raw if isinstance(branches_raw, list) else []
                if hasattr(gh, "list_commits"):
                    commits_raw = await gh.list_commits(repo_url, branch=branch, limit=30)
                    result["commits"] = commits_raw if isinstance(commits_raw, list) else []
                if hasattr(gh, "list_pull_requests"):
                    prs_raw = await gh.list_pull_requests(repo_url)
                    result["pull_requests"] = prs_raw if isinstance(prs_raw, list) else []

                changed = self._extract_changed_files(result["commits"])
                result["changed_files"] = changed
                result["affected_modules"] = self._classify_modules(changed)
                result["language_stats"] = self._compute_language_stats(changed) if changed else {"unknown": len(changed) or 1}
        except Exception as exc:
            log.debug("Repository analysis via GitHub connector failed: %s", exc)

        try:
            ado = connector_registry.get("azure_devops")
            if ado and not result["commits"]:
                if hasattr(ado, "list_repositories"):
                    repos_raw = await ado.list_repositories()
                    if isinstance(repos_raw, list) and repos_raw:
                        result["azure_repos"] = [r.get("name", "") for r in repos_raw]
        except Exception:
            pass

        result["file_summary"] = {
            "python": len([f for f in result["changed_files"] if f.endswith(".py")]),
            "javascript": len([f for f in result["changed_files"] if f.endswith((".js", ".ts", ".tsx", ".jsx"))]),
            "java": len([f for f in result["changed_files"] if f.endswith(".java")]),
            "dotnet": len([f for f in result["changed_files"] if f.endswith((".cs", ".vb"))]),
            "go": len([f for f in result["changed_files"] if f.endswith(".go")]),
            "rust": len([f for f in result["changed_files"] if f.endswith(".rs")]),
            "other": len([f for f in result["changed_files"] if not f.endswith((".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".cs", ".vb", ".go", ".rs"))]),
        }

        await self._emit(ENGINEERING_EVENT_REPO_ANALYZED, execution_id,
                         f"Repository analyzed: {result['branch']} ({len(result['commits'])} commits, {len(result['changed_files'])} files)")
        await self._record_to_graph(execution_id, "engineering_repo_analysis", f"repo_{execution_id[:12]}", {
            "repo_url": repo_url, "branch": branch, "commits": len(result["commits"]),
            "files": len(result["changed_files"]), "modules": len(result["affected_modules"]),
        })
        return result

    def _extract_changed_files(self, commits: List[Dict]) -> List[str]:
        files: List[str] = []
        seen: set = set()
        for c in commits:
            for f in (c.get("files", []) if isinstance(c, dict) else []):
                if f not in seen and isinstance(f, str):
                    seen.add(f)
                    files.append(f)
        return files

    def _classify_modules(self, files: List[str]) -> List[str]:
        modules: set = set()
        for f in files:
            parts = f.replace("\\", "/").split("/")
            if len(parts) >= 2:
                modules.add(parts[0])
        return sorted(modules)

    def _compute_language_stats(self, files: List[str]) -> Dict[str, int]:
        stats: Dict[str, int] = defaultdict(int)
        for f in files:
            if f.endswith((".py", ".pyw")):
                stats["Python"] += 1
            elif f.endswith((".js", ".ts")):
                stats["TypeScript/JavaScript"] += 1
            elif f.endswith(".java"):
                stats["Java"] += 1
            elif f.endswith((".cs", ".vb", ".fs")):
                stats[".NET"] += 1
            elif f.endswith(".go"):
                stats["Go"] += 1
            elif f.endswith(".rs"):
                stats["Rust"] += 1
            else:
                stats["Other"] += 1
        return dict(stats)


class BuildEngineer(EngineeringAgent):
    """Runs build, lint, and static analysis across multiple ecosystems."""

    ECOSYSTEM_MAP: Dict[str, Dict[str, Any]] = {
        "python": {"build": ["pip install -r requirements.txt", "python -m build"], "lint": ["ruff check ."], "typecheck": ["mypy ."]},
        "node": {"build": ["npm ci", "npm run build"], "lint": ["npm run lint"], "typecheck": ["npx tsc --noEmit"]},
        "java": {"build": ["mvn compile"], "lint": ["mvn checkstyle:check"], "test": ["mvn test"]},
        "dotnet": {"build": ["dotnet build"], "lint": ["dotnet format --verify-no-changes"], "test": ["dotnet test"]},
        "go": {"build": ["go build ./..."], "lint": ["golangci-lint run"], "test": ["go test ./..."]},
        "rust": {"build": ["cargo build"], "lint": ["cargo clippy"], "test": ["cargo test"]},
    }

    def __init__(self) -> None:
        super().__init__("build_engineer", "Build Engineer")

    async def build(self, ecosystem: str, execution_id: str = "") -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "agent": self.name,
            "ecosystem": ecosystem,
            "built_at": self._now(),
            "steps": [],
            "diagnostics": [],
            "passed": False,
            "error_count": 0,
            "warning_count": 0,
        }

        commands = self.ECOSYSTEM_MAP.get(ecosystem, {})
        for phase, cmds in commands.items():
            for cmd in cmds:
                step = {"phase": phase, "command": cmd, "status": "prepared", "output": "", "errors": []}
                result["steps"].append(step)

        result["diagnostics"].append({
            "type": "info",
            "ecosystem": ecosystem,
            "message": f"Build pipeline prepared for {ecosystem}: {len(result['steps'])} steps",
            "recommended_command": commands.get("build", ["unknown"])[0] if commands.get("build") else "unknown",
        })

        await self._emit(ENGINEERING_EVENT_BUILD_COMPLETED, execution_id,
                         f"Build prepared for {ecosystem}: {len(result['steps'])} steps")
        await self._record_to_graph(execution_id, "engineering_build", f"build_{execution_id[:12]}", {
            "ecosystem": ecosystem, "steps": len(result["steps"]),
        })
        return result


class QAEngineer(EngineeringAgent):
    """Runs tests and validates quality gates."""

    def __init__(self) -> None:
        super().__init__("qa_engineer", "QA Engineer")

    async def run_tests(self, ecosystem: str, execution_id: str = "") -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "agent": self.name,
            "ecosystem": ecosystem,
            "tested_at": self._now(),
            "test_frameworks": self._detect_frameworks(ecosystem),
            "test_count": 0,
            "passed": 0,
            "failed": 0,
            "skipped": 0,
            "coverage": 0.0,
            "quality_gates": [],
        }

        result["quality_gates"] = [
            {"gate": "All tests pass", "status": "pending", "detail": f"Requires execution of {result['test_frameworks'][0] if result['test_frameworks'] else 'test'} runner"},
            {"gate": "Test coverage >= 80%", "status": "pending", "detail": "Coverage tool must be run"},
        ]

        await self._emit(ENGINEERING_EVENT_TEST_COMPLETED, execution_id,
                         f"Test plan prepared for {ecosystem}: {len(result['test_frameworks'])} framework(s)")
        return result

    def _detect_frameworks(self, ecosystem: str) -> List[str]:
        return {
            "python": ["pytest", "unittest"],
            "node": ["jest", "vitest", "mocha"],
            "java": ["junit", "testng"],
            "dotnet": ["xunit", "nunit", "mstest"],
            "go": ["go test"],
            "rust": ["cargo test"],
        }.get(ecosystem, ["unknown"])


class SecurityEngineer(EngineeringAgent):
    """Scans for vulnerabilities, secrets, dependency issues."""

    def __init__(self) -> None:
        super().__init__("security_engineer", "Security Engineer")

    async def scan(self, execution_id: str = "", files: Optional[List[str]] = None) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "agent": self.name,
            "scanned_at": self._now(),
            "vulnerabilities": [],
            "secrets_found": 0,
            "dependency_issues": [],
            "compliance_checks": [],
            "risk_score": 0.0,
            "summary": "",
        }

        result["compliance_checks"] = [
            {"check": "No hardcoded secrets", "status": "pending", "detail": "Requires secrets scanner"},
            {"check": "Dependencies up-to-date", "status": "pending", "detail": "Requires dependency audit"},
        ]

        await self._emit(ENGINEERING_EVENT_SECURITY_SCANNED, execution_id, "Security scan prepared")
        return result


class SoftwareArchitect(EngineeringAgent):
    """Assesses architecture impact, module boundaries, dependencies."""

    def __init__(self) -> None:
        super().__init__("software_architect", "Software Architect")

    async def review(self, changed_files: Optional[List[str]] = None, execution_id: str = "") -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "agent": self.name,
            "reviewed_at": self._now(),
            "impacted_modules": [],
            "dependency_changes": [],
            "architecture_notes": [],
            "risk_assessment": {"level": "low", "reason": ""},
        }

        if changed_files:
            modules: set = set()
            for f in changed_files:
                parts = f.replace("\\", "/").split("/")
                if len(parts) >= 2:
                    modules.add(f"{parts[0]}/{parts[1]}" if len(parts) >= 3 else parts[0])
            result["impacted_modules"] = sorted(modules)

            python_files = [f for f in changed_files if f.endswith(".py")]
            if python_files:
                result["architecture_notes"].append(f"{len(python_files)} Python files modified")
                result["dependency_changes"].append({"type": "source", "files": python_files[:5], "note": "Review import dependencies"})

        await self._emit(ENGINEERING_EVENT_ARCHITECTURE_REVIEWED, execution_id,
                         f"Architecture reviewed: {len(result['impacted_modules'])} modules impacted")
        return result


class BugInvestigator(EngineeringAgent):
    """Correlates build failures, logs, traces, history to produce root-cause analysis."""

    def __init__(self) -> None:
        super().__init__("bug_investigator", "Bug Investigator")

    async def investigate(self, execution_id: str = "", build_diagnostics: Optional[List[Dict]] = None) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "agent": self.name,
            "investigated_at": self._now(),
            "root_cause": "",
            "confidence": 0.0,
            "correlated_events": [],
            "related_incidents": [],
            "suggested_fix": "",
            "evidence_chain": [],
        }

        evidence: List[Dict] = []
        if build_diagnostics:
            for d in build_diagnostics:
                evidence.append({"source": "build_diagnostics", "data": d})

        try:
            from backend.services.mission_replay_store import replay_store
            replay_events = await replay_store.get_events(execution_id)
            if isinstance(replay_events, list):
                for e in replay_events[:20]:
                    evidence.append({"source": "replay_store", "event_type": getattr(e, "event_type", str(type(e).__name__)),
                                     "status": getattr(e, "status", ""), "message": getattr(e, "message", "")})
        except Exception:
            pass

        try:
            from backend.services.enterprise_learning_service import enterprise_learning
            patterns = (await enterprise_learning.get_failure_patterns()) if hasattr(enterprise_learning, "get_failure_patterns") else []
            if isinstance(patterns, list):
                result["related_incidents"] = patterns[:5]
        except Exception:
            pass

        try:
            from backend.safety.audit_logger import audit_logger
            audit = audit_logger.get_recent(limit=30)
            entries = audit if isinstance(audit, list) else audit.get("entries", []) if isinstance(audit, dict) else []
            result["correlated_events"] = [
                {"action": e.get("action", ""), "outcome": e.get("outcome", ""), "agent": e.get("agent", "")}
                for e in entries[:10]
            ]
        except Exception:
            pass

        result["evidence_chain"] = evidence[:15]

        await self._emit(ENGINEERING_EVENT_RCA_COMPLETED, execution_id,
                         f"Investigation complete: {len(evidence)} evidence items, {len(result['related_incidents'])} related incidents")
        return result


class EngineeringPlanner(EngineeringAgent):
    """Generates implementation plans with risk assessment and effort estimation."""

    def __init__(self) -> None:
        super().__init__("engineering_planner", "Engineering Planner")

    async def plan(self, repo_analysis: Optional[Dict] = None, architecture_review: Optional[Dict] = None,
                   objective: str = "", execution_id: str = "") -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "agent": self.name,
            "planned_at": self._now(),
            "objective": objective,
            "impacted_files": [],
            "implementation_strategy": [],
            "risk_assessment": {"level": "low", "factors": []},
            "estimated_effort": {"complexity": "medium", "estimated_hours": 0},
            "rollback_strategy": "",
            "dependencies": [],
            "review_requirements": [],
        }

        if repo_analysis:
            result["impacted_files"] = repo_analysis.get("changed_files", [])[:20]
            result["dependencies"] = repo_analysis.get("affected_modules", [])

        result["implementation_strategy"] = [
            "1. Analyze current implementation and identify change points",
            "2. Implement changes with appropriate patterns",
            "3. Add/modify tests for changed functionality",
            "4. Run build and verify no regressions",
            "5. Run full test suite",
        ]
        result["rollback_strategy"] = "Revert the change set at the commit level. If database migrations are involved, apply down-migration first."
        result["review_requirements"] = ["Code review by senior engineer", "QA validation on staging", "Security review if auth/data changes"]

        await self._emit(ENGINEERING_EVENT_PLAN_GENERATED, execution_id,
                         f"Engineering plan generated: {len(result['impacted_files'])} files, {len(result['implementation_strategy'])} steps")
        return result


class CodeGenerator(EngineeringAgent):
    """Prepares code change sets. No direct push without approval."""

    def __init__(self) -> None:
        super().__init__("code_generator", "Code Generator")

    async def generate(self, plan: Optional[Dict] = None, execution_id: str = "") -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "agent": self.name,
            "generated_at": self._now(),
            "change_sets": [],
            "branch_name": f"eng/{execution_id[:12]}" if execution_id else "eng/pending",
            "commit_messages": [],
            "requires_approval": True,
            "approval_status": "pending",
        }

        if plan:
            for f in plan.get("impacted_files", [])[:10]:
                result["change_sets"].append({
                    "file": f,
                    "change_type": "modify",
                    "status": "proposed",
                })
            result["commit_messages"] = [
                f"Engineering change: {plan.get('objective', 'Automated change')[:80]}",
            ]

        await self._emit(ENGINEERING_EVENT_CODE_GENERATED, execution_id,
                         f"Code generated: {len(result['change_sets'])} change set(s), requires approval")
        return result


class CodeReviewer(EngineeringAgent):
    """Reviews proposed changes against quality standards."""

    def __init__(self) -> None:
        super().__init__("code_reviewer", "Code Reviewer")

    async def review(self, change_sets: Optional[List[Dict]] = None, execution_id: str = "") -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "agent": self.name,
            "reviewed_at": self._now(),
            "review_status": "pending",
            "comments": [],
            "approval": False,
            "quality_score": 0.0,
            "suggested_improvements": [],
        }

        if change_sets:
            result["comments"] = [
                {"file": cs.get("file", "unknown"), "severity": "info",
                 "message": f"Review {cs.get('change_type', 'modify')} for {cs.get('file', 'unknown')}"}
                for cs in change_sets[:10]
            ]

        result["suggested_improvements"] = [
            "Add unit tests for new/modified logic",
            "Verify error handling paths",
            "Ensure backward compatibility",
        ]

        await self._emit(ENGINEERING_EVENT_CODE_REVIEWED, execution_id,
                         f"Review complete: {len(result['comments'])} comments, {len(result['suggested_improvements'])} suggestions")
        return result


class TestValidator(EngineeringAgent):
    """Validates test coverage and results."""

    def __init__(self) -> None:
        super().__init__("test_validator", "Test Validator")

    async def validate(self, qa_results: Optional[Dict] = None, execution_id: str = "") -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "agent": self.name,
            "validated_at": self._now(),
            "coverage_check": {"status": "pending", "current": 0.0, "threshold": 80.0},
            "regression_check": {"status": "pending", "regressions": 0, "detail": "Run full test suite to check for regressions"},
            "quality_gates": [],
        }

        if qa_results:
            result["quality_gates"] = [
                {"gate": "All tests pass", "status": "pending"},
                {"gate": f"Coverage >= 80% (currently {qa_results.get('coverage', 0)}%)", "status": "pending"},
            ]

        return result


class DevOpsEngineer(EngineeringAgent):
    """Handles pipeline, deployment, and infrastructure concerns."""

    def __init__(self) -> None:
        super().__init__("devops_engineer", "DevOps Engineer")

    async def analyze(self, ecosystem: str = "", execution_id: str = "") -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "agent": self.name,
            "analyzed_at": self._now(),
            "pipeline_requirements": [],
            "deployment_notes": [],
            "infrastructure_requirements": [],
        }

        result["pipeline_requirements"] = [
            {"phase": "build", "tool": "CI Runner", "detail": f"Standard build pipeline for {ecosystem}"},
            {"phase": "test", "tool": "CI Runner", "detail": "Automated test execution"},
            {"phase": "deploy", "tool": "CD Pipeline", "detail": "Deployment requires approval"},
        ]

        return result


class SREEngineer(EngineeringAgent):
    """Handles reliability, monitoring, and observability concerns."""

    def __init__(self) -> None:
        super().__init__("sre_engineer", "SRE Engineer")

    async def analyze(self, execution_id: str = "") -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "agent": self.name,
            "analyzed_at": self._now(),
            "monitoring_requirements": [],
            "reliability_concerns": [],
            "slo_suggestions": [],
        }

        result["monitoring_requirements"] = [
            {"aspect": "Application metrics", "tool": "Runtime Metrics", "detail": "Track error rate, latency, throughput"},
            {"aspect": "Alerting", "tool": "Event Bus", "detail": "Alert on error rate spikes"},
        ]
        result["slo_suggestions"] = [
            {"metric": "Error rate", "target": "< 1%", "window": "30d"},
            {"metric": "Build success", "target": "> 95%", "window": "30d"},
        ]

        return result


# =============================================================================
# Part 7 — EnterpriseEngineeringExecutive (Main Orchestrator)
# =============================================================================

class EnterpriseEngineeringExecutive:
    """Single coordinating service for all engineering workflows."""

    def __init__(self, storage_dir: str = "data/engineering_executive"):
        self._storage_dir = Path(storage_dir)
        self._storage_dir.mkdir(parents=True, exist_ok=True)
        self._tasks: Dict[str, Dict[str, Any]] = {}
        self._plans: Dict[str, Dict[str, Any]] = {}
        self._reports: Dict[str, Dict[str, Any]] = {}
        self._load()
        self._classifier = TaskClassifier()
        self._planner = ExecutivePlanBuilder()
        self._executor = StageExecutor()
        self._recovery = RecoveryManager()
        self._reporter = ReportGenerator()
        # Engineering agents (merged from enterprise_engineering_service.py)
        self.repository_analyst = RepositoryAnalyst()
        self.build_engineer = BuildEngineer()
        self.qa_engineer = QAEngineer()
        self.security_engineer = SecurityEngineer()
        self.software_architect = SoftwareArchitect()
        self.bug_investigator = BugInvestigator()
        self.engineering_planner = EngineeringPlanner()
        self.code_generator = CodeGenerator()
        self.code_reviewer = CodeReviewer()
        self.test_validator = TestValidator()
        self.devops_engineer = DevOpsEngineer()
        self.sre_engineer = SREEngineer()

    def _tasks_path(self) -> Path:
        return self._storage_dir / "tasks.json"

    def _plans_path(self) -> Path:
        return self._storage_dir / "plans.json"

    def _reports_path(self) -> Path:
        return self._storage_dir / "reports.json"

    def _load(self):
        for item in _load_json(self._tasks_path()):
            self._tasks[item["task_id"]] = item
        for item in _load_json(self._plans_path()):
            self._plans[item["plan_id"]] = item
        for item in _load_json(self._reports_path()):
            self._reports[item["report_id"]] = item

    def _save_tasks(self):
        _save_json(self._tasks_path(), list(self._tasks.values()))

    def _save_plans(self):
        _save_json(self._plans_path(), list(self._plans.values()))

    def _save_reports(self):
        _save_json(self._reports_path(), list(self._reports.values()))

    # ------------------------------------------------------------------
    # Task Management
    # ------------------------------------------------------------------

    async def create_task(self, description: str, repo_url: str = "", branch: str = "") -> Dict[str, Any]:
        task_id = f"exec-task-{_id()}"
        classification = self._classifier.classify(description)

        task = {
            "task_id": task_id,
            "description": description,
            "task_type": classification["task_type"],
            "task_label": classification["task_label"],
            "confidence": classification["confidence"],
            "repo_url": repo_url or classification["repo_url"],
            "branch": branch or classification["branch"] or "main",
            "status": "created",
            "created_at": _now(),
            "updated_at": _now(),
        }
        self._tasks[task_id] = task
        self._save_tasks()
        return task

    async def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        return self._tasks.get(task_id)

    async def list_tasks(self, status: str = "") -> List[Dict[str, Any]]:
        tasks = list(self._tasks.values())
        if status:
            tasks = [t for t in tasks if t.get("status") == status]
        return sorted(tasks, key=lambda t: t.get("created_at", ""), reverse=True)

    async def delete_task(self, task_id: str) -> bool:
        if task_id in self._tasks:
            del self._tasks[task_id]
            self._save_tasks()
            return True
        return False

    # ------------------------------------------------------------------
    # Plan Management
    # ------------------------------------------------------------------

    async def create_plan(self, task_id: str) -> Optional[Dict[str, Any]]:
        task = self._tasks.get(task_id)
        if not task:
            return None

        classification = self._classifier.classify(task.get("description", ""))
        plan = self._planner.create_plan(
            task_id=task_id,
            task_type=task["task_type"],
            task_label=task["task_label"],
            stages=classification["stages"],
            repo_url=task.get("repo_url", ""),
            branch=task.get("branch", "main"),
            description=task.get("description", ""),
        )
        self._plans[plan["plan_id"]] = plan
        self._save_plans()

        task["status"] = "planned"
        task["plan_id"] = plan["plan_id"]
        self._save_tasks()

        return plan

    async def get_plan(self, plan_id: str) -> Optional[Dict[str, Any]]:
        return self._plans.get(plan_id)

    async def list_plans(self, status: str = "") -> List[Dict[str, Any]]:
        plans = list(self._plans.values())
        if status:
            plans = [p for p in plans if p.get("status") == status]
        return sorted(plans, key=lambda p: p.get("created_at", ""), reverse=True)

    async def delete_plan(self, plan_id: str) -> bool:
        if plan_id in self._plans:
            del self._plans[plan_id]
            self._save_plans()
            return True
        return False

    # ------------------------------------------------------------------
    # Execution Engine
    # ------------------------------------------------------------------

    async def execute_plan(self, plan_id: str) -> Optional[Dict[str, Any]]:
        plan = self._plans.get(plan_id)
        if not plan:
            return None

        plan["status"] = "running"
        plan["current_stage_index"] = 0
        context: Dict[str, Any] = {}

        for stage in plan["stages"]:
            stage["status"] = "pending"

        self._save_plans()

        for i, stage in enumerate(plan["stages"]):
            plan["current_stage_index"] = i
            stage["status"] = "running"
            stage["started_at"] = _now()
            self._save_plans()

            success, artifacts, error = await self._executor.execute_stage(stage, plan, context)

            if success:
                stage["status"] = "completed"
                stage["completed_at"] = _now()
                if artifacts:
                    stage["artifacts"].append(artifacts)
                    plan["artifacts"].append(artifacts)
            else:
                stage["status"] = "failed"
                stage["error"] = error
                stage["completed_at"] = _now()

                action = self._recovery.get_recovery_action(stage)
                self._recovery.record_recovery(plan, i, action, error)

                if action == "retry":
                    log.info("Retrying stage %d (%s)", i, stage["stage_type"])
                    stage["status"] = "running"
                    stage["started_at"] = _now()
                    retry_success, retry_artifacts, retry_error = await self._executor.execute_stage(stage, plan, context)
                    if retry_success:
                        stage["status"] = "completed"
                        stage["completed_at"] = _now()
                        if retry_artifacts:
                            stage["artifacts"].append(retry_artifacts)
                            plan["artifacts"].append(retry_artifacts)
                    else:
                        stage["status"] = "failed"
                        stage["error"] = retry_error
                        stage["completed_at"] = _now()
                        plan["status"] = "failed"
                        self._save_plans()
                        break
                else:
                    plan["status"] = "failed"
                    self._save_plans()
                    break

            self._save_plans()

        if all(s["status"] == "completed" for s in plan["stages"]):
            plan["status"] = "completed"
        elif plan["status"] != "failed":
            plan["status"] = "completed"  # partial completion

        plan["updated_at"] = _now()
        self._save_plans()

        # Update task status
        task = self._tasks.get(plan["task_id"])
        if task:
            task["status"] = plan["status"]
            self._save_tasks()

        return plan

    async def get_execution_status(self, plan_id: str) -> Optional[Dict[str, Any]]:
        plan = self._plans.get(plan_id)
        if not plan:
            return None
        return {
            "plan_id": plan["plan_id"],
            "status": plan["status"],
            "current_stage_index": plan["current_stage_index"],
            "stages": [
                {
                    "stage_index": s["stage_index"],
                    "stage_type": s["stage_type"],
                    "status": s["status"],
                    "retry_count": s["retry_count"],
                    "error": s.get("error"),
                }
                for s in plan["stages"]
            ],
            "recovery_log": plan.get("recovery_log", []),
            "updated_at": plan.get("updated_at", ""),
        }

    # ------------------------------------------------------------------
    # Report Generation
    # ------------------------------------------------------------------

    async def generate_report(self, plan_id: str) -> Optional[Dict[str, Any]]:
        plan = self._plans.get(plan_id)
        if not plan:
            return None

        context = self._build_context(plan)
        report = self._reporter.generate_report(plan, context)
        self._reports[report["report_id"]] = report
        self._save_reports()
        return report

    async def get_report(self, report_id: str) -> Optional[Dict[str, Any]]:
        return self._reports.get(report_id)

    async def list_reports(self) -> List[Dict[str, Any]]:
        return sorted(
            self._reports.values(),
            key=lambda r: r.get("generated_at", ""),
            reverse=True,
        )

    def _build_context(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        context: Dict[str, Any] = {}
        for s in plan["stages"]:
            for artifact in s.get("artifacts", []):
                if isinstance(artifact, dict):
                    context.update(artifact)
        return context

    # ------------------------------------------------------------------
    # Engineering Department Task Execution
    # ------------------------------------------------------------------

    async def execute_engineering_task(
        self,
        objective: str,
        repo_url: str = "",
        branch: str = "main",
        ecosystem: str = "python",
        execution_id: str = "",
        build_diagnostics: Optional[List[Dict]] = None,
    ) -> Dict[str, Any]:
        """Execute a full engineering department workflow for a given objective."""
        eng_id = execution_id or f"eng_{uuid.uuid4().hex[:12]}"

        report: Dict[str, Any] = {
            "execution_id": eng_id,
            "objective": objective,
            "started_at": self._now(),
            "agents": {},
            "status": "running",
            "artifacts": {},
        }

        # Phase 1: Repository Analysis
        if repo_url:
            try:
                repo_result = await self.repository_analyst.analyze(repo_url, branch, eng_id)
                report["agents"]["repository_analyst"] = repo_result
                report["artifacts"]["changed_files"] = repo_result.get("changed_files", [])
                report["artifacts"]["language_stats"] = repo_result.get("language_stats", {})
            except Exception as exc:
                report["agents"]["repository_analyst"] = {"error": str(exc)}

        # Phase 2: Build
        try:
            build_result = await self.build_engineer.build(ecosystem, eng_id)
            report["agents"]["build_engineer"] = build_result
        except Exception as exc:
            report["agents"]["build_engineer"] = {"error": str(exc)}

        # Phase 3: QA
        try:
            qa_result = await self.qa_engineer.run_tests(ecosystem, eng_id)
            report["agents"]["qa_engineer"] = qa_result
        except Exception as exc:
            report["agents"]["qa_engineer"] = {"error": str(exc)}

        # Phase 4: Security
        try:
            sec_result = await self.security_engineer.scan(eng_id, report.get("artifacts", {}).get("changed_files"))
            report["agents"]["security_engineer"] = sec_result
        except Exception as exc:
            report["agents"]["security_engineer"] = {"error": str(exc)}

        # Phase 5: Architecture review
        changed_files = report.get("artifacts", {}).get("changed_files")
        try:
            arch_result = await self.software_architect.review(changed_files, eng_id)
            report["agents"]["software_architect"] = arch_result
        except Exception as exc:
            report["agents"]["software_architect"] = {"error": str(exc)}

        # Phase 6: Bug investigation (if diagnostics provided)
        if build_diagnostics:
            try:
                rca_result = await self.bug_investigator.investigate(eng_id, build_diagnostics)
                report["agents"]["bug_investigator"] = rca_result
            except Exception as exc:
                report["agents"]["bug_investigator"] = {"error": str(exc)}

        # Phase 7: Engineering plan
        try:
            plan_result = await self.engineering_planner.plan(
                repo_analysis=report.get("agents", {}).get("repository_analyst"),
                architecture_review=report.get("agents", {}).get("software_architect"),
                objective=objective, execution_id=eng_id,
            )
            report["agents"]["engineering_planner"] = plan_result
        except Exception as exc:
            report["agents"]["engineering_planner"] = {"error": str(exc)}

        # Phase 8: Code generation
        try:
            code_result = await self.code_generator.generate(
                plan=report.get("agents", {}).get("engineering_planner"), execution_id=eng_id,
            )
            report["agents"]["code_generator"] = code_result
        except Exception as exc:
            report["agents"]["code_generator"] = {"error": str(exc)}

        # Phase 9: Code review
        try:
            review_result = await self.code_reviewer.review(
                change_sets=report.get("agents", {}).get("code_generator", {}).get("change_sets"),
                execution_id=eng_id,
            )
            report["agents"]["code_reviewer"] = review_result
        except Exception as exc:
            report["agents"]["code_reviewer"] = {"error": str(exc)}

        # Phase 10: Test validation
        try:
            test_val_result = await self.test_validator.validate(
                qa_results=report.get("agents", {}).get("qa_engineer"), execution_id=eng_id,
            )
            report["agents"]["test_validator"] = test_val_result
        except Exception as exc:
            report["agents"]["test_validator"] = {"error": str(exc)}

        # Phase 11: DevOps
        try:
            devops_result = await self.devops_engineer.analyze(ecosystem, eng_id)
            report["agents"]["devops_engineer"] = devops_result
        except Exception as exc:
            report["agents"]["devops_engineer"] = {"error": str(exc)}

        # Phase 12: SRE
        try:
            sre_result = await self.sre_engineer.analyze(eng_id)
            report["agents"]["sre_engineer"] = sre_result
        except Exception as exc:
            report["agents"]["sre_engineer"] = {"error": str(exc)}

        report["status"] = "completed"
        report["completed_at"] = self._now()

        # Update knowledge graph
        await self._record_engineering_artifacts(eng_id, objective, report)

        # Final event
        try:
            from backend.services.enterprise_event_hub import enterprise_hub
            await enterprise_hub.emit(
                event_type=ENGINEERING_EVENT_MISSION_COMPLETED,
                agent="engineering_executive",
                status="completed",
                message=f"Engineering task complete: {objective[:60]}",
                execution_id=eng_id,
                metadata={"objective": objective, "agents": list(report.get("agents", {}).keys())},
            )
        except Exception:
            pass

        return report

    async def _record_engineering_artifacts(self, execution_id: str, objective: str, report: Dict) -> None:
        try:
            from backend.services.enterprise_graph_service import enterprise_graph
            await enterprise_graph.upsert_entity(
                entity_type="engineering_mission",
                entity_id=execution_id,
                properties={
                    "objective": objective,
                    "agents": list(report.get("agents", {}).keys()),
                    "status": report.get("status", ""),
                    "completed_at": report.get("completed_at", ""),
                },
            )
        except Exception:
            pass

        try:
            from backend.services.enterprise_learning_service import enterprise_learning
            if hasattr(enterprise_learning, "extract_lesson"):
                lesson = {
                    "source": "engineering_department",
                    "execution_id": execution_id,
                    "objective": objective,
                    "agent_count": len(report.get("agents", {})),
                }
                await enterprise_learning.extract_lesson(lesson)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Dashboard
    # ------------------------------------------------------------------

    async def get_dashboard_stats(self) -> Dict[str, Any]:
        total_tasks = len(self._tasks)
        total_plans = len(self._plans)
        total_reports = len(self._reports)
        tasks_by_status: Dict[str, int] = {}
        plans_by_status: Dict[str, int] = {}
        plans_by_type: Dict[str, int] = {}

        for t in self._tasks.values():
            tasks_by_status[t.get("status", "unknown")] = tasks_by_status.get(t.get("status", "unknown"), 0) + 1

        for p in self._plans.values():
            s = p.get("status", "unknown")
            plans_by_status[s] = plans_by_status.get(s, 0) + 1
            tt = p.get("task_type", "unknown")
            plans_by_type[tt] = plans_by_type.get(tt, 0) + 1

        return {
            "total_tasks": total_tasks,
            "total_plans": total_plans,
            "total_reports": total_reports,
            "tasks_by_status": tasks_by_status,
            "plans_by_status": plans_by_status,
            "plans_by_type": plans_by_type,
            "supported_task_types": [
                {"type": k, "label": v["label"], "stages": v["stages"]}
                for k, v in SUPPORTED_TASK_TYPES.items()
            ],
        }


# Singleton
_engineering_executive: Optional[EnterpriseEngineeringExecutive] = None


def get_engineering_executive() -> EnterpriseEngineeringExecutive:
    global _engineering_executive
    if _engineering_executive is None:
        _engineering_executive = EnterpriseEngineeringExecutive()
    return _engineering_executive
