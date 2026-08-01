from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.enterprise_alert_incident_reasoner import (
    build_prompt,
    generate_incident_hypothesis,
)

def _signals():
    return [
        {"source": "deploy_regression", "summary": "p95 latency +30%", "severity": "critical", "detected_at": "t1"},
        {"source": "rollback", "summary": "rollback to abc123 triggered", "severity": "info", "detected_at": "t2"},
    ]


class TestBuildPrompt:
    def test_includes_service_and_signal_sources(self):
        prompt = build_prompt("org/repo", _signals())
        assert "org/repo" in prompt
        assert "deploy_regression" in prompt
        assert "rollback" in prompt

    def test_empty_signals_uses_placeholder(self):
        prompt = build_prompt("org/repo", [])
        assert "(no signals)" in prompt


@pytest.mark.asyncio
class TestGenerateIncidentHypothesis:
    async def test_returns_none_with_fewer_than_two_signals(self):
        result = await generate_incident_hypothesis("org/repo", _signals()[:1])
        assert result is None

    async def test_returns_llm_output_on_success(self):
        fake_result = MagicMock(success=True, output="Likely the same root cause.")
        with patch("backend.llm.llm_router.llm_router.route", new=AsyncMock(return_value=fake_result)):
            result = await generate_incident_hypothesis("org/repo", _signals())
        assert result == "Likely the same root cause."

    async def test_returns_none_when_llm_call_fails(self):
        fake_result = MagicMock(success=False, error="provider down")
        with patch("backend.llm.llm_router.llm_router.route", new=AsyncMock(return_value=fake_result)):
            result = await generate_incident_hypothesis("org/repo", _signals())
        assert result is None

    async def test_returns_none_when_llm_call_raises(self):
        with patch("backend.llm.llm_router.llm_router.route", new=AsyncMock(side_effect=RuntimeError("boom"))):
            result = await generate_incident_hypothesis("org/repo", _signals())
        assert result is None
