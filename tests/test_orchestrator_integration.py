from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from backend.orchestrator.artifact_manager import artifact_manager
from backend.orchestrator.engine import OrchestrationEngine
from backend.orchestrator.event_pipeline import event_pipeline
from backend.orchestrator.handlers import wire_runtime_handlers
from backend.orchestrator.models import (
    ExecutionMode,
    MissionLifecycleState,
    OrchestratorMission,
    OrchestratorStatus,
)
from backend.orchestrator.recovery import FailureClassifier, RecoveryManager
from backend.orchestrator.service import AutonomousMissionOrchestrator, orchestrator_service


@pytest.fixture
def clean_state():
    orchestrator_service._missions.clear()
    orchestrator_service._engine._running_missions.clear()
    orchestrator_service._engine._paused_missions.clear()
    orchestrator_service._engine._handlers_wired = False
    artifact_manager._artifacts.clear()
    event_pipeline._events.clear()
    yield


@pytest.fixture
def mock_di_container():
    patches = []

    def _mock_service(name, mock_obj):
        patcher = patch(f"backend.orchestrator.runtime_resolver._resolve", return_value=mock_obj)
        patcher.start()
        patches.append(patcher)
        return mock_obj

    yield _mock_service

    for p in patches:
        p.stop()


def _register_mock_handlers(eng: OrchestrationEngine) -> None:
    async def ok(mission, ctx):
        return True, {"ok": True, "runtime_result": f"handled_{MissionLifecycleState(mission.current_state).value}"}, ""

    async def analyze(mission, ctx):
        return True, {"category": "deployment", "complexity": "medium", "risk_score": 0.4}, ""

    async def plan(mission, ctx):
        return True, {
            "tasks": ["namespace-apply", "ingress-config", "health-check"],
            "capability_plan": {"connector": "k8s", "action": "apply"},
            "knowledge_insight": {"relevant_docs": 3},
            "learning_insight": {"patterns": 2},
            "governance_plan": {"approval": "auto"},
            "execution_plan": {"steps": ["apply", "verify"], "timeout": 300},
        }, ""

    async def k8s_execute(mission, ctx):
        return True, {
            "execution_id": "exec-k8s-001",
            "connectors": [
                {"connector": "kubernetes", "result": {"namespace": "production", "status": "created", "ingress": "configured"}},
                {"connector": "prometheus", "result": {"alerts": 0}},
            ],
        }, ""

    async def verify(mission, ctx):
        return True, {
            "verified": True,
            "checks_passed": 5,
            "checks_failed": 0,
        }, ""

    eng.register_stage(MissionLifecycleState.ANALYZED, analyze, timeout_seconds=30)
    eng.register_stage(MissionLifecycleState.PLANNED, plan, timeout_seconds=30)
    eng.register_stage(MissionLifecycleState.EXECUTION_STARTED, k8s_execute, timeout_seconds=60)
    eng.register_stage(MissionLifecycleState.VERIFIED, verify, timeout_seconds=30)

    for state in [
        MissionLifecycleState.KNOWLEDGE_RETRIEVED,
        MissionLifecycleState.LEARNING_RETRIEVED,
        MissionLifecycleState.GOVERNANCE_EVALUATED,
        MissionLifecycleState.EXECUTION_PLANNED,
        MissionLifecycleState.EXECUTION_COMPLETED,
        MissionLifecycleState.KNOWLEDGE_UPDATED,
        MissionLifecycleState.LEARNING_UPDATED,
    ]:
        eng.register_stage(state, ok, timeout_seconds=30)


class TestScenarioBasedIntegration:
    @pytest.mark.asyncio
    async def test_scenario_k8s_deploy(self, clean_state):
        eng = OrchestrationEngine()
        _register_mock_handlers(eng)
        service = AutonomousMissionOrchestrator(orchestration_engine=eng)
        mission = service.start_mission(
            goal="Deploy k8s namespace production and configure ingress",
            mission_id="int_k8s_001",
            tenant_id="acme-corp",
            user_id="devops-bot",
            permissions=["admin", "deploy"],
            metadata={"risk_level": "medium", "objective": "Production deployment", "category": "infrastructure"},
        )
        assert mission.mission_id == "int_k8s_001"
        assert mission.metadata["tenant_id"] == "acme-corp"
        assert mission.metadata["user_id"] == "devops-bot"

        result = await service.run_mission("int_k8s_001")
        assert result is not None
        assert result.status == OrchestratorStatus.COMPLETED

        summary = service.get_mission_summary("int_k8s_001")
        assert summary is not None
        assert summary["mission_id"] == "int_k8s_001"
        assert "stages" in summary
        assert "stage_metrics" in summary

        sorted_stages = [
            "mission_received", "mission_analyzed", "mission_planned",
            "knowledge_retrieved", "learning_retrieved", "governance_evaluated",
            "execution_planned", "execution_started", "execution_completed",
            "verification", "knowledge_updated", "learning_updated",
        ]
        for s in sorted_stages:
            assert s in summary["stages"], f"Missing stage {s}"

        timeline = service.get_events("int_k8s_001")
        assert len(timeline) > 0

        artifacts = service.get_artifacts("int_k8s_001")
        assert len(artifacts) > 0

    @pytest.mark.asyncio
    async def test_scenario_production_incident(self, clean_state):
        eng = OrchestrationEngine()
        _register_mock_handlers(eng)
        service = AutonomousMissionOrchestrator(orchestration_engine=eng)
        mission = service.start_mission(
            goal="Investigate production incident #4521: high error rate on payment API",
            mission_id="int_incident_001",
            tenant_id="acme-corp",
            user_id="sre-oncall",
            permissions=["read", "investigate"],
            metadata={
                "risk_level": "critical",
                "objective": "Root cause analysis and remediation",
                "category": "incident",
                "incident_id": "INC-4521",
                "source": "pagerduty",
            },
        )
        assert mission.mission_id == "int_incident_001"
        result = await service.run_mission("int_incident_001")
        assert result is not None
        assert result.status == OrchestratorStatus.COMPLETED
        summary = service.get_mission_summary("int_incident_001")
        assert "context" in summary
        assert summary["context"]["tenant_id"] == "acme-corp"
        assert summary["context"]["user_id"] == "sre-oncall"

    @pytest.mark.asyncio
    async def test_scenario_governance_rejection(self, clean_state):
        eng = OrchestrationEngine()
        eng._stage_handlers.clear()

        async def governance_deny(mission, ctx):
            return False, None, "Governance denied: policy violation - cross-region deployment not approved"

        for state in [
            MissionLifecycleState.ANALYZED,
            MissionLifecycleState.PLANNED,
            MissionLifecycleState.KNOWLEDGE_RETRIEVED,
            MissionLifecycleState.LEARNING_RETRIEVED,
            MissionLifecycleState.EXECUTION_PLANNED,
            MissionLifecycleState.EXECUTION_STARTED,
            MissionLifecycleState.EXECUTION_COMPLETED,
            MissionLifecycleState.VERIFIED,
            MissionLifecycleState.KNOWLEDGE_UPDATED,
            MissionLifecycleState.LEARNING_UPDATED,
        ]:
            async def ok_handler(mission, ctx):
                return True, {"ok": True}, ""
            eng.register_stage(state, ok_handler)

        async def analyze_handler(mission, ctx):
            return True, {"category": "deployment", "complexity": "medium"}, ""
        eng.register_stage(MissionLifecycleState.ANALYZED, analyze_handler)

        async def plan_handler(mission, ctx):
            return True, {"tasks": ["task1", "task2"], "execution_plan": {"steps": []}}, ""
        eng.register_stage(MissionLifecycleState.PLANNED, plan_handler)

        eng.register_stage(MissionLifecycleState.GOVERNANCE_EVALUATED, governance_deny)

        service = AutonomousMissionOrchestrator(orchestration_engine=eng)
        mission = service.start_mission(
            goal="Deploy to cross-region cluster",
            mission_id="int_deny_001",
        )
        result = await service.run_mission("int_deny_001")
        assert result is not None
        assert result.status == OrchestratorStatus.FAILED
        summary = service.get_mission_summary("int_deny_001")
        assert summary["failure_category"] == "policy"

    @pytest.mark.asyncio
    async def test_scenario_connector_timeout_with_retry(self, clean_state):
        eng = OrchestrationEngine()
        eng._stage_handlers.clear()
        eng._recovery_mgr = RecoveryManager()
        eng._recovery_mgr.set_max_retries(3)

        fail_once = {"count": 0}

        async def connector_handler(mission, ctx):
            fail_once["count"] += 1
            if fail_once["count"] < 2:
                return False, None, "Connector timeout: upstream service did not respond within 30s"
            return True, {"deployment_id": "dep-123", "status": "running"}, ""

        async def ok_handler(mission, ctx):
            return True, {"ok": True}, ""

        for state in [
            MissionLifecycleState.ANALYZED,
            MissionLifecycleState.PLANNED,
            MissionLifecycleState.KNOWLEDGE_RETRIEVED,
            MissionLifecycleState.LEARNING_RETRIEVED,
            MissionLifecycleState.GOVERNANCE_EVALUATED,
            MissionLifecycleState.EXECUTION_PLANNED,
            MissionLifecycleState.EXECUTION_COMPLETED,
            MissionLifecycleState.VERIFIED,
            MissionLifecycleState.KNOWLEDGE_UPDATED,
            MissionLifecycleState.LEARNING_UPDATED,
        ]:
            eng.register_stage(state, ok_handler)

        async def analyze_handler(mission, ctx):
            return True, {"category": "deployment", "complexity": "low"}, ""
        eng.register_stage(MissionLifecycleState.ANALYZED, analyze_handler)

        async def plan_handler(mission, ctx):
            return True, {"tasks": ["deploy"], "execution_plan": {"steps": []}}, ""
        eng.register_stage(MissionLifecycleState.PLANNED, plan_handler)

        eng.register_stage(MissionLifecycleState.EXECUTION_STARTED, connector_handler, timeout_seconds=10)

        service = AutonomousMissionOrchestrator(orchestration_engine=eng)
        mission = service.start_mission(
            goal="Deploy application to staging",
            mission_id="int_retry_001",
        )
        result = await service.run_mission("int_retry_001")
        assert result is not None
        assert result.status == OrchestratorStatus.COMPLETED, f"Failed: {result.error}"
        assert fail_once["count"] == 2
        stage = result.stage_results.get("execution_started")
        assert stage is not None
        assert stage.success

    @pytest.mark.asyncio
    async def test_scenario_checkpoint_restore(self, clean_state):
        from backend.orchestrator.recovery import recovery_manager
        recovery_manager._checkpoints.clear()

        eng = OrchestrationEngine()
        eng._stage_handlers.clear()

        async def fail_on_first(mission, ctx):
            if "restored" not in mission.metadata:
                return False, None, "Transient runtime error: service temporarily unavailable"
            return True, {"verified": True}, ""

        async def ok_handler(mission, ctx):
            return True, {"ok": True}, ""

        for state in [
            MissionLifecycleState.ANALYZED,
            MissionLifecycleState.PLANNED,
            MissionLifecycleState.KNOWLEDGE_RETRIEVED,
            MissionLifecycleState.LEARNING_RETRIEVED,
            MissionLifecycleState.GOVERNANCE_EVALUATED,
            MissionLifecycleState.EXECUTION_PLANNED,
            MissionLifecycleState.EXECUTION_STARTED,
            MissionLifecycleState.EXECUTION_COMPLETED,
            MissionLifecycleState.KNOWLEDGE_UPDATED,
            MissionLifecycleState.LEARNING_UPDATED,
        ]:
            eng.register_stage(state, ok_handler)

        async def analyze_handler(mission, ctx):
            return True, {"category": "config", "complexity": "low"}, ""
        eng.register_stage(MissionLifecycleState.ANALYZED, analyze_handler)

        async def plan_handler(mission, ctx):
            return True, {"tasks": ["verify"], "execution_plan": {"steps": []}}, ""
        eng.register_stage(MissionLifecycleState.PLANNED, plan_handler)

        eng.register_stage(MissionLifecycleState.VERIFIED, fail_on_first)

        service = AutonomousMissionOrchestrator(orchestration_engine=eng)
        mission = service.start_mission(
            goal="Verify cluster configuration",
            mission_id="int_ckpt_001",
        )
        result = await service.run_mission("int_ckpt_001")
        assert result is not None
        assert result.status == OrchestratorStatus.FAILED

        ckpt = eng._recovery_mgr.get_checkpoint("int_ckpt_001")
        assert ckpt is not None
        assert ckpt["state"] in [s.value for s in MissionLifecycleState]

        restored = await service.restart_from_checkpoint("int_ckpt_001")
        assert restored is not None
        mission_ref = service._missions["int_ckpt_001"]
        mission_ref.metadata["restored"] = True
        restored2 = await service.run_mission("int_ckpt_001")
        assert restored2 is not None
        assert restored2.status == OrchestratorStatus.COMPLETED


class TestContextPropagation:
    @pytest.mark.asyncio
    async def test_context_preserved_through_lifecycle(self, clean_state):
        eng = OrchestrationEngine()
        eng._ensure_runtime_handlers()
        service = AutonomousMissionOrchestrator(orchestration_engine=eng)
        mission = service.start_mission(
            goal="Test context",
            mission_id="int_ctx_001",
            tenant_id="tenant-alpha",
            user_id="user-beta",
            trace_id="trace-gamma",
            correlation_id="corr-delta",
            permissions=["read", "write", "admin"],
        )
        assert mission.context["tenant_id"] == "tenant-alpha"
        assert mission.context["user_id"] == "user-beta"
        assert mission.context["trace_id"] == "trace-gamma"
        assert mission.context["correlation_id"] == "corr-delta"
        assert mission.context["permissions"] == ["read", "write", "admin"]

        result = await service.run_mission("int_ctx_001")
        assert result is not None
        summary = service.get_mission_summary("int_ctx_001")
        assert summary["context"]["tenant_id"] == "tenant-alpha"

    @pytest.mark.asyncio
    async def test_default_context_generated(self, clean_state):
        eng = OrchestrationEngine()
        eng._ensure_runtime_handlers()
        service = AutonomousMissionOrchestrator(orchestration_engine=eng)
        mission = service.start_mission(
            goal="Test default context",
            mission_id="int_ctx_002",
        )
        assert mission.context["tenant_id"] == ""
        assert mission.context["user_id"] == ""
        assert mission.context["trace_id"] != ""
        assert mission.context["correlation_id"] != ""


class TestFullLifecycleWiring:
    @pytest.mark.asyncio
    async def test_all_real_handlers_gracefully_skip(self, clean_state):
        eng = OrchestrationEngine()
        eng._ensure_runtime_handlers()
        service = AutonomousMissionOrchestrator(orchestration_engine=eng)
        mission = service.start_mission(
            goal="Test all handlers gracefully skip when DI unavailable",
            mission_id="int_graceful_001",
        )
        result = await service.run_mission("int_graceful_001")
        assert result is not None
        for state_name, stage in result.stage_results.items():
            if stage.runtime:
                if not stage.success:
                    reason = (stage.error or "").lower()
                    assert "unavailable" in reason or "timeout" in reason or "denied" in reason, \
                        f"Stage {state_name} failed with unexpected error: {stage.error}"

    @pytest.mark.asyncio
    async def test_runtime_availability_reporting(self, clean_state):
        from backend.orchestrator.runtime_resolver import resolve_runtime_status
        status = resolve_runtime_status()
        assert isinstance(status, dict)
        expected = {"mission_intel", "knowledge", "learning", "governance",
                     "execution", "connector", "cognitive_memory", "mission", "ai"}
        assert set(status.keys()) == expected
        for name, available in status.items():
            assert isinstance(available, bool)
