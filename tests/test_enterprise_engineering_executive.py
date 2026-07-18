"""
Comprehensive validation tests for Enterprise Engineering Executive.
Verifies all 6 parts plus end-to-end workflow scenarios.
"""
from __future__ import annotations

import pytest

from backend.services.enterprise_engineering_executive import (
    EnterpriseEngineeringExecutive,
    TaskClassifier,
    ExecutivePlanBuilder,
    StageExecutor,
    RecoveryManager,
    ReportGenerator,
    get_engineering_executive,
    SUPPORTED_TASK_TYPES,
)
from backend.events.enterprise_event_types import EnterpriseEventTypes as EET


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def exec_service():
    eng = EnterpriseEngineeringExecutive()
    eng._tasks = {}
    eng._plans = {}
    eng._reports = {}
    return eng


# =============================================================================
# Pipeline Constants
# =============================================================================

class TestEngineeringExecutiveConstants:
    def test_event_strings(self):
        assert EET.ENGINEERING_EXECUTIVE_TASK_CREATED == "engineering.executive.task_created"
        assert EET.ENGINEERING_EXECUTIVE_PLAN_CREATED == "engineering.executive.plan_created"
        assert EET.ENGINEERING_EXECUTIVE_COMPLETED == "engineering.executive.completed"
        assert EET.ENGINEERING_EXECUTIVE_REPORT_GENERATED == "engineering.executive.report_generated"

    def test_event_hub_routing(self):
        from backend.services.enterprise_event_hub import _topic_for_event
        assert _topic_for_event("engineering.executive.task_created") == "enterprise:engineering"
        assert _topic_for_event("engineering.executive.completed") == "enterprise:engineering"

    def test_supported_task_types_structure(self):
        assert len(SUPPORTED_TASK_TYPES) == 14
        for task_type, config in SUPPORTED_TASK_TYPES.items():
            assert "label" in config
            assert "stages" in config
            assert len(config["stages"]) >= 2

    def test_all_task_types_have_keywords(self):
        from backend.services.enterprise_engineering_executive import TASK_CLASSIFIER_KEYWORDS
        for task_type in SUPPORTED_TASK_TYPES:
            assert task_type in TASK_CLASSIFIER_KEYWORDS, f"Missing keywords for {task_type}"


# =============================================================================
# Part 1 — Task Classifier
# =============================================================================

class TestTaskClassifier:
    def test_classify_bug_investigation(self):
        result = TaskClassifier.classify("Investigate the failing login test causing 500 errors")
        assert result["task_type"] == "bug_investigation"
        assert result["task_label"] == "Bug Investigation"
        assert "workspace" in result["stages"]
        assert "code_intel" in result["stages"]

    def test_classify_security_review(self):
        result = TaskClassifier.classify("Run a security review on the authentication module")
        assert result["task_type"] == "security_review"

    def test_classify_dependency_upgrade(self):
        result = TaskClassifier.classify("Upgrade FastAPI to the latest version")
        assert result["task_type"] == "dependency_upgrade"

    def test_classify_deployment(self):
        result = TaskClassifier.classify("Deploy release v2.0 to production")
        assert result["task_type"] == "deployment"

    def test_classify_rollback(self):
        result = TaskClassifier.classify("Rollback the last production deployment")
        assert result["task_type"] == "rollback"

    def test_classify_production_incident(self):
        result = TaskClassifier.classify("P1 production outage in payment processing")
        assert result["task_type"] == "production_incident"

    def test_classify_test_repair(self):
        result = TaskClassifier.classify("The test suite needs repair")
        assert result["task_type"] == "test_repair"

    def test_classify_generic_patch(self):
        result = TaskClassifier.classify("Add a new feature to the dashboard")
        assert result["task_type"] == "patch_generation"

    def test_classify_unknown_falls_back_to_patch(self):
        result = TaskClassifier.classify("Something completely random with no matching keywords")
        assert result["task_type"] == "patch_generation"

    def test_classify_extracts_repo_url(self):
        result = TaskClassifier.classify("Analyze repo https://github.com/org/repo.git for bugs")
        assert "github.com" in result["repo_url"]

    def test_participating_subsystems(self):
        subs = TaskClassifier.get_participating_subsystems("deployment")
        assert "delivery_orchestrator" in subs
        assert "git_operations" in subs

    def test_participating_subsystems_fallback(self):
        subs = TaskClassifier.get_participating_subsystems("nonexistent_type")
        assert len(subs) >= 5


# =============================================================================
# Part 2 — Engineering Planner
# =============================================================================

class TestExecutivePlanBuilder:
    def test_create_plan_structure(self):
        classification = TaskClassifier.classify("The test suite needs repair")
        plan = ExecutivePlanBuilder.create_plan(
            task_id="exec-task-test",
            task_type=classification["task_type"],
            task_label=classification["task_label"],
            stages=classification["stages"],
            description="The test suite needs repair",
        )
        assert plan["plan_id"].startswith("exec-plan-")
        assert len(plan["stages"]) >= 2
        assert plan["status"] == "created"
        assert plan["current_stage_index"] == -1
        assert len(plan["participating_subsystems"]) > 0
        assert "recovery_log" in plan

    def test_plan_stages_have_correct_structure(self):
        classification = TaskClassifier.classify("Deploy to production")
        plan = ExecutivePlanBuilder.create_plan(
            task_id="test", task_type=classification["task_type"],
            task_label=classification["task_label"], stages=classification["stages"],
        )
        for stage in plan["stages"]:
            assert "stage_id" in stage
            assert "stage_type" in stage
            assert "status" in stage
            assert stage["status"] == "pending"
            assert "retry_count" in stage
            assert "max_retries" in stage
            assert "subsystem" in stage

    def test_plan_stage_subsystem_mapping(self):
        assert ExecutivePlanBuilder._stage_subsystem("workspace") == "WorkspaceManager"
        assert ExecutivePlanBuilder._stage_subsystem("code_intel") == "EnterpriseCodeIntelligence"
        assert ExecutivePlanBuilder._stage_subsystem("patch") == "EnterprisePatchPipeline"
        assert ExecutivePlanBuilder._stage_subsystem("sandbox") == "EnterpriseExecutionSandbox"
        assert ExecutivePlanBuilder._stage_subsystem("git") == "EnterpriseGitOperations"
        assert ExecutivePlanBuilder._stage_subsystem("delivery") == "EnterpriseDeliveryOrchestrator"
        assert ExecutivePlanBuilder._stage_subsystem("learning") == "EnterpriseLearningEngine"
        assert ExecutivePlanBuilder._stage_subsystem("recommendation") == "EnterpriseRecommendationEngine"
        assert ExecutivePlanBuilder._stage_subsystem("unknown") == "Unknown"


# =============================================================================
# Part 3 — Recovery Manager
# =============================================================================

class TestRecoveryManager:
    def test_should_retry_when_below_max(self):
        stage = {"retry_count": 0, "max_retries": 2}
        assert RecoveryManager.should_retry(stage)

    def test_should_not_retry_when_at_max(self):
        stage = {"retry_count": 2, "max_retries": 2}
        assert not RecoveryManager.should_retry(stage)

    def test_get_recovery_action_retry(self):
        stage = {"retry_count": 0, "max_retries": 2}
        assert RecoveryManager.get_recovery_action(stage) == "retry"

    def test_get_recovery_action_escalate(self):
        stage = {"retry_count": 2, "max_retries": 2}
        assert RecoveryManager.get_recovery_action(stage) == "escalate"

    def test_record_recovery(self):
        plan = {
            "stages": [{"stage_type": "code_intel", "retry_count": 0}],
            "recovery_log": [],
        }
        RecoveryManager.record_recovery(plan, 0, "retry", "Connection timeout")
        assert len(plan["recovery_log"]) == 1
        assert plan["recovery_log"][0]["action"] == "retry"
        assert plan["recovery_log"][0]["reason"] == "Connection timeout"
        assert plan["stages"][0]["retry_count"] == 1


# =============================================================================
# Part 4 — Report Generator
# =============================================================================

class TestReportGenerator:
    def test_generate_report_structure(self):
        plan = {
            "plan_id": "exec-plan-test",
            "task_id": "exec-task-test",
            "task_type": "bug_investigation",
            "task_label": "Bug Investigation",
            "status": "completed",
            "stages": [
                {"stage_index": 0, "stage_type": "workspace", "status": "completed", "retry_count": 0, "error": None, "subsystem": "WorkspaceManager", "artifacts": [], "started_at": None, "completed_at": None},
                {"stage_index": 1, "stage_type": "code_intel", "status": "completed", "retry_count": 0, "error": None, "subsystem": "EnterpriseCodeIntelligence", "artifacts": [], "started_at": None, "completed_at": None},
                {"stage_index": 2, "stage_type": "patch", "status": "completed", "retry_count": 0, "error": None, "subsystem": "EnterprisePatchPipeline", "artifacts": [], "started_at": None, "completed_at": None},
            ],
            "recovery_log": [],
            "artifacts": [],
        }
        context = {
            "workspace_id": "ws-1",
            "sandbox_id": "sb-1",
            "plan_id": "plan-1",
            "branch_name": "fix/bug",
            "pr_number": 42,
            "delivery_id": "del-1",
            "candidates": [{"id": "c1"}, {"id": "c2"}],
        }
        report = ReportGenerator.generate_report(plan, context)
        assert report["report_id"].startswith("exec-report-")
        assert report["overall_status"] == "completed"
        assert report["total_stages"] == 3
        assert report["completed_stages"] == 3
        assert report["failed_stages"] == 0
        assert report["artifacts_summary"]["workspace_id"] == "ws-1"
        assert report["artifacts_summary"]["candidate_count"] == 2
        assert len(report["stage_summary"]) == 3

    def test_report_with_failures(self):
        plan = {
            "plan_id": "exec-plan-fail",
            "task_id": "exec-task-fail",
            "task_type": "deployment",
            "task_label": "Deployment",
            "status": "failed",
            "stages": [
                {"stage_index": 0, "stage_type": "workspace", "status": "completed", "retry_count": 0, "error": None, "subsystem": "WorkspaceManager", "artifacts": [], "started_at": None, "completed_at": None},
                {"stage_index": 1, "stage_type": "patch", "status": "failed", "retry_count": 2, "error": "Build failed", "subsystem": "EnterprisePatchPipeline", "artifacts": [], "started_at": None, "completed_at": None},
            ],
            "recovery_log": [
                {"stage_index": 1, "stage_type": "patch", "action": "retry", "reason": "Build failed", "timestamp": ""},
                {"stage_index": 1, "stage_type": "patch", "action": "escalate", "reason": "Build failed after retry", "timestamp": ""},
            ],
            "artifacts": [],
        }
        report = ReportGenerator.generate_report(plan, {})
        assert report["overall_status"] == "failed"
        assert report["completed_stages"] == 1
        assert report["failed_stages"] == 1
        assert len(report["recovery_actions_taken"]) == 2
        assert report["stage_summary"][1]["error"] == "Build failed"


# =============================================================================
# Part 5 — Full Orchestrator
# =============================================================================

class TestEnterpriseEngineeringExecutive:
    @pytest.mark.asyncio
    async def test_create_task(self, exec_service):
        task = await exec_service.create_task("Test suite needs repair in login module")
        assert task["task_id"].startswith("exec-task-")
        assert task["task_type"] == "test_repair"
        assert task["task_label"] == "Test Repair"
        assert task["status"] == "created"

    @pytest.mark.asyncio
    async def test_create_task_with_repo(self, exec_service):
        task = await exec_service.create_task(
            "Bug in payment module",
            repo_url="https://github.com/org/repo.git",
            branch="develop",
        )
        assert task["repo_url"] == "https://github.com/org/repo.git"
        assert task["branch"] == "develop"

    @pytest.mark.asyncio
    async def test_get_task(self, exec_service):
        created = await exec_service.create_task("Test task")
        fetched = await exec_service.get_task(created["task_id"])
        assert fetched is not None
        assert fetched["task_id"] == created["task_id"]

    @pytest.mark.asyncio
    async def test_get_task_not_found(self, exec_service):
        assert await exec_service.get_task("nonexistent") is None

    @pytest.mark.asyncio
    async def test_list_tasks(self, exec_service):
        await exec_service.create_task("Task A")
        await exec_service.create_task("Task B")
        tasks = await exec_service.list_tasks()
        assert len(tasks) == 2

    @pytest.mark.asyncio
    async def test_list_tasks_by_status(self, exec_service):
        t1 = await exec_service.create_task("Task 1")
        t2 = await exec_service.create_task("Task 2")
        t2["status"] = "planned"
        exec_service._tasks[t2["task_id"]] = t2
        exec_service._save_tasks()
        created_tasks = await exec_service.list_tasks(status="created")
        assert len(created_tasks) >= 1

    @pytest.mark.asyncio
    async def test_delete_task(self, exec_service):
        t = await exec_service.create_task("Delete me")
        assert await exec_service.delete_task(t["task_id"])
        assert await exec_service.get_task(t["task_id"]) is None

    @pytest.mark.asyncio
    async def test_delete_task_not_found(self, exec_service):
        assert not await exec_service.delete_task("nonexistent")

    @pytest.mark.asyncio
    async def test_create_plan(self, exec_service):
        task = await exec_service.create_task("Deploy to staging")
        plan = await exec_service.create_plan(task["task_id"])
        assert plan is not None
        assert plan["plan_id"].startswith("exec-plan-")
        assert plan["task_id"] == task["task_id"]
        assert len(plan["stages"]) >= 2

    @pytest.mark.asyncio
    async def test_create_plan_nonexistent_task(self, exec_service):
        assert await exec_service.create_plan("nonexistent") is None

    @pytest.mark.asyncio
    async def test_get_plan(self, exec_service):
        task = await exec_service.create_task("Security review")
        plan = await exec_service.create_plan(task["task_id"])
        fetched = await exec_service.get_plan(plan["plan_id"])
        assert fetched is not None
        assert fetched["plan_id"] == plan["plan_id"]

    @pytest.mark.asyncio
    async def test_list_plans(self, exec_service):
        task1 = await exec_service.create_task("Deploy")
        task2 = await exec_service.create_task("Patch")
        await exec_service.create_plan(task1["task_id"])
        await exec_service.create_plan(task2["task_id"])
        plans = await exec_service.list_plans()
        assert len(plans) == 2

    @pytest.mark.asyncio
    async def test_delete_plan(self, exec_service):
        task = await exec_service.create_task("Test")
        plan = await exec_service.create_plan(task["task_id"])
        assert await exec_service.delete_plan(plan["plan_id"])
        assert await exec_service.get_plan(plan["plan_id"]) is None

    @pytest.mark.asyncio
    async def test_execute_plan_not_found(self, exec_service):
        assert await exec_service.execute_plan("nonexistent") is None

    @pytest.mark.asyncio
    async def test_get_execution_status_not_found(self, exec_service):
        assert await exec_service.get_execution_status("nonexistent") is None

    @pytest.mark.asyncio
    async def test_execute_plan_basic(self, exec_service):
        task = await exec_service.create_task("Fix the tests")
        plan = await exec_service.create_plan(task["task_id"])
        result = await exec_service.execute_plan(plan["plan_id"])
        assert result is not None
        assert result["status"] in ("completed", "failed")
        assert result["current_stage_index"] >= 0

    @pytest.mark.asyncio
    async def test_execution_status(self, exec_service):
        task = await exec_service.create_task("Deploy")
        plan = await exec_service.create_plan(task["task_id"])
        await exec_service.execute_plan(plan["plan_id"])
        status = await exec_service.get_execution_status(plan["plan_id"])
        assert status is not None
        assert status["plan_id"] == plan["plan_id"]
        assert len(status["stages"]) >= 2

    @pytest.mark.asyncio
    async def test_generate_report(self, exec_service):
        task = await exec_service.create_task("Bug investigation")
        plan = await exec_service.create_plan(task["task_id"])
        # Mark plan as completed manually for report generation
        plan["status"] = "completed"
        exec_service._plans[plan["plan_id"]] = plan
        report = await exec_service.generate_report(plan["plan_id"])
        assert report is not None
        assert report["report_id"].startswith("exec-report-")
        assert report["plan_id"] == plan["plan_id"]

    @pytest.mark.asyncio
    async def test_generate_report_nonexistent(self, exec_service):
        assert await exec_service.generate_report("nonexistent") is None

    @pytest.mark.asyncio
    async def test_get_report(self, exec_service):
        task = await exec_service.create_task("Patch")
        plan = await exec_service.create_plan(task["task_id"])
        plan["status"] = "completed"
        exec_service._plans[plan["plan_id"]] = plan
        report = await exec_service.generate_report(plan["plan_id"])
        fetched = await exec_service.get_report(report["report_id"])
        assert fetched is not None
        assert fetched["report_id"] == report["report_id"]

    @pytest.mark.asyncio
    async def test_list_reports(self, exec_service):
        task = await exec_service.create_task("R1")
        plan = await exec_service.create_plan(task["task_id"])
        plan["status"] = "completed"
        exec_service._plans[plan["plan_id"]] = plan
        await exec_service.generate_report(plan["plan_id"])
        reports = await exec_service.list_reports()
        assert len(reports) >= 1

    @pytest.mark.asyncio
    async def test_dashboard_stats(self, exec_service):
        await exec_service.create_task("T1")
        await exec_service.create_task("T2")
        stats = await exec_service.get_dashboard_stats()
        assert stats["total_tasks"] == 2
        assert stats["total_plans"] == 0
        assert stats["total_reports"] == 0
        assert len(stats["supported_task_types"]) == 14

    @pytest.mark.asyncio
    async def test_dashboard_empty(self, exec_service):
        stats = await exec_service.get_dashboard_stats()
        assert stats["total_tasks"] == 0
        assert stats["total_plans"] == 0
        assert stats["total_reports"] == 0


# =============================================================================
# E2E Workflow Scenarios
# =============================================================================

class TestEngineeringExecutiveWorkflows:
    """Validates real engineering workflows through the Executive."""

    @pytest.mark.asyncio
    async def test_full_fix_tests_workflow(self, exec_service):
        """Execute: 'Fix failing tests' → classify → plan → execute → report"""
        # 1. Create task
        task = await exec_service.create_task("Test suite needs repair in unit tests")
        assert task["task_type"] == "test_repair"
        assert task["confidence"] > 0

        # 2. Create plan
        plan = await exec_service.create_plan(task["task_id"])
        assert len(plan["stages"]) >= 2
        stage_types = [s["stage_type"] for s in plan["stages"]]
        assert "workspace" in stage_types
        assert "patch" in stage_types or "code_intel" in stage_types
        assert "learning" in stage_types

        # 3. Execute plan
        result = await exec_service.execute_plan(plan["plan_id"])
        assert result is not None
        assert result["status"] in ("completed", "failed")

        # 4. Check execution status
        status = await exec_service.get_execution_status(plan["plan_id"])
        assert status is not None
        for s in status["stages"]:
            assert s["status"] in ("completed", "failed", "pending")

    @pytest.mark.asyncio
    async def test_full_deploy_workflow(self, exec_service):
        """Simulate a deploy workflow end-to-end."""
        task = await exec_service.create_task(
            "Deploy release v2.0 to production",
            repo_url="https://github.com/org/app.git",
            branch="main",
        )
        assert task["task_type"] == "deployment"
        assert task["repo_url"] == "https://github.com/org/app.git"

        plan = await exec_service.create_plan(task["task_id"])
        assert plan["repo_url"] == "https://github.com/org/app.git"
        stage_types = [s["stage_type"] for s in plan["stages"]]
        assert "delivery" in stage_types or "git" in stage_types

        # Execute
        result = await exec_service.execute_plan(plan["plan_id"])
        assert result is not None

    @pytest.mark.asyncio
    async def test_incident_response_with_recovery(self, exec_service):
        """Production incident with possible recovery steps."""
        task = await exec_service.create_task("P1 outage in payment processing system")
        assert task["task_type"] == "production_incident"

        plan = await exec_service.create_plan(task["task_id"])
        subs = plan["participating_subsystems"]
        assert "recommendation_engine" in subs
        assert "delivery_orchestrator" in subs

        # Recovery manager should allow retries
        for stage in plan["stages"]:
            assert RecoveryManager.should_retry(stage)

    @pytest.mark.asyncio
    async def test_report_generation_after_execution(self, exec_service):
        """Generate a comprehensive report after a completed execution."""
        task = await exec_service.create_task("Refactor authentication module")
        plan = await exec_service.create_plan(task["task_id"])
        result = await exec_service.execute_plan(plan["plan_id"])

        # Generate report regardless of execution outcome
        report = await exec_service.generate_report(plan["plan_id"])
        assert report is not None
        assert report["overall_status"] in ("completed", "failed")
        assert len(report["stage_summary"]) == len(plan["stages"])
        assert len(report["subsystems_used"]) > 0

    @pytest.mark.asyncio
    async def test_multiple_tasks_and_plans(self, exec_service):
        """Handle multiple concurrent tasks correctly."""
        tasks = []
        descriptions = [
            "Test suite needs repair in login module",
            "Upgrade FastAPI to latest version",
            "Run security review on API endpoints",
            "Deploy the new dashboard",
            "Investigate production memory leak",
        ]
        for desc in descriptions:
            t = await exec_service.create_task(desc)
            tasks.append(t)

        assert len(await exec_service.list_tasks()) == len(descriptions)

        task_types = {t["task_type"] for t in tasks}
        assert "test_repair" in task_types
        assert "dependency_upgrade" in task_types
        assert "security_review" in task_types
        assert "deployment" in task_types
        assert "root_cause_analysis" in task_types

        # Create plans for all tasks
        for t in tasks:
            plan = await exec_service.create_plan(t["task_id"])
            assert plan is not None

        plans = await exec_service.list_plans()
        assert len(plans) == len(descriptions)

    @pytest.mark.asyncio
    async def test_dashboard_reflects_activity(self, exec_service):
        """Dashboard stats update after operations."""
        # Empty dashboard
        stats = await exec_service.get_dashboard_stats()
        assert stats["total_tasks"] == 0

        # After creating tasks
        await exec_service.create_task("Task 1")
        await exec_service.create_task("Task 2")
        await exec_service.create_task("Task 3")
        stats = await exec_service.get_dashboard_stats()
        assert stats["total_tasks"] == 3
        assert stats["tasks_by_status"].get("created") == 3
        assert len(stats["supported_task_types"]) == 14

    @pytest.mark.asyncio
    async def test_singleton(self):
        """get_engineering_executive returns the same instance."""
        s1 = get_engineering_executive()
        s2 = get_engineering_executive()
        assert s1 is s2
