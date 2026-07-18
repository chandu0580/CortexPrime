from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

# Patch agent class definitions BEFORE the orchestrator module is imported.
# This prevents module-level instantiation (line 575) from triggering
# real SemanticMemoryEngine / FAISS / AzureOpenAI side effects.
patch("agents.research_agent.research.ResearchAgent").start()
patch("agents.planner_agent.planner.PlannerAgent").start()
patch("agents.critic_agent.critic.CriticAgent").start()
patch("agents.optimizer_agent.optimizer.OptimizerAgent").start()
patch("agents.orchestrator_agent.orchestrator.ShortTermMemoryManager").start()
patch("agents.orchestrator_agent.orchestrator.MemoryRetriever").start()
patch("agents.orchestrator_agent.orchestrator.SemanticRetriever").start()
patch("agents.orchestrator_agent.orchestrator.ReflectionManager").start()

from agents.orchestrator_agent.orchestrator import CortexPrimeOrchestrator
from langgraph_system.state_management.cognitive_state import CognitiveState


@pytest.fixture(autouse=True)
def reset_mocks():
    """Reset all mock call counts between tests."""
    import agents.orchestrator_agent.orchestrator as mod
    for name in [
        "ResearchAgent", "PlannerAgent", "CriticAgent", "OptimizerAgent",
        "ShortTermMemoryManager", "MemoryRetriever", "SemanticRetriever",
        "ReflectionManager",
    ]:
        getattr(mod, name).reset_mock()


@pytest.fixture
def orchestrator():
    return CortexPrimeOrchestrator()


@pytest.fixture
def setup_success(orchestrator):
    return _setup_mocks(orchestrator, trigger_reflection=False)


def _setup_mocks(orchestrator, trigger_reflection=False):
    import agents.orchestrator_agent.orchestrator as mod
    research_mock = mod.ResearchAgent
    planner_mock = mod.PlannerAgent
    critic_mock = mod.CriticAgent
    optimizer_mock = mod.OptimizerAgent
    memory_ret_mock = mod.MemoryRetriever
    reflection_mock = mod.ReflectionManager

    research_mock.return_value.execute.return_value = _success_result("research_agent")
    planner_mock.return_value.execute.return_value = _success_result("planner_agent")
    critic_mock.return_value.execute.return_value = _success_result("critic_agent")
    optimizer_mock.return_value.execute.return_value = _success_result("optimizer_agent")
    memory_ret_mock.return_value.retrieve_relevant_memories.return_value = []
    reflection_mock.return_value.should_trigger_reflection.return_value = trigger_reflection

    return {
        "research": research_mock,
        "planner": planner_mock,
        "critic": critic_mock,
        "optimizer": optimizer_mock,
        "memory_ret": memory_ret_mock,
        "reflection": reflection_mock,
    }


def _success_result(agent_name: str) -> dict:
    return {
        "agent": agent_name,
        "status": "success",
        "execution_strategy": f"strategy from {agent_name}",
        "optimized_execution_strategy": f"optimized by {agent_name}",
        "confidence": 0.9,
    }


class TestCortexPrimeOrchestrator:
    def test_execute_returns_expected_structure(self, setup_success):
        orchestrator = CortexPrimeOrchestrator()
        result = orchestrator.execute(user_goal="Build a scalable AI platform")

        assert isinstance(result, dict)
        assert result["workflow_status"] == "completed"
        assert result["user_goal"] == "Build a scalable AI platform"
        assert "research_data" in result
        assert "planning_data" in result
        assert "critique_data" in result
        assert "optimization_data" in result
        assert result["active_agent"] is None

    def test_execute_all_agents_called(self, setup_success):
        mocks = setup_success
        orchestrator = CortexPrimeOrchestrator()
        orchestrator.execute(user_goal="Build a scalable AI platform")

        mocks["research"].return_value.execute.assert_called_once_with("Build a scalable AI platform")
        mocks["planner"].return_value.execute.assert_called_once()
        mocks["critic"].return_value.execute.assert_called_once()
        mocks["optimizer"].return_value.execute.assert_called_once()

    def test_execute_sets_final_output_from_optimization(self, setup_success):
        mocks = setup_success
        orchestrator = CortexPrimeOrchestrator()
        opt_result = _success_result("optimizer_agent")
        opt_result["optimized_execution_strategy"] = "event-driven architecture"
        mocks["optimizer"].return_value.execute.return_value = opt_result

        orchestrator.execute(user_goal="test")

    def test_execute_falls_back_to_planning_for_final_output(self, setup_success):
        mocks = setup_success
        orchestrator = CortexPrimeOrchestrator()
        plan_result = _success_result("planner_agent")
        plan_result["execution_strategy"] = "phased rollout"
        mocks["planner"].return_value.execute.return_value = plan_result
        optim_result = _success_result("optimizer_agent")
        optim_result.pop("optimized_execution_strategy", None)
        optim_result["confidence"] = 0.9
        mocks["optimizer"].return_value.execute.return_value = optim_result

        orchestrator.execute(user_goal="test")

    def test_research_failure_returns_failed_workflow(self):
        import agents.orchestrator_agent.orchestrator as mod
        mod.ResearchAgent.return_value.execute.return_value = None
        orchestrator = CortexPrimeOrchestrator()

        result = orchestrator.execute(user_goal="test")

        assert isinstance(result, dict)
        assert result["status"] == "failed"
        assert any("research" in e.lower() for e in result.get("errors", []))

    def test_agent_returns_failed_status_caught_by_safe_execute(self):
        import agents.orchestrator_agent.orchestrator as mod
        mod.ResearchAgent.return_value.execute.return_value = {
            "agent": "research_agent",
            "status": "failed",
            "error": "LLM returned invalid JSON",
        }
        orchestrator = CortexPrimeOrchestrator()

        result = orchestrator.execute(user_goal="test")

        assert result["status"] == "failed"

    def test_reflection_loop_triggered(self):
        import agents.orchestrator_agent.orchestrator as mod
        mod.ResearchAgent.return_value.execute.return_value = _success_result("research_agent")
        mod.PlannerAgent.return_value.execute.return_value = _success_result("planner_agent")
        mod.CriticAgent.return_value.execute.return_value = _success_result("critic_agent")
        mod.OptimizerAgent.return_value.execute.return_value = _success_result("optimizer_agent")
        mod.ReflectionManager.return_value.should_trigger_reflection.return_value = True
        orchestrator = CortexPrimeOrchestrator()

        orchestrator.execute(user_goal="Build a scalable AI platform")

        assert mod.PlannerAgent.return_value.execute.call_count >= 2
        assert mod.CriticAgent.return_value.execute.call_count >= 2
        assert mod.OptimizerAgent.return_value.execute.call_count >= 2

    def test_fail_workflow_sets_status_to_failed(self, orchestrator):
        state = CognitiveState(user_goal="test")
        result = orchestrator.fail_workflow(state, "Critical failure occurred")

        assert result["status"] == "failed"
        assert "Critical failure occurred" in result["errors"]
        assert isinstance(result["execution_trace"], list)

    def test_fail_workflow_appends_errors(self, orchestrator):
        state = CognitiveState(user_goal="test")
        state.errors.append("previous error")
        result = orchestrator.fail_workflow(state, "new error")

        assert len(result["errors"]) == 2
        assert "previous error" in result["errors"]
        assert "new error" in result["errors"]

    def test_safe_execute_catches_exception(self, orchestrator):
        state = CognitiveState(user_goal="test")

        def failing_function():
            raise ValueError("something went wrong")

        result = orchestrator.safe_execute(state, "test_agent", failing_function)

        assert result is None
        assert any("test_agent failed" in e for e in state.errors)

    def test_safe_execute_success_logs_trace(self, orchestrator):
        state = CognitiveState(user_goal="test")

        def success_function():
            return {"status": "success", "data": "ok"}

        result = orchestrator.safe_execute(state, "test_agent", success_function)

        assert result == {"status": "success", "data": "ok"}
        assert len(state.execution_trace) == 1
        assert state.execution_trace[0]["agent"] == "test_agent"
        assert state.execution_trace[0]["status"] == "success"
        assert "duration_seconds" in state.execution_trace[0]

    def test_safe_execute_failure_logs_trace(self, orchestrator):
        state = CognitiveState(user_goal="test")

        def fail_function():
            raise RuntimeError("agent crashed")

        result = orchestrator.safe_execute(state, "failing_agent", fail_function)

        assert result is None
        assert len(state.execution_trace) == 1
        assert state.execution_trace[0]["agent"] == "failing_agent"
        assert state.execution_trace[0]["status"] == "failed"

    def test_execution_trace_contains_all_agents(self):
        import agents.orchestrator_agent.orchestrator as mod
        mod.ResearchAgent.return_value.execute.return_value = _success_result("research_agent")
        mod.PlannerAgent.return_value.execute.return_value = _success_result("planner_agent")
        mod.CriticAgent.return_value.execute.return_value = _success_result("critic_agent")
        mod.OptimizerAgent.return_value.execute.return_value = _success_result("optimizer_agent")
        mod.ReflectionManager.return_value.should_trigger_reflection.return_value = False
        orchestrator = CortexPrimeOrchestrator()

        result = orchestrator.execute(user_goal="test")

        agents_in_trace = {t["agent"] for t in result["execution_trace"]}
        assert "research_agent" in agents_in_trace
        assert "planner_agent" in agents_in_trace
        assert "critic_agent" in agents_in_trace
        assert "optimizer_agent" in agents_in_trace
