from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from agents.optimizer_agent.optimizer import OptimizerAgent
from agents.optimizer_agent.utils import safe_json_parse
from langgraph_system.state_management.cognitive_state import CognitiveState


@pytest.fixture
def mock_openai():
    with patch("agents.optimizer_agent.optimizer.client") as mock_client:
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content='{"optimized_execution_strategy": "event-driven microservices", "optimized_architecture_decisions": ["use Kafka"], "scalability_improvements": ["auto-scaling"], "security_enhancements": ["mTLS"], "operational_optimizations": ["observability stack"], "hallucination_reduction_measures": ["fact-checking pipeline"], "deployment_readiness_improvements": ["canary deployments"], "refined_execution_phases": [{"phase": "phase1", "optimization": "parallelize", "impact": "high"}], "confidence": 0.92, "metadata": {"optimization_level": "high", "architecture_maturity": "advanced", "production_readiness": "ready"}}'))]
        )
        yield mock_client


@pytest.fixture
def cognitive_state():
    return CognitiveState(
        user_goal="Build a scalable AI platform",
        research_data={
            "summary": "Research shows event-driven architecture is best",
            "domain": "AI",
        },
        planning_data={
            "execution_strategy": "Phased rollout with Kubernetes",
            "execution_phases": [{"phase": "phase1", "objective": "setup"}],
        },
        critique_data={
            "recommendations": ["add rate limiting", "improve monitoring"],
            "reasoning_validity": "high",
            "hallucination_risk": "low",
        },
    )


class TestOptimizerAgent:
    def test_execute_returns_expected_keys(self, mock_openai, cognitive_state):
        agent = OptimizerAgent()
        result = agent.execute(cognitive_state)

        assert isinstance(result, dict)
        assert result["agent"] == "optimizer_agent"
        assert result["status"] == "success"
        assert result["optimized_execution_strategy"] == "event-driven microservices"
        assert result["confidence"] == 0.92

    def test_execute_includes_all_optimization_fields(self, mock_openai, cognitive_state):
        agent = OptimizerAgent()
        result = agent.execute(cognitive_state)

        expected_keys = {
            "agent", "status", "optimized_execution_strategy",
            "optimized_architecture_decisions", "scalability_improvements",
            "security_enhancements", "operational_optimizations",
            "hallucination_reduction_measures", "deployment_readiness_improvements",
            "refined_execution_phases", "confidence", "metadata",
        }
        assert expected_keys.issubset(result.keys())
        assert result["optimized_architecture_decisions"] == ["use Kafka"]
        assert result["scalability_improvements"] == ["auto-scaling"]
        assert result["security_enhancements"] == ["mTLS"]
        assert result["operational_optimizations"] == ["observability stack"]
        assert result["hallucination_reduction_measures"] == ["fact-checking pipeline"]
        assert result["deployment_readiness_improvements"] == ["canary deployments"]

    def test_execute_refined_execution_phases(self, mock_openai, cognitive_state):
        agent = OptimizerAgent()
        result = agent.execute(cognitive_state)

        assert isinstance(result["refined_execution_phases"], list)
        assert len(result["refined_execution_phases"]) == 1
        phase = result["refined_execution_phases"][0]
        assert phase["phase"] == "phase1"
        assert phase["optimization"] == "parallelize"
        assert phase["impact"] == "high"

    def test_execute_handles_invalid_json(self, mock_openai, cognitive_state):
        mock_openai.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="not valid json"))]
        )
        agent = OptimizerAgent()
        result = agent.execute(cognitive_state)

        assert result["agent"] == "optimizer_agent"
        assert result["status"] == "failed"
        assert "Invalid JSON" in result["error"]
        assert result["raw_output"] == "not valid json"

    def test_execute_empty_llm_response(self, mock_openai, cognitive_state):
        mock_openai.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content=""))]
        )
        agent = OptimizerAgent()
        result = agent.execute(cognitive_state)

        assert result["status"] == "failed"

    def test_execute_uses_correct_temperature_and_format(self, mock_openai, cognitive_state):
        agent = OptimizerAgent()
        agent.execute(cognitive_state)

        call_kwargs = mock_openai.chat.completions.create.call_args[1]
        assert call_kwargs["temperature"] == 0.2
        assert call_kwargs["max_tokens"] == 1200
        assert call_kwargs["response_format"] == {"type": "json_object"}

    def test_execute_includes_all_state_in_prompt(self, mock_openai, cognitive_state):
        agent = OptimizerAgent()
        agent.execute(cognitive_state)

        messages = mock_openai.chat.completions.create.call_args[1]["messages"]
        user_content = messages[1]["content"]
        assert cognitive_state.user_goal in user_content
        assert cognitive_state.research_data["summary"] in user_content
        assert cognitive_state.planning_data["execution_strategy"] in user_content
        assert "add rate limiting" in user_content
        assert "improve monitoring" in user_content

    def test_execute_metadata_contains_expected_keys(self, mock_openai, cognitive_state):
        agent = OptimizerAgent()
        result = agent.execute(cognitive_state)

        meta = result["metadata"]
        assert "optimization_level" in meta
        assert "architecture_maturity" in meta
        assert "production_readiness" in meta

    def test_execute_with_empty_critique_data(self, mock_openai):
        state = CognitiveState(
            user_goal="test",
            research_data={"summary": "test"},
            planning_data={"execution_strategy": "test"},
            critique_data={},
        )
        agent = OptimizerAgent()
        result = agent.execute(state)

        assert result["status"] == "success"

    def test_execute_with_all_empty_data(self, mock_openai):
        state = CognitiveState(
            user_goal="test",
            research_data={},
            planning_data={},
            critique_data={},
        )
        agent = OptimizerAgent()
        result = agent.execute(state)

        assert result["status"] == "success"

    def test_safe_json_parse_valid(self):
        result = safe_json_parse('{"key": "value"}')
        assert result == {"key": "value"}

    def test_safe_json_parse_with_markdown_code_block(self):
        raw = "```json\n{\"key\": \"value\"}\n```"
        result = safe_json_parse(raw)
        assert result == {"key": "value"}

    def test_safe_json_parse_with_triple_backticks_only(self):
        raw = "```\n{\"key\": \"value\"}\n```"
        result = safe_json_parse(raw)
        assert result == {"key": "value"}

    def test_safe_json_parse_extra_whitespace(self):
        raw = "  \n  {\"key\": \"value\"}  \n  "
        result = safe_json_parse(raw)
        assert result == {"key": "value"}

    def test_safe_json_parse_invalid_returns_none(self):
        result = safe_json_parse("not json at all")
        assert result is None
