from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from agents.critic_agent.critic import CriticAgent
from agents.critic_agent.utils import safe_json_parse
from langgraph_system.state_management.cognitive_state import CognitiveState


@pytest.fixture
def mock_openai():
    with patch("agents.critic_agent.critic.client") as mock_client:
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content='{"reasoning_validity": "high", "hallucination_risk": "low", "execution_feasibility": "feasible", "contradictions_detected": ["timeline vs scope"], "scalability_concerns": ["database bottleneck"], "security_risks": ["auth weakness"], "compliance_issues": ["gdpr gap"], "operational_weaknesses": ["monitoring lack"], "recommendations": ["add rate limiting"], "confidence": 0.75, "metadata": {"overall_risk_level": "medium", "architecture_stability": "stable", "deployment_readiness": "ready"}}'))]
        )
        yield mock_client


@pytest.fixture
def cognitive_state():
    return CognitiveState(
        user_goal="Build a scalable AI platform",
        research_data={
            "summary": "Research shows microservices architecture is best",
            "domain": "AI",
        },
        planning_data={
            "execution_strategy": "Phased rollout with Kubernetes",
            "execution_phases": [{"phase": "phase1", "objective": "setup"}],
        },
    )


class TestCriticAgent:
    def test_execute_returns_expected_keys(self, mock_openai, cognitive_state):
        agent = CriticAgent()
        result = agent.execute(cognitive_state)

        assert isinstance(result, dict)
        assert result["agent"] == "critic_agent"
        assert result["status"] == "success"
        assert result["reasoning_validity"] == "high"
        assert result["hallucination_risk"] == "low"
        assert result["execution_feasibility"] == "feasible"
        assert result["confidence"] == 0.75

    def test_execute_includes_all_critique_fields(self, mock_openai, cognitive_state):
        agent = CriticAgent()
        result = agent.execute(cognitive_state)

        expected_keys = {
            "agent", "status", "reasoning_validity", "hallucination_risk",
            "execution_feasibility", "contradictions_detected",
            "scalability_concerns", "security_risks", "compliance_issues",
            "operational_weaknesses", "recommendations", "confidence", "metadata",
        }
        assert expected_keys.issubset(result.keys())
        assert result["contradictions_detected"] == ["timeline vs scope"]
        assert result["scalability_concerns"] == ["database bottleneck"]
        assert result["security_risks"] == ["auth weakness"]
        assert result["compliance_issues"] == ["gdpr gap"]
        assert result["operational_weaknesses"] == ["monitoring lack"]
        assert result["recommendations"] == ["add rate limiting"]

    def test_execute_handles_invalid_json(self, mock_openai, cognitive_state):
        mock_openai.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="not valid json"))]
        )
        agent = CriticAgent()
        result = agent.execute(cognitive_state)

        assert result["agent"] == "critic_agent"
        assert result["status"] == "failed"
        assert "Invalid JSON" in result["error"]
        assert result["raw_output"] == "not valid json"

    def test_execute_empty_llm_response(self, mock_openai, cognitive_state):
        mock_openai.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content=""))]
        )
        agent = CriticAgent()
        result = agent.execute(cognitive_state)

        assert result["status"] == "failed"

    def test_execute_uses_correct_temperature_and_format(self, mock_openai, cognitive_state):
        agent = CriticAgent()
        agent.execute(cognitive_state)

        call_kwargs = mock_openai.chat.completions.create.call_args[1]
        assert call_kwargs["temperature"] == 0.2
        assert call_kwargs["max_tokens"] == 1200
        assert call_kwargs["response_format"] == {"type": "json_object"}

    def test_execute_includes_state_data_in_prompt(self, mock_openai, cognitive_state):
        agent = CriticAgent()
        agent.execute(cognitive_state)

        messages = mock_openai.chat.completions.create.call_args[1]["messages"]
        user_content = messages[1]["content"]
        assert cognitive_state.user_goal in user_content
        assert cognitive_state.research_data["summary"] in user_content
        assert cognitive_state.planning_data["execution_strategy"] in user_content

    def test_execute_with_empty_research_data(self, mock_openai):
        state = CognitiveState(user_goal="test", research_data={}, planning_data={})
        agent = CriticAgent()
        result = agent.execute(state)

        assert result["status"] == "success"

    def test_execute_reasoning_validity_value(self, mock_openai, cognitive_state):
        agent = CriticAgent()
        result = agent.execute(cognitive_state)

        assert result["reasoning_validity"] in ("high", "medium", "low", "")

    def test_execute_hallucination_risk_value(self, mock_openai, cognitive_state):
        agent = CriticAgent()
        result = agent.execute(cognitive_state)

        assert result["hallucination_risk"] in ("high", "medium", "low", "")

    def test_execute_metadata_contains_expected_keys(self, mock_openai, cognitive_state):
        agent = CriticAgent()
        result = agent.execute(cognitive_state)

        meta = result["metadata"]
        assert "overall_risk_level" in meta
        assert "architecture_stability" in meta
        assert "deployment_readiness" in meta

    def test_execute_recommendations_is_list(self, mock_openai, cognitive_state):
        agent = CriticAgent()
        result = agent.execute(cognitive_state)

        assert isinstance(result["recommendations"], list)

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
