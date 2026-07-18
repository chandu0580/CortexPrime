from __future__ import annotations

import pytest

from backend.mission_intel.analyzer import mission_analyzer, MissionAnalyzer
from backend.mission_intel.capability_planner import capability_planner, CapabilityPlanner
from backend.mission_intel.decomposer import mission_decomposer, MissionDecomposer
from backend.mission_intel.execution_planner import execution_planner, ExecutionPlanner
from backend.mission_intel.governance_planner import governance_planner, GovernancePlanner
from backend.mission_intel.knowledge_planner import knowledge_planner, KnowledgePlanner
from backend.mission_intel.learning_planner import learning_planner, LearningPlanner
from backend.mission_intel.models import (
    CapabilityPlan,
    ComplianceCheck,
    ExecutionPlan,
    GovernancePlan,
    KnowledgeInsight,
    LearningInsight,
    MissionAnalysis,
    MissionDecomposition,
    MissionPriority,
    MissionStep,
    MissionTask,
    MissionTimeline,
    MissionVerification,
    PlanStatus,
    RiskLevel,
    TaskGroup,
    TimelineEntry,
)
from backend.mission_intel.service import MissionIntelligenceService, mission_intel_service
from backend.mission_intel.timeline import mission_timeline_builder, MissionTimelineBuilder
from backend.mission_intel.verification import mission_verifier, MissionVerifier


# ==============================================================================
# Mission Analyzer Tests
# ==============================================================================

class TestMissionAnalyzer:
    async def test_analyze_basic_goal(self):
        result = await mission_analyzer.analyze("Deploy software release to production")
        assert result.goal == "Deploy software release to production"
        assert result.category == "software_release"
        assert result.risk == RiskLevel.HIGH
        assert result.priority == MissionPriority.MEDIUM
        assert "deploy" in result.required_capabilities or "build" in result.required_capabilities
        assert result.confidence == 0.85
        assert result.reasoning

    async def test_analyze_incident_response(self):
        result = await mission_analyzer.analyze(
            "Incident affecting production database"
        )
        assert result.category == "incident_response"
        assert result.risk == RiskLevel.HIGH
        assert result.priority == MissionPriority.MEDIUM

    async def test_analyze_with_explicit_category(self):
        result = await mission_analyzer.analyze(
            "Run compliance audit",
            context={"category": "compliance_audit"},
        )
        assert result.category == "compliance_audit"

    async def test_analyze_with_priority_hint(self):
        result = await mission_analyzer.analyze(
            "Emergency security breach investigation",
            context={"priority": "critical"},
        )
        assert result.priority == MissionPriority.CRITICAL

    async def test_analyze_security_investigation(self):
        result = await mission_analyzer.analyze(
            "Security investigation for exposed credentials"
        )
        assert result.category == "security_investigation"

    async def test_analyze_constraints_extraction(self):
        result = await mission_analyzer.analyze(
            "Deploy within 2 hours, must not affect customer traffic"
        )
        assert len(result.constraints) > 0

    async def test_estimates_vary_by_risk(self):
        low = await mission_analyzer.analyze("Documentation update (low risk)", context={"risk": "low"})
        high = await mission_analyzer.analyze("Documentation update (high risk)", context={"risk": "high"})
        assert high.estimated_duration_minutes >= low.estimated_duration_minutes


# ==============================================================================
# Mission Decomposer Tests
# ==============================================================================

class TestMissionDecomposer:
    async def test_decompose_release(self):
        analysis = await mission_analyzer.analyze("Deploy software release")
        result = await mission_decomposer.decompose(analysis)
        assert result.mission_id.startswith("mi-")
        assert len(result.tasks) > 0
        assert len(result.steps) > 0
        assert result.estimated_duration_seconds > 0

    async def test_decompose_respects_category(self):
        analysis = await mission_analyzer.analyze("Security breach investigation")
        result = await mission_decomposer.decompose(analysis)
        task_names = [t.name for t in result.tasks]
        assert any("threat" in n or "alert" in n or "contain" in n for n in task_names)

    async def test_decompose_creates_groups(self):
        analysis = await mission_analyzer.analyze("Software release v2.0")
        result = await mission_decomposer.decompose(analysis)
        assert len(result.groups) > 0

    async def test_decompose_sequential_steps(self):
        analysis = await mission_analyzer.analyze("Investigate security alert")
        result = await mission_decomposer.decompose(analysis)
        for i, step in enumerate(result.steps):
            assert step.order == i
            if i > 0:
                assert f"s_{i - 1}" in step.depends_on or f"t_{i - 1}" in step.depends_on

    pass


# ==============================================================================
# Capability Planner Tests
# ==============================================================================

class TestCapabilityPlanner:
    async def test_plan_without_registry(self):
        analysis = await mission_analyzer.analyze("Deploy to kubernetes cluster")
        decomposition = await mission_decomposer.decompose(analysis)
        result = await capability_planner.plan(decomposition)
        assert isinstance(result, CapabilityPlan)
        assert len(result.task_mappings) > 0
        assert len(result.connector_mappings) > 0
        assert len(result.available_connectors) > 0

    async def test_plan_with_custom_registry(self):
        analysis = await mission_analyzer.analyze("Release software version 3.0")
        decomposition = await mission_decomposer.decompose(analysis)
        class MockRegistry:
            def list(self):
                return [{"connector_type": "github"}, {"connector_type": "slack"}]
        result = await capability_planner.plan(decomposition, MockRegistry())
        assert len(result.available_connectors) == 2
        assert "github" in result.available_connectors

    async def test_capability_gaps_detected(self):
        analysis = await mission_analyzer.analyze("Deploy with terraform")
        decomposition = await mission_decomposer.decompose(analysis)
        class EmptyRegistry:
            def list(self):
                return []
        result = await capability_planner.plan(decomposition, EmptyRegistry())
        assert result.available_connectors == []

    pass


# ==============================================================================
# Knowledge Planner Tests
# ==============================================================================

class TestKnowledgePlanner:
    async def test_plan_without_service(self):
        analysis = await mission_analyzer.analyze("Research market trends")
        result = await knowledge_planner.plan(analysis)
        assert isinstance(result, KnowledgeInsight)
        assert result.confidence == 0.0

    async def test_plan_with_mock_service(self):
        analysis = await mission_analyzer.analyze("Compliance audit for SOC2")
        mock_ks = type("MockKS", (), {
            "search": lambda kq: type("Result", (), {"entries": []})()
        })()
        planner = KnowledgePlanner(knowledge_service=mock_ks)
        result = await planner.plan(analysis)
        assert isinstance(result, KnowledgeInsight)


# ==============================================================================
# Learning Planner Tests
# ==============================================================================

class TestLearningPlanner:
    async def test_plan_without_service(self):
        analysis = await mission_analyzer.analyze("Standard change management")
        ki = KnowledgeInsight()
        result = await learning_planner.plan(analysis, ki)
        assert isinstance(result, LearningInsight)

    async def test_plan_with_mock_service(self):
        analysis = await mission_analyzer.analyze("Release v4.0")
        ki = KnowledgeInsight(similar_missions=[{"id": "1"}], previous_failures=[{"id": "f1"}])
        mock_ls = type("MockLS", (), {
            "list_patterns": lambda category, min_confidence, limit: [],
            "list_sessions": lambda mission_type, limit: [],
        })()
        planner = LearningPlanner(learning_service=mock_ls)
        result = await planner.plan(analysis, ki)
        assert isinstance(result, LearningInsight)


# ==============================================================================
# Governance Planner Tests
# ==============================================================================

class TestGovernancePlanner:
    async def test_low_risk_mission(self):
        analysis = MissionAnalysis(
            goal="Low risk doc update",
            category="knowledge_discovery",
            risk=RiskLevel.LOW,
            priority=MissionPriority.LOW,
        )
        li = LearningInsight()
        result = await governance_planner.plan(analysis, li)
        assert result.governance_level == "none"
        assert result.approved is True
        assert len(result.approval_gates) == 0

    async def test_high_risk_mission(self):
        analysis = MissionAnalysis(
            goal="Critical security incident",
            category="security_investigation",
            risk=RiskLevel.CRITICAL,
            priority=MissionPriority.HIGH,
        )
        li = LearningInsight()
        result = await governance_planner.plan(analysis, li)
        assert result.governance_level == "high"
        assert len(result.compliance_checks) > 0
        assert len(result.approval_gates) > 0

    async def test_regulated_category(self):
        analysis = MissionAnalysis(
            goal="SOC2 compliance audit",
            category="compliance_audit",
            risk=RiskLevel.MEDIUM,
            priority=MissionPriority.HIGH,
        )
        li = LearningInsight()
        result = await governance_planner.plan(analysis, li)
        policies = [c.policy for c in result.compliance_checks]
        assert "regulated_workflow_policy" in policies

    async def test_risk_indicators_add_checks(self):
        analysis = MissionAnalysis(
            goal="Test mission",
            category="knowledge_discovery",
            risk=RiskLevel.LOW,
            priority=MissionPriority.LOW,
        )
        li = LearningInsight(risk_indicators=["Low confidence pattern 'X'"])
        result = await governance_planner.plan(analysis, li)
        assert any("learning_risk_indicator" in c.policy for c in result.compliance_checks)


# ==============================================================================
# Execution Planner Tests
# ==============================================================================

class TestExecutionPlanner:
    async def test_basic_execution_plan(self):
        analysis = await mission_analyzer.analyze("Deploy software release")
        decomposition = await mission_decomposer.decompose(analysis)
        cp = await capability_planner.plan(decomposition)
        gp = GovernancePlan(risk_assessment=RiskLevel.LOW, approved=True)
        result = await execution_planner.plan(decomposition, cp, gp)
        assert isinstance(result, ExecutionPlan)
        assert result.mission_id == decomposition.mission_id
        assert len(result.sub_plans) > 0
        assert result.status == PlanStatus.PENDING

    async def test_execution_plan_with_retries(self):
        analysis = await mission_analyzer.analyze("Infrastructure deployment")
        decomposition = await mission_decomposer.decompose(analysis)
        cp = await capability_planner.plan(decomposition)
        gp = GovernancePlan(risk_assessment=RiskLevel.MEDIUM, approved=True)
        result = await execution_planner.plan(decomposition, cp, gp, context={"retries": 5})
        assert result.max_retries == 5

    async def test_execution_plan_connectors(self):
        analysis = await mission_analyzer.analyze("Release software")
        decomposition = await mission_decomposer.decompose(analysis)
        cp = await capability_planner.plan(decomposition)
        gp = GovernancePlan(risk_assessment=RiskLevel.LOW, approved=True)
        result = await execution_planner.plan(decomposition, cp, gp)
        assert len(result.connectors_needed) > 0


# ==============================================================================
# Mission Verification Tests
# ==============================================================================

class TestMissionVerifier:
    async def test_basic_verification(self):
        analysis = await mission_analyzer.analyze("Deploy software")
        decomposition = await mission_decomposer.decompose(analysis)
        cp = await capability_planner.plan(decomposition)
        gp = GovernancePlan(risk_assessment=RiskLevel.LOW, approved=True)
        ep = await execution_planner.plan(decomposition, cp, gp)
        result = await mission_verifier.verify(decomposition, ep)
        assert isinstance(result, MissionVerification)
        assert len(result.success_criteria) > 0
        assert len(result.verification_steps) > 0
        assert len(result.completion_criteria) > 0

    async def test_verification_methods(self):
        analysis = await mission_analyzer.analyze("Observe prometheus metrics")
        decomposition = await mission_decomposer.decompose(analysis)
        cp = await capability_planner.plan(decomposition)
        gp = GovernancePlan(risk_assessment=RiskLevel.LOW, approved=True)
        ep = await execution_planner.plan(decomposition, cp, gp)
        result = await mission_verifier.verify(decomposition, ep)
        for tid, method in result.verification_methods.items():
            assert isinstance(method, str)
            assert len(method) > 0

    async def test_rollback_criteria(self):
        analysis = await mission_analyzer.analyze("Critical deployment")
        decomposition = await mission_decomposer.decompose(analysis)
        cp = await capability_planner.plan(decomposition)
        gp = GovernancePlan(risk_assessment=RiskLevel.HIGH, approved=True)
        ep = await execution_planner.plan(decomposition, cp, gp)
        result = await mission_verifier.verify(decomposition, ep)
        assert len(result.rollback_criteria) > 0


# ==============================================================================
# Mission Timeline Tests
# ==============================================================================

class TestMissionTimelineBuilder:
    async def test_basic_timeline(self):
        analysis = await mission_analyzer.analyze("Release software v5.0")
        decomposition = await mission_decomposer.decompose(analysis)
        cp = await capability_planner.plan(decomposition)
        gp = GovernancePlan(risk_assessment=RiskLevel.LOW, approved=True)
        ep = await execution_planner.plan(decomposition, cp, gp)
        result = await mission_timeline_builder.build(analysis, decomposition, ep)
        assert isinstance(result, MissionTimeline)
        assert len(result.entries) > 0
        assert len(result.pipeline_steps) > 0
        assert len(result.connectors_used) > 0

    async def test_timeline_includes_constraints(self):
        analysis = await mission_analyzer.analyze("Deploy within 2 hours, must not affect traffic")
        decomposition = await mission_decomposer.decompose(analysis)
        cp = await capability_planner.plan(decomposition)
        gp = GovernancePlan(risk_assessment=RiskLevel.LOW, approved=True)
        ep = await execution_planner.plan(decomposition, cp, gp)
        result = await mission_timeline_builder.build(analysis, decomposition, ep)
        constraint_entries = [e for e in result.entries if e.event_type == "constraint_noted"]
        assert len(constraint_entries) > 0


# ==============================================================================
# Mission Intelligence Service Tests
# ==============================================================================

class TestMissionIntelligenceService:
    async def test_full_pipeline(self):
        result = await mission_intel_service.run_full_pipeline(
            "Deploy software release version 2.0 to production"
        )
        assert "analysis" in result
        assert "decomposition" in result
        assert "capability_plan" in result
        assert "knowledge_insight" in result
        assert "learning_insight" in result
        assert "governance_plan" in result
        assert "execution_plan" in result
        assert "verification" in result
        assert "timeline" in result
        assert result["analysis"].category == "software_release"

    async def test_analyze_only(self):
        result = await mission_intel_service.analyze("Investigate security alert")
        assert isinstance(result, MissionAnalysis)
        assert result.category == "security_investigation"

    async def test_individual_steps(self):
        analysis = await mission_intel_service.analyze("Compliance audit for SOC2")
        decomposition = await mission_intel_service.decompose(analysis)
        assert len(decomposition.tasks) > 0

        cp = await mission_intel_service.plan_capability(decomposition, None)
        assert len(cp.connector_mappings) > 0

        ki = await mission_intel_service.plan_knowledge(analysis)
        assert isinstance(ki, KnowledgeInsight)

        li = await mission_intel_service.plan_learning(analysis, ki)
        assert isinstance(li, LearningInsight)

        gp = await mission_intel_service.plan_governance(analysis, li)
        assert isinstance(gp, GovernancePlan)

        ep = await mission_intel_service.plan_execution(decomposition, cp, gp)
        assert isinstance(ep, ExecutionPlan)

        v = await mission_intel_service.verify(decomposition, ep)
        assert isinstance(v, MissionVerification)

        t = await mission_intel_service.build_timeline(analysis, decomposition, ep)
        assert isinstance(t, MissionTimeline)


# ==============================================================================
# Model Tests
# ==============================================================================

class TestModels:
    def test_risk_level_values(self):
        assert RiskLevel.LOW.value == "low"
        assert RiskLevel.MEDIUM.value == "medium"
        assert RiskLevel.HIGH.value == "high"
        assert RiskLevel.CRITICAL.value == "critical"

    def test_mission_priority_values(self):
        assert MissionPriority.LOWEST.value == "lowest"
        assert MissionPriority.CRITICAL.value == "critical"

    def test_mission_analysis_defaults(self):
        ma = MissionAnalysis(goal="test")
        assert ma.risk == RiskLevel.LOW
        assert ma.priority == MissionPriority.MEDIUM
        assert ma.constraints == []
        assert ma.confidence == 0.8

    def test_mission_task_defaults(self):
        mt = MissionTask(id="t1", name="test")
        assert mt.retry_allowed is True
        assert mt.params == {}

    def test_execution_plan_defaults(self):
        ep = ExecutionPlan()
        assert ep.status == PlanStatus.PENDING
        assert ep.max_retries == 2

    def test_compliance_check_defaults(self):
        cc = ComplianceCheck()
        assert cc.status == "pending"
        assert cc.required_role == "admin"

    def test_timeline_entry(self):
        te = TimelineEntry(timestamp="now", source="test", event_type="info", detail="detail")
        assert te.metadata == {}
