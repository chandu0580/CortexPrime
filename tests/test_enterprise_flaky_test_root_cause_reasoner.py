from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.enterprise_flaky_test_root_cause_reasoner import (
    build_prompt,
    generate_flaky_hypothesis,
)


class TestBuildPrompt:
    def test_includes_service_and_workflow(self):
        prompt = build_prompt("org/repo", "CI", "evidence here")
        assert "org/repo" in prompt
        assert "CI" in prompt
        assert "evidence here" in prompt


@pytest.mark.asyncio
class TestGenerateFlakyHypothesis:
    async def test_returns_none_when_llm_call_fails(self):
        fake_result = MagicMock(success=False, error="all providers down")
        with patch("backend.llm.llm_router.llm_router.route", new=AsyncMock(return_value=fake_result)):
            hypothesis = await generate_flaky_hypothesis("org/repo", "CI", [])
        assert hypothesis is None

    async def test_returns_none_when_llm_call_raises(self):
        with patch("backend.llm.llm_router.llm_router.route", new=AsyncMock(side_effect=RuntimeError("boom"))):
            hypothesis = await generate_flaky_hypothesis("org/repo", "CI", [])
        assert hypothesis is None

    async def test_returns_hypothesis_text_on_success(self):
        fake_result = MagicMock(success=True, output="Likely a race condition in the parallel test runner.")
        attempt_jobs = [
            {"attempt": 1, "job_name": "backend-tests-parallel", "conclusion": "failure", "failed_steps": ["Run pytest -n4"]},
            {"attempt": 2, "job_name": "backend-tests-parallel", "conclusion": "success", "failed_steps": []},
        ]
        with patch("backend.llm.llm_router.llm_router.route", new=AsyncMock(return_value=fake_result)) as mock_route:
            hypothesis = await generate_flaky_hypothesis("org/repo", "CI", attempt_jobs)

        assert hypothesis == "Likely a race condition in the parallel test runner."
        mock_route.assert_awaited_once()
        _, kwargs = mock_route.call_args
        assert "backend-tests-parallel" in kwargs["prompt"]
        assert kwargs["agent_type"] == "flaky_test_root_cause_reasoner"
