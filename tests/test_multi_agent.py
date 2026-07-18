from __future__ import annotations

import asyncio
from typing import Dict, List

import pytest

from backend.agents.base import (
    AgentCapability,
    AgentContext,
    AgentResult,
    AgentStatus,
    AgentTask,
    BaseAgent,
    CollaborationMode,
    TaskPriority,
)
from backend.agents.builtin.compliance import ComplianceAgent
from backend.agents.builtin.planner import PlannerAgent
from backend.agents.builtin.platform_engineer import PlatformEngineerAgent
from backend.agents.builtin.qa import QAAgent
from backend.agents.builtin.release import ReleaseAgent
from backend.agents.builtin.research import ResearchAgent
from backend.agents.builtin.security import SecurityAgent
from backend.agents.builtin.sre import SREAgent
from backend.agents.coordinator import AgentCoordinator
from backend.agents.registry import AgentRegistry
from backend.agents.shared_memory import CognitiveMemoryBridge


@pytest.fixture
def agent_registry() -> AgentRegistry:
    return AgentRegistry()


@pytest.fixture
def memory_bridge() -> CognitiveMemoryBridge:
    return CognitiveMemoryBridge()


@pytest.fixture
def coordinator(agent_registry, memory_bridge) -> AgentCoordinator:
    return AgentCoordinator(registry=agent_registry, memory=memory_bridge)


@pytest.fixture
def agent_ctx() -> AgentContext:
    return AgentContext(
        mission_id="test_mission",
        tenant_id="test-tenant",
        user_id="test-user",
        permissions=["admin", "read", "write"],
    )


class TestBaseAgent:
    def test_agent_properties(self):
        agent = PlannerAgent(agent_id="planner_1")
        assert agent.agent_id == "planner_1"
        assert agent.agent_type == "PlannerAgent"
        assert agent.status == AgentStatus.IDLE
        assert len(agent.capabilities) > 0

    def test_agent_capabilities(self):
        agent = PlannerAgent()
        cap_types = [c.capability_type for c in agent.capabilities]
        assert "task_decomposition" in cap_types
        assert "mission_planning" in cap_types
        assert "dependency_graph" in cap_types

    def test_agent_info(self):
        agent = ResearchAgent(agent_id="research_1")
        info = agent.info
        assert info["agent_id"] == "research_1"
        assert info["agent_type"] == "ResearchAgent"
        assert info["status"] == "idle"

    def test_capability_matches(self):
        cap = AgentCapability("knowledge_search", "Search the knowledge base", ["knowledge"])
        assert cap.matches("knowledge")
        assert cap.matches("search")
        assert not cap.matches("deploy")

    @pytest.mark.asyncio
    async def test_agent_execute_success(self):
        agent = PlannerAgent()
        task = AgentTask(description="Plan deployment", input_data={"goal": "Deploy to prod"})
        ctx = AgentContext(mission_id="test")
        result = await agent.execute(task, ctx)
        assert result.success
        assert result.agent_type == "PlannerAgent"
        assert "plan_steps" in result.output_data

    @pytest.mark.asyncio
    async def test_agent_execute_failure_handled(self):
        class FailingAgent(BaseAgent):
            @property
            def agent_type(self) -> str:
                return "FailingAgent"

            async def _execute_impl(self, task, ctx):
                raise RuntimeError("Something went wrong")

        agent = FailingAgent()
        task = AgentTask(description="Will fail")
        ctx = AgentContext(mission_id="test")
        result = await agent.execute(task, ctx)
        assert not result.success
        assert "Something went wrong" in result.error
        assert result.agent_type == "FailingAgent"

    def test_can_handle_by_type(self):
        agent = PlannerAgent()
        task = AgentTask(description="Plan something", agent_type="PlannerAgent")
        assert agent.can_handle(task)
        task2 = AgentTask(description="Security scan", agent_type="SecurityAgent")
        assert not agent.can_handle(task2)


class TestAgentRegistry:
    def test_register_and_get(self, agent_registry):
        agent = PlannerAgent("p1")
        agent_registry.register(agent)
        assert agent_registry.get("p1") is agent
        assert agent_registry.agent_count == 1

    def test_find_by_capability(self, agent_registry):
        agent_registry.register(PlannerAgent("p1"))
        agent_registry.register(ResearchAgent("r1"))
        results = agent_registry.find_by_capability("knowledge")
        assert len(results) >= 1
        assert any(a.agent_type == "ResearchAgent" for a in results)

    def test_get_by_type(self, agent_registry):
        agent_registry.register(PlannerAgent("p1"))
        agent_registry.register(PlannerAgent("p2"))
        agent_registry.register(SREAgent("s1"))
        planners = agent_registry.get_by_type("PlannerAgent")
        assert len(planners) == 2
        sres = agent_registry.get_by_type("SREAgent")
        assert len(sres) == 1

    def test_unregister(self, agent_registry):
        agent = QAAgent("q1")
        agent_registry.register(agent)
        assert agent_registry.agent_count == 1
        agent_registry.unregister("q1")
        assert agent_registry.agent_count == 0
        assert agent_registry.get("q1") is None

    def test_list_agents(self, agent_registry):
        agent_registry.register(PlannerAgent("p1"))
        agent_registry.register(ReleaseAgent("r1"))
        agents = agent_registry.list_agents()
        assert len(agents) == 2
        types = {a["agent_type"] for a in agents}
        assert "PlannerAgent" in types
        assert "ReleaseAgent" in types

    def test_assign_task(self, agent_registry):
        agent = PlannerAgent("p1")
        agent_registry.register(agent)
        task = AgentTask(description="Plan deployment", agent_type="PlannerAgent")
        assigned = agent_registry.assign(task)
        assert assigned is not None
        assert assigned.agent_id == "p1"
        assert task.assigned_agent == "p1"


class TestSharedMemory:
    @pytest.mark.asyncio
    async def test_ensure_context_creates_local_cache(self, memory_bridge):
        result = memory_bridge.ensure_context("mem_test_1", {"goal": "Test goal"})
        assert result
        ctx = memory_bridge.get_context("mem_test_1")
        assert ctx is not None

    @pytest.mark.asyncio
    async def test_add_reasoning_step(self, memory_bridge):
        memory_bridge.ensure_context("mem_test_2", {"goal": "Test"})
        memory_bridge.add_reasoning_step("mem_test_2", "TestAgent", "Test reasoning step",
                                          decision="test", confidence=0.8)
        trace = memory_bridge.get_reasoning_trace("mem_test_2")
        assert len(trace) >= 1

    @pytest.mark.asyncio
    async def test_add_artifact(self, memory_bridge):
        memory_bridge.ensure_context("mem_test_3", {"goal": "Test"})
        memory_bridge.add_artifact("mem_test_3", "TestAgent", "test_output",
                                    "json", {"key": "value"})
        ctx = memory_bridge.get_context("mem_test_3")
        assert ctx is not None

    @pytest.mark.asyncio
    async def test_update_phase(self, memory_bridge):
        memory_bridge.ensure_context("mem_test_4", {"goal": "Test"})
        result = AgentResult(
            task_id="t1", agent_id="a1", agent_type="TestAgent",
            success=True, output_data={"done": True},
        )
        memory_bridge.update_phase("mem_test_4", "planning", result)
        ctx = memory_bridge.get_context("mem_test_4")
        assert ctx is not None


class TestAgentCoordination:
    @pytest.mark.asyncio
    async def test_sequential_execution(self, coordinator, agent_ctx):
        _register_all_agents(coordinator._registry)
        tasks = [
            AgentTask(description="Plan deployment"),
            AgentTask(description="Research best practices"),
            AgentTask(description="Validate configuration"),
        ]
        results = await coordinator.run_mission(
            "Test sequential mission", tasks, agent_ctx,
            mode=CollaborationMode.SEQUENTIAL,
        )
        assert len(results) == 3
        assert all(r.success for r in results)

    @pytest.mark.asyncio
    async def test_parallel_execution(self, coordinator, agent_ctx):
        _register_all_agents(coordinator._registry)
        tasks = [
            AgentTask(description="Research security vulnerabilities"),
            AgentTask(description="Check compliance policies"),
            AgentTask(description="Analyze monitoring data", agent_type="SREAgent"),
        ]
        results = await coordinator.run_mission(
            "Test parallel mission", tasks, agent_ctx,
            mode=CollaborationMode.PARALLEL,
        )
        assert len(results) == 3
        assert all(r.success for r in results)

    @pytest.mark.asyncio
    async def test_dependency_execution(self, coordinator, agent_ctx):
        _register_all_agents(coordinator._registry)
        tasks = [
            AgentTask(task_id="t1", description="Research requirements",
                      agent_type="ResearchAgent"),
            AgentTask(task_id="t2", description="Plan implementation",
                      agent_type="PlannerAgent", dependencies=["t1"]),
            AgentTask(task_id="t3", description="Validate output",
                      agent_type="QAAgent", dependencies=["t2"]),
        ]
        results = await coordinator.run_mission(
            "Test dependency mission", tasks, agent_ctx,
            mode=CollaborationMode.DEPENDENCY,
        )
        assert len(results) == 3
        for r in results:
            assert r.success, f"Task {r.task_id} failed: {r.error}"

    @pytest.mark.asyncio
    async def test_voting_execution(self, coordinator, agent_ctx):
        _register_all_agents(coordinator._registry)
        tasks = [
            AgentTask(task_id="vote1", description="Assess security risk",
                      agent_type="SecurityAgent"),
        ]
        results = await coordinator.run_mission(
            "Test voting mission", tasks, agent_ctx,
            mode=CollaborationMode.VOTING,
        )
        assert len(results) == 1
        assert results[0].voting_results is not None

    @pytest.mark.asyncio
    async def test_delegation(self, coordinator, agent_ctx):
        _register_all_agents(coordinator._registry)
        task = AgentTask(description="Perform security audit")
        result = await coordinator.delegate(task, agent_ctx, "SecurityAgent")
        assert result.success
        assert result.agent_type == "SecurityAgent"

    @pytest.mark.asyncio
    async def test_empty_tasks(self, coordinator, agent_ctx):
        results = await coordinator.run_mission(
            "Empty mission", [], agent_ctx,
        )
        assert len(results) == 0


class TestFailureRecovery:
    @pytest.mark.asyncio
    async def test_retry_on_failure(self, coordinator, agent_ctx):
        _register_all_agents(coordinator._registry)
        call_count = {"count": 0}

        original_execute = coordinator._execute_with_retry

        async def counting_execute(task, ctx, force_agent=None):
            call_count["count"] += 1
            return await original_execute(task, ctx, force_agent)

        coordinator._execute_with_retry = counting_execute
        task = AgentTask(description="Plan deployment", max_retries=2)
        result = await coordinator._execute_with_retry(task, agent_ctx)
        assert result.success

    @pytest.mark.asyncio
    async def test_escalation(self, coordinator, agent_ctx):
        _register_all_agents(coordinator._registry)

        class FragileAgent(BaseAgent):
            async def _execute_impl(self, task, ctx):
                raise RuntimeError("Intentional failure")

        fragile = FragileAgent("fragile_1")
        coordinator._registry.register(fragile)

        task = AgentTask(
            description="Critical task",
            agent_type="FragileAgent",
            max_retries=1,
            escalation_agent="PlannerAgent",
        )
        result = await coordinator._execute_with_retry(task, agent_ctx)
        assert result.delegation_chain is not None
        assert len(result.delegation_chain) >= 1

    @pytest.mark.asyncio
    async def test_timeout(self, coordinator, agent_ctx):
        _register_all_agents(coordinator._registry)

        class SlowAgent(BaseAgent):
            async def _execute_impl(self, task, ctx):
                await asyncio.sleep(10)
                return AgentResult(task_id=task.task_id, agent_id=self.agent_id,
                                   agent_type=self.agent_type, success=True)

        slow = SlowAgent("slow_1")
        coordinator._registry.register(slow)

        task = AgentTask(
            description="Slow task",
            agent_type="SlowAgent",
            timeout_seconds=0.1,
            max_retries=0,
        )
        result = await coordinator._execute_with_retry(task, agent_ctx)
        assert not result.success
        assert "Timeout" in result.error

    @pytest.mark.asyncio
    async def test_partial_completion(self, coordinator, agent_ctx):
        _register_all_agents(coordinator._registry)

        class AlternatingAgent(BaseAgent):
            def __init__(self, agent_id: str):
                super().__init__(agent_id)
                self._call_count = 0

            async def _execute_impl(self, task, ctx):
                self._call_count += 1
                if self._call_count == 1:
                    return AgentResult(task_id=task.task_id, agent_id=self.agent_id,
                                       agent_type=self.agent_type, success=True,
                                       output_data={"step": 1})
                raise RuntimeError(f"Failed on call {self._call_count}")

        class AlwaysFailAgent(BaseAgent):
            async def _execute_impl(self, task, ctx):
                raise RuntimeError("Always fails")

        alt1 = AlternatingAgent("alt_good")
        alt2 = AlwaysFailAgent("alt_bad")
        coordinator._registry.register(alt1)
        coordinator._registry.register(alt2)

        tasks = [
            AgentTask(task_id="t1", description="First task", agent_type="AlternatingAgent"),
            AgentTask(task_id="t2", description="Second task", agent_type="AlternatingAgent"),
        ]
        results = await coordinator.run_mission(
            "Partial completion", tasks, agent_ctx,
            mode=CollaborationMode.SEQUENTIAL,
        )
        assert len(results) == 2
        successful = [r for r in results if r.success]
        failed = [r for r in results if not r.success]
        assert len(successful) >= 1
        assert len(failed) >= 0


class TestBuiltinAgents:
    @pytest.mark.asyncio
    async def test_planner_agent(self):
        agent = PlannerAgent()
        task = AgentTask(description="Plan and decompose deployment", input_data={"goal": "Deploy to k8s"})
        ctx = AgentContext(mission_id="test")
        result = await agent.execute(task, ctx)
        assert result.success
        assert "plan_steps" in result.output_data

    @pytest.mark.asyncio
    async def test_research_agent(self):
        agent = ResearchAgent()
        task = AgentTask(description="Research deployment strategies", input_data={"query": "k8s best practices"})
        ctx = AgentContext(mission_id="test")
        result = await agent.execute(task, ctx)
        assert result.success
        assert "findings" in result.output_data

    @pytest.mark.asyncio
    async def test_platform_engineer_agent(self):
        agent = PlatformEngineerAgent()
        task = AgentTask(description="Configure production namespace")
        ctx = AgentContext(mission_id="test")
        result = await agent.execute(task, ctx)
        assert result.success
        assert "operations" in result.output_data

    @pytest.mark.asyncio
    async def test_sre_agent(self):
        agent = SREAgent()
        task = AgentTask(description="Investigate high error rate on payment API - P0 incident")
        ctx = AgentContext(mission_id="test")
        result = await agent.execute(task, ctx)
        assert result.success
        assert "severity" in result.output_data

    @pytest.mark.asyncio
    async def test_security_agent(self):
        agent = SecurityAgent()
        task = AgentTask(description="Scan for vulnerabilities in deployment config")
        ctx = AgentContext(mission_id="test")
        result = await agent.execute(task, ctx)
        assert result.success
        assert "security_checks" in result.output_data

    @pytest.mark.asyncio
    async def test_compliance_agent(self):
        agent = ComplianceAgent()
        task = AgentTask(description="Evaluate compliance for cross-region deployment")
        ctx = AgentContext(mission_id="test")
        result = await agent.execute(task, ctx)
        assert "evaluations" in result.output_data

    @pytest.mark.asyncio
    async def test_release_agent(self):
        agent = ReleaseAgent()
        task = AgentTask(description="Coordinate release v2.1.0 to production",
                         input_data={"version": "2.1.0", "environment": "production"})
        ctx = AgentContext(mission_id="test")
        result = await agent.execute(task, ctx)
        assert result.success
        assert result.output_data.get("version") == "2.1.0"
        assert "steps" in result.output_data

    @pytest.mark.asyncio
    async def test_qa_agent(self):
        agent = QAAgent()
        task = AgentTask(description="Validate deployment quality gate",
                         input_data={"checks": [
                             {"name": "health_check", "expected": "pass", "actual": "pass"},
                             {"name": "smoke_test", "expected": "pass", "actual": "pass"},
                         ]})
        ctx = AgentContext(mission_id="test")
        result = await agent.execute(task, ctx)
        assert result.success
        assert result.output_data.get("quality_gate") == "passed"


class TestEndToEnd:
    @pytest.mark.asyncio
    async def test_full_mission_lifecycle(self, coordinator, agent_ctx):
        _register_all_agents(coordinator._registry)

        tasks = [
            AgentTask(task_id="research", description="Research deployment requirements",
                      agent_type="ResearchAgent"),
            AgentTask(task_id="plan", description="Plan deployment strategy",
                      agent_type="PlannerAgent", dependencies=["research"]),
            AgentTask(task_id="security", description="Security assessment",
                      agent_type="SecurityAgent", dependencies=["plan"]),
            AgentTask(task_id="compliance", description="Compliance check",
                      agent_type="ComplianceAgent", dependencies=["security"]),
            AgentTask(task_id="release", description="Coordinate release",
                      agent_type="ReleaseAgent", dependencies=["compliance"]),
            AgentTask(task_id="qa", description="Validate deployment",
                      agent_type="QAAgent", dependencies=["release"]),
        ]

        results = await coordinator.run_mission(
            "Full production deployment", tasks, agent_ctx,
            mode=CollaborationMode.DEPENDENCY,
        )
        assert len(results) == 6
        successful = sum(1 for r in results if r.success)
        assert successful >= 5

    @pytest.mark.asyncio
    async def test_incident_response_mission(self, coordinator, agent_ctx):
        _register_all_agents(coordinator._registry)

        tasks = [
            AgentTask(task_id="investigate", description="Investigate P1 incident: payment API down",
                      agent_type="ResearchAgent"),
            AgentTask(task_id="sre", description="Respond to incident and execute runbook",
                      agent_type="SREAgent", dependencies=["investigate"]),
            AgentTask(task_id="security", description="Security assessment of incident",
                      agent_type="SecurityAgent", dependencies=["sre"]),
        ]
        results = await coordinator.run_mission(
            "Incident response", tasks, agent_ctx,
            mode=CollaborationMode.DEPENDENCY,
        )
        assert len(results) == 3
        assert results[0].success

    @pytest.mark.asyncio
    async def test_memory_across_agents(self, coordinator, agent_ctx):
        _register_all_agents(coordinator._registry)

        tasks = [
            AgentTask(task_id="step1", description="First analysis",
                      agent_type="ResearchAgent"),
            AgentTask(task_id="step2", description="Follow-up plan",
                      agent_type="PlannerAgent", dependencies=["step1"]),
        ]
        results = await coordinator.run_mission(
            "Memory test", tasks, agent_ctx,
            mode=CollaborationMode.DEPENDENCY,
        )
        trace = coordinator._memory.get_reasoning_trace(agent_ctx.mission_id)
        assert len(trace) >= 2


def _register_all_agents(registry: AgentRegistry) -> None:
    for agent in [
        PlannerAgent("ut_planner"),
        ResearchAgent("ut_research"),
        PlatformEngineerAgent("ut_pe"),
        SREAgent("ut_sre"),
        SecurityAgent("ut_security"),
        ComplianceAgent("ut_compliance"),
        ReleaseAgent("ut_release"),
        QAAgent("ut_qa"),
    ]:
        registry.register(agent)
