from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from agents.planner_agent.planner import PlannerAgent
from agents.planner_agent.utils import safe_json_parse
from langgraph_system.state_management.cognitive_state import CognitiveState


@pytest.fixture
def mock_openai():
    with patch("agents.planner_agent.planner.client") as mock_client:
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content='{"execution_strategy": "scalable microservices", "execution_phases": [{"phase": "phase1", "objective": "setup", "priority": "high", "deliverables": ["infra"]}], "dependencies": ["docker"], "technical_requirements": ["kubernetes"], "risks": ["latency"], "scalability_considerations": ["horizontal scaling"], "estimated_complexity": "high", "confidence": 0.85, "metadata": {"estimated_timeline": "3 months", "infrastructure_scale": "large", "operational_risk": "medium"}}'))]
        )
        yield mock_client


@pytest.fixture
def cognitive_state():
    return CognitiveState(
        user_goal="Build a scalable AI platform",
        research_data={"summary": "Research shows microservices architecture is best"},
    )


class TestPlannerAgent:
    def test_execute_returns_expected_keys(self, mock_openai, cognitive_state):
        agent = PlannerAgent()
        result = agent.execute(cognitive_state)

        assert isinstance(result, dict)
        assert result["agent"] == "planner_agent"
        assert result["status"] == "success"
        assert result["execution_strategy"] == "scalable microservices"
        assert result["estimated_complexity"] == "high"
        assert result["confidence"] == 0.85
        assert "execution_phases" in result
        assert isinstance(result["execution_phases"], list)
        assert len(result["execution_phases"]) == 1
        assert result["execution_phases"][0]["phase"] == "phase1"

    def test_execute_includes_all_planning_fields(self, mock_openai, cognitive_state):
        agent = PlannerAgent()
        result = agent.execute(cognitive_state)

        expected_keys = {
            "agent", "status", "execution_strategy", "execution_phases",
            "dependencies", "technical_requirements", "risks",
            "scalability_considerations", "estimated_complexity",
            "confidence", "metadata",
        }
        assert expected_keys.issubset(result.keys())
        assert result["dependencies"] == ["docker"]
        assert result["technical_requirements"] == ["kubernetes"]
        assert result["risks"] == ["latency"]

    def test_execute_handles_invalid_json(self, mock_openai, cognitive_state):
        mock_openai.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="not valid json"))]
        )
        agent = PlannerAgent()
        result = agent.execute(cognitive_state)

        assert result["agent"] == "planner_agent"
        assert result["status"] == "failed"
        assert "Invalid JSON" in result["error"]
        assert result["raw_output"] == "not valid json"

    def test_execute_empty_llm_response(self, mock_openai, cognitive_state):
        mock_openai.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content=""))]
        )
        agent = PlannerAgent()
        result = agent.execute(cognitive_state)

        assert result["status"] == "failed"

    def test_execute_uses_correct_temperature_and_format(self, mock_openai, cognitive_state):
        agent = PlannerAgent()
        agent.execute(cognitive_state)

        call_kwargs = mock_openai.chat.completions.create.call_args[1]
        assert call_kwargs["temperature"] == 0.2
        assert call_kwargs["max_tokens"] == 1200
        assert call_kwargs["response_format"] == {"type": "json_object"}

    def test_execute_includes_system_and_user_messages(self, mock_openai, cognitive_state):
        agent = PlannerAgent()
        agent.execute(cognitive_state)

        messages = mock_openai.chat.completions.create.call_args[1]["messages"]
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert cognitive_state.user_goal in messages[1]["content"]
        assert cognitive_state.research_data["summary"] in messages[1]["content"]

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

    def test_safe_json_parse_empty_string(self):
        result = safe_json_parse("")
        assert result is None
