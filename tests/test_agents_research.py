from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from agents.research_agent.research import ResearchAgent
from agents.research_agent.utils import safe_json_parse


@pytest.fixture
def mock_openai():
    with patch("agents.research_agent.research.client") as mock_client:
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content='{"domain": "AI platform", "complexity": "high", "confidence": 0.9, "summary": "Research summary here", "insights": ["insight1"], "risks": ["risk1"], "opportunities": ["opp1"], "reasoning_scope": ["scope1"], "metadata": {"urgency": "high", "strategic_value": "critical", "execution_difficulty": "medium"}}'))]
        )
        yield mock_client


@pytest.fixture
def mock_semantic_memory():
    with patch("agents.research_agent.research.SemanticMemoryEngine") as mock:
        engine = MagicMock()
        engine.search_memory.return_value = [
            {"memory_text": "Past project used microservices"},
        ]
        engine.store_memory.return_value = None
        mock.return_value = engine
        yield mock


class TestResearchAgent:
    def test_execute_returns_expected_keys(self, mock_openai, mock_semantic_memory):
        agent = ResearchAgent()
        result = agent.execute(user_goal="Build a scalable AI platform")

        assert isinstance(result, dict)
        assert result["agent"] == "research_agent"
        assert result["status"] == "success"
        assert result["domain"] == "AI platform"
        assert result["complexity"] == "high"
        assert result["confidence"] == 0.9
        assert result["summary"] == "Research summary here"

    def test_execute_includes_all_research_fields(self, mock_openai, mock_semantic_memory):
        agent = ResearchAgent()
        result = agent.execute(user_goal="Build a scalable AI platform")

        expected_keys = {
            "agent", "status", "domain", "complexity", "confidence",
            "summary", "insights", "risks", "opportunities",
            "reasoning_scope", "metadata",
        }
        assert expected_keys.issubset(result.keys())
        assert result["insights"] == ["insight1"]
        assert result["risks"] == ["risk1"]
        assert result["opportunities"] == ["opp1"]
        assert result["reasoning_scope"] == ["scope1"]

    def test_execute_handles_invalid_json(self, mock_openai, mock_semantic_memory):
        mock_openai.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="not valid json"))]
        )
        agent = ResearchAgent()
        result = agent.execute(user_goal="test goal")

        assert result["agent"] == "research_agent"
        assert result["status"] == "failed"
        assert "Invalid JSON" in result["error"]
        assert result["raw_output"] == "not valid json"

    def test_execute_empty_llm_response(self, mock_openai, mock_semantic_memory):
        mock_openai.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content=""))]
        )
        agent = ResearchAgent()
        result = agent.execute(user_goal="test goal")

        assert result["status"] == "failed"

    def test_execute_uses_correct_temperature_and_format(self, mock_openai, mock_semantic_memory):
        agent = ResearchAgent()
        agent.execute(user_goal="Build a scalable AI platform")

        call_kwargs = mock_openai.chat.completions.create.call_args[1]
        assert call_kwargs["temperature"] == 0.3
        assert call_kwargs["max_tokens"] == 1200
        assert call_kwargs["response_format"] == {"type": "json_object"}

    def test_execute_includes_user_goal_in_prompt(self, mock_openai, mock_semantic_memory):
        agent = ResearchAgent()
        agent.execute(user_goal="Custom goal for research")

        messages = mock_openai.chat.completions.create.call_args[1]["messages"]
        assert len(messages) == 2
        assert "Custom goal for research" in messages[1]["content"]

    def test_execute_calls_semantic_memory_search(self, mock_openai, mock_semantic_memory):
        agent = ResearchAgent()
        agent.execute(user_goal="Build a scalable AI platform")

        mock_semantic_memory.return_value.search_memory.assert_called_once_with(
            query="Build a scalable AI platform",
            top_k=3,
        )

    def test_execute_calls_semantic_memory_store(self, mock_openai, mock_semantic_memory):
        agent = ResearchAgent()
        agent.execute(user_goal="Build a scalable AI platform")

        mock_semantic_memory.return_value.store_memory.assert_called_once()
        call_kwargs = mock_semantic_memory.return_value.store_memory.call_args[1]
        assert "memory_text" in call_kwargs
        assert "metadata" in call_kwargs
        assert call_kwargs["metadata"]["agent"] == "research_agent"
        assert call_kwargs["metadata"]["domain"] == "AI platform"

    def test_normalize_list_field_with_strings(self):
        from agents.research_agent.research import normalize_list_field
        result = normalize_list_field(["  item1  ", "item2", ""])
        assert result == ["item1", "item2"]

    def test_normalize_list_field_with_dicts(self):
        from agents.research_agent.research import normalize_list_field
        result = normalize_list_field([
            {"key": "language", "value": "Python"},
            {"key": "framework", "value": "FastAPI"},
        ])
        assert "language: Python" in result
        assert "framework: FastAPI" in result

    def test_normalize_list_field_mixed_types(self):
        from agents.research_agent.research import normalize_list_field
        result = normalize_list_field(["string1", {"key": "k", "value": "v"}, 42])
        assert "string1" in result
        assert "k: v" in result
        assert "42" in result

    def test_execute_with_lists_in_response(self, mock_openai, mock_semantic_memory):
        mock_openai.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content='{"domain": "test", "complexity": "low", "confidence": 1.0, "summary": "test", "insights": [{"key": "i", "value": "1"}], "risks": ["risk_a", ""], "opportunities": [], "reasoning_scope": [], "metadata": {}}'))]
        )
        agent = ResearchAgent()
        result = agent.execute(user_goal="test")

        assert result["status"] == "success"
        assert "i: 1" in result["insights"]
        assert result["risks"] == ["risk_a"]

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
