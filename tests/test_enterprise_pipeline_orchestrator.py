"""
Comprehensive integration tests for the Enterprise Pipeline Orchestrator,
covering CRUD, state machine, stage execution, Patch-to-PR auto-workflow,
event constants, dashboard stats, and full end-to-end pipeline orchestration.
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch

from backend.services.enterprise_pipeline_orchestrator import (
    EnterprisePipelineOrchestrator,
    PipelineStateMachine,
    PIPELINE_STAGES,
    PIPELINE_EVENTS,
)
from backend.events.enterprise_event_types import EnterpriseEventTypes as EET


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def ops():
    from backend.services.enterprise_delivery_orchestrator import delivery_orchestrator
    # Clear any pre-existing pipeline data from delivery_orchestrator
    import json
    from pathlib import Path
    _PIPELINES_FILE = Path(__file__).resolve().parent.parent / "backend" / "data" / "pipelines.json"
    _PIPELINES_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(_PIPELINES_FILE, "w") as f:
        json.dump([], f)
    orch = EnterprisePipelineOrchestrator()
    return orch


# =============================================================================
# Pipeline Constants
# =============================================================================

class TestPipelineConstants:
    def test_pipeline_stages_defined(self):
        assert len(PIPELINE_STAGES) == 7
        assert PIPELINE_STAGES == [
            "trigger", "sandbox", "code_intel", "patch", "git", "approval", "complete",
        ]

    def test_all_pipeline_events_defined(self):
        assert len(PIPELINE_EVENTS) == 11

    def test_pipeline_events_in_enterprise_types(self):
        pipeline_events_from_eet = [
            getattr(EET, attr)
            for attr in dir(EET)
            if attr.startswith("PIPELINE_")
        ]
        for key, val in PIPELINE_EVENTS.items():
            assert val in pipeline_events_from_eet, f"{key}: {val} not in EET"

    def test_pipeline_event_keys_present(self):
        expected = {
            "created", "started", "stage_started", "stage_completed",
            "stage_failed", "completed", "failed", "cancelled",
            "patch_to_pr", "pr_created", "artifact_passed",
        }
        assert set(PIPELINE_EVENTS.keys()) == expected


# =============================================================================
# Pipeline State Machine
# =============================================================================

class TestPipelineStateMachine:
    def test_valid_transitions(self):
        assert PipelineStateMachine.can_transition("pending", "running")
        assert PipelineStateMachine.can_transition("running", "completed")
        assert PipelineStateMachine.can_transition("running", "failed")
        assert PipelineStateMachine.can_transition("running", "paused")
        assert PipelineStateMachine.can_transition("running", "cancelled")
        assert PipelineStateMachine.can_transition("paused", "running")
        assert PipelineStateMachine.can_transition("paused", "cancelled")

    def test_invalid_transitions(self):
        assert not PipelineStateMachine.can_transition("pending", "completed")
        assert not PipelineStateMachine.can_transition("completed", "running")
        assert not PipelineStateMachine.can_transition("failed", "running")
        assert not PipelineStateMachine.can_transition("cancelled", "running")

    def test_terminal_states(self):
        assert PipelineStateMachine.is_terminal("completed")
        assert PipelineStateMachine.is_terminal("failed")
        assert PipelineStateMachine.is_terminal("cancelled")
        assert not PipelineStateMachine.is_terminal("running")
        assert not PipelineStateMachine.is_terminal("pending")
        assert not PipelineStateMachine.is_terminal("paused")


# =============================================================================
# Pipeline CRUD
# =============================================================================

class TestPipelineCRUD:
    @pytest.mark.asyncio
    async def test_create_pipeline(self, ops):
        pipe = await ops.create_pipeline(name="test-pipe", description="A test pipeline")
        assert pipe["status"] == "pending"
        assert pipe["name"] == "test-pipe"
        assert pipe["description"] == "A test pipeline"
        assert pipe["pipeline_id"].startswith("pipe-")
        assert pipe["created_at"]

    @pytest.mark.asyncio
    async def test_create_pipeline_default_name(self, ops):
        pipe = await ops.create_pipeline()
        assert pipe["name"].startswith("Pipeline pipe-")

    @pytest.mark.asyncio
    async def test_get_pipeline(self, ops):
        created = await ops.create_pipeline(name="get-test")
        fetched = await ops.get_pipeline(created["pipeline_id"])
        assert fetched is not None
        assert fetched["pipeline_id"] == created["pipeline_id"]
        assert fetched["name"] == "get-test"

    @pytest.mark.asyncio
    async def test_get_pipeline_not_found(self, ops):
        assert await ops.get_pipeline("nonexistent") is None

    @pytest.mark.asyncio
    async def test_list_pipelines(self, ops):
        await ops.create_pipeline(name="A")
        await ops.create_pipeline(name="B")
        pipes = await ops.list_pipelines()
        assert len(pipes) == 2

    @pytest.mark.asyncio
    async def test_list_pipelines_filter_status(self, ops):
        await ops.create_pipeline(name="A")
        p = await ops.create_pipeline(name="B")
        await ops._transition(p["pipeline_id"], "running")
        running = await ops.list_pipelines(status="running")
        pending = await ops.list_pipelines(status="pending")
        assert len(running) == 1
        assert len(pending) == 1

    @pytest.mark.asyncio
    async def test_list_pipelines_limit(self, ops):
        for i in range(5):
            await ops.create_pipeline(name=str(i))
        assert len(await ops.list_pipelines(limit=3)) == 3

    @pytest.mark.asyncio
    async def test_update_pipeline(self, ops):
        p = await ops.create_pipeline(name="old")
        updated = await ops.update_pipeline(p["pipeline_id"], {"name": "new"})
        assert updated is not None
        assert updated["name"] == "new"
        fetched = await ops.get_pipeline(p["pipeline_id"])
        assert fetched["name"] == "new"

    @pytest.mark.asyncio
    async def test_update_pipeline_not_found(self, ops):
        assert await ops.update_pipeline("nonexistent", {}) is None

    @pytest.mark.asyncio
    async def test_delete_pipeline(self, ops):
        p = await ops.create_pipeline()
        assert await ops.delete_pipeline(p["pipeline_id"])
        assert await ops.get_pipeline(p["pipeline_id"]) is None

    @pytest.mark.asyncio
    async def test_delete_pipeline_not_found(self, ops):
        assert not await ops.delete_pipeline("nonexistent")


# =============================================================================
# Pipeline State Management
# =============================================================================

class TestPipelineStateManagement:
    @pytest.mark.asyncio
    async def test_transition_valid(self, ops):
        p = await ops.create_pipeline()
        result = await ops._transition(p["pipeline_id"], "running")
        assert result is not None
        assert result["status"] == "running"

    @pytest.mark.asyncio
    async def test_transition_invalid(self, ops):
        p = await ops.create_pipeline()
        with pytest.raises(ValueError, match="Cannot transition"):
            await ops._transition(p["pipeline_id"], "completed")

    @pytest.mark.asyncio
    async def test_transition_not_found(self, ops):
        assert await ops._transition("nonexistent", "running") is None

    @pytest.mark.asyncio
    async def test_pause_pipeline(self, ops):
        p = await ops.create_pipeline()
        await ops._transition(p["pipeline_id"], "running")
        paused = await ops.pause_pipeline(p["pipeline_id"])
        assert paused is not None
        assert paused["status"] == "paused"

    @pytest.mark.asyncio
    async def test_cancel_pipeline(self, ops):
        p = await ops.create_pipeline()
        cancelled = await ops.cancel_pipeline(p["pipeline_id"])
        assert cancelled is not None
        assert cancelled["status"] == "cancelled"
        assert cancelled["completed_at"]

    @pytest.mark.asyncio
    async def test_start_pipeline_invalid_state(self, ops):
        p = await ops.create_pipeline()
        await ops._transition(p["pipeline_id"], "running")
        await ops._transition(p["pipeline_id"], "completed")
        with pytest.raises(ValueError, match="Cannot start"):
            await ops.start_pipeline(p["pipeline_id"])


# =============================================================================
# Stage Execution
# =============================================================================

class TestStageExecution:
    @pytest.mark.asyncio
    async def test_start_pipeline_no_mission_raises(self, ops):
        p = await ops.create_pipeline(name="no-mission")
        with pytest.raises(RuntimeError, match="Stage 'trigger' failed"):
            await ops.start_pipeline(p["pipeline_id"])

    @pytest.mark.asyncio
    async def test_completed_stages_skipped(self, ops):
        p = await ops.create_pipeline()
        p["stages_completed"] = ["trigger", "sandbox"]
        p["status"] = "running"
        ops._pipelines[p["pipeline_id"]] = p
        result = await ops._execute_stages(p["pipeline_id"])
        assert result is not None

    @pytest.mark.asyncio
    async def test_stage_markup(self, ops):
        p = await ops.create_pipeline()
        p["mission_id"] = "test-mission"
        p["status"] = "running"
        ops._pipelines[p["pipeline_id"]] = p
        with patch.object(ops, "_execute_stage", new_callable=AsyncMock) as mock:
            mock.return_value = None
            result = await ops._execute_stages(p["pipeline_id"])
            assert result is not None

    @pytest.mark.asyncio
    async def test_stage_recorded_in_completed(self, ops):
        p = await ops.create_pipeline()
        p["mission_id"] = "test-mission"
        p["status"] = "running"
        ops._pipelines[p["pipeline_id"]] = p

        async def fake_execute(pid, stage):
            pass

        ops._execute_stage = fake_execute
        result = await ops._execute_stages(p["pipeline_id"])
        assert result is not None
        stages_completed = result.get("stages_completed", [])
        assert "trigger" in stages_completed
        assert "complete" in stages_completed

    @pytest.mark.asyncio
    async def test_pause_during_execution(self, ops):
        from backend.services.enterprise_delivery_orchestrator import delivery_orchestrator as do
        p = await ops.create_pipeline()
        p["mission_id"] = "test-mission"
        p["status"] = "running"
        ops._pipelines[p["pipeline_id"]] = p
        await ops._ensure_in_memory_synced(p["pipeline_id"])

        call_count = 0

        async def fake_execute(pid, stage):
            nonlocal call_count
            call_count += 1
            if call_count == 3:
                # Update the persisted pipeline status to "paused"
                await ops.update_pipeline(pid, {"status": "paused"})

        ops._execute_stage = fake_execute
        await ops._execute_stages(p["pipeline_id"])
        assert call_count == 3
        pipe = await ops.get_pipeline(p["pipeline_id"])
        assert pipe["status"] == "paused"


# =============================================================================
# Dashboard
# =============================================================================

class TestDashboard:
    @pytest.mark.asyncio
    async def test_dashboard_empty(self, ops):
        stats = await ops.get_dashboard_stats()
        assert stats["total_pipelines"] == 0
        assert stats["by_status"] == {}

    @pytest.mark.asyncio
    async def test_dashboard_counts(self, ops):
        p1 = await ops.create_pipeline()
        p2 = await ops.create_pipeline()
        p3 = await ops.create_pipeline()
        await ops._transition(p1["pipeline_id"], "running")
        await ops._transition(p2["pipeline_id"], "running")
        ops._pipelines[p2["pipeline_id"]]["status"] = "completed"
        # Sync in-memory changes to JSON before reading dashboard
        ops._flush_in_memory_to_json()
        stats = await ops.get_dashboard_stats()
        assert stats["total_pipelines"] == 3
        assert stats["running"] == 1
        assert stats["completed"] == 1
        assert stats["generated_at"]


# =============================================================================
# Patch-to-PR Auto-Workflow
# =============================================================================

class TestPatchToPR:
    @pytest.mark.asyncio
    async def test_patch_to_pr_invalid_candidate(self, ops):
        from backend.services.enterprise_patch_pipeline import patch_pipeline
        plan = await patch_pipeline.create_plan("bug", "test issue", source="test")
        with pytest.raises(ValueError, match="Candidate not found"):
            await ops.patch_to_pr(
                repo_url="https://github.com/org/repo",
                plan_id=plan["plan_id"],
                candidate_id="nonexistent",
            )


# =============================================================================
# Pipeline Constants Validation
# =============================================================================

class TestPipelineEvents:
    def test_all_events_in_eet(self):
        eet_attrs = {a for a in dir(EET) if not a.startswith("_")}
        pipeline_events = {a for a in eet_attrs if a.startswith("PIPELINE_")}
        assert len(pipeline_events) == 11

    def test_each_event_type_string_matches(self):
        assert EET.PIPELINE_CREATED == "pipeline.created"
        assert EET.PIPELINE_STARTED == "pipeline.started"
        assert EET.PIPELINE_STAGE_STARTED == "pipeline.stage_started"
        assert EET.PIPELINE_STAGE_COMPLETED == "pipeline.stage_completed"
        assert EET.PIPELINE_STAGE_FAILED == "pipeline.stage_failed"
        assert EET.PIPELINE_COMPLETED == "pipeline.completed"
        assert EET.PIPELINE_FAILED == "pipeline.failed"
        assert EET.PIPELINE_CANCELLED == "pipeline.cancelled"
        assert EET.PIPELINE_PATCH_TO_PR == "pipeline.patch_to_pr"
        assert EET.PIPELINE_PR_CREATED == "pipeline.pr_created"
        assert EET.PIPELINE_ARTIFACT_PASSED == "pipeline.artifact_passed"


# =============================================================================
# Full E2E Integration
# =============================================================================

class TestFullPipelineE2E:
    @pytest.mark.asyncio
    async def test_full_create_transition_delete_cycle(self, ops):
        p = await ops.create_pipeline(
            name="e2e-test",
            description="Full E2E pipeline test",
            mission_id="test-mission-123",
        )
        assert p["status"] == "pending"
        assert p["name"] == "e2e-test"

        result = await ops._transition(p["pipeline_id"], "running")
        assert result["status"] == "running"

        result = await ops._transition(p["pipeline_id"], "completed")
        assert result["status"] == "completed"

        assert await ops.delete_pipeline(p["pipeline_id"])
        assert await ops.get_pipeline(p["pipeline_id"]) is None

    @pytest.mark.asyncio
    async def test_full_pipeline_with_mocked_stages(self, ops):
        p = await ops.create_pipeline(
            name="mock-e2e",
            mission_id="test-mission",
            repo_url="https://github.com/org/repo",
        )
        p["status"] = "running"
        ops._pipelines[p["pipeline_id"]] = p

        executed_stages = []

        async def fake_execute(pid, stage):
            executed_stages.append(stage)

        ops._execute_stage = fake_execute
        await ops._execute_stages(p["pipeline_id"])
        assert executed_stages == PIPELINE_STAGES

        pipe = await ops.get_pipeline(p["pipeline_id"])
        assert pipe["status"] == "completed"
        assert set(pipe.get("stages_completed", [])) == set(PIPELINE_STAGES)

    @pytest.mark.asyncio
    async def test_e2e_start_pause_resume_cancel(self, ops):
        p = await ops.create_pipeline(
            name="lifecycle-test",
            mission_id="test-mission",
        )
        p["status"] = "running"
        ops._pipelines[p["pipeline_id"]] = p
        await ops._ensure_in_memory_synced(p["pipeline_id"])

        should_pause = [True]
        call_count = [0]

        async def fake_execute(pid, stage):
            call_count[0] += 1
            if should_pause[0] and call_count[0] == 3:
                await ops.update_pipeline(pid, {"status": "paused"})

        ops._execute_stage = fake_execute
        await ops._execute_stages(p["pipeline_id"])
        pipe = await ops.get_pipeline(p["pipeline_id"])
        assert pipe["status"] == "paused"
        assert call_count[0] == 3

        await ops.update_pipeline(p["pipeline_id"], {"status": "running"})
        should_pause[0] = False
        call_count[0] = 0
        result = await ops._execute_stages(p["pipeline_id"])

        assert result["status"] == "completed"

        assert await ops.delete_pipeline(p["pipeline_id"])

    @pytest.mark.asyncio
    async def test_e2e_three_pipelines_dashboard(self, ops):
        for i in range(3):
            p = await ops.create_pipeline(name=f"e2e-batch-{i}", mission_id=f"mission-{i}")
            p["status"] = "running"
            ops._pipelines[p["pipeline_id"]] = p

            async def fake(pid, stage):
                pass

            ops._execute_stage = fake
            await ops._execute_stages(p["pipeline_id"])

        stats = await ops.get_dashboard_stats()
        assert stats["total_pipelines"] == 3
        assert stats["completed"] == 3

    @pytest.mark.asyncio
    async def test_e2e_stage_failure_non_fatal(self, ops):
        p = await ops.create_pipeline(
            name="non-fatal-fail",
            mission_id="test-mission",
        )
        p["status"] = "running"
        ops._pipelines[p["pipeline_id"]] = p

        async def fake_execute(pid, stage):
            if stage == "code_intel":
                raise RuntimeError("Non-fatal code intel failure")

        ops._execute_stage = fake_execute
        result = await ops._execute_stages(p["pipeline_id"])
        assert result["status"] == "completed"
        assert "trigger" in result["stages_completed"]
        assert "sandbox" in result["stages_completed"]
        assert "code_intel" in result["stages_failed"]

    @pytest.mark.asyncio
    async def test_e2e_stage_failure_fatal(self, ops):
        p = await ops.create_pipeline(
            name="fatal-fail",
            mission_id="test-mission",
        )
        p["status"] = "running"
        ops._pipelines[p["pipeline_id"]] = p

        async def fake_execute(pid, stage):
            if stage == "patch":
                raise RuntimeError("Fatal patch failure")

        ops._execute_stage = fake_execute
        with pytest.raises(RuntimeError, match="Stage 'patch' failed"):
            await ops._execute_stages(p["pipeline_id"])

        pipe = await ops.get_pipeline(p["pipeline_id"])
        assert pipe["status"] == "failed"


# =============================================================================
# Event Hub Routing Test
# =============================================================================

class TestEventHubRouting:
    def test_pipeline_topic_routing(self):
        from backend.services.enterprise_event_hub import _topic_for_event
        assert _topic_for_event("pipeline.created") == "enterprise:pipeline"
        assert _topic_for_event("pipeline.started") == "enterprise:pipeline"
        assert _topic_for_event("pipeline.stage_completed") == "enterprise:pipeline"
        assert _topic_for_event("pipeline.patch_to_pr") == "enterprise:pipeline"
        assert _topic_for_event("git.branch_created") == "enterprise:git"
