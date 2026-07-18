from __future__ import annotations

import asyncio
from typing import Any, Dict

import pytest

from backend.orchestrator.artifact_manager import artifact_manager
from backend.orchestrator.engine import OrchestrationEngine
from backend.orchestrator.event_pipeline import event_pipeline
from backend.orchestrator.models import (
    ExecutionMode,
    FailureCategory,
    MissionLifecycleState,
    OrchestratorMission,
    OrchestratorStatus,
    StageResult,
)
from backend.orchestrator.recovery import (
    FailureClassifier,
    RecoveryManager,
    RecoveryStrategy,
)
from backend.orchestrator.service import AutonomousMissionOrchestrator
from backend.orchestrator.state_machine import MissionStateMachine


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def clean_state():
    event_pipeline._events.clear()
    event_pipeline._handlers.clear()
    artifact_manager._artifacts.clear()
    yield


@pytest.fixture
def engine():
    return OrchestrationEngine()


@pytest.fixture
def orch(engine):
    return AutonomousMissionOrchestrator(orchestration_engine=engine)


# =============================================================================
# Models
# =============================================================================


class TestMissionLifecycleState:
    def test_enum_values(self):
        assert MissionLifecycleState.RECEIVED.value == "mission_received"
        assert MissionLifecycleState.ANALYZED.value == "mission_analyzed"
        assert MissionLifecycleState.PLANNED.value == "mission_planned"
        assert MissionLifecycleState.KNOWLEDGE_RETRIEVED.value == "knowledge_retrieved"
        assert MissionLifecycleState.LEARNING_RETRIEVED.value == "learning_retrieved"
        assert MissionLifecycleState.GOVERNANCE_EVALUATED.value == "governance_evaluated"
        assert MissionLifecycleState.EXECUTION_PLANNED.value == "execution_planned"
        assert MissionLifecycleState.EXECUTION_STARTED.value == "execution_started"
        assert MissionLifecycleState.EXECUTION_COMPLETED.value == "execution_completed"
        assert MissionLifecycleState.VERIFIED.value == "verification"
        assert MissionLifecycleState.KNOWLEDGE_UPDATED.value == "knowledge_updated"
        assert MissionLifecycleState.LEARNING_UPDATED.value == "learning_updated"
        assert MissionLifecycleState.ARCHIVED.value == "mission_archived"

    def test_sequential_order(self):
        assert len(MissionStateMachine.SEQUENTIAL_ORDER) == 13


class TestOrchestratorStatus:
    def test_enum_values(self):
        assert OrchestratorStatus.PENDING.value == "pending"
        assert OrchestratorStatus.RUNNING.value == "running"
        assert OrchestratorStatus.PAUSED.value == "paused"
        assert OrchestratorStatus.CANCELLED.value == "cancelled"
        assert OrchestratorStatus.COMPLETED.value == "completed"
        assert OrchestratorStatus.FAILED.value == "failed"


class TestFailureCategory:
    def test_enum_values(self):
        assert FailureCategory.TRANSIENT.value == "transient"
        assert FailureCategory.POLICY.value == "policy"
        assert FailureCategory.CONNECTOR.value == "connector"
        assert FailureCategory.TIMEOUT.value == "timeout"
        assert FailureCategory.RUNTIME.value == "runtime"
        assert FailureCategory.UNKNOWN.value == "unknown"


class TestOrchestratorMission:
    def test_mission_creation(self):
        mission = OrchestratorMission(mission_id="m1", goal="Test goal")
        assert mission.mission_id == "m1"
        assert mission.goal == "Test goal"
        assert mission.current_state == MissionLifecycleState.RECEIVED
        assert mission.status == OrchestratorStatus.PENDING
        assert mission.created_at != ""
        assert mission.updated_at != ""

    def test_add_event(self):
        from backend.orchestrator.event_pipeline import event_pipeline
        mission = OrchestratorMission(mission_id="m2", goal="Test")
        event = event_pipeline.emit("m2", MissionLifecycleState.RECEIVED, "test.event", "test", "msg")
        mission.add_event(event)
        assert len(mission.timeline) == 1

    def test_set_state(self):
        mission = OrchestratorMission(mission_id="m3", goal="Test")
        mission.set_state(MissionLifecycleState.ANALYZED)
        assert mission.current_state == MissionLifecycleState.ANALYZED


# =============================================================================
# State Machine
# =============================================================================


class TestMissionStateMachine:
    def test_can_transition_valid(self):
        assert MissionStateMachine.can_transition("mission_received", "mission_analyzed")
        assert MissionStateMachine.can_transition("mission_analyzed", "mission_planned")
        assert MissionStateMachine.can_transition("mission_planned", "knowledge_retrieved")

    def test_can_transition_invalid(self):
        assert not MissionStateMachine.can_transition("mission_received", "mission_planned")
        assert not MissionStateMachine.can_transition("mission_archived", "mission_received")

    def test_is_terminal(self):
        assert MissionStateMachine.is_terminal("mission_archived")
        assert not MissionStateMachine.is_terminal("mission_received")

    def test_next_state(self):
        assert MissionStateMachine.next_state("mission_received") == "mission_analyzed"
        assert MissionStateMachine.next_state("mission_analyzed") == "mission_planned"
        assert MissionStateMachine.next_state("mission_planned") == "knowledge_retrieved"
        assert MissionStateMachine.next_state("learning_updated") == "mission_archived"
        assert MissionStateMachine.next_state("mission_archived") == "mission_archived"

    def test_can_change_status(self):
        assert MissionStateMachine.can_change_status("pending", "running")
        assert MissionStateMachine.can_change_status("running", "paused")
        assert MissionStateMachine.can_change_status("running", "completed")
        assert MissionStateMachine.can_change_status("paused", "running")
        assert MissionStateMachine.can_change_status("failed", "running")
        assert not MissionStateMachine.can_change_status("completed", "running")
        assert not MissionStateMachine.can_change_status("pending", "completed")

    def test_valid_transitions_count(self):
        assert len(MissionStateMachine.VALID_TRANSITIONS) == 13

    def test_status_transitions_count(self):
        assert len(MissionStateMachine.STATUS_TRANSITIONS) == 6


# =============================================================================
# Event Pipeline
# =============================================================================


class TestEventPipeline:
    def test_emit_event(self, clean_state):
        event = event_pipeline.emit(
            "m1", MissionLifecycleState.RECEIVED, "mission.received", "test", "hello"
        )
        assert event.mission_id == "m1"
        assert event.event_type == "mission.received"
        assert event.correlation_id != ""
        assert event.timestamp != ""

    def test_get_events(self, clean_state):
        event_pipeline.emit("m1", MissionLifecycleState.RECEIVED, "e1", "src", "msg")
        event_pipeline.emit("m1", MissionLifecycleState.ANALYZED, "e2", "src", "msg")
        events = event_pipeline.get_events("m1")
        assert len(events) == 2

    def test_get_events_by_type(self, clean_state):
        event_pipeline.emit("m1", MissionLifecycleState.RECEIVED, "type_a", "src", "msg")
        event_pipeline.emit("m1", MissionLifecycleState.ANALYZED, "type_b", "src", "msg")
        assert len(event_pipeline.get_events_by_type("m1", "type_a")) == 1

    def test_get_events_by_state(self, clean_state):
        event_pipeline.emit("m1", MissionLifecycleState.RECEIVED, "e1", "src", "msg")
        event_pipeline.emit("m1", MissionLifecycleState.RECEIVED, "e2", "src", "msg")
        assert len(event_pipeline.get_events_by_state("m1", MissionLifecycleState.RECEIVED)) == 2

    def test_register_handler(self, clean_state):
        results = []
        event_pipeline.register_handler("custom.event", lambda e: results.append(e))
        event_pipeline.emit("m1", MissionLifecycleState.RECEIVED, "custom.event", "src", "msg")
        assert len(results) == 1

    def test_isolation(self, clean_state):
        event_pipeline.emit("m1", MissionLifecycleState.RECEIVED, "e1", "src", "msg")
        event_pipeline.emit("m2", MissionLifecycleState.ANALYZED, "e2", "src", "msg")
        assert len(event_pipeline.get_events("m1")) == 1
        assert len(event_pipeline.get_events("m2")) == 1


# =============================================================================
# Artifact Manager
# =============================================================================


class TestArtifactManager:
    def test_add_artifact(self, clean_state):
        a = artifact_manager.add("m1", "output.txt", "text", b"data", source="test")
        assert a.name == "output.txt"
        assert a.artifact_type == "text"

    def test_get_artifact(self, clean_state):
        a = artifact_manager.add("m1", "out", "text", "data")
        assert artifact_manager.get("m1", a.artifact_id) is not None

    def test_list_by_mission(self, clean_state):
        artifact_manager.add("m1", "a1", "type1", "data")
        artifact_manager.add("m1", "a2", "type2", "data")
        assert len(artifact_manager.list_by_mission("m1")) == 2

    def test_list_by_type(self, clean_state):
        artifact_manager.add("m1", "a1", "report", "data")
        artifact_manager.add("m1", "a2", "log", "data")
        assert len(artifact_manager.list_by_type("m1", "report")) == 1

    def test_list_by_state(self, clean_state):
        artifact_manager.add("m1", "a1", "type", "data", state=MissionLifecycleState.ANALYZED)
        artifact_manager.add("m1", "a2", "type", "data", state=MissionLifecycleState.PLANNED)
        assert len(artifact_manager.list_by_state("m1", MissionLifecycleState.ANALYZED)) == 1

    def test_delete_artifact(self, clean_state):
        a = artifact_manager.add("m1", "del", "type", "data")
        assert artifact_manager.delete("m1", a.artifact_id)
        assert artifact_manager.get("m1", a.artifact_id) is None

    def test_clear_mission(self, clean_state):
        artifact_manager.add("m1", "a", "t", "d")
        artifact_manager.clear_mission("m1")
        assert len(artifact_manager.list_by_mission("m1")) == 0


# =============================================================================
# Recovery
# =============================================================================


class TestFailureClassifier:
    def test_classify_timeout(self):
        cat, strat = FailureClassifier.classify("Operation timed out after 30s", "exec")
        assert cat == FailureCategory.TIMEOUT
        assert strat == RecoveryStrategy.RETRY

    def test_classify_connector(self):
        cat, strat = FailureClassifier.classify("connector connection refused", "exec")
        assert cat == FailureCategory.CONNECTOR
        assert strat == RecoveryStrategy.RETRY

    def test_classify_policy(self):
        cat, strat = FailureClassifier.classify("policy violation detected", "gov")
        assert cat == FailureCategory.POLICY
        assert strat == RecoveryStrategy.COMPENSATE

    def test_classify_runtime(self):
        cat, strat = FailureClassifier.classify("runtime internal error", "exec")
        assert cat == FailureCategory.RUNTIME
        assert strat == RecoveryStrategy.ABORT

    def test_classify_unknown(self):
        cat, strat = FailureClassifier.classify("random error occurred", "exec")
        assert cat == FailureCategory.UNKNOWN
        assert strat == RecoveryStrategy.RETRY


class TestRecoveryManager:
    def test_save_and_get_checkpoint(self):
        rm = RecoveryManager()
        rm.save_checkpoint("m1", MissionLifecycleState.ANALYZED, {"key": "value"})
        cp = rm.get_checkpoint("m1")
        assert cp is not None
        assert cp["state"] == "mission_analyzed"
        assert cp["context"]["key"] == "value"

    def test_get_last_successful_state(self):
        rm = RecoveryManager()
        results = {
            "mission_received": StageResult(MissionLifecycleState.RECEIVED, True),
            "mission_analyzed": StageResult(MissionLifecycleState.ANALYZED, True),
            "mission_planned": StageResult(MissionLifecycleState.PLANNED, False, error="err"),
        }
        last = rm.get_last_successful_state("m1", results)
        assert last == "mission_analyzed"

    def test_should_retry(self):
        rm = RecoveryManager()
        rm.set_max_retries(3)
        assert rm.should_retry("m1", "mission_analyzed", 0)
        rm.record_retry("m1", "mission_analyzed")
        assert rm.should_retry("m1", "mission_analyzed", 0)

    def test_max_retries_exceeded(self):
        rm = RecoveryManager()
        rm.set_max_retries(1)
        rm.record_retry("m1", "exec")
        assert not rm.should_retry("m1", "exec", 0)

    def test_execute_compensation(self):
        from backend.orchestrator.recovery import CompensationHook
        rm = RecoveryManager()
        results = []
        hook = CompensationHook(
            name="test_hook",
            handler=lambda mid, s, ctx: results.append(mid),
            states=[MissionLifecycleState.PLANNED],
        )
        rm.register_compensation_hook(hook)
        rm.execute_compensation("m1", MissionLifecycleState.PLANNED, {})
        assert len(results) == 1

    def test_execute_rollback(self):
        rm = RecoveryManager()
        called = []
        rm.register_rollback_handler("mission_analyzed", lambda mid, s, ctx: called.append(mid))
        rm.execute_rollback("m1", "mission_analyzed", {})
        assert len(called) == 1


# =============================================================================
# Orchestration Engine
# =============================================================================


class TestOrchestrationEngine:
    @pytest.mark.asyncio
    async def test_full_lifecycle(self, clean_state):
        eng = OrchestrationEngine()

        async def make_handler(success: bool = True):
            async def handler(mission, ctx):
                return (success, {"result": f"{mission.goal} done"}, "")
            return handler

        state_order = [
            MissionLifecycleState.RECEIVED,
            MissionLifecycleState.ANALYZED,
            MissionLifecycleState.PLANNED,
            MissionLifecycleState.KNOWLEDGE_RETRIEVED,
            MissionLifecycleState.LEARNING_RETRIEVED,
            MissionLifecycleState.GOVERNANCE_EVALUATED,
            MissionLifecycleState.EXECUTION_PLANNED,
            MissionLifecycleState.EXECUTION_STARTED,
            MissionLifecycleState.EXECUTION_COMPLETED,
            MissionLifecycleState.VERIFIED,
            MissionLifecycleState.KNOWLEDGE_UPDATED,
            MissionLifecycleState.LEARNING_UPDATED,
        ]
        for state in state_order:
            h = await make_handler(True)
            eng.register_stage(state, h)

        mission = OrchestratorMission(mission_id="lifecycle_test", goal="Full lifecycle test")
        result = await eng.run_mission(mission)

        assert result.status == OrchestratorStatus.COMPLETED
        assert result.current_state == MissionLifecycleState.ARCHIVED
        assert len(result.stage_results) == 12

    @pytest.mark.asyncio
    async def test_stage_failure_retry(self, clean_state):
        eng = OrchestrationEngine()
        call_count = [0]

        async def failing_handler(mission, ctx):
            call_count[0] += 1
            if call_count[0] < 2:
                return (False, None, "timeout occurred")
            return (True, {"result": "ok"}, "")

        eng.register_stage(MissionLifecycleState.RECEIVED, failing_handler)

        mission = OrchestratorMission(mission_id="retry_test", goal="Retry test")
        result = await eng.run_mission(mission)

        assert result.stage_results.get("mission_received").success
        assert call_count[0] == 2

    @pytest.mark.asyncio
    async def test_stage_failure_no_retry_policy(self, clean_state):
        eng = OrchestrationEngine()

        async def policy_failure(mission, ctx):
            return (False, None, "policy violation - not allowed")

        eng.register_stage(MissionLifecycleState.RECEIVED, policy_failure)

        mission = OrchestratorMission(mission_id="policy_fail", goal="Policy fail test")
        result = await eng.run_mission(mission)

        assert result.status == OrchestratorStatus.FAILED
        assert result.failure_category == "policy"
        assert "policy" in result.error

    @pytest.mark.asyncio
    async def test_stage_timeout(self, clean_state):
        eng = OrchestrationEngine()

        async def slow_handler(mission, ctx):
            await asyncio.sleep(10)
            return (True, None, "")

        eng.register_stage(MissionLifecycleState.RECEIVED, slow_handler, timeout_seconds=0.05)

        mission = OrchestratorMission(mission_id="timeout_test", goal="Timeout test")
        result = await eng.run_mission(mission)

        stage = result.stage_results.get("mission_received")
        assert stage is not None
        assert not stage.success
        assert "timed out" in stage.error.lower()

    @pytest.mark.asyncio
    async def test_pause_and_resume(self, clean_state):
        eng = OrchestrationEngine()
        stage2_started = asyncio.Event()
        stage2_continue = asyncio.Event()

        async def handler1(mission, ctx):
            return (True, {"step": 1}, "")

        async def handler2(mission, ctx):
            stage2_started.set()
            await stage2_continue.wait()
            return (True, {"step": 2}, "")

        eng.register_stage(MissionLifecycleState.RECEIVED, handler1)
        eng.register_stage(MissionLifecycleState.ANALYZED, handler2)

        mission = OrchestratorMission(mission_id="pause_test", goal="Pause test")

        async def run():
            return await eng.run_mission(mission)

        result_future = asyncio.create_task(run())
        await asyncio.wait_for(stage2_started.wait(), timeout=2)

        paused = await eng.pause_mission("pause_test")
        assert paused
        assert mission.status == OrchestratorStatus.PAUSED

        resumed = await eng.resume_mission("pause_test")
        assert resumed
        assert mission.status == OrchestratorStatus.RUNNING

        stage2_continue.set()

        result = await asyncio.wait_for(result_future, timeout=5)
        assert result.status == OrchestratorStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_cancel(self, clean_state):
        eng = OrchestrationEngine()

        async def blocking_handler(mission, ctx):
            await asyncio.sleep(30)
            return (True, None, "")

        eng.register_stage(MissionLifecycleState.RECEIVED, blocking_handler)

        mission = OrchestratorMission(mission_id="cancel_test", goal="Cancel test")

        async def run():
            return await eng.run_mission(mission)

        result_future = asyncio.create_task(run())
        await asyncio.sleep(0.1)

        cancelled = await eng.cancel_mission("cancel_test")
        assert cancelled
        assert mission.status == OrchestratorStatus.CANCELLED

    @pytest.mark.asyncio
    async def test_no_handler_skips_stage(self, clean_state):
        eng = OrchestrationEngine()

        async def handler(mission, ctx):
            return (True, {"ok": True}, "")

        eng.register_stage(MissionLifecycleState.RECEIVED, handler)

        mission = OrchestratorMission(mission_id="skip_rest", goal="Skip test")
        result = await eng.run_mission(mission)

        assert result.status == OrchestratorStatus.COMPLETED
        assert "mission_received" in result.stage_results
        assert result.stage_results["mission_received"].result["ok"] is True
        assert result.stage_results["mission_analyzed"].metadata.get("skipped") is True

    @pytest.mark.asyncio
    async def test_conditional_branch(self, clean_state):
        eng = OrchestrationEngine()

        async def handler(mission, ctx):
            return (True, {"ok": True}, "")

        eng.register_stage(MissionLifecycleState.RECEIVED, handler)

        def branch_resolver(mission, ctx):
            return "mission_archived"

        eng.register_conditional_branch(MissionLifecycleState.ANALYZED, branch_resolver)

        async def skip_handler(mission, ctx):
            return (True, None, "")

        eng.register_stage(MissionLifecycleState.ARCHIVED, skip_handler)

        mission = OrchestratorMission(mission_id="branch_test", goal="Branch test")
        result = await eng.run_mission(mission)

        assert result.status == OrchestratorStatus.COMPLETED


# =============================================================================
# Orchestrator Service
# =============================================================================


class TestAutonomousMissionOrchestrator:
    @pytest.mark.asyncio
    async def test_start_and_run_mission(self, clean_state):
        eng = OrchestrationEngine()

        async def handler(mission, ctx):
            return (True, {"ok": True}, "")

        for state in [
            MissionLifecycleState.RECEIVED,
            MissionLifecycleState.ANALYZED,
            MissionLifecycleState.PLANNED,
            MissionLifecycleState.KNOWLEDGE_RETRIEVED,
            MissionLifecycleState.LEARNING_RETRIEVED,
            MissionLifecycleState.GOVERNANCE_EVALUATED,
            MissionLifecycleState.EXECUTION_PLANNED,
            MissionLifecycleState.EXECUTION_STARTED,
            MissionLifecycleState.EXECUTION_COMPLETED,
            MissionLifecycleState.VERIFIED,
            MissionLifecycleState.KNOWLEDGE_UPDATED,
            MissionLifecycleState.LEARNING_UPDATED,
        ]:
            eng.register_stage(state, handler)

        svc = AutonomousMissionOrchestrator(orchestration_engine=eng)
        mission = svc.start_mission("Test goal", mission_id="svc_test")
        assert mission.mission_id == "svc_test"
        assert mission.status == OrchestratorStatus.PENDING

        result = await svc.run_mission("svc_test")
        assert result is not None
        assert result.status == OrchestratorStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_get_mission(self, clean_state):
        svc = AutonomousMissionOrchestrator()
        svc.start_mission("Goal", mission_id="get_test")
        m = svc.get_mission("get_test")
        assert m is not None
        assert m.goal == "Goal"

    @pytest.mark.asyncio
    async def test_get_mission_nonexistent(self, clean_state):
        svc = AutonomousMissionOrchestrator()
        assert svc.get_mission("nonexistent") is None

    @pytest.mark.asyncio
    async def test_list_missions(self, clean_state):
        svc = AutonomousMissionOrchestrator()
        svc.start_mission("G1", mission_id="m1")
        svc.start_mission("G2", mission_id="m2")
        missions = svc.list_missions()
        assert len(missions) == 2

    @pytest.mark.asyncio
    async def test_list_missions_by_status(self, clean_state):
        svc = AutonomousMissionOrchestrator()
        svc.start_mission("G1", mission_id="m1")
        missions = svc.list_missions(status="pending")
        assert len(missions) == 1
        missions = svc.list_missions(status="running")
        assert len(missions) == 0

    @pytest.mark.asyncio
    async def test_list_active_missions(self, clean_state):
        svc = AutonomousMissionOrchestrator()
        svc.start_mission("G1", mission_id="m1")
        active = svc.list_active_missions()
        assert len(active) == 1

    @pytest.mark.asyncio
    async def test_get_mission_timeline(self, clean_state):
        svc = AutonomousMissionOrchestrator()
        svc.start_mission("G1", mission_id="tl_test")
        events = svc.get_mission_timeline("tl_test")
        assert len(events) == 1
        assert events[0]["event_type"] == "mission.received"

    @pytest.mark.asyncio
    async def test_get_artifacts(self, clean_state):
        svc = AutonomousMissionOrchestrator()
        svc.start_mission("G1", mission_id="art_test")
        artifact_manager.add("art_test", "out.txt", "text", b"data", source="test")
        artifacts = svc.get_artifacts("art_test")
        assert len(artifacts) == 1
        assert artifacts[0]["name"] == "out.txt"

    @pytest.mark.asyncio
    async def test_get_events(self, clean_state):
        svc = AutonomousMissionOrchestrator()
        svc.start_mission("G1", mission_id="ev_test")
        events = svc.get_events("ev_test")
        assert len(events) == 1

    @pytest.mark.asyncio
    async def test_get_mission_summary(self, clean_state):
        svc = AutonomousMissionOrchestrator()
        svc.start_mission("G1", mission_id="sum_test")
        summary = svc.get_mission_summary("sum_test")
        assert summary is not None
        assert summary["mission_id"] == "sum_test"
        assert summary["goal"] == "G1"
        assert summary["current_state"] == "mission_received"
        assert summary["status"] == "pending"

    @pytest.mark.asyncio
    async def test_health(self, clean_state):
        svc = AutonomousMissionOrchestrator()
        health = svc.health()
        assert health["status"] == "healthy"
        assert health["total_missions"] == 0

    @pytest.mark.asyncio
    async def test_pause_resume_mission(self, clean_state):
        eng = OrchestrationEngine()

        async def handler(mission, ctx):
            await asyncio.sleep(30)
            return (True, None, "")

        eng.register_stage(MissionLifecycleState.RECEIVED, handler)

        svc = AutonomousMissionOrchestrator(orchestration_engine=eng)
        svc.start_mission("G1", mission_id="pr_test")

        async def run():
            return await svc.run_mission("pr_test")

        result_future = asyncio.create_task(run())
        await asyncio.sleep(0.1)

        paused = await svc.pause_mission("pr_test")
        assert paused

        resumed = await svc.resume_mission("pr_test")
        assert resumed

        await svc.cancel_mission("pr_test")

    @pytest.mark.asyncio
    async def test_cancel_mission(self, clean_state):
        eng = OrchestrationEngine()

        async def handler(mission, ctx):
            await asyncio.sleep(30)
            return (True, None, "")

        eng.register_stage(MissionLifecycleState.RECEIVED, handler)

        svc = AutonomousMissionOrchestrator(orchestration_engine=eng)
        svc.start_mission("G1", mission_id="cancel_test2")

        async def run():
            return await svc.run_mission("cancel_test2")

        result_future = asyncio.create_task(run())
        await asyncio.sleep(0.1)

        cancelled = await svc.cancel_mission("cancel_test2")
        assert cancelled

    @pytest.mark.asyncio
    async def test_restart_from_checkpoint(self, clean_state):
        eng = OrchestrationEngine()
        call_count = [0]

        async def handler(mission, ctx):
            call_count[0] += 1
            return (True, {"count": call_count[0]}, "")

        eng.register_stage(MissionLifecycleState.RECEIVED, handler)

        svc = AutonomousMissionOrchestrator(orchestration_engine=eng)
        svc.start_mission("G1", mission_id="restart_test")

        result = await svc.run_mission("restart_test")
        assert result.status == OrchestratorStatus.COMPLETED
        assert call_count[0] == 1

        svc._missions["restart_test"].status = OrchestratorStatus.PENDING
        result2 = await svc.restart_from_checkpoint("restart_test")
        assert result2 is not None

    @pytest.mark.asyncio
    async def test_start_mission_generates_id(self, clean_state):
        svc = AutonomousMissionOrchestrator()
        m = svc.start_mission("Auto ID")
        assert m.mission_id != ""
        assert len(m.mission_id) == 12

    @pytest.mark.asyncio
    async def test_get_mission_summary_nonexistent(self, clean_state):
        svc = AutonomousMissionOrchestrator()
        assert svc.get_mission_summary("bad_id") is None


# =============================================================================
# Cross-Runtime Integration (without actual runtime dependencies)
# =============================================================================


class TestCrossRuntimeIntegration:
    @pytest.mark.asyncio
    async def test_mission_intel_integration(self, clean_state):
        eng = OrchestrationEngine()

        async def analyze(mission, ctx):
            return (True, {"analysis": "completed"}, "")

        async def decompose(mission, ctx):
            return (True, {"decomposition": "completed"}, "")

        async def plan(mission, ctx):
            return (True, {"plan": "completed"}, "")

        eng.register_stage(MissionLifecycleState.RECEIVED, analyze)
        eng.register_stage(MissionLifecycleState.ANALYZED, decompose)
        eng.register_stage(MissionLifecycleState.PLANNED, plan)

        svc = AutonomousMissionOrchestrator(orchestration_engine=eng)
        svc.start_mission("Integration test", mission_id="int_test")
        result = await svc.run_mission("int_test")

        assert result.stage_results["mission_received"].result["analysis"] == "completed"
        assert result.stage_results["mission_analyzed"].result["decomposition"] == "completed"
        assert result.stage_results["mission_planned"].result["plan"] == "completed"

    @pytest.mark.asyncio
    async def test_parallel_stage_execution(self, clean_state):
        eng = OrchestrationEngine()

        async def slow_handler(mission, ctx):
            await asyncio.sleep(0.05)
            return (True, {"done": True}, "")

        eng.register_stage(
            MissionLifecycleState.RECEIVED,
            slow_handler,
            mode=ExecutionMode.PARALLEL,
        )

        mission = OrchestratorMission(mission_id="parallel_test", goal="Parallel test")
        result = await eng.run_mission(mission)
        assert result.status == OrchestratorStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_artifact_tracking_across_stages(self, clean_state):
        eng = OrchestrationEngine()

        async def stage1(mission, ctx):
            artifact_manager.add(mission.mission_id, "stage1_out", "stage_result", {"step": 1}, source="stage1")
            return (True, {"step": 1}, "")

        async def stage2(mission, ctx):
            a = artifact_manager.add(mission.mission_id, "stage2_out", "stage_result", {"step": 2}, source="stage2")
            return (True, {"artifact_id": a.artifact_id}, "")

        eng.register_stage(MissionLifecycleState.RECEIVED, stage1)
        eng.register_stage(MissionLifecycleState.ANALYZED, stage2)

        svc = AutonomousMissionOrchestrator(orchestration_engine=eng)
        svc.start_mission("Artifact test", mission_id="art_cross")
        await svc.run_mission("art_cross")

        artifacts = svc.get_artifacts("art_cross")
        assert len(artifacts) >= 2
        types = {a["source"] for a in artifacts}
        assert "stage1" in types
        assert "stage2" in types

    @pytest.mark.asyncio
    async def test_event_correlation(self, clean_state):
        events = []

        event_pipeline.register_handler("stage.complete", lambda e: events.append(e))

        eng = OrchestrationEngine()

        async def handler(mission, ctx):
            return (True, {"ok": True}, "")

        eng.register_stage(MissionLifecycleState.RECEIVED, handler)

        svc = AutonomousMissionOrchestrator(orchestration_engine=eng)
        svc.start_mission("Event test", mission_id="ev_corr")
        await svc.run_mission("ev_corr")

        assert len(events) >= 1
        assert events[0].mission_id == "ev_corr"

    @pytest.mark.asyncio
    async def test_compensation_hook_execution(self, clean_state):
        from backend.orchestrator.recovery import CompensationHook
        eng = OrchestrationEngine()
        rm = RecoveryManager()
        compensated = []

        rm.register_compensation_hook(
            CompensationHook(
                name="comp_test",
                handler=lambda mid, s, ctx: compensated.append((mid, s)),
                states=[],
            )
        )

        eng._recovery_mgr = rm

        async def fail_handler(mission, ctx):
            return (False, None, "policy violation - not allowed")

        eng.register_stage(MissionLifecycleState.RECEIVED, fail_handler)

        mission = OrchestratorMission(mission_id="comp_test", goal="Comp test")
        result = await eng.run_mission(mission)

        assert result.status == OrchestratorStatus.FAILED
        assert result.failure_category == "policy"
        assert len(compensated) == 1
        assert compensated[0][0] == "comp_test"

    @pytest.mark.asyncio
    async def test_rollback_handler(self, clean_state):
        eng = OrchestrationEngine()
        rm = RecoveryManager()
        rolled_back = []

        rm.register_rollback_handler(
            "mission_received",
            lambda mid, s, ctx: rolled_back.append(mid),
        )

        eng._recovery_mgr = rm

        async def fail_handler(mission, ctx):
            return (False, None, "runtime internal crash")

        eng.register_stage(MissionLifecycleState.RECEIVED, fail_handler)

        mission = OrchestratorMission(mission_id="rb_test", goal="Rollback test")
        result = await eng.run_mission(mission)

        assert result.status == OrchestratorStatus.FAILED


# =============================================================================
# Routes
# =============================================================================


class TestRoutes:
    def test_router_imports(self):
        from backend.orchestrator.routes import router
        assert router is not None
        assert len(router.routes) > 0

    def test_router_prefix(self):
        from backend.orchestrator.routes import router
        assert router.prefix == "/api/orchestrator"

    def test_router_endpoints(self):
        from backend.orchestrator.routes import router
        paths = {r.path for r in router.routes}
        assert "/api/orchestrator/start" in paths
        assert "/api/orchestrator/pause" in paths
        assert "/api/orchestrator/resume" in paths
        assert "/api/orchestrator/cancel" in paths
        assert "/api/orchestrator/restart" in paths
        assert "/api/orchestrator/health" in paths
        assert any("/{mission_id}" in p or "/{mission_id}/timeline" in p for p in paths)

    def test_router_methods(self):
        from backend.orchestrator.routes import router
        methods = {}
        for r in router.routes:
            methods[r.path] = r.methods
        assert "POST" in methods.get("/api/orchestrator/start", set())
        assert "GET" in methods.get("/api/orchestrator/health", set())
